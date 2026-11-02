# Rubrics_poster 接入原仓库 main — 2026-11-02

用户要求将 Rubrics_poster 发布到原仓库的 main。远程仓库仍为
[Yaosvd/PosterGen](https://github.com/Yaosvd/PosterGen)，仓库根目录的当前项目
变为 Rubrics_poster，不在远端额外嵌套一层 Rubrics_poster/。

## 基线和认证

- 原 main：900a1191ef273aca91776a473a0155a5485fc6d4。
- 独立项目发布前：05fb42e90c92096afbe04dc9b3f0dfcddbae7dd4。
- 独立迁出根提交：b1358464d90623d1f505138bb365fa95cb32d85a。
- 工作目录：/projectone/projects/Rubrics_poster。
- origin：https://github.com:443/Yaosvd/PosterGen.git。
- 本地发布分支：main，发布后跟踪 origin/main。

先准备了保留双方历史的本地合并提交，但终端 HTTPS push 返回无法读取用户名；
没有credential helper、可用SSH身份或常规GitHub token环境变量。没有读取.env、
提取连接器凭据或要求把密钥写入报告。已连接GitHub工具确认本仓库push权限，
因此改用其Git数据接口发布。连接器不会为终端安装认证；以后直接git push
仍需使用者配置正常GitHub认证，也可继续使用已授权的连接工具。

## 实际发布方案

以核对过的独立项目文件树创建远端tree和commit，父提交取原 main900a119；
更新main时校验旧SHA，使用非force更新。原远端历史全部可达，未重写已有提交。
API创建的提交标识由GitHub返回，本地main随后获取并对齐该实际提交。

原独立本地历史保留在codex/independent-rubrics，预备合并和发布说明保留在
codex/main-publish-prepared；不删除或重写这些分支。远端main的新增发布提交
承载完整项目当前状态，不宣称其包含原独立仓库的三个同SHA提交。迁出清单及
报告中的b135846等哈希仍是这些本地保留分支的历史证据。

## 文件范围和验证

发布前对348个已跟踪文件做哈希快照。本次只更新AGENTS.md、README.md、
PROJECT_EXTRACTION_20261102.md，并新增本报告。生产源码、提示词、配置、字体、
前端实现和测试与发布前逐文件一致。原PosterGen本地工作区不变。

没有新增私密配置、论文、虚拟环境、依赖目录、运行缓存或海报到当前文件树。
旧远端提交中已有的文件仍可在历史查看，本次保留历史不抹除这些旧版本。
GitHub树与本地准备树逐项核对；发布后读取main确认提交和tree，并检查本地
跟踪分支及工作区。发布记录通过git log查看，不把提交自身的哈希写进其内容。

本次为Git和文档工作，使用文件指纹、差异空白检查、树一致性和父提交检查，
不重跑全量回归、模型/GPU生成或新增海报。没有新增Rubrics自动循环能力。
