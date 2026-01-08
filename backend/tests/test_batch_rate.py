# tests/test_batch_rate.py
import requests
import json

def test_rate_collection():
    url = "http://127.0.0.1:8000/rate_collection"  # 根据你的实际地址修改
    
    payload = {
        "src_database": "db_dev",
        "src_collection": "2026-01-04-test",
        "score": "S",  # 目标评分
        "dst_database": "db_test",
        "dst_collection": "dataset_high_quality",
        "comment": "Batch processed S-rank data"
    }
    
    headers = {
        "Content-Type": "application/json"
    }

    print(f"🚀 正在发送全量评分请求...")
    try:
        response = requests.post(url, data=json.dumps(payload), headers=headers)
        if response.status_code == 200:
            print("✅ 测试通过！")
            print(json.dumps(response.json(), indent=2, ensure_ascii=False))
        else:
            print(f"❌ 测试失败，状态码: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"❌ 发生异常: {e}")

if __name__ == "__main__":
    test_rate_collection()