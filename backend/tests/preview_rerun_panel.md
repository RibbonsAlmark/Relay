### Quality Grading (Frame 1024)
**Current Status:**
## `C`

---

### Range Action (Interval Selection)
[ 🚩 Set as Range Start ](javascript:(function(){localStorage.setItem('dp_tagger_range_start', '1765000544.183081299');alert('🚩 Range Start Set: 1765000544.183081299');})())
 &nbsp; | &nbsp; [ 🏁 Set as Range End ](javascript:(function(){localStorage.setItem('dp_tagger_range_end', '1765000544.183081299');alert('🏁 Range End Set: 1765000544.183081299');})())

[ ⚡ **Execute Range Rating (Confirm)** ](javascript:(function(){const s=localStorage.getItem('dp_tagger_range_start');const e=localStorage.getItem('dp_tagger_range_end');if(!s || !e){alert('❌ Please set both Start and End first!');return;}window.open('http://127.0.0.1:8000/quick_rate_range?start='+s+'&end='+e+'&db=prod_database&col=lidar_pointcloud_v1');})())

---

### Batch Action (Rate ALL frames)
[A](http://127.0.0.1:8000/quick_rate_collection?score=A&db=prod_database&col=lidar_pointcloud_v1) &nbsp; | &nbsp; [B](http://127.0.0.1:8000/quick_rate_collection?score=B&db=prod_database&col=lidar_pointcloud_v1) &nbsp; | &nbsp; [C](http://127.0.0.1:8000/quick_rate_collection?score=C&db=prod_database&col=lidar_pointcloud_v1) &nbsp; | &nbsp; [D](http://127.0.0.1:8000/quick_rate_collection?score=D&db=prod_database&col=lidar_pointcloud_v1) &nbsp; | &nbsp; [E](http://127.0.0.1:8000/quick_rate_collection?score=E&db=prod_database&col=lidar_pointcloud_v1) &nbsp; | &nbsp; [F](http://127.0.0.1:8000/quick_rate_collection?score=F&db=prod_database&col=lidar_pointcloud_v1)

---

### Rate this single frame
[A](http://127.0.0.1:8000/quick_rate?frame_id=/data-platform/users/administrator/upload/ros2bag/zbl/%40TEACH_ARM%402025_12_06_13_55_42/camera2_color/1765000544.183081299&score=A&db=prod_database&col=lidar_pointcloud_v1) &nbsp; | &nbsp; [B](http://127.0.0.1:8000/quick_rate?frame_id=/data-platform/users/administrator/upload/ros2bag/zbl/%40TEACH_ARM%402025_12_06_13_55_42/camera2_color/1765000544.183081299&score=B&db=prod_database&col=lidar_pointcloud_v1) &nbsp; | &nbsp; [C](http://127.0.0.1:8000/quick_rate?frame_id=/data-platform/users/administrator/upload/ros2bag/zbl/%40TEACH_ARM%402025_12_06_13_55_42/camera2_color/1765000544.183081299&score=C&db=prod_database&col=lidar_pointcloud_v1) &nbsp; | &nbsp; [D](http://127.0.0.1:8000/quick_rate?frame_id=/data-platform/users/administrator/upload/ros2bag/zbl/%40TEACH_ARM%402025_12_06_13_55_42/camera2_color/1765000544.183081299&score=D&db=prod_database&col=lidar_pointcloud_v1) &nbsp; | &nbsp; [E](http://127.0.0.1:8000/quick_rate?frame_id=/data-platform/users/administrator/upload/ros2bag/zbl/%40TEACH_ARM%402025_12_06_13_55_42/camera2_color/1765000544.183081299&score=E&db=prod_database&col=lidar_pointcloud_v1) &nbsp; | &nbsp; [F](http://127.0.0.1:8000/quick_rate?frame_id=/data-platform/users/administrator/upload/ros2bag/zbl/%40TEACH_ARM%402025_12_06_13_55_42/camera2_color/1765000544.183081299&score=F&db=prod_database&col=lidar_pointcloud_v1)

---

### Frame ID
`/data-platform/users/administrator/upload/ros2bag/zbl/@TEACH_ARM@2025_12_06_13_55_42/camera2_color/1765000544.183081299`

### Source Info
**Database:** `prod_database`  
**Collection:** `lidar_pointcloud_v1`

### Data Preview
```json
{
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
        {
          "timestamp": "1765000543.303930000",
          "image": "..."
        },
        {
          "timestamp": "1765000544.167893000",
          "image": "..."
        }
      ]
    }
  ],
  "joint_state": [
    {
      "name": "left_gripper",
      "param": {
        "frame_id": ""
      },
      "frame": [
        {
          "timestamp": "1765000544.195000614",
          "name": [],
          "position": [
            -0.009346150911726525
          ],
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
      "stamp": {
        "secs": 0,
        "nsecs": 0
      }
    },
    "pose": {
      "position": {
        "x": 0,
        "y": 0,
        "z": 0
      },
      "orientation": {
        "x": 0,
        "y": 0,
        "z": 0,
        "w": 1
      }
    }
  },
  "pose_estimation": {
    "left": {
      "header": {
        "frame_id": "left_camera2_color_optical_frame",
        "stamp": {
          "secs": 1765000544,
          "nsecs": 183081388
        }
      },
      "pose": {
        "position": {
          "x": 0.0032665422186255455,
          "y": -0.10911841690540314,
          "z": 0.7075226306915283
        },
        "orientation": {
          "x": 0.19339752534953636,
          "y": 0.2214708703207807,
          "z": 0.6888549528742147,
          "w": -0.662591053885196
        }
      }
    },
    "right": {
      "header": {
        "frame_id": "right_camera2_color_optical_frame",
        "stamp": {
          "secs": 1765000544,
          "nsecs": 183081388
        }
      },
      "pose": {
        "position": {
          "x": 0.2568111717700958,
          "y": 0.00811736285686493,
          "z": 0.6992560625076294
        },
        "orientation": {
          "x": 0.39751327846548506,
          "y": -0.38813369848628815,
          "z": -0.24944661134939847,
          "w": 0.7931656911574523
        }
      }
    }
  },
  "tag": [
    "rating:C"
  ],
  "relabel_time": "2026-01-07 15:07:01",
  "comment": "Batch rated via Rerun UI"
}
```