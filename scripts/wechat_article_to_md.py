#!/usr/bin/env python3
"""
微信公众号文章抓取并转换为 Markdown 文档
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


def sanitize_filename(name):
    """清理文件名中的非法字符"""
    # 替换 Windows/macOS/Linux 非法字符
    illegal_chars = r'[<>:"/\\|?*]'
    name = re.sub(illegal_chars, '_', name)
    # 去除首尾空格和点
    name = name.strip('. ')
    return name or 'article'


def clear_images_directory(img_dir):
    """清理图片目录中的所有图片文件"""
    if not img_dir or not img_dir.exists():
        return
    try:
        image_files = []
        for ext in ['*.jpg', '*.jpeg', '*.png', '*.gif', '*.webp', '*.bmp']:
            image_files.extend(img_dir.glob(ext))
        for file_path in image_files:
            file_path.unlink()
        if image_files:
            print(f"  已清理 {len(image_files)} 个旧图片文件")
    except Exception as e:
        print(f"  清理图片目录失败: {e}")


def detect_image_ext(data):
    """按 magic bytes 检测图片真实格式，返回带点的扩展名（如 '.png'）；无法识别返回 None。

    用于修正「扩展名与内容不符」的图片（公众号常见：SVG/GIF 被存成 .png）。
    """
    if not data:
        return None
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return '.png'
    if data[:6] in (b'GIF87a', b'GIF89a'):
        return '.gif'
    if data[:3] == b'\xff\xd8\xff':
        return '.jpg'
    if data[:2] == b'BM':
        return '.bmp'
    if data[:4] in (b'II*\x00', b'MM\x00*'):
        return '.tiff'
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return '.webp'
    head = data.lstrip()[:256]
    if head.startswith(b'<svg') or head.startswith(b'<?xml') or b'<svg' in head[:120]:
        return '.svg'
    return None


def download_image(url, img_dir, index, article_id=None):
    """下载图片到本地

    Args:
        url: 图片 URL
        img_dir: 图片保存目录
        index: 图片序号
        article_id: 文章唯一标识，用于生成唯一文件名
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        data = response.content
        # 按 magic bytes 检测真实格式，修正「扩展名与内容不符」的图（如 SVG/GIF 存成 .png）
        ext = detect_image_ext(data)
        if not ext:
            # 回退：从 URL 提取扩展名
            ext = Path(url).suffix or '.png'
            if '?' in ext:
                ext = ext.split('?')[0]
        if not ext or ext == '':
            ext = '.png'

        # 确保扩展名有效（含 svg）
        valid_exts = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg']
        if ext.lower() not in valid_exts:
            ext = '.png'

        # 使用文章 ID 作为前缀，避免不同文章的图片文件名冲突
        if article_id:
            filename = f"{article_id}_{index:03d}{ext}"
        else:
            filename = f"image_{index:03d}{ext}"
        file_path = img_dir / filename

        file_path.write_bytes(response.content)
        print(f"  下载图片: {filename}")
        return filename
    except Exception as e:
        print(f"  下载图片失败 ({url}): {e}")
        return None


def promote_fake_headings(content_root):
    """公众号大标题常是「样式伪装的文本」而非真正的 <h1>/<h2> 标签。

    典型形态：彩色渐变背景条 + 白字居中，文本形如「一、背景」「二、xxx」「结语」。
    脚本只认标签的话，这些大标题会退化成普通段落。

    本函数把符合特征的短文本块提升为 <h2>，使最终层级为：
      # 文章标题 / ## 大标题 / ### 1.1 / #### 2.3.1
    """
    pattern = re.compile(
        r'^\s*(?:[一二三四五六七八九十]+、|结语|附\s*[:：]?|总结'
        r'|\d{1,2}[.．]?[\u4e00-\u9fffA-Za-z])\s*.{0,40}$'
    )
    promoted = []
    for el in list(content_root.find_all(['section', 'p', 'div'])):
        if any(el in p.descendants for p in promoted):
            continue
        txt = el.get_text(strip=True)
        if not txt or len(txt) > 40:
            continue
        if not pattern.match(txt):
            continue
        if el.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'table', 'img', 'ul', 'ol']):
            continue
        el.name = 'h2'
        promoted.append(el)
    return len(promoted)


