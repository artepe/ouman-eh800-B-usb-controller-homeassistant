# Ouman EH-800B + ESP32-S3 – oma Wi-Fi ja selainkäyttöliittymä

> **Kokeellinen Arduino-ohjelma.** Tämä ESP32-S3-versio on erillinen vaihtoehto repositorion vakaalle Home Assistant v0.1.2 -USB-integraatiolle. Arduino-käännöksen onnistumisesta ja ESP32:n oman Wi-Fi-verkon toiminnasta on saatu käyttäjätesti. **Oumanin USB Host -tiedonsiirtoa ja todellista säätöjen kirjoittamista ei ole vielä vahvistettu toimivaksi ESP32-S3:lla.** Ei tuotantolämmityksen turvakäyttöön.

[Arduino-ohjelma (.ino)](Ouman_EH800_S3_Dashboard/Ouman_EH800_S3_Dashboard.ino) · [English documentation](README.md)

## Mitä ESP32-S3-versio tekee?

- Luo oman salasanalla suojatun Wi-Fi-verkon **`OUMAN-ESP32`**.
- Näyttää **OUMAN CONTROL** -käyttöliittymän ilman pilveä, Raspberry Pi:tä tai Home Assistantia osoitteessa **http://192.168.4.1/**.
- Käyttöliittymässä on **Mittaukset**- ja **Lämmityskäyrä**-välilehdet sekä `/status` ja `/measurements` JSON-rajapinnat.
- Yrittää lukea Oumanin USB-huoltoportista `MEASUREMENTS`-komennolla **28 mittauskanavaa noin 15 sekunnin välein**. Kaikkien mittausten merkityksiä ei ole vielä vahvistettu.
- Tukee myös valinnaista kotiverkon Wi-Fiä ja MQTT-sensorien julkaisua Home Assistantiin.
- Lämmityskäyrän säätötoiminto on **oletuksena estetty**. Säätimeltä ei vielä ole luotettavaa nykyarvojen takaisinlukua; näkymän tyhjät kentät **eivät ole Oumanin nykyisiä asetuksia**.

## Tarvittavat laitteet

- **ESP32-S3**, jonka USB OTG / Host -toimintoa voidaan käyttää.
- USB-datakaapeli ESP32:n ohjelmointiin.
- Ouman EH-800/EH-800B:n **USB Mini-B -huoltoportin** johto.
- USB Host -puolelle oikea **5 V VBUS -syöttö**, esimerkiksi **virtalähteellinen USB-hubi**, sekä kortin kytkentään sopiva OTG-USB-liitin.

ESP32-S3:n sisäiset USB D−/D+ -signaalit ovat **GPIO19/GPIO20**, mutta liittimet ja 5 V:n syöttö vaihtelevat korttimalleittain. Tarkista kytkentä ennen kuin yhdistät laitteita. **Älä yhdistä kahta 5 V virtalähdettä suoraan toisiinsa.**

```text
MacBook ---- USB-ohjelmointi ----> ESP32-S3
                                      |
                            USB OTG / HOST
                                      |
                            Virtalahteellinen hubi
                                      |
                             Ouman USB Mini-B
                                      |
                                Ouman EH-800B

MacBook / puhelin --Wi-Fi--> OUMAN-ESP32
Selaimen osoite: http://192.168.4.1/
```

Älä kytke Oumanin samaan USB-palveluporttiin Raspberry Pi -integraatiota ja ESP32-S3:a samanaikaisesti. USB-yhteyttä käyttää kerrallaan **yksi host-laite**.

## Asennus MacBookilla Arduino IDE:llä

1. Valitse GitHubista **Code → Download ZIP** ja pura ladattu tiedosto. Avaa tiedosto `esp32_s3/Ouman_EH800_S3_Dashboard/Ouman_EH800_S3_Dashboard.ino` **Arduino IDE 2** -ohjelmalla. Jos Arduino ehdottaa projektikansion luomista, hyväksy.
2. Asenna Arduino IDE:n **Boards Manager** -osiosta **esp32 by Espressif Systems** (kehityksessä 3.3.12), ja **Library Manager** -osiosta **PubSubClient by Nick O'Leary**. Muut kirjastot tulevat ESP32 Arduino -paketin mukana.
3. Valitse **Tools → Board → ESP32S3 Dev Module** ja oikea **Tools → Port** -USB-sarjaportti, esimerkiksi `/dev/cu.usbmodem...`. Portin numero saattaa muuttua.
4. Wi-Fi-salasana: aseta ohjelman `AP_PASSWORD` omaksi 8–63-merkkiseksi salasanaksi tai jätä `Ouman12345` ennalleen. Julkista oletusta ei koskaan käytetä sellaisenaan: kortti luo silloin ensimmäisellä käynnistyksellä satunnaisen 16-merkkisen salasanan, tallentaa sen flash-muistiin ja tulostaa sen jokaisella käynnistyksellä **Serial Monitoriin (115200)** muodossa `Wi-Fi password: ...`.
5. USB Host -käyttö vaatii kortin ja Arduino-ESP32-version mukaan sopivat USB OTG -asetukset. Saatat joutua valitsemaan **USB CDC On Boot = Disabled**. Jos portti katoaa aiemman USB Host -ohjelman takia: pidä **BOOT** alhaalla, paina kerran **EN/RESET**, vapauta EN ja sitten BOOT. Valitse uudelleen ilmestynyt portti.
6. Paina **Verify**, sitten **Upload** ja odota onnistunutta ohjelmointia. Pelkkä `Sketch uses ...` kertoo vasta käännöksestä. Jos portti on varattu, sulje Arduino IDE:n Serial Monitor.
7. Paina tarvittaessa ESP32:n RESET-painiketta, etsi MacBookin Wi-Fi-listasta **`OUMAN-ESP32`** ja yhdistä siihen omalla AP-salasanallasi. Mac voi huomauttaa internet-yhteyden puuttumisesta, mikä on normaalia.
8. Avaa selaimella **http://192.168.4.1/**. Diagnostiikka löytyy **http://192.168.4.1/status**. Jos `/status` näyttää `"wifi":false` mutta ESP32:n oma verkko toimii, kyse on **kotireititinyhteyden** tilasta, ei oman tukiaseman viasta.
9. Vasta sitten yhdistä Ouman **oikein virtasyötettyyn USB Host -liitäntään** ja seuraa mittauksia. Oikeiden, muuttuvien mittausten vahvistaminen on erillinen testivaihe.

