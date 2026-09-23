# PosterGen Development Guide

This file is the persistent development context for AI coding agents working in
this repository. Read it completely before inspecting or modifying the project.

## Project Purpose

PosterGen converts an academic paper into an academic poster. It extracts and
grounds scientific content from a PDF, selects figures and tables, plans a
controlled layout-family composition, and exports an editable PowerPoint file
plus a PNG preview.

The classic editable three-column poster remains supported, while the active
optimization path can select among twelve controlled layout families through a
versioned LayoutSpec and deterministic coordinate compiler.

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
new exploration, existing-Lineage improvement, structural mutation, or template
validation. Improvement iterations run RevisionPlanner and
GroundedContentOptimizer before the design agents, Renderer, and Critic. A
quality score never terminates a Batch early.

Graceful stop finishes the current candidate evaluation; force-stop exits at
the next safe agent boundary after the current blocking model/render call
returns. Pause/resume/stop controls are provided by `LoopControl`.

Campaigns span process launches and are matched by hashes of the PDF/logos,
poster dimensions, foundation schema, and layout-engine schema. A Campaign can
retain multiple independently resumable finite Batches, each targeting 100
committed Critic evaluations by default, but its exclusive lease permits only
one `IN_PROGRESS` Batch. Graceful stop persists the selected Batch as `PAUSED`;
another Batch may then be created without deleting it, and either can later be
selected explicitly. Batch IDs are Campaign-scoped, monotonically increasing,
and never reused. Each Batch freezes its scheduling policy/target but reads the
latest Campaign Portfolio/content state and eligible global knowledge whenever
it resumes. `iterations/<N>/COMPLETED.json` is the only commit marker and now
records `batch_id`; `batch_state.json` owns an explicit committed-iteration
ledger, so interleaved Batches may own non-contiguous global iterations. A stale
uncommitted attempt is abandoned and consumes no Batch budget. CLI/WebUI default
to the newest compatible campaign; callers may require an exact Campaign,
select an exact paused Batch, deliberately create a new Batch, or start an
independent Campaign.

The persistent Portfolio targets 40% exploration, 45% existing-Lineage
improvement, and 15% structural mutation over mixed-mode Campaign history.
Strict template validation is absent from mixed scheduling and runs only in a
pure validate Batch; pure-mode iterations never distort mixed quotas. It retains multiple branches, separates latest from best candidates,
creates a child Lineage for structural family changes, caps active Lineages at
eight, and carries family coverage debt across Batches.

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
    admission, four level-isolated global
    retrieval seat limits (10 per level/family), promotion, and storage policy.
  - Critic system `4.0.0` uses rubric `academic_poster_multifamily_v2`.
  - The existing 78-point archive threshold is unchanged. The old 85-point
    template threshold is now a high-potential label, never a second save gate;
    calibrate scores before changing admission.
- `config/agent_policy.yaml`
  - Per-agent temperature, output length, JSON mode, and thinking policy.

### Scientific content pipeline

- `src/agents/parser.py`
  - Uses Marker to convert the PDF to Markdown and extract visual assets.
  - Extracts captions, title/authors, legacy ABT narrative, and visual classes.
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
  - Uses a semantic verifier and revalidates any proposed correction.
  - Verification failure is fail-closed: the claim is not published.
- `src/agents/grounded_curator.py`
  - Arranges verified claims into sections and columns.
  - The model may select/group claim IDs and visuals, but cannot rewrite claim
    text.
  - Unknown IDs are removed and omitted verified claims are restored.

### Design and rendering pipeline

- `src/agents/color_agent.py`
  - Uses the affiliation logo with the vision model to select a theme color.
  - Falls back to the key figure and then to the configured navy theme.
  - Records palette provenance and applies only named deterministic accessible
    palette/contrast presets selected by RevisionPlanner.
- `src/agents/section_title_designer.py`
  - Produces the fixed `rectangle_left` section-title treatment in code.
