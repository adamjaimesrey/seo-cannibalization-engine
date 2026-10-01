import re

import pandas as pd

RAW_CSV_PATH = "data/raw/semrush-cannibalization-YYYY-MM.csv"
PROCESSED_CSV_PATH = "data/processed/filtered.csv"

COLUMN_MAP = {
    "keyword": "Keyword",
    "best_url_end": "Best URL (End)",
    "position_end": "Position (End)",
    "all_ranking_urls_count": "All Ranking URLs (Count)",
    "best_ranking_urls_count": "Best Ranking URLs (Count)",
    "avg_position_best_ranking": "Avg. Position (Best Ranking)",
    "best_ranked_url_changes": "Best ranked URL changes (Change)",
    "best_traffic": "Best Traffic",
    "lowest_traffic": "Lowest Traffic",
    "traffic_risk": "Traffic Risk",
    "search_volume": "Search Volume",
}

OPTIONAL_COLUMN_MAP = {
    "position_delta": "Position Delta (Average to End)",
    "volatility": "Volatility (Start to End)",
}


def normalize_headers(df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(columns=lambda col: re.sub(r"\s+", " ", col.strip()))


def validate_columns(df: pd.DataFrame) -> None:
    missing = [header for header in COLUMN_MAP.values() if header not in df.columns]
    if missing:
        raise ValueError(
            f"Missing expected columns in {RAW_CSV_PATH}: {missing}. "
            f"Columns found: {list(df.columns)}"
        )


def rename_optional_columns(df: pd.DataFrame) -> pd.DataFrame:
    present = {
        csv_header: clean_name
        for clean_name, csv_header in OPTIONAL_COLUMN_MAP.items()
        if csv_header in df.columns
    }
    return df.rename(columns=present)


def load_and_map(path: str = RAW_CSV_PATH) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = normalize_headers(df)
    validate_columns(df)
    df = df.rename(columns={csv_header: clean_name for clean_name, csv_header in COLUMN_MAP.items()})
    df = rename_optional_columns(df)
    return df


def filter_and_flag(df: pd.DataFrame) -> pd.DataFrame:
    df = df[df["position_end"] <= 30]
    df = df[df["best_ranking_urls_count"] > 1].copy()

    df["priority"] = (df["traffic_risk"] > 10) & (df["best_ranked_url_changes"] >= 3)

    df.loc[df["all_ranking_urls_count"] == 2, "strategy"] = "content_fix"
    df.loc[df["all_ranking_urls_count"] >= 3, "strategy"] = "structural"

    return df


def main() -> None:
    df = load_and_map()
    rows_in = len(df)

    noise_filtered = df[df["position_end"] <= 30]
    rows_discarded_noise = rows_in - len(noise_filtered)

    filtered = filter_and_flag(df)
    rows_kept = len(filtered)

    filtered.to_csv(PROCESSED_CSV_PATH, index=False)

    written_rows = len(pd.read_csv(PROCESSED_CSV_PATH))
    assert written_rows == rows_kept, (
        f"On-disk row count ({written_rows}) does not match in-memory rows kept ({rows_kept})"
    )

    priority_count = int(filtered["priority"].sum())
    strategy_counts = filtered["strategy"].value_counts()

    print(f"Rows in: {rows_in}")
    print(f"Discarded by noise floor (position_end > 30): {rows_discarded_noise}")
    print(f"Rows kept: {rows_kept} (verified on disk: {written_rows})")
    print(f"Flagged priority: {priority_count}")
    print(f"Strategy breakdown: {strategy_counts.to_dict()}")


if __name__ == "__main__":
    main()
