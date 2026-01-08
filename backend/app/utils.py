import socket

def find_free_port() -> int:
    """扫描并返回一个系统空闲端口"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]