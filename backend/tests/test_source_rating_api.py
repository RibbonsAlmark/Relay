import requests

def test_source_api():
    url = "http://127.0.0.1:8000/quick_rate_source"
    payload = {
        "db": "db_dev",
        "col": "2026-01-04-test",
        "source": "/data-platform/users/administrator/upload/ros2bag/zbl/@TEACH_ARM@2025_12_06_13_55_42", 
        "score": "A"
    }
    
    print(f"Testing Source Rating API: {url}")
    response = requests.get(url, params=payload)
    
    if response.status_code == 200:
        print("✅ SUCCESS!")
        # 简单验证返回的 HTML 中是否包含“序列评级完成”字样
        if "序列评级完成" in response.text:
            print("✨ Template rendered correctly.")
    else:
        print(f"❌ FAILED: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    test_source_api()