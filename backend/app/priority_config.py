
class PriorityConfig:
    """
    Processor 优先级配置中心
    数值越小，优先级越高 (0 > 10)
    """
    
    # 核心高频数据 (Sequential)
    POSE = 9
    JOINT = 1
    
    # 元数据（帧描述、源信息）
    META = 10
    
    # 耗时传感器数据 (Async)
    LIDAR = 4
    IMAGE = 3

    # 评分UI
    UI = 0
    
    # 默认兜底
    DEFAULT = 10
