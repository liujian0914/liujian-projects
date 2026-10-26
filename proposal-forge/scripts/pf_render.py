#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
proposal-forge / pf_render.py
=============================
申报书配图的生成与运维库。

两类图，两套做法：
  数据图 —— matplotlib 出矢量级 PNG（dpi=300），中文用系统黑体族；
  示意图 —— 用同一个 pf_render 的框线工具画，保证整篇风格一致。

图像运维：HSV 配色家族分化、透明压白底、横排拼接、改图上的字。

依赖：matplotlib、numpy、Pillow
"""

from __future__ import annotations

import colorsys
import os
import re
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ---------------------------------------------------------------- 字体

FONT_CANDIDATES = [
    (os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "msyh.ttc"), 0),
    (os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "msyhbd.ttc"), 0),
    (os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "simhei.ttf"), 0),
    (os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "simsun.ttc"), 0),
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 0),
    ("/System/Library/Fonts/PingFang.ttc", 0),
]

# 一套低饱和、适合打印的学术配色（避免默认 tab10 的花哨感）
PALETTE = {
    "navy": "#1f3a5f",
    "teal": "#2c6e6b",
    "clay": "#8c5a3c",
    "sand": "#c9a76c",
    "plum": "#6b4463",
    "sage": "#5c7f5c",
    "slate": "#4a5568",
    "rose": "#a05a6b",
}
FAMILIES = {
    "teal": ["#1f4e4a", "#2c6e6b", "#4f918c", "#7fb5b0", "#b6d6d2"],
    "clay": ["#5e3524", "#8c5a3c", "#b07a58", "#cfa184", "#e6c8b3"],
    "navy": ["#16283f", "#1f3a5f", "#3a5a80", "#6b88a8", "#a8bdd1"],
    "plum": ["#43263d", "#6b4463", "#8f6486", "#b28fa9", "#d3bccd"],
    "sage": ["#33482f", "#5c7f5c", "#7fa07f", "#a5c0a5", "#c8dcc8"],
    "rose": ["#6b2f3d", "#a05a6b", "#bd7f8e", "#d4a5b1", "#e8c6cf"],
    "gray": ["#2f3437", "#4a5568", "#6f7a86", "#98a2ac", "#c4cbd2"],
}


def find_cn_font():
    """返回可用的中文字体路径；找不到返回 None。

    注意：不要用 NotoSansSC-VF.ttf（可变字体），matplotlib 只注册到
    weight 100，出来的图细到没法看。用注册了 400/700 的 msyh.ttc。
    """
    for p, idx in FONT_CANDIDATES:
        if os.path.exists(p):
            return p
    return None


def setup_cn_font(save_json=None):
    """配置 matplotlib 中文字体，返回实际使用的字体名。"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    path = find_cn_font()
    name = "sans-serif"
    if path:
        try:
            font_manager.fontManager.addfont(path)
            name = font_manager.FontProperties(fname=path).get_name()
        except Exception:
            name = "Microsoft YaHei"
        plt.rcParams["font.family"] = [name, "sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 120
    plt.rcParams["savefig.dpi"] = 300
    plt.rcParams["savefig.bbox"] = "tight"
    plt.rcParams["axes.edgecolor"] = "#333333"
    plt.rcParams["axes.linewidth"] = 0.8
    plt.rcParams["font.size"] = 9
    plt.rcParams["axes.titlesize"] = 10.5
    plt.rcParams["axes.labelsize"] = 9
    plt.rcParams["xtick.labelsize"] = 8.5
    plt.rcParams["ytick.labelsize"] = 8.5
    plt.rcParams["legend.fontsize"] = 8.5
    plt.rcParams["axes.spines.top"] = False
    plt.rcParams["axes.spines.right"] = False
    plt.rcParams["grid.color"] = "#d9d9d9"
    plt.rcParams["grid.linestyle"] = "--"
    plt.rcParams["grid.linewidth"] = 0.6
    if save_json:
        Path(save_json).write_text(
            '{"font_path": %r, "font_name": %r}' % (path, name), encoding="utf-8")
    return name


def _save(fig, out):
    out = str(out)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, facecolor="white")
    import matplotlib.pyplot as plt
    plt.close(fig)
    return out


