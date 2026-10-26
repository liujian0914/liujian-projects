# proposal-forge

**中文项目申报书全流程工坊** —— 让 AI 帮你把一份毛坯稿做成能提交的正式件。

A skill + CLI toolkit for producing submission-ready Chinese project proposals (大创 / 国创赛 / 挑战杯 / 课题申报), covering document surgery, figure generation, typography repair, citation normalization, and de-AI-styling.

```bash
pf probe 稿.docx        # 看清手上有什么
pf chart --demo ./fig   # 七种图型各出一张
pf renumber 稿.docx     # 图表编号按位置重排
pf qa 稿.docx           # 交付前自检
```

---

## 为什么有这个

中文申报书很少败在"内容不够多"，通常败在四处：

| 失败点 | 具体表现 |
|---|---|
| **结构不认** | 模板分节没对齐，评委翻到第三页找不到研究内容 |
| **图不对** | 数据图是 Excel 默认样式，示意图配色各一套，整篇像拼贴 |
| **排版崩** | 图号跳号、目录页码错、表格跨页裁字、题注与图分家 |
| **语言飘** | 通篇"赋能、抓手、闭环、深刻变革"，读完不知道具体做了什么 |

这套东西按四个失败点组织，每一步都有命令和验收标准。

---

## 三十秒上手

```bash
# 1. 装依赖
pip install -r requirements.txt

# 2. 放进你的 skills 目录（任选其一）
#    Claude Code / WorkBuddy:  ~/.workbuddy/skills/proposal-forge/
#    Claude.ai:                 打包成 zip 上传到 Skills
#    Codex / Cursor:            放到项目 .skills/ 或全局 skills 目录

# 3. 自检
python scripts/pf.py doctor
```

然后对 AI 说一句"帮我把这份大创申报书改到能交"，它会自动读 `SKILL.md` 走完六阶段。

也可以纯命令行用：

```bash
python scripts/pf.py qa 我的申报书.docx --out 自检报告.md
```

---

## 六阶段流程

```
① 定基 ── probe 结构基线、锁定权威数据源、列缺口
   ↓
② 搭骨 ── 与官方模板逐项对齐，定编号体系
   ↓
③ 填肉 ── 每节"结论→问题→方法→证据→边界"
   ↓
④ 配图 ── 七种图型 + 配色家族 + 生图三件套
   ↓
⑤ 修面 ── 题注重排 → 表格防裁 → 图宽统一 → 目录页码 → 文献规范
   ↓
⑥ 交付 ── 自检报告 + docx/pdf + 改动说明
```

每阶段有门禁，门禁不过不进下一步。原因很实际：返工成本是几何级上升的。

---

## 能做什么

### 文档手术

- 旧 `.doc` / WPS 伪 `.docx` → 真 OOXML，转换后做**逐页像素比对**证明无损
- 穿透表格遍历正文（中文申报书常把全文塞进 1×1 表格，`doc.paragraphs` 会返回空）
- 克隆模板段落/表格插入新内容，格式与原文件完全一致
- 批量替换文字，自带**整段加粗**复核（这是批量替换最典型的副作用）

### 图表

七种即为申报书够用的全部图型：

| 图型 | 用在哪 |
|---|---|
| `bar` 分组柱状图 | 多对象多指标对比 |
| `dumbbell` 哑铃图 | 两组值的落差（认知 vs 执行） |
| `slope` 斜率图 | 同一批对象的前后变化 |
| `gantt` 里程碑甘特图 | 项目进度 |
| `donut` 环形图 | 样本结构（百分比自动凑满 100%） |
| `heatmap` 热力图 | 多对象 × 多维度得分矩阵 |
| `framework` 分层框架图 | 架构、流程、机制 |

配色有**家族机制**：同族是明度梯度，跨族换色相，一篇之内既统一又分得开。语义色（绿=合规、红=风险）默认不动。

### 图像运维

- 透明 PNG 压白底（不压插 Word 会渲染成黑块）
- 两张竖图合成一张横排图（分别插会把题注挤到下一页）
- HSV 分区换色，淡色填充自动提饱和（只换色相根本看不出变化）
- 改图片上的文字：反解墨迹高度/颜色/中心，字间距分摊，不改字号
- 直接换 zip 内的图，尺寸与色彩模式保持

### 排版与文字

- 图表编号按**文档位置**重排，不靠字符串匹配
- 目录页码**两遍占位法**（先定行数，渲染取页，再回填）
- 表格 `cantSplit` 修跨页裁字，表头跨页重复
- GB/T 7714-2015 文献规范化指引 + 真实性核验清单
- **去 AI 味检测器**：五类痕迹（铺垫、拔高、公式化节奏、排版痕迹、中式机器腔），给分 + 命中项 + 改写建议

### 交付自检

一条命令查：体量、图/表编号连续性、正文 `[n]` 与文献条目对应、整段加粗、重复标点、未填占位符、插图宽度分布。

---

## 命令总表

```bash
pf doctor                             # 环境自检（依赖/字体/COM）
pf init <dir>                         # 建工作区 fig/img/bak/out
pf probe <docx> [--out md]            # 结构基线
pf convert <src> [--pdf]              # 旧 doc → 真 docx
pf verify <a.docx> <b.docx>           # 双 PDF 逐页像素比对
pf renumber <docx> [--out]            # 图/表题注重排
pf toc <docx>                         # 目录页码重建
pf tables <docx> [--header]           # 表格防裁字
pf text <docx> --set A=>B             # 批量替换 + 加粗复核
pf images <docx> --action list|width|replace|keepnext
pf chart --spec x.json | --demo dir   # 出图
pf recolor <img> --anchors .. --targets ..
pf retext <img> --box x0,y0,x1,y1 --text 新字
pf hstack <imgs...> --out out.png
pf whitebg <img>
pf qa <docx> [--out md]               # 交付自检
pf style <md|docx>                    # 去 AI 味检测
```

