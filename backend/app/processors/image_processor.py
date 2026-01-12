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
            is_depth = "depth" in cam_name.lower()
            entity_path = f"world/camera/{cam_name}"
            
            for f in cam.get('frame', []):
                img_path = f.get('image')
                if img_path and os.path.exists(img_path):
                    try:
                        with Image.open(img_path) as pil_img:
                            if is_depth:
                                # 深度图：通常保持原样或转为 uint16 以减小体积
                                img_array = np.array(pil_img)
                                yield entity_path, rr.DepthImage(img_array, meter=1000.0)
                            else:
                                # --- 优化核心：直接传输压缩字节流 ---
                                
                                # 1. 可选：降采样（如果图片太大，比如超过 1080p）
                                if pil_img.width > 1920:
                                    pil_img = pil_img.resize((1280, 720), Image.LANCZOS)
                                
                                # 2. 将 PIL Image 转换为 JPEG 字节流
                                img_byte_arr = io.BytesIO()
                                pil_img.save(img_byte_arr, format='JPEG', quality=75) # 质量 75 是体积/画质平衡点
                                
                                # 使用 EncodedImage 发送
                                component = rr.EncodedImage(contents=img_byte_arr.getvalue())
                                
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