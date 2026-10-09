# Capacity search and grounded text repair (2026-10-09)

## Resulting behavior

The optimization route searches each selected layout family using the original
prefix claim choices plus up to twelve additional non-prefix claim subsets per
module. A failed four-wide assignment beam is retried at width eight. Up to
two variants per family with small measured height pressure may be reconsidered
without the conservative fast-estimate reserve; every selected variant still
requires exact layout compilation and preflight. The effective minimum section
count respects zone capacity. `layout_feasibility_report.json` records the
failure class, pressure samples, search limits, and exact outcomes.

When fitting fails with a repairable text-height near miss, or an exact fitted
zone is severely sparse (below 70% utilization), `CapacityActionPlanner`
requests allow-listed actions from the existing `GroundedContentOptimizer`.
Overfull modules first try a shorter previously verified same-root variant;
otherwise they request a verified compact variant. Sparse modules first try a
relevant existing verified claim, then a new paper-supported claim. The
optimizer never accepts arbitrary Planner-provided scientific prose.

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

The loop writes `content/capacity_repair_report.json` and a compact terminal
event with repair status and consumed per-iteration rounds. The report and
content revision are included in committed iteration snapshots. The standalone
one-shot classic route is unaffected. Critic still decides poster acceptance
after rendering; improved fit alone does not archive a poster or template.

## Verification and limits

CPU regressions cover non-prefix selection without losing shorter prefix
fallbacks, near-miss exact opportunity, near-pressure action selection,
successful fixed-zone adoption, rollback of failed content, later source-chunk
retrieval, and refusal to publish a corrected sentence that fails its final
semantic check. Full CPU suite: 203 passed plus 5 subtests. The suite reports
four third-party deprecation warnings unrelated to this change.

No live model-backed poster run was performed. The model-based semantic and
editorial checks lower the risk of wrong scientific wording but cannot prove
zero factual errors. When evidence is absent, ambiguous, or verification
fails, the optimizer keeps the prior verified content or abandons the repair.
The 95%-100% module-fill band remains a design target, never a reason to invent
or repeat scientific information.
