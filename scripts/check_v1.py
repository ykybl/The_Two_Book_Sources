#!/usr/bin/env python3
"""
算法1: xin-verify-book-source 校验逻辑
GET bookSourceUrl, 状态码200即有效
"""
import requests, urllib3

urllib3.disable_warnings()
HEADERS = {"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def check(book, timeout=5):
    """返回 True=有效, False=无效"""
    url = book.get("bookSourceUrl", "")
    if not url:
        return False
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, verify=False, allow_redirects=True)
        return r.status_code == 200
    except Exception:
        return False
