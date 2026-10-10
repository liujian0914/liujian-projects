# 蒸汽快线 SteamFast

Windows 平台的 Steam / GitHub / HuggingFace 网络加速小工具。

## 这是什么

蒸汽快线是一款 Windows 平台的「Steam 网络加速小工具」。

它和 Steam++（Watt Toolkit）不是替代关系，而是**互补关系**：

- **Steam++** -> 在本机架起代理，处理需要走代理的域名
- **蒸汽快线** -> 多源测速后，把最快的直连 IP 写进 hosts，处理适合直连的域名

两者叠加使用，效果最好。

## 功能特性

- 多源 DNS 解析（绕过污染）
- TCP + TLS 双验证测速
- 智能优选最快可用 IP
- 一键加速 / 停止 / 还原
- 开机自启支持
- DPI 等比缩放适配高屏
- 与 Steam++ 互不干扰（独立标记区块）

## 支持的域名

- Steam: store.steampowered.com, api.steampowered.com, community.steamstatic.com 等
- GitHub: github.com, api.github.com, raw.githubusercontent.com 等
- AI: huggingface.co, cdn-lfs.huggingface.co 等

## 使用方法

1. 双击运行 SteamFast.exe
2. 勾选需要加速的范围（Steam / GitHub / AI）
3. 选择加速模式：
   - **直连优选**（推荐）：只测速写 hosts，不装证书
   - **完整反代**：唤起已装的 Watt Toolkit
   - **双引擎**：先直连优选，再唤起 Watt Toolkit
4. 点「一键加速」，等待完成即可

## 安全设计

- 只做一件事：在 hosts 文件里插入带标记的记录块
- 只动自己那一段，其他内容一律不碰
- 首次加速前自动备份原始 hosts
- 可随时还原或停止加速

## 编译

本工具使用单文件 C# 编写，无需额外依赖。

## 与 Steam++ 的关系

两者可以共存，各自维护独立的 hosts 标记区块，互不干扰。

## 许可证

GNU General Public License v3.0

## 作者

liujian0914
