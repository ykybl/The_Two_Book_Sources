#!/usr/bin/env python3
"""
The Two Book Sources — 总调度入口
用法:
  python manage.py add <新书源文件或URL>   # 添加新书源 (2→1→2)
  python manage.py verify                   # 定期维护校验 (算法2)
  python manage.py stats                    # 显示统计
"""
import os, sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "add" and len(sys.argv) >= 3:
        import add_manage
        add_manage.main(sys.argv[2])

    elif cmd == "verify":
        import verify_manage
        verify_manage.main()

    elif cmd == "stats":
        import glob, json
        sources_dir = os.path.join(os.path.dirname(SCRIPT_DIR), "sources")
        files = sorted(glob.glob(os.path.join(sources_dir, "batch_*.json")))
        total = 0
        print(f"{'文件':<25} {'条数':>8} {'大小':>10}")
        print("-" * 45)
        for f in files:
            books = json.load(open(f, encoding="utf-8"))
            size = os.path.getsize(f) / 1024 / 1024
            total += len(books)
            print(f"{os.path.basename(f):<25} {len(books):>8} {size:>8.2f}MB")
        print("-" * 45)
        print(f"{'合计':<25} {total:>8}")

    else:
        print(__doc__)


if __name__ == "__main__":
    main()
