import html
import json
import os
import sys
from urllib.parse import urlsplit

import pandas as pd
import plotly.graph_objects as go
import plotly.offline as pyo

MONTH_LABEL = "Sample Month"

INPUT_CSV_PATH = "data/processed/enriched.csv"
OUTPUT_HTML_PATH = "output/dashboard.html"
BRIEFS_PATH = "reference/remediation-briefs.json"

COLOR_PRIMARY = "#1e293b"
COLOR_ACCENT = "#4f46e5"
COLOR_ACCENT_LIGHT = "#a5b4fc"
COLOR_PAGE_BG = "#f1f5f9"
COLOR_CARD_BG = "#fff"
COLOR_TEXT = "#0f172a"
COLOR_MUTED = "#64748b"

COLOR_BLOG = COLOR_PRIMARY
COLOR_PLP = COLOR_ACCENT
COLOR_PDP = COLOR_ACCENT_LIGHT
PAGE_TYPE_COLORS = {"blog": COLOR_BLOG, "plp": COLOR_PLP, "pdp": COLOR_PDP}
PAGE_TYPE_LABELS = {"blog": "Blog", "plp": "PLP", "pdp": "PDP"}
SCOPED_PAGE_TYPES = ["blog", "plp", "pdp"]
STRATEGY_LABELS = {"structural": "Structural", "content_fix": "Content fix"}
ROUTE_STYLES = {
    "refocus": ("REFOCUS", COLOR_ACCENT, "rgba(165,180,252,0.25)"),
    "strengthen": ("STRENGTHEN", "#059669", "#d1fae5"),
}

HEADER_GRADIENT = "linear-gradient(100deg,#0f172a 0%,#1e293b 55%,#4f46e5 100%)"

MIN_OUTPUT_BYTES = 500 * 1024


def url_path_only(url: str) -> str:
    path = urlsplit(str(url)).path
    return path if path else str(url)


