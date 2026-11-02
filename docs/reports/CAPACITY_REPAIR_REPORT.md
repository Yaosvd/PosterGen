# Capacity search and grounded text repair (2026-10-09)

## Exact restoration to bab9907 (2026-10-20)

ACTIVE BOUNDARY: the user abandoned all later changes and requested an exact
match to `bab9907fb0a6c4704c7ff5c93a17395d7d117ebf`. All tracked project paths,
bytes, modes and deletions match the target tree
`66c41451134387fe2455e6f9599d821ba6017373`. This restores Critic 4.3.6 / rubric v10,
paper_presentation_v3 and editorial_selection_v1. Neither ff6d2b7's required-visual
implementation nor 9488498's necessity-review implementation is retained, including
the uncommitted selection-review edits present before rollback. The target's HTML
is also restored. No selective later fixes are carried into the restored tree.

The former critical-visual/I13 implementation sections were moved intact to
[the inactive archive](archive/POST_BAB9907_EXPERIMENTS_REPORT.md). The retained
sections below describe bab9907 and earlier work. Historical commits, papers,
posters and Campaign/Batch/template/knowledge data are preserved. The loop was
already stopped, and development did not launch/resume a Batch or call models.
Budget/history records are not reset. No direct-edit or forced continuation of
failed/newer-policy Batches was performed.

Before restoration, the current two-path uncommitted diff and full local guide /
report were copied to `/tmp/postergen-rollback-bab9907-20261020-112240/`.
The public README is restored exactly from the target. Local ignored reports and
AGENTS intentionally document the rollback and are excluded from the tree check;
Git did not track historical copies of these local files at bab9907.

Verification: focused source/auxiliary/route/Campaign regressions **101 passed**,
two existing third-party warnings, **11.29 s**. The target's historical full
regression was 868 passed plus five subtests; that older result is retained below,
not claimed as a newly rerun full suite. The rollback itself is verified by full
Git tree and tracked-worktree equality, including modes and later-file removal.
Protected-file inventory covers 2,453 files under data/, output/ and
storage/critic_loop/: their complete path/size/mtime inventory is unchanged.
Final verification is saved at
`/tmp/postergen-rollback-bab9907-20261020-112240/verification.json`.

Atomic rollback commit: **`c83300f`**, `revert: restore exact bab9907 project tree`,
40 tracked files. Its Git tree is exactly bab9907's tree; tracked worktree bytes
and modes match too. The final Git worktree is clean. No new report/guide file is
staged, and no generated output or runtime data is committed.

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

### I12 regression and isolated export evidence

- Final full CPU regression on the frozen final source: **868 passed plus five
  subtests**, four existing dependency deprecation warnings, **584.96 s**.
  `git diff --check` passes. Full output is in
  `/tmp/postergen-auxiliary-full-final.log`; focused output is in
  `/tmp/postergen-auxiliary-focused-final.log`.

- Focused regression: **194 passed**, three existing dependency warnings,
  **100.30 s**. Cases cover 4/8, 5/8 and 6/8 setup hints across all twelve
  families, a future family, core methods, primary-label/foreign-ID refusal,
  original-root variants, stale unlocked flags, strict locks, real pregeometry
  failure scope, one-attempt stop/pause accounting, and preserved family/reading/
  exact retries. Tests exercise the actual runner without real model services.
  Known old v2 Batch presentation metadata upgrades on an authorized simulated
  resume without spending budget or changing frozen family pools.

- Read-only original I12 attempts: all **6 own boards x 12 families = 72** shared
  preparation checks pass. The AGS task module retains its own eight verified
  claim IDs and exact sentences, including when 5/8 hints say setup. Dataset
  claims still integrate into their appropriate method/evaluation owners. These
  checks are content preparation only, not a claim that all twelve geometries fit.

- Original attempt 1's non-symmetric two-column fit uses ONLY that attempt's
  saved board/state plus the same Campaign's immutable assets. It never reads
  the reused visible iteration output directory for another attempt's board,
  and never borrows the successful attempt 6's content. Original setup/definition
  hints are retained; no counterfactual hint change or new Curator call is needed.
  Full bounded CPU fitting/export took **159.74 s**, yielding 18 selected claims
  in six modules, worst zone fill **.958082**, largest empty rectangle **.038127**.
  This is a diagnostic selection from the original scientific bank, not retention
  of all 48 available claims or a new model-content/whole-poster quality judgment.
  No search, model or recovery budget was enlarged.

- Actual PPTX/PNG export and visual inspection pass exact Preflight and RenderFit:
  **12/12** editable title/body elements, no overflow/overlap/title-spacing issues.
  Outputs and replay input live under `/tmp/postergen-i12-structurefix/` only;
  `summary.json`, `fit_report.json`, `all_attempt_preparation.json` and
  `render_fit_report.json` record the conditions. The replay input uses current
  presentation v3 and refuses drift; the old attempt snapshots are untouched.
  No full model-backed Critic/admission was run, so physical success is not a
  claim of optimal aesthetics or scientific coverage.

- All **367 Campaign JSON files**, including attempt/commit/Batch records, retain
  their original inventory and SHA-256 hashes through preparation, fitting,
  rendering and audit. No live Batch/model/GPU run, no source-paper changes and
  no historical score/artifact/knowledge rewrite. The unrelated HTML deletion
  remains outside this task.

Atomic implementation commit: **`bab9907`**, `fix(layout): preserve core functions
and scope structure failures`, 10 tracked source/config/prompt/test/README files.
This report and AGENTS remain local/ignored. No generated input/output, runtime
record or unrelated HTML deletion is staged.

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

### Expression validation and own-input export evidence

Atomic implementation commit: `604b863` — `feat(editorial): refine shared poster
prose and emphasis` (25 tracked files). `AGENTS.md` and this existing report are
updated locally and intentionally excluded from Git. Nothing was pushed.

- Final full CPU regression, on the final frozen source: **815 passed plus five
  subtests**, four existing dependency warnings, **575.62 s**. `git diff --check`
  and staged diff checks pass. All 25 task-owned tracked files are staged explicitly;
  local Markdown, generated data and the unrelated HTML deletion are excluded.

- Focused integration regression: 154 passed, two existing dependency warnings,
  200.51 s. After the final flat-body and v3-upgrade review, the final protection
  suite passed 83 tests, two warnings, 23.39 s. New expression tests cover exact
  local cues, malformed metadata, no-label modes, genuine-step numbering,
  same-root cue invalidation, cache/style identity, actual PPTX bold runs, four
  palette hues, strict route locks, unsafe-panel suppression, actual colored runs,
  flat bodies, and failed/successful/reused style variants. Existing compaction
  still rejects length growth. No real model was called by these tests.

- Read-only joint-color audit of all ten historical root-output palettes:
  10/10 original light backgrounds are retained, two accent inks are darkened,
  minimum panel/canvas ratio is 1.1631 and minimum accent/panel contrast is 4.5083.
  Results: `/tmp/postergen-expression-palette-audit.json`. This tests palette
  resolution only, not whole-poster quality.

- Own-I10 diagnostic: `/tmp/postergen-expression-i10/`. It starts from I10's OWN
  historical input board/foundation and uses only that same I10 diagnostic's saved
  geometry. A finite list of phrases from its own verified text exercises optional
  cues; those manually supplied display hints are NOT a new Curator model result.
  Fixed-geometry fitting took 64.36 s and retained 22 claims in five modules, with
  worst-zone fill .886338, largest empty rectangle .039475 and maximum terminal
  gap 3.1689 in. This is a fresh bounded diagnostic selection, not an assertion
  that every metric beats the earlier six-module candidate. Scientific necessity
  decisions on a new model-generated board were not tested here.

- The actual I10 PPTX/PNG was exported and visually inspected. Preflight passes;
  RenderFit matches 10/10 editable title/body elements with no overflow, overlap
  or title-spacing failures. The central panel is `#efe6e6` (previously nearly
  white `#fbf9f9`), with module accent `#117272`. Actual colored-run contrast on
  the panel is 4.663; panel/canvas ratio is 1.2258. ColorQuality passes with no
  issues. The deterministic family component passes. SectionFit passes physical
  gates but scores 73.49 and still reports six major space/allocation findings
  plus one warning; this is NOT a whole-poster Critic score or quality admission.
  Old 'The authors' wording remains because this replay did not run model repair.

