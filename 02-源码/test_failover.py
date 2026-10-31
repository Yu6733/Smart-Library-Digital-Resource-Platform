# -*- coding: utf-8 -*-
"""故障转移演示脚本：连接串与库名统一来自 mongodb_connect（config.json / 环境变量）。

流程：
    1) 先运行本脚本，它会写一条基线文档；
    2) 按提示在另一个窗口结束主节点的 mongod 进程（taskkill /F /PID <pid>），模拟宕机；
    3) 脚本会自动发现写入中断，并持续重试直到新主选出，打印中断时长与恢复耗时。
"""
import time

from pymongo import errors

from mongodb_connect import MONGO_DB, get_client, print_connection_status

COLL = "failover_demo"


def write(tag):
    db = get_client()[MONGO_DB]
    db[COLL].insert_one({"msg": tag, "time": time.time()})
    return db[COLL].count_documents({})


def main():
    print_connection_status()
    n = write("故障转移前写入")
    print("写入成功，当前 %s 文档数 %d" % (COLL, n))
    print("")
    print(">>> 现在请在另一个窗口结束主节点的 mongod 进程（taskkill /F /PID <pid>）<<<")
    print(">>> 脚本会持续探测，发现中断后每 2 秒重试，直到新主可写（最长 120 秒）<<<")
    print("")

    t_start = time.time()
    down_at = None
    t_down = None
    fails = 0
    while time.time() - t_start < 120:
        try:
            write("故障转移期间探测")
            if down_at is not None:
                print("")
                print("切换完成：新主已可写，%s 文档数 %d"
                      % (COLL, get_client()[MONGO_DB][COLL].count_documents({})))
                print("写入中断时长约 %.1f 秒，期间失败重试 %d 次，恢复写入发生在检测到停机后 %.1f 秒"
                      % (time.time() - t_down, fails, time.time() - t_down))
                return
            time.sleep(1)
        except errors.PyMongoError as e:
            if down_at is None:
                down_at = time.time()
                t_down = down_at
                print("[%s] 检测到写入中断（%s），开始重试等待新主选出 ..."
                      % (time.strftime("%H:%M:%S"), str(e).split(":")[0]))
            fails += 1
            time.sleep(2)
        except Exception as e:
            print("[非数据库错误] %s" % e)
            return

    if down_at is None:
        print("120 秒内写入一直正常，未检测到主节点停机：请确认是否结束了 mongod 进程。")
    else:
        print("中断后 120 秒仍未恢复写入，请检查集群是否还有可用节点。")


if __name__ == "__main__":
    main()
