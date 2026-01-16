import rerun as rr
import json
from typing import Dict, Any, Generator, Tuple
from .base import BaseProcessor
from app.priority_config import PriorityConfig

class MetaProcessor(BaseProcessor):
    """
    元数据处理器：将原始 doc 完整透传至 Rerun，并附带数据源目录。
    """
    is_sequential = False
    priority = PriorityConfig.META

    def process(self, doc: Dict[str, Any], **kwargs) -> Generator[Tuple[str, Any], None, None]:
        # 1. 处理当前帧的完整 JSON
        doc_json = json.dumps(doc, ensure_ascii=False)
        yield "meta/frame_info", rr.AnyValues(raw_json=doc_json)

        # 2. 获取并处理数据源目录 (source_catalog)
        # 建议从 kwargs 安全获取
        source_catalog = kwargs.get("source_catalog")
        
        if source_catalog is not None:
            catalog_json = json.dumps(source_catalog, ensure_ascii=False)
            yield "meta/source_catalog", rr.TextDocument(catalog_json, media_type="text/json"),