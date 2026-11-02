# claude-usage-swiftbar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** SwiftBar plugin showing Claude Code quota + token usage in the menubar, with a local web dashboard (filters, date ranges, quota history, cost, settings) and a public installable repo.

**Architecture:** Thin bash SwiftBar plugin dispatches to a Python package. An incremental scanner indexes `~/.claude/projects/**/*.jsonl` into SQLite; a quota module polls Anthropic's OAuth usage endpoint and logs history; `menubar.py` renders SwiftBar text from settings; `server.py` (stdlib) serves a JSON API + static vanilla-JS dashboard.

**Tech Stack:** bash, Python 3.9+ stdlib (`sqlite3`, `http.server`, `json`, `urllib`), optional Pillow, vanilla JS + inline SVG, pytest for tests.

## Global Constraints

- No third-party Python deps required at runtime. Pillow optional (text rows fall back to plain text).
- All data local. Only network call: `https://api.anthropic.com/api/oauth/usage`.
- Settings file: `~/.config/claude-usage/settings.json`. Cache dir: `~/.cache/claude-usage/` (`usage.db`, `quota.json`, `quota.backoff`).
- Dashboard binds `127.0.0.1` only. Default port 48123.
- Paths overridable via env `CLAUDE_USAGE_HOME` (config) and `CLAUDE_USAGE_CACHE` (cache) so tests use tmp dirs.
- Repo root: `~/Projects/claude-usage-swiftbar`. Package import path: `lib/` (tests add it to `sys.path` via `tests/conftest.py`).

---

### Task 1: Settings

**Files:** Create `lib/claude_usage/__init__.py`, `lib/claude_usage/settings.py`, `tests/conftest.py`, `tests/test_settings.py`

**Produces:** `DEFAULTS: dict`; `load() -> dict` (defaults deep-merged with file, validated); `save(d: dict) -> None`; `validate(d) -> dict` (raises `ValueError` on bad field names/styles/ints); `config_dir() -> Path`, `cache_dir() -> Path` (env-overridable, created on demand). `FIELDS = ["five_pct","five_left","week_pct","week_left","today_tokens","today_cost","week_tokens"]`, `STYLES = ["pill","icon","text","compact"]`.

- [ ] Test: load without file returns DEFAULTS copy; file overrides nested key keeps siblings; invalid field → ValueError; save then load roundtrip.
- [ ] Implement; run `pytest tests/test_settings.py`; commit `feat: settings`.

### Task 2: DB + scanner

**Files:** Create `lib/claude_usage/db.py`, `lib/claude_usage/scan.py`, `tests/fixtures/*.jsonl`, `tests/test_scan.py`

**Produces:** `db.connect() -> sqlite3.Connection` (WAL, schema v1: `messages`, `files`, `quota`, `meta`); `scan.run(conn, settings, now=None) -> dict(files, added)`; `scan.project_of(cwd, path, labels) -> str`.

Rules: dedupe on `(msg_id, request_id)`; rows lacking msg_id keyed `(session, ts)`; incremental via `files(path, mtime, size, offset)` — read from offset if size grew and mtime changed, restart at 0 if size shrank; skip files older than `scan_days` by mtime; usage fields `input_tokens, output_tokens, cache_creation_input_tokens, cache_read_input_tokens, output_tokens_details.thinking_tokens`; `day` local `YYYY-MM-DD`, `hour` local 0-23, `weekday` 0-6.

- [ ] Tests: two fixtures (dup lines, missing usage, bad json); first run adds N; second run adds 0; append line → adds 1; truncate → reindex; label map applied.
- [ ] Implement; commit `feat: sqlite schema + incremental scanner`.

### Task 3: Pricing

**Files:** Create `lib/claude_usage/pricing.py`, `lib/claude_usage/pricing.json`, `tests/test_pricing.py`

**Produces:** `cost(model, inp, out, cw, cr, table) -> float` (USD; unknown model → prefix match e.g. `claude-opus-*` → fallback `default` entry); `table(settings) -> dict` (pricing.json merged with `settings["pricing"]`). Per-MTok keys `in,out,cache_w,cache_r`.

- [ ] Tests: exact model, prefix match, default, settings override.
- [ ] Implement; commit `feat: pricing`.

### Task 4: Quota

**Files:** Create `lib/claude_usage/quota.py`, `tests/test_quota.py`

**Produces:** `fetch(conn, settings, now, http=urlopen, keychain=read_token) -> dict|None` (respects poll_interval + 600 s backoff; writes `quota.json`, inserts `quota` row); `current() -> dict|None` (cached JSON + `age_s`); `left_minutes(window, now) -> int`; `history(conn, from_ts, to_ts) -> list`.

