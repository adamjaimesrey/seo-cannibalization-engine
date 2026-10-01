# CLAUDE.md — cannibalization-engine

Claude Code reads this before acting. Keep it short.

## What this is

An SEO pipeline that detects keyword cannibalization on `ecomusa.example` from a
Semrush Cannibalization Report export, classifies competing URLs by page type,
and outputs a visual client dashboard. **Full details live in `SPEC.md` — read it
before building.** MVP = Stages 1–3. Stage 4 (RAG remediation) is deferred; do
not build it or install its dependencies.

## How to work with me

- **One step at a time.** Issue one command or decision, then stop and wait for
  my output. No batching, no long option lists.
- **Plan Mode before any non-trivial build.** Show the plan, wait for approval,
  then write code.
- **Be explicit.** "Open this file and add this exact line" — not vague guidance.
- **MVP-first.** Park maintenance items and edge cases for later; note them, don't
  build them.

## Token discipline

- Use Claude Code only for genuine build/debug work.
- Mechanical operations (git, file moves, checksums, folder creation) go in the
  **plain terminal**, not here.
- Never read large data files into context. Parse in Python and print summaries.

## Data handling (non-negotiable)

- Map CSV columns by **header name, never by position** — Semrush export column
  order is not guaranteed.
- **Verify from disk before trusting printed output.** Use a CSV-aware row count
  (`python3 -c`), not `wc -l`, for files that may contain embedded newlines.
- Write intermediate output to `data/processed/`; never overwrite `data/raw/`.
- The blog copy bank (`reference/blog_articles/`) names files by PAGE TITLE, not URL slug (e.g. /blog/post/example-slug is saved under its article title). Never conclude an article is missing from a slug match alone: search the bank by title/H1, or fetch the live URL.
- The edit-history Google Sheets are MIRRORS of the master xlsx files in `EDIT_HISTORY_DIR`, refreshed by manual File > Import > Replace (the updater prints a reminder after --apply). Fill or correct values in the master xlsx, never only in the Google Sheet: the import overwrites the tab.

## Hard rules

- Before any blog is proposed for optimization, check blog-edit-history (master xlsx in `EDIT_HISTORY_DIR`). Any page already listed there is excluded as a candidate, whatever its status, and the next candidate is used instead. Re-proposing a listed page requires the user to add it to EXCLUSION_OVERRIDES in scripts/route_worklist.py. This check is enforced in code in route_worklist.py.

## Tech stack (MVP)

- Python 3 in a `.venv`.
- `pandas`, `openpyxl`, `plotly` — nothing else.
- Dashboard output is a single self-contained `output/dashboard.html` (no server,
  no Streamlit).

## Secrets & version control

- `.env` is in `.gitignore`; API keys never enter git history.
- Git for version control. Commit after each passing test with a descriptive
  message. Verify the file was written before committing.

## Model selection

- Sonnet 5 is the default for routine scripting.
- Escalate to Opus 5 within Claude Code if Sonnet stalls twice on the same problem.
