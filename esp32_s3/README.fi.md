# Ouman EH-800B + ESP32-S3 + Home Assistant (kokeellinen)

**Tama on ESP32-S3:n USB Host -toteutuksen ensimmainen kehitysversio.**
Aiemmin fyysisella EH-800B:lla toimivaksi todettua Home Assistantin v0.1.2-versiota **ei muuteta main-haarassa**.

## Mitä tassa toteutuksessa on

ESP32-S3 ottaa vastaan Oumanin USB CDC-ACM -yhteyden, siirtaa USB-datan Wi-Fin yli TCP-porttiin, ja Raspberry Pi:n Home Assistant tulkitsee edelleen `MEASUREMENTS`-vastauksen nykyisella Ouman Python -integraatiolla. S3 ei itse dekoodaa kaikkia antureita.

```text
Ouman EH-800B Mini-USB (USB CDC-ACM)
      |
      v
USB-A -> Mini-USB cable + POWERED USB hub (5 V VBUS)
      |
      v
ESP32-S3 USB/OTG PORT (GPIO19=D-, GPIO20=D+)
      | Wi-Fi (local LAN only)
      v
TCP port 8880 (IP allowlist)
      |
      v
Home Assistant (Raspberry Pi 5)
  custom_components/ouman_eh800: sensor only
  port: socket://<ESP_IP>:8880
```

**EI VIELA TESTATTU oikealla ESP32-S3 + EH-800B -parilla!** Kolmannen osapuolen USB-silta ilmoittaa CDC-ACM-tuen, mutta Oumanin laitetunnusta `eb03:0920` ei mainita sen testilaitteissa. Ensiksi varmistetaan USB-laitteen loytyminen ja 28 mittausrivin luku.

## 1. Laitteisto

- ESP32-S3 DevKit (taman esimerkin ESPHome-asetus `esp32-s3-devkitc-1`; muilla korteilla board-asetus voi poiketa)
- S3:n **USB/OTG**-liitin, joka on fyysisesti kytketty GPIO19/GPIO20-pinneihin
- USB OTG -sovitin ja **omalla 5 V virtalahteella toimiva USB-hubi**, tarvittaessa
- USB-A uros / Mini-B -kaapeli Oumanille
- Erillinen riittava virtalahde ESP32-S3:lle
- Home Assistant ja ESPHome Device Builder -lisaosa
- Yhteinen suojattu Wi-Fi/lahiverkko

S3:n USB Host -toiminto ja USB-Serial-JTAG jakavat USB-rautaa. Jos kortilla on kaksi USB-liitinta, USB/OTG-liitin tulee varata Oumanille ja USB/UART-ohjelmointiliitinta kayttaa tarvittaessa ohjelmointiin. Kaikissa S3-korteissa ei ole tarvittavia liittimia tai 5 V USB Host -virransyottoa.

**Ala kytke USB:n 5 V VBUS-linjaa ESP32:n 3,3 V pinniin. Ala yhdista eri 5 V virtalahteita suoraan vastakkain.** Kayta asianmukaista virtalahteellista hubia.

## 2. Asenna firmware ESPHomeen

