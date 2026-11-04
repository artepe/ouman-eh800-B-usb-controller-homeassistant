#!/usr/bin/env python3
"""Turn verified Modbus CSV/XML point lists into read-only OpenHVAC JSON.

Never derives points from a vague product number. Every input address must
be supplied by the vendor's firmware/application-specific register table.
"""
import argparse
import csv
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET


def normalize_point(row):
    key = row.get("key", "").strip().lower()
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", key):
        raise ValueError(f"Invalid key: {key!r}")
    address = int(row["address"])
    decimals = int(row.get("decimals", 0) or 0)
    kind = row.get("kind", "s16").strip().lower()
    area = row.get("area", "holding").strip().lower()
    if not 1 <= address <= 65535:
        raise ValueError("Address must be 1-based in 1..65535")
    if kind not in ("s16", "u16", "s32", "u32") or area not in ("holding", "input"):
        raise ValueError("Unsupported kind or Modbus area")
    if not 0 <= decimals <= 5:
        raise ValueError("Decimals must be 0..5")
    return {"key": key, "name": (row.get("name") or key)[:90],
            "address": address, "kind": kind, "decimals": decimals,
            "area": area, "unit": row.get("unit") or None}


def parse_file(path):
    path = Path(path)
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
    elif path.suffix.lower() == ".xml":
        root = ET.parse(path).getroot()
        rows = [elem.attrib for elem in root.findall(".//point")]
    else:
        raise ValueError("Use .csv or .xml with explicit columns; PDFs require manual verification")
    if not 1 <= len(rows) <= 128:
        raise ValueError("Point list size must be 1..128")
    points = [normalize_point(row) for row in rows]
    if len({p["key"] for p in points}) != len(points):
        raise ValueError("Duplicate point keys")
    return {"registers": points}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", help="CSV/XML from a verified vendor point table")
    parser.add_argument("-o", "--output", help="Optional output JSON path")
    args = parser.parse_args()
    content = json.dumps(parse_file(args.source), ensure_ascii=False, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(content, encoding="utf-8")
    else:
        print(content, end="")


if __name__ == "__main__":
    main()
