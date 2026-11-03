# OpenLVI English AI Guide — optional local Ollama (experimental)

Version: **OpenLVI Bridge 0.4.0-beta.1**, English-first advisory assistant.

This is **not** an autonomous controller or AI tuning system.
It **never calls** `number.set_value`, `SET PROPERTY`, Modbus writes,
BACnet WriteProperty, or other actuator actions. An AI text response is
**not authorized to write equipment settings**.

## Included features

- The existing OpenLVI device page gains an **OpenLVI English AI guide**
  sensor, which immediately explains recognised readings and gives
  conservative setup recommendations *without requiring an AI server*.
- A **Review settings in English** button runs a fresh review. The result is
  visible in the guide sensor's `english_explanation` attribute.
- The `openlvi.ask_assistant` Home Assistant action accepts a question
  and returns an English answer as action response data (Home Assistant
  Developer Tools → Actions). If multiple controllers exist, pass a
  `config_entry_id` to choose one.
- The optional local Ollama AI model writes **text only**. Suggested first
  model: `qwen2.5:0.5b` (approximately 398 MB model download).
- Optional automatic English AI review on integration startup and about
  every six hours. Default **off** until configured explicitly. Initial
  monitoring explanations run automatically even without Ollama.
- No cloud API key, vendor cloud service, internet endpoint or paid
  model is required. When Ollama is unavailable, the deterministic offline
  setting guide remains available.

**Known limit:** EH-800B USB property values (heating-curve and setpoints)
cannot currently be read side-effect-free from the controller. The AI
therefore **does not know current stored setpoints**. It uses only
identified live measurements, never guessed setpoint defaults or sensor
channels with unknown meaning.

## Local model deployment

The model is not bundled with the GitHub repository. Install Ollama on
a computer that remains powered on and has sufficient RAM/CPU. A
MacBook or N100 computer on the same private LAN as the HA host is a
convenient choice. An RPi5 8 GB can be used with a small model if the
underlying Ollama installation supports the hardware, but this
integration does **not** install or manage an Ollama runtime or guarantee
real-time performance on RPi5/HAOS.

On the Ollama computer:

```bash
ollama pull qwen2.5:0.5b
ollama list
```

Ensure Ollama is reachable from the HA Core container on private network
port 11434; this typically requires configuring Ollama's listening
interface and your OS firewall to permit **only your HA host**.
The service is unauthenticated by default; do **not** expose it to the
internet, publicly forwarded ports, or untrusted Wi-Fi.

To confirm from the HA terminal (substitute your own LAN IP):

```bash
curl --max-time 6 http://192.168.10.50:11434/api/tags
```

## Home Assistant setup

1. Update **both** `/config/custom_components/openlvi` and its module
   files, then restart HA. The stable `ouman_eh800` directory can
   remain untouched.
2. Settings → Devices & services → OpenLVI Bridge → **Configure**.
3. Under AI options, set **Local Ollama address** such as
   `http://192.168.10.50:11434`, and model
   `qwen2.5:0.5b`. The URL must be a **numeric private IPv4**
   address on the default port; a public or HTTPS endpoint is rejected.
4. Optionally turn on **Auto-review every six hours**; this schedules
   advisory readings analysis, not device writes.
5. Return to the EH-800B device, open the English AI guide sensor, or
   press **Review settings in English** and read its details.

## Ask a question (example)

Use Home Assistant → Developer Tools → Actions → `openlvi.ask_assistant`.

```yaml
action: openlvi.ask_assistant
data:
  question: What does the L1 heating curve at 0 degrees mean, and what should I check first?
response_variable: openlvi_answer
```

The action returns `answer`, `model`, `inference` and
`controller_settings_changed: false`. It can be used inside scripts
and automations to prepare a notification or display a suggestion.

## How much automation does it perform?

- **Automatically:** set up English guidance, review actual sensor
  readings, identify simple anomalies and provide suggestions. If you
  enable periodic AI review, this runs on startup and about every 6 hours.
- **Never automatically:** change heating curves, PID, pump speed,
  freezing/safety functions, or valve positions. No AI-generated setting
  values are passed to a physical controller.
- **Future option (not yet implemented):** human approval workflow
  that presents an exact proposed value, validates firmware and physical
  limits, confirms an independent readback and only then performs an
  explicitly approved write. USB EH-800B lacks a proven safe setpoint
  readback, so it cannot support those guarantees yet.

AI suggestions can be wrong. Validate advice against manufacturer
documentation and current controller settings.
