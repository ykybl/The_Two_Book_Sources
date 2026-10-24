#!/usr/bin/env python3
"""
合并插件 — 智能归档新书源
用法: python merge_manage.py <新书源JSON文件>

规则:
- 每个文件不超过10MB
- 新书源总大小<5MB时，优先合并到上一个文件
- 若合并后超过10MB，则均匀分配到所有已有文件
- 新书源≥5MB时，新建batch文件
"""
import json, os, sys, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES_DIR = os.path.join(ROOT, "sources")

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
    """将校验后的新书源智能合并到已有文件，返回更新的文件列表"""
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
            print(f"合并到 {os.path.basename(last_file)} ({len(last_books)}条, {combined/1024/1024:.2f}MB)")
            return [last_file]

        print(f"合并后超10MB，均匀分配到{len(existing)}个文件...")
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

    # >=5MB，新建
    nums = [int(os.path.basename(f).replace("batch_", "").replace(".json", ""))
            for f in existing if os.path.basename(f).startswith("batch_")]
    num = max(nums) + 1 if nums else 1
    fname = f"batch_{num:03d}.json"
    fpath = os.path.join(SOURCES_DIR, fname)
    save_json(fpath, new_books)
    print(f"新建 {fname} ({len(new_books)}条, {new_mb:.2f}MB)")
    return [fpath]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    books = load_json(sys.argv[1])
    merge(books)
