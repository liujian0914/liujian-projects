<div align="center">

# 🔨 competition-forge

**中文竞赛全流程工坊 · 从"有个想法"到"评委愿意读下去"**

定赛道 → 写材料 → 配图 → 做 PPT → 自检交付，一条链路打通

[![Version](https://img.shields.io/badge/version-2.0.1-2D5016?style=for-the-badge)](CHANGELOG.md)
[![License](https://img.shields.io/badge/license-MIT-lightgrey?style=for-the-badge)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![Agent](https://img.shields.io/badge/agent-agnostic-6B7461?style=for-the-badge)](SKILL.md)
[![Tracks](https://img.shields.io/badge/tracks-大创%20%7C%20大挑-9C7734?style=for-the-badge)](#-step-0-先定赛道)

Quick Start · [为什么分赛道](#-step-0-先定赛道) · [能做什么](#-能做什么) · [命令总表](#-命令总表) · [目录结构](#-目录结构) · [实测来源](#-实测来源)

</div>

---

> **一句话**：中文竞赛材料很少败在"内容不够多"，几乎都败在五处 —— 结构不认、图不对、排版崩、语言飘、讲不出来。这个工坊按这五个失败点组织流程，每一步都有可执行的命令和验收门禁。

> [!IMPORTANT]
> **这不是"一键生成申报书"的许愿池。** 它接管的是最耗时的机械部分（结构对齐、图表编号、目录页码、表格跨页、去 AI 味），
> 内容、数据、调研仍然是你的活。而且它强制你先回答一个问题：**投哪个比赛？**

---

## 🚀 Quick Start

### 1. 装依赖

```bash
pip install -r requirements.txt
```

### 2. 放进你的 skills 目录

| Agent | 放在哪 |
|---|---|
| WorkBuddy | `~/.workbuddy/skills/competition-forge/` |
| Codex / Cursor | 项目 `.skills/` 或全局 skills 目录 |
| Claude Code | `~/.claude/skills/competition-forge/` |

### 3. 自检

```bash
python scripts/pf.py doctor    # 环境自检
python scripts/pf.py deps      # ★ 完整自检：缺什么、怎么装、去哪下
```

### 4. 对 AI 说

> 「帮我做大挑的社会调查报告」

它会先问赛道，再按该赛道的评审标准走。

<details>
<summary><b>换台电脑 / 队友那边缺依赖怎么办</b></summary>

**不用猜缺了什么。** 跑这一条：

```bash
python scripts/pf.py deps --md 环境报告.md
```

它扫三类东西：Python 包、外部工具、中文字体。**每缺一项都给出 `pip`/`winget` 安装命令和官方下载链接**，
分「🔴 必须安装 / 🟡 可选安装 / ✅ 已就绪」三档，报告可直接发队友照着装。

**⚠️ 先确认解释器**：报告第一行会打印 `解释器：<路径>`。本机有多个 Python 时，
用错解释器会报"缺 6 项核心依赖"——那不是真缺，是找错了环境。

**仓库不塞大文件**：SD 模型（4GB）、ppt-master（145MB）、案例库（1.09GB）都只给获取方式，用检测代替打包。

</details>

---

## ⛔ Step 0：先定赛道

**本技能不允许在未确定赛道的情况下产出任何正式材料。** 这不是建议，是硬门禁。

| | 大创 | 大挑 |
|---|---|---|
| **官方全称** | 国家级大学生创新创业训练计划 | "挑战杯"全国大学生课外学术科技作品竞赛 |
| **本质** | **项目立项**：要钱、要按期结题 | **成果竞赛**：已有成果去比拼 |
| **评委看什么** | 可行性、创新性、经费合理性、能不能结题 | 选题价值、调研方法、数据真实性、社会效益 |
| **核心材料** | 申请书 1.2–1.6 万字 | 社会调查报告 2 万字以上 |
| **要 PPT 吗** | 通常不需要 | **必需，且是决胜环节** |
| **常见死法** | 经费编不圆、进度排不出 | 数据来源说不清、结论撑不住 |

**为什么必须分**：同一个项目，投大创要证明"这笔钱给我能按期做出来"，投大挑要证明"我已经做出了有价值的成果"。写法反了就是硬伤 —— 按大创的写法做大挑死在"没有真调研"，按大挑的写法做大创死在"不像个项目"。

> [!NOTE]
> **名称澄清**：「大创」是**训练计划**（立项拿钱），不是"大赛"；「大挑」是**课外学术科技作品竞赛**，
> 与「小挑」（创业计划竞赛）是两个不同赛事，别混。

**要加新赛事**：走 `competitions/README.md` 的注册流程，不动主流程代码。

---

## ✨ 能做什么

### 文档手术

| 能力 | 说明 |
|---|---|
| 旧格式净化 | `.doc` / WPS 伪 `.docx` → 真 OOXML，转换后做**逐页像素比对**证明无损 |
| 穿透表格遍历 | 中文申报书常把全文塞进 1×1 表格，`doc.paragraphs` 返回空 —— 本工具全部穿透 |
| 克隆式插段 | 克隆模板段落/表格插入新内容，格式与原文件完全一致 |
| 安全批量替换 | 自带**整段加粗**复核（`set_text` 只保留 run0 格式，run0 是加粗序号就会炸） |

### 七种图表

| 图型 | 用在哪 |
|---|---|
| `bar` 分组柱状图 | 多对象多指标对比 |
| `dumbbell` 哑铃图 | 两组值的落差（认知 vs 执行） |
| `slope` 斜率图 | 同一批对象的前后变化 |
| `gantt` 里程碑甘特图 | 项目进度 |
| `donut` 环形图 | 样本结构 |
| `heatmap` 热力图 | 多对象 × 多维度得分矩阵 |
| `framework` 分层框架图 | 架构、流程、机制 |

配色有**家族机制**：同族是明度梯度，跨族换色相。语义色（绿=合规、红=风险、蓝=授权等级）默认不动。

### PPT 编排

**不自己实现 PPT，只做编排层** —— 决定"这个赛道该讲什么、什么风格、要不要动画"，交给 [ppt-master](https://github.com/hugohe3/ppt-master) 生成原生 PPTX。

- **动画**：元素级进场/强调/路径/退出 + 页面切换（`svg_to_pptx.py -a auto`）
- **多风格**：田园实景 / 商务数据 / 人文纪实 / 学术简约，四套配色
- **按赛道区分**：大创讲技术路线图与可行性，大挑讲调研规模数据墙与社会价值

### AI 生图 · 科研绘图

- **本机 SD 为主**（免费无限）：AWPainting + majicmix 双模型
- **AGNES 免费档为辅**：写实人物、复杂场景
- **科研绘图**：Nature/Science 配色、多子图 a/b/c 标注、误差棒、散点拟合、矢量输出

> [!WARNING]
> **红线**：调研现场照片、获奖证书、政策文件截图 **绝不能** AI 生成或修改。
> 往年获奖案例只用于学习写法，**不得搬运其数据、结论或图表**。

### 排版与语言

- 图表编号按**文档位置**重排（不按字符串匹配 —— 总有"图 0""表 2 带空格"的漏网之鱼）
- 目录页码**两遍占位法**（编辑器里的域不可信，按渲染结果算）
- 表格 `cantSplit` 修跨页裁字 + 表头跨页重复
- GB/T 7714-2015 文献规范化 + 逐条真实性核验
- **去 AI 味检测**：五类痕迹给分 + 命中项 + 改写建议（含中文文档最易暴露的「空格痕迹」）

---

## 🔄 六阶段流程

每阶段有**门禁**，门禁不过不进下一步 —— 返工成本是几何级上升的。

```
⓪ 定赛道 ── 大创 / 大挑 / 以后新增的赛事
   ↓
① 定基 ── probe 结构基线、锁定权威数据源、列缺口
   ↓
② 搭骨 ── 与官方模板逐项对齐，定编号体系
   ↓
③ 填肉 ── 每节"结论→问题→方法→证据→边界"
   ↓
④ 配图 ── 数据图 + 示意图 + AI 形象图
   ↓
⑤ 修面 ── 题注重排 → 表格防裁 → 图宽统一 → 目录页码 → 文献规范
   ↓
⑥ 交付 ── 自检报告 + docx/pdf + 改动说明
   ↓
⑦ PPT ── 按赛道策略调 ppt-master 生成答辩 PPT（含动画）
```

**门禁示例**
- ① 过不了：说不出"核心结论是什么，用哪三个数据支撑"
- ② 过不了：标题数量/层级/顺序与模板不一致，或表格数量不一致
- ⑤ 过不了：`pf qa` 报告里图/表编号不连续，或正文引用与条目对不上
- ⑥ 过不了：去 AI 味得分 < 80

---

## 📟 命令总表

```bash
pf doctor                             # 环境自检
pf deps [--md 报告.md]                 # ★ 完整依赖自检（缺失项带安装命令与官方链接）
pf init <dir>                         # 建工作区 fig/img/bak/out
pf probe <docx> [--out md]            # 结构基线：字数/段落/表/图/标题/图宽
pf convert <src> [--pdf]              # 旧 doc / OLE → 真 docx
pf verify <a.docx> <b.docx>           # 双 PDF 逐页像素比对
pf renumber <docx> [--out]            # 图/表题注按文档位置重排
pf toc <docx>                         # 目录页码两遍占位法重建
pf tables <docx> [--header]           # 表格防跨页裁字 + 表头重复
pf text <docx> --set A=>B             # 批量替换 + 加粗复核
pf images <docx> --action list|width|replace|keepnext
pf chart --spec x.json | --demo dir   # 出图（七种图型）
pf recolor <img> --anchors .. --targets ..   # HSV 分区换色
pf retext <img> --box x0,y0,x1,y1 --text 新字
pf hstack <imgs...> --out out.png     # 竖图合成横排图
pf whitebg <img>                      # 透明 PNG 压白底（不压插 Word 变黑块）
pf qa <docx> [--out md]               # 交付自检
pf style <md|docx>                    # 去 AI 味检测
```

所有命令支持 `--json`，便于 agent 直接消费。

---

## 🏗️ 目录结构

```
competition-forge/
├── SKILL.md                    # 主控：强制定赛道 + 六阶段 + 11 条硬规则
├── README.md
├── CHANGELOG.md
├── competitions/               # ★ 赛道层
│   ├── registry.md             #   注册表：定赛道第一步先查这个
│   ├── README.md               #   赛道机制 + 怎么加新比赛
│   ├── dachuang/               #   大创
│   │   ├── PROFILE.md          #     评审偏好、骨架、字数、失分点
│   │   ├── cases.md            #     GIEP 实战复盘
│   │   └── ppt.md              #     PPT 策略
│   └── datiao/                 #   大挑
│       ├── PROFILE.md          #     评审偏好、骨架、字数、失分点
│       ├── cases.md            #     15 份计划书骨架 + 12 条写作规律
│       ├── visual-style.md     #     配色量化 + 四套方案 + 图型规范
│       └── ppt.md              #     PPT 策略
├── ppt/
│   └── PLAYBOOK.md             # 赛道→策略→动画→调 ppt-master
├── figures/
│   ├── SCIENCE-PLOT.md         # 顶刊风格科研绘图
│   └── AI-IMAGERY.md           # AI 生图（本机 SD + AGNES）
├── scripts/                    # 10 个脚本
│   ├── pf.py                   #   统一 CLI
│   ├── pf_docx.py              #   Word 结构手术库
│   ├── pf_render.py            #   图表与图像运维库
│   ├── pf_style.py             #   去 AI 味检测器
│   ├── pf_doctor.py            #   依赖自检
│   ├── pf_selftest.py          #   17 项断言自测
│   └── analyze_*.py            #   案例分析方法脚本
├── references/                 # 11 份通用方法
│   ├── 01-pipeline.md          #   完整流程每阶段动作与话术
│   ├── 02-docx-surgery.md      #   Word 结构手术
│   ├── 03-figures.md           #   七种图型参数与配色家族
│   ├── 04-image-ops.md         #   图片处理
│   ├── 05-typography.md        #   题注/目录/表格/缩进/封面
│   ├── 06-citations.md         #   文献规范与真实性核验
│   ├── 07-humanize.md          #   去 AI 味（含「空格痕迹」专章）
│   ├── 08-toolchain.md         #   科研工具链
│   ├── 09-pitfalls.md          #   踩坑速查 62 条
│   ├── 10-case-dachuang-giep.md        # 大创实战复盘
│   └── 11-lessons-2026-tianmai.md      # 6 轮返工教训清单
└── templates/
    ├── outline-dachuang.md     #   大创申请书骨架
    ├── outline-guochuang.md    #   国创赛申报书骨架
    ├── outline-tiaozhanbei.md  #   挑战杯调研报告骨架
    ├── gbt7714.md              #   文献著录格式卡
    ├── prompt-figures.md       #   生图提示词模板
    ├── prompt-humanize.md      #   去 AI 味改写提示词
    └── paper-format/           #   参选论文编排格式（格式卡 md + 官方范本 docx）
```

---

## 📚 实测来源

这套东西不是照着文档写的，是拿真材料改出来的。

### 文档侧

- **一份 39 页作业申报书**：58MB、OLE 复合文档、含 50MB 图片流。转真 OOXML 后 39 页像素差全为 0，重建 59 条目录，重排图 1–34 / 表 1–11。
- **一份 14.3MB 大创申请书**：正文全在 1×1 表格内、355 段、24 图、8 表。六轮修订到 15,469 字 / 29 页 / 28 图。
- **一份 25 页大挑调研报告**：6 轮退回，教训全部写进 `references/11-lessons-2026-tianmai.md`。

### 赛道侧

- **大挑**：14 个往年获奖作品（7 类主题，1.09 GB）。逐页分析 8 份答辩 PPT，提炼出调研规模数据墙、自创框架图、四种视觉风格等规律；OCR 15 份计划书取出章节骨架与 12 条写作规律。
- **大创**：GIEP·地标智眸完整改造复盘（22 份评委样本书 + 《评审说明》提炼的评审偏好）。

### 三条值得单独说的坑

1. **不要用 `id()` 给 lxml 元素去重** —— 子元素代理回收后地址会复用，用 id 判重会把后面的段落静默跳过。实测一份 14,465 字的文档因此只统计到 668 字，**不报错，只是数少了**。
2. **WPS 对含嵌入图的段落不遵守 `keepNext`/`keepLines`** —— 唯一可行是让"图+题注"整体装得下。
3. **`set_text` 只保留 run0 格式** —— run0 若是加粗序号段，整段会被加粗。

---

## 🗺️ Roadmap

- [x] v1.0 文档手术 + 七种图表 + 排版修复
- [x] v1.1 大创 GIEP 实战复盘回灌
- [x] v2.0 多赛道架构（大创 / 大挑）+ PPT 编排层 + AI 生图 + 科研绘图
- [x] v2.0.1 返工教训清单 + 参选论文格式卡
- [ ] 更多赛道：国创赛、互联网+、创青春
- [ ] 大挑案例库扩充到 30 份
- [ ] 图表规格 JSON 的可视化编辑器

---

## 🤝 Contributing

有新的赛事、新的坑、更好的判据，欢迎提 PR：

1. Fork 本仓库
2. 新建分支 `feature/你的改动`
3. 提交（一个改动一个 commit，说明"为什么"而不只是"改了什么"）
4. 开 PR

**加新赛道**请先读 `competitions/README.md`，按注册表流程走，不要改主流程代码。

---

## 📄 License

MIT，详见 [`LICENSE`](LICENSE)。

去 AI 味的规则思路参考 [blader/humanizer](https://github.com/blader/humanizer) 与 [op7418/Humanizer-zh](https://github.com/op7418/Humanizer-zh)（均 MIT），按中文学术文体重写了词表与判据。
PPT 能力调用 [ppt-master](https://github.com/hugohe3/ppt-master)（MIT），不复制其代码。

**边界**：不做代替本人编造调研数据与获奖经历；不把别人的成果写成自己的；不改他人可见的公开页面。

---

<div align="center">

**liujian0914** · [GitHub](https://github.com/liujian0914)

</div>
