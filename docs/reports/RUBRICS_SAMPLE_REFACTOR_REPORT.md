# Independent Explore samples for the Rubrics framework

## Adaptive visible-source PDF extraction (2026-11-02)

The user authorized changing extraction after run_5bad7021de5547218688 failed
before layout. Its24-page grammar paper embedded a clipped PDF Form whose hidden
text leaked through PDFium into Marker header/caption regions; native PyMuPDF
excluded those characters. Six disagreements stopped foundation building,then
save_timing_log raised KeyError on missing joint_preparation. Both paths are
addressed without rewriting that failed run or its receipts.

Current editorial Parser uses editorial_visible_source_v2. Readable native text
retains its literal characters and precision despite converter prose differences.
Rotation/scaled boxes normalize once into native PDF coordinates. Converter-only
extras on Form pages are diagnostics,not copied source. Numerical substitutions
require visible raster reconciliation; formatting-equivalent values preserve
native precision,signs and percent units. Tables/formulas do not use prose-order
similarity to diagnose corruption. Severe prose garbling,OCR-only regions and
ownership ambiguity use existing Surya models on rendered pixels. Scans use one
full-page pass; at most24regional attempts per page,12M pixels per crop,and.85
line/numeric-word confidence. OCR column order follows Marker regions; uncertain
fallback reading order remains explicit. Visually uniform regions and unreadable
headers/footers can be omitted with diagnostics. Unresolved body/numeric regions
and unusable text remain failures; no scientific truth is certified by extraction.

Original Marker output and detailed native/OCR records persist. Selected methods,
coordinates,engine/image hashes and confidence distinguish OCR from native text.
Ambiguous captions retain converter text marked unresolved. The existing writing
and final Critic calls receive extraction quality; current snapshots and published
diagnostics retain the report. No new writing/review request or dependency.
Classic keeps Marker;explicit old source route keeps strict native policy. The
strict helper's optional native_coordinates keyword defaults to legacy behavior.
Generator v31 and updated extraction code identity reject old normal resumes and
paper caches; material/scoring/storage/layout/edit policies remain unchanged.
Early foundation failure now saves timing with joint_preparation not_started,
without raising a second exception.

Preliminary tests exposed double rotation scaling in the strict helper and false
garbling detection on linearized tables. Normalized coordinates now use the
explicit opt-in native-coordinate path; structural blocks retain numeric checks
without prose-order rejection. Those preliminary runs are not final acceptance.
Final frozen CPU validation:1638tests plus5subtests pass,7warnings,1560.00s
(26m00s),normal exit0. Focused136tests pass,3warnings,12.09s,normal exit0,
including62new cases. Coverage includes cropped Forms,rotation/scaling,scans,
multicolumn OCR ordering,garbled text,blank raster rejection,confidence and numeric
conflicts,leading decimal points,long identifier precision,corrupt records,caption
ambiguity,cache identity and real CLI early failure. Full-suite realPPTX/PNG
publication/recovery cases retain the exact extraction report and send its quality
summary to final Critic without new request allowances. Both CLI help commands,
offline lock and staged tracked/new-file diff checks pass.

All354frozen source/task files,8432historical files and19pre-existing user paths
remain unchanged;no new historical artifacts. Task scope12files;guide/report stay
ignored. Evidence:/tmp/postergen-pdf-adaptive-{baseline,frozen,scope,validation-final}.json,
/tmp/postergen-pdf-adaptive-focused-frozen.log and-full-cpu-final.log.

Real-paper engineering replay uses three distinct original PDF hashes and saved
Marker-region records under /tmp/postergen-pdf-adaptive-replays,with the summary
at /tmp/postergen-pdf-adaptive-replay-summary.json. Across51pages and714selected
native blocks,the emitted raw-text digest equals every complete original native
transcription. Grammar24pages/278blocks now passes with12diagnostics instead of
6blocking conflicts;NEDS18pages/274blocks passes with3warnings;HAGS9pages/162blocks
passes with52warnings. No body was omitted to evade disagreement. All three use
zero live OCR/authoring calls. Surya bridge tests use real rendered pixel crops
and deterministic prediction fixtures;they verify integration/control flow and
coordinates,not production GPU OCR accuracy. No live model/GPU sample generation
or scientific/aesthetic acceptance is claimed. Normal reruns require a new run
under generator v31;the original failed run remains untouched.

Atomic local commit:83d3239 (12files,860insertions/23deletions);no push. Guide/
report stay ignored;all19pre-existing user paths remain outside this commit.

## Shared module frames and measured region transfers (2026-11-02)

The current editorial route now separates allocated paint geometry from intrinsic
content bounds. section_container.height keeps its original honest measurement
semantics; module_frame under editorial_module_frames_v1 holds the allocated
rectangle. Backgrounds render inside these frames with inherited shadows disabled.
Exact compilation/readiness validate every frame against final zone geometry,
Curator module order, weights and gutters, while geometry_digest binds both content
and paint bounds. The inspection-only template blueprint uses actual paint boxes.
Overflow remains visible to existing Preflight, RenderFit and scoring; no clipping,
font shrinking, false occupancy, hard physical admission or post-freeze repair.

All fifteen families use one topology-aware shared-cut allocator for both axes.
It proposes measured displacements and coordinated cuts around grids/spanning
regions, preserving adjacency gutters, metadata, capacity, order and legal merge
provenance. Coupled transfers share the donor's one measured spare-space budget.
Final edge shifts are bounded by .08 normalized, with the existing maximum twelve
fast candidates/four exact finalists. Alternative exact horizontal splits expose
minimum readable height while preserving vertical-reference image area; vertical
pressure includes height-capped images growing with their allocation. Exact rows
retain text/formula safety correction but no longer divide the whole region by1.20.

Curator's existing core_module_ids guidance now requires concrete, paper-specific
architecture/method/key mechanism, necessary theory or decisive evidence of the
distinctive contribution. Background/problem/vision and generic pipelines alone
are insufficient. Two cores must complement one another; two is an upper limit,
not a quota. Count/ownership/palette freezing remains deterministic; semantic
selection remains model judgment in the same call, not scientific certification.
Generator v30 invalidates old normal resumes; no historical rewriting, model/GPU
generation, new authoring/review request or edit allowance is authorized here.

Preliminary verification is in /tmp/postergen-module-space-*. Four old assertions
expected strict height underuse; they now allow full-height exact fits with a1e-6
tolerance. Early replay exposed a coupled donor double-spend; the allocator now
limits all shrinking edges together. Neither preliminary run is acceptance.
The first merged-grid fixture had equal measured row demands and therefore no
useful legal transfer. Its corrected mixed-pressure fixture now exercises the
intended merge-preserving redistribution. A pre-final repeated run was interrupted
after this known fixture failure; it is excluded from acceptance.

Final frozen full CPU validation:1576tests plus5subtests pass,7warnings,1559.71s
(25m59s),process exit0. Final isolated focused validation:49passed,2warnings,
109.96s,process exit0. The broader parallel focus log reported200passed/519.42s
but its process later returned143;it is excluded from clean-exit acceptance.
Its cases all pass in the normal-exit full run;source remained frozen throughout.
The49new regressions
cover all15families,realPPTX frame geometry/effects,merge provenance,both axes,
coupled donor budgets,minimum image height,vertical image feedback,corrupt frames,
finite search limits and frozen readiness. Existing full integrations cover real
PPTX/PNG publication,capacity editing,recovery and physical failure publication.
Both CLI helps,offline dependency lock and staged tracked/new-file diff checks
pass. All351frozen source/task files,8420historical files and19pre-existing user
paths remain unchanged,with no new historical artifacts. Only14task-owned files
are staged;guide/report remain ignored. Evidence:
/tmp/postergen-module-space-{baseline,frozen,scope,validation-final}.json,
/tmp/postergen-module-space-focused-isolated.log and-full-cpu-final.log.

Engineering-only replay at /tmp/postergen-module-space-replay-verified retains
the saved NEDS prose and prior core IDs to isolate geometry. It is not a new
sample,live palette extraction or semantic acceptance of that old core selection.
Independent reopening of the actualPPTX confirms6disjoint allocated frames and
zero inherited effects. Top/middle and middle/bottom gaps both=.697in;the former
middle/bottom gap was2.13747in with the old duplicate region reduction. Method
remains image-left/text-right with9.20607x4.26690in image;the original old-source
thumbnail was5.5942x2.59284in. RenderFit passes with12/12editable matches. The
unchanged content still has1.23404in total planned-height overage across modules;
fit/Preflight retains its failed verdict. No capacity model requests were made,
and this does not certify scientific or aesthetic quality. Full generation still
uses existing bounded capacity edits and freeze-and-score policy. Original saved
paper/sample artifacts and receipts remain immutable.

Atomic local commit:1bf20d4 (14files,505insertions/52deletions);no push. Guide/
report remain ignored;all19pre-existing user paths remain outside the commit.

## Two explicit core panels and exact initial directions (2026-10-30)

User approved implementation with up to two core module IDs chosen within the
existing Curator response, independently of importance. Text-only core panels use
the global poster palette; image-owning cores use their own key visual, otherwise
their first selected visual/table. Image extraction adds at most two durable
color-agent requests, never an extra writing/capacity opportunity. Nullable local
extraction prevents a default navy or another module's figure from masquerading
as a local accent. Unavailable extraction produces a transparent panel plus an
explicit diagnostic. Source asset hashes, resolved accessible colors and the
actual extraction-receipt hashes bind editorial_core_panels_v1; checkpoints,
snapshots, readiness, renderer, color scoring and publication all carry it.
Capacity edits preserve core IDs while leaving prose/importance/legal placement
editable. Global palette source policy and scientific review are unchanged.

Current-route first-fit directions now measure three distinct actual image widths
derived from image aspects and usable stack height using the final editable-body
measurement, not coarse word/line rejection. Candidates preserve total image area
relative to the vertical reference and prioritize readable image area among fits.
The normal exact selector is shared on both sides of the direction freeze. If no
normal plan remains, a frozen horizontal keeps an exact bounded overflow plan;
vertical remains vertical. No font reduction, extra geometry/family/edit allowance
or post-freeze direction repair. Classic and explicit older-source behavior remain.
Generator explore_samples_v29 refuses old normal resume; historical results stay
immutable. Preparation/material/scoring/storage identities stay unchanged.

Preliminary tests caught a floating-point boundary at the tallest image candidate,
and a locked selector that could enlarge an already selected image on unchanged
inputs. Both were corrected before acceptance. One old fixture now explicitly
uses the old-source selector to retain its intended legacy comparison; the current
unlocked exact selector correctly rescues that same five-entry case. A legacy-render
fixture also needed an initialized palette. Preliminary runs are not acceptance.
Focused validation: 220 tests pass, 4 warnings, 464.74s; the final independent
importance-versus-panel scoring assertion also passes (1 test, 2 warnings, 8.20s).
Both CLI help commands, offline dependency lock and tracked/new-file diff checks
pass. Final frozen full CPU validation: 1527 tests plus 5 subtests pass, 7 warnings,
1442.89s (24m02s). All 348 frozen tracked/task files retain their frozen bytes;
7000 baseline paper/sample files and 1420 old-output files remain unchanged, with
no new historical artifacts. All 19 pre-existing dirty/untracked paths are
preserved outside the 16-path task scope. Evidence:
/tmp/postergen-core-exact-{baseline,frozen,scope,validation-final}.json,
/tmp/postergen-core-exact-focused-final.log, -full-cpu-final.log and -color-score.log.
Guide/report stay ignored. Atomic local commit: 28c96a7 (16 paths, 636 insertions /
19 deletions); no push. All pre-existing region-policy changes/untracked files and
the HTML deletion remain excluded.

Engineering-only NEDS replay uses the SAME saved initial geometry, original
prose/assets and existing keyword choices from run_4fa6b7ce97d046568493. Only m1/m3
are explicitly selected as core for this replay; the image-core response fixture
is deterministically derived from its own pixels, not a live palette-model result.
No model/GPU request, new official sample or scientific/aesthetic acceptance is
implied. Editable PPTX/PDF/PNG are under /tmp/postergen-core-exact-replay-same-geometry/.
m3 now uses image-left/text-right: original 5.5942x2.59284-inch image becomes
12.05139x5.58567 inches; the original body wraps in a 39.04861-inch text box and
retains all 524 normalized characters. PDF matching finds all 12/12 editable text
elements. The two existing top-module/body versus m3-title collisions remain
honestly failed diagnostics; no prose/geometry repair or historical rewrite was
performed to hide them. The earlier base-geometry replay and incomplete block-only
PDF check were exploratory and are excluded from final same-geometry evidence.

## Frozen initial module directions (2026-10-30)

The user approved keeping the first fitted image/text direction throughout later
capacity editing. Generator v28 adds `editorial_module_composition_v1` without
changing preparation/material/storage/scoring markers, Parser/native extraction,
models, family policy, finite geometry limits or the three-capacity-edit budget.
Classic and explicit older-source routes keep their original adaptive planner.

The first existing bounded fit still selects geometry and internal directions.
Before any capacity request, its actual result and one horizontal/vertical mode
per image owner are persisted to `preparation/editorial/composition.json`. Initial
sample, paper/resource, candidate, zone, dimensions and style inputs bind the
receipt. Recovery loads this exact first result, retaining the original first
edit's payload and charges instead of searching or choosing again. Lost/corrupt
receipts after capacity editing cannot recreate an initial selection. The mode map
travels through preparation checkpoints, render-ready/final-output snapshots and
publication diagnostics; readiness checks compare it to the initial receipt and
the actual compiled image/text relationships, not merely mode labels.

The current-route shared planner respects that mode during fast fitting and exact
compilation. A horizontal module first retains any ordinarily fitting adaptive
plan. If the conservative selector rejects it, at most three width splits receive
exact editable-body measurements within the same horizontal direction. Drawable
overflow keeps the least-overflowing horizontal plan for the existing finite
capacity editing and freeze-and-score diagnostics. Vertical modules cannot switch
to horizontal. Images keep aspect ratios, owners and order; dimensions, column
widths, region sizes and prose remain editable. Text-only structural patches remain
legal. No new Curator call, figure probe, quality round or post-freeze repair exists.

The production defect was demonstrated using immutable run
`run_7c282388d5ef4432b1e2` (v26): initial HAGS was horizontal at 59 words/three
entries, then became vertical after expansion to five entries and reduced region
height. The final 62-word candidate's horizontal fast text estimate was about
5.328 inches versus a 5.005-inch reserved body limit. Exact geometry for the same
row used about 6.62 inches including the title, within its 7.95-inch allocation.
The new counterexample uses local synthetic fixtures; no production poster or
stored history is rewritten, and there is no fresh real-model paper generation.

Focused checks cover both directions, all fifteen family compilations, HAGS
five-entry edits and reduced heights, multi-image order/aspects, narrow/tall and
overflowing horizontal boxes, text-only structure changes, input/receipt/snapshot
corruption, and interrupted charged-response replay without extra model work.
Default-route real editable-PPTX/PNG integrations additionally cover three edits,
publication recovery, retained physical defects and all-score saving.
The HAGS-specific real render's standard RenderFit is honestly partial (11/12;
the formula-containing `module_2_text` is unmatched), not conclusive approval.
Independent PDF glyph/frame checks are recorded separately, without modifying
the matching policy or converting partial coverage into an all-clear.

Final frozen CPU suite: **1452 passed plus five subtests**, seven existing warnings,
1308.01 seconds. Focused validation passed 135 cases plus three final readiness
counterexamples; default-route render/publication validation passed 35 cases.
All 344 frozen files, 19 pre-existing worktree paths and 9,333 historical files
remain unchanged. Both CLI help checks, offline dependency lock and diff checks
pass. Independent HAGS PDF validation finds all five labels and 433 nonspace
glyphs within the intended body frame, disjoint from the left image, while keeping
the standard RenderFit's partial verdict explicit. No real model/GPU generation,
fresh scientific acceptance or historical-output rewrite is implied. Atomic commit
is recorded in the current AGENTS.md section. Evidence prefix:
`/tmp/postergen-composition-lock-` (baseline, frozen source manifest, focused/full
test logs, CLI checks, integrity validation and the independent glyph check).
Local atomic commit: `6e6cae8`, 13 task-owned files, no push. The guide/report
remain ignored; all pre-existing modified/untracked paths remain excluded.

## Final engineering replay result (2026-10-23, 15:20 Beijing)

**Code/tests complete; full poster acceptance still NOT achieved.** The user-
approved old-science engineering replay ended without PNG/PPTX or score. All
new artifacts, journals and ledgers are under `/tmp/postergen-engineering-module-
replay-20261023T065442Z/`; the authoritative small summary is `summary.json`.
These records are explicitly NOT independent samples and NOT eligible for Rubrics.

- Coordinated module compaction implementation: local commit `0bc819d`.
  Real replay exposed input-echo preservation responses; focused repair
  `a93ab17` adds a dedicated audit role, final verdict schema after input and
  explicit invalid-response diagnosis. No science/font/geometry gate, retry or
  repair allowance was weakened. Only module_compaction.py and its test changed
  in the follow-up commit. No push; worktree clean.
- Final full CPU suite: **908 passed +5 subtests**, 749.43s, four pre-existing
  warnings. Focused suite:49 passed. Eighteen critical classic/extraction/
  geometry/render/store files remain identical to the pre-follow-up source.
- Classic follow-up passed all9 scientific and9 preservation checks. Two
  complete modules shrank284→223words (2015→1647characters), preserving identities,
  necessary-information coverage, sources and local dependencies. Exact canonical
  16.64in-wide module heights each fell2.93333in, and beam placement improved1→3.
  Ordinary full search still returned NO_FAST_FEASIBLE_VARIANT; no trial bank or
  board was adopted as final. Initial attempt471.60s; corrected classic376.81s.
- Final asymmetric-two-column retry used original attempt_0013, fresh original
  verified science/board and the SAME engineering ledger. One module passed all
  checks (1126→947chars); canonical exact heights fell2.2in at16.12in width and
  .73333in at34.32in width. The other draft made no net shortening and was
  rejected. Full search remained infeasible (placement1→2), total224.36s.
- Exactly3 capacity rounds spent across the three real attempts,0 quality rounds;
  the reserved quality round cannot be spent on further infeasible capacity
  work. No reset/refund.48 physical requests completed,0 transient retries,
  0 unfinished. No further model replay or stochastic official launch occurred.
- All source-run files retained their hashes; official-store file inventory was
  unchanged.14 foundations,208 resource refs,11 finalized samples and1 original
  poster bundle verified. All three owned workers exited, GPU5 has no process
  allocation, GPU3 model service PID5003 remains alive. Single-use entries removed.
- This demonstrates real coordinated rewriting, full re-verification and exact
  local physical savings, NOT whole-poster fit/Preflight/RenderFit success. Only
  two families were tested with these actual compacted drafts; no claim of
  mathematical impossibility or all-family compacted failure. No rendering stage
  was reached. Do not confuse copied asset PNGs with a generated poster.
- Separate latest official fresh-science run56650... still failed upstream in
  Writer because11–37% exists in original context but no corresponding evidence
  item. Engineering success at the module level does not fix or conceal that
  missing citable-evidence issue. Remaining independent end-to-end acceptance is
  explicitly unsatisfied; preserve the recorded diagnostics before choosing
  further changes rather than restarting blindly or weakening gates.

## User-approved whole-module compaction follow-up (2026-10-23)

After quota recovery, all 15 saved v5 family attempts were replayed read-only on
CPU with exact LayoutAgent section heights replacing fast estimates. All bounded
searches remained infeasible (791.27 seconds summed); no model/renderer/GPU calls,
official sample creation or historical edits. This does not prove mathematical
impossibility. Full diagnostic: /tmp/postergen-final-exact-search.json; text-only
lower-bound measurements: /tmp/postergen-final-exact-capacity.json.

The user explicitly chose “继续扩展整模块压缩（推荐）” after reviewing the additional
scope. This supersedes the earlier proposal-only status recorded below. Implement
sample_module_compaction_v1 / generator explore_samples_v6, retaining preparation
v3/body v2/storage v2. New operation targets complete current module loads after
height failure, keeps one row per original expression/root in order, retains
verified indispensable-assertion coverage and original provenance/dependencies,
and rejects the entire batch on any missing/invalid/unsafe item. All existing
scientific, necessary-information, editorial-preservation and physical gates stay.

Work remains under existing capacity round/action limits with durable charge
before calls. At most eight expressions per module action; larger/mixed/locked
modules can use existing ordinary repair. Raw responses precede parsing, exact
input requests replay, missing responses after durable requests fail closed.
One context recheck is allowed only after verifier correction; further rewriting
rejects the batch. Exact canonical-zone height probes diagnose local progress,
never certify overall feasibility. They may justify the existing second charged
round when a shorter complete module has not yet changed early beam placement.
Full fitting/compile/Preflight/RenderFit still gate adoption/publication. More
expressions mean more per-action verification work; round limits are not API-call
limits. No new preparation allowance, re-curation trigger or science selection.

Implementation and validation are in progress below; no successful v6 poster has
yet been claimed. Baseline for this follow-up is local source commit 62f41d1.

Final compatibility/scientific audit tightened both module and ordinary sample-
body variants: previous indispensable-assertion coverage must be present in the
explicit new verdict AND actual supported evidence in support_map. Citation
intersection by itself is still insufficient. Single-expression compaction/style
fallback and reuse of an existing same-root variant get original_expression and
the same required-coverage guard. Sample-body single-expression prompts receive
all original cited evidence; classic retains its prior first-six behavior.
Display dependency hints follow new variant IDs, keeping original dependency
records in each claim; exact progress probes run prepare_board on both sides so
labels/indents do not vanish merely because IDs changed. Fixed topology is locked
along with fit_locked. No scientific gate/font/geometry/scoring change.

Final related regression passed 100 tests, two existing warnings, 125.25s. The
first full follow-up snapshot passed 887 + five subtests in 741.63s; it precedes
the last audit changes and is not presented as the final full-suite result. An
outdated in-flight snapshot was deliberately stopped (221 passes, no test failure)
before running the final full source/test set. Final log:
/tmp/postergen-module-compaction-final-full.log.

FINAL full CPU regression against the frozen source: **901 passed + five subtests**,
four existing dependency warnings, 748.78s (12m28s). Atomic local commit **0bc819d**
(fix(samples): compact module prose within repair budgets), seven task-owned
files, 721 insertions / seven deletions, no push. Worktree clean after commit;
local AGENTS/report intentionally excluded, no runtime/paper/poster data staged.

Final complete real validation launched at 2026-10-23 14:23 Beijing:
run_56650dbf9beb46df85a6, Neural Encoding and Decoding at Scale, Qwen3.8-27B text/
vision, 54x36, one sample, original run seed1494476416. Standard strict donor is
run_da8fb99a67ca47e6b6fb. It copies only original paper/evidence/assets and reruns
all sample preparation/design; no old prose/plan/score/template enters this run.
All126 frozen production source/prompt files match actual current bytes. Job:
storage/rubrics_samples/background/module_compaction_final_validation_20261023T062353Z/.
Supervisor301693, GPU5 client, GPU3 service remains untouched. Launch is not
success; final outcome/bundle and successful-poster acceptance remain pending.

Actual final outcome: run_56650dbf9beb46df85a6 finalized **preparation_failed**,
before any new module-compaction call, layout, Critic or rendering. Planner12
units/22 required evidence, Curator6 modules after one patch for ev0129/0154/0215.
Writer module004 itemc included “NDT2 by11–37%” citing ev0123/0127/0102; those
items do not support11/37%. The range exists in original section_17/chunk0 but
is absent from ALL274 extracted evidence items. It entered prose from the full
referential source context, contrary to the writing contract. Numeric admission
correctly failed; the one shared preparation correction was already spent.
No budget expansion, citation guessing or fabricated supported verdict was made.
Original raw/parsed/validation data remain under preparation/content/module_writing/.
Exit1, elapsed633.23s (10m33s), zero owned survivors, no PNG/PPTX/score. This is
not proof of module-compaction runtime success/failure because design was not
reached. End-to-end successful independent sample acceptance remains UNMET.

The user explicitly approved a real ENGINEERING-ONLY replay of old verified
science from run_8229d8748aa94d3e884f to exercise module compaction without another
fresh preparation attempt. It can call current models, exact fitting and native
rendering, but all outputs/ledgers stay under /tmp, explicitly ineligible for
Rubrics mining. It must not publish an official sample, change history, reuse a
poster/template/score, or claim new science. Original foundation/resource/READY/
science/snapshot hashes are checked and assets copied. Diagnostic work uses one
fresh, finite engineering ledger under the existing capacity/quality limits;
this is not a resume/refund of any original failed sample. Detailed result follows
when that specifically authorized component validation finishes.

Earlier v6 prototype run_d040386c567a4021acb0 was cooperatively force-stopped at
the Planner boundary for the last scientific audit. Its original Planner request
completed and stage_01 is preserved; no Curator/design/READY/official outcome,
PAUSED 0/1, zero posters/scores, elapsed343.63s, no owned survivors. It is not
resumed and its science is not imported under changed code. Initial launcher
run_0705ad79935d46248880 was never created: erroneous --run-id meant resume of
a nonexistent manifest. It exited before models in10.92s, no survivors. Bootstrap
records stay under module_compaction_validation_20261023T060014Z; this is not an
official generation failure. Correct new-run CLI omits --run-id.

## Module responsibility, evidence scope and recovery implementation (2026-10-23)

Baseline d5edeff. User explicitly authorized implementation of the reviewed plan,
including a real full sample validation using the compatible completed foundation.
No old result is resumed, migrated or altered. No exceptional cache loader is used.

Implemented generator v5 / preparation v3 / assignment v1 / request-journal v2.
Scientific expression contract stays sample_body_v2: all original exact support,
conditions, numeric/entity/metric/comparison and relationship checks remain.
Explicit required_unit_ids or split required_evidence_ids allocate responsibility;
program materializes the original obligations, never guesses from mere origin
intersection. Optional source-unit support is passed separately to whole-module
Writer. Stable module IDs and whitelisted local patches preserve valid neighbors.
Per-module Writer and per-expression Verifier raw/parsed records support exact-
input replay. One durable editorial correction is shared between planning and
module-body recovery, without debiting layout budgets or refund on interruption.
Body correction maps protected original expressions/prerequisites and requires
explicit necessary-information preservation during full scientific re-verification.
Request/format verification failures cannot trigger an editorial network retry.

First relevant regressions passed: 144 tests (131.42s), related suite 80 tests
(129.95s). Final targeted additions/interfaces: 66 passed (8.84s), two existing
warnings. Full regression and real run result will be appended below.

Full CPU regression completed: 835 passed plus 5 subtests, 735.48s (12m15s),
four existing dependency warnings, no failures. Log:
/tmp/postergen-assignment-full.log. git diff --check passed.

