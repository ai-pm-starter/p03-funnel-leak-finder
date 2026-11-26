"""Funnel Leak Finder (P3-06): pick dates → funnel → ranked leaks → AI brief.

Run: streamlit run app/app.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
from leaks import find_leaks, funnel, load  # noqa: E402
from report import TOP_N, build_input, generate, money, pct  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SAVED = ROOT / "data" / "saved_report.json"   # report for the default view, so the demo never waits on Gemini
MIN_SESSIONS_VIEW = 5000

st.set_page_config(page_title="Funnel Leak Finder", page_icon="🔎", layout="wide")


@st.cache_data
def data() -> pd.DataFrame:
    return load()


@st.cache_data
def leaks_for(start, end, depth: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = data()
    view = df[(df["day"] >= pd.Timestamp(start)) & (df["day"] <= pd.Timestamp(end))]
    return funnel(view), find_leaks(view, depth=depth), int(view["sessions"].sum())


@st.cache_data(show_spinner=False, ttl=24 * 3600)
def ai_report(input_json: str) -> dict:
    return generate(json.loads(input_json), api_key=_api_key())


def _api_key() -> str | None:
    try:
        if "GEMINI_API_KEY" in st.secrets:
            os.environ.setdefault("GEMINI_MODEL", st.secrets.get("GEMINI_MODEL", ""))
            return st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    return os.environ.get("GEMINI_API_KEY")


def saved_report(input_data: dict) -> dict | None:
    if not SAVED.exists():
        return None
    saved = json.loads(SAVED.read_text())
    return saved["result"] if saved.get("input") == input_data else None


# ---------- Sidebar ----------
df = data()
first, last = df["day"].min().date(), df["day"].max().date()
with st.sidebar:
    st.header("Settings")
    dates = st.date_input("Date range", (first, last), min_value=first, max_value=last)
    pairs = st.toggle("Include segment pairs (e.g. mobile × referral)", value=True)
    st.caption("Data: Google Merchandise Store GA4 sample (public, obfuscated), Nov 2020 – Jan 2021. Revenue in USD.")
    st.caption("Leaks: ≥ 300 sessions entering the step, ≥ 10% worse than the rest of the shop, "
               "significant after a false-discovery correction (5%).")
start, end = (dates[0], dates[1]) if isinstance(dates, (tuple, list)) and len(dates) == 2 else (first, last)

# ---------- Header ----------
st.title("🔎 Funnel Leak Finder")
st.markdown("Where does the shop's funnel leak, **for whom**, how much revenue does it cost, and **what should we test**? "
            "Statistics find and size the leaks; Gemini writes the brief from those numbers only.")

steps, leaks, n_sessions = leaks_for(start, end, 2 if pairs else 1)
if n_sessions < MIN_SESSIONS_VIEW:
    st.warning(f"Only {n_sessions:,} sessions in this range. Pick at least a week so leaks can be told apart from noise.")
    st.stop()

# ---------- KPIs ----------
view = df[(df["day"] >= pd.Timestamp(start)) & (df["day"] <= pd.Timestamp(end))]
buyers, revenue = int(view["purchase"].sum()), float(view["revenue_usd"].sum())
c1, c2, c3, c4 = st.columns(4)
c1.metric("Sessions", f"{n_sessions:,}")
c2.metric("Sessions with a purchase", f"{buyers:,}")
c3.metric("Conversion", pct(buyers / n_sessions))
c4.metric("Revenue", money(revenue))

# ---------- Funnel ----------
left, right = st.columns([3, 2])
with left:
    st.subheader("Funnel")
    fig = go.Figure(go.Funnel(y=steps["step"], x=steps["sessions"], texttemplate="%{value:,} · %{percentPrevious:.0%}",
                              marker={"color": "#1f5fbf"}))
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=320)
    st.plotly_chart(fig, use_container_width=True)
with right:
    st.subheader("Step by step")
    t = steps.copy()
    t["sessions"] = t["sessions"].map("{:,}".format)
    t["of previous step"] = t["of_previous"].map(lambda x: "" if pd.isna(x) else pct(x))
    t["of visits"] = t["of_visits"].map(pct)
    st.dataframe(t[["step", "sessions", "of previous step", "of visits"]], hide_index=True, use_container_width=True)

# ---------- Leaks ----------
st.subheader(f"Leaks, ranked by lost revenue ({len(leaks)})")
if leaks.empty:
    st.success("No leaks in this range: no segment converts clearly worse than the rest of the shop at any step.")
    st.stop()
show = pd.DataFrame({
    "#": [f"L{i}" for i in leaks.index],
    "Segment": leaks["segment"],
    "Step": leaks["step_from"] + " → " + leaks["step_to"],
    "Segment conv.": leaks["conv_segment"].map(pct),
    "Rest of shop": leaks["conv_rest"].map(pct),
    "Sessions entering": leaks["sessions_in"].map("{:,}".format),
    "Lost purchases": leaks["lost_purchases"].map("{:,.0f}".format),
    "Lost revenue": leaks["lost_revenue_usd"].map(money),
})
st.dataframe(show, hide_index=True, use_container_width=True, height=min(400, 38 + 35 * len(show)))
st.caption("Lost revenue = extra purchases if the segment converted like the rest of the shop at this step × its revenue per "
           "buyer. Returning visitors always convert better than new ones, so treat 'new' leaks as an upper bound.")

# ---------- AI brief ----------
st.subheader(f"AI brief for the top {min(TOP_N, len(leaks))} leaks")
input_data = build_input(leaks, steps, str(start), str(end))
result = saved_report(input_data)
if result:
    st.caption(f"Saved report for this view ({result['model']}). Change the dates to generate a new one.")
elif not _api_key():
    st.info("No Gemini key configured, so the AI brief is off. The leak table above still works.")
    st.stop()
elif st.button("Generate AI brief", type="primary"):
    with st.spinner("Asking Gemini… usually 10–40 s, longer when the free tier is busy."):
        try:
            result = ai_report(json.dumps(input_data, ensure_ascii=False))
        except Exception as e:
            st.error(f"Gemini didn't answer ({type(e).__name__}). The free tier may be busy or out of quota: try again later.")
            st.stop()
    st.caption(f"Generated by {result['model']} in {result['seconds']} s.")
else:
    st.caption("Uses one Gemini call (free tier, limited per day).")
    st.stop()

if result["unverified"]:
    st.warning("These numbers in the brief don't appear in the data, so don't trust them: " + ", ".join(result["unverified"]))
report = result["report"]
st.info(report.get("summary", ""))
by_id = {f"L{i}": r for i, r in leaks.iterrows()}
for item in report.get("leaks", []):
    conf = item.get("confidence", {})
    with st.expander(f"**{item.get('id')}** · {item.get('headline', '')}  ·  confidence: {conf.get('level', '?')}",
                     expanded=item.get("id") == "L1"):
        st.markdown(item.get("what_is_happening", ""))
        a, b = st.columns(2)
        with a:
            st.markdown("**Likely causes** (hypotheses)")
            for c in item.get("likely_causes", []):
                st.markdown(f"- **{str(c.get('cause', '')).rstrip('.')}**: {c.get('why_plausible')}")
            st.markdown("**What to check this week**")
            for c in item.get("what_to_check", []):
                st.markdown(f"- {c}")
        with b:
            st.markdown("**Experiments**")
            for x in item.get("experiments", []):
                st.markdown(f"- **{str(x.get('name', '')).rstrip('.')}**: {x.get('hypothesis')}  \n  *Metric:* {x.get('metric')}")
            st.markdown(f"**Confidence:** {conf.get('level', '?')}: {conf.get('reason', '')}")
            if item.get("caveat") and item["caveat"].lower() != "none":
                st.markdown(f"**Caveat:** {item['caveat']}")
st.caption("The brief is written by Gemini from the leak table only. Causes are hypotheses to test, not findings.")
