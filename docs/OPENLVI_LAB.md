# OpenLVI Lab — 12-feature experimental development branch

Primary language: English. This is an experimental, read-only-first
engineering companion toolkit, NOT a certified BMS, fully autonomous
controller, commercial cloud service, or complete universal driver.

The existing OpenLVI 0.4.3-beta.1 driver and the stable legacy
Ouman EH-800B USB driver are unchanged in this development branch.

## Feature matrix

| # | Feature | Working prototype | Limitations |
|---|---|---|---|
| 1 | Fault Doctor | tools/openlvi_lab/doctor.py: COP trends, filter pressure, valve/supply mismatch, low flow, defrost. Optional local Ollama narrative in ai.py | Evidence-based suggestions, not confirmed fault diagnoses |
| 2 | Register Explorer | profiles.py: plain text, CSV, optional PDF extraction and review-first Modbus candidate tags | No automatic scaling guessing; no physical register probing/writes |
| 3 | Digital Twin | www/openlvi-digital-twin-card.js: HA-linked clickable isometric floors and zones | Schematic 2.5D, not genuine BIM/3D geometry |
| 4 | Hydronic Balance | hydronics.py: target deviation, valve-open cold room prioritization and water delta T | No direct commissioning or valve actuation |
| 5 | Predictive Heating | heating.py: heat-loss, forecast prices/COP, buffer storage and dispatch cost model | No Nord Pool API or heat-pump write actions; thermal inertia/defrost ignored |
| 6 | Ventilation Lab | ventilation.py: sensible heat recovery, SFP approximation, CO2 warning | Not a standardized certified performance test |
| 7 | Refrigerant Analyzer | refrigerant.py: schematic log(p)-h SVG from real P/h states | No saturation dome; external CoolProp tool provides optional real fluid state calculation |
| 8 | Auto Commissioning | commissioning.py: read-only verification checklist, Markdown, optional ReportLab PDF | Human physical signoff required |
| 9 | Sensor Gateway | gateway.py: one normalized sensor schema for already-decoded LoRaWAN, wM-Bus, MQTT, Zigbee, BLE, KNX, BACnet etc | Not an RF receiver, decoder or bridge |
| 10 | Safety Monitor | safety.py: advisory leak/frost/high CO2/stale device alerts | Does not replace OEM fire/frost/emergency safety |
| 11 | Multi-Site Monitor | multisite.py and tools/openlvi_lab_server.py: token-authenticated local SQLite status API | Local-only prototype, no public cloud or multitenant security model |
| 12 | Community Device Library | profiles.py: verified-document metadata, firmware, read-only points, validation | No automatic acceptance or writes |

Bonus Auto Commissioning combines profile import, measurement quality,
site review and a manually signed report.

## Run the offline examples

Use Python 3.11+ from the repository root. Core functionality depends
only on the Python standard library. Optional packages are pypdf for
PDF text extraction and reportlab for commissioning PDF export.

    python3 tools/openlvi_lab_cli.py fault-doctor --input examples/openlvi-lab/fault-doctor.json
    python3 tools/openlvi_lab_cli.py hydronic-balance --input examples/openlvi-lab/hydronic-balance.json
    python3 tools/openlvi_lab_cli.py heating-forecast --input examples/openlvi-lab/heating-forecast.json
    python3 tools/openlvi_lab_cli.py ventilation-lab --input examples/openlvi-lab/ventilation.json
    python3 tools/openlvi_lab_cli.py safety-monitor --input examples/openlvi-lab/safety.json
    python3 tools/openlvi_lab_cli.py sensor-gateway --input examples/openlvi-lab/gateway.json
    python3 tools/openlvi_lab_cli.py validate-profile --input examples/openlvi-lab/profile-candidate.json
    python3 tools/openlvi_lab_cli.py commissioning --input examples/openlvi-lab/commissioning.json --output /tmp/openlvi-review.md
    python3 tools/openlvi_lab_cli.py refrigerant-svg --input examples/openlvi-lab/ph-cycle.json --output /tmp/openlvi-cycle.svg

To add a PDF report:

    python3 -m pip install reportlab
    python3 tools/openlvi_lab_cli.py commissioning --input examples/openlvi-lab/commissioning.json --output /tmp/openlvi-review.md --pdf /tmp/openlvi-review.pdf

For a local PDF-based candidate register extraction:

    python3 -m pip install pypdf
    python3 tools/openlvi_lab_cli.py register-explorer --format pdf --input device_register_manual.pdf

This creates UNVERIFIED candidate rows. PDF register tables are not
inherently trustworthy for automatic interpretation. The installer
must review address base, FC03/FC04 area, signedness, scaling,
units, firmware, exact model and compared live value.

## Digital Twin in Home Assistant

