# ESP32-S3 standalone USB/Wi-Fi dashboard for Ouman EH-800B

> **Experimental community firmware.** Separate from the official stable Home Assistant v0.1.2 USB integration in the repository root. The Arduino sketch has been reported to compile on an ESP32-S3 and its own Wi-Fi network has been tested. **Ouman USB Host data transfer and live write control have NOT been validated end-to-end on physical ESP32-S3 + EH-800B hardware.** Do not rely on this for critical heating or safety control.

[Suomenkieliset asennusohjeet](README.fi.md) · [Arduino sketch](Ouman_EH800_S3_Dashboard/Ouman_EH800_S3_Dashboard.ino)

## What does it do?

- Runs on an **ESP32-S3**, broadcasting its own protected **`OUMAN-ESP32` Wi-Fi network**, even without a home router.
- Serves a local **OUMAN CONTROL** dashboard at **http://192.168.4.1/**. There are monitoring and L1 heating-curve tabs, plus `/status` and `/measurements` JSON endpoints.
- Attempts to read the EH-800B USB CDC-ACM service interface with `MEASUREMENTS\n` at approximately 15-second intervals and display 28 values. Not all channel meanings are verified.
- Optionally connects to an existing Wi-Fi router and an MQTT broker to announce sensors via Home Assistant MQTT discovery. No Home Assistant is required to use the direct web dashboard.
- Includes **experimental heating-curve write code, disabled by default**. This is not a validated substitute for the controller's front panel or safety features.

## Files

- [`Ouman_EH800_S3_Dashboard/Ouman_EH800_S3_Dashboard.ino`](Ouman_EH800_S3_Dashboard/Ouman_EH800_S3_Dashboard.ino): full Arduino firmware, including the embedded web interface. **Only one .ino file is needed.**
- [`README.fi.md`](README.fi.md): detailed installation and troubleshooting in Finnish.

## Required hardware

1. ESP32-S3 board supporting **USB OTG host mode**.
2. A USB data cable for flashing the ESP32-S3 from a Mac/PC; preferably a dedicated programming/UART interface if the board has two USB connectors.
3. Ouman EH-800 / EH-800B USB Mini-B service-port cable.
4. A **powered USB hub or correct 5 V VBUS supply** for host-side USB, wired according to your board's pinout. The ESP32-S3 USB OTG D−/D+ signals use GPIO19/GPIO20 internally, but **not all breakout boards expose a correctly powered host connector**. Do not connect two 5 V supplies together or inject 5 V into an unknown pin.

Typical topology:

```text
Mac / PC --USB programming port--> ESP32-S3
                                      |
                         USB OTG HOST + powered hub
                                      |
                                USB Mini-B cable
                                      |
                               Ouman EH-800B

Mac / phone --Wi-Fi "OUMAN-ESP32"--> http://192.168.4.1/
```

Do not connect the Raspberry Pi's existing direct USB Ouman integration and the ESP32-S3 simultaneously to the same service USB port. Choose one USB host.

## Flash using Arduino IDE (macOS)

