"""Gemini leak report (P3-05): turns the ranked leak table into a brief a PM can act on.

The model gets only the computed leak table and the overall funnel, with every number pre-formatted.
It must reuse those numbers exactly. `unverified_numbers()` flags any number in the report that wasn't
in the input, so made-up numbers are caught at run time and counted in the P3-07 eval.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PROMPT = ROOT / "prompts" / "v1-leak-report.md"
TOP_N = 5
SHOP = "Google Merchandise Store (Google's online shop for branded merchandise), GA4 sample data, revenue in USD"


def pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def money(x: float) -> str:
    return f"${x / 1000:.1f}k" if abs(x) >= 1000 else f"${x:,.0f}"


def build_input(leaks: pd.DataFrame, funnel: pd.DataFrame, start: str, end: str, top_n: int = TOP_N) -> dict:
    """The only data the model sees: context, overall funnel and the top leaks, numbers as strings."""
    steps = [{"step": r.step, "sessions": f"{r.sessions:,}",
              **({"of_previous_step": pct(r.of_previous)} if pd.notna(r.of_previous) else {})}
             for r in funnel.itertuples()]
    items = []
    for rank, r in leaks.head(top_n).iterrows():
        items.append({
            "id": f"L{rank}",
            "segment": r.segment,
            "segment_type": r.dimension,
            "step": f"{r.step_from} → {r.step_to}",
            "segment_conversion": pct(r.conv_segment),
            "rest_of_shop_conversion": pct(r.conv_rest),
            "sessions_entering_step": f"{r.sessions_in:,}",
            "segment_share_of_all_visits": pct(r.segment_share_of_visits),
            "lost_purchases": f"{r.lost_purchases:,.0f}",
            "lost_revenue": money(r.lost_revenue_usd),
        })
    return {"shop": SHOP, "date_range": f"{start} to {end}", "funnel": steps, "leaks": items}


def _allowed_numbers(data: dict) -> set[str]:
    nums = set()
    for s in re.findall(r"\$?\d[\d,]*(?:\.\d+)?%?k?", json.dumps(data, ensure_ascii=False)):
        nums.add(_norm(s))
    return nums


def _norm(s: str) -> str:
    return s.replace(",", "").rstrip(".")


def unverified_numbers(report: dict, data: dict) -> list[str]:
    """Numbers in the report that don't appear in the input (ignores small counts like '2' or '3')."""
    allowed = _allowed_numbers(data)
    text = json.dumps(report, ensure_ascii=False)
    found = re.findall(r"\$?\d[\d,]*(?:\.\d+)?%?k?", text)
    bad = []
    for s in found:
        n = _norm(s)
        if n in allowed or re.fullmatch(r"L?\d", n) or re.fullmatch(r"\d{1,2}", n) and "%" not in s:
            continue   # leak ids, list numbers and small counts ("2–3 tests") are fine
        bad.append(s)
    return sorted(set(bad))


FALLBACK_MODEL = "gemini-3.1-flash-lite"     # free tier, fast; used when the main model is overloaded (503)
CALL_TIMEOUT_S = 90                         # one call normally takes 10–30 s; give up on a hung call


def generate(data: dict, model: str | None = None, api_key: str | None = None, retries: int = 2) -> dict:
    """Call Gemini once for all top leaks. Returns {'report', 'unverified', 'seconds', 'model'}.

    On 'overloaded' (503) or a bad JSON reply it retries with 10 s, then 20 s waits, then tries the fallback
    model. A quota error (429) on the main model goes straight to the fallback (separate quota); a 429 on
    the fallback is raised: the free daily limit will not come back within seconds.
    """
    from google import genai
    from google.genai import errors, types

    client = genai.Client(api_key=api_key or os.environ["GEMINI_API_KEY"],
                          http_options=types.HttpOptions(timeout=CALL_TIMEOUT_S * 1000))
    main = model or os.environ.get("GEMINI_MODEL") or "gemini-3.6-flash"
    fallback = os.environ.get("GEMINI_FALLBACK_MODEL") or FALLBACK_MODEL
    prompt = PROMPT.read_text() + "\n\nINPUT:\n" + json.dumps(data, ensure_ascii=False, indent=1)
    config = types.GenerateContentConfig(temperature=0.2, response_mime_type="application/json")
    t0, last = time.time(), None
    for m in dict.fromkeys([main, fallback]):          # main first, fallback once (no duplicates)
        for attempt in range(retries + 1):
            try:
                resp = client.models.generate_content(model=m, contents=prompt, config=config)
                report = json.loads(resp.text)
                return {"report": report, "unverified": unverified_numbers(report, data),
                        "seconds": round(time.time() - t0, 1), "model": m}
            except errors.ClientError as e:            # 4xx: no point retrying the same model
                if getattr(e, "code", None) == 429 and m != fallback:
                    last = e                           # this model's daily quota is used up: try the fallback,
                    break                              # which has its own quota
                raise
            except Exception as e:                     # overloaded (503), timeout, network, bad JSON → retry
                last = e
                if attempt < retries:
                    time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"Gemini unavailable after retries on {main} and {fallback}: {last}")


if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv

    sys.path.insert(0, str(Path(__file__).parent))
    from leaks import find_leaks, funnel, load

    load_dotenv(ROOT / ".env")
    df = load()
    data = build_input(find_leaks(df, depth=2), funnel(df), str(df["day"].min().date()), str(df["day"].max().date()))
    out = generate(data)
    print(json.dumps(out, ensure_ascii=False, indent=1))
