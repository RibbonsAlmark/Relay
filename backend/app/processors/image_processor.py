import rerun as rr
import os
import numpy as np
from PIL import Image
from typing import Dict, Any, List
from .base import BaseProcessor

class ImageProcessor(BaseProcessor):
    def process(self, doc: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        payload = {}
        for cam in doc.get('camera', []):
            cam_name = cam.get('name', 'camera')
            is_depth = "depth" in cam_name.lower()
            entity_path = f"world/camera/{cam_name}"
            
            for f in cam.get('frame', []):
                # 1. 处理图像数据
                img_path = f.get('image')
                if img_path and os.path.exists(img_path):
                    try:
                        pil_img = Image.open(img_path)
                        img_array = np.array(pil_img)
                        if is_depth:
                            payload[entity_path] = rr.DepthImage(img_array, meter=1000.0)
                        else:
                            # 压缩动作在这里执行，利用多线程加速
                            payload[entity_path] = rr.Image(img_array).compress(jpeg_quality=85)
                    except Exception as e:
                        print(f"Image error: {e}")

                # 2. 处理标注框
                frame_label = f.get('frame_label', {})
                for source_data in frame_label.values():
                    labels_list = source_data.get('label', [])
                    if labels_list:
                        box_data = self._get_boxes_component(labels_list)
                        if box_data:
                            payload[f"{entity_path}/labels"] = box_data
        return payload

    def _get_boxes_component(self, labels_list: List[Dict[str, Any]]) -> Any:
        centers, sizes, labels = [], [], []
        for item in labels_list:
            pos, size = item.get('position_2d', {}), item.get('size_2d', {})
            centers.append([pos.get('x', 0), pos.get('y', 0)])
            sizes.append([size.get('x', 0), size.get('y', 0)])
            labels.append(f"{item.get('type', 'UNK')} {item.get('confidence', 0):.2f}")
        
        return rr.Boxes2D(centers=centers, sizes=sizes, labels=labels) if centers else None