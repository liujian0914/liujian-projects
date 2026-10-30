# 科研绘图 · 顶刊风格数据图

> 竞赛申报书和 PPT 里的数据图，默认 `pf chart` 的七种图型已经够用。
> 本文件解决的是**更高要求**：要看起来像 Nature/Science 论文里的图。

---

## 一、什么时候需要顶刊风格

| 场景 | 用 `pf chart` 够了 | 需要顶刊风格 |
|---|---|---|
| 常规柱状图、饼图 | ✅ | |
| 多子图组合（a/b/c/d 标注） | | ✅ |
| 误差棒 / 置信区间 | | ✅ |
| 散点 + 拟合线 + R² | | ✅ |
| 热力图 + 聚类 | | ✅ |
| 双轴图 | ✅ | |
| 需要矢量输出（EPS/PDF） | | ✅ |

**判断标准**：如果你的图要放在"研究方法"或"数据分析"章节，且评委里有相关专业背景，用顶刊风格。

---

## 二、顶刊风格的五条硬规则

### 2.1 配色：不用默认色

matplotlib 默认的 `tab10` 一眼就是"没调过"。用这些：

```python
# Nature 风格（推荐）
NATURE_COLORS = [
    "#E64B35",  # 红
    "#4DBBD5",  # 青
    "#00A087",  # 绿
    "#3C5488",  # 深蓝
    "#F39B7F",  # 橙
    "#8491B4",  # 灰蓝
    "#91D1C2",  # 浅青
    "#DC0000",  # 正红
    "#7E6148",  # 棕
    "#B09C85",  # 米棕
]

# Science 风格
SCIENCE_COLORS = ["#3B4992", "#EE0000", "#008B45", "#631879", "#008280", "#BB0021"]

# 单色渐变（适合热力图）
GREEN_GRADIENT = ["#F7FCF5", "#E5F5E0", "#C7E9C0", "#A1D99B", "#74C476", "#41AB5D", "#238B45", "#006D2C", "#00441B"]
```

### 2.2 字体：无衬线 + 统一字号

```python
import matplotlib.pyplot as plt

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "Microsoft YaHei"],  # 中文用雅黑
    "font.size": 9,              # 正文字号
    "axes.titlesize": 10,        # 标题
    "axes.labelsize": 9,         # 轴标签
    "xtick.labelsize": 8,        # 刻度
    "ytick.labelsize": 8,
    "legend.fontsize": 8,
    "figure.dpi": 300,           # 高分辨率
    "savefig.dpi": 300,
    "savefig.bbox": "tight",     # 不留白边
    "axes.linewidth": 0.8,       # 细轴线
    "xtick.major.width": 0.8,
    "ytick.major.width": 0.8,
    "xtick.direction": "out",
    "ytick.direction": "out",
})
```

**⚠️ 本机踩过的坑**：`Noto Sans SC` 可变字体在 matplotlib 里**只注册 weight 100**（超细），
中文会显示成极细线。改用 `Microsoft YaHei`（注册了 400/700）。

### 2.3 去掉一切多余装饰

```python
ax.spines["top"].set_visible(False)      # 去上边框
ax.spines["right"].set_visible(False)    # 去右边框
ax.grid(False)                            # 去网格（或用极淡的）
# 或者保留网格但要极淡：
# ax.grid(True, linestyle=":", alpha=0.3, linewidth=0.5)
```

**顶刊图的特点**：留白多、装饰少、数据本身突出。

### 2.4 多子图要标注 a/b/c/d

```python
fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.4))  # 7.2 英寸 = 双栏宽

for i, ax in enumerate(axes):
    # ... 画图 ...
    ax.text(-0.15, 1.05, "abc"[i], transform=ax.transAxes,
            fontsize=12, fontweight="bold", va="top", ha="right")

plt.tight_layout()
plt.savefig("fig.pdf", bbox_inches="tight")   # 矢量
```

### 2.5 尺寸按期刊规范

| 用途 | 宽度 | 说明 |
|---|---|---|
| 单栏 | 3.5 英寸（89mm） | 竖排小图 |
| 双栏 | 7.2 英寸（183mm） | 横排大图 |
| 全宽 | 7.5 英寸 | 跨页图 |

**竞赛文档里**：Word 正文宽约 12.2cm ≈ 4.8 英寸。所以图宽设 4.8 英寸，
或者按 7.2 英寸画完再 `pf images --action width --cm 12.2` 统一缩放。

---

## 三、六种高频图的顶刊写法

### 3.1 带误差棒的柱状图

```python
import numpy as np
import matplotlib.pyplot as plt

groups = ["认知", "执行", "意愿", "能力"]
means = [75.3, 40.2, 68.5, 52.1]
stds = [8.2, 9.6, 7.4, 8.8]

fig, ax = plt.subplots(figsize=(4.8, 3.2))
x = np.arange(len(groups))
bars = ax.bar(x, means, 0.6, yerr=stds, capsize=3,
              color="#00A087", edgecolor="black", linewidth=0.8,
              error_kw={"elinewidth": 0.8, "capthick": 0.8})

ax.set_xticks(x)
ax.set_xticklabels(groups)
ax.set_ylabel("得分")
ax.set_ylim(0, 100)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

plt.tight_layout()
plt.savefig("fig_bar.pdf")
plt.savefig("fig_bar.png", dpi=300)
```

### 3.2 散点 + 拟合线 + R²

