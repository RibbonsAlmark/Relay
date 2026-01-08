import requests

url = "http://127.0.0.1:8000/list_sessions"

try:
    response = requests.get(url)
    print(f"状态码: {response.status_code}")
    print(f"当前活跃会话: {response.json()}")
except Exception as e:
    print(f"请求失败: {e}")