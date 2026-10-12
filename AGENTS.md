# PosterGen Development Guide

This file is the persistent development context for AI coding agents working in
this repository. Read it completely before inspecting or modifying the project.

## Project Purpose

PosterGen converts an academic paper into an academic poster. It extracts and
grounds scientific content from a PDF, selects figures and tables, plans a
controlled layout-family composition, and exports an editable PowerPoint file
plus a PNG preview.

The independent one-shot classic route retains the original editable
three-column Balancer path. The optimization route treats classic three-column
as an equal member of twelve controlled layout families and can search
bounded paper-aware geometry variants, and reuse promoted paper-free layout
archetypes through a versioned LayoutSpec and deterministic coordinate compiler.

This repository is a heavily modified fork of:

- https://github.com/Y-Research-SBU/PosterGen

Do not assume the upstream README or upstream architecture describes the local
implementation. The local source code and this file are authoritative.

## Repository Safety

- Run `git status --short` before making changes.
- The worktree may contain extensive user-owned modified and untracked files.
- Preserve all unrelated changes. Never discard, overwrite, reset, or clean the
  worktree unless the user explicitly requests it.
- Do not use `git reset --hard`, `git checkout --`, `git clean`, or broad file
  deletion commands.
- Do not read, print, modify, or commit secret values from `.env`.
- Do not commit generated data, model logs, uploaded papers, or poster outputs
  unless the user explicitly requests it.
- Historical files under directories named `old versions` are references only
  and are not part of the active pipeline.
- Prefer small, focused changes. Avoid unrelated formatting or rewrites.

## Current Active Pipeline

The active LangGraph workflow is defined in `src/workflow/pipeline.py` and is a
linear graph:

1. `parser`
2. `evidence_builder`
3. `narrative_planner`
4. `claim_writer`
5. `claim_verifier`
6. `curator` (implemented by `grounded_curator_node`, not legacy `curator.py`)
7. `color_agent`
8. `section_title_designer`
9. `layout_optimizer`
10. `font_agent`
11. `renderer`
12. `critic`

In compact form:

```text
PDF + logos
  -> Parser
  -> Evidence Builder
  -> Narrative Planner
  -> Claim Writer
  -> Claim Verifier
  -> Grounded Curator
  -> Color Agent
  -> Section Title Designer
  -> Layout Optimizer
  -> Font Agent
  -> Renderer
  -> Critic
  -> PPTX + PNG
```

The graph currently has no conditional failure edges. Agents append messages to
`state["errors"]`; the pipeline checks accumulated errors after graph execution.

The user-controlled workflow is exposed by
`src/workflow/optimization_loop.py`; its public `run()` delegates to the active
engine in `src/workflow/campaign_runner.py`, which owns campaign persistence,
resume, finite Batch budgets, multi-Lineage Portfolio scheduling, and iteration
commits. The CLI and WebUI both launch this path. Parser
through ClaimVerifier run once per compatible campaign, and their scientific
state is persisted as immutable foundation data. Each iteration is scheduled as
new exploration, existing-Lineage improvement, or template validation.
Improvement iterations run RevisionPlanner and
GroundedContentOptimizer before the design agents, Renderer, and Critic.
Planner/content optimization share the current `story_board`; the visible
parent is read-only comparison/fallback data, never an implicit optimizer
input. Improve carries a candidate revision contract and branch-local recovery
policy, verifies actual compiled effects, checks deletion-induced whitespace
regression, and may explicitly revoke a harmful deletion with one same-family
refit. Automatic repair cannot silently restore intentionally excluded assets
or claim roots. A post-Critic revision admission veto preserves raw scores and
diagnostics but prevents unsafe archives/templates and best-base advancement.
Loop-family layout fitting may also invoke bounded GroundedContentOptimizer
capacity repair from Explore, Improve, or Validate before rendering when a
measured near miss or severely sparse zone warrants it. This stays within the
same candidate attempt; exact compile/preflight and the ordinary Critic remain
mandatory. Uncommitted repair content is discarded with the attempt. The
standalone classic route never enters capacity repair.
The one-shot CLI in `pipeline.py` sets `generation_route=standalone_classic`;
the Critic-loop entry point sets `generation_route=optimization_family`. The
one-shot route does not register loop templates, archetypes, or design memory.
The optimization-loop design subgraph inserts LayoutPreflight after FontAgent.
Explore does not retrieve saved poster templates or their content: it rotates
layout families and searches controlled paper-aware geometry/content assignments.
It may sample at most two promoted paper-free geometry archetypes beside fresh
seed-family variants. Improve can read one eligible same-family, other-Lineage
template as relational inspiration after warmup; exact saved topology is used
only by strict validation.
Explore selection-policy v1 opens all registered, enabled families regardless
of semantic flags. It first restricts selection to the least-used eligible
families, then draws with bounded weights `1 + bonus * match` (bonus 0..0.5,
match 0..1). Existing `family_counts` measure committed Explore/Improve design
uses, not pure exploration attempts. Current-iteration fit exclusions never
reenter an exhausted pool. Batch `schedule_policy.family_selection` freezes
enabled IDs, profile schema, coverage basis and bonus. Legacy resumable Batches
upgrade once at resume, with explicit migration metadata; historical commits
are not rewritten. Campaign resume also restores the Portfolio scheduler seed.
Profile v2 reads NarrativePlanner `title_intent`/`narrative_role`, with legacy
title aliases and text-free signal provenance; IDs are not scientific text.
Its legacy `profile_key` remains unchanged for validation/retrieval. Signals
are selection hints, not proof of scientific relationships. Each session saves
the derived profile and each Explore attempt saves its selection report.
A deterministic preflight runs before Renderer. Infeasible Explore attempts are
persisted for diagnosis, exclude the failed family, and retry the same global
iteration without consuming Batch budget or calling Critic. Improve retries
bounded parent-local geometry and freezes the actually visible optimized parent
board, LayoutSpec, and both content-selection identities for its final safe
fallback. A digest-verified exact fallback is committed as a no-change
stagnation event that consumes Batch budget but creates no archive, template,
poster outcome count, archetype, or global design event. If exact recovery still
fails, mixed mode persists a Batch-local Lineage recovery block and reschedules
the same global iteration without consuming budget; pure Improve remains
fail-closed. Validate preflight failure commits an unscored strict-transfer attempt
without calling Critic or changing poster accepted/rejected counts. A quality
score never terminates a Batch early.

Unexpected generation exceptions are not poster-quality rejections. The loop
captures the innermost exception in an attempt-local failure report, retains
the pre-repair fit and partial repair audit, and fails the Batch without
Critic, budget consumption, rejection learning, or template publication.
Immediately before Critic, the current candidate must be marked rendered and
own nonempty PPTX/PNG files in its attempt output directory. Known geometry
failures retain the existing Explore/Improve retries and unscored Validate
semantics. Never silently retry an unknown programming error as another family.

Historical loop-classic snapshots are not trusted merely because a replayed
Lineage file carries the current writer version. The committed candidate's
layout origin, inner LayoutSpec schema/fingerprint, feasible solver report,
passed preflight, family topology, and visible section ownership must agree
before Improve may use it. Compatible best/latest tracks can still be used;
otherwise mixed mode skips that Lineage without losing the iteration budget,
and pure Improve ends `UNAVAILABLE` before model work when no eligible parent
remains (or its target is incompatible). Historical artifacts and
Critic feedback remain intact; no automatic layout rebase is performed.

Graceful stop finishes the current candidate evaluation; force-stop exits at
the next safe agent boundary after the current blocking model/render call
returns. A force request observed after Critic but before commit abandons the
attempt, deletes its uncommitted PPTX/PNG, and consumes neither Batch budget nor
learned knowledge. A request arriving during atomic commit finishes that commit
before pausing. Pause/resume/stop controls are provided by `LoopControl`.

Campaigns span process launches and are matched by hashes of the PDF/logos,
poster dimensions, foundation schema, and layout-engine schema. A Campaign can
retain multiple independently resumable finite Batches, each targeting 100
committed iterations by default, but its exclusive lease permits only
one `IN_PROGRESS` Batch. Graceful stop persists the selected Batch as `PAUSED`;
another Batch may then be created without deleting it, and either can later be
selected explicitly. Batch IDs are Campaign-scoped, monotonically increasing,
and never reused. `FAILED_REQUIRES_USER` is immutable and cannot be
resumed; create the next Batch to continue from the Campaign's next uncommitted
global iteration. Each Batch freezes its scheduling policy/target but reads the
latest Campaign Portfolio, Campaign-wide verified content/evidence memory, and
eligible global knowledge whenever it resumes. Lineage snapshots contain
branch-local design plus `content_selection`; they deliberately exclude the
shared `verified_content_bank` and `supplemental_evidence_bank`, so resuming
an old Lineage cannot roll Campaign knowledge backward. Each Lineage now keeps three independent tracks: latest attempt, best safe
rejected working base, and best accepted base. Improve loads the best accepted
base when one exists, otherwise the rubric-scoped best-promising snapshot;
`latest_feedback.json` and bounded `revision_history.json` still provide the
newest committed attempt's full Critic/revision feedback. A promising rejection
is selected lexicographically by repairability, critical/major issue counts,
poster score, presentation score, and iteration. It remains a Lineage-local editable base only: it is never archived, templated,
or promoted to an archetype, and it creates no separate reusable global base.
Its de-identified Critic outcome still follows the ordinary committed-rejection
path into bounded global design feedback. Feedback and promising snapshots cannot cross
Lineages, Campaigns, or rubric versions.
Every Batch stores
creation/resume/last-iteration knowledge watermarks. Each committed iteration
records the exact Campaign-content, Portfolio, template-library, and global
design-memory identities it consumed. `iterations/<N>/COMPLETED.json` is the
only commit marker and records `batch_id`; `batch_state.json` owns an explicit
committed-iteration ledger, so interleaved Batches may own non-contiguous global
iterations. A stale attempt is abandoned without consuming Batch budget.
CLI/WebUI can select an exact Campaign or paused Batch, deliberately create a
new Batch, or start an independent Campaign.

Commit accounting uses draft state: counters, best bases, Portfolio, selection
and scientific additions are rolled back on pre-marker failure. Each new
committed attempt stores `commit_runtime_state.json`; its digest is bound into
`COMPLETED.json`. Recovery derives poster/template/evidence counts from complete
commit history and restores new runtime/Batch projections without changing
failed or archived lifecycle states. Missing history or a missing/corrupt
digest-bound projection fails closed, never resets genuine work to zero.
The legacy rejection journal is now appended only after commit, under a lock
with an idempotent Campaign/iteration/candidate identity, and replay is safe
even after an append-before-publication crash. Legacy uncommitted entries are
retained with append-only invalidations in `rejection_memory_corrections.jsonl`;
this journal is not the global Planner knowledge store.

The persistent Portfolio targets 45% exploration and 55% existing-Lineage
improvement over mixed-mode Campaign history. If all active Lineages stagnate,
the scheduler forces exploration. Strict template validation is absent from
mixed scheduling and runs only in a pure validate Batch; pure-mode iterations
never distort mixed quotas. It retains multiple branches, separates latest from
best candidates, caps active Lineages at eight, and carries family coverage debt
across Batches.

## Important Modules

### Entry points and shared infrastructure

- `src/workflow/pipeline.py`
  - CLI entry point and LangGraph construction.
  - Captures stdout/stderr in `run.log`.
  - Writes timing, token, model, and API-call information.
