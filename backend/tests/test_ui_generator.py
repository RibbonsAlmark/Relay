import os
import sys
from datetime import datetime

# 确保能导入 app 模块
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.rerun_ui_utils import RerunInterfaceHelper

def test_generate_markdown():
    # 1. 模拟一个真实的 doc 数据
    mock_doc = {
        "_id": "/data-platform/users/administrator/upload/ros2bag/zbl/@TEACH_ARM@2025_12_06_13_55_42/camera2_color/1765000544.183081299",
        "info": {
            "name": "/data-platform/users/administrator/upload/ros2bag/zbl/@TEACH_ARM@2025_12_06_13_55_42/camera2_color/1765000544.183081299",
            "timestamp": "1765000544.183081299",
            "clip": "@TEACH_ARM@2025_12_06_13_55_42",
            "source": "/data-platform/users/administrator/upload/ros2bag/zbl/@TEACH_ARM@2025_12_06_13_55_42",
            "meta": {
                "sensor_name": "camera2_color",
                "sensor_type": "camera",
                "left_masks": "/data-platform/users/administrator/upload/masks/@TEACH_ARM@2025_12_06_13_55_42/frame_0000/camera2_mask_obj0.png",
                "left_mesh": "/data-platform/users/administrator/upload/models/zbl/mesh/umi-adjusted.obj",
                "left_k": "/data-platform/users/administrator/upload/models/zbl/cam_K.txt",
                "right_masks": "/data-platform/users/administrator/upload/masks/@TEACH_ARM@2025_12_06_13_55_42/frame_0000/camera2_mask_obj1.jpg",
                "right_mesh": "/data-platform/users/administrator/upload/models/zbl/mesh/umi-adjusted.obj",
                "right_k": "/data-platform/users/administrator/upload/models/zbl/cam_K.txt"
            }
        },
        "camera": [
            {
                "name": "camera2_color",
                "param": {
                    "frame_id": "camera2_color_optical_frame"
                },
                "frame": [
                    {
                        "timestamp": "1765000544.183081299",
                        "image": "/data-platform/users/administrator/upload/ros2bag/zbl/@TEACH_ARM@2025_12_06_13_55_42.parsed/camera2_color/1765000544.183081299.jpg"
                    }
                ]
            },
            {
                "name": "camera1_color",
                "param": {
                    "frame_id": "camera1_color_optical_frame"
                },
                "frame": [
                    {
                        "timestamp": "1765000544.158046143",
                        "image": "/data-platform/users/administrator/upload/ros2bag/zbl/@TEACH_ARM@2025_12_06_13_55_42.parsed/camera1_color/1765000544.158046143.jpg"
                    },
                    {
                        "timestamp": "1765000544.191387939",
                        "image": "/data-platform/users/administrator/upload/ros2bag/zbl/@TEACH_ARM@2025_12_06_13_55_42.parsed/camera1_color/1765000544.191387939.jpg"
                    }
                ]
            },
            {
                "name": "camera1_depth",
                "param": {
                    "frame_id": "camera1_color_optical_frame",
                    "width": 640,
                    "height": 480
                },
                "frame": [
                    {
                        "timestamp": "1765000544.158046143",
                        "image": "/data-platform/users/administrator/upload/ros2bag/zbl/@TEACH_ARM@2025_12_06_13_55_42.parsed/camera1_depth/1765000544.158046143.png"
                    },
                    {
                        "timestamp": "1765000544.191387939",
                        "image": "/data-platform/users/administrator/upload/ros2bag/zbl/@TEACH_ARM@2025_12_06_13_55_42.parsed/camera1_depth/1765000544.191387939.png"
                    }
                ]
            },
            {
                "name": "camera2_depth",
                "param": {
                    "frame_id": "camera2_color_optical_frame",
                    "width": 640,
                    "height": 480
                },
                "frame": [
                    {
                        "timestamp": "1765000544.183081299",
                        "image": "/data-platform/users/administrator/upload/ros2bag/zbl/@TEACH_ARM@2025_12_06_13_55_42.parsed/camera2_depth/1765000544.183081299.png"
                    }
                ]
            },
            {
                "name": "camera3_color",
                "param": {
                    "frame_id": "camera3_color_optical_frame"
                },
                "frame": [
                    {
                        "timestamp": "1765000544.157366943",
                        "image": "/data-platform/users/administrator/upload/ros2bag/zbl/@TEACH_ARM@2025_12_06_13_55_42.parsed/camera3_color/1765000544.157366943.jpg"
                    },
                    {
                        "timestamp": "1765000544.190717041",
                        "image": "/data-platform/users/administrator/upload/ros2bag/zbl/@TEACH_ARM@2025_12_06_13_55_42.parsed/camera3_color/1765000544.190717041.jpg"
                    }
                ]
            },
            {
                "name": "camera3_depth",
                "param": {
                    "frame_id": "camera3_color_optical_frame",
                    "width": 640,
                    "height": 480
                },
                "frame": [
                    {
                        "timestamp": "1765000544.157366943",
                        "image": "/data-platform/users/administrator/upload/ros2bag/zbl/@TEACH_ARM@2025_12_06_13_55_42.parsed/camera3_depth/1765000544.157366943.png"
                    },
                    {
                        "timestamp": "1765000544.190717041",
                        "image": "/data-platform/users/administrator/upload/ros2bag/zbl/@TEACH_ARM@2025_12_06_13_55_42.parsed/camera3_depth/1765000544.190717041.png"
                    }
                ]
            },
            {
                "name": "usb_cam_left",
                "param": {
                    "frame_id": "camera1"
                },
                "frame": [
                    {"timestamp": "1765000543.303930000", "image": "..."},
                    {"timestamp": "1765000544.167893000", "image": "..."}
                ]
            }
        ],
        "joint_state": [
            {
                "name": "left_gripper",
                "param": { "frame_id": "" },
                "frame": [
                    {
                        "timestamp": "1765000544.195000614",
                        "name": [],
                        "position": [-0.009346150911726525],
                        "velocity": [],
                        "effort": []
                    }
                ]
            }
        ],
        "meta": {
            "create_time": "2025-12-17T03:47:33.197000",
            "update_user": "136092213@qq.com",
            "update_time": "2026-01-07T07:07:01.067000",
            "schema_name": "FoundationPoseResultV1",
            "processed_by": "FoundationPose_tracker_v1"
        },
        "camera2_color_pose": {
            "header": {
                "frame_id": "camera2_color/img0001.jpg",
                "stamp": { "secs": 0, "nsecs": 0 }
            },
            "pose": {
                "position": { "x": 0, "y": 0, "z": 0 },
                "orientation": { "x": 0, "y": 0, "z": 0, "w": 1 }
            }
        },
        "pose_estimation": {
            "left": {
                "header": {
                    "frame_id": "left_camera2_color_optical_frame",
                    "stamp": { "secs": 1765000544, "nsecs": 183081388 }
                },
                "pose": {
                    "position": { "x": 0.0032665422186255455, "y": -0.10911841690540314, "z": 0.7075226306915283 },
                    "orientation": { "x": 0.19339752534953636, "y": 0.2214708703207807, "z": 0.6888549528742147, "w": -0.662591053885196 }
                }
            },
            "right": {
                "header": {
                    "frame_id": "right_camera2_color_optical_frame",
                    "stamp": { "secs": 1765000544, "nsecs": 183081388 }
                },
                "pose": {
                    "position": { "x": 0.2568111717700958, "y": 0.00811736285686493, "z": 0.6992560625076294 },
                    "orientation": { "x": 0.39751327846548506, "y": -0.38813369848628815, "z": -0.24944661134939847, "w": 0.7931656911574523 }
                }
            }
        },
        "tag": ["rating:C"],
        "relabel_time": "2026-01-07 15:07:01",
        "comment": "Batch rated via Rerun UI"
    }

    # 2. 调用 Helper 生成 Markdown
    # 模拟环境：backend_host="127.0.0.1:8000", db="test_db", col="test_col"
    markdown_content = RerunInterfaceHelper.generate_frame_panel(
        doc=mock_doc,
        frame_idx=1024,
        backend_host="127.0.0.1:8000",
        src_db="prod_database",
        src_col="lidar_pointcloud_v1"
    )

    # 3. 写入本地文件
    output_path = "preview_rerun_panel.md"
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        
        print(f"✅ 测试成功！Markdown 已生成到: {os.path.abspath(output_path)}")
        print(f"📅 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("\n--- 预览内容片段 ---")
        print("\n".join(markdown_content.split("\n")[:10])) # 只打印前10行
        print("...")
        
    except Exception as e:
        print(f"❌ 写入文件失败: {e}")

if __name__ == "__main__":
    test_generate_markdown()