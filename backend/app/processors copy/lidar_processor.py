import rerun as rr
import os
import numpy as np
import open3d as o3d
from typing import Dict, Any
from .base import BaseProcessor

class LidarProcessor(BaseProcessor):
    def process(self, stream: rr.RecordingStream, doc: Dict[str, Any], **kwargs):
        # 遍历 lidar 数组
        for lidar in doc.get('lidar', []):
            lidar_name = lidar.get('name', 'lidar_top')
            entity_path = f"world/lidar/{lidar_name}"
            
            for f in lidar.get('frame', []):
                pcd_path = f.get('point_cloud')
                
                if pcd_path and os.path.exists(pcd_path):
                    try:
                        # 加载点云
                        pcd = o3d.io.read_point_cloud(pcd_path)
                        points = np.asarray(pcd.points)
                        
                        # --- 参考文档后的改进点 ---
                        
                        # 1. 颜色处理：如果 PCD 没颜色，我们可以根据 Z 轴高度自动着色（很实用的可视化技巧）
                        colors = None
                        if pcd.has_colors():
                            colors = np.asarray(pcd.colors)
                        else:
                            # 按照高度(z轴)映射颜色，让点云看起来更有层次感
                            z_values = points[:, 2]
                            z_min, z_max = np.min(z_values), np.max(z_values)
                            # 简单的从蓝到红的映射
                            norm_z = (z_values - z_min) / (z_max - z_min + 1e-6)
                            colors = np.zeros((len(points), 3))
                            colors[:, 0] = norm_z          # R
                            colors[:, 2] = 1.0 - norm_z    # B
                        
                        # 2. 使用 Points3D 及其文档中提到的属性
                        stream.log(
                            entity_path,
                            rr.Points3D(
                                positions=points,      # 对应文档中的 positions
                                colors=colors,         # 对应文档中的 colors
                                radii=0.02,            # 设置点的大小（2cm），文档中提到这是控制视觉效果的关键
                                labels=None,           # 如果有分类信息可以加 label，点云通常不需要
                                class_ids=None         # 暂时不需要分类 ID
                            )
                        )
                    except Exception as e:
                        print(f"[{lidar_name}] PCD 处理失败: {e}")