- `src/state/poster_state.py`
  - Defines `PosterState`, `ModelConfig`, token accounting, and timing metrics.
  - Initializes per-iteration `global_design_context` for bounded shared
    Critic priors; it contains no scientific prose or exact template geometry.
  - Creates timestamped output directories.
- `utils/langgraph_utils.py`
  - Creates provider-specific chat clients.
  - Handles text/vision calls, JSON response mode, retrying, and API-call
    tracking.
- `utils/agent_policy.py`
  - Applies per-agent settings from `config/agent_policy.yaml` without mutating
    the shared base model configuration.
- `config/poster_config.yaml`
  - Layout, typography, color, measurement, rendering, and capacity constants.
- `config/critic_config.yaml`
  - Schema-v4 evaluator, explicit dimension-source weights, shared poster/template
    admission, four level-isolated global retrieval seat limits (10 per
    level/family), promotion, storage policy, bounded explore geometry search,
    preflight retry limits, archetype promotion, and unlimited complete
    rejected-poster diagnostic retention.
  - Critic system `4.2.0` uses rubric `academic_poster_multifamily_v4`. It
    gates actual rendered-body bounds/collisions and empty or severely unused
    loop zones; weighted module-share overage is advisory, not physical overflow.
  - The existing 78-point archive threshold is unchanged. The old 85-point
    template threshold is now a high-potential label, never a second save gate;
    calibrate scores before changing admission.
- `config/agent_policy.yaml`
  - Per-agent temperature, output length, JSON mode, and thinking policy.

### Scientific content pipeline

- `src/agents/parser.py`
  - Uses Marker to convert the PDF to Markdown and extract visual assets.
  - Extracts captions, title/authors, legacy ABT narrative, and paper-semantic
    visual classes from IDs, captions, types, and aspect ratios, not image pixels.
    Classification never assigns poster columns or layout families.
  - `src/agents/visual_classification.py` normalizes model/fallback output:
    every available ID belongs to exactly one of five scientific-role lists;
    `key_visual` is an optional pointer, not a sixth role. It repairs invalid,
    duplicate, or omitted IDs and records caption-only provenance in
    `visual_classification_report.json` without raw scientific text.
  - Splits Markdown deterministically by headings via `utils/section_utils.py`.
  - Large sections are chunked at approximately 12,000 characters without
    silently truncating scientific content.
- `src/agents/evidence_builder.py`
  - Extracts atomic evidence from every parsed section/chunk.
  - A normalized `source_excerpt` must occur verbatim in the source chunk.
  - Metric direction is retained only when grounded by a supporting excerpt.
- `src/agents/narrative_planner.py`
  - Organizes evidence IDs into poster sections without writing poster prose.
  - Has a deterministic evidence-type fallback.
- `src/agents/claim_writer.py`
  - Writes concise poster claims from evidence assigned to each planned section.
  - Every claim must cite valid evidence IDs from that section.
  - Claims containing numbers not found in cited evidence are discarded.
- `src/agents/claim_verifier.py`
  - Applies deterministic numeric validation.
  - Checks cross-evidence entity, metric, and comparison consistency.
  - Uses a semantic verifier and independently re-runs semantic verification
    on the exact final wording of any proposed correction. Deterministic
    numeric and cross-evidence checks run before that final pass.
  - Verification failure is fail-closed: the claim is not published.
- `src/agents/grounded_curator.py`
  - Arranges verified claims and approved visuals into sections. The
    optimization-family prompt does not assign columns; its retained
    `column_assignment` field is a compatibility placeholder ignored by the
    family solver. The standalone classic prompt keeps column selection.
  - The model may select/group claim IDs and visuals, but cannot rewrite claim
    text.
  - Unknown IDs are removed and omitted verified claims are restored.
  - In the loop route, a valid omitted key visual may be offered to a matching
    verified scientific module as an optional solver candidate, never forced
    into the poster. `visual_curation_report.json` records available, selected,
    and unselected visual IDs and the key-seed decision.

### Design and rendering pipeline

- `src/agents/color_agent.py`
  - Uses the affiliation logo with the vision model to select a theme color.
  - Falls back to the key figure and then to the configured navy theme.
  - Records palette provenance and applies only named deterministic accessible
    palette/contrast presets selected by RevisionPlanner.
- `src/agents/section_title_designer.py`
  - Produces the fixed `rectangle_left` section-title treatment in code.
- `src/agents/layout_with_balancer.py`
  - Dispatches by explicit route. Only the standalone classic path uses the
    legacy Balancer. Every loop family, including classic three-column, runs
    the same paper-aware feasibility solver and deterministic LayoutSpec
    compiler. Strict validation preserves its saved topology.
- `src/agents/balancer_agent.py`
  - May reorder/move existing sections, change vertical priorities, select a
    subset of existing claim IDs, and remove approved visuals.
  - Must not create sections, rewrite section titles or scientific text, invent
    claim IDs, or add unapproved visuals. Sanitization enforces these rules after
    the LLM response.
- `src/agents/layout_agent.py`
  - Preserves the original three-column renderer for the standalone route and
    compiles every loop family into bounded zones using the same
    inch-based text, visual, logo, and section measurement helpers.
    Solver-selected geometry carries `iteration_random_seed` so final layout
    generation does not silently rebuild the default family LayoutSpec.
    Loop-only body-text measurement reserves LibreOffice's observed 1.20 line
    advance and aligns visible section gaps to the configured body-line target;
    the independent standalone classic route retains its prior behavior.
- `src/layout/families.py`
  - Defines LayoutSpec schema v3, the LayoutFamilyRegistry, PaperProfile-aware
    family applicability, strict explicit assignment validation, deterministic
    geometry compilation, geometry fingerprints/mutation provenance, and
    generalized region utilization analysis.
  - Registers twelve initial families: classic three column, asymmetric two
    column, four-column modular, central hero with side rails, top hero with
    bottom grid, horizontal narrative bands, method flow spine, comparison
    split, result dashboard cards, small-multiples matrix, timeline/stage
    narrative, and modular editorial mosaic.
  - Models never supply final x/y/width/height. RevisionPlanner may change only
    relational zone assignments, reading order, and the primary anchor.
- `src/layout/paper_profile.py` and `src/layout/family_selection.py`
  - Own the model-free profile-v2/semantic-rule-v1 extraction, bounded matching,
    policy validation, profile digest and explicit selection-exhausted error.
    `templates.library.build_paper_profile` remains an import-compatible alias.
    Role signals have strength 1; title and broad visual-count hints have
    strength 0.5. Unobserved signals are not negative evidence. Matching uses
    the strongest applicable hint rather than accumulating arbitrary bonuses.
    These strengths are deterministic policy values, not calibrated confidence.
  - Preserve conditional Solver role constraints for method spine, result
    dashboard and top hero, and share narrative-role normalization. Internal
    stage/comparison zone IDs do not generate scientific prose. Curator and
    RevisionPlanner prompts explicitly prohibit inventing relationships to fit
    a family. No new semantic-proof evaluator or Critic scoring gate is claimed.
- `src/layout/feasibility.py`
  - Generates bounded seeded geometry and permitted split/span variants for
    all twelve families and runs
    a joint content/layout beam search over exact grounded claim IDs, approved
    visuals, and zone assignments. Conservative fast measurements shortlist
    candidates; exact measurements restore fitting verified claims, approved
    visuals, and whole grounded modules, then compile and preflight near-best
    candidates. Reports separate estimated and compiled zone utilization.
    Every historical prefix claim subset remains available, with a bounded
    number of additional non-prefix subsets. Failed narrow beams retry with
    wider search. Bounded closest, worst, and most-advanced height-pressure
    samples are retained per variant; up to two near-miss variants are ranked
    across the family by assignment progress and overage and may bypass only
    the conservative fast-estimate reserve before exact compile/preflight.
    Effective minimum section count respects available zone capacity.
    A seeded choice is limited to near-best exact scores to retain diversity
    without knowingly selecting a sparse outlier. The exact-candidate cap,
    refill-step cap, and near-best score window are set in
    `config/critic_config.yaml`. Scientific prose is never
    rewritten by the Solver.
    Exact scoring includes worst-zone utilization, largest bottom gap,
    priority-weighted approved visual retention, and whole-poster whitespace.
    A visual-rich beam branch and near-best non-displacement guard reduce the
    chance of choosing a text-only or globally sparse fit merely because it is
    locally dense. A bounded source-visual restoration request may target
    original approved assets without changing scientific prose.
    Explore may expand its first four bounded variants to twelve when no exact
    fit or a sparse first-pass result is found; reports record this choice.
  - Failed bounded searches emit a schema-v5 `layout_feasibility_report.json`
    with stage/reason code, attempted/fast-feasible variant counts, bounded
    per-variant blocker evidence, bounded section/zone closest/worst/advanced
    height-pressure samples, near-miss recheck count, exact
    compile/preflight issue identifiers, and search limits. Frequent gates are
    observations, not proof that a family is intrinsically infeasible. Reports
    omit raw scientific text and do not alter candidate selection or scoring.
    The display-only `trials` cap is twelve, but up to 128 text-free
    `repair_pressure_candidates` are derived from all searched variants before
    that cap. Count/truncation metadata prevents a missing displayed trial from
    being mistaken for absent repair pressure. Older v3/v4 reports remain
    readable. Successful reports distinguish configured default safety factor
    from the selected standard/adaptive/near-miss candidate's actual factor;
    compiled-preflight report schema remains v4.
- `src/layout/whitespace.py`
  - Measures compiled whole-poster composition from exact section rectangles:
    unallocated body fraction, largest contiguous empty rectangle fraction,
    largest cross-zone gap, and largest within-zone gap. Geometry-only
    non-regression guards prevent a local-fill improvement from relocating
    materially more blank space to the rest of the poster.
- `src/layout/capacity_repair.py`
  - Converts sampled text-height pressure and feasible zones below 90% fill
    or with a bottom gap above two body lines into bounded repair. Source key
    visual omission also triggers repair. A source-visual manifest survives
    Lineage snapshots; restoration re-fits the same family and source section,
    preserving visible content, strict Validate topology, exact preflight,
    and whole-poster whitespace. Visual defaults are two attempts per family,
    four per global iteration. Text actions use the existing grounded optimizer
    on a staged working state and require material density improvement without
    content or global-whitespace regression. Text defaults remain two rounds
    per family, four per global iteration, two actions per round, and a two-inch
    estimated overage gate.
    `capacity_repair_report.json` records actions/results or a skip reason
    without claim prose. Only actionable text pressure triggers compaction;
    exact geometry/preflight failures and nontext overage do not. The report
    is copied into each unique Campaign attempt directory, including
    abandoned fit retries, preventing later retries from overwriting it.
    Retry terminal events show near-miss rechecks and repair status/skip reason.
    The standalone classic route does not enter this repair path.
- `src/agents/layout_preflight.py`
  - Runs after FontAgent and before Renderer. It fail-closes on canvas/zone
    bounds, overflow, missing or duplicated section ownership, child/container
    ownership and bounds, undersized section-title textboxes, intra-section flow
    overlap, and invalid LayoutSpec topology so known-bad geometry never reaches
    rendering or Critic.
