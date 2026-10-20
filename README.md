<div align="center">
  
  <img src="./resource/logo.png" height="100" style="object-fit: contain;">

  <h2>PosterGen: Aesthetic-Aware Multi-Modal Paper-to-Poster Generation <br> via Multi-Agent LLMs</h2>
  <!-- <h4>🌟 🌟</h4> -->
  
  <br>
  
  <p>
    <a href="https://hadlay-zhang.github.io">Zhilin Zhang</a><sup>1,2 ★</sup>&nbsp;
    <a href="https://wyattz23.github.io">Xiang Zhang</a><sup>3 ★</sup>&nbsp;
    <a href="https://upup-wei.github.io/">Jiaqi Wei</a><sup>4</sup>&nbsp;
    <a href="https://Y-Research-SBU.github.io/PosterGen">Yiwei Xu</a><sup>5</sup>&nbsp;
    <a href="https://chenyuyou.me/">Chenyu You</a><sup>1</sup>
  </p>

  <p>
    <sup>1</sup> Stony Brook University &nbsp;&nbsp; 
    <sup>2</sup> New York University &nbsp;&nbsp;
    <sup>3</sup> University of British Columbia &nbsp;&nbsp; <br>
    <sup>4</sup> Zhejiang University &nbsp;&nbsp; 
    <sup>5</sup> University of California, Los Angeles &nbsp;&nbsp; 
    <sup>★</sup> Equal Contribution <br>
  </p>

<p align="center">
  <a href="https://arxiv.org/abs/2508.17188">
    <img src="https://img.shields.io/badge/ArXiv-2508.17188-B31B1B?style=flat-square&logo=arxiv" alt="Paper">
  </a>
  <a href="https://Y-Research-SBU.github.io/PosterGen">
    <img src="https://img.shields.io/badge/Project-Website-blue?style=flat-square&logo=googlechrome" alt="Project Website">
  </a>
  <a href="https://huggingface.co/spaces/Y-Research-Group/PosterGen">
    <img src="https://img.shields.io/badge/Hugging%20Face-Demo-yellow?style=flat-square&logo=huggingface" alt="Hugging Face Demo">
  </a>
  <a href="#">
    <img src="https://img.shields.io/badge/LangGraph-0.4.8-042f2c?style=flat-square&logo=langgraph" alt="LangGraph 0.4.8">
  </a>
  <br>
  <a href="https://github.com/Y-Research-SBU/PosterGen/issues/1">
    <img src="https://img.shields.io/badge/WeChat-Group-green?style=flat-square&logo=wechat" alt="WeChat Group">
  </a>
  <a href="https://discord.gg/BSJpG8TQSg">
    <img src="https://img.shields.io/badge/Discord-Community-5865F2?style=flat-square&logo=discord" alt="Discord Community">
  </a>
</p>

</div>

## Abstract

> In this work, we propose a multi-agent LLMs framework that is guided by design principles.  
> Our multi-agent LLMs adopt a workflow of specialist agents that mirrors a professional design process:
>
> - **Parser Agent** – extracts and structures all content from the source paper.  
> - **Curator Agent** – designs a narrative-based storyboard.  
> - **Layout Agent** – transforms the storyboard into a constrained, editable layout selected from multiple families.
> - **Styling Agents** – apply a harmonious color palette and a hierarchical typographic system to ensure aesthetic coherence.  
>
> This methodology is designed to generate a well-designed poster that minimizes the need for manual fine-tuning.

![](./resource/method.png)

## 📢 News

