import datetime
from typing import Any, Dict, Generator, Optional, List, Tuple, Union
from dp_data_common.client.data_client import DataClient
from loguru import logger
from .logic.tagger import TaggerLogic

class DataManager:
    _client_instance = None
    DB_CONFIG = {
        'host': '101.6.69.214:27018',
        'username': '136092213@qq.com',
        'password': 'HiTSPasiXWHcWrOud5cw5jNNxIvgN1KkaCTfsVvm51k',
    }

    @classmethod
    def batch_relabel_and_save(cls, src_db: str, src_col: str, score: str, target_db: str, target_col: str):
        client = cls.get_client()
        frames = list(cls.fetch_frames_iter(src_db, src_col))
        
        for doc in frames:
            if "_id" in doc: doc.pop("_id")
            
            # 使用统一逻辑更新标签
            doc["tag"] = TaggerLogic.update_score_in_tags(doc.get("tag", []), score)
            doc["update_at"] = datetime.datetime.now().isoformat()

        try:
            client.write(target_db, target_col, frames)
            return len(frames)
        except Exception as e:
            logger.error(f"Batch write failed: {e}")
            raise e
    
    @classmethod
    def get_client(cls):
        if cls._client_instance is None:
            cls._client_instance = DataClient(**cls.DB_CONFIG)
        return cls._client_instance

    @classmethod 
    def get_all_db_collections(cls):
        """获取所有数据库及其对应的集合列表"""
        client = DataManager.get_client()
        result = {}
        exclude_dbs = ['admin', 'config', 'local']
        
        try:
            # DataClient 实例通常持有底层的 pymongo 对象 client.client
            all_dbs = client.client.list_database_names()
            
            for db_name in all_dbs:
                if db_name in exclude_dbs:
                    continue
                try:
                    # 使用 DataClient 提供的 list_collections 方法
                    collections = client.list_collections(db_name)
                    # 过滤掉 MongoDB 内部集合
                    filtered_cols = [c for c in collections if not c.startswith("system.")]
                    result[db_name] = filtered_cols
                except Exception as e:
                    logger.warning(f"无法读取数据库 {db_name} 的集合: {e}")
        except Exception as e:
            logger.error(f"获取数据库列表失败: {e}")
            
        return result

    @staticmethod
    def get_frame_range(database: str, collection: str) -> Tuple[int, int]:
        """
        获取数据集的帧范围 (Start, End)
        目前逻辑简化为：Start=0, End=TotalCount
        """
        client = DataManager.get_client()
        try:
            total_count = client.count(database, collection)
            return 0, total_count
        except Exception as e:
            logger.error(f"Failed to get frame range: {e}")
            return 0, 1000 # Fallback

    @staticmethod
    def fetch_frames(
        database: str, 
        collection: str,
        query: Optional[Dict] = None,
        projection: Optional[Union[List[str], Dict[str, bool]]] = None,
        sort: Optional[List[Tuple[str, int]]] = None,
        skip: Optional[int] = None,
        limit: Optional[int] = None,
        sample_step: Optional[int] = None,
    ) -> Generator[Dict, None, None]:
        """
        通用数据获取接口，支持 DataClient.find 的所有查询参数。
        强制使用流式返回 (stream=True) 并自动清洗数据 (_clean_doc)。

        Args:
            database (str): 数据库名称
            collection (str): 集合名称
            query (Optional[Dict]): 查询条件 (MongoDB 语法), e.g. {"tag.score": "good"}
            projection (Optional[Union[List[str], Dict[str, bool]]]): 字段投影, e.g. {"image": 0} 或 ["timestamp", "pose"]
            sort (Optional[List[Tuple[str, int]]]): 排序规则, e.g. [("timestamp", 1)]
            skip (Optional[int]): 跳过前 N 条数据
            limit (Optional[int]): 限制返回的数据条数
            sample_step (Optional[int]): 采样步长 (每 N 条取 1 条)

        Returns:
            Generator[Dict, None, None]: 清洗后的数据生成器

        Usage:
            # 1. 基础全量
            frames = DataManager.fetch_frames("db", "col")
            
            # 2. 复杂查询 (筛选 + 排序 + 分页)
            frames = DataManager.fetch_frames(
                "db", "col",
                query={"meta.valid": True},
                sort=[("meta.create_time", -1)],
                skip=100,
                limit=50
            )
            
            # 3. 字段过滤 (只取 timestamp)
            frames = DataManager.fetch_frames("db", "col", projection=["timestamp"])
        """
        client = DataManager.get_client()
        try:
            cursor = client.find(
                database=database,
                collection=collection,
                query=query,
                projection=projection,
                sort=sort,
                skip=skip,
                limit=limit,
                sample_step=sample_step,
                stream=True
            )
            for doc in cursor:
                yield DataManager._clean_doc(doc)
        except Exception as e:
            logger.error(f"Database Fetch Error: {e}")

    @staticmethod
    def fetch_frames_iter(database: str, collection: str) -> Generator[Dict, None, None]:
        """全量迭代器 (Wrapper around fetch_frames)"""
        yield from DataManager.fetch_frames(database, collection)

    @staticmethod
    def fetch_frames_range(database: str, collection: str, start: int, end: int) -> Generator[Dict, None, None]:
        """获取指定范围的数据 (Wrapper around fetch_frames)"""
        limit = end - start
        if limit <= 0:
            return
        yield from DataManager.fetch_frames(database, collection, skip=start, limit=limit)

    @staticmethod
    def _clean_doc(doc: Any) -> Any:
        if isinstance(doc, dict):
            return {k: DataManager._clean_doc(v) for k, v in doc.items()}
        elif isinstance(doc, list):
            return [DataManager._clean_doc(i) for i in doc]
        elif isinstance(doc, datetime.datetime):
            return doc.isoformat()
        return doc