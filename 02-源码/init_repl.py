# -*- coding: utf-8 -*-
"""初始化三节点副本集。

不写死地址、端口与副本集名：
    - 连接串取 MONGODB_STANDALONE_URI 或 config.json 的 standalone_uri
    - 成员列表取 MONGODB_REPL_MEMBERS 或 config.json 的 repl_members
    - 副本集名取 MONGODB_REPL_SET / config.json 的 repl_set，
      若节点已用 --replSet 启动，则自动采用该节点上报的集合名
"""
import json
import os
import sys
import time

from pymongo import MongoClient
from pymongo.errors import OperationFailure, PyMongoError

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")


def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def members_from(cfg):
    raw = os.environ.get("MONGODB_REPL_MEMBERS")
    if raw:
        return [h.strip() for h in raw.split(",") if h.strip()]
    return list(cfg.get("repl_members") or [])


def detect_set_name(client):
    """从 mongod 启动参数里取 --replSet 的值（未初始化的节点 hello 不带 setName）。"""
    try:
        opts = client.admin.command("getCmdLineOpts")
    except PyMongoError:
        return None
    parsed = opts.get("parsed") or {}
    repl = parsed.get("replication") or {}
    return repl.get("replSet") or repl.get("replSetName")


def print_status(client, seconds=25):
    """轮询 replSetGetStatus，成功打印各节点角色。"""
    last = None
    for _ in range(seconds):
        try:
            st = client.admin.command("replSetGetStatus")
        except OperationFailure as e:
            if "not authorized" in str(e):
                print("读取集群状态被拒绝（该环境已开启认证，属正常）：用 rs.status() 或副本集连接串查看")
                return True
            last = str(e).split(",")[0]
            time.sleep(1)
            continue
        except PyMongoError as e:
            last = str(e).split(",")[0]
            time.sleep(1)
            continue
        roles = {m["name"]: m["stateStr"] for m in st["members"]}
        primary = [n for n, r in roles.items() if r == "PRIMARY"]
        if not primary:
            # 刚 initiate 时成员还在 STARTUP，继续等选举
            last = "成员状态：%s" % ", ".join("%s=%s" % kv for kv in roles.items())
            time.sleep(1)
            continue
        print("集群状态：集合 %s，成员 %d 个" % (st.get("set", "?"), len(roles)))
        for name, role in roles.items():
            print("    %-24s %s" % (name, role))
        print("汇总：PRIMARY=%s，SECONDARY=%d 个"
              % (primary[0], sum(1 for r in roles.values() if r == "SECONDARY")))
        return True
    print("集群尚未就绪（最后一次错误：%s）" % last)
    return False


def main():
    cfg = load_config()
    uri = os.environ.get("MONGODB_STANDALONE_URI") or cfg.get("standalone_uri")
    if not uri:
        print("未找到单节点连接串：请在 config.json 填写 standalone_uri，"
              "或设置环境变量 MONGODB_STANDALONE_URI")
        return 2
    hosts = members_from(cfg)
    if not hosts:
        print("未找到成员列表：请在 config.json 填写 repl_members，"
              "或设置环境变量 MONGODB_REPL_MEMBERS（逗号分隔）")
        return 2

    print("正在直连单节点：%s" % uri)
    client = MongoClient(uri, serverSelectionTimeoutMS=6000)
    try:
        hello = client.admin.command("hello")
    except PyMongoError as e:
        print("连接失败：%s" % str(e).split(",")[0])
        print("请先启动 mongod（不加 --replSet 也可，但初始化后需要带 --replSet 重启）")
        return 3

    # 集合名优先级：节点上报的 setName > 启动参数里的 --replSet > 环境变量 > 配置 > rs0
    # 未初始化的节点 hello 里没有 setName，只能从启动参数取，否则服务端会拒绝初始化
    name = (hello.get("setName") or detect_set_name(client)
            or os.environ.get("MONGODB_REPL_SET") or cfg.get("repl_set") or "rs0")
    if hello.get("setName"):
        print("该节点已属于副本集 %s，当前角色 %s，无需重复初始化"
              % (hello["setName"], "PRIMARY" if hello.get("isWritablePrimary") else "SECONDARY"))
        rs_client = MongoClient(uri.replace("directConnection=true", "replicaSet=" + hello["setName"]),
                               serverSelectionTimeoutMS=6000)
        print_status(rs_client)
        return 0

    doc = {"_id": name,
           "members": [{"_id": i, "host": h, "priority": 2 if i == 0 else 1}
                       for i, h in enumerate(hosts)]}
    print("将要初始化的成员（第 1 个 priority=2，优先成为主）：%s" % ", ".join(hosts))
    print("正在发送 replSetInitiate ...")
    try:
        client.admin.command("replSetInitiate", doc)
        print("replSetInitiate 已接受")
    except OperationFailure as e:
        msg = (e.details or {}).get("errmsg", str(e))
        if "already initialized" in msg:
            print("提示：该节点已初始化过，跳过（%s）" % msg.split(",")[0])
        else:
            print("初始化失败：%s" % msg)
            return 4
    except PyMongoError as e:
        print("初始化失败：%s" % str(e).split(",")[0])
        return 4

    print("等待集群完成选举（最长 25 秒）...")
    ok = print_status(client)
    if not ok:
        print("提示：确认三个 mongod 都用同一 --replSet %s 启动，且相互可达（bindIp / keyFile 一致）" % name)
        return 5
    print("初始化完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())