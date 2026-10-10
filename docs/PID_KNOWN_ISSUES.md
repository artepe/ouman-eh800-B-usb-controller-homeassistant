# EH-800B PID / valve issues observed during reverse engineering

**Status:** Investigative notes from one physical EH-800B installation;
causality and affected firmware versions are **not fully established**.

## Observations

- Changing L1 controller PID properties **56 (P band), 57 (I time) and
  58 (D time)** during experimentation coincided with **abnormal valve
  operation** and a possible controller or valve-control malfunction.
- The original user subsequently restored previously captured
  controller-specific properties (269 unique properties); the five-point
  L1 heating curve returned to a normal-looking shape during recovery.
- No controlled root-cause isolation, independent reproduction, or
  device firmware comparison has been completed.
- Property **92** changes manual valve position and deserves special
  caution; it is **not** one of the PID parameters.

## Production policy

- Hide 56/57/58 from writable HA Number entities.
- Saved PID snapshot information can be displayed as **read-only** sensors.
  A timestamp belongs to the backup file, not necessarily a live read.
- Never issue `SET PROPERTY` to discover a property value.
- Regular supported L1 writes are limited to documented property IDs
  and validated raw boundaries; physical effect remains to be tested
  for every exposed property.
- A manually invoked **full restore** is separate emergency recovery.
  It may write PID properties deliberately because it replays a
  known-good snapshot from the **same unit**; this is a hazardous
  exception, not general PID editing.

## Developer experimentation

See the separate `developer/usb-unrestricted-lab` Git branch. That
branch is **not** intended for a running heating installation, and its
CLI includes deliberate safeguards against accidental writes.
Stop testing immediately if valve movement or water temperature
deviates from expectations.

## v0.2.2 Home Assistant regression (2026-10-10)

During installation of the 0.2.2 experimental USB integration on the
project author's EH-800B, Home Assistant started successfully and the
manifest showed version 0.2.2. However, outdoor temperature, supply
water and multiple other named Ouman entities became `unavailable` even
under Developer Tools → States. The older Lovelace graph still contained
historical values; its history does not prove current readings are valid.

**Severity:** non-production / unreliable live monitoring. The root cause
has not been proven (potential serial transport and/or polling regressions
remain unconfirmed hypotheses). A configuration check and synthetic tests
are insufficient to demonstrate a working hardware integration. Avoid
installing v0.2.2 as a replacement for a working v0.1.2 until its readings
and writes have passed physical hardware acceptance tests.

**Recommendation:** v0.1.2 was the last known working local HA installation;
for comprehensive RAW/HEX protocol exploration use the separate
`developer/usb-unrestricted-lab` branch on a controlled bench. It does not
promise decoded names for every `MEASUREMENTS` channel or real-time GET
access to all 269 snapshot properties.
