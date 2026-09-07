#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Step 2.5：图片格式归一化（必须在 lark-cli docs +create 之前跑）。

做两件事：
1. 按 magic bytes 检测真实格式，把「扩展名与内容不符」的图片改名，并同步替换 doc.md 里的引用
   （公众号常见：GIF 动图被存成 .png；SVG 被存成 .gif/.png）。
2. 打印出「内容是 SVG」的文件清单，交给 svg2png.js 转成真 PNG。

用法：
    python normalize_images.py <_build目录>
"""
import io
import os
import sys

MAGIC = [
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
    (b"\xff\xd8\xff", "jpg"),
    (b"BM", "bmp"),
]

TIFF = (b"II*\x00", b"MM\x00*")


def detect(head: bytes):
    if head[:4] in TIFF:
        return "tiff"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    for sig, ext in MAGIC:
        if head.startswith(sig):
            return ext
    if head.lstrip()[:5] in (b"<svg ", b"<svg\n", b"<?xml"):
        return "svg"
    return None


def main():
    if len(sys.argv) < 2:
        print("usage: python normalize_images.py <build_dir>")
        return 1
    root = sys.argv[1]
    img_dir = os.path.join(root, "images")
    doc_path = os.path.join(root, "doc.md")
    if not os.path.isdir(img_dir):
        print("no images dir:", img_dir)
        return 0

    doc = io.open(doc_path, encoding="utf-8").read() if os.path.exists(doc_path) else ""
    doc_changed = False
    svgs = []

    for name in sorted(os.listdir(img_dir)):
        p = os.path.join(img_dir, name)
        if not os.path.isfile(p):
            continue
        with open(p, "rb") as fh:
            head = fh.read(16)
        real = detect(head)
        cur = name.rsplit(".", 1)[-1].lower()
        if real == "svg":
            # SVG 最终会被 svg2png.js 渲染成同名 .png，这里先把扩展名对齐，
            # 避免渲染后 doc.md 还指向已不存在的 .gif/.svg 文件。
            new = name.rsplit(".", 1)[0] + ".png"
            if new != name:
                os.rename(p, os.path.join(img_dir, new))
                if "images/" + name in doc:
                    doc = doc.replace("images/" + name, "images/" + new)
                    doc_changed = True
            svgs.append(new)
            print("SVG (需转 PNG):", name, "->", new)
            continue
        if real and real != cur:
            new = name.rsplit(".", 1)[0] + "." + real
            os.rename(p, os.path.join(img_dir, new))
            if "images/" + name in doc:
                doc = doc.replace("images/" + name, "images/" + new)
                doc_changed = True
            print("renamed", name, "->", new)
        else:
            print("ok", name, real)

    if doc_changed:
        io.open(doc_path, "w", encoding="utf-8").write(doc)
        print("doc.md 引用已同步更新")

    if svgs:
        print("\n>>> 先跑：NODE_PATH=<node_workspace>/node_modules node svg2png.js <images_dir>")
        print(">>> 再跑一次本脚本确认，然后再 docs +create")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