- `src/agents/render_fit_audit.py` and `src/layout/render_fit.py`
  - Loop-only post-render audit exports the candidate PPTX to a temporary PDF,
    uniquely matches editable body text without storing scientific prose in the
    report, and measures actual glyph bounds against planned boxes, canvas, and
    other modules. Confirmed overflow/collision retries Explore/Improve before
    Critic and without Batch budget; the first three such failed retries per
    iteration retain `render_fit_preview.png` beside the attempt report.
    Strict Validate sends the finding to Critic as a hard geometry issue.
    Partial/unavailable extraction is inconclusive, not a
    false hard failure. The standalone one-shot route does not run this audit.
- `src/layout/archetypes.py`
  - Stores accepted paper-free geometry blueprints in a locked global JSON
    registry. Same-paper candidates are immediately reusable; foreign-paper
    retrieval requires three accepted posters spanning at least two papers.
    Ranking uses only the independent structural template design score.
- `src/layout/text_height_measurement.py`
  - Uses `python-pptx` fit behavior plus cached Fontconfig resolution to measure
    the same regular/bold system font face LibreOffice will substitute; bundled
    files remain the fallback when Fontconfig is unavailable.
  - Its margins, wrapping, bold-face, and line-height assumptions must remain
    synchronized with the renderer.
- `src/agents/font_agent.py`
  - Identifies keywords and applies custom bold, italic, and color markup.
  - Applies Critic-directed deterministic emphasis-density, font-family, and
    typography-hierarchy presets; it accepts no arbitrary Planner font values.
  - Must not insert or rewrite visible scientific text.
- `src/agents/renderer.py`
  - Publishes `current_candidate` and `render_diagnostics` so Critic evaluates
    exact PPTX/PNG artifacts rather than an internal plan.
  - Creates a single-slide editable PPTX with `python-pptx`.
  - Preserves simple inline subscript/superscript as editable DrawingML runs.
  - Renders supported display fractions as high-resolution PNG images.
  - Uses LibreOffice headlessly to convert the PPTX to PNG.
- `utils/inline_math.py` and `utils/display_formula.py`
  - Implement the safe inline-script and display-formula grammars.
- `utils/evidence_utils.py`
  - Implements number extraction/normalization and evidence-reference checks.

### Critic and continuous optimization

- `src/critic/engine.py`
  - Runs independently registered evaluators and aggregates seven stable
    dimensions through explicit evaluator-source weights; artifact validity is
    a hard gate only and never inflates a quality dimension.
  - Critic v4 emits report schema v3 with nested `poster_evaluation`, explicit
    source contributions and submetrics, plus a reserved `task_evaluation`;
    compatibility top-level fields remain available.
  - Saves the full actionable `critic_report.json`; `rejection_summary` is only
    a concise synopsis, while `issues` carries observations, required outcomes,
    allowed operations, and forbidden operations for RevisionPlanner.
  - `archive_eligible` and `template_eligible` now share one gate. A separate
    `presentation_quality_score` omits scientific-integrity weighting only for
    auditing; scientific grounding still gates archive admission. The old
    stricter conditions are exposed as `high_potential_template`, not used to
    reject template storage. Strict-transfer validation is a separate
    `task_evaluation` in the same persisted Critic report.
- `src/critic/evaluators.py`, `src/critic/quality.py`,
  `src/critic/section_fit.py`, `src/critic/layout_family.py`, and
  `src/critic/visual.py`
  - Enforce artifact validity, geometry, grounding, typography hierarchy,
    layout-region capacity, independent module fit, content adequacy, palette
    provenance/WCAG contrast, approved-asset integrity, and multimodal quality.
  - Information/narrative quality covers layering, coverage, depth,
    completeness, structure, flow, and concision without requiring ABT.
  - The expanded visual rubric covers layout, whitespace, anchor, balance,
    color, typography, alignment, robustness, and visual relevance without
    preferring a layout family or fixed image/module count.
  - Visual issue locations are validated against the actual visible storyboard
    and LayoutSpec; nonexistent or section/zone-inconsistent model identifiers
    are removed while the raw location remains audit evidence.
  - Section fit targets 95%-100% utilization with controlled inter-module gaps;
    97.5% is the planning target, not permission to add filler. Every loop
    family uses actual LayoutSpec zone heights. Empty zones or zones with
    severe unused bottom area now fail the section-fit hard gate.
    A section exceeding its weighted ideal allocation is a major repair hint,
    not a physical overflow hard gate. Actual region or rendered-text bounds
    remain critical. This distinction is rubric-versioned.
    Whole-poster whitespace and omitted source-visual evidence are recorded in
    Critic metadata for diagnosis; this update does not change Critic weights,
    hard gates, or archive thresholds without calibration.
  - New methods can be registered through `PosterCritic` and enabled or
    versioned in `config/critic_config.yaml`.
  - LayoutFamilyCritic validates registered families, normalized non-overlapping
    zones, unambiguous reading order, compiled section ownership, and primary
    anchor occupancy; family-specific geometry is evaluated in addition to
    common hard gates.
- `src/agents/revision_planner.py`
  - Converts the full Critic report into allow-listed layout, approved-visual,
    deterministic style-preset operations, and content-action requests.
  - Raw coordinates, colors, font names/sizes, and replacement scientific prose
    are rejected. It may request grounded text changes but never supplies them.
  - Uses the shared allow-list in `src/agents/revision_operations.py`.
    Layout changes are LayoutSpec relations only: move/swap zone ownership,
    reading order, and primary anchor. Legacy column operations are either
    safely translated when unambiguous or rejected.
  - Receives two distinct Lineage contexts: the best accepted base, or the
    best safe promising rejection when no accepted base exists, plus the latest
    committed attempt feedback/history, preventing failed
    revisions from being forgotten without replacing the stable base.
  - Plan schema v4 gives candidate-local operation/action IDs. Destructive
    operations require a reason and scoped actionable Critic issue references;
    duplicates are occurrence-scoped and protected visuals need stronger
    object-specific evidence or a justified replacement. Later explicit
    `restore_visual` is restricted to readable approved original source
    occurrences; excluded-root claim reconsideration is staged until placement.
- `src/agents/revision_contract.py`
  - Derives final sequential board effects, branch recovery exclusions/owners,
    text-free deletion evidence, and schema-v3 execution audit statuses.
  - Prefers exact safe candidates, compares parent/candidate global holes,
    utilization and gaps using existing 0.01 fraction / 0.35-inch tolerances,
    and supports one explicit valid-content rollback/refit. Missing historical
    baselines are labeled and remain subject to absolute preflight/Critic gates.
  - Final styled preflight checks actual assets, module importance, adjacency
    gaps and visible text (including renderer literal escapes). Final
    `revision_admission` never changes raw Critic scores/poster evaluation.
    Vetoed candidates cannot advance observed best or best-promising tracks.
    See `IMPROVE_REVISION_REPORT.md` for persistence and acceptance semantics.
- `src/agents/content_optimizer.py`
  - Executes bounded requests to use a same-root verified variant, make a compact
    variant, restore a relevant omitted claim, or add a claim from evidence.
  - Newly generated prose must pass the full ClaimVerifier. Supplemental
    evidence must be a new exact normalized excerpt from a source chunk.
    Generated compactions/additions additionally pass a source-excerpt audit
    for scientific qualifiers, module relevance, and non-redundancy. Existing
    bank variants are reverified when reused. Supplemental evidence and new
    variants remain staged until verification and board placement succeed;
    failed actions cannot leak them to Campaign memory. Source search ranks
    windows across paper chunks rather than inspecting only the first two.
  - Base `verified_claims` stay immutable. Verified variants and supplemental
    evidence are append-only Campaign-wide memory materialized from committed
    iterations. `content_selection` remains Lineage-local and is sanitized
    against the latest shared banks whenever an older Lineage is restored.
  - Explicit `board_override` takes precedence; empty/malformed overrides or a
    missing ordinary working board fail closed, never load the parent. Empty
    actions and disabled optimization preserve Planner edits. Automatic repair
    excludes intentionally removed claim roots; explicit later reconsideration
    revokes the exclusion only after successful grounded placement.
- `src/templates/scoring.py` and `src/templates/seats.py`
  - Score reusable structure under independent rubric `structural_template_v1`:
    topology integrity plus only design-related Critic submetrics. Scientific
    integrity, paper content quality, source poster total score, and strict
    transfer evidence never contribute. Missing evidence is marked partial or
    unscored with coverage; scores are comparable only within one rubric.
  - Derive ordinary-reference seats from the full global library: per layout
    family, at most 10 templates each at L0, L1, L2, and L3, with no borrowing
    between levels. Rank by scoring coverage/design score, suppress near
    duplicates within a level, and preserve every accepted record regardless
    of ordinary seat selection.
- `src/templates/library.py`
  - Every Critic-accepted poster in a normal design mode produces exactly one
    candidate-specific template JSON plus editable PNG/PPTX preview; rejected
    posters produce no accepted bundle/template. Pure `validate` is the
    exception: it never distills or registers a new template.
    Accepted normal templates carry `template_design_score` and versioned
    `template_evaluation`. Every committed rendered rejection in Explore or
    Improve stores an unlimited complete PNG/PPTX diagnostic bundle under
    `rejected_posters/<campaign>/<batch>/<candidate>/`. Validate stores the
    same diagnostic when the poster is rejected or when poster admission passes
    but strict transfer fails. Preflight failures have no rendered artifact;
    no-change Improve fallbacks and force-abandoned attempts are not diagnostics.
    Rejected bundles also contain Critic, feasibility, preflight, storyboard,
    styled-layout, and provenance JSON. They are staged before commit and
    published only after `COMPLETED.json`; a separate publication marker makes
    final diagnostic deletion user-controlled and prevents startup replay from
    recreating deleted files. Diagnostics are never template or design knowledge.
  - Stores exact blueprints internally, while Planner receives only relational
    bands/classes and design principles. Ordinary retrieval samples at most
    one template per family; it does not send 40 templates or exact geometry to
    Planner. New loop templates use a family-zone similarity signature rather
    than projecting every family onto left/middle/right; old signature versions
    remain comparable only to their own version. The 10x4 seats are global
    across all papers, not per-paper quotas.
  - L0 ordinary reference is source-paper-only. A successful accepted and
    topology-verified strict transfer to another paper promotes L0 to L1; L1
    may then be ordinary-referenced by foreign papers only in a strictly
    validated profile. L2/L3 are broader levels, still subject to applicability.
    Inspired `adapt`/`hybridize` acceptance does not promote levels.
  - Strict `validate` retrieval bypasses ordinary seats, recent-use cooldown,
    and the L0 restriction; it still requires an eligible paper and visual
    count. Each cross-paper template-paper task permits three committed
    attempts. The first two failures remain retryable; only the third becomes a
    finalized distinct failed-paper result. Two distinct finalized failures in
    one profile, with no success, narrow applicability; a later strict success
    restores it. Source replay is one attempt and never affects cross-paper
    applicability. The mandatory queue retains all saved templates, including
    duplicates and over-cap templates.
  - A validation attempt freezes the source template fingerprint and topology.
    A strict success stores PPTX/PNG plus report snapshots under
    `validation_evidence/` and appends that evidence only to the original
    template. It may update level, applicability, validation status, and derived
    retrieval seats. It must not change the blueprint, fingerprint, original
    structural design score/evaluation, or template previews. Failed validation
    posters are deleted after their committed reports/retry result are recorded.
    Validation never increments ordinary usage/cooldown.
  - Schema-v11 adds direct source Campaign, Batch, iteration, Lineage, mode,
    and parent-candidate provenance to each template. Older records backfill
    this chain from immutable accepted-bundle provenance when available and
    otherwise remain explicitly partial/unavailable.
  - Schema-v9 adds a semantic `knowledge_revision` and `knowledge_digest`
    without re-running validation-trial migration on valid schema-v8 records.
    The schema-v8 migration still backfills independent design scores from
    archived Critic reports, reconstructs legacy L1 cross-paper validated
    profiles, and conservatively reconstructs per-paper retry trials from
    strict usage logs. If profile proof is absent, old L1 cross-paper ordinary
    reference fails closed while strict validation remains available.
    Migration never deletes accepted bundles.
  - Registration, validation promotion, and replay recompute derived seats
    under the registry lock; usage remains idempotent by committed event ID.
    Normal design bundles stage under `accepted_posters/.pending/`; validation
    evidence stages separately under `validation_evidence/.pending/`. Neither
    is published before `COMPLETED.json`. Startup replay publishes the matching
    committed artifact, registers templates only for normal design bundles, and
    discards only the abandoned attempt's pending artifact.
  - Bundle/index records include relative `artifact_paths` for direct lookup.
    A corrupt existing index raises instead of silently resetting to empty.
    The library is global across campaigns; `--resume new` can reuse eligible
    templates after the mixed-mode template-free warmup.
  - Cooldown remains campaign-scoped; at most 128 campaign usage records are
    retained per template. Strict validation locks saved zone order, roles,
    normalized geometry, and primary anchor in the deterministic compiler.
    Legacy templates without topology remain stored but cannot demonstrate
    strict transfer until structure is reconstructed.
  - Explore retrieves no saved templates. Revise can retrieve one eligible
    same-family template from another Lineage after the mixed-mode three-step
    warmup; pure modes bypass that warmup, but pure Explore remains template-free.
    Exact coordinates and scientific prose are never sent to Planner. Family
    rotation, cooldown, near-duplicate suppression, and small relational
    contexts protect against fixation. Distillation explicitly rejects the
    standalone classic route. Newly saved templates record route and layout
    engine version. Old loop-classic templates without verifiable geometry
    remain stored but are blocked from strict transfer.
