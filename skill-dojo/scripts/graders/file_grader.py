"""
File Grader - 文件存在性评估器
"""

import os
import re
from pathlib import Path
from typing import Dict, List
from .base import BaseGrader, register_grader


@register_grader
class FileExistsGrader(BaseGrader):
    """检查文件是否存在"""
    
    @property
    def grader_type(self) -> str:
        return "file_exists"
    
    def evaluate(self, assertion: Dict, output: str, messages: List[Dict]) -> Dict:
        name = assertion.get("name", "file exists check")
        # 从 assertion 中获取文件路径，或从输出中提取
        file_path = assertion.get("path")
        pattern = assertion.get("extract_pattern", r"/[\w/.-]+\.(html|md|json|py|txt)")
        
        # 如果没有指定路径，从输出中提取
        if not file_path:
            matches = re.findall(pattern, output)
            if matches:
                # 重新匹配完整路径
                full_matches = re.findall(r"/[\w/.-]+\." + matches[0], output)
                if full_matches:
                    file_path = full_matches[0]
            
            if not file_path:
                return {
                    "name": name,
                    "passed": False,
                    "expected": "存在的文件路径",
                    "actual": "未找到文件路径",
                    "evidence": f"使用正则 '{pattern}' 未能在输出中找到文件路径"
                }
        
        # 展开 ~ 路径
        file_path = os.path.expanduser(file_path)
        
        # 检查文件是否存在
        exists = os.path.exists(file_path)
        is_file = os.path.isfile(file_path) if exists else False
        
        if exists and is_file:
            # 获取文件大小
            size = os.path.getsize(file_path)
            size_str = f"{size} bytes" if size < 1024 else f"{size/1024:.1f} KB"
            
            return {
                "name": name,
                "passed": True,
                "expected": "文件存在",
                "actual": f"存在 ({size_str})",
                "evidence": file_path
            }
        elif exists and not is_file:
            return {
                "name": name,
                "passed": False,
                "expected": "文件",
                "actual": "是目录",
                "evidence": file_path
            }
        else:
            return {
                "name": name,
                "passed": False,
                "expected": "文件存在",
                "actual": "不存在",
                "evidence": file_path
            }


@register_grader
class FileContentGrader(BaseGrader):
    """检查文件内容是否包含指定文本"""
    
    @property
    def grader_type(self) -> str:
        return "file_content"
    
    def evaluate(self, assertion: Dict, output: str, messages: List[Dict]) -> Dict:
        name = assertion.get("name", "file content check")
        file_path = assertion.get("path", "")
        contains = assertion.get("contains", "")
        
        file_path = os.path.expanduser(file_path)
        
        if not os.path.exists(file_path):
            return {
                "name": name,
                "passed": False,
                "expected": f"文件包含: {contains[:30]}",
                "actual": "文件不存在",
                "evidence": file_path
            }
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            passed = contains.lower() in content.lower()
            
            return {
                "name": name,
                "passed": passed,
                "expected": f"包含: {contains[:30]}",
                "actual": "找到" if passed else "未找到",
                "evidence": f"文件: {file_path}"
            }
        except Exception as e:
            return {
                "name": name,
                "passed": False,
                "expected": f"文件包含: {contains[:30]}",
                "actual": f"读取错误: {e}",
                "evidence": file_path
            }
