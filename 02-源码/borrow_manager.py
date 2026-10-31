# -*- coding: utf-8 -*-
"""
借阅管理模块
功能：借阅登记、归还处理、逾期查询
方法：insert_one、update_many、find
"""
from datetime import datetime
from mongodb_connect import get_collection


def _coll():
    return get_collection("borrow_logs")


def borrow_book(reader_card: str, book_isbn: str):
    """借阅登记：插入一条借阅记录"""
    doc = {
        "borrow_date": datetime.now(),
        "reader_card": reader_card,
        "book_isbn": book_isbn,
        "status": "借出",
    }
    result = _coll().insert_one(doc)
    print(f"[借阅] 登记成功，_id = {result.inserted_id}")
    return result.inserted_id


def return_book(reader_card: str, book_isbn: str):
    """归还处理：把借出状态改为已归还，并记录归还时间"""
    query = {"reader_card": reader_card, "book_isbn": book_isbn, "status": "借出"}
    update = {
        "$set": {
            "status": "已归还",
            "return_date": datetime.now(),
        }
    }
    result = _coll().update_many(query, update)
    print(f"[归还] 匹配 {result.matched_count} 条，修改 {result.modified_count} 条")
    return result.modified_count


def find_overdue():
    """逾期查询：状态为“逾期”的记录"""
    results = list(_coll().find({"status": "逾期"}))
    if not results:
        print("[查询] 无逾期记录")
    return results


def find_logs_by_reader(reader_card: str):
    """查询某读者的所有借阅记录"""
    results = list(_coll().find({"reader_card": reader_card}))
    if not results:
        print(f"[查询] 读者 {reader_card} 无借阅记录")
    return results