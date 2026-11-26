# Evals

P3-07 · Nov 26, 2026 · status: **partial** (2 briefs and the PM rubric scores still to do)

## Eval set
**Planted leaks** (`evals/planted_leaks.csv`): 5 scenarios. Each takes the real 92-day funnel table and plants ONE known leak in a copy, so the planted leak has to compete with the real ones, as it would in a real shop. One leak per funnel step, a mix of single segments and pairs, from small (1,216 sessions) to large (26,824):

| Id | Planted leak | Drop |
|---|---|---|
| E1 | Canada · visit → view item | 30% fewer |
| E2 | mobile × paid · view item → add to cart | 50% fewer |
| E3 | India · add to cart → checkout | 40% fewer |
| E4 | returning × referral · checkout → payment info | 40% fewer |
| E5 | desktop × direct · payment info → purchase | 30% fewer |

**How a leak is planted** (`evals/plant.py`): sessions in the segment that reach the step are thinned at random (binomial, fixed seed); later steps and revenue shrink with them. A first version rounded down on every one of the 20,874 small rows, which made the drops far bigger than intended (India's checkout rate fell to 14% instead of about 33%) and the leaks too easy to find. It was replaced before any results were recorded.

**Briefs:** one Gemini brief per scenario (`evals/results/brief-E*.json`) plus the two real all-dates briefs from P3-05.

**Rubric** (`evals/rubric.csv`): the PM scores each distinct leak brief 1–5 on *specific* (fits this step and segment), *grounded* (numbers right, caveats present), *testable* (an experiment the team could start this month) and *overall* (would you act on it).

Run: `python evals/run_eval.py` (recall, no AI) · `python evals/run_eval.py --briefs` (5 Gemini calls, skips saved ones) · `python evals/make_rubric.py`.

## Metrics and pass bar
| Metric | Definition | Pass bar | Result |
|---|---|---|---|
| Planted leaks in the top 5 | planted segment × step ranked 1–5 | ≥ 4/5 | **2/5 ✗** |
| Planted leaks found | anywhere in the leak list, exact segment | (diagnostic) | 4/5 |
| … or at parent level | a parent segment flagged at the right step | (diagnostic) | 5/5 |
| #1 among new leaks | the planted leak is the top leak that isn't already in the real data | (diagnostic) | 3/5 |
| False alarms | new leaks unrelated to the planted one | 0 | **0 ✓** |
| Made-up numbers | numbers in briefs not in the input | 0 | **0 ✓** (5 briefs so far) |
| Brief quality | average PM rubric score | ≥ 4/5 | pending |

## Results
**Leak finder recall** (`evals/results/recall.csv`):

| Id | Found | Rank | Segment vs rest | Lost revenue | Note |
|---|---|---|---|---|---|
| E1 Canada | ✓ | 6 | 15.3% vs 21.4% | $9.1k | #1 among new leaks; behind 5 real leaks |
| E2 mobile × paid | ✓ | 9 | 12.5% vs 26.3% | $1.7k | small segment, small revenue → ranks low |
| E3 India | ✓ | 5 | 32.2% vs 54.7% | $14.4k | in top 5 |
| E4 returning × referral | parent only | (5) | | | flagged as **referral** at checkout → payment (46.6% vs 60.0%) |
| E5 desktop × direct | ✓ | 5 | 49.3% vs 71.1% | $14.3k | in top 5 |

**What this shows:**
1. **The finder finds planted leaks and raises no false alarms.** Every planted leak was flagged at the right step, 4 of 5 at the exact segment.
2. **The top-5 bar fails because the real "new visitor" leaks are bigger.** They are worth $18k–$105k each, so a planted leak worth $9k–$14k ranks 5th–9th. The ranking by lost revenue is doing its job; the bar assumed a shop without big existing leaks.
3. **Weak spot, pair vs parent (E4):** returning × referral, after the planted drop, converts about like all referral traffic (which is mostly new visitors), so the "drop repeats" rule keeps the parent *referral* and drops the more precise pair. The leak is still found at the right step, but less specifically.

**Brief number check:** 5 briefs so far (real data × 2, E1, E2, E4), **0 unverified numbers**. E3 and E5 hit the free daily quota (429) and run again after the reset (about 08:00 GMT). That run also uses a fix found here: a 429 on the main model now goes straight to the fallback model, which has its own quota.

## Decisions for the PM
- **Top-5 bar:** keep it (and count it as a fail), or change it to "found, and #1 among leaks that aren't already in the data". The second measures detection without penalising the tool for real leaks being bigger.
- **Pair vs parent rule (E4):** improve in v2, e.g. compare a pair with its parent's *other* members within the same visitor type, or show "referral, mostly returning visitors".

## Results log
| Date | Prompt/model version | Score | Notes |
|---|---|---|---|
| Nov 26, 2026 | leak finder v1 (depth 2) | top-5 2/5 · found 4/5 (+1 parent) · 0 false alarms | 5 planted leaks, binomial thinning, seed 7 |
| Nov 26, 2026 | prompt v1 · gemini-3.6-flash / 3.1-flash-lite | 0 made-up numbers in 5 briefs | E3, E5 pending (quota) · rubric pending |
