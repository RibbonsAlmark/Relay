import rerun as rr
import uuid
import time
import threading
import json
import queue
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from app.metadata_utils import get_global_sources
from typing import Dict, List
from itertools import groupby
from operator import itemgetter
from loguru import logger
import psutil
import os

from .data_provider import DataManager
from .rerun_logger import RerunLogger
from .port_manager import PortManager
from app.config import WORKER_THREAD_MULTIPLIER, BACKPRESSURE_QUEUE_MULTIPLIER, SENDER_THREAD_COUNT, BATCH_BUFFER_SIZE_LIMIT, BATCH_BUFFER_TIMEOUT, SLIDING_WINDOW_CACHE_SIZE
from app.utils import estimate_payload_size

class RerunSession:
    def __init__(self, dataset: str, collection: str, port_manager: PortManager):
        self.dataset = dataset
        self.collection = collection
        self.port_manager = port_manager
        self.app_id = f"{dataset}/{collection}"
        
        # 1. 生成录制 ID
        timestamp_str = time.strftime("%Y%m%d-%H%M%S")
        self.recording_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{self.app_id}/{timestamp_str}"))
        
        self.port = self.port_manager.acquire()
        
        # 2. 状态控制变量
        self.is_playing = False
        self.has_started = False
        self.is_dead = False 
        self.play_lock = threading.Lock()
        self.stop_signal = threading.Event() 
        
        # 2. 并发执行器：处理耗时任务（图像、点云等）
        self.max_workers = (os.cpu_count() or 4) * WORKER_THREAD_MULTIPLIER
        self.process_executor = ThreadPoolExecutor(max_workers=self.max_workers)

        # --- 【背压控制 & 双队列架构】 ---
        # 1. 顺序队列 (Sequential Queue): FIFO, 严格保序, 仅由 1 个发送线程消费
        self.seq_queue = queue.Queue(maxsize=self.max_workers * 2)
        
        # 2. 异步队列 (Async Queue): PriorityQueue, 支持并发发送, 由 SENDER_THREAD_COUNT 个线程消费
        self.async_queue = queue.PriorityQueue(maxsize=self.max_workers * BACKPRESSURE_QUEUE_MULTIPLIER)

        # 3. 对齐队列 (Alignment Queue): 用于存放已合并完整帧的队列
        self.alignment_mode = False
        self.alignment_buffer = {} # {idx: {'seq': ..., 'async': ..., 'count': 0}}
        self.alignment_lock = threading.Lock()
        self.aligned_queue = queue.PriorityQueue(maxsize=self.max_workers * BACKPRESSURE_QUEUE_MULTIPLIER)
        
        self.log_queue_counter = 0  # 用于解决 PriorityQueue 优先级相同时的排序冲突
        self.queue_lock = threading.Lock() # 保护 counter 的线程安全
        self.max_frame_idx = 0 
        self.streaming_mode = False # 是否处于流式模式
        
        self.created_at = time.time()
        self.last_heartbeat = time.time()

        # 3. 启动 Rerun 流
        self.stream = rr.RecordingStream(
            application_id=self.app_id,
            recording_id=self.recording_uuid,
            make_default=False
        )

        # 1. 顺序任务执行器：只有一个 worker，保证任务“先入先出”
        # 所有的 PoseProcessor 任务都提交到这里，它们会排队，绝不超车
        self.seq_executor = ThreadPoolExecutor(max_workers=1)
        

        # 内存限制 10MB
        memory_limit = "10MB"
        self.stream.serve_grpc(grpc_port=self.port, server_memory_limit=memory_limit)

        # 线程锁
        self.log_lock = threading.Lock()

        # 1. Source Catalog 独立线程初始化
        self._source_catalog_cache = []
        self._source_catalog_event = threading.Event()
        
        # 2. Frames Iter 独立线程初始化 (Background Cache)
        self._frames_iter_cache = None
        self._frames_iter_event = threading.Event()

        def _init_frames_iter():
            try:
                t0 = time.time()
                logger.debug(f"[{self.recording_uuid}] 开始后台加载 Frames Cache...")
                cursor = DataManager.fetch_frames_iter(dataset, collection)
                # 全量加载到内存
                self._frames_iter_cache = list(cursor)
                t1 = time.time()
                logger.success(f"[{self.recording_uuid}] Frames Cache 加载完成，共 {len(self._frames_iter_cache)} 帧，耗时 {t1 - t0:.2f}s")
            except Exception as e:
                logger.error(f"[{self.recording_uuid}] Frames Cache Init Failed: {e}")
                self._frames_iter_cache = [] # 失败则置为空列表防崩
            finally:
                self._frames_iter_event.set()
        
        # 启动后台加载线程
        threading.Thread(target=_init_frames_iter, daemon=True).start()
        
        def _init_source_catalog():
            try:
                t0 = time.time()
                logger.debug(f"[{self.recording_uuid}] 开始初始化 Source Catalog (Aggregation)...")
                
                # 使用 Aggregation 直接从 DB 获取，无需遍历所有帧
                result = get_global_sources(
                    dataset=dataset,
                    collection=collection
                )
                json.dumps(result, ensure_ascii=False) = result
                t1 = time.time()
                logger.debug(f"[{self.recording_uuid}] Source Catalog 初始化完成，耗时 {t1 - t0:.2f}s")
                
                # Log source_catalog to frame 0 immediately
                if result:
                    catalog_json = json.dumps(result, ensure_ascii=False)
                    self.stream.set_time("frame_idx", sequence=0)
                    self.stream.log("meta/source_catalog", rr.TextDocument(catalog_json, media_type="text/json"))
                    
            except Exception as e:
                logger.error(f"[{self.recording_uuid}] Source Catalog Init Failed: {e}")
            finally:
                self._source_catalog_event.set()

        threading.Thread(target=_init_source_catalog, daemon=True).start()

        # 2. 时间轴初始化 (Range Markers)
        # 不再预加载所有帧，仅查询总数以设定时间轴范围
        try:
            total_count = DataManager.get_collection_count(dataset, collection)
            if total_count > 0:
                self.stream.set_time("frame_idx", sequence=0)
                self.stream.log("internal/range_marker", rr.TextLog("Start"))
                self.stream.set_time("frame_idx", sequence=total_count - 1)
                self.stream.log("internal/range_marker", rr.TextLog("End"))
                self.max_frame_idx = total_count
        except Exception as e:
            logger.error(f"Failed to set range markers: {e}")


        # 2. 顺序任务重组缓冲区 (Reordering Buffer)
        # 不再使用单线程池，而是通过缓冲区实现并发计算 + 顺序提交
        self.next_seq_idx = 0
        self.seq_buffer = []  # Heapq: (idx, prio, payload)
        self.seq_lock = threading.Lock()
        
        # --- 3. 滑动窗口缓存 (Sliding Window Cache) ---
        # 用于优化 load_range 的连续请求，避免重复查询数据库
        self._recent_frames_cache = OrderedDict()
        self._recent_frames_limit = SLIDING_WINDOW_CACHE_SIZE  # 缓存最近访问的帧 (默认 300)

        # --- 启动消费者线程 (Senders) ---
        # 无论是否处于“播放”状态，消费者线程都必须常驻，以处理 load_range 等按需请求
        self._start_sender_threads()

        logger.info(f"[{self.recording_uuid}] Session initialized on port {self.port} (Limit: {memory_limit})")

    def _start_sender_threads(self):
        """启动所有发送队列的消费者线程"""
        
        # --- B1. 启动顺序发送者 (1 Thread, FIFO) ---
        def seq_sender_loop():
            logger.info(f"[{self.recording_uuid}] Seq Sender Loop (Strict Order) Started")
            local_buffer = {}
            local_count = 0
            local_buffer_size = 0
            last_flush = time.time()
            try:
                while not self.is_dead: # 改为检查 is_dead，只要 Session 活着就一直运行
                    batch_items = []
                    try:
                        # 批量获取以减少锁开销，但必须保证 FIFO
                        try:
                            item = self.seq_queue.get(timeout=0.1)
                            batch_items.append(item)
                            for _ in range(20):
                                batch_items.append(self.seq_queue.get_nowait())
                        except queue.Empty:
                            pass
                        
                        if batch_items:
                            for item in batch_items:
                                idx, payload = item
                                # 估算 payload 大小
                                local_buffer_size += estimate_payload_size(payload)
                                
                                for path, component in payload.items():
                                    if path not in local_buffer: local_buffer[path] = []
                                    local_buffer[path].append((idx, component))
                                    local_count += 1
                                self.seq_queue.task_done()

                        # 检查刷新条件: 大小达标 或 时间超时 或 队列暂时空了
                        now = time.time()
                        if local_count > 0 and (local_buffer_size >= BATCH_BUFFER_SIZE_LIMIT or now - last_flush > BATCH_BUFFER_TIMEOUT or not batch_items):
                            self._flush_batch_buffer(local_buffer)
                            local_count = 0
                            local_buffer_size = 0
                            last_flush = now
                            
                    except Exception as e:
                        logger.error(f"[{self.recording_uuid}] Seq Sender Error: {e}")
            finally:
                # 退出前强制刷新剩余数据
                if local_count > 0:
                    self._flush_batch_buffer(local_buffer)
                logger.info(f"[{self.recording_uuid}] Seq Sender Loop Stopped")

        # --- B2. 启动异步发送者 (N Threads, Parallel) ---
        def async_sender_loop(thread_id, target_queue, queue_name):
            logger.info(f"[{self.recording_uuid}] {queue_name} Sender #{thread_id} Started")
            local_buffer = {}
            local_count = 0
            local_buffer_size = 0
            last_flush = time.time()
            try:
                while not self.is_dead: # 改为检查 is_dead
                    batch_items = []
                    try:
                        # 批量获取
                        try:
                            item = target_queue.get(timeout=0.1)
                            batch_items.append(item)
                            for _ in range(10): 
                                batch_items.append(target_queue.get_nowait())
                        except queue.Empty:
                            pass
                        
                        if batch_items:
                            for item in batch_items:
                                _, idx, _, payload = item
                                # 估算 payload 大小
                                local_buffer_size += estimate_payload_size(payload)
                                
                                for path, component in payload.items():
                                    if path not in local_buffer: local_buffer[path] = []
                                    local_buffer[path].append((idx, component))
                                    local_count += 1
                                target_queue.task_done()
                        
                        # 检查刷新条件
                        now = time.time()
                        if local_count > 0 and (local_buffer_size >= BATCH_BUFFER_SIZE_LIMIT or now - last_flush > BATCH_BUFFER_TIMEOUT or not batch_items):
                            self._flush_batch_buffer(local_buffer)
                            local_count = 0
                            local_buffer_size = 0
                            last_flush = now
                    except Exception as e:
                        logger.error(f"[{self.recording_uuid}] {queue_name} Sender #{thread_id} Error: {e}")
            finally:
                # 退出前强制刷新剩余数据
                if local_count > 0:
                    self._flush_batch_buffer(local_buffer)
                logger.info(f"[{self.recording_uuid}] {queue_name} Sender #{thread_id} Stopped")

        # 启动线程
        threading.Thread(target=seq_sender_loop, daemon=True).start()
        
        # 启动 Async Queue Consumers
        for i in range(SENDER_THREAD_COUNT):
            threading.Thread(target=async_sender_loop, args=(i, self.async_queue, "Async"), daemon=True).start()

        # 启动 Aligned Queue Consumers
        threading.Thread(target=async_sender_loop, args=(0, self.aligned_queue, "Aligned"), daemon=True).start()


    @property
    def frames_iter(self):
        """获取数据流迭代器：优先使用内存缓存，未就绪则直连 DB"""
        if self._frames_iter_cache is not None:
            # 缓存已就绪，返回迭代器
            return iter(self._frames_iter_cache)
        else:
            # 缓存未就绪，直接查询 DB (Fallback)
            return DataManager.fetch_frames_iter(self.dataset, self.collection)

    @property
    def source_catalog(self):
        """懒加载获取 source_catalog，如果未完成则阻塞等待"""
        # 等待初始化线程完成
        self._source_catalog_event.wait()
        return self._source_catalog_cache

    def set_alignment_mode(self, enabled: bool):
        """动态切换对齐模式"""
        logger.info(f"[{self.recording_uuid}] Alignment Mode set to {enabled}")
        self.alignment_mode = enabled

    def _handle_alignment_merge(self, idx, part_type, payload, priority=10):
        """
        [Alignment Mode] 数据汇聚核心逻辑
        等待 seq 和 async 两部分都到达后，合并为一个 Payload 入队
        """
        ready_item = None
        with self.alignment_lock:
            if idx not in self.alignment_buffer:
                self.alignment_buffer[idx] = {'seq': None, 'async': None, 'count': 0, 'prio': priority}
            
            entry = self.alignment_buffer[idx]
            entry[part_type] = payload
            entry['count'] += 1
            
            # 如果是 async 数据，更新优先级（通常 async 带有图像处理的优先级）
            if part_type == 'async':
                entry['prio'] = priority

            # 检查是否收齐 (需要 seq 和 async 各回报一次，共 2 次)
            if entry['count'] >= 2:
                # 合并 Payload
                merged_payload = {}
                if entry['seq']: merged_payload.update(entry['seq'])
                if entry['async']: merged_payload.update(entry['async'])
                
                # 准备入队数据
                prio = entry['prio']
                
                # 清理 Buffer
                del self.alignment_buffer[idx]
                
                # 只有当有数据时才发送
                if merged_payload:
                    ready_item = (prio, merged_payload)

        # 在锁外获取 queue counter 并入队，减少锁竞争
        if ready_item:
            prio, payload = ready_item
            with self.queue_lock:
                count = self.log_queue_counter
                self.log_queue_counter += 1
            self.aligned_queue.put((prio, idx, count, payload))

    def _enqueue_seq(self, idx, payload):
        """顺序数据入队 (FIFO)"""
        # 顺序数据直接入队，不需要 priority/count，因为是 FIFO
        self.seq_queue.put((idx, payload), block=True)

    def _enqueue_async(self, priority, idx, payload):
        """异步数据入队 (Priority)"""
        with self.queue_lock:
            count = self.log_queue_counter
            self.log_queue_counter += 1
        # 结构：(priority, idx, count, payload)
        self.async_queue.put((priority, idx, count, payload), block=True)

    def _try_send_batch(self, path, indices, components):
        """尝试使用 send_columns 进行批量发送"""
        if not hasattr(rr, 'send_columns') or not components:
            return False

        try:
            first = components[0]
            # 统一时间列 - 兼容不同版本
            if hasattr(rr, 'TimeSequenceColumn'):
                time_col = rr.TimeSequenceColumn("frame_idx", indices)
            else:
                time_col = rr.TimeColumn("frame_idx", sequence=indices)

            # 1. Transform3D (PoseProcessor)
            if isinstance(first, rr.Transform3D):
                # [Fix] Transform3D 内部属性提取在不同版本中可能不一致，
                # 为保证顺序数据的绝对正确性，暂时禁用批量发送，回退到标准 log。
                return False
                # translations = [c.translation for c in components]
                # rotations = [c.rotation for c in components]
                # rr.send_columns(
                #     path,
                #     indexes=[time_col],
                #     columns=rr.Transform3D.columns(translation=translations, rotation=rotations)
                # )
                # return True

            # 2. TransformAxes3D (PoseProcessor)
            elif isinstance(first, rr.TransformAxes3D):
                # [Fix] 同上，保证正确性
                return False
                # axis_lengths = [c.axis_length for c in components]
                # rr.send_columns(
                #     path,
                #     indexes=[time_col],
                #     columns=rr.TransformAxes3D.columns(axis_length=axis_lengths)
                # )
                # return True

            # 3. Scalars (JointProcessor)
            elif isinstance(first, rr.Scalars):
                vals = []
                for c in components:
                    s = getattr(c, 'scalars', None)
                    if hasattr(s, '__len__') and len(s) == 1:
                        vals.append(s[0])
                    else:
                        vals.append(s)
                
                rr.send_columns(
                    path,
                    indexes=[time_col],
                    columns=rr.Scalars.columns(scalars=vals)
                )
                return True

            return False

        except Exception as e:
            # logger.warning(f"Batch send failed for {path}: {e}")
            return False

    def heartbeat(self):
        """外部调用此方法续命"""
        self.last_heartbeat = time.time()

    def clear_pending_queues(self):
        """
        [Backpressure] 紧急制动：清空所有待发送队列。
        用于在用户拖拽进度条或重置播放时，丢弃不再需要的陈旧数据。
        """
        logger.warning(f"[{self.recording_uuid}] Clearing all pending queues...")
        
        # 1. 清空顺序队列
        while not self.seq_queue.empty():
            try: self.seq_queue.get_nowait()
            except: break
            
        # 2. 清空异步队列
        while not self.async_queue.empty():
            try: self.async_queue.get_nowait()
            except: break
            
        # 3. 清空对齐队列
        while not self.aligned_queue.empty():
            try: self.aligned_queue.get_nowait()
            except: break
            
        # 4. 清空对齐缓冲区
        with self.alignment_lock:
            self.alignment_buffer.clear()
            
        logger.info(f"[{self.recording_uuid}] Queues cleared.")

    def send_sentinel_frame(self, frame_idx: int):
        """
        发送一个“哨兵帧”（Sentinel Frame）。
        这是一个仅包含时间戳的空帧，用于通知前端 Rerun Viewer 强制刷新时间轴，
        或者作为一个明确的信号表明“在此之前的数据已作废”。
        """
        try:
            self.stream.set_time("frame_idx", sequence=0)
            self.stream.log("internal/range_marker", rr.TextLog("Start"))
            self.stream.set_time("frame_idx", sequence=self.max_frame_idx - 1)
            self.stream.log("internal/range_marker", rr.TextLog("End"))
            self.stream.set_time("frame_idx", sequence=0)
            self.stream.log("meta/source_catalog", rr.TextDocument(json.dumps(json.dumps(result, ensure_ascii=False), ensure_ascii=False), media_type="text/json"))
        except Exception as e:
            logger.error(f"[{self.recording_uuid}] Failed to send sentinel frame: {e}")

    def push_frames(self, frames: list, start_idx: int = 0):
        """
        对外数据推送接口：支持历史覆盖、增量追加与精确插入。
        
        该接口具备“背压感知”功能。若队列填满，调用线程将阻塞直至空间释放，确保数据不丢失。
        
        Args:
            frames (list): 待发送的原始数据帧列表。
            start_idx (int): 插入起始索引。
                - 0 : 从时间轴起点开始（默认）。
                - n : 从第 n 帧开始。
                - -1: 从当前已知的末尾追加（Last + 1）。
                - -n: 从末尾向前偏移（例如 -2 代表从倒数第二帧位置开始覆盖）。

        Returns:
            bool: 推送任务是否成功进入管道。
        """
        t0 = time.time()
        if self.is_dead:
            logger.warning(f"[{self.recording_uuid}] 尝试向已销毁的 Session 推送数据")
            return False

        # --- 1. 索引逻辑转换 (Pythonic Indexing) ---
        with self.play_lock:
            if start_idx >= 0:
                # 绝对位置
                base_idx = start_idx
            else:
                # 负数索引逻辑：-1 为末尾追加，-2 为倒数第二帧偏移
                base_idx = max(0, self.max_frame_idx + start_idx + 1)
            
            # 更新逻辑指针
            count = len(frames)
            if base_idx + count > self.max_frame_idx:
                self.max_frame_idx = base_idx + count

        # --- 2. 异步任务定义 (生产者) ---
        def _async_task(frame_data, idx):
            # 及时检查生命周期，防止无效计算
            if self.is_dead or self.stop_signal.is_set():
                return
            try:
                # 执行耗时的 Processor 计算（在独立的工作线程中并行）
                payload = RerunLogger.compute_frame_payload(
                    frame_data, idx, 
                    src_db=self.dataset, src_col=self.collection,
                    recording_uuid=self.recording_uuid,
                )
                # 阻塞入队：实现背压的核心
                # 优先级 10 (低)
                self._enqueue_payload(10, idx, payload)
            except Exception as e:
                logger.error(f"Async Task Error at frame {idx}: {e}")

        # --- 3. 提交至常驻线程池 ---
        # 瞬间提交所有帧，不阻塞主线程，实现 I/O 与计算的分离
        try:
            # 获取当前模式快照，确保同一帧的任务处理逻辑一致
            use_alignment = self.alignment_mode
            submit_start = time.time()

            for i, frame_data in enumerate(frames):
                idx = base_idx + i
                
                # --- 分支 A: 顺序支流 ---
                # 仅仅是提交任务，瞬间完成，不阻塞读取
                self.seq_executor.submit(self._seq_task_handler, frame_data, idx, use_alignment)

                # --- 分支 B: 异步支流 ---
                # 依然由多线程池全速计算图像
                self.process_executor.submit(self._async_task_handler, frame_data, idx, use_alignment)
            
            submit_end = time.time()
            if len(frames) > 100: # 仅在批量较大时打印
                 logger.debug(f"[{self.recording_uuid}] push_frames 提交 {len(frames)} 帧耗时: {submit_end - submit_start:.3f}s (Total overhead: {submit_end - t0:.3f}s)")
            return True
        except Exception as e:
            logger.error(f"[{self.recording_uuid}] 异步任务提交失败: {e}")
            return False

    def load_range(self, start_idx: int, end_idx: int):
        """
        加载指定范围的数据并发送（支持重载或初次加载）
        Hybrid Mode: 如果全量缓存已就绪，直接从内存切片；否则走 LRU + DB 增量拉取。
        """
        t0 = time.time()
        if self.is_dead:
            return

        # --- A. 快速路径：全量缓存已就绪 ---
        if self._frames_iter_cache is not None:
            try:
                # 直接内存切片，速度极快
                # 注意范围越界处理
                safe_end = min(end_idx, len(self._frames_iter_cache))
                safe_start = min(start_idx, safe_end)
                
                final_frames = self._frames_iter_cache[safe_start:safe_end]
                
                if not final_frames:
                    logger.warning(f"[{self.recording_uuid}] [Cache] No data found for range [{start_idx}, {end_idx})")
                    return

                # 推送数据
                self.push_frames(final_frames, start_idx=start_idx)
                logger.debug(f"[{self.recording_uuid}] [Cache] load_range hit memory cache, cost {time.time() - t0:.3f}s")
                return
            except Exception as e:
                logger.error(f"[{self.recording_uuid}] [Cache] load_range failed: {e}")
                return

        # --- B. 慢速路径：流式 + LRU 缓存 ---
        logger.info(f"[{self.recording_uuid}] [Streaming] Loading range [{start_idx}, {end_idx})...")
        
        try:
            fetch_start = time.time()
            
            # --- 1. 计算缺失区间 ---
            needed_indices = range(start_idx, end_idx)
            missing_indices = [idx for idx in needed_indices if idx not in self._recent_frames_cache]
            
            # --- 2. 增量拉取缺失数据 ---
            if missing_indices:
                # 将离散的缺失索引合并为连续区间，减少 DB 查询次数
                # e.g. [100, 101, 105, 106] -> [(100, 102), (105, 107)]
                ranges_to_fetch = []
                for k, g in groupby(enumerate(missing_indices), lambda ix: ix[0] - ix[1]):
                    group = list(map(itemgetter(1), g))
                    ranges_to_fetch.append((group[0], group[-1] + 1))
                
                logger.debug(f"[{self.recording_uuid}] Cache miss: {len(missing_indices)} frames. Fetching {len(ranges_to_fetch)} chunks...")
                
                for r_start, r_end in ranges_to_fetch:
                    new_chunk = list(DataManager.fetch_frames_range(
                        self.dataset, 
                        self.collection, 
                        start=r_start, 
                        end=r_end
                    ))
                    # 更新缓存
                    for i, frame in enumerate(new_chunk):
                        self._recent_frames_cache[r_start + i] = frame
            
            fetch_end = time.time()
            
            # --- 3. 组装完整数据 & 维护 LRU ---
            final_frames = []
            for idx in needed_indices:
                if idx in self._recent_frames_cache:
                    frame = self._recent_frames_cache[idx]
                    final_frames.append(frame)
                    # LRU: 标记为最近使用 (移到末尾)
                    self._recent_frames_cache.move_to_end(idx)
            
            # --- 4. 清理溢出缓存 ---
            while len(self._recent_frames_cache) > self._recent_frames_limit:
                self._recent_frames_cache.popitem(last=False) # 移除最旧的 (FIFO/LRU)

            if not final_frames:
                logger.warning(f"[{self.recording_uuid}] No data found for range [{start_idx}, {end_idx})")
                return

            # 推送数据
            push_start = time.time()
            self.push_frames(final_frames, start_idx=start_idx)
            push_end = time.time()
            
            logger.debug(f"[{self.recording_uuid}] load_range 完成，总耗时 {time.time() - t0:.3f}s (Fetch: {fetch_end - fetch_start:.3f}s, Push: {push_end - push_start:.3f}s, Cache Hit: {len(needed_indices) - len(missing_indices)}/{len(needed_indices)})")

        except Exception as e:
            logger.error(f"[{self.recording_uuid}] Load range failed: {e}")

    def _seq_task_handler(self, frame_data, idx, use_alignment=False):
        """这个函数由于在 max_workers=1 的线程池运行，天然具备顺序性"""
        if self.is_dead or self.stop_signal.is_set(): return
        try:
            # 只提取顺序数据 (Pose, Axes 等)
            prio, payload = RerunLogger.compute_sequential_payload(
                frame_data, idx, 
                src_db=self.dataset, 
                src_col=self.collection,
                recording_uuid=self.recording_uuid,
                streaming_mode=self.streaming_mode
            )
            
            if use_alignment:
                # 对齐模式：无论是否有 payload，都必须汇报
                self._handle_alignment_merge(idx, 'seq', payload, prio)
            elif payload:
                # 传统模式：只入队有数据的
                self._enqueue_seq(idx, payload)
                
        except Exception as e:
            logger.error(f"Sequential Task Error at frame {idx}: {e}")
            if use_alignment:
                # 异常时也要汇报，防止死锁
                self._handle_alignment_merge(idx, 'seq', None)

    def _async_task_handler(self, frame_data, idx, use_alignment=False):
        """在多线程池运行，处理图像等耗时项"""
        if self.is_dead or self.stop_signal.is_set(): return
        try:
            if not self.recording_uuid:
                logger.error(f"RerunSession: recording_uuid is empty at frame {idx}!")

            # 只提取异步数据 (Image 等)
            prio, payload = RerunLogger.compute_async_payload(
                frame_data, idx, 
                src_db=self.dataset, 
                src_col=self.collection,
                recording_uuid=self.recording_uuid,
                streaming_mode=self.streaming_mode
            )
            
            if use_alignment:
                self._handle_alignment_merge(idx, 'async', payload, prio)
            elif payload:
                # 入异步队列
                self._enqueue_async(prio, idx, payload)
                
        except Exception as e:
            logger.error(f"Async Task Error at frame {idx}: {e}")
            if use_alignment:
                self._handle_alignment_merge(idx, 'async', None)

    def _flush_batch_buffer(self, local_buffer):
        """清空并发送缓冲区"""
        for path, items in local_buffer.items():
            if not items: continue
            
            try:
                # 按索引排序确保时序
                items.sort(key=lambda x: x[0])
                indices = [x[0] for x in items]
                components = [x[1] for x in items]
                
                # 尝试批量发送
                if not self._try_send_batch(path, indices, components):
                    # 回退到逐个发送
                    for idx, comp in items:
                        try:
                            self.stream.set_time("frame_idx", sequence=idx)
                            if isinstance(comp, list):
                                self.stream.log(path, *comp)
                            else:
                                self.stream.log(path, comp)
                        except Exception as e:
                            logger.error(f"Fallback log failed for {path} at {idx}: {e}")
            except Exception as e:
                logger.error(f"Flush buffer failed for {path}: {e}")
                
        local_buffer.clear()
    
    def play_logic(self):
        # --- A. 抢占与重置逻辑 ---
        if self.is_playing:
            self.stop_signal.set()
            wait_start = time.time()
            while self.is_playing and (time.time() - wait_start < 2.0):
                time.sleep(0.1)
        self.stop_signal.clear()
        
        # 清空两个队列 (可选，视需求而定，这里保留以确保全新的播放开始)
        while not self.seq_queue.empty():
            try: self.seq_queue.get_nowait()
            except: break
        while not self.async_queue.empty():
            try: self.async_queue.get_nowait()
            except: break
        while not self.aligned_queue.empty():
            try: self.aligned_queue.get_nowait()
            except: break

        with self.play_lock:
            self.is_playing = True
            self.max_frame_idx = 0

        try:
            # 消费者线程现在已经由 _start_sender_threads 在初始化时启动，
            # 所以这里不需要再定义和启动 sender loops 了。

            # --- C. 推送历史数据 (Producer) ---
            logger.info(f"[{self.recording_uuid}] 开始全速流水线加载 (Streaming)...")
            # 使用流式 Cursor
            frames_cursor = self.frames_iter
            
            batch = []
            batch_size = 15
            
            for i, doc in enumerate(frames_cursor):
                if self.stop_signal.is_set() or self.is_dead: 
                    logger.info(f"[{self.recording_uuid}] 检测到 Session 销毁，停止读取数据")
                    break
                if self.stop_signal.is_set(): break
                batch.append(doc)
                
                if len(batch) >= batch_size:
                    # 批量提交任务，不阻塞
                    self.push_frames(batch, start_idx=i - (len(batch) - 1))
                    batch = []
                
                # 提示：移除 time.sleep(0.01)，靠 log_queue 的 Block 特性自动限速

            # 处理末尾残余
            if batch and not self.stop_signal.is_set():
                self.push_frames(batch, start_idx=i - (len(batch) - 1))

            # --- D. 维持 Session 存活 ---
            while not self.stop_signal.is_set() and not self.is_dead:
                time.sleep(1.0)

        except Exception as e:
            logger.error(f"[{self.recording_uuid}] play_logic 异常: {e}")
        finally:
            with self.play_lock:
                self.is_playing = False

    def _execute_recompute_pipeline(self, target_processors: list, label: str, ranges: list = None):
        if self.is_dead: return
        
        range_info = f"范围: {ranges}" if ranges else "全量"
        logger.info(f"[{self.recording_uuid}] 启动异步重计算: {label}, {range_info}")

        def _task(frame_data, idx):
            if self.is_dead or self.stop_signal.is_set(): 
                return
            try:
                prio, payload = RerunLogger.compute_async_payload(
                    doc=frame_data,
                    frame_idx=idx,
                    target_processors=target_processors,
                    src_db=self.dataset, 
                    src_col=self.collection,
                    recording_uuid=self.recording_uuid,
                    streaming_mode=self.streaming_mode
                )
                self._enqueue_async(prio, idx, payload)
            except Exception as e:
                logger.error(f"[{label}] 帧 {idx} 任务失败: {e}")

        # 根据 ranges 决定处理哪些帧
        submitted_tasks = 0
        submit_start = time.time()

        if ranges:
            for start, end in ranges:
                # 越界保护
                safe_start = max(0, int(start))
                # 使用 fetch_frames_range 获取游标
                cursor = DataManager.fetch_frames_range(self.dataset, self.collection, safe_start, int(end))
                
                for i, doc in enumerate(cursor):
                    if self.stop_signal.is_set(): break
                    real_idx = safe_start + i
                    self.process_executor.submit(_task, doc, real_idx)
                    submitted_tasks += 1
                    if submitted_tasks % 100 == 0:
                        logger.debug(f"[{label}] 已提交任务: {submitted_tasks}")
        else:
            # 全量处理 - 使用流式迭代器
            cursor = self.frames_iter
            for i, doc in enumerate(cursor):
                if self.stop_signal.is_set(): break
                self.process_executor.submit(_task, doc, i)
                submitted_tasks += 1
                if submitted_tasks % 500 == 0:
                     logger.debug(f"[{label}] 已提交任务: {submitted_tasks}")
        
        submit_end = time.time()
        logger.success(f"[{self.recording_uuid}] [{label}] 异步重计算任务提交完成，共提交 {submitted_tasks} 个任务，耗时 {submit_end - submit_start:.3f}s")
    
    def cleanup(self):
        if self.is_dead: 
            return
        try:
            self.is_dead = True
            # 通知 play_logic 线程停止工作
            self.stop_signal.set() 
            # 断开 Rerun 连接
            self.process_executor.shutdown(wait=False, cancel_futures=True)
            self.stream.disconnect()
        finally:
            self.port_manager.release(self.port)
            logger.info(f"[{self.recording_uuid}] 资源已释放，端口 {self.port} 已回收。")

