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

### Protected manual restore (experimental branch)

**Status:** The production-tested v0.1.2 and the default `main` branch do
not include the new restore action. The implementation is available in the
[protected manual restore feature branch](../tree/feature/manual-restore-protected-20261024)
and has **not yet been verified on physical EH-800B hardware**.

The feature reproduces the original `ouman_eh800.restore_original` action
but adds explicit opt-in, a read-only backup preflight, a matching checksum,
a mandatory write confirmation and response checks. It never restores
automatically. A failed write stops the restore, but earlier writes cannot
be rolled back.

1. Before using the feature branch, back up Home Assistant and verify a
   controller-specific **known-good** `/config/ouman_properties.txt`.
2. Install the feature branch files on an isolated or supervised system.
   Keep existing `sensor:` and `number:` configuration unchanged.
3. Explicitly enable the restore action in `configuration.yaml`:

```yaml
ouman_eh800:
  port: /dev/serial/by-id/usb-OUMAN_Ouman_EH-800-if00
  enable_manual_restore: true
```

4. Validate YAML, restart Home Assistant, then open **Developer Tools ->
   Actions** and choose `ouman_eh800.restore_original`.
5. First run only a dry run (default) to validate the backup without touching
   the controller:

```yaml
action: ouman_eh800.restore_original
data:
  dry_run: true
```

6. In Home Assistant logs, locate `OUMAN RESTORE DRY RUN` and copy the
   recorded `sha256`. Independently verify that the backup is a known-good
   snapshot from the *same controller*. SHA-256 proves which file was selected,
   **not** whether its values are correct or safe.
7. **Only if manual recovery is necessary**, while supervising the controller
   locally, execute the following action with the exact verified checksum:

```yaml
action: ouman_eh800.restore_original
data:
  dry_run: false
  confirm: "RESTORE EH800 SETTINGS"
  backup_sha256: "REPLACE_WITH_EXACT_64_CHARACTER_SHA256"
```

8. Watch `OUMAN RESTORE` log messages and verify the physical controller
   display, valve movement, heat curve and safety limits afterwards.
   No automated proof of success or safe rollback is available.

**Do not add the write-enabled restore command to the daily target deviation
automation.** A persistent 3 C shortfall can be caused by heat pump output,
flow or defrost rather than corrupted Ouman configuration.

**Do not interrupt power/USB during a restore.** The heating system must be
safe and supervised. Restore operations may overwrite PID and other sensitive
controller parameters. Do not repeat a partially completed restore blindly.

## Open data vs per-device settings

Source code, protocol notes, parsers and example fixtures are public.
Actual raw backups (`ouman_properties.txt`, `objects.dat`), firmware
images and unique device identifiers are **not** bundled in GitHub;
they have not been provided as publishable, verified anonymized copies.
Use `tools/capture_raw_usb.py` locally and inspect exports first.
