#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import argparse
from collections import defaultdict

def group_by_group_id(in_path: str, out_path: str = None):
    # Load JSON file
    with open(in_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Prepare grouping dict
    grouped = defaultdict(list)

    elems = []
    for element_id, element_data in data.items():
        gid = element_data.get('group_id')
        if not gid:
            gid = "__NO_GROUP_ID__"  # mark missing ones
        grouped[gid].append({
            "id": element_id,
            **element_data
        })
        if gid not in elems:
            elems.append(gid)

    # Sort dictionary by group_id name for readability
    grouped_sorted = dict(sorted(grouped.items(), key=lambda x: x[0]))

    # Optionally save output to file
    if out_path:
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(grouped_sorted, f, ensure_ascii=False, indent=2)
        print(f"✅ Grouped output saved to: {out_path}")
    else:
        # Just print summary
        print(f"✅ Found {len(grouped_sorted)} unique group_id values")
        for gid, items in grouped_sorted.items():
            print(f"{gid}: {len(items)} elements")
    print(elems)

    return grouped_sorted

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Group elements in JSON by their group_id.")
    parser.add_argument("--json", required=True, help="Path to input JSON file")
    parser.add_argument("--out", required=False, help="Optional path to output grouped JSON file")
    args = parser.parse_args()

    group_by_group_id(args.json, args.out)
