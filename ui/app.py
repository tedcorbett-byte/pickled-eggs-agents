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
import json
import os
from datetime import datetime

from flask import Flask, jsonify, render_template_string, request

from shared.bars import BARS
from shared.categories import CATEGORY_LABELS
from shared.db import execute, fetchall, fetchone, get_conn, run_migrations
from agents.design_brief.agent import run_for_bar as generate_design_brief

app = Flask(__name__)


# ─────────────────────────────────────────────
# ENSURE TABLES EXIST ON STARTUP
# ─────────────────────────────────────────────

def init_all_tables():
    """Create all agent tables if they don't exist yet.
    Called once at web startup so the dashboard never crashes on missing tables."""
    with get_conn() as conn:
        execute(conn, """
            CREATE TABLE IF NOT EXISTS posts (
                id TEXT PRIMARY KEY,
                platform TEXT,
                subreddit TEXT,
                title TEXT,
                body TEXT,
                url TEXT,
                author TEXT,
                created_at TEXT,
                matched_bar TEXT,
                matched_triggers TEXT,
                relevance_score INTEGER,
                relevance_reason TEXT,
                draft_reply TEXT,
                status TEXT DEFAULT 'pending',
                reviewed_at TEXT,
                scanned_at TEXT
            )
        """)
        execute(conn, """
            CREATE TABLE IF NOT EXISTS content_drafts (
                id TEXT PRIMARY KEY,
                bar_name TEXT NOT NULL,
                bar_city TEXT,
                content_type TEXT NOT NULL,
                draft TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TEXT,
                reviewed_at TEXT
            )
        """)
        execute(conn, """
            CREATE TABLE IF NOT EXISTS freshness_queue (
                id TEXT PRIMARY KEY,
                shopify_product_id TEXT NOT NULL,
                product_title TEXT,
                product_url TEXT,
                old_description TEXT,
                new_description TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT,
                reviewed_at TEXT
            )
        """)
        execute(conn, """
            CREATE TABLE IF NOT EXISTS bar_candidates (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                city TEXT,
                state TEXT,
                description TEXT,
                source_url TEXT,
                source_subreddit TEXT,
                evidence TEXT,
                grief_score INTEGER,
                grief_breakdown TEXT,
                disqualifiers TEXT,
                status TEXT DEFAULT 'discovered',
                notes TEXT,
                discovered_at TEXT,
                updated_at TEXT
            )
        """)
        execute(conn, """
            CREATE TABLE IF NOT EXISTS design_briefs (
                id TEXT PRIMARY KEY,
                bar_name TEXT NOT NULL,
                city TEXT,
                state TEXT,
                brief_json TEXT NOT NULL,
                archival_sources TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT,
                notes TEXT
            )
        """)