- Multi-paper rendering fixtures: `/tmp/postergen-expression-multibody/` contains
  isolated body-only PPTX/PNG fixtures from the historical DP-CutMix and Fourier
  papers, each using its own original words/palette. New extractive cues include
  'Gaussian noise' and 'Fourier layers'. They retain the old prose's existing
  labels and assertions without rechecking their scientific validity. Fixture
  paragraph IDs are rendering identifiers, NOT newly verified scientific claims.
  Both match 2/2 title/body elements without render issues; blue/brown panel ratios
  are 1.2083/1.1944. These sparse body fixtures test wrapping/color/rendering only,
  not full-layout balance, science, selection or new model writing quality.
  All 29/30 original files in those two output directories retain their hashes.

- All 281 JSON files/inventory in the own-I10 Campaign remain unchanged after
  fitting/export/audit. No Campaign, Batch, template or scientific foundation is
  rewritten. No live/model-backed/GPU run was launched or advanced. This work does
  not certify future model language quality or every paper/family's aesthetics.

- A reconstructable fitted-board diagnostic input is separately saved under
  `/tmp/postergen-expression-i10/replay_input/layout_input_snapshot.json`; it is
  created after the diagnostic and is not a replacement for its original fit input
  or any historical attempt snapshot. Digest
  `25a066990048eebee9923a04c49f62e22b59fd140afe6d993ca5946b6ced3bcf` validates with
  current editorial/body/emphasis versions and no model-client fields.

## Source-aware selection implementation (2026-10-19)

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

### Final verification

- Final focused regression: **190 passed**, two existing dependency warnings,
  183.56 s. New source/selection cases cover all twelve families, explicit future
  registration, routine data with visuals, ambiguous visual-owner refusal,
  required-context closure, variants/exclusions, split-source refill, unknown
  excerpts, and source-order previews. The independent full suite passed
  **778 tests plus five subtests**, four existing dependency warnings, 556.79 s.
  `git diff --check` passed. An additional model-stub source-search audit confirmed
  that an omitted paragraph is absent while another verbatim useful paragraph
  remains retrievable; no paid model was involved.

### Own-I10 diagnostics (read-only, not live Batch outcomes)

Every case starts from I10's own original pre-fit board and verified foundation.
No other iteration's content board is used. The two constrained cases reuse only
this same I10 diagnostic's geometry, with explicit test editorial contracts; they
are not generated Curator decisions and must not be described as automatic model
results. Original Campaign JSON inventory and SHA-256 hashes (281 files) remain
unchanged after fitting, export and auditing. Outputs live only under `/tmp`.

| Case | Purpose | Claims / modules | Worst zone fill | Largest empty rectangle | Max terminal gap |
| --- | --- | --- | --- | --- | --- |
| Previous `43e017a` own-I10 audit | Historical diagnostic reference | 17 / 6 | .654001 | .164948 | about 9.65 in |
| Current original-board fit | Full normal bounded family search | 23 / 6 | .912641 | .048494 | 2.4356 in |
| Required-condition exercise | Four explicit required roots, fixed own geometry | 25 / 6 | .912641 | .073011 | 2.4356 in |
| Editorial-contract exercise | Six required roots, three explicit secondary omissions | 25 / 6 | .912641 | .041460 | 2.4356 in |

The normal fit took 708.41 s with the configured eight exact search seats;
shared-x refinement checked two infeasible candidates and adopted neither.
One exact editorial presentation was adopted. Geometry trials, the model budgets
and repair gates were not enlarged. The richer source/selection checks can cost
more CPU time than the old fit; this is not a runtime speedup claim.

The four-root exercise required `pc_0014`, `pc_0018`, `pc_0032` and the sampling /
four-repeat condition `pc_0037`; all remain visible. It took 54.69 s. The six-root
exercise additionally required the parcel/location context `pc_0021` and useful
ablation interpretation `pc_0041`, and explicitly omitted secondary implication
entries `pc_0043`, `pc_0046`, `pc_0049`; all six requirements survive and all three
omissions stay absent. This took 56.77 s. Both are deterministic API exercises,
not claims that the new Curator model has made exactly those choices.

In the editorial exercise data/sample/location are integrated into baseline
evaluation, representation learning stays with the method, and no Dataset module
stands alone. Ablation retains three verified entries plus its original table;
implications retain four useful entries. Background and formal task definition
remain distinct three-entry modules: combining them is allowed when coherent,
not mandatory. Physical reading is left background/task, center method/results,
right ablation/implications. No inversion is reported. Original claim sentences,
images, image proportions, font sizes and theme source remain unchanged.

Both the normal and editorial exercises exported editable PPTX and PNG. Final
FontAgent preflight and RenderFit passed with **12/12 editable body/title matches**,
no overflow, collisions or title-spacing failures. Both PNGs were inspected.
The deterministic LayoutFamily hard gate and physical SectionFit pass. This is
**not complete visual acceptance**: normal-board SectionFit is 42.92 with nine
major allocation/underfill/bottom-space findings and a one-entry ablation module;
the editorial exercise scores 74.26 with eight such findings. These component
scores are not poster totals or a claim of meeting the 78-point admission gate.
No semantic/visual model Critic, poster acceptance, template promotion or live
Batch evaluation was run. The inherited `The authors` sentence remains because
frozen old scientific wording was not rewritten or repaired through a paid call.

Artifacts:

- `/tmp/postergen-selection-i10-final/`: original-board fit, rendered artifacts,
  structural/space reports and current-policy digest-bound replay input. Replay
  identity validates; the saved overlay correctly maps `ev_0060` back to
  Experiments without changing its original Algorithm source record.
- `/tmp/postergen-selection-i10-required/`: four-root contract fit and audits;
  this middle case was not exported.
- `/tmp/postergen-selection-i10-editorial/`: six-root/three-omission exercise,
  exported PNG/PPTX and deterministic checks.
- Logs: `/tmp/postergen-selection-focused-final.log`,
  `/tmp/postergen-selection-full-final.log`, and the corresponding I10 logs.

### Remaining limits

Necessary-versus-secondary judgments belong to the existing Planner/Curator;
this task tests their sanitized ID contract but does not empirically certify new
model choices across papers. Read-only Markdown context cannot recover missing
PDF structure or invent page locations; unresolved excerpts stay unknown. Source
paragraph masking is conservative and may hide useful adjacent source detail.
Finite search can still leave thin main findings or visible whitespace, and
geometry/render success is never aesthetic or scientific acceptance. New genuine
scientific extraction requires a compatible new foundation/Campaign. Existing
scientific verification, same-attempt rollback, Critic weights/admission and all
finite budgets remain in force. No live Batch was created/resumed/advanced and
nothing was pushed. Local Markdown remains ignored; the unrelated HTML deletion
is preserved outside the task commit.

Atomic task commit: `70b4e26` (30 tracked source/config/prompt/test/README
files). Reports and this local guide intentionally stay outside the Git index.


## Shared paper structure, focus and natural reading after I10 (2026-10-16)

This implements the user's approved follow-up plan across the existing twelve
layout families and future registered extensions. It preserves useful information,
scientific verification and the established measured overflow/space/title-spacing
protections. No live Batch is launched or advanced by development.

### Observed gap and correction

I10 used `central_hero_side_rails`: background/problem occupied the central hero,
while method, a one-sentence Dataset module and baseline results occupied the
left rail. The old anchor-first interpretation treated the center as a separate
entry and therefore reported no inversion. This was an interpretation gap,
not evidence that geometric overlap checks had failed.

Dataset's source module contained eleven verified claims; the visible subset
kept only `pc_0021`. Free restorations failed composite ownership/content checks,
and finite model actions were spent on other modules. The fit engine only read
`layout_revision_constraints` in Improve, even though completion also creates
those pins and retention lists in Explore. The correction applies internal
constraints in every mode; repair diagnostics now expose the separate reasons.
Thin/reduced modules keep model priority after unsuccessful free additions.

### Shared implementation and boundaries

- `paper_presentation_v1` prepares bounded auxiliary grouping before content
  selection, preserving every original verified sentence, root, asset and source
  identity. Routine data/setup/metric descriptions join a compatible method or
  evaluation owner. No title blacklist or sentence-count threshold is used.
  An explicitly grounded dataset contribution or central research subject can
  stay independent; merely mentioning a dataset in a new method cannot certify
  that exception. Existing immutable foundations are not rewritten.
- Final subset/refill checks detect standalone auxiliary modules and merged
  modules reduced to only supporting facts. A prominent region must contain
  important paper roots; method/results/interpretation companions may share a
  wide region, while background cannot become the focus merely because it is
  long. Early filtering, bounded exact reassignment and final structure audit
  share the contract, without family-ID branches.
