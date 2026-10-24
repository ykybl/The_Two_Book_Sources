#!/usr/bin/env python3
"""
The Two Book Sources - 书源管理脚本

校验算法:
  算法1 (xin-verify-book-source): GET bookSourceUrl, 状态码200即有效
  算法2 (HarmonyOS-book): 首页可达 + 搜索接口可达性测试

添加新书源流程 (三重过滤):
  1. 算法2 → 2. 算法1 → 3. 归档前再算法2
定期维护校验: 仅算法2

用法:
  python manage.py add <新书源文件或URL>   # 添加新书源（三重过滤）
  python manage.py verify                   # 定期校验（算法2）
  python manage.py stats                    # 显示当前统计
"""
import json, os, re, sys, glob, urllib3, requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

urllib3.disable_warnings()

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES_DIR = os.path.join(ROOT, "sources")
REPORTS_DIR = os.path.join(ROOT, "reports")
HEADERS = {"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# 搜索测试关键词
TEST_KEYWORD = "小说"
# 搜索请求最小返回字节数（低于此视为搜索接口失效）
MIN_SEARCH_BYTES = 100


# ─── 基础工具 ───

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


# ─── 算法1: 首页可达性 ───

def check_v1(book, timeout=5):
    """算法1: GET bookSourceUrl, 状态码200"""
    url = book.get("bookSourceUrl", "")
    if not url:
        return False
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, verify=False, allow_redirects=True)
        return r.status_code == 200
    except Exception:
        return False


# ─── 算法2: 搜索链路可达性 ───

def build_search_url(book):
    """从书源配置解析搜索URL，返回 (method, url_or_none)"""
    search_url = book.get("searchUrl", "").strip()
    if not search_url:
        return None, None

    # Legado searchUrl 格式: "/search?q={{key}}&page={{page}}"
    # 或 POST: "{{page}},{"body":"{{key}}","page":{{page}}}"
    # 检测 POST: 包含 ",," 分隔或以 POST:: 开头
    if search_url.startswith("POST::") or ",," in search_url:
        return "POST", None

    # GET: 替换模板变量
    url = search_url.replace("{{key}}", TEST_KEYWORD).replace("{{page}}", "1")
    # 去掉分页相关的其他模板
    url = re.sub(r"\{\{[^}]+\}\}", "1", url)

    base = book.get("bookSourceUrl", "").rstrip("/")
    if url.startswith("/"):
        url = base + url
    elif not url.startswith("http"):
        url = base + "/" + url
    return "GET", url


def check_v2(book, timeout=8):
    """算法2: 首页可达 + 搜索接口可达性测试"""
    # 第一步: 首页必须可达
    if not check_v1(book, timeout=timeout):
        return False

    # 第二步: 测试搜索接口
    method, search_url = build_search_url(book)

    # 无搜索规则或POST搜索: 首页可达即通过
    if method is None:
        return True
    if method == "POST":
        return True  # POST搜索暂不测试，首页可达即通过

    if not search_url:
        return True

    try:
        r = requests.get(search_url, headers=HEADERS, timeout=timeout, verify=False, allow_redirects=True)
        if r.status_code != 200:
            return False
        # 返回内容不能太短（太短说明搜索接口异常）
        if len(r.content) < MIN_SEARCH_BYTES:
            return False
        return True
    except Exception:
        return False


# ─── 并发校验工具 ───

def run_check(books, check_fn, workers=32, label=""):
    """并发校验，返回 (good_list, bad_count)"""
    good = []
    bad = 0
    done = 0
    total = len(books)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(check_fn, b): b for b in books}
        for fut in as_completed(futures):
            book = futures[fut]
            done += 1
            if fut.result():
                good.append(book)
            else:
                bad += 1
            if done % 50 == 0:
                print(f"  [{label}] {done}/{total} (通过 {len(good)}, 淘汰 {bad})")
    return good, bad


# ─── 添加新书源 (三重过滤) ───

def add_sources(input_path):
    if input_path.startswith("http"):
        books = requests.get(input_path, verify=False, headers=HEADERS, timeout=30).json()
    else:
        books = load_json(input_path)

    raw_count = len(books)
    print(f"新书源原始数量: {raw_count}")

    # 去重
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

    # 三重过滤
    # 第1重: 算法2 (搜索链路)
    print(f"\n=== 第1重过滤: 算法2 (首页+搜索链路) ===")
    after_v2, removed_v2 = run_check(deduped, check_v2, label="算法2")
    print(f"算法2: {len(deduped)} → {len(after_v2)} (淘汰 {removed_v2})")

    # 第2重: 算法1 (首页可达)
    print(f"\n=== 第2重过滤: 算法1 (首页可达) ===")
    after_v1, removed_v1 = run_check(after_v2, check_v1, label="算法1")
    print(f"算法1: {len(after_v2)} → {len(after_v1)} (淘汰 {removed_v1})")

    # 第3重: 归档前再用算法2确认
    print(f"\n=== 第3重过滤: 归档前算法2确认 ===")
    final, removed_final = run_check(after_v1, check_v2, label="算法2终验")
    print(f"终验: {len(after_v1)} → {len(final)} (淘汰 {removed_final})")

    if not final:
        print("三重过滤后无有效书源。")
        return

    # 保存
    num = next_batch_number()
    fname = f"batch_{num:03d}.json"
    fpath = os.path.join(SOURCES_DIR, fname)
    save_json(fpath, final)
    size_mb = os.path.getsize(fpath) / 1024 / 1024
    print(f"\n已保存: sources/{fname} ({len(final)} 条, {size_mb:.2f}MB)")

    # 报告
    os.makedirs(REPORTS_DIR, exist_ok=True)
    report = {
        "date": datetime.now().isoformat(),
        "action": "add",
        "raw": raw_count,
        "duplicates_removed": dup_removed,
        "v2_removed": removed_v2,
        "v1_removed": removed_v1,
        "final_v2_removed": removed_final,
        "added": len(final),
        "file": f"sources/{fname}",
    }
    report_path = os.path.join(REPORTS_DIR, f"{datetime.now().strftime('%Y-%m-%d')}_add.json")
    save_json(report_path, report)
    print(f"报告: reports/{os.path.basename(report_path)}")


# ─── 定期校验 (仅算法2) ───

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
        print(f"\n校验 {fname} ({len(books)} 条) — 算法2...")

        good, removed = run_check(books, check_v2, label=fname)

        if removed > 0:
            save_json(fpath, good)
            print(f"  {fname}: 删除 {removed} 条失效, 保留 {len(good)} 条")
        else:
            print(f"  {fname}: 全部有效")

        total_removed += removed
        results[fname] = {"before": len(books), "after": len(good), "removed": removed}

    print(f"\n总计: {total_before} 条, 删除 {total_removed} 条, 剩余 {total_before - total_removed} 条")

    os.makedirs(REPORTS_DIR, exist_ok=True)
    report = {
        "date": datetime.now().isoformat(),
        "action": "verify",
        "algorithm": "v2",
        "total_before": total_before,
        "total_removed": total_removed,
        "total_after": total_before - total_removed,
        "files": results,
    }
    report_path = os.path.join(REPORTS_DIR, f"{datetime.now().strftime('%Y-%m-%d')}_verify.json")
    save_json(report_path, report)
    print(f"报告: reports/{os.path.basename(report_path)}")


# ─── 统计 ───

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
