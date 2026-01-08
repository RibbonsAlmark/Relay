from typing import List, Dict
from loguru import logger
from .tagger import TaggerLogic

class RangeTagger:
    @staticmethod
    def process_and_transfer(
        source_docs: List[Dict], 
        start_ts: str, 
        end_ts: str, 
        rating: str
    ) -> List[Dict]:
        """
        核心逻辑：筛选、打标、返回待保存的列表
        """
        t_min, t_max = sorted([start_ts, end_ts])
        
        # 依据时间戳筛选
        affected_docs = [
            doc for doc in source_docs 
            if t_min <= doc.get('info', {}).get('timestamp', '') <= t_max
        ]
        
        # 逐帧打标
        for doc in affected_docs:
            current_tags = doc.get('tag', [])
            doc['tag'] = TaggerLogic.update_rating(current_tags, rating)
            
        return affected_docs