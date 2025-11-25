#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Interactive viewer generator with WORKING filtering + better zoom + ID focus.

Additions:
- Smooth, cursor-centered zoom (mouse wheel), with sensible min/max.
- Double-click to zoom in, Shift+Double-click to zoom out.
- Keyboard: "+" / "=" zoom in, "-" zoom out, "0" reset, "f" fit.
- When the search text matches an ID (key) exactly and you press Enter,
  the viewer will center/zoom to that point and temporarily enlarge its circle.

Usage:
  python3 generate_viewer_fixed.py \
    --json data.json \
    --image input.jpg \
    --out viewer.html \
    --radius 18 --min_radius 4 --padding 3 --thickness 2
"""

import argparse
import json
import base64
import mimetypes

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", required=True, help="Path to data JSON")
    ap.add_argument("--image", required=True, help="Background image")
    ap.add_argument("--out", required=True, help="Output HTML file")
    ap.add_argument("--radius", type=float, default=18.0)
    ap.add_argument("--min_radius", type=float, default=4.0)
    ap.add_argument("--padding", type=float, default=3.0)
    ap.add_argument("--thickness", type=float, default=2.0)
    args = ap.parse_args()

    with open(args.json, "r", encoding="utf-8") as f:
        data = json.load(f)

    mime, _ = mimetypes.guess_type(args.image)
    if not mime:
        mime = "image/jpeg"
    with open(args.image, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("ascii")
    img_uri = f"data:{mime};base64,{img_b64}"

    template = r"""<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<title>Interactive Viewer - filtered</title>
<style>
  * { box-sizing: border-box; }
  html, body { height: 100%; margin: 0; font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; }
  #app { display: grid; grid-template-columns: 1fr 360px; height: 100%; }
  #left { position: relative; background: #111; }
  #toolbar { position: absolute; top: 8px; left: 8px; z-index: 10; display:flex; gap:8px; }
  .btn { background:#fff; border:1px solid #ddd; border-radius:8px; padding:6px 10px; cursor:pointer; font-size:13px; }
  #canvasWrap { width: 100%; height: 100%; }
  canvas { display:block; width:100%; height:100%; cursor: grab; }
  #right { padding:12px; border-left:1px solid #ddd; overflow:auto; }
  #search { width:100%; padding:8px 10px; border:1px solid #ccc; border-radius:8px; font-size:14px; margin-bottom:8px; }
  #list { font-size:13px; line-height:1.4; }
  .item { padding:6px 4px; border-bottom:1px dashed #eee; cursor:pointer; }
  .item em { background: #ffefa0; font-style: normal; }
  .dim { opacity: 0.55; }
</style>
</head>
<body>
<div id="app">
  <div id="left">
    <div id="toolbar">
      <button id="fit" class="btn" title="Fit to screen (F)">Fit</button>
      <button id="reset" class="btn" title="Reset (0)">Reset</button>
    </div>
    <div id="canvasWrap"><canvas id="c"></canvas></div>
  </div>
  <div id="right">
    <input id="search" placeholder="Filter / paste exact ID and press Enter"/>
    <div id="list"></div>
  </div>
</div>

<script>
const DATA = __DATA_JSON__;
const IMG_SRC = "__IMG_URI__";
const BASE_R = __BASE_R__;
const MIN_R = __MIN_R__;
const PAD = __PAD__;
const THICKNESS = __THICKNESS__;

// Zoom config
const ZOOM_MIN = 0.1;
const ZOOM_MAX = 8.0;
const ZOOM_SENS = 0.0015; // higher = faster

// Boost highlight
const BOOST_EXTRA = 10;       // extra radius during boost
const BOOST_MS = 1800;        // highlight duration

// Build points
let points = [];
for (const [key, obj] of Object.entries(DATA)) {
  if (!obj || !Array.isArray(obj.pos_img) || obj.pos_img.length < 2) continue;
  const [x,y] = obj.pos_img;
  const rgb = (Array.isArray(obj.rgb) && obj.rgb.length===3) ? obj.rgb : [255,0,0];
  points.push({
    key: key,
    x: Number(x),
    y: Number(y),
    rgb: rgb,
    r: BASE_R,
    layer: (obj.layer||"") + "",
    name: (obj.name||"") + "",
    txt: (obj.txt||"") + "",
    payload: obj,
    hidden: false,
    boostUntil: 0,
  });
}

// Collision solver with padding
function resolveCollisions(maxIter = 400, eps = 1e-3) {
  if (points.length <= 1) return;
  for (const p of points) p.r = BASE_R;
  for (let iter=0; iter<maxIter; iter++) {
    let changed = false;
    const ub = new Array(points.length).fill(BASE_R);
    for (let i=0; i<points.length; i++) {
      for (let j=i+1; j<points.length; j++) {
        const dx = points[j].x - points[i].x;
        const dy = points[j].y - points[i].y;
        const d = Math.hypot(dx,dy);
        if (d <= 1e-6) continue;
        const lim = Math.max(0, d - PAD);
        ub[i] = Math.min(ub[i], lim - points[j].r);
        ub[j] = Math.min(ub[j], lim - points[i].r);
      }
    }
    for (let i=0; i<points.length; i++) {
      const neo = Math.max(MIN_R, Math.min(BASE_R, ub[i]));
      if (Math.abs(neo - points[i].r) > eps) { points[i].r = neo; changed = true; }
    }
    if (!changed) break;
  }
}

// Canvas + state
const canvas = document.getElementById('c');
const ctx = canvas.getContext('2d');
const dpr = Math.max(1, window.devicePixelRatio || 1);
let img = new Image(); img.src = IMG_SRC;
let scale = 1, tx = 0, ty = 0;
let dragging = false, lx = 0, ly = 0;
let selectedKey = null;
let searchQ = "";

// Helpers
function resizeCanvas() {
  const rect = canvas.parentElement.getBoundingClientRect();
  canvas.width = Math.max(1, rect.width * dpr);
  canvas.height = Math.max(1, rect.height * dpr);
}
function fitToScreen() {
  const s = Math.min(canvas.width / img.width, canvas.height / img.height);
  scale = s; tx = (canvas.width - img.width * s)/2; ty = (canvas.height - img.height * s)/2;
}
function resetView() {
  scale = 1; tx = 0; ty = 0;
}
function screenToImage(sx, sy) { // sx/sy in CSS pixels
  const ix = (sx * dpr - tx) / (scale);
  const iy = (sy * dpr - ty) / (scale);
  return [ix, iy];
}
function imageToScreen(ix, iy) { // returns canvas pixels
  const sx = ix * scale + tx;
  const sy = iy * scale + ty;
  return [sx, sy];
}
function pick(sx, sy) { // sx/sy CSS pixels
  const [ix, iy] = screenToImage(sx, sy);
  for (let i=points.length-1; i>=0; i--) {
    const p = points[i];
    const dx = ix - p.x, dy = iy - p.y;
    if (Math.hypot(dx,dy) <= p.r + 3) return p;
  }
  return null;
}

// Zooming
function zoomAt(cssX, cssY, factor) {
  const [ix, iy] = screenToImage(cssX, cssY);
  const newScale = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, scale * factor));
  // Convert to canvas pixel center at CSS position
  const cx = cssX * dpr, cy = cssY * dpr;
  tx = cx - ix * newScale;
  ty = cy - iy * newScale;
  scale = newScale;
}

function centerOnPoint(p, targetScale=null) {
  const newScale = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, targetScale ?? Math.max(scale, 2.0)));
  // Center of canvas in canvas pixels
  const cx = canvas.width * 0.5;
  const cy = canvas.height * 0.5;
  tx = cx - p.x * newScale;
  ty = cy - p.y * newScale;
  scale = newScale;
}

