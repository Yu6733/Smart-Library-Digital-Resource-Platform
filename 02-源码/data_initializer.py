# -*- coding: utf-8 -*-
import json
import os
from datetime import datetime
from mongodb_connect import get_collection

# 数据文件统一按本脚本所在目录定位，避免依赖当前工作目录（老师可在任意路径下运行）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 表 3-3 中的索引清单：导入数据后自动建好，重复执行不会重复创建
INDEX_SPECS = [
    ("books", [("isbn", 1)], {"unique": True}),
    ("books", [("category", 1), ("price", -1)], {}),
    ("books", [("title", 1)], {}),
    ("books", [("tags", 1)], {}),
    ("readers", [("card_no", 1)], {"unique": True}),
    ("borrow_logs", [("reader_card", 1)], {}),
    ("audit_logs", [("operation_time", -1)], {}),
]


def ensure_indexes(verbose=True):
    """按设计建索引（幂等）。用 delete_many 而不是 drop 清数据，索引才不会被一并删掉。"""
    created = []
    for coll_name, keys, opts in INDEX_SPECS:
        name = get_collection(coll_name).create_index(keys, **opts)
        created.append("%s.%s" % (coll_name, name))
    if verbose:
        print("✅ 索引就绪，共 %d 个：%s" % (len(created), ", ".join(created)))
    return created


def import_json(filepath, collection_name, date_fields):
    if not os.path.exists(filepath):
        print(f"[警告] 找不到数据文件 {filepath}，跳过。")
        return

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    for doc in data:
        for field in date_fields:
            if field in doc and isinstance(doc[field], str):
                try:
                    # 兼容带时区的 ISO 8601 字符串
                    doc[field] = datetime.fromisoformat(doc[field].replace('Z', '+00:00'))
                except ValueError:
                    pass

    coll = get_collection(collection_name)
    coll.delete_many({})  # 只清空数据，保留集合与索引（drop 会连索引一起删掉）
    if data:
        coll.insert_many(data)
    print(f"✅ 导入 {collection_name} 成功，共 {len(data)} 条")


def initialize_all():
    print("\n--- 正在初始化数据库 ---")
    import_json(os.path.join(BASE_DIR, 'books.txt'), 'books', ['publish_date'])
    import_json(os.path.join(BASE_DIR, 'readers.txt'), 'readers', ['register_date'])
    import_json(os.path.join(BASE_DIR, 'borrow_logs.txt'), 'borrow_logs', ['borrow_date', 'return_date'])
    ensure_indexes()
    print("--- 数据库初始化完成 ---\n")
