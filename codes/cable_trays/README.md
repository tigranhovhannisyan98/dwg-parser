# Cable Tray Takeoff Tool

Interactive web-based tool for manual cable tray takeoff from electrical plans.

## Features

- **Web-based interface** - More accurate than desktop tools
- **Zoom and Pan** - Mouse wheel to zoom, drag to pan
- **Graph-based plotting** - Click to add backbone points, connect them to form cable trays
- **Ideal diagonal paths** - Automatically saves shortest paths between points
- **Persistent storage** - Saves to JSON file with all metadata

## Installation

Make sure you have Python 3 installed. The tool uses only standard library (no external dependencies for the server).

## Usage

### Start the Server

```bash
python3 server.py --image path/to/your/plan.jpg --output output.json
```

Then open your browser to: `http://localhost:8000`

### Alternative: Load Image via Web Interface

```bash
python3 server.py --output output.json
```

Then use the "Load Image" button in the web interface to select your image file.

## Controls

### Mouse
- **Left-click on empty space**: Add a new point
- **Left-click on existing point**: Select it (turns red), then click another point to connect
- **Right-click on point**: Delete the point and all its connections
- **Mouse wheel**: Zoom in/out
- **Ctrl + Drag** or **Middle-click + Drag**: Pan the canvas

### Keyboard
- **S**: Save to output.json
- **C**: Clear all points (with confirmation)
- **ESC**: Deselect current point

### Toolbar Buttons
- **Load Image**: Select an image file from your computer
- **Zoom In/Out**: Zoom controls
- **Reset Zoom**: Fit image to window
- **Save**: Save cable tray data
- **Clear**: Clear all points
- **Load JSON**: Load previously saved data

## Output Format

The tool saves to `output.json` with the following structure:

```json
{
  "meta": {
    "image_path": "path/to/image.jpg",
    "total_points": 10,
    "total_connections": 8,
    "total_cable_trays": 8,
    "tool": "web_cable_tray_takeoff"
  },
  "points": [
    {
      "id": 0,
      "position": [100.5, 200.3],
      "connections": [1, 2]
    }
  ],
  "cable_trays": [
    {
      "id": "CT_0_1",
      "start_point": [100.5, 200.3],
      "end_point": [150.2, 250.1],
      "length": 70.7,
      "point_ids": [0, 1],
      "path": [
        {"x": 100.5, "y": 200.3},
        {"x": 150.2, "y": 250.1}
      ],
      "metadata": {
        "created_by": "web_takeoff",
        "image_path": "local"
      }
    }
  ]
}
```

## Workflow

1. Start the server with your image
2. Open browser to `http://localhost:8000`
3. Click to add backbone points along cable tray routes
4. Click on points to connect them (forming cable trays)
5. Use zoom to get precise placement
6. Press 'S' or click "Save" to save to output.json
7. The data is automatically saved and can be loaded later

## Notes

- Points are saved with ideal diagonal paths (shortest distance)
- All coordinates are in image pixel coordinates
- The tool automatically loads previous work from localStorage
- You can load/save JSON files to continue work across sessions

