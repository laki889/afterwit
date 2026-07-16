"""The dashboard page — one self-contained HTML template for both delivery
modes:

  - `afterwit serve`  → BOOT is null; the page fetches /api/data and polls.
  - `afterwit report` → BOOT is the full dataset inlined; zero requests.

Privacy invariants: no external fonts/CDNs/requests of any kind (system font
stacks only), and all lesson content is rendered via textContent — never
innerHTML — so model-generated text can't inject markup. The inlined JSON
escapes '<' so `</script>` inside a lesson can't break out of the script tag.
"""

from __future__ import annotations

import json
from string import Template
from typing import Any

from . import __version__


def boot_json(data: dict[str, Any]) -> str:
    """JSON safe to inline inside a <script> block: every '<' in the payload
    (necessarily inside a JSON string) becomes \\u003c, so '</script>' or
    '<!--' in lesson text cannot terminate or comment out the script."""
    return json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")


def render_page(boot: str = "null") -> str:
    return _PAGE.substitute(BOOT=boot, VERSION=__version__)


_PAGE = Template(r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>Afterwit — lessons learned</title>
<style>
:root{
  --bg:#F6F8F5; --surface:#FFFFFF; --ink:#1B231E; --muted:#5C6A61;
  --line:#DFE6DF; --accent:#2E6B52; --accent-ink:#FFFFFF; --wash:#EAF2EC;
  --track:#EDF1ED; --shadow:0 1px 2px rgba(27,35,30,.06),0 4px 14px rgba(27,35,30,.05);
  --font-display:'Iowan Old Style','Palatino Linotype',Palatino,Georgia,'Times New Roman',serif;
  --font-body:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
  --font-mono:ui-monospace,'SF Mono',SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace;
}
@media (prefers-color-scheme: dark){
  :root{
    --bg:#111613; --surface:#191F1B; --ink:#E6ECE7; --muted:#8FA096;
    --line:#28312B; --accent:#63B08D; --accent-ink:#0E1411; --wash:#1F2A23;
    --track:#222B25; --shadow:0 1px 2px rgba(0,0,0,.35),0 4px 14px rgba(0,0,0,.25);
  }
}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{background:var(--bg);color:var(--ink);font:15px/1.55 var(--font-body);
  -webkit-font-smoothing:antialiased}
a{color:var(--accent)}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:4px}
@media (prefers-reduced-motion: reduce){*{transition:none!important;animation:none!important}}

.wrap{max-width:1060px;margin:0 auto;padding:0 20px}

/* ---------- masthead ---------- */
.masthead{border-bottom:1px solid var(--line);background:var(--surface)}
.masthead .wrap{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;padding:18px 20px 14px}
.wordmark{font-family:var(--font-display);font-size:28px;font-weight:600;letter-spacing:.01em}
.wordmark .tick{color:var(--accent)}
.tagline{color:var(--muted);font-size:13px;font-style:italic;font-family:var(--font-display)}
.badge{margin-left:auto;display:inline-flex;align-items:center;gap:6px;
  font-family:var(--font-mono);font-size:11px;color:var(--accent);
  background:var(--wash);border:1px solid var(--line);border-radius:999px;padding:3px 10px;
  white-space:nowrap}
.badge .pulse{width:7px;height:7px;border-radius:50%;background:var(--accent);display:inline-block}
.searchrow{padding:0 0 16px}
.searchrow input{width:100%;max-width:520px;padding:9px 14px;font:14px var(--font-body);
  color:var(--ink);background:var(--bg);border:1px solid var(--line);border-radius:8px}
.searchrow input::placeholder{color:var(--muted)}
.snapshot-note{font-family:var(--font-mono);font-size:11px;color:var(--muted);
  border:1px dashed var(--line);border-radius:6px;padding:2px 8px}

/* ---------- stat tiles ---------- */
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:20px 0}
.tile{background:var(--surface);border:1px solid var(--line);border-radius:10px;
  padding:14px 16px;box-shadow:var(--shadow)}
.tile .num{font-family:var(--font-display);font-size:30px;line-height:1.1;
  font-variant-numeric:tabular-nums}
.tile .lbl{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.08em;margin-top:2px}

