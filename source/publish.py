# -*- coding: utf-8 -*-
"""一键发布：把本地唯一真源同步到 GitHub 仓库并推送。

用法：
    python 发布.py "提交说明"
    python 发布.py            # 用默认说明（含日期）

它会做四件事：
    1. 检查 exe 是否比源码旧（旧了就直接拒发，避免把没编译的源码推上去）
    2. 把 _源码\\ 与成品单向复制到 _repo\\（仓库工作副本）
    3. git add / commit / push
    4. 核对远端 main 的 SHA 与本地 HEAD 一致，不一致就报错

真源只有一个：D:\\SteamFast\\_源码\\SteamFast.cs
_repo\\source\\SteamFast.cs 是发布副本，不要直接改。
"""
import os
import shutil
import subprocess
import sys
import datetime

ROOT = r"D:\SteamFast"
SRC = os.path.join(ROOT, "_源码")
REPO = os.path.join(ROOT, "_repo")
GIT = r"C:\Users\hp\.workbuddy-ai\binaries\PortableGit\versions\1.3.0\cmd\git.exe"
REMOTE = "origin"
BRANCH = "main"

# (源, 目标) —— 单向：本地真源 → 仓库副本
SYNC = [
    (os.path.join(SRC, "SteamFast.cs"), os.path.join(REPO, "source", "SteamFast.cs")),
    (os.path.join(SRC, "app.manifest"), os.path.join(REPO, "source", "app.manifest")),
    (os.path.join(SRC, "SteamFast.ico"), os.path.join(REPO, "source", "SteamFast.ico")),
    (os.path.join(SRC, "编译.py"), os.path.join(REPO, "source", "compile.py")),
    (os.path.join(SRC, "发布.py"), os.path.join(REPO, "source", "publish.py")),
    (os.path.join(ROOT, "SteamFast.exe"), os.path.join(REPO, "SteamFast", "SteamFast.exe")),
    (os.path.join(ROOT, "README.md"), os.path.join(REPO, "SteamFast", "README.md")),
    (os.path.join(ROOT, "AGENTS.md"), os.path.join(REPO, "AGENTS.md")),
    (os.path.join(ROOT, "LICENSE"), os.path.join(REPO, "LICENSE")),
    (os.path.join(ROOT, "LICENSE"), os.path.join(REPO, "SteamFast", "LICENSE")),
]


def die(msg):
    print("!! " + msg)
    sys.exit(1)


def git(*args, **kw):
    r = subprocess.run([GIT, "-C", REPO] + list(args), stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, **kw)
    return r.returncode, r.stdout.decode("utf-8", errors="replace").strip()


def main():
    msg = sys.argv[1] if len(sys.argv) > 1 else ("更新 " + datetime.date.today().isoformat())

    cs = os.path.join(SRC, "SteamFast.cs")
    exe = os.path.join(ROOT, "SteamFast.exe")
    for f in (cs, exe, GIT):
        if not os.path.exists(f):
            die("缺少文件: " + f)

    # 1) exe 必须不比源码旧
    if os.path.getmtime(exe) < os.path.getmtime(cs):
        die("exe 比源码旧，先跑 _源码\\编译.py 编译再发布")

    # 2) 单向同步
    for s, d in SYNC:
        if not os.path.exists(s):
            die("源文件不存在: " + s)
        os.makedirs(os.path.dirname(d), exist_ok=True)
        shutil.copy2(s, d)
        print("  同步 " + os.path.relpath(d, REPO))

    # 3) 提交推送
    rc, out = git("add", "-A")
    if rc != 0:
        die("git add 失败: " + out)
    rc, out = git("status", "--porcelain")
    if rc != 0:
        die("git status 失败: " + out)
    if not out.strip():
        print("没有变更，无需提交")
        return
    print("  变更:\n" + "\n".join("    " + l for l in out.splitlines()))

    rc, out = git("-c", "user.name=liujian0914",
                  "-c", "user.email=liujian0914@users.noreply.github.com",
                  "commit", "-m", msg)
    if rc != 0:
        die("git commit 失败: " + out)
    print("  " + out.splitlines()[0])

    rc, out = git("push", REMOTE, BRANCH)
    if rc != 0:
        die("git push 失败: " + out)
    print("  " + out.strip().splitlines()[-1])

    # 4) 校验远端与本地一致
    rc, local = git("rev-parse", "HEAD")
    rc, remote = git("ls-remote", REMOTE, "refs/heads/" + BRANCH)
    remote_sha = remote.split()[0] if remote else ""
    if local.strip() != remote_sha:
        die("远端 SHA 与本地不一致：本地 %s / 远端 %s" % (local.strip()[:7], remote_sha[:7]))
    print("  已确认远端与本地一致：" + local.strip()[:7])


if __name__ == "__main__":
    main()