- `src/templates/preview.py` and `src/templates/transfer.py`
  - Deterministically render paper-free template/family skeletons as PNG plus
    editable-shape PPTX; check normalized topology transfer. Previews contain
    generic roles and placements, never claim prose or original figure pixels.
  - All twelve initial family PNG/PPTX pairs are tracked under
    `resource/layout_families/`; regenerate with
    `.venv/bin/python -m src.templates.preview` after changing family geometry.
- `src/workflow/optimization_loop.py` and
  `src/workflow/campaign_runner.py`
  - Run finite resumable Batches, invoke the PortfolioScheduler, persist
    reports/Lineage snapshots, restore the best accepted poster or—before the
    first acceptance—the best safe promising rejection, and keep
    rejected diagnostics out of the accepted archive and all knowledge stores.
    At each attempt boundary, restore the committed Campaign content banks and
    last committed selection; fresh Explore/Validate retain Campaign history
    while Improve can load its Lineage-local selection. This prevents
    uncommitted Improve/capacity changes from bleeding into retries.
    Complete rendered failures from every active mode use crash-safe staged
    publication. A committed unpublished diagnostic is replayed on restart;
    once `REJECTED_ARTIFACT_PUBLISHED.json` exists, missing final files are
    treated as an intentional user deletion and are neither recreated nor
    required for Campaign/Batch resume.
  - Accept an exact `batch_id` or an explicit `new_batch` request. Graceful and
    cooperative force stops persist the selected nonterminal Batch as `PAUSED`;
    failures persist `FAILED_REQUIRES_USER`. A force stop after Critic abandons
    and cleans the uncommitted candidate before any counters, Portfolio state,
    template state, or global knowledge can change; force during commit completes
    the atomic commit first. Resume keeps frozen Batch policy while loading
    current Campaign/global knowledge. Every attempt, outcome, commit,
    template-usage marker, and shared design event carries Batch provenance and
    every attempt/commit records its exact knowledge inputs.
  - Each Batch freezes `schedule_policy.mode` and optional target Lineage.
    Supported modes: mixed, explore, improve, validate. Mixed freezes its
    45/55 weights and never schedules validation. Pure validation
    freezes eligible template IDs at Batch creation, reports blocked topology,
    terminates as EXHAUSTED when the snapshot empties, and never falls back to
    exploration. It updates only its source template and creates no new template,
    design Lineage, family-coverage count/debt, ordinary cooldown, or global
    design-feedback event. Pure improve requires an existing Lineage.
  - Improve restores the actually visible optimized board from its Lineage
    snapshot and gives that same board to RevisionPlanner, ContentOptimizer, and
    LayoutOptimizer. It enforces Planner zone/reading-order/anchor requests and
    final verified content as solver constraints, searches bounded same-family
    geometry, and writes schema-v2 `revision_execution_report.json`. Preflight
    retries do not consume Batch budget; the last recovery restores and verifies
    board, topology, geometry, and content-selection digests before a no-change
    commit. Mixed mode isolates an unrecoverable Lineage only for that Batch and
    reschedules the same iteration; pure Improve fails the Batch.
  - Before normal rendering, LayoutPreflight checks exact compiled geometry.
    Explore fit failures retry the same iteration with a different family.
    Validate preflight failures are committed as unscored validation attempts:
    failures one and two stay retryable and the third finalizes the failed
    paper task. They call no Critic, change no poster outcome counts, and create
    no validation evidence, template, Lineage, family debt, or global event.
    Successful normal commits idempotently update the global archetype registry.
  - Emits structured Campaign/Batch/Iteration/Attempt, per-agent stage, fit
    retry/archetype, Critic, promising-base selection, archive/template,
    validation level/status, error,
    and final-status events. Recovery output distinguishes feasibility,
    compiled-preflight, and exact-parent identity failures and announces
    Batch-local Lineage isolation explicitly.
    Candidate success is reported as committed only after `COMPLETED.json`.
  - `optimization_loop._run_legacy()` is retained only as inactive
    compatibility/reference code.
- `src/workflow/loop_progress.py`
  - CLI TTY: Rich live Batch dashboard with committed progress, current
    stage/elapsed time, and outcome counters above a scrolling English event
    stream. Non-TTY: plain chronological event lines and 60-second heartbeats.
    Rich redraw frames are not written to `run.log`; plain events and agent
    messages are. Pure validation also reports its frozen eligible/blocked
    snapshot and per-task attempt x/3, retry-pending, final-failure, pass,
    validation-evidence path, source-template update, and explicit no-new-template
    outcome. Short errors appear in the terminal; raised exceptions have full
    tracebacks in `run.log`. The WebUI receives the same readable stage messages through
    the existing status callback without using the CLI dashboard.
- `src/workflow/generation_failure.py`
  - Captures candidate-local root causes and enforces render readiness before
    Critic. `attempt_failure_report.json` includes provenance, phase, exception
    type/message and traceback, retryability and budget status; it deliberately
    does not capture locals, scientific payloads, prompts or model responses.
- `src/workflow/reconcile_campaign.py`
  - Explicit model-free accounting/legacy-journal correction for one Campaign,
    under its exclusive lease. Does not start/resume a Batch, rewrite foundation
    data, remove historical records, or change terminal lifecycle states.
- `src/workflow/portfolio.py`
  - Separates all-mode counts from mixed-only 45/55 deficit counts; legacy
    Portfolio state lazily migrates by treating prior counts as mixed. Pure
    validation increments only audit mode/history counters; it returns before
    creating/updating Lineages, recent-Lineage rotation, family counts, or
    family exploration debt. Design modes rotate recently used Lineages when
    multiple exist.
  - Owns rolling mode deficits, family coverage, multi-Lineage selection,
    best/latest separation, stagnation, forced exploration when every Lineage
    stagnates, and the active Lineage cap. Portfolio state is Campaign-scoped
    and never resets at a Batch
    boundary.
  - Portfolio schema v5/Lineage schema v3 separate
    `referenced_template_ids` from `produced_template_ids`, store the latest
    full feedback plus a bounded 25-attempt summary, compute parent-local score
    improvement separately from best-promising advancement, and count exact-
    parent no-change fallbacks as stagnation. Unsafe artifact, grounding, Critic,
    renderer, and scientific-integrity failures cannot enter the promising track.
- `src/workflow/campaign.py`
  - Owns compatible campaign discovery, input copies, exclusive leases, frozen
    foundation persistence, attempts, stale-attempt recovery, and atomic JSON
    commit markers, finite Batch state/reports, and per-Lineage latest, best-promising,
    and best-accepted design snapshots.
  - Campaign schema v6 and Batch schema v7 retain `batch_ids`,
    `active_batch_id`, paused/archived registries, the permanent
    `next_batch_number` high-water mark, and per-Batch
    `committed_iteration_ids`. Batch schema v7 adds persistent
    `layout_recovery_blocks` keyed by Lineage; migration initializes it empty,
    and each new Batch starts with an independent empty block set. Compatible layout-engine v1 manifests migrate
    in place to v2 when their input hashes, poster dimensions, and foundation
    schema match, preserving Campaigns, Batches, and Lineages. Schema v6
    records exact restored parent-candidate provenance and schedule-policy v3.
    Zero-use legacy mixed policies migrate from 40/45/15 to 45/55; any executed
    Mutate history fails closed. It also separates Lineage-local snapshots
    from Campaign-wide verified variants/supplemental evidence and maintains
    `memory/content_memory.json` as a replayable revisioned materialized view
    of committed iteration snapshots. Conflicting reuse of a scientific content
    ID fails closed before commit. Legacy sequential Batches migrate lazily from
    their stored iteration ranges and commit markers. Multiple paused Batches
    are allowed; ambiguous default resume fails closed. Terminal states remain
    immutable; archive is reversible and never deletes provenance or knowledge.
  - Lineage latest/best-promising/best-accepted snapshots and feedback/history
    files are derived from
    committed iterations and replayed idempotently on startup, so a crash after
    `COMPLETED.json` cannot permanently lose their audit artifacts.
- `src/workflow/global_knowledge.py`
  - Shares only committed, de-identified Critic design feedback across
    Campaigns. Stores rubric/profile/family outcome aggregates and non-causal
    repair associations, never scientific prose, exact coordinates, claims,
    poster files, or raw Campaign names. It exposes an event count, corrupt
    count, and deterministic digest; retrieval and the recorded snapshot use
    the same exact event set. The Planner receives bounded family-specific
    priors; restart replay fills missing committed design events. Pure
    validation attempts are deliberately excluded from this design-memory
    stream, including crash replay.

The legacy `src/agents/curator.py` and its large spatial-planning prompt are not
used by the active graph.

## Scientific Grounding Invariants

Treat these as correctness requirements, not stylistic preferences:

- Never invent results, methods, entities, numbers, comparisons, limitations,
  conclusions, or metric semantics.
- Evidence excerpts must be traceable to parsed paper text.
- Every poster claim must reference valid evidence IDs.
- Every numerical value in a claim must occur in its cited evidence after the
  repository's normalization rules.
- Preserve exact method/entity names and comparison directions.
- Do not infer that a metric is higher-is-better or lower-is-better from outside
  knowledge.
- Corrections produced by the verifier must pass the same deterministic checks
  as original claims.
- Base `verified_claims` and the original evidence bank are immutable after
  foundation verification.
- RevisionPlanner can request layout or content actions but cannot supply
  replacement scientific prose.
- GroundedContentOptimizer may append verified claim variants and supplemental
  evidence; supplemental excerpts must occur verbatim in the parsed source.
