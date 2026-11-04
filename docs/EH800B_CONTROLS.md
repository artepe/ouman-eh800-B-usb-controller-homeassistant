# EH-800B USB — L1 controls automatically in OpenHVAC Bridge

**Version:** OpenHVAC Bridge 0.4.0-beta.1 (experimental).
The legacy Ouman EH-800B v0.1.2 remains unchanged and was the last
installation version reported working on a physical controller.

## No separate YAML number platform

For a single EH-800B connected via USB, install the OpenHVAC component
in `/config/custom_components/openhvac` and keep the original
`/config/custom_components/ouman_eh800` **source folder** alongside it.
OpenHVAC imports its proven serial hub. Do **not** configure both
`sensor: - platform: ouman_eh800` and the OpenHVAC USB integration
against the same serial port: use **one polling owner**.

Restart Home Assistant. Open **Settings → Devices & services → OpenHVAC
Bridge → Ouman EH-800B**. The device now gets 28 measurement entities
and **11 Number controls** without a separate `number:` YAML setup.
Existing OpenHVAC EH-800B entries also gain these Number entities after
updating and restarting; no need to delete the configuration entry.

## Which controls appear?

Control names below are the English defaults for new installs. Existing Home
Assistant entity IDs are preserved by their stable unique IDs; a user-renamed
entity remains user-renamed.

| USB property ID | HA number control | Allowed range | Increment |
|---|---|---|---|
| 54 | L1 supply minimum | 5–95 °C | 1 °C |
| 55 | L1 supply maximum | 5–95 °C | 1 °C |
| 67 | L1 heating curve −20 °C | 0–100 °C | 1 °C |
| 69 | L1 heating curve −10 °C | 0–100 °C | 1 °C |
| 71 | L1 heating curve 0 °C | 0–100 °C | 1 °C |
| 73 | L1 heating curve +10 °C | 0–100 °C | 1 °C |
| 75 | L1 heating curve +20 °C | 0–100 °C | 1 °C |
| 91 | L1 summer shutoff setting | 5–95 raw | 1 raw |
| 126 | L1 maximum supply change rate | 1–50 raw | 1 raw |
| 127 | L1 supply setpoint | 0–95 °C | 1 °C |
| 134 | L1 fine adjustment | −4–4 °C | 0.1 °C |

**Unsafe or unverified properties are intentionally omitted**, most
importantly PID 56/57/58 and manual valve position 92. Do not attempt
to control them through a custom USB command. All setpoints above can
affect the real heating controller, so adjust them conservatively,
with local supervision and the manufacturer's native safety controls.

## Why are initial values 'unknown'?

A side-effect-free USB `GET PROPERTY` command has **not been verified**.
The original USB service API only confirms the result of a
`SET PROPERTY` command. Reading an unknown value by sending an
arbitrary SET is forbidden: it would change the controller.

Therefore the Home Assistant Number entities start with an **unknown**
value, presented as an input box rather than a slider. Enter the
desired exact value **only when you intend to adjust the controller**.
If a matching PROPERTY response is received, the value becomes
the *last acknowledged user command* in Home Assistant.
It **does not** prove an independent live read. Rebooting HA returns
those Number values to unknown, not invented/stale defaults.

Confirm results on the physical controller; its current open screen
may require leaving and re-entering its menu to refresh. If the
controller does not show the expected result, stop making adjustments.

## How the USB write is protected

- Exactly one `SET PROPERTY <id> <raw>` for one explicit HA user action.
  A malformed or empty reply fails the operation without retrying it.
- Only approved property IDs are allowed; out-of-range and non-step
  values are refused before any serial command is sent.
- Reads and writes share the existing protocol hub's per-port lock.
  Normal polling sends only `MEASUREMENTS`.
- No startup, automatic restart or network discovery writes.
- A serial disconnect or malformed acknowledgement can mean the
  physical state is unknown even if HA reports a write error.

Other Ouman models and all other brands keep their existing
firmware-dependent and opt-in write logic. Do not assume
that model-list membership means writable controls exist.

## USB configuration example (new integration)

The connection wizard uses the USB path such as
`/dev/serial/by-id/usb-OUMAN_Ouman_EH-800-if00`.
No separate YAML number platform is needed for this new integration.

**This is still experimental, not physically validated.**
Retain a verified controller configuration backup and local control.
