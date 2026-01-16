# import rerun as rr
from typing import Dict, Any, List, Optional, Tuple
from loguru import logger

# 导入具体的处理器类
from .processors.base import BaseProcessor
from .processors.ui_processor import UIProcessor
from .processors.image_processor import ImageProcessor
from .processors.joint_processor import JointProcessor
from .processors.pose_processor import PoseProcessor
from .processors.lidar_processor import LidarProcessor
from .processors.meta_processor import MetaProcessor

class RerunLogger:
    # 存储类引用，而不是实例对象
    DEFAULT_PROCESSOR_CLASSES = [
        UIProcessor,
        ImageProcessor,
        JointProcessor,
        PoseProcessor,
        LidarProcessor,
        MetaProcessor,
    ]
    
    @classmethod
    def compute_sequential_payload(
        cls, doc: Dict[str, Any], frame_idx: int,
        target_processors: Optional[List[BaseProcessor]] = None, **kwargs
    ) -> Tuple[int, Dict[str, Any]]:
        """专门提取需要顺序发送的强时序数据 (is_sequential=True)"""
        return cls._compute_by_filter(doc, frame_idx, True, target_processors, **kwargs)

    @classmethod
    def compute_async_payload(
        cls, doc: Dict[str, Any], frame_idx: int, 
        target_processors: Optional[List[BaseProcessor]] = None, **kwargs
    ) -> Tuple[int, Dict[str, Any]]:
        """专门提取可以异步并行处理的数据 (is_sequential=False)"""
        return cls._compute_by_filter(doc, frame_idx, False, target_processors, **kwargs)

    @classmethod
    def _compute_by_filter(
        cls, doc: Dict[str, Any], frame_idx: int, target_is_seq: bool, 
        target_processors: Optional[List[BaseProcessor]] = None, **kwargs
    ) -> Tuple[int, Dict[str, Any]]:
        """内部通用过滤计算函数"""
        payload = {}
        min_priority = 10  # 默认最低优先级

        if target_processors is None:
            target_processors = cls.DEFAULT_PROCESSOR_CLASSES
            
        for proc_cls in target_processors:
            # 过滤逻辑
            is_seq = getattr(proc_cls, 'is_sequential', False)
            if is_seq != target_is_seq:
                continue
                
            try:
                # 获取优先级并更新最小优先级 (数值越小优先级越高)
                prio = getattr(proc_cls, 'priority', 10)
                if prio < min_priority:
                    min_priority = prio

                processor = proc_cls()
                results = processor.process(doc, frame_idx=frame_idx, **kwargs)
                for path, component in results:
                    payload[path] = component
            except Exception as e:
                logger.error(f"Processor {proc_cls.__name__} failed at frame {frame_idx}: {e}")
        return min_priority, payload