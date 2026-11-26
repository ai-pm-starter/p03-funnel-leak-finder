"""Rebuild data/funnel_daily.csv from BigQuery (P3-03). Laptop only; the app just reads the CSV.

Needs: pip install -r requirements-data.txt, `gcloud auth application-default login`, and GCP_PROJECT in .env.
Usage: python scripts/build_data.py
"""
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from google.cloud import bigquery

ROOT = Path(__file__).resolve().parent.parent
TOP_COUNTRIES = 10   # by sessions; the rest become "Other" so the table stays small and segments stay big enough

load_dotenv(ROOT / ".env")
client = bigquery.Client(project=os.environ["GCP_PROJECT"])
sql = (ROOT / "sql" / "funnel_daily.sql").read_text()

job = client.query(sql)
df = job.to_dataframe()
print(f"BigQuery scanned {job.total_bytes_processed / 1e9:.2f} GB, {len(df):,} rows")

top = df.groupby("country")["sessions"].sum().nlargest(TOP_COUNTRIES).index
df["country"] = df["country"].where(df["country"].isin(top), "Other")
df["country"] = df["country"].replace({"(not set)": "Other"})
keys = ["day", "device", "country", "channel", "visitor"]
df = df.groupby(keys, as_index=False).sum(numeric_only=True).sort_values(keys)
df["revenue_usd"] = df["revenue_usd"].round(2)

out = ROOT / "data" / "funnel_daily.csv"
df.to_csv(out, index=False)
print(f"Wrote {out.relative_to(ROOT)}: {len(df):,} rows, {out.stat().st_size / 1e6:.1f} MB")
print(df[["sessions", "view_item", "add_to_cart", "begin_checkout", "add_shipping_info",
          "add_payment_info", "purchase", "purchase_events", "revenue_usd"]].sum().to_string())