- `src/agents/layout_with_balancer.py`
  - Orchestrates initial and final layout. The legacy Balancer and its
    three-column capacity restoration run only for `classic_three_column`;
    other families use deterministic LayoutSpec zone compilation and are
    repaired through Critic/RevisionPlanner.
- `src/agents/balancer_agent.py`
  - May reorder/move existing sections, change vertical priorities, select a
    subset of existing claim IDs, and remove approved visuals.
  - Must not create sections, rewrite section titles or scientific text, invent
    claim IDs, or add unapproved visuals. Sanitization enforces these rules after
    the LLM response.
- `src/agents/layout_agent.py`
  - Preserves the original three-column renderer as one family and compiles the
    other registered families into arbitrary bounded zones using the same
    inch-based text, visual, logo, and section measurement helpers.
- `src/layout/families.py`
  - Defines LayoutSpec schema v1, the LayoutFamilyRegistry, PaperProfile-aware
    family applicability, LayoutArchitect assignment, deterministic geometry
    compilation, and generalized region utilization analysis.
  - Registers twelve initial families: classic three column, asymmetric two
    column, four-column modular, central hero with side rails, top hero with
    bottom grid, horizontal narrative bands, method flow spine, comparison
    split, result dashboard cards, small-multiples matrix, timeline/stage
    narrative, and modular editorial mosaic.
  - Models never supply final x/y/width/height. RevisionPlanner may change only
    relational zone assignments, reading order, and the primary anchor.
- `src/layout/text_height_measurement.py`
  - Uses `python-pptx` fit behavior and bundled font files to estimate rendered
    height.
  - Its margins and wrapping assumptions must remain synchronized with the
    renderer.
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
  - Section fit targets 95%-100% utilization with controlled inter-module gaps;
    97.5% is the planning target, not permission to add filler. Non-classic
    families use their actual LayoutSpec zone heights rather than three-column
    projection.
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
- `src/agents/content_optimizer.py`
  - Executes bounded requests to use a same-root verified variant, make a compact
    variant, restore a relevant omitted claim, or add a claim from evidence.
  - Newly generated prose must pass the full ClaimVerifier. Supplemental
    evidence must be a new exact normalized excerpt from a source chunk.
  - Base `verified_claims` stay immutable; verified variants, supplemental
    evidence, and selection state are append-only campaign memory.
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
    `template_evaluation`.
  - Stores exact blueprints internally, while Planner receives only relational
    bands/classes and design principles. Ordinary retrieval samples at most
    one template per family; it does not send 40 templates or exact geometry to
    Planner. The 10x4 seats are global across all papers, not per-paper quotas.
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
  - Schema-v8 lazily migrates the index, backfills independent design scores
    from archived Critic reports where available, reconstructs legacy L1
    cross-paper validated profiles, and conservatively reconstructs per-paper
    retry trials from strict usage logs. If profile proof is
    absent, old L1 cross-paper ordinary reference fails closed while strict
    validation remains available. Migration never deletes accepted bundles.
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
  - `explore`, `revise`, and `mutate` retrieve no templates. Mixed launches
    begin with three template-free iterations; pure modes bypass warmup while
    pure exploration remains entirely template-free. Family rotation, cooldown,
    near-duplicate suppression, and small relational contexts protect against
    template fixation.
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
    reports/Lineage snapshots, restore the best accepted poster, and keep
    rejected artifacts out of the accepted archive.
  - Accept an exact `batch_id` or an explicit `new_batch` request. Graceful and
    cooperative force stops persist the selected nonterminal Batch as `PAUSED`;
    failures persist `FAILED_REQUIRES_USER`. Resume keeps the frozen Batch policy
    but loads current Campaign/global knowledge. Every attempt, outcome, commit,
    template-usage marker, and shared design event carries Batch provenance.
  - Each Batch freezes `schedule_policy.mode` and optional target Lineage.
    Supported modes: mixed, explore, improve, mutate, validate. Mixed freezes
    its 40/45/15 weights and never schedules validation. Pure validation
    freezes eligible template IDs at Batch creation, reports blocked topology,
    terminates as EXHAUSTED when the snapshot empties, and never falls back to
    exploration. It updates only its source template and creates no new template,
    design Lineage, family-coverage count/debt, ordinary cooldown, or global
    design-feedback event. Pure improve/mutate require an existing Lineage.
  - Emits structured Campaign/Batch/Iteration/Attempt, per-agent stage,
    Critic, archive/template, validation level/status, error, and final-status events.
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
- `src/workflow/portfolio.py`
  - Separates all-mode counts from mixed-only 40/45/15 deficit counts; legacy
    Portfolio state lazily migrates by treating prior counts as mixed. Pure
    validation increments only audit mode/history counters; it returns before
    creating/updating Lineages, recent-Lineage rotation, family counts, or
    family exploration debt. Design modes rotate recently used Lineages when
    multiple exist.
  - Owns rolling mode deficits, family coverage, multi-Lineage selection,
    best/latest separation, stagnation, child mutation Lineages, and the active
    Lineage cap. Portfolio state is Campaign-scoped and never resets at a Batch
    boundary.
