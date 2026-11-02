# Source-backed module consistency

## Current status: withdrawn on 2026-10-14

The user chose to restore the container's tracked project files exactly to
`c3b103829db1d9c75ecea12972bf19b1d8588590` and gather experience across more
papers before deciding whether this feature is needed. Both implementation
commits (`0d7de7a`, `a084cd2`) remain in Git history; rollback commit `b5f0947`
records their net reversal. This is not a configuration-only disable.

All eight added source/prompt/test files are removed from the active tree.
Prepare/final semantic stages, the Critic module gate, association repairs,
Planner/content membership guards, semantic Solver constraints and feature
accounting/persistence changes are withdrawn together. Exact restoration also
restores the old five-word title truncation, omitted-claim fallback and
pre-feature parent-score behavior; no selective feature fragments are retained.
Critic is again `4.3.0 / academic_poster_multifamily_v5`. Existing seven scores,
78-point admission, ClaimVerifier/editorial grounding, twelve-family layout,
measurement speedup, spacing and full rendered-text matching remain intact.

The tracked working tree was verified equal to the target with
`git diff --exit-code c3b1038 -- .`; tracked commit-tree equality is checked
again when publishing the rollback. Both tracked trees have object identity
`d987ce739d0e23a2f55906d8eed241f98e1fa525`. This local ignored report and AGENTS guide
intentionally retain current rollback context instead of historical wording.
Original implementation details below remain historical, not active behavior.

No project entry process was active before mutation. All stored Batches were
PAUSED or FAILED_REQUIRES_USER; the latest paper's Batch 2 has committed I1-I4
and abandoned, uncommitted I5 attempts. No semantic-blocked commit was found.
No Batch is launched, no runtime migration/rescoring occurs and GitHub is not
pushed. Existing source-image payload authorization does not itself re-enable
this withdrawn feature. Any future reintroduction needs explicit user approval.

Focused CPU regressions: **99 passed**, two dependency deprecation warnings,
18.96 seconds. Full CPU regression: **484 passed, five subtests passed**, four
existing dependency deprecation warnings in **416.10 seconds**. The removed
feature tests account for the drop from 561 to the target baseline of 484;
tests were not skipped to hide failures. CLI `--help`, loop import, Critic
configuration and unchanged persistence schema checks also passed. No live
model/GPU workload was used. Final runtime inventories and hashes matched all
three pre-change digests below. `git diff --check` passed.

Pre-change preservation digests (path inventory plus SHA-256 of file bytes):

- `storage/critic_loop`: 565 files, 47,712,121 bytes,
  `a2d48893a8722d8db5f65bbb785ce896d2e9182b5dbef1ee2a48b6c679338e35`.
- `output`: 958 files, 57,567,760 bytes,
  `df12f4d41e85da4b022914844cac17b9711f5306b16c7393e7ced107ddd7042a`.
- `data`: 36 files, 49,866,448 bytes,
  `367e187770438739cdf7f36f87c7afa103a9404e8b9c38757ce5467ea0f45921`.

## Historical implementation record (inactive)

Implemented 2026-10-13. This report describes the optimization-family route;
the independent classic one-shot route keeps its existing generation path.

## Historical repair policy: source_association_repair_v2 (withdrawn)

Updated after user review on 2026-10-13; interrupted work resumed on 2026-10-14.
This section supersedes the original
automatic-repair baseline/comparison policy documented historically below.
Source-check policy `module_consistency_v1` itself remains unchanged.

The corrected poster is judged on its own source correctness, exact layout,
RenderFit and normal Critic admission. Removed the erroneous original candidate's
temporary render/Critic, all-seven-score non-regression veto and semantic-repair
relative whitespace/utilization veto. Ordinary seven scores, weights, rubric v6,
78-point threshold and independent template scoring remain unchanged. Critic
system version is 4.4.1; repair-report schema v2 records its independent policy.
Other normal capacity/composition/Planner-deletion safeguards are not globally
relaxed. Strict Validate and exact-parent fallback remain locked.

Confirmed corrections apply to arbitrary actual module topics, including
different experiments with the same broad role, and both figures and tables.
Source titles/chapters/classification roles alone never establish correct
ownership. Unknown targets are not guessed. At most two confirmed membership or
title edits stage in one transaction. All modules must pass before fitting.

The first fixed-topology same-family fit requires every corrected claim/visual
in both Explore and Improve, without pretending exploration is improvement.
Final inventories check exact per-module ownership, words and asset counts.
Only measured height pressure or sparse zones may request one affected-module
content round (at most two actions), followed by one more exact fit. This round
subtracts earlier layout repair work from the current iteration's remaining
capacity allowance, and the runner charges semantic rounds too. Disabled content
optimization, unavailable text models or budget exhaustion skip content work.
Sparse-fill selection excludes already-visible scientific roots' other wording
variants and explicitly excluded claims. Model-supplied metadata cannot override
the recorded repair-policy version. Normal exact cache use stays
within one bounded measurement context for these two refits, never persisted.

