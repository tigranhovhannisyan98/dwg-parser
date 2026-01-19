#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
spatial_filtering.py

Performs spatial pruning to link SLD Elements (from final_result.json) with
Plan Elements (from extracted_elements_samson.json) based on geometrical coordinates.

The script:
1. Parses location descriptions from SLD Elements (destination field)
2. Converts axis strings to pixel coordinates using LAYOUTS_X and LAYOUTS_Y
3. Creates bounding boxes from the coordinates
4. Filters Plan Elements that fall within those boxes
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set

# Hardcoded coordinate mappings (keys are strings)
LAYOUTS_X = {
    "F": 460, "F1": 590, "G": 1236, "G1": 1886, "G2": 2537, "G3": 3188,
    "G4": 3843, "G5": 4491, "G6": 5136, "G7": 5790, "H": 6440, "H1": 7088,
    "H2": 7739, "H3": 8390, "I": 9044, "I1": 9690, "I2": 10340, "I3": 10990,
    "I4": 11644, "I5": 12300
}

LAYOUTS_Y = {
    "45": 500, "44": 1070, "43": 1730, "42": 2375, "41": 3025, "40": 3680,
    "39": 4330, "38": 4978, "37": 5620, "36": 6280, "35": 6930, "34": 7580,
    "33": 8230, "32": 8880, "31": 9530
}

# Threshold/padding for single-axis expansion (in pixels)
# This creates a buffer zone around single-axis cases to include nearby elements
# Set to approximately the average distance between axes to capture elements in between
SINGLE_AXIS_THRESHOLD_X = 650  # pixels (average X-axis distance is ~623px)
SINGLE_AXIS_THRESHOLD_Y = 650  # pixels (average Y-axis distance is ~645px)


def parse_axis_string(axis_str: str) -> List[Tuple[Tuple[str, str], Tuple[str, str]]]:
    """
    Parse an axis string to extract Y and X ranges.
    
    Examples:
        "Achse 38-44/F1-G1" -> [((38, 44), (F1, G1))]
        "Achse 39/F-F1" -> [((39, 39), (F, F1))]
        "Achse 38-39/G1" -> [((38, 39), (G1, G1))]
        "Achse 44/F1-G Ebene 0 Achse 44/G3-G6 Ebene 1" -> [((44, 44), (F1, G)), ((44, 44), (G3, G6))]
        "Achse 43-44/F1-G, 43-44/G4-G5" -> [((43, 44), (F1, G)), ((43, 44), (G4, G5))]
    
    Returns:
        List of tuples: [((y_min, y_max), (x_min, x_max)), ...]
        Each tuple contains (Y_range, X_range) where ranges are (min_label, max_label)
    """
    results = []
    
    # First, find all "Achse Y_RANGE/X_RANGE" patterns
    # Pattern to match "Achse Y_RANGE/X_RANGE"
    # Y_RANGE can be: single number (38) or range (38-44)
    # X_RANGE can be: single label (F1) or range (F1-G1)
    achse_pattern = r'Achse\s+(\d+)(?:-(\d+))?/([A-Z]\d*)(?:-([A-Z]\d*))?'
    
    # Find all "Achse" matches
    achse_matches = list(re.finditer(achse_pattern, axis_str))
    
    for i, match in enumerate(achse_matches):
        y_start = match.group(1)
        y_end = match.group(2) if match.group(2) else y_start
        x_start = match.group(3)
        x_end = match.group(4) if match.group(4) else x_start
        
        results.append(((y_start, y_end), (x_start, x_end)))
        
        # Check for comma-separated axis definitions after this match
        # Look for patterns like ", Y_RANGE/X_RANGE" (without "Achse" prefix)
        match_end = match.end()
        if i < len(achse_matches) - 1:
            next_match_start = achse_matches[i + 1].start()
            text_between = axis_str[match_end:next_match_start]
        else:
            text_between = axis_str[match_end:]
        
        # Pattern for comma-separated axis: ", Y_RANGE/X_RANGE"
        comma_pattern = r',\s+(\d+)(?:-(\d+))?/([A-Z]\d*)(?:-([A-Z]\d*))?'
        comma_matches = re.finditer(comma_pattern, text_between)
        
        for comma_match in comma_matches:
            y_start_c = comma_match.group(1)
            y_end_c = comma_match.group(2) if comma_match.group(2) else y_start_c
            x_start_c = comma_match.group(3)
            x_end_c = comma_match.group(4) if comma_match.group(4) else x_start_c
            
            results.append(((y_start_c, y_end_c), (x_start_c, x_end_c)))
    
    return results


