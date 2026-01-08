import uvicorn
from fastapi import FastAPI
from app.api import router
from fastapi.middleware.cors import CORSMiddleware
from app.config import BACKEND_PORT

app = FastAPI(title="Rerun Enterprise Data Provider")

# 注册路由
app.include_router(router)

app.add_middleware(
    CORSMiddleware,
    # 允许访问的源列表，测试环境可以直接用 ["*"]
    allow_origins=["*"], 
    # 允许跨域的 cookie
    allow_credentials=True,
    # 允许的方法，包括 POST, GET, OPTIONS 等
    allow_methods=["*"],
    # 允许的请求头
    allow_headers=["*"],
)

if __name__ == "__main__":
    # 使用 uvicorn 启动
    uvicorn.run(app, host="0.0.0.0", port=BACKEND_PORT)