/* ---------- charts ---------- */
.trends{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:0 0 20px}
@media (max-width:760px){.trends{grid-template-columns:1fr}}
.chart-card{background:var(--surface);border:1px solid var(--line);border-radius:10px;
  padding:14px 16px 10px;box-shadow:var(--shadow)}
.chart-card h2{margin:0 0 10px;font-size:12px;font-weight:600;color:var(--muted);
  text-transform:uppercase;letter-spacing:.08em}
.chart-scroll{overflow-x:auto}
svg text{font-family:var(--font-mono);font-size:10px;fill:var(--muted)}
.tagbars{display:flex;flex-direction:column;gap:6px}
.tagbar{display:grid;grid-template-columns:120px 1fr 34px;align-items:center;gap:8px;
  background:none;border:0;padding:2px 4px;font:inherit;color:inherit;text-align:left;
  border-radius:6px;cursor:pointer}
.tagbar:hover{background:var(--wash)}
.tagbar[aria-pressed="true"]{background:var(--wash);box-shadow:inset 0 0 0 1px var(--accent)}
.tagbar .name{font-family:var(--font-mono);font-size:12px;overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap}
.tagbar .track{display:block;height:10px;background:var(--track);border-radius:5px;overflow:hidden}
.tagbar .fill{display:block;height:100%;background:var(--accent);opacity:.85;border-radius:5px 4px 4px 5px}
.tagbar .count{font-family:var(--font-mono);font-size:11px;color:var(--muted);
  text-align:right;font-variant-numeric:tabular-nums}

/* ---------- layout: rail + feed ---------- */
.split{display:grid;grid-template-columns:210px 1fr;gap:20px;align-items:start;margin-bottom:48px}
@media (max-width:760px){.split{grid-template-columns:1fr}}
.rail{position:sticky;top:14px;display:flex;flex-direction:column;gap:16px}
@media (max-width:760px){.rail{position:static}}
.rail h3{margin:0 0 6px;font-size:11px;font-weight:600;color:var(--muted);
  text-transform:uppercase;letter-spacing:.08em}
.rail .group{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.railbtn{display:flex;justify-content:space-between;gap:8px;width:100%;background:none;
  border:0;padding:4px 6px;font:13px var(--font-body);color:var(--ink);text-align:left;
  border-radius:6px;cursor:pointer}
.railbtn:hover{background:var(--wash)}
.railbtn[aria-pressed="true"]{background:var(--wash);box-shadow:inset 0 0 0 1px var(--accent)}
.railbtn .n{font-family:var(--font-mono);font-size:11px;color:var(--muted);
  font-variant-numeric:tabular-nums}
.clearbtn{width:100%;padding:7px;border:1px solid var(--line);border-radius:8px;
  background:var(--surface);color:var(--muted);font:12px var(--font-body);cursor:pointer}
.clearbtn:hover{color:var(--ink);border-color:var(--accent)}

/* ---------- feed ---------- */
.month{margin:26px 0 10px;display:flex;align-items:center;gap:10px}
.month:first-child{margin-top:4px}
.month .m{font-family:var(--font-display);font-size:16px;font-style:italic}
.month .rule{flex:1;height:1px;background:var(--line)}
.month .n{font-family:var(--font-mono);font-size:11px;color:var(--muted)}
.card{background:var(--surface);border:1px solid var(--line);border-radius:10px;
  padding:14px 16px;margin-bottom:10px;box-shadow:var(--shadow)}
.card h4{margin:0 0 6px;font-size:15.5px;line-height:1.35;font-weight:650;text-wrap:balance}
.card .meta{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-bottom:8px}
.chip{background:none;border:1px solid var(--line);border-radius:999px;padding:1px 9px;
  font-family:var(--font-mono);font-size:10.5px;color:var(--muted);cursor:pointer}
.chip:hover{border-color:var(--accent);color:var(--accent)}
.chip[aria-pressed="true"]{background:var(--wash);border-color:var(--accent);color:var(--accent)}
.meta .proj{font-family:var(--font-mono);font-size:11px;color:var(--accent)}
.meta .date{font-family:var(--font-mono);font-size:11px;color:var(--muted)}
.conf{display:inline-flex;align-items:center;gap:6px;margin-left:auto}
.conf .bar{width:44px;height:5px;border-radius:3px;background:var(--track);overflow:hidden}
.conf .bar i{display:block;height:100%;background:var(--accent);border-radius:3px}
.conf .v{font-family:var(--font-mono);font-size:10.5px;color:var(--muted);
  font-variant-numeric:tabular-nums}
.card .lesson{margin:0;max-width:68ch}
.card details{margin-top:9px;border-top:1px dashed var(--line);padding-top:8px}
.card summary{cursor:pointer;font-size:12px;color:var(--muted);user-select:none}
.card summary:hover{color:var(--accent)}
.fieldrow{margin:8px 0 0}
.fieldrow .k{font-size:10.5px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}
.fieldrow .t{margin:2px 0 0;font-size:13.5px;max-width:68ch}
.empty{border:1px dashed var(--line);border-radius:10px;padding:36px;text-align:center;
  color:var(--muted)}
.empty .big{font-family:var(--font-display);font-size:19px;font-style:italic;color:var(--ink)}

/* ---------- footer / tooltip ---------- */
footer{border-top:1px solid var(--line);color:var(--muted);font-size:12px;padding:14px 0 40px}
footer .wrap{display:flex;flex-wrap:wrap;gap:8px 18px}
footer code{font-family:var(--font-mono);font-size:11px}
#tip{position:fixed;pointer-events:none;background:var(--ink);color:var(--bg);
  font-family:var(--font-mono);font-size:11px;padding:4px 8px;border-radius:6px;
  transform:translate(-50%,-130%);white-space:nowrap;display:none;z-index:10}
