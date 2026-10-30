# competition-forge · 中文竞赛全流程工坊

**一条命令级的完整链路：定赛道 → 写材料 → 配图 → 做 PPT → 自检交付。**

> 前身 `proposal-forge`（v1.1.0）。v2.0 从"申报书工坊"升级为**多赛道竞赛工坊**。

```bash
pf probe 稿.docx        # 看清手上有什么
pf chart --demo ./fig   # 七种图型各出一张
pf renumber 稿.docx     # 图表编号按位置重排
pf qa 稿.docx           # 交付前自检
```

---

## ⛔ 用之前必须知道：先定赛道

**本技能不允许在未确定赛道的情况下开始产出。**

| 赛道 | 官方全称 | 核心材料 | 要 PPT 吗 |
|---|---|---|---|
| `dachuang` | **国家级大学生创新创业训练计划** | 申请书 1.2–1.6 万字 | 通常不要 |
| `datiao` | **"挑战杯"全国大学生课外学术科技作品竞赛** | 社会调查报告 2 万字+ | **必需，决胜环节** |

**为什么必须分**：同一个项目，投大创要证明"这笔钱给我能按期做出来"，投大挑要证明"我已经做出了有价值的成果"。写法反了就是硬伤。

按大创的写法做大挑 → 死在"没有真调研"；按大挑的写法做大创 → 死在"不像个项目"。

> 名称澄清：「大创」是**训练计划**（立项拿钱），不是"大赛"；「大挑」是**课外学术科技作品竞赛**，
> 与「小挑」（创业计划竞赛）是两个不同赛事。

---

## 这套东西解决什么

中文竞赛材料很少败在"内容不够多"，通常败在五处：

| 失败点 | 具体表现 |
|---|---|
| **结构不认** | 模板分节没对齐，评委翻到第三页找不到研究内容 |
| **图不对** | 数据图是 Excel 默认样式，示意图配色各一套，整篇像拼贴 |
| **排版崩** | 图号跳号、目录页码错、表格跨页裁字、题注与图分家 |
| **语言飘** | 通篇"赋能、抓手、闭环、深刻变革"，读完不知道具体做了什么 |
| **讲不出来** | 文档不错，答辩 PPT 一放，评委三分钟没抓到重点 |

---

## 三十秒上手

```bash
# 1. 装依赖
pip install -r requirements.txt

# 2. 放进你的 skills 目录
#    WorkBuddy:  ~/.workbuddy/skills/competition-forge/
#    Codex / Cursor: 项目 .skills/ 或全局 skills 目录

# 3. 自检
python scripts/pf.py doctor
python scripts/pf.py deps      # ★ 完整自检：缺什么、怎么装、去哪下
```

然后对 AI 说：「帮我做大挑的社会调查报告」，它会先问赛道，再按赛道标准走。

### 换台电脑怎么办

**不用猜缺了什么。** 跑这一条：

```bash
python scripts/pf.py deps --md 环境报告.md
```

它会扫 Python 包、外部工具、中文字体，**每缺一项都给出 `pip`/`winget` 安装命令和官方下载链接**，
分「🔴 必须安装 / 🟡 可选安装 / ✅ 已就绪」三档。报告可以直接发给队友照着装。

**仓库不塞大文件**：SD 模型（4GB）、ppt-master（145MB）、案例库（1.09GB）都只给获取方式。
用检测代替打包——这就是 `pf deps` 的用途。


---

## 六阶段流程

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

每阶段有门禁，门禁不过不进下一步。

---

## 能做什么

### 文档手术

- 旧 `.doc` / WPS 伪 `.docx` → 真 OOXML，转换后做**逐页像素比对**证明无损
- 穿透表格遍历正文（中文申报书常把全文塞进 1×1 表格，`doc.paragraphs` 会返回空）
- 克隆模板段落/表格插入新内容，格式与原文件完全一致
- 批量替换文字，自带**整段加粗**复核

