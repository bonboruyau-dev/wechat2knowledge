---
name: wechat2knowledge
description: 微信公众号文章 → 知识库一站式转换，两条输出路径。路径 A：抓取公众号文章为干净 GFM Markdown（标题/作者/来源、图片下载、表格含合并单元格展开、样式伪装大标题还原、代码块逐行，支持 Obsidian 模式）。路径 B：落地为飞书云文档（HTML/MD 双输入、图片自动上传与格式归一化、完整性回查、定点修复不重建）。当用户给出 mp.weixin.qq.com 链接或任意 HTML 网页/文件，并要求"转 Markdown""转飞书文档""存知识库""抓取文章""保存这篇文章"时使用。
agent_created: true
slug: wechat2knowledge
displayName: 公众号文章转知识库
version: 1.0.0
license: MIT
---

# 公众号文章转知识库（wechat2knowledge）

## Overview

把微信公众号文章（或任意 HTML 网页/文件）转换为知识库产物。一条链路、两档输出：

- **Path A · 纯 Markdown**：抓取 → 干净 GFM Markdown（快，适合归档/RAG 语料/Obsidian）。
- **Path B · 飞书文档**：抓取 → Markdown → 飞书云文档（含图片上传、完整性回查与定点修复）。

核心中间产物 = **干净 GFM Markdown + ASCII 命名的本地图片目录**。先产出它，再决定落地到哪。

## Path decision

- 用户只要 Markdown / 提到 Obsidian / 要 RAG 语料 → **Path A**。
- 用户要「飞书文档」「存到飞书」「发到飞书」→ **Path B**。
- 未指明且链接是公众号 → 默认先跑 Path A 交付 Markdown，问是否继续落飞书（Path B 创建的文档删不掉，宁少勿废）。

## Prerequisites

- Python：`requests` + `beautifulsoup4`。WorkBuddy 本机用隔离 venv：
  `PY="C:/Users/Jiazi/.workbuddy/binaries/python/envs/default/Scripts/python.exe"`
  其他平台（Claude Code / Codex）先 `pip install -r requirements.txt`。
- Path B 额外需要：飞书连接器（lark-cli）；`svg2png.js` 依赖 playwright（`NODE_PATH` 指向托管 workspace，勿全局装）。Git Bash 里 lark-cli launcher 有 POSIX 路径 bug，必须用 node 直接调入口脚本（见 Step B4）。
- 图片文件名必须 ASCII（脚本已默认 `img_NNN.{ext}`）。中文/含空格图片路径会导致飞书上传**静默失败**，绝对不要改回中文命名。

## Path A：抓取为 Markdown（wechat_article_to_md.py）

```bash
PY="C:/Users/Jiazi/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
"$PY" "<skill_dir>/scripts/wechat_article_to_md.py" "<文章URL>" [输出目录] [-obsidian]
```

- 自动提取标题/作者/来源；下载图片到 `images/`（按 magic bytes 修正真实扩展名）；表格转 GFM（合并单元格展开）；样式伪装大标题（「一、背景」「01引言」「1.引言」「结语」）提升为 `##`——**仅限数字直接连接/英文点形态**，「1、xxx」这类顿号编号是正文列表，不会误提升。
- `-obsidian`：图片引用转 `![[filename.png]]`，落到 `attachments/img/`，适配双链。
- 运行时会**清空**目标 `images/` 旧图片——别把输出目录指向自己的存图处。

## Path B：飞书文档流水线

### Step B1：转 Markdown（html_to_md.py）

```bash
BUILD="<输出根目录>/_build"; mkdir -p "$BUILD"
"$PY" "<skill_dir>/scripts/html_to_md.py" "<HTML文件或URL>" "$BUILD"
```

- 正文容器按优先级提取（`div#js_content` → `article` → `.markdown-body` → `main` → `body`）。
- 产出 `_build/doc.md`（首行 `# 标题`）+ `_build/images/img_NNN.{ext}`，Markdown 引用写为 `![alt](@./images/img_001.png)`。
- 表格转 GFM（合并单元格展开，单元格内块级结构以 `<br>` 分行）；嵌套列表/混排列表（ul 直接子 = `[li, ul]`）正确输出。

### Step B2：图片格式归一化（必做，否则 create 整篇失败）

```bash
NODE="C:/Users/Jiazi/.workbuddy/binaries/node/versions/22.22.2/node.exe"
WS="C:/Users/Jiazi/.workbuddy/binaries/node/workspace/node_modules"
"$PY" "<skill_dir>/scripts/normalize_images.py" "$BUILD"        # magic bytes 纠错；退出码 2 = 有 SVG
NODE_PATH="$WS" "$NODE" "<skill_dir>/scripts/svg2png.js" "$BUILD/images"   # SVG→PNG（原地覆盖）
"$PY" "<skill_dir>/scripts/normalize_images.py" "$BUILD"        # 再跑，退出码 0 才继续
```

飞书按**内容**校验图片（不是扩展名）：SVG/GIF 伪装成 .png 会让整篇创建失败。这是公众号文章最高频失败点。

### Step B3：可选 · 批量图片预压缩

图片总数 >20 张时，建议先把大图压缩（PNG→JPEG、长边 ≤1600px）并同步 `doc.md` 引用——虽不解决限流（见 Step B4 的占位符方案），但能显著加速上传。压缩时**不要删旧文件**（沙箱 unlink 会被拦截；多余文件无害，lark-cli 只按 doc.md 引用取文件）。

### Step B4：创建飞书文档

**先 `cd` 进 `_build`**（`@./` 引用以 cwd 为基准），再调用：

