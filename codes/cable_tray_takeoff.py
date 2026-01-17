#!/usr/bin/env python3
"""
Interactive Cable Tray Takeoff Tool

This tool allows you to manually plot cable tray points on a 2D electrical plan.
- Left-click to add points (backbone points)
- Points are automatically connected to form cable trays
- Right-click on a point to delete it
- Press 's' to save to output.json
- Press 'c' to clear all points
- Press 'q' to quit

Usage:
    python3 cable_tray_takeoff.py --image path/to/plan.jpg [--output output.json]
"""

import argparse
import json
import os
from typing import List, Dict, Tuple, Optional
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch
import numpy as np
from collections import defaultdict

class CableTrayTakeoff:
    def __init__(self, image_path: str, output_path: str = "output.json"):
        self.image_path = image_path
        self.output_path = output_path
        self.points: List[Tuple[float, float]] = []
        self.point_ids: List[int] = []
        self.connections: List[Tuple[int, int]] = []  # (point_idx1, point_idx2)
        self.cable_trays: List[Dict] = []
        self.next_point_id = 0
        self.selected_point: Optional[int] = None
        
        # Load existing data if output file exists
        self.load_existing_data()
        
        # Setup matplotlib
        self.fig, self.ax = plt.subplots(figsize=(16, 12))
        self.img = plt.imread(image_path)
        self.ax.imshow(self.img, extent=[0, self.img.shape[1], self.img.shape[0], 0])
        self.ax.set_title("Cable Tray Takeoff Tool - Left-click to add points, Right-click to delete, 's' to save, 'q' to quit", 
                         fontsize=10)
        
        # Connect events
        self.fig.canvas.mpl_connect('button_press_event', self.on_click)
        self.fig.canvas.mpl_connect('key_press_event', self.on_key)
        self.fig.canvas.mpl_connect('motion_notify_event', self.on_motion)
        
        self.redraw()
        
    def load_existing_data(self):
        """Load existing cable tray data from output.json if it exists"""
        if os.path.exists(self.output_path):
            try:
                with open(self.output_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict) and 'cable_trays' in data:
                        self.cable_trays = data.get('cable_trays', [])
                        # Reconstruct points and connections from cable trays
                        point_map = {}  # (x, y) -> point_id
                        for tray in self.cable_trays:
                            start = tuple(tray['start_point'])
                            end = tuple(tray['end_point'])
                            
                            if start not in point_map:
                                point_map[start] = len(self.points)
                                self.points.append(start)
                                self.point_ids.append(self.next_point_id)
                                self.next_point_id += 1
                            if end not in point_map:
                                point_map[end] = len(self.points)
                                self.points.append(end)
                                self.point_ids.append(self.next_point_id)
                                self.next_point_id += 1
                            
                            start_idx = point_map[start]
                            end_idx = point_map[end]
                            if (start_idx, end_idx) not in self.connections and (end_idx, start_idx) not in self.connections:
                                self.connections.append((start_idx, end_idx))
                    elif isinstance(data, list):
                        # Handle list format
                        self.cable_trays = data
                        # Reconstruct points similarly
                        point_map = {}
                        for tray in self.cable_trays:
                            start = tuple(tray['start_point'])
                            end = tuple(tray['end_point'])
                            
                            if start not in point_map:
                                point_map[start] = len(self.points)
                                self.points.append(start)
                                self.point_ids.append(self.next_point_id)
                                self.next_point_id += 1
                            if end not in point_map:
                                point_map[end] = len(self.points)
                                self.points.append(end)
                                self.point_ids.append(self.next_point_id)
                                self.next_point_id += 1
                            
                            start_idx = point_map[start]
                            end_idx = point_map[end]
                            if (start_idx, end_idx) not in self.connections and (end_idx, start_idx) not in self.connections:
                                self.connections.append((start_idx, end_idx))
                print(f"Loaded {len(self.cable_trays)} existing cable trays from {self.output_path}")
            except Exception as e:
                print(f"Warning: Could not load existing data: {e}")
    
    def find_nearest_point(self, x: float, y: float, threshold: float = 20.0) -> Optional[int]:
        """Find the nearest point to the given coordinates"""
        if not self.points:
            return None
        
        distances = [np.sqrt((px - x)**2 + (py - y)**2) for px, py in self.points]
        min_idx = np.argmin(distances)
        if distances[min_idx] < threshold:
            return min_idx
        return None
    
    def on_click(self, event):
        """Handle mouse clicks"""
        if event.inaxes != self.ax:
            return
        
        x, y = event.xdata, event.ydata
        if x is None or y is None:
            return
        
        if event.button == 1:  # Left click - add point or connect
            nearest = self.find_nearest_point(x, y, threshold=30.0)
            
            if nearest is not None:
                # Clicked near existing point - connect mode
                if self.selected_point is None:
                    # Select this point for connection
                    self.selected_point = nearest
                    print(f"Selected point {self.point_ids[nearest]} at ({self.points[nearest][0]:.1f}, {self.points[nearest][1]:.1f})")
                    print("  Click another point to connect, or click empty space to add new point")
                else:
                    # Connect selected point to this point
                    if self.selected_point != nearest:
                        conn = (min(self.selected_point, nearest), max(self.selected_point, nearest))
                        if conn not in self.connections:
                            self.connections.append(conn)
                            print(f"Connected point {self.point_ids[self.selected_point]} to point {self.point_ids[nearest]}")
                        else:
                            print(f"Connection already exists")
                        self.selected_point = None
                    else:
                        # Clicked same point - deselect
                        self.selected_point = None
                        print("Deselected point")
            else:
                # Clicked empty space - add new point
                self.points.append((x, y))
                self.point_ids.append(self.next_point_id)
                new_idx = len(self.points) - 1
                print(f"Added point {self.next_point_id} at ({x:.1f}, {y:.1f})")
                
                # If we have a selected point, automatically connect it to the new point
                if self.selected_point is not None:
                    conn = (min(self.selected_point, new_idx), max(self.selected_point, new_idx))
                    if conn not in self.connections:
                        self.connections.append(conn)
                        print(f"  Auto-connected to point {self.point_ids[self.selected_point]}")
                    self.selected_point = None
                else:
                    # Select the new point for potential connection
                    self.selected_point = new_idx
                
                self.next_point_id += 1
            
            self.update_cable_trays()
            self.redraw()
            
        elif event.button == 3:  # Right click - delete point
            nearest = self.find_nearest_point(x, y, threshold=30.0)
            if nearest is not None:
                # Remove point and all its connections
                self.points.pop(nearest)
                self.point_ids.pop(nearest)
                # Update connections
                self.connections = [
                    (i1 if i1 < nearest else i1 - 1, i2 if i2 < nearest else i2 - 1)
                    for i1, i2 in self.connections
                    if i1 != nearest and i2 != nearest
                ]
                if self.selected_point == nearest:
                    self.selected_point = None
                elif self.selected_point is not None and self.selected_point > nearest:
                    self.selected_point -= 1
                print(f"Deleted point {nearest}")
                self.update_cable_trays()
                self.redraw()
    
    def on_motion(self, event):
        """Handle mouse motion for highlighting"""
        if event.inaxes != self.ax:
            return
        
        x, y = event.xdata, event.ydata
        if x is None or y is None:
            return
        
        nearest = self.find_nearest_point(x, y, threshold=30.0)
        if nearest is not None:
            self.fig.canvas.set_cursor(1)  # Hand cursor
        else:
            self.fig.canvas.set_cursor(0)  # Arrow cursor
    
    def on_key(self, event):
        """Handle keyboard events"""
        if event.key == 's' or event.key == 'S':
            self.save_data()
        elif event.key == 'c' or event.key == 'C':
            self.clear_all()
        elif event.key == 'q' or event.key == 'Q':
            plt.close(self.fig)
        elif event.key == 'escape':
            self.selected_point = None
            self.redraw()
    
    def update_cable_trays(self):
        """Update cable_trays list from points and connections"""
        self.cable_trays = []
        for i1, i2 in self.connections:
            if i1 < len(self.points) and i2 < len(self.points):
                tray = {
                    "id": f"CT_{self.point_ids[i1]}_{self.point_ids[i2]}",
                    "start_point": list(self.points[i1]),
                    "end_point": list(self.points[i2]),
                    "length": np.sqrt(
                        (self.points[i1][0] - self.points[i2][0])**2 + 
                        (self.points[i1][1] - self.points[i2][1])**2
                    ),
                    "point_ids": [self.point_ids[i1], self.point_ids[i2]],
                    "metadata": {
                        "created_by": "manual_takeoff",
                        "image_path": self.image_path
                    }
                }
                self.cable_trays.append(tray)
    
    def redraw(self):
        """Redraw the plot with all points and connections"""
        self.ax.clear()
        self.ax.imshow(self.img, extent=[0, self.img.shape[1], self.img.shape[0], 0])
        self.ax.set_title("Cable Tray Takeoff Tool - Left-click to add points, Right-click to delete, 's' to save, 'q' to quit", 
                         fontsize=10)
        
        # Draw connections (cable trays)
        for i1, i2 in self.connections:
            if i1 < len(self.points) and i2 < len(self.points):
                p1 = self.points[i1]
                p2 = self.points[i2]
                self.ax.plot([p1[0], p2[0]], [p1[1], p2[1]], 'b-', linewidth=2, alpha=0.7, zorder=1)
        
        # Draw points
        for i, (x, y) in enumerate(self.points):
            color = 'red' if i == self.selected_point else 'green'
            size = 100 if i == self.selected_point else 80
            self.ax.scatter(x, y, c=color, s=size, zorder=2, edgecolors='black', linewidths=1.5)
            # Add point ID label
            self.ax.annotate(str(self.point_ids[i]), (x, y), 
                           xytext=(5, 5), textcoords='offset points',
                           fontsize=8, color='white', weight='bold',
                           bbox=dict(boxstyle='round,pad=0.3', facecolor='black', alpha=0.7))
        
        self.fig.canvas.draw()
    
    def clear_all(self):
        """Clear all points and connections"""
        response = input("Clear all points and connections? (yes/no): ")
        if response.lower() in ['yes', 'y']:
            self.points = []
            self.point_ids = []
            self.connections = []
            self.cable_trays = []
            self.selected_point = None
            self.next_point_id = 0
            self.redraw()
            print("Cleared all points and connections")
    
    def save_data(self):
        """Save cable tray data to output.json"""
        self.update_cable_trays()
        
        output_data = {
            "meta": {
                "image_path": self.image_path,
                "total_points": len(self.points),
                "total_connections": len(self.connections),
                "total_cable_trays": len(self.cable_trays),
                "tool": "cable_tray_takeoff"
            },
            "points": [
                {
                    "id": pid,
                    "position": list(pos),
                    "connections": [
                        self.point_ids[j] for j in range(len(self.points))
                        if (i, j) in self.connections or (j, i) in self.connections
                    ]
                }
                for i, (pos, pid) in enumerate(zip(self.points, self.point_ids))
            ],
            "cable_trays": self.cable_trays
        }
        
        with open(self.output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ Saved {len(self.cable_trays)} cable trays to {self.output_path}")
        print(f"   Total points: {len(self.points)}")
        print(f"   Total connections: {len(self.connections)}")
    
    def show(self):
        """Show the interactive plot"""
        plt.tight_layout()
        plt.show()


def main():
    parser = argparse.ArgumentParser(
        description="Interactive Cable Tray Takeoff Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 cable_tray_takeoff.py --image plan.jpg
  python3 cable_tray_takeoff.py --image plan.jpg --output my_trays.json

Controls:
  - Left-click: Add a new point or connect to existing point
  - Right-click: Delete nearest point
  - 's': Save to output file
  - 'c': Clear all points
  - 'q': Quit
  - ESC: Deselect current point
        """
    )
    parser.add_argument('--image', required=True, help='Path to the electrical plan image')
    parser.add_argument('--output', default='output.json', help='Output JSON file path (default: output.json)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.image):
        print(f"Error: Image file not found: {args.image}")
        return
    
    print(f"Loading image: {args.image}")
    print(f"Output will be saved to: {args.output}")
    print("\nControls:")
    print("  - Left-click: Add a new point or connect to existing point")
    print("  - Right-click: Delete nearest point")
    print("  - 's': Save to output file")
    print("  - 'c': Clear all points")
    print("  - 'q': Quit")
    print("  - ESC: Deselect current point")
    print("\nStarting interactive tool...\n")
    
    tool = CableTrayTakeoff(args.image, args.output)
    tool.show()


if __name__ == '__main__':
    main()

