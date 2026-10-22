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
Use the separate command below to generate independent samples across layout families.

### Independent Explore samples for Rubrics research

The second path generates independent poster samples using fifteen layout families in one shared pool.
It uses the Explore generator as the generation foundation for a future Rubrics iteration
framework. Automatic Rubrics mining, clustering, semantic deduplication and library
updates are not implemented yet.

```bash
python -m src.workflow.critic_pipeline \
  --paper_path ./data/Your_Paper_Name/paper.pdf \
  --text_model local-text --vision_model local-vision \
  --samples 100 --random_seed 31
```

Omitting `--run-id` always creates a new sample run. Resume one new-format run with
its exact ID and the same paper, logos, models and dimensions:

```bash
python -m src.workflow.critic_pipeline \
  --paper_path ./data/Your_Paper_Name/paper.pdf \
  --text_model local-text --vision_model local-vision \
  --run-id run_EXACT_ID
```

Sample count, seed, generation settings and evaluation settings are frozen on resume.
A different configuration fails explicitly. Old `--mode`, `--iterations`, Campaign
and Batch arguments are retired; old runs are never resumed or migrated by this path.
The CLI keeps its existing width normalization to 54 inches; WebUI dimensions remain
direct inputs.

Parser and Evidence Builder run once per run, freezing the original paper material,
metadata, visual assets and source-linked evidence. Each independent sample then runs
its own Narrative Planner, module-planning Curator, module Claim Writer and Claim
Verifier, in that order. Writer sees the global story and neighboring module tasks,
and writes connected display expressions rather than a bank of isolated bullets.
Verifier checks every clause of the exact visible wording and records complete
text-to-evidence coverage. Indispensable assertions require an explicit full-coverage
verdict separately from citation use. Corrections/rejections receive at most one
affected-module final-context recheck. Completed preparation stages have digest-bound checkpoints;
verified module prose and its original scientific sources are frozen before design.
Family retries reuse that sample's preparation and start with fresh display/design
state and empty variant banks, copying its immutable Curator content plan. Other
samples' prose, modules, repairs, scores, templates and feedback are never inputs. Planning, writing and verification now incur work per
sample rather than once per run.

Compatible paper preparation can be explicitly reused with `--paper-cache-run-id
<run_id>`. This validates original input/model/extraction identities and all source
asset hashes, copies only paper fields/assets, and always reruns new sample science.
Changed extraction code refuses reuse; old caches are not silently upgraded.
Sample evidence extraction skips explicit References/Bibliography/Acknowledgments
headings while retaining research appendices. Same-sample family retries reuse color.
These changes do not promise a fixed speedup or matching upstream example quality.

The run freezes sample slots, seeds and selection rules first. After each sample's
science is ready, its family assignment is frozen using that sample's profile and
this run's planned family counts. Coverage-first bounded semantic preference remains;
scores and family retry outcomes cannot change subsequent planned coverage.
Ordinary family retries reuse the current sample's Curator plan without another
Curator request. One targeted content-plan revision is permitted only for diagnosed
shared structure failure, with a separate durable maximum-one budget. It does not
consume the four content-repair rounds or their quality reserve. It preserves
protected information and local prerequisite groups and their dependency records.
Title-only, reserve-only and otherwise structurally unchanged revisions are rejected;
a failed family height search alone does not trigger re-curation. Spent visual-restoration allowances remain charged.
Each plan version can search the frozen family pool; at most two plan versions
are allowed. Exhausted repair budgets leave only bounded geometry search.
The current generator is `explore_samples_v4`, with `rubrics_samples_v2` storage,
`sample_science_v2` preparation and `sample_body_v2` prose. Earlier sample runs
remain readable but cannot resume under changed generation identities; use their matching code or
start a new run. Historical records are never silently upgraded.

