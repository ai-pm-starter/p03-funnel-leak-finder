"""Leak finder (P3-04): where the funnel leaks, for whom, and how much revenue it costs. Statistics only, no AI.

For every funnel step and every segment (e.g. device = mobile), compare the segment's step conversion with
the rest of the shop. Keep a leak only if it is
  - worse than the rest by at least MIN_REL_GAP (relative),
  - based on at least MIN_SESSIONS sessions entering the step, and
  - significant after correcting for testing many segments at once (Benjamini–Hochberg, q < ALPHA).
Then size it: purchases and revenue lost because the segment converts worse than the rest at this step.
"""
from __future__ import annotations

from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

DATA = Path(__file__).resolve().parent.parent / "data" / "funnel_daily.csv"

# begin_checkout and add_shipping_info always fire together in this shop, so they count as one step.
STEPS = ["sessions", "view_item", "add_to_cart", "begin_checkout", "add_payment_info", "purchase"]
STEP_NAMES = {"sessions": "visit", "view_item": "view item", "add_to_cart": "add to cart",
              "begin_checkout": "checkout", "add_payment_info": "payment info", "purchase": "purchase"}
DIMENSIONS = ["device", "country", "channel", "visitor"]

MIN_SESSIONS = 300    # sessions entering the step, in the segment
MIN_REL_GAP = 0.10    # segment converts at least 10% worse (relative) than the rest
ALPHA = 0.05          # false discovery rate across all tests
MIN_DOWNSTREAM = 30   # below this many sessions passing the step, use the shop's downstream rates


def load(path: Path | str = DATA) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["day"])
    return df


def funnel(df: pd.DataFrame) -> pd.DataFrame:
    """Overall funnel: sessions reaching each step and conversion from the previous step."""
    counts = df[STEPS].sum()
    out = pd.DataFrame({"step": [STEP_NAMES[s] for s in STEPS], "sessions": counts.values.astype(int)})
    out["of_previous"] = out["sessions"] / out["sessions"].shift(1)
    out["of_visits"] = out["sessions"] / out["sessions"].iloc[0]
    return out


def _bh(p: np.ndarray) -> np.ndarray:
    """Benjamini–Hochberg adjusted p-values (q-values)."""
    n = len(p)
    if n == 0:
        return p
    order = np.argsort(p)
    ranked = p[order] * n / np.arange(1, n + 1)
    q = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(n)
    out[order] = np.minimum(q, 1.0)
    return out


def _segments(df: pd.DataFrame, depth: int) -> pd.DataFrame:
    """Step counts and revenue per segment: one dimension (depth 1) or pairs of dimensions (depth 2)."""
    frames = []
    for d in range(1, depth + 1):
        for dims in combinations(DIMENSIONS, d):
            g = df.groupby(list(dims), as_index=False)[STEPS + ["revenue_usd"]].sum()
            g["dimension"] = " × ".join(dims)
            g["segment"] = g[list(dims)].astype(str).agg(" × ".join, axis=1)
            frames.append(g[["dimension", "segment"] + STEPS + ["revenue_usd"]])
    return pd.concat(frames, ignore_index=True)


PARENT_MARGIN = 0.10  # a pair (e.g. mobile × new) must convert 10% worse than its leaking parent to be shown


def _drop_explained_by_parent(leaks: pd.DataFrame) -> pd.DataFrame:
    """Drop pair segments that only repeat a single-segment leak at the same step.

    'desktop × new' leaking at checkout is not news if 'new' leaks there and desktop × new converts about the
    same as new. Keep the pair only if it converts clearly worse than every leaking parent.
    """
    single = leaks[~leaks["dimension"].str.contains("×")]
    parent_conv = {(r.segment, r.step_to): r.conv_segment for r in single.itertuples()}
    keep = []
    for r in leaks.itertuples():
        if "×" not in r.dimension:
            keep.append(True)
            continue
        parents = [parent_conv.get((p, r.step_to)) for p in r.segment.split(" × ")]
        parents = [c for c in parents if c is not None]
        keep.append(all(r.conv_segment < c * (1 - PARENT_MARGIN) for c in parents))
    return leaks[pd.Series(keep, index=leaks.index, dtype=bool)]


