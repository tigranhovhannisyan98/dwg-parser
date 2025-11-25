import json

in_path = "slim_sorted.json"
out_path = "slim_sorted_by_first_part.json"

def extract_first_part(name):
    # Handle list
    if isinstance(name, list):
        name = name[0] if name else ""
    if not isinstance(name, str):
        name = str(name) if name else ""
    # Split by underscore and take the first segment
    return name.split("_")[0].strip() if name else ""

with open(in_path, "r", encoding="utf-8") as f:
    data = json.load(f)

# Convert dict to list to ensure stable sorting
rows = []
for _id, rec in data.items():
    name = rec.get("name")
    first_part = extract_first_part(name)
    rows.append({
        "id": _id,
        "name": name if not isinstance(name, list) else (name[0] if name else ""),
        "first_part": first_part,
        "layer": rec.get("layer"),
        "txt": rec.get("txt")
    })

# Sort by first part (case-insensitive), then full name, then ID
rows.sort(key=lambda r: (r["first_part"].lower(), r["name"].lower(), r["id"]))

# If you want to convert back to dict with IDs as keys:
sorted_dict = {r["id"]: {"name": r["name"], "layer": r["layer"], "txt": r["txt"]} for r in rows}

with open(out_path, "w", encoding="utf-8") as f:
    json.dump(sorted_dict, f, ensure_ascii=False, indent=2)

print(f"✅ Sorted by first part of name — saved to {out_path}")
