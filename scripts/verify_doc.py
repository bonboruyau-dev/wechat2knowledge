#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Step 5：完整性回查。

对比「原文正文」与「已创建的飞书文档」，报告：图片/表格/标题/代码块数量，以及缺失的原文行。

用法：
    # 1) 先取原文 HTML（或复用 Step 2 抓下来的 source.html）
    # 2) 导出文档结构
    "$NODE" "$RUNJS" docs +fetch --doc "<doc_id>" --detail with-ids > _verify.json
    # 3) 比对
    "$PY" verify_doc.py <source.html> <_verify.json>

退出码：0 = 完整；3 = 有缺失行。
"""
import html
import io
import json
import re
import sys

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("需要 beautifulsoup4")
    sys.exit(1)


CONTAINERS = [
    ("id", "js_content"),
    ("class", "rich_media_content"),
]


def source_text(html_path):
    soup = BeautifulSoup(io.open(html_path, encoding="utf-8").read(), "html.parser")
    root = None
    for attr, val in CONTAINERS:
        root = soup.find(attrs={attr: val})
        if root:
            break
    if root is None:
        root = soup.body or soup
    txt = root.get_text("\n", strip=True)
    return re.sub(r"\n{2,}", "\n", txt), root


def doc_text(fetch_json):
    raw = io.open(fetch_json, encoding="utf-8").read()
    j = json.loads(raw[raw.find("{"):])
    original = j["data"]["document"]["content"]
    c = re.sub(r"<img [^>]*/>", "", original)
    c = re.sub(r"<(table|tbody|thead|tr)[^>]*>", "\n", c)
    c = re.sub(r"</(td|th)>", " ", c)
    c = re.sub(r"<[^>]+>", "\n", c)
    c = html.unescape(c)
    lines = [l.strip() for l in c.split("\n") if l.strip()]
    return re.sub(r"\s+", "", "\n".join(lines)), original


def main():
    if len(sys.argv) < 3:
        print("usage: python verify_doc.py <source.html> <lark_fetch.json>")
        return 1
    src, root = source_text(sys.argv[1])
    doc, xml = doc_text(sys.argv[2])

    print("=== 结构统计 ===")
    print("原文  : 图片 %d（含无 src 占位 %d）、表格 %d" % (
        len(root.find_all("img")),
        len([i for i in root.find_all("img") if not (i.get("data-src") or i.get("src"))]),
        len(root.find_all("table")),
    ))
    print("文档  : 图片 %d、表格 %d、h3 %d、代码块 %d、引用 %d" % (
        len(re.findall(r"<img ", xml)),
        len(re.findall(r"<table[ >]", xml)),
        len(re.findall(r"<h3[ >]", xml)),
        len(re.findall(r"<code[ >]", xml)),
        len(re.findall(r"<blockquote[ >]", xml)),
    ))

    missing = []
    for line in src.split("\n"):
        l = line.strip()
        if len(l) < 4:
            continue
        if re.sub(r"\s+", "", l) not in doc:
            missing.append(l)

    print("\n=== 文本比对 ===")
    print("原文纯文本 %d 字 / 文档纯文本 %d 字" % (len(re.sub(r"\s+", "", src)), len(doc)))
    print("缺失行数: %d" % len(missing))
    for m in missing[:50]:
        print("  -", m[:120])

    if missing:
        print("\n注意：代码块内的 &nbsp;(\\xa0) 与加粗标记会造成少量误报，")
        print("      用 grep 确认关键词是否真的在 doc.md 里再下结论。")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
