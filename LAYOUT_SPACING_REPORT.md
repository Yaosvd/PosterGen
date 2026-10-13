# 海报标题间距与整体空白优化实施报告

## 范围与结论

本次针对已保存的 geospatial 论文 I1/I2 中三类真实问题：模块标题与内容过近、
跨 zone 的上下模块间空白过大、正文区底部额外空白过大。
实现从测量、编译、渲染复验到 Critic/Planner 反馈的完整约束链。
修改于 2026-10-12 开始，额度中断后于 2026-10-13 继续复查和验收。

规则对循环内十二个家族统一生效，不特殊优待三列式；不改变家族选择和
Explore 的多样性机制。独立 one-shot classic / Balancer 路径保留原有标题
测量和隐式段落行距，不参与新增几何微调、循环 RenderFit 或模板知识发布。

这不是承诺每次生成都能消除空白。无法安全修复的空白会明确进入评价和后续
改进；不能以缩小字体、编造内容、拉伸图片或把空白移到别处来换取“通过”。

## 实现内容

### 1. 统一循环标题的测量和渲染

新增 `src/layout/title_metrics.py`，定义 `loop_title_v1`。
循环 LayoutAgent 和 Renderer 使用同一组文本框边距，标题显式设置
`字号 × 1.20` 点的绝对行距、段前/段后零间距。
标题换行估算取消旧路径额外的粗体宽度放大，保留 0.98 的渲染宽度裕量，
高度取实际 fitting 与安全行数高度的较大值，并留 0.05 英寸保留量。
原字号不因放不下而任意缩小。

测量预先应用已允许的字体归一化/层级预设；字体归一化测量 Arial，层级预设
同时修正标题字号和 accent 占位。FontAgent 后的 Preflight 根据最终字体、
字号、粗体、宽度重新核验标题高度和最小标题内容间距，不能只相信旧测量值。

配置在 `config/poster_config.yaml:text_measurement.loop_section_title`。
最小实际标题内容间距默认是 `0.225 × 字号 / 72` 英寸；64 pt 时为约 0.20 英寸。
这是下限，不是要求所有标题后空白恰好相同。

### 2. 实际渲染标题复验与一次局部修正

`render_fit_report.json` 升至 schema v2。原有临时 PDF 导出同时检查模块标题，
不为正常候选额外重复导出 PDF。仅唯一匹配的 PDF 文本块可以形成硬证据。
短标题与重复标题按文本和位置匹配；无法唯一识别时标明 partial/inconclusive，
不能把提取失败当作溢出。

新增实际标题底部到首个正文块/图片框的间距检查。图片使用真实放置框，不宣称
识别图片内部的空白像素。确认标题溢出或间距不足时，Explore/Improve 最多
进行一次局部扩高：增加标题与模块容器高度，下移本模块内容及同 zone 后续模块。
不改科学文字、字体或图片宽高比，不改 LayoutSpec 的 zone 拓扑。

修正必须重新通过完整几何检查和 Improve 合同/删除保护，才允许重渲染。
未采用的试算不覆盖原 Preflight 报告。重渲染后再次测量；若已确认的问题缺少
新的匹配证据，记录 `RENDER_CORRECTION_UNVERIFIED`，不能静默清除旧失败。
渲染异常保留生成错误，仍走原有 generation-failure 路径，不伪装成质量拒绝。
采用后同步布局、区域统计、Preflight、修正审计及可见产物。

Validate 固定拓扑和 Improve 精确父布局回退不做该修正。正常循环已确认的
渲染失败仍沿用原重试预算语义；Validate 保留失败证据交给 Critic。

### 3. 方向邻接、空白分解与底边指标

`src/layout/whitespace.py` 输出 schema v2 composition 数据，保留旧字段，并新增：

- 分开统计横向与纵向物理邻接，不允许近距离侧邻掩盖较大的上下间隙。
- 扣除中间模块遮挡的投影区间；剩余投影不足 20% 的细小通道不当作贯穿海报
  的巨型邻接空白，其影响仍由空矩形/底边指标记录。
- 跨 zone 纵向空白分解为：内容框尾部、上方 zone 未使用高度、zone gutter、
  下方模块起点偏移、下方可见内容 inset。缺失历史 zone 几何时标明无法分解。
- 额外底部空白的宽度加权均值、最大值、整宽底部空带以及测量覆盖率。
  指标以正文区底边为基准，不把既定外边距算作错误，不强迫各模块底边齐平。

实际字形可用时用于可见模块包络，其他内容用计划框，明确标记混合口径。
图片框永远不能误用同 ID 的正文测量框。
Solver/Improve 比较仍使用编译口径；修正后实际字形口径另存
`rendered_composition_whitespace`，避免不同口径互相比较造成误判。
新增指标只有双方都有数据时才参与非回退比较，历史缺失值不伪装成零。

