import rerun as rr
import os
import numpy as np
import open3d as o3d
from typing import Dict, Any
from .base import BaseProcessor

class LidarProcessor(BaseProcessor):
    def process(self, doc: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        点云处理：并行解析 PCD 文件并应用高度着色
        """
        payload = {}
        
        for lidar in doc.get('lidar', []):
            lidar_name = lidar.get('name', 'lidar_top')
            entity_path = f"world/lidar/{lidar_name}"
            
            for f in lidar.get('frame', []):
                pcd_path = f.get('point_cloud')
                
                if pcd_path and os.path.exists(pcd_path):
                    try:
                        # 1. IO 操作：加载点云（多线程并行）
                        pcd = o3d.io.read_point_cloud(pcd_path)
                        points = np.asarray(pcd.points)
                        
                        if len(points) == 0:
                            continue

                        # 2. 颜色计算逻辑
                        colors = None
                        if pcd.has_colors():
                            colors = np.asarray(pcd.colors)
                        else:
                            # 按照高度(z轴)映射颜色：Z-axis Height Mapping
                            z_values = points[:, 2]
                            z_min, z_max = np.min(z_values), np.max(z_values)
                            # 归一化并映射从蓝 (Low) 到红 (High)
                            norm_z = (z_values - z_min) / (z_max - z_min + 1e-6)
                            colors = np.zeros((len(points), 3))
                            colors[:, 0] = norm_z          # R
                            colors[:, 2] = 1.0 - norm_z    # B
                        
                        # 3. 将 Rerun 组件存入 Payload
                        payload[entity_path] = rr.Points3D(
                            positions=points,
                            colors=colors,
                            radii=0.02 # 保持你之前的视觉设定
                        )
                        
                    except Exception as e:
                        print(f"[{lidar_name}] PCD Processing Failed: {e}")
                        
        return payload