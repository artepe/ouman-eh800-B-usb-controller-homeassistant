# Contributing to OpenHVAC Bridge

Contributions are welcome for local Home Assistant integrations, safe
device-specific register maps, BACnet object lists and verified diagnostics.

## Before submitting changes

1. Open an issue identifying **manufacturer, model, firmware/application key,
   interface module and exact documentation source**. Do not share customer
   credentials or private site topology.
2. Keep vendor profiles separate. Never infer register meaning from a
   different firmware, module or Modbus address base.
3. New/unknown vendor points must default to **read-only**. Never add manual
   valve, pump, freeze protection, alarm override or PID writes without
   isolated physical bench validation, a reversible test plan and reviewer
   approval. Custom JSON/XML/CSV imports cannot authorize writes.
4. Use mock transport tests for scalings, signed 16/32-bit values, holding
   versus input registers, disconnected device handling and invalid input.
5. Document hardware wiring, physical communications modules, polling
   limits, firmware compatibility, and measurements *actually* checked
   against the device display. Describe untested behaviour as experimental.
6. Do not modify `custom_components/ouman_eh800` v0.1.2 in unrelated
   contributions; it is the separate tested legacy implementation.

## Local checks

```bash
python3 -m compileall -q custom_components/openhvac tools
python3 -m unittest discover -s tests -p 'test_*profiles.py' -v
python3 -m unittest discover -s tests -p 'test_openhvac_extended.py' -v
python3 -m unittest discover -s tests -p 'test_openhvac_robustness.py' -v
node --check www/openhvac-scada-card.js
```

Home Assistant level tests (config flow, setup retry, sensor classes;
all transports faked, no hardware):

```bash
python3 -m pip install -r tests_ha/requirements.txt
python3 -m pytest tests_ha
```

GitHub Actions runs these tests automatically on pull requests and `main`.
Unit tests alone do **not** certify Home Assistant startup, BACnet/IP binding
or physical meter/controller interoperability.

## Project map

- `custom_components/openhvac/`: experimental multi-vendor HA integration.
- `custom_components/ouman_eh800/`: legacy tested Ouman EH-800B USB.
- `docs/`: model/firmware references, installation, known limitations.
- `examples/` and `www/`: Lovelace examples and SCADA card.
- `tools/`: point-map import utility; no blind network probing.