- `src/workflow/campaign.py`
  - Owns compatible campaign discovery, input copies, exclusive leases, frozen
    foundation persistence, attempts, stale-attempt recovery, and atomic JSON
    commit markers, finite Batch state/reports, and per-Lineage latest/best
    design snapshots.
  - Campaign schema v4 and Batch schema v4 replace the single-active-Batch
    assumption with `batch_ids`, `active_batch_id`, paused/archived registries,
    a permanent `next_batch_number` high-water mark, and per-Batch
    `committed_iteration_ids`. Legacy sequential Batches migrate lazily from
    their stored iteration ranges and commit markers. Multiple paused Batches
    are allowed; ambiguous default resume fails closed. `COMPLETED`,
    `EXHAUSTED`, and `UNAVAILABLE` are immutable terminal states; archive is
    reversible and never deletes provenance or learned knowledge.
- `src/workflow/global_knowledge.py`
  - Shares only committed, de-identified Critic design feedback across
    Campaigns. Stores rubric/profile/family outcome aggregates and
    non-causal repair associations, never scientific prose, exact coordinates,
    claims, poster files, or raw Campaign names. The Planner receives bounded
    family-specific priors; restart replay fills missing committed design
    events. Pure validation attempts are deliberately excluded from this
    design-memory stream, including crash replay.

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
    structured_sections.json
    evidence_bank.json
    academic_entities.json
    narrative_plan.json
    poster_claims.json
    verified_claims.json
    verification_report.json
    story_board.json
    layout_spec.json
    initial_layout_data.json
    column_analysis.json
    optimized_story_board.json
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
    batches/<batch_id>/
      batch_state.json  # schedule plus committed_iteration_ids ledger
      batch_report.json
    lineages/<lineage_id>/
      lineage_state.json
      latest_state.json
      best_state.json
      best_state_<rubric_version>.json
    sessions/<session_id>/session_state.json
    iterations/<iteration>/
      COMPLETED.json
      TEMPLATE_USAGE_APPLIED.json
      attempts/<attempt_id>/
        status.json
        state_snapshot.json
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
  design_memory/rejection_memory.jsonl
  design_memory/global_knowledge/events/<hashed_campaign>_<iteration>.json
  loop_sessions/<session_id>/
    loop_state.json
    events.jsonl
    progress_events.jsonl
    iterations/<iteration>.json
