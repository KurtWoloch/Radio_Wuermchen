#!/usr/bin/env python3
"""
Radio Wuermchen Show Schedule Editor
Run: python show_editor.py
Then open http://localhost:8080 in your browser.
"""

import json
import os
import sys
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs

BASE_DIR = Path(__file__).parent
SCHEDULE_FILE = BASE_DIR / "shows_schedule.json"
ALIASES_FILE = BASE_DIR / "track_aliases.json"
PORT = 8080

def get_pool_files():
    """Find all suggestion_pool*.txt files in the radio directory."""
    pools = sorted(f.name for f in BASE_DIR.glob("suggestion_pool*.txt"))
    return pools

def read_schedule():
    with open(SCHEDULE_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def write_schedule(data):
    tmp = str(SCHEDULE_FILE) + ".tmp"
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n')
    os.replace(tmp, str(SCHEDULE_FILE))

def read_aliases():
    with open(ALIASES_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def write_aliases(data):
    tmp = str(ALIASES_FILE) + ".tmp"
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n')
    os.replace(tmp, str(ALIASES_FILE))

NAV_BAR = '''<div class="nav">
  <a href="/" id="nav-shows">&#127925; Shows</a>
  <a href="/aliases" id="nav-aliases">&#128257; Track Aliases</a>
</div>'''

NAV_CSS = '''
  .nav { margin-bottom: 18px; display: flex; gap: 4px; }
  .nav a { padding: 7px 18px; border-radius: 6px 6px 0 0; text-decoration: none;
           font-weight: 600; font-size: 0.9em; color: #888; background: #0a1f0a;
           border: 1px solid #1a3a1a; border-bottom: none; transition: background 0.15s; }
  .nav a:hover { background: #0f2f0f; color: #ccc; }
  .nav a.active { background: #1a3a1a; color: #00ff00; }
'''

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Radio Wuermchen - Show Schedule Editor</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0a0a14; color: #eee; padding: 20px; }
  h1 { margin-bottom: 5px; font-size: 1.6em; color: #ccc; }
  h1 span { color: #00ff00; }
  .subtitle { color: #888; margin-bottom: 20px; font-size: 0.85em; }
  .toolbar { margin-bottom: 15px; display: flex; gap: 10px; align-items: center; }
  .toolbar button { padding: 8px 16px; border: 1px solid #1a3a1a; border-radius: 8px; cursor: pointer;
                    font-size: 0.9em; font-weight: 600; transition: background 0.2s; }
  .btn-save { background: #00aa00; color: white; border-color: #00aa00; }
  .btn-save:hover { background: #00cc00; }
  .btn-save.saved { background: #1b4332; color: #95d5b2; border-color: #1b4332; }
  .btn-add { background: #0a1f0a; color: #00ff00; }
  .btn-add:hover { background: #0f2f0f; }
  .btn-reload { background: #0a1f0a; color: #ccc; }
  .btn-reload:hover { background: #0f2f0f; }
  .status { margin-left: 15px; font-size: 0.85em; color: #888; }
  .status.ok { color: #00ff00; }
  .status.err { color: #f5a6a6; }

  table { width: 100%; border-collapse: collapse; margin-bottom: 20px; table-layout: fixed; }
  col.col-drag { width: 30px; }
  col.col-id { width: 8%; }
  col.col-name { width: 10%; }
  col.col-time { width: 3.5%; }
  col.col-style { width: 22%; }
  col.col-personality { width: 13%; }
  col.col-pool { width: 16%; }
  col.col-signation { width: 12%; }
  col.col-news { width: 32px; }
  col.col-del { width: 32px; }
  th { background: #0f1a0f; color: #00ff00; padding: 8px 6px; text-align: left; font-size: 0.8em;
       text-transform: uppercase; letter-spacing: 0.5px; position: sticky; top: 0; z-index: 1;
       border-bottom: 1px solid #1a3a1a; white-space: nowrap; }
  td { padding: 4px 4px; border-bottom: 1px solid #1a3a1a; vertical-align: top; overflow: hidden; }
  tr:hover { background: #0f1a0f40; }
  tr.dragging { opacity: 0.4; }
  tr.drag-over td { border-top: 2px solid #00ff00; }

  input[type=text], select, textarea {
    width: 100%; padding: 5px 7px; background: #0a1f0a; color: #eee;
    border: 1px solid #1a3a1a; border-radius: 4px; font-size: 0.85em; font-family: inherit;
  }
  input[type=text]:focus, select:focus, textarea:focus {
    border-color: #00ff00; outline: none; box-shadow: 0 0 8px rgba(0,255,0,0.2);
  }
  select { text-overflow: ellipsis; }
  textarea { resize: vertical; min-height: 50px; }
  .time-input { text-align: center; }

  .btn-del { background: #461220; color: #f5a6a6; border: 1px solid #692030; border-radius: 4px;
             padding: 4px 8px; cursor: pointer; font-size: 0.8em; }
  .btn-del:hover { background: #692030; }
  .btn-move { background: none; border: none; color: #555; cursor: grab; font-size: 1.1em; padding: 2px 6px; }
  .btn-move:hover { color: #00ff00; }

  .chk-cell { text-align: center; }
  input[type=checkbox] { width: 16px; height: 16px; accent-color: #00ff00; }

  /* Defaults section */
  .defaults-section { background: #0f1a0f; border-radius: 8px; padding: 15px 20px; margin-top: 10px;
                      border: 1px solid #1a3a1a; }
  .defaults-section h2 { color: #00ff00; font-size: 1.1em; margin-bottom: 10px; }
  .defaults-grid { display: grid; grid-template-columns: 150px 1fr; gap: 8px 15px; align-items: center; }
  .defaults-grid label { font-size: 0.85em; color: #aaa; }
  .defaults-grid input, .defaults-grid select { max-width: 400px; }

  .gap-warning { background: #46122040; border: 1px solid #692030; border-radius: 4px;
                 padding: 8px 12px; margin-bottom: 10px; font-size: 0.85em; color: #f5a6a6; }
  .overlap-warning { background: #3a2a0040; border: 1px solid #ff9800; border-radius: 4px;
                     padding: 8px 12px; margin-bottom: 10px; font-size: 0.85em; color: #ff9800; }
  %%NAV_CSS%%
</style>
</head>
<body>

%%NAV_BAR%%
<h1>&#127925; Radio <span>W&uuml;rmchen</span> - Show Schedule</h1>
<p class="subtitle">Edit shows, then click Save. The orchestrator picks up changes on the next cycle.</p>

<div id="warnings"></div>

<div class="toolbar">
  <button class="btn-save" onclick="save()" id="btnSave">&#128190; Save</button>
  <button class="btn-add" onclick="addShow()">&#10133; Add Show</button>
  <button class="btn-reload" onclick="load()">&#128260; Reload</button>
  <span class="status" id="status"></span>
</div>

<table>
  <colgroup>
    <col class="col-drag">
    <col class="col-id">
    <col class="col-name">
    <col class="col-time">
    <col class="col-time">
    <col class="col-style">
    <col class="col-personality">
    <col class="col-pool">
    <col class="col-signation">
    <col class="col-news">
    <col class="col-del">
  </colgroup>
  <thead>
    <tr>
      <th></th>
      <th>ID</th>
      <th>Name</th>
      <th>Start</th>
      <th>End</th>
      <th>Music Style</th>
      <th>DJ Personality</th>
      <th>Suggestion Pool</th>
      <th>Signation</th>
      <th>News</th>
      <th></th>
    </tr>
  </thead>
  <tbody id="showsBody"></tbody>
</table>

<div class="defaults-section">
  <h2>Defaults (used when no show is active)</h2>
  <div class="defaults-grid">
    <label>Music Style:</label>
    <input type="text" id="def_music_style">
    <label>DJ Personality:</label>
    <input type="text" id="def_dj_personality">
    <label>Suggestion Pool:</label>
    <select id="def_suggestion_pool"></select>
    <label>News Enabled:</label>
    <input type="checkbox" id="def_news_enabled" style="width:auto">
  </div>
</div>

<script>
let data = null;
let poolFiles = [];
let dragRow = null;

async function load() {
  try {
    const resp = await fetch('/api/schedule');
    const result = await resp.json();
    data = result.schedule;
    poolFiles = result.pool_files;
    render();
    setStatus('Loaded.', 'ok');
  } catch(e) {
    setStatus('Load failed: ' + e, 'err');
  }
}

function setStatus(msg, cls) {
  const el = document.getElementById('status');
  el.textContent = msg;
  el.className = 'status ' + (cls || '');
  if (cls === 'ok') setTimeout(() => { el.textContent = ''; }, 3000);
}

function poolSelect(selected, id) {
  let html = '<option value="">-- none --</option>';
  for (const p of poolFiles) {
    const sel = p === selected ? ' selected' : '';
    html += `<option value="${p}"${sel}>${p}</option>`;
  }
  return `<select id="${id}" onchange="markDirty()">${html}</select>`;
}

function esc(s) {
  if (s == null) return '';
  return String(s).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;');
}

function render() {
  const tbody = document.getElementById('showsBody');
  let html = '';
  data.shows.forEach((show, i) => {
    const ov = show.overrides || {};
    const newsChecked = ov.news_enabled !== false ? ' checked' : '';
    html += `<tr draggable="true" data-idx="${i}"
              ondragstart="dStart(event,${i})" ondragover="dOver(event)" ondragenter="dEnter(event,this)"
              ondragleave="dLeave(event,this)" ondrop="dDrop(event,${i})" ondragend="dEnd()">
      <td><span class="btn-move" title="Drag to reorder">&#9776;</span></td>
      <td><input type="text" class="id-input" value="${esc(show.id)}" data-field="id" data-idx="${i}" onchange="markDirty()"></td>
      <td><input type="text" class="name-input" value="${esc(show.name)}" data-field="name" data-idx="${i}" onchange="markDirty()"></td>
      <td><input type="text" class="time-input" value="${esc(show.schedule?.start)}" data-field="start" data-idx="${i}" onchange="markDirty()"></td>
      <td><input type="text" class="time-input" value="${esc(show.schedule?.end)}" data-field="end" data-idx="${i}" onchange="markDirty()"></td>
      <td><textarea rows="2" data-field="music_style" data-idx="${i}" onchange="markDirty()">${esc(ov.music_style)}</textarea></td>
      <td><textarea rows="2" data-field="dj_personality" data-idx="${i}" onchange="markDirty()">${esc(ov.dj_personality)}</textarea></td>
      <td>${poolSelect(ov.suggestion_pool, 'pool_'+i)}</td>
      <td><input type="text" value="${esc(ov.signation||'')}" data-field="signation" data-idx="${i}" onchange="markDirty()"></td>
      <td class="chk-cell"><input type="checkbox"${newsChecked} data-field="news_enabled" data-idx="${i}" onchange="markDirty()"></td>
      <td><button class="btn-del" onclick="delShow(${i})" title="Delete show">&#128465;</button></td>
    </tr>`;
  });
  tbody.innerHTML = html;

  // Defaults
  const d = data.defaults || {};
  document.getElementById('def_music_style').value = d.music_style || '';
  document.getElementById('def_dj_personality').value = d.dj_personality || '';
  document.getElementById('def_news_enabled').checked = d.news_enabled !== false;

  // Pool select for defaults
  const defPoolEl = document.getElementById('def_suggestion_pool');
  let ph = '<option value="">-- none --</option>';
  for (const p of poolFiles) {
    const sel = p === d.suggestion_pool ? ' selected' : '';
    ph += `<option value="${p}"${sel}>${p}</option>`;
  }
  defPoolEl.innerHTML = ph;

  checkGaps();
}

function collectData() {
  // Read all fields from DOM back into data
  data.shows.forEach((show, i) => {
    const get = (field) => {
      const el = document.querySelector(`[data-field="${field}"][data-idx="${i}"]`);
      return el ? el.value : '';
    };
    const getChk = (field) => {
      const el = document.querySelector(`[data-field="${field}"][data-idx="${i}"]`);
      return el ? el.checked : true;
    };

    show.id = get('id');
    show.name = get('name');
    if (!show.schedule) show.schedule = {};
    show.schedule.start = get('start');
    show.schedule.end = get('end');
    if (!show.overrides) show.overrides = {};
    show.overrides.music_style = get('music_style') || null;
    show.overrides.dj_personality = get('dj_personality') || null;
    show.overrides.suggestion_pool = document.getElementById('pool_'+i)?.value || null;
    const sig = get('signation');
    if (sig) show.overrides.signation = sig; else delete show.overrides.signation;
    const news = getChk('news_enabled');
    if (!news) show.overrides.news_enabled = false; else delete show.overrides.news_enabled;
  });

  // Defaults
  if (!data.defaults) data.defaults = {};
  data.defaults.music_style = document.getElementById('def_music_style').value || null;
  data.defaults.dj_personality = document.getElementById('def_dj_personality').value || null;
  data.defaults.suggestion_pool = document.getElementById('def_suggestion_pool').value || null;
  data.defaults.news_enabled = document.getElementById('def_news_enabled').checked;
}

function markDirty() {
  document.getElementById('btnSave').classList.remove('saved');
  collectData();
  checkGaps();
}

async function save() {
  collectData();
  // Validate
  for (const show of data.shows) {
    if (!show.id) { setStatus('Error: Show ID cannot be empty.', 'err'); return; }
    if (!show.name) { setStatus('Error: Show name cannot be empty.', 'err'); return; }
    if (!show.schedule?.start || !show.schedule?.end) { setStatus(`Error: Show "${show.name}" needs start and end times.`, 'err'); return; }
    if (!/^\d{2}:\d{2}$/.test(show.schedule.start) || !/^\d{2}:\d{2}$/.test(show.schedule.end)) {
      setStatus(`Error: Times for "${show.name}" must be HH:MM format.`, 'err'); return;
    }
  }
  try {
    const resp = await fetch('/api/schedule', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(data)
    });
    if (resp.ok) {
      setStatus('Saved!', 'ok');
      document.getElementById('btnSave').classList.add('saved');
    } else {
      const err = await resp.text();
      setStatus('Save failed: ' + err, 'err');
    }
  } catch(e) {
    setStatus('Save failed: ' + e, 'err');
  }
}

function addShow() {
  collectData();
  data.shows.push({
    id: 'new_show',
    name: 'New Show',
    schedule: { start: '12:00', end: '13:00' },
    overrides: { music_style: '', dj_personality: '', suggestion_pool: '' }
  });
  render();
  markDirty();
  // Scroll to bottom
  window.scrollTo(0, document.body.scrollHeight);
}

function delShow(idx) {
  const name = data.shows[idx].name;
  if (!confirm(`Delete show "${name}"?`)) return;
  collectData();
  data.shows.splice(idx, 1);
  render();
  markDirty();
}

// Time gap/overlap detection
function timeToMin(t) {
  const [h,m] = t.split(':').map(Number);
  return h * 60 + m;
}

function checkGaps() {
  const w = document.getElementById('warnings');
  if (!data || !data.shows.length) { w.innerHTML = ''; return; }

  // Sort shows by start time for analysis
  const sorted = data.shows.map((s,i) => ({
    name: s.name, start: s.schedule?.start, end: s.schedule?.end, idx: i
  })).filter(s => s.start && s.end).sort((a,b) => timeToMin(a.start) - timeToMin(b.start));

  let msgs = [];
  for (let i = 0; i < sorted.length - 1; i++) {
    const cur = sorted[i], nxt = sorted[i+1];
    const curEnd = timeToMin(cur.end === '00:00' ? '24:00' : cur.end);
    const nxtStart = timeToMin(nxt.start);
    if (curEnd < nxtStart) {
      msgs.push(`<div class="gap-warning">Gap: ${cur.end} - ${nxt.start} (between "${cur.name}" and "${nxt.name}")</div>`);
    } else if (curEnd > nxtStart) {
      msgs.push(`<div class="overlap-warning">Overlap: "${cur.name}" ends ${cur.end} but "${nxt.name}" starts ${nxt.start}</div>`);
    }
  }
  w.innerHTML = msgs.join('');
}

// Drag & drop reordering
function dStart(e, idx) { dragRow = idx; e.dataTransfer.effectAllowed = 'move'; }
function dOver(e) { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; }
function dEnter(e, tr) { tr.classList.add('drag-over'); }
function dLeave(e, tr) { tr.classList.remove('drag-over'); }
function dEnd() { document.querySelectorAll('.drag-over').forEach(r => r.classList.remove('drag-over')); }
function dDrop(e, idx) {
  e.preventDefault();
  if (dragRow === null || dragRow === idx) return;
  collectData();
  const [moved] = data.shows.splice(dragRow, 1);
  data.shows.splice(idx, 0, moved);
  render();
  markDirty();
  dragRow = null;
}

// Activate nav
document.getElementById('nav-shows').classList.add('active');

// Init
load();
</script>
</body>
</html>
"""

ALIASES_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Radio Wuermchen - Track Aliases</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0a0a14; color: #eee; padding: 20px; }
  h1 { margin-bottom: 5px; font-size: 1.6em; color: #ccc; }
  h1 span { color: #00ff00; }
  .subtitle { color: #888; margin-bottom: 20px; font-size: 0.85em; }
  .toolbar { margin-bottom: 15px; display: flex; gap: 10px; align-items: center; }
  .toolbar button { padding: 8px 16px; border: 1px solid #1a3a1a; border-radius: 8px; cursor: pointer;
                    font-size: 0.9em; font-weight: 600; transition: background 0.2s; }
  .btn-save { background: #00aa00; color: white; border-color: #00aa00; }
  .btn-save:hover { background: #00cc00; }
  .btn-save.saved { background: #1b4332; color: #95d5b2; border-color: #1b4332; }
  .btn-add { background: #0a1f0a; color: #00ff00; }
  .btn-add:hover { background: #0f2f0f; }
  .btn-reload { background: #0a1f0a; color: #ccc; }
  .btn-reload:hover { background: #0f2f0f; }
  .status { margin-left: 15px; font-size: 0.85em; color: #888; }
  .status.ok { color: #00ff00; }
  .status.err { color: #f5a6a6; }

  table { width: 100%; border-collapse: collapse; margin-bottom: 20px; table-layout: fixed; }
  col.col-alias { width: 45%; }
  col.col-actual { width: 45%; }
  col.col-del { width: 32px; }
  th { background: #0f1a0f; color: #00ff00; padding: 8px 10px; text-align: left; font-size: 0.8em;
       text-transform: uppercase; letter-spacing: 0.5px; position: sticky; top: 0; z-index: 1;
       border-bottom: 1px solid #1a3a1a; white-space: nowrap; }
  td { padding: 4px 4px; border-bottom: 1px solid #1a3a1a; vertical-align: top; }
  tr:hover { background: #0f1a0f40; }

  input[type=text] {
    width: 100%; padding: 6px 8px; background: #0a1f0a; color: #eee;
    border: 1px solid #1a3a1a; border-radius: 4px; font-size: 0.9em; font-family: inherit;
  }
  input[type=text]:focus {
    border-color: #00ff00; outline: none; box-shadow: 0 0 8px rgba(0,255,0,0.2);
  }
  input[type=text].duplicate { border-color: #ff5555; box-shadow: 0 0 8px rgba(255,85,85,0.3); }

  .btn-del { background: #461220; color: #f5a6a6; border: 1px solid #692030; border-radius: 4px;
             padding: 4px 8px; cursor: pointer; font-size: 0.8em; }
  .btn-del:hover { background: #692030; }

  .hint { color: #555; font-size: 0.8em; margin-bottom: 12px; }

  %%NAV_CSS%%
</style>
</head>
<body>

%%NAV_BAR%%
<h1>&#128257; Radio <span>W&uuml;rmchen</span> - Track Aliases</h1>
<p class="subtitle">Map DJ suggestions to actual filenames. Matching is case-insensitive substring.</p>
<p class="hint">Alias = what the DJ might say &nbsp;|&nbsp; Actual Track = filename in your library (without .mp3)</p>

<div class="toolbar">
  <button class="btn-save" onclick="save()" id="btnSave">&#128190; Save</button>
  <button class="btn-add" onclick="addAlias()">&#10133; Add Alias</button>
  <button class="btn-reload" onclick="load()">&#128260; Reload</button>
  <span class="status" id="status"></span>
</div>

<table>
  <colgroup>
    <col class="col-alias">
    <col class="col-actual">
    <col class="col-del">
  </colgroup>
  <thead>
    <tr>
      <th>Alias (DJ says)</th>
      <th>Actual Track (filename)</th>
      <th></th>
    </tr>
  </thead>
  <tbody id="aliasBody"></tbody>
</table>

<script>
let aliases = [];  // [{alias, actual}]

async function load() {
  try {
    const resp = await fetch('/api/aliases');
    const result = await resp.json();
    aliases = [];
    for (const [k, v] of Object.entries(result.aliases || {})) {
      aliases.push({alias: k, actual: v});
    }
    aliases.sort((a, b) => a.alias.localeCompare(b.alias, undefined, {sensitivity: 'base'}));
    render();
    setStatus('Loaded ' + aliases.length + ' aliases.', 'ok');
  } catch(e) {
    setStatus('Load failed: ' + e, 'err');
  }
}

function setStatus(msg, cls) {
  const el = document.getElementById('status');
  el.textContent = msg;
  el.className = 'status ' + (cls || '');
  if (cls === 'ok') setTimeout(() => { el.textContent = ''; }, 3000);
}

function esc(s) {
  if (s == null) return '';
  return String(s).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;');
}

function render() {
  const tbody = document.getElementById('aliasBody');
  let html = '';
  aliases.forEach((entry, i) => {
    html += `<tr>
      <td><input type="text" value="${esc(entry.alias)}" data-field="alias" data-idx="${i}"
           onchange="markDirty()" oninput="checkDuplicates()"></td>
      <td><input type="text" value="${esc(entry.actual)}" data-field="actual" data-idx="${i}"
           onchange="markDirty()"></td>
      <td><button class="btn-del" onclick="delAlias(${i})" title="Delete alias">&#128465;</button></td>
    </tr>`;
  });
  tbody.innerHTML = html;
}

function collectData() {
  aliases.forEach((entry, i) => {
    const aliasEl = document.querySelector(`[data-field="alias"][data-idx="${i}"]`);
    const actualEl = document.querySelector(`[data-field="actual"][data-idx="${i}"]`);
    if (aliasEl) entry.alias = aliasEl.value;
    if (actualEl) entry.actual = actualEl.value;
  });
}

function markDirty() {
  document.getElementById('btnSave').classList.remove('saved');
  collectData();
}

function checkDuplicates() {
  const inputs = document.querySelectorAll('[data-field="alias"]');
  const seen = {};
  inputs.forEach(inp => {
    const key = inp.value.trim().toLowerCase();
    if (seen[key] !== undefined) {
      inp.classList.add('duplicate');
      inputs[seen[key]].classList.add('duplicate');
    } else {
      inp.classList.remove('duplicate');
    }
    seen[key] = inp.dataset.idx;
  });
}

async function save() {
  collectData();
  // Validate
  for (let i = 0; i < aliases.length; i++) {
    if (!aliases[i].alias.trim()) {
      setStatus('Error: Alias cannot be empty (row ' + (i+1) + ').', 'err'); return;
    }
    if (!aliases[i].actual.trim()) {
      setStatus('Error: Actual track cannot be empty (row ' + (i+1) + ').', 'err'); return;
    }
  }
  // Check duplicates
  const seen = new Set();
  for (const a of aliases) {
    const key = a.alias.trim().toLowerCase();
    if (seen.has(key)) {
      setStatus('Error: Duplicate alias "' + a.alias + '".', 'err'); return;
    }
    seen.add(key);
  }
  // Build object
  const obj = {};
  for (const a of aliases) obj[a.alias.trim()] = a.actual.trim();

  try {
    const resp = await fetch('/api/aliases', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        _comment: "Alias table for DJ track matching. Keys are aliases (substrings the DJ might say), values are the proper spelling (as it appears in filenames). Matching is case-insensitive.",
        aliases: obj
      })
    });
    if (resp.ok) {
      setStatus('Saved ' + aliases.length + ' aliases!', 'ok');
      document.getElementById('btnSave').classList.add('saved');
    } else {
      const err = await resp.text();
      setStatus('Save failed: ' + err, 'err');
    }
  } catch(e) {
    setStatus('Save failed: ' + e, 'err');
  }
}

function addAlias() {
  collectData();
  aliases.push({alias: '', actual: ''});
  render();
  markDirty();
  // Focus the new alias input
  const inputs = document.querySelectorAll('[data-field="alias"]');
  if (inputs.length) inputs[inputs.length - 1].focus();
}

function delAlias(idx) {
  collectData();
  const name = aliases[idx].alias || '(empty)';
  if (!confirm('Delete alias "' + name + '"?')) return;
  aliases.splice(idx, 1);
  render();
  markDirty();
}

// Activate nav
document.getElementById('nav-aliases').classList.add('active');

load();
</script>
</body>
</html>
"""

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress request logs

    def _serve_html(self, template):
        page = template.replace('%%NAV_CSS%%', NAV_CSS).replace('%%NAV_BAR%%', NAV_BAR)
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(page.encode('utf-8'))

    def _serve_json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self._serve_html(HTML_PAGE)
        elif self.path == '/aliases':
            self._serve_html(ALIASES_PAGE)
        elif self.path == '/api/schedule':
            self._serve_json({"schedule": read_schedule(), "pool_files": get_pool_files()})
        elif self.path == '/api/aliases':
            self._serve_json(read_aliases())
        else:
            self.send_error(404)

    def _read_body(self):
        length = int(self.headers.get('Content-Length', 0))
        return self.rfile.read(length).decode('utf-8')

    def _send_ok(self, msg=b'OK'):
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(msg)

    def _send_err(self, msg):
        self.send_response(400)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(str(msg).encode('utf-8'))

    def do_POST(self):
        if self.path == '/api/schedule':
            try:
                new_data = json.loads(self._read_body())
                if 'shows' not in new_data:
                    raise ValueError("Missing 'shows' key")
                for show in new_data['shows']:
                    if not show.get('id'):
                        raise ValueError("Show missing id")
                    if not show.get('schedule', {}).get('start'):
                        raise ValueError(f"Show '{show.get('name','')}' missing start time")
                write_schedule(new_data)
                self._send_ok()
                print(f"  Schedule saved ({len(new_data['shows'])} shows)")
            except (json.JSONDecodeError, ValueError) as e:
                self._send_err(e)

        elif self.path == '/api/aliases':
            try:
                new_data = json.loads(self._read_body())
                if 'aliases' not in new_data:
                    raise ValueError("Missing 'aliases' key")
                if not isinstance(new_data['aliases'], dict):
                    raise ValueError("'aliases' must be an object")
                write_aliases(new_data)
                self._send_ok()
                print(f"  Aliases saved ({len(new_data['aliases'])} entries)")
            except (json.JSONDecodeError, ValueError) as e:
                self._send_err(e)
        else:
            self.send_error(404)

def main():
    if not SCHEDULE_FILE.exists():
        print(f"Error: {SCHEDULE_FILE} not found!")
        sys.exit(1)

    server = HTTPServer(('127.0.0.1', PORT), Handler)
    url = f'http://localhost:{PORT}'
    print(f"Show Schedule Editor running at {url}")
    print("Press Ctrl+C to stop.\n")

    try:
        webbrowser.open(url)
    except Exception:
        pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")

if __name__ == '__main__':
    main()
