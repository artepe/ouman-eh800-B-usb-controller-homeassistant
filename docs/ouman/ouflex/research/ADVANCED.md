# Ouflex: todellinen laitetutkimus 11.11.2026

Tämä ajo varmisti paikalliset FTP- ja Modbus-luvut. **Laitteelle ei tehty
kirjoituksia, firmwaremuutoksia eikä LCD-muutoksia.** Toimilaitteista irrotus
on vielä vahvistamatta. Täydellinen takaisinmallinnus ja oma natiiviohjelmisto
jäävät avoimiksi; tämän muutoksen tulos on toistettava lukututkimus ja sen
työkalut, XML-dekooderi sekä HA:n kartan tuonti ja rekisteriselain.

## Tunnistus ja FTP

| Lähde | Havainto | Rajaus |
|---|---|---|
| `deviceversion.txt` | `2.3.3` | Todellinen FTP-luku |
| FC03, dokumentoitu osoite 15 / PDU 14 | `233` | Tukee laiteversiota 2.3.3 |
| Ounet XML + osoite 16 / PDU 15 | sovellus `1.1.2`, raaka `112` | XML:n ja rekisterin vastaavuus; näyttövertailu puuttuu |
| Osoite 17 / PDU 16 | IO-version raaka `251` | Debug-loki ilmoittaa IO-ohjelmiston 2.51 |
| Debug-käynnistyslokit | OUFLEX Device; platform software 1.8.6; platform firmware 1.0.10; build Jan 18 2016 12:45:55 | Tallennettuja käynnistyslokeja, ei ajantasainen prosessikysely |

Anonyymi FTP toimii. Juuren `files` on pienikirjaiminen. Hakemistossa on
`ounetDescrFile_fi-FI.xml` (101133 tavua) ja `EhnetDescrFile_fi-FI.xml`
(26915 tavua). Molemmat haettiin kahdesti ja kopiot olivat tavutasolla samat.
Ounet-kuvaus on sovellusversiota 1.1.2; vanhempi Ehnet-kuvaus ilmoittaa
0.0.0, joten sitä ei nostettu nykyisen sovelluksen kirjoituskartaksi.

Juuren muut tiedostot: `modulereport.txt` (9717 tavua), `deviceversion.txt`
(6), `lastupdate.txt` (245), `diagnostics.updateready` (tyhjä merkintä).
`new_application`, `updates`, `rammount` ja `commands` listautuivat tyhjinä.
Niissä ei suoritettu toimintoja eikä tiedostoja siirretty laitteeseen.
`debug` sisälsi `wd.log`-tiedoston ja neljä `errordebug*.txt`-tiedostoa;
kaikki kopioitiin lukemalla.

`modulereport.txt` on debuglohkoja ja moduulitunnisteita sisältävä loki,
ei luettelo asennetuista I/O-laajennuksista. Sovellus viittaa perus-I/O:hon;
laajennusmoduulien fyysistä läsnäoloa ei varmistettu. Watchdog-lokissa on
historiallisia platform-viiveitä, I/O-päivitysvirheitä ja uudelleenkäynnistyksiä.
Niistä ei päätellä laitteen nykyistä vikaa tai toimilaitteiden turvallista tilaa.

Raaka-XML sisältää kohteen osoitteen, yhteystietokenttiä ja lataajatunnisteen.
Raakatiedostot, laitekohtainen kartta, sarjanumerot, asetusarvot ja täydet
lokit jäävät gitin ulkopuolelle `ouflex-results/advanced/`- ja
`ouflex-results/advanced-ftp-repeat/`-hakemistoihin. Julkaistu CSV sisältää
vain osoitteet, tyypit ja vastaustilastot, ei kohdekonfiguraation arvoja.

## Modbus: laitteella varmennetut luvut

[hardware-summary.json](hardware-summary.json),
[verified-registers.csv](verified-registers.csv) ja
[protocol-observations.json](protocol-observations.json) ovat tämän ajon
redaktoidut tulokset. CSV käyttää erikseen PDU-osoitetta ja dokumentin
1-alkuista osoitetta; niitä ei saa sekoittaa.

- TCP 502, Unit ID 1: FC03 osoite 0 / yksi sana palautti 0.
- FC01, FC02, FC04 ja FC43/14: osoitteen 0 kokeet (tunnistuksessa ei osoitetta)
  palauttivat poikkeuskoodin 1, Illegal Function.
- Ounet-kuvauksen **240/240 yksittäistä pistettä** vastasi FC03:een:
  139 S32-, 99 U16- ja 2 S16-pistettä, yhteensä 379 eri rekisterisanaa.