</style>
</head>
<body>
<div id="tip" role="presentation"></div>

<header class="masthead">
  <div class="wrap">
    <div class="wordmark">afterwit<span class="tick">.</span></div>
    <div class="tagline">wisdom after the event, filed for the next one</div>
    <span class="badge" id="mode-badge"><span class="pulse"></span><span id="mode-text">100% local</span></span>
  </div>
  <div class="wrap searchrow">
    <input id="q" type="search" placeholder="Search lessons — title, problem, resolution, tags…"
      aria-label="Search lessons">
  </div>
</header>

<div class="wrap">
  <section class="tiles" id="tiles" aria-label="Summary"></section>
  <section class="trends">
    <div class="chart-card">
      <h2>Lessons over time</h2>
      <div class="chart-scroll" id="chart-months" role="img" aria-label="Bar chart of lessons per month"></div>
    </div>
    <div class="chart-card">
      <h2>Top tags</h2>
      <div class="tagbars" id="chart-tags"></div>
    </div>
  </section>
  <div class="split">
    <aside class="rail" aria-label="Filters">
      <div class="group"><h3>Projects</h3><div id="rail-projects"></div></div>
      <button class="clearbtn" id="clear">Reset filters</button>
    </aside>
    <section id="feed" aria-live="polite"></section>
  </div>
</div>

<footer><div class="wrap">
  <span>afterwit v$VERSION</span>
  <span>nothing leaves this machine — the page makes no external requests</span>
  <span id="foot-db"></span>
</div></footer>

<script>
"use strict";
/* Boot data: inlined by `afterwit report`, null under `afterwit serve`. */
var BOOT = $BOOT;

var state = { q: "", project: null, tag: null, month: null, data: null, sig: "" };
var byId = function (id) { return document.getElementById(id); };

function el(tag, cls, text) {
  var e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined && text !== null) e.textContent = String(text);
  return e;
}
function svgEl(tag) { return document.createElementNS("http://www.w3.org/2000/svg", tag); }

/* ---------- filtering ---------- */
function visibleLessons() {
  var q = state.q.toLowerCase();
  return state.data.lessons.filter(function (l) {
    if (state.project && l.project !== state.project) return false;
    if (state.tag && (l.tags || []).indexOf(state.tag) === -1) return false;
    if (state.month && (l.created_at || "").slice(0, 7) !== state.month) return false;
    if (!q) return true;
    var hay = [l.title, l.problem, l.root_cause, l.resolution, l.lesson,
               (l.tags || []).join(" "), l.project].join(" ").toLowerCase();
    return q.split(/\s+/).every(function (w) { return hay.indexOf(w) !== -1; });
  });
}

