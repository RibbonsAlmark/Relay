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
    
    @staticmethod
    def compute_frame_payload(
        doc: Dict[str, Any], 
        frame_idx: int, 
        processor_classes: Optional[List[Type]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        被 ThreadPoolExecutor 调用的核心计算函数。
        
        Args:
            doc: 原始数据字典
            frame_idx: 当前帧索引
            processor_classes: 指定要运行的处理器类列表。若为 None，则运行 DEFAULT_PROCESSOR_CLASSES。
            **kwargs: 传递给处理器的额外参数（如 src_db, src_col）
        """
        # 决定本次计算使用哪些处理器
        target_classes = processor_classes if processor_classes is not None else RerunLogger.DEFAULT_PROCESSOR_CLASSES
        
        frame_payload = {}
        
        for proc_cls in target_classes:
            try:
                # 【关键】动态实例化处理器，确保每个线程拥有独立的处理器对象，线程安全
                processor = proc_cls()
                
                # 迭代 Generator 获取该处理器的所有组件
                results = processor.process(doc, frame_idx=frame_idx, **kwargs)
                for path, component in results:
                    frame_payload[path] = component
                    
            except Exception as e:
                # 使用 loguru 记录错误，比 print 更利于调试
                logger.error(f"Processor {proc_cls.__name__} failed at frame {frame_idx}: {e}")
                
        return frame_payload