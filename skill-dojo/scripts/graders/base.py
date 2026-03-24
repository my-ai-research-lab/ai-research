"""
Base Grader - 评估器基类和注册机制
"""

from typing import Dict, List, Any, Optional
from abc import ABC, abstractmethod

# 评估器注册表
_GRADERS: Dict[str, 'BaseGrader'] = {}


class BaseGrader(ABC):
    """评估器基类"""
    
    @property
    @abstractmethod
    def grader_type(self) -> str:
        """评估器类型名称"""
        pass
    
    @abstractmethod
    def evaluate(self, 
                 assertion: Dict,
                 output: str,
                 messages: List[Dict]) -> Dict:
        """
        执行评估
        
        Args:
            assertion: 断言配置
            output: Agent 输出文本
            messages: 完整消息列表
            
        Returns:
            {
                "name": str,      # 断言名称
                "passed": bool,   # 是否通过
                "actual": Any,    # 实际值
                "expected": Any,  # 期望值
                "evidence": str   # 证据说明
            }
        """
        pass


def register_grader(grader_cls):
    """注册评估器"""
    instance = grader_cls()
    _GRADERS[instance.grader_type] = instance
    return grader_cls


def get_grader(grader_type: str) -> Optional[BaseGrader]:
    """获取评估器"""
    return _GRADERS.get(grader_type)


def run_assertions(assertions: List[Dict], 
                   output: str, 
                   messages: List[Dict]) -> List[Dict]:
    """
    运行所有断言
    
    Args:
        assertions: 断言配置列表
        output: Agent 输出文本
        messages: 完整消息列表
        
    Returns:
        评估结果列表
    """
    results = []
    
    for assertion in assertions:
        grader_type = assertion.get("type", "contains")
        grader = get_grader(grader_type)
        
        if grader:
            result = grader.evaluate(assertion, output, messages)
        else:
            # 未知评估器，默认通过
            result = {
                "name": assertion.get("name", "unknown"),
                "passed": True,
                "evidence": f"未知评估器类型: {grader_type}，已跳过"
            }
        
        results.append(result)
    
    return results


# 延迟导入，确保评估器被注册
def _register_all_graders():
    """注册所有评估器"""
    from . import text_graders
    from . import url_grader
    from . import file_grader


_register_all_graders()
