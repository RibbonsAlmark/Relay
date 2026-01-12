import requests
import sys
import json
from loguru import logger
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.config import BACKEND_PORT

BASE_URL = f"http://localhost:{BACKEND_PORT}"

def manual_ui_refresh():
    # 1. 检查命令行参数或提示输入
    if len(sys.argv) > 1:
        recording_uuid = sys.argv[1]
    else:
        recording_uuid = input("请输入要刷新的 Session UUID: ").strip()

    if not recording_uuid:
        logger.error("UUID 不能为空")
        return

    # 2. 执行刷新请求
    url = f"{BASE_URL}/refresh_ui/{recording_uuid}"
    logger.info(f"正在请求刷新 UI: {url}")
    
    try:
        response = requests.post(url, timeout=5)
        
        if response.status_code == 200:
            result = response.json()
            logger.success(f"刷新指令已送达！")
            print(json.dumps(result, indent=4, ensure_ascii=False))
            print("\n>>> 请观察 Rerun Viewer，UI 面板应该会立即更新。")
        elif response.status_code == 404:
            logger.error(f"失败: Session {recording_uuid} 不存在或已过期。")
        else:
            logger.error(f"服务器返回错误 ({response.status_code}): {response.text}")
            
    except requests.exceptions.ConnectionError:
        logger.error(f"无法连接到服务器，请确保 {BASE_URL} 已启动。")
    except Exception as e:
        logger.exception(f"发生意外错误: {e}")

if __name__ == "__main__":
    manual_ui_refresh()