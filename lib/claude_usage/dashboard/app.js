/* Claude Usage dashboard — vanilla JS, inline SVG, no deps. State lives in location.hash. */
const $ = (s, el = document) => el.querySelector(s), $$ = (s, el = document) => [...el.querySelectorAll(s)];
const C = { input: 'var(--blue)', output: 'var(--accent)', cache_w: 'var(--purple)', cache_r: 'var(--teal)' };
const KEYS = ['input', 'output', 'cache_w', 'cache_r'], LABELS = { input: 'input', output: 'output', cache_w: 'cache write', cache_r: 'cache read' };
const PALETTE = ['var(--accent)', 'var(--blue)', 'var(--purple)', 'var(--teal)', 'var(--green)', 'var(--amber)', '#8e8e93', '#ff6482'];
let state = { tab: 'overview', range: '7d', from: '', to: '', project: [], model: [], session: [], bucket: 'day', metric: 'new_tokens', sort: {} };
let settingsDoc = null, options = { projects: [], models: [], sessions: [] };

const fmt = n => n >= 1e9 ? (n / 1e9).toFixed(2) + 'B' : n >= 1e6 ? (n / 1e6).toFixed(1) + 'M' : n >= 1e3 ? Math.round(n / 1e3) + 'K' : String(Math.round(n || 0));
const money = x => x >= 100 ? '$' + Math.round(x).toLocaleString() : x >= 1 ? '$' + x.toFixed(2) : '$' + (x || 0).toFixed(3);
const pct = x => Math.round((x || 0) * 100) + '%';
const dstr = d => d.toISOString().slice(0, 10);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const ago = ts => { const s = Date.now() / 1000 - ts; return s < 3600 ? Math.round(s / 60) + 'm ago' : s < 86400 ? Math.round(s / 3600) + 'h ago' : Math.round(s / 86400) + 'd ago'; };

/* ---------- state <-> hash ---------- */
function readHash() {
  const h = new URLSearchParams(location.hash.slice(1));
  for (const k of ['tab', 'range', 'from', 'to', 'bucket', 'metric']) if (h.has(k)) state[k] = h.get(k);
  for (const k of ['project', 'model', 'session']) state[k] = h.get(k) ? h.get(k).split(',') : [];
}
function writeHash() {
  const h = new URLSearchParams();
  for (const k of ['tab', 'range', 'from', 'to', 'bucket', 'metric']) if (state[k]) h.set(k, state[k]);
  for (const k of ['project', 'model', 'session']) if (state[k].length) h.set(k, state[k].join(','));
  history.replaceState(null, '', '#' + h.toString());
}
function dateRange() {
  if (state.from || state.to) return { from: state.from, to: state.to };
  const t = new Date(); t.setHours(12);
  const to = dstr(t), d = new Date(t);
  if (state.range === 'all') return { from: '', to: '' };
  if (state.range === 'month') { d.setDate(1); return { from: dstr(d), to }; }
  d.setDate(d.getDate() - ({ today: 0, '7d': 6, '30d': 29, '90d': 89 }[state.range] ?? 6));
  return { from: dstr(d), to };
}
function qs(extra = {}) {
  const r = dateRange(), p = new URLSearchParams();
  if (r.from) p.set('from', r.from); if (r.to) p.set('to', r.to);
  for (const k of ['project', 'model', 'session']) if (state[k].length) p.set(k, state[k].join(','));
  for (const [k, v] of Object.entries(extra)) p.set(k, v);
  return '?' + p.toString();
}
const api = async (path, opts) => { const r = await fetch(path, opts); const j = await r.json(); if (!r.ok) throw new Error(j.error || r.status); return j; };

