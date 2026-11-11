> Historiallinen lähtötilanne ennen tämän tehtävän laiteajoa. Uusimmat FTP-,
> Modbus- ja REA-havainnot: [ADVANCED.md](ADVANCED.md). Alla oleva puuttuvan
> verkkoyhteyden kuvaus ei koske uusinta ajoa.

# OpenHVAC Native Ouflex — tekninen lähtötilanne

2026-11-11. Ensimmäinen vaihe: riippumaton lukija ja todistusaineistoarkisto.
Tämä ei ole valmis natiivifirmware eikä palautuskelpoiseksi todettu varmuuskopio.
Ouflex Tool tai BA Tool eivät ole suunnitellun ratkaisun ajonaikaisia tai
kehitystyön pakollisia riippuvuuksia. Nykyistä firmwarea ei korvata.

## Todisteiden luokittelu

**Dokumentoitu** tarkoittaa lähteen kuvaamaa malliperheen ominaisuutta.
**Testattu** tarkoittaa tämän ajon havaintoa, jonka rajaus mainitaan.
**Hypoteesi** tarvitsee vielä laitekohtaisen mittauksen. Käyttäjän antama
IP ja portit ovat lähtötietoja, eivät laitetunnistus.

Ensisijainen lähde: [vanhan Ouflexin käyttöohje, v2.3.3 / 2017-03-27](https://ouman.fi/documentbank/Ouflex__manual__fi.pdf).
Sivut 2, 8–9, 17–19 ja 24: Ethernet-sovellussiirto, sisäiset Modbus-rekisterit,
FTP:n lukutila, tyyppitiedot, varmuuskopiointivalikko, nimeäminen, I/O ja
USB Device. Lähde ei määrittele ohjelmansiirron tavuprotokollaa, CPU:ta,
muistipiirejä, bootloaderia eikä ulkoisen firmwarevarmuuskopion palautusta.
[Modbus-protokolla](https://www.modbus.org/file/secure/modbusprotocolspecification.pdf)
määrittelee lukupyynnöt ja laitetunnistuksen; valmistajan tuki on erillinen kysymys.

| Tavoite | Dokumentoitu / testattu | Vielä hypoteesi tai avoin kysymys |
|---|---|---|
| 1. Malli, CPU, muisti, arkkitehtuuri | Tyyppitietovalikko dokumentoitu. Tässä ajossa ei laitevastausta. | Mallikilpi, PCB-revisio, CPU- ja flash-piirimerkinnät; ei oletusta Linuxista tai ARMista. |
| 2. USB Device | Liitäntä dokumentoitu. Macin USB-inventaario tässä ajossa tyhjä. | VID/PID, interface-luokat, endpointit, CDC/HID/vendor/bulk, huoltotila. |
| 3. Ethernet-siirto | Valmiin ohjelman lataus Ethernetillä dokumentoitu; protokolla tuntematon. | Sovelluksen siirtopalvelu, kehystys, tarkistussummat, autentikointi ja commit. |
| 4. Varmuuskopio | Näytön varmuuskopiointi huoltokoodilla dokumentoitu. Keräystyökalu testattu synteettisesti. | Kopion sijainti, sisältö, vienti sekä sovellus-/firmwarepalautettavuus. |
| 5. LCD ja syöttölaitteet | Valintapyörä/OK, ESC, piilovalikot ja nimeäminen dokumentoitu. | LCD-ohjain, pinout, jännitetasot, merkkikoodaus ja valikkotiedoston rakenne. |
| 6. Omat tekstit ja valikot | Paikallinen nimeäminen on dokumentoitu ominaisuus. | Nimeämisen verkkorajapinta, vapaiden valikkojen lataus; Modbus-tuki ei todista niitä. |
| 7. I/O ja väylät | Liitynnät ja sähköiset tyypit käyttöohjeessa. | Tämän sovelluksen pistekartta, laajennusmoduulit, sisäisten ADC/DAC-/releohjainten rajapinnat. |
| 8. Formaatti ja lataaja | Arkistomuoto toteutettu. | Natiivin sovellusformaatin kääntäjä ja laitesiirtosovitin odottavat protokollan tunnistusta. |
| 9. Firmware / korvauskortti | Ei testattua boot-/debug-reittiä. | SWD/JTAG/UART, lukusuojaukset, muistialueet; vaihtoehtoinen kortti tarvitsee pinoutit. |
| 10. HA LCD-editori | Aiempi HA-pisteintegraatio on työpuussa; ei LCD-ohjelmoija. | Editorin esikatselu ja projekti ovat toteutettavissa paikallisesti; oikealle LCD:lle julkaisu riippuu rajapinnasta. |

**Testattu ympäristöhavainto:** TCP-yhteydet 192.168.10.105 portteihin
21 ja 502–505 estyivät `Operation not permitted` ennen yhteyden muodostusta.
Tämä ei todista portteja suljetuiksi. Mitään mallia, rekisteriarvoa tai
USB-protokollaa ei vahvistettu. Laitteelle ei tehty kirjoituksia.

## Ensimmäinen työkalu

`tools/ouflex_archive.py`, Python 3.9+, vakio kirjasto. Erillinen CLI ei sisällä
kirjoitus-, reset-, firmware-, bootloader- tai palautuskomentoja. Se käyttää
olemassa olevan Modbus-kuljetuksen ainoastaan read/identify-metodeja.

```sh
python3 tools/ouflex_archive.py collect --host 192.168.10.105 \
  --usb --out ouflex-results/initial
python3 tools/ouflex_archive.py verify ouflex-results/initial
```

Aja verkossa olevassa Macissa/Linuxissa. `--usb` inventoi saman tietokoneen
USB-laitteet käyttöjärjestelmän kautta; se ei avaa sarjaporttia eikä valitse
Ouflexia automaattisesti. Linuxissa tallentuvat myös saatavilla olevat
USB-deskriptorit. Macissa käytetään system_profiler-inventaariota.
EH-800:n `capture_raw_usb.py`-komentoja ei käytetä Ouflexiin.

Oletuskeruu tekee vain viisi TCP-yhteyskoetta ja yhden Modbus 43/14
perustunnistekyselyn porttiin 502, Unit ID 1. Se ei skannaa tuntemattomia
rekistereitä tai yhdyskäytävien laiteosoitteita. Tunnistevastauksen
mahdollista jatkosivua ei haeta; raakaloki säilyttää jatkotiedon.

Tunnettujen alueiden raakaluku: anna `--plan oma-lukusuunnitelma.json`.
Jokaisella rivillä vaaditaan kokonaislukukentät `port`, `unit`, `function`,
`address`, `count`. Osoite on aina **nollapohjainen PDU-osoite**. FC03/04,
portit 502–505, yksikkö 1–255, enintään 4096 sanaa/alue ja 16384 sanaa/ajo.
Tyhjä suunnitelma on `[]`. Mitään esimerkkiosoitetta ei väitetä laitteen kartaksi.
Pyynnöt jaetaan 32 sanaan, välissä 200 ms; virhealueita ei arvata uudelleen.

FTP-keruu pyydetään erikseen `--ftp-user TUNNUS`-valinnalla. Aseta salasana
ympäristömuuttujaan `OUFLEX_FTP_PASSWORD`; sitä ei tallenneta. Ei tunnusten
arvailua. `--ftp-root` on oletuksena `/Files`. MLSD-listaus ja binäärinen RETR
säilyttävät kaikki tiedostotyypit, myös mahdolliset sovellusbinäärit.
Enintään 512 tiedostoyritystä, 2048 hakemistomerkintää, 8 alihakemistotasoa,
64 MiB ja 300 s FTP-vaihetta. Socket-aikakatkaisu voi pidentää aikarajaa.
MLSD:n puuttuminen kirjataan virheeksi; LIST-tulosta ei arvata.
Symbolisia linkkejä ei seurata. Keskeytynyt tiedosto säilyy `.partial`-nimellä.
FTP on salaamaton; käytä olemassa olevaa paikallista yhteyttä.

Arkisto sisältää pyyntösuunnitelman, TCP-tulokset, kestävän JSONL-raakatavulokin,
valinnaiset USB-/FTP-tiedot, osittaisen onnistumisen tilan ja manifestin.
Kohdehakemiston on oltava uusi. Manifesti kattaa myös osittaiset tiedostot.
`verify` tarkistaa pituudet, SHA-256-tunnisteet, puuttuvat ja ylimääräiset tiedostot.
Se todistaa paikallisen eheyden, ei laitteen muistien kattavuutta, autenttisuutta
ulkopuolista hyökkääjää vastaan tai palautettavuutta. Lukuvaiheen arvot eivät
ole atominen otos. Raaka-arkistot on rajattu gitin ulkopuolelle.

## Eteneminen ja palautuksen portti

1. Kerää LAN-luku ja USB-inventaario, mallikilpi sekä näytön tyyppitiedot.
   Tallenna sovelluksen ja järjestelmän versiot sekä mahdollinen pisteluettelo.
2. Kerää FTP-tiedostot tunnetuilla tunnuksilla. Vertaa kaksi erillistä keruuta;
   erottele muuttuvat mittaukset muuttumattomista sovellustiedostoista.
3. Tunnista PCB ja muistit piirimerkinnöistä. Mittaa jännitetasot ennen
   debug-/UART-kytkentää. Lukusuojauksen poistoa ei kokeilla: se voi tyhjentää muistin.
4. Selvitä USB ensin deskriptoreilla ja passiivisella kaappauksella. Selvitä
   Ethernet-siirto saatavilla olevista tiedostoista ja olemassa olevista
   kaappauksista. Valmistajan työkalun käyttö ei saa tulla ratkaisun riippuvuudeksi.
5. Vaadi ennen firmwarekirjoitusta ulkoinen täydellinen kopio tarvittavista
   boot-/sovellus-/asetus-/kalibrointialueista, kaksi yhtäpitävää lukua,
   tunnettu muistijako ja testattu palautus vastaavaan varalaitteeseen tai
   palautettavaan testimuistiin. Pelkkä rekisteriotoksen palautus ei riitä.

Jos CPU:n latausketju estää oman firmwaren, vaihtoehto on oma ohjainkortti,
jossa Ethernet, tarvittavat RS-485-liitännät ja alkuperäisen I/O:n sovittimet.
LCD:n ja alkuperäisten I/O-korttien uudelleenkäyttö päätetään vasta ohjainpiirien,
jännitteiden, liittimien ja protokollien mittauksen jälkeen. Releet/triacit/ADC:t
voivat olla suoraan CPU:n ohjaamia; säilytettävä kokonaisuus ei ole vielä tiedossa.

## Riippumattoman sovellusmuodon suunnitelma

Tuleva `openhvac.native.application/v1` sisältää laitekohteen ja kyvykkyydet,
pysyvät parametri-ID:t, tyypit, yksiköt, rajat, oletusarvot, I/O-sidonnat,
säätölogiikan sekä lokalisoidun valikkopuun. Valikkoteksti ei muuta parametrin
identiteettiä. Projekti ja laitekohtainen käännöstulos ovat erillisiä.

Siirtotyökalun vaiheet: validate → capability check → export current → stage →
verify → activate → health check → rollback. Vaiheita ei mapata arvattuihin
Ouflex-komentoihin. Bootloaderin ja virrankatkaisusta toipumisen tuki täytyy
vahvistaa ennen siirtosovittimen toteutusta.

HA-editori tallentaa saman projektin paikallisesti ja näyttää LCD-esikatselun.
Nimet, tekstit, asetusarvojen määritykset ja valikkopuu ovat editorin sisältöä;
parametrin nykyarvon kirjoitus on erillinen toiminto. Oikealle näytölle julkaisu
avataan vain todetulle siirtosovittimelle. Tätä editoria, kääntäjää ja firmwarea
ei vielä ole toteutettu. Niiden lupaaminen laitteella toimiviksi olisi ennenaikaista.

## Tämän muutoksen tarkistukset

- `python3 -m unittest discover -s tests -p 'test_ouflex*.py' -q`:
  31 testiä, 30 hyväksytty, 1 TCP-ympäristötesti ohitettu. Arkiston viisi
  uutta testiä kattavat kirjoituspyyntöjen hylkäämisen, tiedostojen korruption,
  polkupaon, binäärisen FTP-siirron ja kokorajan. Eivät laitetestejä.
- Arkiston todellinen ajo `ouflex-results/native-verified-run`: TCP estetty,
  USB-inventaario tyhjä, eheys OK, `firmware_recovery_verified=false`.
- Compileall, moduulijakelun 5 testiä, moduulipaketointi ja pakettien
  verify sekä SCADA-JavaScriptin syntaksitarkistus hyväksytty.
- OpenLVI-profiili- ja extended-testit estyivät olemassa olevan
  `profiles.py`:n `str | None` -tyypitykseen ympäristön Python 3.9:llä.
  Tätä toisen moduulin yhteensopivuusasiaa ei muutettu.

Muutokset ovat paikallisessa `feature/ouflex-lab`-työpuussa. Aiemmat
keskeneräiset Ouflex-tiedostot säilytettiin. GitHub-julkaisua tai PR:ää
 ei tehty tämän vaiheen aikana.
