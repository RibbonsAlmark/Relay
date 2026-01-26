import rerun as rr
from typing import Dict, Any, Generator, Tuple
from loguru import logger
from .base import BaseProcessor
from app.priority_config import PriorityConfig
from ..rerun_ui_utils import RerunInterfaceHelper
from ..config import BACKEND_HOST

class UIProcessor(BaseProcessor):
    # 开启强顺序模式，解决位姿抖动
    is_sequential = False
    priority = PriorityConfig.UI

    def process(self, doc: Dict[str, Any], recording_uuid: str = "", **kwargs) -> Generator[Tuple[str, Any], None, None]:
        """
        生成 Markdown 面板：流式返回 TextDocument 组件。
        
        Yields:
            Tuple[str, Any]: (entity_path, rr.TextDocument)
        """
        if not recording_uuid:
            logger.warning(f"UIProcessor: recording_uuid is missing! Doc ID: {doc.get('_id')}")

        # 提取必要的上下文参数
        frame_idx = kwargs.get('frame_idx', 0)
        src_db = kwargs.get('src_db', "")
        src_col = kwargs.get('src_col', "")
        streaming_mode = kwargs.get('streaming_mode', False)

        # 1. 核心计算：生成 Markdown 文本
        # 注意：复杂的字符串拼接和格式化依然在并行线程中完成

        # --- 1. 生成并 Yield 精简版面板 ---
        panel_content = RerunInterfaceHelper.generate_frame_panel(
            doc, 
            frame_idx, 
            backend_host=BACKEND_HOST,
            src_db=src_db,
            src_col=src_col,
            recording_uuid=recording_uuid,
            streaming_mode=streaming_mode
        )
        
        # 2. 流式返回结果
        if panel_content:
            yield "rating_panel", rr.TextDocument(
                panel_content, 
                media_type=rr.MediaType.MARKDOWN
            )

        # # --- 2. 生成并 Yield Pro版面板 ---
        # panel_content = RerunInterfaceHelper.generate_frame_panel_pro(
        #     doc, 
        #     frame_idx, 
        #     backend_host=BACKEND_HOST,
        #     src_db=src_db,
        #     src_col=src_col,
        #     recording_uuid=recording_uuid
        # )
        
        # # 2. 流式返回结果
        # if panel_content:
        #     yield "rating_panel_pro", rr.TextDocument(
        #         panel_content, 
        #         media_type=rr.MediaType.MARKDOWN
        #     )