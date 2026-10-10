# Improve revision handoff and deletion safety (2026-10-10)

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
