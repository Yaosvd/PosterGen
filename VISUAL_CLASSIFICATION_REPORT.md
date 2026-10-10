# Visual classification and layout-family decoupling

## Problem addressed

The old `classify_visuals.txt` described scientific images in terms of a
left/middle/right poster. This could turn an early paper-content decision into
an implicit three-column layout preference before a loop iteration selected
its layout family. A key result image or table could also be treated as though
it must be a method graphic. Since the family solver can only arrange visuals
that survive upstream curation, an omitted important visual could disappear
before layout fitting or Critic evaluation.

## Implemented behavior

1. Parser passes only extracted visual IDs, captions, types, and aspect ratios
   to the visual classifier. The prompt now asks for five paper-semantic roles:
   `problem_illustration`, `method_workflow`, `main_results`,
   `comparative_results`, and `supporting`. It forbids columns, zones, and
   coordinates. `key_visual` is an optional pointer to a role member, and may
   point to a result figure or table or be `null`.
2. `normalize_visual_classification()` keeps valid model assignments, removes
   unknown/duplicate IDs, fills omitted IDs using a deterministic caption
   heuristic, and conservatively chooses a key only when the fallback is
   unambiguous. This keeps the existing six-field JSON contract. The separate
   `visual_classification_report.json` records policy version, input modality,
   available IDs, selected key, and repair observations; it stores no captions.
3. The loop route uses `grounded_curator_family.txt`: Grounded Curator groups
   verified claims and approved visuals but does not choose physical columns.
   Its internal `column_assignment="left"` is a legacy data-shape placeholder
   ignored by the layout-family solver. The independent one-shot classic route
   continues using its column-aware Curator and Balancer path. Classic prompts
   now permit a result visual or table to be key, rather than assuming the key
   is a middle-column method figure.
4. For the loop only, if a classified key is absent from the Curator board and
   has a matching verified narrative-role module, it is offered to that module
   as an optional approved asset. The solver can still omit it if necessary;
   no new claim or visual is invented. The Curator writes
   `visual_curation_report.json` with available/curated/uncurated IDs and the
   key-seed outcome.
5. Critic's visual evaluator records the available, Curator-selected, and
   final-visible IDs, plus whether the key was dropped before layout. This is
   diagnostic metadata only: no score weights, hard gates, archive thresholds,
   or template admission rules changed.

## Persistence and compatibility

New classification provenance joins the Campaign's frozen scientific
foundation. New Curator provenance joins iteration snapshots. Existing Campaign
foundations without the new report still load and keep their original
classification; resume emits a warning instead of silently changing scientific
state. A fresh `--resume new` Campaign is required to apply the new policy to a
previously processed paper. No historical poster, template, or Campaign file is
rewritten.

## Verification and limits

Focused regression tests cover invalid/duplicate/omitted visual IDs, explicit
null keys, table-as-key fallback, Parser normalization, old foundation loading,
loop/classic Curator route separation, fallback key seeding, and Critic
provenance. The complete CPU suite passed: **231 tests and 5 subtests**. No
model-backed paper run or GPU benchmark was performed.

The visual classifier does **not** inspect image pixels; ambiguous captions
remain ambiguous, and `key_visual` may be null. Curation/solver decisions can
still omit an asset for relevance or capacity reasons; the new reports make
the omission stage observable, not automatically correct every omission.
