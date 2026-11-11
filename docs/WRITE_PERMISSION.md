# Optional write access in Open HVAC

**Status: experimental.** Read-only collection is the default on new
OpenLVI and Mango Tuya Local configurations. Write access is a per-device
choice and can be reversed without deleting the configured device.

## OpenLVI Bridge

1. Install the experimental OpenLVI module and add the correct model.
2. Start with **read-only** polling. Verify values against the controller.
3. Go to **Settings → Devices & services → OpenLVI Bridge → Configure**.
4. Enable **Allow reviewed writes**; save. The integration reloads.
5. Only already-approved, bounded **Number** entities appear. Disable the
   same toggle to return to read-only mode; old entities may remain in the
   Home Assistant registry but are not active.

Safety applies in both UI and driver code. HTTP and Modbus writes are
checked at the transport boundary; EH-800B USB checks the write flag
before issuing any SET PROPERTY. Modbus setpoints must be explicitly
listed in vendor/firmware-based hardcoded allowlists; an arbitrary
user-supplied JSON register map is **always read-only**, even if it says
`"writable": true`. Never use an "expert mode" to guess unknown
registers or disable frost, pump, fire, overheat or anti-freeze safeguards.
Selected supported models may have **zero approved writable points**.

The Danfoss MCX is *not* an ECL controller and uses a site-specific
application. It remains read-only until the MCXShape register export and
physical mapping are reviewed. The write toggle cannot make unverified
MCX registers writable.

## Mango Tuya Local (standalone repo and Open HVAC bundle)

1. Go to **Settings → Devices & services → Mango Tuya Local → Configure**.
2. Switch **Enable parameter writes** ON; save and allow the integration
   to reload. Toggle OFF any time to return to read-only.
3. Mango Control shows 770 captured parameters regardless of write mode.
   Apply controls are disabled unless the owner has control permission and
   the setting is enabled. The backend refuses all write calls by default,
   including calls made outside the dashboard.
4. With writes enabled, the local transport still validates current bounds
   and performs readback; failure may attempt a bounded restore, but no
   software can guarantee recovery after an abrupt power loss.

The Mango profile contains many *unverified raw parameters*. An ON toggle
does **not** certify that all 770 points are writable or safe. Do not
mass-change parameters or use uncontrolled pörssisähkö automation to
override compressor / EEV / defrost protections.

## DEVIreg 330 and dry-contact modules

DEVIreg 330 (+5…+45°C) has no writeable Modbus interface. Price
setback is implemented by an **already commissioned** mains-rated
relay/thermostat timer input. Follow the separate one-circuit blueprint;
there is no generic Modbus write toggle to turn on.

Jäspi Tehowatti contact and Roth Touchline PL monitor are **separate
hardware/blueprint examples**, not writeable register interfaces. Their
behavior and physical wiring must remain governed by their respective
documented safety controls.

## Legacy Ouman EH-800B 0.1.2

The pinned **legacy v0.1.2** YAML platform is deliberately unchanged.
It was hardware-tested but exposes historic potentially dangerous PID and
manual valve controls. It has no configuration-entry Options UI. If you
need a controlled opt-in write mode, use the experimental **OpenLVI
EH-800B** driver instead on a *separately backed-up test setup*, and
never run both drivers on the same USB serial port. Do not silently
replace or downgrade a working legacy installation.

## Practical limits

- Enable writes **per device** only after backing up physical settings.
- Write access is a permission gate, **not** a protocol discoverer.
- Hardware protections, thermostat limits, anti-frost actions and manual
  override remain independent of Home Assistant.
- Do not expose the building controller TCP/RTU gateway to the internet.
- Tests use emulated devices; an operating building requires a separately
  supervised commissioning test.
