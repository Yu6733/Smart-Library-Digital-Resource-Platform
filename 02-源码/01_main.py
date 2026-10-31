# -*- coding: utf-8 -*-
import sys
from pymongo.errors import PyMongoError

import mongodb_connect as mc
import book_manager as bm
import reader_manager as rm
import stat_manager as sm
import file_manager as fm
import audit_manager as am
import data_initializer as di

def print_menu():
    print("\n" + "=" * 50)
    print("        智慧图书馆数字资源平台 - 主菜单")
    print("=" * 50)
    print(" 0. ★ 一键初始化导入数据 (请优先执行)")  # <-- 改成了这里
    print("-" * 50)
    print(" 1. 查看数据库连接状态与集合文档数")
    print(" 2. 条件检索图书（按类别）")
    print(" 3. 评分排行 TOP 5")
    print(" 4. 新增一本图书")
    print(" 5. 更新图书库存")
    print(" 6. 删除图书")
    print(" 7. 读者学院统计")
    print(" 8. 借阅趋势统计（年月）")
    print(" 9. 畅销榜 TOP 5")
    print("10. 分类统计（库存/均价/数量）")
    print("--- 文件存储与日志 ---")
    print("11. 批量上传电子书与封面 (自动读取 gridfs_files)")
    print("12. 按 ISBN 下载电子书并校验大小")
    print("13. 查看 GridFS 文件清单")
    print("14. 查看最近操作日志")
    print("--- 高级任务与验证 ---")
    print("15. 学院借阅排行榜 TOP 5 (多集合联合)")
    print("16. 导出分类统计结果集合")
    print("17. 分片集群查询性能对比演示")
    print("99. 退出")
    print("=" * 50)

def get_float_input(prompt, default=0.0):
    while True:
        try:
            val = input(prompt).strip()
            return float(val) if val else default
        except ValueError:
            print("[提示] 输入格式错误，请输入数字！")

def get_int_input(prompt, default=0):
    while True:
        try:
            val = input(prompt).strip()
            return int(val) if val else default
        except ValueError:
            print("[提示] 输入格式错误，请输入整数！")

def safe_run(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except PyMongoError as e:
        print(f"[数据库错误] {e}")
        print("[提示] 请检查本机的 MongoDB 服务是否已启动！")
    except Exception as e:
        print(f"[错误] {e}")
    return None

def main():
    print("\n正在尝试连接数据库...")
    try:
        mc.print_connection_status()
    except Exception:
        print("\n❌ 连接失败！请确保本机已安装并启动了 MongoDB 服务 (默认端口 27017)")
        sys.exit(1)

    while True:
        print_menu()
        choice = input("请输入功能编号：").strip()

        if choice == "0":
            safe_run(di.initialize_all)
        elif choice == "1":
            safe_run(mc.print_connection_status)
        elif choice == "2":
            cat = input("请输入类别（如 计算机）：").strip()
            books = safe_run(bm.find_books, {"category": cat}, limit=5)
            if books:
                for b in books:
                    print(f"  {b.get('title')} | 作者：{b.get('author')} | 库存：{b.get('stock')}")
            else:
                print("  未找到相关图书。")
        elif choice == "3":
            books = safe_run(bm.top_rated, 5)
            if books:
                for i, b in enumerate(books, 1):
                    print(f"  {i}. {b.get('title')} | 评分：{b.get('rating')}")
        elif choice == "4":
            book = {
                "isbn": input("ISBN：").strip(),
                "title": input("书名：").strip(),
                "author": input("作者：").strip(),
                "category": input("类别：").strip(),
                "price": get_float_input("价格："),
                "stock": get_int_input("库存："),
                "rating": get_float_input("评分："),
                "borrow_count": 0,
            }
            safe_run(bm.add_one, book)
        elif choice == "5":
            isbn = input("请输入 ISBN：").strip()
            delta = get_int_input("库存增减数量（如 -5）：")
            safe_run(bm.update_one_book, {"isbn": isbn}, {"$inc": {"stock": delta}})
        elif choice == "6":
            isbn = input("请输入要删除的图书 ISBN：").strip()
            safe_run(bm.delete_one_book, {"isbn": isbn})
        elif choice == "7":
            stats = safe_run(rm.college_stats)
            if stats:
                for s in stats: print(f"  {s['_id']}：{s['count']} 人")
        elif choice == "8":
            trend = safe_run(sm.borrow_trend)
            if trend:
                for t in trend: print(f"  {t['_id']}：{t['borrow_count']} 次")
        elif choice == "9":
            books = safe_run(sm.bestsellers, 5)
            if books:
                for i, b in enumerate(books, 1): print(f"  {i}. {b.get('title')} | 借阅：{b.get('borrow_count')}")
        elif choice == "10":
            stats = safe_run(sm.category_stats)
            if stats:
                print("[提示] 统计结果已写入 category_summary 集合并返回：")
                for s in stats: print(f"  {s['_id']}：库存 {s['total_stock']} | 均价 {s['avg_price']:.2f} | 数量 {s['book_count']}")
        elif choice == "11":
            # 【修改点】不再需要输入路径
            print("正在从项目根目录下的 gridfs_files 文件夹读取并上传...")
            safe_run(fm.upload_ebooks)
        elif choice == "12":
            # 任务四要求：既可按 ISBN 也可按书名查询电子书并下载
            key = input("请输入要下载的图书 ISBN 或书名关键字（如 9787115428028 / 数据库）：").strip()
            if key.isdigit():
                safe_run(fm.download_and_verify, key)
            else:
                safe_run(fm.download_by_title, key)
        elif choice == "13":
            print("--- GridFS 文件清单 ---")
            safe_run(fm.list_gridfs_files)
        elif choice == "14":
            logs = safe_run(am.get_recent_logs, 10)
            if logs:
                for log in logs:
                    print("  [%s] %s 执行 %s | 详情: %s" % (
                        log.get("operation_time", "-"), log.get("operator", "-"),
                        log.get("action", "-"), log.get("details", "-")))
        elif choice == "15":
            stats = safe_run(sm.college_borrow_top5)
            if stats:
                for s in stats: print(f"  {s['_id']}：{s['borrow_count']} 次借阅")
        elif choice == "16":
            safe_run(sm.export_category_summary)
        elif choice == "17":
            print("--- 分片集群查询性能对比 ---")
            safe_run(sm.sharding_query_demo)
        elif choice == "99" or choice == "0" and False: # 纯退出
            print("正在退出...")
            mc.close_client()
            sys.exit(0)
        else:
            print("[提示] 无效编号，请重新输入")

if __name__ == "__main__":
    main()