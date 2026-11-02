# Improve revision handoff and deletion safety (2026-10-10)

## Module completion and final-fit rollback (2026-10-15)

The authorized shared completion change builds on `f58626b`'s snapshot isolation.
Improve continues to use its selected same-Lineage visible parent/current board.
Retrieval traces that board's own curated/visible roots to paper evidence;
explicit root deletions, disabled content and module ownership remain protected.
Verified additions and same-root compact restorations use staged banks/contracts
and must survive exact placement without module deletion or space regression.

The runtime completion baseline is bound to the current attempt and never saved
in Lineage snapshots. Final typography/render failure or inconclusive coverage
can revoke completion once, restoring the matching board, selection, banks,
contracts, LayoutSpec and fit report before a fresh normal preflight/render.
It preserves candidate identity and never substitutes another generation's
content board. Unknown programming errors are not treated as safe quality
fallbacks. The exact-parent stagnation fallback remains locked and separate.
Details and final verification are in [CAPACITY_REPAIR_REPORT.md](CAPACITY_REPAIR_REPORT.md).

## Authorized historical storyboard boundary fix (2026-10-14)

This is the explicitly requested minimal fix on `24cde5a`, following a read-only
boundary investigation. It does not restore the withdrawn unrelated edits or
change layout/content quality policy, Critic, scientific verification, geometry
or repair budgets.

### Cause and scope

The loader previously restored only present snapshot fields. A snapshot with
only `story_board` left the previous candidate's `optimized_story_board` in
memory; `_prepare_improve_parent` preferred that stale value. The unmodified
selection/loading/freezing path reproduced this with synthetic compatible
classic and four-column snapshots in `/tmp`. An explicitly null optimized field
already worked; a fitted-only snapshot also froze the correct parent, despite
the temporarily stale raw field. A snapshot lacking both boards could still be
selected for non-classic families and reuse old content.

The prior read-only inventory found 38 real snapshot files and 17 selectable
Lineages, all with both fields present and a usable selected board. This was a
confirmed conditional code defect, not evidence of existing Campaign corruption.
The post-fix read-only check retains the same 17 selectable Lineages; all 38
snapshot SHA-256 hashes remain unchanged. Temporary compatible missing-field
examples now freeze their selected content or are rejected, with no stale
previous-candidate content and no model calls.

### Resulting behavior

`_lineage_parent_reason` shares board availability across all families and
extensions after the existing classic checks. A usable effective board has a
`spatial_content_plan.sections` nonempty list of dictionaries. Current optimized
content takes precedence; an absent/null/empty optimized value may use that same
snapshot's raw board. A truthy malformed optimized board is rejected rather than
silently replaced with raw content. Existing classic reason codes take priority;
other missing/malformed boards report `lineage_storyboard_unavailable`.

Both raw/fitted fields are cleared before loading, including when no eligible
parent exists. Present fields are deep-copied independently. Parent preparation
can therefore freeze only selected-snapshot content. Shared verified variants
and supplemental evidence are not cleared or restored from the Lineage.

Selection skips unusable best/promising tracks and may use the same Lineage's
eligible latest snapshot. Availability reporting uses the same check. If no
eligible parent remains, existing pure Improve UNAVAILABLE or mixed/recovery
semantics apply before model work; no new fallback to another candidate's board,
Critic rejection, budget consumption, archive or historical data migration is
introduced. Exact-parent fallback and ordinary layout/scientific gates remain.

### Validation

`tests/test_lineage_storyboard_isolation.py` exercises real parent selection and
loading: all twelve families plus an extension across five missing/null/present
combinations; unusable/malformed board rejection; a valid same-Lineage alternate;
independent copies and unchanged source files/scientific banks. Its Runner test
uses only a temporary synthetic Campaign, corrupts historical board fields,
then verifies pure Improve ends UNAVAILABLE without any design/Critic calls or
additional committed iteration. Existing promising/base-memory test fixtures
were completed with section lists without changing their assertions.

Final focused regression: **152 passed** in **15.04 seconds**, three existing
dependency deprecation warnings:

