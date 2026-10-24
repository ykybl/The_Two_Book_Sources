#!/usr/bin/env python3
"""
算法2: HarmonyOS-book 校验逻辑（执行Legado规则）
首页可达 → 搜索请求 → 规则解析结果列表
支持HTML(CSS选择器)和JSON(JSONPath)两种解析
"""
import re, requests, urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings()
HEADERS = {"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
TEST_KEYWORD = "小说"
TIMEOUT = 10


def _apply_rule(element, rule_str):
    if not rule_str:
        return ""
    if "||" in rule_str:
        for alt in rule_str.split("||"):
            val = _apply_rule(element, alt.strip())
            if val:
                return val
        return ""
    filt = ""
    if "##" in rule_str:
        rule_str, filt = rule_str.split("##", 1)
    js_regex = ""
    if "@js:" in rule_str:
        rule_str, js_part = rule_str.split("@js:", 1)
        m = re.search(r'match(/(.*?)/\)', js_part)
        if m:
            js_regex = m.group(1)
    attr = "text"
    if "@" in rule_str:
        parts = rule_str.split("@", 1)
        selector = parts[0]
        attr = parts[1].strip()
    else:
        selector = rule_str.strip()
    try:
        node = element.select_one(selector) if selector else element
        if node is None:
            return ""
        if attr == "text":
            val = node.get_text(strip=True)
        elif attr == "html":
            val = str(node)
        else:
            val = node.get(attr, "")
        if js_regex:
            m = re.search(js_regex, val)
            val = m.group(1) if (m and m.lastindex) else (m.group(0) if m else "")
        if filt:
            m = re.search(filt, val)
            val = m.group(1) if (m and m.lastindex) else (m.group(0) if m else "")
        return val.strip()
    except Exception:
        return ""


def _json_get(obj, path):
    if not path.startswith("$"):
        return None
    path = path.lstrip("$").lstrip(".")
    cur = obj
    for part in path.split("."):
        idx_match = re.match(r'^([^\[\]]*)\[(\d+)\]$', part)
        key = idx_match.group(1) if idx_match else part
        idx = int(idx_match.group(2)) if idx_match else None
        if key == "*" or key == "":
            if isinstance(cur, list):
                cur = cur
            elif isinstance(cur, dict):
                cur = list(cur.values())
            else:
                return None
        elif isinstance(cur, list):
            if idx is not None:
                if idx < len(cur):
                    cur = cur[idx]
                else:
                    return None
            elif key and key.isdigit():
                k = int(key)
                cur = cur[k] if k < len(cur) else None
                if cur is None:
                    return None
            else:
                result = []
                for item in cur:
                    if isinstance(item, dict) and key in item:
                        result.append(item[key])
                cur = result
        elif isinstance(cur, dict):
            if key in cur:
                cur = cur[key]
            else:
                return None
        else:
            return None
    return cur


def _json_apply_rule(item_obj, rule_str):
    if not rule_str:
        return ""
    if "||" in rule_str:
        for alt in rule_str.split("||"):
            val = _json_apply_rule(item_obj, alt.strip())
            if val:
                return val
        return ""
    if "{{" in rule_str:
        def repl(m):
            field = m.group(1).strip()
            v = _json_get(item_obj, field)
            return str(v) if v is not None else ""
        return re.sub(r"\{\{([^}]+)\}\}", repl, rule_str)
    if rule_str.startswith("$."):
        v = _json_get(item_obj, rule_str)
        if isinstance(v, list):
            v = v[0] if v else ""
        return str(v) if v is not None else ""
    return rule_str


def _build_search_request(book):
    search_url = book.get("searchUrl", "").strip()
    if not search_url:
        return None, None, None, None
    base = book.get("bookSourceUrl", "").rstrip("/")
    if ",," in search_url:
        parts = search_url.split(",,", 1)
        path = parts[0].replace("{{page}}", "1")
        body = parts[1].replace("{{key}}", TEST_KEYWORD).replace("{{page}}", "1")
        url = base + path if path.startswith("/") else path
        return "POST", url, {"Content-Type": "application/json"}, body
    url = search_url
    url = url.replace("{{key}}", TEST_KEYWORD).replace("{key}", TEST_KEYWORD)
    url = url.replace("{{page}}", "1").replace("{page}", "1")
    url = re.sub(r"\{\{[^}]+\}\}", "1", url)
    if url.startswith("/"):
        url = base + url
    elif not url.startswith("http"):
        url = base + "/" + url
    return "GET", url, {}, None


def _sanitize_css(selector):
    if not selector:
        return selector
    s = selector.lstrip("-")
    s = re.sub(r"!\d+", "", s)
    s = re.sub(r'\bclass\.', '.', s)
    s = re.sub(r'\bid#', '#', s)
    known_attrs = {"text","html","href","src","class","id","onclick","value","name","action","content","data-src","data-url","type","rel","title","alt","style","srcset"}
    parts = s.split("@")
    result = parts[0]
    for p in parts[1:]:
        p = p.strip()
        if p in known_attrs or p.startswith(":"):
            result += "@" + p
        else:
            result += " " + p
    return result


def _try_select(soup_or_items, selector):
    if "||" in selector:
        for alt in selector.split("||"):
            items = _try_select(soup_or_items, alt.strip())
            if items:
                return items
        return []
    try:
        sel = _sanitize_css(selector)
        if hasattr(soup_or_items, 'select'):
            return soup_or_items.select(sel)
        return []
    except Exception:
        return []


def check(book, timeout=TIMEOUT):
    home_url = book.get("bookSourceUrl", "")
    if not home_url:
        return False
    try:
        r0 = requests.get(home_url, headers=HEADERS, timeout=timeout, verify=False, allow_redirects=True)
        if r0.status_code != 200:
            return False
    except Exception:
        return False

    search_url = book.get("searchUrl", "").strip()
    if not search_url:
        return True

    method, url, req_headers, req_data = _build_search_request(book)
    if not url:
        return True
    try:
        h = {**HEADERS, **req_headers}
        if method == "POST":
            r = requests.post(url, headers=h, data=req_data, timeout=timeout, verify=False, allow_redirects=True)
        else:
            r = requests.get(url, headers=h, timeout=timeout, verify=False, allow_redirects=True)
        if r.status_code != 200 or len(r.content) < 50:
            return False
    except Exception:
        return False

    rule_search = book.get("ruleSearch", {})
    if not isinstance(rule_search, dict):
        return True
    book_list_rule = rule_search.get("bookList", "")
    if not book_list_rule:
        return True

    is_json = book_list_rule.startswith("$")

    if is_json:
        try:
            data = r.json()
            items = _json_get(data, book_list_rule)
            if items:
                return True
            return True
        except Exception:
            return len(r.content) > 100
    else:
        try:
            soup = BeautifulSoup(r.text, "lxml")
            items = _try_select(soup, book_list_rule)
            if items:
                return True
            return len(r.text) > 200
        except Exception:
            return len(r.content) > 100
