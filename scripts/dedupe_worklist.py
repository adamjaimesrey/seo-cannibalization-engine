import pandas as pd

INPUT = "data/processed/remediation-worklist.csv"
OUTPUT = "data/processed/remediation-worklist-deduped.csv"

df = pd.read_csv(INPUT)

agg = (
    df.sort_values("traffic_risk", ascending=False)
      .groupby(["blog_url", "commercial_url"], as_index=False)
      .agg(
          blog_focus_keyword=("blog_focus_keyword", "first"),
          blog_intent=("blog_intent", "first"),
          route=("route", "first"),
          commercial_page_type=("commercial_page_type", "first"),
          traffic_risk=("traffic_risk", "max"),
          keyword_count=("keyword", "count"),
          keywords=("keyword", lambda s: "; ".join(sorted(set(s)))),
      )
      .sort_values("traffic_risk", ascending=False)
      .reset_index(drop=True)
)

agg.to_csv(OUTPUT, index=False)

check = pd.read_csv(OUTPUT)
print(f"unique blog pairs: {len(check)}")
print(f"route split: {check['route'].value_counts().to_dict()}")
print()
print(check[["blog_focus_keyword","route","commercial_page_type","traffic_risk","keyword_count"]].to_string(index=False))
