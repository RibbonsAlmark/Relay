import rerun as rr
from typing import Dict, Any

class BaseProcessor:
    """所有处理器的基类：仅负责计算并返回数据包"""
    def process(self, doc: Dict[str, Any], **kwargs) -> Dict[str, rr.AsComponents]:
        """
        返回格式: { "entity/path": rerun_component_object }
        """
        raise NotImplementedError