```bash
RUNJS="C:/Users/Jiazi/.workbuddy/binaries/node/cli-connector-packages/node_modules/@larksuite/cli/scripts/run.js"
"$NODE" "$RUNJS" docs +create --doc-format markdown --content "@./doc.md" \
  --title "<标题>" --parent-position my_library     # 或 --parent-token <folder/wiki token>
```

- Git Bash 沙箱里不要直接用 `lark-cli` 命令（launcher 路径 bug：`/c/`→`c:\c\`）。
- 校验：`new_blocks` 中 `block_type=="image"` 数量应等于 doc.md 的图片引用数；为 0 或偏少即图片路径问题。

**批量图片限流（>~20 张）**：一次 create 从第 3 张起稳定报 `correlation_failed / invalid_response`（压缩、等待重试均无效）。不要硬刚，改用**占位符方案**：

1. doc.md 中每个图片引用替换为唯一占位符文本（`IMG-PLACEHOLDER-NNN`），重新 create（纯文本必成功）；
2. `docs +fetch --detail with-ids` 定位每个占位符的 block id；
3. 逐张 `docs +update --command block_insert_after --block-id <占位符id> --content '<img path="@./images/img_NNN.jpg"/>'`，随后 `block_delete` 占位符块；
4. fetch 验证 img 数 = 引用数。

注意：`block_replace` **不允许** text→image 类型转换（报 no document changes）；`str_replace` 不支持资源替换；网络 URL 图片方案不可用（飞书服务端拉不动微信 CDN 防盗链，img 块为 0）。

### Step B5：完整性回查（交付前必做）

```bash
# 原文 HTML：Path B 用 URL 转换时另存一份 source.html
"$NODE" "$RUNJS" docs +fetch --doc "<doc_id>" --detail with-ids > _verify.json
"$PY" "<skill_dir>/scripts/verify_doc.py" source.html _verify.json
```

- 原文图片数 > 文档图片数未必丢图（公众号有无 src 的空占位）；纯文本多几十字正常，**少了才是问题**。
- 缺失行先 grep 文档 XML 确认：代码块内文本因格式差异极易误报。
- 结构健康基线：img 数、`<table>` 数、`<pre>` 数应与原文对应。

### Step B6：定点修复（绝不要重建）

lark-cli **没有删除文档命令**，重建会留废稿。发现问题一律用 `docs +update` 外科手术修补：

- 常用：`block_replace`（同类型块替换）、`block_insert_after`、`block_delete`、`append`、`str_replace`、`overwrite`。
- `block_replace` 不允许跨类型（text→image）；跨类型用 insert_after + delete 组合。
- 插入列表用 XML：`<ul><li><p>子项</p></li></ul>`；插到 li 后会正确变成该 li 的子项；避免用顶层 `block_insert_after` 插多个列表项（会被并进同一列表顶乱编号）。
- 多行内容走文件（`@./insert.xml`），不要命令行转义。
- 修复后重跑 Step B5，确认缺失行只剩已知误报。

## 共享经验（两路径通用）

- **长链风控**：带 `poc_token` 的长链（`/s?__biz=…`）易被验证页拦截（表现为标题 `untitled`、0 图、无正文）。换 UA/Referer/真实浏览器均无效——**改用 `/s/xxxxxx` 短链**。
- **代码围栏错位**：原文（尤其 Prompt 模板）残留孤立 ```` ``` ````，而 ```` ```json{…} ```` 按 CommonMark **不能闭合**围栏，会把后续大段正文+表格吞进巨型代码块。转换后校验：模拟配对（开启 = 任意 ```` ``` ```` 行，闭合 = 仅 ```` ``` ```` 行），发现跨度异常大的块即中招，回 doc.md 删除孤立残留行。注意「# 最终输出内容格式」这类 Prompt 内小节常是原文真实 h1/h2，勿误判。
- **常见误报**：`verify_doc.py` 的缺失行若全是代码块片段、`\xa0` 或加粗标记附近文本，先 grep 确认关键词在不在文档里再下结论。

## Caveats

- **删除文档**：lark-cli 无 delete 命令，废稿需用户手动删——所以宁少勿废、一律定点修复。
- **网络图片**：防盗链/过期链接下载失败会回退为原始 URL；飞书服务端拉不动微信 CDN，URL 形式创建后 img 块为 0——必须本地下载后用 `@./` 引用。
- **大文档**：超飞书单次限制需分段创建后拼接（v1 不内置分页）。
- **跨平台**：三端（WorkBuddy / Claude Code / Codex）通用。WorkBuddy 用内置 venv 与连接器；其他平台 `pip install -r requirements.txt` + 自装 `@larksuite/cli` 并配置飞书应用凭证。

## Resources

### scripts/

- `wechat_article_to_md.py` — Path A 主脚本：公众号 URL → Markdown（作者提取、Obsidian 模式、大标题还原）。
- `html_to_md.py` — 通用 HTML/URL → GFM Markdown（ASCII 图片、容器适配、飞书流水线入口）。
- `normalize_images.py` — magic bytes 纠错扩展名 + 列出待转 SVG（退出码 2）。
- `svg2png.js` — Playwright/Chromium 将 SVG 渲染为 PNG（原地覆盖，2x）。
- `verify_doc.py` — 原文 HTML vs 飞书文档完整性比对（结构统计 + 逐行缺失，退出码 3 = 有缺失）。

### 常用常量（WorkBuddy 本机）

```
PY   = C:/Users/Jiazi/.workbuddy/binaries/python/envs/default/Scripts/python.exe
NODE = C:/Users/Jiazi/.workbuddy/binaries/node/versions/22.22.2/node.exe
RUNJS= C:/Users/Jiazi/.workbuddy/binaries/node/cli-connector-packages/node_modules/@larksuite/cli/scripts/run.js
WS   = C:/Users/Jiazi/.workbuddy/binaries/node/workspace/node_modules   # playwright 在这
```
