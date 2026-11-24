"""Build an interactive sales dashboard from the cleaned dataset.

Usage:
    python dashboard.py output/clean_sales.csv output/dashboard.html

Rows flagged as price outliers or with a quantity/price missing are excluded
from the revenue figures; EGP rows are excluded from USD totals (no exchange
rate is assumed). Their counts are shown on the dashboard so nothing is hidden.
"""
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

PALETTE = ["#2E6FD8", "#F28C28", "#2BA84A", "#9B59B6", "#E04F5F", "#17A2B8"]
TEMPLATE = "plotly_white"
REGION_COLORS = {"Cairo": "#2E6FD8", "Giza": "#F28C28", "Alexandria": "#2BA84A"}


def load(path):
    df = pd.read_csv(path)
    df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
    df["review_flag"] = df["review_flag"].fillna("")
    return df


def kpi_card(label, value, note=""):
    return (f'<div class="kpi"><div class="kv">{value}</div><div class="kl">{label}</div>'
            f'<div class="kn">{note}</div></div>')


def main(src, out):
    df = load(src)
    usable = df[(~df["review_flag"].str.contains("price_outlier"))
                & df["quantity"].notna() & df["unit_price"].notna()]
    usd = usable[usable["currency"] == "USD"].copy()
    usd["month"] = usd["order_date"].dt.to_period("M").dt.to_timestamp()

    revenue = usd["line_total"].sum()
    orders = len(usd)
    aov = revenue / orders if orders else 0
    flagged = (df["review_flag"] != "").sum()

    figs = []

    monthly = usd.groupby(["month", "region"], as_index=False)["line_total"].sum()
    f1 = px.line(monthly, x="month", y="line_total", color="region", markers=True,
                 color_discrete_map=REGION_COLORS, template=TEMPLATE,
                 labels={"line_total": "Revenue (USD)", "month": "", "region": "Region"},
                 title="Monthly revenue by region")
    figs.append(f1)

    by_product = usd.groupby("product", as_index=False)["line_total"].sum().sort_values("line_total")
    f2 = px.bar(by_product, x="line_total", y="product", orientation="h", template=TEMPLATE,
                color_discrete_sequence=[PALETTE[0]],
                labels={"line_total": "Revenue (USD)", "product": ""}, title="Revenue by product")
    figs.append(f2)

    by_region = usd.groupby("region", as_index=False)["line_total"].sum()
    f3 = px.pie(by_region, names="region", values="line_total", hole=0.55, template=TEMPLATE,
                color="region", color_discrete_map=REGION_COLORS, title="Revenue share by region")
    figs.append(f3)

    top = usd.groupby("customer_name", as_index=False)["line_total"].sum().nlargest(8, "line_total")
    f4 = px.bar(top.sort_values("line_total"), x="line_total", y="customer_name", orientation="h",
                template=TEMPLATE, color_discrete_sequence=[PALETTE[1]],
                labels={"line_total": "Revenue (USD)", "customer_name": ""}, title="Top customers")
    figs.append(f4)

    flag_counts = (df.loc[df["review_flag"] != "", "review_flag"].str.split(";").explode()
                   .str.replace(r"missing:.*", "missing value", regex=True).value_counts().reset_index())
    flag_counts.columns = ["issue", "rows"]
    f5 = px.bar(flag_counts, x="issue", y="rows", template=TEMPLATE, color_discrete_sequence=[PALETTE[4]],
                labels={"issue": "", "rows": "Rows"}, title="Data quality: rows flagged for review")
    figs.append(f5)

    for f in figs:
        f.update_layout(margin=dict(l=20, r=20, t=50, b=20), height=340,
                        font=dict(family="Inter, Arial", size=13), title_font_size=16)

    cards = "".join([
        kpi_card("Revenue (USD)", f"${revenue:,.0f}", "excl. outliers & EGP rows"),
        kpi_card("Orders", f"{orders}", "clean USD orders"),
        kpi_card("Avg order value", f"${aov:,.0f}"),
        kpi_card("Rows flagged", f"{flagged}", f"of {len(df)} for review"),
    ])
    blocks = [f.to_html(full_html=False, include_plotlyjs=("cdn" if i == 0 else False))
              for i, f in enumerate(figs)]
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Sales Dashboard</title>
<style>
body{{font-family:Inter,Arial,sans-serif;background:#f5f7fa;margin:0;color:#1f2937}}
header{{padding:28px 40px 10px}} h1{{margin:0;font-size:28px}} .sub{{color:#6b7280;margin-top:4px}}
.kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:16px 40px}}
.kpi{{background:#fff;border-radius:12px;padding:18px 20px;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
.kv{{font-size:30px;font-weight:700;color:#2E6FD8}} .kl{{font-weight:600;margin-top:4px}} .kn{{color:#6b7280;font-size:13px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:0 40px 40px}}
.card{{background:#fff;border-radius:12px;padding:8px;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
.wide{{grid-column:1 / span 2}}
</style></head><body>
<header><h1>Sales Dashboard</h1><div class="sub">Built from the cleaned dataset · Python + Plotly · hover for details, click legend items to filter</div></header>
<div class="kpis">{cards}</div>
<div class="grid">
<div class="card wide">{blocks[0]}</div>
<div class="card">{blocks[1]}</div><div class="card">{blocks[2]}</div>
<div class="card">{blocks[3]}</div><div class="card">{blocks[4]}</div>
</div></body></html>"""
    Path(out).write_text(html, encoding="utf-8")
    print(f"Wrote {out}: revenue ${revenue:,.0f}, {orders} orders, {flagged} flagged rows")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "output/clean_sales.csv",
         sys.argv[2] if len(sys.argv) > 2 else "output/dashboard.html")
