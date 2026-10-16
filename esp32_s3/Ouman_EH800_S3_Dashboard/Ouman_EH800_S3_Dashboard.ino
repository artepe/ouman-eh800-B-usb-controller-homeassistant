/*
 * Ouman EH-800B USB Host -> Wi-Fi -> Home Assistant, Arduino ESP32-S3.
 * Version 0.2.0-Dashboard, experimental; read-only by default.
 * ESP32-S3 creates its own protected Wi-Fi AP for MacBook (192.168.4.1).
 * Tested: parser unit tests; NOT verified on a real EH-800B + ESP32-S3.
 * Requires Arduino-ESP32 3.3.12+, PubSubClient and a USB-OTG host power supply.
 * Commands: MEASUREMENTS only, unless operator explicitly unlocks curve writes.
 */

#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <PubSubClient.h>
#include <USBHost.h>
#include <USBHostSerial.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <ctype.h>
// Enter your own details before uploading. Do not share filled-in credentials.
// Direct MacBook connection: join this ESP32 access point.
// Change the AP password before using this outside a private test setup.
static const char *AP_SSID = "OUMAN-ESP32";
static const char *AP_PASSWORD = "Ouman12345"; // CHANGE before real use!
// Optional: set your home Wi-Fi values to also connect via router/MQTT.
// Leave placeholders unchanged for direct MacBook -> ESP32 AP testing.
static const char *WIFI_SSID = "YOUR_WIFI_NAME";
static const char *WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
static const char *MQTT_HOST = "192.168.1.10";  // Example only: change to your HA/MQTT broker IP
static const uint16_t MQTT_PORT = 1883;
static const char *MQTT_USER = "YOUR_MQTT_USERNAME";
static const char *MQTT_PASSWORD = "YOUR_MQTT_PASSWORD";
static const char *MQTT_TOPIC_PREFIX = "ouman_eh800_s3";

// Safety interlock: after REAL hardware verification only, set true and
// change WRITE_PASSWORD to a NEW secret with 12+ characters. Reflash.
// Never enable writes while someone else controls the same Ouman over USB.
static constexpr bool ENABLE_CURVE_WRITES = false;
static const char *WRITE_PASSWORD = "CHANGE_ME_BEFORE_ENABLING";


#if !defined(CONFIG_IDF_TARGET_ESP32S3)
#error "Select Tools -> Board -> ESP32S3 Dev Module (ESP32-S3 required)."
#endif

#if defined(ARDUINO_USB_MODE) && (ARDUINO_USB_MODE == 0) && ARDUINO_USB_CDC_ON_BOOT
#error "For USB Host: set Tools -> USB CDC On Boot = Disabled."
#endif

namespace {
constexpr uint8_t CHANNELS = 28;
constexpr unsigned long POLL_MS = 15000;
constexpr unsigned long READ_TIMEOUT_MS = 6500;
constexpr unsigned long QUIET_MS = 550;
constexpr unsigned long WIFI_RETRY_MS = 15000;
constexpr unsigned long MQTT_RETRY_MS = 5000;
constexpr size_t RX_CAPACITY = 8192;
constexpr unsigned long WRITE_COOLDOWN_MS = 15000;
constexpr unsigned long WRITE_TIMEOUT_MS = 4500;
constexpr size_t MAX_WRITE_REPLY = 2048;


USBHostSerialClass oumanSerial;
WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);
WebServer server(80);

float readings[CHANNELS] = {0};
char readingUnits[CHANNELS][4] = {{0}};
bool validReadings = false;
uint8_t lastValidChannels = 0;
unsigned long lastSuccessMs = 0;
unsigned long nextPollMs = 0;
unsigned long readStartedMs = 0;
unsigned long lastByteMs = 0;
unsigned long lastWiFiAttemptMs = 0;
unsigned long lastMqttAttemptMs = 0;
unsigned long totalSuccess = 0;
unsigned long totalFailures = 0;
bool awaiting = false;
bool previouslyMounted = false;

struct CurveOption {
  uint16_t id;
  int outdoorC;
  const char *label;
};
// Identified EH-800 curve property IDs from real-device research.
const CurveOption CURVE[] = {
  {67, -20, "-20 C"}, {69, -10, "-10 C"}, {71, 0, "0 C"},
  {73, 10, "+10 C"}, {75, 20, "+20 C"}
};
constexpr size_t CURVE_COUNT = sizeof(CURVE) / sizeof(CURVE[0]);
bool writeQueued = false;
bool writing = false;
uint16_t requestedId = 0;
int requestedRaw = 0;
unsigned long lastWriteStartMs = 0;
unsigned long writeStartedMs = 0;
String writeState = "idle";
String writeDetails = "No setpoint write has been attempted";