- An intermediate own-input I10 counterfactual passed geometry/render matching
  but omitted every root from the merged data/setup source. It is a diagnostic,
  not the final result. The added context-group guard retains a usable core
  root from each merged source (an original root if no core is annotated).
  Verified same-root variants remain valid; explicit exclusions/disabled roots
  take precedence. Compact core subsets include this closure inside the existing
  nonprefix-seat budget. No minimum sentence count or invented scientific
  dependency is imposed. A merged module cannot solve fragmentation by deleting
  all of its useful supporting information.
- `FamilyContract` v2 separates focus from exceptional reading entry. Ordinary
  center/spine/mosaic emphasis follows physical traversal. Only registered
  result-first contracts may lead with findings, with a measured, idempotent
  "Key finding" cue. Comparison/matrix branches retain independent sequences.
  Extensions inherit validation and conservative natural traversal; automatic
  grouping requires explicit opt-in. Classic remains three unsplit/unspanned
  regions; grouping content does not split or span geometry.
- `family_reading_v3` prefers the main body source order derived from original
  evidence/source provenance; abstract previews do not move findings earlier.
  Roles remain a legacy fallback when body order is unavailable. Unknown sources
  keep their slots rather than becoming a fabricated final stage. Reordered IDs
  cannot conceal actual physical inversions.
- Unresolved unlocked structure is a known fit failure, with ordinary bounded
  retry semantics and no content-model call for a structure-only problem.
  Final preflight and LayoutFamily Critic hard gates prevent high total scores
  overriding it. Strict Validate/fallback keep their topology/content locks and
  expose findings; fallback remains a no-change recovery without publication.
- Every content addition/compaction retains the existing verifier, dependencies,
  exclusions, visible roots/assets and finite model budgets. Exact local/global
  whitespace, title/body spacing, typography, image proportions, final render
  audit and same-attempt rollback remain mandatory. Completion never borrows
  another iteration's board. No guarantee of perfect aesthetics or universally
  feasible family search is implied, especially for ambiguous legacy hints.

Policy identities: `grounded_family_design_v2`, `paper_presentation_v1`,
`poster_editorial_v2`, `family_reading_v3`, composition scoring v5. Critic
**4.3.3 / academic_poster_multifamily_v7_structure** uses narrative evaluator
1.3.0 and layout-family evaluator 1.1.0. Weights, 78-point threshold and scientific
gates stay unchanged. Known legacy reading/editorial versions upgrade explicitly
on resume without changing frozen family pools, budgets or historical commits.
Replay snapshots bind presentation identity and derived source order and reject
drift. No real Campaign resume/migration is performed by this task.

### Verification

Final frozen-source full suite: **749 passed plus 5 subtests**, four existing
dependency warnings, in **408.07 seconds**. The final context/editing/completion
subset passed 115 tests; source/reading coverage passed 71. Coverage includes
all twelve preparation contracts and an actually registered extension, true
dataset contributions, routine auxiliary grouping, retained context through
same-root variants/exclusions, source-body precedence over abstract/repeated
introduction previews, unknown-source slot preservation, cross-mode pins,
actual entry-title styling, Critic gates, legacy resume isolation and existing
geometry/spacing/rollback tests. `git diff --check` passes.

The final I10 counterfactual uses **only I10's own original fit snapshot and the
same Campaign's immutable foundation metadata/assets**, with its own palette,
keywords and original family/seed. No board from another iteration or family
is substituted. Full normal bounded fitting found a feasible candidate in
324.08 seconds; source module 4 is grouped into Methods, with **pc_0021** retained
alongside method root pc_0015. The final six visible modules contain 17 verified
claims and the same three visuals. Actual physical traversal is background ->
AGS definition -> Methods -> baseline results -> ablation -> implications;
the central region contains the important baseline results. Mirrored zone IDs
are interpreted by coordinates, not their left/right names.

Exact preflight and final FontAgent typography pass. Exported PNG/PPTX pass
RenderFit **12/12 editable titles/body textboxes**, with no overflow/collision/
title-spacing issues. Preview was also visually inspected. Temporary diagnostic
files are under `/tmp/postergen-structure-i10-final/`; they are not archived,
scored accepted posters or Campaign commits. The initial intermediate output
under `/tmp/postergen-structure-i10/` omitted data context and is superseded.

**Material limit:** the final model-free fit leaves a conspicuous central bottom
gap: worst zone utilization **0.654001**, largest empty rectangle **0.164948** of
the body, with a maximum terminal gap of about **9.65 inches**. It is not an
aesthetic acceptance. Running the existing same-input free completion attempts
eight original-root additions and adopts none because exact fitting fails;
the last feasible board is preserved, zero model rounds are charged, and four
modules remain flagged. A normal model-enabled iteration still has the bounded
grounded-addition/compaction and Critic paths; this offline check does not prove
that those calls will eliminate the gap. No fill threshold/spacing/overflow gate
is relaxed, no filler is added, and no whole-poster quality guarantee is claimed.
Final model-free LayoutFamily checks pass; the unchanged SectionFit evaluator
still emits major underfill/bottom-gap findings and scores layout/balance 53.94.
Its physical hard gate passing is not aesthetic acceptance. No overall model
Critic score or archive admission is inferred from these diagnostic evaluators.

All **281** real Campaign JSON files retain identical SHA-256 hashes and inventory
after fitting, completion and export checks. No live model/GPU generation, Batch
launch/resume, historical artifact rewrite, template publication or push occurs.
The unrelated deletion of `excavator_loading.html` remains outside this task.
Atomic task commit: **`43e017a`** (`fix(layout): enforce shared paper structure
and natural reading`), 25 source/config/prompt/test/README files. Post-commit
verification retains only the unrelated user-owned HTML deletion; reports and
AGENTS remain local/ignored and outside the commit as required.

## Shared poster editing after I8/I9 (2026-10-16)

This is the user-approved editorial optimization, including the clarification
that fast scanning must preserve important information and clear explanation.
It does not restore the withdrawn module/source semantic association feature.

### Scope and implementation

- `poster_editorial_v1` is shared by every loop family and future registered
  extension. Curator prepares short complete titles, discourse hints and
  labeled main/supporting entries before layout selection. Scientific body
  sentences remain materialized from verified IDs. Settings-first and explicit
  takeaway-first styles are supported; unknown relationships stay flat.
- Local required contexts cannot disappear during compact selection, including
  same-root variants and mutual dependencies. Unknown/foreign IDs are ignored;
  cyclic dependencies remain all-or-none groups rather than being erased.
  Omitted loop claims follow original narrative source membership instead of
  the shortest unrelated module. No new semantic model admission stage exists.
- Newly prepared presentations retain a verified root from each available
  important Planner phase, with core-root preferences and same-root wording
  freedom. This closes an observed intermediate I8 replay that fit six modules
  but omitted the implications phase. Compact late-core options and their
  prerequisite closure use existing bounded subset seats. This is current-plan
  information retention, not source/module semantic association or a fixed
  module count. Final counterfactuals below distinguish it from the intermediate
  result; an infeasible retained phase must fail fitting rather than vanish.
- At most two exact editorial trials per fit may refill useful original roots
  and merge one adjacent thin same-role pair in the same zone. Source/merged IDs
  persist; no visible root/visual or occupied zone is removed. All twelve family
  contracts explicitly permit content grouping; extensions default to preserving
  grouping until opted in. Classic geometry still has three fixed regions and
  forbids split/span. Strict Validate/exact fallback retain locks, and Improve
  retains its revision contract, importance and owners.
- Display labels and actual 0.30-inch supporting indents participate in the
  same exact measurement/render path. An initial all-bold reserve rejected a
  dense I8 trial; it was replaced by per-word mixed-face wrapping with cached
  regular/bold fonts/glyphs, a width reserve and final rendered-glyph checks.
  Dense historical zones may keep flat exact sentences if labels do not fit.
- One visible core/hero module receives light-theme emphasis only when body and
  highlighted text meet configured contrast. A bounded lighter tint can replace
  the unsafe original light background; color checks inspect the actual
  rendered choice. No arbitrary model colors or type-size changes are accepted.
- Legacy author-review wording can use one existing quality round of at most
  two verified compact actions, counted in existing global/family ledgers before
  calls. Failed verification, disabled optimization, budgets, fit/space regression
  retain the previous content. Base scientific data stays immutable.
- Pure fitting returns an ordinary three-item tuple with a runtime-only rollback
  attachment, never writes state or scientific prose into fit reports. Only
  adopted results install the same-attempt rollback. Board/banks/selection,
  source-visual ownership, metadata, layout and reports restore together if final
  preflight/render fails or text coverage is inconclusive. The baseline must
  still pass normal rendering; it is not proof of universal visual quality.
