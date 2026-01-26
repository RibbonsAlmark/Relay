import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
from .data_provider import DataManager
from app.config import SCAN_THREAD_COUNT

def process_chunk(chunk_data: List[tuple]) -> Dict[str, int]:
    """
    子线程执行：处理局部数据块，返回该块内每个 source 对应的最小 index。
    这样做避免了在循环中频繁获取全局锁。
    """
    local_results = {}
    for idx, doc in chunk_data:
        # 安全获取嵌套字段
        info = doc.get("info")
        if not info:
            continue
            
        s_id = info.get("source")
        if s_id:
            # 如果 s_id 不在 local_results 中，或者当前 idx 更小，则记录
            if s_id not in local_results or idx < local_results[s_id]:
                local_results[s_id] = idx
    return local_results

def get_global_sources(dataset: str, collection: str, start_index: int = 0, max_workers: int = SCAN_THREAD_COUNT, existing_iter: List[Dict] = None) -> List[Dict[str, Any]]:
    """
    并发扫描数据集提取数据源及其首次出现的帧序号。
    使用多线程分片 (Skip-Limit) 并行拉取，大幅提升初始化速度。
    线程安全策略：Map-Reduce (局部计算，主线程合并)
    """
    logging.info(f"开始扫描数据集 {dataset}/{collection} 以提取 Source Catalog (Parallel Scan, workers={max_workers})...")
    sources_map = {}
    
    try:
        # 1. 获取总数以计算分片
        total_count = DataManager.get_collection_count(dataset, collection)
        if total_count == 0:
            return []

        # 2. 定义分片任务
        def _scan_chunk(chunk_offset: int, chunk_limit: int) -> Dict[str, int]:
            local_map = {}
            try:
                # 只取 info.source
                cursor = DataManager.fetch_frames(
                    dataset, 
                    collection, 
                    skip=chunk_offset,
                    limit=chunk_limit,
                    projection={"info.source": 1}
                )
                for i, doc in enumerate(cursor):
                    s = doc.get("info", {}).get("source")
                    # 记录局部相对索引
                    if s and s not in local_map:
                        local_map[s] = chunk_offset + i
            except Exception as e:
                logging.error(f"Chunk scan failed at {chunk_offset}: {e}")
            return local_map

        # 3. 并发执行
        chunk_size = (total_count + max_workers - 1) // max_workers
        futures = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for i in range(max_workers):
                c_start = i * chunk_size
                if c_start >= total_count:
                    break
                c_limit = min(chunk_size, total_count - c_start)
                futures.append(executor.submit(_scan_chunk, c_start, c_limit))
            
            # 4. 合并结果
            for future in as_completed(futures):
                try:
                    part_map = future.result()
                    for s, idx in part_map.items():
                        # 全局合并：保留最小的 index (即最早出现的)
                        # 注意：这里需要加上外部传入的 start_index 偏移
                        global_idx = idx + start_index
                        if s not in sources_map or global_idx < sources_map[s]:
                            sources_map[s] = global_idx
                except Exception as e:
                    logging.error(f"Worker failed: {e}")

    except Exception as e:
        logging.error(f"Source scan failed: {e}")
        return []

    # 构造结果
    manifest = [
        {"source": s_id, "index": idx}
        for s_id, idx in sources_map.items()
    ]
    manifest.sort(key=lambda x: x["index"])

    logging.info(f"扫描完成，找到 {len(manifest)} 个数据源。")
    return manifest
