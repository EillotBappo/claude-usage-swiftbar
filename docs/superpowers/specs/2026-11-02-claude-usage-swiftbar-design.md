# claude-usage-swiftbar — design

Date: 2026-11-02. Status: approved.

## Goal

A SwiftBar menubar plugin for Claude Code usage with (a) a customizable menubar readout, (b) a local web dashboard with full token history, filters, date ranges, quota history, cost estimates and settings, and (c) a public repo others can install from.

## Non-goals

Multi-user/auth, CSV export, threshold notifications, native SwiftUI window. All deferred.

## Requirements

macOS, SwiftBar, system `python3` (3.9+), Claude Code logged in (OAuth creds in Keychain under `Claude Code-credentials`). Pillow optional: used for crisp white text rows in the dropdown; absent → plain SwiftBar text.

## Layout

```
claude-usage.1m.sh               SwiftBar plugin; dispatches to python
lib/claude_usage/
  __init__.py
  settings.py                    defaults, load/merge/validate, save
  db.py                          sqlite open + schema + migrations
  scan.py                        incremental jsonl indexer
  quota.py                       OAuth usage fetch, cache, backoff, history
  pricing.py  pricing.json       $/MTok per model; cost calc
  savings.py                     optional rtk/distill/context-mode readers
  menubar.py                     SwiftBar output renderer
  server.py                      stdlib HTTP server: JSON API + static
  dashboard/index.html  app.js  style.css
install.sh  uninstall.sh  README.md  LICENSE (MIT)  tests/
```

## Data

SQLite `~/.cache/claude-usage/usage.db` (WAL).

- `messages(id PK, ts INTEGER, day TEXT, hour INT, model, project, cwd, session, msg_id, request_id, input, output, cache_w, cache_r, thinking)` — unique on `(msg_id, request_id)`; rows without `msg_id` are keyed by `(session, ts)`.
- `files(path PK, mtime REAL, size INTEGER, offset INTEGER)` — incremental: on each scan, files whose `mtime`/`size` changed are read from `offset` (shrunk/rotated file → restart from 0).
- `quota(ts PK, five_pct, five_reset, week_pct, week_reset, raw JSON)` — one row per successful fetch.
- `meta(key, value)` — schema version, last scan.

Project = basename of `cwd` (fallback: project dir name under `~/.claude/projects`), with an optional `project_labels` map in settings. Scan roots default to `~/.claude/projects`; settings may add roots and include/exclude globs.

Scan runs from the menubar tick (every refresh) and from the server on API calls when the last scan is older than 60 s. Scan cost after first index: only appended bytes.

## Quota

Same approach as today: fetch `https://api.anthropic.com/api/oauth/usage` with bearer token from Keychain, at most every `poll_interval` (default 300 s), 600 s backoff after any error, cache last good reply at `~/.cache/claude-usage/quota.json`. Each success also appends to `quota` table. Countdowns computed locally.

## Settings

`~/.config/claude-usage/settings.json`, merged over defaults:

```json
{
  "menubar": {
    "fields": ["five_pct", "five_left", "week_pct"],
    "style": "pill",            // pill | icon | text | compact
    "thresholds": {"warn": 75, "danger": 90},
    "show_when": {"mode": "always", "apps": ["zed", "Claude"]},   // always | apps
    "hide_below_pct": 0,
    "dropdown": {"charts": true, "days": 14}
  },
  "data": {"poll_interval": 300, "scan_days": 90, "roots": ["~/.claude/projects"],
           "include": [], "exclude": [], "project_labels": {}},
  "pricing": {"claude-fable-5-1": {"in": 15, "out": 75, "cache_w": 18.75, "cache_r": 1.5}, "...": {}},
  "dashboard": {"port": 48123, "idle_exit_min": 30, "default_range": "7d"}
}
```

Available menubar fields: `five_pct`, `five_left`, `week_pct`, `week_left`, `today_tokens`, `today_cost`, `week_tokens`. Order = display order.

## Menubar (`menubar.py`)

1. Evaluate `show_when`; if hidden, print nothing (SwiftBar hides the item).
2. Title line from `fields` + `style`; color by worst utilization vs thresholds.
3. Dropdown: quota rows with progress bars, today/7-day tokens + est. cost, daily chart, hour chart, top models (as today), then `Open dashboard`, `Settings…`, `Refresh now`.

## Dashboard (`server.py` + static)

Server: `http.server.ThreadingHTTPServer` on `127.0.0.1:<port>`. `claude-usage.1m.sh open [tab]` → if port answers `/api/ping`, open browser; else spawn server detached (`nohup`) then open. Server exits after `idle_exit_min` without requests.

API (all JSON; filters as query: `from`, `to` (ISO dates, inclusive), `project`, `model`, `session` — comma lists):

- `GET /api/ping`
- `GET /api/summary` → totals, cost, cache hit %, sessions, messages
- `GET /api/series?bucket=day|hour` → per-bucket in/out/cache_w/cache_r/cost
- `GET /api/heatmap` → weekday×hour totals
- `GET /api/breakdown?by=model|project|session` → rows with totals/cost/first/last
- `GET /api/quota` → current + history in range
- `GET /api/savings` → `{available:false}` or rtk/distill/context-mode totals
- `GET|PUT /api/settings` → validated; PUT writes file
- `GET /api/pricing` (part of settings)

Front end: vanilla JS, inline SVG charts, no network. Filter bar (date presets today/7d/30d/month/custom + project/model/session multi-select) persisted in URL hash. Tabs: Overview, Tokens, Quota, Projects, Sessions, Savings (hidden when unavailable), Settings. Light/dark via `prefers-color-scheme`.

## Install

`install.sh`: copy/clone to `~/.claude-usage-swiftbar`, symlink `claude-usage.1m.sh` into SwiftBar plugin dir (`defaults read com.ameba.SwiftBar PluginDirectory`, fallback `~/.swiftbar`), `chmod +x`, write default settings if missing, run one initial scan, tell SwiftBar to refresh. `uninstall.sh` removes the symlink; leaves data unless `--purge`.

Migration from the current personal plugin: install replaces `~/.swiftbar/claude-usage.1m.sh` and `~/.swiftbar/lib/claude-usage.py` (backed up to `*.bak`); the Zed gate becomes `show_when.mode = "apps"` in the seeded settings for this machine only.

## Errors

No creds / 401 → menubar shows "✳︎ sign in" with a hint row; dashboard still works on local data. 429/network → stale marker as today. Corrupt jsonl line → skipped. DB locked → retry 3× then skip tick.

## Testing

pytest in `tests/`: `test_scan.py` (fixture jsonl: dedupe, incremental offset, truncated file restart, project mapping), `test_pricing.py`, `test_settings.py` (merge, validation, bad values), `test_api.py` (spin server on port 0, hit each endpoint, filter combos), `test_menubar.py` (field order, styles, show_when, thresholds). Manual: SwiftBar render, dashboard smoke in Chrome.