- Batch upgrades record editorial policy separately from reading/design identity
  and preserve frozen pools/budgets/history. Replay inputs include editorial
  identity and palette, refuse drift and exclude models/secrets. Critic 4.3.2
  uses `academic_poster_multifamily_v6_editorial`, narrative evaluator 1.2.0;
  weights, 78-point admission and scientific verification are unchanged. The
  shorter distinct rubric respects existing 48-character snapshot naming.
  Old best/promising scores are not relabeled, so pure Improve may lack a base.

### Verification

The final focused design/content/family search suite passed **99 tests** in
89.21 s. The final editing suite, including the actual Curator entry in both
routes, passed **38 tests** in 15.61 s. These cover all twelve registrations,
an extension, local prerequisites/cycles/same-root replacements, important-phase
retention, late core selection, source-preserving grouping, exact science,
mixed-face cached measurement, real DrawingML indentation, accessible background,
standalone/locked modes, rollback isolation and the adversarial same-ID foreign
board case. A pre-render complete regression passed **705 tests plus five
subtests** in **634.23 s**, with four existing dependency deprecation warnings.
The final rendered-title correction and locked-measurement checks below receive
a fresh full regression; only its final result is the handoff baseline. `git
diff --check` also passed.

No live/model-backed Batch is started by development. Historical I8/I9 inputs
are used separately and original files are never overwritten; temporary
counterfactuals are not Campaign posters, templates or quality admissions.
The diagnostic explicitly reapplies current Curator presentation preparation to
each own historical input; it is not a policy-compatible benchmark replay of an
old snapshot. The official replay validator correctly refuses policy drift.

I8's prepared fit completed in **338.21 s**, passed exact preflight and retained
all four available important research phases. Editorial refinement grouped the
two adjacent same-role method modules into one (7 -> 6 modules), retaining all
19 pre-edit visible claims and restoring two more (21 total). Titles are 1-4
words, with complete scientific names retained. Known reading conflicts are zero.
The actual PPTX/PNG passed final styled preflight and RenderFit **12/12**, with
no issues; the retained result module has the accessible light-theme background.

The I8 preview also exposes a material limit: the full *fresh* prepared search
leaves an 8.13-inch right terminal gap (largest empty rectangle fraction 0.099146),
versus 1.5073 inches / 0.037732 in the old historical composition. The adopted
editorial trial itself passed all strict per-zone/global nonregression checks
against its own pre-edit candidate. A fresh selection with changed presentation
and information constraints is not the old layout's safe editing baseline.
The normal free completion audit tried eight original-verified additions in
88.45 s, adopted none and retained the same candidate. Required placement/content
guards rejected unsafe fits; no original verified addition was available for the
already fully represented implications module. All six modules remain reported
as unresolved under unused-zone-capacity diagnostics; no model
round was allowed in this CPU audit. Model-backed useful evidence additions or a
later different bounded composition may improve this case, but were not tested.
Neither geometry preflight nor
perfect text coverage certifies overall aesthetic quality. Do not present this
counterfactual as an accepted or universally improved poster.

I9's own prepared timeline fit completed in **845.65 s**, passed exact preflight
and retained all four available important phases, with zero known reading
conflicts. It retained seven modules and 23 claims (historical visible count 22);
its ungrouped editorial trial preserved all 23 and emphasized the result module.
Both counterfactuals have at least two claims per visible module, without a forced
minimum sentence count. I9's maximum terminal gap is 4.1317 inches and largest
empty rectangle fraction 0.075720, versus historical 2.2028 / 0.051226; the same
fresh-composition limitation applies. The final I8/I9 prepared search and I8
render/free completion each verified **all 260 original Campaign JSON hashes and
the JSON inventory unchanged**. CPU search times include concurrent validation
work and are diagnostic costs, not a production latency benchmark.

An earlier protected-visible-content experiment on the old I8/I9 boards
rejected dense/space-regressing edits and retained their old compositions. This
demonstrates the intended fallback: post-fit editing does not weaken whitespace
guards simply to force short titles, grouping or a new background. The original
all-bold measurement failure was corrected before final validation. New Curator
presentation is budgeted earlier; old visible layouts can legitimately retain
their baseline. No model-backed ClaimWriter/Curator/wording repair or semantic
Critic has been run, so direct-voice rewriting and scientific-quality admission
are covered by deterministic/mocked boundary tests rather than a new paid run.
ClaimWriter's new prose instructions apply when a new scientific foundation is
built. Resuming an existing Campaign does not regenerate its immutable claims;
structured display still applies, while any scientific rewording must be a
verified optimizer alternative within the existing budgets.

Final visual inspection found a stale-title boundary: after restoring method
detail to a dataset-only subset, mixed-case words from the saved full source
title were incorrectly rejected by the extractive vocabulary filter. All title
vocabulary is now normalized consistently; the I9 module broadens from `Dataset`
to `Multi-Modal Data & Setup`. The same review protects strict Validate/exact
fallback titles and internal order during both fast option measurement and exact
measurement, including `allow_changes=False`. Regression cases cover these
locks, mixed-case source-title restoration and uppercase names in verified body
text. No scientific text is rewritten to achieve the correction. The final
editing suite passes **45 tests in 16.23 s**.

After that narrow correction, both own visible candidates were revalidated with
their own current content and fixed geometry: all module claim sets and zones
remained identical, exact compile/preflight passed, and I9's second-stage terminal
gap decreased from 2.1111 to 1.0444 inches. This is a final fixed-candidate
revalidation, not a second full fresh family search. The 338.21/845.65-second
fresh-search figures above precede that last correction.

Final actual PPTX/PNG exports under `/tmp/postergen-editorial-final/` passed
styled preflight and complete rendered-text matching: **I8 12/12, I9 14/14**,
both `passed` with empty issue lists. Visual inspection confirmed the corrected
broader I9 heading fits its reserved space, the result emphasis is visible, and
both retain coherent physical reading order. The noted fresh-search whitespace
limits remain; the render audit is not an aesthetic acceptance score. Both final
exports again verified the original **260 JSON hashes and inventory unchanged**.
The I9 no-model free-completion diagnostic (before the last title correction)
also attempted eight original additions in 225.29 s, adopted none and retained
the safe current candidate under content/ownership guards; seven capacity hints
remained unresolved with a zero-model-round limit. These temporary diagnostics
are not a live Campaign attempt, and generated files are excluded from Git.

The **final frozen-source full regression passed 712 tests plus five subtests**
in **637.61 s**, with four existing dependency deprecation warnings. The final
45-case editing suite and both final rendered exports above are on that same
source. Final `git diff --check` and staged patch checks pass. README documents
the public behavior and the local ignored AGENTS guide records the current
architecture/validation baseline. No live Batch, model call, Campaign resume,
template publication or historical rewrite was performed. The unrelated
user-owned deletion of `excavator_loading.html` is excluded from the task commit.

Atomic task commit: **`accaeb0`**, `feat(layout): add grounded poster editorial
optimization` (**30 source/config/prompt/test/README files**, 1,444 insertions,
56 deletions). Reports and AGENTS remain local/ignored under repository policy;
generated previews, diagnostic logs and Campaign data are not committed.

## Shared reading-flow correction after Batch 3 (2026-10-15/16)

Implemented in response to the user's request to fix the reading problems found
in Batch 3's committed I6 and I7. This section supersedes older historical reading
descriptions below; the editorial section above owns the current Critic identity.
Module completion and its protections
remain active. No withdrawn source/module-association feature is restored.

### Observed causes and correction

- I6's actual bands were problem definition, performance, ablation, setup,
  method. The solver reported one known conflict but its two bounded pair swaps
  did not fix it. Reading policy `family_reading_v2` retains a dedicated ordered
  beam path, then searches complete order-preserving partitions of the currently
  visible modules before refill consumes their room, and again after refill.
  Each phase has at most 128 states, at most 256 per exact candidate. This can
  express multi-zone cycles and variable per-zone module counts without changing
  geometry or deleting/rewriting any visible content.
- Search considers classified narrative roles early, so larger result modules
  do not consume the earliest body slots before context/method can be placed.
  Entirely unknown-role inputs keep the original priority processing. Regression
  checking caught a compact-three-column loss when unknown slots were also
  preserved in the search-processing queue; that trial was removed. Unknown
  *physical* slots remain protected by the shared per-zone sorting rule.
