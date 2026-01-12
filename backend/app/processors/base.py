from typing import Dict, Any, Generator, Tuple
import rerun as rr

class BaseProcessor:
    """
    所有处理器的基类。
    职责：负责将原始文档(doc)解析并计算为 Rerun 组件，通过生成器流式输出。
    """
    
    def process(self, doc: Dict[str, Any], **kwargs) -> Generator[Tuple[str, Any], None, None]:
        """
        解析逻辑的具体实现。
        
        Yields:
            Tuple[str, Any]: 一个元组，包含：
                - str: Rerun 中的实体路径 (entity_path)，例如 "world/camera/left"
                - Any: Rerun 的组件对象，需符合 rr.AsComponents 协议（如 rr.Image, rr.Points3D 等）
        
        Raises:
            NotImplementedError: 子类必须实现此方法。
        """
        raise NotImplementedError