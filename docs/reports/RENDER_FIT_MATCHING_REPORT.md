# RenderFit Complete Editable-Text Matching

## 2026-10-30: adjacent inline-script fragments (v2)

The current repair addresses a separate coverage defect from the original v1
work documented below. LibreOffice/PyMuPDF split the HAGS loss-function line into
three adjacent physical-row fragments, sometimes in separate extraction blocks.
The complete normalized expected/PDF text was identical (405 characters), but
the fallback required every continuation to advance downward and stay near the
first line's x coordinate. It could not join the horizontal formula pieces.

`src/layout/render_text_matching.py` now tracks each physical row's union and
accepts a continuation extending to its right with at most 1pt top difference,
2pt bottom difference, 2pt gap and 1pt overlap. A binary search over sorted line
tops also accommodates slight y jitter that puts the right piece earlier in
extraction order. The current row's union prevents cumulative vertical drift.
Original next-row constraints, whole-block fast matching, complete normalized
text equality, exclusive block/character ownership and ambiguity rejection
remain. All six existing limits remain unchanged; every scanned continuation
is charged to the existing search budget. Complete fragment edges also retain
separated bullet/punctuation glyphs in measured bounds, including real overflow.
There is no clipping to the planned textframe or relaxed prefix/fuzzy equality.

Matching policy is `editable_exact_fragments_v2`, with the four geometric limits
included in diagnostic metadata. RenderFit report schema remains 3; generator
remains `explore_samples_v28`. Ordinary code identity prevents old-run resume.
No changes to Renderer, scripts, fonts, layout/direction locking, scientific text,
models, scoring or request budgets. Normalization still compares NFKC lowercase
alphanumeric text: it does not certify script baselines, punctuation equivalence
or mathematical meaning. Formula-image contents are still excluded. Other PDF
extraction patterns can remain explicitly partial or unavailable.

Read-only replay used the official saved poster
`storage/rubrics_samples/posters/run_7c282388d5ef4432b1e2_sample_000001`.
The baseline matcher was loaded from commit `6e6cae8` in memory and both policies
received the SAME isolated LibreOffice PDF export:

| Policy | Matched boxes | HAGS body | RenderFit result |
| --- | ---: | --- | --- |
| v1 | 11/12 | unmatched | incomplete coverage |
| v2 | 12/12 | 405/405 characters, 7 fragments | conclusive passed, zero issues |

Saved PPTX/PNG, layout/spec and original diagnostic files retained their hashes;
no historical reports, Critic scores or publication decisions were replaced.
Evidence: `/tmp/postergen-renderfit-row-saved-replay/validation.json` and
`render_fit_v2_diagnostic.json` in that directory.

Final focused run: **128 passed**, two dependency warnings, **64.92s**. The
matcher file now has 70 cases (28 new), covering cross-block same-row pieces,
reversed extraction order/y jitter, subsequent paragraphs, missing/wrong-script/
reordered/extra text, gutters, overlap, row/height mismatch, accumulated drift,
shared block/character ownership, ambiguous duplicate completion, real overflow
and collisions, separated edge symbols and all six exhaustion paths. A real
editable-script PPTX is checked through LibreOffice without modifying it or the
input state. The existing horizontal HAGS capacity-edit/PPTX/PNG integration now
requires conclusive successful RenderFit and exact 405-character coverage.

The first focused run failed only because the competing-evidence fixture's whole
PDF block equaled the expected text and took the existing fast path. An unrelated
heading was added to that synthetic block to exercise the intended fragment
ownership fallback; production matching was not weakened. That preliminary run
is not acceptance.

Final frozen full CPU suite: **1,480 passed, 5 subtests passed**, seven dependency
warnings, **1,308.92s (21m49s)**. All 344 frozen tracked files remained identical
during verification. All 19 pre-existing modified/untracked paths and all 9,333
historical files retain their original bytes, with no added historical artifacts.
Both CLI help checks, `uv lock --check --offline` and `git diff --check` pass.
Evidence prefix: `/tmp/postergen-renderfit-row-` with `full-cpu-final.log`,
`focused-final.log`, `baseline.json`, `frozen.json` and `validation-final.json`.
Only four task-owned tracked paths belong in the local commit; this report and
AGENTS remain ignored. No live model/GPU generation or scientific/aesthetic
acceptance is claimed.

