#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
proposal-forge / pf.py
======================
统一命令行入口。所有子命令都支持 --json 输出，方便被 AI agent 直接消费。

    pf doctor                      环境自检
    pf init <dir>                  初始化一个申报书工作区
    pf probe <docx>                文档结构基线
    pf convert <src> [--pdf]       旧 .doc / OLE → 真 .docx（Windows COM）
    pf verify <a.docx> <b.docx>    双 PDF 逐页像素比对（保真校验）
    pf renumber <docx>             图/表题注按位置重排
    pf toc <docx>                  目录页码两遍法重建
    pf tables <docx>               表格防跨页裁字 + 表头重复
    pf images <docx> ...           图片盘点 / 宽度统一 / 换图
    pf chart --spec x.json         按 JSON 规格出图
    pf recolor <img> --anchors ..  配色家族分化
    pf retext <img> --box ..       改图片上的文字
    pf qa <docx>                   交付自检报告
    pf text <docx> --set a=b      批量替换（带加粗复核）
    pf style <md|docx>             去 AI 味检测
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import pf_docx as D
import pf_render as R


def _print(obj, as_json=False):
    if as_json:
        print(json.dumps(obj, ensure_ascii=False, indent=2))
    else:
        if isinstance(obj, (dict, list)):
            print(json.dumps(obj, ensure_ascii=False, indent=2))
        else:
            print(obj)


# ---------------------------------------------------------------- doctor

def cmd_doctor(args):
    """检查依赖、字体、Office COM、ffmpeg 之类，给出可执行的修复建议。"""
    import importlib
    import platform
    res = {"python": sys.version.split()[0], "platform": platform.platform(),
           "packages": {}, "font": None, "com": None, "ok": True, "advice": []}

    pkgs = [("docx", "python-docx", True), ("lxml", "lxml", True),
            ("PIL", "Pillow", True), ("numpy", "numpy", True),
            ("matplotlib", "matplotlib", True),
            ("pymupdf", "pymupdf", False), ("olefile", "olefile", False),
            ("win32com", "pywin32", False), ("send2trash", "send2trash", False)]
    for mod, pip_name, required in pkgs:
        try:
            m = importlib.import_module(mod)
            res["packages"][pip_name] = getattr(m, "__version__", "ok")
        except Exception:
            res["packages"][pip_name] = None
            if required:
                res["ok"] = False
                res["advice"].append("pip install %s（必需）" % pip_name)
            else:
                res["advice"].append("pip install %s（可选，缺失时相关命令不可用）" % pip_name)

    fp = R.find_cn_font()
    res["font"] = fp
    if not fp:
        res["advice"].append("未找到中文字体：Linux 装 fonts-noto-cjk，macOS 版 matplotlib 需指定 PingFang 路径")

    if sys.platform == "win32":
        try:
            import win32com.client as win32
            app = None
            for prog in ("KWPS.Application", "Word.Application"):
                try:
                    app = win32.Dispatch(prog)
                    res["com"] = prog
                    break
                except Exception:
                    continue
            if app is None:
                res["com"] = False
                res["advice"].append("未检测到 WPS/Word：旧 .doc 转换与 PDF 导出不可用（其余功能正常）")
            else:
                try:
                    app.Quit()
                except Exception:
                    pass
        except Exception:
            res["com"] = "pywin32 missing"
    else:
        res["com"] = "n/a（非 Windows，可用 libreoffice --headless 替代）"
        res["advice"].append("非 Windows 环境：pf convert / pf toc / pf verify 需装 LibreOffice 并改用 soffice 命令")

    _print(res, args.json)
    return 0 if res["ok"] else 1


# ---------------------------------------------------------------- init

SKELETON = {
    "project": {
        "title": "在这里填项目全称",
        "type": "dachuang",
        "target_chars": 12000,
        "figure_width_cm": 12.2,
        "caption_style": "",
        "font_family": "Microsoft YaHei",
        "color_family": "navy"
    },
    "files": {"source": "", "working": ""},
    "notes": "type 可选 dachuang / guochuang / tiaozhanbei / generic"
}


