# Ouman EH-800B / EH-800 USB Home Assistant — open USB protocol

> [!CAUTION]
> **VERSION STATUS — 2026-10-10 / reported hardware regression**
>
> **v0.2.2 = experimental "dummy / prototype" release, NOT recommended for production.** "Dummy" here means **unfinished/test version**, **NOT simulated or fake measurements**: it connects to real USB hardware. On the author's actual EH-800B/Home Assistant installation, installing v0.2.2 was followed by `unavailable` states for the outdoor temperature, supply temperature and other Ouman sensors, including in Developer Tools → States. Home Assistant's configuration check passed, but the live measurements did **not** work reliably. Root cause is **not yet established**. Do not use v0.2.2 as a reliable heating-control integration.
>
> **For ordinary Home Assistant use:** prefer the earlier **v0.1.2 installation verified working on the tested controller**, or restore a verified local backup. Note that v0.1.2's PID controls can be writable: avoid PID changes.
>
> **For hardcore developers / full raw-data research:** use the **[Developer USB Lab branch](https://github.com/artepe/ouman-eh800-B-usb-homeassistant/tree/developer/usb-unrestricted-lab)** and the [original low-level USB tool](https://github.com/artepe/ouman-eh800-B-usb-homeassistant/blob/developer/usb-unrestricted-lab/research/eh800b_usb_tool_original.py). They expose the **available raw USB responses and HEX bytes** (`MEASUREMENTS`, `TYPE objects.dat`, etc.) independently of Home Assistant, and a separate lab CLI can investigate property IDs with explicit write confirmations. This is the recommended version **for reverse-engineering on a controlled test bench**, **not** for unattended heating. All 28 channels may be captured raw; that does **not** mean every channel or all 269 properties have verified meanings or that the full property set is live-readable.
>
> **Suomeksi:** Uusin **v0.2.2 on keskeneräinen kokeiluversio ("dummy")**: oikealla EH-800B:llä moni anturi jäi `unavailable`-tilaan. Toimivaan lämmitysohjaukseen suositellaan aiempaa testattua v0.1.2-asennusta. **Edistyneille USB-protokollan tutkijoille** suosittelemme erillistä Developer USB Lab -versiota, josta raakavastaukset ja HEX-data ovat tutkittavissa. Se ei ole turvallinen tuotantoversio.


Independent reverse-engineering project for the **Ouman EH-800 and EH-800B USB protocol**, providing local USB CDC communication directly between the heating controller and Home Assistant.

**Home Assistant reads the Ouman directly through the Raspberry Pi USB port** using a USB Mini-B cable — no Ethernet interface, Modbus gateway, cloud connection, or separate protocol converter is required.

**Author:** Petteri Miikkael Arte  
**Copyright © 2026 Petteri Miikkael Arte**  
**License:** MIT

Not affiliated with or endorsed by Ouman Oy.

> **Project variants and research source (October 2026):** [stable v0.1.2 main](https://github.com/artepe/ouman-eh800-B-usb-homeassistant/tree/main) · [merged restore + safe controls v0.2.2 review branch](https://github.com/artepe/ouman-eh800-B-usb-homeassistant/tree/feat/usb-async-safe-config-20261010) · [developer USB console / unrestricted property research](https://github.com/artepe/ouman-eh800-B-usb-homeassistant/tree/developer/usb-unrestricted-lab).
>
> **Raw USB protocol:** [ASCII commands & HEX](https://github.com/artepe/ouman-eh800-B-usb-homeassistant/blob/feat/usb-async-safe-config-20261010/docs/USB_PROTOCOL_RESEARCH.md) · [standalone Python library](https://github.com/artepe/ouman-eh800-B-usb-homeassistant/blob/feat/usb-async-safe-config-20261010/docs/STANDALONE_LIBRARY.md) · [original USB research script](https://github.com/artepe/ouman-eh800-B-usb-homeassistant/blob/developer/usb-unrestricted-lab/research/eh800b_usb_tool_original.py) · [recovery](https://github.com/artepe/ouman-eh800-B-usb-homeassistant/blob/feat/usb-async-safe-config-20261010/docs/RESTORE_AND_BACKUPS.md).
>
> **Physical display refresh:** USB writes can take effect without immediately refreshing an already-open EH-800B menu. Press **ESC once**, then reopen the heating-curve settings. The P/I/D settings were linked to abnormal valve behaviour in one installation; experimental v0.2.2 blocks PID writes in the ordinary UI. Other USB-equipped Ouman models **may** share the protocol, but this is unverified.

## Project status / significance

This project implements the **USB service protocol used by the Ouman EH-800 / EH-800B family**. Home Assistant can communicate with the controller locally through the Raspberry Pi's USB port: live data can be read directly from the controller and confirmed configuration properties can be written back to the physical controller.

Current hardware reverse-engineering and write testing has been performed on an **EH-800B**. The integration uses the controller's USB CDC-ACM service interface instead of the Ethernet interface used by conventional EH-800 network integrations.

During hardware testing, property writes have been verified on the physical controller, a 269-property snapshot has been captured, and the same snapshot has been used for controller recovery.

This may be the **first known Home Assistant EH-800B USB integration with confirmed read/write support**, but this is intentionally stated as "first known" rather than an absolute claim until prior implementations have been exhaustively ruled out.

## What works in v0.1.2

- USB CDC serial connection (tested device VID:PID `eb03:0920`)
- `MEASUREMENTS` polling into 28 Home Assistant sensor entities
- Confirmed configuration writes with `SET PROPERTY <id> <value>`
- Safe first set of L1 controls as Home Assistant Number entities
- Shared per-port USB locking and property-write retries
- Stable tested Linux device path: `/dev/serial/by-id/usb-OUMAN_Ouman_EH-800-if00`

Confirmed write example: `SET PROPERTY 67 910` changed the L1 -20 °C curve point from 90.0 °C to 91.0 °C on the physical controller.

## Home Assistant OS

Copy `custom_components/ouman_eh800` to `/config/custom_components/ouman_eh800`.

Add:

```yaml
sensor:
  - platform: ouman_eh800
    port: /dev/serial/by-id/usb-OUMAN_Ouman_EH-800-if00

number:
  - platform: ouman_eh800
    port: /dev/serial/by-id/usb-OUMAN_Ouman_EH-800-if00
```

Restart Home Assistant after validating the configuration.

## Restoring a previously saved EH-800 property snapshot

This recovery procedure is being hardware-tested on an EH-800B during reverse engineering. During the current restore of a previously captured 269-property snapshot, the normal line between the five L1 heating-curve points returned on the physical EH-800 display while the restore was still in progress.

### Important safety notes

> **WARNING — valve/PID tuning:** During development, changing the L1 valve/PID controller parameters was associated with abnormal valve/controller behaviour and a possible controller/valve-control crash. The exact cause has not yet been isolated. **Do not change the P/I/D valve-control parameters unless you understand the controller behaviour and have a known-good backup.** For normal use, leave the PID values at their known-good/original values. These parameters should be treated as experimental/unsafe until further hardware testing confirms otherwise.

The restore writes live controller configuration. Use only a snapshot captured from the **same controller**.

The project does not contain universal factory defaults and does not guess missing values. Do not use another controller's property dump as a factory-reset file.

Do not restart Home Assistant, disconnect USB, power-cycle the EH-800, or change settings from the physical controller while a restore is running.

### Required backup file

Keep the known-good property snapshot at:

```text
/config/ouman_properties.txt
```

The tested file contains records in this format:

```text
PROPERTY(67):'L1_KAYRAN_MENOVESI_5A'(0-1000) = 900
PROPERTY(73):'L1_KAYRAN_MENOVESI_5D'(0-1000) = 490
```

Before restoring, verify the number of unique properties:

```bash
grep -oE 'PROPERTY\([0-9]+\)' /config/ouman_properties.txt | sort -u | wc -l
```

The tested full snapshot contained **269 unique properties**. Do not continue with a clearly incomplete file.

### Enable the restore helper

The currently tested development restore helper is loaded from the integration's `async_setup` and registers:

```text
ouman_eh800.restore_original
```

The integration must therefore also have a top-level configuration entry:

```yaml
ouman_eh800:
  port: /dev/serial/by-id/usb-OUMAN_Ouman_EH-800-if00
```

After installing the restore-enabled development version, validate first:

```bash
ha core check
```

Continue only when Home Assistant reports:

```text
Command completed successfully.
```

Then restart Home Assistant:

```bash
ha core restart
```

### Start the restore

Open **Developer Tools → Actions** and search for:

```text
ouman_eh800.restore_original
```

Run the action **once**.

Do not use an unauthenticated Terminal `curl` call as a substitute. In testing, the Supervisor/Core API request returned HTTP 401, while running the registered action from Home Assistant Developer Tools worked correctly.

### Follow progress

Open Terminal & SSH and run:

```bash
ha core logs -f | grep "OUMAN RESTORE"
```

A normal restore looks like:

```text
OUMAN RESTORE START: 269 properties
OUMAN RESTORE 1/269 property=1 value=65491 returned=65491
OUMAN RESTORE 10/269 ...
OUMAN RESTORE 20/269 ...
...
OUMAN RESTORE 269/269 ...
OUMAN RESTORE DONE: ok=269 failed=0
```

Values such as `65491` can be the unsigned 16-bit representation of a negative signed setting and are not automatically an error.

The desired final result is:

```text
OUMAN RESTORE DONE: ok=269 failed=0
```

If `failed` is not zero, do not repeatedly rerun the full restore. Check the preceding `OUMAN RESTORE FAILED` lines and identify the affected property IDs first.

### Verify the physical controller

After the restore has finished, verify important settings directly from the EH-800 display before relying on automatic operation:

- L1 heating curve and all five curve points
- supply-water minimum and maximum limits
- controller operating mode
- valve/motor operation
- installation-specific relay, network and hybrid settings

During the current hardware recovery, the L1 curve line visibly returned before the complete 269-property restore had finished. The restore was left running and should not be interrupted before the final `DONE` line.

### Keep recovery copies

Keep known-good recovery files outside the live controller. During development, both a property snapshot and an original `objects.dat` image were retained before further reverse engineering.

The property restore is not a firmware flash. The controller's `FIRMWARE` command is intentionally not used.


## Lovelace dashboard example

A ready-to-paste Home Assistant Lovelace card for the L1 heating circuit is included here:

`examples/lovelace-ouman-l1-dashboard.yaml`

It provides:

- live gauges for supply temperature, calculated target and valve position
- direct adjustment of all five L1 heating-curve points
- real-time L1 values
- a 12-hour supply-temperature/target history graph

Add a **Manual card** in a Home Assistant dashboard and paste the contents of the example YAML file into the card editor.

The example uses the entity IDs produced by the current tested installation. Home Assistant can add suffixes such as `_2` when an object ID already exists, so verify the entity IDs on your own installation if a card shows an unavailable entity.

## Important

Writing properties changes the live heating controller configuration. v0.1 exposes only high-confidence L1 controls mapped during hardware testing.

**Do not experiment with valve/PID parameters (P-band, I-time, D-time) on a live heating system.** The review branch disables writes to PID properties 56/57/58 while retaining all other previously offered L1 Number controls. Manual valve position 92 still changes the real valve. Keep a verified property snapshot before making configuration changes.

Known service-shell commands include `MEASUREMENTS`, `LIST`, `TYPE`, `KEYECHO`, `OSINFO`, `DEVINFO`, `TIME`, `SET CLOCK`, `SET DATE`, `SET DAY`, `RENAME`, `FIRMWARE`, `PTESTER`, and `SET PROPERTY variable value`.

The `FIRMWARE` path is intentionally not implemented.


## Development v0.2.1: writable L1 controls with read-only PID (draft PR)

**Do not install this branch directly on your live heating controller yet.**
The existing `main` branch and your installed v0.1.2 have not been modified.
This is an opt-in review branch with hardware testing outstanding.

### Existing YAML sensor / number setup

- All 28 measurement sensors retain the existing unique IDs and polling.
- **12 existing non-PID Number controls remain writable** using the original
  serial transport and original `SET PROPERTY` path:
  54 supply minimum, 55 supply maximum, 67/69/71/73/75 heating curve,
  91 summer shutoff, 92 manual valve position, 126 maximum change rate,
  127 supply setpoint and 134 fine adjustment.
- PID properties **56 (P), 57 (I), 58 (D) are NO LONGER writable Numbers**.
  They are represented by read-only
  `Ouman L1 P/I/D ... (saved snapshot)` sensors when you have a prior backup
  at `/config/ouman_properties.txt`.
- These three sensors read the existing saved text backup **without making any
  USB requests**. They are **not live** PID readings; the saved backup may
  be older than the controller's present settings. If no backup exists,
  their state remains unknown. The timestamp attribute reflects the
  file modification time, not necessarily the original capture time.
- Legacy Numbers still contain the **old default values on startup**, not
  verified reads of live properties. Do not assume these reflect actual
  controller settings until independently verified.

### Optional Home Assistant UI configuration

This alternate setup supports:
- the native USB port selector, EB03:0920 discovery, and serialx URLs;
- 28 measurement sensors with one 15-second coordinator;
- **the same 12 writable L1 Number entities**, with strict raw range/step
  checks and confirmed per-property controller acknowledgements;
- the same three **snapshot-only** PID sensors;
- one persistent USB session, async lock and no blind write retries;
- a stand-alone protocol package and fake-serial regression tests.

New UI Number entities start with an **unknown value** until a successful
write is acknowledged. We deliberately do not seed them from hardcoded
defaults or a possibly stale file. The Ouman protocol still lacks a verified,
side-effect-free live `GET PROPERTY` command; `SET PROPERTY` must never be
used as a way to read existing values. Do not attempt to migrate dashboards
assuming UI-created entity IDs will match those from YAML.

**Never configure the YAML and new UI connection against the same USB
port at the same time.** The UI path is optional, not required for keeping
existing controls working. The current installation can remain on v0.1.2
until real-hardware acceptance tests finish.

### Physical acceptance before release
1. Test each of the 12 supported writes and immediately verify the actual
   controller menu value (especially valve manual position and limits).
2. Test the five curve points both positive and negative outdoor temperatures;
   verify the menu and calculated supply-target display change.
3. Verify PID changes are impossible through both YAML and UI controls and
   that snapshot sensors make **zero** serial commands.
4. Confirm fragmented 28-reading replies, reconnect after USB unplug,
   and `socket://` behaviour with the specific controller firmware.
5. Confirm Home Assistant does not create duplicate device/entity IDs and
   that the old dashboard still functions after upgrading.

No attempt has been made to publish the Python library to PyPI, to install
the integration into the user's live Home Assistant, or to claim the new
transport has passed physical tests.

## Open USB protocol and developer research

The project publishes human-readable USB protocol notes, HEX-command examples,
raw byte capture utilities and an independent Python async USB client.
See [USB protocol research](docs/USB_PROTOCOL_RESEARCH.md),
[standalone Python library](docs/STANDALONE_LIBRARY.md),
[known PID issues](docs/PID_KNOWN_ISSUES.md), and
[manual restore guide](docs/RESTORE_AND_BACKUPS.md).

The original EH-800B-specific research script (`TYPE objects.dat`, raw HEX
and offline file-offset experiments) is published in the separate
[developer branch](https://github.com/artepe/ouman-eh800-B-usb-homeassistant/tree/developer/usb-unrestricted-lab/research).

A known controller UI behaviour is that changes written over USB may not
immediately refresh the **physical LCD**. Press **ESC once** and open the
heating-curve menu again to display the new setting. This is not a reason
to repeat a write command.

A complete real-device `objects.dat` image, actual firmware, and the original
269-property backup are **not committed**. Only reverse-engineered source,
documentation and tooling are included. Device-specific dumps should be
reviewed and anonymized before a public release. The claim that this works
on other Ouman products with USB is a hypothesis pending hardware testing.
