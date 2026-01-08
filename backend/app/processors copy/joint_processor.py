import rerun as rr
from typing import Dict, Any
from .base import BaseProcessor

class JointProcessor(BaseProcessor):
    def process(self, stream: rr.RecordingStream, doc: Dict[str, Any], **kwargs):
        # 关节反馈 (Scalars)
        for js in doc.get('joint_state', []):
            name = js.get('name', 'joint')
            for jf in js.get('frame', []):
                pos = jf.get('position', [])
                if pos:
                    # 将关节位置推送到 plots/ 命名空间下，方便在 Rerun UI 中查看曲线
                    stream.log(f"plots/joints/{name}", rr.Scalars(pos[0]))