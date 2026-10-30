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

Wide, shallow modules can automatically place original figures/tables on the left
and editable prose on the right beneath a full-width title. Fast fitting and final
compilation share the same measured composition; unsuitable modules retain the
stacked image-above-text arrangement.

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

Parser runs once per run. It retains native PDF text and original figure/table files,
then uses the text model to organize paper sections, key points and an ABT narrative.
The complete raw paper remains available to the final Critic. There is no
`source_document`, separate per-sample SourceNarrativePlanner, EvidenceBuilder,
mandatory paragraph citation, obligation bank or pre-generation SourceVerifier.
Native extraction/font/caption repairs are retained; undecodable or ambiguous input
still fails extraction rather than being guessed. Organized sections are writing
material, not a scientific certificate.

Each sample freezes one of the fifteen peer families using coverage-first selection,
paper features and its seed. Curator initially sees only the registered base regions,
with actual dimensions, typography and original visual footprints. It jointly chooses
content, useful reader questions, dynamic modules, prose hierarchy, figures/tables,
complete region ownership and module order. Natural reading can run down columns,
across rows or through clear mixed groups. The program preserves authored ownership
and relative order; it never silently reassigns modules to obtain a fit. The old
preview/final reading-route verdict protocol and source/role sorting are inactive.
Final Critic still evaluates human readability as ordinary quality.

Every active region holds at least one module and no more than its registered capacity.
For example, classic-three-column starts with 3–6 modules. If Curator returns fewer
meaningful modules than the base minimum, the program searches legal same-family
region merges and offers at most one whole-poster adaptation. Ordinary aligned,
adjacent capacity-1 support regions can merge in one or two disjoint original pairs.
Hero/protected regions do not merge; region splitting and recursive merging remain
disabled. No legal merge means an explicit failed task, not invented filler or another
family. Occupancy requirements do not turn all regions into protected merge regions.

Palette and title style are selected before measured editing, once per sample.
Actual text and visual measurement checks each independent module allocation and
regional gaps. Initial measurement chooses image-left/text-right in suitable wide
modules, with vertical stacking elsewhere. After the first fitted geometry, each
image-owning module's direction is durably fixed before capacity editing. Later
edits may change prose, proportional image sizes, column widths and region sizes,
but cannot switch between horizontal and vertical composition. A conservative
horizontal rejection receives bounded exact sizing within that fixed direction;
unresolved overflow remains explicit. Actual fits guide bounded size adjustment after writing,
with at most twelve size candidates per content version and bounded exact finalists.
Geometry changes preserve topology, capacities, merge provenance, module ownership
and relative ordering. Whitespace and overflow are measured, not inferred from words.
Mixed underfill/overflow first attempts space redistribution; useful expansion follows
for underfill and content compression follows unresolved overflow.

The durable editorial budget allows one initial Curator request, at most one merge
adaptation, at most three measured capacity edits. Edits can coordinate
more than two modules and return changed/new module patches; untouched neighbors are
retained exactly. One sample-wide field-scoped format repair is available. Parser
prioritizes the core method/technical figure as `key_visual`, allowing null when no
suitable figure exists. Curator must visibly use an identified key figure, choosing
its module and region without a fixed column or top-position rule. After Curator's
final draft (including any merge adaptation), selected figures/tables, module owners
and local image order are fixed. Capacity editing preserves them while geometry can
still resize/reposition them. There is no reserve-visual field, automatic supplementation
or independent figure-recovery call. Final Critic judges visual selection and explanation
coverage against the paper; including the key method figure alone does not prove adequacy.
No quality-edit model call or draft preview follows capacity edits. A no-op can stop
capacity editing early. Raw responses precede validation;
charged missing responses, corrupt ledgers and incomplete render receipts refuse
automatic resubmission. Science decisions are final Critic findings, not free retries.

Curator uses worked examples of main/support bullets, optional topic labels, genuine
steps and mixed findings/context. It chooses relationships from the paper rather than
requiring one style or a fixed hierarchy for every module. Supporting entries are not
counted as extra numbered steps; inline and display formulas retain authored support
indentation through shared measurement and editable PowerPoint rendering. Keyword
emphasis still runs through FontAgent. Writing guidance asks for mechanism/purpose,
metric definitions and comparison conditions without introducing mandatory fact fields.
Capacity requests receive actual per-module percentages and expand/keep/compress guidance;
90–100% modules normally remain unchanged unless a coordinated edit needs them. Histories
record program-derived entry/module changes and measurements before/after each edit,
separately from the model's explanation. These are observations, not scientific or
writing-quality certificates, and add no request or retry stage.

