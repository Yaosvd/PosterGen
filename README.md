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

Parser runs once per run, freezing original text, continuous sections, metadata and
visual assets. Rubrics has no EvidenceBuilder stage, evidence-ID permission list or
precomputed atomic fact bank. Every sample independently plans its research story,
then freezes exactly **one layout family** using coverage-first selection and the
current paper profile. Scores and previous sample prose never affect that choice.

SourceCurator jointly writes the whole poster, chooses its module count, titles,
lead/support explanation and original figures/tables from the complete continuous
paper sections. Story obligations protect a few indispensable meanings and their
conditions; they do not enumerate everything the author may write. A source-backed
mechanism remains usable even if an old evidence extractor never selected it.
Original-source IDs and verbatim quotes are locator hints, checked after writing.

All fifteen layout families remain peers. Their registered geometry generators,
legal split/span/mirror variants, measured search, exact compilation, spacing,
Preflight and RenderFit remain shared. Three or four columns are physical regions,
not fixed module counts. Models supply relational intentions, never arbitrary
coordinates or invented comparisons/stages. An unsuitable composition can fail
within its bounded search; no fixed three-column fallback or filler is inserted.

SourceBalancer edits the whole candidate against original sections and the actual
layout's dimensions, overflow, whitespace and rendered draft preview. It can rewrite,
expand, shorten, split, merge, add or remove optional display content while preserving
indispensable meaning, conditions, comparison basis and qualifiers. The sample-wide
ledger still permits at most **three capacity/structure rounds plus one quality round**;
each round affects at most two old and two new modules. Unchanged neighbors stay exact.
Optional same-module reserve visuals, including the existing role-based key-visual
offer, use a separate finite probe ledger. No image quota or new image-association
judge is introduced. Trials and rejected edits remain diagnostic artifacts.

Natural reading is judged from actual previews inside existing Balancer opportunities,
then independently from the final PNG inside the existing visual Critic request.
Top-to-bottom and left-to-right are peer axes: column-major, row-major, mixed and
parallel routes can all be appropriate. Rubrics no longer forces source/role sorting,
reading-specific reassignment or old deterministic reading-order rejection. Schema,
module IDs and candidate/image/text/geometry/style binding are checked in code;
physical containment, non-overlap and source truth remain mandatory. A review of an
old preview cannot certify an edited image. Unreviewed/ambiguous scope stays explicit,
and no free extra judge round or publication filter is added.

Direct original-source verification checks every visible scientific expression,
assertion-bearing title/label and formula in full module and whole-poster context.
It requires exact candidate-text coverage, true original supporting quotes,
entities/numbers/units/conditions/comparators, supported relationships, preserved
necessary information and complete indispensable-meaning verdicts. Multiple original
passages can support synthesis; paper wording need not be copied. Scientific rejection,
insufficient source, malformed output and request failures remain distinct. A single
sample-wide format correction allowance is shared across source stages; scientific
rejection does not unlock a free retry. Raw responses precede validation; charged
missing responses refuse automatic resubmission.

Actual selected visual context is checked with the prose, then refitted at the adopted
geometry and ownership. Science, precise visible text and one coherent feasible layout
freeze together. Styling compiles this candidate without another family search;
final Preflight, rendering and publication recheck the scientific snapshot. Styled
scientific text/titles cannot silently differ from the verified version. Draft previews
are actual editable PPTX/PNG diagnostics, explicitly ineligible for publication.

The generator is `explore_samples_v10`, preparation `sample_source_science_v1`, body
`sample_body_source_v1`; dataset/storage remain `rubrics_samples_v2` / schema 2.
Source-based evaluation has its own rubric `academic_poster_source_editorial_v1`.
Historical results remain readable and unchanged; old runs cannot resume under new
identities. `--paper-cache-run-id` accepts only strictly compatible original-source
foundations, never old EvidenceBuilder caches or another sample's science/prose.
Copied original assets are local to the new foundation. Standalone classic keeps its
independent Parser/EvidenceBuilder/Planner/Writer/Verifier/Curator and Balancer path.