// Draw (dims non-matching)
function draw() {
  ctx.setTransform(1,0,0,1,0,0);
  ctx.clearRect(0,0,canvas.width, canvas.height);
  ctx.setTransform(scale, 0, 0, scale, tx, ty);
  ctx.drawImage(img, 0, 0);
  const now = performance.now();
  for (const p of points) {
    const r = p.rgb[0], g = p.rgb[1], b = p.rgb[2];
    const baseRadius = p.r + ((p.boostUntil > now) ? BOOST_EXTRA : 0);
    ctx.lineWidth = THICKNESS / Math.max(scale, 0.0001);
    ctx.strokeStyle = 'rgb(' + r + ', ' + g + ', ' + b + ')';
    ctx.globalAlpha = p.hidden ? 0.15 : 1.0;
    ctx.beginPath();
    ctx.arc(p.x, p.y, baseRadius, 0, Math.PI*2);
    ctx.stroke();
    if (!p.hidden && p.key === selectedKey) {
      ctx.lineWidth = (THICKNESS*2) / Math.max(scale, 0.0001);
      ctx.strokeStyle = "yellow";
      ctx.beginPath();
      ctx.arc(p.x, p.y, baseRadius + 4, 0, Math.PI*2);
      ctx.stroke();
    }
  }
  ctx.globalAlpha = 1.0;
}

