# -*- coding: utf-8 -*-
from datetime import datetime
from mongodb_connect import get_collection

def log_action(operator: str, action: str, details: dict):
    """写入操作日志"""
    log_doc = {
        "operator": operator,
        "action": action,
        "details": details,
        "operation_time": datetime.now(),
        "status": "SUCCESS"
    }
    get_collection("audit_logs").insert_one(log_doc)

def get_recent_logs(limit=10):
    """查询最近的 N 条日志"""
    return list(get_collection("audit_logs").find().sort("operation_time", -1).limit(limit))