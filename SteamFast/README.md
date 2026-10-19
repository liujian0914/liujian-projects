# 蒸汽快线 SteamFast

> 版本 **3.0.0** ｜ 平台 Windows（.NET Framework 4.8，系统自带） ｜ 单文件 85 KB ｜ GPLv3

Windows 上的 Steam / GitHub 网络加速小工具。
多源测速 + 真实 HTTPS 校验，只把**真的能打开、且明显更快**的 IP 写进 hosts。

不装证书、不设系统代理、不常驻后台 —— 点一下，改完 hosts 就退出。

---

## 一句话说清它管什么、不管什么

**hosts 只能改"域名解析到哪个 IP"，改不了"握手时你说要访问谁"。**

所以：

- DNS 给了个绕远的 IP → 它能修，换成更近的出口
- 域名本身被拦（IP 层超时 / TLS 握手被 RST）→ 它修不了，任何 hosts 工具都修不了

这不是版本问题，是方案边界。v3.0 起把这条写进程序里：碰到修不了的域名，日志会直接说
「hosts 无解，需完整反代」，不再硬写一条假条目充数。

| 场景 | 有效 | 说明 |
|---|---|---|
| Steam 商店/CDN 静态资源 | ✅ | 实测快 50%~85% |
| Steam 登录 / 结算 / 帮助 | ✅ | 换更近的 Akamai 出口 |
| GitHub 主站 / API | ✅ | 换更快的 Azure 出口 |
| GitHub raw 内容、Release 下载 | ❌ | 185.199.x 段被 RST，需代理 |
| steamcommunity.com 整页 | ❌ | IP 层不可达，需代理 |
| store.steampowered.com 商店页 | ❌ | 域名级（SNI）封锁，需代理 |
| Hugging Face 主站 | ❌ | SNI 层封锁，需代理 |

> 商店页那条有对照实验为证：同一个 IP `104.84.150.183`，
> SNI 用 `steamcdn-a.akamaihd.net` 是 160ms / 200 OK，
> SNI 用 `store.steampowered.com` 就超时。同一个 IP，只换握手里的域名，一活一死。

## 本机实测（2026-10-19，校园网，仅供参考）

| 域名 | 耗时 | 结果 |
|---|---|---|
| media.steampowered.com | 96ms | 200 OK |
| cdn.akamai.steamstatic.com | 98ms | 200 OK |
| steamcdn-a.akamaihd.net | 96ms | 200 OK |
| api.steampowered.com | 299ms | 200 OK |
| login.steampowered.com | 251ms | 302 |
| github.com | 163ms（首字节，整页 401KB） | 200 OK |
| api.github.com | — | 200 OK |

改写的收益来自"和系统 DNS 现状比"：例如 store CDN 1268ms → 152ms（快 88%）、
github.com 450ms → 166ms（快 63%）。

## 下载与使用

**开箱即用**：直接下载本目录下的 [`SteamFast.exe`](./SteamFast.exe)（85 KB，单文件）。

1. 双击运行（不弹 UAC）
2. 勾选加速范围（Steam / GitHub 主站 / AI）
3. 选模式：
   - **直连优选**（推荐）：只测速写 hosts，不装证书、不设代理、不常驻
   - **完整反代**：唤起已装的 Watt Toolkit / Steam++（唯一能解商店页、raw、社区整页的方式）
   - **双引擎**：先直连优选，再唤起 Watt Toolkit，覆盖最广
4. 点「一键加速」——只有这一刻会弹一次 UAC（改 hosts 必须提权）

想撤回：点「停止加速」只移除本程序的区块；点「还原 hosts」回到首次运行前的原始内容。

## 和 v2.0 比，改了什么

- **新增** 真实 HTTPS 校验：TCP 通、TLS 证书对得上还不够，必须真拿到正常状态码
- **新增** 现状基线对比：先量系统 DNS 现在多快，只有快 ≥80ms 才改写。写了却不快等于白折腾
- **新增** 内置种子 IP：公共 DNS 被污染时仍有真候选（实测 gist.github.com 被投毒到 59.24.3.173）
- **新增** `--preview`：只算不改，输出 hosts 预览供验收
- **修复** `media.steampowered.com` 被钉到会 RST 的 IP，导致 Steam 图片/视频加载失败
- **修复** `raw.githubusercontent.com` 等无效域名被写进 hosts
- **修复** 只接受与基线同类的状态码，避免把错的边缘节点写进去