Local atomic commit: `6f6452c` (`fix(renderfit): match adjacent inline-script PDF
fragments`), four tracked source/test/README paths; no push. The 19 pre-existing
modified/untracked paths remain outside the commit; guide/report stay ignored.

The following sections retain the original v1 implementation and acceptance
record; v2 supersedes their matching-policy name and same-row limitation.

## Purpose and diagnosis

This change fixes audit coverage, not scientific content or layout search.
Saved I3/I4 reports were partial for two deterministic reasons: body text began
with FontAgent color markup that the old audit normalized as literal letters,
and LibreOffice/PyMuPDF combined parallel title textboxes into larger blocks.
The visible text was present; whole-block matching could not recover it.

## Implementation

- `utils/text_formatting.py` owns the existing Renderer styling grammar, literal
  escape decoder and inline-script expansion. Renderer compatibility wrappers
  delegate to it without changing token semantics, including legacy empty
  italic/unclosed-emphasis behavior. Colored content is not recursively styled.
- Body audit expectations follow stripped paragraph rendering. Titles remain
  literal. Supported display-formula expressions are PNG images and explicitly
  excluded from editable-text verification, while their lead-in remains audited.
- `src/layout/render_text_matching.py` first requires complete normalized block
  equality near the planned origin. Normalization retains the prior NFKC,
  lowercase, alphanumeric comparison semantics: this is not a punctuation or
  scientific-integrity verifier. The old 70%-130% prefix heuristic no longer
  masquerades as complete coverage.
- Only unresolved elements trigger one lazy raw-character PDF extraction from
  the same PDF. Ordered, spatially aligned line chains and independent character
  subranges can recover split paragraphs and wrapped/merged titles. A subrange
  within a line requires physical separation from other text; ordinary words
  or a partial word cannot be truncated into a complete match.
- Global block/character ownership rejects shared evidence. Multiple complete
  possibilities remain ambiguous; nearest-origin selection is not used to hide
  ambiguity. Actual glyph bounds include all matched lines/punctuation and are
  not clipped to planned textframes. Existing overflow/canvas/collision/title
  minimum-gap checks run on the resulting unions.
- Existing one-time geometry correction, strict Validate locks and
  inconclusive-correction rejection remain intact. Optional composition failure
  cannot erase confirmed text evidence. No change to scientific text, Solver,
  measurement caches, Critic weights/thresholds or ordinary template admission.

## Resource and persistence contracts

Fine extraction is bounded to 200,000 PDF characters and 10,000 nonempty lines.
Per-element fallback permits at most 50,000 search steps, 256 lines per path,
64 simultaneously queued paths and 32,000 normalized expected characters.
Exhaustion returns an explicit inconclusive reason, never an assumed match.
These are conservative safety limits, not measured process-RSS ceilings or
promises to match every possible PDF arrangement. Exact whole-block matching
does not require the fine fallback. No additional PDF export is introduced.
Fine extraction explicitly disables embedded image payloads. Temporary
LibreOffice profiles/PDFs and all matching context are released; no
context is persisted in PosterState or measurement caches.

RenderFit schema v3 adds matching policy `editable_exact_fragments_v1`, expected/
matched/unmatched counts, title/body breakdown, per-element method and normalized
character counts, unmatched reasons, title-gap coverage, noneditable exclusions,
fallback/search/timing diagnostics and explicit limits. Existing geometry,
matched boxes and gap fields remain readable by current Critic/correction code.
Reports and logs contain identifiers/numbers/coordinates, not scientific prose.
Old report schemas remain usable by existing consumers; old reports are never
automatically rewritten or rescored. Critic remains 4.3/rubric v5.

Statuses:

- `passed`: all expected auditable editable text matched; no confirmed violation.
- `failed`: at least one confirmed violation, even if other text is unmatched.
- `partial`: no confirmed violation, but incomplete/ambiguous editable coverage.
- `unavailable`: PDF measurement could not be obtained.

