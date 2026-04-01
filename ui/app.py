"""
Pickled Eggs Co — Review Dashboard
====================================
A single Flask app that surfaces all agent output queues for human review.
All agents write to the shared SQLite/Postgres database; this UI reads from it.

Run directly:
  python -m ui.app

Or launched by scheduler.py after a scan:
  python scheduler.py --ui
"""
import os
from datetime import datetime

from flask import Flask, jsonify, render_template_string, request

from shared.db import execute, fetchall, fetchone, get_conn

app = Flask(__name__)

# ─────────────────────────────────────────────
# SHARED DASHBOARD HTML
# ─────────────────────────────────────────────

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Pickled Eggs Co — Review Dashboard</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'IBM Plex Mono', 'Courier New', monospace; background: #0e0c09; color: #e8dcc8; min-height: 100vh; }
  header { background: #181410; border-bottom: 1px solid #2e2720; padding: 1rem 2rem; display: flex; align-items: baseline; gap: 1rem; flex-wrap: wrap; }
  .logo { font-size: 20px; font-weight: 700; color: #d4820a; letter-spacing: 0.1em; }
  .logo span { color: #7a6e60; font-size: 13px; font-weight: 400; margin-left: 8px; }
  .stats { margin-left: auto; display: flex; gap: 1.5rem; font-size: 12px; color: #7a6e60; }
  .stat strong { color: #d4820a; }
  .tabs { background: #181410; border-bottom: 1px solid #2e2720; padding: 0 2rem; display: flex; gap: 0; }
  .tab-btn { background: transparent; border: none; border-bottom: 2px solid transparent; padding: 10px 18px; color: #7a6e60; font-size: 13px; cursor: pointer; font-family: inherit; }
  .tab-btn:hover { color: #e8dcc8; }
  .tab-btn.active { border-bottom-color: #d4820a; color: #d4820a; }
  .filters { background: #0e0c09; border-bottom: 1px solid #2e2720; padding: 0.75rem 2rem; display: flex; gap: 8px; }
  .filter-btn { background: transparent; border: 1px solid #2e2720; border-radius: 4px; padding: 5px 12px; color: #7a6e60; font-size: 12px; cursor: pointer; font-family: inherit; }
  .filter-btn:hover { border-color: #3d3028; color: #e8dcc8; }
  .filter-btn.active { border-color: #d4820a; color: #d4820a; }
  main { max-width: 960px; margin: 0 auto; padding: 1.5rem 2rem; }
  .empty { text-align: center; padding: 4rem; color: #7a6e60; font-size: 13px; }
  .post-card { background: #181410; border: 1px solid #2e2720; border-radius: 6px; margin-bottom: 16px; overflow: hidden; }
  .post-card.approved { border-left: 3px solid #2d6a2d; }
  .post-card.skipped  { border-left: 3px solid #3d3028; opacity: 0.5; }
  .post-head { padding: 14px 16px; border-bottom: 1px solid #2e2720; display: flex; align-items: flex-start; gap: 12px; }
  .score-badge { font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 3px; white-space: nowrap; flex-shrink: 0; }
  .score-high { background: #2d6a2d; color: #6fcf6f; }
  .score-med  { background: #5a4a10; color: #d4a820; }
  .type-badge { font-size: 10px; padding: 3px 8px; border-radius: 3px; background: #2e2720; color: #7a6e60; white-space: nowrap; flex-shrink: 0; }
  .post-title { font-size: 14px; color: #e8dcc8; flex: 1; line-height: 1.4; }
  .post-meta  { font-size: 11px; color: #7a6e60; margin-top: 4px; }
  .post-meta a { color: #d4820a; text-decoration: none; }
  .matched    { font-size: 11px; color: #d4820a; margin-top: 4px; }
  .post-excerpt { font-size: 12px; color: #5F5E5A; padding: 0 16px 10px; white-space: pre-wrap; cursor: pointer; }
  .post-body  { padding: 12px 16px; font-size: 12px; color: #7a6e60; line-height: 1.6; border-bottom: 1px solid #2e2720; display: none; }
  .post-body.open { display: block; }
  .reply-section { padding: 12px 16px; }
  .reply-label { font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; color: #7a6e60; margin-bottom: 8px; }
  .reply-reason { font-size: 11px; color: #7a6e60; margin-bottom: 8px; font-style: italic; }
  textarea { width: 100%; background: #0e0c09; border: 1px solid #2e2720; border-radius: 4px; padding: 10px; color: #e8dcc8; font-size: 13px; font-family: inherit; resize: vertical; line-height: 1.6; min-height: 100px; }
  textarea:focus { outline: none; border-color: #d4820a; }
  .action-row { display: flex; gap: 8px; margin-top: 10px; align-items: center; }
  .btn { padding: 8px 16px; border-radius: 4px; font-size: 13px; font-family: inherit; cursor: pointer; border: 1px solid; }
  .btn-approve { background: #2d6a2d; border-color: #2d6a2d; color: #6fcf6f; }
  .btn-skip { background: transparent; border-color: #3d3028; color: #7a6e60; }
  .btn-copy { background: transparent; border-color: #3d3028; color: #7a6e60; margin-left: auto; }
  .btn-copy:hover { border-color: #d4820a; color: #d4820a; }
  .char-count { font-size: 11px; color: #7a6e60; }
  .status-pill { font-size: 11px; padding: 3px 10px; border-radius: 10px; }
  .pill-approved { background: #2d6a2d; color: #6fcf6f; }
  .pill-skipped  { background: #2e2720; color: #7a6e60; }
</style>
</head>
<body>
<header>
  <div class="logo">Pickled Eggs Co <span>// Review Dashboard</span></div>
  <div class="stats">
    <span><strong id="cnt-pending">—</strong> pending</span>
    <span><strong id="cnt-approved">—</strong> approved</span>
    <span><strong id="cnt-skipped">—</strong> skipped</span>
  </div>
</header>
<div class="tabs">
  <button class="tab-btn active" onclick="setTab('listener')">Community Listener</button>
  <button class="tab-btn" onclick="setTab('content_multiplier')">Content Multiplier</button>
  <button class="tab-btn" onclick="setTab('content_freshness')">Content Freshness</button>
</div>
<div class="filters">
  <button class="filter-btn active" onclick="setFilter('pending')">Pending</button>
  <button class="filter-btn" onclick="setFilter('approved')">Approved</button>
  <button class="filter-btn" onclick="setFilter('skipped')">Skipped</button>
  <button class="filter-btn" onclick="setFilter('all')">All</button>
</div>
<main>
  <div id="post-list"></div>
</main>

<script>
let allItems = [];
let currentFilter = 'pending';
let currentTab = 'listener';

async function load() {
  const r = await fetch('/api/items?tab=' + currentTab);
  allItems = await r.json();
  updateCounts();
  render();
}

function updateCounts() {
  document.getElementById('cnt-pending').textContent  = allItems.filter(p=>p.status==='pending').length;
  document.getElementById('cnt-approved').textContent = allItems.filter(p=>p.status==='approved').length;
  document.getElementById('cnt-skipped').textContent  = allItems.filter(p=>p.status==='skipped').length;
}

function setTab(t) {
  currentTab = t;
  document.querySelectorAll('.tab-btn').forEach(b => {
    const labels = { listener: 'Community Listener', content_multiplier: 'Content Multiplier', content_freshness: 'Content Freshness' };
    b.classList.toggle('active', b.textContent === labels[t]);
  });
  load();
}

function setFilter(f) {
  currentFilter = f;
  document.querySelectorAll('.filter-btn').forEach(b => {
    b.classList.toggle('active', b.textContent.toLowerCase() === f);
  });
  render();
}

function esc(s) { const d=document.createElement('div'); d.textContent=s||''; return d.innerHTML; }

function render() {
  const items = currentFilter === 'all' ? allItems : allItems.filter(p => p.status === currentFilter);
  const el = document.getElementById('post-list');
  if (!items.length) { el.innerHTML = '<div class="empty">No ' + currentFilter + ' items.</div>'; return; }

  el.innerHTML = items.map(item => {
    const isReviewed = item.status !== 'pending';

    if (currentTab === 'listener') {
      const excerpt = (item.body||'').slice(0,200).replace(/\\n/g,' ');
      const scoreClass = item.relevance_score >= 8 ? 'score-high' : 'score-med';
      return `
      <div class="post-card ${isReviewed ? item.status : ''}" id="card-${item.id}">
        <div class="post-head">
          <span class="score-badge ${scoreClass}">${item.relevance_score}/10</span>
          <div style="flex:1">
            <div class="post-title">${esc(item.title)}</div>
            <div class="post-meta">r/${esc(item.subreddit)} · ${esc(item.author)} · <a href="${esc(item.url)}" target="_blank">view on Reddit ↗</a></div>
            ${item.matched_bar ? `<div class="matched">Bar match: ${esc(item.matched_bar)}</div>` : ''}
          </div>
          ${isReviewed ? `<span class="status-pill pill-${item.status}">${item.status}</span>` : ''}
        </div>
        ${excerpt ? `<div class="post-excerpt" onclick="toggleBody('${item.id}')">${esc(excerpt)}${(item.body||'').length>200?'…':''}</div>` : ''}
        <div class="post-body" id="body-${item.id}"><strong>Full post:</strong><br>${esc(item.body)}</div>
        <div class="reply-section">
          <div class="reply-label">Draft reply</div>
          <div class="reply-reason">${esc(item.relevance_reason)}</div>
          <textarea id="reply-${item.id}">${esc(item.draft_reply)}</textarea>
          <div class="action-row">
            ${!isReviewed
              ? `<button class="btn btn-approve" onclick="act('${item.id}','approved','listener')">Approve</button>
                 <button class="btn btn-skip" onclick="act('${item.id}','skipped','listener')">Skip</button>`
              : `<button class="btn btn-skip" onclick="act('${item.id}','pending','listener')">Undo</button>`}
            <span class="char-count" id="cc-${item.id}">${(item.draft_reply||'').length} chars</span>
            <button class="btn btn-copy" onclick="copyReply('${item.id}')">Copy reply</button>
          </div>
        </div>
      </div>`;
    }

    // content_multiplier and content_freshness share a simpler card
    const label = currentTab === 'content_multiplier'
      ? item.content_type : 'refreshed copy';
    const title = currentTab === 'content_multiplier'
      ? `${item.bar_name} — ${item.content_type}` : item.product_title;
    const draft = currentTab === 'content_multiplier'
      ? item.draft : item.new_description;

    return `
    <div class="post-card ${isReviewed ? item.status : ''}" id="card-${item.id}">
      <div class="post-head">
        <span class="type-badge">${esc(label)}</span>
        <div style="flex:1">
          <div class="post-title">${esc(title)}</div>
          <div class="post-meta">${esc(item.created_at ? item.created_at.slice(0,10) : '')}</div>
        </div>
        ${isReviewed ? `<span class="status-pill pill-${item.status}">${item.status}</span>` : ''}
      </div>
      <div class="reply-section">
        <div class="reply-label">Draft</div>
        <textarea id="reply-${item.id}" rows="6">${esc(draft)}</textarea>
        <div class="action-row">
          ${!isReviewed
            ? `<button class="btn btn-approve" onclick="act('${item.id}','approved','${currentTab}')">Approve</button>
               <button class="btn btn-skip" onclick="act('${item.id}','skipped','${currentTab}')">Skip</button>`
            : `<button class="btn btn-skip" onclick="act('${item.id}','pending','${currentTab}')">Undo</button>`}
          <button class="btn btn-copy" onclick="copyReply('${item.id}')">Copy</button>
        </div>
      </div>
    </div>`;
  }).join('');

  // Live char count for listener replies
  if (currentTab === 'listener') {
    items.forEach(item => {
      const ta = document.getElementById('reply-' + item.id);
      const cc = document.getElementById('cc-' + item.id);
      if (ta && cc) {
        ta.addEventListener('input', () => { cc.textContent = ta.value.length + ' chars'; });
      }
    });
  }
}

function toggleBody(id) { document.getElementById('body-'+id).classList.toggle('open'); }

async function act(id, status, tab) {
  await fetch('/api/action', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id, status, tab }),
  });
  await load();
}

async function copyReply(id) {
  const text = document.getElementById('reply-' + id)?.value;
  if (text) {
    await navigator.clipboard.writeText(text);
    const btn = event.target;
    btn.textContent = 'Copied!';
    setTimeout(() => btn.textContent = 'Copy reply', 1500);
  }
}

load();
</script>
</body>
</html>
"""


# ─────────────────────────────────────────────
# API ROUTES
# ─────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/api/items")
def api_items():
    tab = request.args.get("tab", "listener")

    if tab == "listener":
        with get_conn() as conn:
            rows = fetchall(conn, "SELECT * FROM posts ORDER BY relevance_score DESC, scanned_at DESC")
        return jsonify(rows)

    if tab == "content_multiplier":
        with get_conn() as conn:
            rows = fetchall(conn, "SELECT * FROM content_drafts ORDER BY created_at DESC")
        return jsonify(rows)

    if tab == "content_freshness":
        with get_conn() as conn:
            rows = fetchall(conn, "SELECT * FROM freshness_queue ORDER BY created_at DESC")
        return jsonify(rows)

    return jsonify([])


@app.route("/api/action", methods=["POST"])
def api_action():
    data = request.json
    item_id = data["id"]
    status  = data["status"]
    tab     = data.get("tab", "listener")
    now     = datetime.now().isoformat()

    table_map = {
        "listener":           "posts",
        "content_multiplier": "content_drafts",
        "content_freshness":  "freshness_queue",
    }
    table = table_map.get(tab, "posts")

    with get_conn() as conn:
        execute(conn,
            f"UPDATE {table} SET status=?, reviewed_at=? WHERE id=?",
            (status, now, item_id),
        )
    return jsonify({"ok": True})


# ─────────────────────────────────────────────
# ENTRYPOINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    from shared.config import FLASK_PORT
    print(f"\nReview Dashboard running at http://localhost:{FLASK_PORT}")
    app.run(port=FLASK_PORT, debug=False)
