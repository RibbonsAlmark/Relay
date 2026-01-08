import rerun as rr
from typing import Dict, Any
from .base import BaseProcessor

class JointProcessor(BaseProcessor):
    def process(self, doc: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        payload = {}
        # 关节反馈 (Scalars)
        for js in doc.get('joint_state', []):
            name = js.get('name', 'joint')
            for jf in js.get('frame', []):
                pos = jf.get('position', [])
                if pos:
                    # 返回数据包，由 Sender 统一推送
                    # 如果 pos 是一个列表，默认取第一个值作为 Scalar 曲线
                    payload[f"plots/joints/{name}"] = rr.Scalars(pos[0])
        return payload