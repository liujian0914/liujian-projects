# AI 生图 · 本机 SD 为主，免费档为辅

> 原则：**能不花钱就不花钱**。本机 SD 已装好、离线、无限量；只有 SD 明显不行的场景才走云端免费档。

---

## 〇、先看红线（竞赛场景特有）

**绝对不能用 AI 生成或修改的图**：

| 类型 | 为什么 |
|---|---|
| 调研现场照片 | 伪造调研事实，学术不端，直接淘汰 |
| 获奖证书 / 荣誉证明 | 伪造，违法 |
| 政策文件截图 | 伪造依据 |
| 访谈对象肖像 | 需真实授权 |
| 问卷原件扫描 | 伪造证据 |

**可以用 AI 生成的**：

| 类型 | 用途 |
|---|---|
| 章节页背景 / 纹理 | 装饰 |
| 抽象概念图 | 示意（如"协同""赋能"的视觉化） |
| IP 形象 / 吉祥物 | 项目品牌 |
| 架构图底图 | 示意 |
| 图标 | 装饰 |

**一句话**：AI 只能画**装饰和示意**，不能画**证据**。

---

## 一、本机 SD（首选，免费无限）

### 1.1 现状

| 项 | 值 |
|---|---|
| 位置 | `D:\AI\sd-webui\`（AUTOMATIC1111 v1.10.1） |
| 模型 | `AWPainting_v1.2`（动漫/通用，默认）、`majicmixRealistic_v7`（写实） |
| VAE | `vae-ft-mse-840000` / `animevae` |
| LoRA | `add_detail` |
| 嵌入 | `EasyNegative` / `badhandv4` |
| 显卡 | RTX 5060 Laptop 8GB（Blackwell sm_120，必须 cu128） |
| 驱动方式 | DSH 插件 `dsh-sd-bridge-guard` |
| 启动 | 必须带 `--skip-prepare-environment`（上游已删库） |

### 1.2 怎么用

**在 DeepSeek Harness 里**：直接用 `sd_txt2img` / `sd_img2img` / `sd_inpaint` 工具。

**在任何 agent 里**：跑 `D:\AI\sd-webui\webui-user.bat` 开服务，然后调 API。

### 1.3 竞赛 PPT 常用提示词模板

#### 章节页背景（抽象纹理）

```
abstract green gradient background, soft light, subtle geometric patterns,
minimalist, clean, no text, professional presentation background,
high quality, 16:9
```
负向：`text, watermark, logo, people, face, busy, cluttered`

#### 概念示意图底图

```
minimalist illustration of connected nodes and flowing lines,
green and gold color scheme, clean white background,
flat design, infographic style, no text
```

#### IP 形象（项目吉祥物）

```
cute mascot character, [主题元素], simple flat design,
green and cream color palette, friendly expression,
white background, vector art style, high quality
```
负向：`realistic, photo, complex details, dark colors`

### 1.4 参数建议

| 用途 | 尺寸 | 步数 | CFG | 采样器 | denoising（图生图） |
|---|---|---|---|---|---|
| 背景图 | 1920×1080 | 25 | 7 | DPM++ 2M | — |
| 概念图 | 1024×1024 | 25 | 7 | DPM++ 2M | — |
| IP 形象 | 768×768 | 28 | 7.5 | DPM++ 2M | 0.6–0.7 |
| 图标 | 512×512 | 20 | 7 | DPM++ 2M | — |

### 1.5 生成后处理

```bash
# 透明背景压白底（不压插 PPT/Word 会渲染成黑块）
pf whitebg ip.png

# 两张竖图合成一张横排
pf hstack a.png b.png --out ab.png

# 配色统一到项目主色
pf recolor 图.png --out 改色.png --anchors 0 30 170 215 275 --targets 8 40 190 240 300
```

---

## 二、AGNES 免费档（补充）

### 2.1 什么时候用

本机 SD 明显不行的场景：

| 场景 | 为什么 SD 不行 |
|---|---|
| 写实人物 | SD1.5 底模写实能力有限 |
| 复杂场景构图 | 需要更强的语义理解 |
| 特定艺术风格 | SD 需要专门 LoRA |
| 中文文字渲染 | SD 画不好中文 |

### 2.2 怎么用

技能 `agnes-media-generation` 已装，支持：
- 文生图（**免费**）
- 文生视频（含首尾帧控制、多模态参考）

触发词：`生成图片`、`生成视频`、`文生图`、`画一张`、`agnes`

### 2.3 注意

- 免费档有额度限制，**别用来批量试错**
- 生成的内容同样受上面的红线约束
- 竞赛材料里用 AGNES 生成的图，建议在改动说明里标注来源（诚信加分）

---

## 三、决策树：用哪个

```
要生成图
  ├─ 是"证据类"（现场照片/证书/文件截图）？
  │    └─ ❌ 都不能用 AI，必须用真实的
  ├─ 是装饰/示意/IP？
  │    ├─ 抽象背景、纹理、图标 → 本机 SD（免费无限）
  │    ├─ 写实人物、复杂场景 → AGNES 免费档
  │    └─ 需要精确文字 → 不用 AI，用 PPT 原生文字
  └─ 是数据图？
       └─ 不用 AI，用 pf chart 或 SCIENCE-PLOT.md
```

---

## 四、常见问题

**Q：SD 生成 1920×1080 会爆显存吗？**
8GB 显存跑 1920×1080 单张可以，批量要分批。显存不够时插件会自动降级。

**Q：生成的背景图有文字怎么办？**
负向提示词加 `text, watermark, letters`，还不干净就用 `pf retext` 抹掉。

**Q：AI 图会不会和别人的 PPT 撞图？**
SD 本地生成、随机种子，撞图概率极低。AGNES 云端生成的理论上可能，但概率也很低。

**Q：能不能用 AI 生成"调研现场"的照片？**
**绝对不能。** 这是伪造证据，一旦被查出来（比如照片里的光影、人物、场景对不上），直接淘汰并可能影响学校。这条没有例外。

**Q：PPT 里的图表能不能 AI 生成？**
不能。数据图必须用真实数据画（`pf chart` / matplotlib），AI 画出来的数字是假的。