char rx[RX_CAPACITY];
size_t rxUsed = 0;
String baseTopic = "ouman_eh800_s3";
String clientId;
String availabilityTopic;

// Index 1-28 = stable Ouman Python integration's measurement order.
const char *const SENSOR_NAMES[CHANNELS] = {
  "L1 calculated supply target",        // 1
  "Measurement 2",                      // 2
  "Measurement 3",                      // 3
  "Measurement 4",                      // 4
  "Measurement 5",                      // 5
  "Measurement 6",                      // 6
  "L1 calculated supply target 2",      // 7
  "Measurement 8",                      // 8
  "L1 supply water temperature",        // 9
  "Outdoor temperature",                // 10
  "Outdoor temperature adjusted",       // 11
  "Measurement 12",                     // 12
  "Measurement 13",                     // 13
  "Measurement 14",                     // 14
  "L1 valve calculated position",       // 15
  "L1 valve position",                   // 16
  "Measurement 17",                     // 17
  "Measurement 18",                     // 18
  "Measurement 19",                     // 19
  "Measurement 20",                     // 20
  "Delayed outdoor temperature",        // 21
  "Measurement 22",                     // 22
  "Measurement 23",                     // 23
  "Measurement 24",                     // 24
  "Measurement 25",                     // 25
  "Measurement 26",                     // 26
  "Measurement 27",                     // 27
  "Digital input"                       // 28
};

String measurementTopic(uint8_t index) {
  char buf[16];
  snprintf(buf, sizeof(buf), "/m%02u", unsigned(index + 1));
  return baseTopic + "/state" + buf;
}

// The actual EH-800 protocol returns data lines ending with "<number> C", "%" or "dig".
// No setter functions or writable MQTT subscriptions exist in this firmware.
bool parseLine(char *line, float &value, char (&unit)[4]) {
  size_t length = strlen(line);
  while (length && isspace((unsigned char)line[length - 1])) line[--length] = '\0';
  if (!length) return false;

  const char *detected = nullptr;
  size_t unitLen = 0;
  if (length >= 3 && strcasecmp(line + length - 3, "dig") == 0) {
    detected = "dig";
    unitLen = 3;
  } else if (line[length - 1] == '%') {
    detected = "%";
    unitLen = 1;
  } else if (line[length - 1] == 'C' || line[length - 1] == 'c') {
    detected = "C";
    unitLen = 1;
  } else {
    return false;
  }

  // Trim whitespace between numeric reading and its unit.
  char *end = line + length - unitLen;
  while (end > line && isspace((unsigned char)end[-1])) --end;
  char *start = end;
  while (start > line && (isdigit((unsigned char)start[-1]) ||
                          start[-1] == '.' || start[-1] == '-' || start[-1] == '+')) {
    --start;
  }
  if (start == end) return false;
  // Reject alphabetic prefixes concatenated to a numeric reading.
  if (start > line && isalpha((unsigned char)start[-1])) return false;
  char saved = *end;
  *end = '\0';
  char *parsedEnd = nullptr;
  double raw = strtod(start, &parsedEnd);
  bool ok = parsedEnd == end && isfinite(raw) && raw >= -100000.0 && raw <= 100000.0;
  *end = saved;
  if (!ok) return false;
  value = float(raw);
  strcpy(unit, detected);
  return true;
}

size_t parseMeasurements(char *input, float *result, char units[][4], size_t capacity) {
  size_t n = 0;
  char *pos = input;
  while (*pos && n < capacity) {
    char *end = strchr(pos, '\n');
    if (end) *end = '\0';
    char unit[4] = {0};
    float value;
    if (parseLine(pos, value, unit)) {
      result[n] = value;
      memcpy(units[n], unit, sizeof(unit));
      ++n;
    }
    if (!end) break;
    pos = end + 1;
  }
  return n;
}

bool mqttReady() { return WiFi.status() == WL_CONNECTED && mqtt.connected(); }

void reportAvailability() {
  if (!mqttReady()) return;
  bool fresh = validReadings && oumanSerial.mounted() && (millis() - lastSuccessMs < 45000);
  mqtt.publish(availabilityTopic.c_str(), fresh ? "online" : "offline", true);
}

