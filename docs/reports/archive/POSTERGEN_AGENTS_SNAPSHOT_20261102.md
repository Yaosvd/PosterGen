# PosterGen Development Guide

This file is the persistent development context for AI coding agents working in
this repository. Read it completely before inspecting or modifying the project.

## Project Purpose

PosterGen converts an academic paper into an academic poster. It extracts and
grounds scientific content from a PDF, selects figures and tables, plans a
controlled layout-family composition, and exports an editable PowerPoint file
plus a PNG preview.

The independent one-shot classic route retains the original editable
three-column Balancer path. The independent Explore sample route treats classic
three-column as an equal member of fifteen controlled layout families, searches
bounded paper-aware geometry variants, and uses a versioned LayoutSpec plus a
deterministic coordinate compiler. Saved poster layouts are inspection-only;
there is no cross-sample template/archetype retrieval or poster evolution.

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

## Typed field-only editorial format repair (2026-11-02)

User approved fixing the Fourier Layers run_ad9d403a67d541839f1d format-repair
failure, explicitly requesting focused validation ONLY, no full regression.
Generator becomes explore_samples_v33; models, scientific policies, one shared
format allowance, capacity/family/layout/render/scoring/storage policies remain.
Normal old run/code and extraction identities reject resume/reuse; historical
records, including this failed sample, remain immutable. No model/GPU run.

editorial_format.py defines editorial_field_repair_v1. A malformed response gets
one closed repairs object with typed field_N slots for diagnosed JSON paths.
Program applies slots to a copy of the FIRST response, retaining all other valid
fields, modules, prose, order and reason. Additional-property removal targets are
removed explicitly; missing/wrong-type fields retain their original field schema.
An unparseable/wrong-type root gets one root slot using the original schema;
there are no parsed valid neighbors to preserve on that existing recovery path.
Unknown slots, missing values, wrong types and complete/module-only retry responses
are rejected, not silently filtered. The merged result runs the original JSON
schema, masked-neighbor guard and semantic validator. A second invalid response
still fails within the same shared allowance; semantic/content failures buy no
format retry. Structured-output binding switches to the repair-slot schema for
request01 and restores the model afterward; first request schema is unchanged.

repair_plan.json binds diagnosed paths/schema and the first parsed response digest
inside the existing request journal. Interrupted returned replies replay without
extra calls; missing/corrupt charged replies/plans reject. Sparse Balancer patches
now remap normalize_candidate errors from merged-poster module indices to actual
wire-patch indices, including intentional module ordering. Errors in unchanged
modules/frozen fields do not grant write access to them. Existing Parser spelling
review uses correction=False and retains its current behavior. Paper-cache
extraction identity includes the new format helper. Classic is unchanged.

Final focused verification:70tests pass,2warnings,6.33s,normal exit0. Covers20new
field-repair cases, existing shared allowance/neighbor/root/strict-binding cases,
and45spelling-review cases using the same request module. The initial focused
run's two failures were fixtures that also invalidated child references when
changing a main ID; the fixture now supplies both diagnosed leaf slots. This
preliminary run is not acceptance. No full regression per explicit user request.

Real saved response replay under /tmp/postergen-field-repair-saved-replay uses
original four-module patch plus an OFFLINE repairs.field_0=e4 fixture. Actual
merge_patch validation passes, all four changes and original reason remain, final
five modules are retained, and journal replay makes0additional calls. Only the
single blank ID changes. This is exact failure/protocol acceptance, not live model
compliance, final fit/PNG/PPTX or scientific/aesthetic acceptance. Source/history
files remain unchanged. Evidence:/tmp/postergen-field-repair-{baseline,validation-final,scope}.json,
-focused-final.log and-saved-replay/validation.json (same prefix).
Only8task-owned paths belong in the atomic local commit; guide/report stay ignored;
all19pre-existing user paths and10097historical files are outside task scope.

Atomic local commit:900a119 (8files,346insertions/15deletions);no push. All19pre-existing user paths remain unchanged and outside the commit.

## Marker extraction and advisory spelling review (2026-11-02)

User explicitly restores upstream-style Marker extraction and adds ONE logical
paper-level spelling review. Current editorial Parser consumes Marker Markdown,
assets and captions directly; it no longer runs native/Marker regional admission,
extra raster OCR or native caption rebinding. Classic and explicit old source
routes retain their existing extraction paths. Generator explore_samples_v32;
preparation/material/scoring/storage/layout/edit policies and models remain.
Changed code/prompt/extraction identities reject normal old runs/caches; never
migrate or rewrite historical records, including the two failed extraction runs.

utils/marker_proofreading.py uses marker_spelling_review_v1. One complete-paper
request returns stable paragraph IDs, exact before/after local patches, reasons
and uncertainties, under the existing Parser policy, with correction=False.
No extra spelling/format retry or sample edit allowance; existing transport retry
policy remains. Unique exact spans, nonoverlap, spelling-only per-word differences,
unchanged punctuation/numbers/units and protected math/code/markup/URLs/identifiers
are checked individually. Native PDF text is an optional local context reference
for suggested repairs, never a replacement extraction or hard admission gate.
NFKC/Markdown/dehyphenation folding is comparison-only. Nearby eligible repairs
can share native context; an unrelated occurrence of a corrected word cannot
justify a patch. Native-confirmed original spelling stays; unsupported suggestions
and author-typo/technical-term uncertainty remain recorded without changing text.
Scanned/poorly encoded native text may provide no confirmation, leaving Marker
wording intact; this is not complete OCR or spelling accuracy acceptance.

marker_raw.md / marker_raw_text retain uncorrected Marker output. raw.md / raw_text
carry the selected spelling version. source_extraction.json embeds exact accepted/
rejected patches, native context/pages, uncertainties, receipt digest and warnings,
bound to PDF, original/corrected text, model/prompt/review-code identity. Paper
caches and sample snapshots/public diagnostics carry both original and audit;
explicit compatible paper-cache reuse does not repeat proofreading. Final content
Critic sees original_text, proofread_text and spelling_review separately; repairs
are not scientific verification or substitute source evidence. Other Parser
requests (metadata/ABT/sections/visuals) and final scoring behavior stay unchanged.

Timeout/invalid review returns Marker text with unavailable diagnostics, without
spending the shared format allowance. Completed or returned requests replay with
no extra call. Interrupted charged requests without a response retain Marker text
with a durable unavailable record and never resubmit. Cooperative interrupts
propagate in the helper. Corrupt/mismatched durable histories, missing inputs,
conversion errors and empty extraction still fail clearly. No service/GPU changes.

Final frozen CPU suite:1683tests +5subtests pass,7warnings,1563.13s (26m03s),
normal exit0. Focused final46tests pass,4warnings,10.77s,normal exit0,including
45new spelling regressions plus actual Parser integration. Pre-freeze broad213
passed/5warnings/205.74s; later context changes are covered by the final focused
and frozen full runs. Both CLI help checks, offline dependency lock and diff checks
are included in final delivery verification. All357frozen tracked/task files,
19pre-existing user paths and9778historical files remain unchanged; no new
historical artifacts. Only12task-owned paths belong in the local atomic commit;
guide/report stay ignored. No live model or GPU generation was launched.

Two real saved Marker inputs replay with explicit OFFLINE model responses under
/tmp: grammar114481chars,2accepted/1unconfirmed suggestions; watermark119709chars,
unchanged, no regional admission. Both retain source-file hashes and reuse the
returned review without another call. This verifies extraction routing, concrete
missing-letter patches and diagnostics, not live model detection/accuracy or a
new generated poster/scientific/aesthetic acceptance. Earlier pre-context replay
(0accepted/3unconfirmed) is preliminary, not the final real-paper replay evidence.
Evidence prefix:/tmp/postergen-marker-proofreading- (baseline.json,frozen.json,
focused.log,focused-final-small.log,full-cpu-final.log,replay-final-summary.json,
validation-final.json). Commit ID is recorded after final scope inspection.

Atomic local commit:fc7f0be (12files,646insertions/49deletions);no push. All19pre-existing user paths remain outside the commit; guide/report stay ignored.

## Adaptive visible PDF extraction (2026-11-02)

User approved changing PDF extraction for broader paper compatibility. Current
editorial Parser uses editorial_visible_source_v2 in utils/editorial_pdf.py;
generator becomes explore_samples_v31. Classic remains the original Marker path;
explicit old source-editorial retains strict pdf_native_regions_v1 by default.
The shared strict transcriber only gains an optional native_coordinates keyword
for already-normalized current-route boxes; its default behavior remains.
Preparation/material/scoring/storage/model policies and layout/edit budgets stay.
Normal old caches/resumes reject code/extraction identity changes; never migrate
or rewrite historical runs, including the failed run_5bad7021de5547218688.

Readable native text takes priority over converter prose disagreement, preserving
literal typos and scientific notation. Displayed rotated Marker boxes map back
to native PDF space. Converter-only extras on clipped Form pages do not enter
selected text; numerical substitutions are checked separately. Prose similarity
only routes severe garbling to OCR; it never certifies differing numeric values.
Tables/equations retain numerical checks without using prose-order similarity.
Numeric comparisons preserve signs,percent units,leading decimal points,exponents
and long identifiers while allowing equivalent formatting; emitted native precision
stays untouched. Partial/missing text and unresolved numbers use actual rendered
pixels through existing Parser-owned Surya recognition/detection models,not a new
authoring/VLM request. No new dependency or model load is added.

RasterOCR bounds each crop to12M pixels,up to24regional OCR attempts per page;
scans,ambiguous ownership or excessive OCR-only regions use one full-page pass.
At least.85line and numeric-word confidence is required. Engine,raster hash,
pixel dimensions,source boxes and selected method persist. Whole-page OCR groups
lines in Marker region/column order; uncovered layouts retain detection order with
an explicit uncertainty warning. Uniform raster regions are skipped with a
diagnostic. Unreadable headers/footers can be omitted; unresolved body/numeric
conflicts or no usable body still reject. OCR is fallible and never scientific
verification. Missing/corrupt resources,invalid regions and corrupt records fail.

source_extraction.json retains errors,warnings,native diagnostics and native/OCR
provenance; marker_raw.md retains the original converter output. Ambiguous captions
retain converter metadata marked marker_caption_unresolved rather than claiming a
native binding. Existing Parser writing,Curator and final Critic receive a bounded
quality summary; source_extraction_report travels through paper caches,current
sample snapshots and published diagnostics. Four existing Parser requests and
all other authoring/edit/review allowances remain. Cache identity includes both
new extraction modules. No old source-document proof is synthesized from OCR.

Timing logs now handle foundation failure before joint_preparation starts: zero
time with not_started and empty includes,without overwriting the original error.
Final frozen CPU validation:1638tests +5subtests pass,7warnings,1560.00s
(26m00s),normal exit0. Focused136tests pass,3warnings,12.09s,normal exit0,
including62new counterexamples. Both CLI help commands,offline dependency lock,
and staged tracked/new-file diff checks pass. All354frozen tracked/task files,
8432historical files and19pre-existing modified/untracked paths remain unchanged;
no new historical artifacts. Scope12task-owned files;guide/report stay ignored.
Evidence:/tmp/postergen-pdf-adaptive-{baseline,frozen,scope,validation-final}.json,
-focused-frozen.log,-full-cpu-final.log and-replay-summary.json (same prefix).
Preliminary rotation mapping and table-traversal failures are excluded from
acceptance;final full-suite source remained frozen throughout.

Three unique real-paper saved extractions (51pages,714selected native blocks)
replay successfully without live OCR or authoring calls. Grammar paper now has
278blocks/12warnings instead of6blocking disagreements;NEDS274blocks/3warnings
and HAGS162blocks/52warnings remain accepted. Each emitted raw-text digest equals
its complete original native transcription,including the formerly rejected paper;
no body was deleted to avoid conflicts. Actual Surya invocation is exercised with
deterministic prediction fixtures on real PyMuPDF-rendered pixels,not live GPU
accuracy acceptance. Scan/OCR unit fixtures validate confidence,coordinates,
multicolumn order and conflict handling,not universal OCR correctness. No new
model-backed sample or scientific/aesthetic acceptance is implied.

Atomic local commit:83d3239 (12files,860insertions/23deletions);no push. Guide/
report stay ignored;all19pre-existing user paths remain outside this commit.

## Shared module frames and measured space transfers (2026-11-02)

User approved the unified background-boundary/space redistribution fix for all
15 current editorial layout families and stricter core selection guidance.
Generator becomes explore_samples_v30; preparation/material/scoring/storage,
models, finite geometry/edit requests and freeze-and-score policy remain.
Old normal resumes are incompatible; never rewrite historical artifacts.

section_container.height remains the intrinsic content envelope used by fitting,
Preflight, whitespace and scoring. Separate module_frame metadata under
editorial_module_frames_v1 stores the actual allocated paint rectangle. Renderer
uses only that rectangle and disables inherited shape shadows on this route.
Frames retain all region/internal module gutters, even if content overflows;
content is never clipped or counted as filling space because a panel fills it.
Exact compilation/readiness validate frames against final regions, module order
and authored space weights; compiled geometry identity binds the paint boxes.
Inspection-only template export reflects the actual paint geometry. Legacy
renderer behavior is unchanged.

editorial_space shares measured boundary transfers across both axes, grids and
spanning bands without family-specific row rules. Coupled cuts share each donor's
measured spare-space budget and preserve adjacency gutters, metadata, capacities
and legal merge provenance. Final edge shifts remain bounded by .08 normalized;
at most12 fast size candidates and4 exact finalists remain. Exact horizontal
rows use full region height without the duplicate whole-region1.20 reduction;
existing text/formula render corrections remain. Accepted exact image splits
expose a minimum height preserving vertical-reference image area; vertical
pressure accounts for height-capped images growing with larger regions. Fixed
directions, original images, fonts, authored prose and scientific policies remain.

Core selection now prioritizes the paper's distinctive system architecture,
method framework or key mechanism, necessary theory or decisive experimental
evidence, with concrete content and complementary choices. Background/problem/
vision or generic pipelines alone do not qualify. Two is a maximum, not a quota;
importance and image presence do not certify a core. This remains guidance in
the existing Curator call, not a new scientific gate or model request. Existing
two-core palette sources, ownership and durable freezing remain.

Final frozen CPU validation:1576tests +5subtests pass,7warnings,1559.71s
(25m59s),normal exit0. Isolated focused49new regressions pass,2warnings,109.96s,
normal exit0. The broader parallel focus log reported200passed/519.42s but its
process later returned143;exclude that process from clean-exit acceptance. Its
cases are covered by the normal-exit full run; no source changed between runs.
Both CLI help commands,offline dependency lock and tracked/new-file diff checks
pass. All351frozen tracked/task files,8420historical files and19pre-existing
modified/untracked paths remain unchanged; no new historical artifacts. Scope is
14task-owned paths; guide/report remain ignored. No live model/GPU generation.
Evidence:/tmp/postergen-module-space-{baseline,frozen,scope,validation-final}.json,
-focused-isolated.log,-full-cpu-final.log and-replay-verified/independent-check.json
(same prefix). Preliminary strict-underuse assertions, the original merged-grid
fixture without mixed pressure and interrupted pre-final tests are not acceptance.

The engineering-only saved NEDS replay uses original prose and previous core IDs
to isolate geometry (not approval of its old background/vision core choice).
ActualPPTX has6disjoint frames,zero inherited effects; both row gutters=.697in.
All12/12editable text blocks match and RenderFit passes. Method remains image-left/
text-right with9.20607x4.26690in image. Intrinsic planned-height overage still totals
1.23404in across modules; Preflight/fit remains honestly failed for that unchanged
content. No capacity model was invoked,so this is not whole-poster/scientific or
aesthetic acceptance. Existing capacity editing and freeze-and-score handle later
generation; old saved outputs/receipts are untouched.

Atomic local commit:1bf20d4 (14files,505insertions/52deletions);no push. Guide/
report remain ignored;all19pre-existing user paths remain outside the commit.

## Two core panels and exact initial composition (2026-10-30)

User approved at most TWO explicit Curator core modules for background emphasis,
independent of importance, and exact initial image/text direction measurement.
Generator becomes explore_samples_v29; preparation/material/storage/scoring and
Parser/native/model policies remain. Old runs reject normal resume through code/
generator identity; never rewrite or migrate historical artifacts.

The strict Curator response now includes core_module_ids (0..2 distinct existing
IDs; normally choose one or two). Final merge adaptation precedes selection freeze.
Capacity patches preserve these IDs, even for a text-only core; importance can
change without adding/removing backgrounds. Text-only cores use the existing
global palette (normally logo-derived). An image-owning core derives its own light
panel from its owned key visual, otherwise its first selected visual/table. At
most two additional durable palette requests use the existing color-agent policy,
without extra writing/edit calls. Null/no usable image accent or a recorded palette
failure leaves that core transparent with diagnostics; no borrowed image/default
color is disguised as extraction. Missing/corrupt resources or request identities
remain errors. Panel sources, asset hashes, colors and extraction receipt hashes
persist in editorial/emphasis.json under editorial_core_panels_v1. The record
travels through SAMPLE_KEYS, frozen snapshots and publication diagnostics; readiness
checks palette receipts and compiled backgrounds. Renderer and color scoring use
explicit local panels only for this route, retaining legacy behavior elsewhere.
Foreground/keyword colors retain the shared contrast correction, without changing
visible prose or font sizes.

Initial current-route left-image/right-text candidates now use three DISTINCT
actual image-column widths derived from original aspects and available stack
height, with exact final-body measurement (including wraps, hierarchy and formulas).
No coarse text rejection precedes the initial direction lock. Fitting candidates
prioritize total image area and may not reduce it below the vertical reference
merely to choose a row. Existing safety correction, wide-module eligibility and
finite family/geometry/edit budgets remain. The same adaptive exact rule runs
before and after locking, so unchanged inputs compile identical geometry. A locked
horizontal failure retains a bounded exact horizontal overflow plan; a locked
vertical never switches. Global geometry ranking keeps its existing bounded fast
path, and real RenderFit remains authoritative for exported physical diagnostics.
Classic/explicit older-source routes keep their old planner.

Final frozen CPU validation:1527tests +5subtests pass,7warnings,1442.89s
(24m02s). Focused220cases pass,4warnings,464.74s; final independent color-scoring
assertion1passes/8.20s. All348frozen tracked/new source/test files,7000baseline
paper/sample files,1420old-output files and19pre-existing dirty/untracked paths
remain unchanged; no new historical output. Both CLI help commands,offline
dependency lock and diff checks pass. Same-geometry NEDS engineering replay
retains all12/12editable text matches and524/524normalized m3 characters with
image-left/text-right; image grows5.5942x2.59284 to12.05139x5.58567inches.
Two original top-module collisions remain explicit; this is not whole-poster
quality acceptance. Palette response is a pixel-derived offline fixture, not a
live model result. Evidence prefix:/tmp/postergen-core-exact- (baseline.json,
frozen.json,scope.json,focused-final.log,full-cpu-final.log,color-score.log,
validation-final.json,replay-same-geometry/validation.json). Only16task-owned
source/prompt/test/README files belong in the local atomic commit; guide/report
stay ignored,with no push. Local atomic commit:28c96a7 (16files). All19pre-existing
modified/untracked paths remain outside that commit.
Engineering-only saved NEDS replay stays under /tmp; it is not a new sample,
scientific/aesthetic acceptance or authorization for a live model/GPU run.

## RenderFit adjacent inline-script fragments (2026-10-30)

User approved fixing incomplete editable-text matching. RenderFit policy becomes
editable_exact_fragments_v2; report schema3 and generator explore_samples_v28
remain. Normal source-code identity rejects old run resume; historical artifacts,
reports and scores are never rewritten or migrated. This supersedes the HAGS
partial-coverage limitation recorded in the composition-lock acceptance below.

LibreOffice/PyMuPDF can split one inline formula into several adjacent physical
row fragments across extraction blocks. The old fallback only advanced to later
rows. The new bounded fallback accepts rightward fragments within1pt top/2pt bottom
alignment, <=2pt gap and <=1pt overlap; slight extraction-order jitter is allowed
using a sorted-row scan. Full normalized equality, disjoint glyph ownership,
ambiguity rejection, original next-row rules and all six resource limits remain.
Complete fragment edges retain separated bullets/punctuation in real glyph bounds;
no planned-frame clipping or fuzzy/partial-prefix acceptance is introduced.
Normalization remains NFKC/lowercase/alphanumeric: this is geometry/coverage,
not verification of mathematical meaning, script baselines or punctuation identity.
Display-formula images remain excluded. Missing, ambiguous or exhausted searches
remain inconclusive; confirmed overflow/collision still fails. No renderer,
layout-direction lock, prose, models, scoring or model-request budget change.

Final focused verification:128passed,2warnings,64.92s, including28new matcher
cases and real editable-script/HAGS PPTX/PDF/PNG coverage. On the SAME exported
PDF of saved run_7c282388d5ef4432b1e2_sample_000001, old-v1 matches11/12 and
new-v2 matches12/12, conclusive passed with no RenderFit issues; HAGS m3_text
matches405/405normalized characters in7fragments. Original source hashes remain
unchanged. The initial focused failure was a competing-evidence fixture whose
whole-block fast path bypassed fragment matching; its corrected fixture exercises
the intended fallback. That preliminary run is excluded from acceptance.
Final frozen CPU verification:1480tests +5subtests pass,7warnings,1308.92s
(21m49s). All344frozen tracked files,19pre-existing dirty/untracked paths and
9333historical files remain unchanged; no new historical artifacts. Both CLI help
checks, offline dependency lock and diff checks pass. Only4task-owned tracked
source/test/README paths belong in the local atomic commit; guide/report stay
ignored. No live model/GPU generation or scientific/aesthetic acceptance. Evidence prefix:
/tmp/postergen-renderfit-row- (focused-final.log,full-cpu-final.log,baseline.json,
frozen.json,validation-final.json,saved-replay/validation.json and
saved-replay/render_fit_v2_diagnostic.json).
RenderFit-v2 local atomic commit:6f6452c (4files); no push. All19pre-existing
modified/untracked paths remain outside that commit; guide/report stay ignored.

## Frozen initial module composition (2026-10-30)

User approved freezing image-left/text-right versus image-above-text after the
first actual editorial fit and before capacity editing. Generator becomes
explore_samples_v28; material, preparation, scoring and storage markers stay.
The existing bounded initial fit still chooses the first direction. Its exact
result and per-image-owner directions are saved in editorial/composition.json
under editorial_module_composition_v1, bound to initial sample/paper/resource/
content/geometry/style inputs. Recovery reuses that result before replaying edits,
without another initial search, selection or model allowance. Missing/corrupt
receipts after editing fail closed. No historical migration or rewriting.

editorial_composition travels through SAMPLE_KEYS, readiness/final snapshots and
published diagnostics. Capacity requests receive the immutable direction map and
measured direction diagnostics. Image sizes/aspects, column widths, regions and
prose may change while each image owner's initial direction remains. Fixed visual
ownership/order still applies; text-only structural edits remain possible.
The same shared planner serves fast fitting and exact LayoutAgent compilation.
A locked horizontal module that fails ordinary adaptive selection tries three
bounded splits with exact editable-text measurement; it never falls back to
vertical, including on overflow or a changed aspect ratio of the module region.
A locked vertical module never switches to horizontal. Unresolved defects retain
the existing three-edit freeze-and-score publication behavior. Invalid drawable
geometry and identity/resource errors remain failures; no extra model request,
font shrinking, scientific policy, family/merge budget or post-freeze repair.
Standalone classic and explicit older-source routes retain adaptive behavior.

Final frozen CPU verification:1452tests +5subtests pass,7warnings,1308.01s
(21m48s). Focused checks:135pass/153.46s plus3readiness cases/11.45s;
default-route real editable-PPTX/PNG/publication checks:35pass/182.54s, including
two additional horizontal three-edit/recovery cases. New composition file has44
cases, including15families, HAGS five-entry/shorter-region regression, both locked
directions, multiple visuals, overflow, corruption, text-only patches and charged
response replay. HAGS standard RenderFit honestly remains partial (11/12; its
formula-containing body unmatched); separate PDF checks find all5labels and433
nonspace glyphs inside the body frame, disjoint from the left image. This is
offline artifact/geometry evidence, not real-model/scientific/aesthetic acceptance.
All344frozen files,19pre-existing dirty/untracked paths and9333historical files
remain unchanged; no new historical artifacts. Both CLI help checks, offline
dependency lock and tracked/new-file diff checks pass. The preliminary uncached
overflow fixture run was interrupted and replaced before final verification;
it is not acceptance. Evidence:/tmp/postergen-composition-lock-full-cpu-final.log,
-focused-final.log,-readiness.log,-integration-initial.log,-frozen.json,
-validation-final.json,-baseline.json,-scope.json and-glyph-check/validation.json
(same prefix). Only13task-owned paths belong in the local atomic commit;
guide/report remain ignored, with no push or real-model/GPU generation.
Composition-lock local atomic commit:6e6cae8 (13files); no push. All19pre-existing
modified/untracked paths remain outside that commit.

## Editorial writing and hierarchy alignment (2026-10-30)

User approved implementing the read-only writing audit's recommendations in the
existing editorial route. Generator is now explore_samples_v27; preparation,
editorial material, strict response schemas, scoring and storage markers remain.
Parser/native extraction and agent model policies are unchanged. Old runs reject
resume through generator/code identity; historical outputs are not rewritten.

Curator now has four worked examples translated to existing entry/parent/style
fields, covering main/support bullets, optional labels, genuine sequential steps
and mixed findings/context. Main information units are a writing preference, not
an entry quota. Guidance covers mechanism/purpose, metric/comparator/conditions,
useful optional labels and direct prose. No compulsory hierarchy/style distribution,
new scientific proof fields, extra authoring/review request or model change is added.
Capacity editing receives program-derived ratio/percentage/action guidance from
real measurements. Fitting modules normally stay unchanged, with intentional
coordinated edits still permitted. It can merge/rewrite entries and labels rather
than just shorten each sentence. Model reasons never certify successful changes.

editorial_history includes actual candidate-derived module/entry/text/presentation
diffs and before/after measurements, including no-ops and the third edit's final
fit. These diagnostics do not reject a legal no-op or buy another request. Existing
three-capacity-edit freeze-and-score, final-only science Critic and fixed Curator
visual ownership remain. Editable prose is still styled by the unchanged FontAgent.

Only current editorial sections retain support indentation when dollar notation
is present and allow sub-bullets between numbered main steps. Display-formula
blocks share a measured plan between LayoutAgent, horizontal feasibility and
Renderer; surrounding prose/prefixes retain cues, emphasis and support indentation.
Inline scripts remain editable; existing display equations remain images with
exact source alt text. Unformatted source and styled text are parsed separately
to preserve literal stars/backslashes. Classic and explicit older source routes
keep their prior presentation and formula behavior. Physical-defect publication,
15 families/capacities/merge policies and geometry search limits remain unchanged.

Final frozen CPU verification:1406tests +5subtests pass,7warnings,1220.59s;
57focused cases pass,2warnings,82.73s,including33new counterexamples. Coverage
includes15family compilations,step/support/math/style preservation,ratio boundaries,
false claimed deletions,durable three-edit histories and two real editable-PPTX/
PDF/PNG cases. An additional offline formula-plus-horizontal-composition check
confirms shared heights and disjoint image/text boxes. All264frozen files,
19pre-existing modified/untracked paths and9131historical files remain unchanged.
Both CLI help checks,offline lock and diff checks pass. Early fixture/mid-edit
identity failures are preliminary,not acceptance. Evidence:/tmp/postergen-writing-
full-cpu-final.log,-focused-acceptance.log,-frozen.json,-baseline.json,
-validation-final.json,-history.json and-horizontal-check/validation.json
(same prefix). No live model/GPU generation or scientific/prose/aesthetic quality
acceptance is implied. Only12task-owned files belong in the local atomic commit;
the guide/report remain ignored,and all19pre-existing paths remain excluded.
Writing/hierarchy local atomic commit:7d11a7b(12files);no push.

## Curator-owned fixed visual selection (2026-10-30)

User approved removing the current editorial route's reserve-visual probing,
prioritizing a core method/technical diagram as key_visual and requiring Curator
use of a non-null identified key. Generator becomes explore_samples_v26; material,
preparation, scoring and storage markers remain unchanged. Changed Parser prompt/
code identities invalidate old paper caches; old run/code identities reject resume.
No historical migration. Classic/explicit old source routes keep their own behavior.

