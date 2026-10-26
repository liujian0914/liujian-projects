# liujian-projects

个人作品集。每个子目录一个项目，源码与说明都在里面。

| 项目 | 说明 | 版本 | 最近更新 |
|---|---|---|---|
| [SteamFast](./SteamFast) · 蒸汽快线 | Windows 上的 Steam / GitHub 网络加速小工具（hosts 优选 IP + 真实 HTTPS 校验） | 3.0.0 | 2026-10-19 |
| [proposal-forge](./proposal-forge) · 申报书工坊 | 中文项目申报书全流程 AI 技能包：Word 结构手术、七种科研图、配色家族、排版修复、文献规范、去 AI 味检测 | 1.0.0 | 2026-10-26 |

## proposal-forge 速览

- **给 AI 用的技能包**：`SKILL.md` 主控 + 9 份参考手册 + 三套章节骨架，放进 skills 目录即被自动路由
- **可单独当命令行工具**：`pf.py` 17 个子命令，全部支持 `--json`，能被 agent 直接消费
- 解决四类真问题：结构不认模板、图不对版、排版崩（图号/目录/表格跨页）、语言飘（满篇"赋能闭环"）
- 七种图型都带配色家族与白色描边；透明 PNG 自动压白底；改图上的字不改字号
- 自带 `pf_selftest.py`，下载后一条命令验证 17 项能力

说明：[`proposal-forge/README.md`](./proposal-forge/README.md) ／ 技能主控：[`SKILL.md`](./proposal-forge/SKILL.md)

## SteamFast 速览

- 单文件 85 KB，双击即用，不装证书、不设系统代理、不常驻后台
- 只把"真的能打开、且比现状快 ≥80ms"的 IP 写进 hosts
- 能力边界写在 README 里：能修 DNS 层，修不了 SNI 层封锁（商店页、GitHub raw、社区整页需代理）

下载：[`SteamFast/SteamFast.exe`](./SteamFast/SteamFast.exe)
说明：[`SteamFast/README.md`](./SteamFast/README.md)
源码：[`source/SteamFast.cs`](./source/SteamFast.cs)

## 给接手的人

要改代码、要发布、要判断某个域名能不能加速，先看 [`AGENTS.md`](./AGENTS.md)。
里面写清了唯一真源在哪、标准动作是什么、哪些域名永远不在解决范围内。

## 目录说明

- `source/` 放 SteamFast 的源码与脚本（`compile.py` 编译、`publish.py` 发布）
- `SteamFast/` 放项目说明、许可证与可直接运行的成品 exe
- `proposal-forge/` 独立的 AI 技能包（`SKILL.md` + `scripts/` + `references/` + `templates/`），自带 MIT 许可证

## 更新历史

### 2026-10-26

- 新增 **proposal-forge 1.0.0**：中文项目申报书全流程工坊
  - 六阶段 SOP（定基 → 搭骨 → 填肉 → 配图 → 修面 → 交付），每阶段带门禁
  - `pf.py` 17 个子命令：格式嗅探、旧 doc 转换、穿透表格遍历、题注重排、
    目录页码两遍法、表格防裁、图片盘点与替换、七种图表、配色迁移、
    改图上的字、交付自检、去 AI 味检测
  - 9 份参考手册 + 3 套章节骨架（大创 / 国创赛 / 挑战杯）+ 生图与改写提示词
  - 50 条实测踩坑记录，含三个静默出错的坑（id 去重漏数据、WPS 不遵守 keepNext、set_text 整段变粗）
  - 自带 `pf_selftest.py`，17 项断言一键验证

### 2026-10-19

- SteamFast 升到 v3.0.0：三重校验（TCP → TLS 证书 → 真实 HTTPS 状态码）、现状基线对比、
  内置种子 IP、新增 `--preview`；修复 v2.0 把 `media.steampowered.com` 钉到坏 IP 的问题
- 成品 exe 随仓库分发
- 新增 `AGENTS.md` 与 `source/publish.py`，把"改代码 → 编译 → 发布"固化成两条命令

### 2026-10-10

- 仓库建立，SteamFast 开源（源码 + GPLv3）

## 许可

各项目目录内单独标注，默认 GPLv3。
`proposal-forge/` 例外，采用 **MIT**（见 [`proposal-forge/LICENSE`](./proposal-forge/LICENSE)），便于被其他项目和工具自由集成。
