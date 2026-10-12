# 海报生成异常与提交一致性修复报告

日期：2026-10-12。此报告描述已落实的代码、数据契约与验收范围。

## 1. 已确认的原因

新建 geospatial Campaign 的 I1 在 `result_dashboard_cards` 家族完成初始
容量搜索后，进入稀疏区域的自动内容补充。`add_existing_claim` 没有显式
`claim_id`，需要自动寻找相关且未展示的已验证 claim。
`_visible_claim_ids()` 返回列表，而新增排除逻辑使用了列表与集合的并集，
触发 `TypeError: unsupported operand type(s) for |: 'list' and 'set'`。

随后发生了三层连锁问题：

1. Layout 包装层把异常转为 `errors`，丢失根堆栈且未标记已知容量失败。
2. 后续渲染未运行，控制器却继续调用 Critic。缺少 PPTX/PNG 的候选得到
   “拒绝”分数；这不是对真实海报视觉效果的评价。
3. 拒绝存储先写 journal、提前增加计数，再发现 PPTX 不存在而报错。
   因为没有 `COMPLETED.json`，该次迭代没有提交，但留下了虚假的拒绝计数
   和一条提前写入的历史 journal。

根因是代码回归和流程保护不足，不是 GPU 配置问题，也不是家族本身被证明不可用。

## 2. 内容补充修复

`src/agents/content_optimizer.py` 只在并集处执行 `set(visible)`，保留原 helper
的列表接口与顺序语义。自动选择仍排除已展示 claim 和分支明确删除的根 claim，
仍要求模块相关性；没有适合 claim 时安全不修改。基础科学 claims 不变，
新变体和补充证据继续走原有验证与放置门槛。

## 3. 生成失败与评价拒绝分离

新增 `src/workflow/generation_failure.py`，负责根因捕获与渲染就绪检查。
每个 attempt 开始清空 `attempt_failure_report`，不继承父候选故障。

异常报告位置：

```text
storage/critic_loop/campaigns/<campaign>/iterations/<N>/attempts/<attempt>/
  attempt_failure_report.json
  layout_feasibility_report.json
  layout_preflight_report.json
  capacity_repair_report.json
```

报告包含 Campaign、Batch、iteration、attempt、candidate、family、agent、
phase、原异常类型/消息/堆栈、是否可自动重试、是否消费预算。只记录异常栈，
不捕获 locals、提示词、模型响应或整段科学内容。实际异常消息/源代码行仍可能
含业务信息，排障文件应作为本地运行数据管理，不提交到 Git。

Layout 在可选内容修复之前保存初始 feasibility 结果；容量修复开始时即挂接 audit，
异常不会抹去此前测量。内层 ContentOptimizer 的根因不会被外层通用异常覆盖。
Renderer 同样保留原异常。终端保持简洁英文，完整堆栈写入 `run.log` 和故障报告。

| 情况 | 现在的处理 |
| --- | --- |
| 已知 Explore 容量、preflight、render-fit 失败 | 原有有界换家族/重试，同一全局 iteration，不消费预算 |
| 已知 Improve 几何失败 | 原有同分支重试、精确父候选回退或隔离策略 |
| 已知 Validate preflight 失败 | 原有未评分验证结果，提交后消费一次验证尝试，不计海报接受/拒绝 |
| 未知 TypeError 等程序异常 | 立即安全失败，不调用 Critic，不尝试掩盖为换家族重试 |
| 真实已渲染候选未通过 Critic | 正常提交拒绝结果、完整诊断与设计反馈 |

进入 Critic 前必须满足：candidate 身份与当前 attempt 一致；状态为 `rendered`；
PPTX 和 PNG 位于本次候选目录内、真实存在且非空。父候选文件不能代替当前输出。
这里只检查生成就绪，不代替 Critic 对文件可解析性、科学性、几何和质量的检查。

## 4. 提交一致性与恢复

`COMPLETED.json` 仍是唯一提交点。正常结果保存前使用 draft 的 loop、Batch、
Portfolio 和 best 状态；提交前失败恢复原有计数、最佳候选、调度计数以及已提交的
科学内容 banks/selection，清理该候选的 pending bundle。失败不推进 Lineage 或
全局设计记忆。当前失败 iteration/attempt 编号仍保留用于排障。

新增 `commit_runtime_state.json`，写在提交标记之前，包含本次提交后的 runtime
projection 和明确的 Batch 迭代 ledger；提交标记绑定其 digest。没有提交标记时
此文件没有权威性。提交后保存摘要中断，恢复程序从标记及 outcome 重建计数，
从验证过的 runtime projection 恢复 Portfolio、best、策略和 Batch 派生统计，
无需重新生成海报或重复消费次数。

