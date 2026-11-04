# OpenLVI Bridge

**Open-source Home Assistant integration for HVAC and building automation.**

**Primary language: English.** Optional Home Assistant translations: Finnish,
Swedish, Estonian, Polish and Russian. [Language guide](docs/LOCALIZATION.md).

[![OpenLVI core checks](https://github.com/artepe/OpenLVIBridge-homeassistant/actions/workflows/openlvi-core.yml/badge.svg)](https://github.com/artepe/OpenLVIBridge-homeassistant/actions/workflows/openlvi-core.yml)
[![OpenLVI extension checks](https://github.com/artepe/OpenLVIBridge-homeassistant/actions/workflows/openlvi-extensions.yml/badge.svg)](https://github.com/artepe/OpenLVIBridge-homeassistant/actions/workflows/openlvi-extensions.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

> [!IMPORTANT]
> **OpenLVI Bridge is experimental (0.4.1-beta.1).** Automated tests have passed, but
> the multi-vendor drivers **have not been validated on physical controllers**.
> The separate **Ouman EH-800B USB v0.1.2** integration is the last version
> reported working on the project's actual EH-800B. Do not replace a working
> heating installation with unverified drivers.

## What does OpenLVI Bridge do?

OpenLVI Bridge links compatible heating, ventilation, metering and building
automation equipment to **Home Assistant over a local connection**, without
requiring a vendor cloud service for supported interfaces.

- **Setup wizard:** select manufacturer → model → firmware → protocol →
  IP address or serial port.
- **Protocols:** Modbus TCP/RTU, Ouman EH-800 HTTP, EH-800B USB,
  **BACnet/IP (read-only)** and **wired M-Bus (read-only)**.
- **Measurements:** documented temperatures, fan data, valve/setpoint values,
  M-Bus telegram records and BACnet objects, according to model and site.
- **Controls:** EH-800B USB: 11 documented L1 setpoint Number entities
  appear on the device automatically, including on existing OpenLVI entries.
  They perform **no write during setup**; a manual value entry sends one
  validated command. Other models require their separate write opt-in.
  PID 56/57/58, manual valve 92 and unknown properties remain excluded.
  Never bypass native controller safety interlocks.
- **English AI guide:** automatic read-only baseline, on-device review button
  and optional local Ollama Qwen2.5 0.5B to explain settings. The AI does
  **not** write heating controller settings. [Guide](docs/OPENLVI_AI_GUIDE.md).
- **Tools:** manually reviewed CSV/XML → read-only Modbus JSON point maps,
  2.5D isometric SCADA card, and *rule-based* advisory energy diagnostics.
  **No autonomous AI equipment control or full 3D digital twin is included.**

## Supported interfaces and validation status

| Manufacturer / hardware | Included implementation | Validation status |
|---|---|---|
| **Ouman EH-800** | HTTP API through `ouman-eh-800-api` | Experimental OpenLVI driver; official HA integration also exists |
| **Ouman EH-800B** | 28 USB measurements **and 11 on-device L1 setpoint controls** with single-shot writes | Legacy v0.1.2 physically tested; new controls not yet tested |
| **Ouman A203, S203, C203, H23** | Small firmware-specific Modbus register subsets | Automated tests only |
| **Danfoss ECL Comfort 210 / 296 / 310 / 310B** | Modbus PNU read subset; application-key-aware sample | Automated tests only |
| **Swegon CASA Genius 4.x** | SEM/SEC Modbus subset (fan RPM/%, settings, selected modes) | Automated tests only |
| **Regin Corrigo E Ventilation 3.2** | Read-only Modbus temperature/airflow subset | Automated tests only |
| **BACnet/IP equipment** | Read-only target-device object discovery (up to 32 points) or supplied point list | Not yet verified on a real BACnet controller |
| **Kamstrup MULTICAL 403/603/803** | Wired serial M-Bus telegram decoding through powered M-Bus master | Not yet verified on a real meter |
| **Grundfos, Wilo, Belimo, Schneider, Siemens, Fidelix, Produal, Koja, Enervent, Vallox, NIBE and others** | Model selections, generic Modbus/BACnet connection with a *site-specific read-only point map* | **Not plug-and-play**; hardware/options vary |

**A name in the setup wizard does not mean that every model is fully
integrated.** Verify the device firmware, Modbus point list, BACnet object
map, licensing and communications hardware for the exact installation.

## Installation on Home Assistant OS

**OpenLVI Bridge — experimental:**

1. Copy [`custom_components/openlvi`](custom_components/openlvi) into
   `/config/custom_components/openlvi` on Home Assistant OS. The
   *source files* are copied, not just a repository ZIP inside the folder.
2. Restart Home Assistant and open **Settings → Devices & services →
   Add integration → OpenLVI Bridge**.
3. Select the manufacturer/model and the *actual* connection protocol.
   Confirm the correct firmware and device-specific register map. Keep
   writable settings **disabled** on your first test.
4. Confirm live sensor values in **Developer Tools → States** and compare
   with the physical controller display. Dashboard history alone is not proof
   that polling works.

**EH-800B USB controls:** after updating, open the device page and find the
number controls (L1 curve points, supply limits, setpoint and fine adjustment).
No additional `number:` YAML is needed. Since a side-effect-free USB
`GET PROPERTY` is unverified, these Number entities display **unknown**
until you manually enter and confirm a value. A reported value after a
write is the **last confirmed write**, not a fresh independent read.
See [the USB setpoint usage guide](docs/EH800B_CONTROLS.md).

For Ouman EH-800B USB via the new bridge, the legacy
`custom_components/ouman_eh800` directory is also required as its protocol
reader. **Never configure both integrations to poll the same USB port
simultaneously.** For a live heating installation, keep the known-working
legacy driver.

**Stable legacy EH-800B v0.1.2** is installed separately using
[its YAML instructions](docs/STABLE_RELEASE_v0.1.2.md). It does **not** have
the OpenLVI setup wizard.

**HACS / automatic discovery:** this release documents manual installation.
Do not assume HACS compatibility or automatic detection of every manufacturer.

## Dashboards, data and developer documentation

| Resource | Purpose |
|---|---|
| [English default and five additional Ouman languages](docs/LOCALIZATION.md) | Home Assistant translated controller labels and compatibility rules |
| [OpenLVI model/Modbus/HTTP guide](docs/OPENLVI_BRIDGE.md) | Exact model subsets, Modbus maps, connection instructions and limitations |
| [BACnet, wired M-Bus, SCADA and diagnostics](docs/OPENLVI_EXTENSIONS.md) | Hardware setup, BACnet object lists, M-Bus master and energy formulas |
| [Isometric SCADA card](www/openlvi-scada-card.js) and [example](examples/lovelace-openlvi-scada.yaml) | Read-only live Lovelace schematic with example entity IDs |
| [CSV/XML point-map importer](tools/openlvi_pointmap_import.py) | Converts reviewed vendor point tables to read-only JSON |
| [Stable EH-800B v0.1.2](docs/STABLE_RELEASE_v0.1.2.md) | USB integration with real-device test history |
| [PID/valve caution](docs/PID_KNOWN_ISSUES.md) | Known risks of legacy writable PID properties |
| [English AI advisor and Ollama setup](docs/OPENLVI_AI_GUIDE.md) | Optional small model, button, sensor and `openlvi.ask_assistant` action |
| [Changelog](CHANGELOG.md) and [contributing](CONTRIBUTING.md) | Development status and safe additions |

## Safety boundaries

OpenLVI is **not a safety-rated building management controller**.
Maintain the manufacturer's native frost, overheating, pump and valve safety
functions. Do not expose Modbus TCP, BACnet/IP or unencrypted device HTTP
directly to the internet. Use a segmented, trusted local network.

The stable legacy **EH-800B v0.1.2** exposes writable properties 56/57/58
(PID) and 92 (manual valve position). **Do not change those on a live system**
without an independently verified safe procedure.

The diagnostics are only threshold-based observations, not a substitute for
professional troubleshooting. Calculated thermal power assumes **water**,
correct sensor placement, and a separately decoded volume-flow measurement.

## Status and license

- **OpenLVI Bridge:** `custom_components/openlvi` — **0.4.1-beta.1**,
  experimental, in the main branch; real-hardware acceptance tests pending.
- **Ouman USB:** `custom_components/ouman_eh800` — **0.1.2**,
  last physically tested installation version. Both remain separate.
- Contributions and verified register maps are welcome; see
  [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).
- MIT licensed, independent community project. No affiliation with or
  endorsement by Ouman, Danfoss, Swegon, Regin, Kamstrup or other vendors.
