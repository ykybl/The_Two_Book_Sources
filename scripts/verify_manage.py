#!/usr/bin/env python3
"""
定期维护校验 — 仅算法2
用法: python verify_manage.py
"""
import json, os, sys, glob, urllib3
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_v2 import check as check_v2

urllib3.disable_warnings()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES_DIR = os.path.join(ROOT, "sources")
REPORTS_DIR = os.path.join(ROOT, "reports")


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))


def list_source_files():
    return sorted(glob.glob(os.path.join(SOURCES_DIR, "batch_*.json")))


def run_check(books, workers=32, label=""):
    good, bad, done = [], 0, 0
    total = len(books)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(check_v2, b): b for b in books}
        for f in as_completed(futs):
            b = futs[f]
            done += 1
            if f.result(): good.append(b)
            else: bad += 1
            if done % 50 == 0:
                print(f"  [{label}] {done}/{total} (保留 {len(good)}, 删除 {bad})")
    return good, bad


def main():
    files = list_source_files()
    if not files:
        print("没有书源文件。"); return

    total_before = total_removed = 0
    results = {}

    for fpath in files:
        fname = os.path.basename(fpath)
        books = load_json(fpath)
        total_before += len(books)
        print(f"\n校验 {fname} ({len(books)} 条) — 算法2...")

        good, removed = run_check(books, label=fname)

        if removed > 0:
            save_json(fpath, good)
            print(f"  删除 {removed} 条失效, 保留 {len(good)} 条")
        else:
            print(f"  全部有效")

        total_removed += removed
        results[fname] = {"before": len(books), "after": len(good), "removed": removed}

    print(f"\n总计: {total_before} 条, 删除 {total_removed} 条, 剩余 {total_before - total_removed} 条")

    os.makedirs(REPORTS_DIR, exist_ok=True)
    report = {
        "date": datetime.now().isoformat(), "action": "verify", "algorithm": "v2",
        "total_before": total_before, "total_removed": total_removed,
        "total_after": total_before - total_removed, "files": results,
    }
    rpath = os.path.join(REPORTS_DIR, f"{datetime.now().strftime('%Y-%m-%d')}_verify.json")
    save_json(rpath, report)
    print(f"报告: reports/{os.path.basename(rpath)}")


if __name__ == "__main__":
    main()
