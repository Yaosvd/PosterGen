# Layout Optimizer 性能优化实施报告

## 2026-10-13 间距规则后续更新

下文记录 2026-10-12 独立提速改动的原始验收。后续标题/空白质量改动见
[LAYOUT_SPACING_REPORT.md](LAYOUT_SPACING_REPORT.md)：标题测量/渲染契约、
方向空白评分和每次拟合最多 2×4 个共享边界精确候选是新的质量行为。
既有缓存、精确键、LRU/负载预算、版本回退、异常清理均保留；新测量和
微调在布局阶段共享上下文。FontAgent 后的检查不复用旧上下文。

等价性含义为“同一套新规则下，缓存开/关结果一致”，不是要求新旧质量规则
输出相同。性能开关只关闭计算复用，不撤销标题安全或空白约束。
新候选和极少数一次重渲染会增加有界工作，不能宣称总耗时零增加；
`composition_refinement` 子阶段进入既有性能报告，真实全阶段收益仍需测量。
本次质量改动升级 Critic/rubric，但不改 Campaign/LayoutSpec schema；下文
“不改变 rubric”仅指原始提速改动。

## 目标与边界

本次优化减少同一次布局尝试中的重复测量，不通过减少搜索、截断内容、
缩短修复预算或降低质量门槛提速。适用于优化循环中的十二个布局家族，
包括循环内的三列式；独立 one-shot classic / Balancer 路径保持原有计算行为。

保留原有高度二分搜索、字号适配、换行、边距、字体替代与行高规则；
几何候选、beam、近失配复查、精确回填、布局评分、随机选择、科学文本校验、
内容/空白非回退保护、Preflight、RenderFit 与 Critic 均未放宽。

## 实现

### 测量复用与隔离

- 新增 `src/layout/measurement_context.py`：每次进入循环布局 Agent 建立独立
  ContextVar 上下文；同一次初始拟合、视觉恢复、内容修复重拟合及最终编译共享。
  离开 Agent 时，无论成功、不可行或异常，均释放缓存并恢复外层上下文。
- 缓存完整高度测量、估算行数、精确换行、字形尺寸与字体对象。完整测量键包含
  原始文字、未经舍入的宽度、字体名、字号、粗体、行距、精度、边距、配置摘要
  和实际字体文件身份（路径、设备/inode、大小、纳秒修改/变更时间）。
- 配置只在当前上下文复用，检测到配置文件变化重新加载。计算期间配置或字体
  变化时，不缓存该次完整结果；测量异常也不发布为成功缓存。
- 可变返回结果独立复制，防止调用方修改污染后续命中。缓存不跨尝试、线程、
  Batch 或 Campaign；复制 Context 到其他线程也不能继承原线程的缓存对象。
  FontAgent 之后的测量不继承布局阶段上下文。
- 上下文、字体对象和回调不进入 PosterState；只有无论文文本的普通诊断字典
  可进入临时 state。诊断不进入科学/Lineage 快照或模板知识。

### 精确换行适配

新增 `src/layout/text_fit_adapter.py`，在项目内部继承已安装库的 TextFitter，
复用相同文字、宽度、字号与字体下的换行和字形计算。
不修改 site-packages，也不对依赖进行全局 monkey-patch。

适配层仅对已对照验证的 `python-pptx==1.0.2`、`Pillow==10.4.0` 启用。
其他版本或未知接口自动使用原始 `fit_text`，并记录兼容回退。
遇到疑似适配错误时不能直接套用旧测量函数的宽泛异常处理，将程序错误当作
“文字放不下”。意外错误明确抛出 `OptimizedFitError`，走已有生成失败路径。
对于旧库本身的窄框/字体错误，仅在原实现也给出相同类型、相同消息时保留
原异常行为；失败的完整测量不缓存。

### 有界缓存

默认配置在 `config/critic_config.yaml` 的 `layout_performance`：

| 缓存 | 最大条目数 |
| --- | ---: |
| 完整高度测量 exact | 4096 |
| 行数估算 line | 8192 |
| 精确换行 wrap | 8192 |
| 字形尺寸 glyph | 16384 |
| 字体对象 font | 64 |

另设共享 `max_text_payload_bytes: 33554432`，按键和值中 UTF-8 文本负载计量。
逐类条目超限或共享负载超限时按 LRU 淘汰；过大的单条结果不存储，照常返回。
条目上限设为零可禁用该类缓存。配置验证拒绝错误类型、负数与超范围容量。

这些容量是保守初始值，尚非多论文基准调优结果。缓存负载预算不是 Python
进程 RSS 硬上限，不覆盖对象头、临时深拷贝、字体原生内存、模型或渲染内存。
淘汰仅导致重新计算，不改变测量结果；专门测试零缓存和极小预算下的等价性。

### 终端与诊断