```

Some older checked-out/generated examples use the legacy layout directly under
`output/<paper_name>/`. Support both shapes when inspecting historical results.

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

Each launch runs one selected finite Batch with 100 committed Critic
evaluations by default. A Campaign may contain multiple `PAUSED` Batches. If
exactly one exists it resumes automatically; otherwise use `--batch-id
batch_0004` or `--new-batch`. `--list-batches`, `--archive-batch`, and
`--unarchive-batch` are model-free management actions for an existing compatible
Campaign. Omit `--mode` when resuming because mode/target/budget are frozen; new
Batches default to `mixed`. `--mode explore|improve|mutate|validate` selects a
pure mode, and `--target-lineage-id` narrows pure improve/mutate.
Pure validation freezes the eligible template set for its Batch and can
terminate early as EXHAUSTED if no pending eligible tasks remain; this is task exhaustion, not quality-based early stopping. Quality never ends it early. `--iterations` sets the
target for a newly created Batch; an already active Batch retains its stored
target. `Ctrl+C` requests a graceful persistent Batch pause after the current
evaluation; a second `Ctrl+C` requests exit at the next safe agent boundary and
the unfinished attempt remains uncommitted.
The CLI validates an aspect ratio between 1.4 and 2.0, fixes the output width to
54 inches, and derives height from the requested ratio.

`--resume latest` is the default; use `--resume new` for an independent campaign
or `--resume required --campaign_id <id>` to require an exact compatible one.
Compatibility is based on input hashes, dimensions, foundation schema, and
layout-engine schema. An interrupted uncommitted iteration is retried with the
same iteration number, and only committed Critic evaluations consume Batch
budget.

The CLI now tees each optimization launch to its timestamped `run.log`,
displays a live dashboard on a TTY (plain events when redirected), and returns
a nonzero exit code for `FAILED_REQUIRES_USER` or `UNAVAILABLE`. Pure
validation `EXHAUSTED` is a normal, zero-exit terminal state. The compact
`loop_sessions/<session_id>/progress_events.jsonl` records semantic events;
`COMPLETED.json` remains the only iteration commit marker.

The WebUI consists of:

- `webui/backend/main.py`: FastAPI application on port 8001.
- `webui/frontend/`: React + TypeScript + Vite application on port 3000.
- `webui/start_backend.py`: backend launcher.
- `webui/start_frontend.sh`: frontend launcher.

The backend stores job state and recent logs in process memory, saves uploads in
a temporary directory, and creates a ZIP archive after completion. The WebUI
enables resumable Batch optimization by default, accepts the Batch budget,
shows Batch/Portfolio/family/Lineage plus iteration/score/archive counts and the
current best accepted preview, and exposes pause, resume,
graceful-stop, and force-stop endpoints. It also exposes resume mode and an
optional campaign ID. A process restart loses the old in-memory job controls,
but the next compatible `latest` run restores the persisted campaign foundation
and last committed iteration.

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
132 passed, 5 subtests passed
```

Existing tests cover:

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
  paper-free PNG/PPTX previews, rejected artifact deletion, and iteration reports;
- campaign compatibility, committed-iteration resume, same-number retry, and
  attempt-level crash recovery;
- 95%-100% section-fit scoring, gap detection, and content adequacy feedback;
- grounded compact/expanded claim actions, exact supplemental excerpts, and
  cross-root substitution rejection;
- relational-only template context, cross-family duplicate blocking, cooldown,
  idempotent usage tracking, and anti-fixation strategy scheduling;
- campaign-scoped template cooldown, lazy schema migration, and bounded history;
- twelve registered bounded layout-family specs and family-contract Critic
  failures;
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
- Final layout validation is calculated but is not currently used to fail the
  pipeline.
- A recent real run still reported unresolved physical overflow in the right
  column after claim pruning, yet produced PPTX/PNG output. Treat unresolved
  overflow handling as an open issue.
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
- Non-classic families bypass the legacy three-column Balancer. Their zone
  geometry and reading order have deterministic/Critic hard gates, but real
  model-backed visual quality across all twelve families has not yet been
  sampled in this conversation; module overflow is expected to be rejected and
  repaired by later iterations.
- Force-stop is cooperative: it exits between agents but cannot cancel a model
  request or LibreOffice process that is already blocking.
- The Critic store is file-backed JSON/JSONL rather than a database.
- The schema-v8 index retains full blueprints, per-paper trials, and validation
  evidence references for compatibility; very large libraries may later need
  indexed per-template files or a database.
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