Copy www/openlvi-digital-twin-card.js to:

    /config/www/openlvi-digital-twin-card.js

Register /local/openlvi-digital-twin-card.js as a JavaScript dashboard
resource. Use examples/lovelace-openlvi-digital-twin.yaml, replacing
all example entity IDs with actual Home Assistant measurements.
The card opens HA More Info; it does not call HA actuator services.

## Optional local AI summary

The Fault Doctor always works without a language model. The
tools/openlvi_lab/ai.py adapter can optionally send only numeric
evidence and fault codes to a local Ollama IPv4 endpoint on port
11434 (for example, http://192.168.1.50:11434). No cloud,
credentials, raw meter history, addresses or setpoint commands.
AI summaries remain advisory and English-first.

## Forecast heating inputs and warnings

Provide buffer volume, min/max/current buffer temperature, site
building heat-loss coefficient (kW/K), indoor target temperature,
maximum heat pump thermal power and a chronological list of outdoor
forecasts, estimated COP and electricity prices (EUR/kWh).
The example 3000-litre buffer is illustrative.

The discretized cost-based planner ignores building thermal mass,
buffer stratification, heating curves, defrost, compressor start/stop,
hydraulic mixing and OEM protections. Never apply its recommended
thermal-power values directly to an untested real controller.

## Multi-site monitoring

The demo API binds ONLY to localhost 127.0.0.1 and requires a long
bearer token. GET /health, GET /sites, GET /sites/<site-id> and
POST /ingest are the complete endpoint set. No actuator actions
or controller credentials are accepted.

Example offline import:

    python3 tools/openlvi_lab_cli.py multi-site-import --input examples/openlvi-lab/site-report.json --db /tmp/openlvi_sites.sqlite3
    python3 tools/openlvi_lab_cli.py multi-site-summary --db /tmp/openlvi_sites.sqlite3

To run a LOCAL-only API, set a random secret and start:

    export OPENLVI_LAB_TOKEN='REPLACE-WITH-A-RANDOM-STRING-LONGER-THAN-24'
    python3 tools/openlvi_lab_server.py --db /tmp/openlvi_sites.sqlite3 --port 8767

Remote use requires a separate hardened VPN/TLS reverse proxy,
access controls, backups, rate limiting and threat review. DO NOT
expose this HTTP port or any Modbus/BACnet port to the internet.
Never commit network secrets or tenants' personal data.

## Device library profile safety

A profile must name vendor/model/firmware/source HTTPS URL and transport,
and provide each register's key, name, one-based address, area,
signedness/width, decimal scaling and writable=false.

Verification statuses are candidate, bench_verified, site_verified,
all read-only. Even marking site_verified never enables writes.
A full Modbus/BACnet register dump does not prove authorization to
write any point. Retain original hardware emergency protections.

## Commissioning limitations

Reports are preliminary. Human signoff is required after comparing
sensor scaling, site calibration, physical display, wiring, correct
firmware, emergency/frost/fire functions and owner-approved controls.
No automatic safety certification or autonomous commissioning is
claimed.

All tooling produces outputs in English and has no controller
write API. Do not use this toolkit to disable mandatory ventilation,
fire/smoke extraction, frost protection or other safety systems.

## Cloud-independent heat pumps and Zigbee strategy

A new [local-first heat pump / Zigbee guide](LOCAL_FIRST_HEATPUMPS.md)
documents Panasonic Comfort Cloud cloud dependency, Panasonic
CN-CNT/CN-WLAN ESPHome replacements, HeishaMon Aquarea and M-series
Modbus, Chinese R290 Tuya/Modbus, Midea, Gree, Mitsubishi and Daikin.
The strict-offline catalog and Home Assistant read-only normalizer
are in `tools/openlvi_lab/local_hvac.py`. The Zigbee2MQTT/ZHA
network inventory auditor is in `tools/openlvi_lab/zigbee.py`.

    python3 tools/openlvi_lab_cli.py local-hvac-path --path panasonic_comfort_cloud
    python3 tools/openlvi_lab_cli.py local-hvac-path --path panasonic_split_esphome
    python3 tools/openlvi_lab_cli.py local-heatpump-readings --input examples/openlvi-lab/local-heatpump.json
    python3 tools/openlvi_lab_cli.py zigbee-audit --input examples/openlvi-lab/zigbee-mesh.json

These do **not** connect to a device, download cloud credentials, control
a heat pump or pair Zigbee radios. Each source requires verified hardware,
firmware, exact device support and WAN-blocked acceptance tests. Only
already-captured local sensor data is normalized.

Do **not** clone Zigbee2MQTT/ZHA as a second stack. Add upstream quirks
and external converters by exact fingerprint, and reuse their HA entities.
