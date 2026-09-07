#!/usr/bin/env python3
"""
HTML → 飞书 Markdown 转换器（配套 html-to-feishu-doc 技能）

功能：
  - 接收 HTML 文件或网页 URL，输出 GFM Markdown（doc.md）
  - 标题/段落/列表/引用/代码块/分隔线
  - 表格 → GFM 管道表格（复用 process_table，保留单元格内加粗/图片）
  - 图片 → 下载到 ./images/，MD 中写成 ![alt](@./images/xxx.png)
    （飞书 docs +create --doc-format markdown 会在创建时自动上传 @./ 引用的本地图）

说明：
  - 本地图片用 @./ 前缀是 lark-cli 的约定，路径必须位于 lark-cli 运行时的
    当前工作目录内（即 doc.md 与 images/ 同目录，且从该目录执行 lark-cli）。
"""

import re
import sys
from pathlib import Path

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError as e:
    print(f"缺少依赖库: {e}")
    print("请运行: pip install requests beautifulsoup4")
    sys.exit(1)


UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def sanitize_filename(name):
    """清理文件名中的非法字符"""
    name = re.sub(r'[<>:"/\\|?*]', '_', name or '')
    name = name.strip('. ')
    return name or 'article'


def escape_md(s):
    """飞书 Markdown 转义：反斜杠优先转义，左尖括号转义避免被当作 XML 标签"""
    s = s.replace('\\', '\\\\')   # 反斜杠必须最先处理
    s = s.replace('<', '\\<')     # 字面量 < 必须转义，否则被 XML 解析
    return s


def download_image(url, img_dir, index, article_id):
    """下载图片到本地，返回本地文件名；失败返回 None"""
    try:
        resp = requests.get(url, headers={'User-Agent': UA}, timeout=30)
        resp.raise_for_status()
        ext = Path(url.split('?')[0]).suffix or '.png'
        if ext.lower() not in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']:
            ext = '.png'
        # ASCII 序号命名：避免 lark-cli 在 Git Bash/posix cwd 环境下
        # 解析 @./images/中文路径失败导致图片上传失败
        filename = f"img_{index:03d}{ext}"
        (img_dir / filename).write_bytes(resp.content)
        print(f"  下载图片: {filename}")
        return filename
    except Exception as e:
        print(f"  下载图片失败 ({url}): {e}")
        return None


def extract_content(soup):
    """优先提取正文容器，逐级回退到 body"""
    selectors = [
        'div#js_content', 'div.rich_media_content',  # 微信公众号
        'article',
        '.markdown-body',                              # GitHub / 多数博客
        'main',
        '.content', '.post-content', '.article-content', '.entry-content',
    ]
    for sel in selectors:
        el = soup.select_one(sel)
        if el and el.get_text(strip=True):
            return el
    return soup.body or soup


def promote_fake_headings(content_root):
    """公众号大标题常是「样式伪装的文本」而非真正的 <h1>/<h2> 标签。

    典型形态：彩色渐变背景条（background: linear-gradient）+ 白字居中，
    文本形如「一、背景」「二、xxx」「结语」。脚本只认标签的话，这些
    大标题会退化成普通段落，整篇文章的标题层级会全丢。

    本函数把符合特征的短文本块提升为 <h2>，使最终层级为：
      # 文章标题（脚本首行生成） / ## 大标题 / ### 1.1 / #### 2.3.1
    """
    # 中文数字序号（一、二、…）/ 结语 / 附 / 总结 / 阿拉伯数字序号（01引言、1.背景——
    # 仅限「直接连接」或「英文点」两种伪装大标题形态；顿号/空格分隔（1、xxx）是正文编号，不提升）
    pattern = re.compile(
        r'^\s*(?:[一二三四五六七八九十]+、|结语|附\s*[:：]?|总结'
        r'|\d{1,2}[.．]?[\u4e00-\u9fffA-Za-z])\s*.{0,40}$'
    )
    promoted = []
    for el in list(content_root.find_all(['section', 'p', 'div'])):
        # 祖先已被提升则跳过，避免出现嵌套 h2
        if any(el in p.descendants for p in promoted):
            continue
        txt = el.get_text(strip=True)
        if not txt or len(txt) > 40:
            continue
        if not pattern.match(txt):
            continue
        # 只提升「纯净」容器：内部不含子标题 / 表格 / 图片 / 列表
        if el.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'table', 'img', 'ul', 'ol']):
            continue
        el.name = 'h2'
        promoted.append(el)
    return len(promoted)