class RerunSessionManager:
    def __init__(self, max_workers: int = 20, timeout_seconds: int = 180):
        self.sessions: Dict[str, RerunSession] = {}
        self.lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.port_manager = PortManager()
        self.timeout_seconds = timeout_seconds

        self.max_memory_percent = 85  # 内存超过 85% 开始激进清理
        self.max_cpu_percent = 90     # CPU 超过 90% 限制新 Session

        self.monitor_thread = threading.Thread(target=self._monitor, daemon=True)
        self.monitor_thread.start()

    def _monitor(self):
        """全局监控：根据系统负载动态调整 Session 生命周期"""
        while True:
            time.sleep(10)
            now = time.time()
            
            # 获取当前系统负载
            mem_usage = psutil.virtual_memory().percent
            cpu_usage = psutil.cpu_percent(interval=1)
            
            with self.lock:
                # 1. 基础清理：心跳超时的必须死
                to_cleanup = [uid for uid, s in self.sessions.items() 
                             if (now - s.last_heartbeat) > self.timeout_seconds]
                
                # 2. 动态清理：如果内存压力大，强制缩短不活跃 Session 的寿命
                if mem_usage > self.max_memory_percent:
                    logger.warning(f"系统内存高位 ({mem_usage}%)，启动激进清理...")
                    # 额外清理那些超过 30 秒没心跳的（即便没到 180 秒阈值）
                    for uid, s in self.sessions.items():
                        if uid not in to_cleanup and (now - s.last_heartbeat) > 30:
                            to_cleanup.append(uid)
                
                for uid in to_cleanup:
                    session = self.sessions.pop(uid, None)
                    if session:
                        session.cleanup()

    def create_session(self, dataset: str, collection: str) -> RerunSession:
        """根据 CPU 负载决定是否允许创建新 Session"""
        cpu_usage = psutil.cpu_percent()
        if cpu_usage > self.max_cpu_percent:
            # 如果 CPU 已经爆了，直接拒绝新连接，保护现有用户
            raise Exception(f"服务器负载过高 ({cpu_usage}%)，请稍后再试")

        session = RerunSession(dataset, collection, self.port_manager)
        with self.lock:
            self.sessions[session.recording_uuid] = session
        return session

    def keep_alive(self, recording_uuid: str):
        """暴露给 API 层调用的心跳接口"""
        with self.lock:
            session = self.sessions.get(recording_uuid)
            if session:
                session.heartbeat()
                return True
        return False

    def start_playback(self, recording_uuid: str):
        with self.lock:
            session = self.sessions.get(recording_uuid)
            if session:
                self.executor.submit(session.play_logic)

manager = RerunSessionManager()