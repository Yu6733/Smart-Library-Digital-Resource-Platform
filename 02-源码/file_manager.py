# -*- coding: utf-8 -*-
import json
import os
from datetime import datetime
from mongodb_connect import get_fs, get_collection
import audit_manager as am


def upload_ebooks():
    """上传电子书和封面到 GridFS（自动读取项目下的 gridfs_files 文件夹）"""
    fs = get_fs()
    
    # 自动定位到项目根目录下的 gridfs_files
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_dir = os.path.join(base_dir, "gridfs_files")
    manifest_path = os.path.join(file_dir, "files_manifest.txt")

    if not os.path.exists(manifest_path):
        print(f"[错误] 找不到清单文件: {manifest_path}")
        print("[提示] 请确保项目根目录下有 gridfs_files 文件夹，且包含 files_manifest.txt")
        return

    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)
    
    files_to_upload = manifest.get("ebooks", []) + manifest.get("covers", [])
    success_count = 0
    
    for item in files_to_upload:
        filename = item["filename"]
        isbn = item["related_isbn"]
        filepath = os.path.join(file_dir, filename)

        if not os.path.exists(filepath):
            print(f"[警告] 找不到文件: {filename}")
            continue

        # 防止重复上传，先查询是否已存在
        if fs.find_one({"filename": filename}):
            print(f"[跳过] {filename} 已存在 GridFS 中。")
            continue

        # 元数据：关联 ISBN、文件类型、原始文件名、上传时间、所属分类
        book = get_collection("books").find_one({"isbn": isbn},
                                                {"category": 1})
        meta = {
            "isbn": isbn,
            "type": "pdf" if filename.endswith('.pdf') else "image",
            "original_name": filename,
            "upload_date": datetime.now(),
            "category": (book or {}).get("category", "未知"),
        }
        with open(filepath, 'rb') as f:
            file_id = fs.put(f, filename=filename, metadata=meta)
            print(f"[上传] 成功: {filename} (关联ISBN: {isbn})")
            success_count += 1

    print(f"[完成] 本次共上传 {success_count} 个文件。")
    am.log_action("admin", "UPLOAD_FILES", {"count": success_count})


def download_and_verify(isbn):
    """按 ISBN 查找电子书并下载到当前项目目录，校验字节数"""
    fs = get_fs()
    books = get_collection("books")

    book = books.find_one({"isbn": isbn})
    if not book or "ebook_name" not in book:
        print(f"[失败] 未找到 ISBN {isbn} 关联的电子书")
        return

    filename = book["ebook_name"]
    try:
        grid_out = fs.find_one({"filename": filename})
        if not grid_out:
            print(f"[失败] GridFS 中不存在文件 {filename}")
            return

        # 保存到本脚本所在的项目目录（不依赖当前工作目录）
        save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "downloaded_" + filename)

        with open(save_path, 'wb') as f:
            f.write(grid_out.read())

        original_size = grid_out.length
        downloaded_size = os.path.getsize(save_path)

        print(f"[下载] 文件已保存至项目目录: downloaded_{filename}")
        print(f"       原始字节数: {original_size}")
        print(f"       下载字节数: {downloaded_size}")

        if original_size == downloaded_size:
            print("✅ [校验成功] 字节数完全一致！")
            am.log_action("libReader", "DOWNLOAD_VERIFY",
                          {"isbn": isbn, "file": filename,
                           "bytes": downloaded_size, "result": "MATCH"})
        else:
            print("❌ [校验失败] 字节数不一致！")
            am.log_action("libReader", "DOWNLOAD_VERIFY",
                          {"isbn": isbn, "file": filename,
                           "bytes": downloaded_size, "result": "MISMATCH"})
    except Exception as e:
        print(f"[错误] 下载失败: {e}")


def download_by_title(keyword):
    """按书名关键字查询图书，取其中带电子书的一本下载并校验字节数"""
    books = get_collection("books")
    rows = list(books.find({"title": {"$regex": keyword}},
                           {"isbn": 1, "title": 1, "author": 1, "ebook_name": 1})
                .limit(10))
    if not rows:
        print(f"[失败] 没有书名包含「{keyword}」的图书")
        return

    print(f"[查询] 书名包含「{keyword}」的图书共 {len(rows)} 本：")
    for b in rows:
        print("  ISBN %s | %s | 电子书: %s" % (
            b.get("isbn"), b.get("title"), b.get("ebook_name") or "（无）"))

    target = next((b for b in rows if b.get("ebook_name")), None)
    if not target:
        print("[失败] 上述图书均未关联电子书")
        return

    print("[选书] 取第一本带电子书的：%s（ISBN %s）" % (target.get("title"), target.get("isbn")))
    am.log_action("libReader", "QUERY_BOOK_BY_TITLE",
                  {"keyword": keyword, "hits": len(rows), "isbn": target.get("isbn")})
    download_and_verify(target.get("isbn"))


def list_gridfs_files():
    """列出 GridFS 所有文件及大小时间"""
    fs = get_fs()
    files = fs.find()
    count = 0
    for f in files:
        print(f"  文件名: {f.filename:<15} | 大小: {f.length} bytes | 上传时间: {f.upload_date}")
        meta = f.metadata or {}
        print("    元数据: 关联ISBN=%s | 类型=%s | 原始文件名=%s | 分类=%s | 记录上传时间=%s"
              % (meta.get("isbn", "-"), meta.get("type", "-"),
                 meta.get("original_name", "-"), meta.get("category", "-"),
                 meta.get("upload_date", "-")))
        count += 1
    if count == 0:
        print("  GridFS 中暂无文件。")