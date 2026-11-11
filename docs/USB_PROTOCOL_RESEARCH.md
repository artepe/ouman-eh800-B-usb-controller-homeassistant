# Ouman EH-800 / EH-800B USB protocol research (open source)

**Origin:** Independent reverse engineering on a physical EH-800B using
USB CDC ACM on Linux. Tested USB identifier **VID:PID eb03:0920**.
The observed interface uses a newline-delimited ASCII service shell, with
some replies (notably `TYPE objects.dat`) containing binary data.

## Status and scope

- **Confirmed on EH-800B:** `MEASUREMENTS\n` for live readings,
  `SET PROPERTY 67 910\n` for a heating-curve write; replies include
  `PROPERTY(67):'L1_KAYRAN_MENOVESI_5A'(0-1000) = 910`.
- **Observed/probed shell commands:** `LIST`, `TYPE objects.dat`,
  `DEVINFO`, `OSINFO`, `TIME`, `MEASUREMENTS`, `SET PROPERTY`.
  The presence of a command does **not** guarantee support on other models.
- **Other EH-800 series with USB:** a plausible reuse of the protocol,
  **not yet verified**. EH-80, EH-203, C203 and network-only EH-800 are
  **not claimed compatible**.
- `FIRMWARE` and file-upload functions are **not used** by the normal
  integration. There is no validated general-purpose device upload protocol.

## Wire examples

ASCII request `MEASUREMENTS\n` as HEX:
`4d 45 41 53 55 52 45 4d 45 4e 54 53 0a`.

ASCII request `SET PROPERTY 67 910\n` as HEX:
`53 45 54 20 50 52 4f 50 45 52 54 59 20 36 37 20 39 31 30 0a`.

The sample property reply above is a **documented observed response**.
The HEX examples are mechanically encoded from the command strings, not
a claimed complete capture of a real USB session.

The current legacy driver opens serial anew and uses short quiet periods
as a reply heuristic. The async `serialx` implementation holds a
persistent connection with `asyncio.Lock` and requires 28 valid lines
for `MEASUREMENTS`. That fixed-count framing needs hardware validation
across firmware revisions; it is not known to be universal.

## Raw binary objects.dat notes

An earlier independent USB research script assumes an EH-800B
`objects.dat` image of **3192 bytes**. This is a model/firmware-specific
working assumption rather than a verified universal file format.

Known experimental offsets (zero-based bytes):

| Value | Offset | Encoding |
|---|---:|---|
| heating curve at -20 °C | 2536 | uint16 LE, raw/10 |
| heating curve at -10 °C | 2556 | uint16 LE, raw/10 |
| heating curve at 0 °C | 2576 | uint16 LE, raw/10 |
| heating curve at +10 °C | 2596 | uint16 LE, raw/10 |
| heating curve at +20 °C | 2616 | uint16 LE, raw/10 |
| stored curve X coordinate | above offsets + 10 | int16 LE, raw/10 |
| fine adjustment | 2776 | int8, raw/10 |

These offsets were inferred from **one** research script. Verify on each
different controller and firmware, and never flash a locally patched image.

## Critical UI observation

A successful USB `SET PROPERTY` changes controller state, but the
controller's **physical display may remain stale** on the already-open
menu. On the tested EH-800B, press **ESC once** to leave the menu, then
open heating-curve settings again; the physical screen then refreshes.
This screen refresh is **not an additional USB write** and does not prove
all firmware models behave identically. If controller state still
disagrees, do not continue changing values.

## Live reads versus snapshot data

A side-effect-free `GET PROPERTY` command has **not been verified**.
Do not use `SET PROPERTY` as a read. The PID P/I/D sensor data in this
project are marked as **stored snapshot values** from the test
controller's `ouman_properties.txt` and may not reflect actual live settings.

For a capture from a hardware controller, run
`python tools/capture_raw_usb.py --port /dev/serial/by-id/... --command MEASUREMENTS --output my_capture.json`
while Home Assistant is not holding that serial port.

Raw captures may reveal configuration, network details, identifiers and
personal data: review and redact them before uploading anywhere public.
No genuine objects.dat backup, firmware image or 269-property
controller dump has been committed to this repository.