Actual-input fixture /tmp/postergen-assignment-real-fixture.json uses the unchanged
real failed 11-module draft plus an explicitly annotated NEW module-3 responsibility
for poster_sec_3. It is not claimed to be original model output. All 28 mandatory
IDs are preserved, ev_0073 is materialized, no module is added, and evaluation
support includes ev_0078/79/80. Original draft/foundation/FINALIZED hashes match.

Real validation launched at 2026-10-23 08:51 Beijing: run_490d6f1c48cb482dbba3,
one Neural Encoding and Decoding at Scale sample, Qwen3.8-27B text/vision,
54x36 inches, run seed 1494476416. Standard --paper-cache-run-id uses
run_da8fb99a67ca47e6b6fb after exact extraction/input/model/resource validation;
no waiver or old sample prose/plan/score/template is imported. Background records:
storage/rubrics_samples/background/responsibility_validation_20261023T005137Z/.
Supervisor PID 285527; generation PID/group 285529; CUDA_VISIBLE_DEVICES=5.
The generic temporary supervisor removes its own script on launch. Cleanup is
restricted to descendants observed under this process, with PID/create-time checks.
Planner completed in 219.47s: 11 units, 165 selected evidence, 33 required IDs.
Launch and this intermediate result do not establish successful poster generation.

This first v5 run finalized preparation_failed after 1849.27s (30m49s), no poster
or score. Curator needed one 15.1s local patch after its 106.1s initial response;
all 33 mandatory IDs were assigned across seven modules. Writer completed in
270.44s with 26 expressions/642 words. Verifier accepted 22, rejected four:
pc_display_002_002 echoed the input instead of a verdict; pc_display_004_001's
correction verification hit LengthFinishReasonError at 814.5s; pc_display_005_002
and _004 corrections failed existing final semantic/necessary-information checks.
The run stopped before family selection, layout or Critic. Supervisor exit1,
owned_processes_remaining=[], temporary supervisor removed. Historical records
are untouched. No claim of successful poster acceptance is made.

The real echo exposed a diagnostic classification defect: missing/nonboolean
supported had been treated as ordinary rejection. Four offline cases reproduced
it. Sample verifier_response now saves raw/parsed output then requires the boolean
verdict, covering initial and correction requests; failures are verification_failure
and cannot call editorial recovery. The sample prompt adds one complete response
schema and explicitly forbids copying input. No model/token/timeout/retry changes,
weaker scientific admission or added correction allowance. A mixed good/bad module
regression checks that no editorial call occurs even when some claims pass.

Post-fix tests: all four reproduced protocol cases passed (3.93s); combined module
planning/writing/verification regression 121 passed, two existing warnings, 124.20s.
Final full CPU regression restarted against the changed protocol/prompt; log
/tmp/postergen-assignment-full-final.log. A fresh one-sample complete validation
launched at 09:25 Beijing; background records:
storage/rubrics_samples/background/responsibility_final_validation_20261023T012540Z/.
Same standard strict cache/model/dimensions/seed; no failed-run continuation or
sample science import. The generic supervisor again removes itself before work.

Final full CPU regression passed: 839 tests plus 5 subtests, four existing
dependency warnings, 738.63s (12m18s), no failures. This includes the post-real-run
protocol fix and its four mixed-validity recovery regressions. Log:
/tmp/postergen-assignment-full-final.log.

Second validation run_92cd32bee57d4e51b1b2 produced 12 units/25 required evidence,
seven modules and 23 candidate expressions/713 words. Curator 124.34s, Writer
248.55s. Thirteen saved verification responses had boolean verdicts (no repeat of
the input-echo defect); one ordinary semantic correction passed re-verification.
IBL dataset statement pc_display_003_001 nevertheless hit LengthFinishReasonError
after 817s. Another later request became long while the sample was already
irrecoverably failed. The owned validation worker PID 287902 was terminated to
avoid continuing this unsuccessful diagnostic run. Supervisor exit -15 after
1926.35s, owned_processes_remaining=[], script removed; stop.json records reason.
No FINALIZED marker/poster/score is claimed. The old run_state is stale RUNNING,
not evidence of a live process. Its saved science is not reused or migrated.

Both long dataset checks cited fragments with unresolved pronouns ("This dataset",
"The recordings"). Previous semantic feedback incorrectly treated visual-task and
adult-mouse attributes in separate excerpts as incompatible. Original Abstract
and Dataset chunks explicitly establish their common IBL referent, but these
chunks had not been supplied to the module Verifier. This is an identified context
interface deficiency, not proof that it is the sole cause of model long output.
/tmp/postergen-verification-context-audit.json confirms all 274 excerpts map
verbatim to unique original chunks (34 source chunks), with no new model work.

Added sample-only exact source-context mapping and explicit multi-excerpt reference
resolution instructions, preserving the original excerpt-grounded scientific
standards. No facts outside cited excerpts or new IDs are admitted via context.
Missing/wrong/ambiguous source mapping never searches another section. Initial
and existing correction prompts include deduplicated original chunks; journal
identity binds actual context. Added six source/context regressions. Request or
malformed-verdict failures now save partial diagnostics and not_checked_claim_ids,
set verification false, and abort sample verification immediately, preventing
further calls after unrecoverable failure. Classic and normal semantic repair stay.

Context/fail-fast focused regression: 127 passed, two existing warnings, 124.36s.
Final key cases after placing original context before the final response schema:
32 passed, 4.09s. Full CPU regression is running in /tmp/postergen-context-full.log;
the changed prompt will also receive a final targeted check. Actual new helper
maps all 274 evidence IDs to 34 original chunks with no missing context.

New context/fail-fast complete validation started at 2026-10-23 10:04 Beijing:
run_4a2e85e7f2634e97b58a; supervisor PID290025, original-cache source unchanged,
same Qwen3.8-27B/54x36/one-sample/run-seed settings. Background records:
storage/rubrics_samples/background/responsibility_context_validation_20261023T020440Z/.
Only a launch is established here; actual outcome will be recorded below.

Full CPU regression including context mapping and fatal sample-request stop:
845 passed plus 5 subtests, four existing warnings, 746.89s (12m26s). Log:
/tmp/postergen-context-full.log. The final response-schema order also passed the
32 critical tests after its change. No source/prompt mutation during this final
real validation. git diff --check passed.

Context validation preparation completed successfully: 11 modules, 27 required
evidence, 33 candidate expressions/632 words. Verifier 32 passed, one safe scope
correction, zero rejected; affected-module final context recheck also passed.
All mandatory assertion coverage passed, READY/science snapshot was frozen, no
preparation editorial correction was used. The dataset's three expressions all
passed; reasons explicitly used original context to bind the same IBL referent.
This establishes actual successful module-first scientific preparation, not yet
final poster acceptance. Initial assigned family comparison_split entered normal
bounded geometry/content fitting after preparation.

Run_4a2e85e7f2634e97b58a then finalized fit_failed across all 15 peer families,
NO_FAST_FEASIBLE_VARIANT/estimated_height. Frozen verified body: 643 words, eleven
modules, thirty protected expressions. Exact rendering/Critic never began. Report
explicitly says search_exhausted_not_proven_impossible; do not claim geometric
impossibility. Supervisor exit0 after 1563.05s, no owned survivors, no poster/score.
Classic diagnostics show long headings, many distinct bullet/paragraph entries
and figures consume the available estimated height. Read-only LayoutAgent replay
reproduced height pressure at 15/16/17-inch module widths; no new layout-interface
error was found. Historical science/finalization/output records remain unchanged.

Within the approved module-writing scope, refined only planning/writing prompts:
prefer compatible question-level grouping, compact complete headings and one/two
connected paragraph entries; prioritize indispensable assertions over enumerated
optional context. essential=true remains model-declared and fully protected, but
the prompt distinguishes necessary explanatory support from merely useful detail.
All original protection, soft quotas, fonts, geometry, physical/science checks,
family pool, budgets and re-curation triggers stay. No new capacity-driven Actor
loop or automatic content dropping is introduced. Final focused/full regression
logs: /tmp/postergen-compact-prose-focused.log and /tmp/postergen-compact-prose-full.log.

Final compact-prompt focused regression: 127 passed, two existing warnings,
126.12s. New independent validation run_e3170f21e3dc4cf8a395 launched 10:43 Beijing,
same standard strict donor/source/model/dimensions/run seed; no previous sample
science is imported. Supervisor PID292099; records:
storage/rubrics_samples/background/responsibility_compact_validation_20261023T024351Z/.
Planner completed in 259.81s with eleven scientific units. Run discovery uses the
worker's owned run-lease descriptor; temporary supervisor removed itself on launch.

Latest full CPU regression against the final compact prompts passed: 845 tests
plus 5 subtests, four existing warnings, 752.10s (12m32s). This is the final full
source/prompt regression; log /tmp/postergen-compact-prose-full.log.

Compact validation finalized preparation_failed: six modules, 19 required evidence,
21 candidate entries/557 words; Verifier 18 passed, one safe scope repair, two
rejected. Shared preparation allowance was already spent on the three-ID Curator
patch. No layout/poster/score. Detailed actual rejection review found:
- pc_display_002_001 had supported=true and relationships_supported=true, with all
  scientific text grounded, but its split coverage omitted ONE separating clause
  comma. The full-character gate correctly rejected the raw response format.
- pc_display_004_003's proposed correction was supported with full coverage but
  omitted necessary_information_preserved. It was never accepted as preserved.
- Visible prose contained machine citation annotations (ev_0117, ev_0118), distinct
  from its JSON evidence_ids. Model omission of a block-decoding exception was
  correctly caught and safely repaired by the scientific verifier.

Added tightly bounded format normalization: top-level comma separators between
already supported multiword spans can be attached as exact slices only after
positive whole-claim/relationship verdicts and coverage of every scientific
character. Scientific operators, words, negation, numeric separators and commas
inside parentheses/brackets remain hard failures; false verdicts are unchanged.
Raw parsed output and separately normalized spans/notes are archived. Missing
positive-correction preservation booleans now fail as protocol, never default true.
The response example always includes the preservation field.

Writer and existing targeted body recovery now also receive deduplicated original
chunks for their allowed evidence. They must take qualifications from support
evidence when needed for truth and cannot infer universality from named baselines.
Internal parenthetical citation-ID lists are removed before actual text verification
and recorded in display_normalizations. Undeclared IDs fail; scientific parentheses,
values, and literal source-supported ID-like names are untouched. No new model call,
science judge, hard quota, reduced font, budget increase or old-data import.

Read-only actual response replay /tmp/postergen-final-interface-real-replay.json
verifies the single comma normalization restores exact full coverage with unchanged
claim/evidence assignments, and annotation cleanup preserves all scientific numbers.
It does NOT claim the rejected scope statement became supported or preserved.
All real historical outcomes remain immutable. New related/full CPU regressions:
/tmp/postergen-final-boundary-focused.log and /tmp/postergen-final-boundary-full.log.

Final boundary-related suite: 141 passed, two existing warnings, 125.93s. Critical
source/science-format cases: 46 passed, 4.38s, including a multiword numeric comma
case. Final source is frozen. A new complete independent validation started at
11:22 Beijing: run_8229d8748aa94d3e884f, same original strict donor/model/dimensions/
run seed; supervisor PID294335. Records:
storage/rubrics_samples/background/responsibility_final_protocol_validation_20261023T032243Z/.
No old sample science is imported and no exception entry exists.

Interrupted run_92cd32bee57d4e51b1b2 runtime-only metadata was reconciled under its
exclusive lease after PID/create-time and supervisor-exit checks: PAUSED with
explicit diagnostic interruption reason and process_exit_code=-15, counters
unchanged, no FINALIZED sample. This corrects the earlier stale RUNNING display;
its immutable foundation, stage records and all other historical outcomes remain.

Final full CPU regression passed: 859 tests plus 5 subtests, four existing
dependency warnings, 746.97s (12m26s), no failures. Log:
/tmp/postergen-final-boundary-full.log. The strengthened numeric-comma test also
passed in the final 46-case critical check. Final real validation continues with
frozen production sources/prompts; no more model/threshold/font/budget changes.

Atomic local source commit: 62f41d1 (fix(samples): bind module evidence and recover
grounded prose), seventeen task files, no push. Working tree was clean after
commit. Local AGENTS/report remain excluded; no paper/output/log data staged.
Final read-only audit /tmp/postergen-final-boundary-audit.json: 18 critical boundary
files byte-identical to d5edeff, 12 verified foundations/174 resource references,
nine finalized samples and existing bundle hashes valid, original failed-draft/
foundation/FINALIZED hashes unchanged. All 124 current code/prompt files match
the final run manifest.

Final real validation outcome (confirmed after quota interruption):
run_8229d8748aa94d3e884f finalized **fit_failed**, not poster success. Its six-module
preparation passed: 21 verified expressions / 585 words, all 19 required evidence
IDs covered, 20 initial passes plus one scientifically bounded correction, zero
rejections, final affected-module context check passed, READY present. The
correction changed an unsupported "state-of-the-art generalization" conclusion
to "improved generalization", retaining the 73/10-animal conditions and named
comparators. No request retry/truncation/failure occurred in this preparation.
Twenty expressions became protected under the unchanged essential/required-source
contract. All 15 family attempts exhausted bounded search at estimated_height /
NO_FAST_FEASIBLE_VARIANT. No poster, Critic score, PNG/PPTX or inspection template
was produced. Supervisor exit0 / run COMPLETED is finalized failure, not success;
exit.json records 1319.26 seconds (21m59s), no owned survivors, temporary supervisor
removed. The approved real successful-poster acceptance criterion is NOT met.

Post-interruption diagnosis uses saved inputs strictly read-only, on CPU without
model requests or writes under the run. Exact LayoutAgent measurements of the
20 protected expressions plus headings, omitting ALL visuals for a generous
lower-bound diagnostic, give:

| Equal-width diagnostic | Width per column | Total module heights | Raw column height sum |
| --- | ---: | ---: | ---: |
| Two columns | 25.48 in | 52.963 in | 55.760 in |
| Three columns | 16.64 in | 80.766 in | 83.640 in |
| Four columns | 12.22 in | 106.033 in | 111.520 in |

These totals exclude inter-module gaps and every visual. The actual default
optimization-route gap is one body line (44/72 = 0.611 in), not the standalone
section_spacing=1.0 setting. The three-column text/heading sum leaves only
2.874 column-inches before these gaps, render reserves and all visuals. The
two-column sum leaves 2.797 column-inches before its four gaps and all visuals.
They show substantial genuine content pressure at unchanged
44pt body / 64pt section headings; they do not prove impossibility across all
fifteen geometries. Diagnostic JSON: /tmp/postergen-final-exact-capacity.json.
Further exact-search replay distinguishes conservative-estimate rejection from
actual search failure without changing production algorithms or physical gates.

Current remaining interface limitation: Curator/Writer receive only soft size
references. In this actual sample Writer still produced 585 words (39% above
the 420-word upper reference), marked 20/21 expressions essential, and placed
164 words in one evaluation module. Twenty protected expressions total 555 words;
four expressions / 110 words have no direct mandatory-evidence coverage but were
marked essential by Writer. This does NOT establish that they are dispensable:
some provide mechanism, interpretation or evaluation prerequisites. They cannot
be silently unprotected/dropped merely to make geometry pass.

The current physical repair interface works one original expression at a time.
Actual accepted trial actions targeted five expressions in three capacity rounds;
the first two overages were only 0.093 and 0.048 inches. Their verified shortening
did not make a whole family feasible; remaining attempts correctly reported
exhausted capacity allowance. This is inadequate evidence to claim that increasing
family count, changing font sizes or adding more random real runs will solve it.

A proposed FOLLOW-UP, not implemented or accepted as finished here, is a
sample-only whole-module coordinated compaction action under the EXISTING layout
repair ledger/action limits. Retain every original protected root, responsibility,
local prerequisite, necessary condition/number/comparator and explanatory order;
generate coordinated per-root variants rather than merging provenance IDs. Any
changed wording must pass the existing full-body support/relationship checks and
explicit information-preservation check, followed by an affected-module context
check and exact physical fitting. Reject incomplete/unsafe batches atomically;
never obtain a fit by weakening gates or changing the meaning of essential.
Capacity diagnostics should target the module's complete load rather than only
a tiny local miss. This adds a new repair action and needs a separate concrete
implementation/review scope; it is not silently represented as part of the
already committed interface repair. A new official validation must still start
fresh sample science using only a strictly compatible original paper foundation.

After the last real outcome finalized, a read-only recheck verified all 12 paper
foundations, 174 original resource references, 10 finalized sample records and
existing published bundle hashes. Log: /tmp/postergen-final-history-recheck.json.

Read-only boundary audit /tmp/postergen-assignment-boundaries.json verifies 18
classic/extraction/design/layout/render/storage/cache boundary files byte-identical
to d5edeff, seven historical foundations and 89 resource references, all six
historical finalized samples and their published bundles. Recorded failed-draft,
foundation and FINALIZED hashes match; the old exceptional loader is absent.



## Module-plan interface repair after the one-off failure (2026-10-22)

The user requested these fixes after the real run finalized preparation_failed.
Baseline source commit: 98fd690. No new model-backed generation is launched, no
cache-exception entry is recreated, and no historical runtime file is changed.

### Failure evidence and limits

Run run_d7b03f0e308b4d0796ab ended FAILED at 15:10 Beijing (about 6m17s):
Planner returned 12 units in 250.38s; module Curator returned normally in 126.28s,
then normalize_module_plan rejected the response. Both requests finished with
stop; no network retry, request failure or output truncation occurred. The old
single error conflated empty evidence with invalid IDs/ownership. The response
was only saved after normalization, so the original rejected JSON is lost. No
claim is made about the exact failing module/ID or replay of that lost response.
The one-time loader and its directory were removed before generation; exit.json
confirms exit code 1 and no owned GPU processes remaining. Old outcome is intact.

### Implemented behavior

- Structured ModulePlanValidationError records module index/title, distinct codes
  and offending IDs; ambiguity records candidate original source units.
- Per-evidence original source IDs are supplied to Curator. Uniquely assigned
  evidence can deterministically complete omitted owners, with an explicit log.
  It never changes selected IDs, grouping, body wording or required evidence.
  Shared evidence requires an explicit original owner, independently of evidence
  order; an owner auto-added for another evidence cannot guess that choice.
- Unknown/unplanned evidence, invalid/unrelated owners, empty/malformed modules,
  empty evidence, missing indispensable evidence and invalid/duplicate visuals
  remain rejection conditions. No generic recovery modules or new semantic judge.
- module_planning_requests.py stores sample/input identity plus digest-bound
  initial/corrective raw responses BEFORE parsing, parsed drafts and detailed
  validation. The accepted plan carries source-normalization/diagnostic summaries
  through existing science checkpoints and poster diagnostics.
- Only a diagnosed model-format/contract failure permits one corrective logical
  call with the archived draft and exact feedback. Its durable pre-call charge
  is independent of the existing four layout-content rounds and one structure
  re-curation allowance. Standard physical transient retries remain unchanged.
- Restart reuses archived initial/corrected responses; a charged missing response
  or corrupt/input-mismatched history fails closed, without an automatic remote
  resubmission or refunded correction. Invalid second output stops preparation.
- Classic, Writer/Verifier, family geometry/compiler, physical gates, renderer,
  all-score/unclassified publication and strict ordinary cache checks are unchanged.

### Validation

Initial related
regression: 92 passed (2 existing dependency warnings; 124.41s). Final new-interface
suite: 44 passed (2 existing warnings; 8.67s), including full normal preparation
nodes to synthetic publication after a corrected draft. All model calls are stubs.

Offline actual-input validation: /tmp/postergen-module-interface-real-input.json.
Synthetic drafts over the real 12-unit/160-evidence Planner input accept unique-
source omission and a valid cross-unit module; all 21 required evidence IDs stay.
Empty/unknown/unplanned evidence and unrelated source references are separately
rejected. Original foundation, Planner and FINALIZED file hashes were unchanged.
No original failed Curator output is available, and no new visual-quality result
is claimed by these tests.



### Final verification

Atomic local commit: `d5edeff` (`fix(samples): harden module plan provenance and correction`), six tracked files. No push.

- Full CPU suite: 813 passed plus 5 subtests; 750.29 seconds. Four existing
  dependency deprecation warnings; no failures. Log:
  /tmp/postergen-module-interface-full.log.
- Final focused interface suite after strengthening the integration assertion to
  use the actual layout budget_usage counter: 44 passed; 8.85 seconds; two
  existing warnings. Log: /tmp/postergen-module-interface-final-focused.log.
- Read-only boundary audit: 20 classic/scientific/layout/render/cache safety files
  byte-identical to baseline; 15 peer families intact. Six historical paper
  foundations, 72 visual-resource references and the one existing published
  poster bundle verified against stored hashes/finalization. No exceptional cache
  entry exists. Audit: /tmp/postergen-module-interface-boundaries.json.
- git diff --check passed. Six tracked task files only; runtime data and local
  AGENTS/report remain excluded. No new real model/GPU generation was launched.

## Authorized one-off real sample launch (2026-10-22, 15:03 Beijing)

- User authorized one real sample and required the exceptional old-evidence reuse
  entry to disappear after use. No permanent source, prompt, config or CLI change.
- New run: `run_d7b03f0e308b4d0796ab`; source foundation:
  `run_2dd3e09720624e259f24` (Neural Encoding and Decoding at Scale).
- Qwen3.8-27B text/vision; 54x36 inches; samples=1; run seed=1494476416.
- Preflight checked matching input/model identities, original foundation digest
  4e2df2fb6921e7d1fdbf1293a0e5cbc8c0982775c8cd43e875b83ebfbf5dcb94,
  asset hashes/ownership, all evidence excerpts and optional metric excerpts in
  their original source chunks. The extraction delta was proven to be exactly
  the reviewed metadata-heading filter by removing that block in memory and
  matching the old file hash. Request timeout/retry settings match; the new
  curation limit was explicitly recorded as unrelated to extraction.
- The skipped acknowledgments/reference chunks contributed no old evidence:
  all 274 evidence IDs were retained unchanged; scientific appendices remain.
- Only original paper fields/evidence/assets were copied into the fresh run.
  New Planner, module Curator, module Writer, Verifier and design/render/evaluate
  execute normally. The source is never modified and extraction is not claimed
  to have been regenerated under the new code.
- The sole executable `/tmp/postergen-oneoff-module-run/entry.py` and its parent
  directory were already deleted before worker execution. Only the in-memory
  current process retains the one-off loader; provenance includes its hash.
- Runtime records: `storage/rubrics_samples/background/module_prose_oneoff_20261022/`;
  supervisor PID 269638, generation PID/group 269641. Background launch confirmed
  a new model request from Narrative Planner after cache import completed in 0.11s.
- CUDA_VISIBLE_DEVICES=5; the supervisor cleans only its own processes and writes
  exit.json including GPU process checks. It does not stop any pre-existing GPU
  workload or the GPU 3 Qwen service. No result or successful poster is claimed
  at launch; inspect final result/bundle when this one-sample task finishes.



## Current implementation: module-first writing and diagnosed fit repair (2026-10-22)

Baseline: `3fff259`. The user approved both the detailed module-writing plan and
the small repairs diagnosed from Neural Encoding run `run_2dd3e09720624e259f24`.
This section supersedes the older v3 implementation description below; all earlier
validation and real-run evidence remains historical, not a claim for this version.

### Implementation and contracts

- Generator v4, preparation sample_science_v2, body sample_body_v2, curation v2;
  dataset/storage stay v2/schema 2. New runs freeze current code/prompts/config;
  old finalized records remain readable but incompatible runs cannot resume.
- Sample science is research Planner → module Curator → module Writer → existing
  ClaimVerifier with sample-only full-body checks and deterministic finalization.
  No second atomic writing/verifying bank or extra normal initial Curator call.
  Writer sees whole-story/neighbor tasks, original evidence and a dimensions/font-
  scaled soft word range. One display expression can combine related assertions.
- Exact quote coverage must cover every visible character, including signs/math
  operators, with valid evidence and explicit supported relationships. Existing
  numeric/entity/metric/comparison checks remain. Corrected text is freshly checked
  and must preserve necessary information. If correction/rejection changes module
  context, only affected modules are rechecked once against actual final wording;
  another rewrite fails rather than opening an unbounded verification loop.
- Essential rejection, missing indispensable evidence, absent module prose and
  broken local prerequisites prevent READY/publication and retain diagnostics.
  Required evidence protects one adequate supported expression, not every sentence
  sharing that citation. The Verifier must explicitly confirm complete expression
  of the indispensable assertion via covered_required_evidence_ids; a relevant
  citation or partially expressed evidence cannot satisfy mandatory coverage. All final prerequisite closure is reported explicitly.
- Canonical source_plan_unit_ids preserve every original scientific source. A
  mixed-origin expression has no fictitious single section_id. Root provenance
  drives modules, retrieval, reading, content adequacy and verified fit variants.
- Layouts install immutable verified module prose and preserve explanatory order.
  Auxiliary setup is not automatically accumulated into these written modules.
  Genuine auxiliary ownership failure still routes to shared pregeometry repair.
  Core hints prioritize substantive method/result/goal expressions, preserving
  conditions-first order. Existing optional key-visual candidates are retained
  using original scientific role provenance, including mixed module origins.
  Existing exact same-source thin-module grouping, subset/compaction/completion,
  measured refinement, Preflight, RenderFit and rollback remain. Fifteen peer
  registrations/geometry algorithms and standalone classic prompts/graph remain.
- All fast/exact failure exits include preparation/merges and module loads. Curator
  feedback keeps closest/worst per-module pressure instead of eight repeated small
  misses. Re-curation triggers only on explicit shared structure failure, spends
  one separate durable charge before work, and cannot reset content/visual budgets.
  Title-only/reserve-only/structurally unchanged revisions cannot reopen the pool.
  Quality targets prioritize missing information then gap/use severity with fair turns.
- A science-bound per-sample color cache avoids duplicate family calls. Explicit
  --paper-cache-run-id copies only compatible hash-verified paper/evidence/assets,
  never sample prose, scores or poster/templates. Changed extraction identity
  rejects reuse (including caches produced before this extraction-code change).
  Copies are checked against the original frozen resource hashes, including a
  mutation between validation and copy. A cache-validation error records FAILED
  before sample calls rather than leaving a stale RUNNING projection.
  EvidenceBuilder skips explicit references/bibliography/acknowledgments only;
  research appendices remain. Planner retains compact source-order metadata rather
  than repeating full source paragraphs. These are bounded cost reductions, not
  promises of a specific runtime or first-attempt success.
- Official all-score/unclassified poster and inspection-only sibling template
  publication remains. No old Campaign data, Rubrics mining/Harness, semantic-image
  judge, necessity-v2 or key-visual feature has been introduced.

### Validation evidence

New no-model tests cover module planning/writing/verifying through actual nodes,
multisource and colliding-ID provenance, full/partial/foreign/mathematical support,
critical rejection, dependency preservation, required-source selection, final-context
refresh/failure bounds, sample/family isolation, all four checkpoint interruptions,
all fifteen shared family search/compile paths, no-op revisions, separate durable
budget, color reuse, and paper-cache input/model/code/resource/digest rejection.