GroundedContentOptimizer remains the only prose editor, using existing
ClaimVerifier/editorial/module checks. Custom/cross-chapter modules can use their
current claim evidence as source-search hints. Compactions must preserve each
scientific root in its corrected module; additions require approved verified
receipts. Titles, all visual counts/ownership and unaffected module text must
remain unchanged during text work. No claim deletion, figure deletion, filler,
font shrinking or silent relaxation of bounds. Earlier candidate content-action
audits are retained when a semantic content round succeeds.

Confirmed membership/title corrections replay against the real visible board
before narrowly amending Improve's desired-board contract. Unrelated changes,
pre-existing contract failures, unusable assets and excluded target occurrences
remain blocked. Original Planner operations remain in history; superseded effects
are explicitly explained. Adopted visual moves update restoration owners.

Science banks, selection, contract, layout, styled input and reports stage
together. Failed text actions/second fits discard their supplemental evidence
and variants. If the first corrected fit was feasible, optional text failure can
retain that corrected fit without a third search; this is never the erroneous
original. Failed final semantics/Preflight prevents adoption. Unknown programming
or model-service exceptions propagate through existing no-budget failure handling.

Final rendered normal admission saves one poster/template bundle. A correct but
ordinary-quality-rejected poster follows normal diagnostics and safe promising
eligibility, without reverting its image association. A retained semantically
unverified candidate remains unscored and creates no archive/template/global
design event. Validate content deferral and crash accounting remain unchanged.

New snapshots exclude `module_semantic_repair_baseline`; attempt reset/finalize
clear legacy fields. Old reports and failed `module_semantic_admission` records
remain historical and are not automatically rehabilitated or rescored. Repair
audits record association versus layout status, edits/targets, refit counts,
requested/accepted content actions and adoption/rollback. Critic records the
repair policy/status; concise English logs announce corrected-module refitting
and distinguish repair adoption from final archive admission.

Validation uses mocked source/vision models and real CPU exact fit/Preflight
tests. No real-model scientific accuracy or aesthetic guarantee is claimed.
Completed verification on 2026-10-14: final focused tests **127 passed**, two
dependency warnings in 22.32 seconds; final full CPU regression **561 passed,
five subtests passed**, four dependency deprecation warnings in 422.93 seconds.
`git diff --check` passed. The pre-interruption full-test output was unavailable
on resume and was not counted as acceptance; the final full run tested all
resumed code, including immutable policy metadata and unavailable-text skipping.
No live model/GPU work or historical Campaign/template-store mutation occurred.

## Historical original implementation (repair v1)

The following original implementation record is retained for history. Its
temporary-render, relative-whitespace and seven-score repair veto paragraphs
are superseded by v2 above and no longer describe the active repair path.

## Purpose and scope

Each visible module must present a coherent paper-supported topic through its
title, verified claims and figures/tables. True individual claims and genuine
paper images do not by themselves prove correct grouping. Related source
paragraphs may span chapters; narrative/source section IDs are candidate hints,
not rigid ownership rules. Layout families remain equally available, and source
relationships are never inferred from a family's desired appearance.

Critic 4.4 / `academic_poster_multifamily_v6` adds a score-neutral module gate.
The seven dimension weights, 78-point threshold and independent structural
template rubric remain unchanged. Existing foundation data, historical posters,
scores, templates, previews and validation evidence are not retroactively edited.

## Data and evidence contracts

`src/semantic/consistency.py` derives a versioned paper-local index from immutable
source chunks/raw text, original and committed supplemental evidence, captions,
reference paragraphs and source-image SHA-256 hashes. Excerpts and caption text
must occur in original parsed text under the existing whitespace normalization.
Paper labels come from actual caption references, never extraction sequence:
internal `figure_1` can correspond to paper Figure 7. Placeholder captions,
ambiguous parser associations, duplicate paper labels and missing assets remain
inconclusive. Parser now records caption provenance; multi-image groups cannot
silently claim unique caption ownership. Legacy data stays readable.

Every module response must cover its title, collective coherence, each Claim ID
and each visual ID. Quotes must be real substrings of named source records.
Claim judgments cite their own original evidence; visual judgments cite both
their caption and current-claim evidence. Unsupported numerical title claims
are blocked. Models must not infer new prose/numbers from image OCR. Supplied
paper strings are explicitly treated as untrusted data rather than instructions.