### 图表

七种图型覆盖申报书需求：

| 图型 | 用在哪 |
|---|---|
| `bar` 分组柱状图 | 多对象多指标对比 |
| `dumbbell` 哑铃图 | 两组值的落差（认知 vs 执行） |
| `slope` 斜率图 | 同一批对象的前后变化 |
| `gantt` 里程碑甘特图 | 项目进度 |
| `donut` 环形图 | 样本结构 |
| `heatmap` 热力图 | 多对象 × 多维度得分矩阵 |
| `framework` 分层框架图 | 架构、流程、机制 |

配色有**家族机制**：同族是明度梯度，跨族换色相。语义色（绿=合规、红=风险）默认不动。

### PPT（v2.0 新增）

**不自己实现 PPT，做编排层**：决定"这个赛道该讲什么、什么风格、要不要动画"，交给 [ppt-master](https://github.com/hugohe3/ppt-master) 生成。

- **动画能力**：元素级进场/强调/路径/退出 + 页面切换，通过 `svg_to_pptx.py -a auto` 控制
- **多风格**：田园实景 / 商务数据 / 人文纪实 / 学术简约，四套配色方案
- **按赛道区分**：大创讲技术路线图，大挑讲调研规模数据墙

### AI 生图（v2.0 新增）

- **本机 SD 为主**（免费无限）：`D:\AI\sd-webui`，AWPainting + majicmix 双模型
- **AGNES 免费档为辅**：写实人物、复杂场景
- **红线**：调研现场照片、获奖证书、政策截图**绝不能** AI 生成

### 科研绘图（v2.0 新增）

顶刊风格数据图：Nature/Science 配色、多子图 a/b/c 标注、误差棒、散点拟合、矢量输出。

### 图像运维

- 透明 PNG 压白底（不压插 Word 会渲染成黑块）
- 两张竖图合成一张横排图
- HSV 分区换色
- 改图片上的文字：反解墨迹高度/颜色/中心

### 排版与文字

- 图表编号按**文档位置**重排
- 目录页码**两遍占位法**
- 表格 `cantSplit` 修跨页裁字，表头跨页重复
- GB/T 7714-2015 文献规范化 + 真实性核验
- **去 AI 味检测器**：五类痕迹，给分 + 命中项 + 改写建议

---

## 命令总表

```bash
pf doctor                             # 环境自检
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

所有命令支持 `--json`。

---

## 目录结构

```
competition-forge/
├── SKILL.md                    # 主控：强制定赛道 + 六阶段 + 硬规则
├── README.md
├── CHANGELOG.md
├── competitions/               # ★ 赛道层（v2.0 新增）
│   ├── registry.md             #   注册表：先查这个
│   ├── README.md               #   赛道机制说明 + 怎么加新比赛
│   ├── dachuang/               #   大创
│   │   ├── PROFILE.md          #     评审偏好、骨架、失分点
│   │   ├── cases.md            #     GIEP 实战复盘
│   │   └── ppt.md              #     PPT 策略
│   └── datiao/                 #   大挑
│       ├── PROFILE.md          #     评审偏好、骨架、失分点
│       ├── cases.md            #     14 个获奖案例深度分析
│       └── ppt.md              #     PPT 策略
├── ppt/                        # ★ PPT 编排层（v2.0 新增）
│   └── PLAYBOOK.md             #   赛道→策略→动画→调 ppt-master
├── figures/                    # ★ 绘图能力（v2.0 新增）
│   ├── SCIENCE-PLOT.md         #   顶刊风格科研绘图
│   └── AI-IMAGERY.md           #   AI 生图（本机 SD + AGNES）
├── scripts/
│   ├── pf.py                   # 统一 CLI
│   ├── pf_docx.py              # Word 结构手术库
│   ├── pf_render.py            # 图表与图像运维库
│   ├── pf_style.py             # 去 AI 味检测器
│   └── analyze_datiao_ppt.py   # 大挑案例 PPT 分析工具（v2.0）
├── references/                 # 通用方法（10 份）
└── templates/                  # 章节骨架（6 份）
```

---

## 实测来源

### 文档侧

- 一份 39 页的作业申报书：**58MB、OLE 复合文档**，含 50MB 图片流。转真 OOXML 后 39 页像素差全为 0，重建 59 条目录，重排图 1–34 / 表 1–11。
- 一份 14.3MB 的大创申请书：正文全在 1×1 表格内、355 段、24 图、8 表。经六轮修订到 15,469 字 / 29 页 / 28 图。

### 赛道侧

- **大挑**：桌面「大挑案例」库，14 个往年获奖作品（7 类主题，1.09 GB）。
  逐页分析 8 份答辩 PPT，提炼出调研规模数据墙、自创框架图、四种视觉风格等规律。
- **大创**：GIEP·地标智眸完整改造复盘（22 份评委样本书 + 《评审说明》提炼的评审偏好）。

踩过的坑全部写进 `references/09-pitfalls.md`，其中三条值得单独提：

1. **不要用 `id()` 给 lxml 元素去重**。子元素代理回收后地址会复用，用 id 判重会把后面的段落静默跳过——实测一份 14,465 字的文档因此只统计到 668 字，不报错，只是数少了。
2. **WPS 对含嵌入图的段落不遵守 `keepNext`/`keepLines`**。唯一可行是让"图+题注"整体装得下。
3. **`set_text` 只保留 run0 格式**。run0 若是加粗序号段，整段会被加粗。

---

## 边界

**能做**：结构手术、图表生成、排版修复、文献规范、语言改写、PPT 编排、科研绘图、AI 配图、自检。

**不做**：代替本人编造调研数据与获奖经历；把别人的成果写成自己的；改他人可见的公开页面。

**红线**：往年获奖案例只用于学习写法，**不得搬运其数据、结论或图表**；调研现场照片、获奖证书、政策文件截图**不得用 AI 生成或修改**。

---

## 许可

MIT。详见 `LICENSE`。

去 AI 味的规则思路参考 [blader/humanizer](https://github.com/blader/humanizer) 与 [op7418/Humanizer-zh](https://github.com/op7418/Humanizer-zh)（均为 MIT），按中文学术文体重写了词表与判据。
PPT 能力调用 [ppt-master](https://github.com/hugohe3/ppt-master)（MIT，v6.7.2），不复制其代码。

---

## English

**competition-forge** is a multi-track workflow for Chinese academic competitions, covering the entire pipeline from project proposals to defense slide decks.

**v2.0 upgrade**: it is now track-based. Every task must first declare which competition it targets:

- **大创** (National Undergraduate Innovation and Entrepreneurship Training Program) — a *funding application*; judges ask "can you deliver?"
- **大挑** ("Challenge Cup" National Undergraduate Academic and Scientific Works Competition) — a *results competition*; judges ask "what did you find?"

The two have different evaluation criteria, document structures, and slide-deck logic. Writing one like the other is a fatal error.

**Capabilities**:
- **Document surgery** on real-world `.docx` files, including WPS-flavored OLE documents and full-text-inside-a-table layouts.
- **Seven chart types** with a color-family system.
- **Slide-deck orchestration** — decides track-specific narrative, style, and animation, then delegates to [ppt-master](https://github.com/hugohe3/ppt-master) for native PPTX generation (element-level entrance/emphasis/motion-path animations supported).
- **AI imagery** — local Stable Diffusion (free, unlimited) as primary, free-tier cloud as supplement, with a hard red line against AI-generating evidence photos.
- **Publication-grade plotting** — Nature/Science color palettes, multi-panel a/b/c labeling, error bars, vector output.
- **Typography repair** and **de-AI-styling** detection for Chinese academic registers.

All commands emit `--json`. MIT licensed.
