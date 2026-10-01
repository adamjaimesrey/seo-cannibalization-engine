import os
from pathlib import Path

import openpyxl
import pandas as pd

from classify import normalize_url

ENRICHED_CSV_PATH = "data/processed/enriched.csv"
BLOG_INTENT_CSV_PATH = "reference/blog-intent-classification.csv"
OUTPUT_CSV_PATH = "data/processed/remediation-worklist.csv"

EDIT_HISTORY_DIR = Path(os.environ.get("EDIT_HISTORY_DIR", "data/edit-history"))
EDIT_HISTORY_PATH = EDIT_HISTORY_DIR / "blog-edit-history.xlsx"

# Slugs only. A page in the edit history is re-proposed only if its slug is added here.
EXCLUSION_OVERRIDES: set = set()

WORKLIST_SIZE = 6
COMMERCIAL_PAGE_TYPES = {"plp", "pdp"}

OUTPUT_COLUMNS = [
    "keyword",
    "blog_url",
    "blog_focus_keyword",
    "blog_intent",
    "route",
    "commercial_url",
    "commercial_page_type",
    "traffic_risk",
    "volatility",
    "priority",
    "competitor_count",
]


def is_qualifying_pair(page_type: str, challenger_page_type: str) -> bool:
    sides = {page_type, challenger_page_type}
    if "unknown" in sides:
        return False
    if "blog" not in sides:
        return False
    other = sides - {"blog"}
    return other <= COMMERCIAL_PAGE_TYPES and len(other) == 1


def pick_blog_and_commercial(row) -> dict:
    if row["page_type"] == "blog":
        return {
            "blog_url": row["best_url_end"],
            "commercial_url": row["challenger_url"],
            "commercial_page_type": row["challenger_page_type"],
        }
    return {
        "blog_url": row["challenger_url"],
        "commercial_url": row["best_url_end"],
        "commercial_page_type": row["page_type"],
    }


def filter_qualifying_pairs(enriched: pd.DataFrame) -> pd.DataFrame:
    df = enriched[enriched["challenger_url"].notna()].copy()
    qualifies = df.apply(
        lambda r: is_qualifying_pair(r["page_type"], r["challenger_page_type"]), axis=1
    )
    df = df[qualifies].copy()

    picks = df.apply(pick_blog_and_commercial, axis=1, result_type="expand")
    return pd.concat([df, picks], axis=1)


def url_slug(url) -> str:
    if url is None or (isinstance(url, float) and pd.isna(url)):
        return ""
    return normalize_url(url).rsplit("/", 1)[-1]


def load_edited_urls(path: Path = EDIT_HISTORY_PATH) -> tuple:
    """Return (slugs of every blog in the edit history, ids of rows with no usable slug)."""
    if not path.exists():
        raise FileNotFoundError(f"Blog edit history not found: {path}")

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        slugs, blank_rows = set(), []
        for ws in wb.worksheets:
            header = None
            for row in ws.iter_rows(values_only=True):
                if header is None:
                    if "edit_id" in row:
                        header = list(row)
                    continue
                if "blog_url" not in header:
                    break
                record = dict(zip(header, row))
                if not any(v not in (None, "") for v in row):
                    continue
                slug = url_slug(record["blog_url"])
                if slug:
                    slugs.add(slug)
                else:
                    blank_rows.append(record.get("edit_id") or "(no edit_id)")
            if header is not None:
                if "blog_url" not in header:
                    raise ValueError(f"No blog_url column in {path} (sheet {ws.title!r})")
                return slugs, blank_rows
    finally:
        wb.close()
    raise ValueError(f"No header row containing 'edit_id' found in {path}")


def load_blog_intent(path: str = BLOG_INTENT_CSV_PATH) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["url_norm"] = df["url"].map(normalize_url)
    return df[["url_norm", "final_intent", "focus_keyword"]].rename(
        columns={"focus_keyword": "blog_focus_keyword"}
    )


def assign_route(final_intent) -> str:
    if final_intent == "informational":
        return "strengthen"
    if final_intent == "commercial":
        return "refocus"
    return "needs_intent"


def build_worklist(
    enriched: pd.DataFrame, blog_intent: pd.DataFrame, edited_slugs: set
) -> tuple:
    qualifying = filter_qualifying_pairs(enriched)
    qualifying["url_norm"] = qualifying["blog_url"].map(normalize_url)

    excluded_mask = qualifying["blog_url"].map(url_slug).isin(edited_slugs - EXCLUSION_OVERRIDES)
    excluded = qualifying[excluded_mask]
    qualifying = qualifying[~excluded_mask].copy()

    merged = qualifying.merge(blog_intent, on="url_norm", how="left")
    merged["blog_intent"] = merged["final_intent"].fillna("unknown")
    merged["route"] = merged["final_intent"].map(assign_route)

    merged = merged.sort_values("traffic_risk", ascending=False, kind="mergesort")
    return merged[OUTPUT_COLUMNS], excluded


def main() -> None:
    enriched = pd.read_csv(ENRICHED_CSV_PATH)
    blog_intent = load_blog_intent()
    edited_slugs, blank_history_rows = load_edited_urls()

    full_worklist, excluded = build_worklist(enriched, blog_intent, edited_slugs)
    qualifying_total = len(full_worklist)

    top = full_worklist.head(WORKLIST_SIZE)
    top.to_csv(OUTPUT_CSV_PATH, index=False)

    written = pd.read_csv(OUTPUT_CSV_PATH)
    assert len(written) == len(top), (
        f"On-disk row count ({len(written)}) does not match in-memory rows ({len(top)})"
    )
    assert len(written) <= WORKLIST_SIZE, (
        f"On-disk row count ({len(written)}) exceeds worklist size ({WORKLIST_SIZE})"
    )

    excluded_urls = sorted(excluded["blog_url"].unique())
    print(f"Pairs excluded by edit history: {len(excluded)} ({len(excluded_urls)} blog URLs)")
    for url in excluded_urls:
        print(f"  - {url}")
    if blank_history_rows:
        print(f"History rows with empty/unusable blog_url: {blank_history_rows}")
    print(f"Qualifying Blog<->commercial pairs (after exclusion, before top-{WORKLIST_SIZE} cut): {qualifying_total}")
    print(f"Route breakdown (top {len(top)}): {top['route'].value_counts().to_dict()}")
    print()
    print(top[["blog_url", "route", "commercial_url", "traffic_risk"]].to_string(index=False))


if __name__ == "__main__":
    main()
