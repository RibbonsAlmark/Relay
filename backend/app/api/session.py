import time
from fastapi import APIRouter, HTTPException
from ..schemas import CreateSourceConfig, SourceResponse
from ..core import manager
from ..config import BACKEND_IP
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