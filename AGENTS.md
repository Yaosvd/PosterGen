# PosterGen Development Guide

This file is the persistent development context for AI coding agents working in
this repository. Read it completely before inspecting or modifying the project.

## Project Purpose

PosterGen converts an academic paper into an academic poster. It extracts and
grounds scientific content from a PDF, selects figures and tables, plans a
three-column layout, and exports an editable PowerPoint file plus a PNG preview.

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
  -> PPTX + PNG
```

The graph currently has no conditional failure edges. Agents append messages to
`state["errors"]`; the pipeline checks accumulated errors after graph execution.

## Important Modules

### Entry points and shared infrastructure

- `src/workflow/pipeline.py`
  - CLI entry point and LangGraph construction.
  - Captures stdout/stderr in `run.log`.
  - Writes timing, token, model, and API-call information.
- `src/state/poster_state.py`
  - Defines `PosterState`, `ModelConfig`, token accounting, and timing metrics.
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
- `src/agents/section_title_designer.py`
  - Produces the fixed `rectangle_left` section-title treatment in code.
- `src/agents/layout_with_balancer.py`
  - Orchestrates initial layout, LLM balancing, grounded-content restoration,
    physical-capacity enforcement, and final layout.
- `src/agents/balancer_agent.py`
  - May reorder/move existing sections, change vertical priorities, select a
    subset of existing claim IDs, and remove approved visuals.
  - Must not create sections, rewrite section titles or scientific text, invent
    claim IDs, or add unapproved visuals. Sanitization enforces these rules after
    the LLM response.
- `src/agents/layout_agent.py`
  - Builds a three-column layout using inch-based CSS-like geometry.
  - Measures section titles, body text, visuals, logos, and section containers.
- `src/layout/text_height_measurement.py`
  - Uses `python-pptx` fit behavior and bundled font files to estimate rendered
    height.
  - Its margins and wrapping assumptions must remain synchronized with the
    renderer.
- `src/agents/font_agent.py`
  - Identifies keywords and applies custom bold, italic, and color markup.
  - Must not insert or rewrite visible scientific text.
- `src/agents/renderer.py`
  - Creates a single-slide editable PPTX with `python-pptx`.
  - Preserves simple inline subscript/superscript as editable DrawingML runs.
  - Renders supported display fractions as high-resolution PNG images.
  - Uses LibreOffice headlessly to convert the PPTX to PNG.
- `utils/inline_math.py` and `utils/display_formula.py`
  - Implement the safe inline-script and display-formula grammars.
- `utils/evidence_utils.py`
  - Implements number extraction/normalization and evidence-reference checks.

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
- After verification, downstream agents may arrange or omit claims but must not
  rewrite them.
- The Balancer output is untrusted until sanitized against the original
  GroundedCurator board.
- Formula normalization must not reinterpret ordinary Markdown or prose.

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
    initial_layout_data.json
    column_analysis.json
    optimized_story_board.json
    balancer_decisions.json
    optimized_layout.json
    final_column_analysis.json
    final_design_layout.json
    color_scheme.json
    section_title_design.json
    keywords.json
    styling_interfaces.json
    styled_layout.json
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

The CLI validates an aspect ratio between 1.4 and 2.0, fixes the output width to
54 inches, and derives height from the requested ratio.

The WebUI consists of:

- `webui/backend/main.py`: FastAPI application on port 8001.
- `webui/frontend/`: React + TypeScript + Vite application on port 3000.
- `webui/start_backend.py`: backend launcher.
- `webui/start_frontend.sh`: frontend launcher.

The backend currently stores job state and recent logs in process memory, saves
uploads in a temporary directory, runs the same LangGraph in a background task,
and creates a ZIP archive after completion. A process restart loses job state.

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
27 passed, 5 subtests passed
```

Existing tests cover:

- body-text and section-title geometry;
- display formula parsing, measurement, and rendering;
- formula multiplication normalization;
- editable inline subscript/superscript rendering;
- grounded claim restoration, pruning, section removal, and column rebalancing;
- successful and failed model-call tracking.

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

## Known Technical Context

- README documentation still describes the older six-agent architecture and
  does not fully document the grounding pipeline or all current JSON artifacts.
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
- WebUI jobs, logs, and temporary directories have no persistence or cleanup
  policy.
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

- 2026-09-14: Added the repository-wide requirement that every file-changing
  conversation must also maintain this `AGENTS.md` and report that maintenance
  in its final handoff.
