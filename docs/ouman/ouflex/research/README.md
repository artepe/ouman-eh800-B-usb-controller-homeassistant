# Ouman Ouflex: tutkimus ja kokeellinen OpenHVAC-moduuli

Uusin laiteajo: [ADVANCED.md](ADVANCED.md). FTP-kuvaukset ja versiot sekä
240/240 pisteen ja 720 kalenterirekisterin FC03-luvut on nyt varmennettu.
Kirjoituksia ja fyysisen LCD:n muutoksia ei ole vahvistettu.

**Alla on aiemman PR #30 -vaiheen historiallinen lähtötilanne**, jonka
verkkorajoitukset ja puuttuva pistekartta eivät kuvaa uusinta ajoa.
Uusimmat todisteet ja rajaukset ovat yllä linkitetyssä tutkimusraportissa.

## Mitä on toteutettu

- `tools/ouflex_lab.py`: oikea Modbus TCP MBAP -asiakas ilman ulkoisia Python-riippuvuuksia; macOS/Linux, Python 3.9+.
- `discover`, `identify`, `scan`, `read`, `read-block`, `decode`, `import-map`, `export`, `compare`, `write`, `write-test`, `report`.
- Lisäksi `fetch-map` (vain FTP:n luku), `capture-map`, `map-info`, `backup` ja yhden pisteen `restore`.
- Erillinen `custom_components/ouman_ouflex/`-integraatio omalla domainilla. Nykyisiä Ouman-/OpenLVI-ajureita ei muuteta.
- Sensor-, binary sensor-, alarm-, number-, select- ja switch-sovittimet. Kirjoittava entiteetti syntyy vasta erikseen hyväksytystä ja fyysisesti varmennetusta pisteestä. Muuten piste näkyy sensorina.
- Alueittainen luku, eksplisiittinen Unit ID ja osoitepohja, poikkeusten ja viiveiden lokitus, tietotyypit sekä takaisinluku ja alkuarvojen palautus.
- Synteettinen TCP-palvelin ja testit. Synteettisen kartan osoitteilla ei ole yhteyttä oikean Ouflexin karttaan.

## Todelliset havainnot ja rajat

[environment-probe.json](environment-probe.json) sisältää neljä CLI:n oikeaa yhteysyritystä: portit 502–505, Unit ID 1, FC03, PDU-osoite 0. Kaikki estyivät **ennen TCP-yhteyttä** virheeseen `Operation not permitted`. Osoite 0 on tunnistuskokeen raakaosoite, **ei tunnistettu mittauspiste**. Myös erillinen FTP-portin 21 TCP-kokeilu estyi. Käyttäjän aiemmat ping-/porttihavainnot ovat käyttäjän ilmoittamia, eivät tämän ajon varmennuksia.

Ympäristö estää myös loopback-palvelimen bind-kutsun. Paikallisesti suoritetut protokollatestit käyttävät tavutasolla toimivaa socket-testikaksoista. Varsinaiset TCP-palvelintestit ohitettiin paikallisesti mutta läpäisivät GitHub CI:ssä Python 3.9- ja 3.13-ajoissa. Home Assistant ei ole paikallisesti asennettu; paikalliset HA-testit ovat sovittimen sopimustestejä kehystestikaksoisilla. Erillinen CI-ajo läpäisi kaikki neljä testiä oikealla Home Assistant 2026.11.1 -kehyksellä ja simuloidulla laiteyhteydellä.

Lähdepuu haettiin GitHub-liittimellä main-commitista `71b6ac3d654735f476dbd939f047b03b2d434b98`, koska shellin DNS-verkkoyhteys GitHubiin estyi. Paikallinen lähdekopio koottiin ensin vertailusnapshotiksi, minkä jälkeen aidot GitHub-commitit ja puut rekonstruoitiin ja niiden SHA:t tarkistettiin. Paikallinen repository on nyt aitoon main-commitiin päättyvä shallow-checkout, joka seuraa origin/feature/ouflex-lab-haaraa.

Käyttäjä kertoi myöhemmin laitteen olevan internetissä ja hyväksyi laitteen rikkoutumisen riskin. Julkinen/Ouman Access/VPN-yhteysosoite ei vielä ole tiedossa. `192.168.10.105` on yksityinen LAN-osoite. Toimilaitteista irrotusta ei ole vahvistettu. Laitteelle ei ole lähetetty kirjoituksia, firmwarea, resettiä eikä muistin tyhjennystä.

## Dokumentoitu tieto ja lähteet

### Vanha Ouflex LCD

