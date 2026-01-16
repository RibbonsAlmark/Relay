import rerun as rr
import uuid
import time
import threading
import socket
import queue
from concurrent.futures import ThreadPoolExecutor
from app.metadata_utils import get_global_sources
import concurrent.futures
from typing import Dict, Set
from loguru import logger
import psutil
import os

from .data_provider import DataManager
from .rerun_logger import RerunLogger

class PortManager:
    def __init__(self, start_port: int = 10000, end_port: int = 11000):
        self.start_port = start_port
        self.end_port = end_port
        self.used_ports: Set[int] = set()
        self.lock = threading.Lock()

    def acquire(self) -> int:
        with self.lock:
            for port in range(self.start_port, self.end_port + 1):
                if port not in self.used_ports and self._is_port_available(port):
                    self.used_ports.add(port)
                    return port
            raise RuntimeError("No free ports available.")

    def release(self, port: int):
        with self.lock:
            self.used_ports.discard(port)

    def _is_port_available(self, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) != 0

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
        
        # --- 【背压控制】 ---
        # 使用 PriorityQueue 实现优先级控制
        # 优先级定义：0 (高，Pose/Seq) < 10 (低，Image/Async)
        self.log_queue = queue.PriorityQueue(maxsize=32)
        self.max_frame_idx = 0 
        
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
        
        # 2. 并发执行器：处理耗时任务（图像、点云等）
        self.process_executor = ThreadPoolExecutor(max_workers=(os.cpu_count() or 4) * 2)

        # 内存限制 10MB
        memory_limit = "10MB"
        self.stream.serve_grpc(grpc_port=self.port, server_memory_limit=memory_limit)

        # 线程锁
        self.log_lock = threading.Lock()

        # 1. Source Catalog 独立线程初始化
        self._source_catalog_cache = []
        self._source_catalog_event = threading.Event()
        
        def _init_source_catalog():
            try:
                result = get_global_sources(
                    dataset=dataset,
                    collection=collection,
                    start_index=0,
                    max_workers=8
                )
                self._source_catalog_cache = result
            except Exception as e:
                logger.error(f"[{self.recording_uuid}] Source Catalog Init Failed: {e}")
            finally:
                self._source_catalog_event.set()

        # 启动守护线程，不阻塞主线程，且随主线程退出自动销毁
        threading.Thread(target=_init_source_catalog, daemon=True).start()

        # 2. 顺序任务重组缓冲区 (Reordering Buffer)
        # 不再使用单线程池，而是通过缓冲区实现并发计算 + 顺序提交
        self.next_seq_idx = 0
        self.seq_buffer = []  # Heapq: (idx, prio, payload)
        self.seq_lock = threading.Lock()
        
        logger.info(f"[{self.recording_uuid}] Session initialized on port {self.port} (Limit: {memory_limit})")

    @property
    def source_catalog(self):
        """懒加载获取 source_catalog，如果未完成则阻塞等待"""
        # 等待初始化线程完成
        self._source_catalog_event.wait()
        return self._source_catalog_cache

    def heartbeat(self):
        """外部调用此方法续命"""
        self.last_heartbeat = time.time()

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
                    source_catalog=self.source_catalog,
                )
                # 阻塞入队：实现背压的核心
                # 优先级 10 (低)
                self.log_queue.put((10, idx, payload), block=True)
            except Exception as e:
                logger.error(f"Async Task Error at frame {idx}: {e}")

        # --- 3. 提交至常驻线程池 ---
        # 瞬间提交所有帧，不阻塞主线程，实现 I/O 与计算的分离
        try:
            for i, frame_data in enumerate(frames):
                idx = base_idx + i
                
                # --- 分支 A: 顺序支流 ---
                # 仅仅是提交任务，瞬间完成，不阻塞读取
                self.seq_executor.submit(self._seq_task_handler, frame_data, idx)

                # --- 分支 B: 异步支流 ---
                # 依然由多线程池全速计算图像
                self.process_executor.submit(self._async_task_handler, frame_data, idx)
            
            return True
        except Exception as e:
            logger.error(f"[{self.recording_uuid}] 异步任务提交失败: {e}")
            return False

    def _seq_task_handler(self, frame_data, idx):
        """这个函数由于在 max_workers=1 的线程池运行，天然具备顺序性"""
        if self.is_dead or self.stop_signal.is_set(): return
        try:
            # 只提取顺序数据 (Pose, Axes 等)
            prio, payload = RerunLogger.compute_sequential_payload(
                frame_data, idx, 
                src_db=self.dataset, 
                src_col=self.collection,
                recording_uuid=self.recording_uuid,
                source_catalog=self.source_catalog,

            )
            if payload:
                # 使用动态优先级
                self.log_queue.put((prio, idx, payload), block=True)
        except Exception as e:
            logger.error(f"Sequential Task Error at frame {idx}: {e}")

    def _async_task_handler(self, frame_data, idx):
        """在多线程池运行，处理图像等耗时项"""
        if self.is_dead or self.stop_signal.is_set(): return
        try:
            # 只提取异步数据 (Image 等)
            prio, payload = RerunLogger.compute_async_payload(
                frame_data, idx, 
                src_db=self.dataset, 
                src_col=self.collection,
                recording_uuid=self.recording_uuid,
                source_catalog=self.source_catalog,
            )
            if payload:
                # 计算完后塞进队列，由 sender_loop 补发图像
                # 使用动态优先级
                self.log_queue.put((prio, idx, payload), block=True)
        except Exception as e:
            logger.error(f"Async Task Error at frame {idx}: {e}")
    
    def play_logic(self):
        # --- A. 抢占与重置逻辑 (略，保持你现在的代码即可) ---
        if self.is_playing:
            self.stop_signal.set()
            wait_start = time.time()
            while self.is_playing and (time.time() - wait_start < 2.0):
                time.sleep(0.1)
        self.stop_signal.clear()
        while not self.log_queue.empty():
            try: self.log_queue.get_nowait()
            except: break

        with self.play_lock:
            self.is_playing = True
            self.max_frame_idx = 0

        try:
            # --- B. 启动发送者线程 (Consumer) ---
            def sender_loop():
                logger.info(f"[{self.recording_uuid}] Sender Loop 已启动")
                try:
                    while not self.stop_signal.is_set() or not self.log_queue.empty():
                        try:
                            item = self.log_queue.get(timeout=0.5)
                            # 解包：priority, idx, payload
                            _, idx, payload = item
                            try:
                                with self.log_lock:
                                    self.stream.set_time("frame_idx", sequence=idx)
                                    for path, component in payload.items():
                                        if isinstance(component, list):
                                            self.stream.log(path, *component)
                                        else:
                                            self.stream.log(path, component)
                            except Exception as e:
                                logger.error(f"[{self.recording_uuid}] Sender Loop Write Error: {e}")
                            finally:
                                self.log_queue.task_done()
                        except queue.Empty:
                            continue
                finally:
                    logger.info(f"[{self.recording_uuid}] Sender Loop 已关闭")

            threading.Thread(target=sender_loop, daemon=True).start()

            # --- C. 推送历史数据 (Producer) ---
            logger.info(f"[{self.recording_uuid}] 开始全速流水线加载...")
            frames_iter = DataManager.fetch_frames_iter(self.dataset, self.collection)
            
            batch = []
            batch_size = 15 # 增大 Batch，喂饱线程池
            
            for i, doc in enumerate(frames_iter):
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

    def _execute_recompute_pipeline(self, target_processors: list, label: str):
        if self.is_dead: return
        
        logger.info(f"[{self.recording_uuid}] 启动异步重计算: {label}")

        # 移除 limit 参数，直接获取全部数据迭代器
        frames_iter = DataManager.fetch_frames_iter(
            self.dataset, 
            self.collection
        )

        def _task(frame_data, idx):
            if self.is_dead or self.stop_signal.is_set(): return
            try:
                # 【关键修复】确保显式传入 frame_idx 参数
                prio, payload = RerunLogger.compute_async_payload(
                    doc=frame_data,        # 对应 doc
                    frame_idx=idx,         # 对应 frame_idx (之前可能写成了 idx 或者漏传了)
                    target_processors=target_processors,
                    src_db=self.dataset, 
                    src_col=self.collection,
                    recording_uuid=self.recording_uuid,
                    source_catalog=self.source_catalog,
                )
                
                # 检查是否需要启动发送者线程（如果当前没有在播放，需要有一个人消费队列）
                # 使用动态优先级
                self.log_queue.put((prio, idx, payload), block=True)
                
            except Exception as e:
                logger.error(f"[{label}] 帧 {idx} 任务失败: {e}")

        for i, doc in enumerate(frames_iter):
            if self.stop_signal.is_set(): break
            self.process_executor.submit(_task, doc, i)
    
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