- Every generated variant must pass the full ClaimVerifier, and visible text is
  rematerialized from active verified claim IDs.
- The Balancer output is untrusted until sanitized against the original
  GroundedCurator board.
- Formula normalization must not reinterpret ordinary Markdown or prose.
- Continuous iterations may change selection state and append-only content
  memory, but must never mutate the frozen parser-to-verifier foundation or add
  unverified prose to a poster.

Any change that weakens one of these invariants requires explicit user approval
and dedicated tests.

## Input Data

The expected CLI input layout is:

```text
data/<paper_name>/
  paper.pdf
  logo.png
  aff.png
```

- `paper.pdf` is required.
- `logo.png` is the conference/journal logo.
- `aff.png` is the affiliation logo and is normally used for theme extraction.
- The CLI can auto-detect both logos beside the PDF.
- The WebUI currently requires all three files to be uploaded.

Do not modify source papers or logos during ordinary feature development.

## Output Data

New runs use:

```text
output/<paper_name>/<YYYYMMDD_HHMMSS_microseconds>/
  <paper_name>.pptx
  <paper_name>.png
  run.log
  timing_cost_log.json
  assets/
    figures.json
    tables.json
    fig_tab_caption_mapping.json
    <paper_name>-figure-*.png
    <paper_name>-table-*.png
  content/
    raw.md
    narrative_content.json
    classified_visuals.json
    visual_classification_report.json
    structured_sections.json
    evidence_bank.json
    academic_entities.json
    narrative_plan.json
    poster_claims.json
    verified_claims.json
    verification_report.json
    story_board.json
    visual_curation_report.json
    layout_spec.json
    layout_feasibility_report.json
    layout_preflight_report.json
    layout_content_selection.json
    initial_layout_data.json
    column_analysis.json
    optimized_story_board.json
    capacity_repair_report.json  # optimization route only
    balancer_decisions.json
    optimized_layout.json
    final_column_analysis.json
    final_design_layout.json
    color_scheme.json
    color_provenance.json
    section_title_design.json
    critic_report.json
    keywords.json
    styling_interfaces.json
    styled_layout.json
```

Continuous sessions additionally use the git-ignored local store:

```text
storage/critic_loop/
  campaigns/<campaign_id>/
    manifest.json
    campaign_state.json
    inputs/
    foundation/scientific_state.json
    memory/
      content_memory.json  # revisioned Campaign-wide verified content
    batches/<batch_id>/
      batch_state.json  # schedule plus committed_iteration_ids ledger
      batch_report.json
    lineages/<lineage_id>/
      lineage_state.json
      latest_state.json
      latest_feedback.json
      revision_history.json
      best_promising_state.json
      best_promising_state_<rubric_version>.json
      best_state.json
      best_state_<rubric_version>.json
    sessions/<session_id>/session_state.json
    sessions/<session_id>/paper_profile.json  # derived, text-free profile v2
    iterations/<iteration>/
      COMPLETED.json
      CONTENT_MEMORY_APPLIED.json
      TEMPLATE_USAGE_APPLIED.json
      REJECTED_ARTIFACT_PUBLISHED.json  # only for published rejection diagnostics
      attempts/<attempt_id>/
        status.json
        family_selection_report.json  # Explore pool, coverage, weights and seed
        attempt_failure_report.json  # unexpected generation/pre-commit errors
        commit_runtime_state.json  # draft projection, trusted only after commit
        state_snapshot.json
        layout_feasibility_report.json
        layout_preflight_report.json
        capacity_repair_report.json
        critic_report.json
        outcome.json
  accepted_posters/.pending/<candidate_id>/  # staged, unpublished
  accepted_posters/<candidate_id>/
    poster.pptx
    poster.png
    template.json
    template.pptx
    template.png
    critic_report.json
    story_board.json
    styled_layout.json
    provenance.json
  validation_evidence/.pending/<candidate_id>/  # staged, unpublished
  validation_evidence/<template_id>/<paper_id>/<candidate_id>/
    poster.pptx
    poster.png
    critic_report.json
    task_evaluation.json
    story_board.json
    styled_layout.json
    provenance.json
  template_library/index.json
  template_library/validation_queue.json
  template_library/usage_outcomes.jsonl
  layout_archetypes/index.json  # global paper-free geometry registry
  rejected_posters/.pending/<candidate_id>/  # staged, unpublished
  rejected_posters/<campaign_id>/<batch_id>/<candidate_id>/
    poster.png
    poster.pptx
    critic_report.json
    layout_feasibility_report.json
    layout_preflight_report.json
    story_board.json
    styled_layout.json
    provenance.json
  rejected_previews/  # legacy PNG-only diagnostics; never auto-migrated
  design_memory/rejection_memory.jsonl
  design_memory/rejection_memory_corrections.jsonl  # legacy invalidations
  design_memory/global_knowledge/events/<hashed_campaign>_<iteration>.json
  loop_sessions/<session_id>/
    loop_state.json
    events.jsonl
    progress_events.jsonl
    iterations/<iteration>.json
```

Some older checked-out/generated examples use the legacy layout directly under
`output/<paper_name>/`. Support both shapes when inspecting historical results.

Published `rejected_posters/` bundles are observability-only and have no
template-library, Lineage, Campaign-memory, Portfolio, or global-knowledge
dependency. Users may delete any final candidate directory or the whole final
tree without affecting resume or future iterations. Do not manually delete
`rejected_posters/.pending/` while a process is active.

The intermediate JSON files are intentional observability artifacts. When
debugging a bad poster, find the first stage whose output becomes incorrect
instead of starting from the final image.

## Model Configuration

The model layer supports OpenAI-compatible local text and vision endpoints plus
OpenAI, Anthropic, Google, Zhipu, Moonshot, MiniMax, and Alibaba configurations.

- Local endpoints use `LOCAL_TEXT_*` and `LOCAL_VISION_*` environment variables.
- Local text reasoning can be controlled per agent through
  `config/agent_policy.yaml`.
- ChatOpenAI-compatible clients use JSON response mode when enabled.
- Other providers rely on prompt contracts plus JSON repair.
- Model calls may be retried by both the provider client and the outer Tenacity
  wrapper.
- Non-OpenAI token counts may be estimates.

Never hardcode endpoint URLs, model paths, or credentials in source files.

## CLI and WebUI

CLI example:

```bash
.venv/bin/python -m src.workflow.pipeline \
  --paper_path data/<paper_name>/paper.pdf \
  --poster_width 54 \
  --poster_height 36 \
  --text_model local-text \
  --vision_model local-vision
```


Continuous-loop CLI example:

```bash
.venv/bin/python -m src.workflow.critic_pipeline \
  --paper_path data/<paper_name>/paper.pdf \
  --text_model local-text \
  --vision_model local-vision \
  --iterations 100 \
  --resume latest
```

Each launch runs one selected finite Batch with 100 committed
iterations by default. A Campaign may contain multiple `PAUSED` Batches. If
exactly one exists it resumes automatically; otherwise use `--batch-id
batch_0004` or `--new-batch`. `--list-batches`, `--archive-batch`, and
`--unarchive-batch` are model-free management actions for an existing compatible
Campaign. Omit `--mode` when resuming because mode/target/budget are frozen; new
Batches default to `mixed`. `--mode explore|improve|validate` selects a
pure mode, and `--target-lineage-id` narrows pure improve.
Pure validation freezes the eligible template set for its Batch and can
terminate early as EXHAUSTED if no pending eligible tasks remain; this is task exhaustion, not quality-based early stopping. Quality never ends it early. `--iterations` sets the
target for a newly created Batch; an already active Batch retains its stored
target. One `Ctrl+C` requests a graceful persistent Batch pause after the
current evaluation. A second `Ctrl+C` requests force-stop at the next safe
agent boundary; a blocking model/render call must return first. An attempt seen
after Critic but before commit is cleaned without consuming budget; a force
request during commit lets that commit finish before pausing.
The CLI validates an aspect ratio between 1.4 and 2.0, fixes the output width to
54 inches, and derives height from the requested ratio.

`--resume latest` is the default; use `--resume new` for an independent campaign
or `--resume required --campaign_id <id>` to require an exact compatible one.
Compatibility is based on input hashes, dimensions, foundation schema, and
layout-engine schema. An interrupted uncommitted iteration is retried with the
same iteration number, and only committed iterations consume Batch
budget.

The CLI now tees each optimization launch to its timestamped `run.log`,
displays a live dashboard on a TTY (plain events when redirected), and returns
a nonzero exit code for `FAILED_REQUIRES_USER` or `UNAVAILABLE`. Pure
validation `EXHAUSTED` is a normal, zero-exit terminal state. The compact
`loop_sessions/<session_id>/progress_events.jsonl` records semantic events;
`COMPLETED.json` remains the only iteration commit marker.

Model-free correction of one offline Campaign's derived accounting and legacy
uncommitted rejection records:

```bash
.venv/bin/python -m src.workflow.reconcile_campaign --campaign-id <id>
```

The exclusive lease rejects concurrent runs. This command does not launch a
Batch or make a failed Batch resumable; use a new Batch to continue afterward.
`accounting_reconciliation.json` records a changed counter projection.

The WebUI consists of:

- `webui/backend/main.py`: FastAPI application on port 8001.
- `webui/frontend/`: React + TypeScript + Vite application on port 3000.
- `webui/start_backend.py`: backend launcher.
- `webui/start_frontend.sh`: frontend launcher.

The backend stores job state and recent logs in process memory, saves uploads in
a temporary directory, and creates a ZIP archive after completion. The WebUI
enables resumable Batch optimization by default, accepts the Batch budget,
shows Batch/Portfolio/family/Lineage plus iteration/score/archive counts and the
current best accepted preview, and exposes pause, resume, graceful-stop, and
force-stop endpoints. It accepts resume mode and an exact Campaign ID. The
Batch administration panel lists every persisted Batch with status, mode,
progress, target Lineage, and knowledge watermarks; it can select a resumable
Batch, archive/unarchive allowed states, and open full state or terminal report
JSON without model execution. A process restart loses old in-memory job
controls, but the next compatible `latest` run restores the persisted campaign
foundation and last committed iteration.

Known CLI/WebUI mismatch: the WebUI passes width and height directly to
`create_state`, while the CLI normalizes width to 54 inches and preserves only
the aspect ratio. Preserve the current behavior unless the task explicitly aims
to unify it.

## Testing

Use the repository virtual environment:

```bash
.venv/bin/python -m pytest -q
```

The current baseline is:

```text
310 passed, 5 subtests passed
```

Existing tests cover:

- implicit claim-ID selection from real capacity actions, deletion exclusions,
  no-candidate no-ops, root-cause diagnostics, current-artifact readiness,
  pre-marker accepted/rejected staging/Portfolio/commit failures, post-marker
  replay, journal append-crash idempotency, projection digest failures,
  immutable archived terminal states and proof-based historical corrections;

- TTY and redirected terminal progress formatting, plain `run.log` mirroring,
  CLI failure exit codes, and committed accepted/rejected progress events;

- body-text and section-title geometry;
- display formula parsing, measurement, and rendering;
- formula multiplication normalization;
- editable inline subscript/superscript rendering;
- grounded claim restoration, pruning, section removal, and column rebalancing;
- successful and failed model-call tracking.
- deterministic Critic artifact, geometry, grounding, typography, and column
  hard gates;
