# MacBook/Linux: tulosten keruu

Aja samaan verkkoon tai valmiiseen VPN-/Access-reittiin pääsevästä koneesta. USB:tä ei tarvita.
Alla oletetaan repositorion juuri nykyhakemistoksi. Python-työkalu ei vaadi pip-asennuksia.

```sh
cd ~/Projects/Open-HVACBridge-homeassistant
mkdir -p ouflex-results
python3 tools/ouflex_lab.py --help
python3 tools/ouflex_lab.py discover --host 192.168.10.105 --ports 502,503,504,505 --units 1 --address 1 --address-base 1 --out ouflex-results/discovery.json
python3 tools/ouflex_lab.py identify --host 192.168.10.105 --port 502 --unit 1 --out ouflex-results/identify.json
```

Tunnistusprobe lukee **tuntematonta** PDU-osoitetta 0. Se ei oleta lämpötilaa tai muuta merkitystä. Kelvollinen poikkeusvastauskin vahvistaa Modbus-palvelimen. Unit 1 on ensimmäinen kokeilu, ei kaikkien laitteiden todennettu tunniste. Tarvittaessa tee seuraava **rajattu** kierros `--units 1,2,10,255`. Yhdyskäytävällä käytä näytöltä/projektista vahvistettuja RTU-osoitteita. Älä päättele tyhjää väylää pelkästä aikakatkaisusta.

Vaihda `--host` ja `--port` vain, jos käytössä on tiedossa oleva internet-/Ouman Access -yhteys. Älä arvaa julkista osoitetta. Myös FTP:n ulkoinen portti voi poiketa LAN-portista.

## Kuvaustiedosto

FTP-käyttäjätunnusta ei oleteta eikä salasanoja arvata. Anna tiedossa oleva tunnus. Jos laite hyväksyy anonyymin lukemisen, tunnus on `anonymous`; se on varmennettava laitteella. Salasana luetaan ympäristömuuttujasta eikä sitä tallenneta tuloksiin.

```sh
python3 tools/ouflex_lab.py fetch-map --host 192.168.10.105 --username YOUR_KNOWN_FTP_USER --destination ouflex-results/Files --out ouflex-results/ftp.json
```

Jos FTP ei ole käytössä, ota talteen kuvaus Ounetin olemassa olevasta laitteesta, Tool-projektista tai sen varmuuskopiosta. Ohjelmointityökalun käyttö/oikea versio saattaa vaatia Windows-koneen ja valmistajan lisenssin. Älä asenna uutta sovellusta laitteeseen pelkästään kuvauksen saamiseksi.

Tuo kuvaus vain sen todellisella identiteetillä ja osoitepohjalla. Esimerkkipolku vaihdetaan oikeaan tiedostoon:

```sh
python3 tools/ouflex_lab.py import-map ouflex-results/Files/ACTUAL_DESCRIPTION.xml --format xml --model ACTUAL_MODEL --firmware ACTUAL_VERSION --application ACTUAL_APPLICATION --address-base 1 --out ouflex-results/map.json
python3 tools/ouflex_lab.py map-info --map ouflex-results/map.json
```

Tarkista `rejected_rows` ja kaikki osoitteet alkuperäisestä kuvauksesta. Jos XML-skeemaa ei tunnisteta, säilytä tiedosto muuttamattomana ja lisää sille adapteri. CSV:n tuonti tapahtuu `--format csv` -valinnalla, normalisoidun JSONin `--format json` -valinnalla.

## Lukeminen ja rajattu kartoitus

```sh
python3 tools/ouflex_lab.py capture-map --map ouflex-results/map.json --host 192.168.10.105 --port 502 --unit 1 --out ouflex-results/mapped-read.json
python3 tools/ouflex_lab.py backup --map ouflex-results/map.json --host 192.168.10.105 --port 502 --unit 1 --out ouflex-results/before-snapshot.json
```

Vapaaluennassa anna dokumentoitu osoite tai erikseen valittu rajattu tuntematon alue. Seuraava on syntaksimalli; korvaa ADDRESS/COUNT oikeilla kokonaisluvuilla:

```sh
python3 tools/ouflex_lab.py read --host 192.168.10.105 --port 502 --unit 1 --address ADDRESS --address-base 1 --function 3 --out ouflex-results/read.json
python3 tools/ouflex_lab.py read-block --host 192.168.10.105 --port 502 --unit 1 --address ADDRESS --address-base 1 --count COUNT --out ouflex-results/block.json
python3 tools/ouflex_lab.py scan --host 192.168.10.105 --port 502 --unit 1 --address ADDRESS --address-base 1 --count COUNT --block-size 16 --delay 0.2 --out ouflex-results/scan.json
python3 tools/ouflex_lab.py decode 0xffff 0xff85 --kind s32 --decimals 1
```

