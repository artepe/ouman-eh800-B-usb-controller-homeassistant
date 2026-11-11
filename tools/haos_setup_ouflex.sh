#!/usr/bin/env bash
# Register or refresh Ouman Ouflex using Home Assistant's supported config-flow API.
# Run only in Home Assistant OS Terminal & SSH app with homeassistant_api access.
# Does NOT write to the controller or edit .storage files.
set -euo pipefail

HOST="192.168.10.105"
COMPONENT="/config/custom_components/ouman_ouflex"
BASE="http://supervisor/core/api/config/config_entries"

die() { printf 'VIRHE: %s\n' "$*" >&2; exit 1; }
info() { printf '%s\n' "$*"; }

[[ -f "$COMPONENT/manifest.json" ]] || die "Ouflex-integraatio puuttuu: $COMPONENT"
[[ -f "$COMPONENT/ftp_map.py" ]] || die "Uusi FTP-tuonti puuttuu: paivita OpenHVAC feature/ouflex-advanced-research"
command -v curl >/dev/null || die "curl puuttuu"
command -v jq >/dev/null || die "jq puuttuu; asenna/avaa Terminal & SSH, jossa jq on saatavilla"
# Prefer an administrator's own Home Assistant token when present.
# The Supervisor token is only usable if the SSH add-on explicitly permits
# homeassistant_api (401 is otherwise expected from its Core API proxy).
if [[ -n "${HA_TOKEN:-}" ]]; then
  API_BASE="${HA_API_BASE:-http://192.168.10.231:8123/api}"
  API_TOKEN="$HA_TOKEN"
  AUTH_MODE="personal"
elif [[ -n "${SUPERVISOR_TOKEN:-}" ]]; then
  API_BASE="http://supervisor/core/api"
  API_TOKEN="$SUPERVISOR_TOKEN"
  AUTH_MODE="supervisor"
else
  die "API-token puuttuu. Luo Home Assistantin profiilista Long-Lived Access Token ja kaynnista HA_TOKEN-muuttujalla."
fi

api() {
  local method="$1" endpoint="$2" payload="${3:-}"
  if [[ "$method" == GET ]]; then
    curl -fsS --connect-timeout 5 --max-time 40 \
      -H "Authorization: Bearer $API_TOKEN" \
      "$API_BASE$endpoint"
  else
    curl -fsS --connect-timeout 5 --max-time 120 \
      -H "Authorization: Bearer $API_TOKEN" \
      -H "Content-Type: application/json" \
      -X POST --data-binary "$payload" \
      "$API_BASE$endpoint"
  fi
}

summary() {
  printf '%s\n' "$1" | jq -c '{type, step_id, flow_id, errors, reason, message, title}'
}

info "=== Home Assistant API ==="
if ! api GET "/config" >/dev/null; then
  if [[ "$AUTH_MODE" == "supervisor" ]]; then
    die "SSH-lisaosan Supervisor-token ei paase Core APIin (401). Luo yllapitajan Long-Lived Access Token ja anna se HA_TOKEN-muuttujana; kayta suoraa Core API -osoitetta."
  fi
  die "Home Assistant API -yhteys epaonnistui. Tarkista tokenin oikeudet ja HA_API_BASE (oletus http://192.168.10.231:8123/api)."
fi
info "API-yhteys OK."

info "=== Haetaan Ouflex-asennukset ==="
entries="$(api GET "/config/config_entries/entry?domain=ouman_ouflex")" || die "Laiteasetusten lukeminen epaonnistui"
printf '%s' "$entries" | jq -e 'type == "array"' >/dev/null || die "Odottamaton vastaus entiteettilistauksesta"
count="$(printf '%s' "$entries" | jq 'length')"
if (( count > 1 )); then
  die "Useita Ouflex-asennuksia ($count). Ei valita vaaran laitteen asetuksia automaattisesti."
fi

if (( count == 1 )); then
  entry_id="$(printf '%s' "$entries" | jq -er '.[0].entry_id')"
  info "Ouflex on jo lisatty (entry $entry_id). Paivitetaan sen koko XML-rekisterikartta."
  start="$(api POST "/config/config_entries/options/flow" "$(jq -cn --arg id "$entry_id" '{handler:$id}')")" || die "Asetusvalikon avaaminen epaonnistui"
  [[ "$(printf '%s' "$start" | jq -r '.type')" == "menu" ]] || { summary "$start"; die "Odotettiin Ouflex-asetusvalikkoa"; }
  flow_id="$(printf '%s' "$start" | jq -er '.flow_id')"
  next="$(api POST "/config/config_entries/options/flow/$flow_id" '{"next_step_id":"refresh_from_ftp"}')" || die "FTP-paivitysvalikon avaaminen epaonnistui"
  [[ "$(printf '%s' "$next" | jq -r '.type')" == "form" ]] || { summary "$next"; die "Odotettiin vahvistuslomaketta"; }
  result="$(api POST "/config/config_entries/options/flow/$flow_id" '{"confirm":true}')" || die "FTP-pistekartan tuonti epaonnistui"
else
  info "Ouflexia ei ole lisatty. Luodaan laite ja haetaan 240 pistetta FTP:sta."
  start="$(api POST "/config/config_entries/flow" '{"handler":"ouman_ouflex"}')" || die "Ouflex-asennusvalikon avaaminen epaonnistui"
  [[ "$(printf '%s' "$start" | jq -r '.type')" == "form" ]] || { summary "$start"; die "Odotettiin Ouflex-asennuslomaketta"; }
  flow_id="$(printf '%s' "$start" | jq -er '.flow_id')"
  result="$(api POST "/config/config_entries/flow/$flow_id" \
    "$(jq -cn --arg host "$HOST" '{host:$host,port:502,unit_id:1,auto_ftp_map:true,map_json:""}')")" || die "Ouflexin automaattinen FTP-tuonti epaonnistui"
fi

info "=== Asennuksen tulos ==="
summary "$result"
if [[ "$(printf '%s' "$result" | jq -r '.type')" != "create_entry" ]]; then
  die "Integraatio ei vahvistanut luontia/paivitysta. Katso yllä oleva type/errors."
fi

info "=== Ouflexin tila ==="
api GET "/config/config_entries/entry?domain=ouman_ouflex" | \
  jq -c '.[] | {title,entry_id,state,disabled_by}'
info "OK: Ouflex on rekisteroity. Laitteen 240 pisteen ensimmainen kysely voi yha olla kaynnissa."
info "Tarkista Home Assistant: Asetukset -> Laitteet ja palvelut -> Open HVAC Ouman Ouflex."
