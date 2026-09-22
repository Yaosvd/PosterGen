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
foundation schema, and layout-engine schema. Use `--resume new` for an independent campaign, or
`--resume required --campaign_id <id>` to require one exact campaign.

A campaign can span many process launches. An iteration is complete only when
its campaign-level `COMPLETED.json` exists. If iteration 31 was committed and
iteration 32 was interrupted, the next launch retries iteration 32 as a new
attempt. If 32 was committed before stopping, the next launch starts at 33.
An interrupted Batch resumes its remaining budget and its **frozen scheduling
mode**. After a completed Batch, the next launch creates the next Batch.
Omit `--mode` to retain an active Batch mode, or to use `mixed` for a new
Batch. Explicitly changing the mode of an unfinished Batch is rejected.

Choose `--mode explore` for template-free new routes, `--mode improve` for
Critic-directed revisions of existing Lineages, `--mode mutate` for child
Lineages in a different layout family, or `--mode validate` for pending
template validation only. `--target-lineage-id <id>` can narrow a pure improve
or mutate Batch. Improve/mutate require an existing Lineage; validation stops
as `EXHAUSTED` when eligible tasks run out, even before 100 evaluations. No
pure mode silently falls back to exploration. The WebUI exposes the same Batch
mode and optional target Lineage. A fresh pure validate Batch may therefore
finish without a poster when no task is eligible.

Campaign, Batch, Session, Iteration, and Attempt are distinct: a Campaign is
the long-lived paper optimization project; a Batch is a finite budget; a
Session is one process launch; an Iteration is one committed candidate
evaluation; and an Attempt is one execution try that consumes no budget until
it is committed.

Each iteration runs Planner -> Coder -> Critic. A persistent PortfolioScheduler
targets 30% new exploration, 40% existing-Lineage improvement, 12% structural
mutation, and 18% template validation across **mixed-mode** Campaign history.
Pure-mode iterations are counted separately and cannot distort these quotas. Rejected candidates feed the
full structured issue report into RevisionPlanner and then
GroundedContentOptimizer. The Critic measures each module against an independent
height budget; 95%-100% is the ideal utilization band, but the optimizer must
use useful paper-grounded content rather than filler. Non-classic families are
measured against their LayoutSpec zones rather than being projected back into
left/middle/right columns.

Design knowledge is shared globally across Campaigns in
`storage/critic_loop/design_memory/global_knowledge/events/`. Only committed
Critic outcomes contribute: rubric/profile/family, numeric scores, approved
issue categories and operations, and conservative same-rubric repair
associations. No paper prose, claim text, exact coordinates, or poster assets
are copied into this store. The Planner receives a bounded, non-binding
summary for the current family; global templates remain a separate library.
After a crash, committed events missing from this store are replayed
idempotently from `COMPLETED.json`. Template validation usage is also applied
only after the same commit marker, then checkpointed with
`TEMPLATE_USAGE_APPLIED.json`; restart fills any gap before choosing new
validation work. Every Critic-accepted poster now creates exactly one
paper-free template JSON and editable PNG/PPTX preview. Similarity and the
per-family level seats suppress only Planner retrieval, not storage or validation;
pure exploration remains template-free.

The CLI now shows a live progress panel on interactive terminals and a
chronological English event stream on redirected terminals. It reports Campaign
and Batch creation/resume, committed Batch progress (for example 31/100),
global iteration and attempt numbers, mode/family/Lineage/template selection,
agent-stage starts and elapsed times, Critic decisions and issue IDs, accepted
poster archives, saved templates and preview paths, strict-transfer validation
pass/fail with resulting level/status, and the final
Batch status. A stage running over one minute produces periodic heartbeat lines
when output is redirected. These events are informational; only
`campaigns/<campaign_id>/iterations/<N>/COMPLETED.json` consumes a Batch slot.

The launch output's `run.log` contains plain event lines and agent messages.
On raised exceptions, the terminal gives the stage and short message, while
`run.log` contains the full traceback; errors returned by agents show their
reported message. A compact machine-readable copy is written to
`storage/critic_loop/loop_sessions/<session_id>/progress_events.jsonl`.
The CLI exits nonzero for `FAILED_REQUIRES_USER` or `UNAVAILABLE`;
`EXHAUSTED` is a normal end for a pure validation Batch.


