# 公众号文章转知识库 · wechat2knowledge

> 一条链路，两档输出：把微信公众号文章（或任意 HTML）清洗成干净 GFM Markdown，再一键落地飞书云文档。大标题层级还原、表格合并单元格展开、代码块逐行、图片自动上传——脏 HTML 进，干净知识库出。
>
> One pipeline, two targets: turn WeChat Official Account articles into clean Markdown, then publish to Feishu (Lark) cloud docs. Dirty HTML in, clean knowledge out.

[English version](#english)

---

## ✨ 功能特性 / Features

- 📄 **自动提取** 标题、作者、来源链接（多级 fallback，新样式文章也能识别）
- 🅷 **大标题层级还原**：识别「一、背景」「01引言」「1.引言」「结语」等样式伪装标题，提升为 `##`；正文编号（`1、xxx`）不误判
- 📊 **表格 → GFM**：合并单元格自动展开（AI/RAG 友好），单元格内多行结构以 `<br>` 分行
- 💻 **代码块逐行还原**：微信 `<code>` 分行结构正确转换，缩进 NBSP 还原为普通空格
- 🖼️ **图片处理**：本地下载（magic bytes 修正真实扩展名）、SVG 用 Chromium 渲染成 PNG、批量上传限流自动绕过
- 📝 **两条输出路径**：Markdown（含 Obsidian 双链模式）/ 飞书云文档
- ✅ **完整性回查**：原文 vs 产物逐行比对，防整段丢失；发现问题**定点修复**，绝不重建
- 🧩 **列表容错**：嵌套列表、`li` 与子列表同层混排等公众号特殊结构均正确输出

## 🚀 快速开始 / Quick Start

### Path A · 转 Markdown

```bash
pip install -r requirements.txt

# 抓取文章 → 当前目录（图片下载到 images/）
python scripts/wechat_article_to_md.py "https://mp.weixin.qq.com/s/xxxxxx"

# Obsidian 模式（图片引用转 ![[...]]，落到 attachments/img/）
python scripts/wechat_article_to_md.py "https://mp.weixin.qq.com/s/xxxxxx" ./vault -obsidian
```

### Path B · 落飞书云文档（4 步）

```bash
BUILD=./_build && mkdir -p "$BUILD"

# 1. HTML/URL → Markdown（ASCII 图片命名）
python scripts/html_to_md.py "https://mp.weixin.qq.com/s/xxxxxx" "$BUILD"

# 2. 图片格式归一化（SVG→PNG，必做否则整篇失败）
python scripts/normalize_images.py "$BUILD"
node scripts/svg2png.js "$BUILD/images"
python scripts/normalize_images.py "$BUILD"   # 退出码 0 才继续

# 3. 创建飞书文档（在 _build 目录内执行）
cd "$BUILD" && node <lark-cli>/run.js docs +create \
  --doc-format markdown --content "@./doc.md" \
  --title "<标题>" --parent-position my_library

# 4. 完整性回查
python scripts/verify_doc.py source.html _verify.json
```

> 完整工作流（含 >20 张图的占位符方案、定点修复、围栏错位校验）见 [SKILL.md](./SKILL.md)。

## 🧩 跨平台安装 / Multi-Platform Setup

标准 **Agent Skill**（`SKILL.md` + 纯 Python 脚本），三端通用：

| 平台 | 安装方式 | 依赖 |
|---|---|---|
| **WorkBuddy** | 从 SkillHub 一键导入，或放入 `~/.workbuddy/skills/` | 已内置隔离 venv 与飞书连接器 |
| **Claude Code** | 放入 `~/.claude/skills/`（全局）或项目 `.claude/skills/` | `pip install -r requirements.txt`；Path B 需自装 `@larksuite/cli` + 飞书应用凭证 |
| **Codex** | 放入 `~/.codex/skills/` | 同上 |

## 📂 目录结构 / Structure

```
wechat2knowledge/
├── SKILL.md                      # 完整工作流（两条路径 + 踩坑手册）
├── README.md
├── requirements.txt              # requests + beautifulsoup4
├── LICENSE                       # MIT
└── scripts/
    ├── wechat_article_to_md.py   # Path A：公众号 URL → Markdown
    ├── html_to_md.py             # Path B：HTML/URL → GFM Markdown（飞书流水线入口）
    ├── normalize_images.py       # magic bytes 纠错 + 列出待转 SVG
    ├── svg2png.js                # SVG → PNG（Playwright/Chromium）
    └── verify_doc.py             # 原文 vs 文档完整性比对
```

## ⚠️ 注意事项 / Notes

- **长链风控**：带 `poc_token` 的长链易被验证页拦截（标题 untitled、无正文），换 UA/浏览器均无效——**改用 `/s/xxxxxx` 短链**。
- **图片目录会被清空**：Path A 运行时会清空目标 `images/` 旧图片，别把输出目录指向自己的存图处。
- **图片必须 ASCII 命名**：脚本默认 `img_NNN.{ext}`，中文/含空格路径会导致飞书上传静默失败。
- **飞书文档删不掉**：lark-cli 无 delete 命令，发布前先回查；发现内容问题走定点修复，不要重建。
- **代码围栏错位**：原文残留孤立 ``` 会吞大段内容，转换后建议校验配对（详见 SKILL.md）。

## 🔗 上下游 / Related

- **批量获取历史文章**：[wechat-article-exporter](https://github.com/wechat-article/wechat-article-exporter) —— 批量下载到的 HTML 可直接喂给本工具清洗入库（它是「获取」，我们是「沉淀」，上下游互补）。
- 本工具前身：`wechat-article-to-md`（抓取转 MD）+ `html-to-feishu-doc`（飞书落地），已合并至此。

## 🤝 贡献 / Contributing

欢迎提交 Issue 与 Pull Request。PR 请保证：

1. `python -m py_compile scripts/*.py` 与 `node --check scripts/svg2png.js` 通过
2. 新增能力同步更新 `SKILL.md` 对应章节
3. 用至少一篇真实公众号文章端到端验证

## 📄 许可证 / License

[MIT](./LICENSE)

---

## English

One pipeline, two targets for turning WeChat Official Account articles into knowledge assets.

**Highlights**

- Clean GFM Markdown: fake-heading restoration, merged-cell table expansion, per-line code blocks, NBSP normalization
- Feishu (Lark) cloud docs: auto image upload & format normalization, integrity check, surgical fix (never recreate)
- Handles WeChat quirks: nested lists, styled section headings, lazy-loaded images, `<code>`-per-line snippets
- Agent Skill format (SKILL.md) — works with WorkBuddy / Claude Code / Codex

**Usage**

```bash
pip install -r requirements.txt
python scripts/wechat_article_to_md.py "<article_url>" [output_dir] [-obsidian]
# Feishu pipeline: see SKILL.md (Path B)
```

**Keywords**: wechat, weixin, official-account, markdown, converter, html-to-markdown, feishu, lark, knowledge-base, rag, obsidian, scraper, agent-skills, workbuddy, claude-code, codex
