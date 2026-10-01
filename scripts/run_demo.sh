#!/usr/bin/env bash
# Run the full pipeline on the synthetic files in sample_data/.
# Copies them to the paths the scripts expect (all gitignored), then runs each stage, stopping at the first failure.
# Refuses to overwrite a differing existing file (e.g. real data) unless DEMO_FORCE=1.
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=python3; fi

export EDIT_HISTORY_DIR=data/edit-history
export PYTHONDONTWRITEBYTECODE=1

place() {
  local src="sample_data/$1" dest="$2"
  mkdir -p "$(dirname "$dest")"
  if [ -e "$dest" ] && ! cmp -s "$src" "$dest" && [ "${DEMO_FORCE:-0}" != "1" ]; then
    echo "ERROR: $dest exists and differs from $src (set DEMO_FORCE=1 to overwrite)" >&2
    exit 1
  fi
  cp "$src" "$dest"
  echo "  $src -> $dest"
}

echo "== Staging sample data"
place semrush-cannibalization-YYYY-MM.csv data/raw/semrush-cannibalization-YYYY-MM.csv
place semrush-positions-YYYY-MM.csv data/raw/semrush-positions-YYYY-MM.csv
place url-page-type-map.csv reference/url-page-type-map.csv
place semji-focus-keywords.csv reference/semji-focus-keywords.csv
place edit-lists.json reference/edit-lists.json
place remediation-briefs.json reference/remediation-briefs.json
place "blog_articles/Best Cordless Vacuum Cleaners - A Buyers Guide.txt" "reference/blog_articles/Best Cordless Vacuum Cleaners - A Buyers Guide.txt"
place "blog_articles/How to Descale a Steam Iron.txt" "reference/blog_articles/How to Descale a Steam Iron.txt"
place "blog_articles/How to Clean a Fan.txt" "reference/blog_articles/How to Clean a Fan.txt"
place edit-history/blog-edit-history.xlsx "$EDIT_HISTORY_DIR/blog-edit-history.xlsx"

run() {
  local name="$1" script="$2"
  echo
  echo "== $name"
  local log; log="$(mktemp)"
  "$PY" "scripts/$script" | tee "$log"
  # build_edit_docs reports problems in its output instead of exiting non-zero
  if grep -Eq "FAILED|OVER CAP|NO, missing" "$log"; then
    echo "ERROR: $script reported a problem (see above)" >&2
    rm -f "$log"; exit 1
  fi
  rm -f "$log"
}

require() {
  for f in "$@"; do
    [ -s "$f" ] || { echo "ERROR: expected output missing or empty: $f" >&2; exit 1; }
    echo "  -> $f"
  done
}

run "1 ingest"   ingest.py;          require data/processed/filtered.csv
run "2 classify" classify.py;        require data/processed/classified.csv
run "3 enrich"   enrich.py;          require data/processed/enriched.csv
run "4 dashboard" dashboard.py;      require output/dashboard.html
run "5 intent"   classify_intent.py; require reference/blog-intent-classification.csv
run "6 route"    route_worklist.py;  require data/processed/remediation-worklist.csv
run "7 dedupe"   dedupe_worklist.py; require data/processed/remediation-worklist-deduped.csv
run "8 build_edit_docs" build_edit_docs.py; require output/edit-lists/best-cordless-vacuum-cleaner-guide-edit-list.docx

echo
echo "Demo complete. Open output/dashboard.html in a browser."
