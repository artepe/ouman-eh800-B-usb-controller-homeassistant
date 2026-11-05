# Download Open HVAC modules

Open HVAC separates **development source** from **module distribution**.
Choose one module without downloading the complete project.

## Download a single module branch

Each maintained download branch contains only the named module's files,
its README and MIT license. Select the branch below or use the direct ZIP.

| Module | Source branch | Direct ZIP |
|---|---|---|
| OpenLVI Bridge + Ouman USB reader | [Branch](https://github.com/artepe/Open-HVACBridge-homeassistant/tree/download/openlvi-bridge) | [ZIP](https://github.com/artepe/Open-HVACBridge-homeassistant/archive/refs/heads/download/openlvi-bridge.zip) |
| Mango Tuya Local VILP | [Branch](https://github.com/artepe/Open-HVACBridge-homeassistant/tree/download/mango-tuya-local) | [ZIP](https://github.com/artepe/Open-HVACBridge-homeassistant/archive/refs/heads/download/mango-tuya-local.zip) |
| Ouman EH-800B legacy | [Branch](https://github.com/artepe/Open-HVACBridge-homeassistant/tree/download/ouman-eh800b-legacy) | [ZIP](https://github.com/artepe/Open-HVACBridge-homeassistant/archive/refs/heads/download/ouman-eh800b-legacy.zip) |
| CO2 auxiliary ventilation blueprints | [Branch](https://github.com/artepe/Open-HVACBridge-homeassistant/tree/download/co2-blueprints) | [ZIP](https://github.com/artepe/Open-HVACBridge-homeassistant/archive/refs/heads/download/co2-blueprints.zip) |
| OpenLVI SCADA | [Branch](https://github.com/artepe/Open-HVACBridge-homeassistant/tree/download/scada-dashboard) | [ZIP](https://github.com/artepe/Open-HVACBridge-homeassistant/archive/refs/heads/download/scada-dashboard.zip) |
| ESP32-S3 Ouman demo | [Branch](https://github.com/artepe/Open-HVACBridge-homeassistant/tree/download/esp32-s3-ouman-demo) | [ZIP](https://github.com/artepe/Open-HVACBridge-homeassistant/archive/refs/heads/download/esp32-s3-ouman-demo.zip) |

These branches are generated from main by the
[module workflow](../.github/workflows/module-packages.yml).
Use main for development and pull requests. Branch ZIPs are moving snapshots,
not immutable tagged releases.

## Download standalone ZIP packages from GitHub Actions

1. Open [Open HVAC module packages](https://github.com/artepe/Open-HVACBridge-homeassistant/actions/workflows/module-packages.yml).
2. Select a successful run for main and open the artifacts section.
3. Download the artifact called **open-hvac-module-downloads**.
4. Extract the outer artifact, then choose only the required standalone module ZIP.
5. Verify the selected ZIP against the included SHA256SUMS.txt when possible.

Build artifacts are temporary (configured retention: 30 days) and may require
a GitHub login. [Versioned GitHub Releases](https://github.com/artepe/Open-HVACBridge-homeassistant/releases)
receive separate ZIP files and checksum manifests when a maintainer creates
a version tag beginning with v.

## Installation destinations

- **OpenLVI Bridge:** extract custom_components/openlvi and the included
  custom_components/ouman_eh800 reader under /config/custom_components/.
  Do not configure two USB pollers on one port.
- **Mango Tuya Local:** extract custom_components/mango_tuya_local under
  /config/custom_components/. Requires the exact supported Tuya profile,
  device IP, local ID/key and separate setup in Devices & Services.
- **Ouman legacy:** extract custom_components/ouman_eh800 to
  /config/custom_components/; follow [legacy YAML instructions](STABLE_RELEASE_v0.1.2.md).
- **CO2 blueprints:** copy blueprints/automation/openlvi to
  /config/blueprints/automation/openlvi. Supplemental ventilation only.
- **SCADA:** copy www/openlvi-scada-card.js to /config/www, register a
  dashboard JavaScript resource and adapt the included example entity IDs.
- **ESP32-S3:** Arduino sketch and documentation for separate hardware;
  not a Home Assistant integration directory.

Before changing Home Assistant, back up your configuration and keep native
safety functions active. Installation of a component does not prove device
compatibility or safety. Do not upload local keys, site addresses or passwords.

## Build your own ZIPs

From the checked-out main repository:

    python3 tools/package_modules.py --out dist
    python3 tools/package_modules.py --out dist --verify
    python3 -m unittest discover -s tests -p 'test_module_distribution.py' -v

The packager reads [the module catalog](../modules/catalog.json), which
explicitly lists allowed paths. Hidden files, symlinks and traversal paths
are rejected; deterministic timestamps and SHA256 checksums are generated.
The GitHub Actions branch publisher only accepts the current main commit.

## HACS and cloud dependencies

A download branch is not a separate HACS repository. The umbrella project
documents manual installation; [Mango Tuya Local upstream](https://github.com/artepe/chinaheatpump-tuya-local-home-assistant)
also maintains its own HACS integration source. Local operation requires
a compatible device protocol; provisioning the local key may not be offline.

No EZVIZ cameras or cloud proxy integration is included in this project.