- Kuusi XML:n 120 rekisterin aikaohjelma-aluetta luettiin 30 sanan erissä:
  **24/24 pyyntöä, 720 sanaa**. Tämä varmistaa luettavuuden, ei vielä
  tapahtumien formaattia tai oikeaa aikaohjelmakirjoitusta.
- Unit ID 2, FC03, PDU 0, yksi sana: ei vastausta 2 sekunnissa.
  Muita Unit ID:itä ei kokeiltu. Unit 1 vastasi kalenterilukuihin ja erilliseen
  loppukokeeseen; laite ei jäänyt vastaamattomaksi. Viimeinen erillinen
  varmistus oli `000100000006010300000001` → `0001000000050103020000`.
- Porttien 503–505 avoimuus on käyttäjän aiempi havainto. Tässä ajossa ei
  tehty tuntemattomien yhdyskäytäväosoitteiden skannausta.

S32:n kahden komplementin high-word/high-byte-tulkinta ja desimaalikerroin
antavat esimerkiksi XML:ssä lämpötilaksi nimetystä pisteestä `ffff fe0c`
→ −50.0 °C. Tämä **ei todista anturin fyysistä lämpötilaa tai ehjyyttä**.
Näytön ja mittauslaitteen vertailut puuttuvat. Tuntemattomia osoitteita ei
nimetty eikä tämän sovelluksen karttaa yleistetty muihin Ouflexeihin.

Hälytysten maskit tulevat tästä XML:stä: aktiivisuus 1, kuittaamattomuus 2,
prioriteetti 28, **ryhmä 480 (neljä bittiä)**. Tämä poikkeaa aiemmin luetun
yleisohjeen kolmen bitin ryhmästä. Dekooderi käyttää pisteen omia maskeja.
Kuittaus- ja siirtokuittausosoitteet säilyvät metadatassa; ne eivät ole
palautettavia asetusarvoja eikä niitä kirjoiteta yleisellä kirjoitustyökalulla.

## Kirjoitukset ja simulaattori

FC06/FC16:n aiempi suojattu laboratoriotransaktio säilyy: dokumentoitu RW-piste,
rajat, täsmälliseen karttaan sidottu arvioitu politiikka, erilliset kirjoitus-
ja irtikytkentävalinnat, pysyvä alkuarvoloki, takaisinluku ja palautus.
S32 vaatii FC16:n molemmille sanoille. Käsiajon alkuarvo palautetaan erikseen.

Uusi `--observe-display` pysäyttää interaktiivisen `write-test`-ajon onnistuneen
takaisinluvun jälkeen: käyttäjä vertaa aktiivista testiarvoa LCD:hen ja kirjaa
havainnon. Enter jatkaa alkuarvon palautukseen. Myös havaitsijan poikkeus
käynnistää palautuksen. Älä jätä aktiivista testimuutosta ilman valvontaa.
Ilman havaintoa vertailu kirjataan tekemättömäksi. Etukäteen annettu
`--display-note` ei yksin ole todiste fyysisestä näytöstä.

FC05/FC15:n bittipakkaus, kaikuluvun tarkistus ja FC01/FC02-takaisinluku on
lisätty matalan tason asiakkaaseen ja simulaattoriin. Synteettiset testit
kattavat palautuksen, tuntemattomat kelat, virheelliset arvot, tavumäärät ja
padding-bitit. **Tässä laitteessa ei ole dokumentoitua kelakarttaa**:
FC05/FC15:tä ei avata fyysisen laitteen CLI-kirjoituksiin eikä HA:han.
FC01:n Illegal Function ei yksin todista FC05:n käytöstä kumpaankaan suuntaan.

Ounet `writeacceslevel` ei ole yksiselitteinen RW-lippu: myös versio- ja
mittauspisteillä on arvo. Adapteri säilyttää tason todisteena mutta tuo kaikki
pisteet R-tilassa. Kirjoitusehdokas tarvitsee erikseen osoitteen, tyypin,
rajojen ja semantiikan tarkistuksen, dokumentointilähteen ja arvioinnin.
**Yhtäkään fyysistä parametrikirjoitusta ei tässä ajossa vahvistettu.**

## LCD, sovellus ja firmware

XML:ssä parametrin nimi on `point/@name`, tunniste `pointid`, viittaus
`refpointid`, osoite `addressindex`, tyyppi `addressformat`; ryhmittely
`group`/`pointgroup`. Alipiste voi määritellä käsiajolle oman rekisterin.
Ehnet-muodossa vastaavat tiedot ovat `Point/Address` ja `Type`-elementeissä.
Uusi adapteri tukee havaittua Ounet-muotoa; Ehnet ei ole tuettu kirjoitustuonti.

