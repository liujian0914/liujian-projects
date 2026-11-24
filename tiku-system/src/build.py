# -*- coding: utf-8 -*-
"""把 CSS + 页面骨架 + 内嵌题库 + 内嵌规范 + 逻辑脚本 组装成 index.html。"""
import os, re, json, sys, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# 版本真源：version.json。每次构建修订号自动 +1，日期写当天，不用手改。
vpath = os.path.join(ROOT, "version.json")
ver = json.load(open(vpath, encoding="utf-8"))
ver["build"] = int(ver.get("build", 0)) + 1
ver["updated"] = datetime.date.today().isoformat()
with open(vpath, "w", encoding="utf-8") as f:
    json.dump(ver, f, ensure_ascii=False, indent=2)
    f.write("\n")
ver_txt = "v%s（build %d · %s）" % (ver.get("version", "1.0.0"), ver["build"], ver["updated"])

css = open(os.path.join(HERE, "app.css"), encoding="utf-8").read()
page = open(os.path.join(HERE, "page.html"), encoding="utf-8").read()
app = open(os.path.join(HERE, "app.js"), encoding="utf-8").read()
bank = open(os.path.join(ROOT, "samples", "毛概题库.qbank.json"), encoding="utf-8").read().strip()
spec = open(os.path.join(ROOT, "spec", "题库格式规范与AI提示词.md"), encoding="utf-8").read()
assert "</script" not in spec.lower()

extra_css = """
/* 题库列表 */
.bank{display:flex;gap:14px;align-items:center;cursor:pointer;padding:14px 15px}
.bank:active{transform:scale(.995)}
.bk-main{flex:1;min-width:0}
.bk-t{font-size:15px;font-weight:650;line-height:1.4;margin-bottom:2px;word-break:break-word}
.bk-s{font-size:12px;color:var(--sub);margin-bottom:3px}
.bk-p{font-size:12px;color:var(--sub);font-variant-numeric:tabular-nums}
.bk-right{display:flex;flex-direction:column;align-items:center;gap:6px;flex:0 0 auto}
.bk-right .ring{width:44px;height:44px;border-radius:50%;display:grid;place-items:center}
.bk-right .ring span{font-variant-numeric:tabular-nums}
.del{appearance:none;border:0;background:transparent;color:var(--sub);font:inherit;font-size:11.5px;
padding:2px 4px;cursor:pointer;border-radius:6px}
.del:hover{color:var(--bad)}
"""

html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#1f5fa9">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="题库系统">
<link rel="manifest" href="manifest.webmanifest">
<link rel="icon" type="image/png" href="icon-192.png">
<link rel="apple-touch-icon" href="icon-192.png">
<title>题库系统</title>
<style>%s%s</style>
</head>
<body>
%s
<script id="bank" type="application/json">%s</script>
<script id="appVer" type="text/plain">%s</script>
<script id="specDoc" type="text/plain">%s</script>
<script>
%s
</script>
</body>
</html>
""" % (css, extra_css, page, bank, ver_txt, spec, app)

out = os.path.join(ROOT, "index.html")
open(out, "w", encoding="utf-8").write(html)
print("生成 index.html", len(html), "字节")
