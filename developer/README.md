# DEVELOPER USB LAB — unsafe research version

> [!IMPORTANT]
> **Recommended "hardcore" edition for USB reverse engineers:** this Developer USB Lab exposes the complete **raw responses returned by the supported service commands**, including HEX and binary `TYPE objects.dat` capture tools. It intentionally does **not** claim to decode every measurement or expose all 269 controller properties live. **Do not use this developer branch as an unattended Home Assistant heating controller.**
>
> The newer HA v0.2.2 prototype caused `unavailable` sensor states in the project's actual EH-800B hardware trial (2026-10-10); therefore **v0.2.2 is a non-production experiment ("dummy/prototype")**, not a usable upgrade. It is real USB code, **not a simulated data generator**. The observed failure's root cause remains unverified. For a known-working HA setup, use the earlier local v0.1.2 backup.


This directory/branch is specifically for **bench research, NOT production
Home Assistant**. Source code is open and usable without Home Assistant.
All 269 known property IDs can be investigated with the standalone
`tools/developer_console.py`; the controller may reject unknown properties.
No known-safe firmware flashing procedure exists.

## Important experimental findings

During real EH-800B experiments, changing P/I/D properties **56 / 57 / 58**
coincided with abnormal valve-control behaviour and a possible controller
crash or instability. **The precise cause has not been isolated.**
These are **blocked in the production Home Assistant number platform**.
The lab CLI requires an extra `--allow-pid` acknowledgement for those IDs.
Property 92 is manual valve position and changes the physical actuator.

A successful `SET PROPERTY` response is not proof that the **physical LCD
is current**. When changing a five-point heating-curve value through USB,
press **ESC once** on the controller and navigate to the heating-curve menu
again to see the updated value, based on the tested EH-800B.

## Read-only example

After `pip install pyserial==3.5`:

```bash
python tools/developer_console.py --port /dev/serial/by-id/usb-OUMAN_Ouman_EH-800-if00 read MEASUREMENTS
```

This prints the original RX bytes as hexadecimal and readable Latin-1 text.

## Single-property write, intentionally hard to activate

```bash
python tools/developer_console.py --port /dev/serial/by-id/usb-OUMAN_Ouman_EH-800-if00 write 67 910 \
  --snapshot /config/ouman_properties.txt \
  --confirm I_ACCEPT_CONTROLLER_DAMAGE_RISK
```

You must also type `WRITE 67` interactively. No automatic retries.
Do not use against an unattended heating system. Backups and settings
must be taken from the **same** physical Ouman controller.

For PID writes, an **additional** `--allow-pid` is required; this is
provided exclusively for informed developer investigation on a safe bench.
It is not an endorsement of testing on the live heating installation.
`--allow-unbacked` lifts the known-snapshot-ID check (research only).
There is no unrestricted HA UI slider and no firmware-flashing command.

## Original reverse-engineering tool

`research/eh800b_usb_tool_original.py` is a verbatim preserved historical
source supplied by the project author. It contains explorations of
`TYPE objects.dat`, HEX output, local file patching and a `FIRMWARE`
probe. That last probe **must not be used** on a running controller:
actual firmware/bootloader semantics are unknown. Local patched binary
files are never automatically uploaded to the controller.

## Raw files

The actual `objects.dat` and `ouman_properties.txt` are per-device
private backups; this branch does **not** contain those binary contents.
Use the read-only tools to make your own export, inspect identifiers and
confidential settings, and **never publish unreviewed captures**.

This branch intentionally keeps the production UI's PID writes blocked.
Switching Git branches does not bypass Home Assistant's normal controls.