Automatic semantic judgments are fallible. Offline protocol/layout tests establish
engineering behavior, not real-model scientific accuracy or upstream-level writing
and aesthetics. Real-paper content comparison and PNG/PPTX inspection remain necessary.

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

Only the final outcome of each task is an official sample outcome. Every actual
internal render is retained in its own version directory with PNG/PPTX, its inspection
template and geometry/provenance; correction renders never overwrite an earlier poster.
These internal versions are diagnostics, not independent mining samples. A normal
content/fit failure produces a detailed report and advances to the next sample task,
without another family. Programming, authentication, service and storage failures
stop the run. No-poster failures have no score and are not low-score posters.
`--samples` counts tasks, including failures, not guaranteed successful posters.

One Ctrl+C finishes the current sample and pauses. A second Ctrl+C force-stops at the
next safe agent boundary; blocking model/render calls must return first. Interrupted
attempt diagnostics and durable repair charges remain. Completed samples are immutable;
resume verifies their bundles and never reruns completed samples.
When interrupted during preparation, resume reuses completed scientific stages;
unfinished stage work is charged separately from the existing layout repair budget.
Preparation failures retain diagnostics and publish no poster or score. Ordinary
sample-output failures continue to the next task; system/integrity failures stop the run.

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

Global sample writing normally uses two or three concise entries per module and
a size/font/space-aware word reference. Pictures, headings and spacing count toward
its provisional space allocation. These references never truncate text or override
indispensable scientific information; full source evidence remains available.

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

1. **Parser + original-section index** preserve paper text, metadata and visual assets.
2. **SourceNarrativePlanner** builds each sample's story and indispensable meanings.
3. **Family selection** freezes one of fifteen peer families using planned coverage.
4. **SourceCurator** writes complete prose, dynamic modules and visual organization jointly.
5. **SourceBalancer + direct SourceVerifier** edit actual-layout drafts within the existing
   finite budget, judge natural reading from previews, verify original support and refit.
6. **Design agents** style and compile the frozen candidate, then check geometry and exact text.
7. **Renderer** exports editable PPTX and PNG; RenderFit checks actual editable glyph fit.
8. **Critic** evaluates the final artifacts and their natural reading; all rendered outcomes
   are stored regardless of score. Classic retains its independent original graph.

Visual classification remains paper-semantic and caption-based, never a poster-column
assignment. Original source units, mutable display-module IDs, indispensable meanings
and post-writing support records have separate identities. Splits/merges retain an
explicit local candidate history. No cross-sample content, templates or feedback are
retrieved. The sample Parser skips legacy ABT summarization; classic keeps it.

```text
Frozen original paper sections + visual assets
  -> independent source story / freeze ONE peer family
  -> whole-poster SourceCurator with dynamic modules
  -> bounded actual-layout fit / draft previews / SourceBalancer
  -> direct original verification / actual-text refit
  -> freeze coherent source proof, text and layout
  -> ColorAgent / SectionTitleDesigner / compile adopted layout
  -> FontAgent / Preflight / Renderer / RenderFit
  -> existing Critic including final-image natural reading
  -> save poster + its inspection-only layout template
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
      content_edit_budget.json  # sample-wide 3 capacity + 1 quality allowance
      preparation/           # Planner, Curator, space, Writer, joint checkpoints
        joint/               # draft/fit inputs, edits, verification, READY
        content/joint_writing/ # one global Writer raw response and normalized body
        content/sample_module_plan.json
        content/verified_module_board.json
        sample_science.json
        READY.json           # verified science bound to this paper/run/sample/seed
      family_assignment.json
      attempts/<attempt_id>/  # styling, final compilation and diagnostics
        work/renders/render_<n>/ # each actual PNG/PPTX + its inspection template
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
never automatically scanned for samples. New outcomes also record their generation
policy version, so future mining can explicitly select the intended generation cohort.

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