The current MODULE/PATCH schema has no reserve_visual_ids; restore_visuals and its
visual budget phase are removed. After initial Curator and any one legal merge
adaptation, editorial_visual_selection (curator_visual_selection_v1) freezes selected
visual IDs, module owners and local image order. Capacity patches cannot add/drop/
replace/transfer/reorder visuals or remove/rename an image-owning module. Prose,
space weights, intentional module positions and text-only structural edits remain
possible. Geometry can resize/reposition images and use existing horizontal composition.
The selection is carried by checkpoints, sample snapshots and final render identity;
missing/changed selection refuses editing/delivery. This is ownership integrity, not
scientific verification. A valid key must be visible exactly once, in any Curator-chosen
module/region, including the initial deficit draft. Missing mandatory use fails within
the existing finite request flow, without auto-insertion or an extra selection/retry
loop. Original graph, fifteen families, palette/font/render, three capacity edits,
90–100% scoring and freeze-and-score physical-defect publication remain as before.

Normal key preference is the proposed core method/technical figure, not a generic
useful result/table. Explicit null is respected; no suitable method figure may mean
no key. On invalid key IDs, new-route conservative fallback only accepts one unique
method-role figure, never a lone result/table/support asset. Shared legacy default
normalization stays unchanged. Model output semantics remain fallible; method bias
is a prompt preference, not a deterministic scientific proof. Final content Critic
explicitly assesses selected visual/explanation coverage using existing fields/calls;
a mandatory method figure never substitutes for sufficient experimental evidence.

Final frozen CPU verification:1373tests +5subtests pass,7warnings,1160.33s;
105focused tests pass,4warnings,182.25s. The first focused run's five failures were
an offline fixture missing the existing key-figure palette response; the fixture was
completed before both final green runs. All342frozen tracked/task/pre-existing-source
files,19pre-existing dirty/untracked paths and9131historical files remain unchanged.
Real editable-PPTX/PNG integrations retain the mandatory method figure through three
capacity edits, failed physical diagnostics and interrupted-publication recovery with
no repeat calls. Fifteen-family key placement, null/no-assets, forbidden asset edits,
merge-only pre-freeze reselection and legacy isolation have counterexample coverage.
No real-model/GPU or scientific/aesthetic acceptance is implied. Evidence:
/tmp/postergen-fixed-visual-full-cpu-final.log,-focused-final.log,-frozen.json,
-validation-final.json and -baseline.json (same prefix). Guide/report remain ignored;
only twelve task-owned source/prompt/test/README paths belong in the local commit.
Fixed-visual local atomic commit:c16a750 (12files); no push. Existing user-owned
region-policy changes/untracked files and HTML deletion remain excluded.

## Rubrics scoring ideal band 90–100% (2026-10-29)

User explicitly changed the current Rubrics scoring ideal lower bound to90%, matching
its writing target. editorial_critic_config deep-copies the shared config and overrides
ONLY current-route SectionFit ideal_minimum=.90. ContentAdequacy uses that measured
band or configured fallback, so90–100% receives no underfill penalty. Other whitespace,
geometry, overflow, scientific and content scores still apply. Shared diagnostic text
now interpolates the actual band rather than hard-coding95%. Classic/explicit old
source config remains95%; global config/weights/model/geometry policies are untouched.

Scoring identity becomes academic_poster_editorial_v3 / system6.2.0, avoiding comparison
as the same scoring profile as the old95% results. Generator v25, three-edit freeze/output
policy, preparation/material/storage, all-score publication and final-Critic-only flow
are unchanged. No prose rewrite, extra model request or rendering change. Native old
outputs remain immutable. Boundary and legacy-isolation tests cover89.99%,90%,92%,
94.99%,95%,100%,overflow, fallback and threshold-specific messages. This section
supersedes older95% scoring identity statements below, without changing their evidence.

Final verification completed2026-10-30:1337CPU tests +5subtests pass,7warnings,
1161.75s (19m21s);57focused cases pass in160.96s,4warnings. All255frozen source/
config/prompt/test/frontend/package files,9131historical files and19pre-existing dirty/
untracked paths remain unchanged. Model/poster/shared-critic policies, dependencies,
Parser, FontAgent, Renderer, LayoutAgent and module composition retain baseline bytes.
Both CLI help checks, offline lock and diff checks pass. No real-model/GPU generation
or scientific/aesthetic acceptance. Evidence:/tmp/postergen-score90-full-cpu-final.log,
-focused.log,-boundaries.log,-frozen.json,-validation-final.json (same prefix).
Baseline:/tmp/postergen-score90-baseline.json. Existing unrelated changes are excluded.

Scoring90 local atomic commit:c1b2e68 (5task-owned files); no push. AGENTS/report remain local/ignored.

## Rubrics freeze-and-score finalization (2026-10-29)

User explicitly removed the quality-edit stage and approved outputting renderable
posters even when text overflow, out-of-bounds elements or illegal overlaps remain.
This supersedes the v23/v24 quality allowance and hard physical admission ONLY for
the current editorial route. Generator v25; preparation/material/storage and the
academic_poster_editorial_v2 / system6.1.0 scoring identity remain unchanged.

The current route allows at most THREE measured capacity edits, with an honest no-op
ending editing early. There is no quality request, quality draft preview, quality
rollback, or post-freeze title correction/re-render. Optional finite visual probes
continue only from an already physically fitting candidate. The latest candidate
freezes with output policy freeze_and_score_layout_v1; actual compiled geometry is
bound alongside authored text, titles, ownership, styles, assets and receipts.
Utilization remains a90–100% target, not an output gate. Underuse and unresolved
physical defects remain explicit. Preflight and RenderFit keep their genuine failed
verdicts but record nonblocking admission under this policy. Runner renders, sends
actual PNG and physical reports to final Critic, and publishes unclassified outcomes
through the existing all-score policy. Geometry scoring also retains recorded
Preflight defects not otherwise detected. Critic never triggers regeneration.

Only drawable finite boxes with positive dimensions can freeze; NaN/nonpositive
geometry, missing/corrupt resource or request identity, runtime/rendering failures
still stop generation. A recorded physical failure must never hide a real renderer
error. Classic and explicit old source routes retain their original strict behavior.
Old runs reject resume after the generator/code change; historical outputs stay
untouched.

Final verification:1327CPU tests +5subtests pass,7warnings,1167.02s (19m27s).
Final focused59cases pass in180.54s,4warnings. All254frozen source/config/prompt/
test/frontend/package files stayed byte-identical; all9131historical files and19
pre-existing dirty/untracked paths remain unchanged. Model/poster/critic policies,
dependencies, Parser, FontAgent, Renderer, LayoutAgent and module composition retain
baseline bytes. Frontend build, both CLI help checks, offline lock and diff checks pass.
Two real editable-PPTX/PNG OFFLINE-response integrations retain revision3 text with
failed Preflight/RenderFit, lower physical scores and successful publication, including
interrupted-publication recovery without extra calls. Actual PPTX text and2048x1365
PNG files were reopened independently. No real-model/GPU or scientific/aesthetic
acceptance. Evidence:/tmp/postergen-freeze-full-cpu-final.log, -focused-final.log,
-frozen.json, -validation-final.json, -artifact-check.json, -frontend.log (same prefix).
Baseline:/tmp/postergen-finalize-baseline.json. All preliminary interrupted/failed
fixture runs are excluded from final acceptance.

Freeze-and-score local atomic commit:ad16863 (15 task-owned files); no push. Existing
region-policy modifications/untracked files and HTML deletion remain excluded.

## Rubrics compatibility alignment (2026-10-29)

User explicitly accepts the new implementation; do NOT consolidate paths merely for
file/name continuity. Preserve previous Rubrics behavior outside the approved Parser,
joint writing/module allocation/reading, measured fitting, early style and final-source
Critic changes. Generator v24; same sample_editorial_v1 / poster_editorial_v1 material
contracts; academic_poster_editorial_v2 / system6.1.0 scoring identity. Old runs reject
resume after code changes. This section supersedes v23's simplified palette/scoring.

Compatibility audit found omissions: palette fallback/style/emphasis/source provenance,
strict JSON schema binding, shared physical scoring, structured visual findings and
positive patterns, granular measurement/timing/region diagnostics. These are
restored without reintroducing source proofs, mandatory meaning/quote fields or reading
sorting. The SAME existing ColumnBalanceEvaluator, SectionFitEvaluator and family Critic
are reused; SectionFit reads new author-chosen independent planned_module_height only
for the new route, retaining gap/whitespace scoring. Family Critic skips the explicitly
retired source/role/sequence admission only for this route. Full dimension weights AND
source contributions match prior Rubrics. Content quality retains the six old semantic
submetrics; adequacy retains per-module25duplicate/6underuse penalties. Science remains
one final original-paper comparison. Visual review restores locations, actionable issues
and positives, without dedicated reading_review. Palette uses original logo/figure
prompts, logo->key FIGURE->configured color fallback and existing deterministic styling;
no body-format allowance is consumed by color fallback. Native extraction, original
policies/models, fifteen families/capacities, font/render/RenderFit, storage, pause,
publication and classic remain shared.

Final compatibility verification:1318CPU tests +5subtests pass in1089.73s (18m09s),
7warnings;41focused editorial/compatibility cases pass in107.26s. All253frozen files
stayed byte-identical throughout the full suite; all9131historical files stay unchanged,
and all19pre-existing user-owned dirty/untracked paths are preserved. Model policies,
dependencies, FontAgent, Renderer and RenderFit are byte-identical to this task baseline.
Frontend build, both CLI help checks, offline lock check and diff checks pass. Ten new
parity cases compare shared scoring/metadata, weight matrices, adequacy penalties,
palette fallback, actionable visual locations/positives and strict-schema restoration.
No real-model/GPU poster generation or scientific/prose/aesthetic quality acceptance.
Evidence:/tmp/postergen-parity-full-cpu-final.log, -contract-final.log, -frontend.log,
-validation-final.json and -frozen.json (same prefix). Full worktree baseline is
/tmp/postergen-parity-baseline.json. Preliminary fixture/mid-edit identity failures
are excluded from final acceptance. Existing Rubrics report contains the scope table.

Compatibility local atomic commit:8951a54 (14 task-owned files); no push. Existing
region-policy worktree changes/untracked files and HTML deletion remain excluded.

## Current upstream-style editorial route (2026-10-29)

User approved the detailed redesign and requested complete implementation. This section
supersedes the older source-editorial production route below. Generator v23,
preparation sample_editorial_v1, editorial marker poster_editorial_v1. Default paper
nodes: Parser ONLY, retaining native extraction but restoring model-organized sections,
key points, ABT, metadata and caption-based visual classification. No source_document,
SourceNarrativePlanner, obligations, EvidenceBuilder or pre-generation SourceVerifier.
Final Critic compares exact final content with ORIGINAL raw paper, reporting factual
supported/issues/uncertain/unavailable under academic_poster_editorial_v1 / system6.
No fake verified=true or old proof fallback. Old contracts remain explicit diagnostics.

After Parser, program freezes one of15peer families using organized paper features.
Curator sees only base geometry, jointly writes/chooses modules, hierarchy, visuals,
full region ownership and within-region sequence. Every active region is occupied;
minimum=len(active regions), maximum=sum(capacities). Shortage triggers legal original
pair merges and at most ONE full-draft adaptation. Occupancy is not merge protection.
Registered region capacities, no-split/protected/nonrecursive policy remain. No family
retry or automatic source/role/read-order reassignment. Existing wide image-left/text-
right composition is retained. Geometry search happens AFTER actual content measurement,
<=12 pressure-driven sizes per content version, with bounded exact finalists.

Palette/title selection precedes editing and is not repeated in design; new titles get
applications of the same fixed style. Three measured content edits + one quality edit,
no two-module cap, patches preserve untouched neighbors. Initial Curator1/merge1 and
optional visual probes are separately durable; field-scoped format repair shared once.
Utilization target90–100%; unfillable underuse stays explicit, no filler/density tricks.
Render-ready snapshot binds authored text/labels/titles, allocation and original assets,
not scientific truth. Final compile/FontAgent/Preflight/Renderer/RenderFit use it; final
Critic does not trigger regeneration. Every final rendered outcome saves unclassified;
failed evaluation has no overall score. New caches bind organized-material identity
and copy assets locally; old caches/resumes and old sample science are incompatible.
Classic, historical outputs and pre-existing region-policy worktree edits are preserved.

Final v23 verification:1308CPU tests +5subtests pass in1076.79s (17m56s),7warnings.
All252frozen source/config/prompt/test/package/frontend files stayed byte-identical;
all9131historical files remain present and unchanged. Pre-existing unrelated worktree
changes and HTML deletion are preserved outside this task commit. New31focused cases
include all15family base fits, deficit/merge/patch/format/budget counterexamples, native
Parser material branching and three real editable-PPTX/PNG/RenderFit/full-publication
integrations with OFFLINE model responses (low-score, evaluation-failed, and interrupted
before publication recovered without extra calls). A later final-Critic exact-visible-text
binding improvement is covered by the full frozen suite. Recovery snapshots carry paper,
logo/resource and budget paths needed by new readiness checks. Critic compares explicit
renderer-visible titles/labels/ordinals/body, not unused authoring metadata. Top-level
seven weights remain; retired family-role hierarchy contribution goes to actual-image
visual scoring (typography20%/visual80%). Frontend build, both final CLI help checks,
uv lock --check --offline and diff checks pass. No real-model/GPU poster generation or
real scientific/prose/aesthetic acceptance is implied. Prior fixture failures and
pre-recovery interrupted full runs are preliminary, not this final result. Evidence:
/tmp/postergen-editorial-v23-full-cpu-final.log, -delivery-focused.log,
-frontend-build.log, -validation-final.json and -frozen.json (same prefix). Baseline
of21pre-existing worktree paths and9131historical files remains
/tmp/postergen-editorial-v23-baseline/manifest.json.

v23 atomic local commit:2e5d9d1 (34 task-owned files); no push. Existing uncommitted
region-policy files/tests and the unrelated HTML deletion remain outside this commit.

## Current Rubrics source-editorial route (2026-10-27)

This section supersedes the v9/evidence-driven and proposed reading-order entries
below for the production Rubrics route. User confirmed the final plan and requested
full implementation. Generator explore_samples_v22; preparation
sample_source_science_v2; body sample_body_source_v1; original source contract
original_sections_v2. Dataset/storage remain rubrics_samples_v2/schema2. Classic
keeps its independent graph/prompts and all pre-existing model policy values.
Changed identities reject old run resume and old EvidenceBuilder paper caches.

Default paper nodes: Parser -> source_document_node. No Rubrics EvidenceBuilder,
atomic permission bank, required ev IDs or empty-bank compatibility adapter.
Each sample independently runs source_narrative_node -> freeze ONE peer family ->
source_curator_node (whole poster/prose/modules/visuals jointly) ->
source_joint_preparation_node. Continuous original sections and global story are
writing inputs; post-writing source references are audit support, not a renamed
precomputed fact list. Original text is complete within an explicit240000-character
context bound; excess fails without silent truncation. Few indispensable meanings
are preserved across mutable display entries and module split/merge/addition.

All15registered families/geometry generators remain. Actual fitting and source
Balancer editing happen before freeze, under existing3capacity+1quality and at
most2affected old/new modules per round. No-op quality review consumes its chance.
Optional role-based key reserves and at most2same-family visual probes share a
separate durable limit<=4. Physical selection updates actual visual context before
verification; final refit pins adopted geometry/ownership/visible visuals. Source
support, complete exact visible-text coverage, module-function consistency,
relationships, required meaning, preservation and useful additions use the SAME
module-level SourceVerifier, without a second judge. False scientific decisions do
not trigger format retries; malformed/incomplete verdicts use only the one shared
format allowance, then fail closed without buying prose retries. Valid neighboring
modules cannot be changed by format recovery. Raw responses, exact source/paragraph
spans, ambiguous locations, budgets and failed trials remain durable. Missing charged
responses and corrupt histories refuse resubmission. Shared-percent notation is
checked against actual quoted source; scientific identifiers are not treated as
measured quantities solely because they contain digits.

New Rubrics removes source/ROLE_RANK forced sorting,128-state reading reassignment
and old reading Preflight/heuristic-Critic admission. Actual-image natural routes
are judged inside existing Balancer opportunities and the existing final visual
Critic call. Vertical/horizontal axes are peers; row,column,mixed and parallel
routes are allowed. Schema/IDs/branch coverage and image/text/geometry/style binding
are checked; old preview clear status never certifies an edited/final image.
Hard geometry and scientific integrity remain. Mandatory role-region witnesses
are prioritized only for resource-allocation search, not displayed reading order.
Source primary scientific modules can fill the relevant hero even when another
role has a higher relative importance; Verifier checks the actual declared function.

Frozen direct-source proof binds exact candidate/text/context/source; compilation,
Preflight, Renderer, readiness and publication check it again, including module
titles, visible styled text and original visual paths/hashes. Final natural reading
is checked on the actual PNG. Source Critic uses original-paper explanation and
necessary-meaning verdicts rather than evidence counts, under distinct rubric
academic_poster_source_editorial_v1 / system5.0.0 with unchanged dimension weights.
All rendered outcomes still save unclassified regardless of score/reference failure.
No future Rubrics/Harness, cross-sample content/template retrieval or score filter.

Source-only caches are strictly identity-checked and remap copied document asset
paths to the new foundation; no donor-path dependency or sample science import.
Old caches/results remain untouched. Legacy helpers remain for shared/classic or
explicit diagnostic interfaces, never an automatic new-Rubrics generation fallback.
Public README, CLI help, WebUI text and source-specific nested timing are updated.

Prior v10 baseline verification (before the native PDF repair below): complete CPU suite1077passed +5subtests,6existing dependency warnings,
974.80s. Generation/config/README hashes stayed frozen during that suite. One extra
cache isolation/self-containment regression was added during the suite; the final
cache file separately passes10tests (9.69s). Frontend build and both CLI help checks
pass. All8089baseline historical files remain present/byte-identical. Existing
model policy entries are unchanged; Parser/ClaimWriter/ClaimVerifier/shared model
wrapper and family geometry/compiler implementations retain their prior bytes.
New61source tests include15family contract fits, direct-source/protocol/budget
counterexamples, actual editable draft rendering and a complete default Runner
through real compile/Preflight/RenderFit/PNG/PPTX/template/publication with OFFLINE
MODEL TRANSCRIPTS. These synthetic /tmp outputs are not real paper/scientific or
Rubrics-quality acceptance. No real model/GPU generation was launched. Actual
semantic stability, prose quality and aesthetics require separately arranged fresh
paper acceptance; never infer them from CPU success or synthetic scores.
Evidence: /tmp/postergen-source-editorial-full-cpu.log,
/tmp/postergen-source-cache-final.log,/tmp/postergen-source-frontend-build.log,
/tmp/postergen-source-editorial-baseline-20261027.json and frozen-tree manifest.
Detailed implementation/limitations: docs/reports/RUBRICS_SAMPLE_REFACTOR_REPORT.md
and docs/reports/RUBRICS_SOURCE_EDITORIAL_PLAN.md. Atomic commit recorded below.

## Adaptive horizontal module composition (2026-10-29)

Family-engine modules with visuals and prose can use image-left/text-right beneath
one full-width title when zone width/height >=1.6. module_composition.py compares
three bounded width splits, preserves original aspect ratios and multi-visual order,
returns unused image width to text, and requires a conservative fit plus reduced
body height. Narrow/tall, text/image-only or infeasible cases retain vertical stacking.
Standalone classic is unchanged. Fast feasibility and exact LayoutAgent compilation
use the SAME deterministic plan; final editable text measurement and ordinary
containment/overlap/RenderFit gates still apply. Visual height allowance can use the
horizontal row's measured height, while existing vertical sizing defaults remain.
No prose/source changes, extra model calls, family/region policy or budget changes.

User requested small-scope verification only: tests/test_module_composition.py has
8 passing cases (12.91s), including horizontal geometry/aspect/text preservation,
fast-vs-exact fit, ordinary Preflight child checks, narrow/classic/insufficient-space
fallbacks, single-medium modules, multiple images and actual editable PPTX plus
LibreOffice PDF RenderFit. Two existing dependency warnings. No full suite or real
model/GPU generation. Local commit f9c15a3 contains only the five task-owned
source/test/README changes; no push. Existing region-policy worktree edits and unrelated HTML
deletion remain outside this task commit. Source code identity prevents old run
resume after this implementation changes; no old outputs were modified.

## Region capacity and nonrecursive merge policy (2026-10-28)

User explicitly authorized capacities, in registry order:
222 /22 /2222 /222 /1111 /1111 /11211 /221 /111111 /111111 /2222 /
111111 /11111 /211111 /111111. Generator explore_samples_v22 rejects old resume;
LayoutSpec schema4. Original-source extraction/cache/preparation/body/storage and
model policies remain unchanged. Independent classic graph is untouched; the classic
family inside the shared family engine has the requested2/2/2 limits.

Region splits are disabled for every family, including topology/Preflight rejection
of old __lower regions. Body module editorial split/merge remains separate and keeps
its original budgets. All size generators inherit registered region capacities.
Framed columns no longer have an implicit two-column capacity4 bypass: ordinary
pair merges produce two-column variants under the same explicit provenance rules.

Only aligned adjacent ordinary support regions of capacity1 may merge: horizontal
same-y/equal-height or vertical same-x/equal-width, normalized gap<=0.06. Required
regions/protected_spans and hero/non-support regions are excluded. Each candidate
contains one or two disjoint original pairs, never recursion or a shared member.
merged_from binds exact original region membership; canonical coverage, role,
capacity, at-most-two merges and no split are checked during topology validation,
compilation and final Preflight. Geometry fingerprints include merge membership.
Curator briefs, actual fitting, fixed verified refits and previews use this policy.

Size edits are accepted only inside a strict measured whitespace envelope: total
container-union empty area, unallocated area, largest hole and directional/internal/
terminal gaps cannot increase beyond six/four-decimal rounding. Composition trials
with a higher score still reject if they add whitespace. Source quality geometry
edits recheck against their own baseline. This is geometric non-regression, not a
promise of zero blank space or universal image/typography quality. No new real-model
or GPU generation is implied. Validation covers1269CPU cases plus5subtests using a frozen1268-case full run
(1262pass/6obsolete-fixture failures,943.23s) plus complete152-case recheck after
ONLY correcting2test-fixture files (152pass,383.62s). The production code/config/
README stayed frozen; this is combined current-case coverage, not a second single
full-green run. One mixed-axis test was added after full collection and passes
within the real12-candidate budget. Final214-file manifest and evidence are in
/tmp/postergen-region-policy-validation.json and the existing Rubrics report. Historical samples and the
unrelated excavator_loading.html deletion must remain untouched.

## Native PDF source / paragraph locator repair (2026-10-27)

Supersedes the v10 extraction/quote protocol while retaining source editorial,
15 families/dynamic modules, visual reading, 3 capacity + 1 quality, <=2 old/new
modules, all-score storage and the same semantic verifier. Source route marker
source_editorial_v1 and body/storage contracts remain; generator v11/preparation
sample_source_science_v2/original_sections_v2/direct_original_verification_v2
refuse old resume and old paper foundations. Never migrate old sample science.

Actual v10 run_a6b3bccf23ca4ce4b2a9 failed in source_narrative_node before Curator
or family selection, 151.87s/3 successful API calls. Of 13 proposed quotes, 6 had
case/fi-letter/Markdown differences, not demonstrated scientific fabrication. PDF
visible pages and native text have intact first/significantly/efficacy/finding.
The old Marker Markdown loses letters. No real poster quality can be inferred.

Rubrics Parser now transcribes literal native PDF characters in Marker semantic
region order BEFORE title/classification/model work. Classic stays on its old
branch. Every native nonspace character is assigned once, with page/region/bbox,
original glyphs/fonts and line positions. Missing/ambiguous regions, OCR-only or
scan-only text, rotated pages, undecodable fonts and unexplained prose/numeric
conflicts fail with durable diagnostics. No global PDF x/y reordering, dictionary
repair, broad NFKC, silent OCR fallback or model guessing. Comparison-only fi/fl
folding admits the observed converter defect; emitted words remain native PDF
text. Actual PDF spellings are preserved. Table numeric comparison uses separate
Marker cells, never concatenated cell strings. Native table/formula line geometry
is supplied with full source. Asset captions bind to native same-page regions;
generated fallback labels are explicitly distinguished from original captions.

Some TeX CFF delimiters map to control codes even in the native decoder. Recover
only from the exact native text-trace glyph ID plus a unique embedded CFF font
and known glyph name/Unicode mapping. Unknown names remain errors. Font xref,
program digest, glyph ID/name, bbox and before/after stay in extraction audit.
No scientific word/number repair uses font-name inference. fonttools is a direct
dependency already at its old locked version; no package versions were upgraded.

marker_raw.md retains converter output; source_extraction.json retains native
coverage, disagreements, environment and font decoding; asset_caption_audit.json
retains bindings. Original source includes this digest-bound proof, raw positions
and ambiguous locations. Actual PDF identity is rechecked during source inputs
and science readiness. Cache identity also binds native extractor code and runtime
versions. The 240000-character context bound includes original paragraph locator
annotations/geometry; excess errors rather than truncating the original source.

Models select source_id + paragraph_ids, not retype source quotes. The program
copies exact original paragraph substrings and persists raw parsed locators plus
bound responses. Source material shows IDs around all continuous verbatim original
paragraphs, not a fact list. Positive wire and bound-verdict schemas differ;
semantic support, exact target coverage, quantities/conditions/comparators and
necessary meanings still require the SAME SourceVerifier. No extra judge or call.
Invalid locators use only the existing single shared format repair, preserving
non-reference content, correct reference fields and valid neighboring modules.
Every explicit negative science flag (including coverage/obligations) rejects
without buying a locator retry. An actual quoted "range/ranges/ranging from A%-B%"
licenses positive unsigned percentage endpoints for natural paraphrases; a missing
percent sign, negative endpoint, mathematical minus or subtraction remains strict.
This fixes the real paper 3%-17% false rejection without changing semantic checks. Charged missing/corrupt requests refuse replay.

Native text coverage is NOT a universal certificate of PDF visible semantics.
Incorrectly encoded printable glyphs, image-only details and formula/table semantic
interpretation still need source review; uncertainty cannot be described as
verified scientific quality. This repair does not promise error-free arbitrary
PDF recognition. Detailed real extraction and CPU evidence are recorded in the
existing Rubrics report. No fresh full model poster acceptance is implied.

Final repair validation: 1131 CPU tests + 5 subtests pass, 6 pre-existing dependency
warnings, 978.36s. All 204 frozen source/config/test/package files remain identical
through the final suite; all 8128 historical data/output files remain present and
byte-identical. Focused pre-final set: 155 passed; final native/protocol file:52
passed. Both CLI help checks and uv lock --check --offline pass. Final actual
Marker/native/asset extraction on GPU5 exits0 in27.82s:9pages/162regions/39022
nonspace native characters/46763 source characters,3CFF recoveries,7caption
bindings,5strict table regions,15source units,122418-character full source context.
Supervised parser379776 and its process group are gone; no owned GPU residency
remains. Existing unrelated GPU5 allocations and GPU3Qwen service were untouched.
All real parser diagnostics are /tmp/postergen-extraction-native-validated/;
CPU evidence /tmp/postergen-extraction-full-cpu-final.log; frozen/history manifests
/tmp/postergen-extraction-frozen-tree.json and /tmp/postergen-extraction-repair-baseline.json.
No fresh whole-poster model generation/scientific/aesthetic acceptance is claimed.

## Rubrics presentation metadata / recovery repair (2026-10-27)

Supersedes v11 presentation handling; generator explore_samples_v12 rejects old
run resume. Preparation sample_source_science_v2 and original_sections_v2 remain:
PDF extraction and strictly identical original-paper caches have not changed.
Real run_32b3fb2b0d26442d89f5 failed after Curator: all11 display labels were
independent headings, and the steps module had indices0/1/2 instead of1/2/3.
No science, fit, Balancer, PNG or PPTX followed. Narrative and native extraction
passed; this is not proof that the entire draft was scientifically supported.

