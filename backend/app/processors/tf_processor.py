import rerun as rr
from typing import Dict, Any, Generator, Tuple
from .base import BaseProcessor
from app.priority_config import PriorityConfig

class TransformProcessor(BaseProcessor):
    # 保持与位姿处理一致的优先级，确保在 3D 空间中同步
    is_sequential = True
    priority = PriorityConfig.DEFAULT
    
    def process(self, doc: Dict[str, Any], **kwargs) -> Generator[Tuple[str, Any], None, None]:
        # 获取 transform 列表
        transforms = doc.get('transform', [])
        if not isinstance(transforms, list):
            return

        for item in transforms:
            name = item.get('name', 'unknown')
            frames = item.get('frame', [])
            param = item.get('param', {})
            
            # 获取父级坐标系名称
            parent_frame = param.get('frame_id', 'world')
            
            for frame_data in frames:
                if name == "tf":
                    # --- 处理 tf 类型 ---
                    child_frame = frame_data.get('child_frame_id', 'unknown')
                    trans_data = frame_data.get('transform', {})
                    
                    yield from self._yield_transform(
                        base_path=f"{parent_frame}/{child_frame}",
                        pos=trans_data.get('translation'),
                        ori=trans_data.get('rotation')
                    )
                    
                elif name == "PoseStamped":
                    # --- 处理 PoseStamped 类型 ---
                    # PoseStamped 结构较深：frame -> data -> pose
                    pose_container = frame_data.get('data', {}).get('pose', {})
                    if pose_container:
                        yield from self._yield_transform(
                            base_path=f"{parent_frame}/{name}",
                            pos=pose_container.get('position'),
                            ori=pose_container.get('orientation')
                        )

    def _yield_transform(self, base_path: str, pos: Dict, ori: Dict) -> Generator[Tuple[str, Any], None, None]:
        """
        统一解析位姿并生成 Rerun 组件
        """
        try:
            # 1. 构造位姿组件
            transform = rr.Transform3D(
                translation=[pos['x'], pos['y'], pos['z']],
                rotation=rr.Quaternion(xyzw=[ori['x'], ori['y'], ori['z'], ori['w']])
            )

            # 2. 构造坐标轴组件
            axes = rr.TransformAxes3D(axis_length=0.2)

            # 【关键：合并交付】
            # 在 Rerun 二次开发中，如果你返回一个元组列表或在同一个 entity_path 下 yield 两个 archetype，
            # 必须确保底层 DataStore 接收到了这两者。
            # 建议直接在同一路径下产出这两个对象
            yield base_path, [transform, axes]

        except (KeyError, TypeError):
            pass