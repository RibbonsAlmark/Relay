import rerun as rr
import os
import numpy as np
from PIL import Image
from typing import Dict, Any, List
from .base import BaseProcessor

class ImageProcessor(BaseProcessor):
    def process(self, stream: rr.RecordingStream, doc: Dict[str, Any], **kwargs):
        """
        处理图像及其关联的 2D 标注框
        """
        for cam in doc.get('camera', []):
            cam_name = cam.get('name', 'camera')
            is_depth = "depth" in cam_name.lower()
            entity_path = f"world/camera/{cam_name}"
            
            for f in cam.get('frame', []):
                # 1. 推送图像
                img_path = f.get('image')
                if img_path and os.path.exists(img_path):
                    self._log_image(stream, entity_path, img_path, is_depth)

                # 2. 推送标注框 (如有)
                frame_label = f.get('frame_label', {})
                for source_data in frame_label.values():
                    labels_list = source_data.get('label', [])
                    if labels_list:
                        self._log_boxes(stream, entity_path, labels_list)

    def _log_image(self, stream: rr.RecordingStream, path: str, img_path: str, is_depth: bool):
        try:
            pil_img = Image.open(img_path)
            img_array = np.array(pil_img)
            if is_depth:
                stream.log(path, rr.DepthImage(img_array, meter=1000.0))
            else:
                stream.log(path, rr.Image(img_array).compress(jpeg_quality=85))
        except Exception as e:
            print(f"[{path}] Image error: {e}")

    def _log_boxes(self, stream: rr.RecordingStream, entity_path: str, labels_list: List[Dict[str, Any]]):
        centers = []
        sizes = []
        labels = []

        for item in labels_list:
            pos = item.get('position_2d', {})
            size = item.get('size_2d', {})
            obj_type = item.get('type', 'UNKNOWN')
            conf = item.get('confidence', 0)
            
            centers.append([pos.get('x', 0), pos.get('y', 0)])
            sizes.append([size.get('x', 0), size.get('y', 0)])
            labels.append(f"{obj_type} {conf:.2f}")

        if centers:
            stream.log(
                f"{entity_path}/labels", 
                rr.Boxes2D(
                    centers=centers,
                    sizes=sizes,
                    labels=labels
                )
            )