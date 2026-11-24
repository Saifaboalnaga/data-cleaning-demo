"""Clean a messy sales dataset and produce a clean file plus a changelog.

Usage:
    python clean_data.py data/raw_sales.csv output/

Rules applied (agreed up front, nothing valid is overwritten):
  - Trim whitespace and normalize case in text columns
  - Map region aliases to one canonical name
  - Parse mixed date formats into ISO 8601 (YYYY-MM-DD)
  - Strip currency symbols/codes and thousands separators from prices,
    keeping the detected currency in its own column (EGP rows are flagged, never converted silently)
  - Invalid quantities (non-numeric or <= 0) are set to empty and flagged
  - Prices above the outlier threshold are flagged, not deleted
  - Exact duplicates removed; same invoice_id kept once (first occurrence)
  - Rows with missing required fields are kept and flagged for review
"""
import re
import sys
from pathlib import Path

import pandas as pd

REGION_ALIASES = {"alex": "Alexandria", "alexandria": "Alexandria", "cairo": "Cairo", "giza": "Giza"}
DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%m-%d-%Y", "%d %b %Y"]
PRICE_OUTLIER = 10_000
REQUIRED = ["invoice_id", "order_date", "customer_name", "product", "region", "quantity", "unit_price"]

log = []


def note(step, count, detail):
    log.append({"step": step, "rows_affected": int(count), "detail": detail})


def parse_date(value):
    if pd.isna(value) or str(value).strip() == "":
        return pd.NaT
    for fmt in DATE_FORMATS:
        try:
            return pd.to_datetime(str(value).strip(), format=fmt)
        except ValueError:
            continue
    return pd.NaT


def parse_price(value):
    if pd.isna(value):
        return None
    cleaned = re.sub(r"[^0-9.]", "", str(value).replace(",", ""))
    try:
        return round(float(cleaned), 2)
    except ValueError:
        return None


def main(src, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(src, dtype=str, keep_default_na=False)
    start_rows = len(df)
    note("load", start_rows, f"Loaded {start_rows} rows from {src}")

    # 1. whitespace and case
    for col in ["customer_name", "product", "region"]:
        before = df[col].copy()
        df[col] = df[col].str.strip().str.replace(r"\s+", " ", regex=True).str.title()
        note("normalize_text", (before != df[col]).sum(), f"Trimmed/normalized case in '{col}'")

    # 2. region aliases
    before = df["region"].copy()
    df["region"] = df["region"].apply(lambda r: REGION_ALIASES.get(r.lower(), r) if r else r)
    note("region_aliases", (before != df["region"]).sum(), "Mapped region aliases to canonical names")

    # 3. dates
    parsed = df["order_date"].apply(parse_date)
    bad_dates = parsed.isna() & (df["order_date"].str.strip() != "")
    df["order_date"] = parsed.dt.strftime("%Y-%m-%d").fillna("")
    note("dates", (~parsed.isna()).sum(), "Converted mixed date formats to YYYY-MM-DD")
    note("dates_unparseable", bad_dates.sum(), "Dates that could not be parsed (flagged)")

    # 4. prices: detect currency first so EGP values are never silently treated as USD
    df["currency"] = df["unit_price"].apply(lambda v: "EGP" if "EGP" in str(v).upper() else "USD")
    df["unit_price"] = df["unit_price"].apply(parse_price)
    note("prices", df["unit_price"].notna().sum(), "Removed currency symbols/codes and separators")
    note("currency_egp", (df["currency"] == "EGP").sum(), "Prices in EGP kept in a separate currency column (no conversion applied)")

    # 5. quantities
    qty = pd.to_numeric(df["quantity"], errors="coerce")
    invalid_qty = qty.isna() & (df["quantity"].str.strip() != "") | (qty <= 0)
    df["quantity"] = qty.where(qty > 0).astype("Int64")
    note("quantity_invalid", invalid_qty.sum(), "Non-numeric or non-positive quantities set empty and flagged")

    # 6. duplicates
    before = len(df)
    df = df.drop_duplicates()
    note("exact_duplicates", before - len(df), "Removed exact duplicate rows")
    before = len(df)
    df = df.drop_duplicates(subset="invoice_id", keep="first")
    note("duplicate_invoice_id", before - len(df), "Removed repeated invoice_id (kept first occurrence)")

    # 7. flags
    flags = []
    for _, row in df.iterrows():
        f = []
        missing = [c for c in REQUIRED if pd.isna(row[c]) or str(row[c]).strip() == ""]
        if missing:
            f.append("missing:" + "|".join(missing))
        if pd.notna(row["unit_price"]) and row["unit_price"] > PRICE_OUTLIER:
            f.append("price_outlier")
        if row["currency"] != "USD":
            f.append("currency_needs_confirmation")
        flags.append(";".join(f))
    df["review_flag"] = flags
    note("flags", (df["review_flag"] != "").sum(), "Rows flagged for review (missing values or outliers)")

    df["line_total"] = (df["quantity"].astype("Float64") * df["unit_price"]).round(2)
    df = df.sort_values("invoice_id").reset_index(drop=True)

    # integrity checks
    assert df["invoice_id"].is_unique, "invoice_id must be unique after cleaning"
    assert df["order_date"].str.match(r"^(\d{4}-\d{2}-\d{2})?$").all(), "dates must be ISO or empty"
    note("integrity", len(df), f"Final rows: {len(df)} (from {start_rows}); invoice_id unique; dates ISO")

    df.to_csv(out_dir / "clean_sales.csv", index=False)
    with pd.ExcelWriter(out_dir / "clean_sales.xlsx") as xw:
        df.to_excel(xw, sheet_name="clean_data", index=False)
        pd.DataFrame(log).to_excel(xw, sheet_name="changelog", index=False)
    pd.DataFrame(log).to_csv(out_dir / "changelog.csv", index=False)
    print(pd.DataFrame(log).to_string(index=False))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data/raw_sales.csv",
         sys.argv[2] if len(sys.argv) > 2 else "output")