def html_to_markdown(soup, img_dir=None, article_id=None):
    """将 HTML 子树转换为 Markdown，保持原始元素顺序"""
    md = []
    img_index = 0
    img_map = {}  # URL -> 本地文件名

    # 预下载图片
    if img_dir:
        for img in soup.find_all('img'):
            src = img.get('data-src') or img.get('data-original') or img.get('src', '')
            if src and src not in img_map:
                img_index += 1
                local = download_image(src, img_dir, img_index, article_id)
                if local:
                    img_map[src] = local

    def img_ref(src, alt=''):
        if src and src in img_map:
            return f"![{alt}](@./images/{img_map[src]})"
        if src:
            return f"![{alt}]({src})"   # 下载失败则回退为原始 URL
        return ''

    def process_inline(element):
        parts = []
        for child in element.children:
            if hasattr(child, 'name') and child.name:
                t = child.name
                if t in ('b', 'strong'):
                    txt = child.get_text(strip=True)
                    if txt:
                        parts.append(f"**{escape_md(txt)}**")
                elif t in ('i', 'em'):
                    txt = child.get_text(strip=True)
                    if txt:
                        parts.append(f"*{escape_md(txt)}*")
                elif t == 'code':
                    txt = child.get_text(strip=True)
                    if txt:
                        parts.append(f"`{escape_md(txt)}`")
                elif t == 'a':
                    href = child.get('href', '')
                    txt = child.get_text(strip=True)
                    if txt:
                        parts.append(f"[{escape_md(txt)}]({href})")
                elif t == 'img':
                    parts.append(img_ref(child.get('data-src') or child.get('src', ''),
                                        child.get('alt', '')))
                elif t == 'br':
                    parts.append('<br>')
                else:
                    r = process_inline(child)
                    if r:
                        parts.append(r)
            else:
                txt = str(child).strip()
                if txt:
                    parts.append(escape_md(txt))
        return ''.join(parts)

    def process_table(table):
        """<table> → GFM 管道表格。合并单元格（colspan/rowspan）自动展开成规则网格
        （跨行列的单元格在对应位置重复填充），保持纯 GFM、对 AI/RAG 友好。"""
        rows = [r for r in table.find_all('tr') if r.find_parent('tr') is None]
        if not rows:
            return ''

        def cell_text(cell):
            # 单元格内多个块级元素（<p>/<li>/<section>/<div>）之间用 <br> 换行，避免挤成一行
            blocks = cell.find_all(['p', 'li', 'section', 'div'])
            for i, el in enumerate(blocks):
                if i > 0:
                    el.insert_before(cell.new_tag('br'))
            txt = process_inline(cell).strip()
            txt = txt.replace('|', '\\|')   # 单元格内竖线转义，避免 GFM 错位
            return txt if txt else ' '

        # 列数 = 第一行各 cell 的 colspan 之和
        n_cols = sum(int(c.get('colspan', 1) or 1)
                     for c in rows[0].find_all(['td', 'th'], recursive=False))
        if n_cols <= 0:
            return ''

        # 展开为规则二维网格（None 表示尚未填充）
        grid = []
        for r_idx, row in enumerate(rows):
            while len(grid) <= r_idx:
                grid.append([None] * n_cols)
            col = 0
            for cell in row.find_all(['td', 'th'], recursive=False):
                # 跳过已被上方 rowspan 占用的列
                while col < n_cols and grid[r_idx][col] is not None:
                    col += 1
                cs = int(cell.get('colspan', 1) or 1)
                rs = int(cell.get('rowspan', 1) or 1)
                content = cell_text(cell)
                for dr in range(rs):
                    rr = r_idx + dr
                    while len(grid) <= rr:
                        grid.append([None] * n_cols)
                    for dc in range(cs):
                        cc = col + dc
                        if cc < n_cols:
                            grid[rr][cc] = content
                col += cs

        # None → ' '，输出 GFM（首行作表头）
        final = [[c if c is not None else ' ' for c in row] for row in grid]
        lines = ['| ' + ' | '.join(final[0]) + ' |',
                 '| ' + ' | '.join(['---'] * n_cols) + ' |']
        for row in final[1:]:
            lines.append('| ' + ' | '.join(row) + ' |')
        return '\n'.join(lines) + '\n\n'

    def list_item_text(li):
        """取 li 的自身文本（排除嵌套子列表，避免子项被拼进父项）"""
        import copy
        c = copy.copy(li)
        for sub in c.find_all(['ul', 'ol']):
            sub.decompose()
        return escape_md(c.get_text(strip=True))

    def direct_sublists(li):
        """li 的直接子列表：往上第一个 ul/ol/li 祖先就是该 li 自己"""
        res = []
        for sub in li.find_all(['ul', 'ol']):
            anc = sub.find_parent(['ul', 'ol', 'li'])
            if anc is not None and anc.name == 'li' and anc is li:
                res.append(sub)
        return res

    def process_list(el, ordered, depth=0):
        """
        递归处理 ul/ol。三处关键容错：
        1) 公众号常见 `<ol style="list-style:none"><ol>…</ol></ol>` 布局容器
           ——外层没有直接 li，必须下钻，否则整段列表被吞掉；
        2) li 里嵌子列表 —— 缩进输出，而不是把子项文本拼进父项；
        3) li 与子 ul/ol **混排**（ul 直接子 = [li, ul]）—— 按文档顺序同时
           输出直接 li 与递归子列表，否则子列表被静默吞掉。
        """
        lines = []
        indent = '  ' * depth
        has_li = any(getattr(c, 'name', None) == 'li' for c in el.children)
        if not has_li:
            for sub in el.find_all(['ul', 'ol'], recursive=False):
                lines.extend(process_list(sub, sub.name == 'ol', depth))
            return lines
        idx = 0
        for child in el.children:
            name = getattr(child, 'name', None)
            if name == 'li':
                idx += 1
                txt = list_item_text(child)
                prefix = f"{idx}." if ordered else "-"
                if txt:
                    lines.append(f"{indent}{prefix} {txt}\n")
                for sub in direct_sublists(child):
                    lines.extend(process_list(sub, sub.name == 'ol', depth + 1))
            elif name in ('ul', 'ol'):
                lines.extend(process_list(child, name == 'ol', depth))
        return lines

    def traverse(element):
        for child in element.children:
            if not hasattr(child, 'name') or child.name is None:
                txt = str(child).strip()
                if txt:
                    md.append(f"{escape_md(txt)}\n\n")
                continue
            t = child.name

            if t == 'img':
                ref = img_ref(child.get('data-src') or child.get('src', ''),
                              child.get('alt', ''))
                if ref:
                    md.append(ref + '\n\n')
                continue
            if t == 'table':
                tbl = process_table(child)
                if tbl:
                    md.append(tbl)
                continue
            if t in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
                level = int(t[1])
                txt = escape_md(child.get_text(strip=True))
                if txt:
                    md.append(f"\n{'#' * level} {txt}\n\n")
                continue
            if t == 'p':
                content = process_inline(child)
                if content:
                    md.append(f"{content}\n\n")
                continue
            if t in ('ul', 'ol'):
                lines = process_list(child, t == 'ol')
                if lines:
                    md.extend(lines)
                    md.append('\n')
                continue
            if t == 'blockquote':
                txt = escape_md(child.get_text(strip=True))
                if txt:
                    md.append(f"\n> {txt}\n\n")
                continue
            if t == 'pre':
                # 公众号代码块：每个 <code> 子元素是一行（微信用 <code> 分行，无 <br>/<p>）
                codes = child.find_all('code')
                if codes:
                    code = '\n'.join(c.get_text() for c in codes)
                else:
                    # 无 <code> 时：把 <br> 转成换行再取文本（兼容传统 <pre>）
                    for br in child.find_all('br'):
                        br.replace_with('\n')
                    code = child.get_text()
                code = code.replace('\xa0', ' ').strip('\n')
                if code.strip():
                    md.append(f"\n```\n{code}\n```\n\n")
                continue
            if t == 'hr':
                md.append("\n---\n\n")
                continue
            if t == 'br':
                md.append('\n')
                continue
            # 容器元素递归
            traverse(child)

    traverse(soup)
    return ''.join(md)