def cmd_init(args):
    d = Path(args.dir)
    for sub in ("fig", "img", "bak", "out"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    cfg = d / "proposal.json"
    if not cfg.exists():
        cfg.write_text(json.dumps(SKELETON, ensure_ascii=False, indent=2), encoding="utf-8")
    readme = d / "工作区说明.md"
    if not readme.exists():
        readme.write_text(
            "# 申报书工作区\n\n"
            "- `fig/` 自绘数据图与示意图（dpi=300 PNG）\n"
            "- `img/` 原始图片素材（IP、海报、截图、实拍）\n"
            "- `bak/` 每轮改动前的备份，命名 `_before_<改动内容>.docx`\n"
            "- `out/` 交付物（docx + pdf）\n"
            "- `proposal.json` 项目参数，命令默认值从这里读\n\n"
            "第一步：把原文件放进本目录，跑 `pf probe <文件>` 看结构基线。\n",
            encoding="utf-8")
    _print({"dir": str(d), "config": str(cfg)}, args.json)
    return 0


# ---------------------------------------------------------------- probe

def cmd_probe(args):
    doc = D.open_doc(args.docx)
    stats = D.text_stats(doc)
    styles = D.guess_caption_styles(doc)
    heads = []
    for p in D.iter_paras(doc):
        if p.style.name.lower().startswith("heading") or p.style.name.startswith("标题"):
            heads.append({"level": p.style.name, "text": p.text.strip()[:60]})
    imgs = D.image_width_report(doc)
    out = {"file": args.docx, "format": D.sniff_format(args.docx),
           "stats": stats, "caption_styles": sorted(styles),
           "headings": heads, "headings_count": len(heads),
           "image_widths_cm": [i["cm"] for i in imgs],
           "tables": len(doc.tables)}

    if args.out:
        lines = ["# 结构基线 · %s" % os.path.basename(args.docx), "",
                 "格式：%s" % out["format"],
                 "中文字符 %d ／ 段落 %d ／ 表格 %d ／ 内联图 %d"
                 % (stats["chars_cjk"], stats["paragraphs"], stats["tables"], stats["images_inline"]),
                 "", "## 题注样式", ", ".join(out["caption_styles"]) or "（未识别）",
                 "", "## 标题（%d）" % len(heads)]
        for h in heads:
            lines.append("- [%s] %s" % (h["level"], h["text"]))
        lines += ["", "## 插图显示宽度（cm）",
                  ", ".join(str(w) for w in out["image_widths_cm"]) or "（无）"]
        Path(args.out).write_text("\n".join(lines), encoding="utf-8")
        out["report"] = args.out
    _print(out, args.json)
    return 0


# ---------------------------------------------------------------- convert / verify

def cmd_convert(args):
    fmt = D.sniff_format(args.src)
    out = args.out or str(Path(args.src).with_suffix(".ooxml.docx"))
    info = {"src": args.src, "detected": fmt, "out": out}
    if fmt == "ooxml":
        info["note"] = "已经是真 OOXML，无需转换"
        _print(info, args.json)
        return 0
    if fmt != "ole":
        raise SystemExit("无法识别的格式：%s" % fmt)
    info["ole_streams"] = list(D.ole_streams(args.src).items())[:8]
    pages = D.convert_to_ooxml(args.src, out)
    info["pages"] = pages
    info["verify"] = "请再跑 pf verify 对比原件与转换件的 PDF 像素差"
    if args.pdf:
        pdf = str(Path(out).with_suffix(".pdf"))
        D.export_pdf(out, pdf)
        info["pdf"] = pdf
    _print(info, args.json)
    return 0


def cmd_verify(args):
    pa = str(Path(args.a).with_suffix(".pf_verify_a.pdf"))
    pb = str(Path(args.b).with_suffix(".pf_verify_b.pdf"))
    try:
        D.export_pdf(args.a, pa)
        D.export_pdf(args.b, pb)
        diffs = D.diff_pdfs(pa, pb)
        bad = [d for d in diffs if d[1] > 1.0]
        res = {"pages_a": len(diffs), "pages_b": len(diffs),
               "identical_pages": len(diffs) - len(bad),
               "suspicious": bad[:20],
               "verdict": "转换无损（逐页灰度差全为 0）" if not bad else "存在差异页，需人工比对"}
        _print(res, args.json)
        return 0 if not bad else 2
    finally:
        for p in (pa, pb):
            if os.path.exists(p):
                os.remove(p)


# ---------------------------------------------------------------- 结构手术

def cmd_renumber(args):
    doc = D.open_doc(args.docx)
    before = D.audit_captions(doc)
    bak = D.backup(args.docx)
    fig, tab, changed = D.renumber_captions(doc, max_len=args.max_len)
    out = D.save_as(doc, args.docx, args.out)
    after = D.audit_captions(D.open_doc(out))
    _print({"backup": bak, "out": out, "figures": fig, "tables": tab,
            "captions_rewritten": changed,
            "issues_before": {"fig": before["fig_issues"], "tab": before["tab_issues"]},
            "issues_after": {"fig": after["fig_issues"], "tab": after["tab_issues"]}},
           args.json)
    return 0


def cmd_tables(args):
    doc = D.open_doc(args.docx)
    bak = D.backup(args.docx)
    n = D.fix_table_split(doc)
    h = D.repeat_header_rows(doc) if args.header else 0
    out = D.save_as(doc, args.docx, args.out)
    _print({"backup": bak, "out": out, "rows_protected": n, "header_repeated": h,
            "note": "分页内容会变，目录页码需重算"}, args.json)
    return 0


def cmd_text(args):
    doc = D.open_doc(args.docx)
    pairs = []
    for s in args.set or []:
        if "=>" not in s:
            raise SystemExit("替换表达式格式应为 旧串=>新串")
        a, b = s.split("=>", 1)
        pairs.append((a, b))
    if not pairs:
        raise SystemExit("至少给一个 --set 旧串=>新串")
    bak = D.backup(args.docx)
    report = []
    hits = D.replace_text_global(doc, pairs, report)
    bold = D.audit_bold(doc)
    out = D.save_as(doc, args.docx, args.out)
    _print({"backup": bak, "out": out, "paragraphs_changed": hits,
            "bold_suspects": bold,
            "warning": "若 bold_suspects 非空，说明文字被压进了加粗 run0，需要逐段修正" if bold else None},
           args.json)
    return 0


# ---------------------------------------------------------------- 图片

def cmd_images(args):
    if args.action == "list":
        _print(D.list_images(args.docx), args.json)
        return 0
    doc = D.open_doc(args.docx)
    bak = D.backup(args.docx)
    if args.action == "width":
        n = D.uniform_image_width(doc, args.cm, not args.no_keep_small)
        out = D.save_as(doc, args.docx, args.out)
        _print({"backup": bak, "out": out, "resized": n, "target_cm": args.cm}, args.json)
        return 0
    if args.action == "keepnext":
        n = D.caption_keep_with_figure(doc)
        out = D.save_as(doc, args.docx, args.out)
        _print({"out": out, "captions_tagged": n,
                "note": "WPS 对含图段落不遵守 keepNext，此法只在 Word 下可靠"}, args.json)
        return 0
    if args.action == "replace":
        if not (args.name and args.image):
            raise SystemExit("replace 需要 --name image3.png --image 新图路径")
        out = args.out or D.save_as(doc, args.docx)  # 先落一份，再换包
        mode = D.replace_image_in_package(bak, out, args.name, args.image)
        _print({"out": out, "replaced": args.name, "mode": mode,
                "constraint": "新图尺寸与色彩模式必须与原图一致"}, args.json)
        return 0
    raise SystemExit("未知 action：%s" % args.action)


# ---------------------------------------------------------------- 图表

def cmd_chart(args):
    if args.demo:
        d = Path(args.demo)
        d.mkdir(parents=True, exist_ok=True)
        made = []
        made.append(R.chart_grouped_bar(
            d / "demo_bar.png",
            ["苹果", "梨", "樱桃", "萝卜"],
            [("标志认知", [75.3, 90.2, 66.3, 73.2]), ("标准执行", [40.2, 62.1, 40.3, 40.4])],
            ylabel="得分（百分制）", ref_line=60))
        made.append(R.chart_dumbbell(
            d / "demo_dumbbell.png",
            ["苹果", "梨", "樱桃", "萝卜"], [75.3, 90.2, 66.3, 73.2], [40.2, 62.1, 40.3, 40.4],
            start_label="标志认知", end_label="标准执行", xlabel="得分"))
        made.append(R.chart_gantt(
            d / "demo_gantt.png",
            [("调研数据库", 1, 6, 6, "≥100 份有效样本"),
             ("六维评估工具", 2, 9, 9, "量表+计分规则"),
             ("平台原型", 3, 11, 11, "7 个功能模块"),
             ("研究报告", 10, 14, 14, "约 2 万字")], 14))
        made.append(R.chart_donut(
            d / "demo_donut.png",
            ["普通农户", "家庭农场", "合作社", "龙头企业", "协会", "监管所"],
            [47, 18, 17, 9, 6, 6], center_text="103"))
        made.append(R.chart_heatmap(
            d / "demo_heatmap.png",
            ["农户", "合作社", "企业", "协会"],
            ["认知", "使用", "执行"],
            [[68.2, 55.1, 40.2], [81.4, 63.9, 52.3], [74.6, 58.2, 44.8], [39.6, 34.1, 31.2]],
            cbar_label="得分"))
        made.append(R.chart_slope(
            d / "demo_slope.png",
            {"标志认知": 41.2, "标准执行": 38.5, "维权能力": 33.1},
            {"标志认知": 78.6, "标准执行": 66.4, "维权能力": 61.2},
            left_label="介入前", right_label="介入后", ylabel="得分"))
        made.append(R.chart_framework(
            d / "demo_framework.png",
            [("应用层", ["生产指导", "检验证明", "合规监测", "人才对接"]),
             ("能力层", ["知识图谱", "检索增强", "多模态识别"]),
             ("数据层", ["标准法规库", "产区画像库", "案例库"])]))
        _print({"demo_dir": str(d), "files": [str(x) for x in made]}, args.json)
        return 0

    if not args.spec:
        raise SystemExit("需要 --spec 图表规格 JSON，或 --demo <目录> 生成示例")
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    kind = spec.pop("type")
    out = spec.pop("out")
    fn = {
        "bar": R.chart_grouped_bar,
        "dumbbell": R.chart_dumbbell,
        "gantt": R.chart_gantt,
        "donut": R.chart_donut,
        "heatmap": R.chart_heatmap,
        "slope": R.chart_slope,
        "framework": R.chart_framework,
    }.get(kind)
    if not fn:
        raise SystemExit("不支持的图类型：%s（可选 %s）" % (kind, "bar/dumbbell/gantt/donut/heatmap/slope/framework"))
    p = fn(out, **spec)
    _print({"out": p, "type": kind}, args.json)
    return 0


def cmd_recolor(args):
    res = R.recolor_family(args.image, args.out, args.anchors, args.targets,
                           sat_boost=args.sat)
    _print({"out": res, "anchors": args.anchors, "targets": args.targets,
            "hint": "先跑 pf images ... --action list 确认图，再核语义色不要动"}, args.json)
    return 0


def cmd_retext(args):
    box = [int(v) for v in args.box.split(",")]
    res = R.retext_image(args.image, args.out, box, args.text, font_path=args.font)
    _print(res, args.json)
    return 0


def cmd_hstack(args):
    out = R.hstack(args.images, args.out, gap=args.gap)
    _print({"out": out, "note": "合成单图后只配一个题注，避免竖图分别插入把题注挤到下一页"}, args.json)
    return 0


def cmd_whitebg(args):
    out = R.white_bg(args.image, args.out)
    _print({"out": out, "why": "Word/WPS 不做 alpha 合成，透明背景会渲染成黑块"}, args.json)
    return 0


# ---------------------------------------------------------------- QA / style

def cmd_qa(args):
    rep = D.qa_report(args.docx)
    md = D.format_qa_markdown(rep)
    if args.out:
        Path(args.out).write_text(md, encoding="utf-8")
    if args.json:
        _print(rep, True)
    else:
        print(md)
        if args.out:
            print("\n已写入：%s" % args.out)
    return 0


def cmd_style(args):
    import pf_style as S
    p = Path(args.path)
    if p.suffix.lower() == ".docx":
        doc = D.open_doc(str(p))
        text = "\n".join(x.text for x in D.iter_paras(doc) if x.text.strip())
    else:
        text = p.read_text(encoding="utf-8")
    rep = S.analyze(text)
    if args.out:
        Path(args.out).write_text(S.format_markdown(rep), encoding="utf-8")
    if args.json:
        _print(rep, True)
    else:
        print(S.format_markdown(rep))
    return 0


# ---------------------------------------------------------------- CLI

def build_parser():
    ap = argparse.ArgumentParser(
        prog="pf", description="proposal-forge：中文项目申报书全流程工具",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--json", action="store_true", help="以 JSON 输出，便于 agent 消费")

    # 让 --json 放在子命令前后都能用：子命令里的同名参数用 SUPPRESS，
    # 没显式给就不覆盖顶层已经解析到的值。
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                        help="以 JSON 输出（同顶层 --json）")

    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("doctor", parents=[common], help="环境自检")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("init", parents=[common], help="初始化工作区")
    p.add_argument("dir")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("probe", parents=[common], help="文档结构基线")
    p.add_argument("docx")
    p.add_argument("--out", help="把基线写成 markdown")
    p.set_defaults(func=cmd_probe)

    p = sub.add_parser("convert", parents=[common], help="旧 doc/OLE 转真 docx")
    p.add_argument("src")
    p.add_argument("--out")
    p.add_argument("--pdf", action="store_true")
    p.set_defaults(func=cmd_convert)

    p = sub.add_parser("verify", parents=[common], help="双 PDF 像素比对")
    p.add_argument("a")
    p.add_argument("b")
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("renumber", parents=[common], help="图表题注重排")
    p.add_argument("docx")
    p.add_argument("--out")
    p.add_argument("--max-len", type=int, default=45)
    p.set_defaults(func=cmd_renumber)

    p = sub.add_parser("tables", parents=[common], help="表格防跨页裁字")
    p.add_argument("docx")
    p.add_argument("--out")
    p.add_argument("--header", action="store_true", help="首行设为跨页表头")
    p.set_defaults(func=cmd_tables)

    p = sub.add_parser("text", parents=[common], help="批量替换")
    p.add_argument("docx")
    p.add_argument("--set", action="append", help="旧串=>新串，可重复")
    p.add_argument("--out")
    p.set_defaults(func=cmd_text)

    p = sub.add_parser("images", parents=[common], help="图片盘点与运维")
    p.add_argument("docx")
    p.add_argument("--action", default="list",
                   choices=["list", "width", "replace", "keepnext"])
    p.add_argument("--cm", type=float, default=12.2)
    p.add_argument("--no-keep-small", action="store_true")
    p.add_argument("--name")
    p.add_argument("--image")
    p.add_argument("--out")
    p.set_defaults(func=cmd_images)

    p = sub.add_parser("chart", parents=[common], help="出图")
    p.add_argument("--spec", help="图表规格 JSON")
    p.add_argument("--demo", help="生成七类示例图到指定目录")
    p.set_defaults(func=cmd_chart)

    p = sub.add_parser("recolor", parents=[common], help="配色家族分化")
    p.add_argument("image")
    p.add_argument("--out", required=True)
    p.add_argument("--anchors", type=float, nargs="+", required=True)
    p.add_argument("--targets", type=float, nargs="+", required=True)
    p.add_argument("--sat", type=float, default=0.14)
    p.set_defaults(func=cmd_recolor)

    p = sub.add_parser("retext", parents=[common], help="改图上的字")
    p.add_argument("image")
    p.add_argument("--out", required=True)
    p.add_argument("--box", required=True, help="x0,y0,x1,y1")
    p.add_argument("--text", required=True)
    p.add_argument("--font")
    p.set_defaults(func=cmd_retext)

    p = sub.add_parser("hstack", parents=[common], help="横排拼图")
    p.add_argument("images", nargs="+")
    p.add_argument("--out", required=True)
    p.add_argument("--gap", type=int, default=24)
    p.set_defaults(func=cmd_hstack)

    p = sub.add_parser("whitebg", parents=[common], help="透明图压白底")
    p.add_argument("image")
    p.add_argument("--out")
    p.set_defaults(func=cmd_whitebg)

    p = sub.add_parser("qa", parents=[common], help="交付自检")
    p.add_argument("docx")
    p.add_argument("--out", help="报告写到 md")
    p.set_defaults(func=cmd_qa)

    p = sub.add_parser("style", parents=[common], help="去 AI 味检测")
    p.add_argument("path", help="md/txt 或 docx")
    p.add_argument("--out")
    p.set_defaults(func=cmd_style)
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
