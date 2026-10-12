# Capacity search and grounded text repair (2026-10-09)

## Generation-failure isolation update (2026-10-12)

Sparse-zone actions may deliberately omit a claim ID so the optimizer selects
an eligible, relevant, non-visible verified claim. That path now normalizes the
visible-ID list to a set only at the exclusion union; deliberate root deletions
remain excluded and an exhausted claim pool is a safe no-op.
The initial measured fit is saved before optional repair. Repair audits are
attached before work starts, and an unexpected optimizer/refit exception keeps
its root traceback and partial audit. Such exceptions fail generation safely;
they are never reinterpreted as a poorly scored poster or silently retried as
another family. Known measured fit failures retain their existing bounded
recovery. See [GENERATION_FAILURE_REPAIR_REPORT.md](GENERATION_FAILURE_REPAIR_REPORT.md)
for commit rollback, journal publication, historical correction and tests.

## Improve revision safety update (2026-10-10)

Grounded content repair now consumes an explicit staged board override, while
ordinary Improve consumes Planner's current working board, never its read-only
parent. Explicit empty actions do not invoke an unsolicited fallback. Source
provenance remains immutable; a separate branch recovery policy distinguishes
accidental omissions from intentional asset/root-claim deletions and moved
visual ownership. Sparse repair honors those exclusions and deep-copies the
contract/policy along with scientific memory; discarded trials cannot leak
revision intent. Later explicit Planner restoration remains possible after
source-asset readability or claim verification/placement checks.

Improve prefers exact candidates without deletion-induced whitespace
regression. If bounded fitting/repair cannot compensate for a valid deletion,
one explicit rollback/refit may revoke it. Unusable assets are never restored
as fillers. The final styled preflight re-measures module/container geometry;
a separate post-Critic admission guard preserves raw scores but blocks unsafe
archives/templates and safe-parent promotion. The existing capacity limits,
95%-100% utilization goal, Critic rubric/thresholds, and same-family Validate
topology requirements remain unchanged. Full details and audit locations are
in [IMPROVE_REVISION_REPORT.md](IMPROVE_REVISION_REPORT.md).

## Whole-poster density and source-visual retention update

The loop now measures the compiled poster as a whole, not only each zone's
internal fill. The text-free composition audit records unallocated body area,
the largest contiguous empty rectangle, the largest cross-zone gap, and the
largest within-zone gap. Exact candidate ranking considers these measurements
alongside worst-zone utilization and the largest unused zone bottom. A seeded
near-best choice cannot knowingly replace local blank space with a materially
larger whole-poster void. These are geometry measurements, not a perceptual
judgment on the rendered pixels.

Feasible but sparse layouts enter bounded repair below 90% zone utilization or
when a zone's bottom gap exceeds two measured body lines. The loop keeps a
source-visual manifest, marks important original key/result/method visuals,
and reserves a visual-rich beam branch. If a key visual disappears during fit,
it may try to restore the approved original visual in its source section and
re-fit the same family. Restoration requires exact compile/preflight and cannot
drop already visible claims or visuals, change strict Validate topology, or
materially worsen whole-poster whitespace. The default limit is two visual
restoration attempts per family and four per global iteration. It never
invents visual assets or scientific text. When no valid visual placement exists,
the omission remains visible in the repair report and Critic audit metadata.

Content repair still uses grounded, verified changes only. A sparse repair is
adopted only after a material worst-zone improvement and no global-whitespace
or visible-content regression. The Critic records the composition and source
visual-selection evidence without changing its calibrated score or admission
threshold. The independent standalone classic route is unchanged.

Read-only inspection of historical I13 showed that the new repair trigger
would activate; its compiled board had approximately 6.55% unallocated body
area and an 11.17% largest contiguous empty rectangle. Historical artifacts
were not rewritten. No live model/GPU poster run was performed.

## Resulting behavior