Read-only replay of the failed Neural sample's original classic fit still reports
NO_FAST_FEASIBLE_VARIANT; it now exposes both automatic setup merges and the
13-expression/293-word method module in its failure diagnostics. This diagnoses an
old frozen board, not a claim that old prose was automatically repaired. Replay
report: /tmp/postergen-module-layout-replay.json.

Nineteen classic/render/measurement/family core files and original classic prompts
were compared byte-for-byte against the baseline: all identical. Historical paper
foundation digests, all 55 source-asset references across five runs, finalized
record digests and the saved poster bundle passed read-only checks. Report:
/tmp/postergen-module-boundary-verification.json. No model service was called,
no source paper/poster was changed, and no old run was resumed.

First broad run: 730 passed, 5 subtests, one CLI fixture failed because its mock
omitted the real run's failed_samples counter. The fixture was updated; CLI tests
passed in the 55-test expanded focused run. Further context and color tests were
added; the initial missing test-only Path import was corrected and selected tests
passed. The subsequent full run passed **760 tests and five subtests** in 747.08 seconds,
with four existing dependency deprecation warnings. Later final assertion/cache/
visual-boundary additions were covered by complete affected-file regression runs;
the final combined result is recorded below.

The synthetic module was measured and rendered through the actual editable PPTX
and PNG code in /tmp/postergen-module-render-60ko3mre/. Reopened PPTX text matches
the entire expression; actual LibreOffice/PDF RenderFit passed **1/1**, zero issues.
This is a text-interface/overflow check, not a full academic poster quality result.
Summary: /tmp/postergen-module-render-verification.json. Frontend Vite build and
sample CLI --help (including --paper-cache-run-id) passed.

Final affected-file regression after all assertion, source-cache race,
visual-candidate, shared-structure and core-priority checks: **158 passed**, three
existing dependency warnings, in **127.74 seconds**. Together with the successful
760-test/five-subtest broad run, this covers every collected case and all later
changes; the final collection includes 60 new cases over the 709-test baseline.
The full-suite log is /tmp/postergen-module-final-pytest.log; the final affected
log is /tmp/postergen-module-final-focused.log. No source changes follow this
final affected-file run. Diff whitespace/compile checks pass. Local guide/report
updates are deliberately ignored; generated artifacts and logs are not committed.

Atomic local commit: `98fd690` (`feat(samples): write grounded module prose before layout`),
32 tracked paths. Working-tree and staged-path verification completed after commit;
local AGENTS/report remain ignored.

### Practical limits

No new Qwen/GPU paper generation was launched. CPU tests and synthetic rendering
check software contracts, not semantic model accuracy, visual equivalence to
upstream examples, general scientific completeness or multi-paper aesthetic quality.
Full-body coverage and final-context refresh may add verification cost. Mixed
scientific-role modules remain explicitly partial for reading proofs rather than
being assigned an invented single role. Real same-paper/model generation and a
second-paper observation remain the visual acceptance step.

## Current repair: observable requests and bounded sample curation (2026-10-22)

Baseline `7bf32b2`, archived in `/tmp/postergen-generation-fix-baseline-7bf32b2/`.
The user explicitly authorized these fixes and same-paper/model real validation.

### Observed failure and cause boundaries

The overnight Active Geospatial sample `run_afa7c3a7f0af4932bc69` ended FAILED after
449.28 minutes, nine family attempts, no rendered/scored posters. Curator accounted
for 24318.12 seconds (90.21%); layout optimizer 133.04 seconds. Client logical call
counts showed successful replies but did not expose internal retries. Service logs
showed repeated prompt-processing activity about every 500 seconds inside one
logical call, matching the SDK plus outer retry policy. Inputs were about 22.3k
tokens, less than some historical same-paper requests; output was 6.2k-7.4k tokens
at about 14.6 tokens/s, close to the 500-second request deadline. Prompt growth
alone is not a sufficient explanation for those long waits.

The eight fit failures were dominated by estimated height. Current plans retained
55-60 of 72 claims, typically marking 32 required. A historical same-PDF success
started with 65 optional claims and fitted 17 claims/373 words; this is not proof
that 17 claims is a universally correct scientific target. Necessity/condition
contracts materially restrict the available selections. Three usable capacity
rounds were spent in the first two families; later families repeated Curator work
without capacity repair. Final auxiliary-module ownership failed because claim
pc_0051 depended on pc_0050 while their intended owners differed. Existing guards
correctly refused a cross-owner prerequisite split. The last failure was not a
proof that the whole paper is impossible to present.

### Changes

- Sample-only request policy: 900-second response, 15-second compatible-provider
  connection timeout, SDK retries zero, one explicit retry only for identified
  transient connections/service errors. Read/write/pool timeouts do not replay;
  truncated replies fail explicitly. Classic keeps its existing request/retry
  behavior. Per-physical-request JSONL logs record IDs, timing, safe error types,
  finish reason and usage without prompts, endpoints or credentials. Timing report
  model_request_attempts is separate from logical-call statistics.
- Immutable science-bound sample Curator plan reused across fresh family attempts.
  At most one targeted plan revision receives actual failure/height/ownership
  feedback and consumes the EXISTING durable capacity budget. No extra free
  rounds. Protected prior required claims stay visible/required and visible old
  prerequisites stay in the same module and retain their dependency records
  for later subset selection; invalid revisions keep the prior plan.
  A successful revision permits a new bounded family pass; max two plan versions.
  Revision work survives restart accounting and completed plans survive force-stop.
- Sample-only soft module/physical text-budget guidance and selective, nonredundant
  writing/necessity hints. Full scientific/evidence banks remain. Soft Writer references are 2-5 candidates/60-120 words per research unit;
  Curator starts around 2-4 claims per module, with essential-science overrides.
  No numerical
  content cutoff, required-root deletion, scientific prose rewrite by Curator,
  gate relaxation, necessity-v2 or new semantic judge is introduced.
- Sample Solver/compiler normalize absent typography interfaces to existing
  defaults throughout exact refinement; the initial real-input replay exposed
  that None previously crashed exact typography. All exact physical checks remain.
- Generator identity now explore_samples_v3. Dataset/schema remain v2/2. Old
  finalized records and sources are preserved; incompatible runs are not resumed.
  Classic, 15-peer family policy, official all-score saving, inspection-only local
  templates and sample independence remain.

### Validation and historical preservation

Initial focused lifecycle/model/API pass: 46 tests. New requests/curation plus
existing sample/preparation pass: 50 tests (overlapping, not additive counts).
Final CPU suite, deterministic real-input replay, both real model results and
atomic local commit are recorded below.

Final-fixture compatibility: old direct-runner fixtures now initialize the
optional curation cache and old standalone Curator fixtures supply 54x36 physical
dimensions. Original scientific/rollback assertions are unchanged. Those affected
files plus new execution checks pass (102 tests before the additional edge guard);
15 execution cases now include rejection of missing dependency records as well as
required-root deletion, missing conditions and split prerequisites. Cross-sample
cache isolation and interrupted-revision charging/restart are also exercised.
Final execution/sample/preparation focused pass: 55 tests. Accepted revisions
retain previously spent visual-restoration allowance; that path has an explicit
regression assertion.

No-model real-input replay: historical successful same-paper central-hero input
still reaches a feasible exact result (6 modules/16 claims, 913.74s on this CPU).
The old failed classic input remains explicitly infeasible with
NO_FAST_FEASIBLE_VARIANT/estimated_height (6.35s); no gate was relaxed to accept it.
This verifies deterministic compatibility, not universal feasibility or a speedup
of the unchanged exact geometry algorithms.

The live validation launched with the core patch, before final conservative
revision guards additionally required original dependency metadata and preserved
visual-restoration accounting when opening a new family pass. That small
post-launch guard and visual-restoration accounting across an accepted revision
are verified offline; code identity in the validation manifest
faithfully records the launch bytes and is not rewritten to claim otherwise.

Before changes, SHA256 inventory saved for all 2961 existing files under data,
output and storage. Historical artifacts are never edited by these fixes.

Real validation creates a NEW one-sample run with the same PDF, local model IDs,
dimensions and seed. To avoid repeating unchanged extraction, it hash-checks and
copies only original paper/figure/evidence cache from the failed run into the new
run, then executes fresh new Planner/Writer/Verifier/Curator/design/render/evaluate.
No old sample prose, layout, variant, score or template is imported. Client work
is isolated to GPU 5 with supervisor cleanup; the GPU 3 service is untouched.

### First live validation exposed an additional scale problem

Run run_74a4dd53c5f842098d23 finalized one fit_failed outcome in approximately
26.6 minutes, with zero rendered posters. The driver's exit code was zero because
its original condition checked run completion, not poster availability; this was
NOT a successful poster validation. Its complete failure record remains unchanged.
97 physical requests started/finished; no retry, terminal request failure or
truncation. Initial/revision Curator took 292.83/279.05 seconds; family reuse took
about 0.01 seconds. One initial family pass plus a revised 15-family pass produced
16 failed attempts. All remained protected by estimated-height admission.

The writer still generated 62 verified claims, including 20 each for methods and
experimental setup. The revised Curator retained 27 required claims/639 words.
Only 9 claims/193 words were forced by Planner-required evidence; additional
Curator necessity decisions created most of the size lock. Generic “small” hints
were inadequate. No incorrect inference that all 27 may be safely deleted was
made. Instead, the final prompts provide explicit SOFT starting ranges, and the
physical word hint reserves more room for figures, headings and paragraph gaps.
All essential facts/conditions may exceed references; full banks and guards stay.
No hard limit, new semantic judge or required-root relaxation is introduced.

The first live run had no dependency edges or visual-restoration charges, so the
post-launch conservative guards would not have altered its observed execution.
All 2961 pre-existing artifacts remained byte-identical. GPU 5 was empty after
supervisor cleanup; the GPU 3 service was untouched.

After a 91-test focused pass, one NEW follow-up sample was launched at 09:31:21
Beijing in background/generation_fix_scale_validation_20261022_093121. It again
reuses only verified original paper/evidence assets and performs fresh sample
Planner/Writer/Verifier/Curator work. Its driver additionally requires one rendered
poster for a zero validation exit code. Final complete CPU suite: 709 passed, 5 subtests passed, 4 dependency deprecation
warnings, 620.64 seconds (/tmp/postergen-generation-fix-full-release.txt). Final
scale-focused pass: 91 tests. The follow-up sample passed 52 verified claims and
rejected 1; it then entered Curator with no request retries. Its source identity
matches all 115 current frozen source/prompt files. Real outcome and artifact checks are recorded below; the local commit is recorded
after the final staged-source verification.

### Final live validation and artifact checks

The final source/prompt identity (115 files) was frozen BEFORE follow-up launch
and matches the delivered source bytes. Run run_e21b1e0136c044fbb0e5 completed
successfully at 09:57:20 Beijing: one sample, one rendered/scored poster, 88.97
under the existing v10 baseline Critic. It is unclassified, generation_rubrics=null;
this is not the future strong-model Rubrics Harness or a user-defined score split.

Wall time 1550.84s/25.85 minutes, reusing only original paper extraction/evidence.
Parser/EvidenceBuilder were not rerun, so this is not a fresh-PDF extraction speed
benchmark. Planner 123.61s, Writer 317.93s, Verifier 190.16s, Curator 508.97s total,
layout optimizer 178.55s total. Two physical Curator requests took 259.412s and
249.129s; other family attempts reused the saved board in about 0.01s. All 92
physical requests completed with zero retries/failures/truncation. The aggregate
legacy Critic timing component remains zero because the runner invokes Critic
outside timed design nodes; its physical content/visual requests took 8.0/82.1s.
Use physical request records rather than interpreting that zero as no evaluation.

The final plan retained 20 claims/461 words, grouped by existing fit/presentation
logic into six display modules. The first/revised central family plus subsequent
peer searches produced seven internal attempts; the successful family was
four_column_modular, variant 58fc6d1e782f6790. Its own fit call took 89.92s, found
3/12 feasible variants, and reused 340 of 484 measurement requests (144 computed).
Scientific variants stayed inside the current attempt; required roots and three
original local prerequisite edges survived accepted re-curation. Nothing from
another sample's text, repair, score or template entered this sample.

Saved bundle:
storage/rubrics_samples/posters/run_e21b1e0136c044fbb0e5_sample_000001/
- poster.png / poster.pptx
- template.json / template.png / template.pptx
- evaluation.json / provenance.json / bundle.json / diagnostics/

ExplorationStore.verify_poster passes. Both PNGs decode (2048x1365 poster;
1600x1067 template). Native poster PPTX is one 54x36-inch slide with 30 shapes;
inspection PPTX is a normalized 16x10.667-inch slide with 24 blueprint elements.
Template source candidate and PNG/PPTX hashes match the actual final poster;
its purpose is inspection_only. Both actual images were visually inspected.
Preflight passed with zero issues; RenderFit passed 12/12 editable text matches
(6 section titles, 6 bodies). Existing reading hints still have partial role
coverage, and no new independent image/semantic judge was added. One successful
paper/sample does not prove all future model outputs fit or all aesthetic/semantic
relationships are correct.

Verification summary is /tmp/postergen-generation-fix-artifact-verification.json.
All 2961 pre-existing data/output/storage files still match their original SHA256;
no missing files. Both new validation records are retained, including the first
fit_failed run. The successful supervisor exited 0, generation work ended, GPU 5
has no compute process/allocation, and the GPU 3 service was untouched. Generated
artifacts, logs, papers, local reports and AGENTS are excluded from Git.

### Local commit

Atomic local commit 3fff259 (`fix(workflow): bound requests and reuse sample curation`)
contains 23 task-owned source/config/prompt/test/README paths (600 insertions,
16 deletions). Local AGENTS/report updates remain ignored. No generated runtime
or historical artifact is staged or committed; nothing was pushed.

---

## Current extension: scientific ownership tightening (2026-10-21)

The section below supersedes the original shared Parser-through-Verifier foundation
and dataset-v1 descriptions retained later in this report. Its implementation
baseline is `f60a569` (15 peer layout families), archived before edits under
`/tmp/postergen-tightening-baseline-f60a569/`. No model service or GPU job was run.

### Resulting responsibilities and flow

1. Parser + EvidenceBuilder create one immutable paper foundation per run: original
   text/chunks, visual assets/captions, title/authors and source-linked evidence.
   The sample Parser skips its legacy ABT summary; classic still calls it.
2. Each sample gets a fresh paper copy and runs NarrativePlanner, ClaimWriter and
   ClaimVerifier independently. Planner organizes research-content units with
   grounded source order/priority/necessary evidence. Writer writes candidate
   prose. Verifier retains the original scientific checks. These stages do not
   produce final layout modules or reuse another sample's wording/feedback.
3. Stage snapshots chain input digests; READY and sample_science are bound to
   paper/run/sample/seed. Completed stages survive force-stop. Durable stage-work
   charges precede execution and are separate from the unchanged repair budget;
   they count stage executions, not exact internal API requests. Source mutation
   stops preparation. Failures preserve diagnostic evidence without a poster or
   invented score and stop the run before family assignment/design/evaluation.
4. The sample's prepared science supplies its existing paper profile. Frozen
   slots/seeds/rules and prior planned family uses determine its family assignment
   before design. Coverage-first bounded semantic matching and all 15 peers remain.
   Scores and successful/failed retry families do not change planned coverage.
5. GroundedCurator owns display selection, modules, titles and local presentation.
   Color and title styling precede the unchanged family fitting pipeline; font,
   Preflight, Renderer and RenderFit follow. Existing bounded grouping, completion,
   verified fit/style edits, measurement caches, physical gates and rollback remain.
   Family retries reuse the current sample's verified preparation, while clearing
   attempt-local display state, variants, scores and repair output.
6. Final module provenance links display IDs to original claim roots/research units,
   evidence and paper sections. Module-context retrieval follows allowed curated
   roots as well as visible claims. A display-ID collision cannot import another
   research unit's evidence. Sample ContentAdequacy uses this mapping; standalone
   classic retains its original direct-ID policy. No scoring weights changed.
7. Every final rendered PNG/PPTX and inspection-only template stays together in the
   unchanged common poster pool, including low scores and evaluation failures.
   All remain unclassified. Internal attempts remain diagnostics. Original source
   data is run-owned; sample/poster diagnostics include the sample's verified
   science, repairs, source mappings and foundation/science digests.

### Compatibility and costs

- Generation version `explore_samples_v2`, dataset `rubrics_samples_v2`, storage
  schema 2 and preparation policy `sample_science_v1` explicitly identify this
  contract. V1 sample results remain readable; V1 run resume is refused under V2
  without writing or migrating history. New runs use the same storage root but
  have their own immutable dataset identity. Historical Campaign data is excluded.
- Paper cache is now `paper_foundation/paper_state.json` plus `identity.json`.
  Each sample owns `preparation/stage_*.json`, `model_work_ledger.json`,
  `sample_science.json`, `READY.json`, optional failure diagnostics, and a frozen
  `family_assignment.json`. Existing final-output snapshot recovery is preserved.
- Planning, writing and verification now cost work for every sample rather than
  once per run. Family retries do not repeat those successful stages. An interrupted
  unfinished stage can repeat on resume, with its additional charge retained.
- Original standalone graph, Planner/Writer prompt bytes, legacy ABT call and
  Balancer remain independent. No full Rubrics mining/Harness/update loop exists;
  generation_rubrics is still null. No new semantic judge or withdrawn visual/
  necessity-v2 mechanism was introduced.

### Verification of this extension

- Final preparation/storage/API focused pass: 42 tests; final scientific/provenance/
  completion/editorial focused pass: 140 tests. These are overlapping checks, not
  additive distinct coverage counts. All use offline fixtures or fake model replies.
- All 15 synthetic family outcome digests equal the pre-refactor archive: identical
  board/spec/exact-score/whitespace payloads for feasible cases and identical expected
  failure reasons for infeasible cases. This is not a 15-paper quality benchmark.
- Twelve core files (standalone graph, original Planner/Writer prompts, verifier,
  family solver/registry/geometry, layout agent, Preflight, Renderer, RenderFit and
  template exporter) are byte-identical to the pre-edit baseline archive.
- TypeScript type check, Vite production build and both CLI help checks pass.
- All 2557 historical files under data/output/storage match the pre-edit SHA256
  inventory; no files were added in those directories.
- Final-tree CPU suite: **694 passed plus 5 subtests**, four existing dependency
  deprecation warnings, 618.92 seconds. Log:
  `/tmp/postergen-tightening-final-full.txt`. No test failures or skips reported.
- Atomic local commit: `7bf32b2` (`refactor(workflow): isolate per-sample science
  preparation`), 24 paths, 925 insertions/145 deletions. Local report/AGENTS remain
  ignored and outside the index. No historical data or generated output is committed.
- No actual model-backed poster was generated. These regressions establish tested
  deterministic behavior and safeguards, not a guarantee of unchanged wording,
  runtime cost or visual quality under new independent model preparations.

---

Date: 2026-10-21. Baseline: c83300f, whose tree matches bab9907.

## Scope and user decisions

The user's PDF describes generation, external scoring, high/low reason extraction,
KMeans clustering, per-cluster Rubric synthesis and semantic deduplication into a
Rubrics library. That library is the eventual object of iteration. This change
implements the agreed first stage: remove the former poster/template evolution
mechanisms and preserve independent Explore generation for collecting samples.
It does not implement the complete PDF or automatically follow its algorithm.

Standalone classic three-column generation remains a separate path. Independent
samples retain the existing twelve-family Explore fitting and scientific repair
capabilities. Only a final outcome is an official sample; internal attempts and
re-renders are diagnostic. All rendered final posters are saved, including low
scores and evaluation failures. Layout templates belong solely to their poster
and cannot be used as another poster's reference. Old outputs remain untouched
and outside the new dataset. Score splitting awaits a user-defined threshold.

## Implementation

- Removed old Campaign/Batch persistence, Portfolio/Lineage scheduling, mixed,
  Improve and strict Validate modes, RevisionPlanner/revision operation agents,
  template library/transfer/promotion/seats and global/archetype learning.
  Their mode-only tests were retired; shared scientific/layout/recovery tests
  were migrated rather than removing the underlying safeguards.
- Added `PosterExplorationRunner`, `ExplorationStore`, `RunControl`, the new CLI,
  progress events and `config/exploration_config.yaml`. The stable command is
  `python -m src.workflow.critic_pipeline --paper_path ... --samples N`.
  Omit `--run-id` for a new run; use the exact new run ID to resume.
- Frozen parser-through-verifier scientific foundation is copied into a fresh
  state for every sample/family attempt. Sample-local scientific variants,
  selections, boards, scores, Critic history and diagnostics never become shared
  generation knowledge. Original paper resources are hash checked on resume.
- Family selection v2 freezes a coverage-first plan using planned sample counts,
  with the original bounded semantic preference. Scores never affect the plan.
  Original measurement reuse, bounded geometry/beam search, near-miss search,
  scientific verification, capacity/quality repair, module completion, exact
  compilation, typography preflight, whitespace guards, RenderFit and same-attempt
  recovery remain. Same-sample fixed geometry and ownership locks still work.
- Generic current-sample content/recovery and compiled-text/whitespace guards
  live in `content_guards.py` and `sample_safety.py`; removing Improve did not
  remove these scientific or physical checks. Removed the obsolete `loop_config`
  override and invalid-action fallback that derived repairs from Critic issues;
  the optimizer accepts explicit sample-local actions only.
- Critic retains the baseline seven dimension weights and evaluator policies.
  Its report schema v4 has a neutral evaluated decision and a diagnostic quality
  reference. The existing 78 reference cannot filter saved samples or define
  future high/low groups. Failed/incomplete evaluation has no official score.
  New reports remain distinct from untouched historical reports.
- Each run freezes inputs, models, source/prompt/policy/font identities, seed and
  finite task count. Exclusive lease, durable repair charges, immutable finalized
  markers, verified bundles and pending final-output snapshots support restart.
  Publication recovery never regenerates or re-scores an already final poster.
  Corruption fails closed. Known geometry failures receive bounded family
  retries; shared pregeometry failures and programming failures stop explicitly.
- WebUI now exposes independent samples and classic generation, sample counters,
  all-score previews, local template/evaluation links, pause/stop and exact-run
  resume. ZIP export includes every saved poster bundle. Retired Batch parameters
  fail explicitly; historical Campaign administration is absent.

## New storage contract

All final posters are together under `storage/rubrics_samples/posters/<poster_id>/`:

```
poster.png                 poster.pptx
template.json              template.png             template.pptx
evaluation.json            provenance.json          bundle.json
diagnostics/
```

Templates use final compiled poster geometry, generic labels and editable shapes.
They contain no scientific prose or original figure pixels and are inspection-only.
Every outcome is explicitly `grouping=unclassified`, dataset `rubrics_samples_v1`,
with baseline scoring-profile identity and `generation_rubrics=null`. The latter
does not claim a Seed Rubrics library has already been built.

Run manifests, copied inputs, scientific foundation, frozen plan, events, sample
results, immutable `FINALIZED.json`, pending publication snapshots and internal
attempt artifacts are under `storage/rubrics_samples/runs/<run_id>/`.
Terminal task failures count toward the finite task target; an N-task run does
not promise N successful posters or retry indefinitely. Graceful stop finishes
the current sample; cooperative force-stop preserves diagnostics and charges,
and a later resume starts a fresh attempt for that unfinished sample.

## Verification

- Independent generation, persistence, interrupted publication recovery,
  scientific-state isolation across samples/resume, missing/stale artifacts,
  evaluation failure, low-score saving, local templates, API and CLI integration:
  31 focused tests passed.
- Title correction, current-sample geometry locks, safety guards and family
  selection v2: 63 focused tests passed.
- Shared family design policy: 34 tests passed, including all twelve families,
  a future-family extension, finite repair budgets and physical/scientific locks.
- After the final invalid-action fallback cleanup, all 125 focused content,
  grounding, module-completion and expression tests passed, including a new
  regression proving malformed actions cannot trigger score-driven model calls.
- The same deterministic synthetic inputs were compared before/after refactor:
  all twelve result digests match. This includes both successful compiled cases
  and expected fit-failure outcomes, not twelve successful rendered papers.
  Hash inputs bind boards, LayoutSpecs, exact-score summary and whitespace (or
  explicit failure reason). Evidence is retained under `/tmp/postergen-*`.
- Historical inventory: all 2557 previously recorded files under data/output/
  storage still exist and have identical SHA-256 hashes. No old Batch advanced,
  no historical poster/template/knowledge record was rewritten or removed.
- Frontend `tsc --noEmit` and Vite production build passed. Both CLI `--help`
  entry points imported successfully. `git diff --check` passed.
- Final full CPU suite on the final source tree: **624 passed, 5 subtests passed**
  in 455.96 seconds; four existing third-party deprecation warnings. Command:
  `.venv/bin/python -m pytest -q`. The preceding full run also passed (623 tests);
  the final run includes the added invalid-action regression.
- Atomic task commit: `a916e5f` —
  `refactor(workflow): generate independent Explore samples for Rubrics`.
  113 changed paths; source/config/README/tests/WebUI only. Local AGENTS/report
  remain ignored and outside the commit. Post-commit status and stat were checked;
  the tracked worktree is clean. No push or real generation was performed.

## Limits and deferred work

No real model/GPU generation was performed. CPU regressions and identical
synthetic layout results provide evidence of preserved behavior; they cannot
prove identical quality for all future papers or stochastic model responses.
Existing baseline semantic/association limitations and the withdrawn
post-bab9907 visual/necessity protections stay as documented; none are silently
reintroduced here. Third-party deprecation warnings are unrelated to this task.

The strong external scoring Harness, user-defined high/low grouping, Seed Rubrics
construction, Actor-Critic policy loop, clustering, semantic deduplication and
Rubrics library iteration remain future work. Historical outputs are not
automatically enrolled in any of these stages.

## Three additional peer families (2026-10-21)

The user authorized adding all three proposed layouts with every family at the
same level. The registered and enabled pool now contains 15 families, with no
priority tiers, default/special pools or new family-eligibility gates. The same
coverage-first selection and bounded semantic preference apply to every member.

- `framed_multicolumn`: full-width opening, two/three body columns, full-width
  closing region. Canonical body geometry has five zones.
- `narrative_evidence_grid`: a narrative rail, local two-by-two evidence grid,
  and a shared full-width conclusion. Canonical geometry has six zones.
- `central_evidence_band`: two upper regions, a full-width central evidence
  region, and three lower regions. Canonical geometry has six zones.

Registered deterministic callbacks provide bounded geometry changes through the
existing shared interface. Shared search retains its original geometry, beam,
exact, typography and model-repair budgets. Only the finite family-retry ceiling
changes from 12 to 15 so the larger pool is reachable during known fit failures.

