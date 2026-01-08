import rerun as rr
import uuid
import time
import threading
import socket
import queue
from concurrent.futures import ThreadPoolExecutor
import concurrent.futures
from typing import Dict, Set
from loguru import logger

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
        
        # 生成录制 ID
        timestamp_str = time.strftime("%Y%m%d-%H%M%S")
        self.recording_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{self.app_id}/{timestamp_str}/{uuid.uuid4()}"))
        
        self.port = self.port_manager.acquire()
        self.is_playing = False
        self.has_started = False
        self.created_at = time.time()

        # 启动独立流
        self.stream = rr.RecordingStream(
            application_id=self.app_id,
            recording_id=self.recording_uuid,
            make_default=False
        )
        # 绑定 0.0.0.0 并增大缓冲区
        self.stream.serve_grpc(grpc_port=self.port, server_memory_limit="1GB")

    import queue

    def play_logic(self):
        """完全异步管线：分发即释放，计算完自动排队"""
        try:
            self.is_playing = True
            self.has_started = True
            # 有界队列，作为“背压”控制内存
            log_queue = queue.Queue(maxsize=32)

            # --- 1. 发送者线程 ---
            def sender_loop():
                while self.is_playing or not log_queue.empty():
                    try:
                        idx, payload = log_queue.get(timeout=1.0)
                        self.stream.set_time("frame_idx", sequence=idx)
                        for path, component in payload.items():
                            self.stream.log(path, component)
                        log_queue.task_done()
                    except queue.Empty:
                        continue

            sender_thread = threading.Thread(target=sender_loop, daemon=True)
            sender_thread.start()

            # --- 2. 异步回调函数 ---
            def on_compute_done(future, idx):
                try:
                    payload = future.result()
                    # 计算完成，直接塞入队列。如果队列满，计算线程会在此稍作等待
                    log_queue.put((idx, payload))
                except Exception as e:
                    logger.error(f"Frame {idx} computation failed: {e}")

            # --- 3. 生产者 (主线程) ---
            frames_iter = DataManager.fetch_frames_iter(self.dataset, self.collection)
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                for i, frame in enumerate(frames_iter):
                    # 【核心改变】：不使用 .result() 阻塞，而是绑定回调
                    future = executor.submit(
                        RerunLogger.compute_frame_payload,
                        frame, i,
                        src_db=self.dataset, src_col=self.collection
                    )
                    # 关键点：将当前的序号 i 绑定到回调函数中
                    future.add_done_callback(lambda f, idx=i: on_compute_done(f, idx))
                    
                    # 维持输入节奏，防止瞬间把成千上万个任务丢进线程池
                    time.sleep(0.015) # 稍微快于 50fps，给缓冲留余地

            print(f"[{self.recording_uuid}] All tasks dispatched.")
            
        except Exception as e:
            logger.error(f"Pipeline error: {e}")
        finally:
            # 这里的优雅关闭逻辑需要注意：
            # 需要等待 executor 里的任务全部分发完并执行完回调
            self.is_playing = False 
            sender_thread.join(timeout=5)
            self.cleanup()
    
    # def play_logic(self):
    #     """优化后的回放逻辑：动态时间补偿"""
    #     try:
    #         self.is_playing = True
    #         self.has_started = True
    #         print(f"[{self.recording_uuid}] 开始全量推送数据 (Port: {self.port})")
            
    #         frames_iter = DataManager.fetch_frames_iter(self.dataset, self.collection)
            
    #         # 设置目标帧间隔 (0.02s = 50 FPS)
    #         TARGET_FRAME_TIME = 0.02 

    #         for i, frame in enumerate(frames_iter):
    #             frame_start = time.perf_counter()
                
    #             # 执行推送 (包含图片压缩、JSON 转换等 IO/CPU 耗时操作)
    #             RerunLogger.log_frame_to_stream(
    #                 self.stream, 
    #                 frame, 
    #                 frame_idx=i,
    #                 src_db=self.dataset, 
    #                 src_col=self.collection
    #             )
                
    #             if i % 50 == 0:
    #                 print(f"[{self.recording_uuid}] 已推送 {i} 帧...")
                
    #             # 计算本次推送实际耗时
    #             elapsed = time.perf_counter() - frame_start
    #             # 动态计算剩余需要等待的时间，确保整体频率平滑
    #             sleep_time = max(0.001, TARGET_FRAME_TIME - elapsed)
    #             time.sleep(sleep_time)
                
    #         print(f"[{self.recording_uuid}] 推送完成。")
    #     except Exception as e:
    #         print(f"[{self.recording_uuid}] 推送异常: {e}")
    #     finally:
    #         self.is_playing = False
    #         # 留出时间让 Rerun 缓冲区排空到 Viewer
    #         time.sleep(3)
    #         self.cleanup()

    def cleanup(self):
        try:
            self.stream.disconnect()
        finally:
            self.port_manager.release(self.port)
            print(f"[{self.recording_uuid}] 资源回收完毕。")

class RerunSessionManager:
    def __init__(self, max_workers: int = 20, timeout_seconds: int = 300):
        self.sessions: Dict[str, RerunSession] = {}
        self.lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.port_manager = PortManager()
        self.timeout_seconds = timeout_seconds

        self.monitor_thread = threading.Thread(target=self._monitor, daemon=True)
        self.monitor_thread.start()

    def _monitor(self):
        while True:
            time.sleep(10)
            now = time.time()
            with self.lock:
                to_del = [uid for uid, s in self.sessions.items() 
                          if not s.has_started and (now - s.created_at) > self.timeout_seconds]
                for uid in to_del:
                    self.sessions.pop(uid).cleanup()

    def create_session(self, dataset: str, collection: str) -> RerunSession:
        session = RerunSession(dataset, collection, self.port_manager)
        with self.lock:
            self.sessions[session.recording_uuid] = session
        return session

    def start_playback(self, recording_uuid: str):
        with self.lock:
            session = self.sessions.get(recording_uuid)
            if session and not session.is_playing:
                future = self.executor.submit(session.play_logic)
                future.add_done_callback(lambda f: self._remove_from_map(recording_uuid))

    def _remove_from_map(self, recording_uuid: str):
        with self.lock:
            if recording_uuid in self.sessions:
                del self.sessions[recording_uuid]

manager = RerunSessionManager()