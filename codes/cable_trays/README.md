# Cable Tray Takeoff Tool

Interactive web-based tool for manual cable tray takeoff from electrical plans. This tool allows you to plot backbone points on electrical drawings and automatically connect them to form cable trays, which are exported as a weighted graph format for shortest path calculations.

## Overview

This tool generates a standalone HTML file that embeds the electrical plan image and provides an interactive interface for plotting cable tray routes. The output is saved as a weighted graph in JSON format, perfect for pathfinding algorithms.

## Files

- **`generate_cable_tray_takeoff.py`** - Python script that generates a standalone HTML file with embedded image and all functionality
- **`server.py`** - Alternative web server approach (optional, not the primary method)
- **`web_takeoff.html`** - Alternative HTML template (deprecated in favor of standalone generated HTML)

## Installation

Make sure you have Python 3 installed. The tool uses standard library only - no external dependencies required.

## Usage

### Generate Standalone HTML (Recommended)

```bash
python3 generate_cable_tray_takeoff.py --image path/to/your/plan.jpg --out takeoff.html
```

Or with custom output filename:

```bash
python3 generate_cable_tray_takeoff.py --image plan.jpg --out takeoff.html --output my_trays.json
```

Then simply open the generated HTML file in your browser - no server needed!

## Features

- **Standalone HTML** - Everything embedded (image, JavaScript), just open in browser
- **Zoom & Pan** - Mouse wheel to zoom (0.05x to 20x), drag to pan, arrow keys for navigation
- **Touchpad-friendly** - Optimized zoom sensitivity for trackpads
- **Graph-based plotting** - Click to add backbone points, auto-connects when selecting nodes
- **Visual feedback** - Thick paths (20px), large point numbers (32px), color-coded selection
- **Selection system** - Select nodes (red) or edges (orange) for deletion
- **Undo/Redo** - Full history support (Command+Z / Command+Shift+Z or toolbar buttons)
- **Ideal diagonal paths** - Saves shortest paths between nodes
- **Smart indexing** - Reuses deleted node IDs (no gaps)

## Controls

### Mouse
- **Left-click + Drag**: Pan/move the image
- **Left-click (on node)**: Select node, auto-connects if another node is selected
- **Left-click (on edge)**: Select edge (orange highlight)
- **Left-click (empty space)**: Deselect all
- **Right-click (empty space)**: Add new node
- **Right-click (on node)**: Delete node immediately
- **Mouse wheel**: Zoom in/out at cursor position

### Keyboard
- **D**: Delete selected node or edge
- **S**: Save to JSON file (downloads automatically)
- **C**: Clear all points (with confirmation)
- **Command+Z / Ctrl+Z**: Undo last action
- **Command+Shift+Z / Ctrl+Shift+Z**: Redo
- **ESC**: Deselect current selection
- **Arrow keys**: Navigate/pan the image
- **Space**: Pan mode (hold and drag)

### Toolbar Buttons
- **Load JSON**: Load previously saved work
- **Zoom In/Out**: Zoom controls
- **Fit**: Fit image to screen
- **Reset**: Reset zoom and pan
- **Undo/Redo**: History navigation
- **Delete Selected**: Delete selected node/edge
- **Save**: Save cable tray data
- **Clear**: Clear all points

## Output Format

The tool saves data as a weighted graph in JSON format, perfect for shortest path calculations:

```json
{
  "nodes": {
    "node_id_0": { "x": 100, "y": 200 },
    "node_id_1": { "x": 150, "y": 200 },
    "node_id_2": { "x": 200, "y": 250 }
  },
  "edges": [
    { "from": "node_id_0", "to": "node_id_1", "weight": 50 },
    { "from": "node_id_1", "to": "node_id_2", "weight": 70.71 }
  ]
}
```

### Format Details

- **`nodes`**: Object with node IDs as keys (`node_id_0`, `node_id_1`, etc.), each containing `x` and `y` pixel coordinates
- **`edges`**: Array of edge objects with:
  - `from`: Source node ID
  - `to`: Target node ID
  - `weight`: Distance in pixels (Euclidean distance)

This format is compatible with graph algorithms like Dijkstra's, A*, and Bellman-Ford for shortest path calculations.

## Workflow

1. Generate HTML file with your electrical plan:
   ```bash
   python3 generate_cable_tray_takeoff.py --image plan.jpg --out takeoff.html
   ```

2. Open `takeoff.html` in your browser

3. Navigate the image:
   - Use mouse wheel to zoom in/out
   - Left-click + drag to pan
   - Use arrow keys for precise navigation

4. Add nodes:
   - Right-click on empty space to add a backbone point
   - Continue adding points along the cable tray route

5. Connect nodes:
   - Left-click on a node to select it (turns red)
   - Left-click on another node to automatically connect them
   - Repeat to create a chain of connected edges

6. Edit:
   - Left-click to select nodes or edges
   - Press **D** or click "Delete Selected" to remove
   - Use **Command+Z** to undo mistakes

7. Save:
   - Press **S** or click "Save" button
   - JSON file downloads automatically

## Visual Feedback

- **Selected nodes**: Red color, larger size (12px radius)
- **Selected edges**: Orange color (#ff6600), thicker (25px width)
- **Normal nodes**: Green color, standard size (8px radius)
- **Normal edges**: Blue color (#0066ff), standard width (20px)
- **Point labels**: Large white text (32px) with black outline for visibility

## Tips

- **Zoom in** for precise point placement
- **Select nodes** to create connections - clicking automatically connects to previously selected node
- **Use undo** (Command+Z) if you accidentally delete something
- **Save frequently** - the tool downloads JSON files, so you can save multiple versions
- **Load JSON** to continue work - you can load previously saved files to continue editing

## Use Cases

- Manual cable tray takeoff from electrical plans
- Creating graph representations of cable routes
- Preparing data for shortest path algorithms
- Converting 2D electrical drawings to graph data structures

## Technical Details

- Image is embedded as base64 data URI (fully self-contained)
- All JavaScript is embedded in the HTML file
- Coordinates are in image pixel space
- Edge weights are calculated as Euclidean distance in pixels
- History system supports up to 50 undo/redo states
- Node IDs are automatically reused when nodes are deleted

## Notes

- The generated HTML file is completely self-contained - no server needed
- All coordinates are in image pixel coordinates
- Edge weights are in pixels (distance between nodes)
- The format is optimized for graph algorithms and shortest path calculations
- You can load/save JSON files to continue work across sessions
