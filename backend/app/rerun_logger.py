import rerun as rr
import threading
from typing import Dict, Any, List
from .processors.ui_processor import UIProcessor
from .processors.image_processor import ImageProcessor
from .processors.joint_processor import JointProcessor
from .processors.pose_processor import PoseProcessor
from .processors.lidar_processor import LidarProcessor

class RerunLogger:
    PROCESSORS = [
        UIProcessor(),
        ImageProcessor(),
        JointProcessor(),
        PoseProcessor(),
        LidarProcessor()
    ]
    
    @staticmethod
    def compute_frame_payload(doc: Dict[str, Any], frame_idx: int, **kwargs) -> Dict[str, Any]:
        """
        这是被 ThreadPoolExecutor 调用的核心函数
        """
        frame_payload = {}
        for processor in RerunLogger.PROCESSORS:
            try:
                # 每一个处理器现在都返回 Dict[str, Any]
                results = processor.process(doc, frame_idx=frame_idx, **kwargs)
                if results:
                    # 将所有组件合并到一个大的 payload 字典中
                    frame_payload.update(results)
            except Exception as e:
                print(f"Processor {processor.__class__.__name__} failed: {e}")
        return frame_payload

# import rerun as rr
# from typing import Dict, Any, List
# from .processors.ui_processor import UIProcessor
# from .processors.image_processor import ImageProcessor
# from .processors.joint_processor import JointProcessor
# from .processors.pose_processor import PoseProcessor
# from .processors.lidar_processor import LidarProcessor

# class RerunLogger:
#     # 静态初始化处理器列表
#     # 将来增加传感器只需在这里 append 一个实例
#     PROCESSORS = [
#         UIProcessor(),
#         ImageProcessor(),
#         JointProcessor(),
#         PoseProcessor(),
#         LidarProcessor(),
#     ]
    
#     @staticmethod
#     def log_frame_to_stream(
#         stream: rr.RecordingStream, 
#         doc: Dict[str, Any], 
#         frame_idx: int,
#         src_db: str = "",
#         src_col: str = ""
#     ):
#         """
#         通过分发逻辑到各个处理器来推送数据
#         """
#         # 1. 设置全局时间轴
#         stream.set_time("frame_idx", sequence=frame_idx)

#         # 2. 调度所有已注册的处理器
#         for processor in RerunLogger.PROCESSORS:
#             try:
#                 processor.process(
#                     stream, 
#                     doc, 
#                     frame_idx=frame_idx, 
#                     src_db=src_db, 
#                     src_col=src_col
#                 )
#             except Exception as e:
#                 # 单个处理器崩溃不影响其他数据展示
#                 print(f"Processor {processor.__class__.__name__} failed: {e}")