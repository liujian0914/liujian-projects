# 02 · Word 结构手术

> 适用：一份已经存在的申报书，要在**原格式零损伤**的前提下加章节、插图、换图、改字、调编号。
> 全部代码都可直接复制进 `python -c` 或 `.py` 文件运行，依赖 `python-docx` + `lxml`。

核心思路：**先把它变成真 OOXML，再用 python-docx 做结构编辑，用 Office COM 导 PDF 做保真校验与页码计算。** 全程不要试图在旧 `.doc` 或"编辑器通道"上做重型编辑。

---

## 0. 先验格式

文件名 `.docx` 不代表它是 OOXML：

```python
with open(path, "rb") as f:
    head = f.read(8)

# 50 4B 03 04  → PK..          → 真 OOXML，python-docx 可用
# D0 CF 11 E0 A1 B1 1A E1     → OLE 复合文档（旧 .doc / WPS 存出的 .doc）
```

OLE 文件用 python-docx 打开会抛：

```
KeyError: no relationship of type 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument' in collection
```

确认内容用 `olefile`：

```python
import olefile
o = olefile.OleFileIO(path)
for s in o.listdir():
    print("/".join(s), o.get_size("/".join(s)))
# WordDocument / 0Table|1Table / Data  → 旧版 .doc
# 出现 WpsCustomData                    → WPS 存出的
```

> ⚠️ 不要把旧 `.doc` 丢给"文档编辑器 SDK"做结构编辑。实测这类通道下结构树所有节点类型都返回 `Paragraph`、大纲接口返回空数组，标题层级完全认不出，新增章节的标题格式必然对不上。它只适合轻量文本替换。

---

## 1. 转成真 .docx

Windows + WPS/Word，用 COM：

```python
import win32com.client as win32, pythoncom
pythoncom.CoInitialize()
app = None
for prog in ("KWPS.Application", "Word.Application"):   # WPS 优先：原件多半出自 WPS
    try:
        app = win32.Dispatch(prog); break
    except Exception:
        pass
app.Visible = False
app.DisplayAlerts = 0
d = app.Documents.Open(SRC, ReadOnly=True, AddToRecentFiles=False)
d.SaveAs2(OUT_DOCX, FileFormat=12)          # 12 = wdFormatXMLDocument
pages = d.ComputeStatistics(2)               # 2 = wdStatisticPages
d.Close(False)
app.Quit()
pythoncom.CoUninitialize()
```

Linux/macOS 用 `soffice --headless --convert-to docx`，替代品是 LibreOffice 而非 COM。

---

## 2. 验证保真（这一步不能省）

原件与转换件**各导一份 PDF**（同一通道，`FileFormat=17`），用 PyMuPDF 逐页比灰度均值：

```python
import pymupdf, numpy as np
a, b = pymupdf.open(A_PDF), pymupdf.open(B_PDF)
for i in range(min(a.page_count, b.page_count)):
    ia, ib = a[i].get_pixmap(dpi=80), b[i].get_pixmap(dpi=80)
    A = np.frombuffer(ia.samples, np.uint8).reshape(ia.height, ia.width, ia.n)
    B = np.frombuffer(ib.samples, np.uint8).reshape(ib.height, ib.width, ib.n)
    print(i + 1, float(np.abs(A.mean(2) - B.mean(2)).mean()))
```

**全为 0** 才说明转换无损，可以放心在 `.docx` 上编辑并交付 `.docx`。有差异就换策略（编辑原格式，或换转换器）。

命令行等价物：

```bash
pf verify 原件.docx 转换件.docx
```

---

## 3. 通读全文建基线

**这是本技能与常见脚本最大的区别。**

`doc.paragraphs` 只返回 body 的直接子段落，**不含表格内段落**。中文申报书极度常见把全文装在一个 1×1 表格单元格里——此时 `doc.paragraphs` 近乎为空，基于它的任何统计都是错的。

正确遍历：

```python
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

def iter_paras(doc):
    """按文档顺序产出全部段落，穿透表格。"""
    for el in doc.element.body.iter(qn("w:p")):
        yield Paragraph(el, doc)
```

`body.iter()` 是 XML 树深度优先遍历，每个节点只访问一次：既不会漏掉表格里的正文，也不会因合并单元格重复产出。

> ❌ **不要用 `id(el)` 做去重。** lxml 的子元素代理是临时对象，被回收后内存地址会被复用；用 `id` 判重会把后面的段落误判成"已见过"而静默跳过。实测一份 14465 字的文档因此只统计到 668 字。这不是性能问题，是正确性问题。

