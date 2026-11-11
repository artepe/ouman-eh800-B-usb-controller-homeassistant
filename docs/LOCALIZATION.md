# OpenLVI language support

OpenLVI Bridge is **English-first**. Its source text, stable device identifiers,
default controller labels, setup flow, documentation and protocol descriptions
are written in English. The English translations in
`custom_components/openlvi/strings.json` are authoritative.

## Supported optional interface languages

These are the six languages shown in the Ouman EH-800/EH-800B user manual's
controller language selection page (firmware variants may differ):

| Locale | Language | File |
|---|---|---|
| `en` | English (default/fallback) | `translations/en.json` |
| `fi` | Finnish | `translations/fi.json` |
| `sv` | Swedish | `translations/sv.json` |
| `et` | Estonian | `translations/et.json` |
| `pl` | Polish | `translations/pl.json` |
| `ru` | Russian | `translations/ru.json` |

The translations cover the setup and options forms, all 28 EH-800B USB
measurement labels, 11 allowed L1 control labels and the diagnostic
sensor names.

Home Assistant displays localized names according to the **individual user's
Home Assistant profile language**. To keep *everything visible in English*,
choose **English** in Home Assistant user profile → Language.
A non-English HA profile can use the corresponding translation; unsupported
languages fall back to English.

**This setting does not change the physical Ouman controller's display
language.** The actual device uses its own menu. The integration does not
write language-related USB properties or alter any controller configuration.

## Compatibility and stable identifiers

- `Ouman` is the official manufacturer name. `EH-800` and `EH-800B`
  are official model identifiers; they are not translated.
- Internal USB protocol property identifiers, such as
  `L1_KAYRAN_MENOVESI_5A`, are **on-wire identifiers**, not user-facing
  labels. They must remain byte-for-byte unchanged for compatibility.
- Existing Home Assistant entity **unique IDs** and registry **entity IDs**
  do not change with language. All setpoint addresses, scaling, write
  restrictions, safety interlocks and polling intervals are unchanged.
- Existing entities with manually customized names continue using those
  custom names. For automatic translated labels, remove a *custom display
  name* using the normal Home Assistant entity edit UI; do **not**
  delete or regenerate entities.
- The separate legacy `custom_components/ouman_eh800` v0.1.2 remains
  untouched. Its existing visible names are already in English. Its
  historical properties and device protocol are not migrated by OpenLVI.

## Source and testing

Language list verified against the official Ouman EH-800 English user manual,
page 59: https://kauppa.ouman.fi/wp-content/uploads/2022/06/EH-800-user-manual_eng.pdf

Translations are **community-provided** and require native-speaker review
for precise technical terminology. Automated tests verify locale/key
completeness but do not prove a physical controller operates correctly in
a given firmware language.

When contributing a language, only translate display strings. Never translate
JSON keys, Home Assistant unique IDs, Modbus addresses, USB protocol
commands, entity classes or actual device model codes.
