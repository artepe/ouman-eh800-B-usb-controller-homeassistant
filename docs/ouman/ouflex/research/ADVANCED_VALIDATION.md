# Edistyneen tutkimusvaiheen varmennus

11.11.2026, paikallinen macOS. Laitetestit ja simulaattoritestit on erotettu.

| Suoritettu tarkistus | Tulos |
|---|---|
| `python3 -m unittest discover -s tests -p 'test_ouflex*.py' -q` | 46 hyväksytty Python 3.9:llä ja 3.12:lla; ei ohituksia |
| Ouflex HA-runtime, Python 3.14.10, HA/pytest-homeassistant 2026.11.1 | 6 hyväksytty |
| OpenLVI Discovery HA-runtime samalla HA-kehyksellä | 10 hyväksytty |
| Portable OpenLVI Discovery | 14 hyväksytty |
| `test_*profiles.py`, Python 3.12 | 14 hyväksytty |
| `test_openlvi_extended.py`, Python 3.12 | 4 hyväksytty |
| Moduulijakelun testit | 5 hyväksytty |
| OpenLVI-lokalisointi | 5 hyväksytty |
| Compileall: custom_components ja tools, Python 3.14 | hyväksytty |
| Moduulien build + verify | kaikki 10 pakettia hyväksytty; Ouflex 18 tiedostoa, versio 0.2.0 |
| SCADA JavaScript syntax; git diff --check | hyväksytty |

HA-testit käyttävät oikeaa Home Assistant -kehystä ja simuloituja laitearvoja.
Ne eivät asenna integraatiota käyttäjän HA-palvelimelle tai testaa fyysistä
Ouflexia HA:n kautta. Loopback TCP- ja nc-aliprosessitestit käyttävät
synteettistä palvelinta. FC05/06/15/16, virhevastaukset, rajat, takaisinluku,
palautus ja havaitsijan virhe on testattu simulaattorissa.

Pakkaustarkistuksen ensimmäinen ajo hylkäsi testien luomat `__pycache__`-
tiedostot. Vain generoidut välimuistit poistettiin ja tarkistukset ajettiin
uudelleen onnistuneesti `PYTHONDONTWRITEBYTECODE=1`-asetuksella. Laaja
Python 3.12 compileall osui toisen moduulin Python 3.14:n except-syntaksiin;
projektin laaja tarkistus tehtiin onnistuneesti Python 3.14:llä. Ouflexin
testit läpäisivät myös vanhemmat yllä mainitut Python-versiot.

Todelliset laiteluvut: 240 karttapistettä, kuusi kalenterialuetta (24 pyyntöä),
FC01–FC04/43-kokeet ja Unit ID 2:n aikakatkaisu. Jokaisen Modbus-pyynnön
raakatavut, osoite, funktio, Unit ID, kesto ja poikkeus tallentuivat paikallisiin
JSONL-lokeihin. Unit 1:n vastaavuus vahvistettiin aikakatkaisun jälkeen
kalenteriluvuilla ja erillisellä lopputestillä. FTP-kuvaukset luettiin kahdesti
ja olivat samat. Yksityiset arvot ja koko kuvaukset eivät ole commitissa.

## Vielä tarvittavat fyysiset kokeet

1. Varmista fyysinen irtikytkentä toimilaitteista ja muista ohjausjärjestelmistä.
2. Vertaa pisteiden nimet, arvot, yksiköt, käsiajot ja hälytykset LCD:hen;
   selvitä −50.0 °C -arvojen todellinen merkitys ja anturikytkennät.
3. Tarkista yksittäisen kirjoitusehdokkaan dokumentaatio ja rajat. Tee FC06-/FC16-
   muutos, LCD-vertailu ja palautus valvotusti; älä testaa kaikkia automaattisesti.
   FC05-/FC15-testeihin tarvitaan ensin kelakartta, jota ei löytynyt.
4. Tunnista I/O-laajennukset ja yhdyskäytävien todelliset laiteosoitteet.
5. Varmista kalenteriformaatti ja kuittaussemantiikka erillisillä testitapauksilla.
6. Tunnista CPU, muistit, LCD-ohjain ja debug-liittimet fyysisestä laitteesta.
   Hanki sovellusbinäärit/projekti ja siirtoliikenteen passiivinen kaappaus.
7. Varmenna täydellinen firmware-/kalibrointi-/asetusvarmistus ja palautusreitit
   ennen omaa sovellusta, LCD-siirtosovitinta tai firmwaremuutoksia.
8. Asenna kokeellinen integraatio erikseen HA-testiasennukseen ja vertaa
   fyysiseen laitteeseen. Tämän vaiheen HA-testit ovat kehystestejä.

Täydellistä takaisinmallinnusta, ohjelmointiprotokollaa, fyysistä LCD-editoria
ja omaa firmwarea ei ole saatu valmiiksi pelkillä näillä FTP-/Modbus-tiedoilla.
