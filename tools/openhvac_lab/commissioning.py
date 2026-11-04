"""Generate a commissioning review from a fixed source profile and observations.

Not an autonomous acceptance certificate. The operator must explicitly
sign off the inspection; no device polling, writes, or network access.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from textwrap import wrap
from .core import utc_time, number, InvalidMeasurement
from .profiles import validate_profile


def review_commissioning(profile, observations, *, site_id, checked_at):
    metadata = validate_profile(profile)
    if not isinstance(site_id, str) or not 1 <= len(site_id) <= 64:
        raise ValueError("site_id required")
    if not isinstance(observations, dict):
        raise ValueError("Observations must map register keys to measurements")
    current = utc_time(checked_at)
    checks = []
    for point in profile["registers"]:
        key = point["key"]
        sample = observations.get(key)
        if not isinstance(sample, dict):
            checks.append({"key": key, "status": "missing", "note": "No reading"})
            continue
        try:
            value = number(sample.get("value"), key)
            observed = utc_time(sample.get("observed_at"))
            age = (current-observed).total_seconds()
            if age > 900 or age < -120:
                status = "stale"
                note = "Reading timestamp is stale or has clock skew."
            else:
                status = "observed"
                note = "One plausible observation exists; physical verification pending."
            if "minimum" in point and value < number(point["minimum"]):
                status, note = "out_of_range", "Below site-supplied design range."
            if "maximum" in point and value > number(point["maximum"]):
                status, note = "out_of_range", "Above site-supplied design range."
            checks.append({
                "key": key, "status": status, "note": note,
                "value": value, "observed_at": observed.isoformat(),
            })
        except (InvalidMeasurement, ValueError, TypeError):
            checks.append({"key": key, "status": "invalid", "note": "Measurement not validated"})
    return {
        "title": "OpenHVAC Site Commissioning Review",
        "site_id": site_id,
        "checked_at": current.isoformat(),
        "device": metadata,
        "checks": checks,
        "counts": {status: sum(x["status"] == status for x in checks)
                   for status in ("observed", "missing", "stale", "out_of_range", "invalid")},
        "site_acceptance": "PENDING_OPERATOR_REVIEW",
        "physical_setpoints_changed": False,
        "commands_issued": 0,
    }


def markdown_report(report):
    lines = [
        "# " + report["title"], "",
        f"**Site:** {report['site_id']}",
        f"**Checked (UTC):** {report['checked_at']}",
        f"**Device:** {report['device']['vendor']} {report['device']['model']} "
        f"({report['device']['firmware']})",
        f"**Transport:** {report['device']['transport']}",
        f"**Source:** {report['device']['source_url']}",
        f"**Operator acceptance:** {report['site_acceptance']}",
        "",
        "| Point | Result | Value | Comment |",
        "|---|---|---|---|",
    ]
    for check in report["checks"]:
        row = [str(check.get(k, "")) for k in ("key", "status", "value", "note")]
        escaped = [x.replace("|", "/").replace("\n", " ") for x in row]
        lines.append("| " + " | ".join(escaped) + " |")
    lines.extend([
        "", "## Safety and scope",
        "No hardware commands were issued. The observations are not a signed "
        "commissioning certificate. Validate scaling, sensor position, firmware, "
        "native protective functions and actual controller display on site.",
        "",
        "Operator name/signature: __________________    Date: __________",
    ])
    return "\n".join(lines) + "\n"


def pdf_report(report, path):
    """Optional PDF export using ReportLab; no remote assets or embedded fonts."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except ImportError as exc:
        raise RuntimeError("Optional reportlab required for PDF export") from exc
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(dest), pagesize=A4)
    width, height = A4
    lines = markdown_report(report).splitlines()
    ypos = height - 55
    c.setTitle(report["title"])
    c.setFont("Helvetica", 9)
    for line in lines:
        plain = line.replace("**", "").replace("|", " / ")
        if plain.startswith("# "):
            c.setFont("Helvetica-Bold", 16)
            plain = plain[2:]
        else:
            c.setFont("Helvetica", 9)
        # Standard ReportLab font uses Latin-1; replace unsupported
        # symbols instead of producing missing glyph blocks.
        printable = plain.encode("latin-1", "replace").decode("latin-1")
        for chunk in wrap(printable, width=105) or [""]:
            if ypos < 45:
                c.showPage()
                c.setFont("Helvetica", 9)
                ypos = height-55
            c.drawString(45, ypos, chunk)
            ypos -= 14
    c.save()
    return str(dest)
