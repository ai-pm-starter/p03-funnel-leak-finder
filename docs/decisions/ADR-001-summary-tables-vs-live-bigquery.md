# ADR-001: The app reads summary tables from the repo, not live BigQuery

- **Date:** Nov 28, 2026 (P3-08)
- **Status:** accepted
- **Decider:** Prashant (PM)

## Context
The leak finder needs funnel counts per day and segment. The raw data is the Google Merchandise Store GA4 export in BigQuery: 4.3 M events, 92 daily tables. The app has to run as a **public demo** on Streamlit Community Cloud (P3-09), for free, with no card anywhere. Anyone with the link can open it.

So where does the app get its numbers: from BigQuery on every visit, or from tables computed once and stored with the app?

## Options considered

**A. Summary tables in the repo** (what was built in P3-03)
A script on the laptop runs one SQL query and saves `data/funnel_daily.csv` (20,874 rows, 1.3 MB). The app reads only that file.

**B. Live BigQuery from the app**
The app queries BigQuery when it starts or when the dates change, using a Google service-account key stored in Streamlit secrets.

**C. Scheduled refresh** (A, kept fresh automatically)
A scheduled job (e.g. a free GitHub Actions cron) reruns the query daily and updates the summary table. The app still reads only the table.

| Criterion | A. Tables in repo | B. Live BigQuery | C. Scheduled refresh |
|---|---|---|---|
| **Security** | No Google credentials on the public server at all | A service-account key on a public demo's server. If leaked or misused, it can run queries on the project | Key lives in the job's secrets (GitHub), not on the app server |
| **Cost and quota** | One query per rebuild (1.17 GB). The free 1 TB a month is no concern | 1.17 GB per uncached query: the free 1 TB covers about **850** loads a month. A shared link or a bot could use it up, and the sandbox then stops until next month | One query a day ≈ 35 GB a month, within the free tier |
| **Speed** (measured Nov 28) | **2.8 s** to load the CSV and find leaks, mostly first-time library loading; **0.07 s** to find leaks once loaded | **4.8 s** per query before any analysis, on every new date range unless cached | Same as A |
| **Freshness** | As fresh as the last rebuild. The sample is fixed (Nov 2020 – Jan 2021), so it never changes | Always current | Up to a day old |
| **Privacy** | Only aggregated counts per day and segment: no user IDs, no events | Raw events are queried at run time (here obfuscated and public) | Same as A |
| **Reproducibility** | The exact data the eval ran on is versioned in git next to the results | Results can shift if the source changes | Data changes daily; evals need a pinned copy |
| **Path to a real shop** | Fine for a demo; a real shop needs fresh data | Closest to how a real tool would work, but needs per-shop credentials and query cost control | **The natural next step:** each shop's own GA4 export, refreshed daily into small tables |

## Decision
**Option A for v0: the app reads summary tables committed to the repo.**

The dataset is a fixed public sample, so live queries would add risk and cost while gaining no freshness at all. Option A keeps every credential off the public server, can't burn the free quota, is faster, and makes the P3-07 eval reproducible: the eval and the app run on exactly the same versioned table.

## Consequences
**Easier**
- The public demo needs only a Gemini key in Streamlit secrets, and works without it (minus the AI brief).
- Anyone can clone the repo and run the app without a Google Cloud account.
- Eval results are tied to a data file in git, so they can be rerun and checked.
- The aggregated table holds no user-level data, which is a good default for GDPR when this points at a real shop.

**Harder**
- **Data is only as fresh as the last rebuild.** Rebuilding is a manual step on the laptop (`python scripts/build_data.py`).
- **New segments need a rebuild.** Adding a dimension (e.g. landing page or browser) means changing the SQL and regenerating the table; the app can't slice by something that isn't in it.
- **The table grows with dimensions and days.** 4 dimensions × 92 days is 1.3 MB. A real shop with a year of data and more dimensions may need Parquet or a small database instead of CSV.

## When to revisit
- **When the tool points at a real shop's own GA4 data** (a v1 idea): move to **option C**, a daily scheduled refresh into small tables, with each shop's credentials in the job's secrets, never in the app.
- **If users need ad-hoc segments** the table doesn't have: consider live queries behind a login, with per-user quota limits (option B).