文本框（`w:txbxContent`）里的段落顺序会打乱文档流，需要排除：

```python
def in_textbox(el):
    p = el.getparent()
    while p is not None:
        if p.tag == qn("w:txbxContent"):
            return True
        p = p.getparent()
    return False
```

基线要输出的内容：每段样式名、文本、内嵌图片数、表格行列数、标题列表、图宽分布。落成 txt 再读——**先有基线再动手**。

---

## 4. 新增内容：克隆模板，不要硬造

要"格式与原文件完全一致"，最稳的是**深拷贝一个同类段落**再改文字：

```python
import copy
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

def strip_runs(el):
    """留下第一个 run，清掉其余 run 与超链接/域/书签。"""
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
        r = OxmlElement("w:r"); el.append(r)
    t = OxmlElement("w:t"); t.set(qn("xml:space"), "preserve"); r.append(t)
    return r, t


def clone_before(anchor, template_para, text):
    el = copy.deepcopy(template_para._p)
    _, t = strip_runs(el)
    t.text = text
    anchor._p.addprevious(el)
    return Paragraph(el, anchor._parent)
```

模板取法：一级/二级/三级标题各挑一个正文标题，正文挑一个普通段落，题注挑一个题注样式段落，表格挑一张**列数相同**的表。

**顺序技巧**：往同一锚点连续插入时，每次都 `anchor._p.addprevious(...)`，自然保持先后顺序，不用维护游标。

**克隆表格**：

```python
el = copy.deepcopy(template_table._tbl)
anchor._p.addprevious(el)
tbl = Table(el, doc)
# 缺行：tbl._tbl.append(copy.deepcopy(tbl.rows[-1]._tr))
# 多行：tbl._tbl.remove(tbl.rows[-1]._tr)
```

---

## 5. 整段换字

```python
def set_para_text(p, text):
    """整段换字，保留首个 run 的格式。"""
    if not p.runs:
        p.add_run("")
    r0 = p.runs[0]
    for r in p.runs[1:]:
        r._r.getparent().remove(r._r)
    for tag in ("w:t", "w:br", "w:tab"):
        for c in r0._r.findall(qn(tag)):
            r0._r.remove(c)
    t = OxmlElement("w:t"); t.set(qn("xml:space"), "preserve"); t.text = text
    r0._r.append(t)
```

> ⚠️ **这是最容易造出事故的一步。** 如果首个 run 是加粗的「（1）小标题」，整段会被加粗。批量替换后**必须**查一遍：

```python
def audit_bold(doc, min_len=25):
    bad = []
    for p in iter_paras(doc):
        t = p.text.strip()
        if len(t) < min_len or not p.runs:
            continue
        if all(r.bold for r in p.runs if r.text.strip()):
            bad.append(t[:60])
    return bad
```

修法是按原样式还原为「首句加粗 + 其余常规」，不要图省事整段取消加粗。

---

## 6. 图表编号按位置重排

原文常见毛病：`图10` 写成 `图 0`、`表2` 带空格、某张图的题注用的是普通样式而不是题注样式。逐条字符串匹配必漏。

两步走：

```python
import re
CAPSTYLES = {"题注", "Caption", "图注", "表注"}     # 换成目标文档实际样式名

# ① 先把"短且以 图N/表N 开头"的段落统一成题注样式
for p in iter_paras(doc):
    t = p.text.strip()
    if p.style.name not in CAPSTYLES and re.match(r"^[图表]\s*\d+", t) and len(t) <= 45:
        p.style = doc.styles["题注"]

# ② 再按文档位置顺序遍历，遇题注自增
fig = tab = 0
for p in iter_paras(doc):
    if p.style.name not in CAPSTYLES:
        continue
    m = re.match(r"^([图表])\s*(\d+)\s*(.*)$", p.text.strip())
    if not m:
        continue
    if m.group(1) == "图":
        fig += 1; new = "图%d%s" % (fig, m.group(3))
    else:
        tab += 1; new = "表%d%s" % (tab, m.group(3))
    if new != p.text.strip():
        set_para_text(p, new)
```

长度阈值（≤45 字）用来把"正文里提到 表3 的句子"排除在外。

命令行：

```bash
pf renumber 稿.docx
```

---

## 7. 目录页码：两遍占位法

python-docx 算不了页码。流程是：**先按最终条目数把目录建出来（决定行数）→ 渲染成 PDF 取真实页码 → 回填。**