1. Home Assistant -> Settings -> Add-ons -> ESPHome Device Builder. Avaa ESPHome.
2. Luo `ouman-eh800-s3`-laite ja kopioi sen YAML-sisalloksi [ouman-eh800-s3.yaml](ouman-eh800-s3.yaml).
3. Huolehdi etta ESPHome `secrets.yaml` sisaltaa `wifi_ssid`, `wifi_password`, `api_encryption_key` ja `ota_password`. Encryption key on satunnainen 32 tavun Base64-koodattu avain, esim. generoitu komentorivilla komennolla `python3 -c 'import os,base64; print(base64.b64encode(os.urandom(32)).decode())'`. Aseta oma vahva OTA-salasana.
4. Valitse ESPHome -> Install / Validate. Asenna ensimmainen firmware fyysisesti USB:n kautta. Macissa kayta tarvittaessa **Chrome/Edgea**, koska selaimen Web Serial -tuki vaihtelee ja Safari ei yleensa tue ESPHome Web -USB-asennusta. Tarvittaessa kaanna `.bin` ESPHomessa, ja siirra se [web.esphome.io](https://web.esphome.io/) -palvelulla tuettuun selaimeen.
5. Kun S3 liittyy Wi-Fiin, avaa `http://ouman-eh800-s3.local/` tai sen IP-osoite. Tama on **USB-sillan oma asetusnakyma**.
6. Kytke Ouman Mini-USB:lla USB Hubiin, joka on kytketty S3:n USB/OTG-porttiin. Irrota Ouman Raspberry Pi:n USB-portista ennen tata.
7. Tarkista, nakyyko USB-laite nimella OUMAN / EH-800 tai tunnuksella **VID:PID eb03:0920**. Jos laite ei nay, ala jatka Home Assistant -asetuksiin.
8. Maarita löydetylle USB-laitteelle TCP-portti **8880**. Aseta baud esim. `115200` (virtuaalisen USB CDC:n siirtonopeusasetus; Oumanin USB-sarjayhteys ei ole fyysinen UART).
9. Aseta sillan HTTP-asetusnakymaan vahva salasana ja USB-laitteen TCP-portin IP-allowlistaksi **vain Home Assistant -palvelimesi IP**. Nykyisen Pi:n IP saattaa olla `192.168.10.231`, mutta varmista se ensin. Tallenna ja kaynnista uudelleen.
10. Tee routeriin DHCP-varaus S3:n IP:lle, jotta TCP-sarjaportin osoite pysyy muuttumattomana.

**Tietoturva:** Upstream-sillan raakaa TCP-liikennetta ei ole salattu eika sarjaportti kayta erillista kirjautumista. HTTP-asetusnakyma tarvitsee oman salasanan ja TCP-portti IP-rajauksen. Ala avaa TCP-porttia 8880 internetiin, Tailscale-funneleihin tai portinohjauksella julkiseksi. Pelaa turvallisesti: aloita vain lukemalla antureita.

## 3. Testaa Ouman ilman Home Assistant -ohjelmamuutoksia

Suorita Macin Terminalissa tai muulla saman lahiverkon koneella:

```bash
python3 esp32_s3/test_ouman_tcp.py --host 192.168.10.50 --port 8880
```

Korvaa `192.168.10.50` S3:n oikealla IP:lla. Testi lahettaa vain yhden `MEASUREMENTS`-kaskyn. Se odottaa 28 mittausrivia; jos ehto ei tayty, tulostaa virheen.

Jos testilaite ei vastaa, katso sillan asetusnakymaa ja USB discovery -lokia. Ala yrita satunnaisia `SET PROPERTY`-kaskyja diagnostiikkaan.

## 4. Home Assistantin Ouman-integraatio kayttamaan TCP-porttia

Tama GitHubin **feature/esp32-s3-usb-wifi-bridge** -haara sisaltaa muokatun `custom_components/ouman_eh800/ouman.py`-tiedoston. Se kayttaa `serial.serial_for_url(...)`-rajapintaa `socket://`-osoitteella mutta samaa vahvistettua `serial.Serial(...)`-toimintoa vanhalla paikallisella USB-polulla.

Ota nykyisesta HA-konfiguraatiosta **varmuuskopio**. Jos aiempi Ouman-integraatio on jo asennettuna, tee `ouman.py`-tiedostosta paikallinen varmuuskopio ja vaihda se kehityshaaran vastaavaan tiedostoon. Varmista, ettei Home Assistant lue samaa Oumania samanaikaisesti paikalliselta USB-polulta.

Konfiguroi `configuration.yaml`:

```yaml
sensor:
  - platform: ouman_eh800
    port: "socket://192.168.10.50:8880"
```

Yhdista tama olemassa olevaan `sensor:`-listaan; **ala luo useita sensor-paavaimia**. Alussa poista tai kommentoi vanha Oumanin `number:`-alusta pois: se sisaltaa oikeita lammitysohjauksen kirjoituksia, myos riskeja aiheuttavia PID-parametreja. Jos `number:` sisaltaa muita laitteita, **ala poista koko number-osiota**, vain Ouman-rivi.

Home Assistantin Terminalissa:

```bash
ha core check
ha core restart
```

Tarkista 15-30 sekunnin jalkeen Developer Tools -> States -> `sensor.ouman_...`. Nakymassa pitaisi olla mittausdataa, jos USB/tcp-transportti toimii.

## 5. Mita ei viela ole vahvistettu

- ESPHome-firmwaren todellinen kaantyminen juuri sinun S3-kortillesi
- Ouman EH-800B:n USB enumeration kolmannen osapuolen sillassa
- 28 sensoririvin eheys pitkassa Wi-Fi-kaytossa
- Kirjoitusohjauksen turvallisuus TCP-sillan yli
- USB-hubin ja laitteen kaynnistysjarjestyksen toimivuus

Tata versiota **ei tule kayttaa ainoana turvallisuuden kannalta kriittisena lammityksen ohjaimena**. Vikatilanteessa Oumanin oma paikallinen ohjaus on ensisijainen.

## 6. Palautus

Jos yhteys epavakaa, irrota Ouman S3:sta ja kytke takaisin Raspberry Pi:n USB-porttiin. Palauta alkuperainen `ouman.py` paikallisesta varmuuskopiosta, ja vaihda `sensor:`-alustan portiksi alkuperainen:

```yaml
sensor:
  - platform: ouman_eh800
    port: /dev/serial/by-id/usb-OUMAN_Ouman_EH-800-if00
```

Kaynnista HA uudelleen. Stable `main` on edelleen koskematon.

Kolmannen osapuolen USB-silta: https://github.com/ESDN83/esp-ha-usb-gateway (MIT)
