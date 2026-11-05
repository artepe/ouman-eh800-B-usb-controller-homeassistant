# Open HVAC architecture

## Design goals

1. **Local-first:** prefer LAN, USB and openly documented field protocols.
   Clearly distinguish local operation from cloud-based provisioning.
2. **Independent components:** a Tuya change must not modify the Ouman
   controller, ventilation blueprints or SCADA.
3. **Read-only by default:** unknown register maps must never authorize
   control writes, and native equipment safety remains active.
4. **Measured compatibility:** distinguish a simulated test from physical
   acceptance on the exact model and firmware.
5. **Small downloadable modules:** only allowlisted files reach download
   packages and distribution branches.

## Repository layout

    custom_components/
      openlvi/                 Experimental multi-vendor Home Assistant integration
      ouman_eh800/             Separate EH-800B USB reader/legacy integration
      mango_tuya_local/        Independent local Mango heat-pump integration
    blueprints/automation/openlvi/
    www/                       Optional Lovelace visualization
    esp32_s3/                  Microcontroller demo
    modules/catalog.json       Package allowlist and status metadata
    tools/package_modules.py   Deterministic ZIPs and SHA256 manifest
    tools/sync_download_branches.py
    docs/                      Device and installation instructions

## Branch strategy

| Branch | Function | Maintenance |
|---|---|---|
| main | Reviewed single source of truth | Pull requests |
| feature/* | New devices and experimental code | Review, test, merge to main |
| download/* | One small module per branch | Automated copies; no manual edits |
| stable/* | Previously validated/pinned versions | Never silently overwrite |

The package workflow validates each module on pull requests and main pushes.
When main passes it refreshes the distribution branches, with their
individual Git commit history preserved. A version tag starting with v
publishes named module ZIPs and checksums as GitHub Release assets.

Only the distribution-sync and tagged-release jobs require write permissions.
The package validation job is read-only. Untrusted PRs cannot publish
branches or releases.

## Adding a new module

1. Develop on a feature branch, defining the exact device, firmware,
   protocol, safety limits and validation status.
2. Keep a separate, uniquely named Home Assistant integration domain.
3. Review and add only necessary files to modules/catalog.json.
4. Provide a working installation guide, tests, and clear physical
   verification limitations. Never commit passwords or device local keys.
5. Run module tests and the ZIP packager, then open a pull request to main.
6. The main workflow will generate the download branch automatically.
   Do not modify download branches by hand.

## Important boundaries

The OpenLVI package carries the legacy Ouman reader as a USB protocol
dependency; only one integration may actively poll a given serial port.
Mango Tuya Local has its own setup flow and dashboard, not a combined
OpenLVI wizard. The multi-domain umbrella repository is not advertised
as a single-click HACS integration; dedicated repos are preferable for
individual HACS distributions.

All live installations must preserve native frost, pump, pressure,
over-temperature, fire and ventilation safeguards. Modbus, BACnet and
unsecured local HTTP ports must never be exposed publicly.

EZVIZ cloud camera components are deliberately outside this distribution.