init_all_tables()
run_migrations()


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
  .filters { background: #0e0c09; border-bottom: 1px solid #2e2720; padding: 0.75rem 2rem; display: flex; gap: 8px; flex-wrap: wrap; }
  .filter-btn { background: transparent; border: 1px solid #2e2720; border-radius: 4px; padding: 5px 12px; color: #7a6e60; font-size: 12px; cursor: pointer; font-family: inherit; }
  .filter-btn:hover { border-color: #3d3028; color: #e8dcc8; }
  .filter-btn.active { border-color: #d4820a; color: #d4820a; }
  main { max-width: 960px; margin: 0 auto; padding: 1.5rem 2rem; }
  .empty { text-align: center; padding: 4rem; color: #7a6e60; font-size: 13px; }

  /* Standard post cards */
  .post-card { background: #181410; border: 1px solid #2e2720; border-radius: 6px; margin-bottom: 16px; overflow: hidden; }
  .post-card.approved  { border-left: 3px solid #2d6a2d; }
  .post-card.skipped   { border-left: 3px solid #3d3028; opacity: 0.5; }
  .post-card.rejected  { border-left: 3px solid #3d3028; opacity: 0.5; }
  .post-card.graduated { border-left: 3px solid #6a4fbf; }
  .post-head { padding: 14px 16px; border-bottom: 1px solid #2e2720; display: flex; align-items: flex-start; gap: 12px; }
  .score-badge { font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 3px; white-space: nowrap; flex-shrink: 0; }
  .score-high  { background: #2d6a2d; color: #6fcf6f; }
  .score-med   { background: #5a4a10; color: #d4a820; }
  .type-badge  { font-size: 10px; padding: 3px 8px; border-radius: 3px; background: #2e2720; color: #7a6e60; white-space: nowrap; flex-shrink: 0; }
  .post-title  { font-size: 14px; color: #e8dcc8; flex: 1; line-height: 1.4; }
  .post-meta   { font-size: 11px; color: #7a6e60; margin-top: 4px; }
  .post-meta a { color: #d4820a; text-decoration: none; }
  .matched     { font-size: 11px; color: #d4820a; margin-top: 4px; }
  .post-excerpt { font-size: 12px; color: #5F5E5A; padding: 0 16px 10px; white-space: pre-wrap; cursor: pointer; }
  .post-body   { padding: 12px 16px; font-size: 12px; color: #7a6e60; line-height: 1.6; border-bottom: 1px solid #2e2720; display: none; }
  .post-body.open { display: block; }
  .reply-section { padding: 12px 16px; }
  .reply-label  { font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; color: #7a6e60; margin-bottom: 8px; }
  .reply-reason { font-size: 11px; color: #7a6e60; margin-bottom: 8px; font-style: italic; }
  textarea { width: 100%; background: #0e0c09; border: 1px solid #2e2720; border-radius: 4px; padding: 10px; color: #e8dcc8; font-size: 13px; font-family: inherit; resize: vertical; line-height: 1.6; min-height: 100px; }
  textarea:focus { outline: none; border-color: #d4820a; }
  .action-row { display: flex; gap: 8px; margin-top: 10px; align-items: center; }
  .btn { padding: 8px 16px; border-radius: 4px; font-size: 13px; font-family: inherit; cursor: pointer; border: 1px solid; }
  .btn-approve  { background: #2d6a2d; border-color: #2d6a2d; color: #6fcf6f; }
  .btn-skip     { background: transparent; border-color: #3d3028; color: #7a6e60; }
  .btn-graduate { background: #3d2f6a; border-color: #6a4fbf; color: #b39ddb; }
  .btn-copy     { background: transparent; border-color: #3d3028; color: #7a6e60; margin-left: auto; }
  .btn-copy:hover     { border-color: #d4820a; color: #d4820a; }
  .btn-graduate:hover { background: #4d3f7a; }
  .char-count { font-size: 11px; color: #7a6e60; }
  .status-pill { font-size: 11px; padding: 3px 10px; border-radius: 10px; }
  .pill-approved  { background: #2d6a2d; color: #6fcf6f; }
  .pill-skipped   { background: #2e2720; color: #7a6e60; }
  .pill-rejected  { background: #2e2720; color: #7a6e60; }
  .pill-graduated { background: #3d2f6a; color: #b39ddb; }

  /* Category badges */
  .cat-badge { font-size: 10px; padding: 2px 7px; border-radius: 3px; font-weight: 600; letter-spacing: 0.05em; white-space: nowrap; }
  .cat-bar        { background: #3d2f1a; color: #d4820a; }
  .cat-venue      { background: #1a2d3d; color: #4aa8d4; }
  .cat-restaurant { background: #1a3d1a; color: #4ad44a; }
  .cat-rink       { background: #3d1a3d; color: #d44ad4; }

  /* Bar Scout specific */
  .grief-badge-build    { background: #2d6a2d; color: #6fcf6f; }
  .grief-badge-research { background: #3d2f6a; color: #b39ddb; }
  .grief-badge-watchlist { background: #5a4a10; color: #d4a820; }
  .grief-badge-pass     { background: #2e2720; color: #7a6e60; }
  .candidate-body { padding: 12px 16px; border-bottom: 1px solid #2e2720; }
  .candidate-desc { font-size: 13px; color: #e8dcc8; line-height: 1.6; margin-bottom: 12px; }
  .breakdown-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 4px 16px; margin-bottom: 12px; }
  .breakdown-row { font-size: 11px; display: flex; align-items: center; gap: 6px; }
  .breakdown-label { color: #7a6e60; flex: 1; }
  .breakdown-dots { color: #d4820a; letter-spacing: 1px; font-size: 10px; }
  .breakdown-val { color: #e8dcc8; font-size: 11px; min-width: 24px; }
  .breakdown-weight { color: #5a5045; font-size: 10px; }
  .evidence-block { font-size: 11px; color: #5F5E5A; background: #0e0c09; border: 1px solid #2e2720; border-radius: 4px; padding: 10px; line-height: 1.6; white-space: pre-wrap; max-height: 120px; overflow: hidden; cursor: pointer; }
  .evidence-block.open { max-height: none; }
  .evidence-label { font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; color: #7a6e60; margin-bottom: 6px; }

  /* Design Briefs */
  .brief-card { background: #181410; border: 1px solid #2e2720; border-radius: 6px; margin-bottom: 20px; overflow: hidden; }
  .brief-card.approved { border-left: 3px solid #2d6a2d; }
  .brief-card.skipped  { border-left: 3px solid #3d3028; opacity: 0.6; }
  .brief-header { padding: 14px 16px; border-bottom: 1px solid #2e2720; display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
  .brief-header h3 { font-size: 15px; color: #e8dcc8; margin: 0 0 4px; }
  .brief-header span { font-size: 12px; color: #7a6e60; }
  .brief-header .brief-actions { display: flex; gap: 8px; flex-shrink: 0; }
  .brief-vibe { padding: 12px 16px; font-size: 13px; color: #b0a898; font-style: italic; line-height: 1.6; border-bottom: 1px solid #2e2720; }
  .directions-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; padding: 12px 16px; border-bottom: 1px solid #2e2720; }
  .direction-card { background: #0e0c09; border: 1px solid #2e2720; border-radius: 4px; padding: 12px; }
  .direction-card h4 { font-size: 12px; color: #d4820a; margin: 0 0 6px; text-transform: uppercase; letter-spacing: 0.05em; }
  .direction-card p { font-size: 12px; color: #7a6e60; line-height: 1.5; margin-bottom: 6px; }
  .direction-card ul { font-size: 11px; color: #5F5E5A; padding-left: 16px; margin: 0; }
  .brief-section { padding: 10px 16px; border-bottom: 1px solid #2e2720; }
  .brief-section h4 { font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; color: #7a6e60; margin-bottom: 6px; }
  .brief-section ul { font-size: 12px; color: #7a6e60; padding-left: 16px; margin: 0; line-height: 1.8; }
  .brief-section ul a { color: #d4820a; text-decoration: none; }
  .brief-section pre { font-size: 11px; color: #5F5E5A; white-space: pre-wrap; line-height: 1.6; margin: 0; }
  .briefs-filter { padding: 12px 16px; display: flex; gap: 8px; align-items: center; }
  .briefs-filter label { font-size: 12px; color: #7a6e60; }
  .briefs-filter select { background: #0e0c09; border: 1px solid #2e2720; border-radius: 4px; padding: 5px 10px; color: #e8dcc8; font-size: 12px; font-family: inherit; }

  /* Modal */
  .modal-overlay { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.75); z-index: 100; align-items: center; justify-content: center; }
  .modal-overlay.open { display: flex; }
  .modal-box { background: #181410; border: 1px solid #2e2720; border-radius: 8px; padding: 24px; max-width: 600px; width: 90%; }
  .modal-title { font-size: 14px; color: #d4820a; font-weight: 700; margin-bottom: 8px; }
  .modal-sub { font-size: 12px; color: #7a6e60; margin-bottom: 16px; line-height: 1.5; }
  .modal-code { background: #0e0c09; border: 1px solid #2e2720; border-radius: 4px; padding: 14px; font-size: 12px; color: #b39ddb; white-space: pre; overflow-x: auto; margin-bottom: 16px; line-height: 1.7; }
  .modal-actions { display: flex; gap: 8px; justify-content: flex-end; }
</style>
</head>
<body>

<!-- Graduate modal -->
<div class="modal-overlay" id="graduate-modal">
  <div class="modal-box">
    <div class="modal-title">Graduate to bars.py</div>
    <div class="modal-sub">
      Copy this entry and paste it into the <code>BARS</code> list in <code>shared/bars.py</code>.
      Then add the real Shopify product URL before deploying.
    </div>
    <div class="modal-code" id="modal-snippet"></div>
    <div class="modal-actions">
      <button class="btn btn-skip" onclick="closeModal()">Close</button>
      <button class="btn btn-approve" onclick="copySnippet()">Copy to clipboard</button>
    </div>
  </div>
</div>

<header>
  <div class="logo">Pickled Eggs Co <span>// Review Dashboard</span></div>
  <div class="stats">
    <span><strong id="cnt-a">—</strong> <span id="lbl-a">pending</span></span>
    <span><strong id="cnt-b">—</strong> <span id="lbl-b">approved</span></span>
    <span><strong id="cnt-c">—</strong> <span id="lbl-c">skipped</span></span>
  </div>
</header>

<div class="tabs">
  <button class="tab-btn active" data-tab="listener" onclick="setTab('listener')">Community Listener</button>
  <button class="tab-btn" data-tab="content_multiplier" onclick="setTab('content_multiplier')">Content Multiplier</button>
  <button class="tab-btn" data-tab="content_freshness" onclick="setTab('content_freshness')">Content Freshness</button>
  <button class="tab-btn" data-tab="bar_scout" onclick="setTab('bar_scout')">Bar Scout</button>
  <button class="tab-btn" data-tab="briefs" onclick="setTab('briefs')">Design Briefs</button>
</div>
<div class="filters" id="filter-bar"></div>
<div class="filters" id="category-filter-bar" style="display:none"></div>
<main>
  <div id="post-list"></div>
  <!-- Design Briefs panel (shown when briefs tab is active) -->
  <div id="briefs-panel" style="display:none">
    <div class="briefs-filter">
      <label>Status:</label>
      <select id="briefs-status-filter" onchange="loadBriefs()">
        <option value="pending">Pending</option>
        <option value="approved">Approved</option>
        <option value="skipped">Skipped</option>
      </select>
    </div>
    <div id="briefs-container"></div>
  </div>
</main>

<script>
let allItems      = [];
let currentFilter   = 'pending';
let currentTab      = 'listener';
let currentCategory = '';   // '' = all categories

const CATEGORY_LABELS = {
  '':           'All',
  'bar':        'Dive Bar',
  'venue':      'Music Venue',
  'restaurant': 'Restaurant',
  'rink':       'Roller Rink / Bowling',
};

// Filter configs per tab
const FILTERS = {
  default: [
    { label: 'Pending',  value: 'pending'  },
    { label: 'Approved', value: 'approved' },
    { label: 'Skipped',  value: 'skipped'  },
    { label: 'All',      value: 'all'      },
  ],
  bar_scout: [
    { label: 'Discovered', value: 'discovered' },
    { label: 'Approved',   value: 'approved'   },
    { label: 'Rejected',   value: 'rejected'   },
    { label: 'Graduated',  value: 'graduated'  },
    { label: 'All',        value: 'all'        },
  ],
};

function renderFilters() {
  const config = currentTab === 'bar_scout' ? FILTERS.bar_scout : FILTERS.default;
  const bar = document.getElementById('filter-bar');
  bar.innerHTML = config.map(f =>
    `<button class="filter-btn${currentFilter === f.value ? ' active' : ''}"
             onclick="setFilter('${f.value}')">${f.label}</button>`
  ).join('');
}

function renderCategoryFilters() {
  const bar = document.getElementById('category-filter-bar');
  if (!bar) return;
  if (currentTab !== 'bar_scout') { bar.style.display = 'none'; return; }
  bar.style.display = '';
  const cats = ['', 'bar', 'venue', 'restaurant', 'rink'];
  bar.innerHTML = '<span style="font-size:11px;color:#7a6e60;margin-right:6px">Category:</span>' +
    cats.map(c =>
      `<button class="filter-btn${currentCategory === c ? ' active' : ''}"
               onclick="setCategory('${c}')">${CATEGORY_LABELS[c]}</button>`
    ).join('');
}

function setCategory(cat) {
  currentCategory = cat;
  renderCategoryFilters();
  load();
}

async function load() {
  let url = '/api/items?tab=' + currentTab;
  if (currentTab === 'bar_scout' && currentCategory) url += '&category=' + currentCategory;
  const r  = await fetch(url);
  allItems = await r.json();
  updateCounts();
  render();
}

function updateCounts() {
  if (currentTab === 'bar_scout') {
    document.getElementById('lbl-a').textContent = 'discovered';
    document.getElementById('lbl-b').textContent = 'approved';
    document.getElementById('lbl-c').textContent = 'rejected';
    document.getElementById('cnt-a').textContent = allItems.filter(p=>p.status==='discovered').length;
    document.getElementById('cnt-b').textContent = allItems.filter(p=>p.status==='approved').length;
    document.getElementById('cnt-c').textContent = allItems.filter(p=>p.status==='rejected').length;
  } else {
    document.getElementById('lbl-a').textContent = 'pending';
    document.getElementById('lbl-b').textContent = 'approved';
    document.getElementById('lbl-c').textContent = 'skipped';
    document.getElementById('cnt-a').textContent = allItems.filter(p=>p.status==='pending').length;
    document.getElementById('cnt-b').textContent = allItems.filter(p=>p.status==='approved').length;
    document.getElementById('cnt-c').textContent = allItems.filter(p=>p.status==='skipped').length;
  }
}

function setTab(t) {
  currentTab = t;
  document.querySelectorAll('.tab-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.tab === t);
  });

  const isBriefs = t === 'briefs';
  document.getElementById('post-list').style.display   = isBriefs ? 'none' : '';
  document.getElementById('briefs-panel').style.display = isBriefs ? '' : 'none';
  document.getElementById('filter-bar').style.display   = isBriefs ? 'none' : '';

  if (isBriefs) {
    loadBriefs();
    return;
  }

  currentCategory = '';
  currentFilter = t === 'bar_scout' ? 'discovered' : 'pending';
  renderFilters();
  renderCategoryFilters();
  load();
}

// ── Design Briefs ────────────────────────────────────────────────────────────
async function loadBriefs() {
  const status = document.getElementById('briefs-status-filter').value;
  const r      = await fetch('/api/briefs?status=' + status);
  const briefs = await r.json();
  const container = document.getElementById('briefs-container');
  if (!briefs.length) {
    container.innerHTML = "<div class='empty'>No briefs in this status.</div>";
    return;
  }
  container.innerHTML = briefs.map(b => renderBrief(b)).join('');
}

function renderBrief(b) {
  const brief = b.brief;
  const directions = (brief.design_directions || []).map(d => `
    <div class="direction-card">
      <h4>${esc(d.name)}</h4>
      <p>${esc(d.description)}</p>
      <p><strong style="color:#e8dcc8">Typography:</strong> ${esc(d.typography)}</p>
      <p><strong style="color:#e8dcc8">Era:</strong> ${esc(d.reference_era)}</p>
      <p><strong style="color:#e8dcc8">Palette:</strong> ${esc((d.palette||[]).join(', '))}</p>
      <ul>${(d.key_visual_elements||[]).map(e => `<li>${esc(e)}</li>`).join('')}</ul>
    </div>
  `).join('');

  const avoid   = (brief.avoid||[]).map(a => `<li>${esc(a)}</li>`).join('');
  const queries = (brief.image_search_queries||[]).map(q =>
    `<li><a href="https://www.google.com/search?q=${encodeURIComponent(q)}&tbm=isch" target="_blank">${esc(q)}</a></li>`
  ).join('');

  return `
  <div class="brief-card ${b.status}" id="brief-${b.id}">
    <div class="brief-header">
      <div>
        <h3>${esc(b.bar_name)}</h3>
        <span>${esc(b.city||'')}, ${esc(b.state||'')} — ${esc(brief.era||'')}</span>
      </div>
      <div class="brief-actions">
        <button class="btn btn-approve" onclick="briefAction('${b.id}','approve')">✓ Approve</button>
        <button class="btn btn-skip"    onclick="briefAction('${b.id}','regenerate')">↻ Regenerate</button>
        <button class="btn btn-skip"    onclick="briefAction('${b.id}','skip')">Skip</button>
      </div>
    </div>
    ${brief.vibe ? `<div class="brief-vibe">${esc(brief.vibe)}</div>` : ''}
    ${directions ? `<div class="directions-grid">${directions}</div>` : ''}
    ${avoid ? `<div class="brief-section"><h4>Avoid</h4><ul>${avoid}</ul></div>` : ''}
    ${queries ? `<div class="brief-section"><h4>Image Search</h4><ul>${queries}</ul></div>` : ''}
    ${b.archival_sources ? `<div class="brief-section"><h4>Archival Sources</h4><pre>${esc(b.archival_sources)}</pre></div>` : ''}
    ${brief.brief_notes ? `<div class="brief-section"><h4>Notes</h4><p style="font-size:12px;color:#7a6e60">${esc(brief.brief_notes)}</p></div>` : ''}
  </div>`;
}

async function briefAction(id, action) {
  await fetch('/api/briefs/' + id + '/action', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ action }),
  });
  loadBriefs();
}

function setFilter(f) {
  currentFilter = f;
  renderFilters();
  render();
}

function esc(s) { const d=document.createElement('div'); d.textContent=s||''; return d.innerHTML; }

// ── Signal display helpers ──────────────────────────────────────────────────
const SIGNALS = [
  { key: 'years_in_operation',    label: 'Years open',     max: 5, weight: '2x'   },
  { key: 'reddit_signal',         label: 'Reddit signal',  max: 5, weight: '2x'   },
  { key: 'press_coverage',        label: 'Press coverage', max: 5, weight: '2x'   },
  { key: 'social_grief',          label: 'Social grief',   max: 5, weight: '1.5x' },
  { key: 'neighborhood_anchor',   label: 'Neighborhood anchor', max: 5, weight: '1.5x' },
  { key: 'community_specificity', label: 'Community specificity', max: 5, weight: '1.5x' },
  { key: 'story_richness',        label: 'Story richness', max: 5, weight: '1.5x' },
  { key: 'recency_of_closure',    label: 'Recency of closure', max: 5, weight: '1x' },
  { key: 'design_potential',      label: 'Design potential', max: 5, weight: '1x' },
];

function griefBadgeClass(score) {
  if (score >= 75) return 'grief-badge-build';
  if (score >= 60) return 'grief-badge-research';
  if (score >= 40) return 'grief-badge-watchlist';
  return 'grief-badge-pass';
}

function griefLabel(score) {
  if (score >= 75) return 'Build it';
  if (score >= 60) return 'Research more';
  if (score >= 40) return 'Watchlist';
  return 'Pass';
}

function dots(val, max) {
  const filled = Math.round(val);
  return '●'.repeat(filled) + '○'.repeat(max - filled);
}

function renderBreakdown(breakdown) {
  if (!breakdown) return '';
  let bd = breakdown;
  if (typeof bd === 'string') { try { bd = JSON.parse(bd); } catch(e) { return ''; } }
  return `<div class="breakdown-grid">` +
    SIGNALS.map(s => `
      <div class="breakdown-row">
        <span class="breakdown-label">${s.label}</span>
        <span class="breakdown-dots">${dots(bd[s.key]||0, s.max)}</span>
        <span class="breakdown-val">${bd[s.key]||0}/${s.max}</span>
        <span class="breakdown-weight">${s.weight}</span>
      </div>`).join('') +
  `</div>`;
}

// ── Main render ─────────────────────────────────────────────────────────────
function render() {
  const filterVal = currentFilter;
  let items;
  if (filterVal === 'all') {
    items = allItems;
  } else {
    items = allItems.filter(p => p.status === filterVal);
  }

  const el = document.getElementById('post-list');
  if (!items.length) { el.innerHTML = '<div class="empty">No ' + filterVal + ' items.</div>'; return; }

  if (currentTab === 'bar_scout') {
    el.innerHTML = items.map(item => renderCandidateCard(item)).join('');
    return;
  }

  el.innerHTML = items.map(item => {
    const isReviewed = item.status !== 'pending';

    if (currentTab === 'listener') {
      const excerpt    = (item.body||'').slice(0,200).replace(/\\n/g,' ');
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

    // content_multiplier and content_freshness
    const label = currentTab === 'content_multiplier' ? item.content_type : 'refreshed copy';
    const title = currentTab === 'content_multiplier' ? `${item.bar_name} — ${item.content_type}` : item.product_title;
    const draft = currentTab === 'content_multiplier' ? item.draft : item.new_description;

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
      if (ta && cc) ta.addEventListener('input', () => { cc.textContent = ta.value.length + ' chars'; });
    });
  }
}

function renderCandidateCard(item) {
  const score      = item.grief_score || 0;
  const badgeClass = griefBadgeClass(score);
  const label      = griefLabel(score);
  const isReviewed = item.status !== 'discovered';
  const date       = (item.discovered_at || '').slice(0, 10);

  const catKey   = item.category || 'bar';
  const catLabel = CATEGORY_LABELS[catKey] || catKey;

  return `
  <div class="post-card ${isReviewed ? item.status : ''}" id="card-${item.id}">
    <div class="post-head">
      <span class="score-badge ${badgeClass}">${score}/100</span>
      <span class="cat-badge cat-${catKey}">${catLabel}</span>
      <div style="flex:1">
        <div class="post-title">${esc(item.name)} <span style="color:#7a6e60;font-size:12px;font-weight:400">— ${esc(item.city)}${item.state ? ', '+esc(item.state) : ''}</span></div>
        <div class="post-meta">
          ${item.source_subreddit ? `r/${esc(item.source_subreddit)} · ` : ''}
          ${date}
          ${item.source_url ? ` · <a href="${esc(item.source_url)}" target="_blank">source ↗</a>` : ''}
        </div>
        <div class="post-meta" style="color:#d4820a;margin-top:2px">${label}</div>
      </div>
      ${isReviewed ? `<span class="status-pill pill-${item.status}">${item.status}</span>` : ''}
    </div>
    <div class="candidate-body">
      ${item.description ? `<div class="candidate-desc">${esc(item.description)}</div>` : ''}
      ${renderBreakdown(item.grief_breakdown)}
      ${item.evidence ? `
        <div class="evidence-label">Evidence</div>
        <div class="evidence-block" id="ev-${item.id}" onclick="toggleEvidence('${item.id}')">${esc(item.evidence)}</div>
      ` : ''}
    </div>
    <div class="reply-section">
      <div class="reply-label">Notes</div>
      <textarea id="reply-${item.id}" rows="2" placeholder="Add research notes…">${esc(item.notes||'')}</textarea>
      <div class="action-row">
        ${item.status === 'discovered' ? `
          <button class="btn btn-approve" onclick="act('${item.id}','approved','bar_scout')">Approve</button>
          <button class="btn btn-skip"    onclick="act('${item.id}','rejected','bar_scout')">Reject</button>
        ` : item.status === 'approved' ? `
          <button class="btn btn-graduate" onclick="graduateCandidate('${item.id}')">Graduate → bars.py</button>
          <button class="btn btn-skip"     onclick="act('${item.id}','discovered','bar_scout')">Undo</button>
        ` : `
          <button class="btn btn-skip" onclick="act('${item.id}','discovered','bar_scout')">Undo</button>
        `}
      </div>
    </div>
  </div>`;
}

function toggleBody(id)     { document.getElementById('body-'+id).classList.toggle('open'); }
function toggleEvidence(id) { document.getElementById('ev-'+id).classList.toggle('open'); }

async function act(id, status, tab) {
  // Save notes if on bar_scout before acting
  let body = { id, status, tab };
  if (tab === 'bar_scout') {
    const ta = document.getElementById('reply-' + id);
    if (ta) body.notes = ta.value;
  }
  await fetch('/api/action', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(body),
  });
  await load();
}

async function graduateCandidate(id) {
  const r    = await fetch('/api/graduate', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ id }),
  });
  const data = await r.json();
  if (data.snippet) {
    document.getElementById('modal-snippet').textContent = data.snippet;
    document.getElementById('graduate-modal').classList.add('open');
    await load();
  }
}

function closeModal() { document.getElementById('graduate-modal').classList.remove('open'); }

async function copySnippet() {
  const text = document.getElementById('modal-snippet').textContent;
  await navigator.clipboard.writeText(text);
  const btn = event.target;
  btn.textContent = 'Copied!';
  setTimeout(() => btn.textContent = 'Copy to clipboard', 1500);
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

// Close modal on overlay click
document.getElementById('graduate-modal').addEventListener('click', function(e) {
  if (e.target === this) closeModal();
});

// Initialize
renderFilters();
renderCategoryFilters();
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

    if tab == "bar_scout":
        category = request.args.get("category", "")
        with get_conn() as conn:
            if category:
                rows = fetchall(conn,
                    "SELECT * FROM bar_candidates WHERE category=? ORDER BY grief_score DESC, discovered_at DESC",
                    (category,),
                )
            else:
                rows = fetchall(conn,
                    "SELECT * FROM bar_candidates ORDER BY grief_score DESC, discovered_at DESC"
                )
        return jsonify(rows)

    return jsonify([])


@app.route("/api/action", methods=["POST"])
def api_action():
    data    = request.json
    item_id = data["id"]
    status  = data["status"]
    tab     = data.get("tab", "listener")
    now     = datetime.now().isoformat()

    table_map = {
        "listener":           "posts",
        "content_multiplier": "content_drafts",
        "content_freshness":  "freshness_queue",
        "bar_scout":          "bar_candidates",
    }
    table = table_map.get(tab, "posts")

    with get_conn() as conn:
        if tab == "bar_scout":
            notes = data.get("notes")
            if notes is not None:
                execute(conn,
                    "UPDATE bar_candidates SET status=?, notes=?, updated_at=? WHERE id=?",
                    (status, notes, now, item_id),
                )
            else:
                execute(conn,
                    "UPDATE bar_candidates SET status=?, updated_at=? WHERE id=?",
                    (status, now, item_id),
                )
        else:
            execute(conn,
                f"UPDATE {table} SET status=?, reviewed_at=? WHERE id=?",
                (status, now, item_id),
            )
    return jsonify({"ok": True})


@app.route("/api/graduate", methods=["POST"])
def api_graduate():
    """Mark a candidate as graduated and return a bars.py code snippet."""
    data    = request.json
    item_id = data["id"]
    now     = datetime.now().isoformat()

    with get_conn() as conn:
        row = fetchone(conn, "SELECT * FROM bar_candidates WHERE id=?", (item_id,))
        if not row:
            return jsonify({"ok": False, "error": "Not found"}), 404
        execute(conn,
            "UPDATE bar_candidates SET status='graduated', updated_at=? WHERE id=?",
            (now, item_id),
        )

    # Build a Python snippet ready to paste into shared/bars.py BARS list
    cat        = row.get("category") or "bar"
    cat_labels = {"bar": "Dive Bar", "venue": "Music Venue",
                  "restaurant": "Restaurant", "rink": "Roller Rink / Bowling"}
    cat_label  = cat_labels.get(cat, cat)
    snippet = (
        f"    # Category: {cat_label}\n"
        "    {\n"
        f"        \"name\": {json.dumps(row['name'])},\n"
        f"        \"city\": {json.dumps(row['city'] or '')},\n"
        f"        \"state\": {json.dumps(row['state'] or '')},\n"
        "        \"url\": \"https://pickledeggsco.com/products/ADD-HANDLE-HERE\",\n"
        f"        \"description\": {json.dumps(row['description'] or '')},\n"
        "    },"
    )

    # Generate a design brief for the newly graduated bar (best-effort)
    try:
        graduated_bar = {
            "name":        row["name"],
            "city":        row.get("city", ""),
            "state":       row.get("state", ""),
            "description": row.get("description", ""),
        }
        generate_design_brief(graduated_bar)
    except Exception as e:
        app.logger.error(f"Design brief generation failed after graduation: {e}")
        # Don't fail the graduation — brief generation is best-effort

    return jsonify({"ok": True, "snippet": snippet})


@app.route("/api/briefs")
def api_briefs():
    status = request.args.get("status", "pending")
    with get_conn() as conn:
        rows = fetchall(conn,
            "SELECT id, bar_name, city, state, brief_json, archival_sources, status, created_at, notes "
            "FROM design_briefs WHERE status = ? ORDER BY created_at DESC LIMIT 50",
            (status,),
        )
    briefs = []
    for row in rows:
        briefs.append({
            "id":              row["id"],
            "bar_name":        row["bar_name"],
            "city":            row["city"],
            "state":           row["state"],
            "brief":           json.loads(row["brief_json"]),
            "archival_sources": row["archival_sources"],
            "status":          row["status"],
            "created_at":      str(row["created_at"]),
            "notes":           row["notes"],
        })
    return jsonify(briefs)


@app.route("/api/briefs/<string:brief_id>/action", methods=["POST"])
def api_brief_action(brief_id):
    data   = request.json
    action = data.get("action")
    notes  = data.get("notes", "")
    now    = datetime.now().isoformat()

    if action == "regenerate":
        with get_conn() as conn:
            row = fetchone(conn, "SELECT bar_name FROM design_briefs WHERE id = ?", (brief_id,))
        if not row:
            return jsonify({"ok": False, "error": "Brief not found"}), 404
        bar_name = row["bar_name"]
        bar = next((b for b in BARS if b["name"] == bar_name), None)
        if not bar:
            return jsonify({"ok": False, "error": f"Bar '{bar_name}' not in BARS list"}), 404
        # Delete old and regenerate
        with get_conn() as conn:
            execute(conn, "DELETE FROM design_briefs WHERE id = ?", (brief_id,))
        brief = generate_design_brief(bar)
        return jsonify({"ok": True, "brief": brief})

    status_map = {"approve": "approved", "skip": "skipped"}
    new_status = status_map.get(action, "skipped")
    with get_conn() as conn:
        execute(conn,
            "UPDATE design_briefs SET status = ?, notes = ? WHERE id = ?",
            (new_status, notes, brief_id),
        )
    return jsonify({"ok": True})


# ─────────────────────────────────────────────
# ENTRYPOINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    print(f"\nReview Dashboard running at http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
