import rerun as rr
import os
import numpy as np
from PIL import Image
import io
from typing import Dict, Any, List, Generator, Tuple
from .base import BaseProcessor

class ImageProcessor(BaseProcessor):
    def process(self, doc: Dict[str, Any], **kwargs) -> Generator[Tuple[str, Any], None, None]:
        for cam in doc.get('camera', []):
            cam_name = cam.get('name', 'camera')
            # 这里的 cam_name 如果带 "_color" 后缀，路径就会是 world/camera/camera1_color
            entity_path = f"world/camera/{cam_name}"
            
            # 判断是否为深度图
            is_depth = "depth" in cam_name.lower()
            
            for f in cam.get('frame', []):
                img_path = f.get('image')
                if img_path and os.path.exists(img_path):
                    try:
                        with Image.open(img_path) as pil_img:
                            if is_depth:
                                # --- 1. 深度图处理 ---
                                img_array = np.array(pil_img)
                                # 深度图通常不压缩，直接以原始数组发送
                                yield entity_path, rr.DepthImage(img_array, meter=1000.0)
                            
                            else:
                                # --- 2. 普通彩色图处理 (优化核心) ---
                                
                                # A. 尺寸检查：如果图片太大（超过 1080p），进行降采样以保证传输流畅
                                if pil_img.width > 1920:
                                    # 保持比例缩小到 720p 级别
                                    new_height = int(pil_img.height * (1280 / pil_img.width))
                                    pil_img = pil_img.resize((1280, new_height), Image.LANCZOS)
                                
                                # B. 转换为 JPEG 字节流
                                img_byte_arr = io.BytesIO()
                                # 质量 75 是体积与清晰度的最佳平衡点
                                pil_img.save(img_byte_arr, format='JPEG', quality=75)
                                img_data = img_byte_arr.getvalue()
                                
                                # C. 构造组件：使用兼容性最强的 EncodedImage
                                # 显式指定 media_type 解决 "Dropping chunk" 和 "AttributeError"
                                component = rr.EncodedImage(
                                    contents=img_data,
                                    media_type="image/jpeg"
                                )
                                
                                yield entity_path, component
                                
                    except Exception as e:
                        print(f"[{cam_name}] Image processing error: {e}")

    def _get_boxes_component(self, labels_list: List[Dict[str, Any]]) -> Any:
        """保持原有逻辑，处理 2D 标注框"""
        centers, sizes, labels = [], [], []
        for item in labels_list:
            pos, size = item.get('position_2d', {}), item.get('size_2d', {})
            centers.append([pos.get('x', 0), pos.get('y', 0)])
            sizes.append([size.get('x', 0), size.get('y', 0)])
            labels.append(f"{item.get('type', 'UNK')} {item.get('confidence', 0):.2f}")
        
        return rr.Boxes2D(centers=centers, sizes=sizes, labels=labels) if centers else None