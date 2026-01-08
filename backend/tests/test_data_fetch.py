import sys
import os
import json

# 确保能找到 app 模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.data_provider import DataManager

def inspect_frame(doc):
    print("\n" + "="*50)
    print(f"ID: {doc.get('_id')}")
    info = doc.get('info', {})
    print(f"全局时间戳: {info.get('timestamp')} | 场景: {info.get('clip')}")
    
    # 1. 探测相机模块
    print("\n[相机模块]")
    cameras = doc.get('camera', [])
    for cam in cameras:
        name = cam.get('name')
        frames = cam.get('frame', [])
        ts_list = [f.get('timestamp') for f in frames]
        print(f"  - {name:15} | 帧数: {len(frames)} | 首帧TS: {ts_list[0] if ts_list else 'N/A'}")

    # 2. 探测关节/机械臂反馈
    print("\n[关节状态 (Joint States)]")
    joint_states = doc.get('joint_state', [])
    for js in joint_states:
        name = js.get('name')
        sub_frames = js.get('frame', [])
        if sub_frames:
            last_pos = sub_frames[-1].get('position', [])
            print(f"  - {name:15} | 样本数: {len(sub_frames)} | 最新位置: {last_pos}")

    # 3. 探测算法位姿 (Pose Estimation)
    print("\n[算法位姿 (Pose Estimation)]")
    pose_est = doc.get('pose_estimation', {})
    for side in ['left', 'right']:
        data = pose_est.get(side, {}).get('pose')
        if data:
            pos = data['position']
            ori = data['orientation']
            print(f"  - {side:5} Arm Pos: x={pos['x']:.4f}, y={pos['y']:.4f}, z={pos['z']:.4f}")
            print(f"  - {side:5} Arm Ori: [x:{ori['x']:.3f}, y:{ori['y']:.3f}, z:{ori['z']:.3f}, w:{ori['w']:.3f}]")

    # 4. 探测元数据中的路径
    print("\n[关键元数据路径]")
    meta = info.get('meta', {})
    fields = ['left_masks', 'right_masks', 'left_k']
    for field in fields:
        path = meta.get(field)
        exists = "✅ 存在" if path and os.path.exists(path) else "❌ 不存在/无权限"
        print(f"  - {field:12}: {path} ({exists})")
    print("="*50 + "\n")

def run_inspection():
    REAL_DB = "db_dev" 
    REAL_COL = "2026-01-04-test"
    
    print("正在获取数据...")
    frames = DataManager.fetch_frames(database=REAL_DB, collection=REAL_COL, limit=1)
    
    if frames:
        inspect_frame(frames[0])
        
        # 如果你想看完整的 JSON 结构，取消下面这行的注释
        # print(json.dumps(frames[0], indent=2, ensure_ascii=False))
    else:
        print("未发现数据。")

if __name__ == "__main__":
    run_inspection()