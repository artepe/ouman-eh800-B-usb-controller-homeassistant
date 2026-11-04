"""Safe register/document explorer and community profile approval schema.

This toolkit never polls devices or executes Modbus writes. The PDF/plain
text parser creates candidates requiring manual verification, not a
self-certified register map.
"""
from __future__ import annotations

import csv
import io
import json
import re
from urllib.parse import urlparse

_KEY = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
_ADD = re.compile(r"(?<!\d)([34]\d{4})(?!\d)")
_BAD = re.compile(r"(?i)password|secret|token|appkey|apikey|private.key")


def _slug(label):
    clean = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
    return clean[:60] if clean and clean[0].isalpha() else "register"


def text_candidates(text, *, source_document):
    """Recognize Modbus 3xxxx / 4xxxx labels from extracted text only.

    3xxxx/4xxxx tags do NOT imply PDU=tag-1. The converter strips the
    30000/40000 grouping to an OpenHVAC one-based address. Verify first.
    """
    if not isinstance(text, str) or len(text) > 200_000:
        raise ValueError("Document text is missing or too long")
    if not isinstance(source_document, str) or not source_document.strip():
        raise ValueError("source_document must be specified")
    found, keys = [], set()
    for line in text.splitlines()[:8000]:
        match = _ADD.search(line)
        if not match:
            continue
        tag = int(match.group(1))
        area = "input" if tag // 10000 == 3 else "holding"
        address = tag - (30000 if area == "input" else 40000)
        if not 1 <= address <= 9999:
            continue
        label = (line[:match.start()] + " " + line[match.end():]).strip(" :;\t")
        if not label or _BAD.search(label):
            continue
        label = label[:80]
        key = _slug(label)
        if key in keys:
            key = f"{key[:53]}_{address}"
        if key in keys:
            continue
        keys.add(key)
        found.append({
            "key": key,
            "name": label,
            "area": area,
            "address": address,
            "original_document_tag": tag,
            "kind": None,
            "decimals": None,
            "unit": None,
            "writable": False,
            "reviewed": False,
            "source": source_document,
            "review_notes": "Verify addressing, signedness, scale, firmware and on-device value.",
        })
        if len(found) >= 256:
            break
    return {
        "candidate_count": len(found), "registers": found,
        "writable": False, "device_reads": 0,
        "note": "Document extraction is not a live device scan or a verified profile.",
    }


def csv_candidates(content, *, source_document):
    if not isinstance(content, str) or len(content) > 200000:
        raise ValueError("Invalid CSV content")
    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames or not {"address", "name"} <= set(reader.fieldnames):
        raise ValueError("CSV must provide address and name columns")
    lines = []
    for row in reader:
        address = str(row.get("address") or "").strip()
        name = str(row.get("name") or "").strip()
        if re.fullmatch(r"[34]\d{4}", address) and name:
            lines.append(f"{address} {name[:80]}")
        if len(lines) >= 256:
            break
    return text_candidates("\n".join(lines), source_document=source_document)


def pdf_candidates(path, *, max_pages=50):
    """Use optional pypdf offline. No OCR/network/AI; PDF extraction is advisory."""
    from pathlib import Path
    source = Path(path)
    if not source.is_file() or source.stat().st_size > 15_000_000:
        raise ValueError("PDF not found or larger than 15 MB")
    if max_pages < 1 or max_pages > 100:
        raise ValueError("max_pages outside safe bound")
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("Optional dependency required: pip install pypdf") from exc
    reader = PdfReader(str(source))
    fragments = []
    for page in reader.pages[:max_pages]:
        fragments.append((page.extract_text() or "")[:30000])
    return text_candidates("\n".join(fragments)[:200000],
                           source_document=source.name)


def validate_profile(document):
    """Validate catalog metadata and bound read-only points.

    A community-provided profile is *never* promoted to writable by
    marking it tested. Source URLs must be official or reviewable HTTPS.
    """
    if not isinstance(document, dict):
        raise ValueError("Profile must be an object")
    for key in ("vendor", "model", "firmware", "source_url", "transport", "registers"):
        if key not in document:
            raise ValueError(f"Missing profile field: {key}")
    for key in ("vendor", "model", "firmware", "transport"):
        v = document[key]
        if not isinstance(v, str) or not 1 <= len(v) <= 120:
            raise ValueError(f"Invalid {key}")
    url = document["source_url"]
    parts = urlparse(url) if isinstance(url, str) else None
    if parts is None or parts.scheme != "https" or not parts.netloc:
        raise ValueError("source_url must be HTTPS")
    if document["transport"] not in ("modbus_tcp", "modbus_rtu"):
        raise ValueError("Only documented read-only Modbus point profiles supported")
    status = document.get("verification", "candidate")
    if status not in ("candidate", "bench_verified", "site_verified"):
        raise ValueError("Invalid verification status")
    points = document["registers"]
    if not isinstance(points, list) or not 1 <= len(points) <= 256:
        raise ValueError("Provide 1..256 points")
    keys = set()
    for point in points:
        if not isinstance(point, dict):
            raise ValueError("Invalid point")
        key = point.get("key")
        if not isinstance(key, str) or not _KEY.fullmatch(key) or key in keys:
            raise ValueError("Invalid or repeated point key")
        keys.add(key)
        if type(point.get("address")) is not int or not 1 <= point["address"] <= 65535:
            raise ValueError("Invalid one-based register address")
        if point.get("area") not in ("input", "holding"):
            raise ValueError("Invalid Modbus register area")
        if point.get("kind") not in ("s16", "u16", "s32", "u32"):
            raise ValueError("Unsupported point type")
        if type(point.get("decimals")) is not int or not 0 <= point["decimals"] <= 5:
            raise ValueError("Invalid decimal scaling")
        if not isinstance(point.get("name"), str) or not point["name"].strip():
            raise ValueError("Point name required")
        if point.get("writable", False) is not False:
            raise ValueError("Community profiles are always read-only")
    return {
        "vendor": document["vendor"], "model": document["model"],
        "firmware": document["firmware"], "transport": document["transport"],
        "source_url": url, "verification": status,
        "points": len(points), "read_only": True,
        "approved_for_automatic_writes": False,
    }
