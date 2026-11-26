"""P3-07 eval, part 1: does the leak finder catch planted leaks? Part 2 (--briefs): Gemini briefs + number check.

Each scenario plants ONE known leak into a copy of the real funnel table: sessions in the segment that reach
the step are thinned at random to about `keep` (e.g. 0.6 = 40% fewer); later steps and revenue follow (evals/plant.py).
Real leaks stay in the data, so the planted leak has to compete with them, as it would in a real shop.

Usage:
  python evals/run_eval.py            # recall of planted leaks (no AI)
  python evals/run_eval.py --briefs   # also one Gemini brief per scenario (5 calls; skips ones already saved)
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
from leaks import STEP_NAMES, STEPS, find_leaks, funnel, load  # noqa: E402

sys.path.insert(0, str(ROOT / "evals"))
from plant import plant  # noqa: E402

OUT = ROOT / "evals" / "results"
STEP_LABEL = {s: STEP_NAMES[s] for s in STEPS}


def parse_segment(spec: str):
    parts = dict(p.strip().split("=") for p in spec.split("&"))
    label = " × ".join(parts.values())
    return parts, label


def plant_spec(df: pd.DataFrame, parts: dict, step: str, keep: float) -> pd.DataFrame:
    mask = np.logical_and.reduce([df[k] == v for k, v in parts.items()])
    return plant(df, mask, step, keep)


def key(r):
    return (r["segment"], r["step_to"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--briefs", action="store_true")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    base_df = load()
    baseline = find_leaks(base_df, depth=2)
    base_keys = {key(r) for _, r in baseline.iterrows()}
    rows = []
    for sc in pd.read_csv(ROOT / "evals" / "planted_leaks.csv").itertuples():
        parts, label = parse_segment(sc.segment)
        df = plant_spec(base_df, parts, sc.step, sc.keep)
        leaks = find_leaks(df, depth=2)
        target = (label, STEP_LABEL[sc.step])
        ranks = [i for i, r in leaks.iterrows() if key(r) == target]
        new = leaks[[key(r) not in base_keys for _, r in leaks.iterrows()]]
        new_rank = [n + 1 for n, (_, r) in enumerate(new.iterrows()) if key(r) == target]
        related = [k for k in (key(r) for _, r in new.iterrows())
                   if k != target and k[1] == target[1] and (set(k[0].split(" × ")) & set(label.split(" × ")))]
        other_new = len(new) - (1 if ranks else 0) - len(related)
        hit = ranks[0] if ranks else None
        parents = set(label.split(" × ")) if " × " in label else set()
        parent_ranks = [i for i, r in leaks.iterrows() if r["segment"] in parents and r["step_to"] == target[1]]
        row = {"id": sc.id, "planted": f"{label} · {STEP_NAMES[STEPS[STEPS.index(sc.step) - 1]]} → {STEP_LABEL[sc.step]}",
               "keep": sc.keep, "found": bool(ranks), "rank": hit,
               "found_as_parent": (not ranks) and bool(parent_ranks), "parent_rank": parent_ranks[0] if parent_ranks else None, "in_top5": bool(hit and hit <= 5),
               "rank_among_new_leaks": new_rank[0] if new_rank else None,
               "related_leaks": len(related), "unrelated_new_leaks": other_new}
        if hit:
            r = leaks.loc[hit]
            row.update({"conv_segment": round(r.conv_segment, 3), "conv_rest": round(r.conv_rest, 3),
                        "lost_revenue_usd": round(r.lost_revenue_usd)})
        rows.append(row)
        if args.briefs:
            brief(sc.id, df, leaks)
    res = pd.DataFrame(rows)
    res.to_csv(OUT / "recall.csv", index=False)
    print(res.to_string(index=False))
    print(f"\nFound exactly: {res.found.sum()}/5 · found as parent only: {res.found_as_parent.sum()}/5 · in top 5: {res.in_top5.sum()}/5 · "
          f"#1 among new leaks: {(res.rank_among_new_leaks == 1).sum()}/5 · unrelated new leaks: {res.unrelated_new_leaks.sum()}")


def brief(sid: str, df: pd.DataFrame, leaks: pd.DataFrame):
    from dotenv import load_dotenv
    from report import build_input, generate
    load_dotenv(ROOT / ".env")
    path = OUT / f"brief-{sid}.json"
    if path.exists():
        print(f"  {sid}: brief already saved, skipping")
        return
    data = build_input(leaks, funnel(df), str(df["day"].min().date()), str(df["day"].max().date()))
    try:
        out = generate(data)
    except Exception as e:
        print(f"  {sid}: Gemini failed ({type(e).__name__}): {str(e)[:150]}")
        return
    path.write_text(json.dumps({"input": data, "result": out}, ensure_ascii=False, indent=1))
    print(f"  {sid}: {out['model']} {out['seconds']} s, unverified numbers: {out['unverified']}")


if __name__ == "__main__":
    main()
