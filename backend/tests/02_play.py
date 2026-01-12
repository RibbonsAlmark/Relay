import requests
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.config import BACKEND_PORT

# 请在此处填入 01_create.py 返回的 recording_uuid
# 你也可以通过 input() 动态输入
recording_uuid = input("请输入要播放的 recording_uuid: ").strip()

url = f"http://127.0.0.1:{BACKEND_PORT}/play_data/{recording_uuid}"

try:
    print(f"正在请求播放会话: {recording_uuid}...")
    response = requests.post(url)
    
    if response.status_code == 200:
        print("🚀 播放指令已下达！请观察 Rerun 查看器。")
        print(f"响应内容: {response.json()}")
    elif response.status_code == 404:
        print("❌ 播放失败: 该 UUID 不存在或已超时回收。")
    else:
        print(f"❌ 播放失败, 状态码: {response.status_code}, 原因: {response.text}")
except Exception as e:
    print(f"请求发生异常: {e}")