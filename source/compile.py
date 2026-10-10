# -*- coding: utf-8 -*-
"""一键编译 SteamFast.exe（单文件双角色）。

用法：
    D:\\Python\\python.exe 编译.py
或  C:\\Users\\hp\\.workbuddy\\binaries\\python\\versions\\3.13.12\\python.exe 编译.py

依赖：只需本机自带的 .NET Framework 4.8 编译器 csc.exe，无第三方库。
原理：csc 把 _源码\\SteamFast.cs 编成带图标 + 内嵌清单的 winexe。
      清单里写的是 asInvoker（打开界面不弹 UAC），
      程序自己按命令行参数决定要不要提权（详见 _源码\\SteamFast.cs 的 Main）。
"""
import os
import shutil
import subprocess
import sys

SRC = r"D:\SteamFast\_源码"
OUT = r"D:\SteamFast"
CSC = r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"

ICON_SRC = os.path.join(OUT, "SteamFast.ico")
ICON_SRC_DIR = os.path.join(SRC, "SteamFast.ico")
CS = os.path.join(SRC, "SteamFast.cs")
MANIFEST = os.path.join(SRC, "app.manifest")
EXE = os.path.join(OUT, "SteamFast.exe")


def die(msg):
    print("!! " + msg)
    sys.exit(1)


print("=" * 62)
print(" 编译蒸汽快线 SteamFast")
print("=" * 62)
print("  源码   : %s" % CS)
print("  清单   : %s" % MANIFEST)
print("  输出   : %s" % EXE)
print()

# --- 前置检查 ---
for f, label in ((CS, "源码"), (MANIFEST, "清单"), (ICON_SRC, "图标")):
    if not os.path.exists(f):
        die("缺少%s: %s" % (label, f))
if not os.path.exists(CSC):
    die("找不到编译器 csc.exe: %s" % CSC)
print("  前置检查通过")

# --- 图标同步到源码目录（csc 在 SRC 下工作，用相对路径引用）---
if not os.path.exists(ICON_SRC_DIR) or \
        os.path.getmtime(ICON_SRC) > os.path.getmtime(ICON_SRC_DIR):
    shutil.copy(ICON_SRC, ICON_SRC_DIR)
    print("  已同步图标到源码目录")

# --- 先备份现有 exe，编译失败可回滚 ---
backup = EXE + ".bak"
if os.path.exists(EXE):
    if os.path.exists(backup):
        os.remove(backup)
    shutil.copy2(EXE, backup)
    print("  已备份现有 exe -> SteamFast.exe.bak")

if os.path.exists(EXE):
    os.remove(EXE)

# --- 编译 ---
args = [CSC, "/nologo", "/target:winexe", "/platform:anycpu", "/optimize+",
        "/win32icon:SteamFast.ico", "/win32manifest:app.manifest",
        "/out:" + EXE,
        "/r:System.dll", "/r:System.Core.dll",
        "/r:System.Drawing.dll", "/r:System.Windows.Forms.dll",
        "SteamFast.cs"]

print()
print("  编译中…")
r = subprocess.run(args, cwd=SRC, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
msg = r.stdout.decode("gbk", errors="replace").strip()
if msg:
    print(msg)
print("  返回码 = %d" % r.returncode)

if r.returncode != 0 or not os.path.exists(EXE):
    print()
    print("!! 编译失败")
    if os.path.exists(backup):
        shutil.move(backup, EXE)
        print("   已回滚到编译前的 exe")
    sys.exit(1)

print("  生成成功: %s  %d 字节" % (EXE, os.path.getsize(EXE)))
if os.path.exists(backup):
    os.remove(backup)

# --- 自动自检，确认新 exe 可用 ---
print()
print("  正在自检新 exe…")
try:
    s = subprocess.run([EXE, "--selftest"], cwd=OUT, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, timeout=400)
    print("  自检返回码 = %d" % s.returncode)
    rep = os.path.join(OUT, "selftest_exe.txt")
    if os.path.exists(rep):
        txt = open(rep, encoding="utf-8-sig").read()
        for ln in txt.split("\n"):
            if any(k in ln for k in ("SteamFast v", "管理员", "DPI", "可用 ",
                                     "已有 SteamFast", "停止后 Steam++ 仍在")):
                print("    " + ln.strip())
        os.remove(rep)
    if s.returncode != 0:
        print("  !! 自检未通过，请检查源码")
except Exception as e:
    print("  自检调用失败: %s: %s" % (type(e).__name__, e))

print()
print("=" * 62)
print(" 完成。桌面快捷方式无需重建（仍指向同一个 exe 路径）")
print("=" * 62)
