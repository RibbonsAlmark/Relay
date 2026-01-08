from ..logic.tagger import TaggerLogic
from ..data_provider import DataManager
import time

class RatingService:
    @staticmethod
    async def rate_by_source(db: str, col: str, source_name: str, score: str, comment: str = None):
        client = DataManager.get_client()
        # 1. 使用 SDK 的查询语法查找同 source 的帧
        query = {"info.source": source_name}
        all_frames = client.find(db, col, query)
        
        if not all_frames:
            return 0

        processed = []
        for frame in all_frames:
            frame["tag"] = TaggerLogic.update_rating(frame.get("tag"), score)
            frame["relabel_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
            if comment:
                frame["comment"] = comment
            processed.append(frame)

        # 2. 批量写入
        if processed:
            batch_size = 100
            for i in range(0, len(processed), batch_size):
                client.write(db, col, processed[i : i + batch_size])
        
        return len(processed)