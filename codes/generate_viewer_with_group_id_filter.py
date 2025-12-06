#!/usr/bin/env python3
"""
generate_viewer_with_group_id_filter.py

Interactive viewer with group_id filtering functionality.
Plots circles on the image and allows filtering by group_id via a clickable list.

Usage:
  python3 generate_viewer_with_group_id_filter.py --json extracted_elements.json --image input.jpg --out interactive_viewer_filtered.html \
    --radius 18 --min_radius 4 --padding 3 --thickness 2
"""

import argparse, json, base64, os, mimetypes
from collections import defaultdict

def b64_data_uri(path: str) -> str:
    mime, _ = mimetypes.guess_type(path)
    if mime is None:
        mime = "application/octet-stream"
    with open(path, "rb") as f:
        raw = f.read()
    return f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--json", required=True)
    p.add_argument("--image", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--radius", type=int, default=18)
    p.add_argument("--min_radius", type=int, default=4)
    p.add_argument("--padding", type=float, default=3.0, help="Extra spacing between circles (image px).")
    p.add_argument("--thickness", type=int, default=2)
    args = p.parse_args()

    with open(args.json, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Top-level JSON must be a dict keyed by IDs.")

    # Group elements by group_id
    group_id_map = defaultdict(list)
    for key, obj in data.items():
        group_id = obj.get("group_id", "No Group")
        group_id_map[group_id].append(key)
    
    # Sort group_ids for display
    sorted_group_ids = sorted(group_id_map.keys())
    
    img_uri = b64_data_uri(args.image)
    data_json = json.dumps(data, ensure_ascii=False)
    group_id_map_json = json.dumps({k: v for k, v in group_id_map.items()}, ensure_ascii=False)

    html = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>Interactive Viewer with Group ID Filter</title>
  <style>
    * {{ box-sizing: border-box; }}
    html, body {{ height: 100%; margin: 0; font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; }}
    #app {{ display: grid; grid-template-columns: 1fr 380px; height: 100%; }}
    #left {{ position: relative; background: #111; }}
    #toolbar {{ position: absolute; top: 8px; left: 8px; z-index: 10; display:flex; gap:8px; }}
    .btn {{ background:#fff; border:1px solid #ddd; border-radius:8px; padding:6px 10px; cursor:pointer; font-size:13px; }}
    .btn:active {{ transform: translateY(1px); }}
    #canvasWrap {{ width: 100%; height: 100%; }}
    canvas {{ display:block; width:100%; height:100%; cursor: grab; }}
    canvas:active {{ cursor: grabbing; }}
    #right {{ border-left:1px solid #e5e7eb; padding:12px; overflow:auto; background:#fafafa; display: flex; flex-direction: column; }}
    #right h2 {{ margin:0 0 8px; }}
    #filterSection {{ margin-bottom: 16px; }}
    #filterSection h3 {{ margin: 0 0 8px; font-size: 14px; color: #333; }}
    #groupList {{ max-height: 300px; overflow-y: auto; border: 1px solid #ddd; border-radius: 8px; background: #fff; }}
    .group-item {{ padding: 8px 12px; cursor: pointer; border-bottom: 1px solid #eee; transition: background 0.2s; }}
    .group-item:hover {{ background: #f0f0f0; }}
    .group-item:last-child {{ border-bottom: none; }}
    .group-item.active {{ background: #e3f2fd; font-weight: 600; }}
    .group-item-count {{ color: #666; font-size: 11px; margin-left: 8px; }}
    #search {{ width: 100%; padding: 8px; border:1px solid #ddd; border-radius:8px; margin-bottom:8px; }}
    #info {{ font-size:13px; color:#555; margin-bottom:6px; }}
    .pill {{ display:inline-block; padding:2px 8px; border-radius:999px; background:#eee; font-size:12px; margin:0 6px 6px 0; }}
    pre {{ background: #fff; border:1px solid #eee; border-radius:8px; padding:8px; max-height:45vh; overflow:auto; }}
    #diagnostics {{ position:absolute; top:8px; right:8px; background:rgba(255,255,255,0.9); border:1px solid #ddd; border-radius:8px; padding:6px 10px; font-size:12px; }}
  </style>
</head>
<body>
<div id="app">
  <div id="left">
    <div id="toolbar">
      <button id="reset" class="btn">Reset View</button>
      <button id="fit" class="btn">Fit to Screen</button>
    </div>
    <div id="canvasWrap">
      <canvas id="c"></canvas>
      <div id="diagnostics">overlaps: <span id="ovl">–</span></div>
    </div>
  </div>
  <div id="right">
    <h2>Group ID Filter</h2>
    <div id="filterSection">
      <h3>Filter by Group ID</h3>
      <div id="groupList"></div>
    </div>
    <h2>Details</h2>
    <input id="search" placeholder="Filter by ID / layer / txt..."/>
    <div id="info">Click a circle to see details.</div>
    <div id="badges"></div>
    <pre id="dump"></pre>
  </div>
</div>

<script>
const DATA = {data_json};
const GROUP_ID_MAP = {group_id_map_json};
const IMG_SRC = {json.dumps(img_uri)};
const BASE_R = {args.radius};
const MIN_R = {args.min_radius};
const PAD = {args.padding};
const THICKNESS = {args.thickness};

// Build points
let points = [];
let allPoints = [];
for (const [key, obj] of Object.entries(DATA)) {{
  if (!obj || !Array.isArray(obj.pos_img) || obj.pos_img.length < 2) continue;
  const [x,y] = obj.pos_img;
  const rgb = (Array.isArray(obj.rgb) && obj.rgb.length===3) ? obj.rgb : [255,0,0];
  const point = {{ key, x: Number(x), y: Number(y), rgb, payload: obj, r: BASE_R, baseR: BASE_R }};
  allPoints.push(point);
  points.push(point);
}}

// Current filter state
let selectedGroupId = null;
let useZoomAdaptiveRadius = false;

// Build group list UI
function buildGroupList() {{
  const groupList = document.getElementById('groupList');
  groupList.innerHTML = '';
  
  // Add "All" option
  const allItem = document.createElement('div');
  allItem.className = 'group-item' + (selectedGroupId === null ? ' active' : '');
  allItem.textContent = 'All Groups';
  const allCount = document.createElement('span');
  allCount.className = 'group-item-count';
  allCount.textContent = `(${{allPoints.length}})`;
  allItem.appendChild(allCount);
  allItem.addEventListener('click', () => {{
    selectedGroupId = null;
    applyGroupFilter();
    buildGroupList();
  }});
  groupList.appendChild(allItem);
  
  // Add each group_id
  const sortedGroups = Object.keys(GROUP_ID_MAP).sort();
  for (const groupId of sortedGroups) {{
    const item = document.createElement('div');
    item.className = 'group-item' + (selectedGroupId === groupId ? ' active' : '');
    item.textContent = groupId || '(No Group)';
    const count = document.createElement('span');
    count.className = 'group-item-count';
    count.textContent = `(${{GROUP_ID_MAP[groupId].length}})`;
    item.appendChild(count);
    item.addEventListener('click', () => {{
      selectedGroupId = groupId;
      applyGroupFilter();
      buildGroupList();
    }});
    groupList.appendChild(item);
  }}
}}

// Calculate zoom-adaptive radius
// When zoomed out (low scale): bigger circles
// When zoomed in (high scale): smaller circles
function calculateZoomAdaptiveRadius(currentScale, baseFitScale) {{
  // Normalize scale relative to baseFitScale (1.0 = fit to screen)
  const normalizedScale = currentScale / baseFitScale;
  
  // Inverse relationship: lower scale = bigger radius, higher scale = smaller radius
  // Scale range: 0.1 to 8, but we want to map it to radius multiplier
  // When normalizedScale is low (zoomed out): multiplier should be high (e.g., 2.5x)
  // When normalizedScale is high (zoomed in): multiplier should be low (e.g., 0.4x)
  
  // Clamp normalized scale to reasonable range
  const clampedScale = Math.max(0.1, Math.min(8, normalizedScale));
  
  // Inverse mapping: scale 0.1 -> radius 2.5x, scale 8 -> radius 0.4x
  // Using exponential decay for smooth transition
  const minMultiplier = 0.4;  // Minimum radius when fully zoomed in
  const maxMultiplier = 2.5;  // Maximum radius when fully zoomed out
  const multiplier = maxMultiplier * Math.pow(minMultiplier / maxMultiplier, (clampedScale - 0.1) / (8 - 0.1));
  
  return multiplier;
}}

// Apply group filter
function applyGroupFilter() {{
  if (selectedGroupId === null) {{
    points = [...allPoints];
    useZoomAdaptiveRadius = false;
    // Reset all points to base radius
    for (const p of points) {{
      p.r = p.baseR;
    }}
  }} else {{
    const keysInGroup = GROUP_ID_MAP[selectedGroupId] || [];
    points = allPoints.filter(p => keysInGroup.includes(p.key));
    useZoomAdaptiveRadius = true;
  }}
  // Update radii based on current zoom if filtering
  updateRadiiForZoom();
  // Recalculate collisions for filtered points
  resolveCollisions(600, 1e-3);
  draw();
}}

// Update radii based on current zoom level
function updateRadiiForZoom() {{
  if (!useZoomAdaptiveRadius) return;
  
  const multiplier = calculateZoomAdaptiveRadius(scale, baseFitScale);
  const targetBaseR = BASE_R * multiplier;
  
  // Update base radius for all filtered points
  for (const p of points) {{
    p.baseR = targetBaseR;
    p.r = targetBaseR;
  }}
  
  // Recalculate collisions with new base radius
  resolveCollisions(600, 1e-3);
}}

// Global upper-bound shrinking with padding
function resolveCollisions(maxIter = 400, eps = 1e-3) {{
  if (points.length <= 1) return;
  // init - use baseR for each point
  for (const p of points) p.r = p.baseR;
  for (let iter=0; iter<maxIter; iter++) {{
    let changed = false;
    // start each sweep with current radii as upper-bounds
    const ub = points.map(p => Math.min(p.r, p.baseR));
    // examine all pairs
    for (let i=0; i<points.length; i++) {{
      const a = points[i];
      for (let j=i+1; j<points.length; j++) {{
        const b = points[j];
        const dx = a.x - b.x, dy = a.y - b.y;
        const d = Math.hypot(dx, dy);
        const allowedSum = Math.max(0, d - PAD);
        const sum = Math.max(MIN_R, ub[i]) + Math.max(MIN_R, ub[j]);
        if (sum > allowedSum) {{
          // shrink both bounds proportionally towards allowedSum
          const extra = sum - allowedSum;
          const di = extra/2, dj = extra/2;
          ub[i] = Math.max(MIN_R, ub[i] - di);
          ub[j] = Math.max(MIN_R, ub[j] - dj);
        }}
      }}
    }}
    // apply ubs
    for (let i=0; i<points.length; i++) {{
      const old = points[i].r;
      const neo = Math.max(MIN_R, Math.min(points[i].baseR, ub[i]));
      if (Math.abs(neo - old) > eps) {{ points[i].r = neo; changed = true; }}
    }}
    if (!changed) break;
  }}
}}

// Verify overlaps count (for diagnostics box)
function countOverlaps() {{
  let ovl = 0;
  for (let i=0; i<points.length; i++) {{
    for (let j=i+1; j<points.length; j++) {{
      const a = points[i], b = points[j];
      const dx = a.x - b.x, dy = a.y - b.y;
      const d = Math.hypot(dx, dy);
      if (d + 1e-6 < a.r + b.r + PAD) ovl++;
    }}
  }}
  return ovl;
}}

// Canvas setup
const canvas = document.getElementById('c');
const ctx = canvas.getContext('2d', {{ alpha: true }});
const wrap = document.getElementById('canvasWrap');
const dpr = window.devicePixelRatio || 1;
let img = new Image();
img.src = IMG_SRC;

let scale = 1, tx = 0, ty = 0;
let isPanning = false, panStart = {{x:0, y:0, tx0:0, ty0:0}};
let selectedKey = null;
let baseFitScale = 1;

function resizeCanvas() {{
  const w = wrap.clientWidth;
  const h = wrap.clientHeight;
  canvas.width = Math.max(1, Math.floor(w * dpr));
  canvas.height = Math.max(1, Math.floor(h * dpr));
  canvas.style.width = w + "px";
  canvas.style.height = h + "px";
  ctx.setTransform(1,0,0,1,0,0);
}}

function fitToScreen() {{
  const w = canvas.width / dpr, h = canvas.height / dpr;
  const sx = w / img.width, sy = h / img.height;
  baseFitScale = Math.min(sx, sy);
  scale = baseFitScale;
  tx = (w - img.width * scale)/2;
  ty = (h - img.height * scale)/2;
  updateRadiiForZoom();
}}

function resetView() {{ 
  scale = 1; 
  tx = 0; 
  ty = 0; 
  updateRadiiForZoom();
}}

function draw() {{
  ctx.setTransform(1,0,0,1,0,0);
  ctx.clearRect(0,0,canvas.width, canvas.height);
  ctx.setTransform(scale * dpr, 0, 0, scale * dpr, tx * dpr, ty * dpr);
  ctx.drawImage(img, 0, 0);
  for (const p of points) {{
    const [r,g,b] = p.rgb;
    ctx.lineWidth = THICKNESS / Math.max(scale, 0.0001);
    ctx.strokeStyle = `rgb(${{r}}, ${{g}}, ${{b}})`;
    ctx.beginPath();
    ctx.arc(p.x, p.y, p.r, 0, Math.PI*2);
    ctx.stroke();
    if (p.key === selectedKey) {{
      ctx.lineWidth = (THICKNESS*2) / Math.max(scale, 0.0001);
      ctx.strokeStyle = "yellow";
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r + 4, 0, Math.PI*2);
      ctx.stroke();
    }}
  }}
  document.getElementById('ovl').textContent = countOverlaps();
}}

function screenToImage(mx, my) {{ return [(mx - tx)/scale, (my - ty)/scale]; }}

function pick(mx, my) {{
  const [ix, iy] = screenToImage(mx, my);
  let best = null, bestD2 = 1e18;
  for (const p of points) {{
    const dx = ix - p.x, dy = iy - p.y;
    const d2 = dx*dx + dy*dy;
    if (d2 <= (p.r + 6)**2 && d2 < bestD2) best = p, bestD2 = d2;
  }}
  return best;
}}

function updateDetails(p) {{
  const info = document.getElementById('info');
  const badges = document.getElementById('badges');
  const dump = document.getElementById('dump');
  if (!p) {{ info.textContent = "Click a circle to see details."; badges.innerHTML=""; dump.textContent=""; return; }}
  const layer = p.payload && p.payload.layer ? p.payload.layer : "(no layer)";
  const groupId = p.payload && p.payload.group_id ? p.payload.group_id : "(no group)";
  info.innerHTML = `<b>ID:</b> ${{p.key}}`;
  badges.innerHTML = `
    <span class="pill">x=${{p.x.toFixed(1)}}</span>
    <span class="pill">y=${{p.y.toFixed(1)}}</span>
    <span class="pill">r=${{p.r.toFixed(1)}}</span>
    <span class="pill">layer: ${{layer}}</span>
    <span class="pill">group: ${{groupId}}</span>
  `;
  dump.textContent = JSON.stringify(p.payload, null, 2);
}}

// Events
window.addEventListener('resize', () => {{ resizeCanvas(); draw(); }});
document.getElementById('reset').addEventListener('click', () => {{ resetView(); draw(); }});
document.getElementById('fit').addEventListener('click', () => {{ fitToScreen(); draw(); }});
canvas.addEventListener('mousedown', (e) => {{
  isPanning = true; canvas.style.cursor="grabbing";
  panStart = {{x:e.clientX, y:e.clientY, tx0:tx, ty0:ty}};
}});
window.addEventListener('mouseup', () => {{ isPanning=false; canvas.style.cursor="grab"; }});
window.addEventListener('mousemove', (e) => {{
  if (!isPanning) return;
  tx = panStart.tx0 + (e.clientX - panStart.x);
  ty = panStart.ty0 + (e.clientY - panStart.y);
  draw();
}});
canvas.addEventListener('wheel', (e) => {{
  e.preventDefault();
  const rect = canvas.getBoundingClientRect();
  const mx = e.clientX - rect.left, my = e.clientY - rect.top;
  const [ix, iy] = screenToImage(mx, my);
  const delta = -Math.sign(e.deltaY) * 0.2;
  const newScale = Math.min(8, Math.max(0.1, scale * (1 + delta)));
  tx = mx - ix * newScale;
  ty = my - iy * newScale;
  scale = newScale;
  updateRadiiForZoom();
  draw();
}}, {{ passive:false }});
canvas.addEventListener('click', (e) => {{
  const rect = canvas.getBoundingClientRect();
  const hit = pick(e.clientX - rect.left, e.clientY - rect.top);
  selectedKey = hit ? hit.key : null;
  updateDetails(hit); draw();
}});

// Search filter redraw (dim non-matching)
document.getElementById('search').addEventListener('input', (e) => {{
  const q = e.target.value.trim().toLowerCase();
  ctx.setTransform(1,0,0,1,0,0); ctx.clearRect(0,0,canvas.width, canvas.height);
  ctx.setTransform(scale * dpr, 0, 0, scale * dpr, tx * dpr, ty * dpr);
  ctx.drawImage(img, 0, 0);
  for (const p of points) {{
    const hay = (p.key + " " + (p.payload.layer||"") + " " + (p.payload.txt||"")).toLowerCase();
    const match = hay.includes(q);
    const [r,g,b] = p.rgb;
    ctx.lineWidth = THICKNESS / Math.max(scale, 0.0001);
    ctx.strokeStyle = match ? `rgb(${{r}}, ${{g}}, ${{b}})` : "rgba(200,200,200,0.35)";
    ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, Math.PI*2); ctx.stroke();
    if (p.key === selectedKey) {{
      ctx.lineWidth = (THICKNESS*2) / Math.max(scale, 0.0001);
      ctx.strokeStyle = "yellow";
      ctx.beginPath(); ctx.arc(p.x, p.y, p.r+4, 0, Math.PI*2); ctx.stroke();
    }}
  }}
  document.getElementById('ovl').textContent = countOverlaps();
}});

// Start
img.onload = () => {{
  resizeCanvas(); fitToScreen();
  resolveCollisions(600, 1e-3);
  buildGroupList();
  draw();
}};
</script>
</body>
</html>
"""
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Wrote viewer to:", args.out)

if __name__ == "__main__":
    main()

