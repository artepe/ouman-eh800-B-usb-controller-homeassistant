# Roth Touchline PL (8-channel): local monitoring through an isolated contact

**Status: manufacturer-documented interface; hardware unverified.**

## Identification

The photographed example is *very likely* **Roth Touchline PL, 8 channels,
230 V** (LVI number **2070737**). Match the exact label on the front/rear
of the controller before installation; a photo of the terminal layout
alone cannot prove an exact model or hardware revision.

The manufacturer's terminal layout matches:

- Eight actuator zones **CH1–CH8**, **230 V**, maximum **0.3 A** per
  marked output.
- Pump **230 V**, maximum **0.5 A**.
- **VOLT. FREE CONT. NO / COM / NC** = **potential-free heat-source
  relay OUTPUT** (up to **1 A**). It is **not** an externally controlled
  dry-contact input, analog sensor, RS-485 or Modbus port.
- Thermostats use **868 MHz** radio. This does not imply a public API.

Manufacturer references:
- [Roth Touchline PL product page](https://www.roth-finland.fi/tuotteet/lattialammon-ohjausjarjestelmat/roth-touchline-pl)
- [Roth Touchline PL 8-channel wiring diagram (PDF)](https://www.roth-finland.fi/fileadmin/user_upload/Roth_North_Europe/Images_for_Roth_North_Europe/Finland/PDF_files_for_Finland/PDF_files_for_Products_Finland/Touchline_PL/Installation_Roth_Touchline_PL_kontrolenhed_20220509.pdf)
- [Roth controller-system comparison (PDF)](https://www.roth-finland.fi/fileadmin/user_upload/Roth_North_Europe/Images_for_Roth_North_Europe/Finland/PDF_files_for_Finland/PDF_files_for_Suport_Finland/Palvelut_suunnittelijoille/Vesikiertoisen_lattialaemmityksen_ja_lattiaviilennyksen_suunnitteluopas_A5_20230206.pdf):
  **PL = no Modbus or remote-control accessory**; **SL = optional remote control / Modbus**.

### Limits of the interface

No confirmed PL-specific local LAN/Wi-Fi API, serial register map or
publicly documented bidirectional 868 MHz protocol was found.
Do **NOT** apply the Roth **Touchline SL** Modbus map (room temperature
register 23, setpoint 221 etc.) to a Touchline **PL**. The existing
OpenLVI SL Modbus support is a *different* device generation.
The built-in official Home Assistant "Roth Touchline" integration is
for a network-connected Touchline controller, not this documented PL
contact output. The cloud-dependent HA Touchline SL integration likewise
does not establish local access to PL.

## Local, READ-ONLY Open HVAC support

**What you get:** the state of the single heat-source relay contact,
not the eight zones' current temperature, setpoints, valve positions
or alarm status. The relay is normally used to signal heating demand
to a boiler or heat pump. A physical acceptance test must confirm that
the NO/COM closure represents the desired demand signal and any pump
exercise or delay in the controller.

**Option A: ESPHome + ESP32 (example included)**

1. Have an appropriately qualified installer inspect the exact controller
   and confirm the heat-source relay terminals are **unused, physically
   voltage-free** and no mains/control voltage is present. If already
   connected to a heating appliance, **do not** wire an ESP32 in parallel.
   Use an appropriately approved *isolated interface* instead.
2. Use a separately housed, low-voltage ESP32; connect **COM -> GND** and
   **NO -> GPIO23** only after the above verification. Keep wiring
   separation from the 230 V actuator/pump terminals. Never energize or
   manipulate the PL output via the ESP32.
3. Flash [the ESPHome sample](../examples/esphome/roth-touchline-pl-relay-monitor.yaml).
   Put these values in a **private** ESPHome `secrets.yaml`:

   ```yaml
   wifi_ssid: "your-wifi"
   wifi_password: "your-password"
   roth_pl_api_key: "YOUR_GENERATED_32_BYTE_BASE64_API_KEY"
   roth_pl_ota_password: "YOUR_STRONG_UNIQUE_OTA_PASSWORD"
   ```

   Generate the API key using `openssl rand -base64 32`. Do not commit
   secrets to GitHub.
4. Pair the ESPHome device using Home Assistant's local encrypted API.
   The new `binary_sensor` represents **contact closed / open**. With
   NO/COM, a physically closed contact is ON. Compare its transitions
   to the Roth's display and the heat-source request on site.

**Option B: Shelly** with a compatible *low-voltage, dry-contact
input* and local Home Assistant integration, installed under the same
strict isolation/no-parallel-connection rules. The Shelly model must
be verified to support the chosen low-voltage sensing scheme; **not**
every Shelly switch has an isolated dry-contact input.

### What this intentionally does NOT do

- No setpoint writes, pair/unpair actions, or 868 MHz RF injection.
- No direct ESP32/Shelly connection to CH1–CH8 (230 V), pump, or mains
  terminals.
- No direct monitoring of existing live boiler signal via GPIO.
- No claim that NO/COM relay state equals every zone's real valve state.
- No standalone HA custom integration masquerading as a full controller.

For per-zone monitoring, consider independently approved, isolated
current/voltage monitors and dedicated room sensors, with qualified
electrical design; the above example intentionally implements none.
For complete zone-level control through open, documented interfaces,
consider a compatible controller replacement or a **verified newer
Touchline SL Modbus RTU** system. Never bypass the existing safety
and floor temperature limit functions.

**Community testing requested:** precise model ID / photo of label,
relay contact behavior (including any pump-delay/exercise cases), and
feedback after an electrically safe passive test.