Curator and Balancer now run candidate normalization within the existing durable
SourceRequests validator path. Plain/steps display labels are unused by the
renderer and are cleared; non-step indices become0, steps get1..N in the exact
existing entry order. No prose, title, source or item order is changed. Both stages
persist before/after metadata normalization audits. A topics label must be an
exact renderer-compatible short phrase from its own entry, otherwise empty.
All invalid topics label paths are diagnosed together. The same ONE sample-wide
format recovery may fix only those paths: every other field, prose, reference,
valid label, neighbor, list position, reading review, layout request, reason and
lineage stays identical. The raw, bound, failure and repaired responses remain
in journals. No additional editorial chance or semantic judge is added; a no-op
review still consumes its normal quality opportunity. Step ordinals establish
presentation only; scientific chronology and the normalized visible content still
need the unchanged direct-source verifier. Explicit false science, shared budget
exhaustion, corrupt journals and charged missing responses retain their safeguards.

Prompts/schema descriptions now document these contracts. Classic, all15family
geometry generators, source extraction, model policies, 3capacity+1quality and
<=2affected old/new modules are unchanged. The unrelated user deletion of
excavator_loading.html is preserved and must not be staged with this repair.
Regression and actual saved-response replay evidence are recorded in the existing
Rubrics refactor report; no fresh real-model poster generation is implied.

Final verification:173 focused tests pass (139.85s); the complete frozen-tree CPU
suite passes1148 tests +5subtests (975.27s),6existing dependency warnings. All214
source/config/test/package files stayed frozen; all8179historical files remain
present and byte-identical. Both CLI help checks pass. Real failed-response replay
through source_curator_node passes with5modules/11entries and18metadata changes,
unchanged prose/order,1archived response/no model calls/no format recovery; a
second exact replay issues no new calls. No scientific/physical/aesthetic poster
acceptance is inferred. Evidence:/tmp/postergen-presentation-full-cpu.log,
/tmp/postergen-presentation-focused-final.log,
/tmp/postergen-presentation-real-response/ and integrity/frozen/history manifests.

## Rubrics incomplete draft / combined recovery repair (2026-10-27)

Supersedes v12 topics rejection and missing-meaning format recovery. Generator
explore_samples_v13 refuses old run resume; preparation sample_source_science_v2,
original_sections_v2/body/storage and source extraction/cache identity remain.
Run_ef6a23942b8e40308cb2 initially omitted ob1 (budgeted exploration/exploitation)
and already had3nonextractive topics cues. V12 reported only the missing mapping;
its format guard locked all4modules and their count. The returned6module response
hit old cue errors first, and would also fail that count guard. Do not call these
newly invented second-response cue errors, a family capacity limit, or an API/PDF
failure. The bounded family brief allowed up to7modules; no physical fit occurred.

V13 normalizes all unused/invalid optional labels and ordinals with reasons, never
rewrites prose/order, and aggregates known local candidate structural errors into
one path-scoped format diagnostic. Every non-diagnosed field remains frozen in
that ONE shared format correction. Actual content/scientific SourceOutputError
cannot buy format recovery. Missing necessary meaning assignments are separately
recorded in Curator normalization/completeness audits. Only explicit unverified
Curator/Balancer draft paths allow them; default normalization and direct source
verification still reject incomplete candidates. Optional source-key reserve offers
also support the explicitly incomplete draft, without granting scientific approval.

Before fitting/verifying an incomplete draft, the existing converge loop invokes
Balancer under the existing sample-wide capacity budget, <=3capacity +1quality,
<=2affected old/new modules per edit. It may map already-expressed meaning or add
source-supported explanation, including new modules. Its response must preserve
actual current neighbors AND program-offered reserve visuals; the initial module
count is not a content-edit lock. Format repair still cannot add modules/prose.
Every resulting visible text/context goes through the same exact full SourceVerifier
and final fit; IDs alone never prove meaning is explained. No extra stage/judge,
free content retry, family retry, GPU/model run or score filter was added.

Curator/Balancer/Verifier prompts explicitly check comparator identity, all relevant
baseline rows, cost/budget/target-rate conditions and unsupported derived numbers.
Matching quantities do not prove the best-baseline assertion. Real table3 shows
HAGS4.50,AGS2.50,bestbaseline2.75 at80000/5%;80% is only vsAGS, not the strongest
baseline (about63.6%). No automatic claim substitution or general derived-number
permission is introduced. The same unchanged numeric guard rejects archived80%
when absent from its quoted support, even for an adversarial all-true verdict.
Semantic comparator stability still requires real model acceptance.
Final assert_verified/readiness/publication independently recheck actual assignment
and verdict unions plus covered_obligation_ids against ALL planned meanings; a
rehashed but incomplete receipt cannot bypass that boundary.

New regressions cover combined metadata/content/cue problems, legal4->6additions
across15families, bounded omissions/no-op/excessive edits, fake mapping rejection,
full joint READY and exact replay, interrupted charged responses and key reserves.
Validation evidence and exact limitations belong to the existing Rubrics report.
Preserve the unrelated user deletion of excavator_loading.html outside commits.

Final v13 verification (completed handoff2026-10-28):1179CPU tests +5subtests
pass in984.04s (16m24s),6existing dependency warnings. All215 frozen source/config/
test/package files remained identical; all8236baseline historical files remain
present/byte-identical. Earlier broad focused set202passed; final boundary set48
passed. Both CLI help checks pass. Actual archived draft + adapted legal Balancer
replay passes4->6with1capacity charge,0format corrections and0real model calls;
the archived unsupported80% claim still rejects. This is protocol/code acceptance,
not fresh paper scientific/aesthetic acceptance. No new GPU/model generation.
Evidence:/tmp/postergen-completeness-full-cpu-final.log,
/tmp/postergen-completeness-focused-final.log,
/tmp/postergen-completeness-boundary-final.log,
/tmp/postergen-completeness-frozen-tree-final.json,
/tmp/postergen-completeness-history.json,
/tmp/postergen-completeness-integrity-final.json and
/tmp/postergen-completeness-real-response-validated/.
Final result/commit inspection was delayed by automatic approval service usage
exhaustion, not a safety finding; resumed access and integrity audit succeeded.

## Measured source writing / patch Balancer repair (2026-10-28)

Supersedes v13 whole-candidate Balancer response contracts. Generator v21 rejects
old run resume; original extraction/cache/body/storage/model policies remain.
Real v13 run_22f1fd6e0ebb40afa724 wrote5modules/845words; bounded top_hero_bottom_grid
search failed at height. The capacity model returned unchanged content and redundant
identity lineage for all5modules. Exact lineage validation failed; accepting those
records alone would still leave no actionable edit and no physical fit. This is a
real generation regression, not an API timeout or PDF defect.

Curator now receives per-generated-variant inch/font/title and original visual-cost
writing estimates. Balancer receives bounded unordered provisional allocations (or
actual fitted ownership), measured module title/visual/body load, available body
height and suggested compression targets. Estimates never certify a fit, force a
reading order, pin geometry or replace ordinary scientific/physical gates. All15
families and dynamic module counts remain. No universal fixed word ceiling.

Balancer wire output is a patch: modules contains changed/new module objects;
remove_module_ids, optional module_order, lineage only for actual split/merge, reason
and legal layout requests. Program merges untouched neighbors and derives identity
lineage/candidate hashes/display ordinals. Harmless unchanged identity links normalize
away. It binds image/text/geometry/style fingerprints; the model supplies only visual
route judgments when an actual image is present. Without an image it receives no
reading-review output task and can still edit capacity/source defects. A quality
no-op is legitimate; unresolved capacity no-op fails with explicit diagnostics.
Full patch/candidate/scope/layout/reading checks occur inside the durable request
validation path. Structural recovery remains shared, one-shot and field/neighbor
scoped. Actual content/science decisions cannot buy format retries. Existing
3capacity+1quality and <=2affected old/new modules, finite visual probes, source
verification, final refit/freeze, actual-image Critic and all-score storage remain.
Convergence supplies the starting candidate to the SAME source verifier for complete
before/after preservation context; unverified drafts never become source evidence.

First real v14 acceptance run_04d00101f9034bfd8c50 retained the same family and
reduced the Curator draft from845to381words, but missed obl_1 assignment. Balancer
returned an empty patch and falsely claimed original-source text was already in
visible mod_hero. No PNG/PPTX; supervisor exit1, owned processes gone, GPU5 empty.
This is a real model task-grounding failure, not a protocol/physical pass. V15 now
places a compact CURRENT EDIT TASK after all full-source inputs, separating exact
visible target text/assigned IDs from source paragraphs. Capacity schema requires
at least one module and the controller requires real action; quality remains
optional. Empty capacity patches are content failures before schema validation,
so they cannot buy the one shared format recovery. Same budgets and verifier.
The preliminary full CPU suite was intentionally interrupted before v15 edits;
never cite its partial run as final acceptance. Source and tests must refreeze.

V15 run_208d168de40b4ee68299 used the same family,4modules/331words. Mandatory
Balancer actually edited mod_method to explain exploration/exploitation plus map
ob2/ob3. A complete draft fit passed, initially retaining table4/table5 while
reserving figure2. Hero and method semantic verdicts passed. Results had a positive
semantic verdict citing exact src_00012:p12, but numeric_support falsely rejected
70% because the actual source says "70%.". The old terminal-dot exclusion caused
regex backtracking to a bare70, losing percent units. It could also falsely license
unsupported sentence-final "70%." from a source count70. This is a deterministic
parser defect, not absent original support. V16 admits sentence punctuation while
blocking decimal continuation and percent backtracking; signs, exact values, units,
local quoted support and full semantic judgments remain. Added real-verdict replay
and unit/count/decimal/scientific-notation/adversarial regressions. Same verifier,
no new judge/free repair; the intended numerical standard is preserved.

V15's owned generation411693 and preliminary CPU412660 were SIGINT-stopped before
v16 code edits; supervisor cleanup completed, GPU5 empty. No finalized outcome or
poster existed. Under the standard lease its stale RUNNING projection was marked
PAUSED with validation_interruption.json; source science remains immutable and
ineligible for import. Never resume that run under changed code or cite interrupted
CPU logs as final. New real acceptance must start fresh from original paper cache.

V16 run_0c0abff2fb754652b4c4 wrote5modules/401words with all meanings assigned.
Its first real capacity edit shortened distance/ablation45->27/28words. The model
also pinned the provisional variant601..., reducing12geometry candidates to1.
A second edit echoed all modules and claimed fit because the provisional helper
used safety1.0 while actual fast search used1.2, yielding no suggested targets.
It finalized preparation_failed/no poster; supervisor exit1/GPU5 empty. This is
an implementation feedback inconsistency, not a legitimate no-change quality pass.

V17 planning and editing use the SAME configured fast-measurement safety factor as
ordinary fitting. Actual failed-fit pressure remains authoritative and supplies
explicit targets/word guidance if a provisional estimate has none. Capacity output
must keep variant_id empty; the program continues bounded same-family variant
search after text edits. Intentional local zone requests remain allowed, as do
actual-image quality composition requests. Estimates never certify geometry.
Added independent estimator-parity, observed-pressure fallback and no-provisional-
pin regressions; offline replay of both actual v16 inputs now has actionable targets
with safety1.2. Source-native extraction,15family generators/compiler, all budgets,
semantic verifier and all-score storage remain. Quantity sentence-boundary repair
fromv16 remains. Preliminary v16 full CPU was stopped before these source edits;
final acceptance must use the newly refrozen v17 source, fresh sample science and
original-paper-only cache, with actual PNG/PPTX and final proof/render checks.

V17 run_cfb8d60f9b514c23abf1 wrote4modules/377words and passed initial fit plus
ALL4actual module source verdicts. Final verified refit then hit a latent v10 bug:
source_candidate.modules.visual_ids are STRINGS, but physical_baseline preservation
indexed each as v['visual_id']. Empty-asset tests had not covered that branch.
V18 flattens the actual string IDs. A real-asset final-refit regression now checks
geometry/ownership/visible-visual preservation; module stack order is deliberately
not an old reading-order constraint. The default Runner integration fixture now
embeds an actual PNG into its native PDF and carries that asset through real
fit/science freeze/compile/Preflight/render/RenderFit/template/publication. Both
visual boundary cases pass. The fixture is offline model output, not real science.

A separate zero-model-call /tmp engineering replay of v17's actual supported proof
passes final refit plus real draft PNG/PPTX rendering with table4/table1. It is
explicitly ineligible for Rubrics and NOT a fresh independent sample. Full caption
provenance comes from the immutable paper foundation; layout-input snapshots are
measurement views and intentionally omit some source-caption metadata, so cannot
stand in for complete verified science. No old source records were changed.
V17 finalized FAILED/0posters, supervisor exit1/GPU5 empty. Preliminary CPU stopped
before v18 edits; final acceptance still requires new frozen source and fresh
independent generation from original-paper-only cache. No EB or fixed module count.

V18 formal run_169d0debfbf7415c943c passed fitting but FAILED with0posters. Curator
omitted exploration/exploitation mapping; a real charged edit supplied it. Numeric
support repeatedly rejected80000 because the actual cited source spells80k. This
is equivalent human notation, not missing original content. Generic diagnostics
did not name the value; another edit changed references while falsely claiming a
Manhattan-definition correction, retaining the exact failing text. A final no-op
failed closed. Supervisor exit1, owned processes gone, GPU5empty. V18 full frozen
CPU suite1224tests+5subtests passed1135.25s,6existing warnings;210frozen files and
8287historical files stayed identical. This is not whole-poster acceptance.

V19 preserves the SAME numeric admission decisions, without adding conversions,
judges or retries. Rejections now identify the exact visible target, missing typed
quantity and actual quoted original paragraphs; admission and diagnostics share
one helper. Curator/Balancer preserve original abbreviated numeric notation.
The failed two actual bound verdicts are replayed read-only with0model calls;
they still reject and now identify80000 against80k. New regression protects this
boundary. V19 final frozen CPU suite1225tests+5subtests passed1134.94s,6existing
warnings. V19 actual run_bc4b873d80c64879a1ff still FAILED/0posters: Curator wrote
964words and omitted obl_1;3real capacity edits supplied the mapping and compressed
4modules to338words, then fit passed. Hero's real scientific verdict passed. Method
had a positive semantic verdict but numeric support falsely classified plain
"level 1/level 2" as counts while ignoring original "level-1/level-2" identifiers.
All capacity chances were already spent. Supervisor exit1, generation exited,
GPU5empty. This is an identifier-classification defect, not a false method claim.

V20 treats positive integer hierarchy indices after "level " like the existing
hyphenated structural identifiers; percent, signed/decimal and independent measured
quantities retain strict checks. Regression covers a real level-space/hyphen pair
and adversarial 1-query/1-percent/count licensing. The unchanged actual method
verdict passes zero-call replay; results/ablation were never scientifically judged
in v19, so there is no whole-poster proof. Curator's same single call now repeats a
compact writing task AFTER complete original input: exact necessary meanings and
every variant's real zone/font/body/one-visual estimates. No source truncation,
hard word ceiling, fixed module count, geometry pin, new judge or budget is added.
The complete detailed visual-footprint brief remains. V20 fresh run_edaa78e7c9bd41949981
wrote4modules/281words with every meaning assigned and fit directly,0capacity calls.
The first verifier request ended883.2s with SDK LengthFinishReasonError, not a science
verdict. It finalized preparation_failed/0posters, supervisor exit1, GPU5empty.
Old missing responses refuse replay. V20 CPU1232passed/1failed+5subtests: only the
OFFLINE integration fake's prompt parser failed to strip CURRENT WRITING TASK.
That test-only parser repair passes1/19.13s; production code remains byte-identical
to its launch. A new frozen full suite is required; never call the prior suite green.

V21 captures a real returned OpenAI LengthFinishReasonError.completion ONLY for
SourceVerifier opt-in, with one assistant choice, length finish, id and complete
token usage. Provider completion/raw visible text/usage are digest-bound durable
receipts; internal reasoning is retained in raw audit, never repair source/context.
Missing/stream-incomplete receipts, timeouts, interruption and corrupt/missing
charged records still refuse resubmission. A returned truncated verdict uses ONLY
the pre-existing sample-wide single FORMAT allowance, not an extra judge, content
retry or token/timeout/thinking-policy change. Explicit scientific negatives cannot
buy recovery. Even valid JSON with length finish cannot silently certify delivery;
its complete valid fields/locators freeze if format finishing is required. A second
length response fails closed. Raw receipt loss/corruption refuses any new call.
Classic/shared model wrapper,15geometry families and source extraction remain.
V21 broad focused87pass/103.13s and final receipt boundaries12pass/6.27s.
Final frozen full CPU1245tests+5subtests pass1127.50s,6existing warnings. Both CLI
help checks, uv lock --check --offline and diff whitespace checks pass.

Fresh actual run_851f7afab99d465088a7 COMPLETED with1published poster,0scored,
evaluation_failed; NOT a full quality pass. Same paper/seed/family, only original
paper cache reused. Initial4modules/322words/allmeanings fit and all4real source
verdicts passed. Locked verified refit then found m1 fast height19.747>17.007;
one capacity edit shortened m1 from81to57words, leaving neighbors identical.
All4modules were reverified and final refit passed. Quality opportunity was a
legitimate no-op with preview reading clear. Two bounded visual-restoration probes
failed to retain figure1/figure2. Final298words/4modules, visible table1/table3;
method visuals remain reserved. Capacity1/3,quality1/1,format0/1; no length repair
was exercised by THIS actual run (receipt safety tests are offline SDK fixtures).

Actual published poster directory:
storage/rubrics_samples/posters/run_851f7afab99d465088a7_sample_000001/.
PNG417981bytes; editablePPTX422153bytes/1slide/9textshapes. Bundle hashes, frozen
snapshot, original PDF/direct-source proof and compiled visible text rechecked.
Preflight0issues, RenderFit conclusive passed with8/8body/title matches. Actual
final PNG reading is needs_revision, despite preview clear: top table too small,
bottom text dense/weak hierarchy. Never report old preview clear as final approval.
Manual inspection also finds the HAGS definition after its first result usage,
missing method figure and uneven visual proportions. Results-first alone is not
an error; no forced role/source reading order is restored.

Final visual Critic completed96.0s. Existing critic_content request failed0.328s
with BadRequestError, so overall score is absent and the poster is correctly saved
unclassified/evaluation_failed under all-rendered-outcomes storage. Exact provider
error body is unavailable. Local audit finds283382prompt characters, including
112513chars source-verification trace and122501chars original source; context
pressure is a hypothesis, NOT a confirmed root cause. Extra network tokenization
was rejected by automatic approval for additional paper-content disclosure; it
was NOT executed. Only local zero-network audit followed; no old request replay.

Generation supervisor exit0, owned generation exited, GPU5no compute residue;
GPU3model service untouched.211frozen files and8287baseline historical files are
checked unchanged. This establishes a real generated artifact with supported
body and physical checks, NOT upstream-equivalent aesthetics, stable model
semantics, a complete score, or fresh real acceptance for all15families. Existing
source/report/README hashes and source-only cache boundaries remain authoritative.
Evidence:/tmp/postergen-length-receipt-full-cpu.log,
/tmp/postergen-length-receipt-acceptance.json,
/tmp/postergen-length-receipt-acceptance-audit.log,
/tmp/postergen-final-content-local-audit.json and the formal run/background files.
Packaging note: first explicit staging found a surplus blank EOF line in the new
source_edits.py, invisible to unstaged diff checks on untracked files. Removed only
that whitespace; AST is identical and all other210frozen paths still match. No
behavior/model-policy change or further model/test run. Final delivery manifest
/tmp/postergen-length-receipt-delivery-frozen.json and AST/digest evidence
/tmp/postergen-length-receipt-packaging.json distinguish packaging from the exact
bytes used by the1245-test suite and real generation; do not conflate their hashes.

Formal technical artifact acceptance is complete with the explicit quality/scoring
limitations above. Do not present it as full quality acceptance. Existing historical files and the unrelated
excavator_loading.html deletion are preserved. Detailed evidence belongs in the
existing Rubrics refactor report. No subagents, policy changes, EB restoration,
classic edits, service interruption, score filtering or source-cache bypass.

## Sample verification protocol repair (2026-10-26)

Generator explore_samples_v9 / preparation sample_science_v6; body/storage/schema
remain sample_body_v2 / rubrics_samples_v2 /2. Changed identities refuse v8 resume;
no old scientific output is migrated. Prior run_d6a0e508cfc943ab967c ended15:36:38
Beijing after23m31s: preparation_failed, no PNG/PPTX/score; GPU5 cleanup confirmed.
Its final correction recheck returned a claim object instead of a verdict. Earlier
same-root verdicts alternated small-K RL/standard AGS naming; do not describe this
as a parser losing supported or as proof that the claim was scientifically false.

New sample_verification.py supplies a complete closed verdict JSON Schema, encoded
in the prompt identity and enforced locally. Sample-only opt-in structured-output
binding uses json_schema on ChatOpenAI-compatible text clients; classic keeps its
ordinary json_object behavior. Other clients still undergo identical local schema
validation. Unsupported provider schema is an ordinary request failure, never a
silent weaker fallback or another uncharged model call. Raw malformed/valid output,
validation failures and final response index remain durable in existing journals.
One malformed verdict may use ONLY the existing sample-wide preparation correction
allowance (shared with Planner/Curator/Writer); a spent allowance or another bad
response fails closed. No new free retry, per-root budget or capacity/quality round
is added. Valid supported=false is a scientific decision, not a format-retry trigger.
Missing booleans are never coerced/defaulted; exact coverage, required assertions,
local relationships, preservation and added-information checks remain unchanged.
Charged interrupted/missing responses refuse resubmission. Force stop before the
format recovery is propagated through isolated verification to joint preparation.

Correction rechecks include the previous verdict/reason as explicitly unverified
audit context, never source evidence. Existing Verifier resolves entity referents
against cited excerpts plus exact original chunks, and is instructed not to switch
aliases solely because labels differ. Ambiguity remains a rejection without unsafe
replacement; no new semantic judge or automatic alias map is added. Audit-only
correction_review is removed before accepted science persistence. Real stability
and poster appearance still need runtime acceptance; CPU tests cannot establish them.

Final frozen-tree CPU suite:1016passed +5subtests,6existing dependency warnings,
848.84s. All7851historical baseline files remain unchanged/present; all10frozen
files match their pre-suite hashes. Shared model wrapper is byte-identical to
6603a2a and strict donor extraction identity matches. Targeted protocol18passed;
legacy/model/preparation/execution84passed. Actual archived malformed response
recovery was exercised offline with explicit false support, no server calls and no
historical mutation. Evidence is under /tmp/postergen-verifier-v9-20261026/ and
/tmp/postergen-verifier-v9-frozen-tests.log. Fresh one-sample Active Geospatial
acceptance remains to be launched onGPU5 using seed20261026 and original cache
run_0ac92a0a8f264f4f8319. A launched run does not prove poster/scientific success.


Atomic local commitdb43de5:9tracked paths,331insertions/11deletions; tracked
worktree clean. New acceptance run_2c9c5c5d66874ee0b49a launched16:13:42Beijing,
supervisor347009/generation347010, CUDA_VISIBLE_DEVICES=5,1sample/seed20261026.
Strict original cache reuse succeeded; sample1 entered NarrativePlanner and both
processes were confirmed alive. Runtime records:
storage/rubrics_samples/background/verifier_v9_validation_20261026/.
All7851prelaunch historical files remain unchanged/present after launch. Stop
monitoring now per user preference; supervisor owns process-group cleanup and
exit.json. No real verdict-schema success, semantic stability, PNG/PPTX, score
or aesthetic acceptance is claimed yet. Inspect actual final results later.

### v9 final sample review (2026-10-26)

User-requested inspection confirms run_2c9c5c5d66874ee0b49a finalized SCORED/88.22
at16:26:42Beijing with actual PNG/editablePPTX and inspection templates. Five modules,
12expressions/272words;10required evidence covered. Preflight zero issues; conclusive
RenderFit10/10. All12 scientific verdicts passed without correction/format recovery;
this single run does not prove alias stability. Critic hard_gate_passed=false and
reference_passed=false because SectionFit fails (53.43). All-score publication is
intentional and is NOT quality acceptance. Supervisor exit0/GPU5 cleanup recorded.
Physical left challenge rail48.36% used/14.3967in gap; center85.75%/3.9716in;
right93.76%/1.7385in. Mirrored internal right_rail is physical LEFT. Geometry
refinement did run. Figure51.77DPI;three tables about64DPI, tiny internal text.
Visible table order1,3,2 has correct source pixels/captions but omits the visible
cost/target-rate labels. Do not diagnose an extraction ID swap from their order.
All12 final texts equal Writer;8exact/10near evidence-summary copies. HAGS/K and
actual16000-property evaluation conditions remain poorly explained.
The one quality round for display_002/003 was rejected before science/fit because
new level-2 text fails cited numeric matching. Its shared-policy explanation exists
in the original chunk but is not fully covered by cited ev_0048/0049; do not call
this proven hallucination or presume spelling2 differently would pass verification.
Baseline rollback is correct; quality charge stays spent. targets=[] in rejection
report loses the selected target IDs, though the raw draft retains them. Ranking
prefers copied-summary modules before worst gap, leaving challenge rail untouched.
Detailed review/limitations are in the existing Rubrics refactor report. This task
changes only local ignored documentation, with no code/tests/model run/rerun.

### Legacy versus Rubrics layout behavior audit (2026-10-26)

User-requested read-only comparison of all4 accepted legacy posters confirms real
composition difference. Oct20 same-family/v10 sample:65 verified candidates/1503
inputwords ->17expressions/373visiblewords; zones98.02/94.67/98.20%, largest compiled
gap1.4865in. V9:12initial/final expressions/272words; worst48.36%/14.3967in gap.
All4 old bundles are Explore, no parent/template input. All4 final attempt textual
completion actions were rejected; do NOT attribute their dense appearance solely
to successful model completion. Oct20 adopted figure2 restoration; rich candidate
pool and exact subset/geometry selection are demonstrated key contributors.
Initial Rubricsa916e5f retained layout_with_balancer. Module-first changes narrowed
its content input; later v7f25ee8a replaced that entry with joint pre-freeze search
plus frozen compile, bypassing repair_family_fit/complete_modules/polish_wording.
V8partially restores additions via existing quality edit; v9CAN add roots, but
legacy original-root queue/source search still are not equivalent active paths.
Old final attempts actually used2quality rounds; current joint policy hard-caps
quality at1 (capacity3,total4). Same nominal total is not identical scheduling.
Measurement/title metrics/text adapter/RenderFit/whitespace files are byte-identical
toc83300f anda916e5f. Relative whitespace non-regression is not absolute fullness;
current Critic correctly fails severe underfill. Old accepted-only vs new all-score
publication explains visibility, not the full generation regression. Full capability
preservation claims were too broad. Details/source history are in existing Rubrics
report. Diagnosis only: no code/model/rerun; future fixes must occur before freeze,
retain independent science/finite budgets/all-score storage, and not restore retired
features or hide bad results by score filtering.

### Upstream/current body-writing comparison (2026-10-27)

Read-only source comparison rechecked GitHub main8a54325f. Upstream Parser uses
model-structured continuous sections/key_points plus ABT/hook/impact; Curator is
the initial prose author, jointly returning text_content/hierarchy/visuals/columns.
Measured Balancer may rewrite/expand/shorten from original structured sections.
No upstream evidence-ID/ClaimVerifier stage exists. Example model provenance is
not disclosed; CLI default is not proof of the image's model or universal quality.
Current sample Planner sees compact evidence summaries/location metadata; Writer
DOES receive global story/focus, full permitted evidence and original chunks in
one whole-poster call. Exact support coverage concerns candidate text, not copying
paper words. The current prompt already requests synthesis and explanation.
V9initial/final12texts are identical;8exact/10near summary copies,5primary/plain
modules,all12kind=method,no parent/step hints. Do not blame Verifier rewriting or
missing global context. Actual Writer stage03/04 word ranges: challenge44–66,
method47–71,evaluation98–147,results24–35,impact67–101. Later measured ranges differ.
Useful shared-policy mechanism exists in original text but lacks full evidence
coverage. One quality edit failed and preserved the initial prose. The active
sample graph omits old local polish_wording/complete_modules;v9qualityCANadd roots.
Summary anchoring/permission bottlenecks and weak adopted editorial output are
supported diagnosis, not isolated causal/model ablation. Model effects remain
uncontrolled. Details in existing Rubrics report. No source/model/rerun changes.

### Requested source-driven editorial direction (2026-10-27; proposed only)

