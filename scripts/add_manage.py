#!/usr/bin/env python3
"""
添加新书源 — 三重过滤 2→1→2
用法: python add_manage.py <新书源文件或URL>
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


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))


def list_source_files():
    return sorted(glob.glob(os.path.join(SOURCES_DIR, "batch_*.json")))


def collect_all_urls(exclude_file=None):
    urls = set()
    for f in list_source_files():
        if f == exclude_file:
            continue
        for book in load_json(f):
            u = book.get("bookSourceUrl", "").rstrip("/")
            if u:
                urls.add(u)
    return urls


def next_batch_number():
    existing = [os.path.basename(f) for f in list_source_files()]
    nums = [int(f.replace("batch_", "").replace(".json", "")) for f in existing if f.startswith("batch_")]
    return max(nums) + 1 if nums else 1


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


def main(input_path):
    if input_path.startswith("http"):
        books = requests.get(input_path, verify=False, headers=HEADERS, timeout=30).json()
    else:
        books = load_json(input_path)

    raw_count = len(books)
    print(f"新书源原始数量: {raw_count}")

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

    num = next_batch_number()
    fname = f"batch_{num:03d}.json"
    fpath = os.path.join(SOURCES_DIR, fname)
    save_json(fpath, final)
    size_mb = os.path.getsize(fpath) / 1024 / 1024
    print(f"\n已保存: sources/{fname} ({len(final)} 条, {size_mb:.2f}MB)")

    os.makedirs(REPORTS_DIR, exist_ok=True)
    report = {
        "date": datetime.now().isoformat(), "action": "add",
        "raw": raw_count, "duplicates_removed": dup_removed,
        "v2_first_removed": r1, "v1_removed": r2, "v2_final_removed": r3,
        "added": len(final), "file": f"sources/{fname}",
    }
    rpath = os.path.join(REPORTS_DIR, f"{datetime.now().strftime('%Y-%m-%d')}_add.json")
    save_json(rpath, report)
    print(f"报告: reports/{os.path.basename(rpath)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    main(sys.argv[1])
