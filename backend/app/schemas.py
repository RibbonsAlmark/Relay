from pydantic import BaseModel, Field
from typing import Optional

class CreateSourceConfig(BaseModel):
    dataset: str
    collection: str

class SourceResponse(BaseModel):
    status: str
    app_id: str
    recording_uuid: str
    port: int
    connect_url: str

# 1. 定义基础评分配置 (Base Class)
class BaseRateConfig(BaseModel):
    src_database: str      # 来源数据库
    src_collection: str    # 来源数据集
    dst_database: str      # 目标数据库
    dst_collection: str    # 目标数据集
    score: str             # 数据评分
    comment: Optional[str] = None # 可选评语

# 2. 单帧评分配置
class RateFrameConfig(BaseRateConfig):
    frame_id: str          # 数据的唯一 _id

# 3. 全量数据集评分配置
class RateCollectionConfig(BaseRateConfig):
    pass

# 4. 区间评分配置 (依据时间戳逻辑)
class RateRangeConfig(BaseRateConfig):
    start_timestamp: str   # 开始时间戳 (依据 info.timestamp)
    end_timestamp: str     # 结束时间戳 (依据 info.timestamp)

class RateSourceConfig(BaseModel):
    src_database: str
    src_collection: str
    dst_database: str
    dst_collection: str
    source_name: str
    score: str
    comment: str = Field(None, description="备注信息")