User asks whether Rubrics body writing/editing can follow upstream methodology
while adapting to all15families/variants. Feasibility confirmed; no implementation
or model run in this assessment. Target is continuous-source/global-story Curator
writing plus actual-layout-aware Balancer editing before science/layout freeze.
Module count must emerge from paper, visuals and actual legal geometry, never a
fixed N or family-ID-to-count table. Existing family contracts/solver/compiler are
reusable; models should not emit coordinates or invent relations to fill a family.
EvidenceBuilder may be auxiliary rather than exhaustive prose permissions; useful
new explanations need exact original support and existing full verification, with
sample-local evidence, immutable source bank and required-meaning preservation.
Allow presentation restructuring while keeping scientific identity/provenance and
all finite budgets/physical gates. This needs pipeline/data-contract integration,
not only prompt edits. Full proposal is in the existing Rubrics report. V9remains
active; no old science migration, historical mutation or classic change occurred.

### Detailed source-editorial plan (2026-10-27; not implemented)

Latest user direction removes EvidenceBuilder completely from Rubrics writing,
not even an optional pre-extraction/permission-list dependency. Shared classic
uses may retain the file separately. Direct original-section Curator composition
and actual-variant Balancer editing retain15peer families and dynamic module
counts, followed by complete original-source verification and coherent pre-freeze
fitting. New source references/audit records are post-writing support, never a
renamed precomputed atom bank. Preserve necessary scientific meaning across
split/merge rather than fixing display sentence roots. Existing4edit rounds
(capacity<=3,quality<=1), max2affected old/new modules per round, durable requests,
all scientific/physical/publication gates and independent samples remain.
Detailed user-facing proposal: docs/reports/RUBRICS_SOURCE_EDITORIAL_PLAN.md;
existing Rubrics report links it. Includes downstream Critic/source/provenance,
cache/schema/version compatibility, final-text binding and acceptance. This turn
only writes local ignored design documentation; v9code unchanged, no tests/model
run. Future implementation must not infer parser-only reuse from old evidence
cache compatibility or claim CPU/protocol success establishes poster quality.

### Reading-order audit/plan refinement (2026-10-27; proposed only)

family_reading_v4 remains active: source/role order, actual zone traversal/stacking,
128-state assignments before/after refill, unresolved-order rejection, Preflight
and Critic. Independent parallel/matrix sequences and declared result entries are
preserved. Current joint _fit failures may spend capacity editing even for reading;
do not extrapolate old pure-order skip tests to the current default path.
V9reading audit has0known conflicts/consistent metadata but scopepartial because
display002roleunknown; not a complete semantic/readability certificate.
Source-derived total order is heuristic and can overconstrain cross-section prose.
Plan section13 now separates hard physical route and verified scientific/necessary
interpretation dependencies from soft narrative/raw-source order. EB removal must
replace source-ID mapping, handle split/merge, keep family exceptions and update
shared search/Preflight/Critic/versioning. No guard was changed in active code;
no source/model/test run. Details in existing report and source-editorial plan.

### Final source-editorial/visual-reading proposal (2026-10-27; awaiting confirmation)

User explicitly requests a final integrated plan BEFORE execution. Revision2 of
docs/reports/RUBRICS_SOURCE_EDITORIAL_PLAN.md supersedes the previous hard
physical-traversal/coordinate-prerequisite proposal above. New Rubrics would remove
source/role-based forced ordering,128-state reading reassignment and old reading
Preflight rejection; actual visual natural routes are judged inside existing
Balancer opportunities and final PNG Critic. Top-down/left-right are peer axes;
column,row,mixed and parallel routes may all be valid. Keep hard geometry and
source-semantic integrity; no automatic module-order constraints derived from
paper sequence. No new judge/free rounds:3capacity+1quality remain. Previews and
reviews bind exact candidate/image/text/geometry/style; edits invalidate old visual
clear status, and final-round changes cannot obtain free reassessment. Reading
ambiguity is explicit quality feedback, not a publication filter. Complete Rubrics
EvidenceBuilder removal, continuous-source Curator/Balancer,15families/dynamic
modules and direct original-source verification remain in the integrated plan.
Only local ignored documentation changed; current v9 guards/code remain active.
No tests/model/GPU execution is authorized or performed by this plan-only turn.

## Integrated sample editorial repair (2026-10-26)

User authorized full repair following the upstream same-paper content comparison.
Generator explore_samples_v8 / preparation sample_science_v5; body sample_body_v2,
dataset/storagev2/schema2 and joint3capacity+1quality/two-module limits remain.
Changed identities refuse v7 resume; no historical results or science are migrated.
Original extraction/cache identities, standalone classic graph/prompts and all15
peer-family geometry/compiler/science/physical/publication safeguards remain.

Existing Planner distinguishes indispensable contribution/interpretation assertions
from optional formal definitions, baseline implementation and generic applications;
required-assertion rationales persist and cannot authorize later dropping protection.
Curator records reader question, communication goal and selection rationale and sees
existing caption/source roles/key pointer plus physical footprint/DPI estimates.
Explicit same-module reserve visuals are candidates for the existing finite exact
probe ledger, not initially placed or semantic/image-judge admission. No image quota.
Space briefs use bounded role/source-order partitions with explicit uncertainty,
not count-based round-robin hero allocation. They are never geometry certificates
or solver pins; measured ownership replaces estimates before quality feedback.
Global Writer synthesizes compatible evidence into explained display ideas, with
necessary source conditions/comparators and optional lead/support hierarchy.

Joint quality work diagnoses near-copied evidence summaries, long/review-voice
expressions and actual unused space. These are observable hints, never a new
scientific or aesthetic gate. Select targets by information/severity/fair turns.
The one durably charged quality round can rewrite existing expressions and add
useful supported explanation within two current modules; additions get new roots
with exact original-unit provenance. Existing roots/dependencies survive except
explicit legal optional omissions. Changed local contexts and all additions pass
the existing Verifier, exact coverage/required assertions and actual final fitting.
Added expressions also require explicit relevance/non-redundancy verdicts in the
same existing Verifier response, including any semantic correction; missing or
negative verdicts fail closed. There is no additional judging agent or call.
Citation-only changes cannot count as new supported information. Adoption requires
visible-root/visual preservation, ordinary space safeguards and observed target
prose/hierarchy/explanation/space gain. Explicit quality_report.json records normal
rollback as well as rejection, baseline/trial/final metrics and unresolved targets.
Frozen candidates are still compiled without another family search. No new model
stage, free round, retired necessity/image judge, cross-sample retrieval or score
filtering is added. Tests/source audit and eventual real acceptance belong in the
existing Rubrics report. Respect the user's preference to leave real validation
running in the background without continuous monitoring after a verified launch.
Final frozen-tree CPU suite:980passed +5subtests (868.98s, six dependency warnings).
All7577original historical files are unchanged/present;20classic/extraction/search/
render/storage boundary files match3b709e1. All16task source hashes stayed frozen
during the final suite. Runtime acceptance will use strict Active Geospatial donor
run_0ac92a0a8f264f4f8319 with fresh science onGPU5, one sample/seed20261026.
Atomic local commit71d0f0f (16paths,724insertions/59deletions), tracked tree clean.
New acceptance run_1cb2af91842a43d7b78b launched14:51:51Beijing with
supervisor339829/generation339830; strict original cache reuse succeeded and
sample1 entered Planner. Runtime folder:
storage/rubrics_samples/background/editorial_v8_validation_20261026/.
The user prefers no continuous monitoring after launch; leave this job running,
with automatic owned-group cleanup and exit.json. No PNG/PPTX, score, aesthetic
acceptance or post-run cleanup is claimed yet. Inspect actual final output and
quality/verification/physical audits later; do not replace or resume old v7 runs.

### v8 percentage-range acceptance follow-up (2026-10-26)

Run run_1cb2af91842a43d7b78b ended15:00:41Beijing after8m51s with
preparation_failed, no poster/score. Initial structure fit required a compatible
owner for supporting display_004. Its capacity revision was rejected before
Verifier because compact ranges3–17% and42–70% extracted bare lower endpoints;
the cited ev_0075/ev_0078 explicitly support3%–17% and42%–70%. The earlier
status description of an unsupported number was therefore a formatting false
positive, not evidence that these bounds were hallucinated.
Sample-only prose normalization now spells out the shared percent sign for an
en-dash or word-to range only when BOTH explicit percentage bounds occur in its
cited evidence. Initial/global writing, editorial revisions and quality additions
share this normalization and persist before/after display_normalizations. The
unchanged number guard, actual Verifier, exact-span coverage and final fitting
still run. Signed/ambiguous subtraction and already explicit ranges are untouched;
foreign bounds still fail closed. Classic/extraction and original evidence are
unchanged. An offline copy of the exact saved failed revision now normalizes all
14expressions with two recorded formatting changes; this is not poster acceptance.
Targeted regression:140passed in231.73s plus35preparation/execution tests
in16.40s (175total; existing dependency warnings only); patch checks pass.
A fresh one-sample real run with the same seed20261026, strict Active Geospatial
original-paper cache and GPU5 is authorized. New code identity refuses old run
resume; no old sample science is imported. Leave the new job in the background
after a verified launch, with owned-process cleanup, per user preference.


Fresh acceptance run_d6a0e508cfc943ab967c launched15:13:07Beijing after atomic
local commit6603a2a (3tracked paths,75insertions/1deletion; tracked tree clean).
Supervisor342074/generation342075 are alive; strict original paper cache reuse
succeeded and sample1 entered NarrativePlanner. Runtime folder:
storage/rubrics_samples/background/editorial_v8_percent_validation_20261026/.
Samples1/seed20261026/GPU5; all7636prelaunch historical files remain unchanged
and present.175focused tests pass. Stop monitoring after this bounded startup
check, per user preference. Owned-group cleanup/exit.json remain automatic.
No generated PNG/PPTX, score or aesthetic acceptance is claimed at launch.

## Single-family joint sample preparation (2026-10-26)

This current section supersedes historical per-family retries, module-by-module
Writer, independent re-curation and post-writing family selection descriptions
below. The user authorized full implementation of the reviewed plan and real
Neural Encoding plus Active Geospatial acceptance with fresh sample science.

Generator explore_samples_v7 / preparation sample_science_v4; dataset v2/schema2
and exact scientific body contract sample_body_v2 remain. Shared Parser/Evidence
Builder are unchanged. Planner runs per sample, then one family is frozen BEFORE
Curator. Its planning profile explicitly records unknown unwritten prose density.
Fifteen-peer coverage policy remains score-independent; assigned failures count.
No family retries: normal sample output/fit failure records diagnostics and advances
to the next task. System/programming/auth/storage/history failures stop the run.

Default preparation: NarrativePlanner -> module Curator -> family_capacity space
brief -> ONE whole-poster Writer call -> joint_preparation. Physical-only draft
lookup is explicit, never a verified bank or publication input. Joint preparation
uses existing family geometry/subset/exact search, content edits and unchanged
scientific verification, then refits actual final prose. It freezes one coherent
verified candidate. Later design installs it, styles it, compiles it WITHOUT a
new search, and uses ordinary Font/Preflight/Renderer/RenderFit/Critic/publication.
Column zones can stack modules; classic sample topology stays three main regions.
Conclusion-only closing zones accept actual findings/interpretation on this path.
No default generic Conclusion/Future/Impact/Takeaway filler is required.

Four substantive editing rounds are sample-wide: at most three capacity/structure
plus one reserved quality round, max two target modules per round. The digest-bound
content_edit_budget.json precedes calls and survives interruption; no independent
free re-curation or old two-round family bottleneck applies. Existing one preparation
output/plan correction allowance remains separate. Global Writer correction may
only fix diagnosed invalid modules, preserving valid neighbors. Raw responses and
exact-input caches remain durable; charged missing responses fail closed.

Selective editorial edits preserve claim roots, necessary scientific assertions,
conditions/scope/comparison basis/qualifiers and local dependencies. Optional detail
may be omitted with a reason. Existing Verifier must explicitly certify editorial
preservation, complete required-assertion coverage AND supported exact spans.
Writer essential is only a suggestion; required evidence establishes protection.
Explicit compatible supporting-module merges use existing source/function ownership
proposals, retain all scientific root IDs and origins, and reverify changed local
contexts inside the same edit allowance. No initial automatic auxiliary pile-up.
Old pure compaction interfaces keep their original stronger preservation contract.
Unchanged verified expressions can reuse science only with identical local context.
Changed text/context is verified again. No retired semantic/image judge is added.

The original optional source-key-visual offer and bounded exact visual restoration
remain, with a separate durable finite visual-probe ledger. Measurement scopes/cache
reuse, physical/source/reading/focus/whitespace safeguards remain. Pure draft/fit
inputs and results live under preparation/joint/ for CPU diagnostics. They are not
independent mining samples. All actual renders use distinct render_<n> directories,
retaining PNG/PPTX, actual inspection templates, geometry and parent provenance.
Title correction creates a derived candidate; frozen science/layout stays immutable.
All final posters remain all-score/unclassified with sibling inspection templates.
Historical data is untouched; old changed-identity runs cannot resume or migrate.
Strict original paper cache remains the only cache import. Future Rubrics/Harness
is still absent (generation_rubrics=None). Standalone classic behavior stays separate.

Generation implementation: f25ee8a (41 tracked files, local/no push).
Timing-report-only follow-up: 3b709e1 (three paths);101 targeted tests passed.
New space/joint/install stages have cumulative timing totals. Verifier timing is
explicitly included in joint preparation, not a misleading zero. Classic timing
format is unchanged; no generation/model run was repeated for this report fix.
Committed-tree CPU suite: 944 passed +5 subtests (772.43s, six dependency warnings).
Final joint-specific 36 and broader boundary 74 cases pass. Historical audit before
acceptance: 5,362 baseline files unchanged. No source edits while real jobs run.
Neural acceptance run_1df1257f678c4dd6b9eb finalized preparation_failed: frozen
central_evidence_band, 6 modules /21 expressions /358 initial words, 332 after
three capacity edits. All bounded searches still failed reading order coupled to
zone height. No final science verification, design, PNG/PPTX, Critic or score.
Task COMPLETED / supervisor exit0 is NOT poster success. GPU5 cleanup verified.
A CPU-only same-family source-order pin diagnostic in /tmp also failed conservative
height planning; it does not prove mathematical impossibility or create a sample.
Active Geospatial run_0ac92a0a8f264f4f8319 finalized SCORED/87.65 with a real
PNG and editable PPTX, sibling inspection templates and full provenance. Same
frozen central_evidence_band,6modules,14final expressions/279visible words,
10indispensable evidence IDs covered. All source/physical gates, final Preflight
and RenderFit passed (zero issues); source-order conflicts are empty. Zero
capacity edits, one reserved quality edit,42physical requests all completed with
no failures/retries/truncation. Parser26.10s, EvidenceBuilder1593.51s (88 original
evidence items), Planner127.70s, Curator89.62s, Writer166.70s, joint255.93s.
All-score grouping remains unclassified;87.65 is only the baseline Critic score.
The actual image still has substantial whitespace and a small central figure;
do not claim upstream-level aesthetics or universal family success from this test.
Supervisor326603/generation326605 exited; GPU5 empty at02:37:26UTC, GPU3PID5003
unchanged. No active validation jobs remain. Both job folders preserve logs,
results and cleanup proof under storage/rubrics_samples/background/.
Final historical audit:5,362 original files unchanged, none missing. No historical
sample, original paper, score or previous poster was mutated. Current worktree
should be clean after the two commits. Detailed evidence belongs in the report.
Implementation/CPU/real acceptance results are recorded in the existing local
Rubrics refactor report. Real validation stays on GPU5; never disturb GPU3 Qwen.
A launched job or successful process exit is not evidence of a generated poster.

### User-requested three-family cached-paper comparison (2026-10-26)

The user requested three real samples with different families from a paper that
already has an evidence bank. Use the unchanged v7 runner with samples=3,
seed=20261026, 54x36, local-text/local-vision Qwen3.8-27B and strict original-paper
cache donor run_0ac92a0a8f264f4f8319 (Active Geospatial, 88 evidence items).
The fifteen-peer coverage-first policy gives distinct frozen families; each
sample independently reruns Planner/Curator/Writer/joint verification/design.
No old sample prose, score or inspection template is a generation input.
Wrappers and before/after historical hashes are /tmp/postergen-three-families-20261026;
runtime records are storage/rubrics_samples/background/three_families_20261026/.
GPU5 only; cleanup targets the new generation process group. GPU3 service and
other workloads must remain untouched. No source edits while the job runs.
Launch or process exit does not establish poster success: inspect final markers,
real PNG/PPTX and diagnostics. Final results belong in the existing Rubrics report.
Run run_bd07b4adfb414de98cff started at 11:00 Beijing with supervisor330712 /
generation330713. Strict paper cache reuse succeeded and sample1 entered Planner.
The user explicitly requested stopping monitoring once launched and accepting later;
leave generation running in the background. No generation result is claimed here.
Supervisor owns automatic process-group cleanup/exit.json; inspect those on later
acceptance. Do not start replacement runs merely because this chat has ended.
Final acceptance: all3 finalized by11:47 Beijing (about47m40s). Sample1
central_hero_side_rails scored90.63 with real published PNG/editablePPTX and
inspection templates; final Preflight/RenderFit passed with zero issues.
Sample2 top_hero_bottom_grid preparation_failed after three capacity edits without
convergence. Sample3 method_flow_spine preparation_failed when its first capacity
revision contained a number absent from cited evidence. Neither has a poster/score.
All7148 historical files remain present and byte-identical. Supervisor exit.json
records exit0/GPU5 no compute workers at03:47:48UTC; generation330713 exited.
Actual successful image retains bottom whitespace and a small result table;90.63
is baseline Critic only. Detailed outcomes are appended to the existing report.

### Confirmed partial completion gap in v7 (2026-10-26)

Read-only whitespace diagnosis of run_bd07b4adfb414de98cff sample1 confirms that
fit_family_layout/exact refill/whitespace guards/composition refinement remain
active (four final refinement trials, no_safe_gain). However the new default graph
bypasses layout_with_balancer -> repair_family_fit -> complete_modules; its
original verified-detail/evidence-addition/source-search completion actions are
not fully migrated into joint preparation. Joint _edit rewrites existing roots
and may expand their supported text, but cannot add roots. Its quality target
sorting uses word loads rather than supplied gap severity. Actual quality draft
373->326words failed space_preserved and baseline was retained; the reserved
quality charge was spent without reducing final gaps. Three final zone bottom
gaps are3.24–5.37in; Critic whitespace65 despite total90.63. Thus code retention
is not full active capability preservation. This question authorized diagnosis,
not a fix or rerun. Detailed evidence and bounded pre-freeze migration direction
are in the existing report. Do not add post-freeze search, free repair rounds,
score filtering or weaken science gates when addressing it later.

### Upstream body-content comparison findings (2026-10-26)

User requested detailed original PosterGen comparison, not a code implementation.
Upstream main8a54325f was inspected through actual source/prompts; local original
resource/active-geo.png matches upstream Git blob and is the same-paper example.
Current v7 Writer's19initial expressions include14exact evidence-summary copies,
18single-evidence expressions, no parent/step hints. Verifier changes only2texts;
prose weakness starts in initial planning/writing. All6modules are primary/plain,
18/19final expressions protected. Global narrative and original source chunks DO
reach Writer. Do not falsely diagnose missing source context or blame Verifier
for rewriting all prose. Source correctness and writing quality are distinct.
Capacity brief currently assigns task/implications83–125words each in provisional
hero but architecture19–29in a rail; final hero instead holds architecture/setup.
Its module-count greedy binning is not actual final/source-aware allocation.
Old detailed writing prompts and polish_wording remain but the new default global
Writer/joint route does not call those old prose-polishing interfaces. Existing
structural editorial refinement explicitly does not rewrite scientific prose.
Sample Curator sees visualcaption/aspect, not existing classified roles/key pointer
or actual family-size estimates; it chose onlyfigure2/table3of7originalassets.
No withdrawn necessity/image semantic judge, template retrieval, forced image quota,
post-freeze search or free repair rounds is authorized by this analysis. Detailed
findings, upstream references and integrated improvement direction are in the
existing Rubrics report; source copies/findings are under /tmp/postergen-upstream-content-review/.

## Current architecture: independent Rubrics samples (2026-10-21)

This section supersedes ALL older Campaign/Batch/Portfolio/Lineage, Improve,
Validate, template promotion/retrieval, global learning, score-based saving and
resume instructions below. Those descriptions remain historical references,
not active APIs. Scientific, physical layout and source-grounding invariants
remain in force. The standalone classic graph and its prompts stay independent.
The baseline is c83300f (tree bab9907); withdrawn key-visual/necessity-v2 features
have not been reintroduced. The project no longer equals that rollback tree.

Active entry points:

- `src.workflow.pipeline`: unchanged standalone classic three-column graph.
- `src.workflow.critic_pipeline`: forwards to `exploration_cli`; accepts
  `--paper_path`, models/logos/dimensions, `--samples`, `--random_seed`, `--run-id`.
  New launches always create new runs; only an exact new run ID resumes.
  Old mode/Campaign/Batch/Lineage arguments fail explicitly.
- `PosterExplorationRunner` in `src/workflow/exploration_runner.py`: one immutable
  Parser/EvidenceBuilder paper foundation per run; NarrativePlanner, ClaimWriter
  and ClaimVerifier prepare independent science for EACH sample. A verified sample
  snapshot is reused for its family retries. Fresh create_state plus a deep copy
  of paper/sample fields starts EVERY attempt. Scientific variants, editorial
  selection, boards, Critic feedback and scores never enter the next sample.
  Preserve the existing Explore family search, scientific repairs, measurement
  reuse, exact compile/Preflight, typography and RenderFit/title correction.
- `webui/backend/main.py` exposes `sample_api.app`; the frontend entry imports
  `SampleApp`. Both classic and independent samples are supported. Control and
  file endpoints are scoped to jobs/new runs, never historical Campaigns.

`config/exploration_config.yaml` owns default 100 sample tasks and new root
`storage/rubrics_samples`. `config/critic_config.yaml` retains physical/search/
repair/evaluation settings. Family selection policy v2 uses frozen
`planned_sample_family_uses` (coverage first, bounded semantic bonus), never
previous scores. Slots/seeds/rules freeze first; each sample's family is frozen
after its own science produces a profile, before design. Retry outcomes do not
alter planned coverage. Each run freezes inputs, model/policy/font
identities and source hashes. A changed generation/evaluation environment
refuses resume. One exclusive run lease prevents concurrent writers.

All final rendered posters, including low scores and evaluation failures, are
published together at `storage/rubrics_samples/posters/<poster_id>/` with sibling
`poster.png`, `poster.pptx`, `template.json`, `template.png`, `template.pptx`,
`evaluation.json`, `provenance.json` and `diagnostics/`. Template JSON and editable
previews describe the actual final compiled coordinates; previews use generic
roles without paper prose/pixels. Templates are NEVER generation inputs.
All results have `grouping=unclassified`; 78 remains a diagnostic quality
reference only, never a save/filter/grouping threshold. User-defined score
splitting is deferred. `generation_rubrics=None` explicitly means the new Rubrics
generation library is not implemented yet; existing Critic is only a baseline
evaluation tool, not the future strong-LLM Harness.

Official samples are final outcomes only. Internal fit/repair/re-render work
and force-stopped outputs remain under run/sample/attempt diagnostics; they
are not independent mining samples. Known fit failures retry a different family
within finite task budgets; shared pregeometry failures allow at most one charged
targeted curation repair before stopping rather than blindly retrying families.
Programming failures stop the run without fabricated scores. Render readiness
requires current identity and owned nonempty PNG/PPTX before Critic. Evaluation
failures retain the poster with an unavailable official score. Same-sample
repair budgets are charged durably before calls and survive restart/abandonment.

Storage uses digest-bound immutable `FINALIZED.json` markers and atomic bundle
publication. Pending final output snapshots recover publication without model
regeneration or re-scoring; corrupt history/artifacts fail closed. Graceful stop
finishes the current sample; cooperative force-stop preserves attempt diagnostics
and resumes the unfinished task with a fresh attempt. Missing finalized bundles
are not silently regenerated. No migration reads/writes old `storage/critic_loop`,
Campaigns, posters, templates or knowledge. Historical data is excluded from the
new dataset by explicit new root/dataset identity.

Old scheduling/persistence/template/revision agents and their mode-only tests
were removed. Generic compiled-content/whitespace and recovery guards live in
`src/layout/content_guards.py` and `sample_safety.py`; current-sample fit locks
still protect internal fixed refits. Do not remove these scientific/physical
safeguards merely because their original callers used Improve.

No Seed Rubrics mining, preference/rejection clustering, KMeans, semantic dedup,
Rubrics updates or new Actor-Critic repair loop is implemented in this stage.
No real model/GPU run or historical Batch continuation is authorized by a code
refactor. Validation and limitations are recorded in
`docs/reports/RUBRICS_SAMPLE_REFACTOR_REPORT.md` (local/ignored).

### Scientific ownership tightening (2026-10-21)

This section supersedes the earlier shared Parser-through-Verifier foundation.
Generation/storage contract is now `explore_samples_v2` / `rubrics_samples_v2`,
schema 2, preparation policy `sample_science_v1`. V1 sample outcomes stay readable;
v1 runs cannot resume under v2 or migrate automatically. Use matching old code
or launch a new run. No historical files are changed or imported.

`content_contracts.py` owns paper/science whitelists and original source mapping.
Paper cache is `paper_foundation/paper_state.json` plus `identity.json`; only
Parser/EvidenceBuilder outputs and `narrative_content.meta` are shared. In the
sample route Parser skips legacy And/But/Therefore summarization, preserving
title/authors extraction and paper-semantic visual classification. Classic keeps
that call and original plan_narrative/write_poster_claims prompts unchanged.

`sample_preparation.py` runs Planner/Writer/Verifier under each sample's
`preparation/`, with chained, identity/digest-bound stage checkpoints and immutable
`sample_science.json` / `READY.json`. Preparation binds run/sample/seed/paper and
refuses source mutation. Completed stages survive force-stop; uncompleted work
can repeat with an additional durable stage-work charge in model_work_ledger.json.
This ledger is not an exact API-call counter and does not replace layout budgets.
Graceful stop finishes the sample; preparation failure records diagnostics and a
no-poster/no-score final outcome and stops before family design/Critic. This adds
planning/writing/verification work per sample; do not describe it as a free change.

Sample-only plan_research_units/write_sample_claims prompts distinguish scientific
research units from display modules: Planner owns grounded roles/priorities/source
order and necessary evidence; Writer owns candidate prose; Verifier retains all
existing checks; Curator owns display selection/grouping/titles/local presentation.
Legacy sections/section_id remain compatible internal research-unit keys. Do not
rename verified origins when modules regroup. Solver bounded grouping, recovery,
completion, measured/quality repair, gates and local fit locks remain available.
No new scientific semantic-admission judge or withdrawn necessity-v2 is added.

Display-module provenance is recomputed after final fitting and saved in attempt/
poster diagnostics, linking original claim roots, plan units, evidence and paper
sections. module_context retains allowed curated roots and original source units;
a colliding display ID cannot pull unrelated plan evidence. Sample Critic content
adequacy follows that mapping; classic retains direct-ID evidence policy and all
weights remain unchanged. Layout replay inputs include paper/science digests and
module provenance. Other scientific, physical, RenderFit, publication and all-score
inspection-template contracts above remain in force. The fifteen-family policy
and exact geometry/compiler algorithms are unchanged. Future Rubrics library is
still absent (`generation_rubrics=None`).

### Bounded requests and reusable sample curation (2026-10-22)

Current generator identity is `explore_samples_v3` (dataset/schema remain v2/2).
Changed source/prompt/config identity rejects old run resume; no old result is
migrated. Scientific preparation remains independent per sample. Its immutable
Curator plan now lives under samples/<id>/curation/board_00.json, identity/digest
bound to run/sample/science. Fresh family attempts copy that plan while clearing
variants, scores and layout state. Color/title/fitting/render stages still run.
Do not retrieve another sample's content or inspection template.

