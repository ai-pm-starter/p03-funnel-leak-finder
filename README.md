# Funnel Leak Finder

> For growth PMs: finds where an online shop's funnel leaks, for whom, and what to test next. Statistics find the leaks; Gemini writes the brief.

**Live demo:** coming in P3-09 · **PM:** Prashant · **Status:** Sprint 3, in progress

## The problem
Dashboards show that conversion is low, not where people leave, for whom, or what to try next. Finding one leak by hand takes days of slicing GA4 data. See [docs/01-problem.md](docs/01-problem.md).

## What it does
<demo GIF>

## Results
| Metric | Target | Result |
|---|---|---|
| | | |

## How it works
Architecture diagram + 3–5 bullets.

## Key product decisions
Links to `docs/decisions/`.

## Limitations & what's next

## Built with
Python · Streamlit · Google Gemini (free tier) · [Google Merchandise Store GA4 sample](https://developers.google.com/analytics/bigquery/web-ecommerce-demo-dataset) (BigQuery public dataset, obfuscated)

## Run locally
```bash
cp .env.example .env   # add your keys
pip install -r requirements.txt
streamlit run app/app.py
```