[Ouflex-käyttöohje, FI](https://ouman.fi/documentbank/Ouflex__manual__fi.pdf), erityisesti s. 5–9, 10–16, 18–24: sisäiset rekisterit käyttävät oletuksena TCP-porttia 502. Yhdyskäytävien oletusportit ovat 503 (I/O-laajennusväylä/Modbus 1), 504 (A1/B1) ja 505 (A2/B2). Ohje sijoittaa Ouflexin Modbus 1 -väylässä osoitteeseen 1; tästä ei päätellä portin 502 kaikkien firmwarejen Unit ID -käytäntöä. FTP on vain lukuun. Näytöltä löytyvät tyyppitiedot ja varmuuskopiointi. Sovellus määrittää pisteet. Hälytykset, historia, aikaohjelmat, erikoispäivät, poikkeuskalenteri ja käsiajo esitellään käyttöliittymässä; niiden olemassaolo tässä yksilössä tai luettavuus Modbusilla on vielä selvittämättä. Access-, SMS- ja SNMP-asetukset ovat erillisiä ominaisuuksia. HTTP:n puuttuminen ei yksin osoita Modbusin puuttumista.

### Oumanin Modbus-ohje

[YM0105, FI, 2025/09](https://ouman.fi/wp-content/uploads/2025/09/YM0105_Modbus-guide_FIN.pdf), s. 11–15, 19–21: kuvaus generoidaan sovellukselle; osoitteet ovat 1-alkuisia. U16/S16 vievät yhden, U32/S32 kaksi rekisteriä; järjestys on high-byte/high-word first. Skaalaus on desimaalimäärän mukaan. Holding-merkintä ei yksin takaa pisteen kirjoitettavuutta. Manual Reg on erillinen: 0 automaatti, 1 käsiajo ennen arvokirjoitusta. S32 kirjoitetaan kokonaisena FC16-parina.

Aikaohjelman kokonaiskoko on 362 rekisteriä: tila ja ohjaustapa sekä kolme 120 rekisterin osaa. Muutos voi järjestää tapahtumat uudelleen; koko ohjelma luetaan uudelleen. Ohjeen ensimmäinen esimerkkialue alkaa 10000:sta, mutta sitä ei sovelleta tähän yksilöön ilman karttaa. Erikoispäivätaulukon 10332-osoitteissa ja väitetyssä 120 rekisterin välissä on ristiriita; automaattista kalenterikirjoitinta ei toteuteta arvauksen perusteella.

Hälytyksen U16-bitit: aktiivisuus 0, kuittaamattomuus 1, prioriteetti 2–4, ryhmä 5–7. Ohjeen maininta ryhmistä 1–10 ei mahdu kolmeen bittiin: ryhmät 8–10 jäävät epävarmoiksi. AckReg + hälytyskohtainen Ack value kuittaavat hälytyksen; Transfer Reg kuittaa SNMP-vastaanoton. Niitä ei käsitellä palautettavina tavallisina asetusarvoina. Lähteen pieniä S32-esimerkkejä ei tulkita yleiseksi säännöksi, että ylempi sana olisi vain etumerkki: toteutus käyttää kokonaista 32-bittistä kahden komplementtia.

### Ounet ja projektityökalut

[Ounet-käyttöohje, FI](https://ouman.fi/documentbank/Ounet__manual__fi.pdf), laitteen lisääminen ja FTP-asetukset: pisteluettelo tuodaan XML-kuvauksella; tiedosto voidaan tehdä Ouflex Toolilla tai lukea laitteen FTP:stä. Kuvauksien polku on `/Files`. FTP:n on oltava laitteessa käytössä. XML-kuvaus ei tarkoita alkuperäisen sovellusprojektin eikä firmwaren täydellistä varmuuskopiota.

[Ouflex Tool](https://ouman.fi/tuote/ouman-ouflex/ouflex-tool-ohjelmointityokalu/) sisältää Project Managerin, Application Builderin ja debuggerin. Ohjelmointioikeudet liittyvät lisenssiin/koulutukseen. Sivun perusteella ei voi luvata, että lähdeprojekti saadaan ladattua jokaisesta vanhasta säätimestä. Alkuperäinen projektitiedosto on ensisijainen, jos se on saatavilla.

[Virallinen lataushakemisto](https://ouflextool.ouman.net/downloads/) sisältää DeviceTemplates-, Info-, Charts- ja Sovelluksia-hakemistot. Hakemistolistaus ei tarjoa tämän yksilön sovellustunnistetta. Alahakemistojen lisähaku ei onnistunut kaikilta osin selaintyökalulla. Macin Documents-, Downloads-, Projects- ja ouman-diagnostics-hakemistoista tehty rajattu tiedostonimihaku ei löytänyt valmista Ouflex-projektia tai kuvausta.

### Eri mallit pidetään erillään

| Malli/lähde | Dokumentoitu ero / käyttö tässä työssä |
|---|---|
| Vanha LCD Ouflex | Ensisijainen laite- ja verkkotoimintojen lähde; kartta puuttuu |
| [Ouflex A, YM0008, 2023](https://ouman.fi/wp-content/uploads/2023/01/YM0008_OUFLEX-A_User-manual_ENG.pdf) | Uudempi malliperhe; versioidut käyttöohjeet ja web-käyttöliittymä. Ei siirretä sen rekistereitä vanhaan malliin |
| [Ouflex A XL, YM0084A](https://ouman.fi/wp-content/uploads/2025/09/YM0084A_OUFLEX-A_XL_User-manual_ENG.pdf) | BA Tool, web-käyttöliittymä, oma firmware-/laiteversio. Ei yhteistä oletuskarttaa |
| [Ouflex BA Tool](https://ouman.fi/tuote/ouman-ouflex-a-xl/ouflex-ba-tool-ohjelmointityokalu/) | Modbus-ohjeen kuvausten generointipolku; vanhan Tool-projektin yhteensopivuus varmistettava erikseen |
| FLEX UI8/AO8/DO4 | Modbus-ohjeessa omat laajennusmoduulien kartat; niitä ei asenneta sisäisen portin 502 kartaksi |

[Modbus Application Protocol V1.1b3](https://www.modbus.org/file/secure/modbusprotocolspecification.pdf) määrittää FC03/04-lukupyyntöjen, FC06/16-kirjoitusten ja 43/14-tunnistuksen muodot. Tunnistuksen tuki Ouflexissa on tuntematon: Illegal Function -vastaus on kelvollinen protokollahavainto, ei laitevika. Unit 0 -broadcastia ei käytetä. 43/14-kysely hakee perustunnisteiden ensimmäisen vastauksen ja raportoi mahdollisen jatkotarpeen; se ei väitä tunnistavansa sovellusta tai kaikkia versioita.

## Ominaisuuksien tutkimustila

| Kokonaisuus | Tämän laitteen tila | Seuraava näyttö |
|---|---|---|
| Lämpötilat, paineet, analogia-/digitaalitulot, ulkoiset anturit | Tuntematon | Sovelluskartta + luku + näytön vertailu |
| Anturiviat ja mittausten tilat | Tuntematon | Kartan virhebitit/no-data-määrittelyt; ei oletettuja sentinel-arvoja |
| Digitaali-/analogialähdöt, venttiilit, pumput | Tuntematon | Kartta ja fyysisen irrotuksen vahvistus ennen kirjoitusta |
| Auto/käsiajo, asetusarvot, käyrät, toimintatilat | Tuntematon | Pistekohtainen tyyppi, rajat, Manual Reg ja hyväksytty testiarvo |
| Viikko-ohjelmat, erikoispäivät, poikkeuskalenteri | Tuntematon | Sovelluksen alueet ja ristiriitaisten osoitteiden varmistus; raakaluenta mahdollinen |
| Hälytysrajat ja viiveet | Tuntematon | Kartta; ei nimien perusteella tehtyjä kirjoituksia |
| Aktiiviset hälytykset, prioriteetit, ryhmät | Dekooderi toteutettu, laitehavainto puuttuu | Varmennettu alarm-tyyppinen karttapiste |
| Hälytyshistoria, kuittaus | Ei laitekohtaista karttaa; ei kuittauskomentoa | Erillisen komentosovittimen vaatimat AckReg/Ack value/semantiikka |
| Portti 502 | Ympäristö esti kokeen | Kelvollinen Modbus-vastaus |
| Portit 503, 504, 505 ja I/O-laajennukset | Ympäristö esti kokeen | Väyläkohtaiset laiteosoitteet ja kartat; ei oletettua läsnäoloa |
| FTP /Files | Ympäristö esti porttikokeen | FTP-listaus ja kuvaustiedosto |
| Sovellus-/firmwarepalautus | Ei täydellistä varmuuskopiota | Oikea projekti, versiot ja valmistajan palautusmenettely |

Ominaisuuden puuttumista ei päätellä aikakatkaisusta, Illegal Address -poikkeuksesta tai kartan puuttumisesta. Tässä yksilössä ei vielä ole todettu mitään ominaisuutta poiskytketyksi.

## Käyttö MacBookissa tai samassa verkossa olevassa Linuxissa

Katso [RUNBOOK.md](RUNBOOK.md). Tulokset jäävät paikalliseen `ouflex-results/`-hakemistoon. Verkkokomentoihin saa antaa todellisen internet-/Access-osoitteen `--host`-valinnalla ja oikean portin `--port`-valinnalla. Älä avaa uutta internet-palvelua tätä varten. Jo toimiva LAN/VPN/Access-reitti riittää.

Lukuskannaus rajataan enintään 4096 rekisteriin, 1–125 rekisterin pyyntöihin ja vähintään 50 ms väliin. Oletusviive on 200 ms. Unit ID:t annetaan erikseen, korkeintaan 16 tunnistuskierrosta kohden. Näin kyselybudjetti on nähtävissä eikä virheellisesti tulkita TCP-aukioloa lukuoikeudeksi.

## Kartta, parserit ja kirjoitusoikeudet

[MAP_FORMAT.md](MAP_FORMAT.md) määrittelee normalisoidun JSONin ja rajatun XML/CSV-adapterin. **Yleisen, kaikkia Ounet XML -versioita ymmärtävän parserin toimivuutta ei väitetä.** Aitoa tämän sovelluksen tiedostoa ei ole saatu. Tuntematon skeema hylätään tai rivit säilytetään `rejected_rows`-listassa. Piste-ID:tä ei muuteta Modbus-osoitteeksi.

Kartassa säilyvät nimi, tyyppi, osoitepohja, alue, desimaalit, yksikkö, rajat, käyttöoikeus, enumit, mahdollinen Manual Reg, lähde ja alkuperäisen rivin metadata. Osoitteita ei generoida laitteen mallin perusteella.

Kirjoitus on kolmesti rajattu: erillinen käyttöönottovalinta, täsmälleen karttaan sidottu politiikka ja pistekohtainen dokumentointi/arviointi. HA vaatii lisäksi `physically_verified: true`. Tyhjä tai käyttäjän tuoma RW-kartta ei itsessään myönnä kirjoitusoikeutta. Projektin CONTRIBUTING.md edellyttää hallittua fyysistä varmennusta ja arviointia ohjauspisteille; tälle laitteelle niitä ei vielä ole.

CLI:n kokeellinen tila vaatii sekä `--enable-write-tests` että `--confirm-disconnected`. Testi lukee alkuarvon, tarkistaa rajat/tarkkuuden, kirjoittaa FC06/16:lla, vertaa raakatakaisinlukua ja palauttaa alkuperäiset sanat. Käsiajo vaatii erillisen karttapisteen ja oman sallinnan, ja molemmat alkuarvot palautetaan. Näyttövertailu on paikallisen havainnoijan tehtävä ja merkitään tekemättömäksi ilman havaintoa. Jokainen kirjoitustesti ei siis automaattisesti ole fyysisesti varmennettu.

## Home Assistant

Kopioi vain `custom_components/ouman_ouflex` HA:n `/config/custom_components`-hakemistoon tai käytä moduulin ZIP-pakettia. Käynnistä HA uudelleen ja lisää **Ouman Ouflex (experimental)**. Anna IP, portti, Unit ID ja normalisoitu JSON-kartta (enintään 256 pistettä/entry). Ensimmäinen karttapiste luetaan konfiguroinnin tarkistuksessa; kirjoituksia ei tehdä. Integraation asetuksista voi myöhemmin ottaa käyttöön tarkistetun politiikan. Politiikan tai kartan muuttuminen edellyttää uudelleenarviointia.

Polling 30 s; kaikki luku- ja kirjoitustapahtumat kulkevat saman entry-kohtaisen lukon läpi. I/O tehdään executorissa. Puuttuva piste on unavailable, koko laitteen lukuvirhe nostaa UpdateFailed-tilan. Uusi pollaus yrittää uutta TCP-yhteyttä; vanhaa rikkinäistä socketia ei käytetä. Yhteysanturi ja redaktoitu diagnostiikka ovat mukana. Audit on paikallisesti `.storage/ouflex_<entry_id>.jsonl`; loki voi sisältää kohdetietoja. Lokin kierto/retentio on vielä käyttäjän ylläpidettävä, eikä audit-lokia pidä julkaista sellaisenaan.

HA:ssa käsiajolliset pisteet ja komento-/kalenterikuittaukset eivät saa yleistä kirjoittavaa käyttöliittymää. Number/select/switch eivät avaa vapaata osoitekirjoitusta.

## Testaus ja keskeneräinen työ

[VALIDATION.md](VALIDATION.md) erottaa suoritetut testit, ohitetun TCP-ajon ja todelliset laitetestit. Jatkossa tarvitaan alkuperäinen kuvaus, oikea yhteysreitti, näytön vastaavuudet, hallitut kirjoituskokeet ja kokonaisen HA-asennuksen varmennus. [RECOVERY.md](RECOVERY.md) kertoo palautuksen rajat. Kehitys kuuluu erilliseen feature-haaraan ja draft-PR:ään; mainiin ei yhdistetä tutkimuksen perusteella.
