from typing import Dict, Any, Generator, Tuple, Union, List
import rerun as rr

class BaseProcessor:
    """
    所有处理器的基类。
    职责：负责将原始文档(doc)解析并计算为 Rerun 组件，通过生成器流式输出。
    """

    # 核心策略标识：
    # False (默认): 允许进入线程池异步并行处理。
    # True: 必须在主流中按顺序同步处理，保障时序严格一致。
    is_sequential: bool = False

    def process(self, doc: Dict[str, Any], **kwargs) -> Generator[Tuple[str, Union[rr.AsComponents, List[rr.AsComponents]]], None, None]:
        """
        解析逻辑的具体实现。
        
        Yields:
            Tuple[str, Any]: 一个元组，包含：
                - str: Rerun 中的实体路径 (entity_path)
                - Any: 单个组件或组件列表 (用于原子化打包)
        """
        raise NotImplementedError