Input-alueen lukemiseen `--function 4`. Älä kokeile tuntemattomia kirjoitusfunktioita skannauksen yhteydessä. Yksi epäonnistunut lohkoluku ei kerro, mikä lohkon osoite oli virheellinen: pienennä perustellusti lohkoa, älä nimeä koko aluetta puuttuvaksi.

```sh
python3 tools/ouflex_lab.py export ouflex-results/audit.jsonl --json ouflex-results/export.json --csv ouflex-results/export.csv
python3 tools/ouflex_lab.py compare ouflex-results/before.json ouflex-results/after.json --out ouflex-results/changes.json
python3 tools/ouflex_lab.py report ouflex-results/audit.jsonl --map ouflex-results/map.json --out ouflex-results/report.json
```

Vertailussa avain sisältää IP:n, portin, Unit ID:n, funktion, osoitteen, lukumäärän ja mahdollisen pistenimen. Kahden otoksen tulee käyttää samoja lohkorajoja. Auditissa on erikseen TCP-yhteys, kelvollinen Modbus-vastaus ja onnistunut operaatio. Tuntemattomassa raakaluennassa `datatype`, `interpreted` ja `point_name` jäävät nulliksi tarkoituksella.

## Kirjoitustestit vasta eristetyllä tutkimuslaitteella

1. Vahvista toimilaitteiden ja käytössä olevien järjestelmien fyysinen irrotus. Internet saa olla kytkettynä.
2. Tallenna kartta, alkuperäiset projekti-/backup-tiedostot ja `backup`-snapshot. Tarkista snapshotin `complete` sekä testattavan pisteen sanat.
3. Tee [MAP_FORMAT.md](MAP_FORMAT.md):n erillinen politiikka. Valitse vain dokumentoitu RW-asetusarvo, todellinen tyyppi, rajat ja pieni tarkoituksenmukainen testimuutos. Kuittaus-/kalenterikomennot eivät ole palautettavia asetusarvoja.
4. Aja yksi piste kerrallaan. 32-bittiselle pisteelle vain FC16. FC06 ja FC16 testataan erikseen aidolle U16-pisteelle.
5. Vertaa näyttöön paikallisesti **testiarvon ollessa voimassa**. CLI tekee palautuksen heti eikä odota käyttäjää; erillinen havaitsija voi seurata näyttöä. Älä merkitse näyttövertailua tehdyksi etukäteen. Jos muutos on liian nopea havaittavaksi, tarvitaan erikseen hallittu mittausmenettely.
6. Tarkista `test_confirmed`, `restored`, `errors`, audit ja näyttö. Epäselvä vastaus ei oikeuta merkitsemään kirjoitusta epäonnistuneeksi ilman takaisinlukua.

Seuraavat ovat syntaksimalleja, eivät käyttövalmiita kirjoituskohteita:

```sh
python3 tools/ouflex_lab.py write-test --map ouflex-results/map.json --policy ouflex-results/reviewed-policy.json --key ACTUAL_VERIFIED_U16_KEY --value ACTUAL_TEST_VALUE --function 6 --enable-write-tests --confirm-disconnected --out ouflex-results/u16-fc06-test.json
python3 tools/ouflex_lab.py write-test --map ouflex-results/map.json --policy ouflex-results/reviewed-policy.json --key ACTUAL_VERIFIED_U16_KEY --value ACTUAL_TEST_VALUE --function 16 --enable-write-tests --confirm-disconnected --out ouflex-results/u16-fc16-test.json
python3 tools/ouflex_lab.py write-test --map ouflex-results/map.json --policy ouflex-results/reviewed-policy.json --key ACTUAL_VERIFIED_S32_KEY --value ACTUAL_TEST_VALUE --function 16 --enable-write-tests --confirm-disconnected --out ouflex-results/s32-test.json
```

`write` käyttää samoja sallintatarkistuksia ja takaisinlukua, mutta **jättää uuden arvon voimaan**. Käsiajolliselle pisteelle käytetään vain palauttavaa `write-test`-menettelyä. CLI ei tee firmwarepäivityksiä, nollauksia tai tuntemattomien osoitteiden kirjoituksia.

Palauta tämän koneen tuottamat tulostiedostot jatkoanalyysiin; älä julkaise tunnuksia, koko kohteen yksityisiä karttoja tai audit-lokia avoimeen GitHubiin ilman tarkistusta.
