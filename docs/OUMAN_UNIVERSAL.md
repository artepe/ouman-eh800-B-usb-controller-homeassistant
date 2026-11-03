# Ouman Universal – experimental multi-model Home Assistant integration

**Status: development branch, NOT hardware-validated.** The original
`custom_components/ouman_eh800` v0.1.2 remains unchanged. Do **not** replace
a working heating controller installation with this prototype.

## Setup wizard

In Home Assistant, copy `custom_components/ouman_universal` to
`/config/custom_components/ouman_universal`, restart HA, then go to
**Settings → Devices & services → Add integration → Ouman Universal**.

1. Choose exact Ouman model and firmware; optionally enable *verified writes*
   (**off** by default).
2. Choose USB, HTTP, Modbus TCP or Modbus RTU as offered for that model.
3. Enter device address and, where necessary, site-specific point JSON.
4. A **read-only** connection check runs. No register is written during setup.

If "Ouman Universal" does not appear in Add integration, inspect HA logs and
verify the folder's `manifest.json` and Python dependencies.

## Actual model coverage (not universal automatic register discovery)

| Device | Transport | Register/endpoint coverage | Write support |
|---|---|---|---|
| EH-800 | HTTP | All active endpoints reported by `ouman-eh-800-api==2.0.0` | Selected numeric endpoint allowlist, **opt-in** |
| EH-800B / EH-800 USB | USB Mini-B via original `ouman_eh800` reader | 28 MEASUREMENTS (some unnamed) | **No** new driver writes; continue using v0.1.2 if needed |
| A203 / A203XL fw **2.0.2** | Modbus TCP or RTU | Verified temperature inputs and two room setpoint registers | Room setpoint only, **opt-in** |
| S203 16MB fw **3.0.10** | Modbus RTU / TCP gateway | Same subset, model-specific registers | Room setpoint only, **opt-in** |
| C203 16MB fw **3.0.10** | Modbus RTU / TCP gateway | Verified temperature subset | No |
| H23 8MB fw **4.0.5** | Modbus RTU / TCP gateway | Verified temperature subset | No |
| Ouflex, Ouflex A / A XL / AX, M / M BA / C | TCP / RTU as supported by device or gateway | **Requires site-specific point map** from BA Tool/Ounet | No |
| H21, S105, EH-203/105/686, RU23, EC-104, FLEX I/O | Modbus, hardware adapter/gateway where required | **Requires exact firmware and register profile** | No |

Model selection **does not certify** that a physical controller has any
particular connector or firmware. On site, verify network/bus wiring and
actual program. A Modbus TCP gateway can translate a Modbus RTU controller.

### Sources / vendor documents

- [Ouman downloads and version-specific Modbus PDFs](https://ouman.fi/downloads/)
- [Ouman Modbus guide: 1-based addresses, signed values, S32 word order,
  manual override registers](https://ouman.fi/wp-content/uploads/2025/09/YM0105_Modbus-guide_FIN.pdf)
- [A203XL 2.0.2 registers](https://ouflextool.ouman.net/downloads/DeviceTemplates/Ouman/A203/v202/A203_2.0.2_Modbus_fi-FI.pdf)
- [S203 3.0.10 registers](https://ouflextool.ouman.net/downloads/DeviceTemplates/Ouman/S203/v3010/S203%2016MBModbus_FI.pdf)
- [C203 3.0.10 registers](https://ouflextool.ouman.net/downloads/DeviceTemplates/Ouman/C203/v3010/C203_3.0.10_Modbus_fi.pdf)
- [H23 4.0.5 registers](https://ouflextool.ouman.net/downloads/DeviceTemplates/Ouman/H23/v405/H23%204.0.5_Modbus_fi.pdf)
- [Ouflex manual, TCP default port 502](https://ouman.fi/documentbank/Ouflex__manual__en.pdf)
- [Official HA EH-800 integration](https://www.home-assistant.io/integrations/ouman_eh_800/) and
  [ouman-eh-800-api Python library](https://github.com/Markus98/ouman-eh-800-api)

For production EH-800 (network) use the **official HA integration** whenever
possible; this experimental adapter has not yet been tested on physical EH-800.

## Custom Ouflex / other model points

The application loaded into a freely programmed Ouflex defines the
actual Modbus registers. Obtain its **site-specific Ouflex BA Tool/Ounet point
list**. Do **not** blindly probe all 65,535 registers.

Enter a small JSON profile in the setup wizard, e.g.

```json
{
  "registers": [
    {
      "key": "outdoor",
      "name": "Outdoor temperature",
      "address": 305,
      "kind": "s32",
      "decimals": 1,
      "unit": "°C"
    }
  ]
}
```

**305 is an illustrative example, not a real Ouflex address.**
Replace it with the value from your actual controller's register table.

- `address` is the **1-based Modbus holding-register number** from
  Ouman documentation. The adapter subtracts 1 internally for pymodbus.
- `kind`: `s16`, `u16`, `s32` or `u32`. Signed 32-bit reads use
  Ouman high-word-first ordering.
- `decimals: 1` means the raw integer is divided by 10; 0 means no scale.
- Custom JSON maps are **strictly read-only**, even if they contain
  `"writable": true`. Enabling writes in the wizard **does not** override
  this restriction.

Only a small, directly documented allowlist of setpoints can be written on
the exact listed firmware. This intentionally excludes manual valve commands,
PID parameters, pump/relais overrides, alarms and 32-bit writes.

## USB-specific constraints

The EH-800B USB implementation reuses the module
`custom_components/ouman_eh800/ouman.py` from this same repository. Copy
**both integration directories** when using EH-800B in the universal UI.
Do **not** configure two integrations to poll the same USB port at once:
they would contend for exclusive serial access. The stable legacy integration
is preferred for an actively running heating system.

## Operational safety

This is not a safety-rated building-management system. The controller
continues to perform local safety functions. Validate sensor freshness and
setpoint effects on a test device before enabling remote writes.

**Do not expose Modbus TCP or unencrypted EH-800 HTTP to the internet.**
Use firewall/VLAN and trusted local networks. A Modbus master can write
registers without authentication. Always keep a physical fallback and a
controller-specific backup; do not use remote write to investigate unknown
registers.
