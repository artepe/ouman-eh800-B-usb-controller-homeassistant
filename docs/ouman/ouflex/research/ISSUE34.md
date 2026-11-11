# Issue #34: paikallinen Ouflex Tool ja nimeämisen tutkimustulos

## Toteutuksen rajaus ja testattu aineisto

`tools/ouflex_tool` toteuttaa itsenäisen stdlib-CLI:n ja paikallisen selain-UI:n.
Yhteiset `modbus`, `ounet`, `pointmap` ja `session` säilyvät HA-integraatioiden
käytössä muuttamattomina. Tutkimushaaran myöhemmät muutokset yhdistettiin mukaan. FTP-haku käyttää
yhteistä `ftp_map.py`-lukijaa ja Ounet-tuonti `ounet.py`:tä. Käyttöohje: [README](../../../../tools/ouflex_tool/README.md).

Tämän ajon suorat Python TCP-yhteydet Macilta 192.168.10.105:n portteihin
21, 502, 503, 504 ja 505 palauttivat `EPERM: Operation not permitted` ennen
TCP-yhteyden muodostusta. Anonyymi FTP-haku estyi samasta syystä. Tämä kertoo
suoritusympäristön rajoituksesta, ei palveluiden tilasta. Uutta fyysistä
lukua, kirjoitusta tai LCD-havaintoa ei voi väittää tehdyksi.

Repossa aiemmin tallennettu `ouflex-results/advanced/ftp/ounetDescrFile_fi-FI.xml`
analysoitiin uudelleen: 240 pistettä, U16 99, S16 2, S32 139, kuusi erillistä
kalenterialuetta, ei hylättyjä pisterivejä. Raaka-XML jätettiin paikalliseksi.
Redaktoidut tulokset: [ISSUE34_RESULTS.json](ISSUE34_RESULTS.json).

Issuen käyttäjän aiemmat fyysiset havainnot ovat ulkoista näyttöä: vuoden
FC06 ja huoneasetusarvon FC16 takaisinlukuineen. Niitä ei esitetä tämän ajon
testeinä. Sovelluksen sallittujen kirjoitusten politiikka sitoutuu tarkkaan
karttaan, endpointiin, esitysmuotoon, dokumentoituihin rajoihin ja näihin
kahteen osoitteeseen. Vuoden muuttaminen vaikuttaa kelloon ja kalentereihin:
se on erikseen nimetty toiminto eikä yleinen pääsy järjestelmärekistereihin.

## Missä nimi on ja mitä voidaan todistaa?

[Oumanin Ouflex-käyttöohje](https://ouman.fi/documentbank/Ouflex__manual__fi.pdf),
sivu 17, kuvaa paikallisen nimeämisen valintapyörällä. Sivu 2 kertoo sovelluksen
laatimisesta työkalulla ja siirrosta Ethernetillä. Näistä ei seuraa dokumentoitua
etänimeämisen rajapintaa. Tarkastettu julkinen käyttöohje ei määrittele
tekstin kirjoitusrekisteriä tai ohjelmointi-/RPC-sanomien tavumuotoa.

Ounet-XML:ssä nimi on `point/@name`; pisteen tunniste, osoite ja numeerinen
muoto ovat eri kenttiä. XML on verkkokuvaus. Sen muokkaus ei todista LCD:n
nimen muuttumista. Aiemmissa debuglokeissa näkyvät `Device/objects`-binääripolut
osoittavat sovellusobjekteihin, mutta eivät paljasta nimen pysyvää muistialuetta,
serialisointia tai hyväksyttyä muokkausprotokollaa. Nimen varsinainen
säilytysmekanismi ja sovellusohjelman muutoskäsittely jäävät todentamatta.

L1 menoveden lämpötila on 1-pohjainen 203 / PDU 202, S32, yksi desimaali.
Se on numeerinen mittaus, ei tekstialue. Siihen liittyvä käsiajorekisteri ei
ole nimeämisreitti. `Arte Petteri Coding` → alkuperäinen nimi -verkkokoe ei
ole toteutettavissa varmennetulla semantiikalla tämän aineiston perusteella.
Nimeämistoiminto ilmoittaa UI:ssa tuen puuttuvan. HA-entiteetin näyttönimen
muuttaminen tarjotaan erillisenä vaihtoehtona; se ei muuta LCD:tä.

Myöhempi LCD-adapteri tarvitsee todennetun tekstikentän/protokollan, alkuperäisen
nimen lukemisen ja varmuuskopion, kirjoituksen ja paikallisen näyttövertailun,
palautuksen sekä erillisen käyttäjän hyväksynnän. FTP STOR-, firmware- ja
arvatut RPC-operaatiot puuttuvat työkalusta.

## Portit 503–505

Tuore verkkoajo estyi EPERM-virheeseen. Aiemmin raportoitu avoin TCP-portti ei
määrittele sovellusprotokollaa. Työkalun bannerikoe lähettää nolla tavua ja
lokittaa vastauksen/virheen; tuntemattomiin palveluihin ei lähetetä
Modbus-kehyksiä oletuksena. Passiivisen PCAP-keruun komennot ovat README:ssa.
Protokollat ja mahdollinen yhteys LCD-nimiin jäävät avoimiksi.

## Automaattinen verifiointi

Uudet testit käyttävät olemassa olevaa Modbus-simulaattorin mallia ja oikeaa
MBAP-kuljetuskoodia fragmentoidulla muistissa toimivalla socket-sovittimella.
Ne tarkistavat FC03/FC04, kaikki neljä numerotyyppiä, FC06/FC16-testipalautuksen,
pysyvän asetusmuutoksen, epävarman kuittauksen palautuksen, audit-levyvirheen,
rajat, tarkkuuden sekä kirjoitussuojauksen. Nämä eivät ole fyysisiä laitetestejä.

Tämän ajon tulos: 14 uutta testiä OK. Ouflex-kokonaisuus ilman ympäristön
estämää vanhaa `test_actual_subprocess_binary_roundtrip`-testiä: 57 ajettua,
yksi ohitettu, ei virheitä. Suodattamaton ajo ennen uusien testien lisäämistä:
44 testiä, yksi EPERM-virhe localhost-bindissä, yksi ohitettu. Testiä ei muutettu
piilottamaan ympäristövirhettä. Python compileall, UI:n JavaScriptin
`node --check` ja `git diff --check` hyväksytty. Selaimen visuaalista tai
fyysisen laitteen päästä päähän -testiä ei voitu tehdä tässä ympäristössä.
