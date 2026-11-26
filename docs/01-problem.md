# Problem statement

PM: Prashant · Drafted Nov 26, 2026 (P3-01)

## User
A **growth or e-commerce PM** at a mid-sized online shop, who owns conversion but has no analyst on call. They have GA4 set up and know the funnel numbers on the dashboard, but not what's behind them.

## Pain
The dashboard shows that conversion dropped or is low. It doesn't show **where** in the funnel people leave, **for whom** (mobile? paid traffic? new visitors? one country?) or **what to try next**.
- **Time:** finding one leak means slicing the funnel by step, device, channel, country and visitor type by hand in GA4 explorations or SQL. That's typically **a few days** of analyst time, or it doesn't happen.
- **Money:** a leak in checkout on mobile can cost a large share of revenue, and it stays hidden in the overall average. Teams then test random ideas instead of the step that leaks.

## Why now / why AI
Statistics can rank leaks: compare each step's drop-off per segment against the rest of the shop and size it in lost revenue. That part needs **no AI**, and doing it with code makes the numbers trustworthy. What a rule can't do is turn a ranked table into a **brief a PM can act on**: plausible causes for this kind of leak, what to check first, and 2–3 experiments to run. That's where the model helps. It works only from the computed numbers it is given.

## v0: what it does
A **Streamlit web app** over the public **Google Merchandise Store GA4 dataset** (Google's own online shop, Nov 2020 – Jan 2021, in BigQuery):
1. **Funnel tables** (computed once, saved in the repo): sessions reaching each step, `session_start → view_item → add_to_cart → begin_checkout → add_shipping_info → add_payment_info → purchase`, per day and per segment (device, channel, country, new vs returning).
2. **Leak finder** (statistics, no AI): for each step and segment, compare the step's conversion with the rest of the shop, keep only differences that are significant and big enough to matter, and estimate the **lost revenue** if the segment converted like the rest.
3. **Leak report** (Gemini): for the top leaks, a short brief with the leak in plain words, likely causes, what to check, and experiments to test, each tied to the numbers.
4. **App:** pick a date range → funnel chart → ranked leaks → AI report.

**Data:** the BigQuery dataset is public and obfuscated (some values show as `<Other>` or `(data deleted)`), with no personal data. The hosted app reads only small summary tables, so it needs no Google keys.

## Success metrics
| Metric | Target | How measured |
|---|---|---|
| Finds real leaks | ≥ 4 of 5 **planted** leaks found and ranked **#1 among new leaks** (changed from "in the top 5" on Nov 26: real leaks in the data are bigger) | Eval: copies of the data with known leaks added (P3-07) |
| No made-up numbers | 0 numbers in the AI report that don't match the data | Eval: check every number in the report against the leak table |
| Useful report | ≥ 4/5 average on a rubric (specific, grounded, testable experiment) | PM scores the report for 10 leaks (P3-07) |
| Speed | Report on screen in < 30 s | Timed in the app |
| Demo | Live link anyone can open | Streamlit Community Cloud (P3-09) |
| Cost per task | €0 (free tier) | No card on any service |

## Out of scope (v0)
- Connecting to a shop's **own** GA4 or other analytics (a v1 idea).
- Proving **why** a leak happens. The report gives hypotheses to test, not causes.
- Running A/B tests or changing the shop.
- Real-time data, alerts or scheduled reports.
- Product- or page-level analysis (which product pages leak). Funnel steps and segments only.
- Personal data of any kind.
