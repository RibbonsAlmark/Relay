import requests
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.config import BACKEND_PORT

url = f"http://127.0.0.1:{BACKEND_PORT}/list_sessions"

try:
    response = requests.get(url)
    print(f"状态码: {response.status_code}")
    print(f"当前活跃会话: {response.json()}")
except Exception as e:
    print(f"请求失败: {e}")