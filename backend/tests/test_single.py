import requests
import time
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.config import BACKEND_PORT

BASE_URL = f"http://127.0.0.1:{BACKEND_PORT}"
APP_ID = "test_user_01"

def test_workflow():
    # 1. 创建数据源
    print(f"--- 正在为 {APP_ID} 创建数据源 ---")
    resp = requests.post(f"{BASE_URL}/create_source", json={"app_id": APP_ID})
    if resp.status_code != 200:
        print("创建失败:", resp.text)
        return
    
    data = resp.json()
    port = data["port"]
    url = data["connect_url"]
    print(f"成功分配端口: {port}")
    print(f"请手动运行查看器: rerun {url}")

    # 给用户一点时间启动 Viewer
    print("等待 3 秒后开始播放数据...")
    time.sleep(3)

    # 2. 触发播放
    print(f"--- 开始播放数据 ---")
    play_resp = requests.post(f"{BASE_URL}/play_data/{APP_ID}")
    print("播放接口响应:", play_resp.json())

    # 3. 轮询查看实例是否还在（模拟等待结束）
    print("正在运行模拟...")
    while True:
        check = requests.get(f"{BASE_URL}/list_sessions")
        if APP_ID not in check.json():
            print("模拟结束，资源已自动回收。")
            break
        time.sleep(1)

if __name__ == "__main__":
    test_workflow()