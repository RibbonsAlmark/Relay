import time
from fastapi import APIRouter, HTTPException
from ..schemas import CreateSourceConfig, SourceResponse, LoadRangeConfig
from ..core import manager
from ..config import BACKEND_IP
from ..service import session_service
from loguru import logger
from ..schemas import RefreshUIRequest

router = APIRouter()

@router.post("/load_range/{recording_uuid}")
async def load_range(recording_uuid: str, config: LoadRangeConfig):
    """加载指定范围的数据（支持重载或初次加载）"""
    session = None
    with manager.lock:
        session = manager.sessions.get(recording_uuid)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # 只要调用了流式加载接口，就标记该 Session 为流式模式
    session.streaming_mode = True
    
    try:
        session.load_range(config.start_index, config.end_index)
        return {
            "status": "loading", 
            "range": [config.start_index, config.end_index],
            "recording_uuid": recording_uuid
        }
    except Exception as e:
        logger.error(f"Load range API error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/create_source", response_model=SourceResponse)
async def create_source(config: CreateSourceConfig):
    """创建 Rerun 会话"""
    try:
        session = manager.create_session(config.dataset, config.collection)
        
        # 如果配置要求开启对齐模式
        if config.alignment_mode:
            session.set_alignment_mode(True)
            print(f"Alignment mode enabled for session {session.recording_uuid}")
            
        if config.streaming_mode:
            session.streaming_mode = True
            print(f"Streaming mode enabled for session {session.recording_uuid}")
            
        connect_url = f"rerun+http://{BACKEND_IP}:{session.port}/proxy"
        
        # 尝试获取最大帧索引 (这需要 DataManager 支持，或者我们在 session 初始化时预读了)
        # 暂时使用 session.max_frame_idx，如果 session 还没有数据，可能需要 DataManager 查一下
        # 这里假设 session 初始化时已经大概知道了，或者我们直接查 DataManager
        from ..core import DataManager
        try:
            # 这是一个简单的 count 操作，应该很快
            max_idx = DataManager.get_collection_count(config.dataset, config.collection)
        except:
            max_idx = 0

        return SourceResponse(
            status="created",
            app_id=session.app_id,
            recording_uuid=session.recording_uuid,
            port=session.port,
            connect_url=connect_url,
            max_frame_idx=max_idx
        )
    except Exception as e:
        logger.error(f"Create session error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create Rerun session: {str(e)}")

@router.post("/enable_streaming_mode/{recording_uuid}")
async def enable_streaming_mode(recording_uuid: str):
    """显式开启流式模式"""
    session = None
    with manager.lock:
        session = manager.sessions.get(recording_uuid)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    session.streaming_mode = True
    return {"status": "success", "recording_uuid": recording_uuid, "streaming_mode": True}

@router.post("/enable_alignment_mode/{recording_uuid}")
async def enable_alignment_mode(recording_uuid: str):
    """显式开启对齐模式"""
    session = None
    with manager.lock:
        session = manager.sessions.get(recording_uuid)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    session.set_alignment_mode(True)
    return {"status": "success", "recording_uuid": recording_uuid, "alignment_mode": True}

@router.post("/play_data/{recording_uuid}")
async def play_data(recording_uuid: str):
    """触发指定 UUID 会话的回放"""
    try:
        if recording_uuid not in manager.sessions:
            raise KeyError()
        manager.start_playback(recording_uuid)
        return {"status": "playback_started", "recording_uuid": recording_uuid}
    except KeyError:
        raise HTTPException(status_code=404, detail="Recording UUID not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/list_sessions")
async def list_sessions():
    """列出所有活跃会话"""
    with manager.lock:
        return {
            uuid: {
                "app_id": sess.app_id, 
                "port": sess.port, 
                "is_playing": sess.is_playing,
                "uptime": f"{int(time.time() - sess.created_at)}s"
            } 
            for uuid, sess in manager.sessions.items()
        }

@router.post("/heartbeat/{recording_uuid}")
async def heartbeat(recording_uuid: str):
    """
    接收心跳，延长 Session 的生命周期
    """
    # 调用核心层的 heartbeat() 更新时间戳
    success = manager.keep_alive(recording_uuid)
    
    if not success:
        # 如果返回 False，说明 Manager 里的字典确实没有这个 UUID 了（可能已被清理）
        logger.warning(f"Heartbeat failed: Session {recording_uuid} not found.")
        raise HTTPException(
            status_code=404, 
            detail="Session not found or already expired"
        )
    
    return {
        "status": "alive",
        "recording_uuid": recording_uuid,
        "server_time": time.time()
    }

@router.get("/get_info/{recording_uuid}")
async def get_info(recording_uuid: str):
    """获取 Session 详细信息，包括最大帧数"""
    session = None
    with manager.lock:
        session = manager.sessions.get(recording_uuid)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    # 获取最大帧数
    from ..core import DataManager
    try:
        max_idx = DataManager.get_collection_count(session.dataset, session.collection)
    except:
        max_idx = 0
        
    return {
        "recording_uuid": recording_uuid,
        "app_id": session.app_id,
        "dataset": session.dataset,
        "collection": session.collection,
        "max_frame_idx": max_idx
    }



@router.post("/refresh_ui/{recording_uuid}")
async def refresh_ui(recording_uuid: str, req: RefreshUIRequest):
    """
    单独触发 UI 组件的刷新（不重新加载点云和图像）。
    可选参数 loaded_ranges: 指定只刷新的帧区间 [[start, end], ...]
    """
    # 优先使用 path 参数里的 uuid，其次是请求体中的 uuid
    recording_uuid = req.recording_uuid or recording_uuid

    success = session_service.trigger_ui_refresh(recording_uuid, loaded_ranges=req.loaded_ranges)
    if not success:
        raise HTTPException(
            status_code=404, 
            detail="Session not found or expired"
        )
    
    return {
        "status": "ui_refresh_triggered",
        "recording_uuid": recording_uuid,
        "ranges": req.loaded_ranges,
        "timestamp": time.time()
    }