/* ---------- tiles ---------- */
function renderTiles(lessons) {
  var t = byId("tiles"); t.textContent = "";
  var s = state.data.stats || {};
  var projects = {};
  state.data.lessons.forEach(function (l) { projects[l.project || "unknown"] = 1; });
  [[s.total_lessons || 0, "lessons"],
   [s.processed_sessions || 0, "sessions distilled"],
   [Object.keys(projects).length, "projects"],
   [s.lessons_last_30_days || 0, "last 30 days"]].forEach(function (pair) {
    var tile = el("div", "tile");
    tile.appendChild(el("div", "num", pair[0]));
    tile.appendChild(el("div", "lbl", pair[1]));
    t.appendChild(tile);
  });
}

/* ---------- month chart (SVG bars) ---------- */
function monthRange(lessons) {
  var months = lessons.map(function (l) { return (l.created_at || "").slice(0, 7); })
    .filter(Boolean).sort();
  if (!months.length) return [];
  var out = [], cur = months[0], last = months[months.length - 1], guard = 0;
  while (cur <= last && guard++ < 1200) {
    out.push(cur);
    var y = +cur.slice(0, 4), m = +cur.slice(5, 7);
    m += 1; if (m > 12) { m = 1; y += 1; }
    cur = y + "-" + (m < 10 ? "0" + m : m);
  }
  return out.slice(-60); /* cap keeps the NEWEST months, not the oldest */
}
function renderMonths(lessons) {
  var host = byId("chart-months"); host.textContent = "";
  var months = monthRange(state.data.lessons);
  if (!months.length) { host.appendChild(el("div", "empty", "No data yet")); return; }
  var counts = {};
  lessons.forEach(function (l) {
    var k = (l.created_at || "").slice(0, 7);
    counts[k] = (counts[k] || 0) + 1;
  });
  var max = 1;
  months.forEach(function (m) { if ((counts[m] || 0) > max) max = counts[m]; });

  var bw = 26, gap = 2, padL = 6, padB = 18, padT = 14, H = 150;
  var W = padL * 2 + months.length * (bw + gap);
  var svg = svgEl("svg");
  svg.setAttribute("width", Math.max(W, 260)); svg.setAttribute("height", H);
  svg.setAttribute("viewBox", "0 0 " + Math.max(W, 260) + " " + H);
  /* recessive grid: three hairlines */
  [0.33, 0.66, 1].forEach(function (f) {
    var y = padT + (H - padT - padB) * (1 - f);
    var ln = svgEl("line");
    ln.setAttribute("x1", padL); ln.setAttribute("x2", Math.max(W, 260) - padL);
    ln.setAttribute("y1", y); ln.setAttribute("y2", y);
    ln.setAttribute("stroke", "currentColor"); ln.setAttribute("opacity", "0.08");
    svg.appendChild(ln);
  });
  var maxMonth = months.reduce(function (a, b) { return (counts[b] || 0) > (counts[a] || 0) ? b : a; }, months[0]);
  months.forEach(function (m, i) {
    var c = counts[m] || 0;
    var h = c === 0 ? 2 : Math.max(4, (H - padT - padB) * c / max);
    var x = padL + i * (bw + gap);
    var y = H - padB - h;
    var r = svgEl("rect");
    r.setAttribute("x", x); r.setAttribute("y", y);
    r.setAttribute("width", bw); r.setAttribute("height", h);
    r.setAttribute("rx", 4);
    r.setAttribute("fill", c === 0 ? "currentColor" : "var(--accent)");
    r.setAttribute("opacity", c === 0 ? "0.12" : state.month === m ? "1" : "0.85");
    if (state.month === m) {
      r.setAttribute("stroke", "var(--ink)"); r.setAttribute("stroke-width", "1.5");
    }
    r.style.cursor = "pointer";
    r.setAttribute("role", "button"); r.setAttribute("tabindex", "0");
    r.setAttribute("data-fkey", "month:" + m);
    r.setAttribute("aria-label", m + ": " + c + " lessons; activate to filter by this month");
    var toggleMonth = function () { state.month = state.month === m ? null : m; render(); };
    r.addEventListener("click", toggleMonth);
    r.addEventListener("keydown", function (ev) {
      if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); toggleMonth(); }
    });
    r.addEventListener("mousemove", function (ev) { tip(ev, m + " · " + c + " lesson" + (c === 1 ? "" : "s")); });
    r.addEventListener("mouseleave", hideTip);
    svg.appendChild(r);
    /* selective direct labels: peak month + latest month only */
    if (c > 0 && (m === maxMonth || i === months.length - 1)) {
      var tv = svgEl("text");
      tv.setAttribute("x", x + bw / 2); tv.setAttribute("y", y - 4);
      tv.setAttribute("text-anchor", "middle");
      tv.textContent = c;
      svg.appendChild(tv);
    }
    var tl = svgEl("text");
    tl.setAttribute("x", x + bw / 2); tl.setAttribute("y", H - 5);
    tl.setAttribute("text-anchor", "middle");
    tl.textContent = m.slice(2).replace("-", "·");
    svg.appendChild(tl);
  });
  host.appendChild(svg);
}