All fifteen families are peers: there are no priority tiers or separate eligibility
pools. Coverage takes precedence; the same bounded paper-matching preference applies
within the least-used group. The three added families are `framed_multicolumn`
(shared opening, two/three body columns, shared conclusion), `narrative_evidence_grid`
(narrative rail, local evidence grid, shared conclusion), and `central_evidence_band`
(upper columns, a full-width middle evidence region, lower columns). Their bounded
geometry generators and spanning-band/column reading traversal use the shared
fitting, verification, repair, Preflight, RenderFit and local template-export path.

The existing bounded geometry/content beam search, near-miss checks, exact compilation,
module completion, optional source-key-visual candidates/restoration, verified
compaction/style repair, measurement reuse, shared-boundary
refinement, final typography preflight, RenderFit and same-attempt rollback remain.
Written modules keep their explanatory sequence and are not automatically accumulated
into a giant auxiliary owner. Bounded exact same-source thin-module grouping remains.
Failures record grouping, per-module loads and deduplicated pressure. Completion
prioritizes missing information, then larger gaps/poorer use with fair module turns.
Classic within this path still has three unsplit/unspanned regions and uses the Solver.
The standalone classic command continues to use the original Balancer.

Every final rendered poster is saved regardless of its score or reference-policy result.
Each poster directory contains `poster.png`, editable `poster.pptx`, `template.json`,
`template.png`, editable `template.pptx`, `evaluation.json`, provenance and diagnostics.
Templates describe that poster's actual compiled geometry and contain generic preview
labels. They are inspection artifacts only: no registration, retrieval, promotion,
seats, cooldown, transfer validation or cross-poster reference exists.

All new posters initially share `storage/rubrics_samples/posters/` and are marked
`unclassified`. A user-selected score threshold and high/low grouping will be added
later. The baseline Critic retains its seven dimension weights and 78-point reference,
but that reference never controls saving and is not a high/low grouping threshold.
Scoring-profile identity is separate from the future generation-Rubrics snapshot
(currently null). Failed or incomplete evaluation has no sample score, rather than an
invented zero.

Only the final result of each sample is an official sample. Internal fit retries and
correction previews stay in attempt diagnostics. A failed generation is recorded without
pretending to have produced a poster. Known fit failures have bounded family retries;
genuine shared pregeometry content failures stop once, and programming exceptions stop
the run without being treated as poster-quality failures. The planned task count includes
failed terminal tasks, so failures cannot cause unbounded sample generation.

One Ctrl+C finishes the current sample and pauses. A second Ctrl+C force-stops at the
next safe agent boundary; blocking model/render calls must return first. Interrupted
attempt diagnostics and durable repair charges remain. Completed samples are immutable;
resume verifies their bundles and never reruns completed samples.
When interrupted during preparation, resume reuses completed scientific stages;
unfinished stage work is charged separately from the existing layout repair budget.
Preparation failures retain their diagnostics, publish no poster or score, and stop
the run before layout selection or evaluation.

Historical posters, templates, Campaigns and knowledge under `storage/critic_loop/`
and historical `output/` remain untouched. They are excluded from the new dataset and
are not inputs to future Rubrics mining through this path.