```bash
.venv/bin/python -m pytest -q tests/test_lineage_storyboard_isolation.py tests/test_improve_revision_contract.py tests/test_promising_lineage.py tests/test_multi_batch_lifecycle.py tests/test_generation_routes.py tests/test_batch_modes_global_knowledge.py
```

Final full CPU regression: **600 passed, five subtests passed** in
**433.15 seconds**, with four existing dependency deprecation warnings:

```bash
.venv/bin/python -m pytest -q
```

`git diff --check` passes. No real models, paper generation, GPU workloads or
actual runtime Campaign writes are performed.
Reports and this guide stay local/ignored; only task-owned source/test/README
files enter the atomic commit.
Commit: **`f58626b`**, `fix(loop): isolate restored boards and reject unavailable parents`.
Five tracked files: the loader, the new isolation tests, two completed existing
restore-test fixtures and README. The worktree is clean after commit.

## Shared design-policy integration (2026-10-14)

Planner receives fit content hints and prior repair outcomes in its ordinary
payload. Core claim hints protect verified root information, not literal
wording; grounded compaction/addition still follows the existing verification
contract. Explicit root exclusions are removed from curated reference metadata
and cannot be silently restored by new compact module recovery.

An explicit reading-order request now tests real zone ownership, retaining
current per-zone counts, pins, conditional roles and measured bounds. Failure
reports the actual order instead of declaring unexecuted success. Automatic
linear reading repair permits at most two measured swaps; all final effects
remain subject to existing revision, deletion and geometry audits. Validate,
exact fallback and no-change fitting skip reading edits. Raw Critic scores,
admission rules, persistent scientific banks and commit semantics are unchanged.
Durable pre-call repair charges never refund abandoned model work. See
[CAPACITY_REPAIR_REPORT.md](CAPACITY_REPAIR_REPORT.md) for budgets and validation.

## Outcome

Improve now edits one current working storyboard throughout Planner, grounded
content optimization, family fitting, and final styling. The read-only parent
is used only for comparison and exact fallback. Removing an asset or claim is
an evidence-scoped proposal, not an instruction to leave its old footprint
empty. Exact-fit measurements, final compiled effects, and archive admission
all check that proposal before it can become a reusable template.

The Critic's rubric, dimension weights, admission threshold, and scientific
verification rules were not changed. The 95%-100% utilization band remains a
design target, not permission to invent content, shrink text arbitrarily, or
assume every iteration must succeed.

## Confirmed defects addressed

1. `GroundedContentOptimizer` previously preferred
   `revision_parent_story_board` over the Planner-edited `story_board`. Even
   zero content actions could undo image/claim removal, movement, replacement,
   importance, and board preferences.
2. Source-visual restoration did not distinguish accidental omissions from
   intentional deletions or movements. Sparse repair could re-add an earlier
   source occurrence and contradict the Planner.
3. Board operations in the revision execution report were marked applied
   merely because Planner accepted them; their final visible effects were not
   checked. Superseded requests were not distinguished from failed execution.
4. Snapshot/reset handling did not persist the new branch policies or clear
   their absence in legacy Lineages. `layout_overrides` was also missing from
   the fresh-design reset fields.
5. Exact fallback did not restore/digest-check the recovery policy, palette,
   keyword emphasis, importance, and spacing preferences. Color/keyword model
   calls could restyle what was reported as an unchanged parent.
6. End-to-end testing exposed that a safety-vetoed high score could still update
   the Portfolio's observed-best pointer. That path is now excluded explicitly.

## Working-board contract

| State | Meaning |
| --- | --- |
| `revision_parent_story_board` | Read-only visible parent for comparison |
| `story_board` | Current Planner/content-optimizer working board |
| `optimized_story_board` | Exact fitted visible candidate |
| explicit `board_override` | Highest-priority board for a staged capacity repair |
| `revision_contract` | Candidate-local desired effects and deletion evidence |
| `revision_recovery_policy` | Branch-local exclusions and effective recovery owners |
| `revision_safety_report` | Exact parent/candidate deletion-regression comparison |

