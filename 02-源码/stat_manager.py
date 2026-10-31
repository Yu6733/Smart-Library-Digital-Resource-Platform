# -*- coding: utf-8 -*-
import json
import os
import time

from pymongo import MongoClient

from mongodb_connect import get_collection

# 导出文件与脚本同目录，避免依赖当前工作目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _books():
    return get_collection("books")

def _logs():
    return get_collection("borrow_logs")

def category_stats():
    pipeline = [
        {"$group": {"_id": "$category",
                    "total_stock": {"$sum": "$stock"},
                    "avg_price": {"$avg": "$price"},
                    "book_count": {"$sum": 1}}},
        {"$project": {"total_stock": 1, "book_count": 1,
                      "avg_price": {"$ifNull": ["$avg_price", 0]}}},
        {"$sort": {"total_stock": -1}},
    ]
    # 查询结果先取回，再单独用 $merge 写入 category_summary：
    # $merge 阶段本身不返回文档，直接把它放在末尾会让调用方拿到空列表。
    rows = list(_books().aggregate(pipeline))
    _books().aggregate(pipeline + [
        {"$merge": {"into": "category_summary",
                    "whenMatched": "replace", "whenNotMatched": "insert"}}
    ])
    return rows

def borrow_trend():
    pipeline = [
        {"$group": {"_id": {"$dateToString": {"format": "%Y-%m",
                                              "date": {"$toDate": "$borrow_date"}}},
                    "borrow_count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]
    return list(_logs().aggregate(pipeline))

def bestsellers(n: int = 5):
    pipeline = [
        {"$sort": {"borrow_count": -1}},
        {"$limit": n},
        {"$project": {"_id": 0, "title": 1, "borrow_count": 1, "rating": 1}},
    ]
    return list(_books().aggregate(pipeline))

# ================= 多集合联合分析：学院借阅 TOP 5 =================
def college_borrow_top5():
    pipeline = [
        {"$lookup": {"from": "readers", "localField": "reader_card",
                     "foreignField": "card_no", "as": "reader_info"}},
        {"$unwind": "$reader_info"},
        {"$group": {"_id": "$reader_info.college", "borrow_count": {"$sum": 1}}},
        {"$sort": {"borrow_count": -1}},
        {"$limit": 5},
    ]
    return list(_logs().aggregate(pipeline))

# 导出物化视图为 JSON
def export_category_summary():
    data = list(get_collection("category_summary").find({}, {"_id": 0}))
    filename = os.path.join(BASE_DIR, "category_summary_export.json")
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("[导出] 成功导出 category_summary 集合到 %s（脚本目录下）" % os.path.basename(filename))


# ================= 分片集群查询对比演示 =================
def _shard_uri():
    with open(os.path.join(BASE_DIR, "config.json"), "r", encoding="utf-8") as f:
        cfg = json.load(f)
    return os.environ.get("MONGODB_SHARD_URI") or cfg.get("shard_uri"), cfg.get("db", "library")


def _plan_once(coll, query):
    """返回 (执行阶段, 命中分片列表, 扫描文档数, 服务器端耗时毫秒)。"""
    ex = coll.database.command("explain",
                               {"find": coll.name, "filter": query},
                               verbosity="executionStats")
    wp = ex.get("queryPlanner", {}).get("winningPlan", {})
    stage = wp.get("stage", "-")
    raw = wp.get("shards") or []
    shards = [s.get("shardName") if isinstance(s, dict) else s for s in raw]
    if not shards and wp.get("shardName"):
        shards = [wp["shardName"]]
    es = ex.get("executionStats", {})
    return stage, shards, es.get("totalDocsExamined", 0), es.get("executionTimeMillis", 0)


def _compare(coll, query, rounds=20):
    stage, shards, docs, _ = _plan_once(coll, query)      # 预热，同时取计划信息
    took = 0
    for _ in range(rounds):
        took += _plan_once(coll, query)[3]
    return stage, shards, docs, took / float(rounds)


def _show(title, coll, query, rounds=20):
    stage, shards, docs, ms = _compare(coll, query, rounds)
    print("%s" % title)
    print("  查询条件: %s" % (query,))
    print("  执行阶段: %-12s 命中分片: %-12s 扫描文档: %-7d 平均耗时: %.2f ms"
          % (stage, ",".join(shards) or "-", docs, ms))
    return ms, shards, docs


def sharding_query_demo():
    """在 mongos 上对比“带分片键的定向查询”与“不带分片键的广播查询”。
    没有启动分片集群时给出明确提示，不影响副本集模式的其它功能。"""
    uri, dbname = _shard_uri()
    if not uri:
        print("[提示] config.json 中未配置 shard_uri，跳过分片演示。")
        return
    client = MongoClient(uri, serverSelectionTimeoutMS=4000)
    try:
        client.admin.command("ping")
    except Exception as e:
        print("[提示] 连接 mongos 失败：%s" % str(e).split(":")[0])
        print("[提示] 未启动分片集群时本演示不可用，属正常现象：先按")
        print("      03-数据库与配置/启动与部署说明.md 启动 config 副本集、sh1、sh2 与 mongos 再执行。")
        return
    try:
        db = client[dbname]
        names = set(db.list_collection_names())
        target = "borrow_logs_bench" if "borrow_logs_bench" in names else "borrow_logs"
        coll = db[target]
        total = coll.estimated_document_count()
        print("已连接 mongos（27217），演示集合 %s.%s 共 %d 条（已分片）" % (dbname, target, total))
        if target == "borrow_logs_bench":
            print("（该集合是任务六的性能压测数据，业务集合 borrow_logs 仍为 %d 条）"
                  % db["borrow_logs"].estimated_document_count())
        print("")
        ms1, sh1, d1 = _show("--- 1. 定向查询：条件里带分片键 reader_card ---",
                             coll, {"reader_card": "R20240001"})
        print("")
        ms2, sh2, d2 = _show("--- 2. 广播查询：条件里不带分片键，需路由到全部分片 ---",
                             coll, {"status": "已归还"})
        print("")
        ratio = (ms2 / ms1) if ms1 else 0
        print("结论：定向 %.2f ms（扫描 %d 文档、命中 %s），广播 %.2f ms（扫描 %d 文档、命中 %s），"
              % (ms1, d1, ",".join(sh1) or "-", ms2, d2, ",".join(sh2) or "-"))
        print("      相差约 %.1f 倍。把分片键写进查询条件即可避免 scatter-gather。" % ratio)
    finally:
        client.close()