def load_html(input_arg):
    """从 URL 或本地文件加载 HTML，返回 (html_text, base_title)"""
    if input_arg.startswith(('http://', 'https://')):
        resp = requests.get(input_arg, headers={'User-Agent': UA,
                                                'Accept-Language': 'zh-CN,zh;q=0.9'},
                            timeout=30)
        resp.raise_for_status()
        resp.encoding = 'utf-8'
        return resp.text, input_arg
    p = Path(input_arg)
    if not p.exists():
        raise FileNotFoundError(f"找不到文件: {input_arg}")
    return p.read_text(encoding='utf-8'), str(p)


def main():
    if len(sys.argv) < 2:
        print("用法: python html_to_md.py <HTML文件或URL> [输出目录]")
        print("示例:")
        print("  python html_to_md.py https://mp.weixin.qq.com/s/xxxx ./_build")
        print("  python html_to_md.py ./page.html ./_build")
        sys.exit(1)

    input_arg = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith('-') else '.'

    try:
        html_text, src = load_html(input_arg)
    except Exception as e:
        print(f"加载失败: {e}")
        sys.exit(1)

    soup = BeautifulSoup(html_text, 'html.parser')

    # 标题：og:title > h1 > 文件名
    title = None
    og = soup.find('meta', property='og:title')
    if og:
        title = og.get('content')
    if not title:
        h1 = soup.find('h1')
        if h1:
            title = h1.get_text(strip=True)
    if not title:
        title = Path(src).stem if not src.startswith('http') else 'untitled'
    title = title.strip() or 'untitled'
    print(f"标题: {title}")

    content = extract_content(soup)
    n_promoted = promote_fake_headings(content)
    if n_promoted:
        print(f"识别并提升样式伪装的大标题为 H2: {n_promoted} 个")

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    img_dir = out_path / 'images'
    img_dir.mkdir(exist_ok=True)

    article_id = sanitize_filename(title)[:40]
    body = html_to_markdown(content, img_dir, article_id)
    md_content = f"# {escape_md(title)}\n\n" + body

    md_file = out_path / 'doc.md'
    md_file.write_text(md_content, encoding='utf-8')
    print(f"保存成功: {md_file}")


if __name__ == '__main__':
    main()
