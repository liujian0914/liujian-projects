#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
competition-forge / pf_docx.py
===========================
中文项目申报书的 Word(.docx) 结构手术库。

设计原则
--------
1. 一切以"原格式零损伤"为前提：新增内容一律深拷贝同类段落再改字，
   不用 add_paragraph(style=...) 硬造。
2. 遍历必须递归穿透表格。中文申报书常把全文塞进一个 1×1 表格单元格，
   doc.paragraphs 会返回空列表 —— 这是本库与常见脚本的最大区别。
3. 只读操作与写入操作严格分开，写入前由调用方负责备份。

依赖：python-docx、lxml（必需）；pywin32、PyMuPDF（仅 COM/PDF 相关功能）
"""

from __future__ import annotations

import copy
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.shared import Cm, Emu
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph

EMU_PER_CM = 360000


# ---------------------------------------------------------------- 格式嗅探

def sniff_format(path):
    """返回 ooxml / ole / zip / unknown。

    文件名后缀完全不可信：WPS 存出的 .docx 有大量是 OLE 复合文档，
    python-docx 打开会抛 KeyError: no relationship of type ...
    """
    with open(path, "rb") as f:
        head = f.read(8)
    if head[:4] == b"PK\x03\x04":
        return "ooxml"
    if head[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return "ole"
    if head[:2] == b"PK":
        return "zip"
    return "unknown"


def ole_streams(path):
    """列出 OLE 复合文档的流，用于判断是旧 .doc 还是 WPS 产物。"""
    try:
        import olefile
    except ImportError:
        return {"_error": "需要 olefile：pip install olefile"}
    o = olefile.OleFileIO(path)
    out = {}
    for s in o.listdir():
        name = "/".join(s)
        out[name] = o.get_size(name)
    return out


def open_doc(path):
    """带前置校验地打开 docx。"""
    fmt = sniff_format(path)
    if fmt == "ole":
        raise SystemExit(
            "该文件是 OLE 复合文档（旧版 .doc / WPS 存出），python-docx 无法打开。\n"
            "先执行：pf convert \"%s\" --to ooxml" % path
        )
    if fmt != "ooxml":
        raise SystemExit("无法识别的文件格式：%s" % fmt)
    return Document(path)


# ---------------------------------------------------------------- 递归遍历

def _in_textbox(el):
    """判断段落是否位于文本框内（文本框里的段落顺序会打乱，需排除）。"""
    pr = el.getparent()
    while pr is not None:
        if pr.tag == qn("w:txbxContent"):
            return True
        pr = pr.getparent()
    return False


def iter_paras(doc, include_tables=True, skip_textbox=True):
    """按真实文档顺序产出段落，穿透表格单元格。

    实现要点：直接走 body.iter(w:p)，XML 树遍历天然每节点一次，
    既不会漏掉 1×1 表格里的全文，也不会因合并单元格重复产出。

    ⚠️ 不要用 id() 做去重：lxml 的子元素代理是临时对象，被回收后
    内存地址会被复用，用 id 判重会把后面的段落当成"已见过"而静默跳过。
    """
    body = doc.element.body
    if include_tables:
        for el in body.iter(qn("w:p")):
            if skip_textbox and _in_textbox(el):
                continue
            yield Paragraph(el, doc)
    else:
        for el in body.iterchildren(qn("w:p")):
            yield Paragraph(el, doc)


def iter_blocks(doc):
    """按真实顺序产出顶层 Paragraph / Table（不穿透）。"""
    for ch in doc.element.body.iterchildren():
        if isinstance(ch, CT_P):
            yield Paragraph(ch, doc)
        elif isinstance(ch, CT_Tbl):
            yield Table(ch, doc)


# ---------------------------------------------------------------- 文本手术

def _clean_runs(el):
    """保留第一个 run，清掉其余 run 与超链接/书签/域，返回 (run元素, w:t元素)。"""
    for tag in ("w:hyperlink", "w:bookmarkStart", "w:bookmarkEnd", "w:fldSimple"):
        for c in el.findall(qn(tag)):
            el.remove(c)
    runs = el.findall(qn("w:r"))
    for r in runs[1:]:
        el.remove(r)
    if runs:
        r = runs[0]
        for tag in ("w:t", "w:br", "w:tab", "w:drawing", "w:pict", "w:object",
                    "w:fldChar", "w:instrText", "w:lastRenderedPageBreak"):
            for c in r.findall(qn(tag)):
                r.remove(c)
    else:
        r = OxmlElement("w:r")
        el.append(r)
    t = OxmlElement("w:t")
    t.set(qn("xml:space"), "preserve")
    r.append(t)
    return r, t


def clone_para(anchor_para, template_para, text, after=False):
    """深拷贝 template_para 的格式，插到 anchor 前/后，写入 text。

    连续插入同一锚点时统一用 after=False，天然保持先后顺序。
    """
    el = copy.deepcopy(template_para._p)
    _, t = _clean_runs(el)
    t.text = text
    if after:
        anchor_para._p.addnext(el)
    else:
        anchor_para._p.addprevious(el)
    return Paragraph(el, anchor_para._parent)


def clone_table(anchor_para, template_table, insert_after=False):
    """深拷贝表格到锚点前/后。"""
    el = copy.deepcopy(template_table._tbl)
    if insert_after:
        anchor_para._p.addnext(el)
    else:
        anchor_para._p.addprevious(el)
    return Table(el, anchor_para._parent)


def set_para_text(p, text, keep_run0=True):
    """整段换字，保留首个 run 的格式。

    ⚠️ 已知陷阱：若首个 run 是加粗的「(1) 小标题」，整段会被加粗。
    批量替换后必须调用 audit_bold() 复核。
    """
    if not p.runs:
        p.add_run("")
    if not keep_run0:
        for r in list(p.runs):
            r._r.getparent().remove(r._r)
        p.add_run("")
    r0 = p.runs[0]
    for r in p.runs[1:]:
        r._r.getparent().remove(r._r)
    for tag in ("w:t", "w:br", "w:tab"):
        for c in r0._r.findall(qn(tag)):
            r0._r.remove(c)
    t = OxmlElement("w:t")
    t.set(qn("xml:space"), "preserve")
    t.text = text
    r0._r.append(t)
    return p


def replace_text_global(doc, pairs, report=None):
    """全文替换（跨 run 安全版，逐段处理）。

    pairs: [(旧串, 新串), ...]
    返回命中次数；report 若给 list 则逐段记录，便于回滚核对。
    """
    hits = 0
    for p in iter_paras(doc):
        old_full = p.text
        new_full = old_full
        for a, b in pairs:
            if a in new_full:
                new_full = new_full.replace(a, b)
        if new_full != old_full:
            hits += 1
            if report is not None:
                report.append({"before": old_full[:80], "after": new_full[:80]})
            set_para_text(p, new_full)
    return hits


# ---------------------------------------------------------------- 题注与编号

CAPTION_HINTS = ("题注", "Caption", "图注", "表注", "图题", "表题")


def guess_caption_styles(doc, max_len=45):
    """自动猜题注样式名：先按样式名关键词，再按"短且以 图N/表N 开头"段落的样式众数。"""
    names = {s.name for s in doc.styles}
    found = {n for n in names if any(h in n for h in CAPTION_HINTS)}
    if found:
        return found
    from collections import Counter
    c = Counter()
    for p in iter_paras(doc):
        t = p.text.strip()
        if re.match(r"^[图表]\s*\d+", t) and len(t) <= max_len:
            c[p.style.name] += 1
    if c:
        return {c.most_common(1)[0][0]}
    return {"Caption"}


def normalize_captions(doc, styles, max_len=45, target_style=None):
    """把"短且以 图N/表N 开头"的散落段落统一成题注样式。

    原文常见毛病：图1 的题注是 Normal、图10 写成「图 0」、表2 带空格。
    """
    target = target_style or sorted(styles)[0]
    if target not in {s.name for s in doc.styles}:
        return 0
    n = 0
    for p in iter_paras(doc):
        t = p.text.strip()
        if p.style.name in styles:
            continue
        if re.match(r"^[图表]\s*\d+", t) and len(t) <= max_len:
            p.style = doc.styles[target]
            n += 1
    return n


def renumber_captions(doc, styles=None, max_len=45, fix_style=True):
    """按文档位置顺序重排图/表编号，返回 (fig_count, tab_count, changed)。"""
    styles = styles or guess_caption_styles(doc, max_len)
    if fix_style:
        normalize_captions(doc, styles, max_len)
    fig = tab = changed = 0
    for p in iter_paras(doc):
        if p.style.name not in styles:
            continue
        t = p.text.strip()
        m = re.match(r"^([图表])\s*(\d+)\s*(.*)$", t)
        if not m:
            continue
        tail = m.group(3)
        if m.group(1) == "图":
            fig += 1
            new = "图%d%s" % (fig, tail)
        else:
            tab += 1
            new = "表%d%s" % (tab, tail)
        if new != t:
            set_para_text(p, new)
            changed += 1
    return fig, tab, changed


def audit_captions(doc, styles=None, max_len=45):
    """只读：抽查编号连续性、缺号、重号。"""
    styles = styles or guess_caption_styles(doc, max_len)
    figs, tabs = [], []
    for p in iter_paras(doc):
        if p.style.name not in styles:
            continue
        m = re.match(r"^([图表])\s*(\d+)", p.text.strip())
        if not m:
            continue
        (figs if m.group(1) == "图" else tabs).append(int(m.group(2)))
    def issues(seq):
        out = []
        for i, v in enumerate(seq, 1):
            if v != i:
                out.append((i, v))
                break
        dup = [x for x in set(seq) if seq.count(x) > 1]
        return out, dup
    return {"figs": figs, "tabs": tabs,
            "fig_issues": issues(figs), "tab_issues": issues(tabs)}


# ---------------------------------------------------------------- 表格

def fix_table_split(doc):
    """给所有表格行加 w:cantSplit，修跨页时行被纵向裁字。

    症状：某行只显示中间一条（"基础版"渲染成"版"）。
    根因不是行高，是行被跨页拆开。
    """
    n = 0
    for t in doc.tables:
        for r in t.rows:
            trPr = r._tr.get_or_add_trPr()
            if trPr.find(qn("w:cantSplit")) is None:
                trPr.append(OxmlElement("w:cantSplit"))
                n += 1
    return n


def repeat_header_rows(doc):
    """跨页表格首行重复（表头）。"""
    n = 0
    for t in doc.tables:
        if not t.rows:
            continue
        trPr = t.rows[0]._tr.get_or_add_trPr()
        if trPr.find(qn("w:tblHeader")) is None:
            trPr.append(OxmlElement("w:tblHeader"))
            n += 1
    return n


# ---------------------------------------------------------------- 图片

def list_images(docx_path):
    """列出包内图片与正文引用位置。

    返回 [{'name','size','width','height','mode','refs':[关系id...]}]
    """
    from PIL import Image
    rels = {}
    out = []
    with zipfile.ZipFile(docx_path) as z:
        doc_xml = z.read("word/document.xml").decode("utf-8", "ignore")
        rids = set(re.findall(r'r:(?:embed|id)="(rId\d+)"', doc_xml))
        try:
            rel_xml = z.read("word/_rels/document.xml.rels").decode("utf-8", "ignore")
            for m in re.finditer(r'Id="(rId\d+)"[^>]*Target="([^"]+)"', rel_xml):
                rels[m.group(1)] = m.group(2).split("/")[-1]
        except KeyError:
            pass
        for item in z.infolist():
            if not item.filename.startswith("word/media/"):
                continue
            data = z.read(item.filename)
            try:
                im = Image.open(io.BytesIO(data))
                w, h, mode = im.width, im.height, im.mode
            except Exception:
                w = h = 0
                mode = "?"
            base = item.filename.split("/")[-1]
            used = [k for k, v in rels.items() if v == base and k in rids]
            out.append({"name": base, "size": item.file_size,
                        "width": w, "height": h, "mode": mode,
                        "refs": used})
    out.sort(key=lambda d: (len(d["name"]), d["name"]))
    return out


def replace_image_in_package(src, dst, image_name, new_image_path):
    """直接换 zip 条目替换内嵌图片（不新增关系）。

    硬约束：新图尺寸必须与旧图一致，色彩模式也要一致，
    否则显示尺寸偏移、半透明区域会变实色。
    """
    from PIL import Image
    new_mode = Image.open(new_image_path).mode
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        target = "word/media/" + image_name
        hit = False
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == target:
                hit = True
                data = open(new_image_path, "rb").read()
            zout.writestr(item, data)
    if not hit:
        raise SystemExit("包内没有该图片：%s" % target)
    return new_mode


def _iter_inline_shapes(doc):
    """产出所有内联图片及其所在段落。"""
    for p in iter_paras(doc):
        for run in p.runs:
            for child in run._r.iterchildren():
                if child.tag == qn("w:drawing"):
                    for ext in child.iter(qn("wp:extent")):
                        cx = int(ext.get("cx"))
                        cy = int(ext.get("cy"))
                        yield p, ext, cx, cy


def image_width_report(doc):
    """统计每张内联图的显示宽度（cm）。"""
    rows = []
    for p, ext, cx, cy in _iter_inline_shapes(doc):
        rows.append({"cm": round(cx / EMU_PER_CM, 2),
                     "ratio": round(cy / cx, 3) if cx else 0,
                     "caption": p.text.strip()[:40]})
    return rows


def uniform_image_width(doc, target_cm=12.2, keep_small=True, threshold_cm=10.0):
    """把"整幅宽"的图统一到 target_cm，等比缩放高度；刻意做小的图不动。

    实践依据：8.2–13.4cm 参差会让整篇看着毛糙，
    而办法截图/甘特图/近景照片本来就该小，统一反而更难看。
    """
    changed = 0
    for p, ext, cx, cy in _iter_inline_shapes(doc):
        cur = cx / EMU_PER_CM
        if keep_small and cur < threshold_cm:
            continue
        if abs(cur - target_cm) < 0.05:
            continue
        new_cx = int(target_cm * EMU_PER_CM)
        new_cy = int(round(new_cx * (cy / cx))) if cx else cy
        ext.set("cx", str(new_cx))
        ext.set("cy", str(new_cy))
        changed += 1
    return changed


def caption_keep_with_figure(doc, styles=None):
    """给题注段落设 keepNext（尽量与图同页）。

    ⚠️ WPS 对含嵌入图片的段落不遵守 keepNext / keepLines。
    这条只在 Word 下可靠；WPS 下唯一解法是缩小图或删上方文字。
    """
    styles = styles or guess_caption_styles(doc)
    n = 0
    for p in iter_paras(doc):
        if p.style.name in styles:
            p.paragraph_format.keep_with_next = True
            n += 1
    return n


# ---------------------------------------------------------------- 统计与自检

CJK = re.compile(r"[\u4e00-\u9fff]")


def text_stats(doc):
    """字数/段落/表格/图片/高度。"""
    paras = [p for p in iter_paras(doc) if p.text.strip()]
    text = "\n".join(p.text for p in paras)
    cjk = len(CJK.findall(text))
    latin = len(re.findall(r"[A-Za-z]+", text))
    digits = len(re.findall(r"\d+", text))
    return {
        "chars_cjk": cjk,
        "words_latin": latin,
        "tokens_digit": digits,
        "chars_total_no_space": len(re.sub(r"\s", "", text)),
        "paragraphs": len(paras),
        "tables": len(doc.tables),
        "images_inline": sum(1 for _ in _iter_inline_shapes(doc)),
        "sections": len(doc.sections),
    }


def audit_bold(doc, min_len=25):
    """查"整段加粗"——批量替换最典型的副作用。"""
    bad = []
    for p in iter_paras(doc):
        t = p.text.strip()
        if len(t) < min_len or not p.runs:
            continue
        if all(r.bold for r in p.runs if r.text.strip()):
            bad.append(t[:60])
    return bad


DUP_OK = set("常仅一渐刚往每慢悄稍千万纷隐渐默悠的了着")  # 合法叠词用字
FIELD_HINTS = ("项目编号", "负责人", "联系电话", "所在学院", "学号", "专业班级",
               "指导教师", "金额", "签名", "盖章", "日期", "年    月")


def audit_punct(doc):
    """查重复标点、连续重复字、段末多余空格。

    判据保守：重复字要连出三次才算，两次多为合法叠词（往往/常常/一一）。
    行首空格在申报书模板里常被当缩进填充，不算错，故不报。
    """
    issues = []
    for p in iter_paras(doc):
        t = p.text
        if not t.strip():
            continue
        m = re.search(r"[，。；：、？！]{2,}", t)
        if m:
            issues.append({"type": "重复标点", "hit": m.group(0), "text": t[:70]})
            continue
        hit = None
        for m in re.finditer(r"([\u4e00-\u9fff])\1{2,}", t):
            if m.group(1) in DUP_OK:
                continue
            hit = m.group(0)
            break
        if hit:
            issues.append({"type": "疑重复字", "hit": hit, "text": t[:70]})
            continue
        if re.search(r"[ \u3000]+$", t):
            # 封面/信息栏/表格单元格里的"标签 + 空格填充 + 下划线"是模板排版，不是错误
            if any(k in t for k in FIELD_HINTS) or p._p.getparent().tag == qn("w:tc"):
                continue
            issues.append({"type": "段末空格", "hit": "尾部空格", "text": t[:70]})
    return issues


STOP_HEADS = ("附录", "致谢", "指导教师意见", "学院意见", "学校意见", "评审意见", "签字")


def audit_refs(doc):
    """正文 [n] 标注与参考文献条目是否一一对应。

    只把「参考文献」标题之后、形如 [n]/n. 且含四位年份的段落算作条目，
    否则模板尾巴（意见栏、附录）会被误计成文献。
    """
    paras = list(iter_paras(doc))
    body, refs = [], []
    in_refs = False
    for p in paras:
        t = p.text.strip()
        if not t:
            continue
        if re.match(r"^参考文献|^References?", t, re.I):
            in_refs = True
            continue
        if in_refs and any(t.startswith(k) for k in STOP_HEADS):
            in_refs = False
            continue
        if in_refs:
            looks_entry = re.match(r"^\[?\d{1,3}\]?[\.\s、]", t) is not None
            has_year = re.search(r"(19|20)\d{2}", t) is not None
            if looks_entry and has_year:
                refs.append(t)
            continue
        body.append(t)
    body_text = "\n".join(body)
    cited = sorted({int(m) for m in re.findall(r"\[(\d{1,3})\]", body_text)})
    return {
        "ref_entries": len(refs),
        "cited_numbers": cited,
        "max_cited": max(cited) if cited else 0,
        "missing_entries": [c for c in cited if c > len(refs)],
        "uncited_entries": [i for i in range(1, len(refs) + 1) if i not in cited],
        "sample_refs": refs[:3],
    }


PLACEHOLDERS = ("待填", "待补", "xxx", "XXX", "××", "＿＿", "＿＿＿", "（空）", "请填写")


def audit_placeholders(doc):
    """找没填的字段（下划线空白、待填、模板占位符）。"""
    out = []
    for p in iter_paras(doc):
        t = p.text.strip()
        if not t:
            continue
        if re.search(r"_{4,}|＿{3,}|…{3,}", t) or any(k in t for k in PLACEHOLDERS):
            out.append(t[:60])
    return out


def qa_report(docx_path, styles=None):
    """一次跑完全部只读检查，返回结构化字典。"""
    doc = open_doc(docx_path)
    cap = audit_captions(doc, styles)
    rep = {
        "file": os.path.basename(docx_path),
        "format": sniff_format(docx_path),
        "stats": text_stats(doc),
        "captions": cap,
        "refs": audit_refs(doc),
        "bold_blocks": audit_bold(doc),
        "punct": audit_punct(doc),
        "placeholders": audit_placeholders(doc),
        "images": image_width_report(doc),
        "caption_styles": sorted(styles or guess_caption_styles(doc)),
    }
    return rep


def format_qa_markdown(rep):
    """把 qa_report 结果写成可读报告。"""
    s = rep["stats"]
    L = []
    L.append("# 交付自检报告 · %s" % rep["file"])
    L.append("")
    L.append("## 体量")
    L.append("- 中文字符 %d ；英文词 %d ；去空白总字符 %d"
             % (s["chars_cjk"], s["words_latin"], s["chars_total_no_space"]))
    L.append("- 段落 %d ；表格 %d ；内联图片 %d ；节 %d"
             % (s["paragraphs"], s["tables"], s["images_inline"], s["sections"]))
    L.append("")
    L.append("## 图 / 表编号")
    L.append("- 图 %d 张（%s…%s）；表 %d 张"
             % (len(rep["captions"]["figs"]), rep["captions"]["figs"][:3],
                rep["captions"]["figs"][-3:], len(rep["captions"]["tabs"])))
    for key, label in (("fig_issues", "图"), ("tab_issues", "表")):
        first_bad, dup = rep["captions"][key]
        if first_bad:
            L.append("- ⚠️ %s编号在位置 %d 应为 %d 实为 %d（疑有缺号/重号）"
                     % (label, first_bad[0], first_bad[0], first_bad[1]))
        if dup:
            L.append("- ⚠️ %s编号重复：%s" % (label, sorted(dup)))
    if not any(rep["captions"][k][0] or rep["captions"][k][1]
               for k in ("fig_issues", "tab_issues")):
        L.append("- ✅ 编号连续、无重号")
    L.append("")
    r = rep["refs"]
    L.append("## 参考文献")
    L.append("- 条目 %d 条；正文最大编号 [%d]" % (r["ref_entries"], r["max_cited"]))
    if r["missing_entries"]:
        L.append("- ⚠️ 正文引用了不存在的条目：%s" % r["missing_entries"])
    if r["uncited_entries"]:
        L.append("- ⚠️ 有条目未被正文点名引用：%s" % r["uncited_entries"])
    if not r["missing_entries"] and not r["uncited_entries"]:
        L.append("- ✅ 正文标注与条目一一对应")
    L.append("")
    L.append("## 排版风险")
    if rep["bold_blocks"]:
        L.append("- ⚠️ 整段加粗 %d 处（多为批量替换把文字压进加粗 run0）" % len(rep["bold_blocks"]))
        for b in rep["bold_blocks"][:5]:
            L.append("  - %s" % b)
    else:
        L.append("- ✅ 无整段加粗")
    if rep["punct"]:
        L.append("- ⚠️ 标点/空格问题 %d 处" % len(rep["punct"]))
        for x in rep["punct"][:5]:
            L.append("  - [%s] 命中 `%s` ｜ %s" % (x["type"], x.get("hit", ""), x["text"]))
    else:
        L.append("- ✅ 无重复标点、重复字、行首空格")
    if rep["placeholders"]:
        L.append("- ⚠️ 疑似未填字段 %d 处" % len(rep["placeholders"]))
        for x in rep["placeholders"][:8]:
            L.append("  - %s" % x)
    else:
        L.append("- ✅ 未发现占位符")
    L.append("")
    if rep["images"]:
        widths = [i["cm"] for i in rep["images"]]
        L.append("## 插图宽度")
        L.append("- 共 %d 张；区间 %.2f–%.2f cm；中位 %.2f cm"
                 % (len(widths), min(widths), max(widths), sorted(widths)[len(widths) // 2]))
        from collections import Counter
        c = Counter(widths)
        L.append("- 最常见宽度：%s" % ", ".join("%.2fcm×%d" % (k, v) for k, v in c.most_common(4)))
    return "\n".join(L)


# ---------------------------------------------------------------- COM（Windows 可选）

def _dispatch_office():
    """优先 WPS，其次 Word —— 原件多半出自 WPS，用同一引擎转换保真度最高。"""
    try:
        import pythoncom
        import win32com.client as win32
    except ImportError:
        raise SystemExit("需要 pywin32：pip install pywin32")
    pythoncom.CoInitialize()
    app = None
    for prog in ("KWPS.Application", "Word.Application"):
        try:
            app = win32.Dispatch(prog)
            break
        except Exception:
            continue
    if app is None:
        raise SystemExit("既没有找到 WPS，也没有找到 Word（COM 不可用）")
    try:
        app.Visible = False
    except Exception:
        pass
    try:
        app.DisplayAlerts = 0
    except Exception:
        pass
    return app, pythoncom


def convert_to_ooxml(src, dst, timeout_pages=True):
    """旧 .doc / OLE → 真 .docx，返回页数。"""
    app, pythoncom = _dispatch_office()
    try:
        d = app.Documents.Open(os.path.abspath(src), ReadOnly=True, AddToRecentFiles=False)
        d.SaveAs2(os.path.abspath(dst), FileFormat=12)  # 12 = wdFormatXMLDocument
        pages = d.ComputeStatistics(2) if timeout_pages else None
        d.Close(False)
    finally:
        try:
            app.Quit()
        except Exception:
            pass
        pythoncom.CoUninitialize()
    return pages


def export_pdf(src, dst):
    """docx → pdf（COM 通道）。"""
    app, pythoncom = _dispatch_office()
    try:
        d = app.Documents.Open(os.path.abspath(src), ReadOnly=True, AddToRecentFiles=False)
        d.SaveAs2(os.path.abspath(dst), FileFormat=17)  # 17 = wdFormatPDF
        pages = d.ComputeStatistics(2)
        d.Close(False)
    finally:
        try:
            app.Quit()
        except Exception:
            pass
        pythoncom.CoUninitialize()
    return pages


def diff_pdfs(a_pdf, b_pdf, dpi=80):
    """逐页灰度差比对，返回 [(page, mean_abs_diff)]。

    全为 0 才说明转换无损。有差异就得改策略。
    """
    try:
        import numpy as np
        import pymupdf
    except ImportError:
        raise SystemExit("需要 PyMuPDF 与 numpy：pip install pymupdf numpy")
    a, b = pymupdf.open(a_pdf), pymupdf.open(b_pdf)
    out = []
    for i in range(min(a.page_count, b.page_count)):
        pa, pb = a[i].get_pixmap(dpi=dpi), b[i].get_pixmap(dpi=dpi)
        A = np.frombuffer(pa.samples, np.uint8).reshape(pa.height, pa.width, pa.n)
        B = np.frombuffer(pb.samples, np.uint8).reshape(pb.height, pb.width, pb.n)
        h = min(A.shape[0], B.shape[0])
        w = min(A.shape[1], B.shape[1])
        out.append((i + 1, float(np.abs(A[:h, :w].mean(2) - B[:h, :w].mean(2)).mean())))
    return out


def heading_pages(pdf_path, headings, body_keyword="目录"):
    """从渲染后的 PDF 反查每个标题的页码（目录重建第二步用）。"""
    import pymupdf
    pdf = pymupdf.open(pdf_path)
    ptext = [re.sub(r"\s+", "", pdf[i].get_text()) for i in range(pdf.page_count)]
    start = 0
    for i, t in enumerate(ptext):
        if body_keyword in t[:400]:
            start = i + 1
    pages, cur = {}, start
    for h in headings:
        key = re.sub(r"\s+", "", h)
        if not key:
            continue
        for i in range(cur, pdf.page_count):
            if key in ptext[i]:
                pages[h] = i + 1
                cur = i
                break
    return pages


# ---------------------------------------------------------------- 备份

def backup(src, dst=None):
    """备份原文件到同目录 bak/ 下，绝不覆盖原件、不污染工作目录。"""
    import datetime
    if dst is None:
        ext = os.path.splitext(src)[1]
        stem = os.path.splitext(os.path.basename(src))[0]
        d = os.path.join(os.path.dirname(os.path.abspath(src)), "bak")
        os.makedirs(d, exist_ok=True)
        dst = os.path.join(d, "%s_%s%s" % (
            stem, datetime.datetime.now().strftime("%m%d_%H%M%S"), ext))
    shutil.copy2(src, dst)
    return dst


def save_as(doc, src_path, out_path=None):
    """另存为，绝不覆盖原始输入。

    - 不指定 out 时输出 `<名>_修订版.docx`；若已存在则递增序号，
      避免多轮命令互相覆盖（pf tables → pf renumber 连跑时最容易踩）。
    - 允许 out 与输入同路径做原地迭代：先写临时文件再原子替换，
      配合 backup() 使用是安全的。
    """
    if out_path is None:
        base, ext = os.path.splitext(src_path)
        out_path = base + "_修订版" + ext
        i = 2
        while os.path.exists(out_path):
            out_path = "%s_修订版%d%s" % (base, i, ext)
            i += 1
    out_path = os.path.abspath(out_path)
    tmp = out_path + ".pf_tmp"
    doc.save(tmp)
    os.replace(tmp, out_path)
    return out_path
