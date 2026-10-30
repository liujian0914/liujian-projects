#!/usr/bin/env python3
"""分析大挑案例 PPT/计划书的视觉风格：配色、版式、留白、图片密度。

用法：python analyze_visual_style.py <抽帧目录> <输出md>
"""
import sys
import json
import pathlib
from collections import Counter

import numpy as np
from PIL import Image


def rgb_to_hex(rgb):
    return "#%02X%02X%02X" % tuple(int(c) for c in rgb)


def analyze_image(path: pathlib.Path) -> dict:
    im = Image.open(path).convert("RGB")
    w, h = im.size
    # 缩小加速
    scale = max(1, max(w, h) // 400)
    im_small = im.resize((max(1, w // scale), max(1, h // scale)))
    arr = np.asarray(im_small, dtype=np.uint8).reshape(-1, 3)

    # 量化到 16 级，统计主色
    q = (arr // 16) * 16
    packed = q[:, 0].astype(np.uint32) << 16 | q[:, 1].astype(np.uint32) << 8 | q[:, 2].astype(np.uint32)
    uniq, counts = np.unique(packed, return_counts=True)
    order = np.argsort(-counts)
    total = counts.sum()
    top = []
    for idx in order[:8]:
        p = int(uniq[idx])
        rgb = ((p >> 16) & 0xFF, (p >> 8) & 0xFF, p & 0xFF)
        top.append({"hex": rgb_to_hex(rgb), "pct": round(float(counts[idx]) / total * 100, 1)})

    # 明度分布
    gray = arr.mean(axis=1)
    bright_ratio = float((gray > 200).sum()) / len(gray) * 100   # 白/浅色占比
    dark_ratio = float((gray < 60).sum()) / len(gray) * 100      # 深色占比

    # 饱和度（判断是鲜艳还是素雅）
    mx = arr.max(axis=1).astype(np.float32)
    mn = arr.min(axis=1).astype(np.float32)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0)
    sat_mean = float(sat.mean()) * 100

    # 边缘密度（近似判断信息密度/是否整页图）
    g = np.asarray(im_small.convert("L"), dtype=np.float32)
    dx = np.abs(np.diff(g, axis=1)).mean()
    dy = np.abs(np.diff(g, axis=0)).mean()
    edge = float(dx + dy)

    return {
        "file": path.name,
        "size": f"{w}x{h}",
        "top_colors": top,
        "bright_pct": round(bright_ratio, 1),
        "dark_pct": round(dark_ratio, 1),
        "saturation": round(sat_mean, 1),
        "edge_density": round(edge, 2),
    }


def classify(a: dict) -> str:
    """粗分类视觉风格。"""
    s = a["saturation"]
    b = a["bright_pct"]
    d = a["dark_pct"]
    if b > 55 and s < 18:
        return "白底简约"
    if d > 45:
        return "深色/实景压暗"
    if s > 28:
        return "鲜艳主题色"
    if b > 40:
        return "浅色留白"
    return "实景/复杂背景"


def main():
    indir = pathlib.Path(sys.argv[1])
    outmd = pathlib.Path(sys.argv[2])
    files = sorted(indir.glob("*.png"))
    # 只要单页帧，不要拼图
    files = [f for f in files if not f.name.startswith("SHEET_")]

    results = []
    for f in files:
        try:
            a = analyze_image(f)
            a["style"] = classify(a)
            results.append(a)
        except Exception as e:
            print(f"[ERR] {f.name}: {e}")

    # 汇总
    style_cnt = Counter(r["style"] for r in results)
    lines = ["# 大挑案例视觉风格量化分析", "",
             f"样本：{len(results)} 张 PPT 页面", ""]

    lines += ["## 一、风格分布", "", "| 风格 | 页数 | 占比 |", "|---|---|---|"]
    for s, c in style_cnt.most_common():
        lines.append(f"| {s} | {c} | {c/max(len(results),1)*100:.0f}% |")
    lines.append("")

    # 全局配色统计
    all_colors = Counter()
    for r in results:
        for c in r["top_colors"][:4]:
            all_colors[c["hex"]] += 1
    lines += ["## 二、高频主色（跨页面出现）", "", "| 色值 | 出现页数 |", "|---|---|"]
    for hexv, cnt in all_colors.most_common(20):
        lines.append(f"| `{hexv}` | {cnt} |")
    lines.append("")

    # 指标
    if results:
        avg_b = sum(r["bright_pct"] for r in results) / len(results)
        avg_s = sum(r["saturation"] for r in results) / len(results)
        avg_e = sum(r["edge_density"] for r in results) / len(results)
        lines += ["## 三、整体指标", "",
                  f"- 平均浅色占比：**{avg_b:.1f}%**（越高越偏白底）",
                  f"- 平均饱和度：**{avg_s:.1f}%**（越高越鲜艳）",
                  f"- 平均边缘密度：**{avg_e:.2f}**（越高信息越密）",
                  ""]

    lines += ["## 四、逐页明细", "", "| 页面 | 风格 | 浅色% | 深色% | 饱和% | 主色 |", "|---|---|---|---|---|---|"]
    for r in results:
        cols = " ".join(f"`{c['hex']}`" for c in r["top_colors"][:3])
        lines.append(f"| {r['file'][:34]} | {r['style']} | {r['bright_pct']} | {r['dark_pct']} | {r['saturation']} | {cols} |")

    outmd.write_text("\n".join(lines), encoding="utf-8")
    (outmd.parent / "visual_style_raw.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"写入 {outmd}，{len(results)} 页")
    print("\n风格分布:")
    for s, c in style_cnt.most_common():
        print(f"  {c:3d}  {s}")


if __name__ == "__main__":
    main()
