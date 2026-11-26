"""P3-07 eval, part 3: build the rubric sheet the PM scores by hand (evals/rubric.csv).

Takes one card per distinct leak (segment × step) from the real all-dates brief (data/saved_report.json) and
the planted-scenario briefs (evals/results/brief-E*.json). Planted leaks first, then real ones, up to 10.
Scores 1–5 (5 = best):
  specific   - causes and checks fit THIS step and segment, not generic advice
  grounded   - uses the leak's numbers correctly and adds the caveats that apply (intent, first-touch, unknown)
  testable   - at least one experiment a team could start this month, with a clear metric
  overall    - would you act on this brief?
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "evals" / "results"
planted = pd.read_csv(ROOT / "evals" / "planted_leaks.csv")
recall = pd.read_csv(RES / "recall.csv")


def cards(path: Path, source: str):
    saved = json.loads(path.read_text())
    inputs = {x["id"]: x for x in saved["input"]["leaks"]}
    for c in saved["result"]["report"]["leaks"]:
        x = inputs.get(c["id"], {})
        yield {
            "source": source, "leak_id": c["id"], "segment": x.get("segment"), "step": x.get("step"),
            "numbers": f'{x.get("segment_conversion")} vs {x.get("rest_of_shop_conversion")}, lost {x.get("lost_revenue")}',
            "headline": c.get("headline"),
            "causes": " | ".join(k.get("cause", "") for k in c.get("likely_causes", [])),
            "checks": " | ".join(c.get("what_to_check", [])),
            "experiments": " | ".join(f'{e.get("name")}: {e.get("hypothesis")}' for e in c.get("experiments", [])),
            "confidence": c.get("confidence", {}).get("level"),
            "caveat": c.get("caveat"),
        }


rows, seen = [], set()
planted_keys = {r.planted for r in recall.itertuples()}
for f in sorted(RES.glob("brief-E*.json")):
    for c in cards(f, f.stem.replace("brief-", "planted ")):
        k = (c["segment"], c["step"])
        is_planted = any(c["segment"] and c["step"] and f'{c["segment"]} · {c["step"]}' == p for p in planted_keys)
        if k not in seen and is_planted:
            seen.add(k); rows.append({**c, "kind": "planted leak"})
for c in cards(ROOT / "data" / "saved_report.json", "real data, all dates"):
    k = (c["segment"], c["step"])
    if k not in seen:
        seen.add(k); rows.append({**c, "kind": "real leak"})
for f in sorted(RES.glob("brief-E*.json")):   # fill up with other new leaks from the scenarios (e.g. parent level)
    for c in cards(f, f.stem.replace("brief-", "planted ")):
        k = (c["segment"], c["step"])
        if k not in seen and len(rows) < 10:
            seen.add(k); rows.append({**c, "kind": "scenario leak"})

df = pd.DataFrame(rows[:10])
for col in ["specific", "grounded", "testable", "overall", "notes"]:
    df[col] = ""
df.insert(0, "n", range(1, len(df) + 1))
df.to_csv(ROOT / "evals" / "rubric.csv", index=False)
print(df[["n", "kind", "source", "segment", "step"]].to_string(index=False))
