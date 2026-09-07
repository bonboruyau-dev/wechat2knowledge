# 把公众号文章，变成你自己的知识库

> 一条命令，把微信公众号文章整理成干净的 Markdown 笔记，或直接存成一篇飞书文档。
> 标题、表格、代码、图片，原样保留 —— 你只管读，整理的事交给它。

---

## 一、这些麻烦，你是不是也遇到过？

- **存了等于没存**：看到好文章，收藏夹一丢、链接一复制，过两周再找，要么忘了放哪，要么链接失效。
- **复制粘贴，排版全崩**：把正文拷进笔记软件，小标题变普通文字、表格塌成一坨、代码全挤在一行 —— 勉强能看，但完全没法用。
- **图片是灾难**：手动一张张另存，十几张图点到手酸；有的图存下来打不开，有的在笔记里根本不显示。
- **想长期用，还得再整理半小时**：进 Obsidian 要做双链、进飞书要重新排版、想喂给 AI 做资料库，还得再洗一遍数据。
- **在微信里读完了，然后呢？**：手机里读得再顺，关掉就什么都没留下。读完的收获，应该留下来才对。

如果你点头了，那它就是为你准备的。

---

## 二、它是怎么解决的？

**给它一个链接，还你一份能直接用的文档。** 整个过程全自动，你只需要等几秒。

### 核心能力（每一条都对应上面一个麻烦）

| 你的麻烦 | 它怎么做 | 你得到什么 |
|---|---|---|
| 排版崩了 | 自动识别文章结构，把「一、背景」这类大标题还原成真正的标题层级 | 一份有目录、有层级、能直接生成大纲的笔记 |
| 表格塌了 | 表格转成标准 Markdown 表格，连 Excel 里那种跨行列的合并单元格也会自动展开 | 表格完整可读，复制进任何软件都不乱 |
| 代码挤成一行 | 按行还原代码，缩进也一并修好 | 代码可以直接复制运行 |
| 图片太麻烦 | 自动下载全部图片，自动修正格式错误（比如伪装成图片的矢量图、动图） | 图片一张不丢，本地永久保存 |
| 存哪都要重排 | 一次转换，两个去处：本地 Markdown 笔记，或直接生成飞书文档 | 想放哪放哪，不用重复劳动 |

### 为什么值得用

- **不是复制，是重建**：它不是把网页原样搬过来，而是把文章重新整理成结构清晰的文档 —— 这是"能用"和"只是存了"的区别。
- **图片全自动**：下载、修格式、上传全包，你全程不用手动点一张图。
- **两种归宿，随你选**：想安静躺在本地笔记里？选 Markdown（还能直接适配 Obsidian 双链）。想进团队知识库？选飞书文档。
- **交付前会自检**：生成飞书文档后，它会自动拿原文逐行比对，确认没有漏掉任何一段 —— 交到你手上的就是完整版。
- **三种 AI 助手都能用**：WorkBuddy、Claude Code、Codex 都支持，装一次到处可用。

---

## 三、怎么用？（跟着做就行）

### 最简前置条件

只要两点：

1. **电脑上有 Python**（3.10 或更高版本）。不确定有没有？打开终端输入 `python --version`，能看到版本号就说明有。
2. **装两个小工具**（只需执行一次）：

```bash
pip install -r requirements.txt
```

> 想生成飞书文档？在 WorkBuddy 里使用即可（飞书连接已内置）。在其他 AI 助手里使用，需要额外安装飞书命令行工具 `@larksuite/cli` 并配置好账号，具体见 [SKILL.md](./SKILL.md)。

### 三步上手（本地 Markdown）

**第 1 步：拿到文章链接**

在微信里打开文章 → 右上角「…」→「复制链接」，得到一个以 `https://mp.weixin.qq.com/s` 开头的网址。

**第 2 步：把项目放到本地**

```bash
git clone https://github.com/bonboruyau-dev/wechat2knowledge.git
cd wechat2knowledge
pip install -r requirements.txt
```

**第 3 步：跑一条命令（最小可运行示例）**

```bash
python scripts/wechat_article_to_md.py "https://mp.weixin.qq.com/s/你复制的链接"
```

就这一行。回车后你会看到它自动下载图片、整理正文，几秒后提示「保存成功」。

### 你会得到什么

当前目录下多出两个东西：

```
AI Agent 应用精细化评测.md     ← 整理好的文章
images/                        ← 全部图片
```

打开那个 `.md` 文件（任何笔记软件或编辑器都能打开），长这样：

```markdown
# AI Agent 应用精细化评测：评测体系设计与工程实践

**作者**: 砚东
**来源**: https://mp.weixin.qq.com/s/5Tvv8g20CybjbT0a7iUfHw

---

### 1.1 从"能用"到"好用"的距离

近年来，大模型驱动的 AI Agent 在各行各业加速落地……

| 评测维度 | 指标数 |
| --- | --- |
| 端到端评测 | 11 项 |
| 核心模块评测 | 24 项 |
```

标题是标题、表格是表格、图片各就各位 —— 直接可以用。

### 想直接存成飞书文档？（4 步）

```bash
# 1. 转成带图片的 Markdown（图片名会自动规范成 img_001.png 这种）
python scripts/html_to_md.py "https://mp.weixin.qq.com/s/你复制的链接" ./_build

# 2. 图片格式自检（把矢量图、动图统一转成飞书认识的格式）
python scripts/normalize_images.py ./_build

# 3. 生成飞书文档（在 _build 目录里执行）
cd _build && node <lark-cli>/run.js docs +create \
  --doc-format markdown --content "@./doc.md" \
  --title "文章标题" --parent-position my_library

# 4. 自动比对原文，确认内容一字不差
python scripts/verify_doc.py source.html _verify.json
```

完成后会返回一个飞书文档链接，点开就是一篇排版完整、图片齐全的文档。

> 完整流程、可选参数与进阶玩法，见 [SKILL.md](./SKILL.md)。

### 装到哪些 AI 助手里？

| 你用的助手 | 怎么装 |
|---|---|
| **WorkBuddy** | 从 SkillHub 一键导入，或放到 `~/.workbuddy/skills/` |
| **Claude Code** | 放到 `~/.claude/skills/`（全局）或项目里的 `.claude/skills/` |
| **Codex** | 放到 `~/.codex/skills/`（全局）或项目里的 `.codex/skills/` |

装好后，直接跟 AI 助手说「把这篇文章转成 Markdown」就行，不用记命令。

---

## 目录结构

```
wechat2knowledge/
├── SKILL.md                      # 完整工作流与进阶用法
├── README.md                     # 本文件
├── requirements.txt              # 依赖（requests + beautifulsoup4）
├── LICENSE                       # MIT
└── scripts/
    ├── wechat_article_to_md.py   # 文章链接 → Markdown
    ├── html_to_md.py             # 网页/HTML → Markdown（飞书流程入口）
    ├── normalize_images.py       # 图片格式自检与修正
    ├── svg2png.js                # 矢量图 → 普通图片
    └── verify_doc.py             # 原文与成品的完整性比对
```

## 参与共建

欢迎提 Issue 和 Pull Request。提交前请：

1. 用一篇真实公众号文章完整跑一遍
2. 能力有变化时同步更新 `SKILL.md`

## 许可证

[MIT](./LICENSE)

---

**English**: Turn any WeChat Official Account article into a clean Markdown note or a Feishu (Lark) cloud document — with headings, tables, code blocks and images fully preserved. One command, zero manual cleanup. **Keywords**: wechat, weixin, official-account, markdown, converter, feishu, lark, knowledge-base, rag, obsidian, agent-skills, claude-code, codex