- I7 used anchor-first: the top implications summary was a legitimate entry
  point, but the left column read background then ablation before the middle
  problem/setup and right method/performance. The old conflict helper skipped
  anchor-first entirely. The shared policy now separates hero sequences from
  the supporting body and checks that body in physical zone/stack order.
  Comparison branches and matrix cells remain independent; their internal
  stacks are checked without imposing cross-peer chronology. Unknown roles
  cannot manufacture a final stage or hide a reversal between known roles.
- Critic omitted `insight` and `implications` from its separate role table and
  assigned both rank 5. Solver and Critic now use the same normalized role map,
  including role aliases/discussion, and the same family-aware reading scopes.
  Reports distinguish actual traversal from the declared metadata list. The
  semantic evaluator receives the same scopes and explicit hero/peer guidance.

### Protected boundaries and failure semantics

Reassignment preserves all visible modules, per-module claim/visual content,
topology/coordinates, hero ownership, pins and conditional role constraints.
Exact height limits, compile/preflight, final typography/render audit and all
existing completion/local/global whitespace guards remain. Restore/balance
trials cannot add a known order regression. An automatic unlocked exact candidate
that still reverses known roles is not rendered: `READING_ORDER_UNRESOLVED`,
`reading_flow`, `reading_assignment_limit` and bounded diagnostics describe the
failed attempt. Ordinary family retries apply without Batch iteration or Critic;
content compaction is not invoked for a pure reading failure. No impossibility
claim or guarantee of universal feasibility is made.

Candidate selection also applies the existing whole-poster whitespace envelope
against the highest-scoring exact fit before core preferences/diversity. This
prevents an ordered but much emptier result winning merely for one extra core
root. `selection_whitespace_guard` records its reference/candidate counts and
scoring identity is `multifamily_composition_v4`. Existing 0.01 area/fraction and
0.35-inch comparison tolerances are reused; completion retains its stricter
0.005/0.05 cumulative guard. Search and model budgets are not expanded.

Strict Validate and exact-parent fallback retain saved topology and do not
perform automatic reading reassignment. Explicit Improve reading requests retain
their existing execution contract; an infeasible/pinned request cannot claim
success through metadata alone. The ordinary Critic continues to assess those
locked/requested layouts' actual order. New families receive the same behavior
through their registered reading contract; a neutral grammar remains neutral.
Classic still has exactly three regions, no splits/spans. The independent
standalone Balancer/layout route receives no geometry/solver changes; shared
Critic narrative interpretation uses the new role map for every evaluation.

### Versions and persistence

Critic is 4.3.1, InformationNarrative 1.1.0, with distinct rubric
`academic_poster_multifamily_v5_reading_v2`. Seven dimension weights, the 78-point
gate, structural-template rubric and scientific verification are unchanged.
The new identity prevents old best/promising scores and feedback being relabeled;
a pure Improve run may lack a compatible new-rubric parent. Historical artifacts
and scores are retained; no automatic rebase is performed.

`grounded_family_design_v2` remains active with an additional frozen
`design_optimization.reading_flow` identity and explicit legacy resume-upgrade
record. Family pools, repair budgets and Batch targets are preserved. Saved
attempt input includes reading-policy identity and ordinary replay refuses
policy drift. The diagnostic I6/I7 counterfactual below deliberately uses their
old scientific inputs with the new policy, rather than claiming old-policy
equivalence. No actual Campaign/Batch is resumed by development.

### Validation

Focused CPU reading/design/Critic/capacity regression: **99 passed in 66.57 s**.
Final focused regression after compact-search and whitespace review:
**103 passed**, two existing dependency warnings, in **72.77 s**.
Tests include physical-vs-metadata disagreement, unknown roles,
role aliases, hero/body separation, independent peer branches, mirrored IDs,
bounded partitions, pins, conditional roles, locked recovery, all twelve family
compile/preflight and extension-contract behavior. No real-model run is used.
The added cases cover pure-order failure classification/no content-model action,
old-Batch resume metadata without model/budget consumption, replay policy drift
and rejection of a core-preferred candidate with displaced whitespace.

The raw-source Solver replays are fresh same-family searches from I6's own
horizontal-band board and I7's own top-hero board; no board is borrowed across
attempts/families. Fresh search retains the existing freedom to select a subset
of original verified claims/modules, so it is not an exact content-preserving
edit of either historical poster. The bounded reading reassignment itself
preserves every module/claim/visual already selected in its candidate. These two
scopes must not be conflated. Results/limits and the final commit follow below.

Final same-family counterfactuals (CPU, original saved sources, current reading
policy, no content optimizer/model/Critic calls):

| Input | Actual new order | Visible claims | Visible modules | Final text audit |
| --- | --- | --- | --- | --- |
| I6 bands | background 1, problem 2, setup 4, method 3, performance 5 | 13 → 12 | 5 → 5 (background replaces ablation) | passed, 10/10 |
| I7 top hero/grid | performance 5 as hero; body background 1, problem 2, method 3, setup 4, ablation 6 | 19 → 10 | 7 → 6 (implications omitted) | passed, 12/12 |

Both exact Solver reports have zero known reading conflicts and pass final
typography preflight. Rendering reused each candidate's own saved keywords,
palette and paper assets deterministically; no keyword/model call was made.
PPTX/PNG live only under `/tmp/postergen-reading-replay/i6_render` and
`i7_render`. There were no confirmed glyph overflow/collision/title-gap issues.
The final source searches took 32.39 s (I6) and 161.88 s (I7) on this run;
these are Solver-only diagnostics, not whole-loop performance claims.

The whitespace selection guard removed an intermediate I7 choice with 15.81%
largest empty rectangle when the existing candidate pool offered 8.50%. The
final historical comparison is mixed: I6 largest hole 6.77% → 6.01%, vertical
gap 1.8873 → 1.6767 in, terminal mean 1.2407 → 1.4507 in; I7 largest hole
4.78% → 8.50%, vertical gap 0.6111 → 2.3702 in, terminal mean 2.2291 → 2.0917
in. Thus this is evidence of corrected order and preserved fit checks, **not**
proof of better overall poster aesthetics, unchanged scientific coverage, or
admission. Fresh selections can still omit details, and the model-backed
completion/ordinary Critic must assess them. The new guard compares candidates
inside the same search; it does not claim all metrics beat a historical poster
with a different selection. Completion's stronger cumulative protections and
Improve's parent-comparison guards are unchanged.

All **216 Campaign JSON files** retained identical hashes and inventory after
both the final Solver replay and actual rendering. Batch 3 stayed PAUSED at
2/100; no Campaign knowledge/template/Portfolio update or live generation was
performed. Logs/summaries:
`/tmp/postergen-reading-focused-final.log`,
`/tmp/postergen-reading-replay-final.log`,
`/tmp/postergen-reading-render-final.log`,
`/tmp/postergen-reading-replay/summary.json`,
`/tmp/postergen-reading-replay/render_summary.json` and
`/tmp/postergen-reading-replay/historical_hashes_verified.json`.

Final complete regression on the final source: **667 passed plus five subtests**,
four existing dependency deprecation warnings, in **447.55 s**. Log:
`/tmp/postergen-reading-full-complete.log`. Earlier intermediate full regression
found the compact-three-column queue regression described above; the final
103-case focused and 667-case full runs include its correction and the global
whitespace-selection regression. `git diff --check` passed. There was no GPU or
real-model generation, no historical poster replacement and no Batch resume.

Atomic task commit: **`be69bbb`**, `fix(layout): enforce shared physical reading
flow`, 12 tracked files (shared reading policy, search/repair integration,
Critic/prompt/version/config, input/restart identity, regression tests and README).
`AGENTS.md` and this full report are updated locally and remain Git-ignored under
the project's documentation policy; no generated poster/input/log was committed.

## Module completion with layout protection (2026-10-15)

User-authorized implementation on `f58626b`. This section supersedes the v1
thin-module/completion behavior below, while preserving all historical records.
The implementation applies to all twelve optimization families and registered
extensions through their shared solver/repair path. Classic retains three fixed
regions and no split/span; the independent one-shot route is unchanged. Critic
4.3/rubric v5, weights, scientific gates and the 78-point admission threshold
are unchanged. Withdrawn module/source semantic stages are not reintroduced.

### Retrieval and content

- `utils/module_content.py` derives retrieval context from the explicit current
  board's visible and curated claim roots, their verified evidence, originating
  narrative plans and original paper sections. It does not consult another
  storyboard or a mutable parent. Titles/intents assist retrieval; they do not
  establish scientific membership. Missing historical context stays limited to
  the selected board's own recoverable references.