One targeted Curator revision is allowed after a diagnosed fit/structure failure,
charged DURABLY through the existing capacity ledger (`kind=curation`). No new free
repair budget or weakened scientific/physical gate is introduced. Protected base
claim IDs remain required/visible; existing visible prerequisite pairs must stay
local and retain their original dependency records for later subset selection.
Invalid revisions preserve the old base and diagnostics. One accepted
board_01.json opens a fresh bounded family pass; at most two plan versions, each
with the frozen pool/attempt limit, are searched. Force/restart reuses completed
curation, revision charges survive interruption, and exhausted budgets allow only
ordinary bounded geometry retries. An accepted revision never resets already
spent visual-restoration allowances. Unknown errors still stop without fake scores.

Sample-only prompts provide a soft 4-8 module starting point and a size/font-based
word-budget hint (roughly 280-420 at 54x36/44pt), never a hard truncation/admission
rule. Writer also receives a soft 2-5 candidate/60-120-word unit reference;
Curator starts around 2-4 visible claims per module and may exceed all references
for indispensable science. Full evidence/science banks remain. Essential conditions/claims remain
protected; spare details stay reserve. No necessity-v2 or new semantic judge is
added. Recuration sees exact failure pressure/ownership diagnostics, not Critic
scores. None styling_interfaces is normalized to existing defaults at sample
Solver/compiler boundaries so real saved inputs can reach exact refinement.

utils/model_requests.py applies only to optimization_family: SDK retries disabled,
900-second response / 15-second compatible-provider connection timeout, at most
one explicit transient retry. Read/write/pool timeouts do not retry; interrupted
remote generation is not blindly resubmitted. Classic retains 500 seconds and its
existing retry path. model_requests.jsonl records each physical attempt's UUID,
agent/sample/attempt, start/end, elapsed, safe exception type, token usage and
finish reason without prompts/endpoints/credentials. Truncation fails explicitly;
Curator request failures do not silently turn into deterministic poster success.
Timing reports separately summarize physical attempts and logical API calls.

The user authorized fixes and real validation. The first new same-paper/model
validation (run_74a4dd53c5f842098d23) correctly finalized fit_failed with no poster:
97 physical requests completed without retry, Curator ran twice, but 27 required
claims/639 words exhausted 15 families. This exposed still-ambiguous scale hints;
soft numeric candidate/module/visible-word references were tightened and one fresh
follow-up validation was launched. No scientific/physical gate was relaxed. Validation uses
only hash-verified original paper/asset/evidence cache from the failed sample,
copies assets into the new run, then reruns all new sample science/design stages.
It imports no old sample prose, poster, score, variant or template. All client GPU
work stays on GPU 5; do not stop/disturb the GPU 3 model service. Verification,
actual run result and commit are in the local refactor report's 2026-10-22 section.

### Module-first sample prose and diagnosed fit repair (2026-10-22)

This supersedes the v3 research-unit Writer and capacity-charged re-curation sections
above. Generator `explore_samples_v4`, preparation `sample_science_v2`, prose
`sample_body_v2`, curation `sample_curation_v2`; storage remains v2/schema 2. Old
results remain readable and untouched; changed identities refuse old run resume.

Sample preparation is NarrativePlanner → sample_module_planner_node (one Curator
call) → ClaimWriter (one call per display module) → sample_claim_verifier_node
(existing ClaimVerifier plus deterministic finalization). No second atomic writing/
verification bank is generated. Scientific units stay Planner-owned. Module Writer
receives global narrative, neighbor tasks, module-specific evidence and a dimensions/
font-scaled soft word range; multiple related assertions may share one expression.

`sample_modules.py` owns module normalization, exact supported-span coverage,
required-assertion coverage and immutable verified_module_board finalization.
covered_required_evidence_ids is an explicit existing-Verifier verdict that an
indispensable scientific assertion is fully expressed; citation intersection alone
cannot satisfy this contract. Core preferences prioritize substantive research
expressions without reordering condition-first prose. A
compound expression retains canonical source_plan_unit_ids; section_id is only a
single-source compatibility value, empty for mixed origins. Never use a display ID
as scientific provenance. Original roots remain authoritative for variants. Sample
Verifier requires all visible characters (including scientific operators) to be
covered by supported exact quotes, valid
cited evidence and source-supported local relationships; corrections receive fresh
coverage plus explicit necessary-information preservation. Full numeric/entity/
metric/comparison checks remain. Essential rejection, absent indispensable evidence,
empty modules or broken prerequisites fail preparation with diagnostics. Corrections
or optional rejection trigger at most one affected-module context recheck against
actual final wording; a further rewrite fails rather than looping. Classic
prompts, graph and verification response format remain unchanged.

SCIENCE_FIELDS now includes sample_module_plan, verified_module_board and
module_body_report; checkpoints and READY bind them. Design Curator installs the
verified board without another initial model call, then same-sample caching applies.
Shared fitting preserves written module ownership and explanatory order; it does
not automatically pile auxiliary modules into them. Unsupported auxiliary ownership
is still a shared pregeometry failure eligible for the one diagnosed revision.
Existing optional key-visual seeding uses original module source roles, including
mixed origins, without adding image-semantic judgments or forcing visual retention.
Bounded same-source adjacent
thin-module exact grouping remains; physical/source/focus gates, exact subset/
completion/refinement, Preflight, RenderFit and rollback remain mandatory. Multi-
source mappings drive recovery, reading and Critic. Fifteen peer families retain
existing geometry algorithms and coverage-first selection.

Re-curation now triggers only for explicit shared-content structure failures. One
sample-local curation_budget.json charge occurs before work, independently of four
layout content-repair rounds/quality reserve; interruption does not refund it.
Unchanged visible structure (including title/reserve-only edits) cannot reopen the
family pool. Protected roots and local prerequisite records remain required.
All search-failure paths include structure preparation and module loads. Feedback
selects closest/worst per-module pressure rather than eight repeated tiny misses.
Quality targets prioritize missing information then gap/use severity with fair
turns. Same-sample color.json is identity/digest bound and reused across families.

`--paper-cache-run-id` explicitly copies only a compatible original paper/evidence/
asset foundation from the independent-sample store. It checks inputs, models,
extraction code/policy/config and source/resource hashes. No sample prose, scores,
poster or inspection template is imported; old Campaign roots are never read.
Changed extraction identities reject reuse rather than upgrading old data. Sample
EvidenceBuilder skips only explicit References/Bibliography/Acknowledgments headings,
keeps research appendices, and reports skipped IDs. Planner source-order metadata
omits redundant full context paragraphs, retaining scientific evidence itself.

All-score/unclassified PNG/PPTX plus sibling inspection-template publication and
sample independence contracts remain. No future Rubrics library/Harness, withdrawn
semantic/image judge, necessity-v2 or key-visual guarantee is introduced. This task
implements code and CPU/offline validation; no new model-backed paper run is launched.
Validation and limitations belong in the existing Rubrics refactor report.

### Explicit module responsibility and shared preparation recovery (2026-10-23)

This supersedes earlier v4 module planning/recovery. Generator explore_samples_v5,
preparation sample_science_v3, assignment module_assignment_v1, request journal
module_planning_v2; dataset/storage stay v2/schema2. The body remains sample_body_v2
because exact scientific support/relationship/necessary-information standards stay.
Changed identities refuse old run resume; existing results are immutable/readable.

Curator gets an explicit indispensable-assertion checklist and original assignments.
required_unit_ids explicitly takes ALL existing required evidence of those units;
required_evidence_ids can split responsibility. The deterministic assembler expands
only declared responsibility and records added IDs. Shared origin alone cannot
assign missing content. Duplicate explicit responsibility, unknown/ambiguous IDs,
unassigned indispensable science and invalid modules/visuals stay errors. Stable
module IDs support whitelisted updates/additions and explicit reordering; a valid
module list cannot be replaced wholesale as a correction. Partial invalid rows
retain identities and cannot justify dropping valid neighbors. No new scientific
necessity/image-association judge or retired necessity-v2 is introduced.

Primary/required evidence and optional source-unit support stay distinct. Writer
receives complete allowed support, explicit assertions and neighbor tasks, writes
whole modules with stable module-scoped claim IDs, and cannot cite outside that
scope. Raw/parsed per-module writes and per-expression verification are input/digest
bound and replay without model work. Existing exact numeric/entity/comparison,
full-text support, relationship and necessary-information checks remain. Verifier
prompts clarify punctuation/operator span coverage without relaxing it.

One durable preparation_repair_budget.json allowance is shared between local plan
patching and affected-module body correction, independently of four layout rounds
and one structure re-curation. It is charged before calls, never refunded, and
charged missing responses fail closed. Existing transient/semantic-verifier repair
policy is retained. Body replacement must map essential original expressions and
prerequisites exactly once; its replacement prose is independently reverified with
explicit necessary_information_preserved. Missing verified module obligations get
one local correction only if the shared allowance remains. Network/format failures
in verification are not disguised as editorial retries. No infinite repair loop.

Final scientific snapshots bind all assignment/support/normalization/diagnostic
fields through sample_module_plan and module_body_report. sample_preparation_dir
is runtime-only to share the preparation ledger and response cache, not paper data.
Classic graph/prompts and physical/family/compiler/render/publication policies stay.
Parser/EvidenceBuilder/shared request/agent/poster settings are unchanged, preserving
strict cache compatibility; no old-cache identity exception or one-off loader is
recreated. Full real validation is explicitly authorized by the user's request to
execute the reviewed plan, using only original cached paper/evidence/assets from
run_da8fb99a67ca47e6b6fb, with fresh new sample science/design. Work stays on GPU5;
never stop the GPU3 Qwen service or other workloads. Results and limitations go in
the existing Rubrics refactor report. Launch does not imply successful generation.

Real v5 validation run_490d6f1c48cb482dbba3 finalized preparation_failed: 7 modules,
33 required evidence, 642 candidate words; 22 expressions passed, four rejected.
One response echoed the claim without a verdict; a separate corrected-text request
hit LengthFinishReasonError after 814.5s. No retry/poster/score was fabricated.
The sample-only verifier journal now requires a boolean supported verdict after
saving raw/parsed output, for both initial and correction checks. Missing/nonboolean
verdicts become verification_failure and cannot spend editorial repair. The sample
prompt ends with a complete response schema, never an input-copy contract. Classic
prompt, agent settings, science standards, 12000-token and 900-second limits remain.

Follow-up run_92cd32bee57d4e51b1b2 again hit LengthFinishReasonError on the IBL
dataset expression (817s), with no malformed verdicts in 13 saved responses. It
was deliberately terminated after this unrecoverable failure and another long
request: exit -15, no owned survivors, no FINALIZED sample. Its runtime-only state
was corrected under the run lease from stale RUNNING to PAUSED with explicit
interruption reason; it is interrupted diagnostics, never an official sample.
Do not resume/import its sample science under changed code. Both validation jobs
preserve their requests and raw data; only the first is an official failed outcome.

Sample Verifier now gets deduplicated original chunks by exact source section ID
and chunk index, only when the cited excerpt matches verbatim and the chunk is
unique. Context resolves referents; it cannot add evidence IDs or facts absent
from cited excerpts. Missing/ambiguous context stays explicit, without guesses.
Both initial and existing semantic-correction calls bind this context into their
actual prompt/journal identities. No new model calls or semantic admission judge.
After a sample request/format failure the Verifier saves incomplete partial
diagnostics plus not_checked_claim_ids and aborts immediately, with verification
false and no READY/board/design/Critic. Classic continues its existing behavior.

Run_4a2e85e7f2634e97b58a completed verified preparation (32 pass/one safe repair,
zero rejected; final context recheck passed), but all 15 bounded family searches
ended fit_failed/NO_FAST_FEASIBLE_VARIANT at estimated height: 11 headings, 643
verified words, 30 protected expressions. This is search exhaustion, not proof
of mathematical physical impossibility. No poster/score; supervisor exit0 is not
success. Capacity/quality budgets were respected; no gate or font was relaxed.
Module-planning prompts now emphasize compact compatible question-level groups
(4-6 preferred, 4-8 still soft), complete 2-5-word headings, and reserving detail.
Writer prefers one/two connected paragraph entries, not one entry per evidence,
and protects additional essential explanation only when needed for interpretation.
No programmatic deletion, hard module/word quota, changed scientific protection,
new re-curation trigger, or template/reference retrieval is added.

Compact run_e3170f21e3dc4cf8a395 finalized preparation_failed (18 pass/one repair/
two rejected). A positive verdict omitted a top-level clause comma from coverage;
another positive correction omitted necessary_information_preserved. Writer also
printed ev_... annotations in visible prose. These are retained historical
diagnostics, never retroactively upgraded. Writer and targeted body repair now
receive exact original chunks for allowed evidence (no extra model call), with
explicit qualifier/exception and bounded-comparison instructions. Evidence IDs
belong only in JSON. Declared parenthetical machine citation lists are removed
before verification, with display_normalizations; scientific parentheses, numbers
and literal source-supported ev_... names remain. Undeclared annotations fail.

Sample-verifier response shape always requests a preservation boolean; a positive
correction missing it fails as format, never assumes preservation. After a positive
whole-claim and relationship verdict only, comma normalization can extend an
existing exact supported multiword quote over a separating top-level comma.
All other visible characters must already be covered. Numeric separators,
parenthetical/bracketed commas, words, negation, scientific operators and negative
verdicts cannot be normalized. Raw quotes remain archived; exact extended slices
and coverage_format_normalizations are saved explicitly. The unchanged full-
character coverage gate still runs on the normalized exact spans. No claim text,
evidence assignment, numerical/scientific gate or repair allowance is weakened.

Current source commit 62f41d1, seventeen task-owned files, local/no push. Final full
CPU regression: 859 passed plus five subtests (746.97s, four existing warnings);
related 141 and final critical 46 cases passed. Eighteen classic/layout/render/
storage/cache boundary files match d5edeff; twelve foundations/174 resource refs
and nine finalized samples verified before the last run finished. Final real
validation run_8229d8748aa94d3e884f has now finalized fit_failed: six modules,
21 expressions / 585 words, 20 protected expressions, 19 required evidence IDs.
Verifier passed 20 expressions and safely corrected one, rejected none; the final
context check passed and READY exists. All fifteen bounded family searches then
failed at estimated height; no PNG/PPTX, Critic result or official score exists.
The supervisor exited 0 after 1319.26s with no owned survivors. COMPLETED/exit0
means the task was finalized, not that a poster was produced. Real end-to-end
poster acceptance therefore remains UNSATISFIED despite passing CPU tests.
Do not launch another stochastic validation without a concrete diagnosis. Exact
CPU-only capacity/search replay may inspect this immutable sample diagnostically,
but must never import its science into a fresh independent official sample or
rewrite its failed outcome. The detailed report owns final diagnostic evidence.

### User-approved coordinated module compaction (2026-10-23)

The user explicitly approved extending the task to coordinated whole-module
compaction after v5's failed real acceptance. Generator is now explore_samples_v6;
preparation sample_science_v3, body sample_body_v2, dataset v2/schema2 remain.
Old runs/results remain immutable and cannot resume under changed identities.

src/layout/module_compaction.py owns sample_module_compaction_v1. After a diagnosed
NO_FAST_FEASIBLE_VARIANT with observed estimated-height pressure, existing capacity
repair may request create_compact_module for a current written module. Rank full
visible module loads, giving untouched modules a turn, so early beam failures do
not hide the largest loads. This is not a new Curator/necessity/selection loop.
Only 2–8 verified sample-body expressions with original matching module ownership
qualify per action; larger/mixed/locked modules retain ordinary repair options.
This bound limits repair work, never scientific admission or allowed module size.

Return exactly one coordinated row per current expression in original order.
Keep canonical root IDs, source-plan origins, protected coverage verdicts and
local dependencies; variant IDs are separate and dependencies map to those current
variants with original records saved. Citation alone cannot create a new mandatory
assertion obligation. All prior covered_required_evidence_ids must remain explicitly
covered after full-body verification AND intersect actual supported support_map
evidence IDs, just as the preparation finalizer requires. Every rewrite supplies original_expression
for necessary-information preservation and passes the existing separate editorial
meaning-preservation audit. One affected-module final-context recheck is allowed
only if semantic verification changes proposed wording; any further rewrite fails.
No truncation, necessity relabeling, root merging or automatic scientific deletion.
An incomplete/unsafe batch publishes no board/variant/selection changes.

One module action consumes one existing action slot inside a durably charged
capacity round; four total rounds, the existing quality reserve, family limits
and two-actions-per-round policy remain. It does not use/reset preparation repair
or structure re-curation. One draft request, bounded per-expression verification
and preservation audits, and at most one bounded context recheck can entail more
physical work than the previous single-expression action. Raw/parsed/validation
records are bound to actual model/prompt/run/attempt inputs. Completed requests
replay; missing charged responses/corrupt history fail closed without resubmission.

Single-expression compaction/style fallback and same-root variant reuse in the
sample route also supply the old original_expression and preserve actual verified
required coverage. Sample-body generation gets ALL of its original cited evidence,
instead of the legacy first-six prompt subset; classic retains that existing
subset and behavior. A one-expression or >8-expression module cannot bypass the
sample scientific safeguards by falling back to ordinary repair.

Canonical family-zone exact-height probes normalize current-root display hints
and extractive labels with prepare_board before measuring; nested/step styles
cannot disappear merely because variant IDs changed. Probes may justify another already-budgeted
round if beam placement progress stays unchanged. These are local progress
diagnostics, not a feasible-layout certificate. Actual full fit, exact compile,
scientific/physical/whitespace guards, Preflight and RenderFit remain mandatory;
only a successful complete fit adopts variants into the attempt's active state.
Classic, source extraction, fifteen geometry algorithms, fonts, scores, historical
results, all-score publication and inspection-only template policies remain.

Read-only post-interruption exact-measurement search replay exhausted the same
bounded pool for all 15 families of v5 run_8229d8748aa94d3e884f: none feasible,
791.27 CPU wall seconds across the family passes. This rules out conservative
fast estimates as the sole observed cause, not mathematical impossibility or a
new official sample outcome. Source and finalized histories were not modified.
Implementation tests and new real acceptance are recorded in the existing report;
never infer successful generation from this newly authorized code change.

Final related CPU suite: 100 passed, two existing warnings, 125.25s. The first
full follow-up snapshot passed 887 tests + five subtests; after additional
coverage/style/compatibility hardening, the FINAL full suite passed 901 tests plus
five subtests (748.78s, four existing warnings). Atomic local commit 0bc819d:
seven task files, no push, worktree clean after commit; no generated data staged.
Final complete validation run_56650dbf9beb46df85a6 launched at 14:23 Beijing,
same paper/models/54x36/one sample/seed and strict original donor. All 126 frozen
production code/prompt identities match current source. Records:
storage/rubrics_samples/background/module_compaction_final_validation_20261023T062353Z/.
Preliminary run_d040386c567a4021acb0 was cooperatively force-stopped after its
Planner checkpoint and before Curator/design to finish this audit: PAUSED, zero
finalized/posters/scores, no owned survivors, no science imported into the final
run. An earlier launcher incorrectly supplied a nonexistent --run-id; it failed
before run creation/model calls and remains only a startup diagnostic. CLI
--run-id is RESUME ONLY; omit it when launching a new independent run.

Run_56650dbf9beb46df85a6 finalized preparation_failed before Verifier/layout:
12 research units / 22 required evidence, six modules after one missing-ID patch.
Writer module004/c used NDT2 improvement 11–37% without corresponding cited
evidence. That range exists in original section_17/chunk0 but in NONE of the
274 evidence items; original chunks are referential context, not new citable
assertions. Numeric admission correctly rejected it. The shared preparation
allowance had already been spent on Curator; no free repair was added. Exit1,
633.23s, no owned survivors, no poster/score. This does NOT validate or invalidate
the new module-compaction runtime: design was never reached. Full independent
successful-poster acceptance remains unsatisfied.

The user then explicitly authorized a REAL ENGINEERING REPLAY using old verified
science from run_8229d8748aa94d3e884f. It may call models and exact fitting/rendering,
but ALL new artifacts/ledgers/logs must stay under /tmp, with explicit engineering-
only / ineligible-for-Rubrics markers. It is not a new independent sample, must
not publish to the sample store, import templates/scores, alter source history,
or claim fresh scientific preparation. Verify original READY/science/foundation/
snapshot hashes, use copies of assets, preserve original source files and use
the existing finite repair policy with a new engineering-only diagnostic ledger.
This explicitly extends the earlier original-evidence-only reuse authorization;
it is a one-task diagnostic approval, not a persistent production cache bypass.

### Engineering replay preservation-response correction (2026-10-23)

The explicitly authorized /tmp engineering replay reuses only verified science
from run_8229d8748aa94d3e884f and the source attempt_0003 classic-family input.
It is not fresh sample preparation or an official/mining outcome. Original source
hashes, all sample-store filenames, and copied assets are checked before/after.
Root: /tmp/postergen-engineering-module-replay-20261023T065442Z. Initial attempt
spent ONE capacity round; drafts 164→131 and 120→94 words passed their nine
scientific checks, but preservation responses echoed input without boolean
verdicts (module003 item0 / module002 item3). Both complete batches were correctly
rejected; no variants/poster/score were published. Source/store stayed unchanged.

Only the new module-compaction preservation request interface is corrected:
audit-specific system role, explicit final verdict schema AFTER all input data,
and distinct editorial_preservation_invalid_response for absent/nonboolean
required verdicts. Negative real verdicts remain preservation failures. Raw and
parsed responses remain input/digest-bound; no model retry, science relaxation,
classic-prompt change or free allowance is introduced. A follow-up engineering
attempt uses the SAME attempts-parent durable ledger, with the previous one
capacity/family charge retained: at most ONE further classic-family round.
Focused tests: 49 passed (4.30s). Final full CPU suite: 908 passed plus five
subtests (749.43s, four existing warnings). Follow-up classic replay passed all
nine scientific and nine preservation checks; 284→223 words, exact heights each
reduced 2.93333in, beam placement1→3, but the full family remained infeasible.
Its two accepted module batches stayed trial-only; no poster/bank was adopted.
Two capacity charges remain spent. A final asymmetric_two_column engineering
retry uses original source attempt_0013 and the SAME ledger, at most one remaining
capacity round; no free refund or cross-family variant reuse. Startup guard
rejected an accidentally selected four-column snapshot before any call/charge;
the diagnostic is retained. Detailed outcomes belong in the existing report.

Final follow-up commit: a93ab17 (two tracked files, no push), worktree clean.
The final two-column pass also failed full search: one module1126→947chars
verified, exact savings2.2in / .73333in at canonical narrow/wide widths; the other
module had no net compaction and was rejected. Final ledgercapacity3/quality0,
no capacity allowance left.48 physical requests completed without retry; all
owned workers exited, single-use scripts removed, GPU5 clear and GPU3 PID5003
untouched. Original source-run hashes and official-store inventory unchanged;
14foundations/208resource references/11finalized/1poster bundle verified.
No diagnostic poster PNG/PPTX was generated; all new records are /tmp-only and
ineligible for Rubrics. Module-level scientific/physical savings were demonstrated,
but full independent successful-poster acceptance remains UNSATISFIED. The latest
fresh science validation's uncitable11–37% Writer failure is a separate unresolved
issue. Do not claim that engineering replay fixed this or exhaustively tested all
families with the compacted content. Final evidence is in the existing report.

### Module-plan interface diagnostics and one bounded correction (2026-10-22)

This supersedes the v4 assumption that every initial module Curator response is
immediately accepted or terminates preparation. The normal path still uses one
module-planning call. Its evidence rows now carry the original Planner owner IDs;
Curator need not duplicate uniquely determined ownership. normalize_module_plan
fills only missing UNIQUE original owners and records each normalization without
changing evidence, text, module grouping or required assertions. Shared evidence
needs an explicit original owner; auto-added owners for other evidence cannot
silently disambiguate it. Unknown/unplanned evidence, malformed fields, unknown or
unrelated origins, empty modules/evidence, duplicate visuals and missing required
assertions produce separate ModulePlanValidationError issue codes with module
index/title and offending IDs. No all-source attachment, ID guessing or automatic
dropping of necessary content is allowed. Scientific semantic verification and
all physical/family gates stay unchanged.

module_planning_requests.py binds per-sample prompt/model/context/paper identities
and raw/parsed/validation records under preparation/content/module_planning/.
Raw responses are durably saved BEFORE parsing/normalization. Only diagnosed model
output defects allow one corrective logical Curator call; it has a separate
preparation charge, not a layout-content or structure re-curation charge. The
charge is durable before calling, survives interruption and is never refunded.
Existing transient physical-request policy is unchanged. Saved responses replay
without more model work; a charged request whose response was not saved fails
closed rather than blindly repeating remote generation. Corrupt/mismatched
histories also fail closed. A second invalid response stops preparation without
fallback or a third call. Accepted sample_module_plan includes normalization and
planning-diagnostic summaries and remains bound into science checkpoints/READY.

Only code and offline/CPU validation are authorized by this repair task; no new
paper generation or exceptional cache entry is launched/recreated. Existing
run_d7b03f0e308b4d0796ab remains a failed immutable historical outcome. Its original
Curator response was not saved by the old implementation and cannot be recovered
or asserted to have been successfully replayed. Synthetic drafts over its actual
12-unit/160-evidence Planner input verify new handling while preserving all 21
required evidence IDs. Full CPU regression: 813 passed plus 5 subtests (750.29s,
four existing warnings); final targeted interface regression: 44 passed (8.85s).
Atomic local commit: d5edeff (six tracked files, no push).
Twenty critical classic/science/layout/render/cache files match baseline; six
historical foundations, 72 resource references and one poster bundle verify.
Detailed validation belongs in the existing refactor report.

### User-authorized single-use cached-evidence run (2026-10-22)

The user explicitly authorized one real v4 sample using the completed Neural
Encoding and Decoding at Scale paper foundation from run_2dd3e09720624e259f24.
Run run_d7b03f0e308b4d0796ab started at 15:03 Beijing time with Qwen3.8-27B
text/vision, 54x36 inches, one sample and original run seed 1494476416.
A temporary /tmp entry validated all original input/model/source/resource hashes,
all 274 evidence source excerpts and the reviewed extraction-code delta. The only
extraction change was the explicit metadata-heading filter; none of the old
274 evidence items came from the skipped acknowledgments/reference chunks, so all
were retained with their original IDs. The added max_curation_revisions setting
was separately recorded as a later-design-only change. No sample science, prose,
poster, score or template was imported. All current preparation/design stages rerun.

The sole temporary executable entry unlinked itself AND removed its temporary
directory before starting the worker. There is no durable bypass, new CLI flag,
patched production module or reusable entry. The standard strict paper-cache
identity checks remain unchanged. This is an explicitly documented one-time data
reuse exception, not a claim that EvidenceBuilder was rerun under v4. Source
provenance is bound in the new manifest and paper foundation; logs and PID records
live under storage/rubrics_samples/background/module_prose_oneoff_20261022/.
Supervisor PID 269638 / generation PID+group 269641 at launch. Work stays bound to
CUDA_VISIBLE_DEVICES=5; cleanup targets only this run's processes, preserving other
workloads and the GPU 3 model service. The supervisor records exit/cleanup and
absence of the temporary entry in exit.json. A launch is not generation success;
inspect result.json, sample finalization and the published bundle before claiming
that a poster was produced. No tracked source/config/prompt/test file was changed.

### Fifteen peer layout families (2026-10-21)

The user authorized three additional families: `framed_multicolumn` (shared
opening, two/three body columns, shared conclusion), `narrative_evidence_grid`
(narrative rail, local evidence grid, shared conclusion), and
`central_evidence_band` (upper columns, full-width middle evidence, lower columns).
All fifteen registered families are enabled together. There are no priority
tiers, default/special pools, new eligibility gates or implementation preference
based on the order of prior recommendations. The existing coverage-first policy
and shared bounded semantic bonus remain; peers does not mean identical
paper-match weights. The default bounded family retry limit now covers all 15;
geometry/beam/model-repair budgets and scientific/physical gates are unchanged.

New geometry callbacks in `src/layout/family_geometries.py` use the existing
registration interface; shared search still owns seeded sampling, compilation,
repair and checks. `FamilyContract.reading=framed_columns` reads each full-width
region in vertical order and completes intervening columns (including local
splits) before the next spanning region. A middle hero does not gain a
result-first exemption. Conditional content roles use the existing Planner-hint
mechanism, never invent sections or certify semantic relationships. All fifteen
PNG/editable-PPTX skeleton pairs live in `resource/layout_families/` and remain
inspection assets, not cross-poster learning. Original family registrations and
standalone classic behavior are preserved. Existing new-format runs retain their
frozen pool and refuse changed code/settings on resume; this development does
not migrate old runs or start model generation.

