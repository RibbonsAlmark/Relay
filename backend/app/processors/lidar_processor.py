import rerun as rr
import os
import numpy as np
import open3d as o3d
from typing import Dict, Any, Generator, Tuple
from .base import BaseProcessor

class LidarProcessor(BaseProcessor):
    def process(self, doc: Dict[str, Any], **kwargs) -> Generator[Tuple[str, Any], None, None]:
        """
        点云处理：流式解析 PCD 文件。
        处理完一个点云立刻 yield，释放内存中的 points 和 colors 数组。
        """
        for lidar in doc.get('lidar', []):
            lidar_name = lidar.get('name', 'lidar_top')
            entity_path = f"world/lidar/{lidar_name}"
            
            for f in lidar.get('frame', []):
                pcd_path = f.get('point_cloud')
                
                if pcd_path and os.path.exists(pcd_path):
                    try:
                        # 1. IO 操作：加载点云
                        # 注意：o3d 对象本身也占内存，处理完尽量让它超出作用域
                        pcd = o3d.io.read_point_cloud(pcd_path)
                        points = np.asarray(pcd.points)
                        
                        if len(points) == 0:
                            continue

                        # 2. 颜色计算逻辑
                        colors = None
                        if pcd.has_colors():
                            colors = np.asarray(pcd.colors)
                        else:
                            # 按照高度(z轴)映射颜色
                            z_values = points[:, 2]
                            z_min, z_max = np.min(z_values), np.max(z_values)
                            norm_z = (z_values - z_min) / (z_max - z_min + 1e-6)
                            colors = np.zeros((len(points), 3))
                            colors[:, 0] = norm_z          # R
                            colors[:, 2] = 1.0 - norm_z    # B
                        
                        # 3. 立即 Yield Rerun 组件
                        yield entity_path, rr.Points3D(
                            positions=points,
                            colors=colors,
                            radii=0.02
                        )

                        # 手动清理大数组引用（可选，依靠垃圾回收亦可，但显式清理更安全）
                        del points
                        del colors
                        del pcd
                        
                    except Exception as e:
                        print(f"[{lidar_name}] PCD Processing Failed: {e}")