#!/usr/bin/env python3
"""
调度: 添加新书源
流程: 去重 → 算法2 → 算法1 → 算法2 → 合并插件
用法: python dispatch/add.py <新书源文件或URL>
"""
import json, os, sys, glob, urllib3, requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(SCRIPT_DIR))
from plug.check_v1 import check as check_v1
from plug.check_v2 import check as check_v2
from plug.merge import merge

urllib3.disable_warnings()
ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
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


def collect_all_urls():
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

    print(f"\n=== 第1重: 算法2 ===")
    after_v2, r1 = run_check(deduped, check_v2, "v2")
    print(f"算法2: {len(deduped)} → {len(after_v2)} (淘汰 {r1})")

    print(f"\n=== 第2重: 算法1 ===")
    after_v1, r2 = run_check(after_v2, check_v1, "v1")
    print(f"算法1: {len(after_v2)} → {len(after_v1)} (淘汰 {r2})")

    print(f"\n=== 第3重: 算法2终验 ===")
    final, r3 = run_check(after_v1, check_v2, "v2终验")
    print(f"终验: {len(after_v1)} → {len(final)} (淘汰 {r3})")

    if not final:
        print("三重过滤后无有效书源。"); return

    print(f"\n=== 合并归档 ===")
    updated = merge(final)
    for f in updated:
        print(f"  更新: {os.path.basename(f)}")

    os.makedirs(REPORTS_DIR, exist_ok=True)
    report = {
        "date": datetime.now().isoformat(), "action": "add",
        "raw": raw_count, "duplicates_removed": dup_removed,
        "v2_first_removed": r1, "v1_removed": r2, "v2_final_removed": r3,
        "added": len(final), "updated_files": [os.path.basename(f) for f in updated],
    }
    rpath = os.path.join(REPORTS_DIR, f"{datetime.now().strftime('%Y-%m-%d')}_add.json")
    save_json(rpath, report)
    print(f"报告: reports/{os.path.basename(rpath)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    main(sys.argv[1])
