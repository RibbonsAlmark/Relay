# app/logic/tagger.py
import re
from typing import List, Any, Optional, Set
from loguru import logger

class TaggerLogic:
    """
    统一标签与评级管理模块
    功能：
    1. 命名空间管理：使用 'rating:' 前缀隔离评级数据。
    2. 数据清洗：强制将脏数据（如 dict, None）转化为标准 List[str]。
    3. 自动纠错：自动识别并清理旧版的纯 'S/A/B' 标签和旧版字典评分。
    4. 幂等性：确保标签列表中每个维度只有一个值，且不重复。
    """

    # 配置区
    PREFIX = "rating:"
    VALID_RATINGS: Set[str] = {"A", "B", "C", "D", "E", "F"}
    
    # 匹配模式：用于精准识别所有需要被清理或更新的评级标签
    # 匹配 'rating:S' 或旧版的 'S' (独立单词)
    chars = "".join(sorted(VALID_RATINGS))
    CLEANUP_PATTERN = re.compile(rf"^({PREFIX})?([{chars}])$")

    @classmethod
    def _to_clean_str_list(cls, raw_tags: Any) -> List[str]:
        """
        核心防火墙：将任何输入转换为纯净的字符串列表，彻底解决 unhashable 问题
        """
        if raw_tags is None:
            return []
        
        # 如果是单体（str/dict），先包装成列表统一处理
        if not isinstance(raw_tags, list):
            raw_tags = [raw_tags]
            
        clean_list = []
        for item in raw_tags:
            if isinstance(item, str):
                clean_list.append(item)
            elif isinstance(item, dict):
                # 如果是字典且含有旧的评分信息，可以提取，否则转为字符串
                if "score" in item:
                    # 尝试兼容旧版字典 {"score": "A"}
                    val = str(item["score"]).upper()
                    if val in cls.VALID_RATINGS:
                        clean_list.append(val) 
                else:
                    # 其他字典转为字符串存入，防止 unhashable 报错
                    clean_list.append(str(item))
            elif item is not None:
                clean_list.append(str(item))
                
        return clean_list

    @classmethod
    def update_rating(cls, raw_tags: Any, new_rating: str) -> List[str]:
        """
        更新评级：这是外部调用的主要接口
        :param raw_tags: 数据库中原始的 tag 字段内容
        :param new_rating: 新的等级（如 'S', 'A'）
        :return: 经过清洗和更新后的 List[str]
        """
        # 1. 预处理：转为纯字符串列表
        tags = cls._to_clean_str_list(raw_tags)
        
        # 2. 过滤：移除所有符合评级模式的标签（包括新旧格式）
        # 这样能保证列表中不会同时存在 'rating:A' 和 'rating:B'，也不会有旧的 'A'
        final_tags = []
        for t in tags:
            if cls.CLEANUP_PATTERN.match(t):
                continue
            final_tags.append(t)
            
        # 3. 插入新评级
        if new_rating:
            upper_rating = new_rating.upper()
            if upper_rating in cls.VALID_RATINGS:
                final_tags.append(f"{cls.PREFIX}{upper_rating}")
            else:
                logger.warning(f"尝试更新了非法的评级值: {new_rating}")

        # 4. 去重并排序
        return sorted(list(set(final_tags)))

    @classmethod
    def get_current_rating(cls, tags: Any) -> str:
        """
        从标签列表中提取当前的评级值（用于 UI 显示）
        返回示例: "S", "A" 或 "Unrated"
        """
        tags_list = cls._to_clean_str_list(tags)
        for t in tags_list:
            match = cls.CLEANUP_PATTERN.match(t)
            if match:
                return match.group(2) # 返回 S/A/B 部分
        return "Unrated"