def _text_fx():
    """数值标签的白色描边。

    申报书里的图会被缩到 12cm 宽再看，细标签压在网格线或色块上就糊了，
    加 2px 白描边是成本最低的可读性修复。
    """
    from matplotlib import patheffects as pe
    return [pe.withStroke(linewidth=2.2, foreground="white")]


# ---------------------------------------------------------------- 数据处理

def largest_remainder(values, total=100.0):
    """最大余数法把一组数配成整数百分比且合计恰好等于 total。

    直接四舍五入会出现 46+17+16+9+6+6=100 之外的 101%，
    环形图/饼图上标百分比必须用这个。
    """
    s = float(sum(values))
    if s <= 0:
        return [0] * len(values)
    raw = [v / s * total for v in values]
    floor = [int(math.floor(x)) for x in raw]
    rest = int(round(total - sum(floor)))
    order = sorted(range(len(raw)), key=lambda i: raw[i] - floor[i], reverse=True)
    for i in order[:rest]:
        floor[i] += 1
    return floor


def _setup_ax(ax, ygrid=True, xgrid=False):
    if ygrid:
        ax.yaxis.grid(True, zorder=0)
        ax.set_axisbelow(True)
    if xgrid:
        ax.xaxis.grid(True, zorder=0)
        ax.set_axisbelow(True)


# ---------------------------------------------------------------- 数据图

def chart_grouped_bar(out, categories, series, ylabel="", figsize=(6.3, 3.4),
                      family="teal", value_fmt="{:.1f}", ref_line=None,
                      legend_outside=True, ylim=None):
    """分组柱状图。series = [(名称, [值...]), ...]"""
    setup_cn_font()
    import matplotlib.pyplot as plt

    colors = FAMILIES.get(family, FAMILIES["teal"])
    n = len(series)
    x = np.arange(len(categories))
    w = 0.8 / max(n, 1) * 0.92
    fig, ax = plt.subplots(figsize=figsize)
    for i, (name, vals) in enumerate(series):
        off = (i - (n - 1) / 2) * w
        bars = ax.bar(x + off, vals, w, label=name,
                      color=colors[min(i * 2 + 1, len(colors) - 1)],
                      edgecolor="white", linewidth=0.6, zorder=3)
        for b, v in zip(bars, vals):
            ax.annotate(value_fmt.format(v), (b.get_x() + b.get_width() / 2, b.get_height()),
                        ha="center", va="bottom", fontsize=7.2, xytext=(0, 2),
                        textcoords="offset points", path_effects=_text_fx())
    ax.set_xticks(x)
    ax.set_xticklabels(categories)
    ax.set_ylabel(ylabel)
    _setup_ax(ax)
    if ylim:
        ax.set_ylim(*ylim)
    if ref_line is not None:
        ax.axhline(ref_line, color="#999999", lw=0.8, ls=(0, (4, 3)), zorder=2)
    if legend_outside and n > 1:
        ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.02), ncol=n,
                  frameon=False, handlelength=1.2, columnspacing=1.4)
    return _save(fig, out)


