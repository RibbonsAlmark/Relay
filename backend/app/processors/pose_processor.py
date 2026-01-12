import rerun as rr
from typing import Dict, Any, Generator, Tuple
from .base import BaseProcessor

class PoseProcessor(BaseProcessor):
    def process(self, doc: Dict[str, Any], **kwargs) -> Generator[Tuple[str, Any], None, None]:
        """
        采用原版接口风格，通过 yield 逐个交付组件。
        每个 yield 返回 (entity_path, rerun_component)。
        """
        
        # --- 注册表项 1: 处理 pose_estimation (动态 side) ---
        pose_est = doc.get('pose_estimation')
        if isinstance(pose_est, dict):
            for side, content in pose_est.items():
                if isinstance(content, dict) and 'pose' in content:
                    yield from self._generate_pose_yields(
                        f"world/robot/{side}_hand", 
                        content['pose']
                    )

        # --- 注册表项 2: 处理 camera2_color_pose (特定相机) ---
        cam2_data = doc.get('camera2_color_pose')
        if isinstance(cam2_data, dict) and 'pose' in cam2_data:
            yield from self._generate_pose_yields(
                "world/pose/camera2_color", 
                cam2_data['pose']
            )

    def _generate_pose_yields(self, base_path: str, pose_data: Dict[str, Any]) -> Generator[Tuple[str, Any], None, None]:
        """
        将一个 pose 结构拆解为多个 yield，兼容原版接口。
        """
        try:
            p = pose_data['position']
            o = pose_data['orientation']

            # 1. 交付 Transform3D (主路径)
            # 使用原版习惯的 rr.Transform3D
            yield base_path, rr.Transform3D(
                translation=[p['x'], p['y'], p['z']],
                rotation=rr.Quaternion(xyzw=[o['x'], o['y'], o['z'], o['w']])
            )

            # 2. 交付坐标轴 (子路径 /axes)
            # 这样在 Rerun 树状图中结构清晰，且符合你原版的逻辑
            yield f"{base_path}/axes", rr.TransformAxes3D(axis_length=0.1)

        except (KeyError, TypeError):
            pass