/* ---------- SVG chart builders ---------- */
const tip = document.body.appendChild(Object.assign(document.createElement('div'), { className: 'tip' }));
function attachTips(el) {
  el.addEventListener('mousemove', e => { const t = e.target.closest('[data-tip]'); if (!t) { tip.style.display = 'none'; return; }
    tip.textContent = t.dataset.tip; tip.style.display = 'block'; tip.style.left = Math.min(e.clientX + 12, innerWidth - 240) + 'px'; tip.style.top = (e.clientY + 12) + 'px'; });
  el.addEventListener('mouseleave', () => tip.style.display = 'none');
}
function axisY(max, h, pad, fmtFn) {
  const steps = 4, out = [];
  for (let i = 0; i <= steps; i++) { const v = max * i / steps, y = pad.t + (h - pad.t - pad.b) * (1 - i / steps);
    out.push(`<line x1="${pad.l}" x2="100%" y1="${y}" y2="${y}" stroke="var(--grid)"/><text x="${pad.l - 6}" y="${y + 4}" text-anchor="end" fill="var(--muted)" font-size="11">${fmtFn(v)}</text>`); }
  return out.join('');
}
function stackedBars(el, rows, keys, { label = r => r.bucket, fmtFn = fmt, valueOf = null, single = null } = {}) {
  const W = el.clientWidth || 800, H = el.clientHeight || 220, pad = { l: 48, r: 8, t: 10, b: 26 };
  if (!rows.length) { el.innerHTML = '<div class="empty">No data in range</div>'; return; }
  const tot = r => single ? (valueOf ? valueOf(r) : r[single]) : keys.reduce((a, k) => a + (r[k] || 0), 0);
  const max = Math.max(...rows.map(tot), 1), n = rows.length, gap = Math.max(1, Math.min(6, (W - pad.l - pad.r) / n * .25));
  const bw = (W - pad.l - pad.r - gap * (n - 1)) / n, sy = (H - pad.t - pad.b) / max;
  let s = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">` + axisY(max, H, pad, fmtFn);
  rows.forEach((r, i) => {
    const x = pad.l + i * (bw + gap); let y = H - pad.b;
    const tipText = `${label(r)}\n` + (single ? fmtFn(tot(r)) : keys.map(k => `${LABELS[k]}: ${fmt(r[k] || 0)}`).join('\n') + `\ncost: ${money(r.cost || 0)}`);
    if (single) { const hgt = tot(r) * sy; s += `<rect x="${x}" y="${y - hgt}" width="${bw}" height="${Math.max(hgt, tot(r) ? 1 : 0)}" fill="var(--accent)" rx="2" data-tip="${esc(tipText)}"/>`; }
    else for (const k of keys) { const hgt = (r[k] || 0) * sy; if (hgt > 0) s += `<rect x="${x}" y="${y - hgt}" width="${bw}" height="${hgt}" fill="${C[k]}" data-tip="${esc(tipText)}"/>`; y -= hgt; }
    if (n <= 31 || i % Math.ceil(n / 16) === 0) s += `<text x="${x + bw / 2}" y="${H - 8}" text-anchor="middle" fill="var(--muted)" font-size="10">${esc(label(r).slice(n > 14 ? 5 : 0))}</text>`;
  });
  el.innerHTML = s + '</svg>'; attachTips(el);
}
function line(el, pts, { max = 100, danger = null, fmtFn = v => v + '%', resets = [] } = {}) {
  const W = el.clientWidth || 800, H = el.clientHeight || 220, pad = { l: 40, r: 8, t: 10, b: 26 };
  if (pts.length < 1) { el.innerHTML = '<div class="empty">No quota history yet — it fills in as the menubar polls</div>'; return; }
  const t0 = pts[0].t, t1 = Math.max(pts[pts.length - 1].t, t0 + 3600), sx = (W - pad.l - pad.r) / (t1 - t0), sy = (H - pad.t - pad.b) / max;
  const X = t => pad.l + (t - t0) * sx, Y = v => H - pad.b - v * sy;
  let s = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">` + axisY(max, H, pad, fmtFn);
  if (danger != null) s += `<line x1="${pad.l}" x2="${W - pad.r}" y1="${Y(danger)}" y2="${Y(danger)}" stroke="var(--red)" stroke-dasharray="4 4" opacity=".7"/>`;
  for (const r of resets) if (r >= t0 && r <= t1) s += `<line x1="${X(r)}" x2="${X(r)}" y1="${pad.t}" y2="${H - pad.b}" stroke="var(--muted)" stroke-dasharray="2 3" opacity=".5"/>`;
  const d = pts.map((p, i) => `${i ? 'L' : 'M'}${X(p.t).toFixed(1)},${Y(p.v).toFixed(1)}`).join(' ');
  s += `<path d="${d} L${X(pts[pts.length - 1].t)},${Y(0)} L${X(t0)},${Y(0)} Z" fill="var(--accent)" opacity=".12"/><path d="${d}" fill="none" stroke="var(--accent)" stroke-width="2"/>`;
  for (const p of pts) s += `<circle cx="${X(p.t)}" cy="${Y(p.v)}" r="${pts.length > 300 ? 1.5 : 3}" fill="var(--accent)" data-tip="${esc(new Date(p.t * 1000).toLocaleString() + '\n' + fmtFn(p.v))}"/>`;
  const ticks = 6; for (let i = 0; i <= ticks; i++) { const t = t0 + (t1 - t0) * i / ticks, dt = new Date(t * 1000);
    s += `<text x="${X(t)}" y="${H - 8}" text-anchor="middle" fill="var(--muted)" font-size="10">${(t1 - t0) > 2 * 86400 ? dt.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</text>`; }
  el.innerHTML = s + '</svg>'; attachTips(el);
}
function heatmap(el, grid) {
  const W = el.clientWidth || 800, H = el.clientHeight || 220, pad = { l: 34, t: 6, b: 18 }, cw = (W - pad.l) / 24, ch = (H - pad.t - pad.b) / 7;
  const max = Math.max(1, ...grid.flat()), days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  let s = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">`;
  grid.forEach((row, d) => { s += `<text x="${pad.l - 6}" y="${pad.t + d * ch + ch / 2 + 4}" text-anchor="end" fill="var(--muted)" font-size="11">${days[d]}</text>`;
    row.forEach((v, h) => s += `<rect x="${pad.l + h * cw + 1}" y="${pad.t + d * ch + 1}" width="${cw - 2}" height="${ch - 2}" rx="3" fill="var(--accent)" opacity="${v ? .15 + .85 * Math.sqrt(v / max) : .04}" data-tip="${days[d]} ${String(h).padStart(2, '0')}:00\n${fmt(v)} tokens"/>`); });
  for (let h = 0; h < 24; h += 3) s += `<text x="${pad.l + h * cw + cw / 2}" y="${H - 4}" text-anchor="middle" fill="var(--muted)" font-size="10">${String(h).padStart(2, '0')}</text>`;
  el.innerHTML = s + '</svg>'; attachTips(el);
}
function donut(el, rows, key = 'new_tokens') {
  const total = rows.reduce((a, r) => a + r[key], 0); if (!total) { el.innerHTML = '<div class="empty">No data</div>'; return; }
  const R = 80, r0 = 52, cx = 100, cy = 100; let a0 = -Math.PI / 2, s = `<svg viewBox="0 0 420 200"><g>`;
  rows.slice(0, 8).forEach((r, i) => { const a1 = a0 + 2 * Math.PI * r[key] / total, big = a1 - a0 > Math.PI ? 1 : 0;
    const p = (a, rr) => `${cx + rr * Math.cos(a)},${cy + rr * Math.sin(a)}`;
    s += `<path d="M${p(a0, R)} A${R},${R} 0 ${big} 1 ${p(a1, R)} L${p(a1, r0)} A${r0},${r0} 0 ${big} 0 ${p(a0, r0)} Z" fill="${PALETTE[i % PALETTE.length]}" data-tip="${esc(r.key)}\n${fmt(r[key])} (${pct(r[key] / total)})\n${money(r.cost)}"/>`;
    s += `<rect x="215" y="${22 + i * 21}" width="10" height="10" rx="3" fill="${PALETTE[i % PALETTE.length]}"/><text x="232" y="${31 + i * 21}" font-size="12" fill="var(--fg)">${esc(r.key.replace('claude-', ''))} <tspan fill="var(--muted)">${pct(r[key] / total)} · ${money(r.cost)}</tspan></text>`; a0 = a1; });
  s += `<text x="${cx}" y="${cy + 5}" text-anchor="middle" font-size="16" font-weight="600" fill="var(--fg)">${fmt(total)}</text></g></svg>`;
  el.innerHTML = s; attachTips(el);
}