- Omitted original immutable claims can be restored without a model. Relevant
  verified alternatives are ranked before new wording; variants are reverified.
  Disabled IDs, excluded roots, globally visible roots and exact duplicate text
  cannot enter automatic retrieval. Explicit Planner evidence scopes still apply.
- A bounded model action may compact an omitted original claim and restore its
  same-root verified variant. Otherwise it may add from existing evidence or
  explicitly progress to source retrieval after an unsuccessful evidence action.
  Previously used evidence IDs are not globally discarded: their unexpressed
  information can be used only after the existing full verifier/editorial audit.
- Editorial checks see other visible text and explicitly excluded module claims
  in addition to the source excerpts. New evidence/wording is staged, must remain
  visible in the correct module, and reaches shared memory only through the
  ordinary committed-candidate mechanism. Failure rolls back trial banks too.

### Diagnosis, scheduling and finite work

- A module reduced from two or more original roots to one is now diagnosed even
  if the surviving root carries a core preference. Consecutive short text-only
  modules and unused exact zone capacity are additional repair hints. Compiled
  textbox-height/body-line estimates supplement the short-text fallback; neither
  sentence counts, core labels, nor these estimates certify semantic adequacy.
  A lone concise source/figure module is not automatically forced to expand.
- The queue is per module, including multiple modules in one zone. Attempt counts
  provide fairness, attempted IDs are not repeatedly selected, and a successful
  action does not terminate all remaining work. Reports retain module attempts,
  outcomes, reasons and unresolved section IDs without scientific prose.
- Up to eight original-base restoration attempts use no model round. Text-model
  work retains four rounds per global iteration, two per family and at most two
  actions per round; one global round remains reserved from capacity work for
  quality. Charges precede calls and survive failed/abandoned attempts/restart.
  No-model, disabled and exhausted paths report unresolved work rather than
  claiming that all modules were repaired.
- Design policy is `grounded_family_design_v2`. Resuming v1 records an explicit
  v1-to-v2 policy upgrade while preserving its frozen repair budget and family
  pool. No historical iterations are rewritten. This development session did
  not resume the user's actual paused Batch.

### Space and artifact protection

- Completion first refits the current geometry with all visible claims/visuals,
  module ownership and stacking pinned. If that fails, at most one additional
  same-family search per completion call is permitted, capped at two geometry
  candidates/two exact candidates. Strict Validate and exact-parent fallback
  retain their locks. No automatic module deletion or cross-module merge is
  introduced; fonts, title/body spacing and image proportions are not relaxed.
- Each trial must preserve module IDs, per-module claim roots and visuals,
  visibly retain proposed claim IDs, and pass exact compile/preflight. A useful
  restored/verified addition may be adopted with zero height gain.
- Both the previous adopted result and the original completion baseline must
  pass space non-regression. Every existing zone may lose at most 0.005 fill;
  each terminal gap may grow at most 0.05 inches. Whole-poster empty-area and gap
  checks use 0.005 fraction/0.05-inch tolerances. Comparing to the original
  baseline prevents small stepwise losses from accumulating.
- A runtime-only, attempt-identified baseline retains its board/spec/report and
  content banks/contracts. Final typography/preflight failure, rendered failure,
  partial/unavailable text coverage, or final compiled space regression triggers
  one complete rollback and ordinary preflight/render recheck. Failed candidate
  readiness is cleared. Font emphasis is reapplied deterministically without an
  additional keyword-model call. Unknown generation exceptions remain errors.
  The baseline is removed at the design boundary and never persisted as shared
  knowledge. Baseline render failure still follows existing failure handling.
- Compiled space comparisons and rendered-glyph checks remain distinct. This
  does not add a second baseline render to measure aesthetic differences, nor
  does it turn partial historical evidence into a complete visual guarantee.

### Validation and limits

Targeted regression before the final review: 133 passed in 46.19 seconds.
The new module suite contains 33 regression cases, including actual Solver
compile/preflight for classic/four-column, all-family/extension shared repair,
regrouped-source lookup, used evidence, exclusions, same-zone fairness,
zero-height adoption, cumulative gap regression and downstream rollback.
Final focused module/content suite: 40 passed, two existing dependency warnings,
in 9.08 seconds. Final complete CPU regression: **633 passed plus five subtests**,
four existing dependency warnings, in **423.68 seconds**. The full suite includes
actual LibreOffice title spacing and rendered-text checks. An earlier complete
run before the final duplicate-root guard passed 632 tests plus five subtests;
the final run above validates the final source. `git diff --check` passed.
Logs: `/tmp/postergen-module-root-guard.log` and
`/tmp/postergen-module-full-final.log`.

Read-only I5 diagnostic used only its own saved four-column source and visible
boards. The one-claim `poster_sec_1` is detected; its retrieval context contains
four evidence IDs across two source sections. SHA-256 hashes of all 187 inspected
Campaign/I5 JSON files were unchanged. This was a diagnostic, not a refit, new
poster, source-family swap or model-backed quality benchmark. The temporary
summary is `/tmp/postergen-module-i5-audit.json`.

A separate CPU-only rollback/render check used **that same I5 four-column
snapshot**, its own scientific foundation and a fresh temporary output directory.
It restored the original board and removed a staged test sentinel, recompiled,
passed final typography preflight and rendered PPTX/PNG. RenderFit passed with
**10/10 editable text elements matched**, no issues and no errors. All 187
historical JSON hashes remained unchanged. This validates the rollback path,
not model-generated supplementation or improved poster aesthetics. Its final
summary is `/tmp/postergen-module-rollback-i5-summary.json`; artifacts are in
`/tmp/postergen-module-rollback-i5-gcqeooya/`. The first temporary script omitted
the node wrapper's token-accounting object; that script-only setup omission was
corrected before the successful complete check. No product source fix was needed.

The real Batch remains **PAUSED, 5/100**. Git submission is local only; this
report, AGENTS and the other topic reports remain ignored and unstaged.
Atomic task commit: **`5e45392`** (`fix(layout): complete grounded modules while
preserving fit`), 14 tracked files, 886 insertions and 37 deletions. Post-commit
working-tree and commit-stat checks are part of the final handoff.

Finite budgets and limited paper evidence can leave unresolved modules.
The shared policy improves processing and observability; it does not guarantee
that every one-sentence module will expand or that every poster will be accepted.
No model/GPU generation, Batch advancement or GitHub push is part of this task.

## Shared family design update (2026-10-14)

Policy `grounded_family_design_v1` applies to all twelve loop families and
registered extensions. It does not modify the one-shot Balancer route or
reintroduce withdrawn source/module semantic stages, association repair or
source-image calls. Critic remains 4.3.0 / academic_poster_multifamily_v5,
with unchanged weights and the 78-point admission threshold.

### Family contract

All twelve registrations explicitly declare `FamilyContract` v1: reading
strategy, required regions, fixed IDs, mutation permissions, conditional roles,
sequence/peer checks and a geometry strategy. Classic still owns exactly
left/middle/right and rejects splits/spans during generation and validation.
An extension registers zones and a contract, using generic legal mutations or
a deterministic `geometry_generator`, then enables its ID for a new Batch.
Existing frozen family pools are not silently expanded. See
[FAMILY_SELECTION_REPORT.md](FAMILY_SELECTION_REPORT.md) for the extension API.

Presentation roles never prove scientific relationships. Existing conditional
method/result/top-hero restrictions retain their prior activation rules.
Unknown families use neutral reading; unknown-only stacks retain their order,
and unknown roles cannot hide a reversal between known linear roles.

### Search and content

Coverage, approved-image, compact and editorial beam paths share the existing
4/8 branch budget. Duplicate paths cannot fill every portfolio slot. Configured
4-to-12 geometry expansion, eight exact candidates and two near-miss rechecks
remain bounded; measurement safety, fonts and overflow gates are not relaxed.

`ContentPriorities` counts verified roots/evidence and sanitized Curator core
IDs. Core hints prioritize information, not immutable wording. Same-root
verified compaction and existing grounded additions remain available. Functional
role groups avoid requiring both problem and insight placeholders. One-claim
source modules remain valid; heavily reduced modules with lost information are
diagnosed. `curated_claim_roots` retains the reference across repair/refit and
removes explicit Improve root exclusions. This is editorial metadata, not a
scientific membership guard or an independent admission gate.

