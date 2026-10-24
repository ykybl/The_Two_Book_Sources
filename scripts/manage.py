#!/usr/bin/env python3
"""
The Two Book Sources - 书源管理脚本

用法:
  python manage.py add <新书源文件或URL>   # 添加新书源（自动去重+校验）
  python manage.py verify                   # 校验全部书源，删除失效的
  python manage.py stats                    # 显示当前统计
"""
import json, os, sys, glob, urllib3, requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

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


def check_url(url, timeout=5):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, verify=False, allow_redirects=True)
        return r.status_code == 200
    except Exception:
        return False


def add_sources(input_path):
    if input_path.startswith("http"):
        books = requests.get(input_path, verify=False, headers=HEADERS, timeout=30).json()
    else:
        books = load_json(input_path)
    raw_count = len(books)
    print(f"新书源原始数量: {raw_count}")

    existing_urls = collect_all_urls()
    deduped = []
    dup_removed = 0
    seen = set()
    for b in books:
        u = b.get("bookSourceUrl", "").rstrip("/")
        if not u:
            continue
        if u in existing_urls or u in seen:
            dup_removed += 1
            continue
        seen.add(u)
        deduped.append(b)
    print(f"去重删除: {dup_removed} 条")
    print(f"去重后剩余: {len(deduped)} 条")

    if not deduped:
        print("没有新书源可添加。")
        return

    print(f"开始校验 {len(deduped)} 条书源 URL...")
    good = []
    bad = 0
    done = 0
    with ThreadPoolExecutor(max_workers=32) as pool:
        futures = {pool.submit(check_url, b.get("bookSourceUrl", "")): b for b in deduped}
        for fut in as_completed(futures):
            book = futures[fut]
            done += 1
            if fut.result():
                good.append(book)
            else:
                bad += 1
            if done % 50 == 0:
                print(f"  进度 {done}/{len(deduped)} (有效 {len(good)}, 无效 {bad})")
    print(f"校验完成: 有效 {len(good)}, 无效 {bad}")

    if not good:
        print("没有有效书源可保存。")
        return

    num = next_batch_number()
    fname = f"batch_{num:03d}.json"
    fpath = os.path.join(SOURCES_DIR, fname)
    save_json(fpath, good)
    size_mb = os.path.getsize(fpath) / 1024 / 1024
    print(f"已保存: sources/{fname} ({len(good)} 条, {size_mb:.2f}MB)")

    os.makedirs(REPORTS_DIR, exist_ok=True)
    report = {
        "date": datetime.now().isoformat(),
        "action": "add",
        "raw": raw_count,
        "duplicates_removed": dup_removed,
        "invalid_removed": bad,
        "added": len(good),
        "file": f"sources/{fname}",
    }
    report_path = os.path.join(REPORTS_DIR, f"{datetime.now().strftime('%Y-%m-%d')}_add.json")
    save_json(report_path, report)


def verify_all():
    files = list_source_files()
    if not files:
        print("没有书源文件。")
        return
    total_before = 0
    total_removed = 0
    results = {}
    for fpath in files:
        fname = os.path.basename(fpath)
        books = load_json(fpath)
        total_before += len(books)
        print(f"\n校验 {fname} ({len(books)} 条)...")
        good = []
        removed = 0
        done = 0
        with ThreadPoolExecutor(max_workers=32) as pool:
            futures = {pool.submit(check_url, b.get("bookSourceUrl", "")): b for b in books}
            for fut in as_completed(futures):
                book = futures[fut]
                done += 1
                if fut.result():
                    good.append(book)
                else:
                    removed += 1
                if done % 100 == 0:
                    print(f"  进度 {done}/{len(books)} (保留 {len(good)}, 删除 {removed})")
        if removed > 0:
            save_json(fpath, good)
            print(f"  {fname}: 删除 {removed} 条失效, 保留 {len(good)} 条")
        else:
            print(f"  {fname}: 全部有效")
        total_removed += removed
        results[fname] = {"before": len(books), "after": len(good), "removed": removed}
    print(f"\n总计: 校验前 {total_before}, 删除 {total_removed}, 剩余 {total_before - total_removed}")


def stats():
    files = list_source_files()
    total = 0
    print(f"{'文件':<25} {'条数':>8} {'大小':>10}")
    print("-" * 45)
    for f in files:
        books = load_json(f)
        size = os.path.getsize(f) / 1024 / 1024
        total += len(books)
        print(f"{os.path.basename(f):<25} {len(books):>8} {size:>8.2f}MB")
    print("-" * 45)
    print(f"{'合计':<25} {total:>8}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "add" and len(sys.argv) >= 3:
        add_sources(sys.argv[2])
    elif cmd == "verify":
        verify_all()
    elif cmd == "stats":
        stats()
    else:
        print(__doc__)