The new `framed_columns` traversal processes full-width bands in vertical order
and finishes each intervening column, including local splits, before advancing
to the next column or closing band. A middle hero has no result-first exemption.
The existing conditional Planner-role hints and ordinary scientific/physical
checks apply; no new semantic association stage or automatic filler is added.

All 12 original registration dictionaries and their seeded geometry candidates
were compared with the preceding commit: identical. All 24 existing skeleton
assets are byte-identical. Three new PNG/editable-PPTX pairs were generated and
visually inspected. Real rendered poster data and historical run records are not
modified. Existing runs keep their frozen identities and refuse changed code or
configuration on resume; development does not rewrite or resume them.

Focused regression: **106 passed** in 247.87 seconds, covering the three new
families and all shared family design, selection, reading and preview tests.
Final full regression: **674 passed, 5 subtests passed** in 612.19 seconds, with
four existing third-party deprecation warnings. Command:
`.venv/bin/python -m pytest -q`. All original family, content, typography,
measurement-reuse, repair, renderer, independent-sample and API tests pass.
`git diff --check` passed. The historical inventory of 2557 files is unchanged.
No real model service, historical run, or Batch was started. Atomic commit:
`f60a569` — `feat(layout): add three peer academic poster families` (17 paths).
Post-commit status/stat, the 15-member enabled pool, ignored local documentation
and the historical hashes were verified; tracked worktree clean.


### Authorized engineering replay: preservation interface correction (2026-10-23)

- Diagnostic root: `/tmp/postergen-engineering-module-replay-20261023T065442Z`.
  Original verified v5 sample science + attempt_0003 classic input, all model work
  Qwen3.8-27B / GPU5 client. Explicit `official_sample=false`,
  `eligible_for_rubrics=false`; source READY/science/foundation/snapshot and assets
  validated. No new sample preparation, template retrieval, publication or score.
- Initial attempt: one charged capacity round, 471.60s, no safe batch adopted.
  Module003 five expressions 164→131 words, module002 four expressions 120→94;
  all nine new expressions passed scientific verification. Preservation item0
  (module003) and item3 (module002) echoed input without verdict fields. Correct
  atomic rejection preserved the old board and empty variant bank. Source run
  hash inventory and all official-store filenames remained unchanged.
- Minimal follow-up fix affects only module_compaction.py and its tests: audit
  system role and final output schema after the entire input; missing/nonboolean
  grounded/meaning_preserved explicitly classified as response-format failure.
  No semantic retry or weaker standard. 49 focused tests passed (4.30s).
- Follow-up attempt_0002 shares the SAME /tmp attempts-parent budget ledger;
  prior usage (capacity1,quality0), classic family1. It may spend at most one
  further classic-family round, not receive a fresh four-round budget. Native
  exact fit/Preflight/render checks stay mandatory. Full regression and real
  follow-up acceptance pending; independent successful-poster acceptance also
  remains unmet because run_56650dbf9beb46df85a6 stopped upstream in writing.
- Read-only complete historical verification: 14 paper foundations, 208 source
  resource references, 11 finalized samples and one poster bundle passed.

- Final CPU regression for preservation fix: **908 passed +5 subtests**, four
  existing warnings, 749.43s. `/tmp/postergen-module-preservation-full.log`.
  Eighteen classic/extraction/geometry/renderer/store boundary files remain
  byte-identical to 0bc819d. Only module_compaction.py and its tests changed.
- Corrected classic follow-up: 376.81s overall (374.4s capacity stage),
  nine scientific verdicts and nine preservation verdicts passed; both whole
  modules verified atomically (284→223 words; 2015→1647 characters). Exact module
  heights each decreased2.93333in. Search placement improved1→3, but bounded
  classic search remained NO_FAST_FEASIBLE_VARIANT. No active variant bank or
  poster adopted. Source hashes and official-store inventory unchanged.
- Final engineering family retry is asymmetric_two_column from original source
  attempt_0013, fresh original science/board with no cross-family variants. Same
  diagnostic ledger already spent capacity2/quality0; only one capacity round
  remains. A mistaken four-column source snapshot was rejected before model or
  charge by the startup assertion; corrected input and the bootstrap diagnostic
  are retained. No additional stochastic official sample was launched.


## 2026-10-26 — Single-family global writing and joint preparation

User authorization: execute the agreed final plan, including offline validation
and one fresh Neural Encoding plus one fresh Active Geospatial acceptance. No
historical sample science, poster, score, variant or inspection template is a new
sample input. Original paper cache reuse must pass the standard strict API.

Implemented generator `explore_samples_v7`, preparation `sample_science_v4`, with
unchanged body science contract `sample_body_v2`, dataset v2/schema2. The shared
Parser/EvidenceBuilder and standalone classic graph/prompts are preserved.

Default sample flow:

```
original paper/evidence -> independent Planner -> freeze ONE family
 -> global module Curator -> physical family space brief -> ONE global Writer
 -> joint draft physical search / shared bounded edits / scientific verification
    / actual verified-text refit, until a coherent candidate or bounded failure
 -> freeze science + adopted board/LayoutSpec
 -> install candidate -> color/title -> compile ONLY that candidate
 -> font -> Preflight -> Renderer -> RenderFit -> baseline Critic -> all-score save
```

Family choice uses an explicitly unwritten planning profile: prose density/count
are unknown, not invented low density. Coverage counts frozen assigned tasks,
including failures, without using scores. The runner no longer retries families
or opens a separate targeted re-curation pool. Normal sample-content/fit failures
produce detailed final reports and continue to the next task; programming, model
service/auth, filesystem and corrupt-history failures stop the run. Task count is
not a promise of poster count. Closing regions can contain genuine findings and
interpretation without a fabricated Conclusion module. Zones retain legal local
split/span/stack variants; six real modules in four columns are tested.

`family_capacity.py` exposes zone inches, module stacking capacity, actual title
measurement, estimated picture/text load and soft size/font-aware word targets.
The global Writer sees all module tasks and space in one request, normally writing
2–3 short entries per module. Initial format correction shares the existing single
preparation allowance, preserving already valid neighboring modules. Raw/parsed
responses and scientific checks remain bound to exact inputs and sources.

`joint_preparation.py` owns convergence. Its explicit draft lookup in
`utils/grounded_content.py` is physical-only; no verified flag, verified bank,
Critic or publication is fabricated for a draft. Scientific verification uses
existing deterministic number/entity/comparison and complete visible-character
coverage checks, indispensable-assertion verdicts intersected with actual supported
spans, and local relation/context checks. Changed context or prose is rechecked;
identical verified expressions with identical context may reuse science. Actual
verified text is refitted before freezing. Late compilation checks the frozen
science/candidate digest and performs no new family search.

Selective editorial revisions keep original root IDs and canonical scientific
origins. Optional detail may be omitted with explicit reasons, but necessary facts,
conditions, scope, comparison basis and prerequisites need a positive explicit
Verifier preservation verdict. This is separate from old pure compaction's stricter
whole-expression preservation. Diagnosed supporting-module ownership can propose
compatible source/owner grouping using the existing source/function rules; adoption
requires an explicit edit, retains all scientific roots/origins and rechecks the
new module context. No initial automatic auxiliary accumulation, retired
necessity-v2, semantic admission or image-association judge is introduced.

One digest-bound sample-wide content-edit ledger has 4 substantive rounds: at most
3 capacity/structure plus 1 reserved quality, max2 target modules per round. Draft
edits and verification callbacks share it; no per-family reset or extra free
re-curation. Charges precede calls and survive interruption. Missing charged
responses fail closed. Existing preparation correction accounting remains separate.
Quality regression rolls back to the actually verified feasible baseline. Ordinary
optional source-key-visual offers and bounded exact visual restoration remain;
visual probes have their own finite durable ledger. Measurement scopes/cache reuse
are retained, including reuse within joint work.

Each actual render has a unique `work/renders/render_<n>/` directory with editable
PPTX, PNG, sibling inspection template JSON/PNG/PPTX, actual geometry and parent
provenance. Title correction creates a derived candidate; frozen baseline data is
unchanged. Final all-score/unclassified publication remains atomic and templates
remain inspection-only. No-poster failures have no score, rather than low scores.
Current results carry a generation-policy version for future cohort selection;
Rubrics mining/library/Harness is still unimplemented (`generation_rubrics=None`).
Old samples and files are never migrated or rewritten.

Validation in progress (not a claim of real generation success): 109 focused CPU
cases passed; latest full regression is running. The initial regression exposed
obsolete family-retry/re-curation assertions; they were updated to verify the
reviewed one-family policy. A CPU rendering test originally failed to isolate a
quality request (service returned NotFoundError); CPU tests now prohibit remote
model construction and stub quality/semantic model work explicitly. Actual geometry,
compile, typography, Preflight, editable PPTX and template rendering run on CPU;
PNG conversion is stubbed only in that CPU test, so real LibreOffice/RenderFit
acceptance remains required. Full test/output/acceptance evidence is kept under
`/tmp/postergen-joint-preparation-20261026/` and the real jobs' background folders.

Read-only service preflight advertises only `Qwen3.8-27B`; ambient local-model names
differ. Validation processes explicitly use that advertised ID for both text and
vision, without editing `.env`. Under that exact identity, the original Neural
foundation in run_da8fb99a67ca47e6b6fb passes extraction/input/model compatibility.
No Active Geospatial foundation matches current strict extraction/request identity;
its real acceptance will prepare original paper evidence from scratch. GPU5 is
clear; the existing GPU3 service PID5003 remains untouched. Real jobs will be
supervised with process-group cleanup and GPU5 checks.


CPU validation before real acceptance: full suite 942 passed +5 subtests
(772.59s, six dependency warnings); final new-boundary suite 74 passed;
final joint suite 36 passed (including the final two error-classification cases).
`compileall`, CLI help and `git diff --check` pass. The initial failed/obsolete
runs are retained as diagnostics, not counted as successful validation. All 5,362
baseline historical files are present and byte-identical before acceptance.


Committed-tree regression and first real result:

- Atomic commit `f25ee8a`,41 tracked paths, local/no push, clean worktree.
- Exact committed-tree full regression: **944 passed +5 subtests**,772.43s,
  six dependency warnings. Final focused joint36/boundary74 tests also passed.
- Neural run `run_1df1257f678c4dd6b9eb`, original paper cache only from
  `run_da8fb99a67ca47e6b6fb`, fresh Planner/Curator/Writer. Family frozen
  `central_evidence_band` after Planner and before Curator. Planner182.05s;
  Curator117.27s included one charged local output correction. Six modules,
  sixteen indispensable evidence IDs,21 expressions,358 initial words. Global
  Writer used one initial whole-poster request. Three durably charged capacity
  edit rounds targeted modules2/3,5/1,6/4; final332words, no expressions omitted.
  The quality round remained reserved. Each edit was followed by actual same-family
  physical search; final reading/height constraints remained unresolved.
- Outcome: `preparation_failed`, no verified science READY, no design attempt,
  PNG/PPTX, Critic or score. Run COMPLETED and supervisor exit0 only mean finalized
  task bookkeeping. **Real Neural poster acceptance is UNSATISFIED.** Supervisor
  exit/cleanup record confirms GPU5 empty at01:53:56UTC; GPU3 untouched.
- Read-only CPU probe pinned modules in original scientific source order within
  this same family; conservative planning then failed top-region height (module1
  closest0.254in over, module2 progress over3.077in). Files are only
  `/tmp/postergen-joint-preparation-20261026/neural_reading_probe.*`; no remote
  calls, original history mutation, scientific admission or sample publication.
  This is bounded-search failure, not proof of physical impossibility.
- Second agreed real acceptance: Active Geospatial `run_0ac92a0a8f264f4f8319`,
  from-scratch Parser/EvidenceBuilder, started01:56:56UTC. Background folder
  `storage/rubrics_samples/background/joint_v7_geospatial_20261026/`, supervisor
  326603/generation326605, all client work GPU5. Still RUNNING at this report
  update. Source remains exactly committed while the run is active. Inspect final
  outcome and cleanup before claiming completion or launching another sample.


### Final real acceptance and cleanup (2026-10-26)

Active Geospatial `run_0ac92a0a8f264f4f8319` completed real end-to-end generation:

- Source/vision model: advertised `Qwen3.8-27B`, explicit process-local environment;
  cold Parser/EvidenceBuilder,88grounded evidence items,2figures/5tables available.
- Family frozen once: `central_evidence_band`; no family retry, no old sample prose.
  Six planned/final modules; Writer initial304words/15expressions, final279visible
  words/14verified expressions, all10indispensable evidence IDs explicitly covered.
- Capacity editing rounds0; exactly1reserved quality round. Its output remained
  scientifically checked and passed actual-text refit and whitespace nonregression.
- Final compiled Preflight PASSED/zero issues and real LibreOffice/PDF RenderFit
  PASSED/zero issues. No title correction was necessary. One actual render retained
  with PNG/PPTX plus sibling inspection template JSON/PNG/PPTX and render provenance.
- Baseline Critic score87.65, statusscored, groupingunclassified. All42physical
  requests completed;0failure,0retry,0truncation. Original scientific/source,
  physical and publication gates were not relaxed. Reading order matches positions
  and has no source-order conflicts; its role classification remains partial for
  one mixed-source task module, explicitly preserved in the reading audit.
- Timing: Parser26.10s, EvidenceBuilder1593.51s, Planner127.70s, Curator89.62s,
  space0.68s, initial globalWriter166.70s, joint255.93s, candidate compile8.85s,
  final Preflight3.26s, Renderer1.90s, RenderFit2.57s. Cold evidence extraction
  dominated this run; these timings do not predict every paper/model/family.
- Final bundle:
  `storage/rubrics_samples/posters/run_0ac92a0a8f264f4f8319_sample_000001/`.
  Store bundle verification and actual PNG/PPTX template source-artifact hashes
  pass. Actual final geometry is exported, never a generation input.
- Manual visual inspection: the poster still has substantial whitespace, a small
  central figure, and only one finally visible scientific visual (two curated
  tables were not adopted). The87.65baseline score is not proof that aesthetic
  quality matches upstream examples. No high/low threshold has been invented.
- Supervisor exit0and cleanup at02:37:26UTC; generation326605 and supervisor326603
  exited, GPU5empty. First Neural job also exited/cleaned. GPU3model servicePID5003
  remains untouched. No validation job is active.

The real result matrix is therefore **one successful poster and one bounded
single-family failed task**. The successful case validates the complete new route;
the Neural case validates preserved failure reports/budgets and exposes a remaining
content/reading/geometry fit limitation in that family. Do not claim universal
success or proof of mathematical infeasibility. No family fishing or additional
stochastic validation was performed.

A final diagnostics-only follow-up (`3b709e1`) fixes timing presentation for future
runs: cumulative space/joint/install time survives the bounded recent-record list,
and Verifier time is explicitly marked included_in_joint_preparation instead of0.
Classic timing output stays unchanged. This changes no generation, science, layout,
render or evaluation behavior, and rewrites none of the finished runs' timing files.
101targeted model-tracking/joint/preparation/sample/CLI cases pass (49.14s), plus
compileall/diff checks. The generation implementation tested end-to-end isf25ee8a;
its exact full CPU suite passed944tests+5subtests. No model/GPU run was repeated
for the timing-only addition.

Final historical audit checked all5,362baseline files: zero changed, zero missing.
Acceptance summary and detailed request/CPU probes are in
`/tmp/postergen-joint-preparation-20261026/acceptance_summary.json` and sibling
reports. Local AGENTS.md and this ignored report are maintained; no source push,
old-data migration or future Rubrics-library/Harness implementation occurred.


## 2026-10-26 — User-requested three-family background generation

At the user’s request, launched one unchanged v7 run with three independent
samples using the strict original-paper/evidence/assets cache from
`run_0ac92a0a8f264f4f8319` (Active Geospatial, 88 original evidence items).
Input/model/extraction identities and original foundation/resource hashes passed.
No sample prose, score, template or old scientific preparation was imported.
Dimensions54x36, Qwen3.8-27B text/vision, seed20261026, samples3. Normal fifteen-peer
coverage-first selection gives different families as each independent Planner
finishes; no forced-family override, source/config/prompt changes or free retries.

Run `run_bd07b4adfb414de98cff` launched at11:00 Beijing; strict cache reuse succeeded
and sample1 entered narrative planning. Supervisor330712 / generation330713.
Runtime folder: `storage/rubrics_samples/background/three_families_20261026/`.
Wrappers, launch handoff and baseline7148 historical file hashes are under
`/tmp/postergen-three-families-20261026/`. CUDA_VISIBLE_DEVICES=5; the existing
supervisor cleans only its own generation process group and records exit/GPU check
in exit.json. GPU3 Qwen service PID5003 and other workloads remain untouched.

The user then explicitly requested stopping continuous monitoring after launch,
with acceptance deferred. Both launched processes were alive at handoff. Generation
continues in the background; no poster/result/score or post-run cleanup is claimed.
Later acceptance must inspect FINALIZED results, owned nonempty PNG/PPTX and sibling
inspection templates, exact family assignments, final physical/scientific checks,
request failures, supervisor exit/cleanup and before/after historical hashes.
No test suite was run: generation code is unchanged. AGENTS was maintained locally;
all documentation/runtime data stay ignored and no Git commit is required.


### Three-family result inspection (2026-10-26)

Run run_bd07b4adfb414de98cff finalized3/3: one rendered/scored poster and two
preparation failures. Finished11:47:48 Beijing, approximately47m40 after launch.
- sample000001 / central_hero_side_rails: scored90.63 (baseline Critic), real
  published poster.png527602bytes and editable poster.pptx494637bytes, sibling
  inspection template JSON/PNG/PPTX. Final Preflight and RenderFit passed with
  empty issue lists. Direct visual inspection shows a prominent central method
  figure, two side rails and six modules; bottom whitespace and a small results
  table remain. This is not a universal aesthetic or family-success certificate.
- sample000002 / top_hero_bottom_grid: preparation_failed; single-family joint
  work did not converge after all three capacity edits. No PNG/PPTX or score.
- sample000003 / method_flow_spine: preparation_failed on the first charged
  capacity revision because a number was absent from its cited evidence. The
  scientific gate rejected the revision; no PNG/PPTX or score was published.

All7148 before-run historical file hashes are unchanged and none are missing.
Supervisor exit.json records exit0 and no GPU5 compute processes at03:47:48UTC.
Generation330713 has exited; no model rerun or replacement launch was performed.
COMPLETED/exit0 describes finalization of all tasks, not three successful posters.
Acceptance summary: /tmp/postergen-three-families-20261026/acceptance_summary.json.
No source/config/prompt changes or tests were needed for this read-only result
inspection; AGENTS/report updates remain local and ignored.


### Whitespace diagnosis after the three-family inspection (2026-10-26)

User asked whether original Explore capability was lost. Read-only source/history
and actual sample000001 artifacts confirm a partial orchestration regression, not
loss of the underlying solver. No source edits or new model/GPU calls were made.

1. V7 default_nodes replaced layout_with_balancer_node with frozen-candidate
   install/compile. Joint _fit still invokes fit_family_layout, exact refill,
   editorial refinement, global-whitespace selection guard and composition
   refinement. The final composition_refinement report contains four bounded
   exact trials, all infeasible; status=no_safe_gain. Those capabilities still run.
2. Original layout_with_balancer -> repair_family_fit -> complete_modules can
   restore original verified details and add_claim_from_evidence with bounded
   original-source search. New default joint preparation does not call that
   completion orchestrator. Its _edit requires one row per existing expression
   and explicitly prohibits new roots/modules. Existing expressions can expand
   using their original-unit evidence, but this is narrower than original
   completion. Do not describe this migration as full capability equivalence.
3. This sample had19 visible expressions/373 final words with no thin modules;
   all six modules nevertheless remained completion_targets for unused capacity.
   Final compiled zone uses=.807429/.883851/.849191; terminal gaps5.3689/3.2382/
   4.2045in. Largest empty rectangle=.116149 of body. Actual-glyph bottom metrics
   in Critic are mean4.3471in/max5.5235in/full-width3.3526in. The reported .04
   unallocated_body_fraction measures area outside zones, NOT all empty content.
4. One quality charge targeted display002/003. edit_targets discards target
   severity ordering and uses untouched/word-load ranking when all are sparse.
   Saved quality draft shrank total prose373->326 words. Its subsequent verified
   fit (46fa6ed55339) had gaps6.1022/4.5630/2.5738 vs baseline8241f6884110; direct
   existing space_preserved(baseline,trial) returnedFalse. The frozen poster is
   the373-word baseline. Guard worked; quality improvement did not occur. The
   normal false-guard rollback does not emit quality_rejection.json, unlike the
   exception branch, so the attempt is observable through saved inputs/results
   but lacks an explicit adoption/rejection summary.
5. Critic observed the defects: whitespace_quality65, section_fit73.4, visual
   balance77.01, multiple major underfill/bottom-gap findings, and available
   unused evidence in several modules. Overall90.63 blends science/geometry/
   typography scores and is not aesthetic certification. Critic has no repair
   feedback loop on the independent-sample route; all-score publication remains
   intentional and must not become score filtering. Preflight/RenderFit passing
   certifies checked physical/text-fit conditions, not dense composition.

Recommended direction (not implemented/authorized by this question): migrate the
useful original completion actions into joint preparation before candidate freeze,
with the same scientific verification, sample-wide rounds/actions and durable
charges. Separate overflow compaction from sparse-module completion priorities,
require material relevant improvement for adopting quality edits, and persist
explicit unresolved-target/adoption/rejection diagnostics. Preserve fixed family,
no post-freeze search, all-score publication and original science/physical gates.
Do not simply reattach the legacy helper after freeze or create free extra rounds.
No old/current same-input runtime comparison was performed; this evidence does
not establish that the old pipeline would fill this exact poster or that this
one gap explains every observed blank area.


### Upstream module/prose/visual comparison (2026-10-26)

User requested a detailed comparison against original Y-Research-SBU/PosterGen.
Inspected upstream public main pinned to8a54325f871ee10fa6545de3b3a9b771aa12620c
using GitHub connector source reads, not this fork's dormant curator. Source copies
and quantitative findings are /tmp/postergen-upstream-content-review/. The existing
resource/active-geo.png Git blob bba4bd9e6385ecda24d73fe5fe31cb30d6024203 matches
the upstream tree exactly, allowing direct visual comparison of the same paper.
This is an inspected published example, not a controlled same-model A/B test.

Upstream facts:
- Parser converts paper to Markdown/assets, asks text model for ABT narrative and
  structured scientific sections (content/key_points/importance/figure/table IDs).
  Raw paper enters that section extraction; the prompt requests <1000words/section.
- StoryBoardCurator receives those sections, global narrative, classified visual
  roles, captions/aspect ratios and calculated per-visual column-height loads in
  one request. It jointly chooses sections, titles, prose, visuals, importance and
  placement. There is no separate atomic-claim Writer/EvidenceBuilder/Verifier
  equivalent in that upstream graph.
- spatial_content_planner prompt asks5–8sections,2–3hierarchical text entries per
  section, one critical method/key figure, problem-method-results progression,
  and no separate conclusion/takeaway/future/impact sections. It asks4–6visuals
  and column quotas; do not mistake all prompt quotas for enforced validators.
  Key figure presence/middle-top placement is explicitly validated.
- Upstream visual classification uses text model on caption/type/aspect lists,
  not image pixels; raw_text is a method argument but not rendered into this
  classification prompt. Do not claim upstream has an image semantic judge.
- Initial layout measurement feeds Balancer, which sees structured source sections,
  current storyboard and column utilization and can rewrite prose/add or remove
  supporting sections within columns. It is itself conservative and prefers
  reduction near overflow; it does not prove a universally optimal composition.
- The same-paper example has six modules (Eviction Challenge/Prior Approaches/Our
  Method/Hierarchical Search/Key Results/Performance Analysis), two method figures
  and two result tables, and visible lead/support hierarchy. One method figure
  appears in a problem module: borrowing its visual quota is not a guarantee of
  correct image/module relations. The example's wording/figures are not automatic
  evidence of scientific correctness or its generating model settings.

Confirmed local v7 causes, beyond the earlier whitespace diagnosis:
1. Editorial selection: Planner made18evidence assertions indispensable and
   Curator assigned all of them. Four task/MDP assertions, four setup/baseline
   assertions and two implications assertions carry mandatory responsibility.
   Result: six primary/plain modules, including standalone evaluation setup and
   Outreach Implications. The latter survives despite sample Curator guidance
   against generic impact sections because obligations were fixed upstream.
   Task+setup+implications use197/373words, method+results141/373words. This is a
   specific allocation observation, not a universal ban on those functions.
2. Body writing: saved initial Writer372words/19expressions;14expressions equal a
   cited evidence item's claim verbatim,17have>=.85SequenceMatcher similarity,
  18cite exactly one evidence item. Verifier changes only2expressions;17final
   strings are unchanged. The issue originates before verification, rather than
   broad destruction of good prose by verification. Full source context and
   global narrative DO reach the current Writer; absence of either is ruled out.
   Instructions against one-entry-per-evidence are soft and fail in this sample.
  18of19final expressions are protected; no parent/step relations were written.
3. Wrong provisional capacity allocation: family_capacity greedily bins by module
   counts/capacity and picture load, without matching the eventual joint solution.
   It gives task_definition and Outreach Implications each83–125words in hero,
   while Hierarchical AGS Architecture gets19–29words in a rail, results27–41.
   Final hero contains architecture+evaluation; task and implications are rails.
   Thus the Writer's apparent physical guidance is materially inconsistent with
   the actual composition. References are soft, not truncation, but incentives
   favor the wrong topic allocation. This is not proof it alone caused poor prose.
4. Previous optimization wiring: old write_poster_claims/write_sample_modules
   contain detailed direct-voice/mechanism/consequence/connected-explanation
   guidance; v7 calls write_joint_poster instead. Global prompt preserves some
   concision/coherence guidance but does not mechanically inherit all old text.
   polish_wording/create_style_variant remain in code but are not called by the
   new default joint route. Structural refine_editorial runs with
   scientific_prose_rewritten=false; same name does not establish prose editing.
   Current reserved quality _edit is a different narrower interface and its
   single trial shrank text, failed space_preserved, then reverted.
5. Presentation: all modules presentation_style=plain; despite candidate labels,
   topics labels require topics mode and safe extractive labels. All parent/step
   hints are empty. The result is uniformly weighted bullet lists. FontAgent
   highlighting cannot fix content selection, explanations or paragraph logic.
6. Visual selection: local sample Curator receives caption/aspect only, not the
   existing classified_visuals roles/key pointer or actual per-visual family-size
   estimates. It choosesfigure2+table3; joint optional key seeding already sees
   figure2present and restoration has no omitted curated candidate. Full
   bank still containsfigure1andtables1/2/4/5. Results prose covers both uniform
   and distance costs and multimodality; the only shown table is distance-cost5%
   eviction-rate. This is narrower visual evidence than the story describes, not
   a claim that every omitted table belongs in the poster.

