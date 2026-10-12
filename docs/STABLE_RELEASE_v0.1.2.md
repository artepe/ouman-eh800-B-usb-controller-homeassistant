# Stable release v0.1.2 — Ouman EH-800B / EH-800 USB for Home Assistant

**Official stable source:** `main` and the pinned `stable/v0.1.2` branch.

**Status (12 October 2026):** v0.1.2 is the last version reported working with the project's physical EH-800B controller. This designation is based on that installation, **not** a multi-device compatibility certification. Newer experimental code has not been promoted to the stable integration.

## Included in the stable integration

- Direct USB CDC-ACM communication between Home Assistant and an EH-800B using the service Mini-USB connection.
- A single `MEASUREMENTS` request per poll, normally every **15 seconds**.
- **28 indexed measurement sensor entities**, with the subset of channel meanings documented/identified (the others retain generic names).
- Fifteen L1 Number entities, with USB property-write support and shared locking of serial access.
- YAML platform-based installation without a configuration flow. Requires `pyserial==3.5`.
- The example Lovelace dashboard is provided in `examples/lovelace-ouman-l1-dashboard.yaml`.

## Important safety limits

**Do not change PID parameters 56 / 57 / 58 (P band, I time, D time)** on a live heating system. These Number entities are *writable* in v0.1.2; testing on one controller coincided with abnormal valve operation. Manual valve position (property 92) also changes the real valve. There is no automatic safety rollback.

The 28 data channels are not all fully decoded. The stable version has no `ouman_eh800.restore_original` action; do not try to invoke it after installing this stable branch. Recovery and protocol research documented elsewhere are **experimental** and not part of the supported stable installation. Always preserve your own controller settings before changing them.

## Installation

1. Copy `custom_components/ouman_eh800` from the **main** branch (or the pinned **stable/v0.1.2** branch) into `/config/custom_components/ouman_eh800` on Home Assistant.
2. Confirm the connected USB serial path in your installation. The tested path was `/dev/serial/by-id/usb-OUMAN_Ouman_EH-800-if00`.
3. Add these platforms to `configuration.yaml` (merge with any existing `sensor:` / `number:` definitions instead of duplicating the YAML keys):

```yaml
sensor:
  - platform: ouman_eh800
    port: /dev/serial/by-id/usb-OUMAN_Ouman_EH-800-if00

number:
  - platform: ouman_eh800
    port: /dev/serial/by-id/usb-OUMAN_Ouman_EH-800-if00
```

4. Run `ha core check`, then restart Home Assistant if the check succeeds.
5. Check the current sensor values in **Developer Tools → States**, not only historical Lovelace graphs. In this release the scan interval is 15 seconds.

## Version policy

- **v0.1.2:** official stable Home Assistant integration for the tested device.
- **Experimental / developer branches:** unsupported for unattended heating control. A later experimental build caused multiple `unavailable` sensors on real hardware and was **not merged into main**.
- Research notes remain accessible under `docs/`, but experimental functionality should not be mistaken for included stable features.

## Project links

- [Repository](https://github.com/artepe/ouman-eh800-B-usb-controller-homeassistant)
- [Stable branch](https://github.com/artepe/ouman-eh800-B-usb-controller-homeassistant/tree/stable/v0.1.2)
- [Known PID issues](PID_KNOWN_ISSUES.md)
- [Lovelace example](../examples/lovelace-ouman-l1-dashboard.yaml)

Independent community reverse-engineering project. Not affiliated with or endorsed by Ouman Oy. MIT license.
