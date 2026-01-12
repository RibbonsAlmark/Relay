import time
from fastapi import APIRouter, HTTPException
from ..schemas import CreateSourceConfig, SourceResponse
from ..core import manager
from ..config import BACKEND_IP
from ..service import session_service
from loguru import logger

router = APIRouter()

@router.post("/create_source", response_model=SourceResponse)
async def create_source(config: CreateSourceConfig):
    """创建 Rerun 会话"""
    try:
        session = manager.create_session(config.dataset, config.collection)
        connect_url = f"rerun+http://{BACKEND_IP}:{session.port}/proxy"
        return SourceResponse(
            status="created",
            app_id=session.app_id,
            recording_uuid=session.recording_uuid,
            port=session.port,
            connect_url=connect_url
        )
    except Exception as e:
        logger.error(f"Create session error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create Rerun session: {str(e)}")

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

@router.post("/refresh_ui/{recording_uuid}")
async def refresh_ui(recording_uuid: str):
    """
    单独触发 UI 组件的刷新（不重新加载点云和图像）
    """
    success = session_service.trigger_ui_refresh(recording_uuid)
    if not success:
        raise HTTPException(
            status_code=404, 
            detail="Session not found or expired"
        )
    
    return {
        "status": "ui_refresh_triggered",
        "recording_uuid": recording_uuid,
        "timestamp": time.time()
    }