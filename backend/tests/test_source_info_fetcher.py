import logging
import json
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.metadata_utils import get_global_sources

# 配置日志，方便看到扫描进度
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def main():
    # --- 配置区域 ---
    # 请根据你数据库中的真实数据进行替换
    TARGET_DATASET = "db_dev" 
    TARGET_COLLECTION = "test_tmp"
    START_IDX = 0
    # ----------------

    try:
        print(f"--- 开始执行真实数据扫描 ---")
        print(f"目标数据集: {TARGET_DATASET}")
        print(f"目标集合: {TARGET_COLLECTION}")

        # 1. 直接调用函数
        manifest = get_global_sources(
            dataset=TARGET_DATASET,
            collection=TARGET_COLLECTION,
            start_index=START_IDX
        )

        # 2. 打印结果摘要
        print(f"\n--- 扫描结果摘要 ---")
        print(f"共发现 {len(manifest)} 个唯一数据源:")
        
        # 格式化打印列表
        for item in manifest:
            print(f"  - Source: {item['source']:<20} | First Index: {item['index']}")

        # 3. 验证输出的 JSON 格式（模拟前端将收到的数据）
        print(f"\n--- JSON 输出序列化测试 ---")
        print(json.dumps(manifest, indent=4, ensure_ascii=False))

    except Exception as e:
        logging.error(f"执行过程中发生异常: {e}", exc_info=True)

if __name__ == "__main__":
    main()