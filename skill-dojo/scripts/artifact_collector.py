"""
Artifact Collector - 交付件收集器

从 Agent 输出中提取可校验的交付件:
- URL: 部署链接、文档链接等
- 文件: 本地生成的文件路径
- 截图: (可选) 对 URL 截图
"""

import os
import re
import urllib.request
import urllib.error
from typing import List, Dict, Optional
from pathlib import Path


class ArtifactCollector:
    """交付件收集器"""
    
    def __init__(self, validate_urls: bool = True, validate_files: bool = True):
        """
        Args:
            validate_urls: 是否验证 URL 可访问性
            validate_files: 是否验证文件存在性
        """
        self.validate_urls = validate_urls
        self.validate_files = validate_files
    
    def collect(self, output: str, extractors: List[Dict]) -> List[Dict]:
        """
        收集交付件
        
        Args:
            output: Agent 输出文本
            extractors: 提取器配置列表
                [
                    {"name": "部署URL", "type": "url", "pattern": "https://..."},
                    {"name": "本地文件", "type": "file", "pattern": "/path/..."}
                ]
                
        Returns:
            交付件列表
        """
        artifacts = []
        
        for extractor in extractors:
            artifact_type = extractor.get("type", "url")
            name = extractor.get("name", "未命名")
            pattern = extractor.get("pattern", "")
            description = extractor.get("description", "")
            
            if artifact_type == "url":
                artifact = self._extract_url(output, name, pattern, description)
            elif artifact_type == "file":
                artifact = self._extract_file(output, name, pattern, description)
            else:
                continue
            
            if artifact:
                artifacts.append(artifact)
        
        return artifacts
    
    def _extract_url(self, output: str, name: str, pattern: str, description: str) -> Optional[Dict]:
        """提取 URL 类型交付件"""
        try:
            matches = re.findall(pattern, output, re.IGNORECASE)
            if not matches:
                return None
            
            # 清理 URL
            url = matches[0] if isinstance(matches[0], str) else matches[0][0]
            url = url.rstrip('.,;:!?)"\'>')
            
            artifact = {
                "type": "url",
                "name": name,
                "value": url,
                "description": description or f"从输出中提取的 URL",
                "valid": True,
                "validation_error": ""
            }
            
            # 验证可访问性
            if self.validate_urls:
                is_valid, error = self._check_url(url)
                artifact["valid"] = is_valid
                artifact["validation_error"] = error
            
            return artifact
            
        except Exception as e:
            return {
                "type": "url",
                "name": name,
                "value": "",
                "description": description,
                "valid": False,
                "validation_error": f"提取失败: {e}"
            }
    
    def _extract_file(self, output: str, name: str, pattern: str, description: str) -> Optional[Dict]:
        """提取文件类型交付件"""
        try:
            matches = re.findall(pattern, output)
            if not matches:
                return None
            
            # 获取完整路径
            file_path = matches[0] if isinstance(matches[0], str) else matches[0][0]
            file_path = os.path.expanduser(file_path)
            
            artifact = {
                "type": "file",
                "name": name,
                "value": file_path,
                "description": description or f"从输出中提取的文件路径",
                "valid": True,
                "validation_error": ""
            }
            
            # 验证存在性
            if self.validate_files:
                if os.path.exists(file_path):
                    if os.path.isfile(file_path):
                        size = os.path.getsize(file_path)
                        artifact["description"] += f" ({size} bytes)"
                    else:
                        artifact["valid"] = False
                        artifact["validation_error"] = "路径是目录而非文件"
                else:
                    artifact["valid"] = False
                    artifact["validation_error"] = "文件不存在"
            
            return artifact
            
        except Exception as e:
            return {
                "type": "file",
                "name": name,
                "value": "",
                "description": description,
                "valid": False,
                "validation_error": f"提取失败: {e}"
            }
    
    def _check_url(self, url: str, timeout: int = 10) -> tuple:
        """
        检查 URL 是否可访问
        
        Returns:
            (is_valid, error_message)
        """
        try:
            req = urllib.request.Request(
                url,
                method='HEAD',
                headers={'User-Agent': 'SkillTestRunner/1.0'}
            )
            with urllib.request.urlopen(req, timeout=timeout) as response:
                if 200 <= response.status < 400:
                    return True, ""
                else:
                    return False, f"HTTP {response.status}"
                    
        except urllib.error.HTTPError as e:
            return False, f"HTTP {e.code}: {e.reason}"
        except urllib.error.URLError as e:
            return False, f"连接失败: {e.reason}"
        except Exception as e:
            return False, str(e)
    
    def collect_with_defaults(self, output: str) -> List[Dict]:
        """
        使用默认提取器收集交付件
        
        自动提取:
        - GitHub Pages URL
        - KIM Docs URL
        - 本地 HTML/MD/JSON 文件
        """
        default_extractors = [
            {
                "name": "GitHub Pages",
                "type": "url",
                "pattern": r"https://[a-zA-Z0-9_-]+\.github\.io/[^\s<>\"']+",
                "description": "部署到 GitHub Pages 的页面"
            },
            {
                "name": "KIM 文档",
                "type": "url",
                "pattern": r"https://docs\.corp\.[^\s<>\"']+",
                "description": "KIM Docs 文档链接"
            },
            {
                "name": "Vercel 部署",
                "type": "url",
                "pattern": r"https://[a-zA-Z0-9_-]+\.vercel\.app[^\s<>\"']*",
                "description": "部署到 Vercel 的页面"
            },
            {
                "name": "本地 HTML",
                "type": "file",
                "pattern": r"/Users/[^\s]+\.html",
                "description": "本地生成的 HTML 文件"
            },
            {
                "name": "本地 Markdown",
                "type": "file",
                "pattern": r"/Users/[^\s]+\.md",
                "description": "本地生成的 Markdown 文件"
            },
            {
                "name": "本地 JSON",
                "type": "file",
                "pattern": r"/Users/[^\s]+\.json",
                "description": "本地生成的 JSON 文件"
            },
        ]
        
        return self.collect(output, default_extractors)


# 便捷函数
def collect_artifacts(output: str, extractors: Optional[List[Dict]] = None) -> List[Dict]:
    """
    收集交付件的便捷函数
    
    Args:
        output: Agent 输出文本
        extractors: 提取器配置列表（可选，为空则使用默认）
        
    Returns:
        交付件列表
    """
    collector = ArtifactCollector()
    
    if extractors:
        return collector.collect(output, extractors)
    else:
        return collector.collect_with_defaults(output)
