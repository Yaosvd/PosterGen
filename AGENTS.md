# Rubrics_poster Development Guide

This is the independent Rubrics sample-generation project extracted from the
current PosterGen working tree on 2026-11-02. Work only in this repository.
Read README.md and docs/reports/PROJECT_EXTRACTION_20261102.md for the migration
manifest, current route and validation. Source PosterGen remains a historical
reference; never import its code or load its environment, runs or caches.

Preserve unrelated user changes; run git status --short before edits. Never read,
print or commit .env secrets. Do not commit papers, model logs, generated posters,
virtual environments or runtime storage. Do not reset or clean user files.
Use GPU5 only for a requested live runtime test, never disturb external services.
Do not run live model generation as a routine test. Use the local .venv.

Preserve current Generator v33 behavior: Marker plus one advisory spelling pass,
at most2core panels, immutable image ownership/direction,15peer layout families,
bounded geometry search,3capacity edits,1field-only format repair, freeze-and-score
publication and final original-paper Critic. Future Rubrics mining/updating is
not implemented. Shared legacy helpers retained for compatibility are not default
generation routes and must never become an automatic fallback.

Each durable change updates this guide and relevant report, adds focused tests,
and ends with a task-scoped conventional Git commit unless the user says otherwise.
Reports and this guide are versioned in this independent project. Never use broad
git add or remove historical reports; retain provenance and clearly mark old facts.

## Extraction validation baseline

Source snapshot: PosterGen worktree at900a119, including19existing dirty paths.
368current-route CPU tests pass (599.80s);15/15family outputs and4runtime ASTs
match.48prompt/config/font files and36input files match original hashes. New
project contains14annotated historical report/snapshot documents plus its own
migration report/manifest/validation. Source extraction history remains read-only.

Final independence checks run separately after making the one-time fingerprint
test opt-in via RUBRICS_VALIDATE_EXTRACTION=1, so future algorithm/prompt changes
do not require rewriting the historical extraction manifest. Local.env may be
created by the user; never copy or read source secrets. No live model/GPU run or
whole-paper scientific/aesthetic acceptance is claimed. See migration report for
independent environment setup and source-preservation evidence.

Final extraction independence:10tests pass/34.90s/3warnings. New runtime stores
remain empty;19original dirty paths and10283source runtime files remain identical.
The initial root commit contains the complete code/report baseline; inspect
git log --max-parents=0 for its identity. No Git remote, source env or source
project runtime dependency is configured. No full-suite or live-model claim.

## Local Qwen configuration (2026-11-02)

Text and vision use the existing http://127.0.0.1:8000/v1 service, advertised
model ID Qwen3.8-27B. New .env is local, ignored and mode600; credentials were not
copied from PosterGen. The committed .env.example uses the public EMPTY placeholder.
Per-agent policies and generation algorithms stay unchanged. Configuration work
also restores runtime.py's missing sys import for the console tee. Migration
manifests remain historical baselines; later changes do not rewrite their claims.
See docs/reports/MODEL_SETUP_20261102.md for verification and scope.

Model setup acceptance:17focused tests pass,1one-time fingerprint check skipped,
3dependency warnings,34.66s,normal exit0. Both client constructors and CLI/WebUI
model defaults verified; health and advertised model list returnHTTP200. No live
inference/poster generation, service restart or full regression was performed.

## Environment example removal (2026-11-02)

User explicitly requested deleting .env.example after local model setup. The
example file and its Git ignore exception are removed. Existing local .env stays
untouched and ignored; runtime has no dependency on the example. Current README
points fresh installations to the model setup report. Earlier extraction/setup
references describe historical states, not a currently available template. The
report-preservation test now checks the model setup instructions instead.

Removal verification: report-preservation test1passed/0.06s, exit0; git diff --check passed and .env remains ignored. No model calls or generation run.

## Main repository publication (2026-11-02)

User authorized publishing Rubrics_poster to main of Yaosvd/PosterGen. Origin is
https://github.com:443/Yaosvd/PosterGen.git; main is the publication branch. Future
work belongs in /projectone/projects/Rubrics_poster, not the historical checkout.

Terminal HTTPS push has no credential helper or logged-in identity. The connected
GitHub tool has repository write permission and publishes the verified project
tree as a normal descendant of old main900a119, with an expected-head check and
no force update. The independent local history and prepared merge remain on
codex/independent-rubrics and codex/main-publish-prepared. Local main then tracks
the actually published origin/main. Historical extraction root b135846 remains
in those preserved local branches; it is not a new root in remote main history.

Only publication documents change; production source/config/prompts remain at
05fb42e. Do not restore old runtime files or private configuration. Verify remote
main/tree equality, original main ancestry and local upstream. Command-line
future git push requires normal GitHub authentication configured by the user;
the connected tool does not install terminal credentials. Details are recorded
in docs/reports/MAIN_PUBLICATION_20261102.md. Earlier no-remote notes describe
historical states. No model generation or full regression for Git/docs work.
