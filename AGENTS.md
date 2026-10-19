# AGENTS.md · 维护者与 AI 协作须知

给下一个接手这个项目的人（或 AI）看的。先读完再动手，能省掉 90% 的踩坑。

## 一、唯一真源在哪（最重要）

```
D:\SteamFast\
├── SteamFast.exe            ← 成品（由 _源码 编译而来，不要手改）
├── README.md                ← 项目介绍（真源）
├── AGENTS.md                ← 本文件（真源）
├── LICENSE                  ← GPLv3
├── _源码\                    ← 代码真源，只改这里
│   ├── SteamFast.cs         ★ 唯一的源代码文件（单文件 ~1900 行）
│   ├── app.manifest         清单（asInvoker，按参数自己提权）
│   ├── SteamFast.ico        图标
│   ├── 编译.py              编译：csc → 成品 exe + 自动自检
│   └── 发布.py              发布：同步 → git commit → push → 校验远端
├── backup\
│   ├── hosts_original.bak   ★ 第一次运行前的原始 hosts，程序「还原 hosts」靠它
│   └── hosts_before_apply.bak  每次加速前的快照
├── logs\                    运行日志（可随时清，只留最近一份）
└── _repo\                   GitHub 仓库工作副本（只由 发布.py 写入）
    ├── README.md  AGENTS.md  LICENSE
    ├── SteamFast\  (README.md / SteamFast.exe / LICENSE / .gitignore)
    └── source\    (SteamFast.cs / app.manifest / SteamFast.ico / compile.py / publish.py)
```

**改代码只改 `_源码\SteamFast.cs`。**
`_repo\source\SteamFast.cs` 是发布副本，改它会在下次发布时被覆盖，白干。

## 二、标准动作（照抄即可）

改完代码后：

```bat
python D:\SteamFast\_源码\编译.py          :: 编译 + 自动自检
python D:\SteamFast\_源码\发布.py "说明"    :: 同步 + 提交 + 推送 + 校验
```

`编译.py` 会备份旧 exe，编译失败自动回滚；`发布.py` 发现 exe 比源码旧会直接拒发。

验证（不弹窗、不改 hosts，可反复跑）：

```bat
SteamFast.exe --diagnose    逐条打印每个域名的判断依据与耗时
SteamFast.exe --preview     算出该写什么，输出 logs\hosts_preview.txt
SteamFast.exe --selftest    环境自检
```

发布后核对：`git -C D:\SteamFast\_repo rev-parse HEAD` 与 `git ls-remote origin main` 应一致。

## 三、这台机器上的硬约束

- **编译只能用 `csc.exe`**（.NET Framework 4.8 自带）。Bash 工具会拦 csc，必须经 Python `subprocess` 调（`编译.py` 已封装）。
- 语言是 **C# 5**：不要用字符串插值、`?.`、表达式体成员、内联 out 变量、元组。写了编不过。
- `SslProtocols.None` 在 .NET Framework 上**不是"系统协商"，而是握手直接失败**。必须显式写 `Tls12`。
- 新增命令行参数必须**同时**加进 `Program.Main` 的 `hasWork` 白名单，否则会弹 GUI 卡死。
- 写 hosts 需要管理员。程序用 `ShellExecute("runas")` 拉起自己跑 `--job`，界面本身是 `asInvoker` 不弹 UAC。
- 回收站删除用共用 venv 里的 `send2trash`：`C:\Users\hp\.workbuddy\binaries\python\envs\default\Scripts\python.exe`。**不要**手搓 `SHFileOperationW`，结构体对齐错会变成永久删除。

## 四、能力边界（别再往这儿加东西）

hosts 只能改"域名解析到哪个 IP"。以下域名在 IP 层或 TLS(SNI) 层被拦，**任何 hosts 工具都修不了**，
不要试图加进 `Domains` 列表充数：

- `store.steampowered.com`（商店页）—— 对照实验：同 IP `104.84.150.183`，SNI 换 `steamcdn-a.akamaihd.net` 就 200，SNI 用商店域名就超时
- `raw.githubusercontent.com` / `objects.githubusercontent.com` / `gist.githubusercontent.com`（185.199.x 段全被 RST）
- `steamcommunity.com` / `www.steamcommunity.com`
- `huggingface.co` / `cdn-lfs.huggingface.co`

这些只能靠代理（Steam++ 完整反代 / Clash）。程序里已经会如实报「hosts 无解，需完整反代」，
**不要为了"看起来有效"再给它们写死 IP** —— v2.0 就是这么把 `media.steampowered.com` 搞坏的。

## 五、判断逻辑的四个关卡（改之前先理解）

`Engine.One()` 对每个域名依次做：

1. **候选来源三条腿**：系统 DNS（UDP 直查，绕开 hosts 自身污染）→ `Seeds` 内置种子 → 多源公共 DNS
2. **TCP 测速排序**：取最快的 4 个做深校验
3. **深校验 `Probe.HttpCheck`**：TCP 通 → TLS 证书域名匹配 → **真实 HTTPS 请求拿到状态码**；5xx 直接否
4. **基线对比**：先量系统 DNS 现在多快，候选必须快 ≥80ms 才改写；否则不写（写了等于没写）

`DomainResult` 里的 `BaseIp/BaseMs/BaseStatus/Gain` 就是这套对比的产物，日志直接引用它们。

## 六、别碰的东西

- `backup\hosts_original.bak` —— 删了「还原 hosts」就废了
- `_repo\.git` —— 仓库历史，不要重建
- 用户机器上**正在生效**的 hosts 区块 —— 程序自己会维护，不要手改
- `.gitignore` 里 `!SteamFast.exe` 这条例外 —— 删了成品就不进仓库了

## 七、仓库

- 公开仓库：https://github.com/liujian0914/liujian-projects （GPLv3）
- 分支 `main`，账号 `liujian0914`，凭据走本机 git credential manager
- 提交信息用中文，一行说清"改了什么 + 为什么"