所有命令支持 `--json`，输出结构化结果，便于 agent 直接消费。

---

## 兼容

| 环境 | 支持 |
|---|---|
| Windows + WPS/Word | 全部功能（含 COM 转换、PDF 导出、目录页码） |
| Windows 无 Office | 除 COM 相关外全部可用 |
| macOS / Linux | 除 COM 相关外全部可用（可装 LibreOffice 替代转换） |

依赖分三档，见 `requirements.txt`。最小可用组合：

```bash
pip install python-docx lxml pillow numpy matplotlib pymupdf
```

---

## 目录结构

```
proposal-forge/
├── SKILL.md                    # 主控：路由 + 六阶段 + 十条硬规则
├── README.md
├── LICENSE
├── CHANGELOG.md
├── requirements.txt
├── scripts/
│   ├── pf.py                   # 统一 CLI
│   ├── pf_docx.py              # Word 结构手术库
│   ├── pf_render.py            # 图表与图像运维库
│   └── pf_style.py             # 去 AI 味检测器
├── references/
│   ├── 01-pipeline.md          # 六阶段完整 SOP
│   ├── 02-docx-surgery.md      # Word 结构手术全套代码
│   ├── 03-figures.md           # 配图：选型、配色、缺陷修复
│   ├── 04-image-ops.md         # 图像运维五个动作
│   ├── 05-typography.md        # 排版细则
│   ├── 06-citations.md         # 文献规范与核验
│   ├── 07-humanize.md          # 去 AI 味
│   ├── 08-toolchain.md         # 科研工具链
│   └── 09-pitfalls.md          # 50 条踩坑速查
└── templates/
    ├── outline-dachuang.md     # 大创申请书骨架
    ├── outline-guochuang.md    # 国创赛申报书骨架
    ├── outline-tiaozhanbei.md  # 挑战杯调研报告骨架
    ├── gbt7714.md              # 文献著录格式卡
    ├── prompt-figures.md       # 生图提示词模板
    └── prompt-humanize.md      # 去 AI 味改写提示词
```

---

## 实测来源

流程不是凭空设计的，来自对两份真实申报书的完整改造：

- 一份 39 页的作业申报书：**58MB、OLE 复合文档**，含 50MB 图片流与内嵌表格对象。转真 OOXML 后 39 页像素差全为 0，重建 59 条目录，重排图 1–34 / 表 1–11。
- 一份 14.3MB 的大创申请书：正文全在 1×1 表格内、355 段、24 图、8 表。经六轮修订到 15,469 字 / 29 页 / 28 图，含配色家族分化、IP 与海报补入、文献从 11 条全英文改为 2 英 11 中。

踩过的坑全部写进 `references/09-pitfalls.md`，其中三条值得单独提：

1. **不要用 `id()` 给 lxml 元素去重**。子元素代理回收后地址会复用，用 id 判重会把后面的段落静默跳过——实测一份 14,465 字的文档因此只统计到 668 字，不报错，只是数少了。
2. **WPS 对含嵌入图的段落不遵守 `keepNext`/`keepLines`**。三条常规解法全部失效，唯一可行是让"图+题注"整体装得下。
3. **`set_text` 只保留 run0 格式**。run0 若是加粗序号段，整段会被加粗。批量替换后必须查一遍 bold。

---

## 边界

**能做**：结构手术、图表生成、排版修复、文献规范、语言改写、自检。

**不做**：代替本人编造调研数据与获奖经历；把别人的成果写成自己的；改他人可见的公开页面。

插入含真实人物的照片前确认授权；证件图像不上传公网。

---

## 许可

MIT。详见 `LICENSE`。

去 AI 味的规则思路参考 [blader/humanizer](https://github.com/blader/humanizer) 与 [op7418/Humanizer-zh](https://github.com/op7418/Humanizer-zh)（均为 MIT），按中文学术文体重写了词表与判据，未沿用其口语化主张。检测器为独立实现，可离线运行。

---

## English

**proposal-forge** is a skill package and CLI toolkit for producing submission-ready Chinese project proposals — the kind required by China's undergraduate innovation programs (大创), the China International College Students' Innovation Competition (国创赛), and the Challenge Cup (挑战杯).

It handles what generic document tools miss:

- **Document surgery** on real-world `.docx` files, including WPS-flavored OLE documents, full-text-inside-a-table layouts, and template-paragraph cloning that preserves original formatting exactly.
- **Seven chart types** tuned for proposal use, with a color-family system so a 25-figure document stays visually coherent without every figure looking the same.
- **Image operations**: white-background flattening, horizontal compositing, hue-family remapping, and in-image text replacement.
- **Typography repair**: position-based figure renumbering, two-pass table-of-contents page numbers, table row-split fixes.
- **De-AI-styling**: a rule-based detector for Chinese AI writing patterns, with a scoring report and rewrite guidance — tuned for academic registers, not casual prose.

All commands emit `--json` for agent consumption. Windows gets full functionality; macOS/Linux work minus Office COM features.

MIT licensed.
