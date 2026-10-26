# 08 · 科研工具链

> 每个工具只解决一类问题。选错工具，事情不是做不成，是做出来"看着不对"。
> 下表按任务组织，先说该用什么，再说装法和坑。

---

## 一、按任务选工具

| 要做的事 | 首选 | 备选 | 不推荐 |
|---|---|---|---|
| 改 Word 结构（加章节、插图） | python-docx + lxml | 手动改 | 编辑器 SDK 通道 |
| 旧 .doc → .docx | WPS/Word COM | LibreOffice | 直接改后缀名 |
| 算目录页码 | PyMuPDF 渲染后查 | — | Word 域（跨软件不准） |
| 出数据图 | matplotlib | Excel（仅内部看） | AI 生图 |
| 画架构/流程图 | draw.io / Excalidraw | matplotlib framework | AI 生图 |
| 生成 IP 形象/海报 | 文生图模型 | 找素材 + 改 | 手绘（除非会画） |
| 处理位图（换色/拼接/压白底） | Pillow + numpy | ImageMagick | — |
| 提取 PDF 里的表格 | pdfplumber | camelot | 手工抄 |
| 批量转格式 | pandoc | LibreOffice | — |
| 查文献真实性 | 知网/万方/Scholar + Crossref | — | 凭记忆写 |
| 检测 AI 味 | `pf style` | 人工通读 | 只看词表 |

---

## 二、文档类

### python-docx

**用途**：读写 `.docx` 的结构——段落、表格、样式、图片、关系。

```bash
pip install python-docx
```

**能做的**：遍历段落/表格、读写文字、改样式、克隆段落/表格、插入图片、读写核心属性。

**做不到的**：算页码、渲染、处理旧 `.doc`、做复杂的域更新。

**关键坑**：

- `doc.paragraphs` 不含表格内段落。中文申报书常把全文塞进 1×1 表格——必须走 `doc.element.body.iter(qn("w:p"))`。
- `add_picture` 只能新增，不能替换已有图。替换要改 zip 包。
- 保存到同一路径有风险，先写临时文件再 `os.replace`。

### lxml

**用途**：直接操作 OOXML 底层。python-docx 没封装的功能（`w:cantSplit`、`w:tblHeader`、缩进、域）都要靠它。

```python
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
trPr.append(OxmlElement("w:cantSplit"))
```

**关键坑**：OOXML 的元素顺序是有 schema 约束的。把 `<w:keepLines/>` 随便 append 到 `<w:pPr>` 末尾会被 Word 忽略——必须插在正确位置。不确定顺序时，先深拷贝一个已有正确结构的段落，再改文字。

### PyMuPDF（fitz）

**用途**：PDF 渲染成图、提取文本、算页码、做像素比对。

```bash
pip install pymupdf
```

```python
import pymupdf
pdf = pymupdf.open("x.pdf")
page = pdf[0]
pix = page.get_pixmap(dpi=80)
text = page.get_text()
```

**在本流程里**：① 双 PDF 逐页灰度比对验证转换保真；② 从渲染结果反查标题页码（目录两遍法）；③ 交付前把关键页渲染成图肉眼检查。

**坑**：`import fitz` 已弃用，用 `import pymupdf`。高 dpi 渲染很吃内存，批量比对用 80dpi 足够。

### WPS / Word COM（pywin32）

**用途**：格式转换（旧 doc → docx）、导出 PDF、算页数。**只在 Windows 可用。**

```bash
pip install pywin32
```

```python
import win32com.client as win32, pythoncom
pythoncom.CoInitialize()
app = win32.Dispatch("KWPS.Application")   # 或 "Word.Application"
d = app.Documents.Open(path, ReadOnly=True, AddToRecentFiles=False)
d.SaveAs2(out, FileFormat=12)              # 12=docx, 17=pdf
d.Close(False); app.Quit(); pythoncom.CoUninitialize()
```

**坑**：

- **优先 WPS**（`KWPS.Application`）。原件多半出自 WPS，同引擎转换保真度最高。
- 转换完必须做 PDF 像素比对，不能假设"应该没问题"。
- 忘了 `Quit()` 会留一堆后台进程，下次打开文件被锁。
- 某些安全策略环境里，从 shell 调 PowerShell 会被拦、PowerShell 工具没有 stdout。**一律写 Python 脚本跑，结果落文件再读。**

### LibreOffice（soffice）

**用途**：跨平台的格式转换与 PDF 导出，COM 的替代品。

```bash
soffice --headless --convert-to docx --outdir out in.doc
soffice --headless --convert-to pdf  --outdir out in.docx
```

**坑**：字体缺失会导致版式漂移，Linux 上先装 `fonts-noto-cjk`。

### pandoc

**用途**：markdown ↔ docx 互转、批量格式转换。

```bash
pandoc draft.md -o draft.docx --reference-doc=模板.docx
```

**在本流程里**：先用 markdown 写初稿（改起来快），再用 pandoc 套模板转 docx，最后用 python-docx 做精修。这条路适合"从零写"，不适合"改已有的"。

**坑**：`--reference-doc` 只能套样式，不能套表格结构；复杂表格转过去会散。

### pdfplumber

**用途**：从 PDF 里精确提取表格。

```python
import pdfplumber
with pdfplumber.open("x.pdf") as pdf:
    for table in pdf.pages[0].extract_tables():
        print(table)
```

**在本流程里**：从别人的报告/政策文件里取数据放进 `data.md`。

---

## 三、图像类

### Pillow

**用途**：一切位图操作的地基——缩放、裁剪、压白底、合成、绘制、改字。

```bash
pip install pillow
```

常用三招：