/* ---------- tables ---------- */
function table(el, rows, cols, { key, onKey } = {}) {
  const id = el.id, sort = state.sort[id] || { c: cols[1].k, d: -1 };
  rows = [...rows].sort((a, b) => (a[sort.c] > b[sort.c] ? 1 : a[sort.c] < b[sort.c] ? -1 : 0) * sort.d);
  const max = Math.max(1, ...rows.map(r => r.new_tokens || 0));
  if (!rows.length) { el.innerHTML = '<div class="empty">No data in range</div>'; return; }
  el.innerHTML = `<table><thead><tr>${cols.map(c => `<th data-c="${c.k}" class="${sort.c === c.k ? 'on' : ''}">${c.l}${sort.c === c.k ? (sort.d < 0 ? ' ↓' : ' ↑') : ''}</th>`).join('')}</tr></thead><tbody>${rows.map(r => `<tr>${cols.map((c, i) => `<td class="${i === 0 ? 'k' : ''}" title="${esc(c.t ? c.t(r) : '')}">${i === 0 ? `<span class="bar" style="width:${Math.round(40 * (r.new_tokens || 0) / max)}px"></span>` : ''}${c.f ? c.f(r[c.k], r) : esc(r[c.k])}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
  $$('th', el).forEach(th => th.onclick = () => { const c = th.dataset.c; state.sort[id] = { c, d: sort.c === c ? -sort.d : -1 }; table(el, rows, cols, { key, onKey }); });
  if (onKey) $$('td.k', el).forEach((td, i) => td.onclick = () => onKey(rows[i]));
}
const COLS = [{ k: 'key', l: 'Name', f: v => esc(v) }, { k: 'new_tokens', l: 'New tokens', f: fmt }, { k: 'input', l: 'Input', f: fmt }, { k: 'output', l: 'Output', f: fmt },
  { k: 'cache_w', l: 'Cache write', f: fmt }, { k: 'cache_r', l: 'Cache read', f: fmt }, { k: 'cache_hit', l: 'Cache hit', f: pct }, { k: 'cost', l: 'Est. cost', f: money }, { k: 'messages', l: 'Msgs' },
  { k: 'last_ts', l: 'Last', f: v => v ? ago(v) : '', t: r => r.last_ts ? new Date(r.last_ts * 1000).toLocaleString() : '' }];

/* ---------- rendering per tab ---------- */
function kpis(el, items) { el.innerHTML = items.map(i => `<div class="kpi"><div class="l">${i.l}</div><div class="v">${i.v}</div>${i.s ? `<div class="s">${i.s}</div>` : ''}</div>`).join(''); }

async function renderOverview() {
  const [sum, series, models, quota] = await Promise.all([api('/api/summary' + qs()), api('/api/series' + qs()), api('/api/breakdown' + qs({ by: 'model' })), api('/api/quota' + qs())]);
  const q = quota.current, five = q?.five_hour?.utilization ?? null, week = q?.seven_day?.utilization ?? null;
  kpis($('#kpis'), [
    { l: 'New tokens', v: fmt(sum.new_tokens), s: `${fmt(sum.input)} in · ${fmt(sum.output)} out · ${fmt(sum.cache_w)} cache w` },
    { l: 'Cache reads', v: fmt(sum.cache_r), s: `${pct(sum.cache_hit)} cache hit` },
    { l: 'Est. cost', v: money(sum.cost), s: sum.messages ? money(sum.cost / sum.messages) + ' / message' : '' },
    { l: 'Messages', v: sum.messages.toLocaleString(), s: `${sum.sessions} sessions · ${sum.projects} projects` },
    { l: '5h window', v: five == null ? '–' : Math.round(five) + '%', s: q ? `resets ${new Date(q.five_hour.resets_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}` : 'no quota data' },
    { l: '7-day window', v: week == null ? '–' : Math.round(week) + '%', s: q ? `resets ${new Date(q.seven_day.resets_at).toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short' })}` : '' },
  ]);
  $('#legend-tokens').innerHTML = KEYS.map(k => `<span><i style="background:${C[k]}"></i>${LABELS[k]}</span>`).join('');
  stackedBars($('#chart-daily'), series, KEYS);
  line($('#chart-quota-mini'), quota.history.map(h => ({ t: h.ts, v: h.five_pct })), { danger: settingsDoc?.settings.menubar.thresholds.danger });
  donut($('#chart-models'), models);
}
async function renderTokens() {
  const [series, heat, models] = await Promise.all([api('/api/series' + qs({ bucket: state.bucket })), api('/api/heatmap' + qs()), api('/api/breakdown' + qs({ by: 'model' }))]);
  $$('[data-bucket]').forEach(b => b.classList.toggle('on', b.dataset.bucket === state.bucket));
  $$('[data-metric]').forEach(b => b.classList.toggle('on', b.dataset.metric === state.metric));
  const label = r => state.bucket === 'hour' ? r.bucket.slice(5).replace('T', ' ') : r.bucket;
  if (state.metric === 'cost') stackedBars($('#chart-tokens'), series, KEYS, { label, single: 'cost', fmtFn: money });
  else if (state.metric === 'total') stackedBars($('#chart-tokens'), series, KEYS, { label });
  else stackedBars($('#chart-tokens'), series, ['input', 'output', 'cache_w'], { label });
  heatmap($('#chart-heat'), heat);
  table($('#table-models'), models, COLS.filter(c => !['last_ts'].includes(c.k)), { onKey: r => { state.model = [r.key]; refresh(); } });
}
async function renderQuota() {
  const q = await api('/api/quota' + qs()), cur = q.current, th = settingsDoc?.settings.menubar.thresholds.danger;
  $('#poll-int').textContent = settingsDoc?.settings.data.poll_interval ?? 300;
  const over = q.history.filter(h => h.five_pct >= (th ?? 90)).length;
  kpis($('#quota-kpis'), [
    { l: '5h now', v: cur ? Math.round(cur.five_hour.utilization) + '%' : '–', s: cur ? `resets ${new Date(cur.five_hour.resets_at).toLocaleString([], { hour: '2-digit', minute: '2-digit' })}` : '' },
    { l: '7-day now', v: cur ? Math.round(cur.seven_day.utilization) + '%' : '–', s: cur ? `resets ${new Date(cur.seven_day.resets_at).toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}` : '' },
    { l: 'Peak 5h in range', v: q.history.length ? Math.round(Math.max(...q.history.map(h => h.five_pct))) + '%' : '–' },
    { l: `Polls ≥ ${th ?? 90}%`, v: q.history.length ? over : '–', s: q.history.length ? `${pct(over / q.history.length)} of ${q.history.length} polls` : '' },
    { l: 'Last poll', v: cur ? ago(Date.now() / 1000 - cur.age_s) : '–', s: cur?.backoff ? 'rate limited, backing off' : '' },
  ]);
  const resets = [...new Set(q.history.map(h => h.five_reset && Math.floor(new Date(h.five_reset) / 1000)).filter(Boolean))];
  line($('#chart-five'), q.history.map(h => ({ t: h.ts, v: h.five_pct })), { danger: th, resets });
  line($('#chart-week'), q.history.map(h => ({ t: h.ts, v: h.week_pct })), { danger: th });
}
async function renderProjects() {
  const rows = await api('/api/breakdown' + qs({ by: 'project' }));
  table($('#table-projects'), rows, COLS.concat([{ k: 'first_ts', l: 'First', f: v => v ? ago(v) : '' }]), { onKey: r => { state.project = [r.key]; refresh(); } });
}
async function renderSessions() {
  const rows = await api('/api/breakdown' + qs({ by: 'session' }));
  const cols = [{ k: 'key', l: 'Session', f: (v, r) => `${esc(r.project)} <span class="muted">${esc(v.slice(0, 8))}</span>`, t: r => `${r.key}\n${r.cwd}` }, ...COLS.slice(1)];
  table($('#table-sessions'), rows, cols, { onKey: r => { state.session = [r.key]; refresh(); } });
}
async function renderSavings() {
  const s = await api('/api/savings'); $('#tab-savings').hidden = !s.available; if (!s.available) { $('#savings-body').innerHTML = '<div class="empty">No savings tools found (rtk, distill, context-mode)</div>'; return; }
  $('#savings-body').innerHTML = Object.entries(s.sources).map(([name, d]) => `<div class="card"><h3>${esc(name)}</h3>${d.text ? `<pre style="white-space:pre-wrap;font-size:12px;margin:0">${esc(d.text)}</pre>` :
    `<table>${Object.entries(d).filter(([k]) => k !== 'raw').map(([k, v]) => `<tr><td>${esc(k.replace(/_/g, ' '))}</td><td>${typeof v === 'number' ? v.toLocaleString() : esc(JSON.stringify(v))}</td></tr>`).join('')}</table>`}</div>`).join('');
}

/* ---------- settings ---------- */
function getPath(o, p) { return p.split('.').reduce((a, k) => a?.[k], o); }
function setPath(o, p, v) { const ks = p.split('.'); ks.slice(0, -1).reduce((a, k) => a[k] ??= {}, o)[ks.at(-1)] = v; }
async function renderSettings() {
  settingsDoc = await api('/api/settings'); const s = settingsDoc.settings, f = $('#settings-form');
  $('#paths').textContent = `${settingsDoc.paths.settings} · ${settingsDoc.paths.db}`;
  const sel = f.elements['menubar.style']; sel.innerHTML = settingsDoc.styles.map(x => `<option>${x}</option>`).join('');
  for (const el of f.elements) { if (!el.name) continue; const v = getPath(s, el.name); if (v === undefined) continue;
    if (el.type === 'checkbox') el.checked = !!v; else if (el.tagName === 'TEXTAREA') el.value = Array.isArray(v) ? v.join('\n') : Object.entries(v).map(([k, x]) => `${k} = ${x}`).join('\n');
    else el.value = Array.isArray(v) ? v.join(', ') : v; }
  const ul = $('#fields-list'); const all = [...s.menubar.fields, ...settingsDoc.fields.filter(x => !s.menubar.fields.includes(x))];
  const names = { five_pct: '5h %', five_left: '5h time left', week_pct: 'Week %', week_left: 'Week time left', today_tokens: 'Today tokens', today_cost: 'Today cost', week_tokens: '7-day tokens' };
  ul.innerHTML = all.map(x => `<li draggable="true" data-f="${x}"><span class="h">⋮⋮</span><input type="checkbox" ${s.menubar.fields.includes(x) ? 'checked' : ''}> ${names[x]} <span class="muted">${x}</span></li>`).join('');
  let drag = null; ul.ondragstart = e => { drag = e.target.closest('li'); drag.classList.add('drag'); };
  ul.ondragover = e => { e.preventDefault(); const li = e.target.closest('li'); if (li && li !== drag) li.before(drag); };
  ul.ondragend = () => drag?.classList.remove('drag');
  const tb = $('#pricing-table tbody'); const row = (k, p) => `<tr><td><input value="${esc(k)}" ${k === 'default' ? 'readonly' : ''}></td>${['in', 'out', 'cache_w', 'cache_r'].map(c => `<td><input type="number" step="0.01" min="0" value="${p[c]}"></td>`).join('')}<td>${k === 'default' ? '' : '<button type="button" class="ghost del">×</button>'}</td></tr>`;
  tb.innerHTML = Object.entries(settingsDoc.pricing).map(([k, p]) => row(k, p)).join('');
  tb.onclick = e => { if (e.target.classList.contains('del')) e.target.closest('tr').remove(); };
  $('#add-price').onclick = () => tb.insertAdjacentHTML('beforeend', row('claude-', { in: 3, out: 15, cache_w: 3.75, cache_r: 0.3 }));
  f.onsubmit = async e => {
    e.preventDefault(); const out = JSON.parse(JSON.stringify(s));
    for (const el of f.elements) { if (!el.name) continue;
      if (el.type === 'checkbox') setPath(out, el.name, el.checked);
      else if (el.type === 'number') setPath(out, el.name, Number(el.value));
      else if (el.name === 'menubar.show_when.apps') setPath(out, el.name, el.value.split(',').map(x => x.trim()).filter(Boolean));
      else if (el.name === 'data.project_labels') setPath(out, el.name, Object.fromEntries(el.value.split('\n').map(l => l.split('=').map(x => x.trim())).filter(a => a.length === 2 && a[0])));
      else if (el.tagName === 'TEXTAREA') setPath(out, el.name, el.value.split('\n').map(x => x.trim()).filter(Boolean));
      else setPath(out, el.name, el.value); }
    out.menubar.fields = $$('#fields-list li').filter(li => $('input', li).checked).map(li => li.dataset.f);
    out.pricing = {}; for (const tr of $$('#pricing-table tbody tr')) { const [k, a, b, c, d] = $$('input', tr).map(i => i.value); if (k) out.pricing[k] = { in: +a, out: +b, cache_w: +c, cache_r: +d }; }
    try { await api('/api/settings', { method: 'PUT', body: JSON.stringify(out) }); toast('Saved — menubar updates on its next tick'); settingsDoc = null; await renderSettings(); }
    catch (err) { toast('Not saved: ' + err.message, true); }
  };
}
function toast(msg, bad) { const t = $('#toast'); t.textContent = msg; t.hidden = false; t.style.background = bad ? 'var(--red)' : ''; clearTimeout(t._t); t._t = setTimeout(() => t.hidden = true, 3500); }

/* ---------- filters UI ---------- */
function multi(id, key, items, label, sub) {
  const box = $(`#${id}-opts`), sel = new Set(state[key]);
  box.innerHTML = items.map(x => `<label><input type="checkbox" value="${esc(x.v)}" ${sel.has(x.v) ? 'checked' : ''}> ${esc(label(x))}${sub ? `<small>${esc(sub(x))}</small>` : ''}</label>`).join('') || '<div class="muted">none</div>';
  box.onchange = () => { state[key] = $$('input:checked', box).map(i => i.value); refresh(); };
  $(`#${id}-count`).textContent = sel.size ? `(${sel.size})` : '';
}
async function renderFilters() {
  options = await api('/api/options');
  multi('project', 'project', options.projects.map(v => ({ v })), x => x.v);
  multi('model', 'model', options.models.map(v => ({ v })), x => x.v.replace('claude-', ''));
  multi('session', 'session', options.sessions.map(s => ({ v: s.session, ...s })), x => `${x.project} · ${x.session.slice(0, 8)}`, x => ago(x.last_ts));
  $$('.presets button').forEach(b => b.classList.toggle('on', !state.from && !state.to && b.dataset.range === state.range));
  const r = dateRange(); $('#from').value = state.from || r.from; $('#to').value = state.to || r.to;
}

/* ---------- orchestration ---------- */
const RENDER = { overview: renderOverview, tokens: renderTokens, quota: renderQuota, projects: renderProjects, sessions: renderSessions, savings: renderSavings, settings: renderSettings };
let busy = false;
async function refresh() {
  writeHash(); $$('#tabs button').forEach(b => b.classList.toggle('on', b.dataset.tab === state.tab));
  $$('.tab').forEach(t => t.hidden = t.id !== state.tab);
  if (busy) return; busy = true;
  try { if (!settingsDoc) settingsDoc = await api('/api/settings'); await renderFilters(); await RENDER[state.tab](); }
  catch (e) { toast(String(e.message || e), true); } finally { busy = false; }
}
$('#tabs').onclick = e => { const b = e.target.closest('button'); if (b) { state.tab = b.dataset.tab; refresh(); } };
$('.presets').onclick = e => { const b = e.target.closest('button'); if (b) { state.range = b.dataset.range; state.from = state.to = ''; refresh(); } };
$('#from').onchange = e => { state.from = e.target.value; refresh(); }; $('#to').onchange = e => { state.to = e.target.value; refresh(); };
$('#clear').onclick = () => { state.project = []; state.model = []; state.session = []; state.from = state.to = ''; state.range = settingsDoc?.settings.dashboard.default_range || '7d'; refresh(); };
$$('[data-bucket]').forEach(b => b.onclick = () => { state.bucket = b.dataset.bucket; refresh(); });
$$('[data-metric]').forEach(b => b.onclick = () => { state.metric = b.dataset.metric; refresh(); });
$('#refresh').onclick = async () => { $('#refresh').disabled = true; try { await fetch('/api/refresh', { method: 'POST' }); await refresh(); toast('Refreshed'); } finally { $('#refresh').disabled = false; } };
addEventListener('hashchange', () => { readHash(); refresh(); });
addEventListener('resize', () => { clearTimeout(window._rz); window._rz = setTimeout(refresh, 150); });
(async () => {
  readHash();
  try { const p = await api('/api/ping'); $('#version').textContent = 'v' + p.version; } catch {}
  settingsDoc = await api('/api/settings');
  if (!location.hash) state.range = settingsDoc.settings.dashboard.default_range || '7d';
  api('/api/savings').then(s => $('#tab-savings').hidden = !s.available).catch(() => {});
  refresh();
})();