The optimization route searches each selected layout family using the original
prefix claim choices plus up to twelve additional non-prefix claim subsets per
module. A failed four-wide assignment beam is retried at width eight. Up to
two variants per family with small measured height pressure may be reconsidered
without the conservative fast-estimate reserve; every selected variant still
requires exact layout compilation and preflight. Bounded pressure evidence
keeps the closest, worst, and most-advanced assignment samples separately.
Near-miss variants are ranked across the family by completed assignment count
and then overage, including pressure found only by the wider beam. The
effective minimum section count respects zone capacity. Schema-v5
`layout_feasibility_report.json` records the failure class, pressure samples,
search limits, recheck count, and exact outcomes. Its displayed trials remain
limited to twelve, but a separate repair-candidate list is built first from
all searched variants, including the possible thirteenth and fourteenth.
That list is capped at 128 de-identified numeric/ID samples and records whether
the cap was reached; the planner does not infer “no height pressure” from a
truncated diagnostic. Schema-v3/v4 summaries remain readable. Successful
reports retain the old `safety_factor` as the configured default and add the
selected candidate's actual factor and standard/adaptive/near-miss search path.
The independent compiled-preflight report stays at schema v4. Samples are
observations, not proof of physical impossibility.

When fitting fails with a repairable text-height near miss, or an exact fitted
zone is below the configured 90% repair threshold or has a large bottom gap, `CapacityActionPlanner`
requests allow-listed actions from the existing `GroundedContentOptimizer`.
Overfull modules first try a shorter previously verified same-root variant;
otherwise they request a verified compact variant. Sparse modules first try a
relevant existing verified claim, then a new paper-supported claim. The
optimizer never accepts arbitrary Planner-provided scientific prose.
An exact-compile/preflight failure alone does not request text compaction.
When sampled text height cannot cover the overage, repair is skipped with an
explicit reason. If the bounded repair-candidate list itself was truncated
without a usable action, the reason states that diagnostic limit explicitly.

Each repair uses a private working copy of the storyboard, verified-content
bank, supplemental-evidence bank, and content selection. The changed content
is re-fitted to the same family. Validate passes the original saved zones to
that re-fit. A failed repair leaves the candidate's original scientific memory
unchanged; accepted content reaches Campaign-wide memory only through the
ordinary committed-iteration path. Defaults are two repair rounds per family,
four per global iteration, two content actions per round, and no content
repair for an estimated overage above two inches. These limits are configured
under `capacity_repair` in `config/critic_config.yaml`.
Before each new attempt the runner restores the committed Campaign-wide
content banks and last committed content selection. Explore/Validate keep
Campaign history while discarding provisional choices from an abandoned
attempt. This closes a pre-existing path where an uncommitted Improve attempt
could otherwise leave provisional verified variants in process memory.

New compact/additional claims still pass `ClaimVerifier`. Its proposed
`corrected_text` now receives a second complete semantic pass on the final
wording; a second proposed correction is not automatically published. A
separate source-excerpt audit checks that compact wording retains necessary
scientific conditions and that additions are relevant and non-redundant.
Previously saved variant wording is reverified when reused. Supplemental
evidence is published only when the corresponding claim verifies and is
actually placed. Source search ranks bounded windows across parsed paper
chunks, and each accepted excerpt must occur in its selected source window.

The loop writes `content/capacity_repair_report.json` for the latest attempt
and preserves each attempt's repair report at
`iterations/<N>/attempts/<attempt>/capacity_repair_report.json`; this includes
abandoned layout-fit attempts and committed candidates, so later retries do
not erase predecessor diagnoses. Terminal retry events show near-miss rechecks
and repair status/skip reason; repair rounds also have a compact event. The
report and content revision are included in committed iteration snapshots. The standalone
one-shot classic route is unaffected. Critic still decides poster acceptance
after rendering; improved fit alone does not archive a poster or template.

## Verification and limits

CPU regressions cover non-prefix selection without losing shorter prefix
fallbacks, bounded closest/worst/advanced pressure sampling, cross-variant
ranking, wider-beam-only near misses, exact rejection after a relaxed fast fit,
nontext repair refusal, per-attempt report persistence, retry terminal
diagnostics, near-pressure action selection, a repairable fourteenth variant
hidden by the display cap, bounded repair-candidate payloads, legacy summary
compatibility, and actual selected fast-estimate factor/path reporting,
successful fixed-zone adoption, rollback of failed content, later source-chunk
retrieval, and refusal to publish a corrected sentence that fails its final
semantic check. The original capacity-search update passed 214 CPU tests plus
5 subtests. The whole-poster update passed 222 CPU tests plus 5 subtests; four
third-party deprecation warnings remain unrelated.

No live model-backed poster run was performed. The model-based semantic and
editorial checks lower the risk of wrong scientific wording but cannot prove
zero factual errors. When evidence is absent, ambiguous, or verification
fails, the optimizer keeps the prior verified content or abandons the repair.
The 95%-100% module-fill band remains a design target, never a reason to invent
or repeat scientific information.