// List rendering with highlight
function escapeHtml(s){return s.replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}
function hi(haystack, needle) {
  if (!needle) return escapeHtml(haystack);
  // Escape user input to safe regex
  const re = new RegExp(needle.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'ig');
  return escapeHtml(haystack).replace(re, m => '<em>'+m+'</em>');
}
function renderList() {
  const el = document.getElementById('list');
  let rows = [];
  for (const p of points) {
    const full = (p.key+" "+p.layer+" "+p.txt+" "+p.name).trim();
    if (searchQ && full.toLowerCase().indexOf(searchQ) === -1) continue;
    rows.push(
      '<div class="item" data-key="'+p.key+'">'+
        '<strong>'+hi(p.key, searchQ)+'</strong><br/>' +
        '<span>'+hi((p.layer||""), searchQ)+'</span><br/>' +
        '<span>'+hi((p.txt||""), searchQ)+'</span>' +
      '</div>'
    );
  }
  el.innerHTML = rows.join("") || "<div class='dim'>No matches.</div>";
  for (const div of el.querySelectorAll('.item')) {
    div.onclick = () => { selectedKey = div.dataset.key; draw(); };
  }
}

// Filtering logic — sets p.hidden and redraws
function applyFilter() {
  const q = searchQ;
  for (const p of points) {
    const hay = (p.key + " " + p.layer + " " + p.txt + " " + p.name).toLowerCase();
    p.hidden = q && hay.indexOf(q) === -1;
  }
  renderList();
  draw();
}

// Events
window.addEventListener('resize', () => { resizeCanvas(); draw(); });
document.getElementById('fit').onclick = () => { fitToScreen(); draw(); };
document.getElementById('reset').onclick = () => { resetView(); draw(); };

const search = document.getElementById('search');
search.addEventListener('input', () => { searchQ = search.value.trim().toLowerCase(); applyFilter(); });
search.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    const raw = search.value.trim();
    if (!raw) return;
    const k = raw.toLowerCase();
    // exact ID match
    const p = points.find(pp => (pp.key+"").toLowerCase() === k);
    if (p) {
      selectedKey = p.key;
      p.boostUntil = performance.now() + BOOST_MS;
      centerOnPoint(p, Math.max(scale, 2.2));
      draw();
    }
  }
});

canvas.addEventListener('mousedown', (e) => { dragging=true; canvas.style.cursor='grabbing'; lx=e.clientX; ly=e.clientY; });
window.addEventListener('mouseup', () => { dragging=false; canvas.style.cursor='grab'; });
window.addEventListener('mousemove', (e) => {
  if (!dragging) return;
  const dx = e.clientX - lx, dy = e.clientY - ly;
  tx += dx * dpr; ty += dy * dpr; lx = e.clientX; ly = e.clientY; draw();
});

// Smooth, cursor-centered zoom
canvas.addEventListener('wheel', (e) => {
  e.preventDefault();
  const factor = Math.exp(-e.deltaY * ZOOM_SENS);
  const rect = canvas.getBoundingClientRect();
  zoomAt(e.clientX - rect.left, e.clientY - rect.top, factor);
  draw();
}, { passive:false });

// Double-click zoom in (Shift = zoom out)
canvas.addEventListener('dblclick', (e) => {
  const rect = canvas.getBoundingClientRect();
  const cssX = e.clientX - rect.left, cssY = e.clientY - rect.top;
  const factor = e.shiftKey ? 1/1.75 : 1.75;
  zoomAt(cssX, cssY, factor);
  draw();
});

// Keyboard zoom/reset
window.addEventListener('keydown', (e) => {
  if (e.key === '+' || e.key === '=') {
    const rect = canvas.getBoundingClientRect();
    zoomAt(rect.width/2, rect.height/2, 1.25);
    draw();
  } else if (e.key === '-') {
    const rect = canvas.getBoundingClientRect();
    zoomAt(rect.width/2, rect.height/2, 1/1.25);
    draw();
  } else if (e.key === '0') {
    resetView(); draw();
  } else if (e.key.toLowerCase() === 'f') {
    fitToScreen(); draw();
  }
});

canvas.addEventListener('click', (e) => {
  const rect = canvas.getBoundingClientRect();
  const hit = pick(e.clientX - rect.left, e.clientY - rect.top);
  selectedKey = hit ? hit.key : null; draw();
});

// Start
img.onload = () => {
  resizeCanvas(); fitToScreen();
  resolveCollisions(600, 1e-3);
  renderList();
  applyFilter();
};
</script>
</body>
</html>
"""

    html = (template
            .replace("__DATA_JSON__", json.dumps(data, ensure_ascii=False))
            .replace("__IMG_URI__", img_uri.replace("\\", "\\\\").replace('"', '\\"'))
            .replace("__BASE_R__", str(args.radius))
            .replace("__MIN_R__", str(args.min_radius))
            .replace("__PAD__", str(args.padding))
            .replace("__THICKNESS__", str(args.thickness))
            )

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    print("Wrote:", args.out)

if __name__ == "__main__":
    main()
