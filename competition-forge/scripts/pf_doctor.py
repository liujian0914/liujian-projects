#!/usr/bin/env python3
"""competition-forge 依赖自检 —— 缺什么、怎么装、去哪下，一次说清。

设计目标（2026-10-30 用户要求）：
    别人从 GitHub 克隆或在别的电脑上跑这个项目时，能**自动检测缺什么工具**，
    并**附上官方下载链接**，不用去猜。

用法：
    python scripts/pf_doctor.py              # 人类可读报告
    python scripts/pf_doctor.py --json       # 机器可读
    python scripts/pf_doctor.py --md out.md  # 写成 markdown 清单

退出码：0 = 核心依赖齐全；1 = 缺核心依赖；2 = 只缺可选依赖
"""
import sys
import json
import shutil
import platform
import subprocess
import importlib
import pathlib

IS_WIN = platform.system() == "Windows"

# ---------------------------------------------------------------------------
# 依赖清单：每一行 = 一个能力 + 检测方式 + 缺了怎么办 + 去哪下
# level: core = 没有就跑不起来主流程；opt = 缺了降级但不影响主体
# ---------------------------------------------------------------------------

PY_DEPS = [
    # (模块名, pip 包名, level, 用途, 官网/文档)
    ("docx",     "python-docx",  "core", "Word 结构手术（加章节/换图/题注）", "https://python-docx.readthedocs.io/"),
    ("lxml",     "lxml",         "core", "XML 层操作，python-docx 的底座",     "https://lxml.de/"),
    ("PIL",      "Pillow",       "core", "图像运维（压白底/拼接/换色/改字）",   "https://python-pillow.org/"),
    ("numpy",    "numpy",        "core", "数值计算，图表库底座",               "https://numpy.org/"),
    ("matplotlib", "matplotlib", "core", "七种图表 + 科研绘图",                "https://matplotlib.org/"),
    ("fitz",     "pymupdf",      "core", "PDF 渲染/像素比对/目录页码两遍法",   "https://pymupdf.readthedocs.io/"),
    ("pptx",     "python-pptx",  "opt",  "读/校验 PPTX（PPT 能力要用）",       "https://python-pptx.readthedocs.io/"),
    ("seaborn",  "seaborn",      "opt",  "顶刊风格热力图/统计图",              "https://seaborn.pydata.org/"),
    ("scipy",    "scipy",        "opt",  "散点拟合、显著性检验",               "https://scipy.org/"),
    ("win32com", "pywin32",      "opt",  "Windows COM：旧 doc 转换、PDF 导出、目录页码、PPT 校验",
                                          "https://github.com/mhammond/pywin32"),
]

# 外部程序 / 工具
TOOLS = [
    {
        "name": "git",
        "level": "opt",
        "why": "版本控制、从 GitHub 拉取与推送",
        "check": lambda: shutil.which("git") or _find_git(),
        "windows": "https://git-scm.com/download/win",
        "all": "https://git-scm.com/downloads",
        "install_win": "winget install --id Git.Git -e",
        "note": "本机若只有 MinGit（缺 git-remote-https）则推不了 GitHub，需装完整版",
    },
    {
        "name": "WPS Office 或 Microsoft Word",
        "level": "opt",
        "why": "COM 功能：旧 .doc 转 .docx、导出 PDF、目录页码两遍法、PPT 真开校验",
        "check": lambda: _has_office(),
        "windows": "https://www.wps.cn/ 或 https://www.microsoft.com/microsoft-365",
        "all": "https://www.wps.cn/",
        "install_win": "装 WPS 或 Office 任一即可",
        "note": "没有也能用，只是 pf convert / pf toc / pf verify 不可用",
    },
    {
        "name": "Tesseract OCR",
        "level": "opt",
        "why": "扫描版 PDF/图片的中文 OCR（替代方案：Windows 内置 OCR，见 scripts/ocr_page.ps1）",
        "check": lambda: shutil.which("tesseract"),
        "windows": "https://github.com/UB-Mannheim/tesseract/wiki",
        "all": "https://tesseract-ocr.github.io/",
        "install_win": "winget install --id UB-Mannheim.TesseractOCR -e",
        "note": "本机未装；扫描件 OCR 已改用 Windows 内置 OCR（免费、无需安装）",
    },
    {
        "name": "ppt-master",
        "level": "opt",
        "why": "PPT 生成引擎（本技能只做编排，生成交给它）",
        "check": lambda: _find_ppt_master(),
        "windows": "https://github.com/hugohe3/ppt-master",
        "all": "https://github.com/hugohe3/ppt-master",
        "install_win": "git clone https://github.com/hugohe3/ppt-master.git D:\\AI\\ppt-master",
        "note": "MIT 许可，独立项目，不随本仓库分发",
    },
    {
        "name": "Stable Diffusion WebUI",
        "level": "opt",
        "why": "本机免费 AI 生图（装饰图/背景/IP 形象）",
        "check": lambda: _find_sd(),
        "windows": "https://github.com/AUTOMATIC1111/stable-diffusion-webui",
        "all": "https://github.com/AUTOMATIC1111/stable-diffusion-webui",
        "install_win": "git clone https://github.com/AUTOMATIC1111/stable-diffusion-webui.git D:\\AI\\sd-webui",
        "note": "8GB 显存建议用 cu128 版 torch；无显卡可跳过，改用 AGNES 免费档",
    },
]

