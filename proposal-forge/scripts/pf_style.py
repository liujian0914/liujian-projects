#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
proposal-forge / pf_style.py
============================
中文文本「AI 味」检测器（学术 / 申报书文体专用）。

定位
----
申报书、申请书、研究报告属于**正式事实性文本**。去 AI 味不是把文字改口语，
而是删掉那些"看起来很努力、其实没信息"的写法：

  · 用铺垫代替陈述（"值得注意的是…""随着…的不断发展"）
  · 用拔高代替论证（"深刻变革""全方位赋能""范式重构"）
  · 用排比代替推进（三句同构、四字格堆叠）
  · 用空泛归因代替出处（"业内普遍认为"却不说是谁）
  · 用格式代替逻辑（满屏破折号、粗体、项目符号）

它检查的是**可数的痕迹**，不评判内容好坏。分数高不等于文章差，
但大概率读起来像机器写的。

规则来源与致谢
--------------
思路参考 blader/humanizer（MIT）与 op7418/Humanizer-zh（MIT），
按中文学术写作的实际习惯重写词表与判据，未沿用其口语化主张。

用法
----
    from pf_style import analyze, format_markdown
    rep = analyze(text, mode="academic")
    print(format_markdown(rep))
"""

from __future__ import annotations

import re
from collections import Counter

# ---------------------------------------------------------------- 词表

RULES = [
    # A 铺垫代替陈述
    ("A1", "铺垫开场", 3,
     r"^(值得注意的是|需要指出的是|不难发现|众所周知|毋庸置疑|不言而喻|总的来说|综上所述)",
     "删掉铺垫，直接给结论。首句就写事实或判断。"),
    ("A2", "时代背景套话", 4,
     r"(随着[^。；]{2,20}(的)?(不断|快速|持续)?(发展|推进|深入|普及)|在[^。；]{2,15}的大背景下|进入新时代以来)",
     "除非要引出具体年份或政策，否则删掉。背景段的价值在于给出可核对的时点与文件。"),
    ("A3", "过渡性废话", 2,
     r"(由此可见|可以看出|换言之|也就是说|从这个意义上讲|正如我们所知)",
     "一段里最多留一个，其余删。"),
    ("A4", "动机式自述", 3,
     r"(为了更好地|旨在通过|试图从|力求为|致力于打造)",
     "改成「做了什么 + 得到什么结果」的直陈句。"),

    # B 公式化节奏
    ("B1", "四项以上并列", 2,
     r"(?:[^，。；：、\n]{1,14}、){3,}[^，。；：、\n]{1,14}",
     "数据分类的并列属于正常；但句式层面的四连排读起来像清单，挑两个最有力的，其余改成主谓句。"),
    ("B2", "不仅而且连锁", 2,
     r"(不仅[^。；]{2,30}(而且|更|还)|既[^。；]{2,20}又[^。；]{2,20}|一方面[^。；]{2,40}另一方面)",
     "这种结构一篇里出现三次以上就成模板。改成因果或让步关系，信息量更大。"),
    ("B3", "递进虚词堆叠", 2,
     r"(进一步(推动|促进|提升|深化)|持续(赋能|助力|加码)|不断(优化|完善|升级))",
     "「进一步」若后面没有具体数字或对象，等于没说。"),
    ("B4", "同构句重复", 3,
     None,  # 用结构相似度检测，见 _check_parallel
     "相邻段落开头用同一句式（本项目…／平台…／通过…）会显得套模板。"),

    # C 拔高借权威
    ("C1", "空洞拔高词", 3,
     r"(深刻变革|深远影响|重大而深远|历史性机遇|全新范式|范式重构|颠覆性|革命性|跨越式|质的飞跃|新高度|新格局)",
     "换成可量化的变化（提升了多少、覆盖多少户、缩短多少天）。"),
    ("C2", "商业黑话", 2,
     r"(赋能|抓手|闭环|生态位|护城河|组合拳|方法论沉淀|底层逻辑|顶层设计|颗粒度|对齐|打通|串联|沉淀)",
     "申报书里除项目名与引文外尽量换成日常动词：支持、连接、记录、核对、汇总。"),
    ("C3", "空泛归因", 4,
     r"(业内(普遍|广泛)(认为|关注)|有(研究|学者|专家)(表明|指出|认为)|相关研究显示|实践证明|数据显示(?![^。]{0,12}\d))",
     "必须点名：谁、哪年、什么样本。查不到出处就删掉这句判断。"),
    ("C4", "万能价值句", 3,
     r"(具有(重要|深远|积极)的?(意义|价值|作用)|提供了(有益|重要)的?(参考|借鉴|启示)|奠定了坚实基础)",
     "删。价值由数据与结论自己说话。"),

    # D 排版痕迹
    ("D2", "粗体标记残留", 3,
     r"\*\*[^*]+\*\*",
     "markdown 粗体没清干净。正式文档用样式，不用符号。"),
    ("D3", "项目符号过密", 2,
     r"^[\-\*•]\s",
     "整篇都是 bullet 说明没有论证。关键段落要成句成段。"),
    ("D4", "分隔线残留", 1,
     r"^\s*(---|===)\s*$",
     "删。"),

    # E 中文特有的机器腔
    ("E1", "进行+名词", 2,
     r"进行(了)?(深入)?(的)?(研究|分析|探讨|梳理|优化|提升|改进|论证)",
     "直接用动词：研究、分析、梳理。"),
    ("E2", "通过…的方式", 2,
     r"通过[^。；]{2,25}(的方式|的途径|的手段)",
     "改成「用 X 做 Y」。"),
    ("E3", "基于…的基础上", 3,
     r"基于[^。；]{2,20}的?基础上",
     "语病。二选一：「基于 X」或「在 X 的基础上」。"),
    ("E4", "被字句堆叠", 1,
     r"(被[^。；，]{2,10}，)[^。；]{0,30}(被[^。；，]{2,10}[，。])",
     "连续被动显得含糊，指出施动者。"),
    ("E5", "的的不休", 2,
     r"的[^。；，]{1,6}的[^。；，]{1,6}的",
     "三个「的」连用，拆句。"),
    ("E6", "了了不休", 2,
     r"了[^。；，]{1,8}了[^。；，]{1,8}了",
     "同上，拆句。"),
    ("E7", "虚词开头", 1,
     r"^(此外|同时|另外|并且|而且|因此|所以)[，,]",
     "连续三段都用虚词开头，说明段落之间没有真实逻辑关系。"),
]

COMPILED = [(k, label, w, re.compile(pat, re.M) if pat else None, adv)
            for k, label, w, pat, adv in RULES]


# ---------------------------------------------------------------- 统计工具

def _sentences(text):
    parts = re.split(r"(?<=[。！？；])", text)
    return [p.strip() for p in parts if len(p.strip()) > 1]


def _paragraphs(text):
    return [p.strip() for p in re.split(r"\n\s*\n|\n", text) if len(p.strip()) > 1]


def _check_parallel(paras, min_run=3):
    """相邻段落开头同构（前 4 字相同）连续出现，判为模板化。"""
    hits = []
    run = 1
    for i in range(1, len(paras)):
        a, b = paras[i - 1][:4], paras[i][:4]
        if a and a == b:
            run += 1
            if run == min_run:
                hits.append(paras[i][:40])
        else:
            run = 1
    return hits


def _length_uniformity(paras):
    """段落长度过于均匀是机器生成的典型信号（人写会忽长忽短）。"""
    lens = [len(re.sub(r"\s", "", p)) for p in paras if len(p) > 20]
    if len(lens) < 5:
        return None
    mean = sum(lens) / len(lens)
    var = sum((x - mean) ** 2 for x in lens) / len(lens)
    cv = (var ** 0.5) / mean if mean else 0
    return {"mean": round(mean, 1), "cv": round(cv, 3),
            "verdict": "过于均匀（CV<0.35）" if cv < 0.35 else "正常"}


# ---------------------------------------------------------------- 主分析

def analyze(text, mode="academic"):
    """返回检测报告字典。

    mode: academic（申报书/论文，保留正式度）| general（一般文章）
    """
    text = text.replace("\r\n", "\n")
    chars = len(re.sub(r"\s", "", text))
    sents = _sentences(text)
    paras = _paragraphs(text)
    per_k = max(chars / 1000.0, 0.1)

    findings = []
    total = 0.0
    for key, label, weight, rx, adv in COMPILED:
        if key == "B4":
            hits = _check_parallel(paras)
            n = len(hits)
        else:
            ms = rx.findall(text)
            n = len(ms)
            hits = [m if isinstance(m, str) else "".join(m) for m in ms[:5]]
        if n == 0:
            continue
        # 密度归一：每千字命中次数，避免长文被判死
        density = n / per_k
        scaled = min(density, 10) * weight * 0.5
        total += scaled
        findings.append({"code": key, "label": label, "count": n,
                         "density_per_1k": round(density, 2),
                         "weight": weight, "penalty": round(scaled, 1),
                         "samples": hits[:5], "advice": adv})

    # 破折号专项：不计分，只报位置。项目名与副标题里的「——」是规范用法，不算毛病
    dash = text.count("——")
    dash_where = []
    if dash:
        for para in paras:
            idx = para.find("——")
            if idx >= 0:
                dash_where.append(para[max(0, idx - 12):idx + 14])
    if dash:
        findings.append({"code": "D1", "label": "破折号", "count": dash,
                         "density_per_1k": round(dash / per_k, 2), "weight": 0,
                         "penalty": 0, "samples": dash_where[:5],
                         "advice": "项目名与副标题里的「——」属规范用法；正文里的注解式破折号建议整篇压到 3 处以内，改用冒号或断句。"})

    sent_len = [len(re.sub(r"\s", "", s)) for s in sents] or [0]
    uni = _length_uniformity(paras)
    if uni and uni["verdict"].startswith("过于"):
        total += 6

    score = int(max(0, min(100, 100 - total)))
    if score >= 80:
        verdict = "干净，接近人工写作"
    elif score >= 65:
        verdict = "轻度机器腔，改十几处即可"
    elif score >= 45:
        verdict = "明显机器腔，需要逐段重写开头与收尾"
    else:
        verdict = "模板感很重，建议按段落重构而不是修补"

    findings.sort(key=lambda x: -x["penalty"])
    return {
        "mode": mode,
        "chars": chars,
        "sentences": len(sents),
        "paragraphs": len(paras),
        "avg_sentence_len": round(sum(sent_len) / len(sent_len), 1),
        "long_sentences_over_60": sum(1 for x in sent_len if x > 60),
        "paragraph_uniformity": uni,
        "dash_count": dash,
        "score": score,
        "verdict": verdict,
        "findings": findings,
        "top_actions": [f["advice"] for f in findings[:5]],
    }


def format_markdown(rep):
    L = ["# 去 AI 味检测 · 得分 %d/100（%s）" % (rep["score"], rep["verdict"]), "",
         "- 字符 %d ／ 句 %d ／ 段 %d ／ 平均句长 %.1f 字"
         % (rep["chars"], rep["sentences"], rep["paragraphs"], rep["avg_sentence_len"]),
         "- 超过 60 字的长句 %d 句 ／ 破折号 %d 处"
         % (rep["long_sentences_over_60"], rep["dash_count"])]
    if rep["paragraph_uniformity"]:
        u = rep["paragraph_uniformity"]
        L.append("- 段落长度 均值 %.1f 字，离散系数 %.3f（%s）" % (u["mean"], u["cv"], u["verdict"]))
    L += ["", "## 命中项（按影响排序）", ""]
    if not rep["findings"]:
        L.append("未命中任何规则。")
    for f in rep["findings"]:
        L.append("### [%s] %s · %d 处（每千字 %.2f）"
                 % (f["code"], f["label"], f["count"], f["density_per_1k"]))
        if f["samples"]:
            for s in f["samples"][:3]:
                L.append("- 例：%s" % s.replace("\n", " ")[:60])
        L.append("- 改法：%s" % f["advice"])
        L.append("")
    L += ["## 优先做的五件事", ""]
    for i, a in enumerate(rep["top_actions"], 1):
        L.append("%d. %s" % (i, a))
    return "\n".join(L)


if __name__ == "__main__":
    import sys
    p = sys.argv[1]
    print(format_markdown(analyze(open(p, encoding="utf-8").read())))