def chart_dumbbell(out, categories, start, end, start_label="起点", end_label="终点",
                   xlabel="", figsize=(6.3, 3.2), family="clay", value_fmt="{:.1f}"):
    """哑铃图：一眼看出两组值的落差，比双柱更干净。"""
    setup_cn_font()
    import matplotlib.pyplot as plt

    c = FAMILIES.get(family, FAMILIES["clay"])
    y = np.arange(len(categories))[::-1]
    fig, ax = plt.subplots(figsize=figsize)
    for yi, a, b in zip(y, start, end):
        ax.plot([a, b], [yi, yi], color="#c9c9c9", lw=2.2, zorder=2, solid_capstyle="round")
    ax.scatter(start, y, s=52, color=c[1], label=start_label, zorder=3, edgecolor="white", linewidth=0.8)
    ax.scatter(end, y, s=52, color=c[4], label=end_label, zorder=3, edgecolor="white", linewidth=0.8)
    for yi, a, b in zip(y, start, end):
        ax.annotate(value_fmt.format(a), (a, yi), xytext=(-8, 0), textcoords="offset points",
                    va="center", ha="right", fontsize=7.2, color="#444444",
                    path_effects=_text_fx())
        ax.annotate(value_fmt.format(b), (b, yi), xytext=(8, 0), textcoords="offset points",
                    va="center", ha="left", fontsize=7.2, color="#444444",
                    path_effects=_text_fx())
    ax.set_yticks(y)
    ax.set_yticklabels(categories)
    ax.set_xlabel(xlabel)
    ax.set_ylim(-0.6, len(categories) - 0.4)
    _setup_ax(ax, ygrid=False, xgrid=True)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.02), ncol=2, frameon=False)
    return _save(fig, out)


def chart_gantt(out, tasks, months, figsize=(6.3, 3.2), family="plum",
                xlabel="项目执行月份", note_fmt="第 {m} 月：{note}"):
    """里程碑式甘特图：条形 + 圆点 + 右侧注释。

    tasks = [(任务名, 起始月, 结束月, 里程碑月, 注释), ...]
    """
    setup_cn_font()
    import matplotlib.pyplot as plt

    c = FAMILIES.get(family, FAMILIES["plum"])
    y = np.arange(len(tasks))[::-1]
    fig, ax = plt.subplots(figsize=figsize)
    for yi, (name, s, e, mile, note) in zip(y, tasks):
        ax.barh(yi, e - s + 1, left=s - 1, height=0.42, color=c[4],
                alpha=0.85, zorder=2, edgecolor="white")
        ax.scatter([mile], [yi], s=58, color=c[0], zorder=5, edgecolor="white", linewidth=0.8)
        if note:
            ax.annotate(note_fmt.format(m=mile, note=note), (mile, yi),
                        xytext=(13, 0), textcoords="offset points",
                        va="center", ha="left", fontsize=7.2, color="#333333",
                        zorder=6, path_effects=_text_fx())
    ax.set_yticks(y)
    ax.set_yticklabels([t[0] for t in tasks])
    ax.set_xlim(0, months)
    ax.set_xlabel(xlabel)
    ax.set_ylim(-0.6, len(tasks) - 0.4)
    _setup_ax(ax, ygrid=False, xgrid=True)
    return _save(fig, out)


def chart_donut(out, labels, values, figsize=(4.6, 4.2), family="sage",
                center_text=None, show_counts=True):
    """环形图（样本结构），百分比自动用最大余数法对齐到 100%。"""
    setup_cn_font()
    import matplotlib.pyplot as plt

    colors = FAMILIES.get(family, FAMILIES["sage"])
    total = sum(values)
    pct = largest_remainder(values, 100)
    fig, ax = plt.subplots(figsize=figsize)
    wedges, _ = ax.pie(values, colors=[colors[i % len(colors)] for i in range(len(values))],
                       startangle=90, counterclock=False,
                       wedgeprops=dict(width=0.36, edgecolor="white", linewidth=1.4))
    # 标签一律放环外并带引线：压在色块上时浅色块根本看不清，缩到 12cm 更糊
    for w, lab, p in zip(wedges, labels, pct):
        ang = math.radians((w.theta2 + w.theta1) / 2)
        span = abs(w.theta2 - w.theta1)
        r_lab = 1.30 if span >= 18 else 1.42
        x, y = r_lab * math.cos(ang), r_lab * math.sin(ang)
        ax.annotate("%s %d%%" % (lab, p),
                    xy=(1.0 * math.cos(ang), 1.0 * math.sin(ang)),
                    xytext=(x, y), ha="center", va="center", fontsize=7.6,
                    color="#333333",
                    arrowprops=dict(arrowstyle="-", color="#bdbdbd", lw=0.6,
                                    shrinkA=0, shrinkB=1))
    if center_text:
        ax.text(0, 0.10, center_text, ha="center", va="center", fontsize=15, color="#222222")
        ax.text(0, -0.16, "合计 %d 份" % total, ha="center", va="center", fontsize=8, color="#777777")
    ax.set_aspect("equal")
    ax.set_xlim(-1.62, 1.62)
    ax.set_ylim(-1.62, 1.62)
    return _save(fig, out)


