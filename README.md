# Rubrics_poster

从 PosterGen 当前工作区独立迁出的论文海报样本生成项目。迁出基线为
2026-11-02 的 Generator `explore_samples_v33`，包括尚未提交的区域合并和布局改动。

当前能力是独立样本生成与最终评分；Rubrics 的规则提炼、更新和自动迭代循环
尚未实现，后续在本项目开发。

## 运行

本机已配置现有 `http://127.0.0.1:8000/v1` 服务，文本与视觉均使用服务公布的
`Qwen3.8-27B`。新项目 `.env` 独立保存，无需复制原项目配置。服务配置与验证
见 [模型接入报告](docs/reports/MODEL_SETUP_20261102.md)。

```bash
cd /projectone/projects/Rubrics_poster
# 本机 .env 已配置；其他机器请按模型接入报告配置环境变量或自行创建 .env。
CUDA_VISIBLE_DEVICES=5 .venv/bin/python -m rubrics_poster \
  --paper_path data/Truly_Scale_Equivariant_Deep_Nets_with_Fourier_Layers/paper.pdf \
  --text_model local-text --vision_model local-vision \
  --samples 1 --random_seed 31
```

本地文本、视觉服务使用的显卡由服务启动配置决定；上述环境变量仅指定本进程 GPU。
已复制原论文 PDF 和配套 Logo，位于本项目 `data/`，保持未追踪。可直接指定其他 PDF。
`src.workflow.critic_pipeline`、`src.workflow.exploration_cli` 和
`src.workflow.pipeline` 保留为相同样本路线的 CLI 别名。WebUI 也仅开放样本生成。

Python 环境、依赖锁和 Git 仓库独立。重新安装使用：

```bash
uv sync --frozen
.venv/bin/python -m pytest -q tests/test_project_independence.py
.venv/bin/python webui/start_backend.py
# 另一个终端：./webui/start_frontend.sh
```

## 保留的生成行为

- Marker 直接提取文本、图表和图注，随后一次可缓存的拼写校对；存疑保留原文。
- 每个样本独立选择15个受控布局家族之一，包括三栏家族。
- Curator 组织全文、模块、层次和图表；最多2个核心背景模块。
- 固定图表归属和首次图文方向，精确测量与有限空间分配、几何搜索。
- 最多3次容量编辑、1次字段级格式修复；不缩字体或增加额外修复机会。
- 冻结后渲染并进行最终论文对照评分；失败物理诊断如实保存，评分不筛选输出。
- PNG、可编辑 PPTX、检视布局及诊断保存在本项目 `storage/rubrics_samples/`。

旧项目的海报、run、缓存、分数和模型日志没有迁入。新项目具有独立的项目身份，
不能续跑或直接导入旧项目的历史 run。数据契约与算法版本保留，迁出不重写历史。
当前生产入口已解除对经典工作流启动模块的依赖；部分共享内部兼容实现和历史测试
仍保留，以避免在迁出时改变已有算法行为，它们不是额外正式生成入口或自动回退路线。

## 开发与溯源

- [开发指南](AGENTS.md)
- [独立迁出报告](docs/reports/PROJECT_EXTRACTION_20261102.md)
- [迁出源与文件校验清单](docs/reports/extraction_manifest.json)
- 原有报告保留在 `docs/reports/`，每份均附迁出说明；旧记录中的绝对路径属于历史证据。
- 原始开发指南、README 完整快照位于 `docs/reports/archive/`。

本项目不导入原 PosterGen 的源码、环境或存储。公共 Python 管理器、系统字体、
LibreOffice、模型服务及可选的模型下载缓存属于机器基础设施，版本要求见迁出报告。

本项目继承 Y-Research-SBU/PosterGen 的来源、作者归属和 MIT LICENSE；迁出不改变
已有代码的版权归属。

## 迁出验证

当前路线368项回归通过，最终独立性10项检查通过；15个布局家族的内容、
编译坐标和精确测量与源工作区逐项一致。48个提示词/配置/字体文件逐字节保留。
验证包含真实可编辑PPTX/PNG的离线集成，没有启动真实模型或GPU生成。
详细证据和测试范围见迁出报告及 extraction_validation.json。

一次性核对迁出源文件指纹：

```bash
RUBRICS_VALIDATE_EXTRACTION=1 .venv/bin/python -m pytest -q tests/test_project_independence.py
```

后续正常迭代不默认锁死迁出时的源码指纹，也不要覆盖原始迁出清单。

## Git 推送位置

本项目接入原仓库 [Yaosvd/PosterGen](https://github.com/Yaosvd/PosterGen)，
以 `main` 发布 Rubrics_poster。以后在本目录开发和提交：

```bash
cd /projectone/projects/Rubrics_poster
git status
# 配置终端 GitHub 认证，并提交本次修改的具体文件后：
git push
```

本地 `main` 跟踪 `origin/main`。远程仓库名称仍为 PosterGen，其 main 的
当前项目切换为 Rubrics_poster，保留原远端历史。此次通过已连接的 GitHub
工具发布；它不为终端安装凭据，直接运行 git push 前仍需配置终端认证。
独立项目原始本地历史保存在 codex/independent-rubrics 和
codex/main-publish-prepared 分支。旧本地 PosterGen 保留作参考。
详见 [main 发布记录](docs/reports/MAIN_PUBLICATION_20261102.md)。