def build_donut_chart(scoped: pd.DataFrame) -> go.Figure:
    counts = scoped["page_type"].value_counts()
    counts = counts.reindex([pt for pt in SCOPED_PAGE_TYPES if pt in counts.index])
    labels = [PAGE_TYPE_LABELS[pt] for pt in counts.index]
    colors = [PAGE_TYPE_COLORS[pt] for pt in counts.index]

    fig = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=counts.values,
                hole=0.5,
                marker=dict(colors=colors, line=dict(color=COLOR_CARD_BG, width=2)),
                textinfo="label+percent",
                textposition="outside",
                sort=False,
            )
        ]
    )
    fig.update_layout(
        margin=dict(l=20, r=20, t=20, b=20),
        showlegend=True,
        font=dict(family="Inter, sans-serif", color=COLOR_TEXT),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def build_bar_chart(scoped: pd.DataFrame) -> go.Figure:
    sums = scoped.groupby("page_type")["traffic_risk"].sum().sort_values(ascending=True)
    labels = [PAGE_TYPE_LABELS[pt] for pt in sums.index]
    colors = [PAGE_TYPE_COLORS[pt] for pt in sums.index]

    fig = go.Figure(
        data=[
            go.Bar(
                x=sums.values,
                y=labels,
                orientation="h",
                marker=dict(color=colors),
                text=[f"{v:,.0f}" for v in sums.values],
                textposition="outside",
            )
        ]
    )
    fig.update_layout(
        margin=dict(l=20, r=40, t=20, b=20),
        showlegend=False,
        font=dict(family="Inter, sans-serif", color=COLOR_TEXT),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(title="Traffic Risk", gridcolor="#e2e8f0"),
        yaxis=dict(title=""),
    )
    return fig


def build_table_rows(scoped: pd.DataFrame) -> str:
    ordered = scoped.sort_values("traffic_risk", ascending=False, na_position="last")
    rows = []
    for _, row in ordered.iterrows():
        priority_yes = bool(row["priority"])
        badge_class = "badge-yes" if priority_yes else "badge-no"
        badge_text = "Yes" if priority_yes else "No"
        row_class = "row-priority" if priority_yes else ""
        path_only = url_path_only(row["best_url_end"])
        traffic_risk_text = "—" if pd.isna(row["traffic_risk"]) else f'{row["traffic_risk"]:.1f}'
        strategy_text = STRATEGY_LABELS.get(row["strategy"], row["strategy"])

        if pd.isna(row["challenger_url"]):
            challenger_url_html = "—"
        else:
            challenger_path_only = url_path_only(row["challenger_url"])
            challenger_url_html = (
                f'<a href="{row["challenger_url"]}" target="_blank" rel="noopener">{challenger_path_only}</a>'
            )
        challenger_type_text = (
            "—"
            if pd.isna(row["challenger_page_type"])
            else PAGE_TYPE_LABELS.get(row["challenger_page_type"], row["challenger_page_type"])
        )
        competitor_count_text = "—" if pd.isna(row["competitor_count"]) else f'{int(row["competitor_count"])}'

        rows.append(
            f'<tr class="{row_class}">'
            f'<td>{row["keyword"]}</td>'
            f'<td>{PAGE_TYPE_LABELS.get(row["page_type"], row["page_type"])}</td>'
            f'<td><a href="{row["best_url_end"]}" target="_blank" rel="noopener">{path_only}</a></td>'
            f'<td>{challenger_url_html}</td>'
            f'<td>{challenger_type_text}</td>'
            f'<td>{competitor_count_text}</td>'
            f'<td>{traffic_risk_text}</td>'
            f'<td>{row["volatility"]:.2f}</td>'
            f'<td>{row["position_end"]:.0f}</td>'
            f'<td>{row["all_ranking_urls_count"]:.0f}</td>'
            f'<td><span class="badge {badge_class}">{badge_text}</span></td>'
            f'<td>{strategy_text}</td>'
            f"</tr>"
        )
    return "\n".join(rows)


def load_briefs() -> list:
    with open(BRIEFS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return sorted(data["briefs"], key=lambda b: b["rank"])


def link_html(url: str, text: str) -> str:
    return f'<a href="{html.escape(url, quote=True)}" target="_blank" rel="noopener">{html.escape(text)}</a>'


def action_button(url: str, label: str, pending_label: str, primary: bool) -> str:
    if not url:
        return f'<span class="btn btn-disabled">{pending_label}</span>'
    css = "btn btn-primary" if primary else "btn btn-secondary"
    return f'<a class="{css}" href="{html.escape(url, quote=True)}" target="_blank" rel="noopener">{label}</a>'


def build_priority_card(brief: dict, is_open: bool) -> str:
    route_label, route_fg, route_bg = ROUTE_STYLES[brief["route"]]
    new_kw = html.escape(brief["new_focus_kw"])
    if brief["route"] == "refocus":
        focus_kw_html = f'{html.escape(brief["old_focus_kw"])} &rarr; <strong>{new_kw}</strong>'
    else:
        focus_kw_html = f"<strong>{new_kw}</strong>"
    commercial_type = PAGE_TYPE_LABELS.get(brief["commercial_page_type"], brief["commercial_page_type"])
    entities_html = "".join(f'<span class="chip">{html.escape(e)}</span>' for e in brief["entities"])
    fan_outs_html = "".join(f"<li>{html.escape(q)}</li>" for q in brief["fan_outs"])
    docx_btn = action_button(brief.get("docx_link", ""), "Open edit doc", "Edit doc: link pending", True)
    semji_btn = action_button(brief.get("semji_link", ""), "View in Semji", "Semji: link pending", False)
    open_attr = " open" if is_open else ""

    return f"""<details class="priority-card"{open_attr}>
      <summary>
        <span class="pc-title">{new_kw}</span>
        <span class="route-badge" style="color:{route_fg};background:{route_bg};">{route_label}</span>
        <span class="pc-risk">risk {brief["traffic_risk"]:.1f}</span>
      </summary>
      <div class="pc-body">
        <div class="pc-col">
          <h4>Pair &mdash; edit the blog</h4>
          <p class="pc-url">{link_html(brief["blog_url"], url_path_only(brief["blog_url"]))} <span class="tag tag-edit">edit this</span></p>
          <p class="pc-url">{link_html(brief["commercial_url"], url_path_only(brief["commercial_url"]))} <span class="tag-type">{commercial_type}</span> <span class="tag tag-leave">leave</span></p>
          <h4>Focus KW</h4>
          <p>{focus_kw_html}</p>
          <h4>Focus prompt</h4>
          <p>&ldquo;{html.escape(brief["focus_prompt"])}&rdquo;</p>
          <h4>Connected entities</h4>
          <p class="chips">{entities_html}</p>
        </div>
        <div class="pc-col">
          <h4>Query fan-outs ({len(brief["fan_outs"])})</h4>
          <ol class="fan-outs">{fan_outs_html}</ol>
          <div class="pc-buttons">{docx_btn}{semji_btn}</div>
        </div>
      </div>
    </details>"""


def build_priority_section(briefs: list) -> str:
    cards = "\n    ".join(build_priority_card(b, is_open=(i == 0)) for i, b in enumerate(briefs))
    return f"""<div class="priority-section">
    <h2>Priority Actions &mdash; {MONTH_LABEL}</h2>
    <p class="section-sub">{len(briefs)} cannibalization pairs to remediate this cycle &middot; click a card to expand</p>
    {cards}
  </div>"""


def build_html(
    scoped: pd.DataFrame,
    excluded_count: int,
    donut_html: str,
    bar_html: str,
    plotly_js: str,
    briefs: list,
) -> str:
    scoped_count = len(scoped)
    priority_html = build_priority_section(briefs)
    traffic_at_risk = f"{scoped['traffic_risk'].sum():,.0f}"
    priority_count = int(scoped["priority"].sum())
    table_rows_html = build_table_rows(scoped)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Cannibalization Report — {MONTH_LABEL}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background: {COLOR_PAGE_BG};
    color: {COLOR_TEXT};
  }}
  .header {{
    background: {HEADER_GRADIENT};
    color: #fff;
    padding: 56px 32px;
    text-align: center;
  }}
  .header h1 {{ margin: 0 0 8px; font-size: 2.25rem; }}
  .header .subline {{ color: {COLOR_ACCENT_LIGHT}; font-size: 1rem; margin: 0; }}
  .content {{ max-width: 1200px; margin: 0 auto; padding: 32px; }}
  .kpi-row {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 20px;
    margin-bottom: 32px;
  }}
  .kpi-card {{
    background: {COLOR_CARD_BG};
    border-radius: 12px;
    padding: 24px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    text-align: center;
  }}
  .kpi-card .kpi-value {{ font-size: 2rem; font-weight: 700; color: {COLOR_PRIMARY}; }}
  .kpi-card .kpi-label {{ color: {COLOR_MUTED}; font-size: 0.875rem; margin-top: 4px; }}
  .charts-row {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
    margin-bottom: 32px;
  }}
  .chart-card {{
    background: {COLOR_CARD_BG};
    border-radius: 12px;
    padding: 16px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  }}
  .chart-card h2 {{ font-size: 1.05rem; margin: 8px 12px; }}
  .chart-card .chart-container {{ height: 340px; }}
  .priority-section {{ margin-bottom: 32px; }}
  .priority-section h2 {{ font-size: 1.25rem; margin: 0 0 4px; color: {COLOR_PRIMARY}; }}
  .priority-section .section-sub {{ color: {COLOR_MUTED}; font-size: 0.875rem; margin: 0 0 16px; }}
  .priority-card {{
    background: {COLOR_CARD_BG};
    border-radius: 12px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    margin-bottom: 12px;
  }}
  .priority-card summary {{
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 16px 20px;
    cursor: pointer;
    list-style: none;
  }}
  .priority-card summary::-webkit-details-marker {{ display: none; }}
  .priority-card summary::marker {{ content: ""; }}
  .priority-card summary::before {{
    content: "\\203A";
    flex: 0 0 30px;
    width: 30px;
    height: 30px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    background: rgba(165,180,252,0.25);
    color: {COLOR_ACCENT};
    font-size: 20px;
    font-weight: 700;
    line-height: 1;
    padding-bottom: 2px;
    transition: transform 0.2s, background 0.2s, color 0.2s;
  }}
  .priority-card[open] summary::before {{ transform: rotate(90deg); }}
  .priority-card summary {{ border-radius: 12px; transition: background 0.2s; }}
  .priority-card summary:hover {{ background: rgba(165,180,252,0.12); }}
  .priority-card summary:hover::before {{ background: {COLOR_ACCENT}; color: #fff; }}
  .priority-card summary:focus-visible {{ outline: 2px solid {COLOR_ACCENT}; outline-offset: -2px; }}
  .pc-title {{ font-weight: 600; font-size: 1rem; }}
  .route-badge {{ padding: 2px 10px; border-radius: 999px; font-size: 0.7rem; font-weight: 700; letter-spacing: 0.04em; }}
  .pc-risk {{ margin-left: auto; color: {COLOR_MUTED}; font-size: 0.875rem; font-weight: 600; }}
  .pc-body {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 32px;
    padding: 4px 20px 20px;
    border-top: 1px solid #e2e8f0;
  }}
  .pc-body h4 {{ margin: 16px 0 4px; font-size: 0.75rem; text-transform: uppercase; color: {COLOR_MUTED}; }}
  .pc-body p {{ margin: 0 0 6px; font-size: 0.9rem; }}
  .pc-url {{ word-break: break-all; }}
  .tag {{ font-size: 0.7rem; font-weight: 600; padding: 1px 8px; border-radius: 999px; white-space: nowrap; }}
  .tag-edit {{ background: {COLOR_ACCENT}; color: #fff; }}
  .tag-leave {{ background: #e2e8f0; color: {COLOR_MUTED}; }}
  .tag-type {{ font-size: 0.7rem; font-weight: 600; color: {COLOR_MUTED}; }}
  .chips {{ display: flex; flex-wrap: wrap; gap: 6px; }}
  .chip {{ background: rgba(165,180,252,0.25); color: {COLOR_PRIMARY}; font-size: 0.75rem; padding: 2px 10px; border-radius: 999px; }}
  .fan-outs {{ margin: 0; padding-left: 20px; font-size: 0.9rem; }}
  .fan-outs li {{ margin-bottom: 6px; }}
  .pc-buttons {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 20px; }}
  .btn {{ display: inline-block; padding: 8px 16px; border-radius: 8px; font-size: 0.85rem; font-weight: 600; }}
  .btn-primary {{ background: {COLOR_ACCENT}; color: #fff; }}
  .btn-secondary {{ background: {COLOR_CARD_BG}; color: {COLOR_ACCENT}; border: 1px solid {COLOR_ACCENT}; }}
  .btn-disabled {{ background: #e2e8f0; color: #94a3b8; cursor: not-allowed; }}
  .btn-primary:hover, .btn-secondary:hover {{ text-decoration: none; opacity: 0.9; }}
  @media (max-width: 800px) {{ .pc-body {{ grid-template-columns: 1fr; gap: 0; }} }}
  .table-card {{
    background: {COLOR_CARD_BG};
    border-radius: 12px;
    padding: 8px 16px 16px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    overflow-x: auto;
  }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.875rem; }}
  th, td {{ text-align: left; padding: 10px 12px; border-bottom: 1px solid #e2e8f0; }}
  th {{ color: {COLOR_MUTED}; font-weight: 600; text-transform: uppercase; font-size: 0.75rem; }}
  tr.row-priority {{ background: rgba(184, 136, 239, 0.12); }}
  a {{ color: {COLOR_ACCENT}; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .badge {{
    display: inline-block;
    padding: 2px 10px;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 600;
  }}
  .badge-yes {{ background: {COLOR_ACCENT}; color: #fff; }}
  .badge-no {{ background: #e2e8f0; color: {COLOR_MUTED}; }}
  .footnote {{ font-style: italic; color: {COLOR_MUTED}; font-size: 0.875rem; margin-top: 20px; }}
  .footer {{
    background: {COLOR_PRIMARY};
    color: {COLOR_ACCENT_LIGHT};
    padding: 32px;
    text-align: center;
    margin-top: 32px;
  }}
  .footer .caption {{ font-size: 0.875rem; margin: 0; }}
</style>
<script>{plotly_js}</script>
</head>
<body>

<div class="header">
  <h1>Cannibalization Report</h1>
  <p class="subline">{MONTH_LABEL} &middot; ecomusa.example</p>
</div>

<div class="content">

  <div class="kpi-row">
    <div class="kpi-card">
      <div class="kpi-value">{scoped_count}</div>
      <div class="kpi-label">Cannibalized Keywords</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-value">{traffic_at_risk}</div>
      <div class="kpi-label">Traffic at Risk</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-value">{priority_count}</div>
      <div class="kpi-label">Priority Keywords</div>
    </div>
  </div>

  <div class="charts-row">
    <div class="chart-card">
      <h2>Keyword Share by Page Type</h2>
      <div class="chart-container">{donut_html}</div>
    </div>
    <div class="chart-card">
      <h2>Traffic Risk by Page Type</h2>
      <div class="chart-container">{bar_html}</div>
    </div>
  </div>

  {priority_html}

  <div class="table-card">
    <table>
      <thead>
        <tr>
          <th>Keyword</th>
          <th>Page Type</th>
          <th>Best URL</th>
          <th>Challenger URL</th>
          <th>Challenger Type</th>
          <th>Competitors</th>
          <th>Traffic Risk</th>
          <th>Volatility</th>
          <th>Position</th>
          <th>Ranking URLs</th>
          <th>Priority</th>
          <th>Strategy</th>
        </tr>
      </thead>
      <tbody>
        {table_rows_html}
      </tbody>
    </table>
  </div>

  <p class="footnote">{excluded_count} keywords excluded (unclassified or out-of-scope).</p>

</div>

<div class="footer">
  <p class="caption">Cannibalization Report — {MONTH_LABEL}</p>
</div>

</body>
</html>
"""


def main() -> None:
    df = pd.read_csv(INPUT_CSV_PATH)
    excluded_count = int((df["page_type"] == "unknown").sum())
    scoped = df[df["page_type"].isin(SCOPED_PAGE_TYPES)].copy()

    donut_fig = build_donut_chart(scoped)
    bar_fig = build_bar_chart(scoped)

    plotly_js = pyo.get_plotlyjs()
    donut_html = donut_fig.to_html(include_plotlyjs=False, full_html=False)
    bar_html = bar_fig.to_html(include_plotlyjs=False, full_html=False)

    html = build_html(
        scoped,
        excluded_count,
        donut_html,
        bar_html,
        plotly_js,
        load_briefs(),
    )

    os.makedirs(os.path.dirname(OUTPUT_HTML_PATH), exist_ok=True)
    with open(OUTPUT_HTML_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    file_size = os.path.getsize(OUTPUT_HTML_PATH)

    print(f"Scoped rows: {len(scoped)}")
    print(f"Excluded (unknown) rows: {excluded_count}")
    print(f"Output file: {OUTPUT_HTML_PATH} ({file_size:,} bytes)")
    if file_size <= MIN_OUTPUT_BYTES:
        print(
            f"WARNING: output file is only {file_size:,} bytes (expected > {MIN_OUTPUT_BYTES:,}); "
            "plotly JS may not have been inlined correctly.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