void publishDiscovery() {
  if (!mqttReady()) return;
  for (uint8_t i = 0; i < CHANNELS; ++i) {
    char idx[4];
    snprintf(idx, sizeof(idx), "%02u", unsigned(i + 1));
    String topic = String("homeassistant/sensor/ouman_eh800_s3/m") + idx + "/config";
    String payload = "{";
    payload += "\"name\":\"" + String(SENSOR_NAMES[i]) + "\",";
    payload += "\"unique_id\":\"ouman_eh800_s3_m" + String(idx) + "\",";
    payload += "\"state_topic\":\"" + measurementTopic(i) + "\",";
    payload += "\"availability_topic\":\"" + availabilityTopic + "\",";
    payload += "\"payload_available\":\"online\",\"payload_not_available\":\"offline\",";
    payload += "\"device\":{\"identifiers\":[\"ouman_eh800_s3\"],";
    payload += "\"name\":\"Ouman EH-800B S3\",\"manufacturer\":\"Ouman\",";
    payload += "\"model\":\"EH-800B via ESP32-S3 USB Host\"}";
    if (i == 0 || i == 6 || i == 8 || i == 9 || i == 10 || i == 20) {
      payload += ",\"device_class\":\"temperature\",\"unit_of_measurement\":\"°C\"";
    } else if (i == 14 || i == 15) {
      payload += ",\"unit_of_measurement\":\"%\"";
    }
    payload += "}";
    mqtt.publish(topic.c_str(), payload.c_str(), true);
    mqtt.loop();
    delay(3);
  }
}

void publishValues() {
  if (!mqttReady() || !validReadings) return;
  for (uint8_t i = 0; i < CHANNELS; ++i) {
    String value = String(readings[i], 2);
    mqtt.publish(measurementTopic(i).c_str(), value.c_str(), true);
    mqtt.loop();
    delay(2);
  }
  reportAvailability();
}

void serviceWifi() {
  // If credentials are placeholders, keep the standalone AP running only.
  if (strcmp(WIFI_SSID, "YOUR_WIFI_NAME") == 0 || WIFI_SSID[0] == '\0') return;
  if (WiFi.status() == WL_CONNECTED) return;
  unsigned long now = millis();
  if (now - lastWiFiAttemptMs < WIFI_RETRY_MS) return;
  lastWiFiAttemptMs = now;
  // Never switch to WIFI_STA: that would shut down the MacBook AP.
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
}

void serviceMqtt() {
  if (WiFi.status() != WL_CONNECTED) return;
  if (mqtt.connected()) { mqtt.loop(); return; }
  unsigned long now = millis();
  if (now - lastMqttAttemptMs < MQTT_RETRY_MS) return;
  lastMqttAttemptMs = now;
  bool ok = false;
  if (strlen(MQTT_USER)) {
    ok = mqtt.connect(clientId.c_str(), MQTT_USER, MQTT_PASSWORD,
                      availabilityTopic.c_str(), 0, true, "offline");
  } else {
    ok = mqtt.connect(clientId.c_str(), availabilityTopic.c_str(), 0, true, "offline");
  }
  if (!ok) return;
  mqtt.publish(availabilityTopic.c_str(), "offline", true);
  publishDiscovery();
  if (validReadings && (now - lastSuccessMs < 45000) && oumanSerial.mounted()) publishValues();
}