def get_adjacent_axis(axis_label: str, axis_dict: Dict[str, float], direction: str = "next") -> Optional[str]:
    """
    Get the adjacent axis label in the given direction.
    
    Args:
        axis_label: Current axis label
        axis_dict: Dictionary mapping labels to coordinates
        direction: "next" or "prev"
    
    Returns:
        Adjacent axis label or None
    """
    if axis_label not in axis_dict:
        return None
    
    # Sort axes by coordinate value
    sorted_axes = sorted(axis_dict.items(), key=lambda x: x[1])
    labels = [label for label, _ in sorted_axes]
    
    try:
        idx = labels.index(axis_label)
        if direction == "next" and idx < len(labels) - 1:
            return labels[idx + 1]
        elif direction == "prev" and idx > 0:
            return labels[idx - 1]
    except ValueError:
        return None
    
    return None


def axis_to_coordinates(y_range: Tuple[str, str], x_range: Tuple[str, str]) -> Optional[Tuple[float, float, float, float]]:
    """
    Convert axis labels to pixel coordinates (bounding box).
    Adds padding to all bounding boxes to include surrounding elements.
    Single-axis cases get extra expansion using threshold.
    
    Args:
        y_range: Tuple of (y_min_label, y_max_label) as strings
        x_range: Tuple of (x_min_label, x_max_label) as strings
    
    Returns:
        Tuple (x_min, y_min, x_max, y_max) in pixel coordinates, or None if invalid
    """
    y_min_label, y_max_label = y_range
    x_min_label, x_max_label = x_range
    
    # Get base coordinates first
    if y_min_label not in LAYOUTS_Y or y_max_label not in LAYOUTS_Y:
        return None
    if x_min_label not in LAYOUTS_X or x_max_label not in LAYOUTS_X:
        return None
    
    y_min_coord = LAYOUTS_Y[y_min_label]
    y_max_coord = LAYOUTS_Y[y_max_label]
    x_min_coord = LAYOUTS_X[x_min_label]
    x_max_coord = LAYOUTS_X[x_max_label]
    
    # Handle single Y axis - expand using threshold
    if y_min_label == y_max_label:
        # Single Y axis - expand by threshold in both directions
        y_center = y_min_coord
        y_min_coord = y_center - SINGLE_AXIS_THRESHOLD_Y
        y_max_coord = y_center + SINGLE_AXIS_THRESHOLD_Y
        
        # Also try to expand to next/prev axis if available for better coverage
        next_y = get_adjacent_axis(y_min_label, LAYOUTS_Y, "next")
        prev_y = get_adjacent_axis(y_min_label, LAYOUTS_Y, "prev")
        
        if next_y:
            next_y_coord = LAYOUTS_Y[next_y]
            # Use the larger of threshold expansion or next axis
            y_max_coord = max(y_max_coord, next_y_coord)
        
        if prev_y:
            prev_y_coord = LAYOUTS_Y[prev_y]
            # Use the smaller of threshold expansion or prev axis
            y_min_coord = min(y_min_coord, prev_y_coord)
    else:
        # Range Y axis - ensure correct order
        if y_min_coord > y_max_coord:
            y_min_coord, y_max_coord = y_max_coord, y_min_coord
    
    # Handle single X axis - expand using threshold
    if x_min_label == x_max_label:
        # Single X axis - expand by threshold in both directions
        x_center = x_min_coord
        x_min_coord = x_center - SINGLE_AXIS_THRESHOLD_X
        x_max_coord = x_center + SINGLE_AXIS_THRESHOLD_X
        
        # Also try to expand to next/prev axis if available for better coverage
        next_x = get_adjacent_axis(x_min_label, LAYOUTS_X, "next")
        prev_x = get_adjacent_axis(x_min_label, LAYOUTS_X, "prev")
        
        if next_x:
            next_x_coord = LAYOUTS_X[next_x]
            # Use the larger of threshold expansion or next axis
            x_max_coord = max(x_max_coord, next_x_coord)
        
        if prev_x:
            prev_x_coord = LAYOUTS_X[prev_x]
            # Use the smaller of threshold expansion or prev axis
            x_min_coord = min(x_min_coord, prev_x_coord)
    else:
        # Range X axis - ensure correct order
        if x_min_coord > x_max_coord:
            x_min_coord, x_max_coord = x_max_coord, x_min_coord
    
    # Add padding to ALL bounding boxes (both single-axis and range cases)
    # This ensures we capture surrounding elements
    padding_x = SINGLE_AXIS_THRESHOLD_X // 2  # Half threshold for padding
    padding_y = SINGLE_AXIS_THRESHOLD_Y // 2  # Half threshold for padding
    
    x_min_coord -= padding_x
    x_max_coord += padding_x
    y_min_coord -= padding_y
    y_max_coord += padding_y
    
    return (x_min_coord, y_min_coord, x_max_coord, y_max_coord)


