import pandas as pd

SEMJI_CSV_PATH = "reference/semji-focus-keywords.csv"
ENRICHED_CSV_PATH = "data/processed/enriched.csv"
OUTPUT_CSV_PATH = "reference/blog-intent-classification.csv"

# Point-in-time snapshot of inline LLM judgement (illustrative keywords shown here).
MANUAL_INTENT = {
    "best cordless vacuum cleaner": "commercial",
    "how to descale a steam iron": "informational",
    "steam iron vs dry iron": "informational",
    "hepa filter": "informational, commercial",
    "best garment steamer": "commercial",
    "how to clean a fan": "informational",
}

MANUAL_OVERRIDE = {"steam iron vs dry iron"}


def lenient_final(intent: str) -> str:
    terms = {term.strip() for term in intent.split(",") if term.strip()}
    return "informational" if "informational" in terms else "commercial"


def load_semrush_intent_map(path: str = ENRICHED_CSV_PATH) -> dict:
    enriched = pd.read_csv(path)
    enriched["keyword_norm"] = enriched["keyword"].str.strip().str.lower()
    intent = enriched["keyword_intent"].fillna("").str.strip().str.lower()
    found = enriched[intent != ""]
    return dict(zip(found["keyword_norm"], intent[intent != ""]))


def classify_row(url: str, focus_keyword: str, semrush_map: dict) -> dict:
    keyword_norm = focus_keyword.strip().lower()
    manual_intent = MANUAL_INTENT.get(keyword_norm)
    if manual_intent is None:
        raise KeyError(f"No manual judgment recorded for focus keyword: {focus_keyword!r}")

    semrush_intent = semrush_map.get(keyword_norm)
    manual_final = lenient_final(manual_intent)

    if not semrush_intent:
        return {
            "url": url,
            "focus_keyword": focus_keyword,
            "semrush_intent": "",
            "llm_intent": manual_intent,
            "final_intent": manual_final,
            "intent_source": "llm",
        }

    if keyword_norm in MANUAL_OVERRIDE:
        return {
            "url": url,
            "focus_keyword": focus_keyword,
            "semrush_intent": semrush_intent,
            "llm_intent": manual_intent,
            "final_intent": manual_final,
            "intent_source": "manual_override",
        }

    semrush_final = lenient_final(semrush_intent)
    agree = semrush_final == manual_final
    return {
        "url": url,
        "focus_keyword": focus_keyword,
        "semrush_intent": semrush_intent,
        "llm_intent": "" if agree else manual_intent,
        "final_intent": semrush_final,
        "intent_source": "semrush" if agree else "conflict",
    }


def main() -> None:
    semji = pd.read_csv(SEMJI_CSV_PATH)
    rows_in = len(semji)

    semrush_map = load_semrush_intent_map()

    records = [
        classify_row(row["URL"], row["Focus Keyword"], semrush_map)
        for _, row in semji.iterrows()
    ]
    result = pd.DataFrame.from_records(records)

    result.to_csv(OUTPUT_CSV_PATH, index=False)

    written_rows = len(pd.read_csv(OUTPUT_CSV_PATH))
    assert written_rows == rows_in, (
        f"On-disk row count ({written_rows}) does not match input row count ({rows_in})"
    )

    print(f"Rows in: {rows_in} (verified on disk: {written_rows})")
    print(f"Final intent breakdown: {result['final_intent'].value_counts().to_dict()}")
    print(f"Intent source breakdown: {result['intent_source'].value_counts().to_dict()}")

    conflicts = result[result["intent_source"] == "conflict"]
    if conflicts.empty:
        print("Conflicts: none")
    else:
        print("Conflicts:")
        for _, row in conflicts.iterrows():
            print(
                f"  {row['url']} | {row['focus_keyword']!r} "
                f"| semrush={row['semrush_intent']!r} vs llm={row['llm_intent']!r}"
            )


if __name__ == "__main__":
    main()
