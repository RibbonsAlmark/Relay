import socket
import threading
from typing import Set

class PortManager:
    def __init__(self, start_port: int = 10000, end_port: int = 11000):
        self.start_port = start_port
        self.end_port = end_port
        self.used_ports: Set[int] = set()
        self.lock = threading.Lock()

    def acquire(self) -> int:
        with self.lock:
            for port in range(self.start_port, self.end_port + 1):
                if port not in self.used_ports and self._is_port_available(port):
                    self.used_ports.add(port)
                    return port
            raise RuntimeError("No free ports available.")

    def release(self, port: int):
        with self.lock:
            self.used_ports.discard(port)

    def _is_port_available(self, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) != 0