def _render_list(el):
    """递归渲染嵌套/混排列表为 Markdown 行（供 ul/ol 的混排与纯容器场景复用）"""
    import copy
    lines = []
    ordered = el.name == 'ol'
    idx = 0
    for c in el.children:
        name = getattr(c, 'name', None)
        if name == 'li':
            idx += 1
            cc = copy.copy(c)
            for sub in cc.find_all(['ul', 'ol']):
                sub.decompose()
            text = cc.get_text(strip=True)
            if text:
                prefix = f"{idx}." if ordered else "-"
                lines.append(f"{prefix} {text}\n")
            for sub in [x for x in c.children if getattr(x, 'name', None) in ('ul', 'ol')]:
                lines.extend(_render_list(sub))
        elif name in ('ul', 'ol'):
            lines.extend(_render_list(c))
    return lines


def html_to_markdown(soup, img_dir=None, article_id=None, obsidian_mode=False, article_url=None):
    """将 HTML 内容转换为 Markdown，保持原始元素顺序

    Args:
        soup: BeautifulSoup 对象
        img_dir: 图片保存目录
        article_id: 文章唯一标识，用于生成唯一图片文件名
        obsidian_mode: 是否使用 Obsidian 格式（图片保存到 attachments/img/，使用 ![[filename]]）
        article_url: 原文链接，用于视频提示
    """
    md_content = []
    img_index = 0
    img_map = {}  # URL -> 本地文件名映射
    video_index = 0  # 视频计数器

    # 首先收集所有图片并下载
    if img_dir:
        for img in soup.find_all('img'):
            src = img.get('data-src') or img.get('src', '')
            if src and src not in img_map:
                img_index += 1
                local_img = download_image(src, img_dir, img_index, article_id)
                if local_img:
                    if obsidian_mode:
                        img_map[src] = local_img
                    else:
                        img_map[src] = f"images/{local_img}"

    def add_image(src, alt=''):
        """添加图片到内容"""
        if src:
            if src in img_map:
                if obsidian_mode:
                    md_content.append(f"![[{img_map[src]}]]\n")
                else:
                    md_content.append(f"![{alt}]({img_map[src]})\n")
            else:
                md_content.append(f"![{alt}]({src})\n")

    def process_inline_elements(element):
        """处理元素内的内联元素（粗体、斜体、链接）"""
        parts = []
        for child in element.children:
            if hasattr(child, 'name') and child.name:
                tag_name = child.name

                if tag_name in ['b', 'strong']:
                    text = child.get_text(strip=True)
                    if text:
                        parts.append(f"**{text}**")

                elif tag_name in ['i', 'em']:
                    text = child.get_text(strip=True)
                    if text:
                        parts.append(f"*{text}*")

                elif tag_name == 'a':
                    href = child.get('href', '')
                    text = child.get_text(strip=True)
                    if text:
                        parts.append(f"[{text}]({href})")

                elif tag_name == 'img':
                    # 处理内联图片
                    src = child.get('data-src') or child.get('src', '')
                    alt = child.get('alt', '')
                    if src:
                        if src in img_map:
                            if obsidian_mode:
                                parts.append(f"![[{img_map[src]}]]")
                            else:
                                parts.append(f"![{alt}]({img_map[src]})")
                        else:
                            parts.append(f"![{alt}]({src})")

                elif tag_name == 'br':
                    parts.append('<br>')

                else:
                    result = process_inline_elements(child)
                    if result:
                        parts.append(result)
            else:
                text = str(child).strip()
                if text:
                    parts.append(text)

        return ''.join(parts)

    def process_table(table):
        """<table> → GFM 管道表格。合并单元格（colspan/rowspan）自动展开成规则网格
        （跨行列的单元格在对应位置重复填充），保持纯 GFM、对 AI/RAG 友好。"""
        # 仅取顶层行，排除嵌套表格造成的重复行
        rows = [r for r in table.find_all('tr') if r.find_parent('tr') is None]
        if not rows:
            return ''

        def cell_text(cell):
            # 单元格内多个块级元素（<p>/<li>/<section>/<div>）之间用 <br> 换行，避免挤成一行
            blocks = cell.find_all(['p', 'li', 'section', 'div'])
            for i, el in enumerate(blocks):
                if i > 0:
                    el.insert_before(cell.new_tag('br'))
            text = process_inline_elements(cell).strip()
            return text if text else ' '

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
        table_lines = ['| ' + ' | '.join(final[0]) + ' |',
                       '| ' + ' | '.join(['---'] * n_cols) + ' |']
        for row in final[1:]:
            table_lines.append('| ' + ' | '.join(row) + ' |')
        return '\n'.join(table_lines) + '\n\n'

    # 使用更简单的方式：遍历所有直接子元素，递归处理
    # 但不使用过早的 return，确保所有内容都被处理
    processed_elements = set()  # 已处理的元素，避免重复

    def traverse(element, in_list=False, in_blockquote=False):
        """遍历元素树，按顺序处理"""
        for child in element.children:
            if not hasattr(child, 'name') or child.name is None:
                # 文本节点
                text = str(child).strip()
                if text and not in_list and not in_blockquote:
                    md_content.append(f"{text}\n\n")
                continue

            tag_name = child.name

            # 图片
            if tag_name == 'img':
                src = child.get('data-src') or child.get('src', '')
                alt = child.get('alt', '')
                add_image(src, alt)
                continue

            # 视频 iframe
            if tag_name == 'iframe':
                video_index += 1
                md_content.append(f"\n> 🎥 [视频 {video_index}]\n")
                md_content.append("> 注：微信视频无法在 Markdown 中直接查看\n")
                if article_url:
                    md_content.append(f"> 请访问原文观看: {article_url}\n")
                md_content.append("\n")
                continue

            # 表格 - 转换为 GFM 管道表格（简单规则表格，不含合并单元格）
            if tag_name == 'table':
                table_md = process_table(child)
                if table_md:
                    md_content.append(table_md)
                continue

            # 标题 - 需要特殊处理，因为微信标题内可能嵌套图片
            if tag_name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                level = int(tag_name[1])
                # 提取纯文本内容（不包括图片）
                # 微信标题通常是 h > span > span 结构，需要获取所有 span 的文本
                text = child.get_text(strip=True)
                # 移除图片相关的文本（如果图片有 alt 文本）
                for img in child.find_all('img'):
                    alt = img.get('alt', '')
                    if alt and alt in text:
                        text = text.replace(alt, '')
                text = text.strip()
                if text:
                    md_content.append(f"\n{'#' * level} {text}\n\n")
                # 检查标题内是否有图片，单独处理
                for img in child.find_all('img'):
                    src = img.get('data-src') or img.get('src', '')
                    alt = img.get('alt', '')
                    add_image(src, alt)
                continue

            # 段落 - 处理内联元素，但也要检查内部的图片
            if tag_name == 'p':
                # 先处理内联元素（不含图片）
                content = process_inline_elements(child)
                if content:
                    md_content.append(f"{content}\n\n")
                continue

            # 无序列表
            if tag_name == 'ul':
                # 容错：li 与子 ul/ol 混排（直接子 = [li, ul]）或纯容器嵌套，均按文档顺序递归处理
                direct = [c for c in child.children if getattr(c, 'name', None) in ('li', 'ul', 'ol')]
                if any(c.name == 'li' for c in direct):
                    for c in direct:
                        if c.name == 'li':
                            text = c.get_text(strip=True)
                            if text:
                                md_content.append(f"- {text}\n")
                        else:
                            md_content.extend(_render_list(c))
                else:
                    for c in direct:
                        if c.name in ('ul', 'ol'):
                            md_content.extend(_render_list(c))
                md_content.append("\n")
                continue

            # 有序列表
            if tag_name == 'ol':
                idx = 0
                for c in [x for x in child.children if getattr(x, 'name', None) in ('li', 'ul', 'ol')]:
                    if c.name == 'li':
                        idx += 1
                        text = c.get_text(strip=True)
                        if text:
                            md_content.append(f"{idx}. {text}\n")
                    else:
                        md_content.extend(_render_list(c))
                md_content.append("\n")
                continue

            # 引用
            if tag_name == 'blockquote':
                text = child.get_text(strip=True)
                if text:
                    md_content.append(f"\n> {text}\n\n")
                continue

            # 代码块
            if tag_name == 'pre':
                # 公众号代码块：每个 <code> 子元素是一行（微信用 <code> 分行，无 <br>/<p>）
                codes = child.find_all('code')
                if codes:
                    code = '\n'.join(c.get_text() for c in codes)
                else:
                    for br in child.find_all('br'):
                        br.replace_with('\n')
                    code = child.get_text()
                code = code.replace('\xa0', ' ').strip('\n')
                if code.strip():
                    md_content.append(f"\n```\n{code}\n```\n\n")
                continue

            # 分隔线
            if tag_name == 'hr':
                md_content.append("\n---\n\n")
                continue

            # br 标签
            if tag_name == 'br':
                md_content.append("\n")
                continue

            # 容器元素 - 递归遍历其子元素
            # 包括 section, div, span, article, main, figure 等
            traverse(child, in_list, in_blockquote)

    # 从根元素开始遍历
    traverse(soup)

    return '\n'.join(md_content)


