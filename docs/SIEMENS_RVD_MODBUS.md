# Siemens RVD120 / RVD140 — OpenLVI Bridge (read-only)

**Experimental, no physical-controller validation yet.** This profile uses
Siemens *Basic Documentation P2510*, edition 2.0, controller series A/C,
CE1P2510en (2018-04-30), chapter 20.5.6 (Modbus data point table).

Manufacturer document:
https://sid.siemens.com/api/khub/documents/K2sQQXzf6QS87HzaOTu9xQ/content

## Connection

- RS-485 **Modbus RTU** slave, not built-in Ethernet. Use an isolated
  RS-485-to-USB interface in Home Assistant, or a private-network RTU-to-TCP
  gateway (do not expose it to the public Internet).
- Configure controller operating line **171**: unit number 1–247,
  **172**: parity (0 even, 1 odd, 2 none), **173**: baud
  (0 1200, 1 2400, 2 4800, 3 9600, 4 19200).
- Siemens specifies 8 data bits, 1 stop bit. Typical initial setup is
  **9600 baud, even parity**, but match the real panel configuration.
- Siemens specifies **150 ohm, 0.5 W** termination at the first and last
  device on the physical bus. Check proper RS-485 wiring/isolation.

In Home Assistant: install OpenLVI Bridge, choose **Siemens** and
**RVD120** or **RVD140**, Modbus RTU, the serial device, matching baud,
parity and slave address. The interface may also connect through an
RTU-to-TCP gateway selected as Modbus TCP.

**No settings are written**, even when a user previously enabled
OpenLVI's general write option. This device profile does not create
editable Number controls.

## Registers and scaling

Siemens P2510 calls each address a **Modbus address**, not a 4xxxx
reference. Its decimal 1044 is hex 0x0414, the zero-based **wire offset**
to supply in a Modbus FC03 request. OpenLVI's existing driver sends
point.address - 1, so the stored profile address is **1045**.

| P2510 wire address | Meaning | Scaling |
|---|---|---|
| 1019 | Modbus object version | signed raw / 10 |
| 1020 | Controller software version | signed raw / 10 |
| 1021 | Controller model identity | 140=RVD120, 142=RVD140 |
| 1022 | Plant type | integer |
| 1031 | Current fault code | integer |
| 1032 | Active limitation code | integer |
| 1036 | Heating-circuit pump Q1 energised | 0/1 |
| 1044 | Outdoor temperature B9 | signed raw / 64 °C |
| 1045 | Flow temperature B1 | signed raw / 64 °C |
| 1046 | DHW / tank temperature B3 | signed raw / 64 °C |
| 1047 | Room temperature A6 | signed raw / 64 °C |
| 1048 | Primary return temperature B7 | signed raw / 64 °C |
| 1052 | Secondary pressure U1 (RVD140 profile) | signed raw / 50 bar |
| 1053 | Primary pressure U2 (RVD140 profile) | signed raw / 50 bar |
| 1057 | Room setpoint | signed raw / 64 °C |
| 1058 | DHW setpoint | signed raw / 64 °C |
| 1064 | Resulting flow temperature target | signed raw / 64 °C |
| 1066 | Heating-circuit temperature target | signed raw / 64 °C |
| 1068 | Resulting DHW temperature target | signed raw / 64 °C |

The included profile also reads a documented subset of other relay,
outside-temperature and RVD140 sensor registers. Hardware configuration
and selected plant type determine which points respond. Failure of an
optional point does not invalidate all other measurements.

All reads use **FC03 holding registers**, **signed 16-bit**.
On connection, the driver checks document register **1021** and rejects
unknown/mismatched model identities. This guards against accidentally
polling the wrong device or applying an incorrect address base.

## Verification before use

1. Verify the 1021 model code and correct Modbus slave address.
2. Compare outdoor temperature, flow and return against the controller LCD.
3. Confirm pump contact and fault code against the physical equipment.
4. Leave the physical RVD controller in charge of all frost, pressure,
   overheat, heating and DHW protection.