Exact candidates prefer fewer missing core roots, known reading conflicts and
thin modules before fine composition score. Seeded near-best diversity stays
inside that quality tier; composition refinement cannot regress the tier.
Refill accepts useful zero-height additions within the existing step limit and
can restore compact original modules without new prose or section IDs. Quality
repair targets a thin module ahead of the first module in its zone, even when
aggregate utilization looks dense. All new wording still uses the ordinary
optimizer, source-excerpt checks and full final-wording ClaimVerifier.

### Actual reading and complete titles

Traversal uses real coordinates/roles, including mirrors. Known within-zone
roles are ordered; linear strategies permit at most two measured cross-zone
swaps. Anchor-first and parallel families are not forced into universal ABT.
Explicit Improve reading requests must change actual zone ownership within
current counts, pass role/capacity/pin checks and exact preflight. A failed
request cannot claim success by changing only `reading_order`.
Validate, exact-parent fallback and `allow_changes=False` stay locked.

The existing loop Curator call requests complete concise titles and at most
three core claim IDs; body prose is still copied from verified claims. Loop
fallback titles are complete too. Standalone titles keep five-word truncation;
historical parent titles are not automatically rewritten. Final FontAgent
preflight and rendered text/gap audit remain mandatory.

### Durable budget and replay

Production retains four content-repair rounds per global iteration, reserving
one from infeasible capacity work for quality on an exact feasible candidate.
A second infeasible round requires measured search progress, not merely a
verified wording change. Per-family/action limits remain. A call is charged
before it starts into attempt-local `model_repair_budget.json`, under the
Campaign lease. Resume sums charges and legacy reports for that global
iteration; abandonment, force-stop and exceptions never refund real calls.
The reserve is released after quality work uses it. Direct legacy callers
without policy retain prior budget behavior. Visual-recovery budgets are
separate. Quality work remains inside layout fitting; subsequent FontAgent or
render failure may abandon it, so not every later retry is guaranteed a round.

Batch `schedule_policy.design_optimization` freezes design version and repair
limits and distinguishes creation from explicit legacy-resume upgrade. History
and foundations are not rewritten. Each attempt keeps immutable digest-bound
`layout_input_snapshot.json`, with scientific fit inputs, measurement config,
configured/stored-font identities and dependency versions, excluding model
clients, credentials and unrelated context. It is a local diagnostic, not
shared knowledge. Repair cannot overwrite the original input. Reports remain
text-free and distinguish search exhaustion from exact compilation failure.
Planner receives selection hints and repair outcomes.

```bash
.venv/bin/python -m src.layout.benchmark_measurements --replay-input /path/to/attempt/layout_input_snapshot.json
```

Replay refuses input/config/font/dependency drift and calls no models, renderer
or Campaign commits. Unexpected errors still fail generation, never silently
retry a family or consume a poster-quality rejection.

### Validation and limits

Read-only inspection of original I5 found classic's failure at bounded
fast-search/near-miss fitting, not a proof that the three-region grammar could
never hold the paper. The original committed four-column poster kept five
modules, 22 claims and five visuals: result content was present, while problem
and implications modules were omitted and one retained introductory module
had only a generic claim. The changes address search diversity, information
selection and actual traversal jointly; allowing classic splits is unnecessary
and remains prohibited. Capacity is a measured fit question, while useful
coverage and reading quality remain separate concerns.

Tests cover every current family and an unseen registered grammar through the
shared Solver/compiler; compact three-column false-negative recovery and a
genuinely insufficient canvas; root-safe priorities, zero-height refill,
thin-module targeting, actual and pinned reading requests, locks, unknown roles,
budget restart/corruption, source immutability and input digest/secret exclusion.
Final focused CPU regression: **128 passed** in 53.64 seconds (three existing
dependency deprecation warnings):

```bash
.venv/bin/python -m pytest -q tests/test_family_design_policy.py tests/test_layout_exploration.py tests/test_generation_failure.py tests/test_multi_batch_lifecycle.py tests/test_improve_revision_contract.py
```

Complete CPU regression: **518 passed, five subtests passed** in 438.18 seconds,
with four existing dependency deprecation warnings:

```bash
.venv/bin/python -m pytest -q
```

`git diff --check` passes. Commit **`24cde5a`** (`feat(layout): unify family
contracts and grounded design optimization`) contains the twenty task-owned
source/config/prompt/test/README files. AGENTS.md and topic reports remain local ignored Markdown according
to repository policy. No generated replay artifacts are staged.

Saved I5 replay uses the complete later four-column Curator input, not an exact
reconstruction of the earlier failed three-column input. CPU fitting and
temporary PPTX/PNG rendering write only to `/tmp`; no content or Critic model
is called, and no Campaign or knowledge state changes. Geometry and rendered
text passing cannot certify editorial quality; residual hints remain visible.
The final controlled replay uses four geometry and four exact candidates per
family, without changing production limits. Three original scientific/Curator/
snapshot JSON inputs retain identical SHA-256 hashes before and after replay.

| Saved-input replay | Classic three-column | Four-column modular |
| --- | --- | --- |
| Exact compile/preflight | Passed | Passed |
| Visible modules / claims | 7 / 17 | 6 / 25 |
| Functional-role coverage hint | 1.0 | 0.75 |
| Thin modules | 3 | 0 |
| Known reading conflicts | 1 | 1 |
| Editable body/title matching | 14 / 14 | 12 / 12 |
| Rendered fit | Passed, zero issues | Failed, two horizontal title overflows |

Both result modules survive in both candidates. Four-column omits the
implications module and remains imperfect despite having no thin modules.
Classic keeps three regions containing seven stacked modules without splitting.
The ordinary `render_fit_audit_node` confirms four-column title-right overflows
of 0.1281 and 0.1818 inches; the existing vertical title correction is
inapplicable and the candidate is blocked before Critic. These observations do
not certify acceptance or a causal improvement over the original failed
classic attempt. Saved historical titles/core annotations were not regenerated;
new Curator behavior and model-assisted quality repair are covered by CPU
tests, not a live model run.

Temporary artifacts: `/tmp/postergen-family-design-replay-bounded/summary.json`,
per-family `fit_report.json`, `layout_spec.json`, `board.json`, `layout.json`,
PPTX/PNG and render audits; the normal-node audit is under the four-column
directory's `content/render_fit_report.json`. No runtime archive or template
was published. Latest Campaign Batch 2 stays PAUSED at 5/100 with I5 committed.

More diverse feasible branches and compact restoration can cause more exact
measurements within unchanged caps; this is not a zero-cost or speedup claim.
Incomplete historical inputs cannot support strict causal before/after claims.
Actual Curator core accuracy, multi-paper aesthetics and model-assisted quality
repair still require future controlled observation. No live Batch was started.

## Local density and spacing update (2026-10-13)

Schema-v3 capacity audits now include `fit_comparison`. A feasible sparse-zone
repair no longer requires the globally worst zone to improve by 0.03 when a
different zone benefits. A 0.02 zone-use gain or 0.20-inch zone/whole-poster gap
reduction can also qualify. Every existing zone and the worst fill must remain
within 0.005 of their previous fill; visible content and whole-poster
whitespace non-regression guards still apply. New claims must actually be
visible after fitting. No model/verification budgets or scientific exclusions
were relaxed. The old worst-zone-only rule described below is historical.

Directional adjacency and extra bottom-edge measurements participate in
non-regression only when measured on both sides. A bounded family-legal
shared-boundary refiner runs after feasible fitting (two rounds of four exact
candidates per fit call), reusing the attempt measurement context. Fixed
Validate zones and exact-parent fallback remain locked. Compiled and rendered
glyph composition are stored separately to avoid mixed-baseline comparisons.
Critic 4.3/rubric v5 now scores and reports cross-zone vertical/bottom whitespace;
dimension weights and the 78-point archive threshold are unchanged.
See [LAYOUT_SPACING_REPORT.md](LAYOUT_SPACING_REPORT.md) for title safety,
historical audits, real LibreOffice replay, tests and compatibility limits.

## Generation-failure isolation update (2026-10-12)

Sparse-zone actions may deliberately omit a claim ID so the optimizer selects
an eligible, relevant, non-visible verified claim. That path now normalizes the
visible-ID list to a set only at the exclusion union; deliberate root deletions
remain excluded and an exhausted claim pool is a safe no-op.
The initial measured fit is saved before optional repair. Repair audits are
attached before work starts, and an unexpected optimizer/refit exception keeps
its root traceback and partial audit. Such exceptions fail generation safely;
they are never reinterpreted as a poorly scored poster or silently retried as
another family. Known measured fit failures retain their existing bounded
recovery. See [GENERATION_FAILURE_REPAIR_REPORT.md](GENERATION_FAILURE_REPAIR_REPORT.md)
for commit rollback, journal publication, historical correction and tests.