### 4. 有界内容感知几何微调

新增 `src/layout/composition_refinement.py`，在已有可行候选上尝试释放上方
zone 的实测剩余高度、压缩过大的结构 gutter，并把空间重新分配给下方 zone。
支持同宽上下区域及跨列模块连接多个下方卡片的共享行边界。
每个 `fit_family_layout` 调用最多 2 轮、每轮 4 个精确候选；没有收益即停止。
保留 zone 身份、语义角色、整体外边界和水平几何，必须满足家族拓扑。
使用既有精确回填/编译能力恢复可放入的原始已验证 claim 和批准视觉资产，
不调用新模型，不在几何搜索里改写论文文字。

只采用精确评分更好、可见内容不丢失、整体空白不退化，且 Improve 合同与
删除保护允许的结果。Validate 固定 zones 与精确父布局回退禁用微调。
几何指纹、variant ID、mutation trace 和最终 spec 一起更新。
`layout_feasibility_report.json` 保存 `composition_refinement`、前后测量和
`search_scoring_version: multifamily_composition_v2`。

新增搜索评分项关注纵向模块间隙和额外底部空白。它不是 Critic 的海报总分，
也不是模板的独立设计分。

### 5. 修复局部内容改善被丢弃的问题

容量修复以前主要要求“全局最差 zone 利用率提高至少 0.03”。如果最差 zone
不变，另一个模块真实改善也可能被丢弃。现在可接受下列任一实测收益：

- 最差 zone 利用率提高至少 0.03；或已有 zone 利用率提高至少 0.02；
- zone 底部空白减少至少 0.20 英寸；或整体纵向/底边指标改善至少 0.20 英寸。

同时要求既有 zone 的利用率及最差利用率不下降超过 0.005，不丢失已有可见
claim/视觉资产，新增内容确实出现在拟合结果中，且整体空白通过非回退保护。
不能通过缩小预算框、移动空白或换成更稀疏的海报假装增加内容成功。
`capacity_repair_report.json` schema v3 的 `fit_comparison` 记录前后分区与整体指标。
原修复轮次、验证流程、未提交内容隔离和科学基础不变。

### 6. Critic 与 Planner

Critic 版本为 `4.3.0`，rubric 为 `academic_poster_multifamily_v5`，报告仍为
schema v3。SectionFit 增加跨 zone 纵向空白与正文底部闭合评分/反馈，问题包括
`CROSS-ZONE-GAP-*`、`POSTER-BOTTOM-WHITESPACE`。
RenderFit 的标题间距问题是实际几何证据；一般空白过大仍是评分/改进意见，
原有空 zone、严重闲置 zone、物理溢出的硬门槛不被取消。
无相邻模块或测量不完整时，不能以空列表推断“所有间距都合格”。

RevisionPlanner 收到空白来源分解，并能提出受控的 zone budget 和有依据的
内容补充请求；仅改变同 zone 内 `set_section_gap` 不能解决跨 zone 空白。
提示词明确优先修复实际标题拥挤，不允许填充废话、任意缩字或拉伸图像。

七维权重、78 分归档门槛、海报/模板统一保存门槛、L0–L3 检索限制均不变。
模板独立 `structural_template_v1` 的拓扑与视觉子指标定义未改变，既有模板设计
分和预览不重新写入。Validate 仍只追加原模板的验证证据，不创建新模板。

rubric 变化会触发现有版本隔离：旧海报、反馈、模板和验证证据保留，但旧 rubric
的最好/可改进候选不能当作新 rubric 同分比较；旧全局 Critic priors 也不冒充
新规则经验。首次恢复纯 Improve 可能因为没有兼容基准而不可用，应先以新规则
探索建立候选，而不是人为重标旧分。本文测试没有执行真实 Campaign 的迁移。

## 与提速方案的关系

保留 attempt-local 有界 LRU、精确缓存键、字体/配置身份、私有 fitting 版本
适配和退出清理。新增标题测量及精确微调复用同一布局测量上下文。
FontAgent 后和重渲染后的核验不继承旧上下文，因此不会用旧样式的缓存放行。
新几何微调作为 `composition_refinement` 子阶段进入原性能报告。

`layout_performance.enabled=false` 只关闭计算复用，不关闭本次质量规则。
新规则下缓存开/关结果必须一致，不要求结果与修正前的旧标题/旧评分一致。
新增最多 8 个精确候选是每次拟合调用的上限；容量修复的重拟合仍有自己的
既有有界预算，不能把 8 误解为整个 iteration 的额外计算总上限。
极少数标题修正增加一次渲染/PDF 测量；正常通过的候选不增加该次重渲染。
因此不能承诺本次质量优化对总耗时为零影响。

