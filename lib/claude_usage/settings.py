import copy, json, os
from pathlib import Path

FIELDS = ["five_pct", "five_left", "week_pct", "week_left", "today_tokens", "today_cost", "week_tokens"]
STYLES = ["pill", "icon", "text", "compact"]
SHOW_MODES = ["always", "apps"]

DEFAULTS = {
    "menubar": {
        "fields": ["five_pct", "five_left", "week_pct"],
        "style": "pill",
        "thresholds": {"warn": 75, "danger": 90},
        "show_when": {"mode": "always", "apps": ["zed", "Claude"]},
        "hide_below_pct": 0,
        "dropdown": {"charts": True, "days": 14},
    },
    "data": {
        "poll_interval": 300,
        "scan_days": 90,
        "roots": ["~/.claude/projects"],
        "include": [],
        "exclude": [],
        "project_labels": {},
    },
    "pricing": {},
    "dashboard": {"port": 48123, "idle_exit_min": 30, "default_range": "7d"},
}


def config_dir() -> Path:
    p = Path(os.environ.get("CLAUDE_USAGE_HOME") or "~/.config/claude-usage").expanduser()
    p.mkdir(parents=True, exist_ok=True)
    return p


def cache_dir() -> Path:
    p = Path(os.environ.get("CLAUDE_USAGE_CACHE") or "~/.cache/claude-usage").expanduser()
    p.mkdir(parents=True, exist_ok=True)
    return p


def settings_path() -> Path:
    return config_dir() / "settings.json"


def _merge(base, over):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _int(d, key, lo, hi):
    v = d.get(key)
    if not isinstance(v, int) or isinstance(v, bool) or not (lo <= v <= hi):
        raise ValueError(f"{key} must be an integer in [{lo}, {hi}]")


def validate(d: dict) -> dict:
    m, data, dash = d["menubar"], d["data"], d["dashboard"]
    bad = [f for f in m["fields"] if f not in FIELDS]
    if bad:
        raise ValueError(f"unknown menubar fields: {bad}")
    if m["style"] not in STYLES:
        raise ValueError(f"style must be one of {STYLES}")
    if m["show_when"]["mode"] not in SHOW_MODES:
        raise ValueError(f"show_when.mode must be one of {SHOW_MODES}")
    if not isinstance(m["show_when"].get("apps"), list):
        raise ValueError("show_when.apps must be a list")
    _int(m["thresholds"], "warn", 0, 100)
    _int(m["thresholds"], "danger", 0, 100)
    _int(m, "hide_below_pct", 0, 100)
    _int(m["dropdown"], "days", 1, 365)
    _int(data, "poll_interval", 60, 3600)
    _int(data, "scan_days", 1, 3650)
    for k in ("roots", "include", "exclude"):
        if not isinstance(data[k], list) or not all(isinstance(x, str) for x in data[k]):
            raise ValueError(f"data.{k} must be a list of strings")
    if not isinstance(data["project_labels"], dict):
        raise ValueError("data.project_labels must be an object")
    _int(dash, "port", 1024, 65535)
    _int(dash, "idle_exit_min", 1, 1440)
    for model, p in d["pricing"].items():
        if not isinstance(p, dict) or not all(isinstance(p.get(k), (int, float)) for k in ("in", "out", "cache_w", "cache_r")):
            raise ValueError(f"pricing.{model} needs numeric in/out/cache_w/cache_r")
    return d


def load() -> dict:
    p = settings_path()
    over = {}
    if p.exists():
        try:
            over = json.loads(p.read_text() or "{}")
        except json.JSONDecodeError as e:
            raise ValueError(f"{p}: {e}")
    return validate(_merge(DEFAULTS, over))


def save(d: dict) -> None:
    validate(_merge(DEFAULTS, d))
    p = settings_path()
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, indent=2) + "\n")
    tmp.replace(p)
