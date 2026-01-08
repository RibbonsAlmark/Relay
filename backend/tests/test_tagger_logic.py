# tests/test_tagger_logic.py
import unittest
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.logic.tagger import TaggerLogic

class TestTaggerLogic(unittest.TestCase):
    def test_score_replacement(self):
        """测试：旧评分是否被正确替换，非评分标签是否被保留"""
        original_tags = ["indoor", "S", "night"]
        # 将 S 改为 A
        updated = TaggerLogic.update_score_in_tags(original_tags, "A")
        
        self.assertIn("A", updated)
        self.assertIn("indoor", updated)
        self.assertIn("night", updated)
        self.assertNotIn("S", updated) # 旧的评分必须消失
        self.assertEqual(len(updated), 3)

    def test_invalid_score(self):
        """测试：传入非法评分时不应添加"""
        original_tags = ["indoor"]
        updated = TaggerLogic.update_score_in_tags(original_tags, "Z") # Z 不在 S-E 范围内
        self.assertNotIn("Z", updated)
        self.assertEqual(updated, ["indoor"])

if __name__ == "__main__":
    unittest.main()