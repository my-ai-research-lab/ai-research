"""
URL Grader - URL 有效性评估器
"""

import re
import urllib.request
import urllib.error
from typing import Dict, List
from .base import BaseGrader, register_grader


@register_grader
class UrlValidGrader(BaseGrader):
    """检查 URL 是否可访问"""
    
    @property
    def grader_type(self) -> str:
        return "url_valid"
    
    def evaluate(self, assertion: Dict, output: str, messages: List[Dict]) -> Dict:
        name = assertion.get("name", "url valid check")
        # 从 assertion 中获取 URL，或从输出中提取
        url = assertion.get("url")
        pattern = assertion.get("extract_pattern", r"https?://[^\s<>\"']+")
        timeout = assertion.get("timeout", 10)
        
        # 如果没有指定 URL，从输出中提取
        if not url:
            matches = re.findall(pattern, output)
            if matches:
                url = matches[0]
            else:
                return {
                    "name": name,
                    "passed": False,
                    "expected": "可访问的 URL",
                    "actual": "未找到 URL",
                    "evidence": f"使用正则 '{pattern}' 未能在输出中找到 URL"
                }
        
        # 清理 URL（移除尾部标点）
        url = url.rstrip('.,;:!?)"\'>')
        
        # 验证 URL 可访问性
        try:
            req = urllib.request.Request(
                url,
                method='HEAD',
                headers={'User-Agent': 'SkillTestRunner/1.0'}
            )
            with urllib.request.urlopen(req, timeout=timeout) as response:
                status_code = response.status
                passed = 200 <= status_code < 400
                
                return {
                    "name": name,
                    "passed": passed,
                    "expected": "HTTP 2xx/3xx",
                    "actual": f"HTTP {status_code}",
                    "evidence": f"URL: {url[:80]}{'...' if len(url) > 80 else ''}"
                }
                
        except urllib.error.HTTPError as e:
            return {
                "name": name,
                "passed": False,
                "expected": "HTTP 2xx/3xx",
                "actual": f"HTTP {e.code}",
                "evidence": f"URL: {url[:60]} - {e.reason}"
            }
        except urllib.error.URLError as e:
            return {
                "name": name,
                "passed": False,
                "expected": "可访问",
                "actual": "连接失败",
                "evidence": f"URL: {url[:60]} - {e.reason}"
            }
        except Exception as e:
            return {
                "name": name,
                "passed": False,
                "expected": "可访问",
                "actual": "验证失败",
                "evidence": f"URL: {url[:60]} - {str(e)}"
            }


@register_grader
class UrlExistsGrader(BaseGrader):
    """检查输出中是否存在 URL（不验证可访问性）"""
    
    @property
    def grader_type(self) -> str:
        return "url_exists"
    
    def evaluate(self, assertion: Dict, output: str, messages: List[Dict]) -> Dict:
        name = assertion.get("name", "url exists check")
        pattern = assertion.get("pattern", r"https?://[^\s<>\"']+")
        
        matches = re.findall(pattern, output)
        passed = len(matches) > 0
        
        # 清理 URL
        urls = [url.rstrip('.,;:!?)"\'') for url in matches]
        
        return {
            "name": name,
            "passed": passed,
            "expected": "至少1个URL",
            "actual": f"找到 {len(urls)} 个",
            "evidence": urls[0][:80] if urls else "无URL"
        }
