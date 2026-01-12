import requests
import json
from loguru import logger
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.config import BACKEND_PORT

def test_rate_range_api():
    # 1. 配置参数
    BASE_URL = f"http://127.0.0.1:{BACKEND_PORT}"  # 请根据你实际运行的端口修改
    ENDPOINT = "/rate_range"
    
    # 2. 构造符合 RateRangeConfig 的请求体
    # 注意：这里的 timestamp 必须是你原始数据集中 info.timestamp 存在的范围
    payload = {
        "src_database": "db_dev",                  # 来源数据库
        "src_collection": "2026-01-04-test",       # 来源数据集
        "dst_database": "db_test",                 # 目标数据库
        "dst_collection": "rate_range_test",        # 目标数据集
        "score": "A",                              # 评分
        "start_timestamp": "1765000544.183081299", # 开始时间戳
        "end_timestamp": "1765000544.483279785",   # 结束时间戳
    }

    logger.info(f"🚀 发起区间打分测试请求...")
    logger.info(f"数据范围: {payload['start_timestamp']} -> {payload['end_timestamp']}")

    try:
        # 3. 执行 POST 请求
        response = requests.post(
            f"{BASE_URL}{ENDPOINT}", 
            json=payload,
            headers={"Content-Type": "application/json"}
        )

        # 4. 验证响应
        if response.status_code == 200:
            result = response.json()
            logger.success("✅ 接口调用成功!")
            logger.info(f"响应内容: {json.dumps(result, indent=2, ensure_ascii=False)}")
            
            # 校验返回字段
            processed_count = result.get("processed_count", 0)
            if processed_count > 0:
                logger.success(f"📈 成功处理了 {processed_count} 帧数据")
            else:
                logger.warning("分数为 0，请检查时间戳范围是否正确匹配了数据")
        
        elif response.status_code == 422:
            logger.error("❌ 参数校验失败 (Unprocessable Entity)")
            logger.error(f"详情: {response.text}")
        else:
            logger.error(f"❌ 接口报错，状态码: {response.status_code}")
            logger.error(f"错误信息: {response.text}")

    except requests.exceptions.ConnectionError:
        logger.error("❌ 无法连接到服务器，请确保 main.py 正在运行")
    except Exception as e:
        logger.error(f"❌ 测试脚本运行异常: {e}")

if __name__ == "__main__":
    test_rate_range_api()