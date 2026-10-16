# Ouman EH-800B via ESP32-S3 USB Host -> Wi-Fi -> Home Assistant

**Experimental implementation; not yet verified with physical ESP32-S3 + Ouman EH-800B hardware.**

This directory includes:
- `ouman-eh800-s3.yaml`: ESPHome firmware configuration built on the third-party [ESP HA USB Gateway](https://github.com/ESDN83/esp-ha-usb-gateway) CDC-ACM USB-host bridge, pinned to commit `2c999927bdba5959aebbdfbc0e179c19564fdf95`.
- `test_ouman_tcp.py`: read-only smoke test, sending `MEASUREMENTS\n` to the Ouman over TCP port 8880.
- Transport modification in the **feature branch** `custom_components/ouman_eh800/ouman.py`: opt-in `socket://<IP>:8880` support, preserving the tested local USB serial path.

## Hardware

Use an ESP32-S3 with USB-OTG connected to GPIO19 (D-) and GPIO20 (D+). Use a correctly powered USB host hub/adapter that supplies 5V VBUS to the Ouman's USB interface. A generic ESP32-S3 board does **not** necessarily supply VBUS from its USB-C connector. Do not connect USB VBUS to the 3.3 V pin.

The third-party ESPHome USB gateway supports CDC-ACM, but **Ouman VID:PID eb03:0920 has not been tested** with this bridge.

## Flash

Use Home Assistant ESPHome Device Builder and paste `ouman-eh800-s3.yaml`. Fill ESPHome `secrets.yaml` with `wifi_ssid`, `wifi_password`, `api_encryption_key` (random Base64 32-byte key) and `ota_password`. Compile and flash by USB. When the S3 joins Wi-Fi, open `http://ouman-eh800-s3.local/` or its DHCP IP.

In the **USB gateway web UI** find the Ouman CDC device (`eb03:0920`), assign it TCP 8880, configure an admin password and IP allowlist **restricted to the Home Assistant host IP**, then Save/Reboot. Reserve the S3's address in DHCP.

The USB TCP port is **raw, not encrypted or authenticated**. Do not expose the device or port to the public internet, and keep it on a trusted/isolated LAN.

## Verify

```bash
python3 esp32_s3/test_ouman_tcp.py --host 192.168.10.50 --port 8880
```

This test sends **only** the read-only Ouman `MEASUREMENTS` command. A successful test reports 28 or more measurement lines.

## Home Assistant

Back up your existing integration file. Replace only `custom_components/ouman_eh800/ouman.py` with this feature branch's copy, then configure the YAML **sensor** platform:

```yaml
sensor:
  - platform: ouman_eh800
    port: "socket://192.168.10.50:8880"
```

Merge with existing `sensor:` platforms; do not duplicate top-level keys. Remove/comment out only the existing Ouman `number:` platform during initial testing; those writable entities can change real heating settings including PID (56/57/58) and valve position (92). The remote bridge can transport writes but is **not certified safe for heating control**. Do not test writes during initial deployment.

Run `ha core check`, then `ha core restart`, and verify live sensor values in Developer Tools -> States. The stable USB-connected v0.1.2 on `main` remains untouched.

## Limitations

An ESP32-S3 only forwards USB serial bytes; Python measurement parsing and sensors still run on the HA host. This is not an ESPHome-native Ouman sensor decoder or a standalone firmware binary. ESPHome build and physical hardware interoperability have not yet been validated. The TCP bridge accepts one client per port, so do not poll the port concurrently from both the smoke test and Home Assistant.

See [Finnish detailed guide](README.fi.md).
