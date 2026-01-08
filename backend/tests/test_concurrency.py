import asyncio
import httpx
import time

BASE_URL = "http://127.0.0.1:8000"
CONCURRENT_COUNT = 10  # 同时开启 10 个实例

async def run_client_task(client, user_id):
    app_id = f"stress_test_{user_id}"
    
    # 1. 创建源
    resp = await client.post("/create_source", json={"app_id": app_id})
    if resp.status_code == 200:
        port = resp.json()["port"]
        print(f"[Client {user_id}] 已就绪，端口: {port}")
        
        # 2. 播放
        await client.post(f"/play_data/{app_id}")
        print(f"[Client {user_id}] 正在推送数据...")
    else:
        print(f"[Client {user_id}] 失败: {resp.text}")

async def main():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        tasks = [run_client_task(client, i) for i in range(CONCURRENT_COUNT)]
        start_time = time.perf_counter()
        await asyncio.gather(*tasks)
        end_time = time.perf_counter()
        print(f"\n并发启动完毕，耗时: {end_time - start_time:.2f}s")
        print("请检查后端日志查看线程回收情况。")

if __name__ == "__main__":
    asyncio.run(main())