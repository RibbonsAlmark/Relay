import os
import sys
import json
from datetime import datetime

# 将 backend 目录添加到 path 以便导入 app 模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.data_provider import DataManager

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError ("Type %s not serializable" % type(obj))

def main():
    database = "db_test"
    collection = "2026-01-05-17-01-14-foundation-mgsfm-traj-IMU5"
    
    print(f"正在从 {database}.{collection} 获取第一帧数据...")
    
    try:
        # 使用 DataManager.fetch_frames 获取第一帧
        # limit=1 限制只取一条
        frames_gen = DataManager.fetch_frames(database, collection, limit=1)
        
        # 获取生成器的第一个元素
        first_frame = next(frames_gen, None)
        
        if first_frame:
            print("✅ 获取成功！第一帧数据如下：")
            print("-" * 50)
            # 使用 json.dumps 格式化输出，处理 datetime 序列化
            print(json.dumps(first_frame, indent=4, default=json_serial, ensure_ascii=False))
            print("-" * 50)
        else:
            print("⚠️ 集合为空或无法获取数据。")
            
    except Exception as e:
        print(f"❌ 发生错误: {e}")

if __name__ == "__main__":
    main()