# liujian-projects

个人作品集。每个子目录一个项目，源码与说明都在里面。

| 项目 | 说明 | 版本 | 最近更新 |
|---|---|---|---|
| [SteamFast](./SteamFast) · 蒸汽快线 | Windows 上的 Steam / GitHub 网络加速小工具（hosts 优选 IP + 真实 HTTPS 校验） | 3.0.0 | 2026-10-19 |

## SteamFast 速览

- 单文件 85 KB，双击即用，不装证书、不设系统代理、不常驻后台
- 只把"真的能打开、且比现状快 ≥80ms"的 IP 写进 hosts
- 能力边界写在 README 里：能修 DNS 层，修不了 SNI 层封锁（商店页、GitHub raw、社区整页需代理）

下载：[`SteamFast/SteamFast.exe`](./SteamFast/SteamFast.exe)
说明：[`SteamFast/README.md`](./SteamFast/README.md)
源码：[`source/SteamFast.cs`](./source/SteamFast.cs)

## 目录说明

- `source/` 放 SteamFast 的源码与编译脚本
- `SteamFast/` 放项目说明、许可证与可直接运行的成品 exe

## 更新历史

### 2026-10-19

- SteamFast 升到 v3.0.0：三重校验（TCP → TLS 证书 → 真实 HTTPS 状态码）、现状基线对比、
  内置种子 IP、新增 `--preview`；修复 v2.0 把 `media.steampowered.com` 钉到坏 IP 的问题
- 成品 exe 随仓库分发

### 2026-10-10

- 仓库建立，SteamFast 开源（源码 + GPLv3）

## 许可

各项目目录内单独标注，默认 GPLv3。
