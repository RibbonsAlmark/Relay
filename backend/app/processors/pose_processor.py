import rerun as rr
from typing import Dict, Any, Generator, Tuple
from .base import BaseProcessor

class PoseProcessor(BaseProcessor):
    def process(self, doc: Dict[str, Any], **kwargs) -> Generator[Tuple[str, Any], None, None]:
        """
        处理位姿数据：流式生成 3D 变换和坐标轴可视化。
        
        Yields:
            Tuple[str, Any]: (entity_path, rerun_component)
        """
        pose_est = doc.get('pose_estimation', {})
        
        for side in ['left', 'right']:
            side_data = pose_est.get(side, {})
            data = side_data.get('pose')
            
            if data:
                p, o = data['position'], data['orientation']
                entity_path = f"world/robot/{side}_hand"
                
                # 1. 产生位姿变换 (主路径)
                yield entity_path, rr.Transform3D(
                    translation=[p['x'], p['y'], p['z']],
                    rotation=rr.Quaternion(xyzw=[o['x'], o['y'], o['z'], o['w']])
                )
                
                # 2. 产生坐标轴 (子路径)
                # 关键：将 axes 挂在 entity_path/axes 下
                # 这样 axes 会自动继承父节点的 Transform3D 变换
                yield f"{entity_path}/axes", rr.TransformAxes3D(axis_length=0.1)