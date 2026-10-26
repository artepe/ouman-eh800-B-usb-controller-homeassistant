# Security policy

## Reporting a vulnerability

Please do not report security problems in public issues. Use GitHub's private vulnerability reporting (**Security → Report a vulnerability** on this repository) or contact the maintainer privately through the GitHub profile [@artepe](https://github.com/artepe). Please allow time for a fix before publishing details.

## Supported versions

Security fixes are made to the latest release and the `main` branch only.

## Security design

- The integration talks to the controller over a local USB serial port only. Number entities refuse values outside each property's range before anything is sent to the controller.
- ESP32-S3 firmware: setpoint writes are disabled by default and need a separate 12+ character write password, a same-origin request, an allowlisted property and a cooldown. The Wi-Fi access point never uses the public default password; if `AP_PASSWORD` is left unchanged, a random per-board password is generated and printed on the serial monitor.
- Never commit filled-in Wi-Fi, MQTT or write passwords.
