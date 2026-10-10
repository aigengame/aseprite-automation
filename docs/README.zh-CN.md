<!-- spa-readme-i18n: source=README.md sha256=d510b67325741ae7b685fda400687db5862b72ef29863bad09e1b8c9df6848f1 -->

# SPA — 面向 AI 智能体的 Aseprite 自动化工具

![SPA：巫师泡汤喝咖啡，用魔法生成分层像素画](https://raw.githubusercontent.com/aigengame/aseprite-automation/52febf44ac9f33005b0ec4eca1432c312ba2cc93/docs/assets/hero-wizard-spa-calm-garden.png)

**让 AI 智能体参与像素画和精灵动画的创作、编辑、验证与导出。**

SPA 通过 CLI、Agent Skill 和 MCP 服务，将 Aseprite 接入智能体工作流。
保留可继续编辑的 `.aseprite` 源文件，同时交付 PNG、GIF、精灵图集和瓦片素材。

[![CI](https://github.com/aigengame/aseprite-automation/actions/workflows/ci.yml/badge.svg?branch=main&event=push)](https://github.com/aigengame/aseprite-automation/actions/workflows/ci.yml?query=branch%3Amain+event%3Apush)
[![PyPI 版本](https://img.shields.io/pypi/v/aseprite-automation.svg)](https://pypi.org/project/aseprite-automation/)
[![Python 3.13+](https://img.shields.io/badge/Python-3.13%2B-blue)](https://www.python.org/)
[![CLI · Agent Skill · MCP](https://img.shields.io/badge/access-CLI%20%C2%B7%20Agent%20Skill%20%C2%B7%20MCP-7057ff)](#choose-your-integration)

**阅读语言：** [English](../README.md) · 简体中文

[快速上手](#quick-start) · [使用指南](https://github.com/aigengame/aseprite-automation/blob/main/docs/usage.md) ·
[示例项目](#examples) · [MCP 配置](https://github.com/aigengame/aseprite-automation/blob/main/docs/mcp.md)

<a id="tldr"></a>
## 一句话开始

把下面这段话交给你的 AI 智能体：

> 用 `uv tool install --python 3.13 aseprite-automation` 安装 SPA CLI，
> 再用 `npx skills add aigengame/aseprite-automation --skill spa -g` 安装它的 Agent Skill。
> 然后阅读 Skill，按其中的指引配置 SPA，让它使用我已安装的 Aseprite，
> 最后运行 `spa info`，确认配置可用。

你需要单独安装 Aseprite。环境要求和安装选项见[安装](#installation)与
[Agent Skill](#agent-skill)。也可以直接使用 CLI，或接入 [MCP 客户端](#mcp)。

<a id="contents"></a>
## 目录

- [为什么选择 SPA？](#why-spa)
- [可以用它做什么？](#what-can-you-build)
- [安装](#installation)
- [快速上手](#quick-start)
- [选择接入方式](#choose-your-integration)
- [示例项目](#examples)
- [文档与支持](#documentation-and-support)
- [参与贡献](#contributing)

<a id="why-spa"></a>
## 为什么选择 SPA？

- **素材随时可改。** 使用 Aseprite 原生的图层、帧、Cel 和 Tag 制作素材，
  同时保留源文件与游戏所需的导出文件，方便后续修改。
- **动画由你掌控。** 调整帧时长，以及已有 Cel 的位置、透明度和运动。
  通过明确的操作请求，让工作流中的步骤可以重复执行。
- **接入已有画作。** 为外部 PNG 配置调色板、透明度、尺寸和锚点，
  再导入相容的图像来制作动画。
- **改了什么，看得清楚。** 检查已保存的素材、验证预期属性、对比帧并预览结果。
  结构化输出帮助智能体识别和处理失败。
- **按需选择接入方式。** 可以使用命令行、可复用的 Skill 指引，或 Aseprite MCP 服务；
  三者调用同一套底层操作。

SPA 以批处理模式运行 Aseprite，已支持的操作无需操控编辑器界面。
美术方向、视觉审查和素材接入游戏，仍然是完整工作流的一部分。

<a id="what-can-you-build"></a>
## 可以用它做什么？

| 你的目标 | SPA 提供的能力 | 相关命令 |
| --- | --- | --- |
| 创作可复用的像素素材 | 精灵、图层、帧、Cel、Tag、Slice，以及可编辑的原生文件 | `sprite`、`layer`、`frame`、`cel`、`tag`、`slice` |
| 准备和编辑画作 | PNG 准备与导入、图像变换、选区、原生绘制与滤镜 | `raster`、`image`、`selection`、`paint`、`filter` |
| 制作和检查动画 | 帧时长、Cel 位置、运动曲线、动画检查、帧对比和预览 | `motion`、`animation`、`frame`、`cel` |
| 处理颜色与瓦片 | 调色板、颜色模式与色彩配置、带 Key 的瓦片、瓦片集和瓦片地图区域 | `palette`、`sprite`、`tileset`、`tilemap` |
| 向游戏交付素材 | PNG 图像、GIF、PNG 序列、附带 JSON 的精灵图集，以及瓦片集和地图导出 | `export` |
| 自动执行一组编辑 | 对同一精灵执行已支持的编辑，在最终保存前统一检查 | `plan check`、`plan run` |

用 `spa --help` 和各命令的 `--schema` 查看当前安装版本的能力。
`spa info` 检查 Aseprite 运行环境；`spa schema` 还会报告当前不可用的原生能力。

<a id="installation"></a>
## 安装

需要 **Python 3.13+**、[uv](https://docs.astral.sh/uv/getting-started/installation/)，
以及单独安装的 [Aseprite](https://www.aseprite.org/)。SPA 不包含 Aseprite 可执行程序。

[PyPI 包名](https://pypi.org/project/aseprite-automation/)是 **`aseprite-automation`**，
安装后的命令是 **`spa`**。

<a id="install-from-pypi"></a>
### 从 PyPI 安装

```sh
uv tool install --python 3.13 aseprite-automation
spa version
```

已安装时，用 `uv tool upgrade aseprite-automation` 升级。
如需 MCP，安装可选依赖：
`uv tool install --python 3.13 'aseprite-automation[mcp]'`。
如果找不到 `spa` 命令，运行 `uv tool update-shell`，然后重新打开终端。

也可以从 [GitHub Releases](https://github.com/aigengame/aseprite-automation/releases)
下载 wheel 文件，再用 `uv tool install --python 3.13 /absolute/path/to/the-wheel.whl` 安装。

<a id="install-the-current-development-version"></a>
### 安装当前开发版本

先安装 [Git LFS](https://git-lfs.com/)，再运行：

```sh
git clone --branch dev https://github.com/aigengame/aseprite-automation.git
cd aseprite-automation
git lfs install
git lfs pull
uv tool install --python 3.13 .
spa version
```

Git LFS 用于获取原生能力探针的测试素材和示例资产。
开发分支可能包含尚未发布的能力。
若要参与源码开发，使用 `uv sync` 和 `uv run spa`；详见
[使用指南](https://github.com/aigengame/aseprite-automation/blob/main/docs/usage.md)。

<a id="quick-start"></a>
## 快速上手

先指定 Aseprite 可执行程序的位置。在 macOS 上，应指向
`Aseprite.app/Contents/MacOS/` 内的程序，而不是 `.app` 目录。

```sh
export SPA_ASEPRITE_EXECUTABLE="/absolute/path/to/aseprite"
spa info
```

请在一个新建的工作目录中执行以下命令：创建 32×32 精灵，在透明图层上绘制紫色圆形，
导出 PNG，并核对保存后的尺寸。若目标文件已存在，这些命令会拒绝写入。

**1. 创建可编辑的源文件。**

```sh
spa sprite create --input-json '{
  "target_sprite_file":"canvas.aseprite","overwrite":false,
  "width":32,"height":32,"color_mode":"rgb",
  "initial_layer":{"kind":"transparent"}
}'
```

**2. 在第一个图层的第一帧上绘制。**

```sh
spa paint ellipse --input-json '{
  "source_sprite_file":"canvas.aseprite","target_sprite_file":"orb.aseprite",
  "in_place":false,"overwrite":false,
  "target":{"layer":{"layer_path":[1]},"frame_number":1},
  "coordinate_space":"image-pixel",
  "bounds":{"x":8,"y":8,"width":16,"height":16},"style":"filled",
  "brush":{"kind":"circle","size":1},
  "color":{"kind":"rgba","red":166,"green":104,"blue":255,"alpha":255},
  "ink":"simple","opacity":255
}'
```

**3. 导出图像。**

```sh
spa export image --input-json '{
  "source_sprite_file":"orb.aseprite",
  "destination":{"path":"orb.png","if_exists":"fail"},"frame_number":1,
  "export_image_area":{"kind":"canvas"},"layer_composition":{"mode":"visible"},
  "composition_color_mode":"rgb","color_mode":"preserve",
  "color_profile":"preserve","transparency":"preserve"
}'
```

**4. 检查保存后的源文件，并查看 `orb.png`。**

```sh
spa sprite validate --input-json '{
  "sprite_file":"orb.aseprite",
  "expected":{"width":32,"height":32,"color_mode":"rgb","frame_count":1}
}'
```

命令默认返回 JSON；加上 `--human` 可切换为便于阅读的输出。
验证时请检查 `valid`、`checks` 和 `findings`：`status: success` 只表示检查已执行，
不代表所有检查项都通过。画面效果还需要查看导出的图像来确认。

更多动画、导入、绘制、颜色、瓦片和导出示例见
[使用指南](https://github.com/aigengame/aseprite-automation/blob/main/docs/usage.md)。
通过 `--help` 和 `--schema` 查询参数，无需猜测字段。

<a id="choose-your-integration"></a>
## 选择接入方式

| 接入方式 | 适用场景 | 入口 |
| --- | --- | --- |
| **CLI** | 能运行命令行的智能体、脚本和素材制作管线 | `spa --help` |
| **Agent Skill** | 需要可复用的“创作—验证—导出”操作指引的智能体 | [SPA Skill](https://github.com/aigengame/aseprite-automation/blob/main/skills/spa/SKILL.md) |
| **MCP** | 能发现和调用工具的客户端，并可将导出的 PNG 作为图像内容展示 | [MCP 配置](https://github.com/aigengame/aseprite-automation/blob/main/docs/mcp.md) |

<a id="agent-skill"></a>
### Agent Skill

在使用 SPA 的项目目录中，通过 [Skills CLI](https://github.com/vercel-labs/skills)
安装 Skill。需要 Node/npm。

```sh
npx skills add aigengame/aseprite-automation --skill spa
```

加上 `-g` 可安装到用户目录，供多个项目使用；前面的“一句话开始”采用的就是这种方式。

若使用本地开发仓库，运行：

```sh
npx skills add /absolute/path/to/aseprite-automation --skill spa
```

安装和更新由 Skills CLI 管理。Skill 会读取已安装 SPA 的帮助与 schema，
自身不安装 SPA 或 Aseprite，也不另设兼容性判断或版本管理机制。

<a id="mcp"></a>
### MCP

按[安装](#installation)中的说明安装可选的 `mcp` 依赖，然后配置客户端，
让它启动已安装的 `spa-mcp` 程序。stdio 配置方式见
[MCP 配置](https://github.com/aigengame/aseprite-automation/blob/main/docs/mcp.md)。

仅使用 CLI 时不需要 MCP 依赖。MCP 服务调用同一套操作并返回相同结果，
不会在多次调用之间保留一个活动精灵。

<a id="examples"></a>
## 示例项目

[![通过 SPA 导出的像素巫师施法动画](https://raw.githubusercontent.com/aigengame/aseprite-automation/1ca5e1f4cd7587cf351ddcd1a16122f47d3f8ba0/examples/wizard_cast_v2/evidence/scene-loop.webp)](https://github.com/aigengame/aseprite-automation/blob/main/examples/wizard_cast_v2/README.md)

*Moonlit Spell Practice v2：imagegen 提供画作，Python 编排动作与组装素材，
SPA 制作并导出动画。预览由导出的 PNG 帧生成；示例还包含可玩的 Godot 项目。*

两个巫师示例都保留了可编辑的 Aseprite 源文件和导出的组件素材。
Godot 项目使用这些素材实现施法命中练习：把握时机施法，击中移动靶，完成一轮后可以重玩。

| 示例 | 工作流 | 值得查看的内容 |
| --- | --- | --- |
| [Wizard v1](https://github.com/aigengame/aseprite-automation/blob/main/examples/wizard_cast/README.md) | 程序生成像素与姿态 → SPA → Godot | 128×96 场景、32 帧循环动画、可复用组件和可玩的游戏 |
| [Wizard v2](https://github.com/aigengame/aseprite-automation/blob/main/examples/wizard_cast_v2/README.md) | imagegen 概念图与关键姿态 → 素材准备与动作编排 → SPA → Godot | 384×288 场景、7 个可编辑的 `.aseprite` 资产、导出的 PNG 组件和可玩的游戏 |

SPA 负责动画制作与导出，imagegen 提供 v2 的初始画作，
[gda](https://github.com/aigengame/godot-agent) 负责 Godot 验证。
各示例都记录了素材准备的取舍、验证证据，以及在实际使用中发现的工具改进需求。

无需重建全部资产，即可查看仓库中的素材或打开 Godot 项目。
完整重建属于可选的本地检查；具体步骤见各示例说明和
[测试指南](https://github.com/aigengame/aseprite-automation/blob/main/docs/testing.md)。

<a id="documentation-and-support"></a>
## 文档与支持

- [使用指南](https://github.com/aigengame/aseprite-automation/blob/main/docs/usage.md) — 操作示例、运行环境配置、输出处理与当前限制。
- [精灵图集导出](https://github.com/aigengame/aseprite-automation/blob/main/docs/sprite-sheets.md) — 布局、裁剪、颜色与元数据。
- [MCP 配置](https://github.com/aigengame/aseprite-automation/blob/main/docs/mcp.md) — 安装与客户端配置。
- [Issues](https://github.com/aigengame/aseprite-automation/issues) — 报告问题或提出能力需求。
- [Milestones](https://github.com/aigengame/aseprite-automation/milestones) — 查看规划与交付进度。
- [Aseprite 文档](https://www.aseprite.org/docs/) — 编辑器、文件格式与原生行为。

报告问题时，请附上 `spa version`、`spa info`、最小操作请求和返回的错误。
方便分享时，也请提供一个能复现问题的小型素材。

<a id="contributing"></a>
## 参与贡献

可以从[测试指南](https://github.com/aigengame/aseprite-automation/blob/main/docs/testing.md)、
[架构说明](https://github.com/aigengame/aseprite-automation/blob/main/ARCHITECTURE.md)和
[领域模型](https://github.com/aigengame/aseprite-automation/blob/main/CONTEXT.md)开始了解项目。
产品与实现决策的依据见[权威矩阵](https://github.com/aigengame/aseprite-automation/blob/main/AUTHORITY_MATRIX.md)。

SPA 自有代码和文档采用 [MIT 许可证](https://github.com/aigengame/aseprite-automation/blob/main/LICENSE)。
随包分发的第三方资源遵循各自的[许可声明](https://github.com/aigengame/aseprite-automation/blob/main/THIRD_PARTY_NOTICES.md)。
Aseprite 是独立产品，适用其自身的[许可条款](https://www.aseprite.org/faq/#is-aseprite-free)。
