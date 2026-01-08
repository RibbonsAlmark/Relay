import rerun as rr
from typing import Dict, Any
from .base import BaseProcessor

class PoseProcessor(BaseProcessor):
    def process(self, stream: rr.RecordingStream, doc: Dict[str, Any], **kwargs):
        # 位姿估计 (3D 变换)
        pose_est = doc.get('pose_estimation', {})
        for side in ['left', 'right']:
            data = pose_est.get(side, {}).get('pose')
            if data:
                p, o = data['position'], data['orientation']
                entity_path = f"world/robot/{side}_hand"
                
                # 推送 3D 变换 (平移 + 四元数旋转)
                stream.log(entity_path, rr.Transform3D(
                    translation=[p['x'], p['y'], p['z']],
                    rotation=rr.Quaternion(xyzw=[o['x'], o['y'], o['z'], o['w']])
                ))
                # 在该位置绘制一个坐标轴，方便观察朝向，axis_length 设为 10cm
                stream.log(entity_path, rr.TransformAxes3D(axis_length=0.1))