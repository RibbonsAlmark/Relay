import rerun as rr
from typing import Dict, Any
from .base import BaseProcessor
from ..rerun_ui_utils import RerunInterfaceHelper
from ..config import BACKEND_HOST

class UIProcessor(BaseProcessor):
    def process(self, doc: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        生成 Markdown 面板：并行生成字符串，不触碰 stream
        """
        # 提取必要的上下文参数
        frame_idx = kwargs.get('frame_idx', 0)
        src_db = kwargs.get('src_db', "")
        src_col = kwargs.get('src_col', "")

        # 1. 核心计算：生成 Markdown 文本（耗时字符串操作在并行线程完成）
        panel_content = RerunInterfaceHelper.generate_frame_panel(
            doc, 
            frame_idx, 
            backend_host=BACKEND_HOST,
            src_db=src_db,
            src_col=src_col
        )
        
        # 2. 返回 Payload，由 Sender 线程统一执行 stream.log
        # 使用 TextDocument 组件，并指定 media_type 为 Markdown
        return {
            "rating_panel": rr.TextDocument(
                panel_content, 
                media_type=rr.MediaType.MARKDOWN
            )
        }