def point_in_bbox(point: Tuple[float, float], bbox: Tuple[float, float, float, float]) -> bool:
    """
    Check if a point (x, y) falls within a bounding box.
    
    Args:
        point: Tuple (x, y)
        bbox: Tuple (x_min, y_min, x_max, y_max)
    
    Returns:
        True if point is inside bbox (inclusive boundaries)
    """
    x, y = point
    x_min, y_min, x_max, y_max = bbox
    
    return x_min <= x <= x_max and y_min <= y <= y_max


def parse_destination_to_bboxes(destination: str) -> List[Tuple[float, float, float, float]]:
    """
    Parse a destination string and return all bounding boxes.
    
    Args:
        destination: String like "Lichtschiene 51-0.12 Achse 38-44/F1-G1"
    
    Returns:
        List of bounding boxes: [(x_min, y_min, x_max, y_max), ...]
    """
    bboxes = []
    axis_ranges = parse_axis_string(destination)
    
    for y_range, x_range in axis_ranges:
        bbox = axis_to_coordinates(y_range, x_range)
        if bbox:
            bboxes.append(bbox)
    
    return bboxes


def filter_plan_elements(
    sld_elements: List[Dict],
    plan_elements: Dict[str, Dict],
    output_path: Optional[Path] = None
) -> Dict[str, List[Dict]]:
    """
    Filter plan elements based on spatial matching with SLD elements.
    
    Only processes SLD elements with connection_type == "LOAD".
    
    Args:
        sld_elements: List of SLD element dicts (from final_result.json)
        plan_elements: Dict of plan elements keyed by ID (from extracted_elements_samson.json)
        output_path: Optional path to save results JSON
    
    Returns:
        Dict mapping SLD element IDs to lists of matching plan element IDs
    """
    results = {}
    
    for idx, sld_elem in enumerate(sld_elements):
        # Only process LOAD elements
        connection_type = sld_elem.get("connection_type", "")
        if connection_type != "LOAD":
            continue
        
        # Use circuit as primary ID, fallback to breaker+circuit, then index
        sld_id = sld_elem.get("circuit") or sld_elem.get("id")
        if not sld_id:
            breaker = sld_elem.get("breaker", "")
            circuit = sld_elem.get("circuit", "")
            sld_id = f"{breaker}_{circuit}" if breaker or circuit else f"element_{idx}"
        destination = sld_elem.get("destination", "")
        
        # Skip "Reserve" destinations
        if destination.strip() == "Reserve":
            continue
        
        if not destination or "Achse" not in destination:
            # No spatial information, but still record it
            results[sld_id] = {
                "sld_element": sld_elem,
                "destination": destination,
                "bboxes": [],
                "matching_plan_elements": [],
                "match_count": 0
            }
            continue
        
        # Parse destination to get bounding boxes
        bboxes = parse_destination_to_bboxes(destination)
        
        if not bboxes:
            # Could not parse bounding boxes, but still record it
            results[sld_id] = {
                "sld_element": sld_elem,
                "destination": destination,
                "bboxes": [],
                "matching_plan_elements": [],
                "match_count": 0
            }
            continue
        
        # Find plan elements that fall within any of the bounding boxes
        matching_plan_ids = []
        
        for plan_id, plan_elem in plan_elements.items():
            pos_img = plan_elem.get("pos_img")
            if not pos_img or len(pos_img) < 2:
                continue
            
            x, y = float(pos_img[0]), float(pos_img[1])
            
            # Check if point falls within any bounding box
            for bbox in bboxes:
                if point_in_bbox((x, y), bbox):
                    matching_plan_ids.append({
                        "id": plan_id,
                        "pos_img": pos_img,
                        "txt": plan_elem.get("txt", ""),
                        "name": plan_elem.get("name", ""),
                        "group_id": plan_elem.get("group_id", ""),
                        "layer": plan_elem.get("layer", "")
                    })
                    break  # Found in one box, no need to check others
        
        results[sld_id] = {
            "sld_element": sld_elem,
            "destination": destination,
            "bboxes": bboxes,
            "matching_plan_elements": matching_plan_ids,
            "match_count": len(matching_plan_ids)
        }
    
    # Save results if output path provided
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"Results saved to: {output_path}")
    
    return results