def chart_heatmap(out, row_labels, col_labels, matrix, figsize=(5.4, 3.4),
                  family="navy", vmin=None, vmax=None, cbar_label=""):
    """热力图。x 轴标签挤时在标签内换行，不是缩小字号。"""
    setup_cn_font()
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=figsize)
    m = np.array(matrix, dtype=float)
    im = ax.imshow(m, cmap="BuGn", vmin=vmin, vmax=vmax, aspect="auto")
    ax.set_xticks(range(len(col_labels)))
    ax.set_xticklabels(col_labels, fontsize=8)
    ax.set_yticks(range(len(row_labels)))
    ax.set_yticklabels(row_labels)
    for i in range(m.shape[0]):
        for j in range(m.shape[1]):
            v = m[i, j]
            mid = (np.nanmin(m) + np.nanmax(m)) / 2 if vmin is None else (vmin + vmax) / 2
            ax.text(j, i, "%.1f" % v, ha="center", va="center", fontsize=7.2,
                    color="white" if v > mid else "#222222")
    ax.set_xticks(np.arange(-.5, len(col_labels), 1), minor=True)
    ax.set_yticks(np.arange(-.5, len(row_labels), 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=1.2, linestyle="-")
    ax.tick_params(which="minor", length=0)
    if cbar_label:
        cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
        cb.set_label(cbar_label, fontsize=8)
        cb.ax.tick_params(labelsize=7)
    return _save(fig, out)


def chart_slope(out, points_left, points_right, left_label="介入前", right_label="介入后",
                figsize=(5.2, 3.2), family="teal", ylabel=""):
    """斜率图：同一批对象的前后变化，适合"断裂→贯通""内测前后"这类叙事。"""
    setup_cn_font()
    import matplotlib.pyplot as plt

    c = FAMILIES.get(family, FAMILIES["teal"])
    fig, ax = plt.subplots(figsize=figsize)
    names = list(points_left.keys())
    for i, n in enumerate(names):
        a, b = points_left[n], points_right[n]
        ax.plot([0, 1], [a, b], marker="o", ms=5, lw=1.6,
                color=c[min(i + 1, len(c) - 1)], label=n, alpha=0.92)
        ax.annotate("%.1f" % a, (0, a), xytext=(-8, 0), textcoords="offset points",
                    ha="right", va="center", fontsize=7, path_effects=_text_fx())
        ax.annotate("%.1f" % b, (1, b), xytext=(8, 0), textcoords="offset points",
                    ha="left", va="center", fontsize=7, path_effects=_text_fx())
    ax.set_xlim(-0.28, 1.28)
    ax.set_xticks([0, 1])
    ax.set_xticklabels([left_label, right_label])
    ax.set_ylabel(ylabel)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    _setup_ax(ax)
    ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), frameon=False)
    return _save(fig, out)


