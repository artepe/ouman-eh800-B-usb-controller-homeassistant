# Ouman EH-800B / EH-800 USB → Home Assistant

**Official stable version: v0.1.2** · **GitHub default branch: `main`** · **Tested on a physical EH-800B**

[Stable v0.1.2 installation](docs/STABLE_RELEASE_v0.1.2.md) · [Stable source branch](https://github.com/artepe/ouman-eh800-B-usb-controller-homeassistant/tree/stable/v0.1.2) · [Lovelace dashboard](examples/lovelace-ouman-l1-dashboard.yaml) · [Known PID issues](docs/PID_KNOWN_ISSUES.md)

> **SUOMEKSI:** Projektin virallinen ja aiemmin oikealla Ouman EH-800B -laitteella toimivaksi todettu versio on **v0.1.2**. Asenna `main`- tai `stable/v0.1.2`-haarasta. Keskeneräisiä kokeiluversioita **ei julkaista virallisina asennuksina**. Kaikkien anturien merkitystä ei ole tunnistettu. **Älä muuta PID-arvoja 56/57/58** toimivassa lämmitysjärjestelmässä: niiden muokkaamisen yhteydessä havaittiin poikkeavaa venttiilitoimintaa. Varmista asennuksen jälkeen mittausten *tuoreet* arvot kohdasta Developer Tools → States.

> **ENGLISH:** The official stable Home Assistant integration is **v0.1.2**, the last version reported working with the project's physical EH-800B. Experimental versions are not supported for live heating control. Avoid changing PID properties 56/57/58 because abnormal valve behaviour was observed during testing. Check fresh live measurements after installation.

## What is this?

An independent, open-source Home Assistant integration communicating with the **Ouman EH-800 / EH-800B USB service protocol** directly over a **USB Mini-B cable** from a Raspberry Pi / Home Assistant host. No cloud or separate Ethernet/Modbus gateway is required.

**Author:** Petteri Miikkael Arte · © 2026 · **License:** MIT  
Not affiliated with or endorsed by Ouman Oy.

## Official v0.1.2 features

- Direct USB CDC-ACM service-port communication (tested USB VID:PID `eb03:0920`).
- A set of **28 sensor entities** created from a single `MEASUREMENTS` response, polled every **15 seconds**. Some channels remain generically named because their meanings are not verified.
- L1 heating configuration exposed through Number entities; property writes use `SET PROPERTY` and serialized access to the USB port.
- An example Lovelace L1 dashboard.
- Simple manual Home Assistant installation through YAML. **This stable version is not a HACS/config-flow installation.**

### Home Assistant installation

Copy the folder `custom_components/ouman_eh800` from the [official stable source](https://github.com/artepe/ouman-eh800-B-usb-controller-homeassistant/tree/stable/v0.1.2/custom_components/ouman_eh800) into:

```text
/config/custom_components/ouman_eh800
```

Confirm the correct path for your USB-connected Ouman. The path used on the tested controller was:

```text
/dev/serial/by-id/usb-OUMAN_Ouman_EH-800-if00
```

In `configuration.yaml`, add the following to any existing `sensor:` and `number:` sections (do **not** duplicate top-level YAML keys):

```yaml
sensor:
  - platform: ouman_eh800
    port: /dev/serial/by-id/usb-OUMAN_Ouman_EH-800-if00

number:
  - platform: ouman_eh800
    port: /dev/serial/by-id/usb-OUMAN_Ouman_EH-800-if00
```

Validate the configuration with `ha core check` and restart Home Assistant if it succeeds. Verify current readings in **Developer Tools → States**; old graphs can still show history after a sensor has stopped reporting.

Detailed instructions and release status: [**Official stable release v0.1.2**](docs/STABLE_RELEASE_v0.1.2.md).

## Optional ESP32-S3 Wi-Fi dashboard (experimental)

Prefer a standalone ESP32-S3 instead of a Raspberry Pi? See the **[ESP32-S3 Arduino project and setup guide](esp32_s3/README.md)** or the **[Finnish ESP32-S3 instructions](esp32_s3/README.fi.md)**.

- Independent Wi-Fi access point **`OUMAN-ESP32`** and browser dashboard at **http://192.168.4.1/** (local connection only).
- Optional MQTT Home Assistant sensor discovery; attempts to read the USB service port through USB OTG Host.
- **Firmware and Wi-Fi have been user-tested, but physical ESP32-S3 ↔ EH-800B USB readings and curve writes are not yet verified end-to-end.** Heating-curve writes are disabled by default; do not use unverified controls on live heating systems.
- The existing stable **v0.1.2** Home Assistant USB integration is unchanged. The ESP32-S3 alternative is not a replacement stable release.

Quick links: [Arduino sketch](esp32_s3/Ouman_EH800_S3_Dashboard/Ouman_EH800_S3_Dashboard.ino) · [English guide](esp32_s3/README.md) · [Suomenkielinen ohje](esp32_s3/README.fi.md)

## Safety and known limitations

> [!WARNING]
> The stable version has **writable** PID entities for properties **56 (P), 57 (I), 58 (D)**. Abnormal valve/controller behaviour was observed after PID experimentation on one EH-800B. **Do not modify these properties on a live system.** Property **92** controls the real valve position and also requires care. This software is not a safety-rated heating controller.

- The original v0.1.2 implementation does **not** include the experimental `ouman_eh800.restore_original` service. Do not assume that later experimental restore tools are available in this stable release.
- The stable implementation does **not** claim all 28 measurement channels are semantically identified or all saved controller properties can be queried live.
- The official `main` branch keeps the tested v0.1.2 integration code. A later prototype caused multiple `unavailable` readings on the author's real installation and was not merged into `main`.
- Back up your existing HA configuration and your own controller-specific settings before any changes.

## Ouman behaves abnormally? / Oumanin saadin sekoilee?

If Ouman settings have demonstrably become corrupted, **supervised
manual recovery from a verified backup of the same controller may be
recommended as a last-resort repair**. See
[controller recovery and backups](docs/RESTORE_AND_BACKUPS.md).

Jos saadin toimii poikkeavasti ja asetusten vioittuminen on varmistettu,
tarkistetusta oman laitteen varmuuskopiosta palautus voi olla perusteltu
korjaustoimenpide. **Pelkkä menoveden ja pyynnin ero ei osoita
saativikaa:** tarkista ensin lammonlahde, virtaus, venttiili ja
anturit. Tahan on valmis [kerran paivassa tarkistava ilmoitusautomaatio](examples/automation-ouman-l1-daily-deviation-alert.yaml),
joka **ei tee palautusta automaattisesti**. Kokeellinen
`ouman_eh800.restore_original` ei sisally viralliseen v0.1.2-versioon.

## Protected manual restore action (experimental, opt-in)

A [protected restore implementation](https://github.com/artepe/ouman-eh800-B-usb-controller-homeassistant/tree/feature/manual-restore-protected-20261024) adds
`ouman_eh800.restore_original` for manually recovering confirmed controller
configuration corruption from a **verified backup of the same EH-800B**.
It is **not part of the tested v0.1.2 / main release** and has not been
validated on real hardware in this version. The service is unavailable
unless `ouman_eh800: enable_manual_restore: true` is set in YAML. Its default
mode only validates the backup and logs its SHA-256 without writing to USB;
a real restore requires a matching SHA-256, explicit confirmation and
`dry_run: false`.

See [full backup and restore instructions](docs/RESTORE_AND_BACKUPS.md).
**Never use it as an unattended daily reset merely because the supply target
has not been reached.** The [daily deviation example](examples/automation-ouman-l1-daily-deviation-alert.yaml)
stays notification-only.

## Development and research

Additional low-level protocol notes and historical research are in [docs/](docs/), including [USB protocol research](docs/USB_PROTOCOL_RESEARCH.md) and [PID observations](docs/PID_KNOWN_ISSUES.md). These are research material, **not a second officially supported Home Assistant version**. For reverse engineering, isolate hardware testing from a live heating system; never use unverified property writes as a discovery method.

## Dashboard

A manual-card example is available at [examples/lovelace-ouman-l1-dashboard.yaml](examples/lovelace-ouman-l1-dashboard.yaml). Confirm entity IDs on your installation, as Home Assistant may add suffixes to conflicting names.

---

**Release policy:** `main` and `stable/v0.1.2` represent the official stable Home Assistant integration. New experimental work must pass real-hardware sensor and control tests before being considered for a new stable release.
