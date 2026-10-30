# liujian-projects

个人作品集。每个子目录一个项目，源码与说明都在里面。

| 项目 | 说明 | 版本 | 最近更新 |
|---|---|---|---|
| [SteamFast](./SteamFast) · 蒸汽快线 | Windows 上的 Steam / GitHub 网络加速小工具（hosts 优选 IP + 真实 HTTPS 校验） | 3.0.0 | 2026-10-19 |
| [competition-forge](./competition-forge) · 竞赛工坊 | 中文竞赛全流程 AI 技能包：多赛道（大创/大挑）、Word 结构手术、答辩 PPT 编排、AI 生图、顶刊科研绘图、去 AI 味检测 | 2.0.0 | 2026-10-30 |

## competition-forge 速览

> 原名 `proposal-forge`。v2.0 从"申报书工坊"升级为**多赛道竞赛工坊**。

- **先定赛道再动手**：大创（国家级大学生创新创业训练计划）/ 大挑（"挑战杯"全国大学生课外学术科技作品竞赛），
  两者评审口径完全不同，写法反了就是硬伤
- **一条龙**：文档 → 配图 → PPT → 自检 → 交付
- **PPT 编排层**：不自己实现 PPT，按赛道决定"讲什么、什么风格、要不要动画"，交给 [ppt-master](https://github.com/hugohe3/ppt-master) 生成
  （支持元素级进场/强调/路径动画）
- **AI 生图**：本机 Stable Diffusion 为主（免费无限）+ 云端免费档为辅，含五类"绝不能 AI 生成"的红线
- **科研绘图**：Nature/Science 配色、多子图 a/b/c、误差棒、矢量输出
- **依赖自检**：`pf deps` 一条命令扫出缺什么，**每项给 pip/winget 命令和官方下载链接**，换台电脑不用猜
- **案例研究**：15 份获奖计划书 + 8 份答辩 PPT 的深度分析，提炼出四套章节骨架、12 条写作规律、
  四套配色方案（量化结论：71% 白底简约、平均饱和度仅 13.8%）

说明：[`competition-forge/README.md`](./competition-forge/README.md) ／ 技能主控：[`SKILL.md`](./competition-forge/SKILL.md)

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
- `competition-forge/` 独立的 AI 技能包（`SKILL.md` + `competitions/` 赛道档案 + `ppt/` PPT 编排 + `figures/` 绘图能力 + `scripts/` + `references/` + `templates/`），自带 MIT 许可证

## 更新历史

### 2026-10-30

- **proposal-forge 升级为 competition-forge 2.0.0**：从"申报书工坊"改为"多赛道竞赛工坊"
  - **强制先定赛道**：大创（国家级大学生创新创业训练计划）/ 大挑（"挑战杯"全国大学生课外学术科技作品竞赛），
    两者评审口径完全不同
  - **赛道档案**：`competitions/` 下每个赛道有 PROFILE（评审偏好/骨架/失分点）、cases（案例深度分析）、ppt（PPT 策略）
  - **PPT 编排层**：`ppt/PLAYBOOK.md`，不自己实现 PPT，按赛道决定叙事/风格/动画后交给 ppt-master
  - **AI 生图**：`figures/AI-IMAGERY.md`，本机 SD 免费为主 + 云端免费档为辅，含五类"绝不能 AI 生成"红线
  - **科研绘图**：`figures/SCIENCE-PLOT.md`，Nature 配色、多子图、误差棒、矢量输出
  - **依赖自检**：`pf deps` 扫出缺什么，每项给 pip/winget 命令与官方下载链接
  - **案例研究**：15 份获奖计划书 OCR + 8 份答辩 PPT 抽帧，提炼四套章节骨架、12 条写作规律、四套配色方案
  - 量化结论：**71% 白底简约、平均饱和度仅 13.8%**——获奖作品看起来不花哨

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
`competition-forge/` 例外，采用 **MIT**（见 [`competition-forge/LICENSE`](./competition-forge/LICENSE)），便于被其他项目和工具自由集成。