An override is selected with `is not None`, not truthiness. Empty/malformed
explicit boards fail closed; they do not fall back to the parent. Ordinary
optimization requires a current storyboard. An explicit empty action list
means zero actions; disabled or zero-action optimization does not revert the
Planner's edits. Valid additions/compactions still pass the existing grounded
verification and only then update the contract's desired visible claim IDs.

## Deletion authorization and later reconsideration

`remove_claim`, `remove_visual`, and `replace_visual` require a section, object
ID, reason, and `critic_issue_ids` (or compatibility `issue_ids`). References
must resolve to actionable, object- or section-scoped issues in the current
base report or same-rubric latest Lineage feedback. A forbidden operation or
an issue about another asset cannot authorize deletion. A global aesthetic
suggestion alone is insufficient.

New contracts distinguish unusable assets, duplicate occurrences, resolution
problems, physical capacity, content concision, and visual relevance. The key,
main-result, and method roles receive extra protection: a bare section-level
overflow observation cannot authorize removing them. These roles remain
caption-based priorities, not pixel-level proof of scientific redundancy.
Protected-asset removal needs object-specific evidence, or a permitted
replacement, and all ordinary fit/grounding/Critic gates still apply.

Duplicate repair removes one occurrence, including when two occurrences are
inside the same module. It cannot delete the last occurrence merely by citing
the duplicate issue. Replacements respect the requested source section.

The original `layout_visual_source_manifest` remains provenance. The separate
recovery policy tracks excluded section/asset occurrences, unusable asset IDs,
section/root-claim exclusions, and effective recovery destinations after a
move. Automatic repair cannot silently undo these decisions. It may still
restore other approved omitted assets and use other useful verified claims.
Same-root claim variants cannot bypass an intentional claim deletion.

This is not a global permanent blacklist. A later Planner may explicitly use
`restore_visual` for a readable, approved, originally assigned source asset in
its source section; the asset file is verified before that request is applied.
It may also explicitly request `add_existing_claim` to reconsider a previously
excluded claim root. That root exclusion is revoked only after verification
and successful placement, not when the request is merely proposed. These
permissions are unavailable to automatic capacity-repair overrides. Restored
content must still fit and pass preflight/Critic.

## Bounded deletion evaluation and rollback

The solver first prefers already-exact candidates that satisfy the revision
contract and deletion guard. Existing bounded geometry, text repair, visual
repair, and normal preflight remain in force. It does not add filler or make
unbounded model calls.

The deletion guard compares exact parent/candidate zone utilization, bottom
gaps, unallocated body area, largest empty rectangle, and within-/cross-zone
gaps. It reuses the existing capacity-repair tolerances: by default 0.01 of
body area/utilization and 0.35 inches of gap regression. This is not a new
poster score or a requirement that the total Critic score rise every time.

If the proposal still materially worsens these measurements, there is one
additional same-family rollback/refit. It explicitly restores valid deleted
source occurrences/claims, undoes a corresponding replacement, updates the
contract/retention constraints, and records the revoked operations. It never
restores an unusable/missing asset or duplicates an already visible image to
fill space. If rollback cannot fit or remains regressed, the attempt fails
before Renderer and uses the existing bounded Improve recovery procedure.

The post-Font preflight independently checks final compiled visual ownership,
importance, actual adjacent-module gaps, and exact visible scientific text
after decoding Renderer-compatible emphasis/literal escaping. It re-measures
whitespace and utilization from the final styled module containers. It does
not record scientific prose in the new contract/safety audit files.

When older parent artifacts have no complete exact composition baseline, the
report explicitly says `unavailable_absolute_critic_required`. It never claims
a measured improvement. Ordinary preflight and the Critic's absolute severe
fit/empty-zone gates remain mandatory; no historical artifact is rewritten.

## Execution audit and final admission

Revision plan schema v4 assigns candidate-local operation/action IDs.
Execution report schema v3 distinguishes `applied`, `already_satisfied`,
`not_applied`, `superseded`, `rolled_back`, and `revoked` board/layout effects.
Content action results also record the resulting IDs and verify their final
module visibility. Zone-budget requests remain advisory bounded preferences;
they are not mislabeled as hard arbitrary-coordinate commands.

