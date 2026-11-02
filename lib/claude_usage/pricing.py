import json
from pathlib import Path

_BUILTIN = {k: v for k, v in json.loads((Path(__file__).parent / "pricing.json").read_text()).items() if not k.startswith("_")}


def table(settings) -> dict:
    t = dict(_BUILTIN)
    t.update(settings.get("pricing") or {})
    return t


def rate(model, t) -> dict:
    if model in t:
        return t[model]
    best = max((k for k in t if k != "default" and model.startswith(k)), key=len, default=None)
    return t[best] if best else t["default"]


def cost(model, inp, out, cw, cr, t) -> float:
    r = rate(model or "", t)
    return (inp * r["in"] + out * r["out"] + cw * r["cache_w"] + cr * r["cache_r"]) / 1e6


def cost_sql(t) -> str:
    """SQL CASE expression computing cost per row (USD) for the given table — keeps aggregation in sqlite."""
    cases = []
    for k in sorted((k for k in t if k != "default"), key=len, reverse=True):
        r = t[k]
        cases.append(f"WHEN model LIKE '{k}%' THEN (input*{r['in']}+output*{r['out']}+cache_w*{r['cache_w']}+cache_r*{r['cache_r']})/1e6")
    d = t["default"]
    return f"CASE {' '.join(cases)} ELSE (input*{d['in']}+output*{d['out']}+cache_w*{d['cache_w']}+cache_r*{d['cache_r']})/1e6 END"