1. Download this repository using GitHub **Code → Download ZIP**, unzip it, and open `esp32_s3/Ouman_EH800_S3_Dashboard/Ouman_EH800_S3_Dashboard.ino` in Arduino IDE 2.x. Allow Arduino IDE to create/rename the matching sketch directory if requested.
2. In **Boards Manager**, install **esp32 by Espressif Systems** (developed against **3.3.12**). In **Library Manager**, install **PubSubClient** by Nick O'Leary. The ESP32 core supplies `WiFi.h`, `WebServer.h`, `USBHost.h` and `USBHostSerial.h` in the tested toolchain.
3. Set **Tools → Board → ESP32S3 Dev Module**. Select the USB serial port currently visible under **Tools → Port** (e.g. `/dev/cu.usbmodem...`); do not assume the port number stays the same.
4. Before upload, edit the **`AP_PASSWORD`** in the sketch to a unique 8–63-character password. The default `Ouman12345` is **only a demonstration password**.
5. USB Host builds may require **USB CDC On Boot = Disabled** and the correct USB OTG/TinyUSB mode, depending on your board and ESP32 package. If the USB serial programming interface disappears after a host sketch, enter ROM download mode by holding **BOOT**, pressing/releasing **EN/RESET**, then releasing BOOT; select the reappearing port and upload.
6. Click **Verify** and **Upload**. The earlier `Sketch uses ...` message is only compilation; flashing succeeds only when the tool reports a successful write/reset. Close Serial Monitor if the port is busy.
7. Restart the ESP32-S3 and join **`OUMAN-ESP32`** from your laptop/phone. Open **http://192.168.4.1/** in a browser. No-internet warnings are normal for a direct device-only AP.
8. First test **http://192.168.4.1/status**; the web UI can work without an attached Ouman. The `wifi` field in `/status` means the optional **router/station connection**; it can say `false` while the ESP32 AP is operating normally.
9. Only then attach Ouman through a properly powered USB Host connection and verify fresh, changing values. A mounted connection alone does not prove the 28 measurements are correct.

## Optional home Wi-Fi + Home Assistant MQTT

Leave `WIFI_SSID = "YOUR_WIFI_NAME"` untouched to use the direct AP only. For a router/MQTT setup, edit `WIFI_SSID`, `WIFI_PASSWORD`, `MQTT_HOST`, `MQTT_PORT`, `MQTT_USER` and `MQTT_PASSWORD` to match your network/broker, then reflash. MQTT discovery uses `homeassistant/sensor/.../config` topics and needs a reachable MQTT broker. The direct AP remains enabled.

**Do not commit personal Wi-Fi/MQTT credentials to this repository.**

## Heating-curve adjustments — disabled by default

The curve page displays **empty inputs, not reliably read-back controller settings**. The only hard-coded writable-property allowlist is 67/69/71/73/75. The sketch requires `ENABLE_CURVE_WRITES` to be deliberately set to `true`, a new `WRITE_PASSWORD` (12+ characters), a connected USB interface and request validation before it can submit a write. **Property 67 is the only listed curve write previously reported as tested on the physical controller; the other IDs are not confirmed.** A matching reply is only an acknowledgement, not independent readback. Changing live heating settings is **not recommended** until complete physical verification and a manual rollback plan exist.

No PID property 56/57/58 controls or valve manual-position property 92 controls are provided. Do not expose this HTTP web interface to the Internet or add router port forwarding.

## Troubleshooting

| Problem | Check |
|---|---|
| `OUMAN-ESP32` not found | Was **Upload** successful? AP password must have at least 8 characters. Press RESET. Confirm you flashed the **Dashboard** sketch, not the Wi-Fi-only test. |
| Mac cannot find the ESP32 USB port | Data-capable cable, correct board port, BOOT+EN download mode, close Serial Monitor, retry `ls /dev/cu.usb*`. |
| Wi-Fi connects but the site is blank | Open **http://192.168.4.1/** using **http**, not https. Try `curl -i http://192.168.4.1/status`. |
| Dashboard works but sensor data unavailable | Host VBUS power, board OTG pinout, powered hub, correct Mini-B USB cable, controller CDC mount. `/measurements` returns HTTP 503 when there are no fresh values. |
| Home Assistant MQTT entities missing | Enter router and MQTT settings, verify broker connection, and confirm new sensor values are actually arriving. |

## Support / validation state

- Compile: reported successful in Arduino IDE with Arduino-ESP32 3.3.12.
- Access-point Wi-Fi: reported to work by a user on ESP32-S3.
- Web dashboard: code included; independently validated hardware operation is not established here.
- Direct USB CDC host connection and curve writes: **experimental, not verified end-to-end**.

This firmware is offered **as-is**, for responsible bench testing. The main branch's existing Home Assistant **v0.1.2** USB integration remains the stable option.
