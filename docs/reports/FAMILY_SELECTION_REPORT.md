# Open family exploration and bounded semantic selection

## Shared module completion (2026-10-15)

Design policy v2 adds per-module grounded completion and layout-preserving
adoption in the common Solver/repair path. All twelve families and new registered
families receive it without family-ID branches or a separate opt-in. Existing
`FamilyContract` v1 still controls legal geometry; classic's fixed three regions
and strict validation locks remain intact. New family pools still require a new
Batch; v1 policy resume upgrades preserve the existing frozen pool and budget.
See [CAPACITY_REPAIR_REPORT.md](CAPACITY_REPAIR_REPORT.md) for retrieval,
zero-height information gains, finite queues, final rollback and validation.

## Shared family contracts (2026-10-14)

All twelve existing families now declare `FamilyContract` v1, consumed by
shared topology validation, mutations, conditional role rules, reading traversal
and existing family Critic checks. Registering an extension does not require a
new branch in content search, refill, repair accounting or diagnostics.
Generic legal boundary/split/span/mirror candidates remain available; a
deterministic `geometry_generator` can add bounded geometry for a new grammar.
Existing specialized presets are retained, selected through the contract.

Reading options are neutral, columns, bands, anchor-first, parallel, matrix,
spine and stages. Mirrored physical positions determine column traversal;
stage order is presentation metadata, not verified chronology. Unknown
contracts default to neutral reading. Classic still owns exactly three IDs
and forbids splits/spans. Existing conditional role rules are unchanged.

Extension checklist:

1. Register normalized zones, capacities and an explicit contract in `FAMILIES`.
2. Supply a preset or generator only when generic legal mutations are insufficient.
3. Enable the new ID in configuration for a new Batch. Resume preserves its
   frozen enabled pool; adding a family is not a hot reload.
4. Regenerate previews if geometry changes and test traversal, required regions,
   locks and bounded mutations.
5. Reuse shared content, budget and diagnostic code instead of adding family-ID
   conditions there.

Regression exercises all twelve contracts and an unseen four-track grammar
through fit/compile/preflight. Fit reports include contract/design metadata.
Family-selection policy v1, profile identity, coverage-first drawing and
committed-use accounting remain unchanged. See
[CAPACITY_REPAIR_REPORT.md](CAPACITY_REPAIR_REPORT.md) for content/search changes
and model-free validation limits.

Implemented 2026-10-12. This report describes the active optimization route;
the independent one-shot classic route is unchanged.

## Problem and resulting behavior

The registry contained twelve families, but three were hard-filtered by semantic
flags. The profile builder searched `title`/`section_title`/`section_id`, while
the active NarrativePlanner emits `title_intent` and `narrative_role`. Real
method and comparison content was therefore missed. In the current geospatial
paper the resulting pool contained only nine families.

All registered, configured families now remain explorable without semantic
flags. Selection first removes current-iteration fit failures, then restricts
the draw to the families with the smallest committed design-use count. Only
inside that group does semantic matching affect seeded random selection.
Weights are `1 + semantic_bonus_max * match_strength`, with bonus bounded to
0..0.5 and strength to 0..1. Defaults yield weights 1..1.5, never zero.
Additional matching labels cannot accumulate beyond the strongest hint.

`family_counts` intentionally retains its existing meaning: committed normal
Explore/Improve family usage, not all attempted searches or pure Explore counts.
Validate and no-change fallback retain their existing accounting boundaries.
High-match families cannot jump ahead of less-used candidates. A fresh pure
Explore simulation with twelve feasible, committed candidates visits all twelve
families once. Real runs may have failed fits or Improve work and do not carry
that twelve-iteration success guarantee.

An empty post-exclusion pool raises a dedicated exhaustion result rather than
falling back to excluded families. The runner preserves its existing
`layout_family_search_exhausted` / `FAILED_REQUIRES_USER` semantics with no new
commit, Critic invocation, template publication or consumed Batch budget.
Unknown programming exceptions remain generation errors, not fit rejections.

## Profile contract

`src/layout/paper_profile.py` owns profile schema v2 and semantic rule v1.
The old `src.templates.library.build_paper_profile` import remains available.

- Read normalized `narrative_role` and prefer `title_intent`, falling back to
  legacy `title` or `section_title`. Never search a section ID for keywords.
- Exact supported role labels provide strength 1. Title token matches and
  the retained visual-rich heuristic provide strength 0.5. These values are
  deterministic policy strengths, not statistical confidence or scientific proof.
- Method content does not automatically imply a process or timeline; result
  content does not automatically imply a comparison. Stage hints and temporal
  hints are recorded separately. Missing signals are `unobserved`, not unsuitable.
- Record section IDs, field names and rule IDs, never title/claim/excerpt prose.
- Keep the previous visual-count, claim-density, `kind` and `profile_key`
  definitions intact. This prevents accidental changes to profile-gated template
  reference and strict-validation history. No foundation mutation or new model
  call is needed; the profile is derived at launch from the restored foundation.

Read-only verification of the existing geospatial foundation produced
`visual_heavy:high`, 7 visuals, 48 claims, and flags `comparison`, `method_heavy`,
`results_heavy`. The pool contains twelve families; source-file SHA-256 was
unchanged before/after this check.

## Content placement and scientific boundaries