# 字体（中文图表必需）
FONTS_WIN = [
    (r"C:\Windows\Fonts\msyh.ttc",   "微软雅黑", "图表中文标签"),
    (r"C:\Windows\Fonts\simsun.ttc", "宋体",     "正文/图表"),
    (r"C:\Windows\Fonts\simfang.ttf","仿宋",     "申报书二级标题"),
    (r"C:\Windows\Fonts\simhei.ttf", "黑体",     "强调"),
]


def _find_git():
    cands = [
        r"C:\Program Files\Git\cmd\git.exe",
        r"C:\Program Files (x86)\Git\cmd\git.exe",
        str(pathlib.Path.home() / "AppData/Local/Programs/Git/cmd/git.exe"),
    ]
    for c in cands:
        if pathlib.Path(c).exists():
            return c
    return None


def _has_office():
    if not IS_WIN:
        return None
    try:
        import win32com.client  # noqa: F401
    except Exception:
        return None
    for prog in ("Word.Application", "KWPS.Application"):
        try:
            import win32com.client
            app = win32com.client.Dispatch(prog)
            app.Quit()
            return prog
        except Exception:
            continue
    return None


def _find_ppt_master():
    for c in (r"D:\AI\ppt-master", str(pathlib.Path.home() / "ppt-master")):
        p = pathlib.Path(c)
        if (p / "skills" / "ppt-master" / "SKILL.md").exists():
            return str(p)
    return None


def _find_sd():
    for c in (r"D:\AI\sd-webui", str(pathlib.Path.home() / "sd-webui")):
        p = pathlib.Path(c)
        if (p / "webui.py").exists() or (p / "webui-user.bat").exists():
            return str(p)
    return None


def check_python_deps():
    out = []
    for mod, pkg, level, why, url in PY_DEPS:
        try:
            m = importlib.import_module(mod)
            ver = getattr(m, "__version__", "")
            out.append({"kind": "python", "name": pkg, "module": mod, "level": level,
                        "ok": True, "version": str(ver), "why": why, "url": url})
        except Exception as e:
            out.append({"kind": "python", "name": pkg, "module": mod, "level": level,
                        "ok": False, "version": "", "why": why, "url": url,
                        "install": f"pip install {pkg}", "error": str(e)[:120]})
    return out


def check_tools():
    out = []
    for t in TOOLS:
        try:
            got = t["check"]()
        except Exception:
            got = None
        out.append({
            "kind": "tool", "name": t["name"], "level": t["level"],
            "ok": bool(got), "found": got if isinstance(got, str) else "",
            "why": t["why"],
            "url": t["windows"] if IS_WIN else t["all"],
            "install": t.get("install_win", "") if IS_WIN else "",
            "note": t.get("note", ""),
        })
    return out