Model-free checks:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m src.layout.benchmark_measurements --replay-input /path/to/layout_input_snapshot.json
.venv/bin/python -m src.layout.spacing_audit --candidate-dir /path/to/saved/candidate
.venv/bin/python -m src.layout.family_previews
```

`config/exploration_config.yaml` controls the default sample count and new storage root.
`config/critic_config.yaml` retains baseline evaluation and shared fitting settings.
The withdrawn post-bab9907 critical-visual and necessity-v2 experiments remain absent.

Sample writing uses soft starting references (normally 2-5 candidate claims per
research unit and 2-4 visible claims per display module). A size/font-aware visible
word-range hint leaves room for figures, headings and paragraph spacing; none of
these references is a truncation or admission limit. Essential science may exceed
them, and the full evidence/candidate banks remain available.

Independent samples use a 900-second response timeout and a 15-second connection
timeout for OpenAI-compatible services. SDK retries are disabled. One explicit
retry is allowed only for identified temporary connection/service failures;
read timeouts and truncated outputs do not replay the request. Classic retains
its legacy request policy. Per-request start/end/failure/retry records are saved
in `model_requests.jsonl` under the active paper/preparation/attempt directory,
without scientific prompts, credentials or endpoint values. The timing report's
`model_request_attempts` separates physical requests from logical API-call counts.


### Web Interface

> Developed by: React + TypeScript + Vite

Upload your PDF paper and logos, choose independent Explore samples or a single classic poster, and configure models and dimensions. Sample generation shows every saved result and links its poster, local layout template and evaluation. Use a run ID to resume a stopped sample run; old Batch controls are retired.

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

The single classic route keeps its existing timestamped `output/` directory:

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
            ├── critic_report.json            # evaluation and issues
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
3. **Narrative Planner** organizes scientific research-content units and priorities.
4. **Sample Curator** plans coherent display modules, titles, evidence and approved visuals.
5. **Claim Writer** writes each module as a whole, retaining evidence and all source-unit IDs.
6. **Claim Verifier** checks actual display prose, every supported span, numbers and relationships.
   The independent classic graph retains its existing Planner → Writer → Verifier → Curator order.
7. **Design agents** choose color, titles, layout, balance, and typography.
8. **Renderer** exports an editable PPTX and PNG preview.
9. **Critic** evaluates the exact artifacts and returns actionable issues.

Visual classification is paper-semantic, not a left/middle/right placement
decision. It receives visual IDs, captions, types, and aspect ratios (not image
pixels), assigns each visual to exactly one scientific role, and optionally
selects a key visual. Invalid/omitted model IDs are normalized and audited in
`visual_classification_report.json`. In the optimization route, Grounded Curator
plans display tasks and relevant visual IDs before writing, without choosing columns; the
layout-family solver makes the spatial assignment. The independent one-shot
classic route still uses its three-column Curator/Balancer path. A classified
key visual may be offered as an optional candidate to a matching verified
module, but neither Curator nor Critic forces its placement. The Curator's
selection audit is saved in `visual_curation_report.json`, and Critic records
available, curated, and finally visible visual IDs without changing its score
or acceptance gates. New sample runs freeze paper evidence and per-sample verified
science separately; they never import historical Campaign data.

On the sample route, Planner research-unit IDs and Curator display-module IDs have
separate meanings. A display module may group compatible units while retaining its
original claim, evidence and paper-section provenance. Existing bounded content repairs
remain scientifically verified and local to the current attempt. Critic content checks
and source-chunk recovery follow original claim roots rather than assuming equal IDs.
The sample Parser omits its old And/But/Therefore summary call while preserving exact
title/authors metadata and visual classification. The standalone classic route retains
that call and its original Planner/Writer prompts.

Independent sample generation repeats:

```text
Frozen paper material + evidence
  -> sample NarrativePlanner / module Curator / module ClaimWriter / ClaimVerifier
  -> freeze verified module prose + profile-based family assignment
  -> install this sample’s verified content plan (no additional initial Curator call)
  -> ColorAgent / SectionTitleDesigner
  -> family Solver and bounded current-sample repairs
  -> FontAgent / Preflight / Renderer / RenderFit
  -> baseline Critic
  -> save final poster + its inspection-only layout template
```

New sample storage:

```text
storage/rubrics_samples/
  runs/<run_id>/
    manifest.json
    run_state.json
    sample_plan.json
    inputs/
    paper_foundation/paper_state.json
    paper_foundation/identity.json
    samples/<sample_id>/
      preparation/           # research/module planning, writing, verification checkpoints
        content/sample_module_plan.json
        content/verified_module_board.json
        sample_science.json
        READY.json           # verified science bound to this paper/run/sample/seed
      family_assignment.json
      attempts/<attempt_id>/  # work, fit inputs, repair ledger and diagnostics
      FINALIZED.json
  posters/<poster_id>/
    poster.png
    poster.pptx
    template.json
    template.png
    template.pptx
    evaluation.json
    provenance.json
    diagnostics/
    bundle.json
```

Poster identifiers are stable and results retain their grouping field for later threshold
classification. The new run manifest is the dataset boundary; historical directories are
never automatically scanned for samples.

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