```python
from scipy import stats

x = np.array([...]); y = np.array([...])
slope, intercept, r, p, se = stats.linregress(x, y)

fig, ax = plt.subplots(figsize=(4.8, 3.6))
ax.scatter(x, y, s=20, alpha=0.6, color="#3C5488", edgecolor="none")
xx = np.linspace(x.min(), x.max(), 100)
ax.plot(xx, slope*xx + intercept, color="#E64B35", linewidth=1.2)
ax.text(0.05, 0.95, f"$R^2$ = {r**2:.3f}\n$p$ {'<' if p<0.001 else '='} {p:.3f}",
        transform=ax.transAxes, va="top", fontsize=8)

ax.set_xlabel("自变量")
ax.set_ylabel("因变量")
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
plt.tight_layout()
plt.savefig("fig_scatter.pdf")
```

### 3.3 热力图（相关系数矩阵）

```python
import seaborn as sns

corr = df.corr()
fig, ax = plt.subplots(figsize=(5, 4))
sns.heatmap(corr, annot=True, fmt=".2f", cmap="RdBu_r",
            center=0, vmin=-1, vmax=1,
            square=True, linewidths=0.5, linecolor="white",
            cbar_kws={"shrink": 0.8, "label": "相关系数"},
            annot_kws={"size": 7}, ax=ax)
plt.tight_layout()
plt.savefig("fig_heatmap.pdf")
```

**注意**：seaborn 默认会继承全局 `grid.linestyle`，热力图网格会变虚线——显式设 `linewidths` 和 `linecolor` 覆盖。

### 3.4 分组柱状图 + 显著性标注

```python
fig, ax = plt.subplots(figsize=(5, 3.2))
x = np.arange(3)
w = 0.35
ax.bar(x - w/2, [12, 15, 18], w, label="2022", color="#4DBBD5", edgecolor="black", linewidth=0.6)
ax.bar(x + w/2, [18, 22, 27], w, label="2023", color="#E64B35", edgecolor="black", linewidth=0.6)

# 显著性标注
def sig_bar(ax, x1, x2, y, h, text):
    ax.plot([x1, x1, x2, x2], [y, y+h, y+h, y], lw=0.8, c="black")
    ax.text((x1+x2)/2, y+h, text, ha="center", va="bottom", fontsize=7)

sig_bar(ax, x[0]-w/2, x[0]+w/2, 20, 1, "*")
ax.legend(frameon=False)
```

### 3.5 箱线图 + 散点叠加

```python
fig, ax = plt.subplots(figsize=(4.5, 3.2))
bp = ax.boxplot([g1, g2, g3], labels=["A", "B", "C"], patch_artist=True,
                widths=0.5, showfliers=False,
                medianprops={"color": "black", "linewidth": 1.2})
for patch, color in zip(bp["boxes"], ["#4DBBD5", "#00A087", "#E64B35"]):
    patch.set_facecolor(color); patch.set_alpha(0.7)

# 叠加原始数据点（抖动）
for i, data in enumerate([g1, g2, g3], 1):
    jitter = np.random.normal(i, 0.04, len(data))
    ax.scatter(jitter, data, s=8, alpha=0.4, color="black", edgecolor="none")
```

### 3.6 双轴图（`pf chart` 也支持）

```python
fig, ax1 = plt.subplots(figsize=(5, 3.2))
ax2 = ax1.twinx()

ax1.bar(x, values1, color="#4DBBD5", edgecolor="black", linewidth=0.6, label="总量")
ax2.plot(x, values2, color="#E64B35", marker="o", markersize=4, linewidth=1.2, label="增长率")

ax1.set_ylabel("总量", color="#4DBBD5")
ax2.set_ylabel("增长率 (%)", color="#E64B35")
ax2.spines["top"].set_visible(False)
```

---

## 四、输出格式

| 用途 | 格式 | 参数 |
|---|---|---|
| Word 文档插图 | **PNG 300dpi** | `dpi=300, bbox_inches="tight"` |
| PPT 插图 | **PNG 300dpi** 或 EMF | 同上 |
| 论文投稿 | **PDF / EPS 矢量** | `savefig("x.pdf")` |
| 屏幕预览 | PNG 150dpi | 快速看效果用 |

**Word 里不要用 SVG**（python-docx 支持有限）；要矢量就转 EMF，或者直接 300dpi PNG。

---

## 五、和 `pf chart` 的分工

| 需求 | 用什么 |
|---|---|
| 标准七种图型（柱/哑铃/斜率/甘特/环形/热力/框架） | `pf chart`，一条命令出图 |
| 配色家族统一（一篇内多图） | `pf chart` 的配色家族机制 |
| 需要多子图 a/b/c、误差棒、显著性标注、散点拟合 | **本文件**，手写 matplotlib |
| 需要投稿级矢量输出 | **本文件** |
| 快速出图看效果 | `pf chart --demo` |

**建议**：先用 `pf chart` 出，不满意再手写 matplotlib 调。别一上来就手写，浪费时间。

---

## 六、检查清单

出图后逐条看：

- [ ] 配色不是 matplotlib 默认色
- [ ] 中文字体正常（不是超细线）
- [ ] 去掉了上边框和右边框
- [ ] 字号在 Word/PPT 里能看清（缩到 12cm 宽后仍可读）
- [ ] 数值标签有白色描边（防止压住网格线看不清）
- [ ] 多子图有 a/b/c 标注
- [ ] 误差棒/显著性标注有说明
- [ ] 导出 300dpi PNG 或矢量
- [ ] 图号、图题、数据来源都写全