Recommended integrated improvement, not implementation in this analysis turn:
- Existing Planner/Curator should jointly prioritize the paper's main question,
  mechanism, evidence and interpretation, with minimal true obligations and
  conditional interpretive prerequisites. Distinguish scientifically necessary
  from merely useful or correct details before writing, without a new necessity
  judge or deleting protected assertions after the fact. No module/visual quotas.
- Feed Curator existing source visual roles, key pointer, captions and family-
  aware footprint/readability context; record each chosen visual's scientific
  function/complementary prose and explicit omission rationale. No pixel semantic
  admission judge, forced unrelated pictures or historical template retrieval.
- Make capacity guidance compatible with legal role/source-aware candidate
  placements; do not silently allocate hero-scale words to arbitrary modules.
  Uncertain assignments should expose ranges instead of misleading exact zones.
- Initial whole-poster Writer should synthesize several compatible supported
  assertions into coherent display ideas, with source-backed lead/support
  relationships and necessary scope/comparators beside findings. Keep exact
  supported spans and required-assertion verification. Do not relax science or
  merge old scientific root IDs to conceal omitted information.
- Restore content/prose/composition feedback before freezing, using existing
  sample-wide3capacity+1quality rounds/two-module actions. Separate compaction,
  explanation repair and completion; use gap/reading/value diagnostics and
  persist adoption/rejection/unresolved targets. No post-freeze search or extra
  free rounds, and no new Actor-Critic generation loop.
- Acceptance should compare paper story, mechanism explanation, result conditions,
  visual complementarity/readability and actual composition, not just total
  score/finalization. Retain all-score/unclassified publication. A future
  user-authorized same-paper/same-model controlled comparison is needed before
  attributing the full visual gap to architecture versus the model; upstream
  README's GPT4.1default is not proof of its sample's actual generating model.

No source/config/prompt edits, no models/GPU calls, no source tests or historical
artifact changes were needed. AGENTS/report were maintained locally and ignored.


## 2026-10-26 — Authorized integrated editorial implementation (v8)

The user authorized implementation of the preceding complete repair plan.
Generator explore_samples_v8/preparation sample_science_v5; bodyv2/datasetv2/schema2
remain. New source identities reject old resume; no historical sample migration.
Changes cover existing Planner/Curator editorial responsibility, auditable reader
questions/goals and visual rationales, existing visual-role/key/footprint context,
explicit same-module optional visual reserves, bounded source/role-aware uncertain
capacity estimates, measured ownership for quality work, synthesized global prose,
and a restored quality action that can add fully verified explanation.

The existing four-round sample ledger remains3capacity+1quality/two modules.
New additions use distinct root IDs and original-unit evidence ownership; retained
roots and local prerequisites remain. Every changed context/addition is verified
with unchanged exact scientific support and required-assertion checks, then refit.
Adoption requires actual visible roots/visuals, non-regressing space and measured
prose/hierarchy/explanation/target-space gain. Citations without supported new text
cannot fabricate a gain. An explicit quality report records rejection and unresolved
targets. No new semantic/image judge, Actor-Critic loop, extra free model rounds,
post-freeze search, forced image count, cross-sample learning or score filtering.

Focused existing suite passed177cases. New initial28repair cases passed; a further
real-Verifier negative case, citation-only adoption case and safe rendered-hierarchy
case were added. Combined focused run passed206cases before the last two cases;
three final targeted adoption cases pass. Full CPU suite is running against the
final tree; results will be appended. No paid model/GPU work has yet started.
Historical baseline inventory/hash file is /tmp/postergen-editorial-v8-20261026/.
AGENTS/report remain local/ignored; source changes will receive one atomic commit.

Final hardening includes explicit completion relevance and non-redundancy verdicts
in the existing sample Verifier response, on both initial and corrected additions.
Missing verdicts are format failures; negative verdicts cannot approve additions.
This preserves original editorial addition standards without another judging stage
or model call. Eight related malformed/negative/positive completion cases pass.
Rendered hierarchy gains count only safe cues that actually appear through the
shared paragraph formatter; unsupported/unrendered metadata cannot fabricate a gain.
Final source hashes are frozen under /tmp/postergen-editorial-v8-20261026/.
The final full-suite log is /tmp/postergen-editorial-v8-complete-tests.log; earlier
full-suite runs were deliberately interrupted to include these safety additions.

Final CPU acceptance:980passed plus5subtests, six dependency warnings,868.98seconds.
All16task file hashes match the tree used for that final suite. Twenty original
classic/extraction/search/render/storage boundary files match3b709e1; all7577
historical baseline files remain present and byte-identical. Patch checks pass.
The next one-sample real acceptance uses standard runner/strict original-paper
cache donor run_0ac92a0a8f264f4f8319, seed20261026 and GPU5. It is fresh v8 sample
science, not a replay/import of previous prose. Per user preference, hand off
after confirmed background startup; later acceptance must inspect actual output,
editorial quality audit, source/physical checks and supervisor cleanup.

Atomic local commit71d0f0f:16tracked paths,724insertions/59deletions; tracked
worktree clean after commit. AGENTS and this report remain ignored.
New real acceptance run_1cb2af91842a43d7b78b started14:51:51Beijing with
supervisor339829/generation339830 and CUDA_VISIBLE_DEVICES=5. Strict original cache
reuse succeeded, then sample1 entered NarrativePlanner. One bounded startup
confirmation verified both processes alive; generation is left in the background
per user preference, without continuous monitoring. Runtime records:
storage/rubrics_samples/background/editorial_v8_validation_20261026/.
No rendered poster, score, final visual acceptance or completed cleanup is claimed
at handoff. Later inspection must verify actual output, quality adoption/rejection
and unresolved targets, source/physical checks and supervisor exit/cleanup.


### 2026-10-26 — v8 acceptance failure and percentage notation repair

Requested status inspection found run_1cb2af91842a43d7b78b finalized
preparation_failed, no PNG/PPTX/score, at07:00:41UTC (15:00:41Beijing),8m51s
from launch. GPU5 cleanup is recorded; exit0/COMPLETED only means task completion.
Planner145.65s, Curator146.06s, space brief1.05s and global Writer175.55s completed.
First draft fit reported PRESENTATION_STRUCTURE_UNRESOLVED for supporting
module display_004. Capacity rewrite was then rejected by the strict numeric check.

Exact archived-response inspection shows a false positive: ev_0075 explicitly
supports3%–17% and ev_0078 supports42%–70%; the model used normal shared-unit
notation3–17% and42–70%. extract_numbers treated each lower endpoint as a bare
number, while the evidence numbers retain percentages. No invented numerical
bound was established in this failure; the earlier status phrasing was incomplete.

Focused repair adds sample-only formatting normalization before the existing
number check. Only an en dash or word-to range is expanded, and only when both
explicit percentage bounds pass the unchanged cited-evidence check. Every change
is recorded in display_normalizations. Initial whole-poster/module writing,
editorial rewrites and quality additions all use it. Signed/ambiguous arithmetic,
already explicit units and unsupported bounds remain unchanged/rejected. There is
no change to shared evidence_utils, classic, source evidence, semantic/numeric
verification, root protection, physical guards, budgets or family policy.

CPU replay on an in-memory copy of the exact saved response now normalizes all14
expressions, with only two percentage-format notes. It neither mutates the old run
nor certifies science/geometry. Added regression cases cover initial/revision/
completion paths, both real ranges, unsupported endpoints, preserved explicit
percentages and signed/ambiguous expressions. Existing preparation/execution
boundary suite:35passed (16.40s,4dependency warnings). Further targeted results
and fresh-run launch details follow. All7577previous historical baseline files
remain byte-identical/present; combined new prelaunch snapshot covers7636files.
The user requested an actual sample; use a fresh one-sample standard runner launch
with original paper cache, same seed20261026 and GPU5. Stop monitoring after a
confirmed launch. A launched job is not a generated or aesthetically accepted poster.

Final focused editorial/joint/body suite:140passed,4dependency warnings,231.73s.
Together with preparation/execution:175passed. No full-suite rerun was required
for this narrow sample-only normalization; git diff --check passes.


Fresh acceptance run_d6a0e508cfc943ab967c launched15:13:07Beijing after atomic
local commit6603a2a (3tracked paths,75insertions/1deletion; tracked tree clean).
Supervisor342074/generation342075 are alive; strict original paper cache reuse
succeeded and sample1 entered NarrativePlanner. Runtime folder:
storage/rubrics_samples/background/editorial_v8_percent_validation_20261026/.
Samples1/seed20261026/GPU5; all7636prelaunch historical files remain unchanged
and present.175focused tests pass. Stop monitoring after this bounded startup
check, per user preference. Owned-group cleanup/exit.json remain automatic.
No generated PNG/PPTX, score or aesthetic acceptance is claimed at launch.

Wrapper/audit/handoff evidence: /tmp/postergen-editorial-v8-percent-20261026/.


### 2026-10-26 — v9 verifier protocol and bounded recovery

Run run_d6a0e508cfc943ab967c ended15:36:38Beijing, preparation_failed with no
poster/score after23m31s. Its final pc_display_002_001 recheck returned the input
claim object (claim_id/text/evidence_ids/required_evidence_ids/original_expression),
not a verification verdict. JSON parsing was valid; supported was absent in the raw
response itself. Last physical request finished normally in9.964s with stop/113
output tokens. Earlier same-root verdicts recommended opposing small-K RL/standard
AGS names. These are two distinct problems: protocol conformance and unstable
entity-reference reasoning, not evidence that all underlying science is invalid.

Implemented explore_samples_v9/sample_science_v6, unchanged body/data/schema. A
sample-only closed JSON Schema is bound to compatible ChatOpenAI clients and also
validated locally with the existing jsonschema dependency. Classic json_object and
other agents remain unchanged. Provider schema rejection has no automatic weaker
fallback. Full schema enters prompt identity; malformed raw responses, structural
errors and accepted response index remain in existing durable request journals.
One format correction uses ONLY the existing shared preparation allowance, never
a new/free per-claim round. Writer's spent format correction precludes another;
valid negative semantic verdicts never cause format retries. Missing/negative
preservation/relevance/coverage cannot become implicit approval. All original
scientific/numeric/source/physical gates and3capacity+1quality/two-module limits
remain. Interrupted charged responses fail closed without resubmission; stop before
format recovery propagates from the isolated Verifier to joint preparation.

The correction recheck now sees the preceding verdict and exact reason as untrusted
audit context. Prompts require source-based entity resolution, forbid label-only
alias reversal and retain rejection when ambiguity cannot be resolved safely.
No extra judge, alias admission map or model call is introduced. Audit metadata is
removed before accepted science persistence. This reduces a known source of
inconsistent instructions; it cannot guarantee identical semantic judgments.

The exact archived failing raw response is rejected by the new schema (9structural
violations), using no model calls and no historical writes. Added protocol tests
cover claim echoes, wrong types, shared-budget exhaustion, at-most-once durable
recovery, interrupted/replayed calls, valid negative verdicts, provider opt-in vs
classic behavior, preservation/completion fields, correction auditing and numeric
gate preservation. Targeted18protocol tests passed in5.77s. Updated editorial
fixtures now return the full protocol; protocol/editorial69passed before two final
stop-propagation cases were added. Independent legacy/model/preparation/execution
boundary84passed in16.59s. Complete final frozen-source suite follows.

Final provider binding is scoped entirely inside sample_verification.request_verdict.
The original shared utils/langgraph_utils.py is byte-identical to6603a2a; original
paper-cache extraction identity matches donor run_0ac92a0a8f264f4f8319 exactly.
The final scoped-binding/stop suite passes18tests in5.85s. Exact archived malformed
response recovery was replayed offline through the real journaling/protocol path:
2fixture responses,0server calls,1shared preparation allowance, explicit negative
final verdict, no scientific acceptance and no mutation of the old response.
Full frozen-tree acceptance log: /tmp/postergen-verifier-v9-frozen-tests.log.


Final frozen-tree CPU suite:1016passed +5subtests,6dependency warnings,848.84s.
All7851historical files unchanged/present. All10frozen source/test/boundary hashes
match the pre-suite snapshot. Patch checks pass; original extraction cache identity
matches the strict donor. This is CPU/protocol acceptance, not proof of source
judgment stability, a generated poster or aesthetics. The new one-sample real run
will use the standard strict-cache runner onGPU5, seed20261026, with independent
Planner/Curator/Writer/Verifier science. Leave it in the background after verified
startup and record the actual final artifacts/quality/science/physical audits later.


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

AGENTS/report remain local/ignored. No generated data or logs were committed.


### 2026-10-26 — v9 final sample inspection: rendered, quality not accepted

User requested inspection and analysis of the latest sample, not implementation
or another generation. Read FINALIZED, published PNG/PPTX, full evaluator records,
Writer/Verifier journals, quality draft/rejection, source captions and original
PDF pages 5–7 (one-based). No model calls, tests, GPU runs or source edits were made.

Latest run run_2c9c5c5d66874ee0b49a finalized sample_000001 SCORED/88.22 at
08:26:42 UTC / 16:26:42 Beijing. Runtime 771.23s (12.85min), using strict original
paper cache. Frozen central_hero_side_rails; 5 modules, 12 expressions, 272 words,
10 required evidence IDs covered. Run seed20261026; derived sample seed20261027.
Real published poster.png/poster.pptx and sibling inspection templates exist.
Supervisor exit.json records exit0 at16:26:49Beijing and no GPU5 compute workers.

Separate acceptance facts: Preflight passed with zero issues; conclusive RenderFit
matched10/10 editable body/title boxes, zero issues. All12 initial scientific
verdicts passed, zero semantic corrections/rejections and no malformed-verdict
recovery in this run. The schema path has a successful real exercise, but one
sample without correction does not establish semantic alias stability or exercise
format recovery. Critic evaluation is complete but hard_gate_passed=false and
reference_passed=false. SectionFit is the failed hard evaluator (53.43); total
88.22 is not aesthetic or quality acceptance. Publication is intentional under
the current all-score/unclassified contract, not a score filter failure.

Observed problems and first-stage evidence:

- Geometry is strongly imbalanced. Physical left challenge rail contains37words
  and uses48.36% height; bottom gap14.3967in. Center85.75% /3.9716in gap, physical
  right93.76% /1.7385in gap. Actual visible maximum terminal gap15.2833in and mean
  5.2816in. The narrow left heading wraps over three lines. Geometry refinement
  ran and reported improved, yet retained a severely sparse final rail. Do not
  claim refinement is absent. Mirroring means internal right_rail is physical
  LEFT (x=0), while left_rail is physical RIGHT; use actual coordinates when
  interpreting issue locations. The visual evaluator emitted some mismatched
  zone IDs, which the sanitizer could not resolve from names alone.
- Final result-table order is table_1, table_3, table_2: uniform cost/5% target
  rate, distance cost/5%, uniform cost/10%. Original PDF and individual assets
  confirm the source pixel/caption mappings are correct. Their captions and
  condition labels are absent from the poster. This is a display/context failure,
  not a demonstrated extraction ID swap. The large, differing budgets and ANT
  values are hard to interpret without the omitted cost/rate labels. Curator
  chose table_1+table_3; the finite restoration probe added table_2 and rejected
  table_4 placement. More images alone did not supply better explanation.
- All4 visible scientific assets have low effective resolution: figure_2 51.77DPI,
  table_1/2/3 about64DPI. Actual picture text and dense7-method/9-budget tables
  remain difficult to read at viewing distance. Framework width is substantial
  (about23.74in); the remaining issue is source resolution/internal label density,
  not simply a tiny diagram. RenderFit only certifies editable text geometry,
  not text readability inside raster tables or figures.
- Initial Writer and final12 texts are identical. Diagnostics count8/12 exact
  evidence-summary copies and10/12 near copies (overlapping categories). All5
  modules are primary/plain; all12 discourse hints are method, with no parents,
  steps or visible local labels. Method prose spends two expressions defining
  AGS/objective, then one describing region/parcel choice, leaving shared prediction,
  cross-region policy sharing, multimodal inputs and adaptation poorly explained.
  HAGS is not expanded in visible prose and K appears without a definition.
  This weakness starts in Writer/planning; Verifier did not rewrite the prose.
- Scientific provenance passed, but reader completeness is weaker. The poster
  states the26700-property source pool without the actual16000-property evaluation
  sample/four selections, temporal split or target definition. These details are
  available as ev_0073/ev_0061/ev_0062. The14/54 assigned-evidence use metric is25.93%,
  not a statement that74% of indispensable science is missing; all10 required IDs
  did pass. The100 scores for depth/completeness/structure in the semantic rubric
  should not replace this concrete reader-facing review.

The single quality charge targeted display_002+display_003. Its raw response
contained useful prose revisions plus new explanation/baseline entries, but local
normalization rejected the entire batch before further science/fit:
`display_002/add_display_002_001: unsupported numbers ['2']`.
The additional text uses `level-2`, while its cited ev_0048/ev_0049 claim/excerpt/
numbers fields contain no digit2 (the entity list does, but numeric collection
does not include entities). Crucially, the addition also asserts shared policy
and reduced complexity not fully supported by those two excerpts. The original
Large-Area Search chunk contains the shared predictor/shared level-2 explanation,
but no evidence-bank item records that full passage (the only item containing
shared is ev_0066 about MMFE). Do not call this a proven fabricated result or claim
that changing2 to an English word alone would satisfy semantic verification.
Original chunks remain reference context, not automatic extra citable evidence.

Rollback correctly retained the safe baseline, but all wording improvement was
lost and the reserved quality round remained spent. quality_report.json records
status=rejected and all5 unresolved modules; its targets=[] is an audit gap:
_edit raises before `_joint_last_edit_targets` is installed and copied into the
report. The archived response and charge still identify the two actual modules.
Target ranking prioritizes evidence_summary_list before bottom-gap severity, so
the worst14.4in challenge-rail gap was not selected. Final visual restoration
improved center/right use after the rejection, without changing the12 texts.

Compared with previous same-paper successful v7 sample run_bd07b4adfb414de98cff:
6→5 modules,373→272words,1→3 result tables,90.63→88.22score, hard gate true→false.
This is one stochastic comparison, not a controlled proof of a version-wide
regression. It shows the current sample has not demonstrated the intended
editorial/whitespace improvement despite successful schema and artifact generation.

Suggested repair priorities for future authorization: preserve cost/rate/metric
context in visible figure/table labels; improve evidence extraction/selection for
missing mechanism and evaluation conditions; make initial prose explain the main
contribution with useful local hierarchy; allocate geometry using actual content
and severe gap pressure; retain complete failed-target diagnostics and diagnose
bounded quality-round admission before spending it. Do not add free rounds, relax
scientific checks, force visual quotas, import old sample prose or launch a new
sample as part of this diagnostic task.

