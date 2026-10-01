import re

import pandas as pd

MAP_CSV_PATH = "reference/url-page-type-map.csv"
INPUT_CSV_PATH = "data/processed/filtered.csv"
OUTPUT_CSV_PATH = "data/processed/classified.csv"

UNKNOWN_PRINT_CAP = 50


def normalize_url(url: str) -> str:
    normalized = str(url).strip().lower()
    normalized = re.sub(r"^https?://", "", normalized)
    normalized = re.sub(r"^www\.", "", normalized)
    normalized = re.split(r"[?#]", normalized, maxsplit=1)[0]
    normalized = normalized.rstrip("/")
    return normalized


def load_page_type_map(path: str = MAP_CSV_PATH) -> dict:
    df = pd.read_csv(path)
    df["url"] = df["url"].map(normalize_url)
    df["page_type"] = df["page_type"].str.lower()

    page_type_map = {}
    for url, page_type in zip(df["url"], df["page_type"]):
        if url in page_type_map and page_type_map[url] != page_type:
            print(
                f"WARNING: conflicting page_type for normalized URL '{url}': "
                f"'{page_type_map[url]}' vs '{page_type}' (keeping first)"
            )
            continue
        page_type_map[url] = page_type

    return page_type_map


def classify(df: pd.DataFrame, page_type_map: dict) -> pd.DataFrame:
    df = df.copy()
    df["page_type"] = df["best_url_end"].map(
        lambda url: page_type_map.get(normalize_url(url), "unknown")
    )
    return df


def main() -> None:
    df = pd.read_csv(INPUT_CSV_PATH)
    rows_in = len(df)

    page_type_map = load_page_type_map()
    classified = classify(df, page_type_map)

    classified.to_csv(OUTPUT_CSV_PATH, index=False)

    written_rows = len(pd.read_csv(OUTPUT_CSV_PATH))
    assert written_rows == rows_in, (
        f"On-disk row count ({written_rows}) does not match input row count ({rows_in})"
    )

    page_type_counts = classified["page_type"].value_counts()

    print(f"Total rows: {rows_in} (verified on disk: {written_rows})")
    print(f"Page type breakdown: {page_type_counts.to_dict()}")

    unknown_urls = sorted(
        classified.loc[classified["page_type"] == "unknown", "best_url_end"].unique()
    )
    print(f"Unknown URLs: {len(unknown_urls)}")
    for url in unknown_urls[:UNKNOWN_PRINT_CAP]:
        print(f"  {url}")
    if len(unknown_urls) > UNKNOWN_PRINT_CAP:
        print(f"  ... and {len(unknown_urls) - UNKNOWN_PRINT_CAP} more")


if __name__ == "__main__":
    main()
