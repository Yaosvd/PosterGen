# CV 海报规则归纳记录

2026-11-26 · 版本 1.0.0

2026-11-26 已撤回 CV 规则初稿。以下为该版的历史分析，文中编号对应本地提交 `8ffe4b588`。[逐篇观察表](review_index.tsv)记录了当时核对的材料。

## 样本和审阅深度

按照正式清单的 `research_category == "CV"` 取全部 362 对。190 对来自 ACL 来源记录，172 对来自 arXiv 来源记录。按会议记录细分为 EMNLP 137 对、AACL-IJCNLP 53 对、NeurIPS 159 对、CVPR 11 对、ICML 2 对。本库的 CV 包含多模态推理、音频、测量及综述，覆盖范围比仅看图像生成与识别更宽。

- 每对都按清单取论文和配套海报，以 SHA-256 核对两份原件。使用 PyMuPDF 逐页提取 362 篇论文共 8,941 页文本，渲染或解码全部单页海报。整版浏览使用 23 张联系表，逐张记录一项可见组织方式；对下列案例再放大海报核对具体面板，并回查论文。解析时个别 PDF 出现 MuPDF 绘图语法提示，全部产出了审阅画面。语法提示和缩略图的分辨率限制都可能影响局部细节。
- 190 张 PDF 海报中，183 张文字层达到 50 个空白分隔词。余下 7 张及 172 张 PNG 使用本机 Tesseract 英文 OCR，179 张均取得超过 50 词的文本。这个阈值只用于选择提取方式。OCR 的标点、上下标、表格读序和数值可能有误。案例中的关键数字用原文和成图核对。
- 对每篇计算海报文本和论文参考文献标题之前正文的术语组交集。索引以正式清单的论文哈希为键，保留题名、页数、海报文字来源、画面速记与双侧出现的术语组。画面速记只描述这张海报的一项展示选择。术语组可以为空，主要用于找同类材料；它们没有被用作质量分、违规计数或论文与海报语义相符的证明。
- 以渲染画幅的宽高计，横版 179 张、竖版 182 张、正方形 1 张。横竖版均有将读者快速带到证据的实例，因此规则规定图、标签和主张的关系，保留对栏数、横竖及面板顺序的选择。

## 从材料到规则

**先判定读者需要核实什么。** BridgeMVS 的读者要能将深度估计的改进指回同一场景；RAVEN-Bench 的读者要先理解一题可用什么模态，才读得懂配对输入的收益；综述的贡献则可能是分类轴和跨类发现。主图应随论文的证据而变。CV-P01、P02 先做选材，P03–P14、P16、P17 按贡献类型和证据条件选用，P15、P18 处理最终版面。未触发的规则无需填造相应模块。

**把一次完整比较保留下来。** 海报常从多页实验中选取一组输入、方法和输出。压缩得好，读者仍知道什么发生变化、什么保持相同，以及差异可以支持何种判断。删掉指令、同步时刻、工作点或验证集名，就可能把正确材料拼成错误结论。多个拒绝条款由这些可核查的破坏条件推导。代表案例包括正确处理、存在取舍的官方设计和由证据推导的风险；拒绝条款不意味着案例作者犯了相应错误。

**给原始材料留出空间。** 有些原海报值得学习的是方法图，有些是主表旁的一条读数或一个标好的放大框；同一张海报也可能让装饰或重复说明挤占证据。生成时优先保留最短而充分的解释。若证据依赖真正的像素而 Markdown 只有描述，模型应改用有原文依据的文字或表格，并收窄视觉主张。PDF、PPTX 的文件结构要求由生成程序另行规定。

## 可回查的代表案例

下列页码按 PDF 物理页计。每条区分论文依据、官方海报选择以及转成生成规则时应保留的条件。

- **Lost on Campus: Evaluating Embodied Spatial Reasoning of Vision-Language Models in the Wild**。第 6、8 页分别报告导航成功和诊断题表现。海报中间给闭环导航，右侧给诊断问答，最下面并列摘要数字。25.7% 和 39.6% 属于不同任务，转成大号数字时仍需随各自标签走。 对应 P01、P02、P08、P10、R04。[论文](../../../data/papers/Paper2Poster/CV/Lost%20on%20Campus%3A%20Evaluating%20Embodied%20Spatial%20Reasoning%20of%20Vision-Language%20Models%20in%20the%20Wild/paper.pdf) · [海报](../../../data/papers/Paper2Poster/CV/Lost%20on%20Campus%3A%20Evaluating%20Embodied%20Spatial%20Reasoning%20of%20Vision-Language%20Models%20in%20the%20Wild/poster.png)

