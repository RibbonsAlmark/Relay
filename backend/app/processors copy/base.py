import rerun as rr
from typing import Dict, Any

class BaseProcessor:
    """所有处理器的基类"""
    def process(self, stream: rr.RecordingStream, doc: Dict[str, Any], **kwargs):
        raise NotImplementedError