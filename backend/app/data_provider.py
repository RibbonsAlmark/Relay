import datetime
from typing import Any, Dict, Generator
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
    def fetch_frames_iter(database: str, collection: str) -> Generator[Dict, None, None]:
        """全量迭代器"""
        client = DataManager.get_client()
        try:
            # limit=None 开启全量获取
            cursor = client.find(database=database, collection=collection, limit=None)
            for doc in cursor:
                yield DataManager._clean_doc(doc)
        except Exception as e:
            print(f"Database Error: {e}")

    @staticmethod
    def _clean_doc(doc: Any) -> Any:
        if isinstance(doc, dict):
            return {k: DataManager._clean_doc(v) for k, v in doc.items()}
        elif isinstance(doc, list):
            return [DataManager._clean_doc(i) for i in doc]
        elif isinstance(doc, datetime.datetime):
            return doc.isoformat()
        return doc