- [ ] Tests with injected fake http/keychain: 200 writes cache + row; 429 sets backoff and keeps old cache; no token → None; poll interval respected.
- [ ] Implement; commit `feat: quota fetch + history`.

### Task 5: Queries

**Files:** Create `lib/claude_usage/queries.py`, `tests/test_queries.py`

**Produces:** `Filters(from_day, to_day, projects, models, sessions)` dataclass + `Filters.from_query(dict)`; `summary(conn, f, pricing)`, `series(conn, f, pricing, bucket)`, `heatmap(conn, f)`, `breakdown(conn, f, pricing, by)` returning plain dicts/lists ready for JSON. Cache hit % = `cache_r / (input + cache_w + cache_r)`.

- [ ] Tests on fixture-seeded DB: totals, filter by project/model/day range, bucket day vs hour, breakdown sorted desc.
- [ ] Implement; commit `feat: query layer`.

### Task 6: Savings (optional integration)

**Files:** Create `lib/claude_usage/savings.py`, `tests/test_savings.py`

**Produces:** `collect(settings) -> dict` → `{"available": False}` or `{"available": True, "sources": {"rtk": {...}, "distill": {...}, "context_mode": {...}}}`. rtk via `rtk gain --json` if binary found (fallback parse text), distill/context via sqlite at `~/.claude/tools/*.db` if present. Every source wrapped in try → omitted on failure.

- [ ] Tests: no tools → available False; fake distill.db → parsed.
- [ ] Implement; commit `feat: optional savings sources`.

### Task 7: Menubar renderer

**Files:** Create `lib/claude_usage/menubar.py`, `lib/claude_usage/render.py` (PNG helpers ported from current plugin: `bar`, `chart`, `row` with Pillow fallback), `tests/test_menubar.py`

**Produces:** `menubar.render(settings, quota, stats, now) -> str` (full SwiftBar output); `menubar.visible(settings, running_apps) -> bool`; `main()` entry: load settings → visibility (pgrep) → scan → quota.fetch → print. CLI: `python3 -m claude_usage.menubar`.

- [ ] Tests: fields order/style; thresholds color; show_when apps hidden/visible; hide_below_pct; stale marker; no-quota fallback line.
- [ ] Implement; commit `feat: menubar renderer`.

### Task 8: HTTP server + API

**Files:** Create `lib/claude_usage/server.py`, `tests/test_api.py`

**Produces:** `make_server(settings, port=0) -> ThreadingHTTPServer`; routes per spec (`/api/ping, summary, series, heatmap, breakdown, quota, savings, settings GET/PUT`), static from `lib/claude_usage/dashboard/`, idle-exit thread; `main(argv)`: `--port`, `--open [tab]`. `ensure_running(settings) -> url` used by plugin (ping → else spawn detached).

- [ ] Tests: server on port 0; each endpoint 200 + shape; PUT settings invalid → 400; unknown → 404.
- [ ] Implement; commit `feat: dashboard server + api`.

### Task 9: Dashboard front end

**Files:** Create `lib/claude_usage/dashboard/index.html`, `app.js`, `style.css`

Tabs Overview / Tokens / Quota / Projects / Sessions / Savings / Settings. Filter bar: presets today/7d/30d/month/custom (two date inputs) + multi-selects for project/model/session populated from `/api/breakdown`. State in `location.hash`. Charts: `stackedBars(el, series, keys)`, `line(el, points, markers)`, `heatmap(el, grid)`, `donut(el, rows)` as SVG string builders. Settings tab renders form from `/api/settings`, PUT on save, shows toast. Dark mode via `prefers-color-scheme`.

- [ ] Manual check in Chrome against seeded DB (Puppeteer smoke: each tab renders, filter changes URL + numbers).
- [ ] Commit `feat: dashboard ui`.

### Task 10: Plugin script, install, docs

**Files:** Create `claude-usage.1m.sh`, `install.sh`, `uninstall.sh`, `README.md`

Plugin: metadata header; `PATH` fix; `cd "$(dirname "$(readlink -f "$0")")"`; actions `refresh` (expire cache), `open [tab]` (server.ensure_running + `open`), default → `python3 -m claude_usage.menubar`. Install: clone/copy to `~/.claude-usage-swiftbar`, back up + replace existing `~/.swiftbar/claude-usage.1m.sh` and `lib/claude-usage.py`, symlink plugin into SwiftBar dir, seed settings, initial scan, `open -g swiftbar://refreshallplugins`. README: features, screenshots, install one-liner (`curl -fsSL https://raw.githubusercontent.com/EillotBappo/claude-usage-swiftbar/main/install.sh | bash`), settings reference, privacy, uninstall.

- [ ] Run install locally; verify SwiftBar item + dashboard open.
- [ ] Commit `feat: plugin, installer, readme`; create GitHub repo `EillotBappo/claude-usage-swiftbar` (public, MIT); push.