- **BridgeMVS: Bridging Multi-View Stereo and Monodepth via Bidirectional Dynamic Fusion**。论文第 2 页的总体框架和第 7 页的比较，可与海报上部两条分支、下部深度图对读。左侧把单目误差与公制深度分行并各给色条。可以简化两支的内部层，必须保留相互传递的方向，以及不同图中颜色表示哪个量。 对应 P03、P05、R03、R12。[论文](../../../data/papers/Paper2Poster/CV/BridgeMVS%3A%20Bridging%20Multi-View%20Stereo%20and%20Monodepth%20via%20Bidirectional%20Dynamic%20Fusion/paper.pdf) · [海报](../../../data/papers/Paper2Poster/CV/BridgeMVS%3A%20Bridging%20Multi-View%20Stereo%20and%20Monodepth%20via%20Bidirectional%20Dynamic%20Fusion/poster.png)

- **SUPERVISE: A Unified Framework for Standardized and Reproducible Superpixel Evaluation**。第 1–3 页说明实际超像素数与评测协议。海报左侧用请求规模与实际规模的差异说明问题，中部解释归一化，右侧才给表现曲线。作排名前要让读者看到比较尺度。 对应 P08、P10、R04。[论文](../../../data/papers/Paper2Poster/CV/SUPERVISE%3A%20A%20Unified%20Framework%20for%20Standardized%20and%20Reproducible%20Superpixel%20Evaluation/paper.pdf) · [海报](../../../data/papers/Paper2Poster/CV/SUPERVISE%3A%20A%20Unified%20Framework%20for%20Standardized%20and%20Reproducible%20Superpixel%20Evaluation/poster.png)

- **RAVEN-Bench: A Paired EO-IR Video QA Benchmark for Aerial Multimodal Understanding**。第 1–4 页定义同步 EO–IR 视频和按模态审查的问题，第 8 页可回查打乱输入的控制。海报中部把两条同步帧序列与示例题相邻放置，右侧拆开仅 EO、仅 IR、联合输入。删掉模态或题组会改变读者对配对收益的理解。 对应 P06、P08、P09、R02、R07。[论文](../../../data/papers/Paper2Poster/CV/RAVEN-Bench%3A%20A%20Paired%20EO-IR%20Video%20QA%20Benchmark%20for%20Aerial%20Multimodal%20Understanding/paper.pdf) · [海报](../../../data/papers/Paper2Poster/CV/RAVEN-Bench%3A%20A%20Paired%20EO-IR%20Video%20QA%20Benchmark%20for%20Aerial%20Multimodal%20Understanding/poster.png)

- **Camera3R: Feed-Forward 3D Reconstruction from Heterogeneous Camera Models**。第 1 页说明混合相机带来的重建问题。海报右侧按混合输入、重建、真值对齐，左侧另给不同相机输入上的失败示例；相机视图差异与方法差异需要各自的标签。 对应 P04、P07、R02、R03。[论文](../../../data/papers/Paper2Poster/CV/Camera3R%3A%20Feed-Forward%203D%20Reconstruction%20from%20Heterogeneous%20Camera%20Models/paper.pdf) · [海报](../../../data/papers/Paper2Poster/CV/Camera3R%3A%20Feed-Forward%203D%20Reconstruction%20from%20Heterogeneous%20Camera%20Models/poster.png)

- **Disentangling Where and When: Factored Spatio-Temporal Explanations for Video Action Recognition**。第 1 页区分表观掩膜与运动掩膜。海报中下部保留同一片段的多行输出，右侧把外观和运动指标分开。单帧能展示掩膜的位置，判断动作对时间的依赖还需要帧序或论文的扰动实验。 对应 P05、P06、P17、R05、R06。[论文](../../../data/papers/Paper2Poster/CV/Disentangling%20Where%20and%20When%3A%20Factored%20Spatio-Temporal%20Explanations%20for%20Video%20Action%20Recognition/paper.pdf) · [海报](../../../data/papers/Paper2Poster/CV/Disentangling%20Where%20and%20When%3A%20Factored%20Spatio-Temporal%20Explanations%20for%20Video%20Action%20Recognition/poster.png)