The compatibility boolean `passed` is still "no confirmed issue", so
`partial`/`unavailable` may have `passed: true`. They are not an all-clear.
`conclusive` concerns editable-text coverage, not formula-image contents or
overall poster quality. Geometry/whitespace are not full scientific checks.

Terminal summaries include matched/expected titles/body and up to eight ID/reason
lines, with remaining details in `render_fit_report.json`. Current Campaign
attempt persistence retains that report through existing paths. The one-shot
classic route does not enter the audit. The read-only command
`python -m src.layout.spacing_audit --candidate-dir ... --layout-spec ...`
uses the current matcher without editing saved posters/reports or Campaigns.

## Real I3/I4 read-only replay

Replayed the rejected poster PPTX files for geospatial Campaign
`Active_Geospatial_Search_for_Efficient_Tenant_Ev_3ea24642642e_f080e8`, Batch 2,
using their original styled layouts/LayoutSpecs and isolated temporary PDF export.

| Artifact | Old matched | New matched | Title gaps measured | Text-fit result |
| --- | ---: | ---: | ---: | --- |
| I3 | 9/12 | 12/12 | 6/6 | passed, zero confirmed issues |
| I4 | 5/12 | 12/12 | 6/6 | passed, zero confirmed issues |

Body color-prefix recovery used exact blocks; two I3 titles and six I4 titles
used exact fragments. Final image-free fine extraction plus matching took
approximately 0.03-0.06 seconds per artifact (PDF conversion excluded).
All poster PPTX/PNG, original styled layouts, LayoutSpecs and original RenderFit
reports had unchanged SHA-256 hashes. This does not retroactively accept the
posters, change their Critic scores or prove that their overall quality is good.

## Verification and limitations

Regression coverage includes styling tokens/PPTX runs, malformed markup,
literal escapes, inline math, supported display-image exclusions and editable
prefixes, merged two/three-column titles, wrapped lines, split paragraphs,
independent character subranges, repeated ambiguous titles, evidence conflicts,
missing/reordered/truncated text, outside-frame final-line overflow/collisions,
known failure with incomplete coverage, lazy extraction, bounded-resource exits,
extraction failure, terminal privacy/coverage and real LibreOffice PPTX/PDF.
Existing spacing/correction, Improve scientific contracts and measurement-cache
equivalence regressions remain part of acceptance. A separate 10,000-case
seeded comparison against Git's pre-change Renderer produced identical tokens.

Acceptance commands/results:

- Full `.venv/bin/python -m pytest -q -p no:cacheprovider`: **484 passed,
  5 subtests passed**, four pre-existing dependency deprecation warnings,
  413.82 seconds. This includes the 83 measurement-performance regressions.
- Final focused RenderFit/matching, inline math, display formula, Improve
  revision contract and spacing files: **142 passed**, two dependency warnings,
  27.50 seconds. The new matching file contributes 42 cases.
- Real I3/I4 replay was repeated with the final image-free extraction policy;
  full coverage and unchanged source hashes were reconfirmed.
- `git diff --check`: clean. Only task-owned code/tests/root README are staged;
  this report and AGENTS remain local/ignored under the user's Markdown policy.

This cannot guarantee absence of all future PDF extraction issues. OCR, figure
pixel text and display-image formula contents are not newly verified. Unusual
reading order, distant paragraph gaps, very short text or budget exhaustion can
remain partial rather than inventing evidence. No live model/GPU/Campaign run
was launched and no original scientific or global knowledge data was modified.


---

## 2026-11-02 独立项目迁出说明

本报告的既有内容从 PosterGen 工作区完整保留，现随独立项目 Rubrics_poster
在 `/projectone/projects/Rubrics_poster` 维护。既有记录中的源码版本、测试、旧样本
和绝对路径属于迁出前的历史证据；不代表新项目已运行相同的真实模型验证。
新项目未迁入原来的海报、run、缓存或模型日志，也不依赖原项目源码和环境。
迁出操作、行为保留范围、独立环境及验证结果见[独立迁出报告](PROJECT_EXTRACTION_20261102.md)。
