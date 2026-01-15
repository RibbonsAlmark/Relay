import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Optional
from .data_provider import DataManager

def get_global_sources(dataset: str, collection: str, start_index: int = 0, max_workers: int = 8) -> List[Dict[str, Any]]:
    """
    多线程预扫描数据集，提取所有数据源名称及其对应的逻辑最小序号。
    """
    # 结果字典和保护它的锁
    source_first_occurrence = {}  # {source_name: first_index_found}
    lock = threading.Lock()
    
    logging.info(f"正在多线程扫描数据集 {dataset}/{collection}，线程数: {max_workers}")

    frames_iter = DataManager.fetch_frames_iter(dataset, collection)

    def process_chunk(chunk_data: List[tuple]):
        """
        处理一小块数据：[(index, doc), (index, doc), ...]
        """
        for idx, doc in chunk_data:
            info = doc.get("info", {})
            s_id = info.get("source")
            
            if s_id:
                with lock:
                    # 只有当发现更小的序号时才更新（针对乱序完成的情况）
                    if s_id not in source_first_occurrence or idx < source_first_occurrence[s_id]:
                        source_first_occurrence[s_id] = idx

    # 使用线程池
    chunk_size = 200  # 每组处理 200 帧，避免锁竞争太频繁
    current_chunk = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for current_idx, doc in enumerate(frames_iter, start=start_index):
            current_chunk.append((current_idx, doc))
            
            if len(current_chunk) >= chunk_size:
                executor.submit(process_chunk, current_chunk)
                current_chunk = [] # 开启新块
        
        # 处理最后一批
        if current_chunk:
            executor.submit(process_chunk, current_chunk)

    # 构造结果
    manifest = [
        {"source": s_id, "index": idx}
        for s_id, idx in source_first_occurrence.items()
    ]
    manifest.sort(key=lambda x: x["index"])

    logging.info(f"多线程扫描完成，发现 {len(manifest)} 个唯一数据源。")
    return manifest