def find_attachments_img_dir(start_path):
    """从起始路径向上查找固定的 attachments/img/ 目录

    Args:
        start_path: 开始查找的路径（通常是 md 文件所在目录或输出目录）

    Returns:
        找到的 attachments/img/ 目录路径，如果没找到则返回 None
    """
    path = Path(start_path).resolve()

    # 向上最多查找 3 层目录
    max_levels = 3
    for level in range(max_levels):
        attachments_dir = path / 'attachments'
        img_dir = attachments_dir / 'img'

        # 检查 attachments/img/ 是否存在，或者可以创建
        # 优先使用已存在的目录
        if img_dir.exists() and img_dir.is_dir():
            return img_dir

        # 检查 attachments/ 目录是否存在
        if attachments_dir.exists() and attachments_dir.is_dir():
            # 尝试创建 img 目录
            img_dir.mkdir(exist_ok=True)
            return img_dir

        # 如果这层不是 attachments/，继续向上查找
        if path.parent == path:  # 已到达根目录
            break
        path = path.parent

    # 如果没找到，尝试在 start_path 的父目录创建
    path = Path(start_path).resolve().parent
    for level in range(max_levels):
        attachments_dir = path / 'attachments'
        img_dir = attachments_dir / 'img'

        if attachments_dir.exists() or level == 0:  # 第一层直接尝试创建
            img_dir.mkdir(parents=True, exist_ok=True)
            return img_dir

        if path.parent == path:
            break
        path = path.parent

    # 最后尝试在 start_path 下方创建（降级方案）
    fallback_img_dir = Path(start_path).resolve() / 'attachments' / 'img'
    fallback_img_dir.mkdir(parents=True, exist_ok=True)
    print(f"  注意: 降级在 {start_path} 下创建图片目录")
    return fallback_img_dir