- RevisionPlanner operation allow-listing and exact verified-text restoration;
- template-free exploration, distinct-family retrieval, duplicate retrieval
  suppression with unconditional accepted-template storage,
  cross-paper candidate validation, and promotion;
- accepted 1:1 poster/template bundle staging and crash replay, editable
  paper-free PNG/PPTX previews, unlimited complete rejected PNG/PPTX diagnostics,
  failed-Validate retention, uncommitted cleanup, user-deletion-safe replay,
  and iteration reports;
- campaign compatibility, committed-iteration resume, same-number retry, and
  attempt-level crash recovery;
- 95%-100% section-fit scoring, gap detection, and content adequacy feedback;
- grounded compact/expanded claim actions, exact supplemental excerpts, and
  cross-root substitution rejection;
- relational-only template context, cross-family duplicate blocking, cooldown,
  idempotent usage tracking, and anti-fixation strategy scheduling;
- campaign-scoped template cooldown, lazy schema migration, and bounded history;
- twelve registered bounded layout-family specs, seeded geometry variants,
  paper-aware fit/content assignment, hard pre-render preflight, runtime archetype
  promotion, rejected-diagnostic retention, and family-contract Critic failures;
- rolling Portfolio ratios, multiple Lineages, finite Batch resume, and
  persistent family coverage;
- independent versioned structural-template scoring, global 10x4 per-family
  level seats, L0 source-only and L1 profile-gated cross-paper retrieval,
  strict-journal v5-to-v6 migration, and seat recomputation on promotion;
- mandatory template validation queue, three-attempt failure handling,
  evidence-only successful poster storage, immutable source-template structure,
  identity-guarded/idempotent updates, and applicability narrowing;
- Critic-v4 weighted aggregation/report compatibility, paper-derived content,
  color and visual-asset submetrics, zone-aware fit, safe Planner style/visual
  operations, and rubric-version migration;
- frozen pure/mixed Batch modes, mixed-only quota accounting, unavailable
  Lineage and exhausted validation terminal states, validation cooldown bypass,
  committed evidence/usage replay, no-new-template validation, Portfolio/global
  design-memory isolation, and de-identified global feedback replay.

When changing behavior:

- Add or update focused unit tests.
- Run the focused test file first, then the complete suite.
- For layout changes, inspect `column_analysis.json`,
  `final_column_analysis.json`, and `balancer_decisions.json`.
- For grounding changes, inspect the evidence-to-claim chain and add adversarial
  cases for unsupported numbers, renamed entities, reversed comparisons, and
  unsupported metric direction.
- For renderer changes, verify both the generated PPTX structure and PNG output
  when practical.
- Do not run a full LLM-backed paper generation solely as a routine test: it is
  slow and expensive. Run it only when required by the task or requested by the
  user.
- Ordinary unit tests do not call the Qwen service and should not allocate a GPU.
- Any full/model-backed project run must place the PosterGen test workload on
  GPU 5 (for example with `CUDA_VISIBLE_DEVICES=5`), never on GPU 3, which hosts
  the Qwen3.8-27B service. Do not stop or disturb that service.
- Immediately after a GPU-backed run, terminate the test process and verify that
  it leaves no process or memory allocation on GPU 5. Do not leave models,
  workers, or cached GPU allocations resident there.

## Known Technical Context

- `PosterState` retains compatibility/placeholder fields that are currently
  unused, including `page_records`, `visual_analysis`, `poster_plan`,
  `wireframe_layout`, and `content_filled_layout`.
- `strict_academic`, `reasoning_mode`, `debug_evidence`, and
  `claim_repair_count` are initialized but are not currently functional control
  paths.
- `extract_structured_sections.txt` is loaded by the parser, although active
  section extraction is deterministic and does not use that prompt.
- `GPT-4o-image_generation.txt` is not part of the active pipeline.
- The optimization loop now fail-closes exact compiled layout overflow before
  Renderer. The standalone one-shot graph in `src/workflow/pipeline.py` still
  follows its original renderer path and does not use the new loop preflight.
- Feasibility search uses a conservative fast estimator for tractable variant
  exploration; its selected result must still pass the slower exact LayoutAgent
  compilation and deterministic preflight before rendering.
- The WebUI exposes a narrower model list than the model factory and CLI.
- WebUI progress percentages are coarse milestones, not per-agent progress.
- WebUI job/control state, recent logs, and temporary upload directories remain
  process-local. Restarting the backend loses the active controls, but on-disk
  campaigns now resume automatically on the next compatible `latest` launch;
  only the old process-local job/control handle is lost.
- Batch mode has no quality-based early stop, but each Batch has a finite
  committed-iteration budget (100 by default). A Campaign can retain several
  paused Batches, though only one may run at a time; ambiguous resume requires
  `--batch-id`. Repeated launches can still incur substantial model cost.
- All loop families, including classic three-column, bypass the legacy Balancer
  and use bounded paper-aware geometry/content search. The legacy classic path
  is available only through the independent one-shot entry point. Real
  model-backed visual quality across all twelve families has not yet been
  benchmarked in this conversation.
- Force-stop is cooperative: it exits between agents but cannot cancel a model
  request or LibreOffice process that is already blocking.
- The Critic store is file-backed JSON/JSONL rather than a database.
- The schema-v11 index retains full blueprints, per-paper trials, validation
  evidence references, and semantic revision/digest metadata. Schema-v8 records
  migrate without re-running trial reconstruction. Very large libraries may
  later need indexed per-template files or a database.
- The 78-point admission threshold has not been empirically recalibrated after
  this storage-policy change. CPU tests pass, but no model-backed multi-paper
  quality or transfer benchmark was run in this conversation.
- `webui/start_frontend.sh` deletes `node_modules` and `package-lock.json` before
  reinstalling; do not run it casually when reproducibility matters.
- The configured Git `origin` may point to a proxy/fork rather than the official
  upstream repository. Verify remotes before pulling, pushing, or comparing with
  upstream.

## Development Workflow

### Mandatory AGENTS.md maintenance

- Every conversation that changes any file in this PosterGen repository must
  review and update this root `AGENTS.md` in the same conversation.
- This requirement applies to source code, configuration, prompts, tests,
  scripts, documentation, dependency files, and runtime behavior.
- Record the durable effect of the change in the relevant section of this file:
  architecture, active pipeline, data contracts, commands, tests, known issues,
  or development rules.
- Do not add a meaningless timestamp-only edit. The update must explain what
  future agents need to know about the changed project.
- Before finishing, verify that `AGENTS.md` is included in the changed-file list
  and mention its update in the final handoff.
- If a requested change truly has no lasting effect on project context, add a
  concise note to the `Recent Changes` section below so the maintenance action
  is still explicit and traceable.

### Mandatory Git traceability

- The repository baseline is version-controlled. Every conversation that
  changes durable project files must finish with an atomic Git commit unless
  the user explicitly requests no commit.
- Never use `git add .` or `git add -A`. Inspect `git status --short
  --untracked-files=all`, then stage only the source, configuration, prompt,
  test, WebUI, script, and documentation paths that belong to the task.
- Durable files under `src/`, `config/`, `tests/`, `utils/`, and `webui/` must
  not remain as untracked `??` files at handoff. If an untracked durable file is
  intentionally excluded, explain why in the final response.
- Never commit `.env`, papers, logos, generated posters, model logs, caches,
  temporary uploads, or `storage/critic_loop/` runtime state. The tracked
  `storage/.gitignore` keeps the file-backed Campaign store local.
- Preserve unrelated user changes: when a dirty worktree exists, stage and
  commit only task-owned paths. Do not fold unrelated modifications into the
  task commit merely to make the worktree clean.
- Use an informative conventional commit message such as `feat(critic): ...`,
  `fix(layout): ...`, `test(loop): ...`, or `docs: ...`. Record the resulting
  commit ID, changed-file summary, and test results in the final handoff.
- Before committing, run `git diff --check`, the focused tests, and the full
  suite when proportionate. After committing, verify both `git status --short`
  and `git show --stat --oneline HEAD`.

For each task:

1. Read this file completely.
2. Run `git status --short` and identify user-owned changes.
3. Locate the active code path; do not edit an `old versions` file by mistake.
4. Inspect the relevant prompt, state fields, and intermediate JSON contract.
5. Implement the smallest coherent change.
6. Add focused regression tests.
7. Run focused tests and then the full test suite.
8. Report modified files, tests run, and any remaining risks.

## Recent Changes

- 2026-10-12: Opened all twelve families to Explore, repaired NarrativePlanner
  profile field mapping, and introduced coverage-first bounded semantic
  preference. Selection policy v1 freezes per Batch; legacy resumable Batches
  migrate once without changing existing profile keys, commits or foundation.
  Restored the Portfolio scheduler seed on Campaign resume and removed the
  exhausted-pool fallback that could reintroduce excluded families. Added
  session profile/attempt selection audits and concise English terminal events,
  shared role normalization, and explicit no-invented-relationship prompts.
  CPU regressions cover reachability, coverage, retry exhaustion, semantic
  anchors, migration, policy bounds and resumed reproducibility. The current
  geospatial foundation was checked read-only: method/comparison signals now
  resolve, all twelve families enter the pool, and the source file is unchanged.
  Full CPU suite: 310 passed plus 5 subtests (24 additional test cases over the
  previous baseline). Final review also verifies the committed audit contract
  and fail-closed pre-attempt exhaustion status. See `FAMILY_SELECTION_REPORT.md`;
  no model/GPU run or live Campaign mutation.

- 2026-10-12: Fixed implicit capacity-addition's list/set union regression.
  Preserved pre-repair fit/partial audits and root tracebacks; unrendered or
  failed generation now bypasses Critic/rejection storage and fails safely
  without spending budget. Draft commit accounting rolls back pre-marker
  failures; digest-bound runtime projections and committed outcomes repair
  post-marker summaries. Rejection journaling moved after commit with locked
  deduplication and replay; legacy uncommitted entries gain non-destructive
  invalidations. Recovery preserves original abandonment reasons and failed/
  archived states, including budget-edge migration. Added model-free targeted
  reconciliation CLI. The failed new geospatial Campaign's false rejection
  count was corrected from 1 to 0 while its failed Batch, foundation and logs
  remain intact; no Batch was launched. See
  `GENERATION_FAILURE_REPAIR_REPORT.md`. Full CPU suite: 286 passed plus 5
  subtests; no model/GPU generation run.

- 2026-10-10: Fixed Improve's Planner/content handoff and deletion safety.
  Optimizer now edits the current working board or an explicit validated
  override, never the read-only parent. Evidence-scoped destructive operations,
  final-effect contracts, branch-local asset/root exclusions and moved recovery
  ownership prevent silent undo by capacity repair. Exact candidate/compiled
  whitespace guards support one valid-content rollback/refit; unusable assets
  are not fillers. Later source-visual or grounded-claim restoration remains
  explicit and placement-gated. Execution schema v3 verifies real effects;
  plan schema v4 records operation IDs. A separate post-Critic admission veto
  preserves raw scoring/diagnostics but blocks unsafe archives/templates and
  observed-best/promising advancement. Snapshot/reset and legacy loading are
  isolated; exact fallback restores/digest-checks branch policies, palette,
  keywords, importance and gaps without rolling back shared banks. Added 32
  CPU-only regressions including real solver/preflight and Campaign commits.
  Full suite: 263 passed plus 5 subtests; no live model/GPU run. Updated README,
  capacity report, and `IMPROVE_REVISION_REPORT.md` with contracts/limitations.