- **Encoded but Not Routed: Explaining the Table-Chart Gap in Scientific Claim Verification**。第 5 页讨论相关证据的限制，第 7 页可查表格条件的准确率。海报顶部保持主张和数字相同，突出表格与图形的任务表现；下面另给探针 AUROC，并在结论附近说明解释限度。生成时要分开任务准确率、可解码性和因果使用。 对应 P09、P10、P17、R04、R05。[论文](../../../data/papers/Paper2Poster/CV/Encoded%20but%20Not%20Routed%3A%20Explaining%20the%20Table-Chart%20Gap%20in%20Scientific%20Claim%20Verification/paper.pdf) · [海报](../../../data/papers/Paper2Poster/CV/Encoded%20but%20Not%20Routed%3A%20Explaining%20the%20Table-Chart%20Gap%20in%20Scientific%20Claim%20Verification/poster.pdf)

- **Large Language and Vision-Language Models as World Models: A Survey**。论文摘要区分理论体系与应用分类。海报左侧提供纳入范围和筛选过程，右侧分两组展示类别；左下矩阵说明高、中、低是异质研究的定性综合。综述的核心证据可以是一套能读懂的分类和比较依据。 对应 P02、P14、R04、R11。[论文](../../../data/papers/Paper2Poster/CV/Large%20Language%20and%20Vision-Language%20Models%20as%20World%20Models%3A%20A%20Survey/paper.pdf) · [海报](../../../data/papers/Paper2Poster/CV/Large%20Language%20and%20Vision-Language%20Models%20as%20World%20Models%3A%20A%20Survey/poster.pdf)

- **StitchEdit: Stitching Depth Priors into Image Editors via Per-Layer Gradient Probing**。第 7–9 页可查用户偏好与深度一致性结果。海报下部每组给编辑指令，统一输入与各方法的列序；右侧分别列出四项指标、人评和训练策略消融。空间有限时保留一组完整编辑对照，通常比多摆几张孤立结果更能检验方法。 对应 P04、P12、P16、P18、R02、R10。[论文](../../../data/papers/Paper2Poster/CV/StitchEdit%3A%20Stitching%20Depth%20Priors%20into%20Image%20Editors%20via%20Per-Layer%20Gradient%20Probing/paper.pdf) · [海报](../../../data/papers/Paper2Poster/CV/StitchEdit%3A%20Stitching%20Depth%20Priors%20into%20Image%20Editors%20via%20Per-Layer%20Gradient%20Probing/poster.png)

- **FlashRelight: Portrait Video Relighting with Dynamic Lighting**。第 1、3、5 页可查光照控制与参考视频。右半页把环境图、文字、参考视频三种控制分区；左半页交代去光照的中间产物。抽出一排时要保留输入角色与控制类型，以免把中间状态当最终结果。 对应 P03、P06、R06、R10。[论文](../../../data/papers/Paper2Poster/CV/FlashRelight%3A%20Portrait%20Video%20Relighting%20with%20Dynamic%20Lighting/paper.pdf) · [海报](../../../data/papers/Paper2Poster/CV/FlashRelight%3A%20Portrait%20Video%20Relighting%20with%20Dynamic%20Lighting/poster.png)

- **ReuScope: Auditing Data Reuse and Evaluation Sensitivity in Capsule Vision 2024**。第 1 页限定可识别的共享单位，第 3、5 页区分训练数据变化和验证总体变化。海报中央画出同一比较在不同总体的读数，主例为 −21.32 与 +1.38 个百分点。共享录像可以核定，共享患者人数缺乏标识；两个结论不能互换。 对应 P12、P13、R04、R05、R07、R11。[论文](../../../data/papers/Paper2Poster/CV/ReuScope%3A%20Auditing%20Data%20Reuse%20and%20Evaluation%20Sensitivity%20in%20Capsule%20Vision%202024/paper.pdf) · [海报](../../../data/papers/Paper2Poster/CV/ReuScope%3A%20Auditing%20Data%20Reuse%20and%20Evaluation%20Sensitivity%20in%20Capsule%20Vision%202024/poster.png)

- **BudSplat: Feed-forward 3D Gaussian Splatting under a Rendering Budget**。第 8 页可查不同基元预算下的指标。海报首要数字是约 20 倍少的高斯基元，同区给 23.52 与 23.48 dB PSNR；右表仍保留该工作点的 LPIPS 差异，底部红框指定观察区域。不能把基元倍数直接换写成耗时倍数。 对应 P05、P10、P11、R04、R08。[论文](../../../data/papers/Paper2Poster/CV/BudSplat%3A%20Feed-forward%203D%20Gaussian%20Splatting%20under%20a%20Rendering%20Budget/paper.pdf) · [海报](../../../data/papers/Paper2Poster/CV/BudSplat%3A%20Feed-forward%203D%20Gaussian%20Splatting%20under%20a%20Rendering%20Budget/poster.png)