## Historical version boundary (superseded where noted above)

On 2026-10-14 the user requested restoration of **all tracked files to
`c3b1038`**, retaining `0d7de7a` and `a084cd2` in history under rollback commit
`b5f0947`. The rollback commit tree is identical to c3b1038; subsequent active design
policy changes are documented below. Module consistency is
withdrawn, not merely disabled: no prepare/final
semantic stages, membership guards, automatic association repairs, added source
image calls or semantic admission blocks remain. Critic at that rollback was
**4.3.0 / rubric v5**; current reading-policy scoring is versioned below.
Existing ClaimVerifier/editorial checks, twelve-family layout, capacity repair,
spacing, measurement reuse and complete rendered-text matching remain intact.
This exact rollback also restores Curator's five-word title truncation and
least-populated-module fallback for omitted claims; it does not retain selected
changes from the withdrawn commits. These legacy behaviors and caption-based
classification are not a guarantee of correct image/module relationships.

The archived report at `docs/reports/archive/MODULE_CONSISTENCY_REPORT.md` and the
implementation entries below are historical, not active architecture. Local
ignored reports/this guide differ intentionally from the target to document
withdrawal. Papers, posters, Campaign/Batch progress, templates, design memory
and abandoned attempt diagnostics remain unchanged. Existing Campaigns have no
committed semantic-blocked iterations. The latest paper's Batch 2 remains
PAUSED at 5/100, with I5 committed after the rollback; this design-policy task
did not advance it. Restart must use a fresh process; code changes do not
launch a Batch or push to GitHub. Reintroducing the withdrawn feature requires
explicit user agreement after observations across more papers.

## Exact rollback to bab9907 (2026-10-20)

The user explicitly requested that the project match commit
`bab9907fb0a6c4704c7ff5c93a17395d7d117ebf` exactly and abandon later changes for now.
ALL tracked paths, bytes, file modes and deletions are restored to that tree.
Later commits ff6d2b7 and 9488498 remain in Git history but their implementations
are withdrawn from active code, including uncommitted selection-review edits.
The target's tracked HTML file is restored too; do not preserve the former local
deletion as a design-policy exception after this rollback.

Current policies are those in bab9907: Critic 4.3.6 /
`academic_poster_multifamily_v10_structurefix`, paper_presentation_v3,
editorial_selection_v1, poster_editorial_v4, poster_body_v1, panel_ink_v1,
family_reading_v4 and multifamily_composition_v6. The v10 core-function auxiliary
boundary and shared pregeometry failure routing remain. Key-visual hard retention,
actual required-visual artifact/readability admission and editorial_selection_v2
necessity review/conditional contract are removed, not merely switched off.
Original verification, family fitting, completion, spacing, reading and renderer
checks are exactly the target implementation. Do not claim that the withdrawn
visual guarantees or newer necessity protections still apply.

All paper/logo/output files and Campaign/Batch/Lineage/template/knowledge records
are preserved. No Batch was launched, resumed, reset or advanced. Stored budgets
and terminal states stay authoritative; code restoration does not make a failed
Batch resumable or prove a newer saved input compatible with this older policy.
The process was already stopped before restoration. No model service was called.

The rollback is recorded by a new atomic commit whose TREE equals bab9907, without
rewriting history. Local ignored AGENTS/report notes document withdrawal and are
not part of the tracked-tree identity. Former experiment report sections are
preserved at [the inactive archive](docs/reports/archive/POST_BAB9907_EXPERIMENTS_REPORT.md).
The public README is restored byte-for-byte to the target, without rollback edits.
The pre-rollback uncommitted patch and documentation backups are retained in
`/tmp/postergen-rollback-bab9907-20261020-112240/`.

## Auxiliary function boundary and shared failure routing (2026-10-19)

This supersedes the earlier setup-majority-only auxiliary classification and
Explore's family retry for unrestricted pregeometry ownership failures.
Presentation policy is `paper_presentation_v3`. Other source/selection/reading,
editorial/body/emphasis and composition versions remain unchanged. Critic is
4.3.6 / `academic_poster_multifamily_v10_structurefix` (information/narrative 1.5.1,
layout-family 1.2.1). Weights, hard physical/scientific gates and 78 admission stay.
Historical scores and artifacts are not relabeled or rewritten.

`auxiliary_assessment` in `src/layout/presentation_policy.py` checks visible core
roots against their ORIGINAL verified-source Planner function before using setup
counts. A problem definition/objective or substantive method/result core can
coexist with many supporting settings. A primary label or foreign core ID alone
cannot exempt routine data; grounded dataset centrality and compatible ownership
remain required. A complete source-compatible task definition can also survive a
wrong supporting-purpose hint. Explicit mixed data/method supporting groups still
use claim-level attribution. Unknown functions stay uncertain; these hints are
not an independent semantic/image-association judge. Classification reasons and
protected IDs are text-free diagnostics. Old unlocked v1/v2 preparation stamps
are recomputed; same-root variants use original provenance. Strict locks remain.

A pregeometry unresolved ownership failure records `failure_scope=shared_content`
only for unrestricted shared preparation. Grouping-disabled family contracts and
pinned ownership record `family_constraints`; post-search failures never acquire
shared scope. Explore stops after a genuine shared failure with
`shared_presentation_structure_unresolved`, preserving its reports and abandoning
only that attempt. It does not exclude a family, retry another Curator, call
Critic, spend a committed Batch iteration, save a rejection or publish knowledge.
Staged content memory is restored; a concurrent user graceful stop still pauses
normally. Reading/height/exact failures, Improve and strict Validate retain their
existing retry/recovery/locked semantics. No new model round or automatic content
rewrite is added, and no geometry/space/font/figure/gap gate is weakened.

All twelve families and future shared-interface registrations inherit the fix.
Classic remains three unsplit/unspanned regions; independent standalone behavior
stays unchanged. Batch presentation v1/v2 upgrades to v3 only on an authorized
resume, preserving frozen pools, budgets and history. Replay policy drift is
rejected. Known shared failures remain distinct from programming exceptions;
a genuinely ambiguous content structure still fails closed rather than guessing.

## Shared poster expression and visible emphasis (2026-10-19)

This supersedes the closed visible-label and white-tint-only portions of earlier
editorial entries. Current policies are `poster_editorial_v4`, `poster_body_v1`
and `panel_ink_v1`; paper/source/selection/reading and exact scoring versions stay
unchanged. Critic is 4.3.5 / `academic_poster_multifamily_v9_expression`, with
information/narrative 1.5.0 and color quality 1.1.0. Weights and the 78 gate stay.
Historical rubric scores/bases are never relabeled.

`src/layout/body_presentation.py` separates internal discourse kinds from optional
visible cues. Curator's existing loop call chooses plain/topics/steps and local
extractive `display_label` phrases (max 64 characters/six words), plus genuine
step indices. Empty cues are valid. Unknown, foreign, title/opening-duplicate,
repeated and assertion-bearing cues are suppressed. Same-root replacements,
subsets and grouping recheck the exact current sentence; incomplete/reordered
steps lose numbering. Existing dependency closure and 0.30-inch supporting
indentation stay. No extra semantic/image association stage, label quota,
sentence minimum or module-count rule is introduced. Model-provided procedural
relationships remain hints, not independently proven scientific chronology.

A shared paragraph description supplies visible text, label bold runs, prefixes
and indent to fast/exact measurement and FontAgent. Cache identity includes its
styles. Scientific sentences stay exact verified strings; label styling is
separate from exact-word keyword emphasis. Final Preflight/RenderFit, space and
same-attempt rollback remain mandatory. Historical v1-v3 locked boards keep their
original labels, and strict Validate/exact fallback skip new automatic editing.
All twelve families and extensions use this path; classic stays three unsplit,
unspanned zones. Standalone classic prompts/geometry remain separate.

`src/layout/emphasis.py` jointly selects a visible theme panel and darker text/
accent ink with bounded deterministic candidates. Both white and chosen-panel
text contrast satisfy the configured minimum (normally 4.5). Panel/canvas ratio
1.12 is a configurable design heuristic, not a WCAG requirement. The panel remains
light (candidate canvas ratio at most 1.65). ColorAgent resolves new unlocked loop
palettes; pure fitting can additionally carry module-local resolved inks without
mutating state. Compiler, FontAgent, Renderer and ColorQuality use actual colors.
Unsafe pairs explicitly disable emphasis, including stale backgrounds. The color
evaluator checks actual styled color runs where available and reports faint
panels; no new aesthetic hard gate or score weight is introduced.

Loop ClaimWriter guidance favors direct, information-rich research prose while
retaining mechanisms, conditions, comparators, uncertainty and attribution.
Existing frozen foundations stay immutable. An INTERNAL `create_style_variant`
action (not a new RevisionPlanner permission) requires an allowed visible claim
in the explicit current board. Existing verified `poster_prose` variants are
preferred and reverified without modifying/reappending their bank record. New
variants pass full ClaimVerifier plus the existing excerpt audit requiring
all meaningful source information and `style_improved=True`. Unlike compaction,
style edits may keep length or grow within max(40, floor(1.15*N)+20) characters.
Ordinary compact variants still must shorten. One quality round and at most two
different-module actions share existing global/family budgets; no extra free
model stage is added. Excluded/disabled roots and locked modes remain protected.
Exact same-owner fit and content/global-space guards gate adoption; failed edits
leave banks unchanged and downstream failures restore the same attempt baseline.
Remaining wording hints and verification/budget stops stay explicit. Finite
budgets cannot guarantee that every old sentence will be rewritten.

Batch upgrades record the new editorial/body/emphasis identities on an authorized
resume while preserving pools/budgets/history. Replay inputs bind all three and
refuse drift. Development does not resume/advance a Batch. Local reports and this
guide remain ignored; the user-owned HTML deletion remains unstaged.

## Source-aware editorial selection (2026-10-19)

This supersedes the v1 merged-source retention rule above. Shared policies are
`paper_presentation_v2`, `poster_editorial_v3`, `family_reading_v4`,
`editorial_selection_v1` and `body_context_v1`; exact scoring is
`multifamily_composition_v6`. Critic is 4.3.4 with the distinct
`academic_poster_multifamily_v8_selection` rubric (narrative 1.4.0, family 1.2.0).
Weights and the 78-point gate remain unchanged. Historical scores are not relabeled.

`utils/source_context.py` locates verbatim evidence in the original Markdown,
records body hierarchy and character spans, identifies structural numbered floats
and restores the parent context when prose resumes. Ambiguous/missing evidence
stays unknown; page is retained only when supplied. The overlay does not alter
original source IDs, excerpts, claims or frozen foundations. Attempt replay saves
the overlay and refuses incompatible source/selection policy versions.

NarrativePlanner/Curator make necessity decisions in their existing calls. The
board owns an ID-only editorial-selection contract, separate from the complete
scientific bank: required, optional reserve, and explicitly omitted information.
Required contexts/prerequisites are closed before sanitization. Accidental
unclassified omissions remain reserve, never automatically become source modules.
Only confirmed necessary merged roots are mandatory; every merged source is no
longer automatically required. Same-root verified variants remain possible.
Curator, exact subsets, source_for_fit, completion/recovery and Critic honor these
choices. Source search masks omitted source paragraphs; this is conservative and
can also exclude useful adjacent detail in that paragraph. No new semantic judge
or withdrawn image/module association stage is added.

Auxiliary attribution uses body context and claim function before distance, can
split mixed source groups by existing IDs, retains per-owner root/source mappings,
and refuses cross-owner prerequisite splits or mergers across unrelated stages.
Dataset novelty alone cannot justify an independent module; a central subject
requires grounded explicit Planner metadata. Coherent adjacent context/task
framing may group across legacy roles; substantive research insights remain
separate. Mixed display roles retain their original role provenance.

One optional context composition shares existing geometry/beam seats. Exact
selection uses a measured whitespace Pareto reference, independent of scalar
content score. Refinement also searches shared x boundaries with conserved outer
edges/gutters and hero prominence. Existing four global/two family/two-action
model budgets, quality reserve, eight free restores and two-by-four geometry
refinement limits remain. Required roots, pins, topology, exact preflight, fonts,
image proportions, spacing and same-attempt recovery stay protected. Strict
Validate/exact fallback and standalone classic keep their locks/legacy behavior.
Classic loop geometry remains exactly three unsplit/unspanned zones.

All twelve families share this path. New LayoutFamily registrations must now
explicitly choose a boolean allow_module_grouping policy; omitted declarations
fail registration rather than silently bypassing grouping. Known old Batch
policies upgrade on an authorized resume, preserving family pools, budgets and
history. Development itself never resumes/advances a Batch.

Validation and own-I10 export evidence are recorded in the existing capacity
report. Local Markdown remains outside Git. The unrelated user-owned
`excavator_loading.html` deletion must remain unstaged.

## Historical active pipeline (Campaign architecture retired 2026-10-21)

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
Loop-family layout optimization now owns one bounded measurement context per
LayoutWithBalancerAgent call. It reuses exact heights, estimated lines, wrapping,
glyph sizes and fonts across the initial fit, repair refits and final compile,
then releases them on every exit. Context/cache/callback objects never enter
PosterState or persisted scientific/Lineage snapshots. Measurement reuse itself
does not reduce search budgets or relax gates; the independent classic route
does not enter this context. See `docs/reports/LAYOUT_PERFORMANCE_REPORT.md` for rollback and limits.
Loop spacing policy now shares title measurement/render typography and checks
final FontAgent typography before rendering. Directional adjacency and visible
bottom-edge audits expose cross-zone gaps that same-zone stacking missed.
After feasible selection, Explore/Improve may run at most two rounds of four
family-legal shared-boundary candidates per fit call, reusing that same context.
Only content-preserving, globally non-regressing exact gains are adopted.
Validate fixed topology and exact-parent fallback skip this refinement.
Confirmed rendered title failures may receive one geometry-only correction and
re-render after full preflight; locked modes never make that correction.
An inconclusive correction cannot erase a previously confirmed failure, and
unadopted trials cannot overwrite current reports. Compiled fit composition
and rendered-glyph composition remain separate comparison/audit fields.
Critic 4.3.1/reading-v2 retains cross-zone/bottom spacing feedback without changing
weights or the 78-point threshold. See `docs/reports/LAYOUT_SPACING_REPORT.md` for scope,
historical replay results, costs and version isolation.
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

## Shared family design policy (2026-10-14)

All twelve families now declare `FamilyContract` v2 in their registrations: reading
traversal, required IDs, fixed topology IDs, split/span/mirror permissions,
conditional role constraints, sequence/peer checks and geometry strategy.
An extension may provide a deterministic `geometry_generator`; generic legal
boundary/split/span/mirror candidates otherwise work without new shared-family
branches. Enable new IDs in configuration for a new Batch; existing frozen
family pools are not silently expanded. Classic retains exactly left/middle/
right and never splits/spans. LayoutSpec remains schema v3.

`src/layout/design_content.py` provides bounded root/evidence/core/role hints,
four beam portfolios and actual reading flow; unknown roles cannot certify
scientific order. Core annotations are sanitized Curator priorities, not locks
on immutable wording. Same-root verified compaction and grounded additions
remain available through the existing optimizer/verifier. Loop titles preserve
complete wording; standalone classic still truncates to five words. Exact
refill accepts measured zero-height additions and compact original modules,
prioritizes missing core information, and reports thin modules. At most two
measured swaps improve linear reading flow; explicit Improve reading requests
must change real zone ownership and obey pins/role/capacity constraints. Locked
Validate/exact fallback skip reading changes. Geometry preflight remains final.

`src/layout/repair_budget.py` charges before content-model calls into each
attempt's `model_repair_budget.json`. Total stays four rounds, one reserved
from capacity work for quality. A second infeasible repair requires measured
search progress; no-call attempts spend nothing. Charges survive abandonment,
force-stop and restart, are never refunded, and remain separate from committed
Batch iteration accounting. The Batch freezes design-policy/budget metadata;
legacy runs upgrade explicitly without rewriting history. The quality round
runs on an exact feasible fit; final FontAgent preflight/render audit remain
mandatory and can still reject it. Visual-restoration budgets remain separate.

`src/layout/attempt_inputs.py` writes an immutable digest-bound fit input per
attempt, with scientific board/banks, measurement config and font/dependency
identities, never model clients/secrets. It is a local diagnostic, not knowledge
or a committed poster. The existing benchmark CLI can replay it and refuses
drift. Failure reports remain text-free and distinguish bounded search failure
from exact compile/preflight failure; successful reports include contract,
`design_policy_version`, `content_quality_hints` and scoring v4. Planner receives
these hints/repair outcomes; reading-policy scoring is versioned below, while
weights/admission and scientific grounding remain. No module/source association
semantic feature returns.
See `docs/reports/CAPACITY_REPAIR_REPORT.md` for validation and limits.

## Shared module completion and layout protection (2026-10-15)

Design policy `grounded_family_design_v2` completes thin/sparse modules through
the same path for all registered loop families, including future extensions.
`utils/module_content.py` derives retrieval context exclusively from the explicit
current board's verified/curated roots, evidence and originating narrative/source
sections. It never borrows another attempt's board. Root/evidence/title metadata
are retrieval hints, not a restored module-semantic admission feature.

`src/layout/module_repair.py` diagnoses original-root reductions (including a
surviving core root), consecutive short text-only stacks and exact sparse zones.
Compiled textbox-height hints supplement text length. There is no minimum
sentence count. A per-module fair queue restores up to eight omitted original
base claims without model calls, then uses existing verified alternatives,
same-root compact restorations, evidence additions and bounded source search.
Existing four global/two family/two-action model limits and the quality reserve
remain; charges are durable and precede calls. Used evidence may contain useful
unexpressed details, subject to full ClaimVerifier/editorial checks. Explicit
root exclusions, disabled content, other visible text and source grounding are
protected. Unresolved modules and stop reasons remain in the repair report.

Completion first pins geometry, module ownership, stacking and visible content.
One optional same-family fallback permits at most two geometry/two exact
candidates; strict Validate stays fixed and exact-parent fallback skips repair.
No module is automatically removed or merged. Every trial passes exact fit and
compares all zones/global holes against both the last adopted and original
baseline: 0.005 fill/fraction and 0.05-inch gap tolerances. Information gains need
not increase height. Existing typography, title spacing, image proportions,
render checks and Critic's weights/78-point admission remain intact; the current
reading interpretation/rubric identity is documented below.

`src/layout/module_recovery.py` and the design node runner own one runtime-only,
attempt-identified completion baseline. Final preflight/render failure,
partial/unavailable rendered text coverage or final compiled space regression
restores board/banks/selection/contracts/spec/reports together and reruns normal
preflight/render once, reusing deterministic keyword styling. Unknown generation
exceptions stay errors. The baseline never enters persisted scientific/Lineage
snapshots and is removed at the design boundary. This fallback does not certify
unmeasured aesthetics or repair a genuinely infeasible original layout.

Resuming design policy v1 records an explicit v2 upgrade while retaining frozen
family pools/repair budgets and historical commits. Development does not launch
that resume. The standalone classic route and classic split/span prohibition
remain unchanged. See `docs/reports/CAPACITY_REPAIR_REPORT.md` for validation,
the I5 same-attempt read-only audit, finite-budget limitations and final commit.

## Shared reading-flow correction (2026-10-15)

Reading policy `family_reading_v2` is shared by Solver and InformationNarrative
Critic through `src/layout/reading_flow.py`. It normalizes explicit Planner
roles (including insight, implications, discussion and aliases), ignores unknown
roles as ordering proof, and uses physical zone traversal/module stacking rather
than accepting a reordered metadata list. Anchor-first/spine families assess
each hero separately and check the remaining body; comparison branches and
matrix cells are independent sequences. Neutral extensions retain their order.
All registered families/extensions use the contract, with no family-ID branches.

The existing editorial beam now retains an order-focused path and processes
classified narrative roles early; wholly unclassified inputs retain their old
priority search. Exact fitting
tries bounded whole-body ordered partitions before and after grounded refill,
at most 128 search states per phase/256 per exact candidate. Visible modules,
claims, visuals, topology, geometry, fonts, hero ownership, pins and conditional
roles remain protected; every adoption still compiles and passes preflight.
Refill/restacking cannot introduce a known flow regression. An automatic,
unlocked candidate with a remaining inversion reports `READING_ORDER_UNRESOLVED`
and follows ordinary fit retries without Critic or Batch iteration consumption.
This is bounded search failure, not proof a family cannot fit. No content-model
call is made to treat this pure order failure. Strict Validate, exact-parent
fallback and explicit Improve reading requests preserve their existing locks;
their actual order remains observable to Critic rather than silently rewritten.
Exact selection now applies existing whole-poster whitespace non-regression
against the highest exact-score candidate before core preferences/diversity.
`selection_whitespace_guard` records the reference and candidate counts; scoring
identity is `multifamily_composition_v4`. This prevents a core preference from
selecting a substantially emptier fit among already ordered candidates. It is
not a comparison to another attempt's scientific board or historical poster.

This reading-policy rollout used **4.3.1 / academic_poster_multifamily_v5_reading_v2**,
with InformationNarrative evaluator 1.1.0; the editorial release below supersedes
that scoring identity. Only reading interpretation changed in that rollout; weights,
78-point admission and scientific verification remain. The distinct rubric
prevents old best/promising scores/feedback being relabeled; pure Improve may
need a compatible new-rubric base. No withdrawn semantic association stage
returns. Design policy stays `grounded_family_design_v2`, with an explicit
`design_optimization.reading_flow` record/legacy resume upgrade preserving frozen
family pools and model budgets. Replay input records reading-policy identity
and refuses drift. Development does not perform that resume or rewrite history.
See `docs/reports/CAPACITY_REPAIR_REPORT.md` for I6/I7 evidence and limitations.

## Shared poster editing (2026-10-16)

`src/layout/editorial.py` implements `poster_editorial_v1` for the optimization
route. Grounded Curator prepares extractive short complete titles, local claim
function/order/dependency hints and optional labels/supporting entries BEFORE
layout search. Settings-first and takeaway-first modes are supported; unknown
relations remain flat. Scientific claim sentences are never replaced by display
text. Required local contexts survive subset selection, mutual-dependency groups,
verified same-root variants and final exact checks. Loop omissions follow their
original narrative claim source rather than the shortest unrelated module.
Standalone generation keeps its separate legacy behavior.

Title extraction normalizes source-title/body case consistently, so a dataset
subset can recover its broader source heading after useful method detail returns.
Strict Validate and exact fallback also skip title/order edits during fast and
exact measurement, including the exact helper's `allow_changes=False` mode.

Newly active presentations retain at least one verified root from each available
important Planner research phase (context, method, results, implications), using
core preferences when available. This retains current-plan information, not a
semantic module membership judgment or fixed module count. Existing extra-subset
seats include compact late-core claims with prerequisite closure; no search/model
budget is enlarged. Unknown/supporting roles cannot invent required phases.

At most two extra exact editorial trials per fit can restore useful original
base claims and combine one adjacent thin same-role pair within its current zone.
Every visible root/visual and occupied zone survives; original source/module
identities remain recorded. All twelve contracts explicitly enable content
module grouping, independently of geometry split/span. Extensions default to no
regrouping until `allow_module_grouping=True`; ordinary editing stays shared.
Classic still has exactly three unsplit/unspanned zones. Strict Validate and
exact fallback skip editing; Improve preserves pins, importance and contracts.
Completion remains locked to its adopted modules and owners. Rich presentation
that would overfill an old dense zone can fall back to flat exact sentences.
Per-zone/global whitespace and ordinary exact preflight remain mandatory.

One visible core/hero module may receive a light theme background. A bounded
white tint preserves configured body/highlight contrast without recoloring text;
unsafe or missing palettes do not create emphasis. Renderer and color evaluator
use the actual chosen background. Bold closed-vocabulary labels and real 0.30-inch
supporting indents participate in shared measurement; ordinary text is not
measured as all-bold. Font/glyph/wrapping reuse stays in the attempt context.
`EditorialFitResult` is a three-item tuple with an optional runtime-only baseline:
pure fitting never mutates state or stores prose in its report. Only adopted
orchestrator/repair results install the existing same-attempt rollback, including
source-visual ownership. Unknown errors remain generation failures.

Old review-style wording may use one charged quality round with at most two
existing compact actions, respecting disabled optimization and the global/family
budgets. Full scientific/editorial verification, root preservation, exact fit and
space guards are required before publishing; frozen scientific foundations stay
immutable. Budgets or failed checks can leave wording unchanged, with explicit
audit reasons. Concision must retain important information, intelligible
explanation, conditions, comparisons, uncertainty and limitations; no filler,
minimum sentence count or forced module count is introduced.

ClaimWriter's direct-voice instructions affect newly built foundations. Existing
Campaign foundations stay immutable on resume; old wording changes only through
verified optimizer variants, while the shared display preparation still applies.

Batch `design_optimization.editorial`, attempt replay inputs and fit reports
record the independent policy. Resume upgrades preserve frozen family pools,
repair budgets and history; replay refuses old/missing editorial identities.
Critic **4.3.2 / academic_poster_multifamily_v6_editorial**, narrative evaluator
1.2.0, accounts for within-module organization and actual emphasis backgrounds.
Weights/78 and scientific gates remain unchanged. Historical rubric scores/bases
are never relabeled; pure Improve needs a compatible base. The rubric ID stays
within the existing 48-character snapshot filename limit. No withdrawn semantic
module/source association feature returns. See the existing capacity report for
validation, actual same-input replays, visual limits and the task commit.

## Shared paper structure and focus (2026-10-16)

`paper_presentation_v1` in `src/layout/presentation_policy.py` is shared by every
registered optimization family and extension. Before fitting it groups up to
four routine auxiliary data/setup/metric modules into compatible method or
evaluation owners, retaining all verified IDs, text, roots, assets and original
module/source identities. A grounded dataset contribution or central scientific
subject may stay independent. Discourse/source hints establish the distinction;
there is no title blacklist, minimum sentence count, filler or new semantic
model admission stage. Extensions inherit the checks; automatic regrouping still
requires `allow_module_grouping=True`. Constraints and strict locks forbid silent
regrouping. Classic still owns exactly three unsplit/unspanned zones.

Contracts separate `focus_roles` from exceptional `entry_roles`. Ordinary large
or central regions must include important paper content and cannot be assigned
background merely because it is long. Companion method/results/interpretation
modules can share a wide region while at least one primary root remains there.
Fast search, exact repartition/refill and final audit share the rules. Subset
selection cannot leave a regrouped method as only its supporting facts.
Merged context groups also retain a usable core root (original roots when no
core is annotated), with same-root wording freedom and explicit exclusions /
disabled roots respected. Compact core-subset seats include that context closure
inside the existing nonprefix budget. An intermediate I10 counterfactual exposed
complete loss of data/setup after merging; it is diagnostic only, not the final
validated result. No sentence minimum or scientific dependency is invented.
Unresolved structure fails the known fit attempt with text-free diagnostics;
structure-only failures never request content-model capacity actions. Final
unlocked preflight and the LayoutFamily Critic hard gate prevent score-based
admission. Locked Validate is observed and can be rejected by Critic; exact-parent
fallback remains a no-change recovery, never a newly accepted poster/template.

Reading policy `family_reading_v3` prefers primary paper-body source order,
excluding abstract/related-work previews as ordering anchors, with legacy roles
as fallback. Source order is derived on copies for old immutable foundations;
new loop Planner output records its provenance. Unknown sources keep their slots
and cannot certify chronology. Physical traversal remains down columns then
across, or top-to-bottom bands; comparison/matrix branches remain independent.
Ordinary central heroes/spines no longer imply reading-entry exemptions.
Only explicitly declared finding entries separate the hero from the ordered
body; their measured "Key finding" title cue is idempotent and skipped by locks.
All twelve registrations, including mirror traversal, use the shared contract.

Internal completion pins/required claims now apply in Explore as well as Improve.
Reduced/consecutively thin modules receive model priority over complete sparse
backgrounds even after failed free restorations. Rejected additions identify
ownership, stacking, proposed-ID and visible-content violations separately.
Existing durable repair budgets, exact geometry/typography/image/spacing checks,
per-zone/global whitespace guards and same-attempt rollback stay in force.
No attempt borrows another attempt's content board. Standalone classic is outside
this policy and retains its independent generation path.