- 2026-10-10: Decoupled visual classification from left/middle/right poster
  assumptions. Parser now normalizes five paper-semantic roles and an optional
  key pointer, writes an ID-only classification audit, and keeps old Campaign
  foundations readable without silently reclassifying them. The loop Curator
  uses a route-specific column-free prompt, records selection provenance, and
  can offer a relevant key visual to the solver; the classic one-shot route
  retains its independent three-column behavior. Critic now audits source,
  Curator-selected, and final-visible IDs without changing scoring or gates.
  See `VISUAL_CLASSIFICATION_REPORT.md` for contracts and limitations. Full CPU
  suite: 231 passed plus 5 subtests; no model/GPU run.

- 2026-10-09: Added whole-poster whitespace accounting to loop-family exact
  candidate scoring and near-best selection, so increasing zone fill cannot
  simply push blank space into larger inter-zone gaps. Feasible layouts now
  request bounded repair below 90% zone use or above a two-body-line bottom
  gap. The Solver favors approved key/result/method visuals, and repair may
  restore an omitted source visual to its original section without sacrificing
  visible claims/assets, strict Validate topology, exact fit, or whole-poster
  whitespace. A source-visual manifest persists with the Lineage. Critic
  records composition and source-visual omissions for audit without changing
  calibrated scoring/admission. Added targeted regressions, updated README
  and `CAPACITY_REPAIR_REPORT.md`; complete CPU suite: 222 passed plus 5
  subtests. Historical I13 was checked read-only; no live model/GPU run or
  historical Campaign rewrite was performed. Standalone classic is unchanged.

- 2026-10-09: Closed the post-review repair-diagnostic gap. Feasibility
  schema v5 derives bounded, de-identified repair pressure candidates from
  every searched variant before truncating displayed trial details, so a
  repairable thirteenth/fourteenth variant cannot be misreported as having no
  height pressure. Legacy v3/v4 reports remain readable; a candidate-list cap
  has an explicit diagnostic-limit skip reason. Successful reports now record
  both configured and actually selected fast-estimate safety factors plus the
  selected standard/adaptive/near-miss path. The compiled-preflight schema
  stays v4. Added hidden-variant, nontext, truncation, legacy, provenance, and
  attempt-isolation regressions; updated README and the capacity report.
  Complete CPU suite: 214 passed plus 5 subtests; no model/GPU run and no
  historical Campaign data was changed.

- 2026-10-09: Completed the interrupted near-capacity search correction.
  Feasibility report schema v4 now keeps bounded closest, worst, and
  most-advanced text-free height-pressure samples per geometry variant,
  including wider-beam observations. Up to two near-miss variants are ranked
  across the whole family by assignment progress/overage; only the fast safety
  reserve may be relaxed and exact compile/preflight still gates output.
  Capacity repair distinguishes actionable text pressure from exact failures,
  nontext pressure, and absent near misses with explicit skip reasons.
  Attempt-specific repair reports survive retries, and terminal retry events
  include recheck and repair diagnoses. Added focused regression tests and
  updated README plus `CAPACITY_REPAIR_REPORT.md`. Complete CPU suite: 210
  passed plus 5 subtests; no model or GPU run. Historical I13 is unchanged.

- 2026-10-09: Reduced false family-capacity rejections with extra bounded
  non-prefix claim subsets, adaptive beam width, and limited near-miss
  rechecks before exact compile/preflight. Added measured capacity repair for
  loop Explore/Improve/Validate through the existing GroundedContentOptimizer;
  successful repair keeps verified claims and fixed validation zones, while
  failed/abandoned work leaves Campaign content memory unchanged; retry starts
  by restoring committed banks. Final
  verifier corrections now receive independent semantic verification; new
  compact/additional claims receive a source-excerpt editorial check for
  conditions, relevance, and redundancy. Supplemental source search now spans
  ranked paper windows. Added capacity-repair reports, terminal events,
  configuration bounds, README and a dedicated implementation report. CPU
  tests cover non-prefix/near-miss search, source reach, final wording rejection,
  repair adoption and rollback. Full CPU suite: 203 passed plus 5 subtests;
  no live model/GPU run was performed.

- 2026-10-09: Corrected loop-family text geometry after historical I10-I12
  review. Loop-only body measurement now reserves LibreOffice's measured line
  advance; visible section spacing follows the Critic body-line target.
  Explore adaptively expands controlled geometry search for sparse candidates
  and ranks exact layouts partly by their worst-filled zone/bottom gap. A
  post-render PDF glyph audit catches real text overflow and cross-module
  collisions before normal Critic admission, while strict Validate exposes
  them as Critic hard issues. Critic 4.2/rubric v4 separates weighted target
  imbalance from physical overflow; old-rubric rejected snapshots cannot be
  relabeled as new-rubric promising bases. The standalone one-shot Balancer is
  unchanged. CPU suite and historical I12 read-only audit were run; no live
  model/GPU Campaign was run, so cross-family visual quality still needs a
  fresh real run before any guarantee.

- 2026-10-08: Closed the legacy loop-classic Improve-parent loophole: immutable
  new iteration snapshots record generation-time layout origin; replay of older
  commits infers origin conservatively and never upgrades it to the current
  writer's layout-engine version. Improve validates the internal geometry,
  solver/preflight evidence, topology, and section ownership, falling back only
  to a compatible same-Lineage track. Mixed mode skips incompatible Lineages;
  pure Improve reports `UNAVAILABLE` before model work. Historical outputs are
  retained and not auto-rebased. Feasibility failures now preserve bounded,
  text-free schema-v3 diagnostics in each attempt and show concise English
  stage/reason/count information in the terminal. CPU regressions cover stale
  outer-version stamps, replay, malformed parents, fast/exact search failures,
  and terminal formatting. Full CPU suite: 183 passed plus 5 subtests; no
  model/GPU loop was run.

- 2026-10-08: Separated generation routes explicitly: `pipeline.py` stays a
  one-shot legacy-Balancer three-column generator and never writes loop design
  knowledge; `critic_pipeline.py` routes all twelve families, including loop
  classic, through the common LayoutSpec Solver/compiler. LayoutSpec schema v3
  adds bounded family-legal split/span and shared-boundary variants, semantic
  zone guards, exact post-search compilation/refill of grounded claims/visuals/
  modules, actual utilization reporting, and near-best diversified selection.
  Fixed the solver-to-final-layout seed handoff so selected geometry cannot be
  silently rebuilt as a default family layout. Critic 4.1 / rubric
  `academic_poster_multifamily_v3` applies zone-aware section fit to loop
  classic and hard-gates empty or severely unused zones; RevisionPlanner can
  request bounded zone-budget changes. Improve may read one same-family
  other-Lineage relational template after warmup; Explore remains template-free.
  New templates record source route/engine version and zone-based similarity
  signature, historical loop-classic
  templates with unverified geometry remain stored but cannot strict-validate,
  and legacy classic Lineages cannot be silently restored as exact parents.
  Added route, geometry, fit, compatibility, and retrieval regressions. Full
  CPU suite: 178 passed plus 5 subtests; no model-backed visual benchmark or
  GPU run.

- 2026-09-30: Added a crash-safe best-promising track for Critic-rejected
  designs. Lineage schema v3 now separates latest feedback, the best safe
  rejected working base, and the best accepted base. Before the first accepted
  poster, Improve resumes from the best-promising snapshot while still applying
  feedback from the newest committed attempt; after acceptance, the accepted
  snapshot always remains the edit base. Promising eligibility excludes
  artifact, grounding, evaluator, renderer, preflight, and scientific-integrity
  failures, and ranking prioritizes repairability and issue severity before
  scores. Parent-local score improvement is tracked independently from
  best-promising advancement and stagnation. Rejected promising designs
  never enter poster archives, templates, archetypes, or any globally reusable
  base; their de-identified Critic outcomes still feed
  the existing bounded global rejection-feedback memory. Snapshot publication is reconstructible from commit
  history, legacy safe latest snapshots migrate conservatively, and terminal
  output identifies the loaded base and promising decision. Added persistence,
  ranking, accepted-base precedence, replay, and terminal regressions. Full
  model-free suite: 169 passed plus 5 subtests; no model or GPU run.

- 2026-09-30: Fixed the I8/I10 layout-recovery failures. Improve now freezes
  the loaded Lineage's visible optimized storyboard instead of mixing it with the
  pre-fit Curator board; RevisionPlanner, GroundedContentOptimizer, and the
  layout solver consume that same parent. Final safe fallback restores and
  digest-verifies the board, LayoutSpec, content selection, and layout-content
  selection. Batch schema v7 persists Batch-local recovery blocks: mixed mode
  isolates an unrecoverable Lineage and reschedules the same global iteration
  without budget use, while pure Improve still fails closed and terminal failed
  Batches remain immutable. Attempt reports now distinguish feasibility,
  compiled-preflight, and exact-parent identity failures. Section-title
  measurement resolves LibreOffice's actual regular/bold font substitutions;
  preflight now checks required title height, child containment/zone ownership,
  and intra-section overlap for classic and controlled families. Visual Critic
  locations are sanitized against real section-zone assignments. The existing
  failed Batch 1 was not rewritten; a new Batch 2 will begin at global I10. The
  actual I8 artifact was checked offline: its 0.920-inch title box now requires
  about 1.795 inches for the rendered two-line title. Full model-free suite: 165
  passed plus 5 subtests; no model or GPU run.

- 2026-09-30: Replaced capped PNG-only rejected previews with unlimited complete
  rejected-poster diagnostics. Every committed rendered Explore/Improve
  rejection now preserves PNG, editable PPTX, Critic, feasibility, preflight,
  storyboard, styled-layout, and provenance data. Pure Validate preserves the
  same bundle both for poster rejection and for an admitted poster that fails
  strict transfer, while successful validation remains evidence-only and creates
  no template. Pre-render failures, no-change Improve fallbacks, and
  force-abandoned attempts still create no diagnostic. Bundles stage before the
  sole iteration commit point and publish afterward; committed publication
  replays after crashes, while a durable publication marker makes later user
  deletion final and harmless to Campaign resume, templates, Lineages,
  Portfolio, or global knowledge. Removed the 20-file pruning configuration,
  added explicit English terminal paths, and retained legacy
  `rejected_previews/` untouched. Full model-free suite: 160 passed plus 5
  subtests; no model or GPU run.

- 2026-09-29: Completed full Lineage output tracking and Improve feedback
  continuity. Portfolio schema v5 / Lineage schema v2 now distinguish referenced
  templates from templates produced by each Lineage and retain rubric-scoped
  latest full feedback plus a bounded 25-attempt summary. Improve edits the best
  accepted base while receiving the latest committed attempt feedback; Lineage
  artifacts replay from committed iterations after crashes. Revision operations
  now use a shared LayoutSpec protocol with zone swapping and schema-v2
  per-operation execution reports. Template-library schema v11 stores direct
  Campaign/Batch/iteration/Lineage/mode/parent provenance and backfills legacy
  records from bundle provenance. Exact-parent fallback now commits only a
  no-change stagnation event—no duplicate poster/template/archetype/global
  knowledge—and has explicit terminal output. Full model-free suite: 157 passed
  plus 5 subtests; no model or GPU run.

