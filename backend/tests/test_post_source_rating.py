import requests
import json
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.config import BACKEND_PORT

def test_post_source_rating():
    url = f"http://127.0.0.1:{BACKEND_PORT}/rate_source"
    
    # 根据报错信息，后端需要的字段名是：
    # src_database, src_collection, dst_database, dst_collection, source_name, score
    payload = {
        "src_database": "db_dev",
        "src_collection": "2026-01-04-test",
        "dst_database": "db_dev",     # 通常源和目标是同一个
        "dst_collection": "2026-01-04-test",
        "source_name": "/data-platform/users/administrator/upload/ros2bag/zbl/@TEACH_ARM@2025_12_06_13_55_42",
        "score": "C"
    }
    
    print(f"📡 发起 POST 请求: {url}")
    print(f"📦 提交数据: {json.dumps(payload, indent=2, ensure_ascii=False)}")
    
    try:
        response = requests.post(url, json=payload)
        print(f"⏱ 响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ 成功！")
            print(f"🎉 服务端返回: {response.json()}")
        else:
            print(f"❌ 失败！状态码: {response.status_code}")
            print(f"🔍 错误详情: {response.text}")
            
    except Exception as e:
        print(f"💥 网络请求异常: {e}")

if __name__ == "__main__":
    test_post_source_rating()