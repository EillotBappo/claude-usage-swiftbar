"""Optional token-savings sources (rtk, distill, context-mode). Each is best-effort; absent tools are skipped."""
import json, os, shutil, sqlite3, subprocess
from pathlib import Path

TOOLS = Path(os.environ.get("CLAUDE_USAGE_TOOLS") or "~/.claude/tools").expanduser()


def _rtk():
    exe = shutil.which("rtk")
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "gain", "--json"], capture_output=True, text=True, timeout=10).stdout
        d = json.loads(out)
        return {"saved_tokens": d.get("total_saved") or d.get("saved_tokens") or d.get("tokens_saved"),
                "commands": d.get("commands") or d.get("total_commands"), "raw": d}
    except Exception:
        try:
            txt = subprocess.run([exe, "gain"], capture_output=True, text=True, timeout=10).stdout
            return {"text": txt.strip()[:2000]} if txt.strip() else None
        except Exception:
            return None


def _sqlite_totals(path, candidates):
    if not path.exists():
        return None
    try:
        c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table, cols in candidates:
            if table in tables:
                have = {r[1] for r in c.execute(f"PRAGMA table_info({table})")}
                sel = [f"SUM({col}) {alias}" for col, alias in cols if col in have]
                if sel:
                    r = c.execute(f"SELECT COUNT(*) rows, {', '.join(sel)} FROM {table}").fetchone()
                    keys = ["rows"] + [alias for col, alias in cols if col in have]
                    return {k: (int(v) if v is not None else 0) for k, v in zip(keys, r)}
        return {"tables": sorted(tables)}
    except Exception:
        return None


def collect(settings=None):
    src = {}
    r = _rtk()
    if r: src["rtk"] = r
    d = _sqlite_totals(TOOLS / "distill.db", [
        ("logs", [("original_tokens", "original_tokens"), ("compressed_tokens", "compressed_tokens"), ("tokens_saved", "saved_tokens")]),
        ("compressions", [("original_tokens", "original_tokens"), ("compressed_tokens", "compressed_tokens"), ("saved_tokens", "saved_tokens")]),
    ])
    if d: src["distill"] = d
    c = _sqlite_totals(TOOLS / "context_mode.db", [
        ("files", [("tokens", "tokens"), ("hits", "cache_hits"), ("cache_hits", "cache_hits"), ("tokens_saved", "saved_tokens")]),
        ("tracked_files", [("tokens", "tokens"), ("cache_hits", "cache_hits"), ("saved_tokens", "saved_tokens")]),
    ])
    if c: src["context_mode"] = c
    return {"available": bool(src), "sources": src}
