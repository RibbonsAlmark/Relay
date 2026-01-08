import requests
import json

def test_rate_api():
    # 后端地址
    url = "http://127.0.0.1:8000/rate_frame"
    
    # 构建请求体
    payload = {
        "frame_id": "/data-platform/users/administrator/upload/ros2bag/zbl/@TEACH_ARM@2025_12_06_13_55_42/camera2_color/1765000544.183081299",
        "src_database": "db_dev",
        "src_collection": "2026-01-04-test",
        "dst_database": "db_dev",
        "dst_collection": "2026-01-04-test", # 存入目标集合
        "score": "Excellent",                  # 字符串评分
        "comment": "动作完成度极高，无抖动"
    }
    
    print(f"正在测试评分接口...")
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print("✅ 成功！")
            print(json.dumps(response.json(), indent=2, ensure_ascii=False))
        else:
            print(f"❌ 失败！状态码: {response.status_code}")
            print(f"返回信息: {response.text}")
    except Exception as e:
        print(f"网络连接失败: {e}")

if __name__ == "__main__":
    test_rate_api()