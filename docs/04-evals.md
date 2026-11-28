# Evals

P3-07 · Nov 26, 2026 · status: **partial** (PM rubric scores still to do) · recall bar **passed** with leak finder v2

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
| **Planted leak found and ranked #1 among new leaks** | the exact planted segment × step is flagged, and no other leak that wasn't already in the real data ranks above it | ≥ 4/5 | v1: 3/5 ✗ · **v2: 4/5 ✓** |
| Planted leaks found | anywhere in the leak list, exact segment | (diagnostic) | v1: 4/5 (+1 parent) · **v2: 5/5** |
| Planted leaks in the top 5 | ranked 1–5 overall (the old bar) | (diagnostic) | 2/5 · 2/5 |
| False alarms | new leaks unrelated to the planted one | 0 | v1: 0 ✓ · **v2: 1 ✗** |
| Made-up numbers | numbers in briefs not in the input | 0 | **0 ✓** (7 briefs, 35 leak cards) |
| Brief quality | average PM rubric score | ≥ 4/5 | pending |

## Results
**Leak finder v1 recall** (first run, pair rule v1):

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

**Brief number check: 7 briefs, 0 unverified numbers.** Real data × 2 (Nov 26), E1, E2, E4 (Nov 26, leak finder v1, gemini-3.1-flash-lite after 3.6 was overloaded), E3 and E5 (Nov 28, leak finder v2, gemini-3.6-flash, 70–89 s). E3 and E5 first hit the free daily quota (429) on Nov 26; that led to a fix: a 429 on the main model now goes straight to the fallback model, which has its own quota.

**Rubric sheet:** `evals/rubric.csv` has **8 distinct leak briefs** (2 planted, 5 real, 1 scenario leak). E1 and E2's planted leaks rank below 5th, so the app doesn't brief them.

**Leak finder v2 recall** (`evals/results/recall.csv`, new pair rule, see `docs/03-ai-design.md`):

| Id | Found | Rank | Among new leaks | Segment vs rest | Lost revenue |
|---|---|---|---|---|---|
| E1 Canada · visit → view item | ✓ | 6 | **#1** | 15.3% vs 21.4% | $9.1k |
| E2 mobile × paid · view item → add to cart | ✓ | 8 | **#1** | 12.5% vs 26.3% | $1.7k |
| E3 India · add to cart → checkout | ✓ | 5 | **#1** | 32.2% vs 54.7% | $14.4k |
| E4 referral × returning · checkout → payment info | ✓ | 7 | #3 | 49.2% vs 58.5% | $7.0k |
| E5 desktop × direct · payment info → purchase | ✓ | 5 | **#1** | 49.3% vs 71.1% | $14.3k |

- **E4** is now found at the exact segment. It ranks behind its parent `referral` (which the plant also pulls down) and one false alarm.
- **False alarm:** `unknown × new` at checkout → payment info appears in E4 only. It is borderline on the real data, and the plant shifts the shop's average at that step enough to push it over. Logged, not tuned away.
- **Eval bug fixed:** the eval wrote E4's pair as "returning × referral" while the finder names pairs in a fixed order ("referral × returning"), so a correct find would not have matched. Labels now use the finder's order. Under pair rule v1 the pair was missing anyway, so the v1 result stands.

## Decisions
- **Nov 26, 2026, PM: changed the main bar** from "planted leak in the top 5" to "**found, and #1 among new leaks**". The old bar penalised the tool for the real new-visitor leaks being bigger than the planted ones, which is correct ranking, not a miss. The new bar measures whether a fresh leak is detected and put first among fresh leaks. The old bar stays as a diagnostic.
- **Result under the new bar: 3/5, still below 4/5.** The two misses are real weaknesses:
  - **E2 (mobile × paid):** found, but #2 among new leaks, behind a side effect of the plant. Small segments with little revenue rank low.
  - **E4 (returning × referral):** only found at parent level (pair vs parent rule).
- **Nov 26, 2026, PM: improve the pair rule** → leak finder v2 compares a pair with what *both* parents predict. Result: **4/5 ✓**, 5/5 found exactly, 1 false alarm.

## Results log
| Date | Prompt/model version | Score | Notes |
|---|---|---|---|
| Nov 26, 2026 | leak finder v1 (depth 2) | **#1 among new 3/5** · found 4/5 (+1 parent) · top-5 2/5 · 0 false alarms | 5 planted leaks, binomial thinning, seed 7 |
| Nov 26, 2026 | leak finder v2 (pair rule: predicted from both parents) | **#1 among new 4/5 ✓** · found 5/5 · top-5 2/5 · 1 false alarm | same 5 planted leaks, seed 7 |
| Nov 28, 2026 | prompt v1 · gemini-3.6-flash / 3.1-flash-lite | 0 made-up numbers in 7 briefs | rubric (8 briefs) pending |