Editorial policy is `poster_editorial_v2`, composition scoring v5, and Critic is
**4.3.3 / academic_poster_multifamily_v7_structure** (narrative evaluator 1.3.0,
layout-family evaluator 1.1.0). Weights/78 and scientific verification are unchanged.
Batch resume explicitly upgrades known reading-v2/editorial-v1 policies and adds
presentation metadata while preserving frozen family pools/budgets/history.
Replay input includes derived source order and presentation identity and refuses
policy drift. Historical scores/best bases are never relabeled. Development does
not perform a live resume or advance a Batch. Validation, I10 own-input offline
findings and limits are recorded in `docs/reports/CAPACITY_REPAIR_REPORT.md`.

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
  - Critic system `4.3.6` uses rubric `academic_poster_multifamily_v10_structurefix`. It
    gates actual rendered body/title bounds/collisions, title-content minimum
    spacing and empty or severely unused loop zones. Cross-zone vertical and
    terminal-bottom whitespace affect SectionFit scores/feedback; weighted
    module-share overage remains advisory, not physical overflow.
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
  - Unknown IDs are removed; loop omissions return to a module with their
    original narrative source (or a recovered source module). Standalone keeps
    the legacy least-populated-module fallback. The loop keeps complete concise titles and sanitizes up to
    three original-module `core_claim_ids` as selection preferences. Standalone
    classic keeps five-word title truncation. There is no independent module
    semantic gate; new body wording uses the existing optimizer/verifier.
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
- `src/layout/title_metrics.py`
  - Loop-only `loop_title_v1` contract shares exact textbox margins, explicit
    1.20-font-size point line advance, bounded wrap/height reserve and minimum
    actual title-content gap (0.225 font lines, about 0.20 inches at 64 pt).
    It measures the allowed final font/hierarchy preset before compile; styled
    preflight rechecks final font, size, bold and width. Classic keeps its prior
    measurement and implicit paragraph line spacing.
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
    a family. Profile hints alone provide no semantic proof or scoring gate;
    source-backed module-consistency checks were withdrawn on 2026-10-14.
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
- `src/layout/composition_refinement.py`
  - Bounded same-family shared-boundary/gutter refinement after feasible exact
    selection, including spanning-to-card row groups. Keeps zone roles/IDs and
    outside edges, runs existing grounded refill/compile/preflight, preserves
    visible claim/visual IDs and global whitespace, and honors Improve contracts.
    Each fit call permits at most 2x4 extra exact candidates, not eight per whole
    iteration. Config is `composition_refinement`; fixed Validate and exact
    fallback skip it. Audit/provenance live inside the feasibility report with
    `search_scoring_version=multifamily_composition_v2`. No model coordinates or
    prose, font shrinking, figure stretching, or scientific rewriting.
- `src/layout/whitespace.py`
  - Measures compiled whole-poster composition from exact section rectangles:
    unallocated body fraction, largest contiguous empty rectangle fraction,
    largest cross-zone gap, and largest within-zone gap. Schema v2 adds separate
    horizontal/vertical adjacency, occlusion-aware projection corridors,
    cross-zone gap decomposition, visible content envelopes and terminal-bottom
    mean/max/full-width gaps/coverage beyond the outer margin. Glyph bounds
    supplement planned children only when uniquely matched; image frames are
    not pixel-content detection. New comparison fields require measurements on
    both sides, never manufactured historical zeroes. Geometry-only
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
    Schema-v3 repair audits include `fit_comparison`: material local zone-use or
    gap improvements may qualify even if the globally worst zone stays unchanged,
    but existing zones/worst fill cannot lose more than 0.005, visible content
    must survive, and global non-regression remains mandatory.
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
    Loop-policy titles are remeasured using final typography and minimum gaps.
    Internal correction trials use `persist=False`; only adopted geometry
    publishes its full preflight/revision reports.
- `src/agents/render_fit_audit.py`, `src/layout/render_fit.py`, and
  `src/layout/render_text_matching.py`
  - Loop-only post-render audit exports the candidate PPTX to a temporary PDF,
    uniquely matches editable body text and section titles without storing scientific prose in the
    report, and measures actual glyph bounds against planned boxes, canvas, and
    other modules. Confirmed overflow/collision retries Explore/Improve before
    Critic and without Batch budget; the first three such failed retries per
    iteration retain `render_fit_preview.png` beside the attempt report.
    Strict Validate sends the finding to Critic as a hard geometry issue.
    Partial/unavailable extraction is inconclusive, not a
    false hard failure. Schema v3/matching policy `editable_exact_fragments_v1`
    shares Renderer-visible body styling via `utils/text_formatting.py`, keeps
    titles literal, requires full normalized equality (not prefix coverage),
    and lazily extracts PDF characters once for unresolved merged/wrapped/split
    text. Disjoint character ownership, origin proximity, ordered line chains
    and explicit work/branch/payload limits preserve ambiguity protection;
    overflow glyphs are never clipped to planned frames. Short, missing,
    ambiguous or budget-limited text stays inconclusive. Reports/English logs
    expose title/body and title-gap coverage, per-ID methods/reasons, exclusions
    and timings without prose. Display formula images are explicitly excluded,
    not falsely verified; their editable prefixes are included. `passed=True`
    remains a compatibility "no confirmed issue", not an all-clear when status
    is partial/unavailable. Optional composition extraction failure cannot erase
    already confirmed text violations. No extra PDF export or Layout cache/search
    change is introduced. See `docs/reports/RENDER_FIT_MATCHING_REPORT.md` for scope and replay.
    The audit measures title-content gaps and visible
    composition. Explore/Improve can attempt one bounded title-height/flow
    correction and re-render after complete geometry/revision preflight; strict
    Validate and exact fallback cannot. Re-extraction lacking prior failure
    evidence stays failed (`RENDER_CORRECTION_UNVERIFIED`), while a renderer
    failure remains a generation error, not a quality rejection. Corrected state,
    files and fit diagnostics stay aligned; compiled and actual-glyph whitespace
    are stored separately. The standalone one-shot route does not run this audit.
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
- `src/layout/measurement_context.py` and `src/layout/text_fit_adapter.py`
  - Attempt-local ContextVar scope with per-bucket LRU entry limits and a shared
    32 MiB measurable UTF-8 text-payload budget, not a process-RSS ceiling.
    Keys retain exact text/width/style/precision, configuration digest and actual
    font-file identity. Mutable measurement results are copied; errors and
    file/config changes during computation prevent full-result caching.
  - A project-local TextFitter subclass reuses wrapping/glyph work while keeping
    the original binary height/font-size searches. Its private-API adapter is
    enabled only for verified python-pptx 1.0.2 / Pillow 10.4.0; unknown versions
    or interfaces use original fitting. Unexpected adapter bugs fail closed,
    never masquerading as ordinary layout infeasibility. Dependencies are not
    edited or globally monkey-patched.
  - `config/critic_config.yaml:layout_performance.enabled=false` restores
    original measurement computation on the next launch. `reuse_wrapping=false`
    separately disables the local fitting adapter. Runtime cache objects are
    thread-owned and cannot cross attempts, Campaigns or post-Font stages.
  - Text-free `layout_performance_report.json` records cache counts, bounded
    hierarchical substage timings, dependency versions and fallback/error
    status. Timing totals are inclusive, not additive. The latest output copy
    is best-effort on OSError; the report remains in memory for the ordinary
    Campaign attempt persistence. Successful commits, known fit retries and
    generation failures retain unique attempt copies. These diagnostics do not
    contribute to quality scores, scientific knowledge or snapshot identities.
- `src/layout/benchmark_measurements.py`
  - Read-only CPU CLI for saved-module original/cold/warm equivalence/timing or
    pure-Solver replay from complete explicit inputs, including Validate's fixed
    topology. It does not execute models, renderers or Campaign commits.
- `src/layout/spacing_audit.py`
  - Read-only saved-poster CPU audit using a temporary LibreOffice PDF. Prints
    JSON without updating source files, Campaigns, templates or old reports.
    Historical flat bundles without LayoutSpec require explicit `--layout-spec`.
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
- `utils/text_formatting.py`
  - Shared renderer-faithful styling/literal-escape grammar. Renderer retains
    compatibility method wrappers and unchanged style tokens, including legacy
    malformed/unclosed-emphasis behavior. Editable audit text is built per
    stripped paragraph with supported inline math; display images are counted
    separately. Do not replace this grammar with generic tag stripping or
    broaden the scientific revision contract as an audit convenience.
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
    Critic metadata. Rubric v5 adds directional cross-zone vertical/bottom
    scoring and actionable decomposition; unknown/no-adjacency evidence is not
    an all-clear. Template density metadata retains null/partial gap evidence.
    The seven dimension weights and 78-point threshold are unchanged.
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
  - Cross-zone whitespace feedback can request bounded zone-budget adjustment
    and useful grounded additions. Prompt guidance distinguishes structural
    gutter/unused capacity from within-zone stacking gaps, prohibits moving
    whitespace elsewhere, and does not demand a uniform bottom baseline.
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
    See `docs/reports/IMPROVE_REVISION_REPORT.md` for persistence and acceptance semantics.
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
  - Parent selection now requires a board containing a nonempty list of section
    dictionaries for every family, after existing classic compatibility checks.
    Missing/invalid boards report `lineage_storyboard_unavailable`; a valid
    same-Lineage alternate track remains eligible. Loading clears both current
    storyboard fields before selection and deep-copies only restored fields,
    so absent historical fields cannot retain another candidate's board.
    Failed loading leaves both boards empty and follows existing unavailable/
    recovery handling before design work. Shared scientific memory is untouched.
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
    layout_performance_report.json  # loop-only text-free measurement diagnostics
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
        layout_performance_report.json  # unique attempt timing/cache audit
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

Read-only saved-poster spacing audit (temporary PDF rendering, no models or
Campaign writes):

```bash
.venv/bin/python -m src.layout.spacing_audit --candidate-dir /path/to/candidate
```

For a flat historical accepted/rejected bundle missing LayoutSpec, append
`--layout-spec /path/to/original/content/layout_spec.json`. The command prints
rendered title/body issues, internal title gaps and composition metrics only;
it never rewrites the historical poster or report.

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

The active tree is restored exactly to bab9907. Its historical full CPU regression
was 868 passed plus five subtests (584.96 s). The withdrawn 914/959-test suites
belong to later commits and are not current coverage. This rollback reran 101
focused source/auxiliary/route/Campaign tests: all passed (11.29 s), with two
existing third-party warnings. Exact index/tree and tracked-worktree equality to
the target are checked separately; no model-backed generation was run.

Existing tests cover:

- shared poster editing across twelve families and a future extension, real
  Curator loop/standalone entry, exact scientific text, prerequisites/cycles,
  important research-phase retention, compact late-core options, same-zone
  source-preserving grouping, cached mixed-face measurement and actual indent,
  background contrast, locks, rollback and same-ID foreign-board isolation;

- shared physical reading traversal and canonical roles, legal hero entry
  points, independent comparison/matrix branches, unknown-role coverage,
  bounded exact repartition/pins/conditional roles, pure-reading failure with
  no content-model action, all twelve families/extensions, compact-three-column
  recovery, global whitespace selection before core preferences, and paused
  Batch reading-policy upgrade without model/budget consumption;

- shared per-module source retrieval after Curator regrouping, independent
  module queues, omitted-root restoration/compaction, disabled/excluded/visible
  root guards, used-evidence additions, all-family/extension repair, zero-height
  adoption, cumulative space regression and complete final-fit rollback;

- selected-Lineage board isolation for all twelve families and an extension,
  missing/null/malformed parent boards, independent copies, same-Lineage track
  fallback and pure Improve refusal before design/Critic or budget consumption;
- all twelve family contracts and unseen registered grammars through shared
  fit/compile/preflight; classic fixed regions, compact search recovery, root
  priorities, zero-height refill, real/pinned reading requests, complete loop
  titles, thin-module repair targets, restart-safe global/family model budgets
  and immutable replay inputs with secret exclusion;
- renderer-faithful body styling and literal titles, exact block/fragment
  coverage, merged/wrapped parallel titles, split paragraphs, display-image
  exclusions with editable prefixes, duplicate evidence/ambiguity, truncation
  and ordering failures, bounded extraction/search, actual overflow unions,
  lazy image-free PDF extraction and English coverage/reason diagnostics;
- shared loop title measurement/rendering, actual LibreOffice multi-line
  PPTX/PDF/PNG, final-font Preflight, minimum gaps, ambiguous repeated titles,
  one-time correction, geometry/contract rejection, inconclusive re-extraction,
  render failure, report isolation, compiled/rendered baseline separation,
  directional/occluded adjacency, bottom whitespace, local repair gains,
  shared row boundaries, strict locks and bounded refinement/configuration;
- attempt-local measurement equivalence (including all twelve families in
  Explore, parent-local Improve and fixed-topology Validate), exact cache keys,
  config/font invalidation, LRU/payload limits, zero-sized caches, version
  fallback, fail-closed adapter bugs, exception cleanup, copied-thread isolation,
  classic-route isolation and performance-report commit/retry/error persistence;
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

- Module source/visual consistency checks and automatic association repair
  were explicitly withdrawn on 2026-10-14. The rollback removed the feature rather than switching off its evaluator.
  The active code now adds grounded_family_design_v2 and family_reading_v2 on that baseline. Individual scientific
  verification remains, but correct figure/module grouping is not guaranteed.
  The old feature report and abandoned attempts remain historical evidence.


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
- Layout measurement reuse preserves the original computation instead of
  reducing the search. Three saved I2 modules showed equal outputs and roughly
  4.2–7.2x faster first measurements, but no complete model-backed iteration or
  multi-paper benchmark has validated whole-stage speedup. Stage reports will
  distinguish fast search, exact refinement, visual recovery and content-model
  repair on future runs. The private fitting adapter deliberately falls back
  after dependency upgrades; its cache payload budget is not an RSS hard limit.
- Spacing quality rules are a separate behavior change: cache equivalence now
  means on/off equality under the new rules, not equality to pre-fix layouts.
  Extra bounded exact candidates and occasional one-time re-rendering are real
  cost, not a zero-overhead guarantee. Saved I2's model-free recompile fixed
  title crowding and reduced mean extra bottom gap but retained local large
  gaps, now reported by Critic; no universal gap-free quality is claimed.
  Rubric v5 uses existing score/feedback version isolation; old best/promising
  ranks are retained historically, not relabeled. Pure Improve may be
  unavailable without a compatible new-rubric parent. Campaign/LayoutSpec
  schemas and original template structural scores/previews remain unchanged.
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

### Local implementation reports

- Topic reports live together under `docs/reports/`; keep `AGENTS.md` and the
  public `README.md` at the repository root. Existing report filenames and
  full historical contents are preserved. Resolve report references in this
  guide relative to the repository root; report-to-report links are siblings.
- Withdrawn feature reports belong under `docs/reports/archive/`, not among
  active topic reports. Preserve their full contents and explicit inactive
  status; update guide references and any relative links when moving a report.
  Archiving documentation never re-enables a withdrawn feature. These files
  remain local/ignored and do not require an empty Git commit.
- For routine changes, update this guide and its concise Recent Changes entry.
  Update an existing topic report when detailed evidence belongs there; create
  a new report only for a genuinely new topic needing durable detail, and put
  it in `docs/reports/`, never the root. No per-conversation report is required.
- Git ignores all Markdown files except the root `README.md`. Existing reports,
  this `AGENTS.md`, and the layout-family README have been removed from the
  index without deleting their working-tree copies. Do not stage them for a
  normal GitHub commit.
- New coding sessions in this same workspace can read the local `AGENTS.md`.
  A fresh clone does not contain it, so carry it separately if development
  moves to a new workspace. The root README is the public project explanation.
- This local-file policy is an explicit user exception to the Git traceability
  rule below: keep updating `AGENTS.md` after project changes, but exclude it
  from Git commits. Older commits may still contain these Markdown files; no
  repository history is rewritten.

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
- Before finishing, verify that the local `AGENTS.md` was updated and mention
  its update in the final handoff; it must remain excluded from the Git index.
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

- 2026-11-02: Fix editorial format recovery with typed field-only patches and sparse-wire diagnostic mapping; generator v33, same single format allowance. User explicitly requested focused-only validation:70pass; saved Fourier Layers failure replays successfully without live models.

- 2026-11-02: Restore current-route upstream Marker extraction and add one advisory, durable spelling pass; retain original/corrected texts and per-edit diagnostics without regional admission or additional raster OCR. Generator v32; see the current section above.

- 2026-11-02: Current editorial PDF extraction now selects native/raster sources
  by region with explicit diagnostics,rotation/crop handling,confidence/numeric
  checks and bounded OCR. Keep legacy strict extraction separate; fix early
  foundation-failure timing. Generator v31 invalidates old normal resumes.

- 2026-11-02: Separate current editorial allocated paint frames from real content
  bounds; share bounded measured space transfers across all15 families and both
  axes, with coupled donor budgets and original gutters. Remove duplicate exact
  row height reservation and tighten architecture/method/evidence core criteria.
  Generator v30; fonts, directions, finite requests and historical outputs remain.

- 2026-10-30: Limit explicit core backgrounds to two modules with global/owned-image
  color sources, durable palette receipts and renderer/scoring agreement. Use exact
  distinct aspect-derived widths for current-route initial image/text directions.
  Generator v29; legacy routes and historical artifacts remain separate.

- 2026-10-30: RenderFit v2 joins exact adjacent same-row PDF fragments from
  editable inline scripts while retaining glyph ownership, ambiguity/budget
  safeguards and actual overflow bounds. Saved HAGS replay improves11/12 to12/12
  without rewriting outputs. Validation is recorded above and in the existing
  RenderFit matching report.

- 2026-10-30: Freeze current editorial modules' initial image/text directions
  before capacity editing, persist the initial fit for crash-safe replay, and
  retain direction through sizing, compilation, readiness and publication.
  Generator v28; legacy routes and finite model/geometry budgets remain.

- 2026-10-30: Align current Rubrics writing guidance with upstream-style hierarchy
  examples, record actual capacity edits/measurements and preserve support around
  steps/formulas through shared rendering measurements. Generator v27; schemas,
  model policies, fixed visual ownership, three edits and final scoring remain.
  Validation details are in the current editorial-writing section above.

- 2026-10-30: Current editorial Curator fixes its selected figures/tables after any merge adaptation; reserve probes are removed. Core-method key preference and mandatory visible use preserve free family placement; capacity editing retains image ownership/order. Validation is recorded in the existing Rubrics report.

- 2026-10-29: Editorial generator v25 removes quality editing and draft preview;
  at most three measured capacity edits precede a geometry-bound freeze. Renderable
  overflow/bounds/overlap outcomes retain failed diagnostics and proceed through
  actual PPTX/PNG, final Critic and unclassified publication. No post-freeze title
  repair. Real runtime/integrity failures and classic/old source guards remain.

- 2026-10-29: Added `crocodile_cycling.html`, a standalone offline illustration
  requested for direct browser opening. Inline SVG draws a crocodile, two bicycle
  wheels, connected frame, handlebars and pedals; native SVG animation synchronizes
  wheel/crank rotation with precomputed two-link leg paths every two seconds.
  Inline CSS handles the responsive page and a static reduced-motion alternative.
  No JavaScript, external images, fonts, packages or network resources are required.
  Structural/resource/closed-loop checks and a system-librsvg static preview were
  verified; no actual browser was available for playback testing. This artifact
  is independent of the poster pipeline. Existing user edits and the deleted
  `excavator_loading.html` remain untouched; only the new HTML belongs in its commit.

- 2026-10-29: Added measured image-left/text-right composition for wide shallow
  family modules, shared by fast fitting and exact editable compilation, with
  vertical fallback and unchanged standalone classic. Focused 8-case suite passes,
  including real PPTX/LibreOffice RenderFit; no broad suite or model generation.

- 2026-10-28: Implemented spatially informed original-source Curator and patch-only
  Balancer, program-owned provenance/image binding and no-image capacity editing.
  Runtime acceptance and final tests remain pending; see current section/report.

- 2026-10-27: Repaired v13 combined Curator content omission and presentation
  recovery. Invalid optional cues clear with audit; missing indispensable meanings
  use existing charged content edits, allowing legal dynamic module additions.
  Structural format correction remains field-scoped; science/readiness stays strict.
  See the current section and existing Rubrics report for runtime limitations.

- 2026-10-27: Fixed v12 Rubrics Curator/Balancer presentation metadata and shared
  recovery after the actual failed Curator response. Program-owned ordinals and
  unused-label clearing retain prose/order; invalid topics labels use only the
  existing one shared field-scoped format correction. See the current repair
  section and existing Rubrics report for validation and acceptance limits.

- 2026-10-27: Repaired Rubrics original-PDF transcription and paragraph-ID source
  binding after real v10 narrative failure. Added strict native glyph/region and
  scientific-number conflict checks, embedded-CFF delimiter decoding, native asset
  captions, source/PDF/environment binding and adversarial CPU regressions. Classic
  branch and existing scientific/edit budgets remain independent. See the current
  repair section and existing Rubrics refactor report for exact validation limits.

- 2026-10-27: Implemented v10 original-section Curator/Balancer and direct source
  verification, complete Rubrics EvidenceBuilder removal, image-based natural
  reading inside existing edit/final Critic calls, variable modules for15families,
  final-text/asset binding and strict source-cache isolation. Full1077CPU tests
  +5subtests pass, final cache10pass, frontend/CLI pass,8089historical files intact.
  Synthetic offline full-run rendering is engineering evidence only; no real model
  acceptance was launched. See current source-editorial section and existing report.

- 2026-10-27: Final source-editorial plan revision2 incorporates visual LLM reading judgment within existing Balancer/final Critic, replacing the prior hard physical-route proposal. Planning only; execution awaits user confirmation. See the final proposal section above and docs/reports/RUBRICS_SOURCE_EDITORIAL_PLAN.md.

- 2026-10-26: Added v9 sample verdict schema enforcement, recovery inside the
  existing shared preparation allowance, source-grounded correction audit context
  and cooperative-stop propagation. Classic and scientific gates remain intact.

- 2026-10-26: Diagnosed the first v8 real failure as shared-percent-range
  formatting rejected by numeric matching. Added evidence-bound sample-only
  normalization across writing and edits; preserved scientific gates and
  prepared a fresh background sample for visual acceptance.

- 2026-10-26: Implemented the authorized v8 integrated sample editorial repair:
  contribution-focused selection, source/role-aware uncertain space estimates,
  visual rationale/reserves, synthesized writing and verified pre-freeze quality
  completion with durable budgets and explicit adoption diagnostics. Full CPU
  regression and new acceptance evidence are recorded in the existing report.

- 2026-10-26: User requested three distinct-family real samples using the strict
  Active Geospatial paper/evidence cache; fresh per-sample science, normal finite
  budgets and all publication gates remain. Runtime results recorded in the
  existing Rubrics report; no generation code or settings changed.

- 2026-10-23: Real /tmp-only engineering replay exposed preservation input echoes.
  Added a dedicated audit role/final response schema and distinct missing-verdict
  diagnostics without retrying or relaxing science. 49 focused tests and final
  908 tests plus five subtests passed. Same-ledger real module rewrites passed
  all checks and reduced exact height; whole-poster acceptance remains bounded
  by ordinary fitting. Detailed runtime result stays in the Rubrics report.

- 2026-10-23: User approved whole-module coordinated compaction after v5 real
  acceptance failed. V6 uses existing durable capacity rounds/actions, preserves
  canonical roots/required supported coverage/dependencies, and atomically rejects
  incomplete or unsafe batches. Added raw input-bound request journals, complete
  cited evidence for sample-body fallback, and exact normalized-style local probes;
  full exact layout/render gates remain mandatory. Final validation is in progress
  in the existing Rubrics report; no new successful poster is yet claimed.

- 2026-10-23: Implemented explicit module responsibility, deterministic obligation
  assembly and bounded original-unit support; replaced whole-plan correction with
  local patches; shared one preparation editorial allowance across planning/body
  recovery; added input-bound writing/verification journals and information-
  preserving, fully verified local body correction. Original science standards,
  layout budgets, inspection storage and historical outcomes remain intact.
  Real validation exposed an input-echo verdict and repeated long dataset checks;
  require boolean verdicts, supply exact original context for cited excerpts, and
  stop immediately with incomplete diagnostics after sample request/format failure.

- 2026-10-22: Hardened sample module planning after run_d7b03f0e308b4d0796ab failed
  in preparation. Preserve raw/parsed/rejected responses; report precise module/ID
  defects; complete only unique original provenance; allow one durable, restart-
  safe interface correction. No scientific/physical gate or layout budget was
  relaxed, no permanent old-cache bypass exists, and no real generation rerun.

- 2026-10-22: Implemented user-approved module-first sample prose plus diagnosed
  fit fixes on 3fff259. Sample preparation is research Planner → module Curator →
  module Writer → full exact-body Verifier/finalizer, with canonical multi-source
  provenance and explicit mandatory-assertion coverage. Conditional context refresh
  is bounded to one affected-module pass. Separate durable one-shot structural
  re-curation, no-op rejection, complete failure loads/pressure, fair severity
  repair targets, same-sample color reuse and explicit paper-only cache are active.
  Original optional key-visual candidates remain available through source-role
  mappings; auxiliary ownership gates still route shared failures before search.
  Core hints retain substantive results without changing condition-first order.
  Nineteen classic/family/render/measurement files/prompts are byte-identical to
  baseline; five historic paper foundations/55 asset references and final bundles
  passed read-only verification. Broad suite: 760 tests + 5 subtests passed;
  final affected-file suite: 158 tests passed. Synthetic editable PPTX/PNG and
  actual RenderFit 1/1 passed. Frontend build/CLI help passed. No Qwen/GPU paper
  generation, historical run continuation or data migration occurred. Generator v4,
  sample science/body/curation v2; dataset/storage v2/2 unchanged. Details and
  real-quality limitations are in the local refactor report. Atomic commit: `98fd690` (32 paths). This guide/report remain ignored.

- 2026-10-22: User-authorized slow/failing sample repair adds bounded, observable
  sample-only physical requests (900s response/15s connection, no SDK retry,
  at most one identified transient retry), immutable per-sample Curator reuse,
  and one existing-budget targeted revision preserving required content and
  prerequisite ownership/records. Soft content scale hints keep all science
  banks and gates. Exact sample fitting normalizes absent typography defaults.
  Generator v3 refuses incompatible run resume; classic and fifteen peer
  families remain. Validation uses saved inputs and one new Active Geospatial
  sample with only original paper/evidence cache, never old sample science.
  Final CPU suite: 709 tests plus 5 subtests; scale-focused pass: 91 tests.
  Final same-paper run run_e21b1e0136c044fbb0e5 produced one four-column poster,
  baseline score 88.97, all-score/unclassified bundle with inspection templates.
  92/92 physical requests completed without retry, final Preflight/RenderFit passed;
  total 25.85min with original paper/evidence cache. All 2961 historical files
  unchanged and GPU 5 clear. Atomic local commit: 3fff259 (23 paths); no push.
  Both real results and validation limitations are in the local report.

- 2026-10-21: User explicitly requested one real independent sample of Active
  Geospatial Search for overnight inspection. Launched the unchanged v2 CLI
  (`--samples 1`, seed 31, local-text/local-vision, 54x36) detached with local
  CUDA_VISIBLE_DEVICES=5. Run: `run_afa7c3a7f0af4932bc69`. Runtime supervisor/logs
  are under `storage/rubrics_samples/background/active_geospatial_20261021_171350/`;
  supervisor PID 231868, generation PID/process group 231869 at launch. Supervisor
  records exit.json, cleans only its own generation group after exit, and checks
  GPU 5 allocations without touching the GPU 3 model service. Previous Neural
  sample client had already exited; its artifacts/stale run projection remain
  untouched. No source/prompt/config changes, old Campaign continuation or Git
  commit of runtime data. Do not assume success until FINALIZED/run state and
  actual PNG/PPTX/template artifacts are checked.

