import requests
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.config import BACKEND_PORT

url = f"http://127.0.0.1:{BACKEND_PORT}/create_source"

# 现在的参数是 dataset 和 collection
payload = {
    "dataset": "db_dev",
    "collection": "2026-01-04-test"
}

try:
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        data = response.json()
        print("✅ 创建成功")
        print(f"Recording UUID: {data['recording_uuid']}")
        print(f"分配端口: {data['port']}")
        print("-" * 30)
        print("请在终端运行以下命令查看数据:")
        print(f"rerun {data['connect_url']}")
        print("-" * 30)
        print(f"提示: 请记下 UUID，稍后运行 02_play.py 时需要用到。")
    else:
        print(f"❌ 创建失败, 状态码: {response.status_code}, 原因: {response.text}")
except Exception as e:
    print(f"请求发生异常: {e}")