- **2025.08.26** Our paper is now available on [arXiv](https://arxiv.org/abs/2508.17188)! 📄
- **2025.08.23** Code Released. PosterGen now available! 🎉🎉

## 🚀 Quick Start

### System Requirements
- **Operating System**: Windows, Linux, or macOS
- **Python Version**: 3.11

### 1. Environment Setup

#### Option 1: [UV](https://docs.astral.sh/uv/getting-started/installation/) (Recommended)

```bash
git clone -b main https://github.com/Y-Research-SBU/PosterGen.git
cd PosterGen

uv sync
```

#### Option 2: Conda

```bash
# Create and activate conda environment
conda create -n poster python=3.11 -y
conda activate poster

git clone -b main https://github.com/Y-Research-SBU/PosterGen.git
cd PosterGen

pip install -r requirements.txt
```

### 2. Install LibreOffice

**Windows:**
1. Download and install LibreOffice from [official website](https://www.libreoffice.org/download/download/)
2. Add LibreOffice to your system PATH:
   - Default installation: Add `C:\Program Files\LibreOffice\program` to PATH
   - Or custom installation: Add `<your_install_path>\LibreOffice\program` to PATH

**macOS:**
```bash
brew install --cask libreoffice
```

**Ubuntu/Linux:**
```bash
sudo apt install libreoffice
# Or using snap:
sudo snap install libreoffice
```

### 3. API Keys Configuration

Create a `.env` file in the project root with your API keys:

```bash
OPENAI_API_KEY="your_openai_key"
ANTHROPIC_API_KEY="your_anthropic_key"
ZHIPU_API_KEY="your_zhipu_key"
```

To use a compatible API service or a custom deployment, set the base URL in your `.env` file:

```bash
OPENAI_BASE_URL="https://your-api-endpoint.com/v1"
ANTHROPIC_BASE_URL="https://your-anthropic-endpoint.com"
GOOGLE_BASE_URL="https://your-google-endpoint.com"
ZHIPU_BASE_URL="https://your-zhipu-endpoint.com"
```

#### Local text and vision models

PosterGen can use separate OpenAI-compatible endpoints for text and vision
models. Configure both services in `.env`:

```bash
LOCAL_TEXT_BASE_URL="http://127.0.0.1:8000/v1"
LOCAL_TEXT_MODEL="qwen3.8-27b"
LOCAL_VISION_BASE_URL="http://127.0.0.1:8000/v1"
LOCAL_VISION_MODEL="qwen3.8-27b"
LOCAL_API_KEY="EMPTY"
```

When these variables are set, the CLI defaults to the configured local models.
Their model IDs can also be passed explicitly with `--text_model` and
`--vision_model`.

## Data Structure Setup

Before running the multi-agent pipeline, organize your files in the `data/` folder:

```
data/
└── <your_paper_name>/
    ├── paper.pdf          # Your research paper (required)
    ├── aff.png           # Affiliation logo for color extraction (required)
    └── logo.png          # Conference logo for poster (required)
```

**Examples (check ``data/`` folder):**
```
data/
└── Neural_Encoding_and_Decoding_at_Scale/
    ├── paper.pdf
    ├── aff.png
    └── logo.png
└── ...
```

## 🎯 Usage

### Command-line Interface

Generate your poster with a single command:

**For UV setup:**
```bash
uv run python -m src.workflow.pipeline \
  --poster_width 54 --poster_height 36 \
  --paper_path ./data/Your_Paper_Name/paper.pdf \
  --text_model gpt-4.1-2025-04-14 \
  --vision_model gpt-4.1-2025-04-14 \
  --logo ./data/Your_Paper_Name/logo.png \
  --aff_logo ./data/Your_Paper_Name/aff.png
```

**For Conda setup:**
```bash
python -m src.workflow.pipeline \
  --poster_width 54 --poster_height 36 \
  --paper_path ./data/Your_Paper_Name/paper.pdf \
  --text_model gpt-4.1-2025-04-14 \
  --vision_model gpt-4.1-2025-04-14 \
  --logo ./data/Your_Paper_Name/logo.png \
  --aff_logo ./data/Your_Paper_Name/aff.png
```

**Parameters:**
- `--poster_width/height`: Poster dimensions in inches, with aspect ratio (w/h): lower bound 1.4 (ISO A paper size), upper bound 2 (human vision limit)
- `--paper_path`: Path to your PDF paper
- `--text_model`: LLM for text processing (options: "gpt-4.1-2025-04-14" (default), "gpt-4o-2024-08-06", "gpt-4.1-mini-2025-04-14", "claude-sonnet-4-20250514")
- `--vision_model`: Vision model for analysis (same options as text_model)
- `--logo`: Conference logo
- `--aff_logo`: Affiliation logo (used for color scheme extraction)

This `src.workflow.pipeline` command is the independent one-shot classic
three-column route. It still uses the original Balancer/renderer path and does
not create Campaigns, loop Lineages, accepted-template records, or global
layout-design knowledge. Its Critic report is only a diagnosis of that run.
Use the separate command below to search layout families and accumulate
optimization knowledge.

### Resumable Critic Optimization Batches

Run a finite Planner-Coder-Critic Batch with:

```bash
python -m src.workflow.critic_pipeline \
  --paper_path ./data/Your_Paper_Name/paper.pdf \
  --text_model gpt-4.1-2025-04-14 \
  --vision_model gpt-4.1-2025-04-14 \
  --logo ./data/Your_Paper_Name/logo.png \
  --aff_logo ./data/Your_Paper_Name/aff.png \
  --iterations 100 \
  --resume latest
```

Scientific parsing, evidence extraction, claim writing, and verification run
once. Poster planning, rendering, Critic evaluation, and grounded revision then
continue until the finite committed-iteration budget is complete. Quality never
terminates a Batch early; --iterations changes the default budget of 100.

Resume semantics are campaign-based. The default `--resume latest` reopens the
newest campaign with the same PDF, logos, poster dimensions, scientific
foundation schema, and layout-engine schema. Use `--resume new` for an
independent campaign, or `--resume required --campaign_id <id>` to require one
exact campaign.

A Campaign may retain several unfinished Batches, but its exclusive lease
allows at most one `IN_PROGRESS` Batch. A graceful stop persists the selected
Batch as `PAUSED`; it does not cancel or delete its work. If exactly one paused
Batch exists, the next default launch resumes it. When several paused Batches
exist, select one with `--batch-id batch_0004`, or deliberately allocate the
next permanent ID with `--new-batch`. Batch IDs are monotonically increasing
within a Campaign and are never reused. The same `batch_0004` in another
Campaign is independent because its full identity is `(campaign_id, batch_id)`.

```bash
# Resume one exact paused Batch
python -m src.workflow.critic_pipeline \
  --paper_path ./data/Your_Paper_Name/paper.pdf \
  --resume required --campaign_id <campaign_id> \
  --batch-id batch_0004

# Preserve paused Batches and create the next Batch
python -m src.workflow.critic_pipeline \
  --paper_path ./data/Your_Paper_Name/paper.pdf \
  --resume required --campaign_id <campaign_id> \
  --new-batch --mode explore --iterations 100
```

List or non-destructively archive Batch records without running the model:

```bash
python -m src.workflow.critic_pipeline --paper_path <paper.pdf> \
  --resume required --campaign_id <campaign_id> --list-batches
python -m src.workflow.critic_pipeline --paper_path <paper.pdf> \
  --resume required --campaign_id <campaign_id> --archive-batch batch_0004
python -m src.workflow.critic_pipeline --paper_path <paper.pdf> \
  --resume required --campaign_id <campaign_id> --unarchive-batch batch_0004
```

Only `PAUSED` or `FAILED_REQUIRES_USER` Batches can be archived; archive is a
reversible visibility state, not physical deletion. `COMPLETED`, `EXHAUSTED`,
and `UNAVAILABLE` are terminal. A failed Batch requires explicit `--batch-id`
retry after the underlying problem is fixed.

A Campaign can span many process launches. An iteration is complete only when
its campaign-level `COMPLETED.json` exists. Every new marker records its owning
Batch. If iteration 31 was committed and iteration 32 was interrupted, the
abandoned attempt consumes no budget and global iteration 32 is reused by the
next selected Batch. Batch progress comes from its explicit committed-iteration
ledger, so a resumed Batch can own non-contiguous global iteration numbers.
Each Batch keeps its **frozen scheduling mode and target**, while resume loads
the latest Campaign Portfolio, Campaign-wide verified content/evidence memory,
and eligible global templates/design priors. Old Lineage snapshots restore only
their branch-local design and content selection; they cannot roll shared
verified variants or supplemental evidence backward. Each Batch stores
creation/resume/last-iteration knowledge watermarks, and each
`COMPLETED.json` records the exact content, Portfolio, template-library, and
global-design-memory digests used by that candidate. Omit `--mode` when
resuming; changing an unfinished Batch policy is rejected.

Choose `--mode explore` for template-free new routes, `--mode improve` for
Critic-directed revisions of existing Lineages, or `--mode validate` for
pending template validation only. `--target-lineage-id <id>` can narrow a pure
improve Batch. Improve requires an existing Lineage; validation stops as
`EXHAUSTED` when eligible tasks run out, even before 100 evaluations. No pure
mode silently falls back to exploration. The WebUI exposes the same Batch mode
and optional target Lineage. A fresh pure validate Batch may therefore finish
without a poster when no task is eligible.

Campaign, Batch, Session, Iteration, and Attempt are distinct: a Campaign is
the long-lived paper optimization project; a Batch is a finite budget; a
Session is one process launch; an Iteration is one committed candidate
evaluation; and an Attempt is one execution try that consumes no budget until
it is committed.

Each iteration runs Planner -> Coder -> Critic. A persistent PortfolioScheduler
targets 45% new exploration and 55% existing-Lineage improvement across
**mixed-mode** Campaign history. If every active Lineage is stagnated, the next
mixed task is forced to exploration. Strict template validation is never
scheduled by mixed mode and runs only in a pure `--mode validate` Batch.
Improve keeps three independent Lineage tracks: latest attempt, best safe
rejected working base, and best accepted base. It edits the best accepted base
when one exists; before the first acceptance it edits the rubric-scoped best-
promising rejection. The most recently committed attempt's full Critic/revision
feedback is supplied separately, so a later worse repair is not forgotten and
does not replace the stronger base. Promising rejects remain Lineage-local editable bases: they are not
poster archives, templates, archetypes, or globally reusable bases. Their de-identified
Critic outcomes still contribute to the existing bounded global feedback memory.
Feedback is rubric-scoped and the bounded recent history never crosses Lineages
or Campaigns. Improve turns Planner zone/reading-order/anchor requests
and verified content changes into hard solver constraints, searches only nearby same-family geometry,
and retries preflight without spending Batch budget. Its final recovery attempt
compiles the unchanged parent geometry and records a per-operation revision
execution report. This exact-parent result commits as a no-change/stagnation
attempt and consumes one Batch iteration, but creates no archive, template,
poster outcome count, archetype, or global design-memory event.
Planner edits now remain on the current working storyboard through content
optimization; the parent is comparison/fallback data only. Deletions require
scoped actionable Critic evidence. A branch-local recovery policy prevents
automatic repair from silently restoring deliberately removed content or the
old owner of a moved image. Exact parent/candidate whitespace checks can revoke
a harmful deletion and perform one bounded same-family refit. Final styled
preflight verifies visible effects, and a separate revision-admission veto
prevents unsafe high-score results from entering archives/templates while
retaining the original Critic score and committed diagnostic evidence.
Explicit later source-visual/verified-claim restoration remains available;
these policies do not permanently blacklist source content.
Older loop-classic Lineages remain preserved, but Improve will only restore a
parent whose saved LayoutSpec, geometry fingerprint, feasibility and preflight
evidence, topology, and visible section assignments agree. A replayed snapshot
writer version alone is not evidence of a modern generated layout. Mixed mode
skips an incompatible Lineage; a pure Improve Batch targeting one stops as
`UNAVAILABLE` before model work. This does not delete old posters or feedback,
and does not automatically rebase an old poster into a new layout.

A Validate topology that fails before rendering is not assigned a poster score
and is not counted as an accepted or rejected poster. It is nevertheless a
committed strict-transfer attempt: failures one and two stay retryable, and the
third finalizes the failed template-paper task. Such attempts create no poster
evidence, template, Lineage, family coverage, or global design-feedback event.
Pure-mode iterations are counted separately and cannot distort these quotas. Rejected candidates feed the
full structured issue report into RevisionPlanner and then
GroundedContentOptimizer. The Critic measures each module against an independent
height budget; 95%-100% is the ideal utilization band, but the optimizer must
use useful paper-grounded content rather than filler. Every loop family,
including classic three-column, is measured against its actual LayoutSpec
zones. Empty zones and severe unused bottom regions are hard fit failures.

Design knowledge is shared globally across Campaigns in
`storage/critic_loop/design_memory/global_knowledge/events/`. Only committed
Critic outcomes contribute: rubric/profile/family, numeric scores, approved
issue categories and operations, and conservative same-rubric repair
associations. No paper prose, claim text, exact coordinates, or poster assets
are copied into this store. The Planner receives a bounded, non-binding
summary for the current family; global templates remain a separate library.
Template-library schema v11 carries a monotonic semantic revision and digest
and direct source Campaign/Batch/iteration/Lineage/mode/parent provenance;
legacy records backfill that chain from accepted-bundle provenance when
available. Portfolio schema v5 separates templates merely referenced by a
Lineage from templates actually produced by it. The
global design memory exposes an event count and digest; Campaign content memory
uses its own revision/digest; and Portfolio snapshots include schema, committed
task count, and digest. These identities make it possible to audit what changed
between Batch creation, resume, and each committed iteration.
After a crash, committed events missing from this store are replayed
idempotently from `COMPLETED.json`. Template validation usage is also applied
only after the same commit marker, then checkpointed with
`TEMPLATE_USAGE_APPLIED.json`; restart fills any gap before choosing new
validation work. Every Critic-accepted poster from a normal design mode creates
exactly one paper-free template JSON and editable PNG/PPTX preview. A pure
`validate` iteration never distills or registers a new template.
Similarity and per-family level seats suppress only Planner retrieval, not
storage or validation; pure exploration remains template-free.

The CLI now shows a live progress panel on interactive terminals and a
chronological English event stream on redirected terminals. It reports Campaign
and Batch creation/resume, committed Batch progress (for example 31/100),
global iteration and attempt numbers, mode/family/Lineage/template selection,
agent-stage starts and elapsed times, Critic decisions and issue IDs, accepted
poster archives, saved templates and preview paths, strict-transfer validation
pass/fail with attempt number, retry/final status and resulting level, explicit
validation-evidence paths and “no new template created”, the frozen validation
snapshot including topology-blocked templates, and the final Batch status.
A stage running over one minute produces periodic heartbeat lines
when output is redirected. These events are informational; only
`campaigns/<campaign_id>/iterations/<N>/COMPLETED.json` consumes a Batch slot.

The launch output's `run.log` contains plain event lines and agent messages.
On raised exceptions, the terminal gives the stage and short message, while
`run.log` contains the full traceback; errors returned by agents show their
reported message. A compact machine-readable copy is written to
`storage/critic_loop/loop_sessions/<session_id>/progress_events.jsonl`.
The CLI exits nonzero for `FAILED_REQUIRES_USER` or `UNAVAILABLE`;
`EXHAUSTED` is a normal end for a pure validation Batch.

Unexpected generation errors are not Critic rejections. A current candidate
must complete rendering and own nonempty PPTX/PNG files before Critic runs.
Programming errors fail the Batch without consuming an iteration or teaching
rejection feedback; known geometry failures keep their bounded retries (or
unscored strict-validation result). Root tracebacks and partial fit/repair
audits are preserved under the unique attempt directory, including
`attempt_failure_report.json`. The terminal stays concise; `run.log` contains
the full traceback.

All accounting remains draft until `COMPLETED.json`. A digest-bound
`commit_runtime_state.json` supports post-commit recovery, while pre-commit
failures restore counters, Portfolio, best bases and committed content memory.
Rejection journal publication is post-commit and idempotent. An offline,
model-free repair command is available for one explicitly selected Campaign:

```bash
.venv/bin/python -m src.workflow.reconcile_campaign --campaign-id <id>
```

It takes the Campaign lease, verifies complete commit history, reconciles
derived accounting, and retains legacy bad journal lines with append-only
invalidations. It does not launch a Batch, delete history, change scientific
foundation data, or unlock a failed Batch. Use a new Batch after a terminal
failure.


#### Critic v4 evaluation and repair contract

Critic 4.3.8 (`academic_poster_multifamily_v12_necessity`) separates hard validity gates from
quality scores. Rendered-artifact validity, scientific grounding, geometry,
minimum typography, region capacity, module fit, layout-family contracts, color
contrast, approved visual assets, and the required multimodal pass can reject a
candidate, but artifact existence itself does not inflate a layout score.
For the optimization route, the PPTX is additionally exported to a temporary
PDF and uniquely matched editable body text and module titles are checked against their
planned boxes, the canvas, and neighboring modules. Actual title-to-content
spacing is also checked. Explore/Improve may make one geometry-only title
correction and re-render after full preflight; strict Validate and exact-parent
fallback never make this correction. Inconclusive second measurements cannot
erase a previously confirmed failure. A confirmed collision or
overflow retries Explore/Improve before Critic without spending the Batch
iteration; the first three such retries per iteration retain an inspectable
`render_fit_preview.png` beside the attempt's `render_fit_report.json`.
Validate records the finding as a Critic failure. Unmatched text
is reported as inconclusive, not falsely rejected. The independent one-shot
classic route is unchanged. Weighted per-module target-share overage is now a
repair suggestion, not a hard physical-overflow finding; actual bounds errors
remain hard failures. This rubric change does not alter the 78-point admission
threshold.

RenderFit report schema v3 (`editable_exact_fragments_v1`) uses the same styling
grammar as Renderer: color/emphasis markup is not mistaken for visible body
text, while malformed markup and escaped literals retain their render behavior.
Section titles remain literal text. It first tries complete normalized block
equality, then lazily extracts PDF characters once to recover wrapped titles,
merged parallel textboxes and split paragraphs. Complete text, position,
reading order and unique character ownership are required; matching only a
prefix is not full coverage. Actual overflow glyphs are not clipped to planned
frames. Ambiguous or budget-exhausted matches remain `partial` with explicit
reasons. Display-formula images are explicitly outside editable-text scope;
their editable lead-in still requires matching.

Reports include title/body coverage, per-element matching methods/reasons,
title-gap coverage and bounded matching diagnostics, without scientific prose.
The terminal prints concise English summaries such as
`RenderFit partial | matched 9/12 | titles 4/6 | body 5/6` and unmatched IDs/reasons.
`passed` status means complete editable-text coverage with no confirmed fit
issue; `failed` preserves any confirmed issue even with incomplete coverage.
For compatibility, the boolean `passed` means only "no confirmed issue" and can
still be true for `partial`/`unavailable`; use `status` and `conclusive` as well.
These are text-fit findings, not overall Critic acceptance. Historical reports
are not overwritten or automatically rescored; the read-only spacing-audit
command below uses the current matcher on saved artifacts.

Loop titles share a versioned measurement/render contract with explicit point
line spacing; final typography is rechecked after FontAgent. Directional
adjacencies distinguish cross-zone vertical gaps from nearby side neighbors.
Critic reports the gap's unused-zone/gutter/content-inset decomposition and
extra terminal bottom whitespace beyond the outer margin. General spacing
issues are actionable score deductions, not automatic rejection of every
nonuniform baseline. Empty/severely unused zones and real overflow remain hard
failures. Missing gap evidence is explicitly unknown, not an all-clear.

The seven stable top-level dimensions are weighted as follows:

| Dimension | Weight | Archive minimum |
| --- | ---: | ---: |
| scientific integrity | 25% | 100 |
| content quality | 15% | 70 |
| layout integrity | 15% | 75 |
| readability | 15% | 70 |
| visual hierarchy | 10% | 65 |
| visual balance | 10% | 65 |
| aesthetics | 10% | 65 |

Each dimension has explicit evaluator-source weights in
`config/critic_config.yaml`; adding an evaluator therefore cannot silently
change all averages. The report also records paper-derived submetrics for
information layering/coverage/depth/completeness, narrative
structure/flow/concision, layout/whitespace/anchor/balance,
color palette/hierarchy/contrast/source, font hierarchy/emphasis/legibility,
alignment, robustness, and visual relevance. It does not impose a fixed
three-column layout, ABT narrative, module count, or image count.

`critic_report.json` uses schema v3. `poster_evaluation` contains the poster
aggregate, submetrics, and source contributions; `task_evaluation` records
strict template-transfer checks on validation runs. The older top-level score
and issue fields remain for loop/UI consumers. Poster archive admission remains
at 78 with all hard gates and dimension minima. Every admitted poster and its
structural template are saved together; the old 85-point template threshold is
only a high-potential audit label, not a second save gate.

RevisionPlanner receives the full structured issues, not only the rejection
summary. It can request grounded content changes and relational layout changes.
For visual repair it may select only named deterministic presets for WCAG text
contrast, accessible palette variants, semantic color normalization, reduced
accent density, typography hierarchy, and font normalization. It may replace a
visual only with another extracted approved asset. Raw colors, font sizes, font
names, coordinates, and replacement scientific prose are rejected. ColorAgent
and FontAgent execute those presets, while GroundedContentOptimizer and
ClaimVerifier remain solely responsible for scientific text changes.

Critic and rubric versions are stored with iteration and Lineage snapshots.
Best-score comparisons are scoped by rubric version, so upgrading the evaluator
does not compare a v4 score directly with a historical v3 score.

The content branch can select an already verified same-claim variant, create a
shorter variant, reuse an omitted relevant verified claim, or extract one new
exact excerpt from the original paper source for an underfilled module. Every
new or rewritten variant passes the full ClaimVerifier before it can appear.
The original verified evidence and claims remain immutable; variants and
supplemental evidence are append-only campaign memory.
The final wording of a verifier-suggested correction is independently checked
again for semantic support. Newly generated compact and supplemental claims
also pass a source-excerpt editorial audit: compaction must retain necessary
conditions, and added claims must be relevant and non-redundant. Failed claims
and their tentative evidence do not enter Campaign memory. Semantic model
checks reduce risk but cannot guarantee detection of every scientific error.

Poster layout is no longer restricted to three columns. Twelve controlled
families are enabled initially: classic three column, asymmetric two column,
four-column modular, central hero with side rails, top hero with bottom grid,
horizontal narrative bands, method flow spine, comparison split, result
dashboard cards, small-multiples matrix, timeline/stage narrative, and modular
editorial mosaic. The classic three-column family remains available in the
loop, but uses the same family Solver/coordinate compiler as its peers. It is
independent of the one-shot Balancer route described above.

Explore opens every registered, enabled family, including method flow,
comparison and timeline/stage families even when semantic hints are absent.
Paper profile v2 reads the actual NarrativePlanner `title_intent` and
`narrative_role` fields (with legacy title aliases); section IDs are never
searched as scientific prose. It records text-free rule/source provenance.
The existing `profile_key` classification remains unchanged for template
validation and retrieval. Hints indicate matching opportunities, not proof of
comparisons, chronology or causal relationships.

Selection is coverage-first: after excluding families that failed layout in
the current iteration, only families with the smallest committed design-use
count enter the draw. These counts include Explore and Improve, not just
exploration. Within that group, weights are `1 + bonus * match`, with match in
`[0, 1]` and `layout_families.selection.semantic_bonus_max` defaulting to 0.5
(allowed range 0 to 0.5). Missing hints never give zero weight. High semantic
matches cannot override coverage. The full pool being exhausted ends the
bounded search; excluded families are never silently reintroduced. This does
not guarantee twelve successful posters in twelve iterations.

Each Batch freezes selection-policy v1, the enabled family IDs and bonus.
An older resumable Batch upgrades once on its next launch and records the
migration; historical commits and foundation files stay intact. Existing
Campaigns retain their seed, including the Portfolio scheduler's seed.
Changes take effect after a safe pause/restart, not by hot-reloading a running
candidate. Each session writes `sessions/<session_id>/paper_profile.json` in
its Campaign, and each Explore attempt writes `family_selection_report.json`
beside its `status.json`. The report includes profile identity, policy, usage
counts, exclusions and their prior attempt reasons, match weights, seed and
selection. Terminal output distinguishes the enabled pool, current exclusions,
least-used group and selected weight.

All twelve families now declare `FamilyContract` v2: reading traversal,
required regions, split/span/mirror permissions, conditional role hints and a
bounded geometry strategy, plus independent focus and reading-entry policies.
New families register the same contract and may
provide a deterministic geometry generator; shared content search, refill,
repair accounting and diagnostics do not need another family-ID branch.
Classic three-column still has exactly three regions and forbids splits/spans.
Unknown reading roles remain hints, never invented chronology or comparison.

Loop design policy `grounded_family_design_v2` retains coverage, approved-visual,
compact and editorial beam paths within the existing search limits. Core claim
IDs are priorities over verified roots, not wording locks: grounded additions
and fully verified compact variants remain supported. Exact refill can restore
useful zero-height additions and compact original modules; reading repairs
change actual zone ownership/stacking and are checked by exact preflight.
Shared reading policy `family_reading_v4` uses primary paper-body source order in
search and Critic, with normalized roles as a legacy fallback. Abstract previews
do not move later findings ahead of their body sections. Traversal follows real
zones and stacking: columns down then across, bands top to bottom. Ordinary
central heroes and method spines participate in that sequence. Only explicit
finding-entry contracts separate a result/summary from the body, with a measured
"Key finding" title cue. Comparison branches and matrix cells remain independent.
Unknown sources/roles cannot certify order or become a synthetic final stage.
Search processes explicit narrative roles early and preserves the old
priority search when no role is classified. A dedicated beam path and bounded
exact repartition (at most 256 states
per exact candidate, before/after refill) preserve modules, claims, visuals,
geometry, pins and role constraints. Automatic unlocked candidates with a
remaining known inversion fail with `READING_ORDER_UNRESOLVED` and follow normal
family retries. Strict Validate, exact-parent recovery and explicit Improve
reading requests retain their locks; Critic still records their actual flow.
Candidate priorities and random diversity also stay inside the global whitespace
envelope of the highest-scoring exact candidate; a core preference cannot select
a substantially emptier fit when a better ordered exact fit is available.
Loop Curator titles remain complete instead of being mechanically cut to five
words; the independent one-shot route keeps its historical behavior.

Shared poster editing (`poster_editorial_v4`) prepares short complete titles,
settings/findings order, and optional labeled main/supporting entries before
loop layout search. Verified claim sentences remain unchanged; presentation
metadata records local claim IDs and prerequisites. Compact selection cannot
leave a dependent finding without its required context, including after a
same-root verified replacement. Concision must preserve important information,
clear explanation, comparisons and qualifications; filler is not a fill strategy.
Newly prepared presentations retain a verified root from each available important
research phase in the current plan. Bounded compact options include late core
claims and their required contexts, rather than depending only on claim prefixes.
The scientific bank, displayed IDs and editorial reserve are separate. Curator's
ID-only `editorial_selection_v2` contract marks required, optional and deliberately
omitted information with bounded reason codes. Missing unclassified claims remain
reserve rather than automatically reappearing as modules. Required conditions and
local prerequisites survive subset selection and verified same-root variants.
Refill/completion honor deliberate omissions; source search masks omitted source
paragraphs rather than recreating their information under a new claim ID.
Existing Campaign foundations remain immutable.

Necessity differs from usefulness: required reasons are core explanations or
indispensable conditions; useful/secondary details remain reserve. There is no
required ratio or sentence quota. A contradictory contract, or measured initial
fast-capacity failure, can receive one ID-only necessity review inside the existing
content-optimizer budget (four global/two per family rounds, with quality reserve).
The review honors Planner requirements/pins and retained research phases; it
cannot write scientific prose, change visual requirements or borrow another
attempt's board. Demotions require retained anchors in their actual current
module. Conditions scoped to `required_for_claim_ids` follow selected findings
rather than permanently locking every optional context. Curator only recovers
contexts reached from actual selections. Same-root verified
variants retain the decision; merged modules recompute supporting protection.
A shared unresolved review stops with `shared_editorial_selection_unresolved`,
without family exclusion, Critic, committed Batch budget or rejection knowledge.
Normal compaction, completion, exact fit, space and rendered-artifact gates still
apply. This does not guarantee that every family has enough capacity. All shared
family registrations inherit the path; strict locks and standalone classic keep
their existing behavior. Critic 4.3.8 uses the distinct v12 necessity rubric;
weights and the 78 admission threshold are unchanged. Authorized Batch resumes
record selection v2 without rewriting historical results.

Shared `paper_presentation_v3` derives a read-only `body_context_v1` overlay from
saved verbatim excerpts and Markdown spans. It distinguishes numbered structural
floats from body headings, resumes their enclosing body context and records unknown
or ambiguous locations without guessing page coordinates. Original evidence IDs,
source records and excerpts remain intact. Saved overlays make attempt replay
independent of a later mutable foundation.

Necessity precedes grouping. Routine data are optional unless needed to understand
the study; merely introducing data does not certify a central dataset contribution.
A principal dataset subject needs explicit grounded Planner metadata. Mixed source
modules may be divided by existing claim IDs between method and evaluation owners.
Body context/function qualify the owner first; distance only breaks ties among
compatible owners without intervening unrelated stages. Only confirmed necessary
context is mandatory after merging. Important scientific content still belongs in
prominent regions, and final structure checks reject loss of required information.

Auxiliary classification protects a compatible original-source core function,
including task definitions/objectives and substantive methods/results, before
applying setup-count hints. Curator's `primary` label alone is insufficient;
ordinary data still integrate into an appropriate owner, and genuine dataset
centrality still requires grounded Planner metadata. Verified same-root variants
retain their original scientific source. Classification reasons and protected
root IDs are recorded without scientific prose. Old unlocked preparation stamps
are recomputed; strict Validate and exact-parent fallback preserve their locks.

A genuinely unresolved shared ownership problem detected before geometry is
reported as `failure_scope=shared_content`. Explore abandons that attempt and
stops with `shared_presentation_structure_unresolved`, without excluding layout
families, calling Critic, consuming a committed Batch iteration or producing
rejection knowledge. Repeating Curator for different families cannot fix an
unchanged content-only ownership failure. User stop requests still pause normally.
Grouping-disabled contracts, pinned ownership, reading failures and failures after
geometry search retain ordinary family retries/Improve recovery. Unknown errors
remain generation failures. This does not launch or advance any Batch.

A coherent adjacent background/problem/task definition can combine even when
legacy narrative-role labels differ; substantive insights remain separate. One
optional context composition shares existing geometry/beam seats. At most two
extra exact editorial trials can restore useful original claims or group one thin
adjacent pair in its current zone. All twelve families explicitly allow grouping;
new family registration must explicitly declare `allow_module_grouping=True` or
`False`. Fixed Validate/exact-parent fallback preserve their topology and content
locks. Classic remains three unsplit, unspanned zones.

Information coverage is weighted by necessity/core status rather than sentence
count alone. Exact selection compares visible holes, terminal gaps and worst-zone
use independently of aggregate score. Shared-boundary refinement can also move
aligned column boundaries inside the existing two-round/four-candidate limit,
preserving outer body edges, gutters, hero prominence, fonts and image proportions.
Exact compilation, space guards and the same-attempt downstream rollback remain
mandatory; no filler, font reduction or invented scientific text is permitted.

One visible core module can receive a theme background through shared
`panel_ink_v1` joint selection. A bounded deterministic search preserves a visible
panel and darkens its text/accent ink when needed, checking both white and panel
backgrounds. Panel/canvas contrast defaults to a configurable 1.12 design heuristic,
separate from the unchanged 4.5 text-contrast requirement. Unsafe pairs disable
panel emphasis with an explicit reason. Renderer and color checks use actual
module backgrounds and text colors; color checks also inspect rendered color runs.

`poster_body_v1` separates internal claim functions from optional display cues.
Curator chooses plain bullets, content-specific topics, or actual procedural steps;
real supporting relationships can use 0.30-inch indents. Cues are bounded extracts
from the same verified sentence, with unsupported assertion-bearing labels rejected.
No label quota or fixed visible vocabulary applies to new presentations. Subsets,
mergers and same-root replacements recheck local cues and step numbering. Exact
measurement, cache identities and FontAgent share one paragraph description and
mixed regular/bold typography; final preflight/render checks remain mandatory.
Locked historical presentations retain their original labels and typography.

New loop foundations use direct, information-rich research prose while retaining
mechanisms, conditions, comparators, uncertainty and attribution. Old foundations
stay immutable. A bounded internal `create_style_variant` quality action can reuse
a verified prose variant or generate one, with full ClaimVerifier and a separate
source-excerpt audit requiring preserved meaning and improved expression. It may
retain length or grow by at most 15% plus 20 characters; ordinary compaction still
requires shorter text. One quality round, at most two module actions, shares the
existing global/family budget. Exact fit, content/space non-regression and the same
attempt's downstream rollback are mandatory. Verification/budget stops and remaining
wording hints stay in the report; this cannot promise a complete rewrite of old
posters. Planner cannot request arbitrary style prose or this internal operation.
`poster_editorial.enabled=false` disables optional post-fit editing, joint palette
preparation and wording repair; initial Curator preparation still applies.
Standalone generation keeps its separate behavior.

Module completion follows each current module's verified claim roots back to
paper evidence, including modules regrouped by Curator. It restores eligible
original information omitted by fitting first; deliberate editorial omissions
remain excluded. It then uses bounded verified content actions and
source retrieval. A used evidence ID can support a distinct, still-unexpressed
detail; generated text still requires full scientific and editorial verification.
Short modules are repair hints, not a minimum sentence-count admission rule.
Every module in a sparse or consecutively thin stack can enter the repair queue.

Completion first fixes geometry and module ownership in every scheduling mode,
including Explore. Internal pins and required claims are honored during fitting;
rejected repairs identify placement/content violations separately. Reduced and
consecutively thin modules receive priority over complete sparse backgrounds.
It may try one bounded
same-family geometry fallback outside locked validation. Every adopted change
must preserve visible modules/content, pass exact fit, and avoid both local and
cumulative whitespace regression. Useful additions need not increase textbox
height. Final typography/render failure or inconclusive text coverage rolls back
the completion once, restores its matching board/banks/layout, and rechecks the
baseline through normal preflight/rendering. This is not another Lineage's
storyboard. Unresolved modules and budget stops remain explicit diagnostics;
these checks do not promise that every poster is aesthetically optimal.

Lineage restoration clears both prior storyboard fields and copies only the
selected snapshot's boards. Parent selection skips snapshots without a usable
board and may use another eligible snapshot of that same Lineage. If none is
available, Improve follows its existing unavailable/recovery path before model
work; shared verified Campaign content remains intact.

Content-model repair still permits at most four rounds per global iteration,
with one round reserved from capacity work for a feasible candidate's quality
repair. Attempt-local `model_repair_budget.json` charges before blocking calls
and survives abandonment/restart; calls are never refunded. Batch scheduling
records the frozen design/budget policy and explicit legacy upgrade metadata.
Failed searches are not proofs of physical impossibility, and geometry success
is not poster admission. Reading-policy upgrades are recorded on Batch resume
without changing frozen family pools or model-repair budgets. Reading and
editorial/presentation upgrades are separately recorded. Critic 4.3.8 uses the distinct
`academic_poster_multifamily_v12_necessity` rubric so historical
scores/bases are never relabeled. Weights and the 78-point gate are unchanged;
no withdrawn module-consistency gate is reintroduced.

Each new layout attempt keeps a digest-bound `layout_input_snapshot.json` with
scientific fit inputs, configuration and font/dependency identities, excluding
model clients and credentials. Replay also refuses changed reading/editorial/presentation
policies, body/emphasis versions and source-context/selection identities, and records the palette used to select accessible emphasis.
It supports the existing read-only CPU replay:

```bash
.venv/bin/python -m src.layout.benchmark_measurements --replay-input /path/to/attempt/layout_input_snapshot.json
```

Snapshots and budget ledgers stay in the local Campaign store. Replay refuses
changed input/config/font identities and does not execute content models,
renderers or Campaign commits. Validate topology and exact-parent fallback
remain locked; Improve's explicit exclusions and retention contracts still win.

All families use LayoutSpec schema v3. The Planner assigns semantic
modules to zones and reading order; deterministic code owns final coordinates.
Raw model-generated x/y/width/height values are forbidden. Multiple Lineages
retain independent latest, best-promising, and best-accepted candidates.
Exploration
creates new Lineages, while family coverage debt, active-Lineage limits, and
least-used-family selection prevent fixation. Improve stays inside the selected
Lineage and performs bounded parent-local geometry repair. RevisionPlanner uses
one shared operation registry: layout edits are relational LayoutSpec operations
(`move_section_to_zone`, `swap_section_zones`, `set_reading_order`,
`set_primary_anchor`, and bounded `adjust_zone_budget` preferences), not legacy
left/middle/right column mutations. The Solver samples legal shared-boundary
changes and family-permitted zone splits/spans. It searches grounded
claim/visual assignments, then precisely measures and compiles near-best
candidates, restoring useful verified content or whole modules where they fit.
Every original prefix claim selection remains available, while bounded
non-prefix subsets broaden the search. A failed narrow beam retries with a
wider beam. The search keeps bounded closest-overage, largest-overage, and
most-advanced pressure samples per variant. It ranks up to two near-miss
variants across the family by assignment progress and measured overage, then
may reconsider them without only the conservative fast-estimate reserve.
Actual zone bounds, exact compilation, and preflight remain mandatory.
The selected LayoutSpec is retained through final rendering. Estimated and
compiled utilization are both recorded in `layout_feasibility_report.json`.
The loop reserves the measured LibreOffice body-line advance and uses a
body-line-sized inter-module gap; the standalone Balancer keeps its historical
measurement and spacing. Exact family scoring now considers the least-filled
zone, largest unused bottom area, original approved visual retention, and
whole-poster whitespace: unallocated body area, largest contiguous empty
rectangle, and cross-/within-zone gaps. Near-best random selection excludes
materially displaced whitespace. Explore starts with four controlled
geometry variants and can expand to twelve when the first pass is infeasible
or sparse. The report records whether that adaptive expansion ran.
When the bounded search finds no usable layout, the attempt's report records
the failure stage and reason code, variant counts, sampled section/zone fit
pressure, observed search gates, exact preflight issue IDs, and search limits.
Schema-v5 failure reports keep the displayed variant details bounded while
deriving a separate, at-most-128-item `repair_pressure_candidates` list from
every searched variant before that display limit. It contains identifiers and
measurements, not paper prose; a truncation flag prevents a sample cap from
being mistaken for proof that no repair is possible. Older reports remain
readable. Successful reports distinguish the configured fast safety factor
from the selected candidate's actual factor and search path; a near-miss
recheck can use `1.0` while the configured default remains `1.20`.
The terminal prints a concise English summary. These diagnostics describe the
attempted search, not proof that the layout family can never fit the paper;
historical failures cannot acquire details that were not recorded at the time.
In the optimization route, measured near-capacity failures, zones below 90%
utilization, large bottom gaps, or omitted important source visuals may trigger
bounded repair inside the same attempt. The loop first attempts to restore an
approved source visual to its original section, subject to exact compile,
preflight, strict Validate topology, and no visible-content or whole-poster
whitespace regression. The default visual-restoration budget is two per family
and four per global iteration. The capacity action planner requests only
allow-listed ContentOptimizer operations when
the failed search shows repairable text pressure; exact-compile or preflight
failure alone does not trigger text compaction. It
prefers existing verified content, remeasures after each verified change, and
adopts a change only if exact fit succeeds or density materially improves
without displacing blank space or losing visible content.
Defaults are two rounds per family, four across one global iteration, and two
actions per round. `content/capacity_repair_report.json` records the latest
attempt; the Campaign's unique `iterations/<N>/attempts/<attempt>/` directory
also retains its own report, including skipped repairs, so retries cannot
overwrite prior diagnoses. Retry messages show near-miss rechecks and the
repair outcome or skip reason.
Failed or abandoned attempts publish no tentative scientific memory. Strict
Validate retains the saved zone topology and normal three-attempt accounting;
the independent one-shot route does not use capacity repair.

Loop layout optimization reuses repeated text measurements in one bounded,
attempt-local context, shared by the initial fit, capacity-repair refits and
final compilation. It does not reduce geometry/beam/exact-search budgets or
relax preflight/Critic gates. Contexts are released on success or failure and
never stored as scientific or template knowledge. The classic one-shot route
is unchanged. Configuration is under `layout_performance` in
`config/critic_config.yaml`: set `enabled: false` to restore original
measurement computation on the next launch; `reuse_wrapping: false` disables
only the version-gated local fitting adapter. Its verified backend versions are
python-pptx 1.0.2 and Pillow 10.4.0; other versions use original fitting.
Per-cache entry caps and a shared 32 MiB UTF-8 text-payload budget bound retained
cache data, not the entire process RSS. Terminal layout events now distinguish
fast variants, exact candidates, visual recovery and content-optimizer repair.
`content/layout_performance_report.json` and the unique Campaign attempt copy
record text-free timings/cache counts; nested timing totals are inclusive and
must not be summed.

Read-only CPU benchmarks (no models, GPU work, rendering or Campaign writes):

```bash
.venv/bin/python -m src.layout.benchmark_measurements \
  --candidate-dir output/<paper>/<session>/iterations/000002 --sample-limit 3
.venv/bin/python -m src.layout.benchmark_measurements --replay-input /path/to/replay.json
```

The first compares saved module measurements, not the entire old iteration.
The second requires a complete JSON object with `state`, `board`, `family_id`
and `config`; it compares the pure Solver's exact outputs, retaining Improve
parent constraints and Validate fixed zones from those inputs. A partial
historical snapshot alone is insufficient to reproduce missing model-repair
intermediate states.

Loop composition refinement adds at most two rounds of four exact candidates
per fit call, preserving family topology, visible content and global whitespace.
It reuses the existing measurement context; Validate and exact-parent fallback
skip this refinement. `composition_refinement.enabled: false` disables only
the extra geometry search, not title safety or Critic spacing checks.
Capacity repair may now admit a material improvement in one zone even if the
globally worst zone is unchanged, provided no existing zone/content/global
whitespace materially regresses. Its schema-v3 audit records `fit_comparison`.
Cache on/off equivalence applies under these new rules, not to the old layout
results before the spacing correction. Extra exact candidates and occasional
one-time re-rendering have bounded but nonzero cost.

Read-only audit of a saved poster (temporary PDF rendering, no models or
Campaign writes):

```bash
.venv/bin/python -m src.layout.spacing_audit --candidate-dir /path/to/candidate
```

For a flat historical archive without its LayoutSpec, add
`--layout-spec /path/to/original/content/layout_spec.json`.

Before each retry, the runner reloads the committed Campaign-wide content
banks and restores the last committed content selection. Fresh exploration
therefore keeps the Campaign's established selection without inheriting
tentative claims from an abandoned Improve or capacity-repair attempt.

Template reuse is deliberately diverse: mixed-mode launches begin with three
template-free iterations, and the legacy strategy selector retains a 40%
template-free floor. Pure exploration remains entirely template-free.
`explore` retrieves no saved templates. Improve (`revise`) may retrieve at most
one eligible same-family, other-Lineage template after mixed-mode warmup as a
relational reference, never as an exact geometry copy. Ordinary retrieval
chooses at most one template per family, respects campaign cooldown, and gives
Planner only relational patterns rather than exact normalized coordinates.
Older loop-classic templates remain stored, but strict validation is blocked
when their rendered geometry cannot be proven to match saved topology.
New loop templates also use actual zone distributions for duplicate/seat
similarity; older column-projection signatures are kept without being mixed
into the new comparison scale.

Each accepted template has an independent, versioned structural design score
in `template.json` and the global index. The score reuses only design-related
Critic observations and deterministic topology checks; it excludes source
poster total score, scientific/content quality, and cross-paper proof. The
score still describes design observed on its source poster, not guaranteed
transferability. Missing
observations are marked partial or unscored. Existing records are backfilled from saved Critic reports where available.
Schema v8 adds evidence-only strict-validation records while preserving the v7
per-paper retry migration and never deleting accepted artifacts.

The global library offers, per layout family, up to 10 ordinary-reference
seats each for Levels 0, 1, 2, and 3 (40 maximum). Seats never borrow between
levels. Within a level, coverage, structural design score, and structural
near-duplicate suppression determine the selected representatives. All
accepted templates remain stored and in the mandatory validation queue even
without an ordinary-reference seat. Planner sees only a bounded selection
each iteration, never all 40 templates.

Level 0 is ordinary-reference eligible only on its source paper. A template
reaches Level 1 only after an accepted, strictly topology-preserving poster
on another paper; Level 1 may then be referenced by other papers with a
verified compatible profile. Levels 2 and 3 require broader distinct-paper
and profile evidence and remain subject to applicability checks. Ordinary
`adapt`/`hybridize` success cannot promote a template. Strict `validate` tasks bypass ordinary seats/cooldowns, so even an L0 or
over-cap template can be tested on a different paper. Each template-paper pair
gets at most three committed attempts: failures one and two stay retryable,
and only a third failure becomes one distinct failed-paper result. A profile is
narrowed only after two distinct papers in that profile reach final failure
without any success; a later strict success restores its eligibility. Source
replay is a one-attempt audit and never contributes cross-paper applicability.
A pure validation Batch freezes its eligible template IDs when created, so
templates saved mid-Batch wait for the next validation Batch. Missing or invalid
strict topology is reported as blocked and consumes no attempt.
A validation run locks the selected template fingerprint and topology through
commit. Success saves the generated PPTX/PNG under `validation_evidence/` as
proof, then updates only the original template's validation evidence, level,
applicability, validation status, and derived retrieval eligibility. Its layout
blueprint, fingerprint, source design score, and preview files remain unchanged.
Failure keeps the committed evaluation/task/preflight report and retry state but
does not save the poster. Validation never increments ordinary retrieval cooldown/usage,
creates a template, creates a design Lineage, changes family coverage debt, or
feeds global design feedback.

The template library is shared across campaigns. `--resume new` builds an
independent campaign foundation but retains access to eligible global
templates after mixed-mode warmup. Cooldown is campaign-scoped, so one
campaign's recent use does not block another campaign's retrieval.

- Press `Ctrl+C` once to finish and checkpoint the current iteration, persist
  the selected Batch as `PAUSED`, release the Campaign lease, and stop.
- Press it again to force-stop at the next safe agent boundary; an in-flight
  model or LibreOffice call cannot be cancelled safely. If the request arrives
  after Critic but before commit, the attempt is abandoned and its PPTX/PNG is
  removed; no Batch budget or learned knowledge is consumed. If commit has
  begun, it finishes atomically before the Batch pauses.
- Every accepted normal design candidate is archived with its own structural
  template JSON and PNG/PPTX previews. A successful strict-validation candidate
  is archived only as evidence for its source template; rejected PPTX/PNG
  candidates are removed while committed evaluation/task/preflight reports remain.

Until a database is introduced, loop memory is stored under:

```text
storage/critic_loop/
  campaigns/<campaign_id>/
    manifest.json
    campaign_state.json
    inputs/
    foundation/scientific_state.json
    memory/
      content_memory.json      # Campaign-wide verified variants/evidence
    batches/<batch_id>/
      batch_state.json       # includes committed_iteration_ids ledger
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
    iterations/<iteration>/
      COMPLETED.json
      CONTENT_MEMORY_APPLIED.json
      attempts/<attempt_id>/
        status.json
        state_snapshot.json
        critic_report.json
        outcome.json
  accepted_posters/<candidate_id>/
    poster.pptx, poster.png, critic_report.json
    template.json, template.pptx, template.png
  accepted_posters/.pending/<candidate_id>/  # unpublished before commit
  validation_evidence/.pending/<candidate_id>/  # unpublished before commit
  validation_evidence/<template_id>/<paper_id>/<candidate_id>/
    poster.pptx, poster.png, critic_report.json, task_evaluation.json
    story_board.json, styled_layout.json, provenance.json
  template_library/
    index.json
    validation_queue.json
    usage_outcomes.jsonl
  design_memory/
  loop_sessions/<session_id>/
```

The twelve initial layout skeletons are committed as editable PPTX and PNG
pairs under `resource/layout_families/`. Regenerate them after editing the
family registry with `.venv/bin/python -m src.templates.preview`. These are
schematic starting structures, not pre-rated posters. Accepted-template
previews show actual generic module/visual positions without copying scientific
text or figure pixels. The current 78-point admission score is unchanged;
Critic additionally reports a presentation-only score and a high-potential
label for later threshold calibration, not a second save gate.

The WebUI enables resumable Batch mode by default, accepts a Batch budget,
displays Batch/Portfolio/family/Lineage state, and exposes pause, resume,
graceful stop, and force-stop controls plus the latest accepted preview.
It also exposes `latest`, `required`, and `new` resume modes plus an exact
Campaign ID. Loading it shows every persisted Batch with mode, status, progress,
target Lineage, and knowledge watermarks. Batches can be selected, archived, or
unarchived as their state permits; full state and terminal reports are available
without running a model.

### Web Interface

> Developed by: React + TypeScript + Vite

Upload your PDF paper and logos through drag-and-drop, configure models and dimensions, then generate and download your poster files.

**Prerequisites:**
- Node.js installed
- Main PosterGen dependencies installed (from project root)
- API keys configured in `.env` file

```bash
# Install main project dependencies (if not done already, refer to Environment Setup above)

# Start backend
cd webui && python start_backend.py

# Start frontend (in new terminal, from project root)
cd webui && sh ./start_frontend.sh

# Open http://localhost:3000 in your browser
```

![webui](./resource/webui-start.png)

![webui](./resource/webui-finish.png)

## Output Structure

After successful generation, you'll find your results in the `output/` folder:

```
output/
└── <paper_name>/
    └── <YYYYMMDD_HHMMSS_microseconds>/
        ├── <paper_name>.png           # final poster image
        ├── <paper_name>.pptx          # editable PowerPoint file
        ├── run.log                    # complete stdout/stderr for this run
        ├── timing_cost_log.json       # runtime & api cost log
        ├── assets/                    # extracted content from paper via Marker
        │   ├── figures.json           # figure metadata with aspect ratios
        │   ├── tables.json            # table metadata with aspect ratios
        │   ├── figure-*.png           # individual figures from paper
        │   ├── table-*.png            # individual tables from paper
        │   └── fig_tab_caption_mapping.json  # caption mappings
        └── content/                   # multi-agent artifacts
            ├── raw.md                         # raw text extraction
            ├── structured_sections.json      # organized sections
            ├── classified_visuals.json       # categorized visuals
            ├── visual_classification_report.json # role normalization provenance
            ├── narrative_content.json        # paper summary
            ├── story_board.json              # content organization
            ├── visual_curation_report.json   # selected/omitted source visuals
            ├── initial_layout_data.json      # initial layout
            ├── column_analysis.json          # column usage stats
            ├── optimized_story_board.json    # balanced content
            ├── balancer_decisions.json       # optimization details
            ├── final_column_analysis.json    # final usage metrics
            ├── optimized_layout.json         # balanced layout
            ├── final_design_layout.json      # element coordinates
            ├── color_scheme.json             # resolved color palette
            ├── color_provenance.json         # source and Critic preset variant
            ├── critic_report.json            # v3 nested evaluation and issues
            ├── revision_plan.json            # sanitized repair operations
            ├── revision_execution_report.json # per-operation execution audit
            ├── layout_performance_report.json # loop-only timing/cache diagnostics
            ├── section_title_design.json     # title styling
            ├── keywords.json                  # highlighted terms
            ├── styled_layout.json            # formatted text
            └── styling_interfaces.json       # typography settings
```

## 🤖 Multi-Agent Pipeline

The local fork uses a grounded scientific pipeline rather than the older
six-agent architecture:

1. **Parser** extracts the paper and visual assets.
2. **Evidence Builder** creates source-traceable atomic evidence.
3. **Narrative Planner** assigns evidence to poster sections.
4. **Claim Writer** writes evidence-linked poster claims.
5. **Claim Verifier** fail-closes unsupported claims and numbers.
6. **Grounded Curator** arranges verified claim IDs and approved visuals.
7. **Design agents** choose color, titles, layout, balance, and typography.
8. **Renderer** exports an editable PPTX and PNG preview.
9. **Critic** evaluates the exact artifacts and returns actionable issues.

Visual classification is paper-semantic, not a left/middle/right placement
decision. It receives visual IDs, captions, types, and aspect ratios (not image
pixels), assigns each visual to exactly one scientific role, and optionally
selects a key visual. Invalid/omitted model IDs are normalized and audited in
`visual_classification_report.json`. In the optimization route, Grounded Curator
selects verified claims and relevant visual IDs without choosing columns; the
layout-family solver makes the spatial assignment. The independent one-shot
classic route still uses its three-column Curator/Balancer path.

The optimization route uses `critical_visuals_v1`: NarrativePlanner and Curator
account for all paper figures/tables in their existing calls, marking required,
optional and omitted assets with paper evidence and source-section IDs. Every
indispensable method/result/comparison visual is required; a valid classified
key visual is always required. Missing decisions remain unresolved. Requirements
are independent of layout capacity, frozen across family retries, and recovered
only from committed Campaign snapshots; Lineage restore cannot downgrade them.
Old scientific foundations remain immutable: Curator can establish the new
contract outside the foundation on the next authorized exploration.

All twelve layout families and future shared-interface registrations must retain
required assets from initial fitting through final rendering. Capacity failure
may change optional text or legal geometry, or retry a family within existing
budgets; it cannot silently publish an all-text substitute. Classic keeps three
unsplit/unspanned regions. Strict Validate and exact fallback retain their locks.
Standalone classic keeps its existing behavior.

Actual PPTX image identities, occurrences, crop, aspect, bounds, size and DPI are
checked against the source contract. The existing RenderFit PDF export confirms
painted image positions; audit evidence binds the candidate and PPTX/PNG hashes.
Conservative size floors are configurable in `critical_visuals`; they do not
prove axis/legend legibility. The existing vision Critic must explicitly confirm
each required visual is readable. Missing or unconfirmed evidence blocks
admission regardless of the total score. A reviewed image-free paper receives
an inapplicable asset score, not an automatic 100. Critic is 4.3.8 with rubric
`academic_poster_multifamily_v12_necessity`; overall weights and the 78-point gate
remain unchanged, and historical scores/artifacts are never rewritten.

Diagnostics include `visual_requirements.json`, `visual_requirement_report.json`
and `render_visual_report.json`, alongside the existing curation/fit reports.
Unresolved shared requirements or unavailable rendering proof stop once without
excluding families, spending a committed iteration, or learning a rejection.
Batch policy upgrades occur only on an authorized resume; development itself
does not launch or resume a Batch.

Batch optimization freezes the scientific foundation and repeats:

```text
Frozen verified paper state
  -> Portfolio task and LayoutFamily selection
  -> GroundedCurator or RevisionPlanner
  -> GroundedContentOptimizer (Improve revisions and bounded capacity repair)
  -> design agents
  -> Renderer
  -> Critic
  -> archive/template memory or grounded feedback
```

## Key Features

- **Professional Layout**: CSS-like precision positioning with proper spacing
- **Intelligent Balancing**: Automatic column optimization prevents overflow
- **Color Harmony**: Automatic color scheme generation from your institution branding
- **Typography Excellence**: Professional font choices and keyword highlighting
- **Flexible Output**: Both PNG images and editable PowerPoint files
- **Academic Standards**: Follows poster design best practices for conferences

## Other Configurations

The system supports customization through `config/poster_config.yaml`. You can adjust:

- Layout parameters (margins, padding, spacing)
- Typography settings (fonts, sizes, line spacing)
- Color generation algorithms
- Visual asset sizing constraints
- Content optimization thresholds

**Custom Fonts:**
If you would like to use other fonts, you can add the font files under `fonts/`, modify the `get_font_file_path()` mapping in `src/layout/text_height_measurement.py`, and adjust the 'typography' in `config/poster_config.yaml`.

## 📊 Example Results

Our system generates professional academic posters with high visual quality. Here are some examples of generated posters:

![Example 1](./resource/neural-encoding.png)

![Example 2](./resource/active-geo.png)

## Local Development Documentation

In this development workspace, `AGENTS.md` holds the current architecture,
constraints and concise change history. Detailed topic reports are grouped in
`docs/reports/`; update an existing report instead of creating one per change.
These local Markdown files are Git-ignored and are not included in a fresh clone.

## Citation
```
@inproceedings{zhang2026postergen,
  title={PosterGen: Aesthetic-Aware Multi-Modal Paper-to-Poster Generation Via Multi-Agent LLMs},
  author={Zhang, Zhilin and Zhang, Xiang and Wei, Jiaqi and Xu, Yiwei and You, Chenyu},
  booktitle={Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition},
  pages={9813--9823},
  year={2026}
}
```

## Acknowledgments

This codebase is built upon following open-source projects. We express our sincere gratitude to:

- **[LangGraph](https://github.com/langchain-ai/langgraph)**: Multi-agent workflow framework;
- **[Marker](https://github.com/datalab-to/marker)**: High-quality PDF parsing library that enables accurate content extraction from research papers.
- **[python-pptx](https://github.com/scanny/python-pptx)**: Python library for creating PowerPoint (.PPTX) poster files.

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=Y-Research-SBU/PosterGen&type=Date)](https://www.star-history.com/#Y-Research-SBU/PosterGen&Date)
