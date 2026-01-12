import requests
import time
import sys
from app.config import BACKEND_PORT
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = f"http://127.0.0.1:{BACKEND_PORT}" # 根据实际端口修改

def test_session_lifecycle():
    # 1. 创建 Session
    print("--- 步骤 1: 创建 Session ---")
    create_res = requests.post(f"{BASE_URL}/create_source", json={
        "dataset": "test_db",
        "collection": "test_col"
    })
    create_res.raise_for_status()
    data = create_res.json()
    uuid = data["recording_uuid"]
    print(f"创建成功: {uuid}, 端口: {data['port']}")

    # 2. 启动播放
    print("\n--- 步骤 2: 启动播放 ---")
    requests.post(f"{BASE_URL}/play_data/{uuid}").raise_for_status()
    
    # 3. 模拟心跳 (循环 3 次，每次间隔 5 秒)
    print("\n--- 步骤 3: 发送持续心跳 (验证续命) ---")
    for i in range(3):
        hb_res = requests.post(f"{BASE_URL}/heartbeat/{uuid}")
        if hb_res.status_code == 200:
            print(f"心跳 {i+1} 发送成功...")
        else:
            print(f"心跳失败: {hb_res.text}")
            return
        time.sleep(5)

    # 4. 验证 Session 依然存在
    print("\n--- 步骤 4: 检查 Session 状态 ---")
    list_res = requests.get(f"{BASE_URL}/list_sessions").json()
    if uuid in list_res:
        print(f"验证成功: Session {uuid} 依然存活。")
    else:
        print("错误: Session 意外消失！")
        return

    # 5. 模拟超时 (这里为了测试，你可以临时把 core.py 里的 timeout 改小，
    # 或者就在这里等，但测试脚本通常不建议等 180 秒)
    print("\n--- 步骤 5: 停止心跳并等待超时 (测试建议将 timeout 改为 20s 进行验证) ---")
    print("等待超时清理中...")
    
    # 这里我们等待稍微超过 core.py 中定义的 timeout 时间
    # 假设为了测试你把核心代码 timeout 改成了 30
    WAIT_TIME = 35 
    time.sleep(WAIT_TIME)

    # 6. 最终验证
    final_list = requests.get(f"{BASE_URL}/list_sessions").json()
    if uuid not in final_list:
        print("验证成功: Session 已被 monitor 线程清理。")
    else:
        print(f"警告: Session {uuid} 在 {WAIT_TIME}s 后依然存在，请检查 monitor 逻辑。")

if __name__ == "__main__":
    try:
        test_session_lifecycle()
    except Exception as e:
        print(f"测试过程中出错: {e}")