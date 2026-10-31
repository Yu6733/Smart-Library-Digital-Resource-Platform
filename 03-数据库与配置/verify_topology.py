
# -*- coding: utf-8 -*-
"""拓扑核验脚本（老师自查用）：检查多端口是否在监听、副本集一主两从、分片两片是否都有数据。
用法：在 03-数据库与配置 目录下执行  python verify_topology.py
连接串取自 ../02-源码/config.json，可用环境变量 MONGODB_ADMIN_URI / MONGODB_SHARD_URI / MONGODB_SHARD_ADMIN_URI 覆盖。
"""
import json
import os
import socket
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = os.path.join(HERE, "..", "02-源码", "config.json")

REPL_PORTS = [27017, 27018, 27019]
SHARD_PORTS = [27200, 27201, 27202, 27217]


def line(title):
    print("\n" + "=" * 62)
    print(title)
    print("=" * 62)


def port_open(port, host="127.0.0.1", timeout=0.6):
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def load_cfg():
    if not os.path.exists(CFG):
        print("[!!] 未找到 %s" % os.path.abspath(CFG))
        return {}
    with open(CFG, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    cfg = load_cfg()
    admin_uri = os.environ.get("MONGODB_ADMIN_URI") or cfg.get("admin_uri")
    shard_uri = os.environ.get("MONGODB_SHARD_URI") or cfg.get("shard_uri")
    shard_admin_uri = os.environ.get("MONGODB_SHARD_ADMIN_URI") or cfg.get("shard_admin_uri")
    if any("CHANGE_ME" in (u or "") for u in (admin_uri, shard_uri, shard_admin_uri)):
        print("[提示] config.json 里的连接串密码仍是占位符 CHANGE_ME。")
        print("       请先按 启动与部署说明.md 第 2 节创建账号（libAdmin/libReader/libWriter/shardAdmin/libApp），")
        print("       再把 config.json 中四条连接串的 CHANGE_ME 替换成实际密码后重跑本脚本。")
        return 5
    members = cfg.get("repl_members") or ["127.0.0.1:27017", "127.0.0.1:27018", "127.0.0.1:27019"]

    line("一、端口监听检查（副本集 27017/27018/27019，分片 27200/27201/27202/27217）")
    ok_ports = 0
    for p in REPL_PORTS + SHARD_PORTS:
        alive = port_open(p)
        ok_ports += 1 if alive else 0
        tag = "副本集节点" if p in REPL_PORTS else ("mongos" if p == 27217 else "分片/配置节点")
        print("  端口 %-6d %-12s %s" % (p, tag, "监听中" if alive else "未监听"))
    print("  合计：%d / %d 个端口在监听" % (ok_ports, len(REPL_PORTS + SHARD_PORTS)))

    from pymongo import MongoClient
    from pymongo.errors import PyMongoError

    line("二、副本集 rs0：成员、角色与优先级")
    if not admin_uri:
        print("  [!!] 没有 admin_uri，跳过副本集检查")
    else:
        try:
            adm = MongoClient(admin_uri, serverSelectionTimeoutMS=8000)
            st = adm.admin.command("replSetGetStatus")
            print("  集合名：%s" % st.get("set"))
            print("  成员数：%d" % len(st.get("members", [])))
            for m in st["members"]:
                print("    %-22s %-10s health=%s uptime=%ss" % (m["name"], m.get("stateStr"), m.get("health"), m.get("uptime")))
            conf = adm.admin.command("replSetGetConfig")["config"]
            pr = {m["host"]: m.get("priority", 1) for m in conf["members"]}
            print("  优先级：%s（主节点故意设为 2，重启后按优先级重新当选）" % ", ".join("%s=%s" % kv for kv in pr.items()))
            prim = [m["name"] for m in st["members"] if m.get("stateStr") == "PRIMARY"]
            if len(prim) == 1:
                print("  结论：一主 %d 从，主节点 %s" % (len(st["members"]) - 1, prim[0]))
            else:
                print("  结论：当前没有唯一主节点，请稍等几秒再运行")
            print("  连接串种子地址：%s" % ",".join(members))
        except PyMongoError as e:
            print("  [!!] 副本集检查失败：%s" % str(e).split(", full error")[0])

    line("三、分片集群：分片清单与数据分布")
    dbname = cfg.get("db", "library")
    if shard_admin_uri:
        try:
            sh = MongoClient(shard_admin_uri, serverSelectionTimeoutMS=8000)
            shards = sh.admin.command("listShards")["shards"]
            print("  分片数：%d" % len(shards))
            for s in shards:
                print("    分片 %-5s %-26s state=%s" % (s["_id"], s["host"], s.get("state")))
        except PyMongoError as e:
            print("  [!!] listShards 失败（需要 shardAdmin/clusterAdmin 权限）：%s" % str(e).split(", full error")[0])
    else:
        print("  [!!] 没有 shard_admin_uri，跳过分片清单（可用 shardAdmin 账号连 27217 查看）")

    if shard_uri:
        try:
            sh = MongoClient(shard_uri, serverSelectionTimeoutMS=8000)
            for coll in ("borrow_logs",):
                try:
                    cs = sh[dbname].command("collStats", coll)
                    dist = cs.get("shards", {})
                    total = sum(v.get("count", 0) for v in dist.values())
                    print("\n  %s.%s 共 %d 条，分布：" % (dbname, coll, total))
                    for name, v in dist.items():
                        pct = 100.0 * v.get("count", 0) / total if total else 0
                        print("    %-5s %6d 条 (%.1f%%)" % (name, v.get("count", 0), pct))
                    both = [1 for v in dist.values() if v.get("count", 0) > 0]
                    print("  结论：%s" % ("两个分片都有数据（分片键生效）" if len(both) >= 2 else "只有一片有数据，请检查分片键"))
                except PyMongoError as e:
                    print("  [!!] %s 分布检查失败：%s" % (coll, str(e).split(", full error")[0]))
        except PyMongoError as e:
            print("  [!!] 连不上 mongos(27217)：%s" % str(e).split(", full error")[0])

    print("\n提示：图形化可在 Compass 里连三节点种子地址（标题栏会显示三个地址），")
    print("      连 27217 后在 Shell 里跑 sh.status() 看分片；命令行没装 mongosh 时用本脚本即可。")
    return 0


if __name__ == "__main__":
    sys.exit(main())