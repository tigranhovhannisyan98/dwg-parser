#!/usr/bin/env python3
"""
Generate standalone HTML file for Cable Tray Takeoff Tool

Creates a self-contained HTML file with embedded image and all functionality.
Similar to generate_viewer.py but for manual cable tray plotting.

Usage:
    python3 generate_cable_tray_takeoff.py --image plan.jpg --out takeoff.html [--output output.json]
"""

import argparse
import json
import base64
import os
import mimetypes

def b64_data_uri(path: str) -> str:
    """Convert file to base64 data URI"""
    mime, _ = mimetypes.guess_type(path)
    if mime is None:
        mime = "application/octet-stream"
    with open(path, "rb") as f:
        raw = f.read()
    return f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")

def main():
    parser = argparse.ArgumentParser(
        description="Generate standalone HTML for Cable Tray Takeoff",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 generate_cable_tray_takeoff.py --image plan.jpg --out takeoff.html
  python3 generate_cable_tray_takeoff.py --image plan.jpg --out takeoff.html --output my_trays.json
        """
    )
    parser.add_argument("--image", required=True, help="Path to electrical plan image")
    parser.add_argument("--out", required=True, help="Output HTML file path")
    parser.add_argument("--output", default="output.json", help="Default output JSON filename (default: output.json)")
    args = parser.parse_args()
    
    if not os.path.exists(args.image):
        print(f"Error: Image file not found: {args.image}")
        return
    
    # Convert image to base64
    img_uri = b64_data_uri(args.image)
    output_json_js = json.dumps(args.output)
    
    html = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Cable Tray Takeoff Tool</title>
  <style>
    * {{ box-sizing: border-box; }}
    html, body {{ height: 100%; margin: 0; font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; }}
    #app {{ display: grid; grid-template-columns: 1fr 320px; height: 100%; }}
    #left {{ position: relative; background: #111; overflow: hidden; }}
    #toolbar {{ position: absolute; top: 8px; left: 8px; z-index: 10; display:flex; gap:8px; flex-wrap: wrap; }}
    .btn {{ background:#fff; border:1px solid #ddd; border-radius:8px; padding:6px 10px; cursor:pointer; font-size:13px; }}
    .btn:hover {{ background:#f5f5f5; }}
    .btn:active {{ transform: translateY(1px); }}
    .btn.success {{ background:#4CAF50; color:white; border-color:#4CAF50; }}
    .btn.success:hover {{ background:#45a049; }}
    .btn.danger {{ background:#f44336; color:white; border-color:#f44336; }}
    .btn.danger:hover {{ background:#da190b; }}
    #canvasWrap {{ width: 100%; height: 100%; }}
    canvas {{ display:block; width:100%; height:100%; cursor: crosshair; }}
    canvas:active {{ cursor: crosshair; }}
    #right {{ border-left:1px solid #e5e7eb; padding:12px; overflow-y: auto; overflow-x: hidden; background:#fafafa; display: flex; flex-direction: column; height: 100%; }}
    #right h2 {{ margin:0 0 12px; font-size:18px; }}
    #status {{ font-size:13px; color:#555; margin-bottom:12px; padding:8px; background:#fff; border:1px solid #ddd; border-radius:6px; }}
    #info {{ font-size:12px; color:#666; margin-bottom:12px; }}
    .info-section {{ margin-bottom:16px; padding:12px; background:#fff; border:1px solid #ddd; border-radius:6px; }}
    .info-section h3 {{ margin:0 0 8px; font-size:14px; color:#333; }}
    .stat {{ font-size:12px; color:#666; margin:4px 0; }}
    #zoom-info {{ position:absolute; bottom:12px; right:12px; background:rgba(0,0,0,0.7); color:#fff; padding:8px 12px; border-radius:6px; font-size:12px; z-index:10; }}
    #file-input {{ display:none; }}
    .file-label {{ display:inline-block; padding:6px 10px; background:#666; color:white; border-radius:8px; cursor:pointer; font-size:13px; }}
    .file-label:hover {{ background:#777; }}
  </style>
</head>
<body>
<div id="app">
  <div id="left">
    <div id="toolbar">
      <label for="file-input" class="file-label">Load JSON</label>
      <input type="file" id="file-input" accept="application/json">
      <button id="zoom-in" class="btn">Zoom In (+)</button>
      <button id="zoom-out" class="btn">Zoom Out (-)</button>
      <button id="fit" class="btn">Fit</button>
      <button id="reset" class="btn">Reset</button>
      <button id="save" class="btn success">Save (S)</button>
      <button id="clear" class="btn danger">Clear (C)</button>
    </div>
    <div id="canvasWrap">
      <canvas id="c"></canvas>
      <div id="zoom-info">Zoom: <span id="zoom-level">100%</span></div>
    </div>
  </div>
  <div id="right">
    <h2>Cable Tray Takeoff</h2>
    <div id="status">Ready - Click to add points</div>
    <div class="info-section">
      <h3>Instructions</h3>
      <div id="info">
        <div><strong>Left-click:</strong> Add point (auto-connects if point selected)</div>
        <div><strong>Left-click point:</strong> Auto-connect to selected point</div>
        <div><strong>Right-click:</strong> Delete point</div>
        <div><strong>Shift+Drag:</strong> Pan image</div>
        <div><strong>Space+Drag:</strong> Pan mode</div>
        <div><strong>Mouse wheel:</strong> Zoom</div>
        <div><strong>Arrow keys:</strong> Navigate/pan</div>
        <div><strong>S key:</strong> Save to JSON</div>
        <div><strong>C key:</strong> Clear all</div>
        <div><strong>ESC:</strong> Deselect current point</div>
      </div>
    </div>
    <div class="info-section">
      <h3>Statistics</h3>
      <div class="stat">Points: <span id="stat-points">0</span></div>
      <div class="stat">Connections: <span id="stat-connections">0</span></div>
      <div class="stat">Cable Trays: <span id="stat-trays">0</span></div>
    </div>
  </div>
</div>

<script>
const IMG_SRC = {json.dumps(img_uri)};
const OUTPUT_JSON = {output_json_js};
const ZOOM_MIN = 0.05;
const ZOOM_MAX = 20.0;
const ZOOM_SENS = 0.002;

// State
const canvas = document.getElementById('c');
const ctx = canvas.getContext('2d');
const dpr = Math.max(1, window.devicePixelRatio || 1);
let img = new Image();
img.src = IMG_SRC;

let scale = 1, tx = 0, ty = 0;
let dragging = false, lx = 0, ly = 0;
let points = [];
let connections = [];
let nextPointId = 0;
let selectedPointIndex = null;

// Helpers
function resizeCanvas() {{
  const rect = canvas.parentElement.getBoundingClientRect();
  canvas.width = Math.max(1, rect.width * dpr);
  canvas.height = Math.max(1, rect.height * dpr);
}}

function fitToScreen() {{
  if (!img.complete) return;
  const s = Math.min(canvas.width / img.width, canvas.height / img.height) * 0.95;
  scale = s;
  tx = (canvas.width - img.width * s) / 2;
  ty = (canvas.height - img.height * s) / 2;
  updateZoomInfo();
  draw();
}}

function resetView() {{
  scale = 1;
  tx = 0;
  ty = 0;
  updateZoomInfo();
  draw();
}}

function screenToImage(sx, sy) {{
  // sx, sy are in CSS pixels
  // Convert to canvas pixels first
  const canvasX = sx * dpr;
  const canvasY = sy * dpr;
  // Then convert to image coordinates
  const ix = (canvasX - tx) / scale;
  const iy = (canvasY - ty) / scale;
  return [ix, iy];
}}

function findNearestPoint(x, y, threshold = 30) {{
  if (points.length === 0) return null;
  let minDist = Infinity;
  let nearestIndex = null;
  const thresholdScaled = threshold / scale;
  for (let i = 0; i < points.length; i++) {{
    const p = points[i];
    const dist = Math.sqrt((p.x - x) ** 2 + (p.y - y) ** 2);
    if (dist < thresholdScaled && dist < minDist) {{
      minDist = dist;
      nearestIndex = i;
    }}
  }}
  return nearestIndex;
}}

function zoomAt(cssX, cssY, factor) {{
  // Get the image coordinates at the cursor position
  const [ix, iy] = screenToImage(cssX, cssY);
  // Calculate new scale
  const newScale = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, scale * factor));
  // Calculate new translation to keep the point under cursor fixed
  const canvasX = cssX * dpr;
  const canvasY = cssY * dpr;
  tx = canvasX - ix * newScale;
  ty = canvasY - iy * newScale;
  scale = newScale;
  updateZoomInfo();
}}

function updateZoomInfo() {{
  document.getElementById('zoom-level').textContent = Math.round(scale * 100) + '%';
}}

function updateStats() {{
  document.getElementById('stat-points').textContent = points.length;
  document.getElementById('stat-connections').textContent = connections.length;
  document.getElementById('stat-trays').textContent = connections.length;
}}

function updateStatus(message) {{
  document.getElementById('status').textContent = message;
}}

function addPoint(x, y) {{
  const point = {{ x: x, y: y, id: nextPointId++ }};
  points.push(point);
  const newIndex = points.length - 1;
  
  if (selectedPointIndex !== null) {{
    // Auto-connect to previously selected point
    connectPoints(selectedPointIndex, newIndex);
    updateStatus(`Added point ${{point.id}} and connected to point ${{points[selectedPointIndex].id}} - Continue clicking to extend`);
  }} else {{
    updateStatus(`Added point ${{point.id}} - Click another point to connect`);
  }}
  
  // Keep the new point selected for continued connection
  selectedPointIndex = newIndex;
  updateStats();
}}

function connectPoints(index1, index2) {{
  const conn = [Math.min(index1, index2), Math.max(index1, index2)];
  const exists = connections.some(c => c[0] === conn[0] && c[1] === conn[1]);
  
  if (!exists) {{
    connections.push(conn);
    updateStatus(`Connected point ${{points[index1].id}} to point ${{points[index2].id}}`);
  }} else {{
    updateStatus('Connection already exists');
  }}
  updateStats();
}}

function deletePoint(index) {{
  const pointId = points[index].id;
  points.splice(index, 1);
  
  connections = connections
    .filter(conn => conn[0] !== index && conn[1] !== index)
    .map(conn => [
      conn[0] > index ? conn[0] - 1 : conn[0],
      conn[1] > index ? conn[1] - 1 : conn[1]
    ]);
  
  if (selectedPointIndex === index) {{
    selectedPointIndex = null;
  }} else if (selectedPointIndex > index) {{
    selectedPointIndex--;
  }}
  
  updateStatus(`Deleted point ${{pointId}}`);
  updateStats();
}}

function clearAll() {{
  if (confirm('Clear all points and connections?')) {{
    points = [];
    connections = [];
    selectedPointIndex = null;
    nextPointId = 0;
    updateStatus('Cleared all points');
    updateStats();
    draw();
  }}
}}

function calculateIdealDiagonalPath(p1, p2) {{
  return {{
    start: {{ x: p1.x, y: p1.y }},
    end: {{ x: p2.x, y: p2.y }},
    path: [{{ x: p1.x, y: p1.y }}, {{ x: p2.x, y: p2.y }}]
  }};
}}

function saveData() {{
  // Build nodes object
  const nodes = {{}};
  points.forEach(p => {{
    nodes[`node_id_${{p.id}}`] = {{ x: p.x, y: p.y }};
  }});
  
  // Build edges array with weights (distances in pixels)
  const edges = connections.map(conn => {{
    const p1 = points[conn[0]];
    const p2 = points[conn[1]];
    const weight = Math.sqrt((p2.x - p1.x) ** 2 + (p2.y - p1.y) ** 2);
    
    return {{
      from: `node_id_${{p1.id}}`,
      to: `node_id_${{p2.id}}`,
      weight: weight
    }};
  }});
  
  const outputData = {{
    nodes: nodes,
    edges: edges
  }};
  
  const blob = new Blob([JSON.stringify(outputData, null, 2)], {{ type: 'application/json' }});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = OUTPUT_JSON;
  a.click();
  URL.revokeObjectURL(url);
  
  updateStatus(`✅ Saved ${{edges.length}} edges and ${{Object.keys(nodes).length}} nodes to ${{OUTPUT_JSON}}`);
}}

function loadData(data) {{
  // Handle new weighted graph format
  if (data.nodes && data.edges) {{
    // Build points from nodes
    points = [];
    const nodeIdToIndex = new Map();
    
    for (const [nodeId, nodeData] of Object.entries(data.nodes)) {{
      // Extract numeric ID from node ID (e.g., "node_id_1" -> 1)
      const numericId = parseInt(nodeId.replace(/^node_id_/, ''), 10);
      const index = points.length;
      points.push({{
        x: nodeData.x,
        y: nodeData.y,
        id: numericId
      }});
      nodeIdToIndex.set(nodeId, index);
    }}
    
    // Update nextPointId
    nextPointId = Math.max(...points.map(p => p.id), -1) + 1;
    
    // Build connections from edges
    connections = [];
    data.edges.forEach(edge => {{
      const idx1 = nodeIdToIndex.get(edge.from);
      const idx2 = nodeIdToIndex.get(edge.to);
      if (idx1 !== undefined && idx2 !== undefined) {{
        connections.push([Math.min(idx1, idx2), Math.max(idx1, idx2)]);
      }}
    }});
  }} else if (data.points) {{
    // Legacy format support
    points = data.points.map(p => ({{
      x: Array.isArray(p.position) ? p.position[0] : p.x,
      y: Array.isArray(p.position) ? p.position[1] : p.y,
      id: p.id
    }}));
    nextPointId = Math.max(...points.map(p => p.id), -1) + 1;
    
    if (data.cable_trays) {{
      connections = [];
      const pointMap = new Map();
      points.forEach((p, idx) => pointMap.set(p.id, idx));
      
      data.cable_trays.forEach(tray => {{
        const idx1 = pointMap.get(tray.point_ids[0]);
        const idx2 = pointMap.get(tray.point_ids[1]);
        if (idx1 !== undefined && idx2 !== undefined) {{
          connections.push([Math.min(idx1, idx2), Math.max(idx1, idx2)]);
        }}
      }});
    }}
  }}
  
  updateStats();
  draw();
  updateStatus(`Loaded ${{points.length}} nodes and ${{connections.length}} edges`);
}}

function draw() {{
  if (!img.complete) return;
  
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.setTransform(scale, 0, 0, scale, tx, ty);
  
  // Draw image
  ctx.drawImage(img, 0, 0);
  
  // Draw connections (ideal diagonal paths)
  ctx.strokeStyle = '#0066ff';
  ctx.lineWidth = 20 / Math.max(scale, 0.1);
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.shadowColor = 'rgba(0, 102, 255, 0.6)';
  ctx.shadowBlur = 6 / Math.max(scale, 0.1);
  
  connections.forEach(conn => {{
    const p1 = points[conn[0]];
    const p2 = points[conn[1]];
    ctx.beginPath();
    ctx.moveTo(p1.x, p1.y);
    ctx.lineTo(p2.x, p2.y);
    ctx.stroke();
  }});
  
  // Reset shadow
  ctx.shadowColor = 'transparent';
  ctx.shadowBlur = 0;
  
  // Draw points
  points.forEach((point, index) => {{
    const isSelected = index === selectedPointIndex;
    const radius = (isSelected ? 12 : 8) / Math.max(scale, 0.1);
    
    ctx.fillStyle = isSelected ? '#ff4444' : '#44aa44';
    ctx.strokeStyle = '#000';
    ctx.lineWidth = 3 / Math.max(scale, 0.1);
    
    ctx.beginPath();
    ctx.arc(point.x, point.y, radius, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    
    // Draw point ID - much bigger
    ctx.fillStyle = '#fff';
    ctx.strokeStyle = '#000';
    ctx.lineWidth = 4 / Math.max(scale, 0.1);
    const fontSize = 32 / Math.max(scale, 0.1);
    ctx.font = `bold ${{fontSize}}px Arial`;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    const textX = point.x + 12 / Math.max(scale, 0.1);
    const textY = point.y;
    // Draw text with outline for better visibility
    ctx.strokeText(point.id.toString(), textX, textY);
    ctx.fillText(point.id.toString(), textX, textY);
  }});
}}

// Event listeners
window.addEventListener('resize', () => {{ resizeCanvas(); draw(); }});

document.getElementById('zoom-in').onclick = () => {{
  const rect = canvas.getBoundingClientRect();
  zoomAt(rect.width / 2, rect.height / 2, 1.25);
  draw();
}};

document.getElementById('zoom-out').onclick = () => {{
  const rect = canvas.getBoundingClientRect();
  zoomAt(rect.width / 2, rect.height / 2, 1 / 1.25);
  draw();
}};

document.getElementById('fit').onclick = () => {{ fitToScreen(); }};
document.getElementById('reset').onclick = () => {{ resetView(); }};
document.getElementById('save').onclick = () => {{ saveData(); }};
document.getElementById('clear').onclick = () => {{ clearAll(); }};

document.getElementById('file-input').addEventListener('change', (e) => {{
  const file = e.target.files[0];
  if (file) {{
    const reader = new FileReader();
    reader.onload = (event) => {{
      try {{
        const data = JSON.parse(event.target.result);
        loadData(data);
      }} catch (error) {{
        alert('Failed to load JSON: ' + error.message);
      }}
    }};
    reader.readAsText(file);
  }}
}});

let isPanMode = false; // Track if we're in pan mode (space key)
let rightClickStart = null; // Track right-click start position for panning

canvas.addEventListener('mousedown', (e) => {{
  if (!img.complete) return;
  
  const rect = canvas.getBoundingClientRect();
  const x = e.clientX - rect.left;
  const y = e.clientY - rect.top;
  const [ix, iy] = screenToImage(x, y);
  
  if (e.button === 0) {{ // Left click
    if (isPanMode || e.shiftKey) {{ // Pan mode or Shift+drag
      dragging = true;
      lx = e.clientX;
      ly = e.clientY;
      canvas.style.cursor = 'grabbing';
    }} else {{
      const nearest = findNearestPoint(ix, iy);
      
      if (nearest !== null) {{
        // Clicked on an existing point
        if (selectedPointIndex === null) {{
          // No point selected, select this one
          selectedPointIndex = nearest;
          updateStatus(`Selected point ${{points[nearest].id}} - Click another point to connect`);
        }} else if (selectedPointIndex === nearest) {{
          // Clicked same point - deselect it
          selectedPointIndex = null;
          updateStatus('Point deselected');
        }} else {{
          // Auto-connect to the selected point
          connectPoints(selectedPointIndex, nearest);
          // Keep the new point selected for continued connection
          selectedPointIndex = nearest;
          updateStatus(`Connected! Point ${{nearest}} selected - Click another point to continue`);
        }}
      }} else {{
        // Clicked on empty space - add new point
        addPoint(ix, iy);
        // If there was a selected point, it's already auto-connected in addPoint()
        // The new point is now selected for continued connection
      }}
      draw();
    }}
  }} else if (e.button === 1) {{ // Middle click for panning
    dragging = true;
    lx = e.clientX;
    ly = e.clientY;
    canvas.style.cursor = 'grabbing';
  }} else if (e.button === 2) {{ // Right click - start tracking for pan or delete
    rightClickStart = {{ x: e.clientX, y: e.clientY, time: Date.now() }};
    dragging = true;
    lx = e.clientX;
    ly = e.clientY;
    canvas.style.cursor = 'grabbing';
  }}
}});

canvas.addEventListener('mousemove', (e) => {{
  if (dragging) {{
    const dx = e.clientX - lx, dy = e.clientY - ly;
    tx += dx * dpr;
    ty += dy * dpr;
    lx = e.clientX;
    ly = e.clientY;
    draw();
  }} else if (img.complete) {{
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const [ix, iy] = screenToImage(x, y);
    const nearest = findNearestPoint(ix, iy);
    if (isPanMode) {{
      canvas.style.cursor = 'grabbing';
    }} else {{
      canvas.style.cursor = nearest !== null ? 'pointer' : 'crosshair';
    }}
  }}
}});

canvas.addEventListener('mouseup', (e) => {{
  if (dragging && rightClickStart) {{
    // Right-click: if moved significantly, it was panning; otherwise delete point
    const moved = Math.abs(e.clientX - rightClickStart.x) > 5 || Math.abs(e.clientY - rightClickStart.y) > 5;
    const timeDiff = Date.now() - rightClickStart.time;
    
    if (!moved && timeDiff < 200) {{ // Quick right-click without movement = delete
      const rect = canvas.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const [ix, iy] = screenToImage(x, y);
      const nearest = findNearestPoint(ix, iy);
      if (nearest !== null) {{
        deletePoint(nearest);
        draw();
      }}
    }}
    rightClickStart = null;
  }}
  
  if (dragging) {{
    dragging = false;
    if (!isPanMode) {{
      canvas.style.cursor = 'crosshair';
    }}
  }}
}});

canvas.addEventListener('wheel', (e) => {{
  e.preventDefault();
  const rect = canvas.getBoundingClientRect();
  const factor = Math.exp(-e.deltaY * ZOOM_SENS);
  zoomAt(e.clientX - rect.left, e.clientY - rect.top, factor);
  draw();
}}, {{ passive: false }});

canvas.addEventListener('contextmenu', (e) => {{
  e.preventDefault(); // Prevent browser context menu
  // Delete is handled in mouseup if it was a quick click without drag
}});

document.addEventListener('keydown', (e) => {{
  if (e.key === 's' || e.key === 'S') {{
    e.preventDefault();
    saveData();
  }} else if (e.key === 'c' || e.key === 'C') {{
    e.preventDefault();
    clearAll();
  }} else if (e.key === 'Escape') {{
    selectedPointIndex = null;
    isPanMode = false;
    updateStatus('Point deselected');
    draw();
  }} else if (e.key === ' ' || e.key === 'Spacebar') {{
    // Space key for pan mode
    e.preventDefault();
    isPanMode = true;
    canvas.style.cursor = 'grabbing';
    updateStatus('Pan mode - Drag to pan, release Space to exit');
  }} else if (e.key === 'ArrowLeft' || e.key === 'ArrowRight' || e.key === 'ArrowUp' || e.key === 'ArrowDown') {{
    // Arrow keys for navigation
    e.preventDefault();
    const panSpeed = 50 / scale; // Pan speed adjusted by zoom level
    if (e.key === 'ArrowLeft') {{
      tx += panSpeed * scale;
    }} else if (e.key === 'ArrowRight') {{
      tx -= panSpeed * scale;
    }} else if (e.key === 'ArrowUp') {{
      ty += panSpeed * scale;
    }} else if (e.key === 'ArrowDown') {{
      ty -= panSpeed * scale;
    }}
    draw();
  }}
}});

document.addEventListener('keyup', (e) => {{
  if (e.key === ' ' || e.key === 'Spacebar') {{
    isPanMode = false;
    canvas.style.cursor = 'crosshair';
    updateStatus('Ready - Click to add points');
  }}
}});

// Start
img.onload = () => {{
  resizeCanvas();
  fitToScreen();
  updateStats();
}};
</script>
</body>
</html>
"""
    
    with open(args.out, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"✅ Generated standalone HTML: {args.out}")
    print(f"   Image: {args.image}")
    print(f"   Output JSON: {args.output}")
    print(f"\nOpen {args.out} in your browser to start plotting cable trays!")

if __name__ == '__main__':
    main()

