# Varmennus 2026-11-11

## Suoritettu paikallisesti

macOS, Python 3.9.6 ja Homebrew Python 3.12.16:

- Uuden moduulin protokolla-, kartta-, CLI- ja HA-sopimustestit läpäisivät ajot. Lopullinen yhteisajo: **98 läpäissyttä testiä**, yksi TCP-testiluokan ohitus (ympäristön bind-eston vuoksi). Näistä 28 on tämän moduulin uusia testejä, 70 repositorion olemassa olevia testejä. Ohitettu luokka sisältää kaksi oikean TCP-palvelimen testiä, joita ei lasketa suoritettuihin 98 testiin.
- Repositorion vaaditut `test_*profiles.py` (14), `test_openlvi_extended.py` (4) ja `test_module_distribution.py` (5) läpäisivät Python 3.12:lla.
- Kaikki kymmenen moduulin ZIP-paketit rakennettiin ja `--verify` tarkisti sisällöt/tarkistussummat.
- Ouflex-paketti sisältää vain oman `custom_components/ouman_ouflex/`-hakemiston (16 tiedostoa). CLI ja tutkimusraportit löytyvät lähdehaarasta erikseen.
- Python-käännöstarkistus OpenLVI-/Ouflex-hakemistoille, työkaluille ja HA-runtime-testille sekä SCADA-JavaScriptin `node --check` onnistuivat.

Ensimmäinen vanhojen profiilitestien ajo järjestelmän Python 3.9:llä epäonnistui olemassa olevan koodin Python 3.10+ -tyyppimerkintöihin. Sama muuttamaton koodi läpäisi Python 3.12 -ajon. Ouflexin oma CLI ja testit tukevat Python 3.9:ää; HA käyttää omaa vaatimaansa Python-versiota.

Yksikkötestit varmistavat U16/S16/U32/S32-rajat, negatiivisen S32:n, skaalaamisen, tavu-/sanajärjestykset, 0/1-osoitesiirtymät, XML/CSV-tuonnin rajat, DTD-hylkäyksen, puuttuvat osoitteet, golden-PDU-tunnistuksen, virheellisen MBAP:n, katkenneet vastaukset, Modbus-poikkeukset, aikakatkaisut, write-gatet, FC06-/FC16-echo/takaisinluvun, palautuksen onnistumisen ja virheen, käsiajon erillisen palautuksen, alkuarvon ja kartan ristiriidan sekä snapshotin ylikirjoittamisen eston.

HA-sopimustestit kattavat oletusarvoisen lukutilan, entiteettien valinnan, number/switch-takaisinluvun, selectin ja hälytysbitit, osittaisen/kokonaisen lukuvirheen sekä diagnostiikan redaktoinnin. Testikehyksen osat ovat näissä eksplisiittisiä testikaksoisia.

## Oikeat laitekokeet

**Ei onnistunutta TCP-/Modbus-/FTP-yhteyttä eikä laitekirjoituksia.** Neljä CLI-yhteysyritystä tallennettiin environment-probe.jsoniin; käyttöympäristö palautti Operation not permitted ennen TCP:tä. Tämä ei ole laitteen virhe tai osoitus rekisterien puuttumisesta. Unit ID:tä, sovellusta, firmwarea, pisteitä tai todellista kirjoitettavuutta ei ole tunnistettu.

## GitHub CI:ssä suoritettu

[Hyväksytty CI-ajo 43069737049](https://github.com/artepe/Open-HVACBridge-homeassistant/actions/runs/43069737049), commit `1fc83762e318cd5bc46ef3553e2e41879f11e081`:

`.github/workflows/ouflex.yml` ajaa:

1. Python 3.9- ja 3.13-yksikkö-/sopimustestit ja oikean loopback TCP -palvelimen testit: **30/30 läpäisi kummassakin versiossa, ei ohituksia**. `OUFLEX_REQUIRE_TCP=1` muuttaa ympäristön verkkokiellon CI-virheeksi, jotta verkkotestejä ei ohiteta hiljaa.
2. Python 3.14.10, `pytest-homeassistant==2026.11.1` ja Home Assistant Core 2026.11.1: **4/4 läpäisi**. `tests/ha/test_ouflex_runtime.py` sisältää oikean HA-kehyksen setup/unload-, read-only-, konfigurointivirta-, number/select/switch-palvelu- ja lukuvirhetestit. Laiteyhteys on tässä testissä mockattu.

Virallisen HA-testipaketin [oma ohje](https://github.com/home-assistant/core/tree/dev/packages/pytest-homeassistant) kuvaa fixturet ja yhteensopivan Core-version. Nämä testit ajetaan erillisessä prosessissa sopimustesteistä. Vanhaa pytest-homeassistant-custom-component-pakettia ei käytetä.

Myös [moduulien paketointiajo 43069737255](https://github.com/artepe/Open-HVACBridge-homeassistant/actions/runs/43069737255) läpäisi. Ensimmäisellä CI-kierroksella löytynyt peräkkäisten HA-ohjausten vanhaksi jäävä UI-tila korjattiin: laitteelta takaisinluettu arvo julkaistaan heti ennen mahdollisesti lykättyä koko laitteen päivitystä. Testikirjasto on nyt lukittu läpäisseeseen versioon. CI-onnistuminen ei varmista fyysisen Ouflexin toimintaa, sen karttaa tai sen palautettavuutta.

## Uusinta

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_ouflex_lab.py' -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_ouflex_ha.py' -v
```

Koko repositorion testeihin tarvitaan Python 3.10+ (varmennettu tässä 3.12:lla). Omalla koneella TCP-simulaattori:

```sh
python3 tools/ouflex_simulator.py --host 127.0.0.1 --port 1502
```

Toisessa terminaalissa:

```sh
python3 tools/ouflex_lab.py discover --host 127.0.0.1 --ports 1502 --units 1 --address 1 --address-base 1 --out ouflex-results/synthetic-discovery.json
python3 tools/ouflex_lab.py identify --host 127.0.0.1 --port 1502 --out ouflex-results/synthetic-identify.json
```

Näitä tuloksia ei nimetä fyysisen Ouflexin havainnoiksi. Kaikki oikean laitteen tutkimuskierrokset tallennetaan erikseen todellisella IP/portti/Unit ID -yhdistelmällä ja aikaleimalla.
