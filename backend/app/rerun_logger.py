import rerun as rr
from typing import Dict, Any, List, Type, Optional
from loguru import logger

# 导入具体的处理器类
from .processors.ui_processor import UIProcessor
from .processors.image_processor import ImageProcessor
from .processors.joint_processor import JointProcessor
from .processors.pose_processor import PoseProcessor
from .processors.lidar_processor import LidarProcessor

class RerunLogger:
    # 存储类引用，而不是实例对象
    DEFAULT_PROCESSOR_CLASSES = [
        UIProcessor,
        ImageProcessor,
        JointProcessor,
        PoseProcessor,
        LidarProcessor
    ]
    
    @classmethod
    def compute_sequential_payload(cls, doc: Dict[str, Any], frame_idx: int, **kwargs) -> Dict[str, Any]:
        """专门提取需要顺序发送的强时序数据 (is_sequential=True)"""
        return cls._compute_by_filter(doc, frame_idx, True, **kwargs)

    @classmethod
    def compute_async_payload(cls, doc: Dict[str, Any], frame_idx: int, **kwargs) -> Dict[str, Any]:
        """专门提取可以异步并行处理的数据 (is_sequential=False)"""
        return cls._compute_by_filter(doc, frame_idx, False, **kwargs)

    @classmethod
    def _compute_by_filter(cls, doc: Dict[str, Any], frame_idx: int, target_is_seq: bool, **kwargs) -> Dict[str, Any]:
        """内部通用过滤计算函数"""
        payload = {}
        for proc_cls in cls.DEFAULT_PROCESSOR_CLASSES:
            # 过滤逻辑
            is_seq = getattr(proc_cls, 'is_sequential', False)
            if is_seq != target_is_seq:
                continue
                
            try:
                processor = proc_cls()
                results = processor.process(doc, frame_idx=frame_idx, **kwargs)
                for path, component in results:
                    payload[path] = component
            except Exception as e:
                logger.error(f"Processor {proc_cls.__name__} failed at frame {frame_idx}: {e}")
        return payload