- **Temporal Gains, Spatial Costs: Revisiting Video Fine-Tuning in Multimodal Large Language Models**。第 1–3 页交代视频微调可能使静态能力下降。题区下方用一组图像问答和一组视频问答说明矛盾；各实验区将两类任务成对显示。这里保留相反方向本身就是保留论文发现。 对应 P09、P11、P13、R04、R11。[论文](../../../data/papers/Paper2Poster/CV/Temporal%20Gains%2C%20Spatial%20Costs%3A%20Revisiting%20Video%20Fine-Tuning%20in%20Multimodal%20Large%20Language%20Models/paper.pdf) · [海报](../../../data/papers/Paper2Poster/CV/Temporal%20Gains%2C%20Spatial%20Costs%3A%20Revisiting%20Video%20Fine-Tuning%20in%20Multimodal%20Large%20Language%20Models/poster.pdf)

- **Perceptually Better, Semantically Worse: Measuring Speech Enhancement Impact on LLM-Based Voice Systems**。第 1、3、4 页可查输出偏离率及实验条件。海报下方把 MetricGAN+ 的感知指标与意图输出变化并列，配原录音的声谱和转写个例。0.135 和 0.318 衡量的是相对干净输入的输出偏离率，该数字不能写成感知质量改善或任务准确率。 对应 P10、P13、P14、R04、R07。[论文](../../../data/papers/Paper2Poster/CV/Perceptually%20Better%2C%20Semantically%20Worse%3A%20Measuring%20Speech%20Enhancement%20Impact%20on%20LLM-Based%20Voice%20Systems/paper.pdf) · [海报](../../../data/papers/Paper2Poster/CV/Perceptually%20Better%2C%20Semantically%20Worse%3A%20Measuring%20Speech%20Enhancement%20Impact%20on%20LLM-Based%20Voice%20Systems/poster.pdf)

- **Mind the Motions: Benchmarking Theory-of-Mind in Everyday Body Language**。论文第 7 页讨论过度解读。官方海报中央插画引入任务，右上给真实片段，底部分别用表和堆叠条说明困难与误判。可学习这种分工；对新海报，如果缩放后底部证据难读，应当先将版面从插画移给任务例和诊断结果。 对应 P02、P15、P18、R09。[论文](../../../data/papers/Paper2Poster/CV/Mind%20the%20Motions%3A%20Benchmarking%20Theory-of-Mind%20in%20Everyday%20Body%20Language/paper.pdf) · [海报](../../../data/papers/Paper2Poster/CV/Mind%20the%20Motions%3A%20Benchmarking%20Theory-of-Mind%20in%20Everyday%20Body%20Language/poster.pdf)

- **Dimple: Discrete Diffusion Parallel Generation for Large Multimodal Modal**。论文第 1 页区分并行解码和预填充。海报速度区也分别报两种加速；但右上等高面板中的结果表只占很小一部分，表与说明间留有大块空白。可保留两种速度口径，把可回收的空间分给要读的数值。 对应 P11、P15、R08、R09、R12。[论文](../../../data/papers/Paper2Poster/CV/Dimple%3A%20Discrete%20Diffusion%20Parallel%20Generation%20for%20Large%20Multimodal%20Modal/paper.pdf) · [海报](../../../data/papers/Paper2Poster/CV/Dimple%3A%20Discrete%20Diffusion%20Parallel%20Generation%20for%20Large%20Multimodal%20Modal/poster.pdf)

- **Decomposing Visual Histories with Vision-Language Agents: Hierarchical Temporal Guidance for Compositional Image Generation**。论文第 9 页图 3 给目标、四个参考和生成结果。海报中央方法图清楚展示去噪阶段，左下的贴纸案例却仅以文字说明哪些参考相关。这是明确的取舍：若要让读者检验图像身份保持，优先选论文已有的案例图；只有文字时，收窄为对论文结果的陈述。 对应 P03、P04、P18、R01、R09、R10。[论文](../../../data/papers/Paper2Poster/CV/Decomposing%20Visual%20Histories%20with%20Vision-Language%20Agents%3A%20Hierarchical%20Temporal%20Guidance%20for%20Compositional%20Image%20Generation/paper.pdf) · [海报](../../../data/papers/Paper2Poster/CV/Decomposing%20Visual%20Histories%20with%20Vision-Language%20Agents%3A%20Hierarchical%20Temporal%20Guidance%20for%20Compositional%20Image%20Generation/poster.pdf)