def fetch_wechat_article(url, output_dir='.', download_images=True, obsidian_mode=False, img_output_dir=None):
    """
    抓取微信公众号文章

    Args:
        url: 微信文章链接
        output_dir: 输出目录（Markdown 文件保存位置）
        download_images: 是否下载图片到本地
        obsidian_mode: 是否使用 Obsidian 格式（图片引用格式 ![[filename]]）
        img_output_dir: 图片保存目录（绝对路径，None 表示相对于 output_dir）
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    }

    print(f"正在请求: {url}")
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        response.encoding = 'utf-8'
    except Exception as e:
        print(f"请求失败: {e}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')

    # 获取标题
    title = soup.find('meta', property='og:title')
    if title:
        title = title.get('content', '无标题')
    else:
        title_elem = soup.find('h1', class_='rich_media_title')
        title = title_elem.get_text(strip=True) if title_elem else '无标题'

    print(f"标题: {title}")

    # 获取作者 - 多级 fallback
    author = None
    # 1) 最可靠：<meta name="author"> / <meta property="og:article:author">
    #    新版公众号常把作者放 meta 里，页面内反而没有 js_author_name
    for attr, val in (('name', 'author'), ('property', 'og:article:author')):
        m = soup.find('meta', attrs={attr: val})
        if m and (m.get('content') or '').strip():
            author = m['content'].strip()
            break
    # 2) 旧版页面元素：js_author_name
    if not author:
        author_elem = soup.find(id='js_author_name')
        author = author_elem.get_text(strip=True) if author_elem else None
    # 3) 更旧的备用：a.rich_media_meta_link
    if not author:
        author_elem = soup.find('a', class_='rich_media_meta_link')
        author = author_elem.get_text(strip=True) if author_elem else None
    if not author:
        author = '未知作者'
    print(f"作者: {author}")

    # 获取正文内容
    content_div = soup.find('div', class_='rich_media_content') or soup.find('div', id='js_content')
    if not content_div:
        print("未找到文章内容")
        return

    # 创建输出目录
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 创建图片目录
    img_dir = None
    article_id = None
    if download_images:
        if img_output_dir:
            # 使用指定的绝对路径作为图片目录
            img_dir = Path(img_output_dir)
            img_dir.mkdir(parents=True, exist_ok=True)
            print(f"创建图片目录: {img_dir.absolute()}/")
        elif obsidian_mode:
            # Obsidian 模式：向上查找固定的 attachments/img/ 目录
            img_dir = find_attachments_img_dir(output_dir)
            print(f"使用固定图片目录: {img_dir.relative_to(Path.cwd()) if img_dir.is_relative_to(Path.cwd()) else img_dir}/")
        else:
            # 普通模式：保存到 images/
            img_dir = output_path / 'images'
            img_dir.mkdir(exist_ok=True)
            print("创建图片目录: images/")
        # 使用清理后的标题作为文章唯一标识
        article_id = sanitize_filename(title)
        # 清理旧图片
        clear_images_directory(img_dir)

    # 构建 Markdown
    md_lines = []
    md_lines.append(f"# {title}\n")
    md_lines.append(f"**作者**: {author}\n")
    md_lines.append(f"**来源**: {url}\n")
    md_lines.append("---\n\n")

    # 转换正文
    n_promoted = promote_fake_headings(content_div)
    if n_promoted:
        print(f"识别并提升样式伪装的大标题为 H2: {n_promoted} 个")
    body_md = html_to_markdown(content_div, img_dir, article_id, obsidian_mode, url)
    md_lines.append(body_md)

    md_content = '\n'.join(md_lines)

    # 保存文件
    filename = sanitize_filename(title) + '.md'
    file_path = output_path / filename

    file_path.write_text(md_content, encoding='utf-8')
    print(f"\n保存成功: {file_path.absolute()}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python wechat_article_to_md.py <微信文章URL> [输出目录] [选项]")
        print("选项:")
        print("  -obsidian     使用 Obsidian 格式（图片引用格式 ![[filename]]）")
        print("  -img-dir DIR  指定图片保存目录（绝对路径，优先于默认位置）")
        print("示例:")
        print("  python wechat_article_to_md.py https://mp.weixin.qq.com/s/B5hK8BywPla6LG3hVxHGqA")
        print("  python wechat_article_to_md.py https://mp.weixin.qq.com/s/B5hK8BywPla6LG3hVxHGqA . -obsidian")
        print("  python wechat_article_to_md.py https://mp.weixin.qq.com/s/B5hK8BywPla6LG3hVxHGqA . -obsidian -img-dir /attachments/img")
        sys.exit(1)

    url = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].upper().startswith('-') else '.'
    obsidian_mode = any(arg.upper() == '-OBSIDIAN' for arg in sys.argv)

    # 解析 -img-dir 参数
    img_output_dir = None
    for i, arg in enumerate(sys.argv):
        if arg.upper() == '-IMG-DIR' and i + 1 < len(sys.argv):
            img_output_dir = sys.argv[i + 1]
            break

    fetch_wechat_article(url, output_dir, True, obsidian_mode, img_output_dir)