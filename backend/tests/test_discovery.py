import unittest
from fastapi.testclient import TestClient
from loguru import logger
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from main import app  # 确保你的 main.py 里有 app = FastAPI(...)

class TestDiscoveryAPI(unittest.TestCase):
    def setUp(self):
        # 初始化 FastAPI 测试客户端
        self.client = TestClient(app) #

    def test_list_all_endpoint(self):
        """直接测试 /list_all 接口的返回结果"""
        logger.info("🧪 开始请求 API: /list_all ...")
        
        # 1. 发送请求
        response = self.client.get("/list_all") #
        
        # 2. 验证 HTTP 状态码
        self.assertEqual(response.status_code, 200, "接口应该返回 200 状态码") #
        
        # 3. 解析并验证数据结构
        result = response.json() #
        self.assertEqual(result["status"], "success") #
        self.assertIn("data", result)
        
        # 4. 打印扫描到的真实业务数据（用于手动核对）
        db_data = result["data"]
        if db_data:
            logger.success(f"✅ 成功通过 API 获取到数据，发现 {len(db_data)} 个数据库")
            for db, cols in db_data.items():
                logger.info(f"📡 库: {db} | 集合数量: {len(cols)}")
        else:
            logger.warning("⚠️ API 返回成功，但数据库列表为空，请确认 MongoDB 权限")

# ==========================================
# 🚀 执行部分
# ==========================================
if __name__ == "__main__":
    unittest.main(verbosity=2) #