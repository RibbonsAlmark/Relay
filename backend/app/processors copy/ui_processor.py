import rerun as rr
from typing import Dict, Any
from .base import BaseProcessor
from ..rerun_ui_utils import RerunInterfaceHelper
from ..config import BACKEND_HOST

class UIProcessor(BaseProcessor):
    def process(self, stream: rr.RecordingStream, doc: Dict[str, Any], **kwargs):
        panel_content = RerunInterfaceHelper.generate_frame_panel(
            doc, 
            kwargs.get('frame_idx', 0), 
            backend_host=BACKEND_HOST,
            src_db=kwargs.get('src_db', ""),
            src_col=kwargs.get('src_col', "")
        )
        
        # 将面板推送到 rating_panel 路径
        stream.log(
            "rating_panel",
            rr.TextDocument(panel_content, media_type=rr.MediaType.MARKDOWN)
        )