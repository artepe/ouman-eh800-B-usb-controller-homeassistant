# Changelog

## Unreleased development branch — OpenLVI Lab 0.5.0-dev

- Expanded the Lab with a local-first Chinese and Panasonic heat pump
  compatibility registry, strict vendor-cloud exclusion (Comfort Cloud /
  Aquarea Smart Cloud), read-only normalized Home Assistant telemetry,
  sample Mango R290 Tuya LAN data, and native Zigbee mesh health audit.
- Documented existing local alternatives: Panasonic ESPHome/HeishaMon and
  M-series Modbus, Chinese OEM Tuya LAN/RS485 Modbus, Midea, Gree,
  Mitsubishi Ecodan and compatible Daikin BRP controllers.
- Required model/firmware/legitimate local-credential checks; cloud-
  assisted commissioning does not imply truly offline commissioning.
- No new heat pump control commands, Tuya key extraction, Zigbee key
  cloning or radio protocol stack duplication.


- Added 12 read-only-first experimental modules for technician diagnostics,
  register review, digital twin, hydronics, storage optimization,
  ventilation analysis, thermodynamic diagram, commissioning,
  normalized sensor networks, building safety and multi-site monitoring.
- Added safe offline CLI, optional local AI narrative, SQLite site
  summary storage and 127.0.0.1-only token-protected HTTP prototype.
- Added Home Assistant isometric digital twin resource and documented
  third-party integration boundaries.
- Added automated regression tests and fixtures; no controller
  modifications or autonomous writes.
- The OpenLVI integration manifest stays on 0.4.3-beta.1 until the
  separately reviewed Lab features are promoted into runtime.


OpenLVI Bridge and the older Ouman EH-800B integration are maintained as
**two separate components**. Versions below are descriptive software
milestones, not compatibility certifications.

## OpenLVI Bridge 0.4.3-beta.1 — 2026-11-04 (experimental)

- Added documented **read-only** Modbus point subsets for
  Uponor Smatrix Base PRO X-148, Roth Touchline SL and Tosibox
  telemetry. Vendor address notation is explicitly normalized.
- Added per-point 16-bit unavailable-value handling (0x7FFF/0xFFFF)
  without manufacturing sensor readings.
- Added manufacturer and communication catalog for Finnish sites,
  including Ouman, Honeywell, Siemens, Wavin, Danfoss, Resideo and more.
- Added separate sustained high-CO2 alert blueprint, CO2 Lovelace sample
  and optional offline CoolProp R290 property/COP CLI; no automatic
  heat-pump or refrigerant writes.
- Added Home Assistant supplemental CO2 fan blueprint with enable helper,
  outdoor cutoff, hysteresis, output deadband and invalid-data protection.
- Added simultaneous water/electric COP and independent refrigerant
  enthalpy-cycle estimates; refrigerant kW requires actual mass flow.
- Added optional pre-configured HA water and refrigerant COP package
  examples. **No new automatic heating or safety-controller writes**.
- No physical production acceptance testing on the new device families.

## OpenLVI Bridge 0.4.2-beta.1 — 2026-11-04 (experimental)

- Added manufacturer/source research for NIBE, MyVallox, Swegon CASA,
  Danfoss, Regin, Grundfos, Wilo, EMS-ESP and HeishaMon.
- Documented LoRaWAN/MQTT topic formats for Milesight UG65 Embedded NS,
  ChirpStack v4 and The Things Stack v3 plus other building networks.
- Added a **standalone read-only** LoRaWAN JSON uplink inspector and test
  fixture messages. No MQTT credentials, subscriptions or downlinks.
- Added optional engineering-unit offset to read-only Modbus point maps,
  with an experimental MyVallox RTU profile (centikelvin -> °C).
- Updated remaining legacy default Modbus point labels to English.
- No new control writes and no physical field acceptance testing.

## OpenLVI Bridge 0.4.1-beta.1 — 2026-11-04 (experimental)

- English is the canonical/default OpenLVI interface language.
- Added complete Home Assistant translations for the Ouman manual's
  six languages: English, Finnish, Swedish, Estonian, Polish, Russian.
- Localized EH-800B USB measurement names, L1 control names, status/AI
  entity names, review button and setup/options UI.
- Preserved existing entity unique IDs, device identifiers and USB property
  IDs. The physical Ouman language setting is not changed.
- Original tested legacy EH-800B v0.1.2 driver is unchanged.
- Localized names and terminology require real-user language review.

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