The measured utilization target is 90–100% of independently allocated module height,
alongside regional and overall whitespace checks. Insufficient useful material can
remain explicitly `underfilled` after finite edits. Spacing inflation, cropped
measurement boxes and repeated filler do not count as useful completion. After finite
capacity edits the latest renderable result freezes even with text overflow, out-of-
bounds elements, overlaps or whitespace. Preflight/RenderFit retain their actual failed
verdicts as scoring diagnostics; they do not block this route's rendering/publication.
Critic evaluates the retained defects. Corrupt content/resource/geometry identities,
non-renderable box data and actual output failures still remain generation errors.

After editing, content and layout freeze as a **render-ready editorial snapshot**,
not scientifically verified claims. FontAgent identifies keywords in the final body
and applies emphasis, then Preflight, Renderer and RenderFit record physical delivery.
There is no post-freeze title correction or automatic re-render to hide a bad outcome.
Visible text, titles, assets and positions remain bound to the authored snapshot.
Colors and title-style selection are not repeated in the final design stage.

The final Critic directly compares exact poster content with the original paper,
checking quantities, conditions, comparators, unsupported assertions and omissions.
It records factual consistency as `supported`, `issues`, `uncertain` or `unavailable`.
There is no previous-proof automatic 100 or pre-render scientific gate. Model review
is fallible; source support, explanatory writing and visual quality require separate
inspection. A failed/incomplete evaluation has no overall score, not an invented zero.

Every final rendered poster is saved regardless of score/reference result, initially
`unclassified`. Bundles include `poster.png`, editable `poster.pptx`, inspection-only
`template.json`/PNG/PPTX, `evaluation.json`, provenance and diagnostics. Internal renders
have distinct version directories; only the final outcome is an independent sample.
Templates and scores are never retrieved by later samples. Automatic Rubrics mining,
clustering, rule updates and score-driven regeneration are not implemented.

Generator `explore_samples_v28`, preparation `sample_editorial_v1`, editorial contract
`poster_editorial_v1`, evaluation rubric `academic_poster_editorial_v3` / system 6.2.0.
Dataset/storage remain `rubrics_samples_v2` / schema 2. Old source/evidence caches and
run resumes are incompatible. New paper caches bind Parser model/prompt/extraction
identity and retain ABT/organized sections, with copied assets local to the new run.
Historical output and independent classic remain untouched.

`--samples` counts tasks, including failures. Normal content/fit failures advance to
the next task; programming, authentication, service and storage failures stop the run.
One Ctrl+C finishes the current sample and pauses; another requests a cooperative stop.
Completed samples are immutable. Preparation checkpoints and all durable charges survive
resume. Independent samples keep the existing 900-second response timeout, 15-second
connection timeout and bounded transient-request policy; classic model policies stay
unchanged. No raw prompt or endpoint is emitted in `model_requests.jsonl`.

Model-free checks:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest -q tests/test_editorial_generation.py
```

The v24 compatibility check retains the previous Rubrics dimension weights and evaluator
contributions, deterministic section/gap and region-balance scoring, structured visual
findings and positive observations, palette fallback and source diagnostics. Editorial
changes remain limited to the approved writing, placement, fitting and final-paper
comparison behavior. Old reading/source admission rules are not reintroduced.

Current Rubrics scoring treats module utilization from 90% through 100% as ideal,
matching the writing target; modules in that band receive no underfill penalty.
Other geometry, whitespace, readability and content checks still apply.

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

```text
Parser: native PDF text/assets + model-organized sections/key points/ABT
  -> program freezes ONE family, base geometry only
  -> Curator jointly writes prose/modules/visuals and assigns positions
  -> optional legal region merge + one adaptation
  -> palette and title style
  -> measured geometry adjustment / at most three capacity edits / freeze current outcome
  -> freeze render-ready editorial content and geometry
  -> final compile / keyword styling / Preflight / Renderer / RenderFit
  -> original-paper Critic + final-image quality evaluation
  -> save every final rendered poster and its inspection-only template
```

```text
storage/rubrics_samples/
  runs/<run_id>/
    manifest.json
    run_state.json
    sample_plan.json
    inputs/
    paper_foundation/
      paper_state.json
      identity.json
      editorial/paper/          # durable Parser model requests
    samples/<sample_id>/
      family_assignment.json
      editorial_budget.json
      preparation/
        stage_<n>.json
        editorial/             # curator, edits, fits, previews, model receipts
        editorial_sample.json
        READY.json             # render-ready; not a scientific certificate
      attempts/<attempt_id>/work/renders/render_<n>/
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
