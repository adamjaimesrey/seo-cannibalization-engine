import pandas as pd

from classify import load_page_type_map, normalize_url
from ingest import normalize_headers

POSITIONS_CSV_PATH = "data/raw/semrush-positions-YYYY-MM.csv"
INPUT_CSV_PATH = "data/processed/classified.csv"
OUTPUT_CSV_PATH = "data/processed/enriched.csv"

MAX_CHALLENGER_POSITION = 20

POSITIONS_COLUMN_MAP = {
    "keyword": "Keyword",
    "url": "URL",
    "position": "Position",
    "traffic": "Traffic",
    "position_type": "Position Type",
    "keyword_intent": "Keyword Intents",
}

BLOG_COMMERCIAL_PAIRS = ({"blog", "plp"}, {"blog", "pdp"})


def validate_positions_columns(df: pd.DataFrame) -> None:
    missing = [header for header in POSITIONS_COLUMN_MAP.values() if header not in df.columns]
    if missing:
        raise ValueError(
            f"Missing expected columns in {POSITIONS_CSV_PATH}: {missing}. "
            f"Columns found: {list(df.columns)}"
        )


def load_positions(path: str = POSITIONS_CSV_PATH) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = normalize_headers(df)
    validate_positions_columns(df)
    df = df.rename(columns={csv_header: clean for clean, csv_header in POSITIONS_COLUMN_MAP.items()})
    return df[list(POSITIONS_COLUMN_MAP.keys())]


def filter_organic(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["position_type"] == "Organic"].copy()


def dedup_positions(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values("position", kind="mergesort")
    return df.drop_duplicates(subset=["keyword", "url"], keep="first").copy()


def tier_for_pair(winner_page_type: str, challenger_page_type: str) -> int:
    pair = {winner_page_type, challenger_page_type}
    if "unknown" in pair:
        return 1
    return 0 if pair in BLOG_COMMERCIAL_PAIRS else 1


def enrich_keyword(
    group: pd.DataFrame | None,
    winner_url_norm: str,
    winner_page_type: str,
    page_type_map: dict,
) -> dict:
    result = {
        "challenger_url": None,
        "challenger_page_type": None,
        "challenger_position": None,
        "challenger_traffic": None,
        "competitor_count": 0,
        "keyword_intent": None,
    }
    if group is None or group.empty:
        return result

    group = group.copy()
    group["url_norm"] = group["url"].map(normalize_url)

    result["competitor_count"] = int(group["url_norm"].nunique())

    winner_rows = group[group["url_norm"] == winner_url_norm]
    source_row = winner_rows.iloc[0] if not winner_rows.empty else group.iloc[0]
    result["keyword_intent"] = source_row["keyword_intent"]

    challengers = group[group["url_norm"] != winner_url_norm]
    challengers = challengers[challengers["position"] <= MAX_CHALLENGER_POSITION]
    if challengers.empty:
        return result

    challengers = challengers.copy()
    challengers["page_type"] = challengers["url_norm"].map(
        lambda u: page_type_map.get(u, "unknown")
    )
    challengers["tier"] = challengers["page_type"].map(
        lambda pt: tier_for_pair(winner_page_type, pt)
    )
    challengers = challengers.sort_values(
        ["tier", "position", "traffic"], ascending=[True, True, False], kind="mergesort"
    )
    top = challengers.iloc[0]
    result["challenger_url"] = top["url"]
    result["challenger_page_type"] = top["page_type"]
    result["challenger_position"] = top["position"]
    result["challenger_traffic"] = top["traffic"]
    return result


def enrich_all(
    classified: pd.DataFrame,
    positions: pd.DataFrame,
    page_type_map: dict,
) -> pd.DataFrame:
    classified = classified.copy()
    classified["keyword_norm"] = classified["keyword"].str.strip().str.lower()
    classified["winner_url_norm"] = classified["best_url_end"].map(normalize_url)

    groups = dict(tuple(positions.groupby("keyword_norm")))

    records = [
        enrich_keyword(
            groups.get(row.keyword_norm),
            row.winner_url_norm,
            row.page_type,
            page_type_map,
        )
        for row in classified.itertuples()
    ]

    enrichment = pd.DataFrame.from_records(records, index=classified.index)
    return pd.concat(
        [classified.drop(columns=["keyword_norm", "winner_url_norm"]), enrichment],
        axis=1,
    )


def main() -> None:
    classified = pd.read_csv(INPUT_CSV_PATH)
    rows_in = len(classified)

    positions = load_positions()
    organic = filter_organic(positions)
    deduped = dedup_positions(organic)
    deduped["keyword_norm"] = deduped["keyword"].str.strip().str.lower()

    page_type_map = load_page_type_map()

    enriched = enrich_all(classified, deduped, page_type_map)

    enriched.to_csv(OUTPUT_CSV_PATH, index=False)

    written_rows = len(pd.read_csv(OUTPUT_CSV_PATH))
    assert written_rows == rows_in, (
        f"On-disk row count ({written_rows}) does not match input row count ({rows_in})"
    )

    matched = enriched["challenger_url"].notna()
    matched_count = int(matched.sum())

    print(f"Rows in: {rows_in} (verified on disk: {written_rows})")
    print(f"Challenger found: {matched_count}")
    print(f"No challenger found: {rows_in - matched_count}")
    print(
        "Challenger page_type breakdown: "
        f"{enriched.loc[matched, 'challenger_page_type'].value_counts().to_dict()}"
    )


if __name__ == "__main__":
    main()