```python
# 压白底（透明 PNG 插 Word 会变黑）
bg = Image.new("RGB", im.size, "white"); bg.paste(im, (0, 0), im)

# 高质量缩放（重采样一定用 LANCZOS）
im.resize((w, h), Image.LANCZOS)

# 拼接（两张竖图合成一张，避免题注掉页）
canvas.paste(im, (x, 0), im)
```

### numpy

**用途**：像素级运算。换色相、算墨迹、比对差异都靠它。

**坑**：`uint8` 运算会溢出回绕，做减法前先转 `float32` 或 `int16`。

### ImageMagick

**用途**：命令行批量处理，适合"几十张图一起转"。

```bash
magick mogrify -resize 2000x -format png *.jpg
```

### OpenCV

**用途**：去噪、inpainting、边缘检测。只有"背景是照片还要去字"这种重活才需要，普通纯色背景用 Pillow 逐列插值就够。

---

## 四、图表类

### matplotlib

**用途**：出 300dpi 的印刷级数据图，本技能的主力。

```bash
pip install matplotlib
```

**关键坑**：

- **不要用可变字体**（`*VF.ttf`）。matplotlib 只注册到 weight 100，图会细得没法看。用 `msyh.ttc`（微软雅黑，注册了 400/700）。
- `axes.unicode_minus = False`，否则负号显示成方块。
- 数值标签加白色描边（`patheffects.withStroke`），缩到 12cm 宽后仍可读。

### pandas

**用途**：整理原始数据、算汇总、生成图表输入。

**在本流程里**：把问卷导出的 Excel 变成 `data.md` 里的表格，顺便核对"样本数是否对得上"。

### openpyxl

**用途**：读写 Excel，不破坏原格式地改数据。

```bash
pip install openpyxl
```

### Graphviz

**用途**：自动布局的关系图、流程图。节点多（>15）时比手工排版省事。

```bash
pip install graphviz    # 另需安装 graphviz 二进制
```

### draw.io / Excalidraw

**用途**：手工画架构图、泳道图、机制图。**含精确文字与数据的示意图，用这个而不是 AI 生图。**

画完导出 PNG（2x），插入后用 `pf recolor` 统一到本文配色家族。

---

## 五、文献类

| 工具 | 用途 | 注意 |
|---|---|---|
| 知网 / 万方 | 中文文献检索与核验 | 需机构账号 |
| Google Scholar | 中英文都能查，找引用关系 | 部分结果无全文 |
| Crossref API | 核实西文条目与 DOI | `api.crossref.org/works?query.bibliographic=题名` |
| Zotero | 文献管理与格式化导出 | 导出的 GB/T 7714 样式仍需人工过一遍 |
| CNIPA / 地方政府网站 | 政策文件原文 | 文号、日期必须逐个核对 |

**底线：不编造。** 查不到卷期页码就换一篇，或标 `[J/OL]` 给真实 URL。

---

## 六、生图类

### 文生图模型

**用途**：IP 形象、海报、界面临摹、氛围图。

**能做的**：3D 卡通吉祥物、扁平插画、海报底图、UI 概念图。

**做不了的**：含精确中文与数字的架构图（文字必糊、数字必错）、需要与表格数据一致的数据图。

**流程**：

```
提示词 → 生成 4 张候选 → 挑一张 → 压白底 → 插入 Word
```

提示词要点见 `templates/prompt-figures.md`。核心是四段式：**主体 + 风格 + 构图用途 + 禁止项**。

**坑**：

- 生成图带透明通道的比例很高，插 Word 前必须 `pf whitebg`。
- 分辨率给 2000×2000 左右就够 12cm 宽打印，再大只是让 docx 变肥。
- 同一 IP 要出多个姿态时，用同一段提示词 + 固定随机种子，否则形象会飘。

---

## 七、OCR

| 工具 | 适用 |
|---|---|
| Tesseract | 通用，离线，中英文都行 |
| PaddleOCR | 中文识别率更高，表格结构还原好 |
| Windows.Media.Ocr | 系统自带，不用装 |

**在本流程里**：从截图/扫描件里取数字放进 `data.md`。取完必须人工核对——OCR 把 62.05 认成 62.06 这种事很常见。

---

## 八、语言类

- **`pf style`**：本技能自带的 AI 味检测，离线、可批量。
- **Word 拼写与语法检查**：中文能力一般，主要用来抓明显的错字与重复。
- **人工通读**：不可替代。工具能抓模式，抓不到"这段话其实没说什么"。

---

## 九、环境

### 依赖隔离

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows
pip install -r requirements.txt
```

共用环境也行，但**同一个包别装两份**——不同 venv 里版本不一致时，`python-docx` 的行为差异会让人怀疑代码写错了。

### 字体

| 平台 | 中文字体路径 |
|---|---|
| Windows | `C:\Windows\Fonts\msyh.ttc`（微软雅黑） |
| Linux | `/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc` |
| macOS | `/System/Library/Fonts/PingFang.ttc` |

`pf doctor` 会报当前可用字体。

### 编码

Windows 上跑 Python 脚本，输出中文到控制台可能报 `UnicodeEncodeError`。开头加：

```python
import sys
sys.stdout.reconfigure(encoding="utf-8")
```

读文件一律显式指定 `encoding="utf-8"`。

---

## 十、最小可用组合

只做"改文档 + 出图"，装这些就够：

```bash
pip install python-docx lxml pillow numpy matplotlib pymupdf
```

要处理旧 `.doc` 与导出 PDF，Windows 上补 `pywin32`；要读写 Excel 补 `openpyxl pandas`；要 OCR 补 `pytesseract`。

`requirements.txt` 里已按"必需 / 推荐 / 可选"分好组。