- 2026-09-29: Removed Mutate from active scheduling, CLI, WebUI, runner, and
  template retrieval. Mixed schedule-policy v3 is 45% Explore / 55% Improve;
  schema-v2 policies migrate only when no Mutate iteration was ever executed,
  otherwise migration fails closed. Campaign/Batch schema v6 records the exact
  restored parent candidate. Improve now preserves Planner relational edits and
  verified content actions as hard constraints, searches bounded parent-local
  geometry, retries preflight without budget use, falls back to exact parent
  geometry, and persists a revision execution report. Validate preflight
  failures now commit as unscored strict-transfer attempts with the existing
  three-attempt rule and no poster outcome, evidence, template, Lineage,
  family-coverage, cooldown, or global-memory side effects. Template-library
  schema v10 fixes validation aggregate scores to read `poster_score` and
  retains null scores for pre-render failures. CLI/WebUI/terminal output and
  regressions were updated. Full model-free suite: 153 passed plus 5 subtests;
  no model or GPU run.

- 2026-09-28: Completed capacity-aware layout-family exploration. Explore is
  now strictly template-free and searches seeded, bounded geometry plus grounded
  claim/visual selections across all twelve families; classic three-column
  remains available and can also vary under controlled exploration. LayoutSpec
  schema v2 records geometry fingerprints and mutation provenance. A hard
  post-font preflight blocks known overflow/bounds/ownership failures before
  rendering or Critic; explore/mutate retry another family on the same iteration
  without spending Batch budget. Accepted layouts feed a global paper-free
  archetype registry whose cross-paper promotion requires three accepted posters
  over at least two papers and whose ranking excludes content scores. Bounded
  rejected PNG diagnostics are retained separately from accepted archives. Added
  compatible v1-to-v2 Campaign identity migration, English fit/archetype events,
  persisted reports, and CPU-only regressions. Full suite: 148 passed plus 5
  subtests. No model or GPU run.

- 2026-09-24: Completed multi-Batch knowledge freshness and auditability.
  Campaign schema v5 / Batch schema v5 separate Lineage-local design and
  content selection from Campaign-wide verified variants and supplemental
  evidence. A revisioned `memory/content_memory.json` is rebuilt idempotently
  from committed snapshots, unions interleaved Batch knowledge, sanitizes old
  Lineage selections, and fails closed on conflicting scientific IDs.
  Per-Batch watermarks and per-attempt/commit knowledge inputs now identify
  Campaign content, Portfolio, template-library, and global-design-memory state.
  Template-library schema v9 adds semantic revision/digest metadata without
  re-running schema-v8 trial migration; global design memory adds event/digest
  snapshots. Force-stop after Critic abandons and removes uncommitted artifacts
  without consuming budget, while force during commit finishes atomically.
  Added WebUI Batch list/detail/report/archive/unarchive administration and
  regressions for interleaved Batches, migrations, watermarks, force-stop, and
  WebUI endpoints. Full CPU suite: 141 passed plus 5 subtests; WebUI production
  build passes. No model or GPU run.

- 2026-09-23: Replaced the single-active-Batch lifecycle with Campaign schema
  v4 / Batch schema v4 multi-Batch persistence. A Campaign may retain multiple
  paused or archived Batches while its lease enforces one runner. Permanent
  Campaign-scoped Batch IDs use a high-water counter and never recycle. Each
  commit/attempt/outcome now records its owning Batch; per-Batch explicit
  committed-iteration ledgers support non-contiguous global iteration numbers.
  Graceful/force stop persists `PAUSED`, failures require explicit retry, and
  completed/exhausted/unavailable states stay terminal. Resume freezes policy
  while refreshing Campaign and global knowledge; pure validate keeps its
  frozen template snapshot. Added `--batch-id`, `--new-batch`, list/archive/
  unarchive CLI controls, matching WebUI selection fields, Batch provenance in
  global/template events, lazy legacy migration, and fail-closed ambiguous
  selection. Focused suite and full CPU suite pass; WebUI production build
  passes. No model or GPU run.

- 2026-09-23: Corrected pure `validate` semantics end to end. Validation now
  locks one saved template's fingerprint and exact topology, renders against
  that topology, and never calls TemplateDistiller or registers another
  template. A successful poster+strict-transfer result stages and publishes a
  dedicated evidence bundle under
  `validation_evidence/<template>/<paper>/<candidate>/`; failures retain only
  committed Critic/task reports and retry metadata. The original template gains
  validation evidence and may change level, applicability, validation status,
  and derived retrieval eligibility, while its blueprint, fingerprint, source
  design score/evaluation, and previews remain immutable. Schema v8 records
  evidence references and source-replay attempts. Validation no longer affects
  ordinary usage/cooldown, recent-template suppression, template totals, best
  design poster, content outcome memory, Lineages, family coverage/debt,
  selector ratios, or global design feedback; crash replay preserves the same
  boundaries. Terminal output names the evidence path, source-template update,
  and “no new template created.” Added storage, identity, retry, replay,
  terminal, Portfolio, global-memory, and end-to-end no-model regressions.
  Full suite: 125 passed plus 5 subtests; no model or GPU run.

- 2026-09-23: Removed strict template validation from mixed scheduling; mixed
  Batches now freeze a 40% explore, 45% improve, 15% mutate policy. Pure
  validate Batches freeze their eligible template IDs so newly saved templates
  wait for the next Batch. Template library schema v7 tracks up to three
  committed attempts per cross-paper template-paper task: failures one and two
  remain retryable, the third finalizes one distinct failed paper, and two
  distinct final failures are required to narrow a profile. Later strict
  success restores that profile. Source replay remains a one-attempt audit and
  does not affect cross-paper applicability; invalid topology is reported as
  blocked without consuming attempts. Added idempotent Batch validation
  counters, migration from legacy usage journals, detailed English terminal
  snapshot/attempt output, README coverage, and CPU-only regression tests.
  Full suite: 117 passed plus 5 subtests; no model or GPU run.

- 2026-09-22: Added independent versioned structural template scores and
  global per-family 10x4 L0/L1/L2/L3 ordinary-reference seats. L0 remains
  source-paper-only; L1 becomes profile-gated cross-paper reference only after
  accepted strict topology transfer. Validation bypasses ordinary seats and
  alone can promote levels. Schema v6 backfills archived Critic design metrics
  and reconstructs old L1 profile proof from strict usage journals; missing
  proof fails closed. Updated English terminal score/seat events, README,
  config validation, and CPU-only regression tests (103 passed plus 5
  subtests). No model-backed run.

- 2026-09-22: Unified Critic poster/template admission: every accepted
  candidate stages and, after `COMPLETED.json`, publishes one poster plus one
  structural template JSON and paper-free editable PNG/PPTX preview. Global
  library schema v5 retains duplicates/over-cap templates for validation while
  limiting only retrieval. Strict template validation now locks saved topology
  and records structural transfer in the Critic report; inspired reuse cannot
  promote levels. Added presentation-only audit score and high-potential label
  without changing the 78-point admission threshold, post-commit replay and
  stale staging cleanup, twelve tracked family preview pairs, README coverage,
  and CPU-only regression tests. Full suite: 89 passed plus 5 subtests.

- 2026-09-21: Added detailed terminal progress for resumable Critic Batches:
  live TTY dashboard, redirected plain events and heartbeats, per-stage timing,
  committed poster/template/validation outcomes, compact progress journal, and
  stage-specific errors with full tracebacks in `run.log`. CLI failures now
  return nonzero; WebUI status callbacks receive readable stage messages.
  Added no-GPU regression tests and documented the new operator workflow.

- 2026-09-21: Added frozen mixed/pure Batch scheduling (explore, improve,
  mutate, validate), optional target Lineage, mixed-only quota accounting,
  explicit validation exhaustion, and CLI/WebUI controls. Added globally
  shared, de-identified Critic design feedback with committed-event replay
  and bounded Planner retrieval; pure exploration remains template-free and
  validation bypasses ordinary reuse cooldown. Added focused regression
  coverage and README instructions.

- 2026-09-21: Established the first complete Git-tracked baseline for the
  accumulated grounded-content, Critic v4, twelve-family layout, resumable
  Campaign/Batch, Portfolio, template-memory, and WebUI work. Added mandatory
  atomic-commit rules for every future file-changing conversation, explicit
  staging only, zero untracked durable source files at handoff, and strict
  exclusion of local papers, outputs, secrets, and Critic-loop runtime data.
- 2026-09-21: Upgraded the evaluator to Critic v4 / report schema v3 with
  explicit per-dimension source weights, seven stable top-level dimensions,
  paper-derived information/narrative, color/WCAG, typography, visual-asset,
  and expanded multimodal submetrics. Made fit/capacity checks LayoutSpec-zone
  aware and kept artifact validity as a score-neutral hard gate. Tightened
  template eligibility independently from archive eligibility. Completed the
  Critic-to-RevisionPlanner path with allow-listed approved-visual changes and
  deterministic accessible-palette, contrast, accent-density, font-family, and
  typography-hierarchy presets; raw style values and scientific replacement
  text remain forbidden. Persisted style/color provenance and rubric-scoped
  best candidates so scores from different rubrics are never silently compared.
  Added focused regression coverage; full CPU-only suite is now 64 passed plus
  5 subtests.
- 2026-09-18: Replaced fixed-three-column-only optimization with LayoutSpec
  schema v1 and twelve controlled layout families while preserving the original
  three-column path. Added deterministic zone compilation, family-aware Critic
  checks, relational RevisionPlanner operations, and layout-engine campaign
  compatibility. Added finite resumable Batches (100 committed iterations by
  default), persistent multi-Lineage Portfolio scheduling at 30/40/12/18,
  structural child branches, per-Lineage latest/best snapshots, family coverage
  debt, CLI/WebUI Batch controls, and status reporting. Upgraded the global
  template library to schema v4: every registered template enters mandatory
  validation, failures narrow applicability without deletion, and successes
  promote Levels 0-3. Added focused regression tests and updated README.
- 2026-09-17: Made template cooldown campaign-scoped while keeping the template
  library global. New campaigns can reuse historical templates after the
  mandatory template-free warmup; resumed campaigns retain their own cooldown
  without interference from other campaigns. Added schema-v3 lazy migration,
  bounded per-template campaign history, campaign IDs in usage outcomes,
  configuration validation, regression tests, and README coverage.
- 2026-09-16: Added crash-aware persistent campaigns with compatible automatic
  resume, same-number retry for interrupted iterations, and frozen scientific
  foundation/state snapshots. Added module-level 95%-100% fit and whitespace
  evaluation, grounded text compaction/expansion through a fully reverified
  append-only content bank, and Critic-to-Planner content actions. Strengthened
  anti-fixation with per-launch template-free warmup, relational-only template
  context, global near-duplicate rejection, family diversity/cooldown, and
  separate archive/template eligibility. Added CLI/WebUI resume controls,
  file-backed campaign observability, focused regression tests, README coverage,
  and the GPU 5 cleanup rule for any future model-backed runtime test.
- 2026-09-15: Integrated the versioned Critic into the single-pass graph and
  added the user-controlled continuous Planner-Coder-Critic workflow. Scientific
  evidence is frozen after verification; rejected candidates feed structured,
  allow-listed repairs to RevisionPlanner, while accepted candidates are
  archived and distilled into diversity-controlled candidate templates.
  Added cross-paper template validation/promotion, a strict 40% template-free
  exploration floor, local JSON/JSONL loop storage, CLI/WebUI controls and live
  best-poster preview, bounded in-memory history, cumulative timing, focused
  regression tests, and human-facing README documentation.
- 2026-09-14: Added the repository-wide requirement that every file-changing
  conversation must also maintain this `AGENTS.md` and report that maintenance
  in its final handoff.
