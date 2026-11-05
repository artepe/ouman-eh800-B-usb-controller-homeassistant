# Contributing to Open HVAC

Open HVAC welcomes Home Assistant developers, automation professionals
and owners of test equipment. All contributions should support independently
maintainable, local-first modules.

## Branches and review

- Start changes in a **feature/** branch and open a pull request to **main**.
- **download/** branches are generated module distributions; do not edit them.
- Historical **stable/** branches represent pinned hardware-tested versions.
- New modules must have their own device domain, documentation and status in
  [modules/catalog.json](modules/catalog.json).
- The module ZIP workflow checks that distribution packages include only the
  explicitly approved source folders.

## Device support acceptance

1. Identify manufacturer, model, exact firmware/application key, communication
   interface and documentation source. Redact credentials and site addresses.
2. Keep each manufacturer profile separate. Do not assume Modbus offsets
   or signal scaling from another firmware version.
3. Make unknown commands and user-supplied maps **read-only**. Do not add PID,
   valve, pump, frost override or alarm bypass commands without controlled
   physical verification, a safe rollback procedure and reviewer approval.
4. Test both normal and disconnected-device states with mocks, then verify
   real sensor values against the physical controller display.
5. Label untested models and registers **experimental** rather than implying
   that adding a manufacturer name equals hardware support.
6. Do not change the tested Ouman v0.1.2 driver as part of unrelated features.

## Run local checks

    python3 -m compileall -q custom_components/openlvi tools
    python3 -m unittest discover -s tests -p 'test_*profiles.py' -v
    python3 -m unittest discover -s tests -p 'test_openlvi_extended.py' -v
    python3 -m unittest discover -s tests -p 'test_module_distribution.py' -v
    python3 tools/package_modules.py --out dist
    python3 tools/package_modules.py --out dist --verify
    node --check www/openlvi-scada-card.js

GitHub Actions tests packages and source before updating download branches.
Tests do not certify physical HVAC safety or interoperability.

## Source map

- custom_components/openlvi/ — experimental multi-vendor bridge.
- custom_components/mango_tuya_local/ — independent LAN Tuya heat pump.
- custom_components/ouman_eh800/ — legacy Ouman EH-800B USB.
- blueprints/ and www/ — optional control templates and SCADA.
- esp32_s3/ — independent hardware demo.
- modules/ — package catalog and distribution policies.
- docs/ — detailed implementation, installation and warnings.

See [Architecture](docs/ARCHITECTURE.md),
[Downloads](docs/DOWNLOADS.md) and [Security](SECURITY.md).