FTP-kuvausten ryhmät ovat verkkokuvauksen rakennetta. Niitä ei ole todistettu
LCD:n alkuperäiseksi valikkopuuksi. Tekstirekistereitä tai LCD:n verkko-API:a
ei löytynyt luetusta kartasta. XML-tiedoston paikallinen nimimuutos ei muuta
laitteen näyttöä. **Näytölle ei ole julkaistu omia tekstejä tai valikoita.**

Debug-lokeissa näkyvät objektien binääritiedostojen polut
`./Device/objects/.../OBJECT_SOFTPOINT.bin`, `OBJECT_BINARY_VALUE.bin` ja
`OBJECT_ANALOG_VALUE.bin`, sovellusobjekteja sekä `./Device/bin/platform`.
Tämä on havainto ohjelmiston objektirakenteesta ja tiedostopoluista, ei
CPU:n, käyttöjärjestelmän, tiedostojen tavumuodon tai bootloaderin tunnistus.
FTP-juuressa ei ollut näitä binäärejä eikä ladattavaa firmwarekuvaa.
`lastupdate.txt` kertoo vanhasta platform/filesystem-päivityksestä mutta ei
päivityspaketin formaattia, allekirjoitusta tai palautusprotokollaa.

REA 6.4.0:n `mcp doctor --json` onnistui: stdio-initialisointi, 208 työkalua,
6 promptia ja `binary_session`. Native-analyysimoottorit puuttuvat.
`inspect-artifact` hylkäsi XML:n unsupported binary format -virheellä;
formaattianalyysi tehtiin Pythonin XML-parserilla. Palvelimen käynnistymistä
ei siis pidä sekoittaa firmwaren onnistuneeseen purkuun.

Oma firmware ja LCD-ajuri vaativat edelleen CPU-/flash-/LCD-piirien tunnistuksen,
liittimet ja jännitetasot, alkuperäisen sovellusbinäärin/projektin,
siirtoprotokollan passiivisen kaappauksen sekä varmennetun palautusreitin.
Lukusuojauksen poistoa, käynnistyslataajan komentoja ja firmwarelatausta ei tehty.

## Home Assistant ja toistaminen

PR #30:n erillinen `ouman_ouflex` ja PR #31:n OpenLVI Discovery Mode on
hyödynnetty yhdistämällä niiden commit-historiat kehityshaaraan, ilman
vastaavien toimintojen uudelleenkirjoittamista. Uudet toiminnot ovat
`ouman_ouflex`-integraatiossa; OpenLVI:n nykyinen tutkinta säilyy lukevana.

Tämän kartan tuonti tuottaa 203 sensor-pistettä, 16 digitaalista binary sensor
-pistettä ja 21 hälytys-binary sensoria sekä yhteysanturin. S32-digitaaliarvot
ovat tuettuja. Number/select/switch-sovittimet toimivat testatussa
simulaattorissa, mutta tämän laitteen kirjoittavia entiteettejä ei aktivoitu.
Kartta ei anna käyttöönotossa kirjoitusoikeutta.

Asetusten rekisteriselain näyttää nimen, dokumentoidun osoitteen, osoitepohjan
ja tyypin. Monivalinnalla valitaan luettavat HA-pisteet ilman koodimuutosta.
Kartan tuonti hyväksyy normalisoidun JSONin tai havaitun Ounet XML:n ja
nollaa kirjoituspolitiikan. Tyhjä valinta hylätään. HA-palvelimelle
192.168.10.231 ei asennettu tai julkaistu muutoksia tämän tutkimuksen aikana.

```sh
# Raaka-aineisto pysyy paikallisena; kohdehakemiston on oltava uusi.
python3 tools/ouflex_ftp.py --out ouflex-results/next-ftp
python3 tools/ouflex_lab.py import-ounet \
  ouflex-results/next-ftp/files/ounetDescrFile_fi-FI.xml \
  --firmware 2.3.3 --out ouflex-results/next-map.json
python3 tools/ouflex_lab.py capture-map --transport nc \
  --map ouflex-results/next-map.json --audit ouflex-results/next-audit.jsonl \
  --out ouflex-results/next-capture.json
```

`--transport nc` käyttää `/usr/bin/nc`:tä ilman shelliä tai telnet-tulkintaa;
MBAP-tarkistukset, aikaraja ja lokitus ovat samat. Tavallinen socket-kuljetus
on oletus ja HA käyttää sitä. Tämän Macin Pythonin suora LAN-connect antoi
`No route to host`, vaikka curl/nc toimivat. Tämä on suoritin-/ympäristöero,
ei osoitus Ouflexin poissaolosta. Lukusarja keskeytyy kuljetusvirheeseen;
protokollan poikkeusvastaukset säilyvät erikseen lokissa.

Testien tulokset ja jäljellä olevat fyysiset kokeet on kirjattu
[ADVANCED_VALIDATION.md](ADVANCED_VALIDATION.md)-tiedostoon.