The user explicitly approved original-figure pixel checks through the project's
existing `state["vision_model"]` service on 2026-10-13. Visual-module calls attach
the existing source PNGs with ID labels and verify their hashes, using the same
configured service as ColorAgent/VisualCritic; no endpoint is added. Text-only
modules use `text_model`. The output must acknowledge actual image inspection.
Unreadable content/ambiguous panels stay inconclusive. Image bytes/base64 are
not written into these reports, Lineage memory or global template/design memory.

Failure judgments require a second blind source-backed review of the same
objects. Disagreement becomes inconclusive. Missing/duplicate checks, invented
quotes, wrong claim citations, caption-only judgments and malformed responses
cannot produce a complete pass. This reduces obvious self-confirmation but is
still model judgment, not an independent mathematical proof.

Passed module records serve as `module_semantic_contracts`: grounded theme
evidence and any essential figure/claim dependencies. The Solver cheaply checks
those dependencies during subset generation and exact refill. Same-root compact
variants can satisfy structural dependencies, but their actual wording still
passes final semantic checks. No semantic model runs inside the geometry beam.

## Integration

The loop fresh-design path adds semantic preparation after GroundedCurator.
Improve adds it after RevisionPlanner/ContentOptimizer. The common design path
adds final semantic checking after FontAgent/LayoutPreflight, before Renderer.
The final Critic evaluator rebinds the report to actual styled text, literal
titles, visual ownership and refreshed source-image hashes. Font styling is
decoded with the shared Renderer grammar; scientific replacements remain
forbidden. RenderFit remains the independent actual-glyph geometry audit.

GroundedCurator no longer puts omitted claims into the least-populated module
in the loop. Same-origin placements are candidates for independent checking;
otherwise omitted claims remain in the verified bank and `unselected_claim_ids`.
They are not deleted. Loop titles, including deterministic fallback titles, are
not cut at five words. Classic retains its previous behavior.

Planner adds controlled `move_claim` and `retitle_module` requests. It never
writes replacement scientific body prose. Actual board operations, including
visual move/replace/restore and deletions, must pass affected-module checks;
unverified board changes are rolled back. Revision contracts now preserve titles
and audit the two additional operations. Existing compact/add/restore/variant
actions in ContentOptimizer share the same check, on staged scientific banks.
Failed actions roll back board, content selection, newly staged variants and
supplemental evidence together. Capacity repair uses this same optimizer.

## Automatic repair and quality protection

Only confirmed object-specific failures authorize automatic membership/title
repair. Inconclusive checks do not authorize destructive changes. At most two
edits may stage in one transaction; a complete passing candidate is required
before any transaction is adopted. Intermediate failures must strictly decrease,
without introducing unresolved modules. Incomplete repair transactions are
discarded, and reports remain bound to the actual retained board.

Allowed automatic edits move existing verified claims or approved visuals, or
propose an independently checked grounded title. They cannot delete claims,
drop visuals, add scientific prose, invent modules or shrink fonts. Exact
claim/text and visual-count inventories must survive. Validate topology and
exact-parent fallback prohibit automatic repairs. Improve revision contracts
remain authoritative; a repair conflicting with them is rejected rather than
silently changing the plan. Accepted visual moves update restoration ownership.

A proposed repair uses one isolated same-topology exact Solver fit, compilation,
existing font/emphasis presets and full preflight. It bypasses neither bounds
nor title spacing, and does not run capacity text generation. Missing comparison
data cannot establish improvement. Whole-poster holes/gaps, worst-zone fill and
maximum bottom gap must not regress (only 1e-6 fraction / 0.01-inch numeric
tolerances). Rejected trial reports cannot overwrite candidate reports.

For an otherwise eligible repair, one temporary render of the original candidate
plus RenderFit/Critic supplies a comparable quality baseline. A partial PDF audit
or incomplete visual evaluation cannot certify this baseline. Temporary files
are automatically released; there is no Campaign commit, template registration,
global event or Lineage publication for this render. Its token/API costs are
tracked with the session. The ordinary final candidate's Critic must not regress
in any of seven dimensions (0.01 point numeric tolerance); missing/noncomparable
scores also fail. A separate `module_semantic_admission` veto preserves raw
scores and nested evaluation while blocking archive/template publication and
best/promising advancement. The original unsafe candidate is not a safe fallback.

These are explicit measurable guards. They do not establish that every human
will find the repaired poster equally attractive, or that model semantics have
zero false positives/negatives. Real-model calibration remains necessary.

## Budgets and failures

Configuration under `module_consistency` bounds one candidate to 32 model calls,
16 modules, two repair edits, 96 KiB JSON context per call, 8 MiB of image bytes
per call and 128 positive cached module results. Image reads are bounded before
encoding; oversized evidence is not silently truncated and declared verified.
New checks use `LangGraphAgent(single_attempt=True)`, disabling both provider
retries and its Tenacity wrapper. Existing agents retain their previous retries.
API/programming failures propagate through existing generation-failure handling:
no Critic quality rejection, commit, budget use or template failure is created.