```python
# ① 收标题
heads = [(p.style.name, p.text.strip()) for p in iter_paras(doc)
         if p.style.name in ("Heading 1", "Heading 2", "Heading 3")]
# ② 删旧目录条目，深拷贝 toc 1/2/3 模板段，文字先写 "标题\t"（页码留空）
# ③ 导 PDF，逐页取文本，按标题顺序从"上一标题所在页"往后找
```

```python
import pymupdf, re
pdf = pymupdf.open(PDF)
ptext = [re.sub(r"\s+", "", pdf[i].get_text()) for i in range(pdf.page_count)]
body_start = max(i for i, t in enumerate(ptext) if "目录" in t[:400]) + 1
cur, pages = body_start, {}
for lvl, h in heads:
    key = re.sub(r"\s+", "", h)
    for i in range(cur, pdf.page_count):
        if key in ptext[i]:
            pages[h] = i + 1
            cur = i
            break
# ④ 回填：set_para_text(toc_para, "%s\t%d" % (label, pages[label]))
```

排序后用 `\s+` 归一化再匹配，能躲开换行与间距差异。行数不变 → 分页稳定 → 页码一次到位。

> 前提：标题使用了**样式**。如果全文标题都是 Normal + 手动加粗，取不到标题列表，此路不通——只能手工做目录，或先把标题套上样式。

---

## 8. 替换文档内嵌图片

`add_picture` 只会**新增**关系。替换已有图片最省事的是改 zip 包：

```python
import zipfile
with zipfile.ZipFile(SRC) as zin, zipfile.ZipFile(DST, "w", zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        data = zin.read(item.filename)
        if item.filename == "word/media/image2.png":
            data = open(NEW_PNG, "rb").read()
        zout.writestr(item, data)
```

三条硬约束：

- **新图尺寸必须与旧图一致**，否则显示尺寸变、版式跑位。
- **色彩模式必须一致**：旧图 RGBA 就存 RGBA，否则原本半透明的区域会变实色。
- **透明背景先压白底**（见 `04-image-ops.md`），Word 不做 alpha 合成。

定位图片顺序：lxml 扫 `word/document.xml`，VML 用 `v:imagedata@r:id`，DrawingML 用 `a:blip@r:embed`，再去 `word/_rels/document.xml.rels` 查 Target。

```bash
pf images 稿.docx --action list                      # 先看清单
pf images 稿.docx --action replace --name image2.png --image 新图.png
```

---

## 9. 插图位置与跟随

- **必须 `addnext` 到目标题注之后**。用 `addprevious` 会把题注与它上面那张图拆开（图在上、题注被推到新插入的图下面），图号重排后完全看不出错在哪。
- 插图先 `doc.add_paragraph()` 建在文末，再 `anchor._p.addprevious(p._p)` 挪到位，设样式 `插图` + 居中。
- 宽度用正文宽：A4 三厘米边距 ≈ **14.5cm**（`(page_width - left_margin - right_margin)`，EMU/360000 = cm）。申报书里通常收到 12.2cm 更协调。

---

## 10. 表格跨页被裁字

症状：某行文字只显示中间一条（"基础版"渲染成"版"）。

根因**不是行高设成 exact**（实测 `trHeight` 多为空），而是**行被跨页拆开**：

```python
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

for t in doc.tables:
    for r in t.rows:
        trPr = r._tr.get_or_add_trPr()
        if trPr.find(qn("w:cantSplit")) is None:
            trPr.append(OxmlElement("w:cantSplit"))
    if t.rows:  # 长表首行重复
        trPr = t.rows[0]._tr.get_or_add_trPr()
        if trPr.find(qn("w:tblHeader")) is None:
            trPr.append(OxmlElement("w:tblHeader"))
```

改完页数可能不变，但**分页内容会变** → 目录页码要重算。

---

## 11. 回到"这一处是不是我引入的"

判断某处错位是既有问题还是自己改坏的，**把原始文件也导一份 PDF，同页对比**。真实案例：原文档本身就有 10 处题注掉页，不比对会误以为是自己的锅，白折腾一轮。

验证方法优先用"渲染成图肉眼比"，不要用启发式判断（例如"页首是不是题注"——图片不产生文字，题注天然就是页首文本行，会大量误报）。

---

## 附：最小依赖

```bash
pip install python-docx lxml pywin32 pymupdf olefile pillow numpy matplotlib
```

其中 `pywin32` 只在 Windows 的 COM 转换/导出 PDF 时需要；`olefile` 只在处理旧 `.doc` 时需要。
