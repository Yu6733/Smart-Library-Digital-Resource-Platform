# -*- coding: utf-8 -*-
"""
读者管理模块
功能：读者信息管理、学院统计、等级分布
方法：find、count_documents、distinct
"""
from mongodb_connect import get_collection


def _coll():
    return get_collection("readers")


def find_readers(query: dict = None, projection: dict = None):
    """条件检索读者"""
    query = query or {}
    results = list(_coll().find(query, projection))
    if not results:
        print("[查询] 无匹配读者")
    return results


def count_readers(query: dict = None):
    """统计读者数量"""
    query = query or {}
    n = _coll().count_documents(query)
    print(f"[统计] 匹配读者 {n} 人")
    return n


def college_stats():
    """学院统计：每个学院的读者人数"""
    pipeline = [
        {"$group": {"_id": "$college", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    results = list(_coll().aggregate(pipeline))
    if not results:
        print("[统计] 无数据")
    return results


def level_distribution():
    """等级分布：distinct + count"""
    levels = _coll().distinct("level")
    print(f"[统计] 共 {len(levels)} 个等级：{levels}")
    result = []
    for lv in levels:
        n = _coll().count_documents({"level": lv})
        result.append({"level": lv, "count": n})
    return result