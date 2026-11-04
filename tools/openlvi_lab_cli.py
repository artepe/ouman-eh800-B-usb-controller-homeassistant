#!/usr/bin/env python3
"""OpenLVI Lab: offline prototype suite, never sends HVAC commands.

Each subcommand reads a JSON file (--input) and writes JSON to stdout
unless an explicit output path is requested. Subcommands are prototypes,
not substitutes for qualified commissioning or building safety systems.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

from openlvi_lab.doctor import analyze_plant
from openlvi_lab.hydronics import balance_rooms
from openlvi_lab.heating import plan_buffer_heating
from openlvi_lab.ventilation import assess_ventilation
from openlvi_lab.safety import inspect_safety
from openlvi_lab.gateway import normalize_bundle
from openlvi_lab.profiles import (
    text_candidates, csv_candidates, pdf_candidates, validate_profile)
from openlvi_lab.commissioning import (
    review_commissioning, markdown_report, pdf_report)
from openlvi_lab.refrigerant import log_ph_svg
from openlvi_lab.multisite import SiteStore
from openlvi_lab.local_hvac import plan_local_path, normalize_heatpump_entities
from openlvi_lab.zigbee import zigbee_mesh_audit
from openlvi_lab.tosibox import interpret_gateway_registers, design_connection


def _read(path, *, limit=2_000_000):
    file = Path(path)
    if file.stat().st_size > limit:
        raise ValueError(f"Input exceeds {limit} bytes")
    return file.read_text(encoding="utf-8")


def run(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=(
        "fault-doctor", "hydronic-balance", "heating-forecast",
        "ventilation-lab", "safety-monitor", "sensor-gateway",
        "register-explorer", "validate-profile", "commissioning",
        "refrigerant-svg", "multi-site-import", "multi-site-summary",
        "local-hvac-path", "local-heatpump-readings", "zigbee-audit",
        "tosibox-status", "tosibox-plan",
    ))
    p.add_argument("--input", help="Source JSON, CSV, extracted text or PDF")
    p.add_argument("--path", help="Known local HVAC catalog path ID")
    p.add_argument("--deployment", choices=("single_site", "few_sites", "multi_site"))
    p.add_argument("--gateway-mode", choices=("lock", "client"))
    p.add_argument("--monitoring-location", choices=("on_site", "central"))
    p.add_argument("--format", choices=("text", "csv", "pdf"), default="text")
    p.add_argument("--source", default="unknown_document",
                   help="Original document name for register exploration")
    p.add_argument("--output", help="Output markdown or SVG path where appropriate")
    p.add_argument("--pdf", help="Optional commissioning PDF output path")
    p.add_argument("--db", default="./openlvi_lab_sites.sqlite3",
                   help="Local SQLite site summary database")
    args = p.parse_args(argv)

    if args.command == "tosibox-plan":
        if not (args.deployment and args.gateway_mode and args.monitoring_location):
            raise ValueError("--deployment, --gateway-mode and --monitoring-location required")
        data = design_connection(deployment=args.deployment,
                                 gateway_mode=args.gateway_mode,
                                 monitoring_location=args.monitoring_location)
    elif args.command == "local-hvac-path":
        if not args.path:
            raise ValueError("--path is required for local-hvac-path")
        data = plan_local_path(args.path)
    elif args.command == "multi-site-summary":
        data = {"sites": SiteStore(args.db).list(), "commands_issued": 0}
    elif args.command == "register-explorer":
        if not args.input:
            raise ValueError("--input is required")
        if args.format == "pdf":
            data = pdf_candidates(args.input)
        elif args.format == "csv":
            data = csv_candidates(_read(args.input), source_document=args.source)
        else:
            data = text_candidates(_read(args.input), source_document=args.source)
    else:
        if not args.input:
            raise ValueError("--input is required")
        payload = json.loads(_read(args.input))
        if args.command == "tosibox-status":
            data = interpret_gateway_registers(
                payload["registers"], gateway_model=payload["gateway_model"],
                firmware=payload["firmware"],
                observed_at=payload["observed_at"], now=payload.get("now"),
                target_reachable=payload.get("target_reachable"))
        elif args.command == "local-heatpump-readings":
            data = normalize_heatpump_entities(
                payload["path"], states=payload["states"],
                mapping=payload["mapping"], now=payload["now"])
        elif args.command == "zigbee-audit":
            data = zigbee_mesh_audit(payload["mesh"], now=payload["now"])
        elif args.command == "fault-doctor":
            data = analyze_plant(payload["current"], payload.get("history", []))
        elif args.command == "hydronic-balance":
            data = balance_rooms(payload["rooms"])
        elif args.command == "heating-forecast":
            data = plan_buffer_heating(payload["config"], payload["forecast"])
        elif args.command == "ventilation-lab":
            data = assess_ventilation(payload)
        elif args.command == "safety-monitor":
            data = inspect_safety(payload, now=payload.get("now"))
        elif args.command == "sensor-gateway":
            data = normalize_bundle(payload["readings"], now=payload["now"])
        elif args.command == "validate-profile":
            data = validate_profile(payload)
        elif args.command == "commissioning":
            data = review_commissioning(
                payload["profile"], payload["observations"],
                site_id=payload["site_id"], checked_at=payload["checked_at"])
            if args.output:
                Path(args.output).write_text(markdown_report(data), encoding="utf-8")
            if args.pdf:
                pdf_report(data, args.pdf)
        elif args.command == "refrigerant-svg":
            svg = log_ph_svg(payload["states"],
                             refrigerant=payload.get("refrigerant", "R290"))
            if not args.output:
                raise ValueError("SVG diagram requires --output path")
            Path(args.output).write_text(svg, encoding="utf-8")
            data = {"saved_svg": str(args.output),
                    "cycle_states": len(payload["states"]), "commands_issued": 0}
        elif args.command == "multi-site-import":
            data = SiteStore(args.db).put(payload)
        else:
            raise ValueError("Unrecognized command")
    print(json.dumps(data, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(run())
    except (KeyError, ValueError, OSError, TypeError, RuntimeError,
            json.JSONDecodeError) as exc:
        print(f"OpenLVI Lab: {exc}", file=sys.stderr)
        sys.exit(2)
