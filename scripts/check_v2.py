#!/usr/bin/env python3
"""
算法2: HarmonyOS-book 校验逻辑（实用版）
首页可达 + 搜索接口可达性测试
"""
import re, requests, urllib3
from check_v1 import check as check_home

urllib3.disable_warnings()
HEADERS = {"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

TEST_KEYWORD = "小说"
MIN_SEARCH_BYTES = 100


def _build_search_url(book):
    """从书源配置解析搜索URL，返回 (method, url_or_none)"""
    search_url = book.get("searchUrl", "").strip()
    if not search_url:
        return None, None

    # POST 搜索: 包含 ",," 分隔或以 POST:: 开头
    if search_url.startswith("POST::") or ",," in search_url:
        return "POST", None

    # GET: 替换模板变量
    url = search_url.replace("{{key}}", TEST_KEYWORD).replace("{{page}}", "1")
    url = re.sub(r"\{\{[^}]+\}\}", "1", url)

    base = book.get("bookSourceUrl", "").rstrip("/")
    if url.startswith("/"):
        url = base + url
    elif not url.startswith("http"):
        url = base + "/" + url
    return "GET", url


def check(book, timeout=8):
    """返回 True=有效, False=无效"""
    # 第一步: 首页必须可达
    if not check_home(book, timeout=timeout):
        return False

    # 第二步: 测试搜索接口
    method, search_url = _build_search_url(book)

    if method is None:
        return True  # 无搜索规则，首页可达即通过
    if method == "POST":
        return True  # POST搜索暂不测试，首页可达即通过
    if not search_url:
        return True

    try:
        r = requests.get(search_url, headers=HEADERS, timeout=timeout, verify=False, allow_redirects=True)
        if r.status_code != 200:
            return False
        if len(r.content) < MIN_SEARCH_BYTES:
            return False
        return True
    except Exception:
        return False
