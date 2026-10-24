#!/usr/bin/env python3
"""
插件: 智能合并归档
被 dispatch/add 调度调用
"""
import json, os, glob

SOURCES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "sources")

MAX_FILE_MB = 10
MERGE_THRESHOLD_MB = 5


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))


def list_source_files():
    return sorted(glob.glob(os.path.join(SOURCES_DIR, "batch_*.json")))


def _size_of(books):
    tmp = json.dumps(books, ensure_ascii=False, separators=(",", ":"))
    return len(tmp.encode("utf-8"))


def merge(new_books):
    """智能合并新书源到已有文件，返回更新的文件路径列表"""
    new_size = _size_of(new_books)
    new_mb = new_size / 1024 / 1024
    existing = list_source_files()

    if new_mb < MERGE_THRESHOLD_MB and existing:
        last_file = existing[-1]
        last_books = load_json(last_file)
        combined = os.path.getsize(last_file) + new_size

        if combined <= MAX_FILE_MB * 1024 * 1024:
            last_books.extend(new_books)
            save_json(last_file, last_books)
            return [last_file]

        n = len(existing)
        per = len(new_books) // n
        rem = len(new_books) % n
        updated = []
        idx = 0
        for i, fpath in enumerate(existing):
            cnt = per + (1 if i < rem else 0)
            chunk = new_books[idx:idx + cnt]
            idx += cnt
            if chunk:
                books = load_json(fpath)
                books.extend(chunk)
                save_json(fpath, books)
                updated.append(fpath)
        return updated

    nums = [int(os.path.basename(f).replace("batch_", "").replace(".json", ""))
            for f in existing if os.path.basename(f).startswith("batch_")]
    num = max(nums) + 1 if nums else 1
    fname = f"batch_{num:03d}.json"
    fpath = os.path.join(SOURCES_DIR, fname)
    save_json(fpath, new_books)
    return [fpath]