Only complete passes are cached. Identity covers exact visible content and
ownership, paper/index/image hashes, effective text/vision model settings,
prompts, policy and limits. Geometry is excluded. Source/wording/title changes
invalidate appropriate checks; budget-limited/unknown/failing results are not
cached as successes. Runtime/cache objects are plain attempt-local diagnostic
state, not appended scientific or shared global knowledge. Candidate call usage
resets on a new attempt; source-bound positive results may be reused in-process.

A pre-render failed or inconclusive semantic result consumes one committed Batch
iteration after bounded work, but is unscored (`overall_score: null`). It creates
no poster, template, accepted/rejected poster count, rejection journal event or
global design event. Uncommitted scientific additions are restored from committed
Campaign memory before this result commits. It cannot be selected as an Improve
parent; historical safe tracks remain available under existing version rules.
Compatible historical latest layouts can still be edited, but an old-rubric
parent score is returned as null for current comparisons. The original score,
rubric and explicit `score_comparable=false` remain available in the base audit
context; historical snapshots are not rewritten.
Force-stop and pre-marker failures still consume no budget. Model absence is
reported as unavailable; actual model-call exceptions follow the error path.

Validate's content-blocked candidates defer the selected template in that
Batch's `validation_content_blocks`. They do not consume one of its three
cross-paper trials, complete source replay, alter applicability/level or rewrite
the original design score/preview. A later Batch may retry. If the frozen set is
entirely deferred, the Batch ends EXHAUSTED. Both ordinary execution and
post-commit replay suppress template usage/trial updates for these outcomes.
Even a late post-render semantic freshness failure cannot become template
transfer evidence or a global negative design prior.

## Reports and observability

Outputs under `content/`, unique committed attempt directories and applicable
accepted/validation/rejected bundles retain:

- `paper_semantic_index.json`: original paper-local source associations;
- `module_consistency_report.json`: status, coverage, per-object source IDs,
  quote hashes, identity, image-inspection acknowledgments and check reasons;
- `module_semantic_repair_report.json`: staged/adopted/rejected transactions;
- Critic's `module_consistency`, module evaluator metadata and any
  `module_semantic_admission` / `validation_content_blocked` result.

No unrendered semantic outcome fabricates a rejected poster bundle. Reports are
published with existing atomic commit accounting; rejected trials cannot replace
the current candidate's files. Terminal output remains concise English and
distinguishes source failure/unknown, no score/archive and consumed Batch budget.
Normal stage events expose preparation/finalization timing. Direct source/asset
scientific data stays paper-local and never enters global Planner priors.

## Validation

CPU tests exercise exact source and true figure-number association, caption
ambiguity/duplicates, coherent cross-chapter grouping, confirmed versus disputed
failures, complete object-specific quotations, pixel payload routing through a
mocked existing service, bounded payloads, no caption-only fallback, cache
invalidation, original classic isolation, content rollback, numeric titles,
staged one/two-edit repairs, actual same-topology Solver/Font/Preflight refits,
strict geometric non-regression, rendered-score admission, Validate accounting,
post-marker replay, pre-marker rollback and no global learning from uncertainty.
The shared client's existing retry/tracking tests also run, with new text/vision
single-attempt fault injection proving one invocation and zero provider retries.
An additional model-mocked Planner integration smoke check exercised both
`move_claim` and `retitle_module` through its actual callable entry point:
verified edits were adopted, inconclusive edits were rolled back, and the
read-only parent plus final revision contract were preserved.

Final complete CPU suite: **535 passed, five subtests passed**, four dependency
deprecation warnings, 422.36 seconds. Final module/parent/resume-focused run:
**68 passed**, two dependency warnings, 13.89 seconds. `git diff --check` passed.
The results are also recorded in AGENTS.md's Recent Changes.
No live model endpoint, uploaded paper, Campaign store or GPU was
used for acceptance testing; original-image routing was mocked. No real-model
semantic accuracy or multi-paper aesthetic benchmark is claimed.


---

## 2026-11-02 独立项目迁出说明

本报告的既有内容从 PosterGen 工作区完整保留，现随独立项目 Rubrics_poster
在 `/projectone/projects/Rubrics_poster` 维护。既有记录中的源码版本、测试、旧样本
和绝对路径属于迁出前的历史证据；不代表新项目已运行相同的真实模型验证。
新项目未迁入原来的海报、run、缓存或模型日志，也不依赖原项目源码和环境。
迁出操作、行为保留范围、独立环境及验证结果见[独立迁出报告](../PROJECT_EXTRACTION_20261102.md)。
