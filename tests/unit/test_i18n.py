"""UX-C: CN/EN presentation layer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from app import i18n
from app.i18n import LOCALE_KEY, clear_locale_cache, get_locale, t
from app.progress_chrome import derive_progress_chrome

ROOT = Path(__file__).resolve().parents[2]
APP_PATH = str(ROOT / "app" / "main.py")
LOCALES = ROOT / "locales"


@pytest.fixture(autouse=True)
def _reset_locale_cache():
    clear_locale_cache()
    yield
    clear_locale_cache()


def test_locale_packs_are_aligned():
    en = json.loads((LOCALES / "en.json").read_text(encoding="utf-8"))
    zh = json.loads((LOCALES / "zh.json").read_text(encoding="utf-8"))
    assert set(en) == set(zh)
    assert len(en) >= 400
    assert en["h1.approve"] == "Approve research plan (H1)"
    assert "批准" in zh["h1.approve"]
    assert en["project.init_ok"] == "Project initialized — analysis not started."


def test_t_defaults_to_english_without_streamlit_session():
    assert get_locale() == "en"
    assert t("chrome.title") == "MCM C Research Lab"
    assert t("h1.approve") == "Approve research plan (H1)"
    assert "Phase 5" not in t("progress.caption.base")


def test_progress_chrome_translates_when_locale_zh(monkeypatch):
    chrome_en = derive_progress_chrome(None)
    assert chrome_en.milestone_metric == "Project"
    assert chrome_en.progress_metric.endswith("steps") or "/9" in chrome_en.progress_metric

    monkeypatch.setattr(i18n, "_session_locale", lambda: "zh")
    chrome_zh = derive_progress_chrome(None)
    assert chrome_zh.milestone_metric == "项目"
    assert "步" in chrome_zh.progress_metric
    assert "Phase 5" not in chrome_zh.sidebar_badge
    assert "Phase 5" not in chrome_zh.caption


def test_apptest_language_toggle_switches_primary_chrome():
    at = AppTest.from_file(APP_PATH, default_timeout=60).run()
    assert not at.exception
    messages = "\n".join(
        [
            *(str(x.value) for x in at.title),
            *(str(x.value) for x in at.caption),
            *(str(x.label) for x in at.button),
        ]
    )
    assert "MCM C Research Lab" in messages or any(
        "MCM C Research Lab" in str(x.value) for x in at.title
    )
    assert any(b.label == "Initialize project" for b in at.button)

    # Language selectbox is first selectbox in sidebar (key ui_locale).
    lang = next(s for s in at.selectbox if s.key == LOCALE_KEY or s.label in {"Language", "语言"})
    at = lang.set_value("zh").run()
    assert not at.exception
    titles = [str(x.value) for x in at.title]
    assert any("研究实验室" in title for title in titles)
    assert any(b.label == "初始化项目" for b in at.button)
    # Primary path should not keep the English init button after toggle.
    assert all(b.label != "Initialize project" for b in at.button)


def test_apptest_default_keeps_english_nav_radio_index():
    """Regression: language control must not steal radio[0] from Navigation."""
    at = AppTest.from_file(APP_PATH, default_timeout=60).run()
    assert at.radio
    # Same contract as test_foundation_app: radio[0] is Navigation.
    at = at.radio[0].set_value("API Settings").run()
    assert not at.exception
    at = at.radio[0].set_value("Research Lab").run()
    assert not at.exception
    assert any(b.label == "Initialize project" for b in at.button)
