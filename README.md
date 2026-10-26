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

Parser and Evidence Builder run once per run, freezing original paper text,
metadata, visuals and source-linked evidence. Each independent sample runs its
own Narrative Planner. The runner then freezes exactly **one layout family**,
before Curator selects display modules. Coverage-first selection uses the current
Planner/paper profile and planned assignments, never previous scores or success.
A failed assigned task still counts toward planned family coverage.

Curator selects one compact scientific story, coherent modules, relevant visuals,
and explicit ownership of indispensable assertions within that family. A zone can
hold several vertically stacked modules: four columns do not mean four modules.
The code supplies provisional zone widths, title/picture loads, text space and soft
word ranges. These estimates are writing guidance, not a feasible-layout certificate.
One global Writer call then writes the whole poster, returning entries organized by
module. Normally a module has two or three short, scannable expressions: its main
point and necessary explanation. Optional source-unit support is not a checklist
to print. Generic Conclusion, Impact, Future Work or Takeaway modules are not added
by default; genuine findings and their necessary interpretation remain available.

Joint preparation integrates family-local geometry/subset search with bounded
content editing and scientific verification. Its physical-only draft view is
explicitly unverified: draft expressions never enter a verified claim bank, rendering,
evaluation or publication. After a draft fits, Verifier checks the actual selected
prose, every visible character, numerical/entity/comparison consistency, local
relationships and complete indispensable-assertion coverage. Citation use alone
cannot certify an assertion. Changed wording or context is checked again and the
actual verified text is measured again; unchanged verified expressions with identical
local context can be reused. Science and one adopted feasible layout are frozen
together. Styling then compiles this candidate, without another full layout search,
and continues through FontAgent, Preflight, rendering and RenderFit.

A single durable sample-wide editing ledger allows four substantive edit rounds:
at most three capacity/structure rounds plus one reserved quality round, with at
most two module editing actions per round. Early draft edits and scientific-feedback
callbacks share this allowance. There is no separate free re-curation pass or
per-family reset. One existing preparation response correction allowance remains
separate, shared by initial module-plan/output corrections. All charges precede
calls; interruption does not refund them. Missing charged responses or inconsistent
identities fail closed. Exact raw/parsed responses are saved before validation and
completed identical requests replay without another call.

Selective editorial revisions retain original scientific roots and local dependencies.
They may remove secondary optional detail, but surviving findings must preserve their
indispensable facts, scope, conditions, qualifiers and comparison basis, with an explicit
Verifier preservation verdict. Writer essential flags are suggestions in this path;
actual indispensable-assertion coverage establishes protection. The older pure
compaction interfaces retain their stricter whole-expression preservation contract.
Explicitly diagnosed supporting-module ownership can regroup a compatible source/owner
pair using the existing source/function rules; all original expressions, required
assertions and scientific origins remain separate and are reverified in the new
local context. The merge uses the same edit allowance, not a new Curator pass.
No new scientific admission or image-association judge is introduced.

Compatible original paper preparation can be reused with `--paper-cache-run-id <run_id>`.
Strict input/model/extraction/resource identities must match. Only original paper,
evidence and assets are copied; sample prose, scores, posters and templates are never
imported. Changed extraction identities refuse reuse. Source context may resolve
referents but cannot introduce facts absent from cited excerpts. Historical data is
never upgraded. The current generator is `explore_samples_v9`, preparation is
`sample_science_v6`, prose remains `sample_body_v2`, and dataset/storage remain
`rubrics_samples_v2` / schema 2. Old results stay readable; changed identities reject
old-run resume. Other samples' prose, modules, repairs, scores and feedback are never
inputs. Planning, writing and verification incur work for each sample.

Sample verification uses a verdict JSON Schema on compatible structured-output
providers and validates the returned structure locally. A malformed verdict may
use the existing single shared preparation-correction allowance; a spent allowance
or another invalid response fails closed. There is no free verification retry or
provider fallback. Scientific rejection does not trigger a format retry. Proposed
corrections are checked independently with their prior verdict as untrusted audit
context; source support, exact coverage and preservation checks still determine
acceptance. Classic request behavior remains independent.

All fifteen families are peers: there are no priority tiers or separate eligibility
pools. Coverage takes precedence; the same bounded paper-matching preference applies
within the least-used group. The three added families are `framed_multicolumn`
(shared opening, two/three body columns, shared conclusion), `narrative_evidence_grid`
(narrative rail, local evidence grid, shared conclusion), and `central_evidence_band`
(upper columns, a full-width middle evidence region, lower columns). Their bounded
geometry generators and spanning-band/column reading traversal use the shared
fitting, verification, repair, Preflight, RenderFit and local template-export path.

The existing family geometry algorithms, bounded content/geometry beam search,
near-miss checks, exact compilation, measurement reuse, shared-boundary refinement,
source-grounded content protection, reading-flow checks, final typography Preflight
and RenderFit remain. Optional paper-semantic key-visual candidates and bounded
same-source visual restoration remain available; no visual placement is guaranteed.
Curator records each module's reader question, communication goal and selection
rationale, using existing visual roles, captions and family-size estimates. Useful
same-module reserve visuals may receive bounded exact probes; they are not initially
placed and do not introduce an image-association judge or an image quota.
Writing space is estimated from bounded role/source-order-compatible assignments,
with explicit uncertainty; measured ownership replaces these hints for quality edits.
Writer synthesizes related supported assertions into connected display ideas rather
than treating evidence summaries as finished prose. Existing exact scientific
verification and indispensable-assertion coverage remain mandatory.

The reserved quality round can rewrite explanations and add nonredundant supported
expressions within at most two current modules. Additions get new scientific root
IDs and original-unit provenance; existing roots/dependencies remain protected and
changed local contexts are verified again. This uses the same sample-wide ledger,
not a free completion or polishing pass. Quality edits must preserve the feasible
baseline's visible content and space, and show an observed explanation or target-space
improvement; otherwise the baseline is retained. Copy/length signals guide this
round but are not scientific or aesthetic admission criteria. The saved quality audit
reports adoption/rejection and unresolved targets; no universal quality is implied.
Written modules retain their explanation order; compatible thin-module grouping
remains bounded. Classic inside this sample path keeps three unsplit/unspanned main
regions with modules stacked within them. The standalone classic command continues
to use its independent original Balancer graph and prompts.

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

1. **Parser** extracts the paper and visual assets.
2. **Evidence Builder** creates source-traceable atomic evidence.
3. **Narrative Planner** organizes scientific research-content units and priorities.
4. **Family selection + Sample Curator** freeze one family and select its scientific modules and visuals.
5. **Space draft + global Claim Writer** allocate provisional space and write the whole poster in one call.
6. **Joint preparation + Claim Verifier** fit the draft, edit within a shared allowance, verify exact prose, and refit actual verified text.
   The independent classic graph retains its existing Planner → Writer → Verifier → Curator order.
7. **Design agents** style and compile the adopted layout, then check final typography and geometry.
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
  -> independent NarrativePlanner
  -> freeze ONE family using Planner/paper profile + planned coverage
  -> global module Curator / provisional family space draft / global Writer
  -> joint draft fit + bounded edits + science verification + actual-text refit
  -> freeze coherent science and adopted single-family candidate
  -> ColorAgent / SectionTitleDesigner / compile adopted layout (no new search)
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
