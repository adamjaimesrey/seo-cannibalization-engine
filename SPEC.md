# SPEC — cannibalization-engine

## 1. Purpose

Detect and visualise **keyword cannibalization** on `ecomusa.example`, where more
than one page ranks for the same query and Google flip-flops between them —
causing URL volatility and lost organic traffic.

The engine ingests the **Semrush Enterprise Cannibalization Report**, classifies
every competing URL by page type, detects cannibalization across four page-type
combinations, and produces a visual client dashboard. An AI copy-remediation
stage is scoped but deferred (see §7).

## 2. Scope

### Detection (all four combinations — always)

Each URL is classified **once** as Blog / PLP / PDP. Every pairing then falls out
of simple pairing logic at zero extra cost:

- Blogs vs PLPs
- Blogs vs PDPs
- Blogs vs Blogs
- PDPs vs PLPs

### Client reporting (MVP default)

- **Blogs vs PLPs** is the default reported combination.
- The other three are selectable but not surfaced by default.

## 3. Data source

- **Primary (MVP):** Semrush Enterprise → *Special Reports → Cannibalization
  Report* → exported to CSV and placed in `data/raw/`.
- Manual export is the MVP path. Semrush API / GSC API integration is a future
  enhancement, not part of MVP.

### Expected input columns (from the Semrush report)

`Keyword`, `Best URL (End)`, `Position (End)`, `All Ranking URLs (Count)`,
`Best Ranking URLs (Count)`, `Avg. Position (Best Ranking)`,
`Best ranked URL changes (Change)`, `Best Traffic`, `Lowest Traffic`, `Traffic Risk`,
`Search Volume`.

> Column names may differ slightly on export. The ingest script must map by
> **header name, never by position.**

## 4. Stages

| Stage | Name | Script | MVP |
|-------|------|--------|-----|
| 1 | Data Ingestion & Filtering | `scripts/ingest.py` | ✅ |
| 2 | URL & Intent Classification | `scripts/classify.py` | ✅ |
| 3 | Visual Dashboard | `scripts/dashboard.py` | ✅ |
| 4 | RAG + AI Copy Remediation | (deferred) | ⏸️ |

### Stage 1 — Ingestion & Filtering

Load the Semrush CSV with pandas. Apply the Signal-vs-Noise logic:

- **Discard** rows where `Position (End) > 30` (noise floor).
- **Priority flag** rows where `Traffic Risk > 10` **AND**
  `Best Ranked URL Changes >= 3`.
- **True-cannibalization isolate:** keep rows where
  `Best Ranking URLs (Count) > 1`.
- **Strategy router** (helper column `strategy`):
  - `All Ranking URLs (Count) == 2` → `content_fix`
  - `All Ranking URLs (Count) >= 3` → `structural` (canonical/redirect)

Write the filtered, flagged frame to `data/processed/filtered.csv`.

### Stage 2 — URL & Intent Classification

Classify each competing URL by regex pattern (documented in
`reference/url-patterns.md`):

- URL contains `/blog/` or `/article/` → **Blog**
- category `.html` catalog page → **PLP**
- product-specific page → **PDP**

For each keyword, tag the cannibalization event with its combination
(e.g. `Blog_vs_PLP`). Write to `data/processed/classified.csv`.

### Stage 3 — Visual Dashboard

Output a **single self-contained `output/dashboard.html`** (plotly, no server)
containing:

- **Pie chart** — cannibalized vs stable share of tracked keywords.
- **Bar chart** — total Traffic Risk broken down by page-type pair.
- **Data table** — prioritised keyword list sorted by `Traffic Risk` descending,
  showing `Keyword`, combination, `Traffic Risk`, `Position (End)`, `strategy`.

Default view filters to `Blog_vs_PLP`; combination is switchable.

## 5. Folder structure

```
cannibalization-engine/
├── .claude/settings.json
├── CLAUDE.md
├── SPEC.md
├── requirements.txt
├── .gitignore
├── data/
│   ├── raw/         # Semrush exports
│   └── processed/   # filtered + classified output
├── scripts/
│   ├── ingest.py
│   ├── classify.py
│   └── dashboard.py
├── reference/
│   └── url-patterns.md
└── output/
    └── dashboard.html
```

## 6. Environment

- Python 3 in a `.venv`.
- Dependencies: `pandas`, `openpyxl`, `plotly`.
- No ChromaDB / OpenAI / Anthropic packages in MVP (those belong to Stage 4).

## 7. Deferred — Stage 4 (Remediation)

Reuses an existing ChromaDB retrieval foundation. For a high-risk pair, pull
both competing pages' content, evaluate intent (informational vs transactional),
and generate targeted copy edits that keep the blog informational and reinforce
the PLP's transactional authority. **Out of MVP scope.**

**Routing pre-check (hard rule):** Before any blog is proposed for optimization, check blog-edit-history (master xlsx in `EDIT_HISTORY_DIR`). Any page already listed there is excluded as a candidate, whatever its status, and the next candidate is used instead. Re-proposing a listed page requires the user to add it to EXCLUSION_OVERRIDES in scripts/route_worklist.py. This check is enforced in code in route_worklist.py. Matching is on the URL slug (last path segment), so full URLs, `/blog/post/` paths and bare slugs all match.

## 8. Definition of done (MVP)

Running the three scripts in order against a real Semrush export produces:

1. `data/processed/filtered.csv` with helper columns and flags.
2. `data/processed/classified.csv` with a combination tag per keyword.
3. `output/dashboard.html` that opens in a browser and shows the three visuals,
   defaulting to Blogs vs PLPs.
