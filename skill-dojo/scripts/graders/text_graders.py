"""
Text Graders - 文本评估器
"""

import re
from typing import Dict, List, Any
from .base import BaseGrader, register_grader


@register_grader
class ContainsGrader(BaseGrader):
    """检查输出是否包含指定文本"""
    
    @property
    def grader_type(self) -> str:
        return "contains"
    
    def evaluate(self, assertion: Dict, output: str, messages: List[Dict]) -> Dict:
        name = assertion.get("name", "contains check")
        value = assertion.get("value", "")
        case_sensitive = assertion.get("case_sensitive", False)
        
        if case_sensitive:
            passed = value in output
        else:
            passed = value.lower() in output.lower()
        
        return {
            "name": name,
            "passed": passed,
            "expected": f"包含: {value[:50]}{'...' if len(value) > 50 else ''}",
            "actual": "找到" if passed else "未找到",
            "evidence": f"搜索 '{value[:30]}' - {'匹配' if passed else '未匹配'}"
        }


@register_grader
class RegexGrader(BaseGrader):
    """正则表达式匹配"""
    
    @property
    def grader_type(self) -> str:
        return "regex"
    
    def evaluate(self, assertion: Dict, output: str, messages: List[Dict]) -> Dict:
        name = assertion.get("name", "regex check")
        pattern = assertion.get("pattern", "")
        flags = re.IGNORECASE if not assertion.get("case_sensitive", False) else 0
        
        try:
            match = re.search(pattern, output, flags)
            passed = match is not None
            actual = match.group(0) if match else None
        except re.error as e:
            return {
                "name": name,
                "passed": False,
                "expected": f"正则: {pattern}",
                "actual": f"正则错误: {e}",
                "evidence": "正则表达式语法错误"
            }
        
        return {
            "name": name,
            "passed": passed,
            "expected": f"正则: {pattern}",
            "actual": actual[:100] if actual else "无匹配",
            "evidence": f"正则匹配结果: {actual[:50] if actual else '无'}"
        }


@register_grader
class CountGteGrader(BaseGrader):
    """计数检查：元素数量 >= N"""
    
    @property
    def grader_type(self) -> str:
        return "count_gte"
    
    def evaluate(self, assertion: Dict, output: str, messages: List[Dict]) -> Dict:
        name = assertion.get("name", "count check")
        pattern = assertion.get("pattern", "")
        min_count = assertion.get("value", 1)
        
        try:
            matches = re.findall(pattern, output, re.IGNORECASE)
            actual_count = len(matches)
            passed = actual_count >= min_count
        except re.error as e:
            return {
                "name": name,
                "passed": False,
                "expected": f">= {min_count}",
                "actual": f"正则错误: {e}",
                "evidence": "正则表达式语法错误"
            }
        
        return {
            "name": name,
            "passed": passed,
            "expected": f">= {min_count}",
            "actual": actual_count,
            "evidence": f"找到 {actual_count} 个匹配项 (期望 >= {min_count})"
        }


@register_grader 
class NotContainsGrader(BaseGrader):
    """检查输出不包含指定文本"""
    
    @property
    def grader_type(self) -> str:
        return "not_contains"
    
    def evaluate(self, assertion: Dict, output: str, messages: List[Dict]) -> Dict:
        name = assertion.get("name", "not contains check")
        value = assertion.get("value", "")
        case_sensitive = assertion.get("case_sensitive", False)
        
        if case_sensitive:
            passed = value not in output
        else:
            passed = value.lower() not in output.lower()
        
        return {
            "name": name,
            "passed": passed,
            "expected": f"不包含: {value[:50]}{'...' if len(value) > 50 else ''}",
            "actual": "未找到" if passed else "找到了",
            "evidence": f"搜索 '{value[:30]}' - {'未找到(正确)' if passed else '找到了(错误)'}"
        }