After Critic, an independent `revision_admission` is added to the same full
report. A safety/contract veto never rerenders or rewrites the evaluated
poster, nested `poster_evaluation`, or raw score. It sets the effective
archive/template flags false and `loop_disposition=revision_safety_rejected`.
Such an already-evaluated candidate commits as a rejected iteration, consumes
one Batch slot, and retains its diagnostic evidence. It cannot advance the
observed-best/safe-promising base, accepted archive, template, or archetype.
`outcome.critic_accepted` retains the raw Critic admission separately from
effective `outcome.accepted`. Normal de-identified rejection feedback remains
negative feedback, never a reusable positive template.

Pre-render failures retain the existing same-iteration retry/no-Batch-charge
semantics. The final exact-parent fallback still commits only a no-change
stagnation event with no new archive/template or poster outcome. Its digest
now also covers board importance/preferences and branch controls. It restores
source/recovery policy, style/gap overrides, palette provenance, and keywords;
color/font agents reuse those frozen values instead of making fresh model
choices. Shared Campaign scientific banks are never rolled back.

## Persistence and operator files

The new fields are optional iteration/Lineage snapshot fields. Legacy absence
means no policy, not inheritance from a previously loaded branch. Fresh-mode
reset includes spacing overrides and the new contract/policy/reports. Failed
staged repairs deep-copy these fields so a discarded trial cannot mutate the
working contract. No Campaign identity/schema migration or historical rewrite
is required.
If a legacy parent lacks a source manifest, only its known visible occurrences
are reconstructed in memory before the fallback digest is frozen; missing
historical source selections are not invented or written back to history.

Inspect these files under the latest output's `content/` directory and the
unique Campaign `iterations/<N>/attempts/<attempt>/` directory:

- `revision_plan.json` (latest content output; full plan also in the snapshot)
- `revision_contract.json`
- `revision_execution_report.json`
- `revision_safety_report.json`
- existing `capacity_repair_report.json`, `layout_preflight_report.json`, and
  `critic_report.json`

Contract/execution/safety files are also copied into accepted or rejected
bundles when present. Attempt evidence is saved before abandoning a failed
preflight and at normal commit. The existing `COMPLETED.json` remains the
only iteration commit marker. No CLI mode, Batch quota, template retrieval
policy, or layout-family diversity mechanism was changed.

## Verification and limitations

CPU-only tests cover the actual Planner -> content optimizer -> family solver
-> compiler -> styled preflight chain; zero/disabled actions; malformed
overrides; scoped evidence; protected/duplicate assets; explicit later visual
and claim restoration; same-root exclusion; moved recovery ownership; staged
repair isolation; bounded rollback; mathematical literal text; palette/
keyword fallback; legacy loading; and real Campaign commit/archive/diagnostic
behavior after a raw Critic pass but safety veto.

The complete CPU suite (`.venv/bin/python -m pytest -q`) passes 263 tests plus
5 subtests; the persistent baseline is also recorded in `AGENTS.md`. No live model,
Marker/GPU paper extraction, or full rendered paper-generation run was
performed for this change. Synthetic exact-layout/Campaign tests establish
the tested contracts, not a guarantee of universally beautiful posters or
an assertion that every possible runtime bug has been eliminated. Existing
model/render I/O failures and human aesthetic calibration remain relevant.


---

## 2026-11-02 独立项目迁出说明

本报告的既有内容从 PosterGen 工作区完整保留，现随独立项目 Rubrics_poster
在 `/projectone/projects/Rubrics_poster` 维护。既有记录中的源码版本、测试、旧样本
和绝对路径属于迁出前的历史证据；不代表新项目已运行相同的真实模型验证。
新项目未迁入原来的海报、run、缓存或模型日志，也不依赖原项目源码和环境。
迁出操作、行为保留范围、独立环境及验证结果见[独立迁出报告](PROJECT_EXTRACTION_20261102.md)。
