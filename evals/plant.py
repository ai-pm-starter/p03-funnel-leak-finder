"""Plant a known leak into the funnel table (P3-07 eval and tests).

Sessions in the segment that reach `step` are thinned at random to about `keep` of their number (binomial,
fixed seed, so runs repeat). Later steps keep their own conversion from that step: they shrink by the same
row-level ratio, so the funnel still only narrows. Revenue shrinks with purchases.
Rows are small (often 1–3 sessions), so plain rounding per row would distort the leak; thinning doesn't.
"""
import numpy as np
import pandas as pd

STEPS = ["sessions", "view_item", "add_to_cart", "begin_checkout", "add_payment_info", "purchase"]


def plant(df: pd.DataFrame, mask, step: str, keep: float, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    df = df.copy()
    m = np.asarray(mask)
    k = STEPS.index(step)
    before = df.loc[m, step].to_numpy(float)
    after = rng.binomial(before.astype(int), keep).astype(float)
    ratio = np.divide(after, before, out=np.zeros_like(after), where=before > 0)
    df.loc[m, step] = after
    if step == "begin_checkout":                      # add_shipping_info always fires with begin_checkout
        df.loc[m, "add_shipping_info"] = np.minimum(np.round(df.loc[m, "add_shipping_info"].to_numpy() * ratio), after)
    for s in STEPS[k + 1:]:
        df.loc[m, s] = np.round(df.loc[m, s].to_numpy() * ratio)   # x_j * ratio <= x_step * ratio = after
    old_p = df.loc[m, "purchase_events"].to_numpy(float)
    df.loc[m, "revenue_usd"] = df.loc[m, "revenue_usd"].to_numpy() * ratio
    df.loc[m, "purchase_events"] = np.round(old_p * ratio)
    return df
