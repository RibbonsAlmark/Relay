import rerun as rr
import os
import numpy as np
from PIL import Image
import io
from typing import Dict, Any, List, Generator, Tuple
from .base import BaseProcessor
from app.priority_config import PriorityConfig

class ImageProcessor(BaseProcessor):
    is_sequential: bool = False
    priority = PriorityConfig.IMAGE

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
                                # 处理深度图
                                component = self._process_depth_image(pil_img)
                            else:
                                # 处理彩色图
                                component = self._process_color_image(pil_img, 1024, 50)
                            
                            if component:
                                yield entity_path, component
                                
                    except Exception as e:
                        print(f"[{cam_name}] Image processing error: {e}")

    def _process_color_image(self, pil_img: Image.Image, max_width=1920, quality=75) -> rr.EncodedImage:
        """激进压缩彩色图：下采样 + 低质量 JPEG"""
        # 1. 下采样到 1024 宽（流式传输推荐尺寸）
        # MAX_WIDTH = 1920
        if pil_img.width > max_width:
            scale = max_width / float(pil_img.width)
            new_height = int(float(pil_img.height) * scale)
            pil_img = pil_img.resize((max_width, new_height), Image.BILINEAR)
        
        # 2. JPEG 激进压缩
        # 质量 75 是体积与清晰度的最佳平衡点
        # 质量设为 50：体积通常只有 Quality 75 的一半甚至更少
        img_byte_arr = io.BytesIO()
        pil_img.save(img_byte_arr, format='JPEG', quality=quality, optimize=True)
        img_data = img_byte_arr.getvalue()
        
        return rr.EncodedImage(
            contents=img_data,
            media_type="image/jpeg"
        )
    
    def _process_depth_image(self, pil_img: Image.Image, compress=False) -> rr.DepthImage:
        if compress:
            # 深度图通常不压缩，直接以原始数组发送
            img_array = np.array(pil_img)
        else:
            """优化深度图：通过大幅下采样减少原始数据量"""
            # 1. 深度图极其占用带宽，强制降采样到 640 宽（或更低）
            DEPTH_MAX_WIDTH = 640
            if pil_img.width > DEPTH_MAX_WIDTH:
                scale = DEPTH_MAX_WIDTH / float(pil_img.width)
                new_height = int(float(pil_img.height) * scale)
                # 必须使用 NEAREST 插值，否则会在深度边缘产生无效的中间值
                pil_img = pil_img.resize((DEPTH_MAX_WIDTH, new_height), Image.NEAREST)
            
            img_array = np.array(pil_img)
            
            # 2. 确保数据类型为 uint16 以节省空间（相比 float32 减小一半）
            if img_array.dtype != np.uint16:
                # 如果是 float 且单位是米，转为毫米
                if np.issubdtype(img_array.dtype, np.floating):
                    img_array = (img_array * 1000).astype(np.uint16)
                else:
                    img_array = img_array.astype(np.uint16)
        
        return rr.DepthImage(img_array, meter=1000.0)
    
    def _get_boxes_component(self, labels_list: List[Dict[str, Any]]) -> Any:
        """保持原有逻辑，处理 2D 标注框"""
        centers, sizes, labels = [], [], []
        for item in labels_list:
            pos, size = item.get('position_2d', {}), item.get('size_2d', {})
            centers.append([pos.get('x', 0), pos.get('y', 0)])
            sizes.append([size.get('x', 0), size.get('y', 0)])
            labels.append(f"{item.get('type', 'UNK')} {item.get('confidence', 0):.2f}")
        
        return rr.Boxes2D(centers=centers, sizes=sizes, labels=labels) if centers else None