def find_leaks(df: pd.DataFrame, depth: int = 1, min_sessions: int = MIN_SESSIONS,
               min_rel_gap: float = MIN_REL_GAP, alpha: float = ALPHA) -> pd.DataFrame:
    """Ranked leaks (most lost revenue first). One row per segment × step that passes all filters."""
    total = df[STEPS + ["revenue_usd"]].sum()
    shop_rev_per_buyer = total["revenue_usd"] / total["purchase"] if total["purchase"] else 0.0
    seg = _segments(df, depth)
    rows = []
    for k in range(1, len(STEPS)):
        prev, step = STEPS[k - 1], STEPS[k]
        n_in, x_in = seg[prev].to_numpy(float), seg[step].to_numpy(float)
        n_rest, x_rest = total[prev] - n_in, total[step] - x_in
        with np.errstate(divide="ignore", invalid="ignore"):
            p_seg, p_rest = x_in / n_in, x_rest / n_rest
            pooled = (x_in + x_rest) / (n_in + n_rest)
            se = np.sqrt(pooled * (1 - pooled) * (1 / n_in + 1 / n_rest))
            z = (p_seg - p_rest) / se
        pval = norm.cdf(z)  # one-sided: is the segment worse than the rest?
        # Downstream: of the sessions passing this step, how many buy, and what is a buyer worth?
        with np.errstate(divide="ignore", invalid="ignore"):
            down = np.where(x_in >= MIN_DOWNSTREAM, seg["purchase"] / x_in, total["purchase"] / total[step])
            per_buyer = np.where(seg["purchase"] >= MIN_DOWNSTREAM, seg["revenue_usd"] / seg["purchase"],
                                 shop_rev_per_buyer)
        lost_sessions = n_in * (p_rest - p_seg)
        for i in range(len(seg)):
            rows.append({
                "dimension": seg.at[i, "dimension"], "segment": seg.at[i, "segment"],
                "step_from": STEP_NAMES[prev], "step_to": STEP_NAMES[step],
                "sessions_in": int(n_in[i]), "conv_segment": p_seg[i], "conv_rest": p_rest[i],
                "rel_gap": (p_rest[i] - p_seg[i]) / p_rest[i] if p_rest[i] else np.nan,
                "z": z[i], "p_value": pval[i],
                "lost_sessions": lost_sessions[i],
                "lost_purchases": lost_sessions[i] * down[i],
                "lost_revenue_usd": lost_sessions[i] * down[i] * per_buyer[i],
                "segment_share_of_visits": seg.at[i, "sessions"] / total["sessions"],
            })
    res = pd.DataFrame(rows)
    res = res[(res["sessions_in"] > 0) & (res["sessions_in"] < total[STEPS[0]])].copy()   # drop empty and 'everyone'
    res["q_value"] = _bh(res["p_value"].fillna(1).to_numpy())
    keep = (res["sessions_in"] >= min_sessions) & (res["rel_gap"] >= min_rel_gap) & (res["q_value"] < alpha)
    out = res[keep]
    if depth > 1:
        out = _drop_explained_by_parent(out)
    out = out.sort_values("lost_revenue_usd", ascending=False).reset_index(drop=True)
    out.index = out.index + 1
    out.index.name = "rank"
    return out


if __name__ == "__main__":
    data = load()
    print(funnel(data).to_string(index=False))
    for d in (1, 2):
        leaks = find_leaks(data, depth=d)
        cols = ["segment", "step_from", "step_to", "sessions_in", "conv_segment", "conv_rest", "rel_gap",
                "q_value", "lost_purchases", "lost_revenue_usd"]
        print(f"\n== depth {d}: {len(leaks)} leaks")
        print(leaks[cols].head(12).round(3).to_string())