def check_fonts():
    if not IS_WIN:
        return []
    out = []
    for path, name, why in FONTS_WIN:
        out.append({"kind": "font", "name": name, "level": "core",
                    "ok": pathlib.Path(path).exists(), "found": path,
                    "why": why, "url": "", "install": "系统自带，若缺请装中文字体"})
    return out


def check_env():
    info = {
        "python": sys.version.split()[0],
        "executable": sys.executable,
        "platform": f"{platform.system()} {platform.release()}",
        "cwd": str(pathlib.Path.cwd()),
    }
    return info


def report_md(results, env):
    lines = []
    missing_core = [r for r in results if not r["ok"] and r["level"] == "core"]
    missing_opt = [r for r in results if not r["ok"] and r["level"] == "opt"]

    lines.append("# competition-forge 环境自检报告")
    lines.append("")
    lines.append(f"- Python：`{env['python']}`")
    lines.append(f"- 解释器：`{env['executable']}`")
    lines.append(f"- 系统：{env['platform']}")
    lines.append("")
    lines.append(f"**结论**：核心依赖缺 {len(missing_core)} 项，可选依赖缺 {len(missing_opt)} 项。")
    lines.append("")

    if missing_core:
        lines.append("## 🔴 必须安装（缺了主流程跑不起来）")
        lines.append("")
        lines.append("| 名称 | 用途 | 安装命令 | 官网 |")
        lines.append("|---|---|---|---|")
        for r in missing_core:
            lines.append(f"| **{r['name']}** | {r['why']} | `{r.get('install','')}` | [下载]({r['url']}) |")
        lines.append("")

    if missing_opt:
        lines.append("## 🟡 可选安装（缺了降级，不影响主体）")
        lines.append("")
        lines.append("| 名称 | 用途 | 安装方式 | 下载 |")
        lines.append("|---|---|---|---|")
        for r in missing_opt:
            inst = r.get("install", "")
            inst = f"`{inst}`" if inst else "—"
            lines.append(f"| {r['name']} | {r['why']} | {inst} | [下载]({r['url']}) |")
        lines.append("")

    ok_items = [r for r in results if r["ok"]]
    if ok_items:
        lines.append("## ✅ 已就绪")
        lines.append("")
        for r in ok_items:
            ver = f" ({r['version']})" if r.get("version") else ""
            found = f" — `{r['found']}`" if r.get("found") and r["kind"] != "python" else ""
            lines.append(f"- {r['name']}{ver}{found}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 一键安装（复制粘贴）")
    lines.append("")
    lines.append("```bash")
    lines.append("# 核心 Python 依赖")
    lines.append("pip install python-docx lxml Pillow numpy matplotlib pymupdf")
    lines.append("")
    lines.append("# 推荐全量（含 PPT / 统计图 / Windows COM）")
    lines.append("pip install python-docx lxml Pillow numpy matplotlib pymupdf python-pptx seaborn scipy pywin32")
    lines.append("```")
    lines.append("")
    if IS_WIN:
        lines.append("```powershell")
        lines.append("# Windows 外部工具")
        lines.append("winget install --id Git.Git -e")
        lines.append("winget install --id UB-Mannheim.TesseractOCR -e   # 可选，OCR 用")
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


def main():
    as_json = "--json" in sys.argv
    md_out = None
    if "--md" in sys.argv:
        md_out = pathlib.Path(sys.argv[sys.argv.index("--md") + 1])

    env = check_env()
    results = check_python_deps() + check_tools() + check_fonts()

    missing_core = [r for r in results if not r["ok"] and r["level"] == "core"]
    missing_opt = [r for r in results if not r["ok"] and r["level"] == "opt"]

    if as_json:
        print(json.dumps({"env": env, "results": results,
                          "missing_core": len(missing_core),
                          "missing_opt": len(missing_opt)},
                         ensure_ascii=False, indent=2))
    else:
        md = report_md(results, env)
        if md_out:
            md_out.write_text(md, encoding="utf-8")
            print(f"报告已写入 {md_out}")
        else:
            print(md)

    if missing_core:
        return 1
    if missing_opt:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