The Solver keeps its conditional semantic-zone restrictions: a method module
belongs in an active method spine, results in the main result region, and
results/conclusions in the top hero. Search and exact refill use the same role
helper; role aliases and legacy/current narrative labels are readable. General
columns and neutral regions gain no rigid scientific-role assignment.

Family hints are never instructions to synthesize comparisons, steps, chronology
or causal statements. Internal `stage_1` / `comparison_a` IDs do not become
visible scientific labels. Curator and RevisionPlanner prompts now explicitly
state these boundaries. Existing verified-content, geometry, capacity, rendered
fit and Critic checks remain mandatory. This update introduces no new complete
verifier of implied scientific relationships, no Critic weight changes and no
new admission threshold. Real model-generated titles/relationships still depend
on existing grounding and evaluation safeguards.

## Batch compatibility and reproducibility

`schedule_policy.family_selection` freezes policy version 1, enabled family IDs,
profile schema version, coverage basis and bonus. New Batches snapshot current
configuration. Legacy resumable Batches gain one `family_selection_migration`
record on their first new-code resume. Repeated resumes preserve that record
and the frozen policy, even if live config changes. Unknown/corrupt versions or
invalid weights fail before resuming the Batch. Terminal Batches are not made
resumable, and historical commits keep their original selection history.

The mode schedule remains v3 (45% Explore / 55% Improve); Batch budget, mode,
target Lineage, strict Validate topology and independent classic route retain
their established contracts. No LayoutSpec/foundation/Campaign identity version
bump is needed. Recovery of committed counters does not overwrite the new
Batch policy with an older runtime projection.

Campaign resume now restores `PortfolioScheduler.random_seed` as well as the
owner/strategy seed. For identical profile, policy, usage counts, exclusions
and iteration, family selection is reproducible. Candidate IDs/session timestamps
remain independently generated; repeatability of the LLM is not claimed.

Do not hot-reload an active candidate. The new policy/profile take effect on a
safe pause and next process launch. No running Batch was paused, resumed or
rewritten as part of this implementation.

## Diagnostics

Within `storage/critic_loop/campaigns/<campaign_id>/`:

```text
sessions/<session_id>/paper_profile.json
iterations/<iteration>/attempts/<attempt_id>/family_selection_report.json
```

Each Explore attempt report stores policy, profile identity/digest, enabled and
available families, exclusions with prior attempt/stage/issue information,
committed family usage, least-used group, matching weights, seed and selection.
Retries have separate immutable attempt paths. Attempt/commit knowledge inputs
also record the profile identity and frozen selection policy. A defensive
pre-attempt exhaustion path writes `family_selection_exhausted.json` in the
session directory. Historical attempts without these reports remain readable.

Example terminal output:

```text
Explore family policy v1: 12 enabled | coverage-first | semantic bonus <= 0.50
I1 Family pool: 12 enabled | 0 excluded this iteration | 12 least-used candidates | selected method_flow_spine | committed design uses 0 | semantic weight 1.50
```

These diagnostics do not constitute accepted template/design knowledge. They
distinguish an available family, a current-iteration fit exclusion and an actual
Critic outcome; a profile mismatch no longer silently removes a family.

## Verification

Focused CPU regressions cover current/legacy fields, false matches in IDs,
profile-key preservation, all-family reachability, coverage before semantics,
nonzero bounded weights, enabled snapshots, deterministic replay, invalid config,
single legacy migration, unchanged frozen policy, no-budget exhaustion over all
twelve failed families, actual solver/refill semantic anchors and unchanged
scientific module content. Existing resume integration now verifies that a new
launch seed cannot override the saved Campaign seed and checks persisted audit
files. Existing Improve, Validate and standalone route regressions are included
in the full suite.

Final full-suite command and result:

```text
CUDA_VISIBLE_DEVICES='' .venv/bin/python -m pytest -q
310 passed, 5 subtests passed, 4 dependency deprecation warnings
```

This is 24 additional test cases over the previous 286-test baseline. The
commit-marker test was updated to verify the newly recorded profile and frozen
selection-policy fields. A separate defensive pre-attempt exhaustion regression
verifies that both the returned loop status and persisted Batch remain failed,
with no generation, Critic invocation, commit marker or consumed budget.

The interrupted handoff was reviewed before completion: Batch counter recovery
does not overwrite the frozen family policy, retries retain distinct audit
files, and the final source changes match the tested implementation. The
interruption occurred during the final repository checks, after the full suite
had passed; it did not interrupt a source-file write or a production Campaign.

No model-backed or GPU generation benchmark was run. Automated selection and
solver checks do not establish that all twelve families will produce attractive
or Critic-accepted posters for this paper.


---

## 2026-11-02 独立项目迁出说明

本报告的既有内容从 PosterGen 工作区完整保留，现随独立项目 Rubrics_poster
在 `/projectone/projects/Rubrics_poster` 维护。既有记录中的源码版本、测试、旧样本
和绝对路径属于迁出前的历史证据；不代表新项目已运行相同的真实模型验证。
新项目未迁入原来的海报、run、缓存或模型日志，也不依赖原项目源码和环境。
迁出操作、行为保留范围、独立环境及验证结果见[独立迁出报告](PROJECT_EXTRACTION_20261102.md)。
