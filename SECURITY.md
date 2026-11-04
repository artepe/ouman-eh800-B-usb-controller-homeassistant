# Security policy

## Reporting

Please do **not** disclose controller credentials or a vulnerability in a
public issue. Use this repository's **Security → Report a vulnerability**
(private vulnerability reporting, when enabled), or privately contact the
maintainer via [@artepe](https://github.com/artepe).

## Release/support status

- `custom_components/ouman_eh800` **v0.1.2**: last version reported working
  with one real EH-800B. It is **not** a safety-certified control system.
- `custom_components/openlvi` **v0.4.0-beta.1**: experimental. The CI tests
  do not establish compatibility with physical HVAC/metering equipment.
- No promise of a vulnerability-remediation SLA is made.

## Security boundaries

- **Transport isolation:** Modbus TCP (normally 502) and BACnet/IP (normally
  UDP 47808) generally have no per-command authentication. Device HTTP may
  use unencrypted credentials. Never publish these services to the internet.
  Use a trusted LAN/VLAN, firewall and secure remote access.
- **Safe-by-default configuration:** the new OpenLVI configuration wizard
  defaults to read-only, except for the eleven separately allowlisted
  EH-800B USB Number controls, which require explicit manual input. User-supplied point maps are read-only; remote
  BACnet and wired M-Bus are read-only in the current implementation. Built-in
  model writes must be explicitly enabled and limited to reviewed ranges.
- **Physical safeguards:** an HA failure must never disable a manufacturer's
  local frost, overheating, pressure, pump or ventilation safety controls.
  Before production use, test sensor meaning, scaling, serial settings and
  any write effects on isolated hardware.
- **Legacy EH-800B warning:** the stable v0.1.2 legacy component has writable
  PID parameters 56/57/58 and manual valve property 92; changes to PID
  parameters coincided with abnormal valve behaviour in earlier experiments.
  **Never use these writable entities for exploratory testing on a live plant.**
- **ESP32-S3 experimental project:** Wi-Fi AP password is device-specific
  when the example default is left unchanged, and setpoint writes require a
  separate password and explicit permission. This does not replace external
  network protection.
- Do not commit credentials, Wi-Fi or MQTT passwords, site addresses,
  customer-specific register exports containing private data or HA storage
  secrets. Sanitize diagnostic logs and screenshots before sharing.

The project does not claim automatic discovery of every device, automatic
safety validation, reliable AI fault diagnosis or autonomous AI-based
physical control. The optional local model provides advisory text only.