def chart_framework(out, layers, figsize=(6.3, 4.0), family="navy", arrow_label=None):
    """分层框架图：每层若干方块，层间竖直箭头。

    layers = [(层名, [块名...]), ...]  自上而下
    连接线一律直角/直线 —— 弧形在窄图里必压字。
    """
    setup_cn_font()
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

    c = FAMILIES.get(family, FAMILIES["navy"])
    n = len(layers)
    box_h = 1.55 if n <= 3 else (1.22 if n <= 5 else 0.98)
    gap = 0.85
    total_h = n * box_h + (n - 1) * gap
    top = 5 + total_h / 2
    left, right = 1.05, 9.92
    avail = right - left

    fig, ax = plt.subplots(figsize=figsize)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")

    layer_geo = []
    for li, (lname, blocks) in enumerate(layers):
        y0 = top - box_h - li * (box_h + gap)
        k = max(len(blocks), 1)
        gx = 0.30 if k > 1 else 0
        bw = min(2.35, (avail - gx * (k - 1)) / k)
        tw = bw * k + gx * (k - 1)
        x0 = left + (avail - tw) / 2
        ax.text(0.08, y0 + box_h / 2, lname, ha="left", va="center",
                fontsize=7.8, color=c[1])
        for bi, b in enumerate(blocks):
            bx = x0 + bi * (bw + gx)
            ax.add_patch(FancyBboxPatch((bx, y0), bw, box_h,
                                        boxstyle="round,pad=0.02,rounding_size=0.10",
                                        linewidth=0.8, edgecolor=c[2],
                                        facecolor=c[4], zorder=2))
            max_chars = max(int(bw / 0.185), 4)
            txt = b if len(b) <= max_chars else "\n".join(
                b[i:i + max_chars] for i in range(0, len(b), max_chars))
            ax.text(bx + bw / 2, y0 + box_h / 2, txt, ha="center", va="center",
                    fontsize=7.6, color="#1a1a1a", zorder=3, linespacing=1.35)
        layer_geo.append(y0)

    # 层间箭头只落在空白带里，绝不穿过方块 —— 弧形连接线在窄图里必压字
    for i in range(n - 1):
        ax.annotate("", xy=(5.0, layer_geo[i + 1] + box_h), xytext=(5.0, layer_geo[i]),
                    arrowprops=dict(arrowstyle="-|>", color=c[1], lw=1.0,
                                    shrinkA=0, shrinkB=0), zorder=1)
    if arrow_label:
        ax.text(5.12, (layer_geo[0] + layer_geo[-1] + box_h) / 2, arrow_label,
                rotation=90, fontsize=7, color=c[1], va="center")
    return _save(fig, out)


# ---------------------------------------------------------------- 图像运维

def white_bg(src, dst=None, color=(255, 255, 255)):
    """透明 PNG 压白底。

    Word / WPS 不做 alpha 合成，透明背景插进去会渲染成黑块。
    """
    im = Image.open(src)
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, color)
        bg.paste(im, (0, 0), im)
        im = bg
    else:
        im = im.convert("RGB")
    dst = dst or str(Path(src).with_name(Path(src).stem + "_white.png"))
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    im.save(dst)
    return dst