### Jos ZIP on jo työpöydällä

```bash
cd ~/Desktop
unzip Ouman_EH800_S3_Dashboard_v0.2.0.zip -d Ouman_Dashboard
find ~/Desktop/Ouman_Dashboard -name "*.ino" -exec open -a "Arduino IDE" {} \;
```

Tämä komento koskee erikseen ladattua Dashboard ZIP -pakettia. Jos lataat **koko GitHub-repon**, avaa sen sisältä yllä mainittu `esp32_s3/...ino`-tiedosto.

## Valinnainen kotiverkko + MQTT / Home Assistant

Jos et tarvitse MQTT:tä, jätä `WIFI_SSID = "YOUR_WIFI_NAME"` ennalleen: ESP32 toimii omalla Wi-Fi-tukiasemallaan.

Jos haluat kotiverkon ja MQTT:n, täytä lähdekoodista **`WIFI_SSID`**, **`WIFI_PASSWORD`**, **`MQTT_HOST`**, **`MQTT_PORT`**, **`MQTT_USER`** ja **`MQTT_PASSWORD`** ja lataa ohjelma uudestaan. MQTT-brokerin pitää olla käynnissä ja saavutettavissa. ESP32:n oma AP jää edelleen päälle.

**Älä julkaise oikeita Wi-Fi- tai MQTT-salasanojasi GitHubiin.**

## Lämmityskäyrän säädöt ja turvallisuus

Käyräpisteiden ID-lista ohjelmassa: **67, 69, 71, 73, 75**. Ainoastaan pisteen **67** kirjoituksesta on aiempaa fyysisen Oumanin tutkimusnäyttöä; muiden pisteiden oikeaa toimintaa ei ole vahvistettu. Säätö on oletuksena lukittu arvolla `ENABLE_CURVE_WRITES = false`. Ohjelma vaatii lisäksi erikseen asetetun vähintään 12-merkkisen `WRITE_PASSWORD`-salasanan, arvorajauksen ja USB-yhteyden.

**Älä avaa kirjoituksia toimivassa lämmitysjärjestelmässä**, ennen kuin mittaukset toimivat varmasti, jokainen piste on todennettu fyysisellä Oumanilla ja kaikkien alkuperäisten arvojen palauttamiseen on toimiva menettely. Komennon kuittaus ei ole erillinen takaisinluku. Ohjelma ei sisällä PID 56/57/58 -säätöjä eikä venttiilin manuaaliasennon kirjoitusta (92).

Älä avaa ESP32:n HTTP-porttia julkiseen internetiin.

## Vianhaku

| Ongelma | Tarkistus |
|---|---|
| Wi-Fi-verkkoa ei löydy | Varmista **onnistunut Upload**, oikea **Dashboard**-ohjelma, vähintään 8-merkkinen salasana ja RESET. |
| Macissa ei näy USB-porttia | Kokeile USB-datakaapelia, ohjelmointiliitintä, BOOT + EN -lataustilaa ja komentoa `ls /dev/cu.usb*`. |
| Wi-Fi toimii, mutta käyttöliittymä ei aukea | Käytä täsmälleen **http://192.168.4.1/**. Testaa Terminalissa: `curl -i http://192.168.4.1/status`. |
| Mittaukset ovat tyhjiä | Tarkista Oumanin USB-kaapeli, ESP32 USB Host -tila, oikea VBUS-virransyöttö ja Oumanin CDC-ACM-yhteyden muodostuminen. `/measurements` palauttaa HTTP 503 ilman tuoretta mittausta. |
| MQTT-antureita ei näy Home Assistantissa | Tarkista Wi-Fi-reititinyhteys, MQTT-kirjautuminen, broker sekä oikeasti saapuvat mittausarvot. |

## Varmennustilanne

- Arduino ESP32-S3 -käännös: **onnistui käyttäjätestissä**.
- ESP32:n oma Wi-Fi: **toimii käyttäjätestissä**.
- Web-käyttöliittymä: lähdekoodi mukana, mutta riippumatonta laitetestausta ei ole vielä vahvistettu.
- Ouman EH-800B USB Host -mittaukset ja säätöjen kirjoittaminen: **kokeellisia, ei kokonaisuutena vahvistettu**.

Jos käytät Oumania suoraan Raspberry Pi 5 / Home Assistantissa, repositorion juuressa oleva **vakaa v0.1.2** on edelleen ensisijainen ratkaisu. Tämä ESP32-S3-polku on vaihtoehtoinen kokeilu.
