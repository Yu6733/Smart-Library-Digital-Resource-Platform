# -*- coding: utf-8 -*-
from mongodb_connect import get_collection
import audit_manager as am

def _coll():
    return get_collection("books")

def add_one(book: dict):
    result = _coll().insert_one(book)
    print(f"[新增] 成功插入 1 条，_id = {result.inserted_id}")
    # 写入日志
    am.log_action("admin", "ADD_BOOK", {"isbn": book.get("isbn"), "title": book.get("title")})
    return result.inserted_id

def find_books(query: dict = None, projection: dict = None, limit: int = 0):
    query = query or {}
    cursor = _coll().find(query, projection)
    if limit > 0:
        cursor = cursor.limit(limit)
    return list(cursor)

def update_one_book(query: dict, update: dict):
    result = _coll().update_one(query, update)
    print(f"[更新] 匹配 {result.matched_count} 条，修改 {result.modified_count} 条")
    if result.modified_count > 0:
        am.log_action("admin", "UPDATE_BOOK", {"query": query})
    return result.modified_count

def delete_one_book(query: dict):
    result = _coll().delete_one(query)
    print(f"[删除] 删除 {result.deleted_count} 条")
    if result.deleted_count > 0:
        am.log_action("admin", "DELETE_BOOK", {"query": query})
    return result.deleted_count

def top_rated(n: int = 5):
    cursor = _coll().find(
        {}, {"_id": 0, "title": 1, "rating": 1, "borrow_count": 1}
    ).sort("rating", -1).limit(n)
    return list(cursor)