import rerun as rr
from typing import Dict, Any, Generator, Tuple, List
from .base import BaseProcessor
from app.priority_config import PriorityConfig

class PoseProcessor(BaseProcessor):
    # 【核心标识】标记该 Processor 必须在主流中按顺序同步处理
    is_sequential = True
    priority = PriorityConfig.POSE
    
    def process(self, doc: Dict[str, Any], **kwargs) -> Generator[Tuple[str, Any], None, None]:
        # --- 1. 处理 pose_estimation (支持字典和列表) ---
        pose_est = doc.get('pose_estimation')
        
        if isinstance(pose_est, list):
            # 处理新版列表格式 (包含 name, header, pose)
            for item in pose_est:
                name = item.get('name', 'unknown')
                pose_data = item.get('pose')
                if pose_data:
                    # 将名称中的空格替换为下划线，避免 Rerun 路径解析问题
                    safe_name = name.replace(" ", "_")
                    yield from self._generate_pose_yields(
                        f"world/robot/estimation/{safe_name}", 
                        pose_data
                    )
                    
        elif isinstance(pose_est, dict):
            # 兼容旧版字典格式 {side: {pose: ...}}
            for side, content in pose_est.items():
                if isinstance(content, dict) and 'pose' in content:
                    yield from self._generate_pose_yields(
                        f"world/robot/{side}_hand", 
                        content['pose']
                    )

        # --- 2. 处理 camera2_color_pose (特定项) ---
        cam2_data = doc.get('camera2_color_pose')
        if isinstance(cam2_data, dict) and 'pose' in cam2_data:
            yield from self._generate_pose_yields(
                "world/pose/camera2_color", 
                cam2_data['pose']
            )

    def _generate_pose_yields(self, base_path: str, pose_data: Dict[str, Any]) -> Generator[Tuple[str, Any], None, None]:
        """
        统一生成位姿和坐标轴的 Generator
        """
        try:
            p = pose_data['position']
            o = pose_data['orientation']

            # 1. 交付位姿 (主路径)
            yield base_path, rr.Transform3D(
                translation=[p['x'], p['y'], p['z']],
                rotation=rr.Quaternion(xyzw=[o['x'], o['y'], o['z'], o['w']])
            )

            # 2. 交付坐标轴 (子路径 /axes)
            # 设为 0.1 (10cm) 长度，方便在 3D 视图中观察朝向
            yield f"{base_path}/axes", rr.TransformAxes3D(axis_length=0.1)

        except (KeyError, TypeError):
            # 如果数据缺失部分坐标，跳过当前项
            pass