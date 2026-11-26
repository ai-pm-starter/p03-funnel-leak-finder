"""Leak finder tests (P3-04). Run: python -m pytest -q"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))
from leaks import STEPS, find_leaks, funnel, load  # noqa: E402


def plant(df, mask, step, factor):
    """Make sessions in `mask` drop out more at `step`: keep only `factor` of those reaching it, and scale
    every later step and the revenue the same way, so the funnel stays consistent."""
    df = df.copy()
    k = STEPS.index(step)
    for s in STEPS[k:] + ["revenue_usd"]:
        df.loc[mask, s] = np.floor(df.loc[mask, s] * factor) if s != "revenue_usd" else df.loc[mask, s] * factor
    return df


def test_funnel_matches_totals():
    f = funnel(load())
    assert f["sessions"].iloc[0] == 360_129
    assert (f["sessions"].diff().dropna() <= 0).all()   # funnel only narrows


def test_finds_planted_leak_in_top_5():
    df = load()
    leaky = plant(df, (df["device"] == "mobile") & (df["channel"] == "referral"), "add_payment_info", 0.6)
    top = find_leaks(leaky, depth=2).head(5)
    hit = top[(top["segment"] == "mobile × referral") & (top["step_to"] == "payment info")]
    assert len(hit) == 1, top[["segment", "step_to"]]


def test_no_leaks_in_uniform_data():
    """Every segment converts the same → nothing should be flagged."""
    rows = []
    for dev in ["desktop", "mobile"]:
        for ch in ["organic", "paid"]:
            rows.append({"day": "2020-11-01", "device": dev, "country": "X", "channel": ch, "visitor": "new",
                         "sessions": 10000, "view_item": 2000, "add_to_cart": 500, "begin_checkout": 250,
                         "add_shipping_info": 250, "add_payment_info": 150, "purchase": 100,
                         "purchase_events": 100, "revenue_usd": 7000.0})
    assert find_leaks(pd.DataFrame(rows), depth=2).empty


def test_small_segments_are_ignored():
    df = load()
    tiny = (df["country"] == "Taiwan") & (df["device"] == "tablet")
    leaky = plant(df, tiny, "add_to_cart", 0.1)
    leaks = find_leaks(leaky, depth=2)
    assert not ((leaks["segment"] == "Taiwan × tablet")).any()
