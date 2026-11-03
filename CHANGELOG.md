# Changelog

OpenLVI Bridge and the older Ouman EH-800B integration are maintained as
**two separate components**. Versions below are descriptive software
milestones, not compatibility certifications.

## OpenLVI Bridge 0.4.0-beta.1 — 2026-11-04 (experimental)

- English setting explanations: on-device guide sensor, manual review button
  and `openlvi.ask_assistant` action with response data.
- Optional local Qwen2.5 0.5B via private LAN Ollama and configurable
  periodic advice every six hours (off by default).
- Automatic initial setup report is offline and read-only; no cloud service
  or model download is required.
- **No AI autonomous equipment setpoint changes, PID writes or valve actions**.

## OpenLVI Bridge 0.3.0-beta.1 — 2026-11-04 (experimental)

- Automatically exposes EH-800B USB heating-curve and approved L1
  parameter Number entities after adding the model in Home Assistant,
  including entries configured in prior OpenLVI versions.
- Uses the legacy USB hub's shared per-port serial lock for measurements and
  writes; rejects unknown/PID/manual-valve properties and invalid increments.
- Sends **one** SET PROPERTY on an explicit manual adjustment, checks the
  property ID and echoed raw value, and does not retry ambiguous writes.
- Never writes anything on installation, reconnect or normal sensor polling.
  Initial setpoint values are *unknown* because safe GET PROPERTY has not
  been verified. No dummy defaults are displayed.
- Added offline protocol/mock tests and a user guide.
- This new USB write path still needs real-controller acceptance testing.

## OpenLVI Bridge 0.2.0-beta.1 — 2026-11-03 (experimental)

- Renamed the new multi-vendor integration to `openlvi` / OpenLVI Bridge.
- Manufacturer-first wizard and Modbus RTU/TCP, EH-800 local HTTP and
  EH-800B USB read-only adapters.
- Documented initial Ouman A203/S203/C203/H23, Danfoss ECL,
  Swegon CASA Genius and Regin Corrigo E register subsets.
- Added read-only, targeted BACnet/IP object reads and active-master wired
  M-Bus polling for Kamstrup MULTICAL model selections.
- Added selected additional manufacturer names; most require custom,
  site-specific **read-only** register/object profiles.
- Added reviewed CSV/XML → JSON point-map importer, an isometric
  (2.5D) Home Assistant SCADA example card and rule-based diagnostics.
- Extended automated syntax/format-independent register tests.

**Limitations:** no real-controller verification of the new multi-vendor
drivers; no production-ready HACS release, general network discovery,
full 3D renderer or AI fault-diagnosis engine.

## Ouman EH-800B USB 0.1.2 — 2026-10 (legacy stable)

- USB CDC-ACM Mini-B protocol for the tested EH-800B.
- 28 measurement entities and L1 number controls; 15-second polling.
- Last reported working version on the project's real EH-800B device.
- **Safety:** do not modify writable PID properties 56/57/58 or manual
  valve position 92 in an operating heating system.

See [PID observations](docs/PID_KNOWN_ISSUES.md) and
[legacy install guide](docs/STABLE_RELEASE_v0.1.2.md).