def main():
    """Main function to run spatial filtering."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Perform spatial filtering to link SLD and Plan elements"
    )
    parser.add_argument(
        "--sld-file",
        type=str,
        default="../parser_single_line/final_result.json",
        help="Path to SLD elements JSON file (default: ../parser_single_line/final_result.json)"
    )
    parser.add_argument(
        "--plan-file",
        type=str,
        default="../extracted_elements_samson.json",
        help="Path to Plan elements JSON file (default: ../extracted_elements_samson.json)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="spatial_matches.json",
        help="Path to output JSON file (default: spatial_matches.json)"
    )
    
    args = parser.parse_args()
    
    # Resolve paths relative to current working directory (where script is run from)
    cwd = Path.cwd()
    sld_path = (cwd / args.sld_file).resolve()
    plan_path = (cwd / args.plan_file).resolve()
    output_path = (cwd / args.output).resolve()
    
    # Check if files exist
    if not sld_path.exists():
        print(f"Error: SLD file not found: {sld_path}", file=sys.stderr)
        print(f"Current working directory: {cwd}", file=sys.stderr)
        print(f"Resolved path from: {args.sld_file}", file=sys.stderr)
        sys.exit(1)
    
    if not plan_path.exists():
        print(f"Error: Plan file not found: {plan_path}", file=sys.stderr)
        print(f"Current working directory: {cwd}", file=sys.stderr)
        print(f"Resolved path from: {args.plan_file}", file=sys.stderr)
        sys.exit(1)
    
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Load SLD elements
    print(f"Loading SLD elements from: {sld_path}")
    with open(sld_path, "r", encoding="utf-8") as f:
        sld_elements = json.load(f)
    print(f"Loaded {len(sld_elements)} SLD elements")
    
    # Count LOAD elements
    load_elements = [e for e in sld_elements if e.get("connection_type") == "LOAD"]
    print(f"Found {len(load_elements)} LOAD elements (will process only these)")
    
    # Load Plan elements
    print(f"Loading Plan elements from: {plan_path}")
    with open(plan_path, "r", encoding="utf-8") as f:
        plan_elements = json.load(f)
    print(f"Loaded {len(plan_elements)} Plan elements")
    
    # Perform spatial filtering
    print("\nPerforming spatial filtering (LOAD elements only)...")
    results = filter_plan_elements(sld_elements, plan_elements, output_path)
    
    # Print summary statistics
    total_matches = sum(r["match_count"] for r in results.values())
    elements_with_matches = sum(1 for r in results.values() if r["match_count"] > 0)
    elements_with_bboxes = sum(1 for r in results.values() if r.get("bboxes"))
    
    print(f"\n=== Summary ===")
    print(f"SLD LOAD elements processed: {len(results)}")
    print(f"SLD LOAD elements with valid bounding boxes: {elements_with_bboxes}")
    print(f"SLD LOAD elements with matches: {elements_with_matches}")
    print(f"Total plan elements matched: {total_matches}")
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
