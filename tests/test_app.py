"""App tests (P3-06) with Streamlit's AppTest. No Gemini calls: the button is never clicked."""
import datetime as dt

from streamlit.testing.v1 import AppTest

from pathlib import Path

APP = str(Path(__file__).resolve().parent.parent / "app" / "app.py")


def run(dates=None, timeout=60):
    at = AppTest.from_file(APP, default_timeout=timeout)
    at.run()
    if dates:
        at.date_input[0].set_value(dates).run()
    return at


def text(at):
    return " ".join(str(e.value) for e in list(at.markdown) + list(at.caption) + list(at.info) + list(at.warning))


def test_default_view_shows_saved_brief():
    at = run()
    assert not at.exception
    assert at.metric[0].value == "360,129"
    assert "Saved report for this view" in text(at)
    assert len(at.expander) == 5


def test_short_range_warns():
    at = run((dt.date(2020, 12, 1), dt.date(2020, 12, 1)))
    assert not at.exception
    assert any("Pick at least a week" in w.value for w in at.warning)


def test_other_range_offers_button_not_saved_report():
    at = run((dt.date(2020, 11, 1), dt.date(2020, 11, 30)))
    assert not at.exception
    assert "Saved report for this view" not in text(at)
    assert any(b.label == "Generate AI brief" for b in at.button)
