# AI design

- **Complexity level:** chain. Fixed steps: funnel tables → leak finder (statistics) → Gemini report. No agent.
- **Model(s) and why:** Gemini free tier (picked in P3-05).
- **Prompt(s):** `prompts/v1-leak-report.md` (P3-05)
- **Tools the model can call:** none. It only writes a report from the leak table it is given.
- **Guardrails:** the model gets computed numbers, never raw events, and must not invent numbers. The P3-07 eval checks every number in the report.
- **Human-in-the-loop:** the PM reads the report and decides what to test.
- **Failure modes:** a false leak (noise ranked high) or a plausible-sounding but wrong cause. Leaks need significance and a minimum size; causes are framed as hypotheses to test.
- **Privacy:** the dataset is public and obfuscated, with no personal data. The hosted app reads summary tables from the repo and sends only those numbers to Gemini.

## Data source: Google Merchandise Store GA4 sample (P3-02)
Explored Nov 26, 2026 from a free **BigQuery sandbox** project (no billing, no card).

| | |
|---|---|
| Table | `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*` (one table per day) |
| What it is | GA4 export of Google's own online merchandise shop, obfuscated by Google for public use. [Docs](https://developers.google.com/analytics/bigquery/web-ecommerce-demo-dataset) |
| Dates | **Nov 1, 2020 – Jan 31, 2021** (92 days, includes Black Friday and Christmas) |
| Size | 4.30 M events · 270 k users · 360 k sessions · 5,692 purchases · **$362 k revenue** |
| Access | sandbox project `funnel-leak-finder-*`; login with `gcloud auth application-default login`, stored in `~/.config/gcloud`, never in the repo |

**Funnel events** (all present, counted as events):

| Step | Events |
|---|---|
| session_start | 354,970 |
| view_item | 386,068 |
| add_to_cart | 58,543 |
| begin_checkout | 38,757 |
| add_shipping_info | 19,722 |
| add_payment_info | 13,899 |
| purchase | 5,692 |

Overall about **1.6%** of sessions end in a purchase. Every purchase has revenue.

**Segments available:**
- **Device:** desktop 58%, mobile 40%, tablet 2% (of events).
- **Channel:** only the user's **first-touch** source (`traffic_source.medium`): organic 34%, (none)/direct 23%, referral 18%, cpc 4%. Session-level source is almost never filled in (0.7% of events), so channel means "how the user first arrived", not "this session's source".
- **Country:** US 44%, India 9%, Canada 8%, UK 3%, then France, Spain, China, Taiwan.
- **New vs returning:** from `ga_session_number` (1 = first session).

**Obfuscation to handle:** 21% of events have channel `<Other>` (14%) or `(data deleted)` (7%). These become their own "unknown" segment, not dropped. Small values are grouped by Google, so the long tail of countries is thin.

**Query cost:** exploring scanned about **1.2 GB** in total. The sandbox allows 1,000 GB a month free, so building the P3-03 tables a few times uses well under 1% of it.

## Funnel tables (P3-03)
Built Nov 26, 2026 by `scripts/build_data.py` from `sql/funnel_daily.sql` (scans 1.17 GB). The app only reads the output, so it needs no Google login.

**Output:** `data/funnel_daily.csv`: 20,874 rows, 1.3 MB. One row per **day × device × country × channel × visitor** with the number of sessions that reached each step and the revenue.

| Column | Meaning |
|---|---|
| `day` | session date (first event) |
| `device` | desktop, mobile, tablet |
| `country` | top 10 countries by sessions; the rest are `Other` |
| `channel` | first-touch medium: organic, direct, referral, paid (cpc), other, unknown (`<Other>`, `(data deleted)`) |
| `visitor` | new (first session) or returning |
| `sessions` … `purchase` | sessions that reached each step |
| `purchase_events`, `revenue_usd` | purchases and revenue in those sessions |

**How a session "reaches" a step:** it fired that event **or any later one**. So the funnel only ever narrows, and a purchase still counts when GA4 skipped an earlier event in the same session (for example, the item was added to the cart in an earlier session).

**Cross-check against direct queries:** sessions 360,129 ✓ · purchase events 5,692 ✓ · revenue $362,165 ✓.

| Step | Sessions reached | Of previous step |
|---|---|---|
| session_start | 360,129 | |
| view_item | 77,318 | 21.5% |
| add_to_cart | 20,338 | 26.3% |
| begin_checkout | 11,112 | 54.6% |
| add_shipping_info | 11,111 | 100% |
| add_payment_info | 6,818 | 61.4% |
| purchase | 4,848 | 71.1% |

**Data quirk:** in this shop, `begin_checkout` and `add_shipping_info` fire together (11,104 of 11,107 sessions with either have both). So the leak finder treats them as **one step, "checkout"**, giving 6 steps: session → view item → add to cart → checkout → payment → purchase. Otherwise a step with 100% conversion would hide real leaks.
