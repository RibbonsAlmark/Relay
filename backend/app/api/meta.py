from fastapi import APIRouter
from ..data_provider import DataManager
from loguru import logger

router = APIRouter()

@router.get("/list_all")
async def list_all():
    """列出所有可用的数据库和集合"""
    try:
        structure = DataManager.get_all_db_collections()
        return {"status": "success", "data": structure, "count": len(structure)}
    except Exception as e:
        logger.error(f"API list_all 出错: {e}")
        return {"status": "error", "message": str(e)}