# 蒸汽快线 SteamFast v3.0

Windows 上的 Steam / GitHub 网络加速小工具。
多源测速 + 真实 HTTPS 校验，只把"真的能打开、且明显更快"的 IP 写进 hosts。

## 先说清楚能力边界（v3.0 起写进程序里，不再靠用户猜）

hosts 只能改 DNS 解析结果。它能修的只有一类问题：**DNS 给错了 IP，或给了一个绕远的 IP**。

如果某个域名是在 **IP 层 / TLS(SNI) 层**被拦（表现为 TCP 超时、或 TLS 握手被 RST），
那么 hosts 钉哪个 IP 都没用 —— 这类问题只有代理（本地反代 / 远端代理）能解。

所以本工具的实际覆盖范围是：

| 场景 | 是否有效 | 说明 |
|---|---|---|
| Steam 商店页 / CDN 静态资源 | 有效 | 实测可快 50%~85% |
| Steam 登录 / 结算 / 帮助 | 有效 | 换成更近的 Akamai 出口 |
| GitHub 主站 / API | 有效 | 换成更快的 Azure 出口 |
| GitHub raw 内容、Release 下载 | **无效** | 185.199.x 属 SNI 层封锁 |
| steamcommunity.com 整页 | **无效** | IP 层不可达 |
| Hugging Face 主站 | **无效** | SNI 层封锁 |

程序会把"无解"的域名如实报出来（`hosts 无解，需完整反代`），
不会像 v2.0 那样硬写一条假条目充数。

## 和 v2.0 比，改了什么

- **新增**：真实 HTTPS 请求校验 —— TCP 通、TLS 证书对得上还不够，必须真的拿到正常状态码
- **新增**：现状基线对比 —— 先量一遍"系统 DNS 现在多快"，只有明显更快（≥80ms）才改写；
  写了却不快，等于白折腾还添风险，所以干脆不写
- **新增**：内置种子 IP —— 公共 DNS 被污染时（例如 gist.github.com 被投毒到 59.24.x.x）仍有候选
- **修复**：v2.0 会把 `media.steampowered.com` 钉到一个会被 RST 的 IP，直接导致 Steam 图片/视频加载失败
- **修复**：v2.0 会把 `raw.githubusercontent.com` 等无效域名写进 hosts
- **修复**：状态码校验 —— 只接受与"现状基线"同类的状态码，避免把错的边缘节点写进去

## 功能特性

- 三条腿找候选 IP：系统 DNS（UDP 直查，不读 hosts）→ 内置种子 → 多源公共 DNS
- 三重校验：TCP 握手 → TLS 证书域名匹配 → 真实 HTTPS 状态码
- 一键加速 / 停止 / 还原，hosts 只动自己那一段（带标记区块）
- 首次加速自动备份原始 hosts
- 开机自启支持、DPI 等比缩放
- 与 Steam++（Watt Toolkit）互不干扰，各占自己的标记区块

## 使用方法

**开箱即用**：直接下载本目录下的 [`SteamFast.exe`](./SteamFast.exe)（约 85 KB，单文件，无需安装 .NET 之外的任何依赖），双击即可。

1. 双击运行 `SteamFast.exe`（不弹 UAC）
2. 勾选加速范围（Steam / GitHub 主站 / AI）
3. 选加速模式：
   - **直连优选**（推荐）：只测速写 hosts，不装证书、不设代理、不常驻
   - **完整反代**：唤起已装的 Watt Toolkit（这是唯一能解 raw / 社区整页的方式）
   - **双引擎**：先直连优选，再唤起 Watt Toolkit
4. 点「一键加速」，此时才会弹一次 UAC（改 hosts 必须提权）

## 命令行（便于脚本化验收）

```
SteamFast.exe --diagnose     只测速，不改 hosts，逐条打印判断依据
SteamFast.exe --preview      算出"该写什么"，输出到 logs\hosts_preview.txt，不动 hosts
SteamFast.exe --selftest     环境自检
SteamFast.exe --stop         移除 hosts 区块
SteamFast.exe --restore      还原到首次运行前的 hosts
```

## 编译

单文件 C# 5，不需要任何第三方依赖，用系统自带的 .NET Framework 4.8 编译器即可：

```
csc.exe /target:winexe /platform:anycpu /optimize+ ^
        /win32icon:SteamFast.ico /win32manifest:app.manifest ^
        /out:SteamFast.exe ^
        /r:System.dll /r:System.Core.dll /r:System.Drawing.dll /r:System.Windows.Forms.dll ^
        SteamFast.cs
```

或直接跑 `compile.py`（含备份 / 回滚 / 编译后自动自检）。

## 许可证

GNU General Public License v3.0

## 作者

liujian0914
