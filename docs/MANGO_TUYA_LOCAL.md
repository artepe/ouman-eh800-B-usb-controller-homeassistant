# Mango Tuya Local integration in Open HVAC / OpenLVI

## Scope and provenance

This project bundles the **complete Home Assistant component** `custom_components/mango_tuya_local`
from [Mango Tuya Local](https://github.com/artepe/chinaheatpump-tuya-local-home-assistant)
(archive source revision `beca3f9fd5cb72ca5b1d0420959ddadb91755a6b`, upstream version **0.2.1 beta**).
The upstream implementation is MIT licensed; see [copied license](third_party/mango-tuya-local.LICENSE).
Changes to the source integration should be compared with upstream before updating.

This is **not** a new driver inside `openlvi`, and it does **not** appear in the
OpenLVI Bridge manufacturer wizard. It installs side by side under its own
Home Assistant integration domain, `mango_tuya_local`. Neither existing Ouman
USB integrations nor building automation profiles are modified.

## Compatibility

- Intended for a specific captured **Mango Energy** heat-pump Tuya product profile
  `tfmjnk5uytzacmma`, using **Tuya protocol 3.5 over the local network**.
- The included profile contains **770 parameter routes / 17 categories** and a
  Mango Control sidebar dashboard. It is not a verified generic Tuya heat-pump driver.
- The manifest installs `tinytuya==1.17.4` through Home Assistant.
- Normal device polling and parameter operations use the device's LAN address,
  device ID and local key, rather than a cloud API account. Obtaining a local key
  in the first place may still require an external provisioning process.
- Only selected write commands have been tested on physical hardware; numerous
  routes and units remain unverified. **Do not make unsupervised parameter changes**
  on an operating heat pump. The device's protections must remain enabled.

## Manual installation on Home Assistant OS

1. Back up the Home Assistant configuration. If `mango_tuya_local` is already
   installed, compare versions; avoid silently overwriting a working installation.
2. Copy **the whole directory** `custom_components/mango_tuya_local` from this
   repository into `/config/custom_components/mango_tuya_local`.
3. Restart Home Assistant. Choose **Settings → Devices & services → Add integration
   → Mango Tuya Local**.
4. Enter the heat pump's local IP, device ID, and local key; the values are
   **private** and must not be committed to GitHub. The upstream repository also
   documents its Pi session exporter for environments where that data already
   exists. Do not copy secrets into the Open HVAC repository.
5. Allow the first full parameter scan to complete. Check read-only telemetry
   against the physical controller and confirm the LAN link before attempting
   any parameter write.
6. The **Mango Control** sidebar appears automatically. No separate OpenLVI
   profile or YAML configuration is needed.

**Safety and concurrency:** run only one installation of the Mango integration
for a given device. Do not change the same parameter from another app during a
write/readback cycle. The upstream client checks observed bounds and performs
readback; an unsuccessful recovery or power interruption can still leave the
controller in an uncertain state. Preserve access to the native controls and
back up settings before testing.

## Verification

- Open HVAC includes a static bundle integrity test at
  `tests/test_mango_tuya_bundle.py` (manifest, files, 770 routes, 17 categories).
- The original project's more extensive simulated-protocol and Home Assistant
  test suite remains at [the upstream repository](https://github.com/artepe/chinaheatpump-tuya-local-home-assistant/tree/main/tests).
- Live hardware acceptance testing is **required**; importing source files and
  passing static checks does not prove compatibility with another model.
- Report bugs to the Open HVAC repository with device firmware and redacted
  diagnostics. Do not publish local keys, device IDs or credentials.

## Cloud independence

The Tuya heat-pump link is LAN-local once device credentials are available.
This is **not** a claim that every vendor app or provisioning workflow is offline.
Cameras or cloud-dependent EZVIZ proxy integrations are **not included** in this import.