Evidence paths: storage/rubrics_samples/background/verifier_v9_validation_20261026/;
run samples/sample_000001/preparation/joint/quality_report.json,
quality_rejection.json and edits/*/parsed_00.json; published evaluation.json and
diagnostics/{module_body_report,layout_spec,render_fit_report}.json.


### 2026-10-26 — Legacy accepted posters versus current Rubrics: behavior was not fully preserved

User specifically requested examination of storage/critic_loop/accepted_posters,
asking how earlier posters avoided overflow/dead space when layout functionality
was supposed to be retained. This is a diagnostic task, not authorization to
implement a repair or start generation. Read all4 accepted bundles, their actual
COMPLETED-selected final attempts, input snapshots, repair ledgers and final
scientific/layout records; visually inspected latest legacy central-hero and
method-flow posters. Read Git history for initial refactor a916e5f, module-first
98fd690, v7 f25ee8a and v8 71d0f0f. No source/test/config/model/GPU execution.

Measured comparison (same54x36in,44pt body):

- Legacy Oct20 central_hero_side_rails bundle8d2c39/i000001: original scientific
  input65 verified expressions/1503 candidate words in7 source modules; actual
  final17 expressions/373 visible words in5 modules. Final exact region use
  .980229/.946682/.981973; compiled bottom gaps.5512/1.4865/.5026in. Critic hard
  gates pass, score87.74 under samev10 rubric as current sample.
- Other accepted examples: Oct16 i10 initial48 expressions/1025 candidate words,
  final22 expressions/458words; Oct19 i11 final23/492words; Oct19 i12 final22/
  486words. All4 bundles are Explore, with no parent candidate/template input.
  Do not attribute their composition to Improve evolution or saved-template reuse.
- Current v9 sample: initial/final12 expressions/272words,5 modules. Physical
  left/center/right utilization.48362/.857548/.937642; compiled bottom gaps
  14.3967/3.9716/1.7385in; Critic hard gates fail. These are same-metric snapshot
  comparisons, not controlled same-input/model-seed replay or universal statistics.

The original path was rich verified candidates -> Curator/ownership -> bounded
family geometry+grounded subset search -> exact refill/regrouping -> sparse-module
repair/visual recovery -> final compile/font/preflight/rendered-glyph audit ->
Critic archive admission. Optional source candidates remained available for exact
refill. It did not display all1503words or shrink fonts to fill space. Empty space
could be addressed with already verified content without another model call;
new additions/source search still needed normal verification and finite charges.

Important correction to a simplistic completion-loss explanation: all4 final
attempt repair reports contain ZERO adopted textual complete_modules actions.
They tried original-claim restorations, compact restoration and/or new evidence/
source search, but rejected them on fit/science/content/ownership grounds. Oct20
report status=applied refers to figure_2 restoration, improving worst exact use
.893104->.946682; it does not prove a successful generated prose addition. Oct19
i11 exact solver separately restored pc_0042 in restored_content. Thus rich input
and exact subset/geometry selection are demonstrated major contributors; a missing
completion helper alone cannot explain all observed composition differences.

What was preserved and what actually changed:

1. Initial Rubrics refactor a916e5f (Oct21) still called layout_with_balancer_node.
   Its initial all-score storage change did not itself remove the solver path.
   The later module-first work changed scientific/display input from a large
   optional verified candidate bank to compact prewritten display modules. This
   is a material change to the solver's feasible content set, even if exact fit
   algorithms are retained. An unchanged refill cannot invent content absent
   from its supplied module board.
2. f25ee8a/v7 (Oct26) replaced the layout_with_balancer design node with joint
   preparation before design plus frozen install/compile afterward. _fit still
   calls fit_family_layout, exact refill, editorial/geometry refinement and
   whitespace guards. But the old feasible-layout repair_family_fit ->
   complete_modules orchestration and polish_wording are bypassed. The frozen
   compile node deliberately cannot reopen that work after preparation.
3. v8 71d0f0f partially migrated completion via additional_claims from target
   modules' available evidence, plus rationale/reserve visuals and diagnostics.
   Current v9 therefore CAN add roots; the old v7 statement that it cannot is
   historical only. It still does not run the original complete_modules queue,
   eight original-root restoration probes or its staged original-source search.
   New completion is coupled to one coordinated two-module quality response.
   Current rejected level-2 addition left all12 texts unchanged.
4. Budget total4 is not identical scheduling: old reports actually used2 quality
   rounds under per-family limit2; old quality reserve was a minimum held from
   capacity, not a hard one-quality maximum. JOINT_POLICY imposes max_capacity3 /
   max_quality1 / total4. Its one failed quality response can leave3 capacity
   slots unused without permitting more sparse-module work. This was a later
   joint-preparation policy change, not byte-equivalent preservation. This review
   does not authorize relaxing or adding rounds.
5. Whitespace scoring/refinement and non-regression protect relative choices;
   they do not guarantee an absolute minimum density. A sparse baseline can
   remain sparse while every guard passes. Preflight/RenderFit primarily verify
   physical upper bounds, ownership and actual editable-text geometry. SectionFit
   is where utilization<.55 plus large bottom gap fails absolute quality. That
   check remains active and rejected the current sample in Critic.
6. Historical accepted_posters includes only accepted outcomes. Current samples
   publish every rendered output, including hard_gate_passed=false, as required
   by independent all-score sampling. Scored means evaluation completed, not
   accepted. This visibility difference explains some apparent regression but
   does not account for the actual measured sparse generation by itself. Do not
   reintroduce score filtering to conceal it. Older accepted posters also have
   remaining1–3in visible gaps, tiny figures/caption/structure shortcomings; they
   are denser, not flawless or proof every old attempt succeeded.

Byte comparisons: text_height_measurement.py, title_metrics.py,
text_fit_adapter.py, render_fit.py and whitespace.py are each identical to BOTH
c83300f and a916e5f. This supports preservation of core measurement/audit logic,
not equivalence of the whole end-to-end behavior. The initial refactor, subsequent
module-first input contract and later v7 execution replacement must be distinguished.
Prior descriptions of full layout-capability preservation were too broad.

Future repair should restore equivalent content-choice and useful completion
capabilities INSIDE current pre-freeze preparation, preserve independent sample
science/original evidence and controlled-family semantics, and validate final
behavior on real saved/current inputs. Keep original scientific/physical checks,
finite durable budgets, no post-freeze search and all-score publication. More
stochastic reruns or stricter result hiding alone do not repair the migration.

Evidence: four legacy bundles and their provenance-selected campaign attempts;
current v9 exact fit/quality reports; source layout_with_balancer.py:250,
capacity_repair.py:487, module_repair.py:106, exploration_runner.py:25,
joint_preparation.py:125/427/529, repair_budget.py:9/81, section_fit.py:314.
No historical artifact was edited or imported into generation. Hash snapshot for
inspected artifacts: /tmp/postergen-legacy-v9-layout-review-20261026-hashes.json.


### 2026-10-27 — Why upstream body writing differs from current samples

User requested an explanation and actual source comparison, not implementation.
GitHub main was rechecked through the connected GitHub reader: still
8a54325f871ee10fa6545de3b3a9b771aa12620c. Reviewed pinned Parser, Curator,
structured-section/ABT/spatial-planning prompts, Balancer and pipeline. Previously
cached upstream source matches fetched text after trimming one added terminal
newline. Local HEAD remains db43de5. This comparison uses GitHub upstream as the
original project; local historical Campaign posters are a separate implementation.

Upstream normal writing path:
PDF -> Marker Markdown -> model-generated structured paper sections (continuous
content, key_points, importance, relevant visuals; up to1000words per section) plus
ABT context/problem/contribution, poster_hook and key_impact -> StoryBoardCurator.
The Curator is the actual initial prose author. It receives these whole-section
materials, global narrative, caption/aspect metadata and estimated column/visual
heights. One call returns headings, full text_content, formatting, importance,
visual selection and column assignment together. Spatial prompt explicitly teaches
nested bullets, short bold point labels, ordered procedures and main/support ideas,
with short concise entries and complementary visual explanation. Its hardcoded
three-column/visual-quota preferences are upstream choices, not current requirements
or a recommendation to restore quotas. ABT is intermediate story context; final
poster need not display ABT headings.

After initial geometry, upstream Balancer reads the current entire story board,
structured_sections and measured column utilization. It can rewrite/shorten existing
text, expand it conservatively and add source-derived sections for severe underfill;
it returns a complete optimized story board. Its source validator checks basic
structure/column assignment, not current evidence IDs, exact support spans or
indispensable assertion verdicts. Upstream has no EvidenceBuilder/ClaimWriter/
ClaimVerifier stage in this pipeline. This is an editorial advantage with less
formal scientific auditing, not a guarantee that its screenshot is fully supported.
README does not disclose the exact model/prompt history of the showcased poster.
Default CLI model is not proof of which model generated that image.

Current active sample path (not standalone classic):
Parser preserves deterministic source chunks and metadata, skipping legacy ABT;
EvidenceBuilder extracts atomic scientific evidence with verbatim source_excerpt;
NarrativePlanner groups compact evidence summaries (no original excerpt/full chunk
in its actual compact_items input), chooses indispensable IDs and narrative_summary/
editorial_focus; family freezes; sample Curator selects module tasks, titles,
primary/support evidence and visuals, explicitly without writing scientific prose;
family_capacity supplies provisional ranges; one whole-poster ClaimWriter call
writes all module bodies. It receives global narrative/focus, all module briefs,
required assertions, module-allowed evidence with full excerpts and deduplicated
original chunks for those excerpts. Thus it does receive global context and source
paragraphs; it is not writing one independent sentence call per evidence item.
System role still emphasizes concise scientific claims strictly from evidence;
output is modules/claims with evidence IDs, local dependencies and optional cues.
Original chunks resolve context but cannot introduce an uncited new assertion.

Joint preparation fits the draft, verifies actual selected expressions with
numeric/entity/comparison/whole-text support and indispensable coverage, then refits
actual final wording. Supported spans are quotes of candidate poster text, NOT a
requirement to copy original-paper wording. Cross-evidence synthesis and paraphrase
are legal when the citations support every assertion and relationship. At most
three capacity/structure rounds and one quality round (two target modules) can
edit before freeze. Roots/order/origins constrain later revisions. V9 can add roots
inside quality; saying it cannot add anything is obsolete. The old local
polish_wording/complete_modules entry is absent from default_nodes; those retained
functions are not a proof of active behavior and were not upstream stages either.
After freeze, ordinary design compiles/styles/renders and cannot freely rewrite.

Concrete v9 evidence, reproduced from stage04 Writer output and verified_claims:
12expressions,272words;8exact and10near (SequenceMatcher>=.85) source-summary copies,
12/12 final strings identical to initial Writer. Only2expressions cite more than
one evidence ID. Five modules are primary/plain with all12 discourse kinds=method,
no parent relationships or numbered steps. Existing prompt already explicitly says
synthesize, do not copy evidence summaries, explain mechanisms and use lead/support.
Therefore missing exhortations or destructive Verifier rewriting are not sufficient
explanations. The bad expression pattern is present in the initial accepted draft.
Narrative_summary/editorial_focus explicitly include hierarchy, exploration versus
exploitation and multimodal features, but the final body scarcely explains them.

Actual stage03/04 provisional word ranges (before later measured ownership):
challenge44–66, method47–71, evaluation98–147, results24–35, impact67–101. Thus the
soft space signal still allocates more prose to setup/impact than the contribution
and findings, despite v8 improving estimation. Later measured ranges in the final
sample_module_plan are different and must not be mistaken for Writer inputs.
Observed output need not exactly follow these soft ranges (method actually79words).
This is a contradictory guidance signal, not an enforced truncation quota or proof
of its isolated causal contribution.

The shared predictor and cross-region shared level-2 policy are described in the
original Large-Area Search chunk, but existing evidence lacks their complete
assertion (the only evidence item containing shared is ev_0066 about MMFE). Strict
Writer citation policy therefore makes some useful reader explanations unavailable
without valid source evidence coverage. The one later quality draft tried adding
shared-policy explanation but failed local numeric matching on level-2 and cited
only ev_0048/0049, whose excerpts also do not cover the full added assertion.
Whole-batch rollback left the initial prose intact. Fixing the digit alone would
not demonstrate scientific validity. Good evidence structure/selection is needed
alongside paragraph writing; relaxing science is not a justified conclusion.

Diagnosis separates established observations from causal inference: serial evidence
summaries and required-assertion duplication plausibly anchor the model toward
minimal fact restatement; source permissions and immutable post-writing identities
limit editorial freedom; optional formatting was not used; later repair failed.
No controlled model/prompt ablation has measured each factor. Current sample uses
local Qwen3.8-27B; the upstream example's exact model is unknown. Model capability
may contribute, but claiming it is the sole/main proven cause would exceed evidence.
Prior tests/protocol fixes establish implementation safety and schema behavior,
not successful reader-facing scientific explanation. Earlier broad claims of full
writing-capability preservation were too strong.

Future improvement direction (not implemented here): keep provenance while making
central mechanism/conditions available as sufficient evidence, make initial writing
produce coherent reader-facing explanations with visible lead/support organization,
and verify adoption through actual output comparisons. Preserve independence,
pre-freeze repairs, finite budgets, all-score publication and scientific gates.
No new code, model calls, tests or generation were authorized/executed in this review.
Sources: upstream config/prompts/{extract_structured_sections,narrative_abt_extraction,
spatial_content_planner,layout_balancer}.txt and src/agents/{parser,curator,
balancer_agent}.py; local src/workflow/{exploration_runner,sample_module_writing,
joint_preparation}.py, config/prompts/write_joint_poster.txt and saved v9 stage03/04.


### 2026-10-27 — Feasibility: upstream-style source-driven editorial workflow across families

User wants Rubrics sample body generation and later editing to follow the original
project's method while accommodating all15 families and legal geometry variants.
The explicit constraint is variable module composition according to actual family,
variant, paper and visuals, never a fixed module count or a per-family N lookup.
This turn assesses feasibility and proposes an architecture; no implementation or
new generation is performed. Current code remains explore_samples_v9.

Confirmed shared foundations: FamilyContract exposes required/conditional zones,
reading traversal, focus roles, split/span/mirror permissions and per-zone capacity.
Capacity is an upper structural bound, not a required number of modules. Classic
has3main regions with several modules allowed per region. Solver already supports
family-local geometry variants and exact compilation. family_capacity accepts an
actual LayoutSpec, but its initial default-zone estimates precede actual ownership
and can misguide writing. A source-driven editor can reuse these interfaces without
model-supplied coordinates or15separate hand-coded writing pipelines.

Proposed editorial sequence:
1. Original continuous source sections plus per-sample narrative/contribution intent.
2. Frozen family under the existing independent coverage-first policy; supply a
   bounded description of legal geometry alternatives, roles, reading and physical
   capacities, not a fixed module list or a default-zone estimate as a certificate.
3. Curator-style whole-poster writing jointly chooses content, full prose, hierarchy,
   module boundaries and complementary source visuals from original sections.
   Module count emerges from research explanation and family constraints.
4. Existing bounded family search and exact draft measurement identify a real legal
   variant or diagnosed best partial placement; drafts remain unverified diagnostics.
5. Family-aware Balancer receives entire current board, continuous source sections,
   actual selected LayoutSpec/ownership/dimensions, image loads, measured text pressure,
   per-zone and whole-poster gaps, and scientific obligations. It can revise prose,
   add useful source explanation and legally split/merge/add/drop optional modules.
   Whole-board context/output does not require rewriting every module per call.
   Existing finite edit limits still govern actual changed targets and calls; no
   free retry per variant. Reuse bounded geometry search rather than restarting
   a fresh editorial process for every variant.
6. Exact source support plus existing scientific verification and final fitting
   must establish one coherent candidate before freeze. Normal styling, Preflight,
   rendering, RenderFit, Critic and all-score publication then proceed.

EvidenceBuilder should cease being the exhaustive permission list for prose.
It may remain an auxiliary paper/source index. New useful source material needs
explicit original section/chunk IDs and verbatim support excerpts, local exact
matching, and the existing Verifier's numerical/entity/comparison/qualifier/
relationship and indispensable-information checks. A new excerpt is source material,
not already-approved science. Existing supplemental-evidence extraction demonstrates
this pattern but is not a drop-in solution: ownership, initial writing, local added
support, metric semantics, checkpoint/version binding and final publication all
need integration. Do not invent a second semantic judge or silently treat whole
chunks as unverified factual permission. Do not mutate the original evidence bank
or import old samples; any added support belongs to the current sample/candidate.

Scientific obligation identity should remain separate from mutable presentation
sentence/module identity. Protect required meaning, conditions and source coverage
while allowing display restructuring. Immutable prior candidate/audit records and
explicit before/after coverage mapping are necessary; a new sentence or new module
cannot silently drop a protected assertion. This is a contract/pipeline change,
not merely swapping a prompt. Changed generation/preparation identities require
new runs; historical science, scores and artifacts remain inspection-only.

All15families remain peers. A four-column family does not mean four modules; a
central-hero family may combine a long coherent method explanation with supporting
modules; card/matrix families may divide coherent comparable findings when source
supports them. Layout cannot invent chronology/comparisons/claims. Legal spanning
is represented as family-generated zones and preserves unique module ownership;
models never emit arbitrary x/y/w/h. A genuinely unsuitable scientific assignment
or exhausted bounded fit still records an ordinary sample failure.

Acceptance should test source-driven initial prose and adopted editorial output,
variable module composition under several legal variants, preservation during
split/merge/addition, existing family and renderer contracts, durable budgets and
historical immutability. Real PNG/PPTX inspection and source checking are needed;
CPU tests alone cannot demonstrate upstream-level writing/aesthetics. No change to
standalone classic, future Rubrics/Harness implementation, score filtering or new
model/GPU validation is implied by this feasibility assessment.


### 2026-10-27 — Detailed source-editorial implementation proposal

User requested a detailed concrete plan, not implementation. The full Chinese
proposal is in [RUBRICS_SOURCE_EDITORIAL_PLAN.md](RUBRICS_SOURCE_EDITORIAL_PLAN.md).
It supersedes the earlier optional-auxiliary EvidenceBuilder direction: Rubrics
removes its invocation and atomic-fact permission contract completely, uses
continuous source/global-story Curator writing and actual-variant-aware Balancer
editing, and directly checks generated body against original paper material.
The plan specifies all15families, variable module counts, exact source/semantic
coverage, pre-freeze fitting and verification, existing finite budgets, source
contracts/Critic/cache/publication integration, version boundaries and CPU/real
acceptance. Classic stays independent; existing v9 implementation remains active.
No generation code, models or tests were changed/run in this plan-only turn.


### 2026-10-27 — Reading-order audit and source-editorial plan refinement

Read current reading_flow/design_content/feasibility/presentation_policy/Preflight/
Critic plus latest v9audit. family_reading_v4 actively sorts physical stacking,
uses source-derived order, performs bounded128-state before/after-refill assignments
and rejects unresolved unlocked candidates. It respects independent parallel/matrix
sequences, declared finding entries and framed traversal. Local prerequisites are
a distinct editorial/scientific contract. Current joint fit failures can consume
a capacity prose edit, unlike the old pure-order repair skip path. V9audit has
no known conflicts but is partial due to mixed/unknown method role.

The source-editorial proposal now explicitly separates hard physical traversal,
verified necessary interpretation dependencies, and soft narrative/source-order
preferences. Raw paper sequence is not itself a scientific dependency proof.
Removing EB requires rebuilding source mappings, split/merge identities and all
shared search/Preflight/Critic consumers. Plan section13 records concrete changes
and regression cases; no generation code or tests/model run changed in this audit.


### 2026-10-27 — Final proposed source-editorial and visual-reading plan (not implemented)

The user requested a final revised plan and explicitly deferred execution until
confirmation. Revision two of [RUBRICS_SOURCE_EDITORIAL_PLAN.md](RUBRICS_SOURCE_EDITORIAL_PLAN.md)
incorporates model judgment of natural reading routes. This supersedes the prior
proposal to retain hard family-derived physical traversal/coordinate prerequisites.
Top-to-bottom and left-to-right have equal standing; actual grouping and rendered
geometry determine reasonable primary, alternative and branching routes.

New Rubrics would remove source/role ordering, forced reading reassignment and
corresponding old Preflight rejection/heuristic Critic flow scoring. Balancer
would judge actual bounded draft previews within existing edit opportunities;
final existing Critic would evaluate the actual final PNG. Schema/IDs, candidate
binding, physical validity and source semantics remain checked. Review does not
transfer to modified geometry/text/style, and a last-round edit cannot earn a
free follow-up call or a falsely inherited clear verdict. Ambiguity stays an
explicit quality finding under all-score publication, not a new filter.

The integrated plan also retains full Rubrics EvidenceBuilder removal, source
Curator/Balancer writing, all15families and variable modules, direct original-source
verification, final-text binding, finite budgets, cache/version compatibility and
classic/history isolation. Only ignored local plan/report/AGENTS documentation
changed; no generation code, tests or model/GPU run. The previous plan copy is
preserved at /tmp/postergen-source-editorial-plan-before-llm-reading-20261027.md.


## 2026-10-27 — Implemented source-editorial Rubrics route (v10)

User confirmed the final plan and requested careful complete implementation. The
production default now uses Parser/source-document foundation, independent source
story planning, one frozen peer family, whole-poster SourceCurator, and a finite
SourceBalancer/direct-original-verification/actual-fit loop. Rubrics no longer
invokes EvidenceBuilder or depends on evidence IDs/banks/required atom roots.
Original continuous chunks, paragraph positions, original visuals and exact source
quotes support generated prose after writing; the source material is not a renamed
atomic permission bank. Long original material fails explicitly above the bounded
context rather than being silently truncated.

Generator explore_samples_v10; preparation sample_source_science_v1; body
sample_body_source_v1; original_sections_v1; storage remains v2/schema2. All15peer
families and legal geometry variants remain. Module count/boundaries are authored
from paper and capacity; edits can rewrite/add/omit/split/merge while preserving
necessary meanings, conditions, comparisons and actual explanation. Existing
3capacity+1quality and two-affected-old/new-module limits remain. No-op quality
review is charged. Compatible reserve/key visuals use separate finite probes.

Direct SourceVerifier checks complete module and whole-poster context, exact
visible text/title/label coverage, quantities against actual support, original
locator truth, relationships, scientific function, required-meaning coverage,
preservation and useful additions. It supplies no automatically accepted rewritten
text. Closed schema and local positive-verdict completeness share one format
allowance. Explicit scientific negatives never consume format retries; exhausted
invalid verdicts cannot unlock prose retries. Format corrections preserve complete
valid neighboring modules. Raw/parsed/rejected responses, exact normalized-to-original
paragraph spans and partial progress remain. Source quantities distinguish identifiers
and conventional unsigned shared-percent notation without broad unit conversion.

Natural reading now belongs to actual-image judgment in existing Balancer calls and
the existing final visual Critic call. Top-down/left-right axes are peers; columns,
rows, mixed and parallel/shared-node routes are legal. Source/role forced sorting,
128-state reading repartition and old order rejection/scoring are isolated from new
Rubrics. Hard physical/source checks remain. Previews are actual editable renders,
separately bounded and explicitly not publishable. Reviews bind image/text/geometry/
style and never transfer clear status to edited/final images. Final Critic judges
the actual final PNG; ambiguity and low quality remain visible under all-score saving.

Two integration findings were repaired without lowering science/physical standards:
legacy module retrieval was still expecting evidence keys and is now explicitly
bypassed by source-authored candidate work; global highest-importance result focus
could conflict with mandatory-method spine placement. Source primary function is
checked by the same Verifier, and required-role witnesses are protected in beam
allocation without imposing a displayed narrative route. Actual visual subset selection
is aligned before source verification, followed by fixed coherent final refit.

Freeze/install/compile/Preflight/Renderer/readiness/publication bind exact body,
module titles, source proof and original asset identities. Source-only caches reject
old Builder contracts and copy/remap original assets into their own foundation.
No sample prose/science/template/score is imported. Source-based content/adequacy and
final reading evaluation use distinct academic_poster_source_editorial_v1 / system5.0.0
identities and existing weights. Classic graph/prompts and all existing agent-policy
values remain; shared source-conditional changes do not alter the independent route.
CLI/WebUI/README and nested timings describe the actual stages.

Validation and evidence:

- Complete CPU suite:1077passed plus5subtests,6existing dependency warnings,974.80s.
  /tmp/postergen-source-editorial-full-cpu.log. Generator/config/README hashes stayed
  frozen throughout. The final cache self-containment regression was added after
  suite collection; its complete final file separately passes10tests in9.69s.
  /tmp/postergen-source-cache-final.log. Do not sum overlapping test totals.
-61new source tests exercise all15family contracts, direct support/protocol negatives,
  mutable module ownership, natural route/branch protocol, durable budgets/replay,
  exact source positions, actual editable draft PNG/PPTX and a complete default Runner
  through actual fit/compiler/font/Preflight/Renderer/RenderFit/Critic/store/templates.
  Model responses in these runs are OFFLINE SYNTHETIC TRANSCRIPTS; outputs are /tmp-only
  fixtures, not real paper science or official Rubrics acceptance. Low/reference-failed
  synthetic outputs are saved, proving storage does not hide quality failures.
- Frontend local npm build and both CLI help/import checks pass. No dependency install.
- All8089baseline historical files remain present/byte-identical;
  /tmp/postergen-source-editorial-baseline-20261027.json. No old run/result migration.
  Existing agent policies equal baseline values; Parser, ClaimWriter, ClaimVerifier,
  shared model wrapper and family geometry/compiler files retain their prior bytes.
- No real model service/GPU paper generation was launched. Scientific alias stability,
  adopted prose improvement and actual aesthetics are UNVALIDATED by these CPU checks.
  Fresh source preparation and human original-paper/PNG/PPTX comparison remain the
  separate real acceptance stage; old evidence caches cannot substitute for it.

The implementation follows docs/reports/RUBRICS_SOURCE_EDITORIAL_PLAN.md. AGENTS was
updated. Atomic local commit and final tree state are recorded below after commit.


Atomic local implementation commit: `65da840` — 44 tracked paths, 2713 insertions / 196 deletions; no push. Tracked worktree clean after commit. Code/CPU acceptance complete; no real model paper acceptance claimed.


## 2026-10-27 — Native PDF source and program-bound paragraph citations

User authorized completion after inspecting failed real run `run_a6b3bccf23ca4ce4b2a9`.
That v10 run failed in narrative planning before family/Curator/Balancer/rendering:
13 citations, 7 whitespace-exact and 6 case/fi-letter/Markdown mismatches. The PDF
visible/native text preserves those letters. All 3 API calls succeeded; the error
was a fragile source-location protocol, not demonstrated scientific hallucination.

Implementation is generator v11 / source preparation v2 / original sections v2;
body and dataset/storage remain unchanged. Marker determines source page regions
and their order; native PDF glyphs determine emitted text. Coverage, overlaps,
OCR-only/missing source, undecodable glyphs and unexplained prose/numeric conflicts
fail before model work. No dictionary/model repair or global column sorting.
Original converter text and font/region/character provenance remain durable.

The first real extraction audit also found three TeX delimiter control codes.
The exact embedded CFF charset maps glyph IDs 3/1/2 to braceleftbigg/parenleftbig/
parenrightbig; deterministic recovery records the font program digest and bounds.
No arbitrary unknown glyph is substituted. Replaying actual Marker region bounds
produced 46763 characters, 162 regions and 15 source units with no unresolved
issues, before final fresh extraction validation. These counts describe source
transcription, not scientific or aesthetic acceptance.

Source references now select original paragraph IDs; program-copied exact text
is bound after schema validation and persisted separately from raw responses.
One existing shared format repair can fix locators only, preserving prose, valid
references and neighbors. Explicit scientific rejection, including any negative
coverage/obligation field, never earns another call. SourceVerifier still judges
meaning, quantities/conditions, relationships and necessary information. Caption
metadata also binds to native original regions; tables/formulas retain native
line positions. Cache/run identities reject previous text and bind dependency
versions; old stored results are untouched. Classic follows its prior branch.

All diagnostics and tests use `/tmp/postergen-extraction-*`. The real extraction
probe uses GPU 5 only, a supervised owned process group, and no poster-writing API.
No fresh full poster run is launched as part of this repair. Final validation and
commit results follow below. Incorrectly encoded printable glyphs and image-only
scientific content remain a recognition limitation; successful coverage cannot
establish universal visible-PDF equivalence or semantic poster accuracy.

Additional real-source regression: the literal paragraph says "improvement ranges\nfrom 3%-17%". The prior numeric helper rejected a scientifically faithful "3% to 17%" paraphrase by interpreting the ASCII hyphen as a negative sign. Only an explicit range/ranges/ranging-from context with both unsigned percent bounds now licenses positive endpoints in the same actual quoted support; signed bounds, Unicode mathematical minus, subtraction and missing percent signs remain strict. The unchanged semantic verifier still checks the actual interval/comparator/conditions. The in-progress preliminary full suite was interrupted to include this demonstrated counterexample; only the final frozen-tree suite is acceptance evidence.

Final repair verification: **1131 passed + 5 subtests**, 6 existing dependency warnings, **978.36s**, exact frozen tree. All 204 source/config/test/package files retain pre-suite hashes; all 8128 baseline historical files remain present/byte-identical. Focused set 155 passed, followed by the final 52-case native/protocol file and complete frozen suite including the additional negative-recovery case. Both CLI help entries and `uv lock --check --offline` pass. No dependency version/artifact hash changed; fonttools was promoted from the existing lock to a direct requirement.

Final fresh extraction (actual Marker, native PDF and real asset-caption binding, no poster-writing API): `/tmp/postergen-extraction-native-validated/`, exit0, 27.82s, GPU5 only. 9pages,162regions,39022 nonspace native characters,46763 source characters,3 exact CFF delimiter recoveries,7caption bindings,5tables with separate-cell numeric checks,15source units. Complete annotated original-source input is122418characters within240000. Owned process379776/process group cleaned; unrelated GPU5 allocations and the GPU3Qwen service untouched. This demonstrates this paper's extraction/provenance behavior, not real-model prose/science or poster aesthetics.

Final CPU log: `/tmp/postergen-extraction-full-cpu-final.log`; manifests `/tmp/postergen-extraction-frozen-tree.json` and `/tmp/postergen-extraction-repair-baseline.json`. Full model poster acceptance remains a separately launched fresh run; old v10/evidence caches and old run resume are incompatible.

Atomic local commit: **`6ea6bd6`**, `fix(source): preserve PDF text and bind paragraph citations`, 22 tracked paths, 1082 insertions / 44 deletions, no push. Local AGENTS/report remain ignored. Post-commit tracked tree is clean.


## 2026-10-27: Curator display metadata and shared format recovery repair

The user requested repair after run_32b3fb2b0d26442d89f5 failed. Native source
extraction and the narrative plan passed, but Curator returned five modules / eleven
entries / roughly496 English words with eleven independent display headings.
normalize_candidate required all labels to be literal prose phrases, although this
response used only plain/steps, where the renderer does not display those labels.
After clearing labels diagnostically, the method step indices0/1/2 also failed the
old1/2/3 contract. Validation happened after request() returned, so no shared format
recovery ran. Neither Balancer, scientific verification, fit nor rendering ran.

Generator is now explore_samples_v12; preparation/source extraction identities
remain sample_source_science_v2/original_sections_v2. Curator and Balancer both
validate candidates within the existing request/recovery scope. Unused plain/steps
labels are cleared, non-step indices canonicalized to0 and steps numbered1..N in
existing list order. Before/after changes persist in Curator normalization.json and
Balancer normalized.json. Source prose, item order and scientific relationships
are not inferred or repaired by these presentation operations.

Topics labels must match actual renderer-compatible exact local text, with an
empty label allowed. All invalid label paths are reported together, and the one
existing sample-wide format correction can change only those exact fields. A masked
raw-response guard preserves every other field, including scientifically correct
neighbors, same-module prose/references, valid labels and Balancer reading/placement/
lineage/reason data. No extra edit/quality round, scientific retry or judge is added.
Scientific support, numeric matching, chronology, full visible-text coverage, exact
source proof and all15family physical gates remain. Prompts/schema/README align.

The actual saved response was replayed through the real source_curator_node in
/tmp/postergen-presentation-real-response/, using a local response provider with
remote model construction explicitly blocked. It passes normalization and exact
journal replay with five modules / eleven entries, unchanged prose and entry order,
eighteen metadata changes, step indices1/2/3, and no format-correction charge. This
is structural acceptance of archived text, not scientific/physical or aesthetic
acceptance; the response still needs actual direct-original verification and fit.
No original run or historical output was edited.

Final frozen-code validation:173 focused tests pass in139.85s; full CPU suite
1148passed +5subtests in975.27s (16m15s), six existing dependency warnings. Both
Rubrics/classic CLI help checks pass. All214 frozen source/config/test/package
files stayed unchanged; all8179 historical data/output files remain present and
byte-identical. Evidence:/tmp/postergen-presentation-focused-final.log,
/tmp/postergen-presentation-full-cpu.log,
/tmp/postergen-presentation-frozen-tree.json,
/tmp/postergen-presentation-repair-history.json and
/tmp/postergen-presentation-integrity-final.json. The unrelated user-owned HTML
deletion remains outside this task; no GPU/model run, historical data migration
or poster-quality acceptance occurred.

Atomic local presentation repair commit: `80aa807` — 8 tracked paths, 261 insertions / 21 deletions; no push. Full1148tests +5subtests pass. Only the pre-existing user deletion of excavator_loading.html remains unstaged; no task source files are untracked.


## 2026-10-27: Combined incompleteness and format recovery repair (v13)

Actual run_ef6a23942b8e40308cb2 passed native extraction/narrative, then failed
Curator. Initial4modules/9entries/~332words assigned ob2/ob3 but omitted ob1, the
budgeted exploration/exploitation trade-off, both in metadata and clear visible
explanation. Three topics cues were already nonliteral. V12 raised the global
missing-meaning error before those cues, sent only that error to recovery, and
classified all4schema/source-valid modules as locked valid neighbors. Recovery
added2modules (6modules/13entries/~471words), keeping old4unchanged, but hit the
old cue errors; even clearing them diagnostically failed the frozen module count.
The family capacity bound was7, not4. No API/timeout/truncation/PDF failure,
Balancer/scientific check, fit or poster output occurred.

V13 clears invalid optional topics cues with before/after/reason audit, preserving
scientific prose/order, and aggregates local structural field errors. Schema
diagnostics report every detected schema path. The one existing shared format
correction freezes all other fields; scientific/content errors no longer enter it.
Curator saves structurally valid but unverified incomplete drafts, with missing
obligation records. converge checks these before fit/verification, charges an
ordinary capacity edit and asks the existing Balancer to map actually explained
meaning or add original-supported explanation/modules within <=2old/2new scope.
Initial module count can change during this charged edit; protected neighbors and
program-offered reserves stay intact. Partial work can continue only within the
existing3capacity+1quality budget. The same direct-source verifier rejects missing
assignments and checks actual visible meaning; no metadata-only approval is added.
Source-key reserve offer has an explicit draft-only incomplete mode.

Prompts check all relevant baselines under identical experimental conditions.
Archived distance result calls AGS2.50 the best baseline, although table3 has
greedy baselines2.75 and HAGS4.50 at80000/5%. The80% ratio is vsAGS, not vsbest
(about63.6%). Science logic is not replaced with keyword/table heuristics or an
extra model judge; unsupported derived-number permission is not expanded.

Isolated replay:/tmp/postergen-completeness-real-response-validated/. The real
archived initial draft passes Curator with ob1 explicitly unverified/missing and
invalid cues cleared. The two added archived modules are adapted to the proper
Balancer envelope (lineage/reason/incomplete reading review), preserving the
CURRENT four modules including program-offered key reserve metadata. Directly
replaying the old raw four-module fields would lose that reserve and correctly
exceed the edit scope; that preliminary diagnostic remains separate. The legal
adapted4->6edit uses1capacity charge and0format corrections; exact replay makes
no further provider calls. Local response providers were used, remote model
construction blocked, and0real model calls made. Original four modules stay
identical. An isolated archived res_2 claim is rejected by unchanged numeric
support even with an adversarial all-true verdict. This is structural/protocol
acceptance of archived content, not full scientific/physical/aesthetic acceptance.
No actual poster generation/GPU run or historical mutation was performed.

Final boundary review also added independent assignment/actual verdict/summary
coverage checks inside assert_verified, used by readiness/compile/render/publication.
Two regressions reconstruct otherwise self-consistent rehashed receipts after
dropping assignments or falsifying the coverage summary; both are rejected. The
preliminary whole-suite PID398564 was explicitly interrupted after~2minutes so
these final source changes are covered by a NEW frozen suite; its interrupted
log is not completion evidence. Final focused presentation/completeness boundary
file set:48passed in14.97s. Earlier broad focused set:202passed in146.84s.

Final frozen-tree validation and handoff2026-10-28:1179tests +5subtests pass in
984.04s (16m24s),6existing dependency warnings. Both CLI help checks pass. All215
frozen source/config/test/package files stayed identical; all8236baseline history
files remain present and byte-identical. Broad focused set202passed; final boundary
set48passed. Evidence:/tmp/postergen-completeness-full-cpu-final.log,
/tmp/postergen-completeness-focused-final.log,
/tmp/postergen-completeness-boundary-final.log,
/tmp/postergen-completeness-frozen-tree-final.json,
/tmp/postergen-completeness-history.json,
/tmp/postergen-completeness-integrity-final.json and
/tmp/postergen-completeness-real-response-validated/replay_report.json.
Automatic approval service usage exhaustion temporarily prevented reading the
final log/committing; resumed access confirmed completion and unchanged sources.
This is not a safety rejection. No source changes or extra test reruns were needed.
No fresh real-model scientific, rendered-poster or aesthetic acceptance is claimed.

Atomic local v13 repair commit: `1213384` — 12 tracked paths,413insertions/60deletions;
local only, no push. Final full suite1179tests +5subtests passes. Only the
pre-existing user deletion of excavator_loading.html remains unstaged; no task
source files are untracked. The guide and existing report are updated but ignored.
No fresh real-model poster generation/scientific/aesthetic acceptance is claimed.


## 2026-10-28：v14 空间写作与局部正文编辑（验收中）

本次修复针对真实 v13 run_22f1fd6e0ebb40afa724 的完整 no-op 编辑与冗余 lineage 拒绝。
失败的845词初稿并非论文提取或接口超时问题。只接受多填的 lineage 仍无法解决高度溢出。

新增 source_space.py 为 Curator 提供各合法变体实际区域、字号、标题与原图表占用估计，
并为 Balancer 提供无阅读顺序约束的非绑定分配、正文可用空间和具体压缩目标。
source_edits.py 使模型仅返回修改/新增模块、显式删除、可选次序及真实拆分合并来源。
程序合并未改邻居、计算普通原位修改来源、候选身份和图片指纹；无图容量编辑不要求视觉判断。
视觉阅读仍在实际图片的既有 Balancer/最终 Critic 调用中完成。

SourceRequests 内完成补丁合并、模块变更范围、布局请求和阅读协议校验。
结构恢复仍只有一个共享名额，严格保护未诊断字段及合法邻居；科学拒绝不获得格式重试。
收敛核验将编辑起点作为完整保义上下文传给同一个原文核验器。没有恢复 EB、固定模块数量、
统一硬词数上限、旧阅读排序、跨样本检索、额外编辑预算或新的科学裁判。
生成版本 v14，其余原文提取/缓存、正文、数据集协议与模型策略保持。

验收要求：相关与全量 CPU 测试；旧输出完整性；真实同论文、同家族样本的 PNG/PPTX、
原文核验、物理检查和可视阅读检查。未取得这些证据前不得宣称样本生成成功。

### v14 首次真实验收与 v15 必须编辑任务修正

真实 run_04d00101f9034bfd8c50：同论文、同 seed20261027，仍选 top_hero_bottom_grid。
Curator 返回5模块/381词，相比失败 v13 的845词明显紧凑；但未分配 obl_1。
Balancer 仅返回166输出 token 的空补丁，理由错误地把原文中的探索/利用说明说成已在
可见 mod_hero 中。当前正文实际没有这段说明，未赋予该 ID；所以不是程序应自动批准的情况。
正式结果 preparation_failed，PNG/PPTX 均无；supervisor exit1，GPU5 无残留。

v15 在完整输入之后单列 CURRENT EDIT TASK，重列实际可见目标正文、当前含义 ID、
缺失含义及必须执行的动作，明确引用不是已显示解释。容量 schema 要求至少一个返回模块，
控制器检查真实动作；空补丁在 schema 前按内容失败处理，不能购买免费格式重试。
质量空补丁仍合法。预算、原文核验、家族与物理门禁保持。
预备全量测试为避免代码混跑已明确中断；后续最终冻结代码重新测试并继续真实验收。

### v16：百分号遇到句末标点的真实误报与单位漏洞

run_208d168de40b4ee68299 返回4模块/331词；Balancer 真实改写方法模块，补入探索／利用
含义和预算约束，并完成 ob2/ob3 映射。初步完整拟合通过，保留 table4/table5，figure2
放回储备。前两个模块语义核验通过。结果模块语义判定为 supported，实际正确引用
src_00012:p12，其中明确有42%、70%、5%。程序仍误报缺数值。

逐字重放证实 quantity_tokens 的末端 (?![\w.]) 错将原文句末70%.回退为裸70，丢失单位；
同一错误也能把不受原文数量70支持的海报句末70%.误当作裸70。v16 改为区分句末标点、
小数续写和百分号回退，保留正负号、数值、百分比单位与本地引句支持要求，不弱化语义检查。
新增句号／百分号／浮点／科学计数法和数量冒充百分比的反例。原始科学布尔判决、正文、
原文、引句均不改的实际 verdict 重放另存 /tmp；不使用新模型判断替代原文核验。

为了避免数值误报继续消耗内容编辑预算，明确停止本任务 v15 验收和预备全量测试。
监督器完成清理、GPU5 无残留；原运行无 FINALIZED，无 PNG/PPTX。标准独占锁下只将
未终结的运行投影改为 PAUSED，并记录 validation_interruption.json，原始科学记录保留。
这些中断记录不是样本成功，也不能导入后续样本。最终 v16 仍需重新冻结、全量测试与真实验收。

### v17：空间反馈必须与拟合器一致，建议变体不固定搜索

v16 run_0c0abff2fb754652b4c4：5模块/401词，必要含义已分配。第一次真实容量编辑把
距离结果／消融各45词压到27／28词，证明编辑已执行；但同时输出变体601...，使拟合
从12个候选变为单一几何。第二次模型看到零估计压力和空建议目标，声称内容已经放得下，
回显全部5模块，因无实际动作被拒绝。结果 preparation_failed，无海报；监督器exit1，GPU5空。

程序空间估计用1.0，实际快速拟合用1.2，是本次新增空间反馈实现的不一致。v17 统一使用
同一配置安全系数；写作预算也计入该系数。真实失败反馈覆盖“估计可行”，缺少建议目标时
从实际高度压力选择具体模块，提供明确当前正文与压缩参考。容量 schema 固定 variant_id
为空，模型不再把建议分配固定成唯一几何；程序继续搜索该家族的合法变体，保留局部区域请求。

独立真实测量回归比较编辑测量与实际默认 fitter 函数；另测失败压力 fallback 与禁止建议变体固定。
离线重放 v16 两次输入，均按1.2生成具体目标，第二次不再丢失目标。真实旧记录不改、不作为新样本输入。
预备 v16 全量测试在源码改动前明确停止。最终仍须冻结 v17、全量测试及真实海报验收，未提前宣称成功。

### v18：含图表的最终核验后重排与完整回归缺口

v17 run_cfb8d60f9b514c23abf1：4模块/377词，初步拟合通过，4个模块的真实原文核验全部通过。
最终 verified refit 在保留已选图表时触发 TypeError：把 source_candidate.modules.visual_ids
中的字符串当作 visual_assets 对象索引。该处是早期 source 路由的真实类型错误；原纯文本
全链路测试没有触发非空资产分支。v18 直接保留字符串ID，语义、原文和物理标准不变。

新增真实图片资产最终重排回归，并把既有默认完整 Runner 测试升级为：原生 PDF 中实际嵌入
PNG，再把该资产穿过完整拟合、科学冻结、compile、Preflight、PNG/PPTX、RenderFit、模板和保存。
2项边界全部通过（35.02s）。堆叠顺序不是旧阅读顺序保护，不把它当作固定几何／所有权的一部分。

另在 /tmp 使用 v17 已真实核验的原文证明，零模型调用重放修复后的最终拟合及实际 draft渲染，
生成真实 PNG/PPTX，保留 table4/table1。明确 eligible_for_rubrics=false，不能伪装成独立新样本。
工程重放必须从原始基础补回完整 caption_source；拟合输入是测量快照，不是完整科学状态。
证据：/tmp/postergen-source-visual-refit-focused-final.log、
/tmp/postergen-source-visual-real-refit-final.log、/tmp/postergen-source-visual-real-refit/acceptance.json。
v17 保留 FAILED/0poster 结果，监督器exit1、GPU5空；旧样本／原文未改。最终仍需新版本真实独立样本。

### v18 正式验收失败与 v19 具体数值诊断

额度恢复后正式启动 run_169d0debfbf7415c943c，同论文、同种子、同 top_hero_bottom_grid，
只复用严格原始论文缓存。初稿4模块327词，缺探索/利用必要含义；一次真实容量编辑补齐，
成为328词，拟合通过。方法与均匀成本结果两个真实语义核验通过。距离成本原文写80k，
正文写80,000；当前保守数值帮助函数不做缩写换算，所以同一引用支持被拒绝。
这不是缺失原文，也不是80,000在科学数值上不等于80k。

此前诊断只有“A quantity is absent from its actual original support”，没有具体数值。
第二次容量编辑错误声称修正Manhattan定义，实际保留全部正文，仅改变引用；重新核验
仍拒绝相同值。第三次容量编辑无有效变化被拒绝。运行正常终结 preparation_failed，
rendered0/scored0，监督器exit1、GPU5空。不存在正式PNG/PPTX，不把临时预览算成功。

V18最终CPU：1224tests+5subtests通过，1135.25s，6个已有依赖警告；重点238通过，
291.79s。两个CLI help通过。210个冻结源/配置/测试文件及8287个历史文件全部未变。
证据：/tmp/postergen-delivery-full-cpu.log、/tmp/postergen-delivery-focused.log、
/tmp/postergen-delivery-integrity.json；真实运行证据位于正式run和background目录。

V19仅改进反馈与提示：同一个typed helper同时产生准入结果和缺失值；错误明确可见target_id、
缺失value/kind以及实际引用的完整原文段落，放入既有CURRENT EDIT TASK。提示要求保留
原文缩写数值写法，不把编辑理由当成正文变更。没有扩展单位换算、放宽数值标准、增加
内容预算/格式名额/裁判，提取和缓存身份保持，旧运行拒绝resume。新增反例保证80,000仍拒绝
而诊断准确指出80000和原文80k；两个真实bound verdict零模型重放保持拒绝结论并获得具体诊断。
证据：/tmp/postergen-numeric-feedback-real.json、/tmp/postergen-numeric-feedback-real.log。
V19最终冻结测试及全新正式样本仍须完成，不能引用v18CPU结果替代。

### v19 正式验收失败与 v20 层级标识／写作任务修正

V19最终完整CPU：1225tests+5subtests通过，1134.94s，6个已有依赖警告；重点116通过，
181.61s，两个CLI help通过。真实 run_bc4b873d80c64879a1ff 同论文／同种子／同家族，
只用原论文缓存，初稿4模块964词且漏obl_1。第一轮补映射；第二轮215/239词降为99/74；
第三轮353/157降为119/46，最终338词，拟合通过。数量缩写80k已保留，未重现前一拒绝。

总述真实原文核验通过；方法语义判决为supported，却被确定性数量检查拒绝：海报写
"level 1 chooses a region, level 2 chooses a parcel"，原文写level-1/level-2。
旧帮助函数把后者当标识忽略，却把前者当实验数量要求再引用。不是方法科学含义错误。
容量机会已耗尽，运行正常终结preparation_failed/0poster；监督器exit1、GPU5空。
结果和消融尚未核验，不把方法正判或临时预览冒充整篇科学／海报验收。

V20让level后正整数层级编号与既有连字符标识得到一致处理；百分比、负数、小数及
独立实验数量保持严格。反例覆盖level1不能给1query/1%授权，也不能把level1.5/-1
忽略。真实原始方法bound verdict在不改正文／原文／判决／引句的零调用重放中通过；
证据/tmp/postergen-hierarchy-real-replay.log，明确非整篇核验。

写作方面，完整源章节位于输入后部，先前family.writing_space会被长原文隔开。
新增CURRENT WRITING TASK放在完整原文之后，同一次Curator调用中重列少数必要含义、
实际字号及每个合法变体的各zone正文估计／带一张图表时的剩余范围；详细每图占用仍在
原brief中。要求连贯精简解释、按一个完整变体共同分摊，而不是跨变体相加容量或复制
整段原文。没有新增模型调用、固定模块数／词数上限、几何固定／阅读排序或新的科学裁判。
回归保护完整原文仍在前文、全部变体仍可选、任务真实位于末尾且不改变布局请求。
V20仍需重点检查、冻结全量CPU和全新正式独立样本验收。

### v20 实际长度异常与 v21 返回凭据接收修正

真实 run_edaa78e7c9bd41949981：末尾写作任务生效，4模块281词，全部必要含义已分配，
初步实际拟合直接通过，尚未使用容量编辑。第一个SourceVerifier等待883.2s后报SDK
LengthFinishReasonError，未取得可解析的科学判决，正常终结preparation_failed/0posters，
监督器exit1、GPU5空。不是科学否定，也不是PDF或物理失败。该旧请求没有持久化正文，
不能恢复/猜测其返回或重新提交。policy仍为thinking=true/max_tokens12000/timeout900。

V20完整CPU：1232通过、1失败、5subtests通过，1125.94s，6个已有警告。
唯一失败是离线完整Runner的假模型解析没有剥离新增CURRENT WRITING TASK，非生产
Curator错误。只修改测试解析分隔符后该完整含图链路1通过/19.13s；生产源/配置与真实
启动字节完全一致。新冻结表记录这一个测试文件差异；旧失败全量不是最终通过证据。

检查本地SDK源码确认LengthFinishReasonError真实携带ChatCompletion对象。V21仅对
SourceVerifier显式启用该返回接收：必须是实际SDK异常且有完整用量、唯一assistant
choice、length结束和非空id，才存原始completion、visible content、usage及摘要绑定。
原始reasoning仅留审计，不当作原文/科学证据，不放回恢复提示。计入真实消耗，保留
原model_requests失败事件。超时、流式缺用量、丢失返回、打断、损坏/缺失凭据均拒绝重发。

返回但被截断的verdict仅使用已有一次样本共享格式名额完成格式；不改变max_tokens/
thinking/timeout、重试政策、科学标准、3capacity+1quality或添加裁判/免费内容机会。
显式科学否定立即拒绝，不进入恢复。JSON自身已完整时全部有效字段和引用也冻结，
只允许完成返回协议；不能借length重写有效判决。第二次length无新机会，精确重放零调用。
新边界测试覆盖原始凭据持久化、全样本格式账本、正负判决、二次耗尽、非opt-in路径、
超时与不完整凭据拒绝、丢失/损坏历史拒绝、费用只记一次及完整JSON不可改写。
V21还须重点回归、完整冻结CPU和全新正式样本，不能用工程接收测试冒充真实海报。

### v21 最终正式样本验收：生成／科学／物理通过，质量仍未通过

真实独立新样本run_851f7afab99d465088a7，论文Active Geospatial Search for Efficient Tenant
Eviction Outreach，run seed20261027／sample seed20261028，仍由标准15家族选择器选中
top_hero_bottom_grid。只复用run_ef6a23942b8e40308cb2的严格原始论文缓存，正文／叙事／
所有科学判决均重新生成，没有旧样本科学内容迁移或重发旧缺失响应。

初稿4模块322词，全部必要含义已分配，首次拟合直接通过；4个真实原文核验也全部通过。
随后的锁定几何复拟合发现m1快速高度19.747in>区域17.007in，触发一次既有容量编辑，
把m1从81词缩成57词，其他模块不动。此后4模块再次逐一真实核验通过，最终复拟合通过。
最初看到source_balancer日志时曾误报为质量阶段，检查journal phase后已向用户更正，
以实际阶段为准，不能从模型调用名推断已完成渲染。

本样本最终4模块298词；m2方法示意图未能保留，figure1/figure2两次有限物理恢复尝试
都未采用；可见table1/table3。预算为capacity1/3、quality1/1、format0/1，视觉恢复2次。
实际质量编辑为reviewed_no_change，预览阅读clear。全程未触发本次新增长度返回恢复，
因此真实成功不能冒充该恢复已在服务端实测；其边界证据来自实际SDK对象的离线反例。

实际最终文件已经原子发布并通过额外只读审计：
- storage/rubrics_samples/posters/run_851f7afab99d465088a7_sample_000001/poster.png，417981bytes；
- 同目录poster.pptx，422153bytes，1张slide，9个非空原生可编辑文字框；
- FINALIZED/bundle/snapshot摘要一致；重新assert_compiled_text，绑定原论文PDF和完整源资产；
- Preflight passed／0issues；RenderFit conclusive passed，正文和章节标题8/8，覆盖率100%；
- 最终PNG已人工打开检查，不用临时工程重放或draft冒充发布结果。

最终实际图片的视觉Critic调用96.0s完成，reading_status=needs_revision，主路由为
m4→m3→m2→m1。它指出顶部距离成本表格过小、底部文本密集且层次不够。此判断绑定
实际最终PNG，优先于先前蓝色草稿的clear。人工观察还包括HAGS缩写在首个结果之后
才解释、关键方法图缺失、留白与图表比例失衡。结果先行本身不是错误；这里需要改善
的是入口自洽、图表可读性和解释层次，不恢复旧ROLE_RANK或源章节硬排序。

紧接着既有critic_content请求0.328s报BadRequestError，因此没有总体分数。
正式结果为COMPLETED／rendered1／scored0／evaluation_failed，PNG/PPTX仍按所有已渲染
结果均保存的契约归档为unclassified。生成成功不等于质量达标，也不能把模型预览clear
或CPU通过说成达到原始项目效果。没有按分数筛样本或删除失败记录。

本地额外诊断（0网络／0模型调用）显示正文评分提示283382字符：original122501、
source_verification112513、candidate23666、story18481、final_reading5597。明显存在
审计追踪重复带来的上下文压力线索，但没有保留服务端具体400错误体，也没有实际token
计数／服务端限制证据，不能断言根因就是上下文超限。向额外分词端点发送完整提示的
附加诊断被自动审批拒绝，理由是可能额外披露论文内容；命令未执行，未绕过拒绝，
只进行了本地审计，也没有重发该失败评分请求或改动其FINALIZED记录。

最终代码验证：重点87通过/103.13s，最终SDK接收边界12通过/6.27s；完整冻结CPU
1245tests+5subtests通过，1127.50s，6个已有依赖警告。两个CLI help、uv lock --check
--offline及git diff --check通过。211个冻结源／配置／测试／包文件与8287个旧历史文件
保持不变。真实生成监督器exit0，生成进程已退出，GPU5无遗留计算进程，GPU3服务未改。
代码在未提交但固定哈希的v21工作树运行，不改写launch中当时真实的HEAD记录。
首次显式暂存才检查出新文件source_edits.py末尾多余空白行；只清理了该EOF空白，
前后AST完全相同，其他210个冻结文件哈希保持相同。没有逻辑／策略变化或额外模型调用，
也不为这一纯空白清理重复全量测试。实际测试／生成清单与最终交付清单明确分开：
/tmp/postergen-length-receipt-delivery-frozen.json、/tmp/postergen-length-receipt-packaging.json。
用户原有excavator_loading.html删除继续留在提交之外。

证据：/tmp/postergen-length-receipt-focused.log、
/tmp/postergen-length-receipt-boundary-final.log、/tmp/postergen-length-receipt-full-cpu.log、
/tmp/postergen-length-receipt-frozen.json、/tmp/postergen-length-receipt-acceptance.json、
/tmp/postergen-length-receipt-acceptance-audit.log、/tmp/postergen-final-content-local-audit.json，
以及storage/rubrics_samples/background/source_receipt_v21_validation_20261028/。

结论：已完成一份真实新样本的技术生成和验收，原文与物理检查通过；阅读／版面质量
仍需改进，正文质量评分尚未完成。单论文单家族结果不证明全部15家族的真实质量，
更不能从离线测试推断科学模型普遍可靠或已达到上游美观效果。

Atomic local measured-source repair commit: `b608a8b` — 18 tracked files,987 insertions/65 deletions; no push. Technical generated-artifact acceptance passes for run_851f7afab99d465088a7; quality remains needs_revision and content scoring unavailable. Only the pre-existing excavator_loading.html deletion remains unstaged. Final delivery manifest explicitly records the AST-identical EOF packaging cleanup. Full acceptance report: storage/rubrics_samples/background/source_receipt_v21_validation_20261028/acceptance_report.json.


### v22 区域容量、双向非递归合并与宽高调整空白保护（2026-10-28）

按用户确认图实施15家族容量：222、22、2222、222、1111、1111、11211、221、
111111、111111、2222、111111、11111、211111、111111。所有注册区域与宽高变体
共用同一容量来源；正文模块编辑的原有预算、科学核验和动态模块数仍保留。

移除区域拆分生成，拓扑/编译/Preflight拒绝旧拆分区域。允许同排等高或同列等宽、
相邻间距不超过正文对应轴6%的两个普通capacity1区域合并为capacity2；最多两对，
互不复用区域、不递归，主视觉/required_zones/protected_spans不可合并。每个合并
保存merged_from并绑定几何指纹，最终验证检查原区域完整覆盖、成员唯一、容量及
角色。13号原专用双列capacity4逻辑移除，双列由合法单对合并产生，不丢失原区域。

宽高变体和局部构图可继续搜索；采用时严格比较整个正文区的容器并集空白面积、
未分配面积、最大空洞、横纵及内部/底部间隙，仅允许测量舍入误差。新增总空白
面积统计，防止最大空洞不变但空白总量增加；更高分数不能豁免空白退化。源编辑
quality请求如改变几何，还须与其自身实际基线比较。该度量是模块几何包络统计，
不是逐像素文字墨迹覆盖证明，也不保证绝对丰满或视觉质量。

版本explore_samples_v22 / LayoutSpec4，拒绝旧运行恢复；提取、原文缓存身份、
准备/正文/存储合同和模型策略均不变。未把本次变更扩成先布局后写作的重构；
未调用真实模型/GPU或修改既有样本。经典独立路线未改；经典家族区域容量按用户
要求更新。旧测试中强制5模块及允许区域拆分等假设按新合同更新；补全仍验证可在
容量内增加两个模块，并非偷偷恢复旧容量。最终验证结果待下方补记。


v22 最终验证：冻结213个源代码/配置/测试/包文件后，全量CPU运行1268项，1262通过、
6失败，另5子测试通过，耗时943.23s。6失败准确为旧性能测试current_pinned的非对称
双列、顶部主视觉网格、横向叙事带、对照布局、首尾框架5项（仍向4/5槽区域分配6
模块），及遗留阅读检查method_flow_spine1项（仍依赖旧侧区容量）。随后仅修改
这两份测试文件中的样本数量/角色分配，生产代码、配置和README完全未改；将这
两份文件及全部新区域规则/混合方向测试合计152项完整复验，152通过，383.62s。
新增混合方向测试检查实际12候选预算中同时存在一横一纵、两对成员互斥的变体，
不扩大搜索预算。本次最终1269个CPU用例全部获得当前文件版本的通过覆盖，另5子
测试通过，无遗留失败；这是全量+受影响文件复验的合并覆盖，不冒称修改测试后又
单次重跑了一份全绿全量。新增测试在首轮全量收集后加入，已单独及合并复验通过。

最终214文件交付清单、首次全量清单和覆盖计算：
/tmp/postergen-region-policy-delivery-frozen.json、
/tmp/postergen-region-policy-frozen.json、
/tmp/postergen-region-policy-validation.json。全量/补验日志分别为
/tmp/postergen-region-policy-full-cpu.log与
/tmp/postergen-region-policy-final-recheck.log。两个CLI帮助检查通过，diff --check
通过。6558个本次基线Rubrics历史文件全部仍存在且字节不变；未改任何历史样本。
用户预先删除excavator_loading.html仍保持删除且未纳入本任务。没有新真实模型或
GPU生成，几何规则验证不等于新真实论文的科学/视觉质量验收。

代码生成的容量和混合合并示意保存在/tmp/postergen-region-policy-delivery/，其中
mixed-axis-example.png来自实际生成的同一候选（纵向合并右列上下两格，同时横向
合并左下两格）。它是几何检查图，不能视为新海报样本或Rubrics成果。

## 2026-10-29：v23 整张海报联合写作改造

本次按用户确认的方案替换默认 Rubrics 生成链路。生成器
explore_samples_v23 / preparation sample_editorial_v1 / editorial
poster_editorial_v1；数据集和 storage schema 保持 rubrics_samples_v2/schema2。
独立 classic 路线保留。旧 source 路线仅保留显式诊断入口，不会成为新流程的回退。

新执行顺序：Parser（PDF原生文字、图表和题注，模型标题作者、ABT、章节关键点、
图表语义分类）→ 程序选定一个布局家族 → Curator联合选择内容、划分模块、写正文、
分配图表和区域 → 配色及标题形式 → 实测联合准备 → 编译 → 原有关键词与字体强调 →
Preflight → PPTX/PNG → RenderFit → 最终Critic → 所有已渲染成果保存。

删除默认链路中的 source_document、SourceNarrativePlanner、必要含义/obligation
分配、source quote/段落定位、独立SourceVerifier和数字准入。原生PDF文字/字体解码及
题注绑定修复保留，因为它们处理输入识别问题，不限制正文写法。完整原始文字交给最终
内容Critic，评估记录 supported/issues/uncertain/unavailable。渲染就绪快照只证明
内容/资源/区域/预算绑定，不代表科学核验通过。评估失败保留成品、总分为空，不重生成。

Curator只看到家族原始区域及实际宽高、字体、图表占用估计，不预生成十二个变体。
初稿模块数范围是区域数到容量总和，十五家族依次为3–6 /2–4 /4–8 /3–6 /4 /4 /
5–6 /3–5 /6 /6 /4–8 /6 /5 /6–7 /6。每个活动区域必须有内容，保护区的合并限制不等同
于占用约束。模型自己决定叙述顺序、区域归属和区内顺序，允许行、列及混合路线，后续
求解不会重新分配模块、套用角色强排或执行专门的reading_review协议。

有意义模块少于原始区域数时，程序只选择本家族已合法化的普通capacity1区域合并，
每次一至两对不相交原始邻区，不递归、不拆区域、不合并hero/required/protected区；
最多一次整稿适配，没有合法变体则显式失败。容量范围随合并后的活动区域更新。
宽而矮的图文模块使用现有image-left/text-right确定性测量/编译能力。

配色沿用现有Logo/原始图色彩提取与对比色算法，标题沿用当前colorblock形式，前移
到实测之前且只选一次；模块/标题变化只更新同一形式的应用。最终字体与关键词强调
仍使用原有FontAgent，输入ABT改用Parser输出，不另加科学写作规则。

联合准备先测正文与图表，再尝试同家族共享边界的宽高调整，每次内容版本最多12个
尺寸候选、最多4个精测候选。模型的区域归属/区内顺序、容量、合并来源保持不变。
候选用实际title/visual/text负载和allocated/intrinsic高度反馈决定扩写或压缩；不设
统一字数上限，不用放大空容器满足90%。达到物理fit但有限预算后仍低于90%的模块
明确标underfilled，并交给最终Critic；无法fit则失败。90%是可观察目标，不能承诺每篇
论文都能在无注水条件下达成。可行基线后的尺寸/质量编辑不得增加测量空白。

预算：初写1、合并适配1、容量编辑3、实际预览质量编辑1；共用1次局部格式修复。
移除旧的每轮至多2模块限制，使用patch保留未修改模块。候选原始可视资源最多两次
恢复试探，受独立持久visual<=4总额约束。真实质量评审no-op仍消费机会；未解决溢出的
no-op失败。请求先计费再发送，响应先归档再校验；中断缺响应、身份/摘要/序号损坏、
重复计费记录不能自动重发。格式修复只能改变诊断字段，科学内容决策不买格式重试。

最终Critic保留七大维度的总权重；旧layout_family对visual_hierarchy的25%启发式
贡献转给最终实际PNG视觉评估（typography20% / visual80%），避免移除旧阅读/角色
规则后出现缺失维度或继续间接强排。其余物理、文件、字体、颜色、图像检查保留。

新版本拒绝旧run恢复及旧source/evidence缓存。新缓存只复制本版Parser论文材料、ABT
和独立资源，绑定抽取代码/提示词/配置/原生抽取环境；不导入任何旧样本正文。
未更改模型策略、温度、依赖版本；未启动真实模型海报或GPU生成。

最终冻结代码的完整CPU回归记录见下一节。前期修复中的红色/中断日志不作
最终验收；离线模型替身的成品/评分只验协议、物理渲染和保存，不能证明真实论文的科学、
写作或审美质量。用户原先21个改动/未跟踪路径和9131个历史文件的基线位于
/tmp/postergen-editorial-v23-baseline/manifest.json；本次提交不包含这些原有改动。


### v23 最终验收（2026-10-29）

最终冻结的完整CPU测试一次全绿：1308 passed、5 subtests passed、7 warnings，
1076.79秒（17分56秒）。252个源码/配置/提示词/测试/依赖/前端文件在整轮测试前后
字节一致。前期测试夹具错误及发现发布恢复遗漏后中断的全量日志均不算最终验收。
新增31项聚焦测试通过；最终可见文字输入补充随后由完整冻结全量覆盖。

新增端到端测试使用离线模型替身，但实际执行可编辑PPTX、PNG、Preflight、
LibreOffice PDF RenderFit、模板和正式保存。覆盖低分仍保存、内容Critic超时后无分数
仍保存，以及渲染完成、正式发布之前中断后无新模型调用恢复。新增默认Parser分支测试
保留native抽取入口、逐一调用模型标题作者/ABT/章节/图表分类；Marker模型初始化被
测试替身隔离，不在CPU回归中启动真实PDF模型。原生抽取本身由既有抽取回归覆盖。

发现并修复的发布恢复问题：旧final_output_snapshot只存诊断和成品字段，新就绪检查
还需要原始论文材料、PDF/Logo路径和编辑预算目录。新路由快照现在带齐这些字段；
中断恢复的真实成品发布用例已纳入最终全量。最终内容Critic收到完整原文和独立的
renderer_visible_text（实际标题/正文/标签/编号）；未显示的辅助标签不作为待核验断言。

前端npm run build、两个CLI帮助、uv lock --check --offline、工作区及暂存diff检查均
通过。config/agent_policy.yaml、pyproject.toml、uv.lock与任务前HEAD字节一致。
9131个历史数据/输出文件全部仍存在且字节一致；其余原有工作区改动保持原样。旧版
SourceVerifier/Planner保留为显式诊断兼容，没有恢复进默认新链路。

证据：/tmp/postergen-editorial-v23-full-cpu-final.log、
/tmp/postergen-editorial-v23-delivery-focused.log、
/tmp/postergen-editorial-v23-frontend-build.log、
/tmp/postergen-editorial-v23-cli-help-final.log、
/tmp/postergen-editorial-v23-classic-help-final.log、
/tmp/postergen-editorial-v23-lock-final.log、
/tmp/postergen-editorial-v23-frozen.json、
/tmp/postergen-editorial-v23-validation-final.json。

本次验收证明协议、恢复、布局和渲染/保存工程行为；没有新真实模型论文海报生成，
不宣称原文语义判断、正文写作、模块选择或审美已达到上游水平。必须用新版本新样本
单独检验真实效果；旧run及旧source/evidence缓存不能恢复或迁移为新样本。

本次原子本地提交：2e5d9d1（34个本任务文件），未推送。原有区域策略源码/测试及
无关HTML删除保持未提交状态，不纳入本任务提交。

## 2026-10-29：新路径的非改造功能兼容性对齐

用户明确接受新路径，要求除已批准的改造功能外，其余行为与上一版source-editorial
Rubrics一致。不进行文件路径合并。审计发现v23实现额外简化了配色、请求输出约束、
确定性评分和诊断字段；本次补齐，生成器v24，评价profile
academic_poster_editorial_v2 / system6.1.0。material/preparation契约保持原样。

| 范围 | 处理及证据 |
| --- | --- |
| CLI/WebUI、Runner、样本计数/家族选择/暂停恢复/发布 | 沿用现有入口和调度，本次不重写；离线真实成品集成含中断恢复 |
| 15家族、容量、合并、横向图文、原生PDF抽取 | 本次不改；原有区域策略工作区逐文件哈希保持 |
| 模型、温度/令牌/超时/重试策略 | 原策略配置不变；恢复先前严格JSON schema绑定，成功/异常后还原模型 |
| 配色/标题 | 仅阶段前移；恢复原Logo/关键figure/配置色回退、原取色提示词、style/emphasis、provenance和JSON文件；不将table当figure取色 |
| 利用率/空白/区域平衡/家族评分 | 直接复用原SectionFit/ColumnBalance/LayoutFamily评估器；仅新路由读取模型分配的独立planned_module_height，跳过明确取消的阅读/角色准入 |
| 评分权重 | 七大维度权重和维度内来源权重全部保持原配置，撤销v23的visual_hierarchy贡献重分配 |
| 内容/视觉质量 | 保留6项语义子指标、原模块内重复25/欠填6扣分、结构化位置/建议/禁止操作/positive_patterns；只替换已批准的原文真实性判断方式 |
| 字体、PPTX/PNG、Preflight、RenderFit、模板、全分数保存 | 继续共享原实现；字体/Renderer/RenderFit本次字节未变 |
| 诊断 | 恢复final_column_analysis、layout_family_analysis、section_fit_analysis、layout_performance_report、实测布局/样式JSON及Balancer/preview子项耗时 |

没有恢复已批准删除的SourceVerifier、source_document、必要含义/段落/数字准入、
强制阅读排序，也没有恢复每轮至多2模块的旧编辑限制。版号和评分profile递增是为了
隔离不同实现/评分的运行结果，不迁移旧样本或隐式续跑旧run。

新增10项兼容性用例：对同一布局使用新旧标记，核对共享评分的scores/issues/metadata；
核对权重矩阵、模块重复/欠填扣分、Logo取色失败到figure回退、配置默认色、非figure
取色限制、视觉位置校验/建议/优点，以及严格schema和异常后的模型还原。
与新链路用例合计41项通过，107.26秒，4条警告；原有成品测试另补诊断文件和
分项耗时断言。随后冻结253个文件运行完整CPU回归，最终证据另附。

测试开发中一次旧夹具使用错误配置键，以及一次在初步测试运行中继续编辑源码导致
其恢复身份校验拒绝，这些初步失败不作为最终验收。最终冻结阶段不再修改源码、提示
词、配置或测试；离线替身仍不等同于真实模型的写作/科学/审美验收。


### 非改造功能兼容性：最终验收

最终冻结完整CPU回归：1318 passed、5 subtests passed、7 warnings，1089.73秒
（18分09秒），退出0。253个源码/提示词/配置/测试/前端/依赖文件全程字节一致。
19个原有dirty/untracked路径保留，9131个历史文件仍存在且字节一致。模型策略及
依赖文件、FontAgent、Renderer、RenderFit与本轮前的2e5d9d1字节相同。
前端构建、两个CLI帮助、uv lock --check --offline、工作区和暂存diff检查通过。

最终证据：/tmp/postergen-parity-full-cpu-final.log、
/tmp/postergen-parity-contract-final.log、/tmp/postergen-parity-validation-final.json、
/tmp/postergen-parity-frozen.json、/tmp/postergen-parity-frontend.log、
/tmp/postergen-parity-cli.log、/tmp/postergen-parity-classic-cli.log、
/tmp/postergen-parity-lock.log。本次不启动真实模型/GPU生成，不把离线评分或文字替身
当作真实正文质量、科学准确率或美观程度验收。

新路径继续保留。兼容边界是原有功能和公开行为，允许的差异是用户批准的Parser材料、
模块联合写作/归属/阅读、实测准备、样式前移和最终原文判断，以及由这些改造导致的
内容/布局/评分结果变化；不承诺随机模型生成的文字、图片位置或总分逐次相同。

兼容性修复原子本地提交：8951a54，14个本任务文件，未推送。AGENTS.md与本报告已更新；原有布局策略修改/未跟踪文件和HTML删除不纳入提交。


## 2026-10-29：取消质量编辑，保留物理缺陷输出供Critic评判

用户明确要求移除质量编辑；将“溢出、越界、非法重叠导致生成失败”改为“冻结当前
结果并输出，交给Critic”。生成器v25；不更换新路径、不迁移历史结果、不修改模型
策略、15家族、容量/合并规则、正文写作输入、配色/标题、关键词字体、评分权重或
科学核验方式。prepare/material/storage及academic_poster_editorial_v2/system6.1.0不变。

| 修改点 | 修改前 | 修改后 |
| --- | --- | --- |
| 实测编辑额度 | 3次容量+1次质量；质量用整张草稿图复审 | 最多3次容量；无质量请求、草稿渲染、质量采纳/回滚；无有用补丁可提前结束 |
| 容量修复后溢出 | no-op仍溢出或3次耗尽，失败 | 最新正文和布局直接冻结，保留未解决缺陷 |
| Preflight | 失败阻断渲染 | 新策略下保留passed=false/issue_count/issues，不写入运行错误并继续 |
| RenderFit | 确认失败可调整标题并重新渲染，最终失败阻断 | 新策略下冻结后不改标题/不重渲染；保留真实failed/partial/unavailable报告供评分 |
| Critic输入 | 正文、原文、最终PNG/区域信息 | 同时收到实测fit、Preflight、RenderFit报告，明确正文目标可能被裁切或遮挡 |
| 确定性评分 | 已有越界、可见元素重叠和RenderFit扣分 | 沿用原逻辑，并覆盖未由其独立检测到的预检缺陷，避免错误给满分 |
| 冻结约束 | 正文、分配、资源、样式和请求身份 | 增加显式输出策略及实际编译坐标摘要，防止输出前偷偷挪动/缩小缺陷 |
| 输出/恢复 | 成品全分数无分组保存；失败评估无总分 | 继续沿用，允许存在物理缺陷的真实PPTX/PNG保存和发布恢复 |

容量扩写/压缩和12个压力驱动几何候选的原算法不变；不通过缩字、填充、裁小测量框
伪造90%利用率。预留视觉探测只在当时已经物理可行时运行，避免为未解决的溢出额外
增加图像。标题样式更新仍使用提前固定的方案。Critic只评判，不购买额外改写机会。

新准入只针对显式冻结的freeze_and_score_layout_v1；classic和旧source诊断入口
保持原来阻断及标题纠正行为。NaN/非正尺寸等不可绘制数据、内容/图像/坐标/预算身份
损坏、实际渲染或输出失败继续报错。Runner额外覆盖“已有几何失败标志，同时实际
Renderer报错”的反例，避免把运行故障误当作已获准的布局缺陷。

新增7项边界回归，另扩充2项真实可编辑PPTX/PNG集成：有缺陷的离线初稿在3次补丁后
仍溢出、越界和跨模块重叠，检查真实失败诊断、Critic扣分、文件发布、发布前中断后
恢复且无新增模型调用。该缺陷夹具固定原始几何以隔离输出准入，尺寸搜索由原有独立
测试覆盖。模型回复全部为OFFLINE替身，不构成真实模型写作、科学准确性或美感验收。
初步测试使用过于昂贵的长行夹具且错误期待Preflight报告跨模块重叠；已改为显式短行
并核对Critic的重叠问题。初步中断/失败日志不属于最终验收。

### 取消质量编辑：最终验收

最终冻结完整CPU回归1327 passed、5 subtests passed、7 warnings，1167.02秒
（19分27秒），退出0；最终定向59项通过，180.54秒，4条警告。254个冻结源码、配置、
提示词、测试、前端和依赖文件全程字节一致。19个原有dirty/untracked路径及9131个
历史文件完整保留、字节相同。模型/海报/评分配置、依赖、Parser、FontAgent、Renderer、
LayoutAgent及横向图文组件与本轮基线8951a54字节相同。前端构建、两个CLI帮助、
uv lock --check --offline、工作区和暂存diff检查全部通过。

独立重新打开两份缺陷成品PPTX，均包含Revision 3正文；PNG均为2048x1365且可解码。
实测fit及Preflight均保留passed=false，含区域/海报边界问题；真实RenderFit均为
failed、2项问题。最终布局完整性分项为27.5，成品仍被保存。该数值只说明缺陷进入了
现有评分组合；全部模型回复为OFFLINE夹具，不能据此推断真实论文科学性或美感。
最终集成还确认两种Critic调用都收到三次编辑后的最终正文及三份实际物理诊断。

证据：/tmp/postergen-freeze-full-cpu-final.log、-focused-final.log、-frozen.json、
-validation-final.json、-artifact-check.json、-frontend.log、-cli.log、-classic-cli.log、
-lock.log（同一prefix）。本轮原有工作区基线/tmp/postergen-finalize-baseline.json；
历史文件使用既有v23基线manifest的9131项，不新增或迁移旧样本。初步夹具失败和中断
均排除在最终验收之外。未启动真实模型/GPU生成。

本次仅提交15个任务文件；既有区域策略修改、3个既有未跟踪源码/测试及HTML删除均
不纳入提交。AGENTS.md和本报告已更新但按照本地文档策略不入Git。


取消质量编辑本地原子提交：ad16863，15个任务文件；未推送。


## 2026-10-29：Rubrics评分理想下限改为90%

按用户要求，当前editorial Rubrics评分区间从95–100%改为90–100%。通过当前路由的
critic config适配覆盖ideal_minimum，保留共享classic/旧source95%配置。ContentAdequacy
同步读取已测理想区间，缺少该元数据时使用当前配置，不再回退到硬编码95%。欠填及
优秀区间文案均按实际配置输出。其他空白、溢出、重叠、内容、科学评估标准未改变。

评价profile更新为academic_poster_editorial_v3 / system6.2.0；生成器v25及冻结/渲染/
保存政策不变，不启动任何正文扩写/压缩或额外模型请求，不重打历史样本分数。
新增边界用例验证89.99%仍欠填，90%/92%/94.99%/95%/100%理想且无欠填扣分，
100.6%不在理想区间；同时验证旧路由92%仍按原95%判断、配置不会被原地修改、
评分权重不变、缺少ideal_band时的回退和动态文案。

初始边界+共享SectionFit定向测试14项通过（6.24秒，2条警告）。2026-10-30完成验收：
冻结代码的完整CPU测试1337项和5个子测试通过，7条警告，1161.75秒（19分21秒）；
评分/生成/兼容性/SectionFit定向57项通过，4条警告，160.96秒。

最终SHA256逐文件核验：255个冻结源码/配置/提示/测试/前端/包文件没有变化；9131个
历史文件及19个原有修改/未跟踪路径均保留原始字节或删除状态。模型策略、共享critic/
poster配置、依赖、Parser、FontAgent、Renderer、LayoutAgent和模块组合均与任务前一致。
两个CLI help、离线依赖锁及工作区/暂存区diff检查通过。未启动真实模型/GPU生成，
不据此声称正文或科学/美学质量已验收。本次无需前端改动，未重复前端构建。

证据：/tmp/postergen-score90-full-cpu-final.log、-focused.log、-boundaries.log、
-frozen.json、-validation-final.json（同一前缀）；任务基线为
/tmp/postergen-score90-baseline.json。历史核验沿用v23基线的9131项history manifest。
仅提交本任务的README、两处评分源码及两个测试文件；原有布局策略修改、未跟踪
源码/测试及HTML删除不入本次提交。AGENTS.md与本报告已更新，按本地策略保持忽略。


90%评分修改本地原子提交：c1b2e68，5个任务文件，75行新增/6行删除；未推送。


## 2026-10-30 — Curator 最终选图与核心方法关键图

用户批准移除当前 Rubrics 的备用图试放，关键图优先核心方法/技术示意图，Curator 必须使用有效关键图，位置由模型结合十五种布局家族决定。实现版本 explore_samples_v26；preparation/material/scoring/storage 不变。

- 当前 MODULE/PATCH 删除 reserve_visual_ids，移除 restore_visuals、调用及 visual 预算；不改独立 classic 和显式旧 source 诊断路径。
- Curator 初稿及可选一次区域合并重写完成后，持久保存 editorial_visual_selection：关键图、各模块可见图表 ID 和局部顺序。后续容量调整禁止加图、删图、换图、转移图表或删除/改名持图模块；正文、空间权重、位置和纯文字模块结构仍可调整。实际尺寸及图左文右布局仍由既有测量处理。
- 有效非空关键图必须可见且唯一，不固定中栏/顶部；无适合方法图允许 null。遗漏关键图直接产生有限流程错误，不另开补图/选图调用，也不以格式修复重写正文。
- Parser 正常提示优先核心创新的方法总览、机制、架构和技术流程，区分背景和 baseline。新路径无效 ID 回退仅接受唯一方法角色图片，不将唯一结果图/表格强设为关键图；共享旧路径默认行为不变。模型正常返回的语义选择仍是模型判断，不新增科学语义硬核验。
- 最终内容 Critic 明确检查图表选取与解释对方法和实验/比较证据的覆盖；沿用已有评分字段、请求与最终评估流程，结果不触发再生成。
- 选图记录纳入 SAMPLE_KEYS、checkpoint、最终 snapshot；恢复/渲染均验证。新代码与提示身份拒绝旧运行恢复和旧 Parser 缓存，不修改历史结果。最多三次容量编辑、90–100% 理想区间和可绘制缺陷输出政策保持不变。

最终验收：全量 CPU 1373 项测试 +5 项子测试通过，7 条依赖警告，1160.33 秒；最终针对性105项通过，4条依赖警告，182.25秒。初轮针对性运行的5个失败来自离线响应替身缺少既有关键图配色取色响应；补齐替身后重新完成针对性和冻结全量绿测，初轮不算验收。全量测试期间342个冻结文件字节不变，原有19处修改/未跟踪路径和9131个历史文件均保持不变，git diff --check通过。

测试覆盖十五家族任意合法区域关键图、强制唯一可见、允许null和无图、无效ID不强选结果/表格、保留旧路径默认行为、禁止增删换图/转移/重排/改名持图模块、允许正文和几何/纯文字模块变化、合并重写完成前可重新分配图表、选图记录丢失拒绝调用、Parser请求重放以及真实可编辑PPTX/PNG导出。端到端测试通过三次容量编辑、物理缺陷保留、评估失败保存、发布中断恢复和再次恢复检查；使用离线模型响应，不是实际模型生成或论文科学/审美验收。

证据：/tmp/postergen-fixed-visual-full-cpu-final.log、-focused-final.log、-frozen.json、-validation-final.json、-history.json 和 -baseline.json（同前缀）。原有19处路径不纳入本次提交；仅12个任务文件提交，AGENTS和本报告继续本地忽略。无推送、无历史输出迁移、无真实模型/GPU运行。固定选图后不能靠删图化解溢出；沿用原有几何调整、最多三次正文编辑和freeze-and-score政策，如仍有物理缺陷则保留并评分。


本次本地原子提交：c16a750，12个任务文件，298行新增/43行删除；未推送。原有19处用户修改/未跟踪路径继续保留且未纳入提交。


## 2026-10-30 — 正文组织、容量执行与公式层级对齐

用户批准落实上一次只读审计提出的四处调整，直接修改现有 editorial Rubrics 路径。
原始 PosterGen 的章节/ABT 输入和联合写作已恢复，但 Curator 曾缺少具体的富层级示例；
本次补全其在当前字段中的表达，不宣称只靠提示词即可复现上游样例质量。

- Curator 增加主干/支撑、可选导航标签、真实步骤及混合结果/条件四类完整 entry 示例；
  示例来自不同假设任务并明确禁止作为论文事实复制。两三个主要信息单元是偏好，
  不等于正文条目上限；不强制每个模块分层或全海报统一样式。补充机制/动机、指标/
  比较条件、缩写解释、去重复标签和直接研究表述。Parser 及其缓存材料没有改变。
- 容量请求增加程序从真实测量生成的 ratio/percent/expand/keep/compress 建议。
  90–100% 模块通常保持原样，保留必要的联动编辑；词数建议不成为硬配额。提示要求
  重组/合并重复条目、维护主从关系，不只把每句截短；返回前核对 patch 与修改说明。
- editorial_history 记录程序计算的模块/条目增删、实际改写、标签/父子关系及其他
  字段变化，并附修改前后测量，覆盖最后一轮及实际 no-op。程序不解释自然语言 reason
  来推断已发生的操作，也不将说明当作真实改善或科学证明。
- 当前路由允许主步骤之间的支撑子条目，只有主步骤编号；含美元符号/行内数学的
  模块不再整体失去子级缩进。显示公式与可编辑正文使用共享块级测量计划，贯穿
  LayoutAgent、横向组合和 Renderer；前缀标签/关键词样式保留，公式继续使用原有
  解析和图片/源表达式 alt text。原文与带样式文本分别解析，保留字面星号和反斜线。
  独立 classic、显式旧 source 及空条目旧编号行为保留。FontAgent 文件不变。

没有增加模型请求/修复重试/质量改写阶段，没有新增科学字段或科学硬核验。
保留严格 JSON、现有模型策略、15家族/容量/合并及几何搜索、固定选图、最多三轮容量
修改、90–100%评分、最终 Critic 和冻结后有缺陷结果的保存。生成器升级 v27，
preparation/material/scoring/storage 标记不变；旧运行身份拒绝恢复，历史输出不改写。

正式定向验收：57项通过，2条既有依赖警告，82.73秒；包含33项新增反例、15家族
编译及两份真实可编辑PPTX/PDF/PNG检查。检查了实际PNG中主从缩进、行内下标、
关键词加粗和公式前缀；图片是离线合成测试，不是论文质量验收。两个CLI help、
uv lock --check --offline及diff检查通过。完整冻结CPU结果待本轮结束后补充。

早期预备测试有一个模拟请求夹具缺少真实持久日志，另有修改源码期间运行恢复测试
正确拒绝代码身份变化；均不作为验收结果。夹具改为完整离线模型响应，最终代码
冻结后重新执行定向与全量验证。证据前缀：/tmp/postergen-writing-；基线
baseline.json、冻结frozen.json、定向focused-acceptance.log、全量full-cpu-final.log。
已核对9131历史文件与19个任务前改动均无变化；最后交付前再次核对。
未启动真实模型或GPU生成，不据离线通过宣称正文、科学或审美质量已经验收。


最终冻结验收：完整CPU测试1406项 +5项子测试全部通过，7条既有依赖警告，
1220.59秒（20分20秒）；正式定向57项通过，2条警告，82.73秒。全量期间264个
冻结源码/配置/提示/测试/README/依赖文件保持字节不变；19个任务前修改/未跟踪
路径和9131个历史文件最终再次核对无差异，没有非任务路径改动。CLI和锁检查通过。

额外离线图左文右+显示公式组合核验通过：图片/正文同顶且不重叠，共享公式方案
高度5.086756英寸，实际文本盒和快速高度均为5.186756英寸；0模型调用。证据为
/tmp/postergen-writing-horizontal-check/validation.json。最终状态、完整测试摘要和
12个任务文件清单见/tmp/postergen-writing-validation-final.json。正式验收不包含
早期夹具失败或源码调整期间的身份拒绝。没有重跑论文或调用GPU/真实模型，不能
以CPU/合成图片结果替代真实正文效果、科学内容或审美验收。

本次本地原子提交：7d11a7b，12个任务文件，516行新增/10行删除；未推送。
AGENTS及本报告已维护但继续本地忽略；提交后工作区仅保留原有19处改动，字节/删除状态一致。


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



---

## 2026-11-02 独立项目迁出说明

本报告的既有内容从 PosterGen 工作区完整保留，现随独立项目 Rubrics_poster
在 `/projectone/projects/Rubrics_poster` 维护。既有记录中的源码版本、测试、旧样本
和绝对路径属于迁出前的历史证据；不代表新项目已运行相同的真实模型验证。
新项目未迁入原来的海报、run、缓存或模型日志，也不依赖原项目源码和环境。
迁出操作、行为保留范围、独立环境及验证结果见[独立迁出报告](PROJECT_EXTRACTION_20261102.md)。