5. Report model, series, firmware, plant type, gateway/adapter and
   redacted Modbus logs when contributing a hardware test.

**Limitations:** no hardware tests in this change; RVD120 supports fewer
plant types than RVD140. Do not assume every sensor exists. No
write/setpoint controls are implemented although Siemens documents
certain FC06/FC16 operations. Modbus requests remain local and should
never be directly Internet-facing.


## Advanced users: write protection and controlled access

**For authorized commissioning/maintenance personnel only.** A building
operator or district-heat utility may own the protected settings. Obtain
permission and record the original plant settings before changing the
controller. Never defeat safety interlocks or utility-mandated limitations.

There are **three distinct gates**; removing one does not remove the others:

| Gate | Where | What it means |
| --- | --- | --- |
| OpenLVI software protection | Integration config and RVD driver | This RVD profile is hardcoded **read-only**; checking `allow_writes` cannot override it |
| RVD protected parameter access | Siemens operating lines 226–251, especially line **251** | Hardware lock and protected commissioning level |
| Individual Modbus register permissions | Siemens P2510 Modbus data-point table | Some addresses are read-only, some read/write, and addresses 1000–1014 are read/write **only if** hardware locking permits it |

### 1. Inspect the existing lock without writing anything

- Confirm **RVD120/RVD140**, controller series and plant type, then read
  P2510 Modbus **wire address 1021** (model: 140 or 142) and **wire
  address 1033** (current hardware-lock state; operating line 251).
- At address **1033**, `0` means **not locked**, `1` means **hardware
  locking active**. The `hardware_write_lock` sensor exposes this state.
- Note that Siemens' address 1033 is a **zero-based wire offset**; the
  OpenLVI point object stores 1034 because the driver subtracts one.
- Do not attempt to write address **1033**: it is a status indicator
  for the controller's protected operating-line setting, not an
  advertised remote-unlock command.

### 2. Enter the protected Siemens commissioning level

The following is the **manufacturer-documented panel procedure** for
RVD120/RVD140, not an OpenLVI bypass:

1. On the front panel, press and hold the two operating-line selection
   buttons (up/down) together for **6 seconds**.
2. The display shows the five-button `Cod` entry prompt.
3. The P2510 manual, section **26.1.6**, documents the default
   five-button sequence as **down, up, right, left, right**
   (`▽ △ ▷ ◁ ▷`). OEM/custom variants may use different access
   arrangements; ask Siemens/the equipment owner for those.
4. Open operating line **251** in the **Locking functions** level
   (operating lines 226–251). Record its current value.

The heating-engineer level (lines 51–222) is different: hold the two
operating-line buttons for **3 seconds**. It **does not** itself release
the protected Locking functions level.

### 3. Remove the device's hardware lock, if permitted

At operating line **251**, Siemens defines:
- `0` = **no hardware locking**;
- `1` = **hardware locking active**.

If the device is already accessible and the site owner authorizes it,
a qualified commissioning technician can change line **251** from
`1` to `0` using the **front panel**, then verify Modbus wire
address **1033** has changed to `0`. Reapply `1` when the authorized
work ends, and verify that the lock is active again.

**Important physical-lock condition:** Siemens section **23.9** states
that when hardware locking is active, access to the protected level
requires a temporary terminal bridge at **B71–M**. The data-point
table (p. 84) instead prints **B71–M2**. As these terminal labels
differ *within Siemens' documentation*, **do not bridge terminals
based on this text alone**. Confirm the actual controller series,
terminal markings, live sensor use, power isolation and Siemens wiring
diagram with a qualified technician before any physical work. Bridging
the wrong terminals can disturb a sensor circuit or cause unsafe plant
operation. Do not cut seals or defeat utility-controlled locks without
permission.

