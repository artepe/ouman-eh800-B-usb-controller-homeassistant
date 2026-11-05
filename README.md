<div align="center">

# Open HVAC

### Local-first building automation for Home Assistant

**One project. Independent modules. Your equipment, your network.**

[Download modules](#download-modules) · [Getting started](#getting-started) · [Supported equipment](#supported-equipment) · [Developer guide](CONTRIBUTING.md)

[![Module packages](https://github.com/artepe/Open-HVACBridge-homeassistant/actions/workflows/module-packages.yml/badge.svg)](https://github.com/artepe/Open-HVACBridge-homeassistant/actions/workflows/module-packages.yml)
[![Core checks](https://github.com/artepe/Open-HVACBridge-homeassistant/actions/workflows/openlvi-core.yml/badge.svg)](https://github.com/artepe/Open-HVACBridge-homeassistant/actions/workflows/openlvi-core.yml)
[![MIT License](https://img.shields.io/badge/license-MIT-2563eb.svg)](LICENSE)
[![Home Assistant](https://img.shields.io/badge/platform-Home%20Assistant-18bcf2.svg)](https://www.home-assistant.io/)

</div>

---

Open HVAC is an open-source umbrella project for connecting heat pumps,
heating controllers, ventilation equipment and building automation to
Home Assistant via **local interfaces where technically supported**.
The OpenLVI Bridge integration is its multi-vendor core; other integrations
ship as independently installable modules.

The goal is to reduce unnecessary vendor-cloud dependencies, preserve
local ownership of equipment, and make device protocols openly testable.

> [!IMPORTANT]
> **Experimental project.** The modules have different verification levels.
> Ouman EH-800B legacy v0.1.2 has been physically tested on one controller,
> while OpenLVI multi-vendor drivers are largely simulator-tested.
> Mango Tuya Local supports a captured device profile, not every Tuya heat
> pump. Never assume a supported brand implies plug-and-play operation.

## Download modules

**Choose only what you need.** Each link opens a small, dedicated download
branch. Select **Code → Download ZIP** on that branch. These snapshots are
automatically maintained from the main project and contain no unrelated modules.

| Module | What you get | Validation | Download |
|---|---|---|---|
| **OpenLVI Bridge Core** | Ouman, Modbus, BACnet/IP, M-Bus, monitoring and selected controls | Experimental | [OpenLVI ZIP branch](https://github.com/artepe/Open-HVACBridge-homeassistant/tree/download/openlvi-bridge) |
| **Mango Tuya Local VILP** | Local Tuya 3.5; captured Mango heat pump profile and control panel | Beta / device-specific | [Tuya VILP ZIP branch](https://github.com/artepe/Open-HVACBridge-homeassistant/tree/download/mango-tuya-local) |
| **Ouman EH-800B Legacy** | Separate USB integration v0.1.2 | Hardware-tested on one device | [Ouman ZIP branch](https://github.com/artepe/Open-HVACBridge-homeassistant/tree/download/ouman-eh800b-legacy) |
| **CO₂ Blueprints** | Shelly 0–10 V auxiliary ventilation and CO₂ alerts | Experimental | [Blueprint ZIP branch](https://github.com/artepe/Open-HVACBridge-homeassistant/tree/download/co2-blueprints) |
| **OpenLVI SCADA** | Read-only isometric Lovelace visualization | Experimental | [SCADA ZIP branch](https://github.com/artepe/Open-HVACBridge-homeassistant/tree/download/scada-dashboard) |
| **ESP32-S3 Ouman Demo** | Prototype controller dashboard and examples | Prototype | [ESP32 ZIP branch](https://github.com/artepe/Open-HVACBridge-homeassistant/tree/download/esp32-s3-ouman-demo) |

**Other download options:** [GitHub Actions module ZIPs](https://github.com/artepe/Open-HVACBridge-homeassistant/actions/workflows/module-packages.yml)
(build artifacts), [versioned releases](https://github.com/artepe/Open-HVACBridge-homeassistant/releases) (when published)
and [SHA256 package checksums](docs/DOWNLOADS.md). See the
[complete downloads and installation guide](docs/DOWNLOADS.md).

> [!NOTE]
> Separate download branches are **not separate HACS repositories**.
> Install these modules manually as documented. The Tuya integration also
> has its own [upstream repository](https://github.com/artepe/chinaheatpump-tuya-local-home-assistant).
> The umbrella repository is not advertised as a single-click HACS integration.

## Getting started

1. [Pick a module](#download-modules) based on your actual device and interface.
2. Download its branch ZIP (or the named ZIP package from Actions/releases).
3. For Home Assistant integrations, copy the included
   **custom_components/<domain>** folder to **/config/custom_components/<domain>**.
   The OpenLVI package also includes its required Ouman USB protocol reader.
4. Back up Home Assistant, restart it, then configure the selected integration
   according to its device-specific guide. Start with **read-only checks**.
5. Confirm values on the physical equipment before using any control entity.

Installation guides: [OpenLVI](docs/OPENLVI_BRIDGE.md) ·
[Mango Tuya](docs/MANGO_TUYA_LOCAL.md) ·
[Ouman EH-800B](docs/STABLE_RELEASE_v0.1.2.md) ·
[SCADA](docs/OPENLVI_EXTENSIONS.md) ·
[ESP32](esp32_s3/README.md).

## Supported equipment

Support is tied to a **specific protocol and firmware**, not merely a brand name.

| Equipment | Interface / scope | Current validation |
|---|---|---|
| Ouman EH-800B | USB monitoring; legacy and experimental control paths | Legacy tested on one unit |
| Mango Energy R290 heat pump | Captured Tuya 3.5 profile with 770 parameter routes | Partial device evidence; other routes experimental |
| Ouman EH-800, A203, S203, C203, H23 | HTTP / limited model-specific Modbus profiles | Experimental |
| Swegon CASA Genius, Danfoss ECL, Regin Corrigo | Documented Modbus subsets | Automated tests only |
| BACnet/IP and wired M-Bus devices | Selected read-only discovery / telemetry | Experimental |
| Vallox, Siemens, Honeywell, NIBE, Uponor, Tosibox and others | Candidate integrations and/or site-specific maps | Research; not universal plug-and-play |

For exact point maps, limitations and references, read the
[engineering reference](docs/ENGINEERING_REFERENCE.md),
[manufacturer catalog](docs/FINLAND_BUILDING_AUTOMATION_CATALOG.md) and
[register/source map](docs/REGISTER_AND_CONTROL_SOURCE_MAP.md).

## Architecture

- **main** — reviewed source of truth for all modules and documentation.
- **feature/*** — development and testing branches; open pull requests to main.
- **download/*** — automatically generated, isolated module snapshot branches.
- **modules/catalog.json** — explicit allowlist controlling what each ZIP contains.
- **tools/package_modules.py** — reproducible standalone ZIPs and SHA256 manifest.
- **GitHub Actions** — validates every package, publishes download branches
  from main and attaches standalone ZIPs to version-tagged releases.

[Architecture and contribution rules](docs/ARCHITECTURE.md) ·
[Module catalogue](modules/catalog.json) ·
[Downloads](docs/DOWNLOADS.md)

## Security and project scope

Local-first does not mean every product is automatically offline: some devices
need a provisioned local key or a separately validated physical interface.
Do **not** expose raw controller ports directly to the internet.
Keep manufacturer frost, pressure, fire, pump and overheat protection active;
do not let Home Assistant replace safety-rated control.

The project **does not bundle cloud-dependent EZVIZ camera proxies**.
See [Security](SECURITY.md) for vulnerability reporting and safe deployment.

## Contribute

Hardware testers, automation specialists and developers are welcome.
Please provide the precise device model, firmware, interface, redacted logs
and reproduction steps. Unsupported functions should remain read-only.

[Report an issue](https://github.com/artepe/Open-HVACBridge-homeassistant/issues) · [Contributing guide](CONTRIBUTING.md) ·
[Changelog](CHANGELOG.md) · [MIT license](LICENSE)

<sub>Independent community project. Not affiliated with or endorsed by device manufacturers.</sub>