/* ---------- tag chart ---------- */
function renderTags(lessons) {
  var host = byId("chart-tags"); host.textContent = "";
  var counts = {};
  lessons.forEach(function (l) {
    (l.tags || []).forEach(function (t) { counts[t] = (counts[t] || 0) + 1; });
  });
  var tags = Object.keys(counts).sort(function (a, b) { return counts[b] - counts[a] || (a < b ? -1 : 1); });
  if (!tags.length) { host.appendChild(el("div", "empty", "No tags yet")); return; }
  var max = counts[tags[0]];
  tags.slice(0, 8).forEach(function (t) {
    var b = el("button", "tagbar");
    if (counts[t] >= 3) b.title = "you keep hitting this \u2014 " + counts[t] + " lessons share this tag";
    b.setAttribute("data-fkey", "tag:" + t);
    b.setAttribute("aria-pressed", state.tag === t ? "true" : "false");
    b.appendChild(el("span", "name", "#" + t));
    var track = el("span", "track");
    var fill = el("span", "fill");
    fill.style.width = Math.max(6, 100 * counts[t] / max) + "%";
    track.appendChild(fill); b.appendChild(track);
    b.appendChild(el("span", "count", counts[t]));
    b.addEventListener("click", function () { state.tag = state.tag === t ? null : t; render(); });
    host.appendChild(b);
  });
}

/* ---------- projects rail ---------- */
function renderProjects() {
  var host = byId("rail-projects"); host.textContent = "";
  var counts = {};
  state.data.lessons.forEach(function (l) {
    var p = l.project || "unknown"; counts[p] = (counts[p] || 0) + 1;
  });
  var names = Object.keys(counts).sort(function (a, b) { return counts[b] - counts[a] || (a < b ? -1 : 1); });
  if (!names.length) { host.appendChild(el("div", "empty", "—")); return; }
  names.forEach(function (p) {
    var b = el("button", "railbtn");
    b.setAttribute("data-fkey", "proj:" + p);
    b.setAttribute("aria-pressed", state.project === p ? "true" : "false");
    b.appendChild(el("span", "", p));
    b.appendChild(el("span", "n", counts[p]));
    b.addEventListener("click", function () { state.project = state.project === p ? null : p; render(); });
    host.appendChild(b);
  });
}