## 历史复验与验证边界

对已保存 I1/I2 PPTX 进行只读 LibreOffice/PyMuPDF 审计，核对前后文件摘要。
I1 有 6 个标题框溢出、4 处标题间距不足；I2 有 4 个标题框溢出、4 处标题间距
不足。这说明不是单次生成的随机视觉感受，而是原约束没有完整覆盖实际结果。
I2 两处跨 zone 可见纵向空白约 2.49/2.56 英寸，正文额外底部空白均值约 1.89 英寸。

在临时目录使用原 I2 已验证内容、原 zone 几何和新测量规则重编译，并用真实
LibreOffice 渲染复验。不执行模型、内容生成、Campaign 提交或模板注册。
标题间距、底部指标和剩余空白的具体验收结果见最终验证记录。
边界微调如果只把中部空白转移到底部，应当不采用；这不是允许放宽保护的理由。

新增 `tests/test_layout_spacing.py` 覆盖标题缓存等价性、实际 LibreOffice 一到
多行标题的 PPTX/PDF/PNG、最终字体 Preflight、重复标题的模糊匹配、一次修正、
修正不可行/合同拒绝/提取不完整/渲染失败、方向邻接、遮挡、底边、局部修复
收益与非回退、共享行边界、候选预算与配置边界。既有十二家族缓存等价性、
Validate 拓扑、独立 classic、Improve 合同和全项目测试一并回归。

没有运行真实大模型循环、没有占用 GPU，也没有改写历史海报或真实知识库。
测试不能证明未来任意论文或外部依赖环境绝无 bug，真实多论文视觉质量和
整个 layout 阶段耗时仍需后续运行验证。

## 只读审计命令与配置

```bash
.venv/bin/python -m src.layout.spacing_audit \
  --candidate-dir /path/to/candidate
```

历史平铺归档没有 LayoutSpec 时，必须显式提供它，不能凭空猜 zone 几何：

```bash
.venv/bin/python -m src.layout.spacing_audit \
  --candidate-dir /path/to/rejected_bundle \
  --layout-spec /path/to/original/content/layout_spec.json
```

命令仅向终端输出 JSON，临时 PDF 自动清理，不启动循环、不写回旧报告。
新运行的审计位置为 `content/render_fit_report.json`、
`content/critic_report.json` 内的 SectionFit metadata；唯一 attempt 目录保存
原有对应报告。模板 density metadata 保留 gap 的 null/partial 状态，不强制转成布尔值。
几何微调在 `config/critic_config.yaml:composition_refinement` 配置，可用
`enabled: false` 单独禁用；质量测量和 Critic 规则仍保留。
已经启动的进程不会因修改源码自动切换，新规则在下次启动时加载。

## 最终验证记录

历史 I1/I2 归档和 LayoutSpec 文件的前后 SHA-256 摘要一致。
I2 离线重编译的真实验收结果：

- 编译 Preflight 通过；实际 RenderFit 通过，无标题框溢出或标题内容间距问题；
  已实际生成 PPTX、PNG 并检查 PNG，不是仅比较内部 JSON。
- Performance 标题到图片间距约 0.8837 → 0.5003 英寸；Ablation 标题约
  0.0128 → 0.5011 英寸；Multi-Modal 标题到正文约 -0.0127 → 0.6724 英寸。
- 额外底部空白均值约 1.8917 → 1.4034 英寸；最终图仍保留既定外边距。
- 所有原可见 claim ID 和视觉资产 ID 都保留，没有删减内容或调整科学文字。
- 固定旧 zone 及原内容下，左侧跨 zone 可见空白约 2.4891 → 2.8721 英寸，
  右侧约 2.5638 → 1.8808 英寸。因此不能声称这张旧布局已消除所有大空白。
  左侧变化与移除上方标题的过量高度预留有关，不应恢复错误标题估算来掩盖。
  新规则已输出 `CROSS-ZONE-GAP-*` 和 `POSTER-BOTTOM-WHITESPACE`，交给后续
  grounded 内容/布局优化，不再误报全部间距正常。
- 4 个边界微调候选虽可减小中部间隙，却使底部空白或整体评分退化，均未采用。
  最终明确为 `no_safe_gain`；测试没有以降低非回退门槛强行取得几何微调成功。

完整回归命令为 `.venv/bin/python -m pytest -q`：

```text
442 passed, 4 warnings, 5 subtests passed in 412.10s (0:06:52)
```

4 条 warning 来自 Marker、Surya、LangGraph 和 Starlette 的依赖弃用提示，
没有测试失败。此前针对间距、Improve 合同和 RenderFit 的专项回归为
87 passed、2 warnings。`git diff --check` 通过，审计 CLI 的帮助入口验证通过。
