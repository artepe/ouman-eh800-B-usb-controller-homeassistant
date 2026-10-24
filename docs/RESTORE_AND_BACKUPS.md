# Controller recovery and backups

The original Home Assistant integration on the user's EH-800B had a
`ouman_eh800.restore_original` service. Its source is included in
`custom_components/ouman_eh800/restore.py` in the review branch.
The service is **registered but never run automatically**.

## Before considering a restore

1. Have the **known-good** `/config/ouman_properties.txt` from the
   **same** controller; the capture used by the original restore had
   **269 unique property IDs**.
2. Back up the current Home Assistant configuration and verify the
   backup is readable.
3. Ensure the heating installation is being supervised and that you
   can safely stop the process and control the valve locally.
4. Check the snapshot's provenance and timestamp. Do not substitute
   generic defaults or someone else's dump.
5. The restore service accepts a minimum of 250 properties, but that
   threshold alone is **not proof of integrity or compatibility**.
   Inspect the snapshot independently before any restore.

## How the original action works

With top-level YAML config `ouman_eh800: {port: ...}`, the integration
registers `ouman_eh800.restore_original` in Developer Tools → Actions.
Manual invocation sends `SET PROPERTY <id> <raw>` for every
matching snapshot property via the legacy serial driver and reports
progress as `OUMAN RESTORE ...` in HA logs.

**WARNING:** This writes even PID properties. It is intentionally
not governed by the normal production PID read-only UI.
It is a destructive recovery operation, not a routine settings refresh.
The original implementation has no dry-run, transactional rollback, or
automated proof that controller state matches all requested values.
Keep power and USB connected. Do **not** call it as a test.

## Recommended response when the controller behaves abnormally

**Suomeksi:** Jos EH-800B:n toiminta on selvästi sekaisin esimerkiksi
virheellisten asetus- tai PID-kirjoitusten jälkeen, **oman laitteen
tarkistetusta, aiemmin toimineesta varmuuskopiosta tehty manuaalinen
palautus voi olla perusteltu vian korjauskeino**. Se ei ole normaali
huoltotoiminto eikä sitä suositella suoritettavaksi automaattisesti
pelkän menoveden lämpötilapoikkeaman perusteella.

**English:** If the EH-800B configuration is genuinely corrupted or
controller behavior remains abnormal after an accidental settings/PID
write, a **supervised manual restore from a verified, known-good backup
of that exact controller** may be an appropriate recovery procedure.
It is not routine maintenance and should not be automatically invoked
solely because measured supply temperature is below the calculated target.

### Diagnosis before restore / Tarkista ennen palautusta

1. Verify both Home Assistant temperatures are live, numeric and from
   the intended Ouman controller. An unavailable or stale USB sensor is
   not evidence of corrupted controller settings.
2. Check that the heat source produces enough heat and that circulation,
   mixing valve, actuators and temperature sensors work physically.
   Warm-up, defrost, insufficient heat output and changing demand can
   create a real target deviation even when the Ouman is healthy.
3. Read the actual controller display, alarm state, heating curve and
   known PID/config values; compare with your last known-good values.
4. If configuration corruption is independently confirmed, use the
   recovery prerequisites above and supervise the restore locally.
5. After a restore, verify actual valve behavior, supply temperature,
   curve, PID values, safety limits and correct regulation. Do not infer
   success from a Home Assistant service response alone.

### Safe once-daily deviation notification

An optional Home Assistant automation is provided at
[examples/automation-ouman-l1-daily-deviation-alert.yaml](../examples/automation-ouman-l1-daily-deviation-alert.yaml).

- At **12:00**, it compares measured L1 supply with the calculated L1
  target. It watches a deficit of **at least 3 C** for **30 minutes**.
- If the deficit persists, it creates a Home Assistant persistent
  notification **at most once per day**. It does **not** write any
  controller settings and does **not** run the restore action.
- Paste the example into Home Assistant's automation YAML editor,
  check entity IDs on your installation and tune limits to your
  particular hydraulics and heating requirements. A different failure
  pattern may not be captured by this daily spot-check.
- This is only monitoring; it does not diagnose why the target was missed.

### Manual restore (experimental installations only)

**Important:** The official stable v0.1.2 / `main` integration does
**not** ship `ouman_eh800.restore_original`. The action below is only
for installations that **already expose it** through the experimental
restore implementation. Do not install a different version solely to
make the action available.

When prerequisites are satisfied, with a qualified person at the
controller and a verified backup from that exact unit, use
**Developer Tools -> Actions** in Home Assistant:

```yaml
action: ouman_eh800.restore_original
data: {}
```

Do **not** place that action in the daily deviation example. The
original operation can overwrite **PID and other device settings**
and is not transactional. If the valve or heating process becomes
abnormal, stop the procedure and recover using the local controller
and a qualified technician.

## Open data vs per-device settings

Source code, protocol notes, parsers and example fixtures are public.
Actual raw backups (`ouman_properties.txt`, `objects.dat`), firmware
images and unique device identifiers are **not** bundled in GitHub;
they have not been provided as publishable, verified anonymized copies.
Use `tools/capture_raw_usb.py` locally and inspect exports first.
