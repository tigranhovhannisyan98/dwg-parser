import json
from collections import Counter, defaultdict
from pathlib import Path


def load_elements(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def analyze_by_group_id(elements: dict):
    """
    elements: dict like {element_id: { ..., "group_id": "RJ45-1-phase", ...}, ...}
    """
    group_counts = Counter()

    for elem in elements.values():
        group_id = elem.get("group_id", "<NO_GROUP_ID>")
        group_counts[group_id] += 1

    return group_counts


def save_summary_to_file(group_counts: Counter, output_path: Path):
    """
    Writes lines like:
    group_id = RJ45-1-phase  count = 124
    sorted by count (descending), then group_id.
    """
    items = sorted(group_counts.items(), key=lambda kv: (-kv[1], str(kv[0])))

    with output_path.open("w", encoding="utf-8") as f:
        for group_id, count in items:
            f.write(f"group_id = {group_id}  count = {count}\n")

    return output_path


def main():
    base_dir = Path(__file__).resolve().parent
    json_path = base_dir / "extracted_elements.json"

    if not json_path.exists():
        raise SystemExit(f"Cannot find JSON file at: {json_path}")

    elements = load_elements(json_path)
    if not isinstance(elements, dict):
        raise SystemExit("Expected top-level JSON to be an object/dict of elements.")

    group_counts = analyze_by_group_id(elements)

    # write analysis to a separate file in the same folder
    out_path = base_dir / "group_stats.txt"
    save_summary_to_file(group_counts, out_path)
    print(f"Wrote group stats to: {out_path}")


if __name__ == "__main__":
    main()
