import rerun as rr
from typing import Dict, Any
from .base import BaseProcessor

class PoseProcessor(BaseProcessor):
    def process(self, doc: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        处理位姿数据：生成 3D 变换和坐标轴可视化
        """
        payload = {}
        pose_est = doc.get('pose_estimation', {})
        
        for side in ['left', 'right']:
            side_data = pose_est.get(side, {})
            data = side_data.get('pose')
            
            if data:
                p, o = data['position'], data['orientation']
                entity_path = f"world/robot/{side}_hand"
                
                # 1. 计算 3D 变换组件
                # 注意：Rerun 默认 Quaternion 顺序为 xyzw，与你数据格式一致
                payload[entity_path] = rr.Transform3D(
                    translation=[p['x'], p['y'], p['z']],
                    rotation=rr.Quaternion(xyzw=[o['x'], o['y'], o['z'], o['w']])
                )
                
                # 2. 计算坐标轴辅助显示组件
                # 注意：在同一个 entity_path 下可以 log 多个 component
                # 但由于我们返回的是字典，同一个 key 只能有一个 value
                # 方案：在 Rerun 中，Transform3D 和 TransformAxes3D 通常建议分层或链式调用
                # 或者在同一个 path 下同时发送多个 components (Rerun 支持在一帧内为同一路径 log 多个组件)
                
                # 为了兼容 Sender 的简单遍历逻辑，我们把坐标轴挂在子路径下，或者直接合并
                payload[f"{entity_path}/axes"] = rr.TransformAxes3D(axis_length=0.1)
                
        return payload