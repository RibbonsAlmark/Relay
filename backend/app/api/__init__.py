# app/api/__init__.py
from fastapi import APIRouter
from .session import router as session_router
from .rating import router as rating_router
from .meta import router as meta_router

# 创建一个总路由
api_router = APIRouter()

# 包含所有子模块的路由
api_router.include_router(session_router)
api_router.include_router(rating_router)
api_router.include_router(meta_router)

router = api_router