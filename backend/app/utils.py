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
    估算 Rerun payload (Dict[str, Any]) 的大小（字节）。
    主要关注 numpy array 和 bytes 等大对象，其他对象使用递归估算。
    """
    size = 0
    try:
        if isinstance(payload, dict):
            for k, v in payload.items():
                size += sys.getsizeof(k)
                size += _estimate_value_size(v)
        else:
            size += _estimate_value_size(payload)
    except Exception:
        pass 
    return size

def _estimate_value_size(obj, depth=0) -> int:
    if depth > 3: return 0
    
    if isinstance(obj, (np.ndarray,)):
        return obj.nbytes
    elif hasattr(obj, 'nbytes'): 
        return obj.nbytes
    elif isinstance(obj, (bytes, bytearray)):
        return len(obj)
    elif isinstance(obj, str):
        return len(obj.encode('utf-8'))
    elif isinstance(obj, list):
        if not obj: return 0
        s = 0
        for item in obj:
            s += _estimate_value_size(item, depth+1)
        return s
    
    # 尝试递归计算对象属性（针对 Rerun Archetypes）
    if hasattr(obj, '__dict__'):
        s = sys.getsizeof(obj)
        for v in obj.__dict__.values():
            s += _estimate_value_size(v, depth+1)
        return s
    
    return sys.getsizeof(obj)