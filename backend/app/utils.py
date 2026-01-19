import socket
import sys
import numpy as np

def find_free_port() -> int:
    """扫描并返回一个系统空闲端口"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

def estimate_payload_size(payload) -> int:
    """
    极速估算 Rerun payload 大小（启发式）。
    避免递归，仅检查顶层组件，大幅降低 CPU 开销。
    """
    size = 0
    if not payload: return 0
    
    try:
        # 只需要遍历顶层 Values
        for v in payload.values():
            # 1. 显式检查 numpy/bytes (图片/Tensor)
            if hasattr(v, 'nbytes'):
                size += v.nbytes
            elif isinstance(v, (bytes, bytearray)):
                size += len(v)
            
            # 2. 检查 Rerun Archetype/Component (通常有 data 属性)
            elif hasattr(v, 'data'):
                d = v.data
                if hasattr(d, 'nbytes'):
                    size += d.nbytes
                elif isinstance(d, (bytes, bytearray)):
                    size += len(d)
                else:
                    size += 200 # 默认小对象
            
            # 3. 列表 (可能是 batch)
            elif isinstance(v, list):
                if v:
                    # 只看第一个元素来粗略估算整个列表
                    first = v[0]
                    est = 100
                    if hasattr(first, 'nbytes'): est = first.nbytes
                    size += est * len(v)
            
            # 4. 其他默认极小
            else:
                size += 100
                
    except Exception:
        # 出错忽略，返回一个非零默认值避免除零等问题
        return 1024
        
    return size

def _estimate_value_size(obj, depth=0) -> int:
    # 保留此函数但不使用，或直接删除。
    # 为保持兼容性暂时保留，但不再被主逻辑调用。
    return 0