Per Siemens section **20.5.5**, activating the hardware lock on line 251
makes Modbus **wire addresses 1000–1014 read-only**. This hardware
lock does *not* make every writable address read-only, and removing it
does *not* make read-only addresses writable.

### 4. OpenHVAC advanced-developer write access: NOT enabled yet

Removing Siemens hardware locking will **not** create a writable entity
in the current OpenHVAC integration. The RVD implementation
(`custom_components/openlvi/siemens_rvd.py`) intentionally creates
only `writable=False` registers. The generic
`custom_components/openlvi/profiles.py` encoder also rejects the
Siemens-specific `read_scale` format to prevent incorrect output.
In the configuration flow, these models force `allow_writes=False`.

A future **separate, opt-in advanced write implementation** must be
reviewed and tested before enabling any live controller writes:

1. Start with a **dedicated development branch**, real controller model
   identity verification and a complete backup of the commissioning
   values. Do not patch `writable=True` into the existing profile.
2. Implement a **strict per-model, per-register allowlist**, using the
   *write-access* columns of the Siemens P2510 table. Restrict it
   initially to non-safety user setpoints validated on a bench unit;
   never expose the complete holding-register address space.
3. Implement exact **signed 16-bit scaling, permitted ranges, value
   resolution and command readback**. Use the documented zero-based
   Siemens wire address, not an inferred 4xxxx address.
4. Add a separate **explicit operator opt-in**, an audit log and a
   clear recovery path to restore original values. No scheduled or
   startup writes; one explicit command per user action.
5. Block safety- and utility-protected functions: return-temperature
   limiting, high/low flow limits, frost protection, legionella
   management, pressure protection, manual valve/pump override,
   EEPROM-heavy polling/writes and all undocumented addresses.
6. Prove the command on isolated hardware before considering a
   production release. Keep the original RVD protective control active.

Siemens cautions that EEPROM write endurance is finite; avoid repeated
setpoint writes in high-frequency automations.

**Sources:** Siemens P2510, sections **20.5.3–20.5.6**, **23.9**,
**26.1.5–26.1.6**, pages **70–71, 84, 100, 108**:
https://support.industry.siemens.com/cs/attachments/109785646/A6V10276177.pdf

### Suomeksi: kirjoitussuojauksen poistaminen (ammattilaisille)

- **Tarkista ensin** OpenLVI-anturista
  `hardware_write_lock`: `0` = suojaus pois,
  `1` = laitelukitus päällä (Siemens Modbus-osoite **1033**).
- **Huoltotaso:** paina rivinvalintanäppäimiä yhtä aikaa
  **6 sekuntia**. Siemens P2510:n peruskoodi on
  **alas, ylös, oikea, vasen, oikea**. Valitse huoltorivi **251**.
- **Huoltorivi 251:** arvo **0** poistaa laitelukituksen,
  arvo **1** ottaa sen käyttöön. Varmista muutos lukemalla
  Modbus-osoite 1033. Palauta lukitus huollon lopuksi.
- **Jos laitetason lukitus estää huoltotasolle pääsyn**, Siemensin
  ohjeessa on B71–M / B71–M2 -liitinsiltausta koskeva ehto.
  Koska saman käsikirjan kahdessa kohdassa on eri liitinmerkintä,
  fyysistä siltausta **ei saa tehdä ilman kyseisen laitteen
  kytkentäkaavion ja liitinmerkintöjen varmistamista**.
- **OpenHVAC pysyy tästä huolimatta vain lukevana.**
  Ohjelmiston kirjoitusoikeus on toteutettava ja testattava
  erikseen; yleinen `allow_writes`-valinta ei poista sen estoa.

Muutokset vaikuttavat kaukolämmön ensiöpuolen rajoituksiin ja
lämmitysturvallisuuteen. Varmista kiinteistön omistajan ja
kaukolämpöyhtiön ehdot ennen lukituksen poistamista.