const char DASHBOARD_HTML[] PROGMEM = R"OUMANHTML(<!doctype html>
<html lang="fi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>OUMAN CONTROL | ESP32-S3</title>
<style>
:root{color-scheme:dark;font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;background:#0b111b;color:#eaf2fb}*{box-sizing:border-box}body{margin:0;min-height:100vh;background:radial-gradient(ellipse at 75% -12%,#183456 0%,transparent 50%),#0b111b}main{max-width:1160px;margin:auto;padding:24px 18px 58px}header{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:28px;flex-wrap:wrap}.brand{font-size:25px;font-weight:850;letter-spacing:-.7px}.brand em{font-style:normal;color:#6de0b1}nav{display:flex;gap:5px;background:#121e2f;border:1px solid #283a53;border-radius:12px;padding:4px}nav button{background:transparent;border:0;color:#bfd1e7;padding:10px 16px;border-radius:9px;font-weight:700}nav button.selected{background:#2a4668;color:white}h1{font-size:clamp(25px,4.5vw,38px);margin:5px 0 7px;letter-spacing:-1.1px}h2{font-size:19px;margin:0 0 14px}.sub{color:#9fb4ca;line-height:1.5;margin:0 0 20px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(175px,1fr));gap:12px}.card,.panel{background:#111d2d;border:1px solid #293b52;border-radius:16px}.card{padding:17px 19px}.card .small{font-size:12px;color:#a8bcd3}.card strong{display:block;font-size:22px;margin-top:11px;overflow-wrap:anywhere}.good{color:#7ce2b5}.bad{color:#ffaaa8}.muted{color:#afc1d4}.panel{padding:20px;margin-top:22px}.sensorgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(225px,1fr));gap:9px}.sensor{border:1px solid #2a3a4f;border-radius:11px;padding:13px 15px;background:#152336}.sensor .name{color:#a9bed4;font-size:12px;min-height:30px}.sensor .value{font-size:22px;font-weight:800;margin:5px 0}.sensor .index{font-size:11px;color:#86a3bc}.pills{display:flex;gap:9px;flex-wrap:wrap}.pill{background:#18334b;border:1px solid #365473;color:#bee1ff;border-radius:8px;padding:7px 11px;font-size:12px}.warning{border:1px solid #886241;background:#37291f;border-radius:12px;padding:16px;line-height:1.55;color:#ffdfbb}.curve{display:grid;grid-template-columns:repeat(auto-fit,minmax(195px,1fr));gap:12px;margin:16px 0}.curve label{font-size:12px;color:#bed0e3}.curve input{width:100%;background:#0d1724;border:1px solid #42546c;color:white;padding:12px;border-radius:9px;font-size:18px;margin:9px 0}.action{background:#49c69b;color:#05241a;border:0;border-radius:9px;font-weight:850;padding:11px 15px;cursor:pointer}.action:disabled{background:#42596a;color:#b0bac3;cursor:not-allowed}.footer{font-size:12px;color:#8ea7c0;line-height:1.7;margin-top:23px}.hidden{display:none}.result{white-space:pre-wrap;overflow-wrap:anywhere;border-radius:10px;background:#0a1522;border:1px solid #2b4056;padding:13px;font:13px ui-monospace,SFMono-Regular,monospace}.protect{margin-top:15px}input[type=password]{width:min(100%,360px);padding:11px;border-radius:8px;color:white;background:#091622;border:1px solid #40516a}a{color:#86d8ff}
</style></head><body><main>
<header><div class="brand">OUMAN <em>CONTROL</em> <span style="font-weight:450;font-size:13px;color:#95acc3">ESP32-S3</span></div><nav><button id="nav-monitor" class="selected" onclick="show('monitor')">Mittaukset</button><button id="nav-curves" onclick="show('curves')">Lämmityskäyrä</button></nav></header>
<section id="monitor"><h1>Ouman EH-800B</h1><p class="sub">Suora paikallinen USB Host -yhteys. Tiedot päivittyvät 5 sekunnin välein; laitetta kysellään noin 15 sekunnin välein.</p>
<div class="grid"><div class="card"><div class="small">USB-yhteys</div><strong id="usb">Odotetaan...</strong></div><div class="card"><div class="small">Wi-Fi / laite</div><strong id="network">OUMAN-ESP32</strong></div><div class="card"><div class="small">Viimeisin mittaus</div><strong id="fresh">Odotetaan...</strong></div><div class="card"><div class="small">Mittaussyklit</div><strong id="cycles">—</strong></div></div>
<div class="panel"><h2>Mittauskanavat</h2><p class="sub" id="notice">Yhdistä Oumanin USB Mini-B -kaapeli ESP32-S3:n USB Host -liitäntään, jossa on oikea VBUS-virransyöttö.</p><div class="sensorgrid" id="measurements"></div></div>
<div class="panel"><h2>Diagnostiikka</h2><div class="pills"><span class="pill" id="mqtt">MQTT: —</span><span class="pill" id="wifi">Wi-Fi STA: —</span><span class="pill" id="uptime">Käynnissä: —</span></div><p class="footer">JSON-rajapinnat: <a href="/status">/status</a> ja <a href="/measurements">/measurements</a>.</p></div>
</section>
<section id="curves" class="hidden"><h1>L1-lämmityskäyrä</h1><p class="sub">Säädettävät viisi menoveden tavoitelämpötilaa ulkolämpötilan mukaan.</p>
<div class="warning"><strong>Tärkeä turvallisuusrajoitus.</strong> Oumanin varmaa GET PROPERTY -takaisinlukua ei ole vahvistettu. Kentissä ei näytetä nykyisiä säätimen asetuksia. Lähetettyä arvoa ei pidä pitää voimassa olevana asetuksena ennen kuin se on tarkistettu fyysisestä säätimestä. Säätö ei saa korvata Oumanin omia turvarajoituksia. PID-säätöjä tai venttiilin käsiajoa ei tarjota.</div>
<div class="panel"><h2>Käyräpisteet</h2><p class="sub" id="write-lock">Tarkistetaan kirjoitusoikeutta...</p><div class="curve" id="curve-fields"></div><div class="protect"><label for="pass">Säätösalasana</label><div style="margin:8px 0 13px"><input id="pass" type="password" autocomplete="off" placeholder="Korttiin asetettu erillinen salasana"></div></div><button class="action" id="save" onclick="submitCurve()" disabled>Lähetä yksi käyräpiste Oumaniin</button><p class="footer">Tallenna aina vain yksi piste kerrallaan. Sallittu arvo testiversiossa 15–70 °C, 0,1 °C askelin. Vahvistuskoodi ja 15 sekunnin lähetysväli estävät vahinkopainalluksia. Asetuksia ei voi palauttaa automaattisesti.</p><div id="result" class="result">Ei säätöyrityksiä.</div></div>
</section><p class="footer">Kokeellinen yhteisöprojekti. Ei turvallisuussertifioitu lämmitysjärjestelmän ohjain. Ei pilviyhteyttä; sivu toimii suoraan ESP32:n Wi-Fi-verkossa.</p>
</main><script>
const names=['L1 laskettu tavoite','Mittaus 2','Mittaus 3','Mittaus 4','Mittaus 5','Mittaus 6','L1 laskettu tavoite 2','Mittaus 8','L1 menoveden lämpötila','Ulkolämpötila','Ulkolämpötila korjattu','Mittaus 12','Mittaus 13','Mittaus 14','L1 laskettu venttiiliasento','L1 venttiilin asento','Mittaus 17','Mittaus 18','Mittaus 19','Mittaus 20','Viivästetty ulkolämpötila','Mittaus 22','Mittaus 23','Mittaus 24','Mittaus 25','Mittaus 26','Mittaus 27','Digitaalitulo'];
const points=[[-20,67],[-10,69],[0,71],[10,73],[20,75]];
const $=id=>document.getElementById(id);
let canWrite=false;
function show(page){for(const p of ['monitor','curves']){$(p).classList.toggle('hidden',p!==page);$('nav-'+p).classList.toggle('selected',p===page);}}
$('measurements').innerHTML=names.map((name,i)=>'<div class="sensor"><div class="name">'+name+'</div><div class="value" id="m'+i+'">—</div><div class="index">Kanava '+String(i+1).padStart(2,'0')+'</div></div>').join('');
$('curve-fields').innerHTML=points.map(([outside,id])=>'<div class="card"><label for="v'+id+'">Ulkolämpötila '+(outside>0?'+':'')+outside+' °C — Ouman ID '+id+'</label><input id="v'+id+'" placeholder="Ei luettu" type="number" min="15" max="70" step="0.1" inputmode="decimal"></div>').join('');
let selectedId=67;
$('curve-fields').addEventListener('focusin',e=>{if(e.target?.tagName==='INPUT') selectedId=Number(e.target.id.substring(1));});
async function getJSON(url){const r=await fetch(url,{cache:'no-store'});if(!r.ok)throw Error('HTTP '+r.status);return await r.json();}
async function update(){try{let s=await getJSON('/status');$('usb').textContent=s.usb_mounted?'Yhdistetty':'Ei yhteyttä';$('usb').className=s.usb_mounted?'good':'bad';$('fresh').textContent=s.fresh?'Tuore ('+s.last_age_seconds+' s)':'Ei tuoreita tietoja';$('fresh').className=s.fresh?'good':'bad';$('cycles').textContent=s.successes+' / '+s.failures;$('wifi').textContent='Wi-Fi STA: '+(s.wifi?'yhdistetty':'pois');$('mqtt').textContent='MQTT: '+(s.mqtt?'yhdistetty':'ei käytössä');$('uptime').textContent='Käynnissä: '+s.uptime_seconds+' s';$('network').textContent=s.ap_ssid||'OUMAN-ESP32';canWrite=!!s.curve_writes_enabled;$('write-lock').textContent=canWrite?'Säädöt käytettävissä vain erillisellä salasanalla.':'Säätö lukittu firmware-asetuksella. Mittauksia voi silti lukea.';$('save').disabled=!canWrite||!s.usb_mounted;$('notice').textContent=s.fresh?'Mittaukset ovat tuoreita.':'Mittauksia ei ole vielä saatu. USB-tunnistus ja laitteiston virransyöttö pitää varmistaa.';
if(s.fresh){let data=await getJSON('/measurements');data.measurements.forEach((v,i)=>{$('m'+i).textContent=Number(v).toFixed(1)+' '+((data.units||[])[i]||'');});}
else {for(let i=0;i<28;i++)$('m'+i).textContent='—';}
let w=await getJSON('/api/write/status');$('result').textContent='Tila: '+w.state+'\n'+w.details+(w.id?'\nKäyräpisteen tunnus: '+w.id:'');
}catch(e){$('usb').textContent='Ei yhteyttä';$('usb').className='bad';$('notice').textContent='Selain ei saanut yhteyttä ESP32:n palvelimeen: '+e.message;}}
async function submitCurve(){if(!canWrite)return;const id=selectedId,input=$('v'+id),value=Number(input.value.replace(',','.'));if(!input.value||!Number.isFinite(value)||value<15||value>70){alert('Valitse kenttä ja syötä luku välillä 15–70 °C.');return;}const confirmTxt='Kirjoita OK vahvistaaksesi käyräpisteen '+id+' uuden arvon '+value.toFixed(1)+' °C.\n\nOumanin nykyistä arvoa ei voida lukea automaattisesti takaisin.';if(prompt(confirmTxt)!=='OK')return;const pass=$('pass').value;if(pass.length<12){alert('Anna erillinen vähintään 12 merkin säätösalasana.');return;}const body='id='+encodeURIComponent(id)+'&value='+encodeURIComponent(value.toFixed(1));$('save').disabled=true;try{const r=await fetch('/api/write',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded','X-Ouman-Key':pass},body});const answer=await r.text();$('result').textContent='Palvelin: '+r.status+' '+answer;}catch(e){$('result').textContent='Lähetys epäonnistui: '+e.message;}finally{$('pass').value='';}}
update();setInterval(update,5000);
</script></body></html>)OUMANHTML";

void sendNoCache() {
  server.sendHeader("Cache-Control", "no-store");
  server.sendHeader("X-Content-Type-Options", "nosniff");
  server.sendHeader("X-Frame-Options", "DENY");
}

const CurveOption* findCurve(int prop) {
  for (size_t i=0; i<CURVE_COUNT; ++i) if (CURVE[i].id==prop) return &CURVE[i];
  return nullptr;
}

void handleRoot() {
  sendNoCache();
  server.send_P(200, "text/html; charset=utf-8", DASHBOARD_HTML);
}

void handleWriteStatus() {
  sendNoCache();
  String body = "{\"state\":\"" + writeState + "\",\"details\":\"" + writeDetails + "\",\"id\":" + String(requestedId) + "}";
  server.send(200, "application/json", body);
}

void handleWrite() {
  sendNoCache();
  // Fail closed until user changes firmware flags and a strong secret.
  if (!ENABLE_CURVE_WRITES || strcmp(WRITE_PASSWORD,"CHANGE_ME_BEFORE_ENABLING")==0 || strlen(WRITE_PASSWORD)<12) {
    server.send(403,"text/plain", "Setpoint writing disabled in firmware"); return;
  }
  if (server.header("X-Ouman-Key") != String(WRITE_PASSWORD)) {
    server.send(403,"text/plain", "Invalid separate write password"); return;
  }
  if (server.hasHeader("Origin") && server.header("Origin") != String("http://")+server.hostHeader()) {
    server.send(403,"text/plain", "Origin rejected"); return;
  }
  if (!oumanSerial.mounted()) {
    server.send(503,"text/plain", "Ouman USB disconnected"); return;
  }
  if (writeQueued || writing) {
    server.send(409,"text/plain", "A write is already pending"); return;
  }
  if (lastWriteStartMs != 0 && millis()-lastWriteStartMs < WRITE_COOLDOWN_MS) {
    server.send(429,"text/plain", "Wait 15 seconds between changes"); return;
  }
  const String idText = server.arg("id");
  const String valueText = server.arg("value");
  if (idText.length()==0 || idText.length()>4 || valueText.length()==0 || valueText.length()>6) {
    server.send(400,"text/plain", "Missing or invalid parameters"); return;
  }
  for (unsigned i=0;i<idText.length();++i) if (!isDigit(idText[i])) {
    server.send(400,"text/plain", "Bad property ID"); return;
  }
  int id = idText.toInt();
  if (!findCurve(id)) {server.send(400,"text/plain", "Property not on approved curve allowlist");return;}
  char *endptr=nullptr;
  float degrees = strtof(valueText.c_str(), &endptr);
  if (!endptr || *endptr!='\0' || !isfinite(degrees) || degrees<15.0f || degrees>70.0f) {
    server.send(400,"text/plain", "Value must be from 15.0 to 70.0 C");return;
  }
  int raw = (int)lroundf(degrees*10.0f);
  if (fabsf(degrees - raw/10.0f) > 0.0005f) {
    server.send(400,"text/plain", "Use 0.1 C steps");return;
  }
  requestedId = (uint16_t)id;
  requestedRaw = raw;
  writeQueued=true;
  writeState="queued";
  writeDetails="Queued for USB; no controller change confirmed yet";
  server.send(202,"text/plain", "Accepted into queue; check /api/write/status");
}

void startWrite() {
  writeQueued=false;
  if (!oumanSerial.mounted()) {
    writeState="failed";writeDetails="USB disconnected before command";return;
  }
  while (oumanSerial.available()) oumanSerial.read();
  char cmd[48];
  snprintf(cmd, sizeof(cmd), "SET PROPERTY %u %d\n", (unsigned)requestedId, requestedRaw);
  size_t len=strlen(cmd);
  size_t sent=oumanSerial.write((const uint8_t*)cmd,len);
  if (sent!=len) {
    writeState="failed";writeDetails="Could not transmit complete command";return;
  }
  oumanSerial.flush();
  rxUsed=0;rx[0]='\0';
  writing=true;writeStartedMs=millis();lastByteMs=writeStartedMs;lastWriteStartMs=writeStartedMs;
  writeState="waiting";writeDetails="Sent; waiting for Ouman PROPERTY(...) response";
}

void finishWrite() {
  writing=false;
  rx[rxUsed]='\0';
  // The controller must acknowledge BOTH the exact requested property and value.
  // This is only an acknowledgement, NOT independent side-effect-free readback.
  bool confirmed=false;
  const char *it=rx;
  while ((it=strstr(it,"PROPERTY("))!=nullptr) {
    it += strlen("PROPERTY(");
    char *idEnd=nullptr;
    long id=strtol(it,&idEnd,10);
    if (idEnd==it || *idEnd!=')')continue;
    const char *lineEnd=strchr(idEnd,'\n');
    if (!lineEnd)lineEnd=rx+rxUsed;
    const char *eq=(const char*)memchr(idEnd,'=',lineEnd-idEnd);
    if (!eq)continue;
    char *valEnd=nullptr;
    long value=strtol(eq+1,&valEnd,10);
    if (valEnd==eq+1)continue;
    if (id==requestedId && value==requestedRaw){confirmed=true;break;}
  }
  if (confirmed) {
    writeState="acknowledged";
    writeDetails="Ouman acknowledged requested value; VERIFY ON PHYSICAL DISPLAY";
  } else {
    writeState="failed";
    writeDetails="No exact property/value acknowledgement; do not assume setting applied";
  }
  nextPollMs=millis()+1000;
}

void serviceWriteReply() {
  uint16_t budget=512;
  while (budget-- && oumanSerial.available()>0) {
    int c=oumanSerial.read();if(c<0)break;
    if (rxUsed + 1 >= MAX_WRITE_REPLY) {finishWrite();return;}
    rx[rxUsed++]=char(c);lastByteMs=millis();
  }
  unsigned long now=millis();
  if ((rxUsed && now-lastByteMs>=QUIET_MS) || now-writeStartedMs>=WRITE_TIMEOUT_MS) finishWrite();
}

void handleStatus() {
  String response = "{";
  response += "\"device\":\"Ouman EH-800B S3\",";
  response += "\"wifi\":" + String(WiFi.status() == WL_CONNECTED ? "true" : "false") + ",";
  response += "\"ap_ssid\":\"" + String(AP_SSID) + "\",";
  response += "\"ap_ip\":\"" + WiFi.softAPIP().toString() + "\",";
  response += "\"sta_ip\":\"" + (WiFi.status() == WL_CONNECTED ? WiFi.localIP().toString() : String("")) + "\",";
  response += "\"usb_mounted\":" + String(oumanSerial.mounted() ? "true" : "false") + ",";
  response += "\"mqtt\":" + String(mqtt.connected() ? "true" : "false") + ",";
  response += "\"curve_writes_enabled\":" + String(ENABLE_CURVE_WRITES && strcmp(WRITE_PASSWORD,"CHANGE_ME_BEFORE_ENABLING")!=0 && strlen(WRITE_PASSWORD)>=12 ? "true":"false") + ",";
  response += "\"fresh\":" + String(validReadings && oumanSerial.mounted() && millis()-lastSuccessMs < 45000 ? "true":"false") + ",";
  response += "\"last_age_seconds\":" + String(validReadings ? ((millis()-lastSuccessMs)/1000) : 0) + ",";
  response += "\"channels\":" + String(lastValidChannels) + ",";
  response += "\"successes\":" + String(totalSuccess) + ",";
  response += "\"failures\":" + String(totalFailures) + ",";
  response += "\"uptime_seconds\":" + String(millis() / 1000) + "}";
  server.send(200, "application/json", response);
}

void handleMeasurements() {
  if (!validReadings || !oumanSerial.mounted() || millis() - lastSuccessMs > 45000) {
    server.send(503, "application/json", "{\"error\":\"no fresh measurements\"}");
    return;
  }
  String response = "{\"measurements\":[";
  for (uint8_t i = 0; i < CHANNELS; ++i) {
    if (i) response += ",";
    response += String(readings[i], 2);
  }
  response += "],\"units\":[";
  for (uint8_t i=0;i<CHANNELS;++i) {
    if(i)response+=",";
    response+="\"" + String(readingUnits[i]) + "\"";
  }
  response+="]}";
  server.send(200, "application/json", response);
}

void startMeasurement() {
  while (oumanSerial.available()) oumanSerial.read(); // discard stale response
  const char command[] = "MEASUREMENTS\n";
  size_t n = oumanSerial.write((const uint8_t *)command, sizeof(command) - 1);
  if (n != sizeof(command) - 1) { ++totalFailures; nextPollMs = millis() + POLL_MS; return; }
  oumanSerial.flush();
  rxUsed = 0;
  rx[0] = '\0';
  awaiting = true;
  readStartedMs = millis();
  lastByteMs = readStartedMs;
  nextPollMs = readStartedMs + POLL_MS;
}

void finishMeasurement() {
  awaiting = false;
  rx[rxUsed] = '\0';
  float parsed[CHANNELS];
  char units[CHANNELS][4] = {{0}};
  const size_t count = parseMeasurements(rx, parsed, units, CHANNELS);
  lastValidChannels = count;
  if (count == CHANNELS) {
    memcpy(readings, parsed, sizeof(readings));
    memcpy(readingUnits, units, sizeof(readingUnits));
    validReadings = true;
    lastSuccessMs = millis();
    ++totalSuccess;
    publishValues();
  } else {
    ++totalFailures;
    reportAvailability();
  }
}

void serviceOuman() {
  bool mounted = oumanSerial.mounted();
  if (mounted != previouslyMounted) {
    previouslyMounted = mounted;
    awaiting = false;
    if (!mounted && (writeQueued || writing)) {
      writeQueued=false;writing=false;
      writeState="failed";writeDetails="USB disconnected during pending write";
    }
    nextPollMs = millis();
    if (!mounted) { validReadings = false; reportAvailability(); }
  }
  if (!mounted) return;
  if (writing) {serviceWriteReply();return;}
  if (awaiting) {
    // Continue collecting a measurement response without mixing it with writes.
  } else {
    if (writeQueued) {startWrite();return;}
    if ((int32_t)(millis() - nextPollMs) >= 0) startMeasurement();
    return;
  }
  // Nonblocking receive. USBHost.task() and Wi-Fi must continue to run.
  uint16_t budget = 512;
  while (budget-- && oumanSerial.available() > 0) {
    const int c = oumanSerial.read();
    if (c < 0) break;
    if (rxUsed + 1 >= RX_CAPACITY) { finishMeasurement(); return; }
    rx[rxUsed++] = char(c);
    lastByteMs = millis();
  }
  unsigned long now = millis();
  if ((rxUsed && now - lastByteMs >= QUIET_MS) ||
      now - readStartedMs >= READ_TIMEOUT_MS) finishMeasurement();
}
}

void setup() {
  Serial.begin(115200); // use UART0 if OTG host takes the native USB PHY
  delay(400);
  Serial.println("Ouman EH-800B ESP32-S3 Arduino USB Host (READ ONLY)");
  baseTopic = MQTT_TOPIC_PREFIX;
  clientId = "ouman-s3-" + String((uint32_t)ESP.getEfuseMac(), HEX);
  availabilityTopic = baseTopic + "/status";

  bool useStation = (WIFI_SSID[0] != '\0' && strcmp(WIFI_SSID, "YOUR_WIFI_NAME") != 0);
  WiFi.mode(useStation ? WIFI_AP_STA : WIFI_AP);
  WiFi.softAPConfig(IPAddress(192, 168, 4, 1), IPAddress(192, 168, 4, 1), IPAddress(255, 255, 255, 0));
  if (!WiFi.softAP(AP_SSID, AP_PASSWORD)) {
    Serial.println("ERROR: Wi-Fi access point could not start");
  } else {
    Serial.print("MacBook Wi-Fi SSID: "); Serial.println(AP_SSID);
    Serial.print("Open http://"); Serial.print(WiFi.softAPIP()); Serial.println("/status");
  }
  if (useStation) {
    WiFi.setAutoReconnect(true);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    lastWiFiAttemptMs = millis();
  }
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setBufferSize(768);
  mqtt.setKeepAlive(30);

  const char *authHeaders[] = {"X-Ouman-Key", "Origin"};
  server.collectHeaders(authHeaders, 2);
  server.on("/", HTTP_GET, handleRoot);
  server.on("/api/write/status", HTTP_GET, handleWriteStatus);
  server.on("/api/write", HTTP_POST, handleWrite);
  server.on("/status", HTTP_GET, handleStatus);
  server.on("/measurements", HTTP_GET, handleMeasurements);
  server.begin();

  if (!USBHost.begin()) Serial.println("ERROR: USB Host init failed");
  // begin(0) does not force USB CDC SET_LINE_CODING. Ouman is USB CDC, not TTL UART.
  oumanSerial.begin(0);
  oumanSerial.setTxTimeoutMs(1000);
}

void loop() {
  USBHost.task();
  serviceWifi();
  serviceMqtt();
  server.handleClient();
  serviceOuman();
  // If the last successful read went stale, flag entities unavailable.
  static bool markedStale = false;
  bool stale = !validReadings || !oumanSerial.mounted() || (millis() - lastSuccessMs > 45000);
  if (stale && !markedStale) { reportAvailability(); markedStale = true; }
  if (!stale) markedStale = false;
  delay(2);
}