恢复保留当前 Batch 的冻结策略、最新 resume 信息、恢复隔离策略和 lifecycle。
失败或归档状态不会仅因达到预算而被迁移为 `COMPLETED`。历史 attempt 已经
`ABANDONED` 时保留原 reason，不覆盖为通用中断原因。
历史缺段、关键 outcome/report 缺失、或新提交绑定的 runtime projection 缺失/
摘要不符时 fail closed，不能靠猜测把真实工作清零。旧提交没有 runtime projection
时可以从完整 outcome 历史证明计数，但不能凭空恢复当时未保存的完整 Portfolio。

## 5. 拒绝 journal 的提交边界

`LoopStorage.record_rejection()` 只暂存完整诊断，不再提前追加正式 journal。
提交后通过 `publish_rejection_record()` 从实际提交的 outcome/report 生成记录。
Campaign/iteration/candidate 构成幂等身份；锁内检查并追加，写后 flush/fsync。
启动重放会补齐遗漏记录；即使追加后、下一步发布前中断也不会重复追加。

Validate、Improve no-change 回退和未提交候选不生成普通拒绝 journal。
已发布拒绝诊断仍遵守原有“用户删除后不自动重建”的策略。
此历史 journal 不参与 Planner 的全局设计知识检索；真正的全局设计事件仍只
来自提交后的设计结果。

## 6. 历史数据纠正与操作

新增不调用模型的命令：

```bash
.venv/bin/python -m src.workflow.reconcile_campaign --campaign-id <campaign_id>
```

可选 `--store-root` 指定本地 store。命令取得 Campaign 独占 lease，不能与该
Campaign 的运行进程并行写入。它不启动 Batch、不修改科学基础、不删除历史，
也不会把失败 Batch 解锁成可续跑状态。

本次仅针对已确认出错的 Campaign：

```text
Active_Geospatial_Search_for_Efficient_Tenant_Ev_3ea24642642e_f080e8
```

它没有提交标记，因此纠正后 accepted/rejected/template 都是 0；旧 Batch 1
继续保留 `FAILED_REQUIRES_USER` 和 0/100，旧 attempt 保留 `ABANDONED` /
`iteration_exception`。科学基础、原始 run.log、历史 journal 原文保留。
计数纠正证据写在 `campaigns/<id>/accounting_reconciliation.json`；提前写入的
journal 通过 `design_memory/rejection_memory_corrections.jsonl` 追加失效证明，
不删除或改写原行。不处理其他旧 Campaign，不重置全局模板库/全局设计知识。

以后用户在该 Campaign 新开 Batch，会得到 `batch_0002`，复用科学基础，从
未提交的全局 I1 建立新 attempt；不是重新解析论文，也不是恢复失败 Batch 1。
本次没有自动启动新 Batch。

## 7. 修改位置

- `content_optimizer.py`：隐式选择 claim 的列表/集合修复。
- `layout_with_balancer.py`、`capacity_repair.py`：修复前报告与异常 audit。
- `renderer.py`、`optimization_loop.py`：保留异常根因，停止生成后续阶段。
- `generation_failure.py`、`poster_state.py`：故障数据契约与渲染就绪门槛。
- `campaign_runner.py`：错误分流、draft 计数回滚与提交后 journal 发布/重放。
- `campaign.py`：digest-bound 提交 projection、派生统计恢复与终态保护。
- `library.py`：仅提交后追加 journal、幂等去重、历史非破坏纠正。
- `reconcile_campaign.py`：单 Campaign 的离线修复命令。
- tests、README、AGENTS、本报告、容量修复报告：验收与持续上下文。

## 8. 验收与边界

CPU-only 测试覆盖真实 CapacityActionPlanner → GroundedContentOptimizer 的隐式
claim 选择、排除与无候选 no-op；Layout/Renderer 根因保留；缺图、未渲染、
候选身份错误；接受/拒绝路径的暂存、Portfolio、提交点故障；提交后重放；
journal 追加后崩溃去重；projection 损坏/丢失；终态保留与历史纠正。
已有回归继续覆盖 Validate 未评分尝试、Improve no-change、交错 Batch、
用户删除拒绝诊断、科学 grounding、模板与全局设计知识边界。

全量测试：`286 passed, 5 subtests passed`。运行时禁用 CUDA，未调用 Qwen，
未启动完整海报生成，未分配 GPU 3 或 GPU 5。
通过测试说明已复现问题及覆盖的边界得到验证，不等于数学意义上的整个项目零 bug；
仍需要后续真实运行验证各家族视觉效果。磁盘整体不可写、外部服务故障等也不能
由单元测试保证永不发生。Critic 权重、门槛、布局家族、多样性策略和独立经典
三列入口未被此次修复重新设定。
