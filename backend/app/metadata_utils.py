import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
from .data_provider import DataManager

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

def get_global_sources(dataset: str, collection: str, start_index: int = 0, max_workers: int = 8) -> List[Dict[str, Any]]:
    """
    高效扫描数据集，提取所有数据源。
    优化点：
    1. 局部处理减少锁竞争。
    2. 字段过滤（需 DataManager 支持）。
    """
    global_source_map = {}
    logging.info(f"开始扫描数据集 {dataset}/{collection}，并发数: {max_workers}")

    # 关键优化：如果 DataManager 支持 projection，只取 'info.source' 字段
    # 这将减少 90% 以上的网络传输和内存占用
    # 示例假设 fetch_frames_iter 接受 projection 参数
    try:
        frames_iter = DataManager.fetch_frames_iter(
            dataset, 
            collection, 
            projection={"info.source": 1} 
        )
    except TypeError:
        # 降级处理：如果不支持字段过滤，速度会受限于文档大小
        frames_iter = DataManager.fetch_frames_iter(dataset, collection)

    chunk_size = 500  # 适当增大块大小
    current_chunk = []
    futures = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 1. 提交任务
        for current_idx, doc in enumerate(frames_iter, start=start_index):
            current_chunk.append((current_idx, doc))
            
            if len(current_chunk) >= chunk_size:
                futures.append(executor.submit(process_chunk, current_chunk))
                current_chunk = []
        
        if current_chunk:
            futures.append(executor.submit(process_chunk, current_chunk))

        # 2. 合并结果 (在主线程进行，天然线程安全)
        for future in as_completed(futures):
            try:
                local_map = future.result()
                for s_id, idx in local_map.items():
                    if s_id not in global_source_map or idx < global_source_map[s_id]:
                        global_source_map[s_id] = idx
            except Exception as e:
                logging.error(f"处理数据块时出错: {e}")

    # 3. 构造最终结果并排序
    manifest = [
        {"source": s_id, "index": idx}
        for s_id, idx in global_source_map.items()
    ]
    manifest.sort(key=lambda x: x["index"])

    logging.info(f"扫描完成，找到 {len(manifest)} 个数据源。")
    return manifest