/* ---------- feed ---------- */
function monthName(k) {
  var names = ["January","February","March","April","May","June","July",
               "August","September","October","November","December"];
  return names[+k.slice(5, 7) - 1] + " " + k.slice(0, 4);
}
function fieldRow(label, text) {
  var d = el("div", "fieldrow");
  d.appendChild(el("div", "k", label));
  d.appendChild(el("p", "t", text));
  return d;
}
function renderFeed(lessons) {
  var feed = byId("feed"); feed.textContent = "";
  if (!lessons.length) {
    var em = el("div", "empty");
    em.appendChild(el("div", "big",
      state.data.lessons.length ? "Nothing matches these filters." : "No lessons yet."));
    em.appendChild(el("div", "",
      state.data.lessons.length ? "Loosen the search or reset the filters."
        : "Finish a Claude Code session, then run `afterwit sync`."));
    feed.appendChild(em);
    return;
  }
  var lastMonth = "";
  lessons.forEach(function (l) {
    var mk = (l.created_at || "").slice(0, 7);
    if (mk && mk !== lastMonth) {
      lastMonth = mk;
      var h = el("div", "month");
      h.appendChild(el("span", "m", monthName(mk)));
      h.appendChild(el("span", "rule"));
      var n = lessons.filter(function (x) { return (x.created_at || "").slice(0, 7) === mk; }).length;
      h.appendChild(el("span", "n", n + " lesson" + (n === 1 ? "" : "s")));
      feed.appendChild(h);
    }
    var card = el("article", "card");
    card.appendChild(el("h4", "", l.title));
    var meta = el("div", "meta");
    meta.appendChild(el("span", "proj", l.project || "unknown"));
    meta.appendChild(el("span", "date", (l.source_ts || l.created_at || "").slice(0, 10)));
    (l.tags || []).forEach(function (t) {
      var c = el("button", "chip", "#" + t);
      c.setAttribute("data-fkey", "chip:" + l.id + ":" + t);
      c.setAttribute("aria-pressed", state.tag === t ? "true" : "false");
      c.addEventListener("click", function () { state.tag = state.tag === t ? null : t; render(); });
      meta.appendChild(c);
    });
    if (typeof l.confidence === "number") {
      var conf = el("span", "conf");
      conf.title = "model confidence this lesson is reusable";
      var bar = el("span", "bar"); var fill = el("i");
      fill.style.width = Math.round(l.confidence * 100) + "%";
      bar.appendChild(fill); conf.appendChild(bar);
      conf.appendChild(el("span", "v", Math.round(l.confidence * 100) + "%"));
      meta.appendChild(conf);
    }
    card.appendChild(meta);
    card.appendChild(el("p", "lesson", l.lesson));
    if (l.problem || l.root_cause || l.resolution) {
      var det = el("details");
      det.appendChild(el("summary", "", "problem · root cause · resolution"));
      if (l.problem) det.appendChild(fieldRow("Problem", l.problem));
      if (l.root_cause) det.appendChild(fieldRow("Root cause", l.root_cause));
      if (l.resolution) det.appendChild(fieldRow("Resolution", l.resolution));
      card.appendChild(det);
    }
    feed.appendChild(card);
  });
}

/* ---------- tooltip ---------- */
function tip(ev, text) {
  var t = byId("tip");
  t.textContent = text; t.style.display = "block";
  t.style.left = ev.clientX + "px"; t.style.top = ev.clientY + "px";
}
function hideTip() { byId("tip").style.display = "none"; }

/* ---------- render root ---------- */
function render() {
  if (!state.data) return;
  hideTip(); /* the hovered mark may not survive the rebuild */
  var fkey = document.activeElement && document.activeElement.getAttribute
    ? document.activeElement.getAttribute("data-fkey") : null;
  var lessons = visibleLessons();
  renderTiles(lessons);
  renderMonths(lessons);
  renderTags(lessons);
  renderProjects();
  renderFeed(lessons);
  if (fkey) { /* keyboard users keep their place when a filter rebuilds the DOM */
    var back = document.querySelector('[data-fkey="' + fkey.replace(/"/g, '') + '"]');
    if (back && back.focus) back.focus();
  }
  byId("clear").style.visibility =
    (state.q || state.project || state.tag || state.month) ? "visible" : "hidden";
}

function setData(data) {
  var sig = JSON.stringify([data.stats, data.lessons.length,
    data.lessons.length ? data.lessons[0].id : 0]);
  var changed = sig !== state.sig;
  state.data = data; state.sig = sig;
  byId("foot-db").textContent = data.db_path ? "db: " + data.db_path : "";
  if (changed) render();
}

byId("q").addEventListener("input", function () { state.q = this.value.trim(); render(); });
byId("clear").addEventListener("click", function () {
  state.q = ""; state.project = null; state.tag = null; state.month = null; byId("q").value = ""; render();
});

if (BOOT) {
  byId("mode-text").textContent = "snapshot · " + (BOOT.generated_at || "").slice(0, 10)
    + (BOOT.filtered_project ? " · " + BOOT.filtered_project + " only" : "");
  document.querySelector(".badge .pulse").style.display = "none";
  setData(BOOT);
} else {
  byId("mode-text").textContent = "live · 100% local";
  var pull = function () {
    fetch("/api/data").then(function (r) { return r.json(); })
      .then(function (data) {
        byId("mode-text").textContent = "live · 100% local"; /* recover after a blip */
        setData(data);
      })
      .catch(function () { byId("mode-text").textContent = "server unreachable — is afterwit serve running?"; });
  };
  pull();
  setInterval(pull, 5000);
}
</script>
</body>
</html>
""")
