from ..core import manager
from ..processors.ui_processor import UIProcessor
from loguru import logger

def trigger_ui_refresh(recording_uuid: str) -> bool:
    """
    业务逻辑：将 '刷新UI' 指令转化为 '对特定 Session 执行 UIProcessor 重计算管线'
    """
    session = manager.sessions.get(recording_uuid)
    if not session:
        logger.warning(f"Service: Session {recording_uuid} not found for UI refresh.")
        return False
        
    # 调用 Session 内部的通用重计算管线
    # 注入 UIProcessor 类（注意是类引用，RerunLogger 会负责实例化）
    session._execute_recompute_pipeline(
        target_processors=[UIProcessor], 
        label="UI_REFRESH_SERVICE"
    )
    return True