## 更新历史

### v3.0.0（2026-10-19）

重做校验逻辑，明确能力边界。

- 三重校验：TCP 握手 → TLS 证书域名匹配 → 真实 HTTPS 状态码
- 现状基线对比，只有明显更快才改写（阈值 80ms）
- 候选来源三条腿：系统 DNS（UDP 直查，不读 hosts）→ 内置种子 → 多源公共 DNS
- 内置种子 IP 表，公共 DNS 被污染时兜底
- 新增 `--preview` 命令行，只算不改
- 修复：`media.steampowered.com` 被钉到会 RST 的 IP（v2.0 的真实 bug，会把 Steam 图片/视频打死）
- 修复：`raw.githubusercontent.com` 等 SNI 层封锁的域名不再写入 hosts
- 修复：状态码必须与基线同类，避免错误的边缘节点
- 界面文案与 README 重写：不再承诺做不到的事

### v2.0.0（2026-10-08）

- 改为原生单文件 exe（C# 5 / .NET Framework 4.8），去掉 PowerShell 脚本依赖
- 单文件双角色：界面 `asInvoker` 不弹 UAC，只在写 hosts 时 `runas` 提权一次
- 嵌入版本资源、DPI 等比缩放、`--render` 离屏截图验收
- 每个候选 IP 必须通过 TLS 握手 + 证书域名校验才允许写入
- hosts 区块插在第一条非注释行之前（避免被 Steam++ 的 `127.0.0.1` 抢先）

### v1.0（2026-10-08）

- 首个可用版本：多源 DNS 优选 + 写 hosts
- 配套整合安装包（内含 Steam++ v3.1.0 便携版，GPLv3 原样再分发）

## 工作原理

```
候选来源（系统 DNS / 内置种子 / 公共 DNS）
        ↓
TCP 握手测速，取最快的 4 个
        ↓
逐个深校验：TCP → TLS 证书 → 真实 HTTPS 状态码
        ↓
和"现状基线"比：快 ≥80ms 才改写
        ↓
写入 hosts 标记区块 → 回读校验 → 刷新 DNS
```

## 命令行

```
SteamFast.exe --diagnose     只测速不改 hosts，逐条打印判断依据
SteamFast.exe --preview      算出该写什么，输出 logs\hosts_preview.txt
SteamFast.exe --selftest     环境自检
SteamFast.exe --stop         移除 hosts 区块
SteamFast.exe --restore      还原到首次运行前的 hosts
```

## 安全设计

- 只做一件事：在 hosts 里插入带标记的记录块
- 只动自己那一段，其他内容一律不碰（Steam++ 的区块互不干扰）
- 首次加速前自动备份原始 hosts（`backup\hosts_original.bak`）
- 随时可停止或还原
- 不联网上传任何数据，不读用户文件

## 编译

单文件 C# 5，不需要第三方依赖，用系统自带的 .NET Framework 4.8 编译器：

```
csc.exe /target:winexe /platform:anycpu /optimize+ ^
        /win32icon:SteamFast.ico /win32manifest:app.manifest ^
        /out:SteamFast.exe ^
        /r:System.dll /r:System.Core.dll /r:System.Drawing.dll /r:System.Windows.Forms.dll ^
        SteamFast.cs
```

或直接跑 `compile.py`（含备份 / 回滚 / 编译后自动自检）。

## 已知限制

- 校园网、运营商对同一域名的封锁状态会变。同一 IP 十分钟内可能 200 → 超时，
  程序只能给"当次实测"的结论，日志里会标明
- 内置种子 IP 会随 GitHub / Akamai 调度变化而失效，失效后只是少几个候选，不会写错
- 被 SNI 层封锁的域名（见上表）永远不在解决范围内

## 许可证

GNU General Public License v3.0

## 作者

liujian0914