- **What Sketches Tell Us about LVLMs: Conventions, Grounding, and Localisation**。第 3 页将绘画顺序、空间定位、内部层读出放在同一研究框架。海报中央直接比较人的笔画顺序、模型顺序与注意图，左边概述，右边给读数。可借用先扫读、再细读的层次；对有多个测量的工作，每项发现仍需自己的证据。 对应 P01、P05、P15、P17、P18、R05。[论文](../../../data/papers/Paper2Poster/CV/What%20Sketches%20Tell%20Us%20about%20LVLMs%3A%20Conventions%2C%20Grounding%2C%20and%20Localisation/paper.pdf) · [海报](../../../data/papers/Paper2Poster/CV/What%20Sketches%20Tell%20Us%20about%20LVLMs%3A%20Conventions%2C%20Grounding%2C%20and%20Localisation/poster.png)

- **LR-V2X: Loss Resilient Collaborative Perception under Low-Bandwidth Communication**。第 7 页按相同载荷比较检测表现。海报顶部把每个协作者每帧载荷、相对稠密表示的倍率、测试丢包率分列，右侧表格分数据集与 IoU 阈值。原文和海报对 KB/KiB 的标注写法有差异；生成时以论文输入为依据，不能自行换算或补精度。 对应 P05、P10、P11、R04、R08、R11。[论文](../../../data/papers/Paper2Poster/CV/LR-V2X%3A%20Loss%20Resilient%20Collaborative%20Perception%20under%20Low-Bandwidth%20Communication/paper.pdf) · [海报](../../../data/papers/Paper2Poster/CV/LR-V2X%3A%20Loss%20Resilient%20Collaborative%20Perception%20under%20Low-Bandwidth%20Communication/poster.png)

- **SliderEdit: Continuous Image Editing with Fine-Grained Instruction Control**。论文第 1–2、6–7 页描述连续控制与评价。海报右侧在同一输入上展示编辑强度的变化，并区分单指令和多指令。展示渐变时既要能追踪被改的属性，也要让读者看到应当保留的部分。 对应 P04、P06 的适用边界、R02、R10。[论文](../../../data/papers/Paper2Poster/CV/SliderEdit%3A%20Continuous%20Image%20Editing%20with%20Fine-Grained%20Instruction%20Control/paper.pdf) · [海报](../../../data/papers/Paper2Poster/CV/SliderEdit%3A%20Continuous%20Image%20Editing%20with%20Fine-Grained%20Instruction%20Control/poster.png)


## 逐篇索引怎么读

`paper_sha256` 可与本地正式清单连接；`visual_note` 是单张海报的版面观察。`shared_term_groups` 为两侧都出现同组英文检索词的记录，分母统一为 362，同一论文可命中多组。比如有消融词不代表消融设计充分。缺词可能来自同义改写、OCR 或图中只用符号表达。以下为本次检索的命中数，括号内为词义范围：

| 术语组 | 成对命中 |
|---|---:|
| ablation（消融） | 106 |
| budget（时延、加速比、帧率、带宽、预算等所选词项） | 57 |
| controlled-input（反事实、单模态、打乱或遮蔽条件） | 51 |
| temporal（选帧、时间定位或一致性等） | 34 |
| geometry（深度图、相机姿态、新视角等） | 17 |
| spatial-output（框、掩膜、误差图、热图等） | 17 |
| human-eval（人类评价、偏好、用户研究等） | 13 |
| taxonomic（taxonomy 及复数） | 11 |
| uncertainty（置信区间、标准差、bootstrap 或随机种子） | 10 |

## 验证边界

全量覆盖指每对原件均核验、每篇论文提取可读文本、每张海报检查整版并有独立索引。正文与海报逐字逐数的精读集中在上列案例。英文 OCR、正文抽取顺序和缩略图均有限制。本轮按要求使用全部 362 对归纳，库内没有独立留出集。官方海报提供可研究的设计选择，不能作为每条科学陈述的最终依据。该版在生成试验前撤回。用论文全文和规则独立生成 XML、PPTX、PNG 的成功率，以及规则能否迁移到新论文，均需另行检验。