## Improve revision safety update (2026-10-10)

Grounded content repair now consumes an explicit staged board override, while
ordinary Improve consumes Planner's current working board, never its read-only
parent. Explicit empty actions do not invoke an unsolicited fallback. Source
provenance remains immutable; a separate branch recovery policy distinguishes
accidental omissions from intentional asset/root-claim deletions and moved
visual ownership. Sparse repair honors those exclusions and deep-copies the
contract/policy along with scientific memory; discarded trials cannot leak
revision intent. Later explicit Planner restoration remains possible after
source-asset readability or claim verification/placement checks.

Improve prefers exact candidates without deletion-induced whitespace
regression. If bounded fitting/repair cannot compensate for a valid deletion,
one explicit rollback/refit may revoke it. Unusable assets are never restored
as fillers. The final styled preflight re-measures module/container geometry;
a separate post-Critic admission guard preserves raw scores but blocks unsafe
archives/templates and safe-parent promotion. The existing capacity limits,
95%-100% utilization goal, Critic rubric/thresholds, and same-family Validate
topology requirements remain unchanged. Full details and audit locations are
in [IMPROVE_REVISION_REPORT.md](IMPROVE_REVISION_REPORT.md).

## Whole-poster density and source-visual retention update

The loop now measures the compiled poster as a whole, not only each zone's
internal fill. The text-free composition audit records unallocated body area,
the largest contiguous empty rectangle, the largest cross-zone gap, and the
largest within-zone gap. Exact candidate ranking considers these measurements
alongside worst-zone utilization and the largest unused zone bottom. A seeded
near-best choice cannot knowingly replace local blank space with a materially
larger whole-poster void. These are geometry measurements, not a perceptual
judgment on the rendered pixels.

Feasible but sparse layouts enter bounded repair below 90% zone utilization or
when a zone's bottom gap exceeds two measured body lines. The loop keeps a
source-visual manifest, marks important original key/result/method visuals,
and reserves a visual-rich beam branch. If a key visual disappears during fit,
it may try to restore the approved original visual in its source section and
re-fit the same family. Restoration requires exact compile/preflight and cannot
drop already visible claims or visuals, change strict Validate topology, or
materially worsen whole-poster whitespace. The default limit is two visual
restoration attempts per family and four per global iteration. It never
invents visual assets or scientific text. When no valid visual placement exists,
the omission remains visible in the repair report and Critic audit metadata.

Content repair still uses grounded, verified changes only. A sparse repair is
adopted only after a material worst-zone improvement and no global-whitespace
or visible-content regression. The Critic records the composition and source
visual-selection evidence without changing its calibrated score or admission
threshold. The independent standalone classic route is unchanged.

Read-only inspection of historical I13 showed that the new repair trigger
would activate; its compiled board had approximately 6.55% unallocated body
area and an 11.17% largest contiguous empty rectangle. Historical artifacts
were not rewritten. No live model/GPU poster run was performed.

## Resulting behavior

The optimization route searches each selected layout family using the original
prefix claim choices plus up to twelve additional non-prefix claim subsets per
module. A failed four-wide assignment beam is retried at width eight. Up to
two variants per family with small measured height pressure may be reconsidered
without the conservative fast-estimate reserve; every selected variant still
requires exact layout compilation and preflight. Bounded pressure evidence
keeps the closest, worst, and most-advanced assignment samples separately.
Near-miss variants are ranked across the family by completed assignment count
and then overage, including pressure found only by the wider beam. The
effective minimum section count respects zone capacity. Schema-v5
`layout_feasibility_report.json` records the failure class, pressure samples,
search limits, recheck count, and exact outcomes. Its displayed trials remain
limited to twelve, but a separate repair-candidate list is built first from
all searched variants, including the possible thirteenth and fourteenth.
That list is capped at 128 de-identified numeric/ID samples and records whether
the cap was reached; the planner does not infer “no height pressure” from a
truncated diagnostic. Schema-v3/v4 summaries remain readable. Successful
reports retain the old `safety_factor` as the configured default and add the
selected candidate's actual factor and standard/adaptive/near-miss search path.
The independent compiled-preflight report stays at schema v4. Samples are
observations, not proof of physical impossibility.

When fitting fails with a repairable text-height near miss, or an exact fitted
zone is below the configured 90% repair threshold or has a large bottom gap, `CapacityActionPlanner`
requests allow-listed actions from the existing `GroundedContentOptimizer`.
Overfull modules first try a shorter previously verified same-root variant;
otherwise they request a verified compact variant. Sparse modules first try a
relevant existing verified claim, then a new paper-supported claim. The
optimizer never accepts arbitrary Planner-provided scientific prose.
An exact-compile/preflight failure alone does not request text compaction.
When sampled text height cannot cover the overage, repair is skipped with an
explicit reason. If the bounded repair-candidate list itself was truncated
without a usable action, the reason states that diagnostic limit explicitly.

Each repair uses a private working copy of the storyboard, verified-content
bank, supplemental-evidence bank, and content selection. The changed content
is re-fitted to the same family. Validate passes the original saved zones to
that re-fit. A failed repair leaves the candidate's original scientific memory
unchanged; accepted content reaches Campaign-wide memory only through the
ordinary committed-iteration path. Defaults are two repair rounds per family,
four per global iteration, two content actions per round, and no content
repair for an estimated overage above two inches. These limits are configured
under `capacity_repair` in `config/critic_config.yaml`.
Before each new attempt the runner restores the committed Campaign-wide
content banks and last committed content selection. Explore/Validate keep
Campaign history while discarding provisional choices from an abandoned
attempt. This closes a pre-existing path where an uncommitted Improve attempt
could otherwise leave provisional verified variants in process memory.

New compact/additional claims still pass `ClaimVerifier`. Its proposed
`corrected_text` now receives a second complete semantic pass on the final
wording; a second proposed correction is not automatically published. A
separate source-excerpt audit checks that compact wording retains necessary
scientific conditions and that additions are relevant and non-redundant.
Previously saved variant wording is reverified when reused. Supplemental
evidence is published only when the corresponding claim verifies and is
actually placed. Source search ranks bounded windows across parsed paper
chunks, and each accepted excerpt must occur in its selected source window.

The loop writes `content/capacity_repair_report.json` for the latest attempt
and preserves each attempt's repair report at
`iterations/<N>/attempts/<attempt>/capacity_repair_report.json`; this includes
abandoned layout-fit attempts and committed candidates, so later retries do
not erase predecessor diagnoses. Terminal retry events show near-miss rechecks
and repair status/skip reason; repair rounds also have a compact event. The
report and content revision are included in committed iteration snapshots. The standalone
one-shot classic route is unaffected. Critic still decides poster acceptance
after rendering; improved fit alone does not archive a poster or template.

## Verification and limits

CPU regressions cover non-prefix selection without losing shorter prefix
fallbacks, bounded closest/worst/advanced pressure sampling, cross-variant
ranking, wider-beam-only near misses, exact rejection after a relaxed fast fit,
nontext repair refusal, per-attempt report persistence, retry terminal
diagnostics, near-pressure action selection, a repairable fourteenth variant
hidden by the display cap, bounded repair-candidate payloads, legacy summary
compatibility, and actual selected fast-estimate factor/path reporting,
successful fixed-zone adoption, rollback of failed content, later source-chunk
retrieval, and refusal to publish a corrected sentence that fails its final
semantic check. The original capacity-search update passed 214 CPU tests plus
5 subtests. The whole-poster update passed 222 CPU tests plus 5 subtests; four
third-party deprecation warnings remain unrelated.

No live model-backed poster run was performed. The model-based semantic and
editorial checks lower the risk of wrong scientific wording but cannot prove
zero factual errors. When evidence is absent, ambiguous, or verification
fails, the optimizer keeps the prior verified content or abandons the repair.
The 95%-100% module-fill band remains a design target, never a reason to invent
or repeat scientific information.


---

## 2026-11-02 独立项目迁出说明

本报告的既有内容从 PosterGen 工作区完整保留，现随独立项目 Rubrics_poster
在 `/projectone/projects/Rubrics_poster` 维护。既有记录中的源码版本、测试、旧样本
和绝对路径属于迁出前的历史证据；不代表新项目已运行相同的真实模型验证。
新项目未迁入原来的海报、run、缓存或模型日志，也不依赖原项目源码和环境。
迁出操作、行为保留范围、独立环境及验证结果见[独立迁出报告](PROJECT_EXTRACTION_20261102.md)。