#### Critic v4 evaluation and repair contract

Critic v4 (`academic_poster_multifamily_v2`) separates hard validity gates from
quality scores. Rendered-artifact validity, scientific grounding, geometry,
minimum typography, region capacity, module fit, layout-family contracts, color
contrast, approved visual assets, and the required multimodal pass can reject a
candidate, but artifact existence itself does not inflate a layout score.

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

Poster layout is no longer restricted to three columns. Twelve controlled
families are enabled initially: classic three column, asymmetric two column,
four-column modular, central hero with side rails, top hero with bottom grid,
horizontal narrative bands, method flow spine, comparison split, result
dashboard cards, small-multiples matrix, timeline/stage narrative, and modular
editorial mosaic. The classic three-column family remains available.

All families use one versioned LayoutSpec grammar. The planner assigns semantic
modules to zones and reading order; deterministic code owns final coordinates.
Raw model-generated x/y/width/height values are forbidden. Multiple Lineages
retain independent latest and best candidates. Structural mutation creates a
child without overwriting its parent, while family coverage debt, cooldown,
active-Lineage limits, and least-used-family selection prevent fixation.

Template reuse is deliberately diverse: mixed-mode launches begin with three
template-free iterations, and the legacy strategy selector retains a 40%
template-free floor. Pure exploration remains entirely template-free.
`explore`, `revise`, and `mutate` retrieve no templates. Ordinary retrieval
chooses at most one template per family, respects campaign cooldown, and gives
Planner only relational patterns rather than exact normalized coordinates.

Each accepted template has an independent, versioned structural design score
in `template.json` and the global index. The score reuses only design-related
Critic observations and deterministic topology checks; it excludes source
poster total score, scientific/content quality, and cross-paper proof. The
score still describes design observed on its source poster, not guaranteed
transferability. Missing
observations are marked partial or unscored. Existing v5 records are
backfilled from saved Critic reports where available and migrated to v6
without deleting accepted artifacts.

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
`adapt`/`hybridize` success cannot promote a template. Strict `validate`
tasks bypass ordinary seats/cooldowns, so even an L0 or over-cap template can
be tested on a different paper. Failed transfers narrow observed
applicability but never delete the successful source template; a later
strictly verified success restores that profile's eligibility.

The template library is shared across campaigns. `--resume new` builds an
independent campaign foundation but retains access to eligible global
templates after mixed-mode warmup. Cooldown is campaign-scoped, so one
campaign's recent use does not block another campaign's retrieval.

- Press `Ctrl+C` once to finish and checkpoint the current iteration, then stop.
- Press it again to force-stop at the next safe agent boundary; an in-flight
  model or LibreOffice call cannot be cancelled safely.
- Every accepted candidate is archived together with its own structural
  template JSON and PNG/PPTX previews. Rejected PPTX/PNG candidates are removed
  while their Critic reports and repair suggestions are retained.

Until a database is introduced, loop memory is stored under:

```text
storage/critic_loop/
  campaigns/<campaign_id>/
    manifest.json
    campaign_state.json
    inputs/
    foundation/scientific_state.json
    batches/<batch_id>/
      batch_state.json
      batch_report.json
    lineages/<lineage_id>/
      lineage_state.json
      latest_state.json
      best_state.json
      best_state_<rubric_version>.json
    sessions/<session_id>/session_state.json
    iterations/<iteration>/
      COMPLETED.json
      attempts/<attempt_id>/
        status.json
        state_snapshot.json
        critic_report.json
        outcome.json
  accepted_posters/<candidate_id>/
    poster.pptx, poster.png, critic_report.json
    template.json, template.pptx, template.png
  accepted_posters/.pending/<candidate_id>/  # unpublished before commit
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
It also exposes `latest`, `required`, and `new` resume modes plus an optional
campaign ID.

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
            ├── narrative_content.json        # paper summary
            ├── story_board.json              # content organization
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

Batch optimization freezes the scientific foundation and repeats:

```text
Frozen verified paper state
  -> Portfolio task and LayoutFamily selection
  -> GroundedCurator or RevisionPlanner
  -> GroundedContentOptimizer (revisions only)
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