新增简洁英文事件，区分 `family_fit`、`fast_variant`、`exact_candidate`、
`visual_recovery`、`capacity_repair` 和 `content_optimizer`，显示开始/结束、
耗时、候选/轮次上限、搜索扩展及修复未采用的原因。保留外层 layout_optimizer
阶段和既有心跳，不误报为整个阶段完成。

循环内重复视觉尺寸 info 默认不逐条打印；真正的警告和错误仍保留。
`verbose_measurements: true` 可恢复细节。

新增 `layout_performance_report.json`，包括依赖版本、设置、缓存请求/命中/
计算/淘汰数、文本负载峰值、测量失败数、兼容回退与分层耗时。
最多保留 256 个子阶段记录，并明确标记截断；缓存键、原始论文文本和字体对象
不写入报告。递归计算和父子阶段耗时为 inclusive，不能相加当作阶段总耗时。

保存位置：

```text
output/<paper>/<session>/iterations/<N>/content/layout_performance_report.json
storage/critic_loop/campaigns/<campaign_id>/iterations/<N>/attempts/<attempt_id>/layout_performance_report.json
```

输出目录里的最新副本在文件系统 OSError 时只告警，报告留在内存供 Campaign
保存，避免掩盖真正生成错误。正常提交、已知拟合重试、生成异常均在原有唯一
attempt 目录保留报告。强制停止在报告持久化前放弃尝试时，不保证有 attempt
副本；原有强停、预算和知识提交语义未变。历史运行不会被自动补写报告。

## 验证

新增 `tests/test_layout_performance.py` 共 83 个测试用例，覆盖：

- 空白、显式换行、窄框、粗体、不同字体、Unicode、行内脚标、分式、
  小数宽度/字号、边距与精度的原实现逐项对照。
- 十二家族在 Explore、父布局约束 Improve、固定拓扑 Validate 下的真实
  LayoutAgent / Solver 编译结果或不可行报告完整相等。测试为可控成本使用
  小型科学模块和较小测试搜索预算，不修改生产配置。
- 配置/字体变化、计算中变化、返回对象修改、LRU 淘汰、零缓存、小负载预算、
  未知依赖版本、原始库错误、适配器编程错误与异常清理；初始/最终编译包装
  不能将适配器错误转换为普通几何重试。
- 独立 classic 路径不启用上下文；嵌套/复制线程上下文隔离；重试、提交、
  生成失败报告持久化及科学快照无诊断污染；报告写失败不覆盖原异常。

完整回归命令：

```bash
.venv/bin/python -m pytest -q
```

本次最终结果：393 passed，5 subtests passed；既有依赖弃用警告仍在。

### 已保存真实模块的 CPU 基准

读取已保存的 geospatial 论文 I2 海报中最长的三个模块，不改动原文件，
比较原始计算、新上下文首次计算、同上下文重复计算；三者返回字典完全相等，
测量失败均为零。

| 字符数 | 原始测量 | 优化首次测量 | 重复命中 | 首次加速比 |
| ---: | ---: | ---: | ---: | ---: |
| 1254 | 12.746 s | 1.767 s | 0.000430 s | 7.214× |
| 671 | 5.113 s | 1.036 s | 0.000356 s | 4.936× |
| 443 | 3.136 s | 0.747 s | 0.000361 s | 4.200× |

这是同一 Python 进程中模块级测量，不是进程冷启动或整个迭代的速度。
耗时会随 CPU 负载波动，不能据此宣称此前约 85 分钟的布局阶段必然缩短为
某个固定时长；搜索与模型修复仍有真实成本。

新增只读复测命令：

```bash
.venv/bin/python -m src.layout.benchmark_measurements \
  --candidate-dir output/<paper>/<session>/iterations/000002 --sample-limit 3
.venv/bin/python -m src.layout.benchmark_measurements --replay-input /path/to/replay.json
```

后者需要完整 JSON：`state`、`board`、`family_id`、`config`，包括尺寸、科学
状态、随机种子、Improve 父布局或 Validate 固定拓扑等真实输入。
它对照纯 Solver 的结果，而不是重新执行整个历史迭代。历史未保存的模型修复
中间 board 不能凭空重放，部分 state_snapshot 也不能代替完整输入。

## 使用与回退

默认启用，现有启动命令不变。已经运行的进程不会热更新，下一次启动才加载。

- `layout_performance.enabled: false`：完整高度和行数走原始计算，保留诊断计时。
- `layout_performance.reuse_wrapping: false`：保留完整结果复用，但精确 fitting
  调用原始库实现，便于分别定位问题。
- 不升级依赖、不改变 Campaign/LayoutSpec/rubric 版本、不迁移现有知识库。

本次未调用大模型、未进行 GPU 工作、未启动或修改用户的真实 Campaign/Batch。
已通过上述 CPU 对照与全项目回归，但不能据此保证所有未来论文、依赖环境或
外部服务绝无 bug。下一次真实循环应检查性能报告，验证整体耗时和视觉结果。
