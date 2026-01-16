import rerun as rr
from typing import Dict, Any, Generator, Tuple
from .base import BaseProcessor
from app.priority_config import PriorityConfig

class JointProcessor(BaseProcessor):
    # 开启强顺序模式，解决位姿抖动
    is_sequential = False
    priority = PriorityConfig.JOINT

    def process(self, doc: Dict[str, Any], **kwargs) -> Generator[Tuple[str, Any], None, None]:
        """
        处理关节状态数据，并以迭代器形式返回 Rerun 标量组件。
        
        Yields:
            Tuple[str, Any]: (entity_path, rr.Scalars)
        """
        # 关节反馈 (Scalars)
        for js in doc.get('joint_state', []):
            name = js.get('name', 'joint')
            entity_path = f"plots/joints/{name}"
            
            for jf in js.get('frame', []):
                pos = jf.get('position', [])
                if pos:
                    # 按照 Rerun 惯例，标量数据通常映射到时间轴上的曲线
                    # 这里返回第一个值作为标量点
                    yield entity_path, rr.Scalars(pos[0])