def hstack(srcs, dst, gap=24, bg=(255, 255, 255), max_h=None):
    """多张图横排拼成一张。

    两张竖图分别插入会把后一张的题注挤到下一页（WPS 不遵守 keepNext），
    合成单图单题注是稳定解法。
    """
    ims = []
    for s in srcs:
        im = Image.open(s)
        im = im.convert("RGBA") if im.mode != "RGB" else im
        if max_h and im.height > max_h:
            w = int(im.width * max_h / im.height)
            im = im.resize((w, max_h), Image.LANCZOS)
        ims.append(im)
    H = max(i.height for i in ims)
    W = sum(i.width for i in ims) + gap * (len(ims) - 1)
    canvas = Image.new("RGB", (W, H), bg)
    x = 0
    for im in ims:
        if im.mode == "RGBA":
            y = (H - im.height) // 2
            canvas.paste(im.convert("RGB"), (x, y), im)
        else:
            canvas.paste(im, (x, (H - im.height) // 2))
        x += im.width + gap
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    canvas.save(dst)
    return dst


def recolor_family(src, dst, anchors, targets, sat_boost=0.14, sat_min=0.030, val_min=0.04):
    """HSV 分区换色，做"配色家族"分化。

    anchors / targets 是色相角度列表（0–360），长度一致，做环形分段线性映射。

    关键：淡色填充的饱和度往往只有 0.04，只换色相根本看不出来，
    必须同时把饱和度抬到 sat_boost 以上。
    白底、黑字、灰线靠 sat/val 阈值排除，不受影响。
    """
    im = Image.open(src)
    has_alpha = im.mode in ("RGBA", "LA")
    rgba = im.convert("RGBA")
    arr = np.array(rgba).astype(np.float32) / 255.0
    rgb, alpha = arr[..., :3], arr[..., 3]
    mx = rgb.max(-1)
    mn = rgb.min(-1)
    d = mx - mn
    s = np.where(mx > 0, d / np.maximum(mx, 1e-6), 0)
    v = mx
    h = np.zeros_like(mx)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    m = (d > 1e-6)
    idx = (mx == r) & m
    h[idx] = ((g[idx] - b[idx]) / d[idx]) % 6
    idx = (mx == g) & m
    h[idx] = ((b[idx] - r[idx]) / d[idx]) + 2
    idx = (mx == b) & m
    h[idx] = ((r[idx] - g[idx]) / d[idx]) + 4
    h = (h * 60.0) % 360.0

    # 环形分段线性映射
    an = sorted(a % 360 for a in anchors)
    tg = [t for a, t in sorted(zip([a % 360 for a in anchors], targets))]
    an2 = an + [an[0] + 360]
    tg2 = tg + [tg[0]]
    hh = h.copy()
    nh = h.copy()
    for i in range(len(an2) - 1):
        lo, hi = an2[i], an2[i + 1]
        mask = (hh >= lo) & (hh < hi)
        if not mask.any():
            continue
        t = (hh[mask] - lo) / max(hi - lo, 1e-6)
        nh[mask] = (tg2[i] + t * (tg2[i + 1] - tg2[i])) % 360
    wrap = hh >= an2[-2]
    if wrap.any():
        t = (hh[wrap] - an2[-2]) / max(360 - an2[-2] + an2[0], 1e-6)
        nh[wrap] = (tg2[-2] + t * (tg2[-1] - tg2[-2])) % 360

    # 只动有饱和度的像素
    mask = (s >= sat_min) & (v >= val_min)
    nh = np.where(mask, nh, h)
    ns = np.where(mask, np.maximum(s, sat_boost), s)

    # HSV → RGB（向量化）
    nh6 = nh / 60.0
    i6 = np.floor(nh6).astype(int) % 6
    f = nh6 - np.floor(nh6)
    p = v * (1 - ns)
    q = v * (1 - ns * f)
    t_ = v * (1 - ns * (1 - f))
    out_rgb = np.zeros_like(rgb)
    conds = [i6 == 0, i6 == 1, i6 == 2, i6 == 3, i6 == 4, i6 == 5]
    vals = [(v, t_, p), (q, v, p), (p, v, t_), (p, q, v), (t_, p, v), (v, p, q)]
    for cond, (R, G, B) in zip(conds, vals):
        out_rgb[cond] = np.stack([R[cond], G[cond], B[cond]], axis=-1)

    out = np.concatenate([np.clip(out_rgb, 0, 1), alpha[..., None]], axis=-1)
    img = Image.fromarray((out * 255).astype(np.uint8), "RGBA")
    if not has_alpha:
        img = img.convert("RGB")
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    img.save(dst)
    return dst


def dominant_hues(src, top=6, sat_min=0.05):
    """统计一张图里占比最高的几个色相（用来反推 recolor 的锚点）。"""
    im = Image.open(src).convert("RGB")
    im.thumbnail((480, 480))
    arr = np.array(im).astype(np.float32) / 255.0
    rgb = arr.reshape(-1, 3)
    mx = rgb.max(1)
    mn = rgb.min(1)
    d = mx - mn
    s = np.where(mx > 0, d / np.maximum(mx, 1e-6), 0)
    keep = (s > sat_min) & (mx > 0.1)
    if keep.sum() == 0:
        return []
    r, g, b = rgb[keep, 0], rgb[keep, 1], rgb[keep, 2]
    mxk, mnk, dk = mx[keep], mn[keep], d[keep]
    h = np.zeros(len(r))
    m = dk > 1e-6
    i = (mxk == r) & m
    h[i] = ((g[i] - b[i]) / dk[i]) % 6
    i = (mxk == g) & m
    h[i] = ((b[i] - r[i]) / dk[i]) + 2
    i = (mxk == b) & m
    h[i] = ((r[i] - g[i]) / dk[i]) + 4
    h = (h * 60) % 360
    bins = np.histogram(h, bins=36, range=(0, 360))[0]
    order = np.argsort(bins)[::-1][:top]
    total = bins.sum()
    return [{"hue": int(i * 10 + 5), "share": round(float(bins[i] / total), 3)}
            for i in order if bins[i] > 0]


def retext_image(src, dst, box, new_text, color=None, font_path=None, bold=False,
                 letter_spacing=None):
    """擦掉图上指定区域的文字并重绘同风格新字。

    box = (x0, y0, x1, y1)：待替换文字的紧包围盒。
    做法：用文字上下方的像素做垂直线性插值还原背景（纯色/平滑渐变背景足够干净），
    再按原墨迹高度与颜色重绘；字数变化时用字间距分摊，不改字号。
    """
    im = Image.open(src).convert("RGB")
    x0, y0, x1, y1 = [int(v) for v in box]
    arr = np.array(im).astype(np.float32)

    # 反解原字：墨迹高度、颜色（中位数，不用均值）、水平中心
    region = arr[y0:y1, x0:x1]
    dark = region.mean(2) < 150
    ys, xs = np.where(dark)
    if len(ys) == 0:
        raise SystemExit("指定区域里没有暗像素，检查 box 是否对准文字")
    ink_top, ink_bot = ys.min(), ys.max()
    ink_h = ink_bot - ink_top + 1
    src_color = tuple(int(v) for v in np.median(region[dark], axis=0))

    # 背景还原：逐列取文字上方与下方像素做垂直插值
    top_pad = max(2, int(ink_h * 0.6))
    bot_pad = max(2, int(ink_h * 0.6))
    ty = max(y0 - top_pad, 0)
    by = min(y1 + bot_pad, arr.shape[0] - 1)
    fill = arr.copy()
    for x in range(x0, x1):
        c_top = arr[ty, x]
        c_bot = arr[by, x]
        span = max(by - ty, 1)
        for y in range(y0, y1):
            t = (y - ty) / span
            fill[y, x] = c_top * (1 - t) + c_bot * t
    base = Image.fromarray(fill.astype(np.uint8))

    # 用同尺寸字体渲染新字
    size = max(int(ink_h * 1.34), 8)
    try:
        font = ImageFont.truetype(font_path or find_cn_font(), size)
    except Exception:
        font = ImageFont.load_default()
    layer = Image.new("L", im.size, 0)
    d = ImageDraw.Draw(layer)
    total_w = d.textlength(new_text, font=font)
    target_w = (x1 - x0)
    if letter_spacing is None:
        letter_spacing = 0
        if len(new_text) > 1 and abs(total_w - target_w) > 2:
            letter_spacing = (target_w - total_w) / (len(new_text) - 1)
    cx = (x0 + x1) / 2
    x = cx - (total_w + letter_spacing * (len(new_text) - 1)) / 2
    baseline_y = y0 + ink_top - int(ink_h * 0.18)
    for ch in new_text:
        d.text((x, baseline_y), ch, font=font, fill=255)
        x += d.textlength(ch, font=font) + letter_spacing
    mask = layer.filter(ImageFilter.GaussianBlur(0.4))
    paint = Image.new("RGB", im.size, color or src_color)
    out = Image.composite(paint, base, mask)
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    out.save(dst)
    return {"dst": dst, "ink_height": int(ink_h), "color": src_color,
            "letter_spacing": round(float(letter_spacing), 2)}


def info(src):
    """图片基本信息（尺寸/模式/主要色相）。"""
    im = Image.open(src)
    return {"path": src, "width": im.width, "height": im.height,
            "mode": im.mode, "hues": dominant_hues(src)}
