#!/usr/bin/env python3
"""
添加新书源 — 三重过滤 2→1→2 + 智能合并
用法: python add_manage.py <新书源文件或URL>

合并规则:
- 每个文件不超过10MB
- 新书源总大小<5MB时，优先合并到上一个文件
- 若合并后超过10MB，则均匀分配到所有已有文件
"""
import json, os, sys, glob, urllib3, requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_v1 import check as check_v1
from check_v2 import check as check_v2

urllib3.disable_warnings()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES_DIR = os.path.join(ROOT, "sources")
REPORTS_DIR = os.path.join(ROOT, "reports")
HEADERS = {"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

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


def collect_all_urls():
    """收集仓库内所有已有书源URL"""
    urls = set()
    for f in list_source_files():
        for book in load_json(f):
            u = book.get("bookSourceUrl", "").rstrip("/")
            if u:
                urls.add(u)
    return urls


def run_check(books, check_fn, workers=32, label=""):
    good, bad, done = [], 0, 0
    total = len(books)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(check_fn, b): b for b in books}
        for f in as_completed(futs):
            b = futs[f]
            done += 1
            if f.result(): good.append(b)
            else: bad += 1
            if done % 50 == 0:
                print(f"  [{label}] {done}/{total} (通过 {len(good)}, 淘汰 {bad})")
    return good, bad


def _write_tmp_and_size(books):
    """计算书源列表序列化后的字节大小"""
    tmp = json.dumps(books, ensure_ascii=False, separators=(",", ":"))
    return len(tmp.encode("utf-8"))


def merge_books(new_books):
    """智能合并新书源到已有文件"""
    new_size = _write_tmp_and_size(new_books)
    new_mb = new_size / 1024 / 1024
    existing_files = list_source_files()

    if new_mb < MERGE_THRESHOLD_MB and existing_files:
        # 尝试合并到最后一个文件
        last_file = existing_files[-1]
        last_books = load_json(last_file)
        last_size = os.path.getsize(last_file)
        combined_size = last_size + new_size

        if combined_size <= MAX_FILE_MB * 1024 * 1024:
            last_books.extend(new_books)
            save_json(last_file, last_books)
            print(f"已合并到 {os.path.basename(last_file)} ({len(last_books)} 条, {combined_size/1024/1024:.2f}MB)")
            return [last_file]

        # 合并后超过10MB，均匀分配到所有文件
        print(f"合并到最后文件会超过10MB，均匀分配到 {len(existing_files)} 个文件...")
        n = len(existing_files)
        per_file = len(new_books) // n
        remainder = len(new_books) % n
        updated = []
        idx = 0
        for i, fpath in enumerate(existing_files):
            count = per_file + (1 if i < remainder else 0)
            chunk = new_books[idx:idx + count]
            idx += count
            if chunk:
                books = load_json(fpath)
                books.extend(chunk)
                save_json(fpath, books)
                updated.append(fpath)
        return updated

    # 新书源>=5MB，新建文件
    existing = [os.path.basename(f) for f in existing_files]
    nums = [int(f.replace("batch_", "").replace(".json", "")) for f in existing if f.startswith("batch_")]
    num = max(nums) + 1 if nums else 1
    fname = f"batch_{num:03d}.json"
    fpath = os.path.join(SOURCES_DIR, fname)
    save_json(fpath, new_books)
    print(f"已新建 {fname} ({len(new_books)} 条, {new_mb:.2f}MB)")
    return [fpath]


def main(input_path):
    if input_path.startswith("http"):
        books = requests.get(input_path, verify=False, headers=HEADERS, timeout=30).json()
    else:
        books = load_json(input_path)

    raw_count = len(books)
    print(f"新书源原始数量: {raw_count}")

    # 去重：和仓库内所有已有书源比对
    existing_urls = collect_all_urls()
    deduped, dup_removed, seen = [], 0, set()
    for b in books:
        u = b.get("bookSourceUrl", "").rstrip("/")
        if not u: continue
        if u in existing_urls or u in seen:
            dup_removed += 1
            continue
        seen.add(u)
        deduped.append(b)
    print(f"去重删除: {dup_removed} 条, 剩余: {len(deduped)} 条")
    if not deduped:
        print("没有新书源可添加。"); return

    # 三重过滤: 2 → 1 → 2
    print(f"\n=== 第1重: 算法2 (首页+搜索链路) ===")
    after_v2, r1 = run_check(deduped, check_v2, "v2")
    print(f"算法2: {len(deduped)} → {len(after_v2)} (淘汰 {r1})")

    print(f"\n=== 第2重: 算法1 (首页可达) ===")
    after_v1, r2 = run_check(after_v2, check_v1, "v1")
    print(f"算法1: {len(after_v2)} → {len(after_v1)} (淘汰 {r2})")

    print(f"\n=== 第3重: 算法2 终验 ===")
    final, r3 = run_check(after_v1, check_v2, "v2终验")
    print(f"终验: {len(after_v1)} → {len(final)} (淘汰 {r3})")

    if not final:
        print("三重过滤后无有效书源。"); return

    # 智能合并
    print(f"\n=== 合并归档 ===")
    updated_files = merge_books(final)

    os.makedirs(REPORTS_DIR, exist_ok=True)
    report = {
        "date": datetime.now().isoformat(), "action": "add",
        "raw": raw_count, "duplicates_removed": dup_removed,
        "v2_first_removed": r1, "v1_removed": r2, "v2_final_removed": r3,
        "added": len(final), "updated_files": [os.path.basename(f) for f in updated_files],
    }
    rpath = os.path.join(REPORTS_DIR, f"{datetime.now().strftime('%Y-%m-%d')}_add.json")
    save_json(rpath, report)
    print(f"报告: reports/{os.path.basename(rpath)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    main(sys.argv[1])
