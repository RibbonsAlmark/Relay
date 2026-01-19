import rerun as rr
import os
import numpy as np
from PIL import Image
import io
from typing import Dict, Any, List, Generator, Tuple, Optional
from .base import BaseProcessor
from app.priority_config import PriorityConfig
from app.config import (
    COLOR_IMG_MAX_WIDTH, 
    COLOR_IMG_QUALITY, 
    DEPTH_IMG_MAX_WIDTH,
    DEPTH_IMG_COMPRESS
)

try:
    import torch
    import torchvision.transforms.functional as TF
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

class ImageProcessor(BaseProcessor):
    is_sequential: bool = False
    priority = PriorityConfig.IMAGE

    def __init__(self):
        # 注册表机制：按顺序测试处理函数
        self.handlers = [
            self._handle_depth_image,
            self._handle_color_image
        ]

    def process(self, doc: Dict[str, Any], **kwargs) -> Generator[Tuple[str, Any], None, None]:
        for cam in doc.get('camera', []):
            cam_name = cam.get('name', 'camera')
            # 这里的 cam_name 如果带 "_color" 后缀，路径就会是 world/camera/camera1_color
            entity_path = f"world/camera/{cam_name}"
            
            # 构造上下文
            context = {
                'name': cam_name,
                'is_depth': "depth" in cam_name.lower()
            }
            
            for f in cam.get('frame', []):
                img_path = f.get('image')
                if img_path and os.path.exists(img_path):
                    try:
                        with Image.open(img_path) as pil_img:
                            # 挨个测试处理函数
                            for handler in self.handlers:
                                component = handler(pil_img, context)
                                if component:
                                    yield entity_path, component
                                    # 如果已被处理（例如识别为深度图），不再尝试后续处理器
                                    break
                                
                    except Exception as e:
                        print(f"[{cam_name}] Image processing error: {e}")

    def _handle_color_image(self, pil_img: Image.Image, context: Dict[str, Any]) -> Optional[rr.EncodedImage]:
        """处理彩色图 (作为通用回退)"""
        # 从配置读取参数
        max_width = COLOR_IMG_MAX_WIDTH
        quality = COLOR_IMG_QUALITY

        # 1. 下采样
        # MAX_WIDTH = 1920
        if pil_img.width > max_width:
            processed_on_gpu = False
            if TORCH_AVAILABLE and torch.cuda.is_available():
                try:
                    # GPU Resize
                    img_tensor = TF.to_tensor(pil_img).to('cuda').unsqueeze(0)
                    scale = max_width / float(pil_img.width)
                    new_height = int(float(pil_img.height) * scale)
                    img_tensor = torch.nn.functional.interpolate(
                        img_tensor, 
                        size=(new_height, max_width), 
                        mode='bilinear', 
                        align_corners=False
                    )
                    pil_img = TF.to_pil_image(img_tensor.squeeze(0).cpu())
                    processed_on_gpu = True
                except Exception as e:
                    print(f"GPU color resize failed: {e}, falling back to CPU")

            if not processed_on_gpu:
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
    
    def _handle_depth_image(self, pil_img: Image.Image, context: Dict[str, Any]) -> Optional[rr.DepthImage]:
        if not context.get('is_depth', False):
            return None
            
        if DEPTH_IMG_COMPRESS:
            # 深度图通常不压缩，直接以原始数组发送
            img_array = np.array(pil_img)
        else:
            """优化深度图：通过大幅下采样减少原始数据量"""
            # 1. 深度图极其占用带宽，强制降采样
            
            processed_on_gpu = False
            img_array = None

            if TORCH_AVAILABLE and torch.cuda.is_available() and pil_img.width > DEPTH_IMG_MAX_WIDTH:
                try:
                    scale = DEPTH_IMG_MAX_WIDTH / float(pil_img.width)
                    new_height = int(float(pil_img.height) * scale)
                    
                    img_arr_in = np.array(pil_img)
                    tensor = torch.from_numpy(img_arr_in).to('cuda')
                    
                    # Ensure dimensions for interpolate (N, C, H, W)
                    if tensor.ndim == 2:
                        tensor = tensor.unsqueeze(0).unsqueeze(0)
                    elif tensor.ndim == 3:
                        tensor = tensor.permute(2, 0, 1).unsqueeze(0)
                    
                    # Interpolate needs float
                    tensor = tensor.float()
                    
                    tensor = torch.nn.functional.interpolate(
                        tensor,
                        size=(new_height, DEPTH_IMG_MAX_WIDTH),
                        mode='nearest'
                    )
                    
                    img_array = tensor.squeeze().cpu().numpy()
                    processed_on_gpu = True
                except Exception as e:
                     print(f"GPU depth resize failed: {e}, falling back to CPU")

            if not processed_on_gpu:
                if pil_img.width > DEPTH_IMG_MAX_WIDTH:
                    scale = DEPTH_IMG_MAX_WIDTH / float(pil_img.width)
                    new_height = int(float(pil_img.height) * scale)
                    # 必须使用 NEAREST 插值，否则会在深度边缘产生无效的中间值
                    pil_img = pil_img.resize((DEPTH_IMG_MAX_WIDTH, new_height), Image.NEAREST)
                
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