- 2026-10-21: Tightened paper/science/display ownership for independent samples.
  Shared foundation now ends at EvidenceBuilder; each sample independently plans,
  writes and verifies science with bound immutable preparation checkpoints. Same-
  sample family retries reuse verified preparation; selection freezes after its
  own profile and ignores scores/retry outcomes. Added source-mutation, checkpoint
  identity, force-stop/resume and ID-collision guards plus final module provenance.
  Sample-only Planner/Writer prompts separate scientific units from display modules;
  sample Parser skips ABT while classic retains its call and original prompts.
  Dataset/storage v2 refuses v1 resume without changing readable historical data.
  All fifteen families and physical/scientific rendering/saving safeguards remain.
  Existing local refactor report and public README document per-sample preparation
  cost, compatibility and verification scope. No model/GPU run or historical job
  advancement occurred. Final-tree CPU suite: 694 passed plus five subtests,
  four dependency deprecation warnings (618.92 s). Final scientific/provenance
  focused pass: 140 tests; preparation/storage/API pass: 42 tests (overlapping).
  TypeScript/Vite and both CLI help checks pass. All 15 synthetic layout outcome
  digests match baseline, 12 core files are byte-identical, and all 2557 historical
  file hashes are unchanged. Atomic commit: `7bf32b2`
  (`refactor(workflow): isolate per-sample science preparation`), 24 paths.
  Local guide/report remain ignored; no generated data or model logs are committed.

- 2026-10-21: Added framed multicolumn, narrative/evidence grid and central
  evidence band as three peer families, enabling all fifteen in the same pool.
  Added bounded registered geometry callbacks and spanning-band/column reading
  support, updated preview assets and documentation, and extended shared
  physical/scientific fitting, selection and preview regression coverage.
  No tiered eligibility, historical-data migration or real model run was added.
  Validation: 106 focused tests passed; full CPU suite 674 passed plus five
  subtests (612.19 s). Original 12 registrations/seeded geometry candidates,
  all 24 old skeleton assets and 2557 historical file hashes are unchanged.
  Atomic commit: `f60a569` (`feat(layout): add three peer academic poster families`),
  17 paths; post-commit worktree clean. Local guide/report stay ignored.
- 2026-10-21: Replaced poster/Lineage/template evolution with isolated Explore
  sample generation for future Rubrics work. Removed Improve/Validate/mixed
  scheduling and all cross-sample learning/retrieval, preserved standalone
  classic plus Explore physical/scientific fitting and repairs. All final
  posters and actual local layout templates are saved unclassified in a new
  dataset, with atomic publication/recovery and exact run-ID resume. Historical
  data is retained and excluded. CLI/WebUI, tests and public README now describe
  this boundary; this guide stays local and ignored. See the new refactor report
  for validation and remaining scope. Final-tree CPU regression: 624 passed plus
  five subtests (455.96 s); TypeScript/Vite build and both CLI help/import checks
  passed. All 2557 historical file hashes match the pre-refactor inventory, and
  all twelve synthetic layout result digests match baseline. No real model/GPU
  generation or historical Batch advancement was performed. Atomic task commit:
  `a916e5f` (`refactor(workflow): generate independent Explore samples for Rubrics`),
  113 changed paths; post-commit tracked worktree clean. This guide and the report
  remain local/ignored as required.
- 2026-10-20: At the user's explicit request, restored every tracked file to
  bab9907, including current uncommitted changes and the target HTML. No later
  implementation is retained. Index tree equals target tree
  `66c41451134387fe2455e6f9599d821ba6017373`; 101 focused tests pass. Later
  implementation reports are archived/inactive; local guide/report are ignored.
  All 2,453 paper/output/runtime files remain unchanged. No model or Batch run.
  Uncommitted changes were backed up under /tmp before restoration. The rollback
  commit identity and final verification are recorded in the capacity report.
  Atomic rollback commit: `c83300f`, 40 tracked files; tree equals bab9907.

- 2026-10-20 [WITHDRAWN by exact bab9907 rollback]: Implemented editorial_selection_v2 necessity review, conditional
  prerequisites, root-safe variant decisions, and merged protection recalculation.
  Review shares existing model budgets; unresolved shared selection stops once
  without a family blacklist, Critic, committed iteration or knowledge. All
  current/future shared families inherit it; exact locks and existing physical,
  whitespace, scientific and critical-visual gates remain. Own-I13 seven-attempt
  offline fixtures retain the original four required visuals and all 424 Campaign
  JSON files; fixed manual necessity decisions still expose real capacity limits,
  not guaranteed generation success. Tests and scope are in the capacity report.
  Full CPU suite: 959 passed plus 5 subtests (717.03 s); focused source/selection/
  presentation: 111 passed; paused-Batch migration: 4 passed. No model service or
  live Batch was run. Local guide/report remain ignored and the unrelated
  user-owned HTML deletion stays unstaged.
  Atomic commit: `9488498` (`fix(content): review necessity without locking
  optional context`), 23 tracked files.

- 2026-10-19 [WITHDRAWN by exact bab9907 rollback]: Implemented critical_visuals_v1 across initial selection, revision,
  recovery, committed Campaign persistence, actual artifact auditing and Critic
  admission. Critic 4.3.7/v11 distinguishes reviewed image-free N/A from missing
  scientific evidence. Required figures/tables cannot be dropped for capacity;
  classic topology and all scientific/typography/spacing/whitespace guards stay.
  Own-I11 offline validation preserves figure_2 and all five result tables,
  exports editable PPTX/PNG, passes Preflight and RenderFit 12/12; actual source
  embeddings/PDF positions pass. The same six-item contract fails closed in
  comparison_split and fits classic_three_column without borrowing prose.
  All 367 Campaign JSON hashes and inventory remain unchanged. This manual
  contract exercise is not a new model decision, full Critic admission or
  scientific completeness/aesthetic certification. Full validation results and
  commit identity are recorded in the capacity report. Final fit/contract suite:
  80 passed (187.05 s), including every current/future registration, after
  deduplicating mandatory subsets without changing source asset order or budgets.
  No model or live Batch was run.
  Atomic commit: `ff6d2b7` (`fix(visuals): retain critical paper evidence through
  rendering`), 34 tracked files. The user-owned HTML deletion remains unstaged;
  this guide and the report remain ignored.

- 2026-10-19: Fixed I12's shared auxiliary-function boundary: source-compatible
  core definitions/objectives/methods/results survive setup-majority hints,
  ordinary data remain integration candidates, and old unlocked stamps are
  recomputed. Genuine unrestricted pregeometry ownership failures stop Explore
  once without blacklisting families, retrying Curator or spending committed iterations.
  Contract/pin/reading/exact recovery and strict locks remain protected. Policy
  is paper_presentation_v3; Critic 4.3.6 uses a distinct v10 rubric. Detailed
  regression and own-attempt I12 evidence are recorded in the existing capacity
  report. Focused suite: 194 passed, three dependency warnings, 100.30 s. All six
  own I12 boards pass preparation for all twelve families. Attempt 1's own two-
  column fit/export passes Preflight and RenderFit 12/12 (18 claims/six modules,
  worst fill .958082, largest empty rectangle .038127), without borrowing another
  attempt's board. All 367 Campaign JSON hashes/inventory remain unchanged.
  This is not full model-Critic admission or aesthetic/coverage certification.
  Development does not run models, resume a Batch or rewrite history.
  Final full CPU regression: 868 passed plus five subtests, four existing
  dependency warnings, 584.96 s. Local guide/report remain ignored; the unrelated
  user-owned HTML deletion remains unstaged.
  Atomic commit: `bab9907` (`fix(layout): preserve core functions and scope
  structure failures`), 10 tracked source/config/prompt/test/README files.

- 2026-10-19: Implemented shared optional extractive body cues and mixed-face
  presentation descriptions, direct-prose generation/verified style variants, and
  deterministic visible-panel/accessible-ink coordination. Added policy/replay
  identities and Critic 4.3.5 / v9_expression without changing weights, admission,
  model budgets, classic topology, strict locks or scientific/physical gates.
  Final full CPU suite: 815 passed plus five subtests, four existing dependency
  warnings, 575.62 s. Final protection suite: 83 passed, two warnings, 23.39 s.
  Own-I10 exact export passes 10/10 RenderFit and actual colors (4.663 accent/panel,
  1.2258 panel/canvas), with remaining space/allocation findings explicitly kept.
  Ten old palettes preserve their light panels; two darken accent ink. Two other
  papers' isolated body render fixtures pass 2/2 each, without claiming new science
  or whole-poster quality. All 281 own-I10 Campaign JSON hashes/inventory remain.
  Detailed validation and limits are in the existing capacity report. No live
  Batch/model/GPU work; unrelated HTML deletion remains unstaged.
  Atomic commit: `604b863` (25 tracked files); this guide and topic report remain
  local/ignored, with no generated data or historical artifacts in the commit.

- 2026-10-19: Implemented source-aware necessity/selection and claim-level
  attribution shared by all twelve families and future explicitly declared
  contracts. Added immutable source overlays, required/reserve/omit decisions,
  omission-aware refill/source search, coherent context composition, mixed-role
  provenance, weighted coverage and shared-x/space-reference improvements.
  Preserved standalone/classic locks, finite budgets and physical/render guards.
  Critic is 4.3.4 / v8_selection. Full suite: 778 passed plus five subtests,
  four existing warnings, 556.79 s; final focused suite: 190 passed. Own-I10
  original-board fit improves worst fill .654001 -> .912641, empty rectangle
  .164948 -> .048494. An explicit six-root/three-omission contract exercise
  retains sample/location conditions, integrates Dataset into evaluation,
  retains ablation detail and yields .041460 empty rectangle. Both exported
  cases pass 12/12 RenderFit with no overflow/overlap/title-spacing failures.
  Component visual scoring still has major allocation/space findings; this is
  not a claim of overall visual acceptance or new model-Curator validation.
  All 281 Campaign JSON hashes/inventory remain unchanged. No paid models,
  GPU or live Batch activity. See the capacity report for precise conditions,
  artifacts and limits. Atomic commit: `70b4e26` (30 tracked files);
  local Markdown and the unrelated HTML deletion remain outside that commit.

- 2026-10-16: Implemented shared paper structure/focus and natural source reading
  for all twelve families and extensions, with auxiliary preparation, retained
  merged context, cross-mode repair pins, explicit result-entry contracts and
  final structural gates. Preserved classic geometry, standalone generation,
  immutable foundations, strict locks, scientific checks, finite budgets and
  measured space/render protection. Updated README and the existing capacity
  report. Final full suite: 749 passed plus five subtests, four dependency
  warnings, in 408.07 s. I10 own-input same-family offline fitting/export passes
  natural flow, Dataset integration/context retention and RenderFit 12/12.
  A central bottom gap remains (worst fill .654001); eight free completion trials
  adopt no unsafe addition. This is explicitly not aesthetic acceptance or a
  guarantee of dense future posters. All 281 Campaign JSON hashes/inventory are
  unchanged; no model/GPU calls or live Batch advance. Unrelated user-owned
  `excavator_loading.html` deletion remains unstaged. Atomic commit: `43e017a`,
  25 source/config/prompt/test/README files; local Markdown stays outside Git.

- 2026-10-16: Implemented the approved shared poster-editing plan: short complete
  titles, information-rich structured prose, protected prerequisites, bounded
  same-zone module grouping and accessible core emphasis. Curator budgets
  presentation before fitting; legacy wording uses existing verification and
  repair budgets. Shared measurement and same-attempt rollback protect existing
  geometry/spacing/content; no live Batch or historical artifact is rewritten.
  Critic uses a distinct editorial rubric. Validation and commit are recorded
  in `docs/reports/CAPACITY_REPAIR_REPORT.md`. Preserved the unrelated user-owned
  deletion of `excavator_loading.html` outside this task's commit.
  Final frozen-source regression: 712 passed plus five subtests in 637.61 s;
  final editing suite: 45 passed. Own-input I8/I9 fixed-candidate revalidation
  and actual exports pass RenderFit 12/12 and 14/14 with no issues; all 260
  Campaign JSON hashes/inventory remain unchanged. Final visual inspection also
  fixed mixed-case title restoration and locked fast/exact title/order handling.
  Fresh search still leaves a material I8 right terminal gap; free completion
  adopted no unsafe additions. This is not a guarantee that fresh posters have
  optimal whitespace. No live/model-backed Batch was launched or resumed.
  Atomic task commit: `accaeb0`, 30 source/config/prompt/test/README files;
  local reports/AGENTS and temporary previews remain outside Git as required.

- 2026-10-16: Added `excavator_loading.html`, an independent offline SVG excavator/truck animation requested as a standalone HTML artifact. It uses inverse-kinematic joints, linked hydraulics, soil/dust particles, six-pass truck loading and truck exchange, with pause/speed controls. It is unrelated to the poster pipeline and requires no external assets.

- 2026-10-16: Completed the interrupted correction of Batch 3's reading-flow gaps through shared
  canonical roles, physical traversal, hero/body and peer-branch scopes, an
  order-focused beam path, early classified-role processing and bounded
  content-preserving exact repartition. Preserved compact three-column search
  and added a global whitespace envelope before core/diversity selection.
  Remaining automatic inversions fail as a known fit attempt; pure order failures
  do not spend content-model rounds. Critic 4.3.1 uses a distinct reading-v2
  rubric while weights/78 and scientific checks stay intact. Resume records a
  reading-policy upgrade; frozen family pools/budgets and old commits remain.
  Updated README and the existing capacity report. Validation and atomic commit
  are recorded in that report. Final focused CPU suite: 103 passed in 72.77 s;
  complete final suite: 667 passed plus five subtests, four existing dependency
  warnings, in 447.55 s. Own-source I6/I7 replays have zero known flow conflicts
  and final RenderFit 10/10 and 12/12 with no issues. Fresh selection changes
  coverage/space and is not a full quality acceptance; all 216 Campaign JSON
  hashes remained unchanged. Batch 3 stays PAUSED at 2/100. No live model/GPU
  generation or Batch resume.

  Atomic task commit: `be69bbb` (`fix(layout): enforce shared physical reading
  flow`), 12 tracked source/config/prompt/test/README files. This guide and the
  capacity report remain local/ignored.

- 2026-10-15: Implemented the explicitly approved shared module-completion plan
  with current-board evidence/root retrieval, fair per-module bounded repair,
  same-root compact restoration, used-evidence novelty verification and
  zero-height information-gain adoption. Protected every visible module,
  ownership, typography and local/cumulative space; added one same-attempt
  rollback through final preflight/render. No module-count gate, withdrawn
  semantic stage, Critic score change, model/GPU run or Batch advance.
  Updated README, capacity/family/Improve reports and this guide; local reports
  remain ignored. Final full CPU regression: 633 passed plus five subtests,
  four existing dependency warnings in 423.68 seconds. Final focused content
  regression: 40 passed in 9.08 seconds. I5 same-snapshot four-column rollback
  passed actual compile/preflight/render audit with 10/10 editable elements
  matched and no render issues; all 187 inspected historical JSON hashes stayed
  unchanged. Batch 2 remains PAUSED at 5/100. Atomic commit: `5e45392`, 14 tracked
  files. This guide and all topic reports remain local/ignored.

- 2026-10-14: With explicit user authorization, fixed only the historical
  Lineage storyboard boundary on `24cde5a`. Selection/status use one generic
  board-availability check, preserving classic provenance/geometry reasons.
  Load clears raw/fitted boards and deep-copies the selected fields; missing
  boards cannot inherit a previous candidate. Added all twelve families plus
  an extension, null/missing/malformed inputs, same-Lineage alternate selection,
  copy isolation and a real Runner no-model/no-budget unavailable regression.
  Existing metadata-only restore fixtures now include section lists. Updated
  README and the existing Improve report. No content/geometry/quality policy,
  Critic/schema, model/GPU or actual Campaign data changes. Final verification
  and commit are recorded in the Improve report.
  Final focused CPU regression: 152 passed in 15.04 seconds. Full CPU regression:
  600 passed plus five subtests, four dependency warnings in 433.15 seconds.
  Post-fix read-only inventory retains 17 selectable Lineages and identical
  SHA-256 hashes for all 38 real snapshots.
  Atomic task commit: `f58626b` (one source file, three test files and README).
  This guide and the Improve report remain local/ignored.

- 2026-10-14: Implemented unified family contracts for all twelve families and
  generic extension support; shared bounded editorial/compact search, root-safe
  core priorities, measured zero-height refill, compact module restoration and
  actual reading-order placement. Preserved classic topology, standalone route,
  strict locks, Improve exclusions and full scientific verification. Added
  complete loop titles, thin-module repair targets, durable pre-call 3+1 repair
  budgeting, Batch policy freeze/upgrade and digest-bound replay inputs with
  font/config identity checks. Updated README and active capacity/family reports.
  Validation results and saved-I5 replay limits are recorded in the capacity
  report; no live model/GPU Batch or historical Campaign mutation.
  Final focused CPU regression: 128 passed in 53.64 seconds. Complete CPU
  regression: 518 passed plus five subtests, four dependency deprecation
  warnings in 438.18 seconds. Saved-input classic replay passed exact and
  rendered checks; four-column replay stayed blocked by two horizontal title
  overflows. No quality-acceptance or exact historical-causality claim.
  Atomic task commit: `24cde5a` (20 source/config/prompt/test/README files);
  this guide and topic reports remain ignored local documentation.

- 2026-10-14: Archived the withdrawn module-consistency report at
  `docs/reports/archive/MODULE_CONSISTENCY_REPORT.md`, preserving its complete
  contents and existing withdrawn-status notice. Updated current and historical
  guide references plus the report organization policy. Other reports are
  unchanged. Verified report hashes and document references; no source/runtime
  changes, model/GPU calls or regression run. All edits are local ignored
  documentation; tracked code remains at rollback commit `b5f0947`.

- 2026-10-14: At the user's request, restored all tracked files exactly to
  `c3b1038`, reversing the net changes in `0d7de7a` and `a084cd2` without
  discarding either commit. Removed the experiment's eight added files and
  restored Critic 4.3.0/rubric v5, original Curator/Planner/content/Solver/
  persistence behavior and pre-feature tests. Earlier performance, spacing
  and complete rendered-text matching remain intact. No project entry process
  was active; existing Batches are PAUSED or failed. Latest Batch stays 4/100
  with I5 uncommitted. No runtime knowledge, papers, posters, templates or
  secrets were changed, and nothing was pushed. Tracked working content was
  checked equal to the target before testing. Focused CPU regression: 99 passed
  in 18.96 seconds; full CPU regression: 484 passed plus five subtests, four
  dependency deprecation warnings in 416.10 seconds. CLI help/import/config
  smoke checks passed. All 565 loop-store, 958 output and 36 input files retained
  identical inventory/content hashes. No live model/GPU run. Details are
  recorded in the existing module-consistency report.
  The implementation entries immediately below are historical and superseded
  by this rollback.


- 2026-10-14: Completed the interrupted replacement of semantic repair's
  erroneous-candidate comparison with
  `source_association_repair_v2`. Removed temporary original renders/Critic,
  seven-dimension veto and semantic-relative whitespace gates, retaining normal
  source/compiled/Preflight/RenderFit/Critic admission. Arbitrary custom modules
  and figures/tables are handled uniformly. Both Explore and Improve enforce
  corrected content retention; confirmed corrections narrowly amend contracts
  and explain superseded intent. Added at most one affected-module grounded
  content round and two fixed-topology refits, charged to existing repair budget,
  with scientific-root/visual/ownership guards and staged rollback. An optional
  content failure may keep a feasible corrected fit, never the erroneous board.
  Repair report v2 distinguishes verified association from layout failure;
  Critic 4.4.1 records policy/status without changing rubric v6, weights or 78.
  Retired baseline fields are excluded from new snapshots/reset, while historical
  vetoes and all original artifacts remain unchanged. Resume review strengthened
  real affected-module budget-exhaustion tests, disabled/missing-text-model
  skipping, duplicate-root/excluded-claim suppression and model-metadata version
  protection. Updated README and `docs/reports/archive/MODULE_CONSISTENCY_REPORT.md`;
  final focused CPU regression: 127 passed, two dependency deprecation warnings
  in 22.32 seconds. Final complete CPU regression: 561 passed plus five subtests,
  four dependency deprecation warnings in 422.93 seconds. Diff whitespace checks
  passed; no real-model/GPU run. Actual model semantic accuracy and multi-paper
  visual quality remain unbenchmarked; passing tests are not a no-bug guarantee.

- 2026-10-13: Added source-backed module consistency for the optimization loop.
  Paper-local evidence/caption/reference/image hashes ground literal module
  titles, each claim, each visual and collective coherence; visual checks use
  the existing vision service with explicitly authorized original-image pixels.
  Failed judgments require blind confirmation; unknown checks cannot certify
  admission. Planner/content actions stage and roll back unsafe membership
  changes. Bounded automatic repairs preserve claims/assets/fonts, require
  exact same-topology fit and whitespace non-regression, then compare all seven
  final Critic dimensions to an isolated original-render baseline. Validate
  and exact fallback remain locked. Critic 4.4/rubric v6 adds a score-neutral
  gate without changing weights/78 threshold. Blocked pre-render iterations
  commit unscored with no poster/template/global learning; Validate defers them
  without using template trials, including crash replay. Preserved unique
  attempt diagnostics on errors, shared-content rollback, historical records
  and rubric-isolated parent scores. See
  `docs/reports/archive/MODULE_CONSISTENCY_REPORT.md` for historical contracts,
  budgets and limits (feature withdrawn).
  Final full CPU regression: 535 passed plus five subtests, four dependency
  deprecation warnings in 422.36 seconds; final focused regression: 68 passed,
  two dependency warnings in 13.89 seconds. A separate mocked Planner smoke
  check verified adoption/rollback through its real callable entry point.
  No real-model generation or GPU use; real-model error rates and visual
  quality still require observation in subsequent runs.

- 2026-10-13: Consolidated all eight root topic reports into `docs/reports/`
  without changing their contents. Updated guide references and documentation
  policy: preserve root AGENTS/README, reuse topic reports and avoid one report
  per conversation. Reports remain local/ignored; source code, runtime data
  and historical modification records are unchanged.
  Verified all eight SHA-256 hashes and report/guide links; documentation-only
  relocation required no model, GPU or runtime regression run.

- 2026-10-13: Fixed incomplete rendered-text matching for styled body text and
  PDF-merged titles. RenderFit schema v3 adds bounded exact character-fragment
  fallback and explicit coverage/reason/method diagnostics plus English terminal
  summaries. Shared styling retains legacy Renderer output; 10,000 seeded token
  comparisons matched the pre-change implementation. Read-only real I3/I4
  replay recovered 12/12 editable elements (previously 9/12 and 5/12), measured
  all six title-content gaps in each, and found no text-fit violations. Source
  poster/layout/report hashes stayed unchanged; no Campaign or knowledge state
  was rewritten. Existing rubric, weights, admission, layout-cache budgets and
  classic route are unchanged. Full CPU regression: 484 passed plus five
  subtests, four dependency deprecation warnings in 413.82 seconds; final
  affected-area regression: 142 passed, two dependency warnings in 27.50 seconds.
  See `docs/reports/RENDER_FIT_MATCHING_REPORT.md` for acceptance
  tests and limitations; `partial` remains possible and explicitly inconclusive.

- 2026-10-13: Made all Markdown files except the root README local only, per
  user preference. Seven implementation reports, `AGENTS.md`, and the resource
  README are removed from Git tracking while local copies remain available.
  Removed README links that would break after publication. Future chats in this
  workspace still use the local AGENTS guide.

- 2026-10-13: Resumed and reviewed the interrupted spacing implementation.
  Unified loop title measurement/rendering, rechecked final typography, added
  title PDF fit/minimum-gap audit and one preflight-guarded correction, and kept
  Validate/exact fallback locked. Added directional adjacency/decomposition,
  visible terminal-bottom metrics, bounded content-aware shared boundaries,
  and multi-metric local repair admission without whitespace/content regression.
  Critic 4.3/rubric v5 reports cross-zone/bottom issues; Planner guidance consumes
  them without arbitrary coordinates, scientific prose or font shrinking.
  Review fixed compiled/rendered baseline mixing, report overwrite on discarded
  correction, lost-evidence false clearing, and visual/body identity collisions.
  Historical I1/I2 audits verified unchanged input hashes; a temporary model-free
  I2 PPTX/PNG recompile passed title fit, retained claims/visuals and reduced mean
  extra bottom gap from 1.8917 to 1.4034 inches. Unsafe gap-to-bottom transfers
  were rejected and remaining gaps reached Critic. Updated README,
  `docs/reports/LAYOUT_SPACING_REPORT.md`, capacity and performance reports. Final full
  regression: 442 passed, five subtests passed, four dependency deprecation
  warnings in 412.10 seconds. No model/GPU work or live Campaign/knowledge-store
  mutation.

- 2026-10-12: Added bounded loop-attempt measurement reuse and a version-gated
  local text-fitting adapter without changing layout search, content guards or
  Critic. Added hierarchical English layout progress and text-free output/unique
  attempt performance reports, with safe cleanup, original-computation switches,
  and explicit programming-error propagation through final compilation. Added
  83 CPU regression cases and a read-only benchmark/replay command; full suite
  is 393 passed plus five subtests. Three saved I2 module measurements matched
  exactly with 4.2–7.2x first-measurement speedups. No model/GPU run or live
  Campaign mutation;
  whole-iteration speedup remains unmeasured. See `docs/reports/LAYOUT_PERFORMANCE_REPORT.md`.

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
  and fail-closed pre-attempt exhaustion status. See `docs/reports/FAMILY_SELECTION_REPORT.md`;
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
  `docs/reports/GENERATION_FAILURE_REPAIR_REPORT.md`. Full CPU suite: 286 passed plus 5
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
  capacity report, and `docs/reports/IMPROVE_REVISION_REPORT.md` with contracts/limitations.

- 2026-10-10: Decoupled visual classification from left/middle/right poster
  assumptions. Parser now normalizes five paper-semantic roles and an optional
  key pointer, writes an ID-only classification audit, and keeps old Campaign
  foundations readable without silently reclassifying them. The loop Curator
  uses a route-specific column-free prompt, records selection provenance, and
  can offer a relevant key visual to the solver; the classic one-shot route
  retains its independent three-column behavior. Critic now audits source,
  Curator-selected, and final-visible IDs without changing scoring or gates.
  See `docs/reports/VISUAL_CLASSIFICATION_REPORT.md` for contracts and limitations. Full CPU
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
  and `docs/reports/CAPACITY_REPAIR_REPORT.md`; complete CPU suite: 222 passed plus 5
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
  updated README plus `docs/reports/CAPACITY_REPAIR_REPORT.md`. Complete CPU suite: 210
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


Atomic local implementation commit: `65da840` — 44 tracked paths, 2713 insertions / 196 deletions; no push. Tracked worktree clean after commit. Code/CPU acceptance complete; no real model paper acceptance claimed.

Atomic native-source repair commit: `6ea6bd6` — 22 tracked paths, 1082 insertions / 44 deletions; local only, no push. Final tracked worktree clean. Native extraction and CPU/protocol acceptance complete; fresh real-model poster acceptance remains pending.

Atomic local presentation repair commit: `80aa807` — 8 tracked paths, 261 insertions / 21 deletions; no push. Full1148tests +5subtests pass. Only the pre-existing user deletion of excavator_loading.html remains unstaged; no task source files are untracked.

Atomic local v13 repair commit: `1213384` — 12 tracked paths,413insertions/60deletions;
local only, no push. Final full suite1179tests +5subtests passes. Only the
pre-existing user deletion of excavator_loading.html remains unstaged; no task
source files are untracked. The guide and existing report are updated but ignored.
No fresh real-model poster generation/scientific/aesthetic acceptance is claimed.

Atomic local measured-source repair commit: `b608a8b` — 18 tracked files,987 insertions/65 deletions; no push. Technical generated-artifact acceptance passes for run_851f7afab99d465088a7; quality remains needs_revision and content scoring unavailable. Only the pre-existing excavator_loading.html deletion remains unstaged. Final delivery manifest explicitly records the AST-identical EOF packaging cleanup. Full acceptance report: storage/rubrics_samples/background/source_receipt_v21_validation_20261028/acceptance_report.json.


---

## 2026-11-02 独立项目迁出说明

本报告的既有内容从 PosterGen 工作区完整保留，现随独立项目 Rubrics_poster
在 `/projectone/projects/Rubrics_poster` 维护。既有记录中的源码版本、测试、旧样本
和绝对路径属于迁出前的历史证据；不代表新项目已运行相同的真实模型验证。
新项目未迁入原来的海报、run、缓存或模型日志，也不依赖原项目源码和环境。
迁出操作、行为保留范围、独立环境及验证结果见[独立迁出报告](../PROJECT_EXTRACTION_20261102.md)。
