import json
import pytest
from claude_usage import settings as S


def test_load_without_file_returns_defaults_copy():
    d = S.load()
    assert d == S.DEFAULTS
    d["menubar"]["fields"].append("week_left")
    assert S.DEFAULTS["menubar"]["fields"] == ["five_pct", "five_left", "week_pct"]


def test_file_overrides_nested_key_keeps_siblings():
    S.settings_path().write_text(json.dumps({"menubar": {"style": "text"}, "dashboard": {"port": 50000}}))
    d = S.load()
    assert d["menubar"]["style"] == "text"
    assert d["menubar"]["fields"] == S.DEFAULTS["menubar"]["fields"]
    assert d["dashboard"]["port"] == 50000
    assert d["dashboard"]["idle_exit_min"] == 30


@pytest.mark.parametrize("over", [
    {"menubar": {"fields": ["nope"]}},
    {"menubar": {"style": "neon"}},
    {"menubar": {"show_when": {"mode": "sometimes"}}},
    {"menubar": {"thresholds": {"warn": 101}}},
    {"data": {"poll_interval": 10}},
    {"dashboard": {"port": 80}},
    {"pricing": {"m": {"in": "x"}}},
])
def test_invalid_values_raise(over):
    S.settings_path().write_text(json.dumps(over))
    with pytest.raises(ValueError):
        S.load()


def test_save_then_load_roundtrip():
    d = S.load()
    d["menubar"]["fields"] = ["week_pct", "today_cost"]
    d["pricing"]["claude-x"] = {"in": 1, "out": 2, "cache_w": 1.25, "cache_r": 0.1}
    S.save(d)
    assert S.load()["menubar"]["fields"] == ["week_pct", "today_cost"]
    assert S.load()["pricing"]["claude-x"]["cache_w"] == 1.25


def test_corrupt_file_raises():
    S.settings_path().write_text("{not json")
    with pytest.raises(ValueError):
        S.load()
