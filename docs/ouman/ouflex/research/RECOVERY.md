# Palautus ja varmuuskopiot

Käyttäjä hyväksyi tutkimuslaitteen rikkoutumisen riskin. Tässä työssä ei kuitenkaan ole saatu alkuperäistä sovellusprojektia, firmwarekuvaa eikä varmennettua bootloader-palautusmenettelyä. **Täydellistä brick-palautusta ei ole toteutettu eikä testattu.**

## Ennen ensimmäistä laitekirjoitusta

Säilytä erillään alkuperäiset Tool-projekti-/varmuuskopiotiedostot, FTP-kuvaustiedostot, normalisoitu kartta, firmware-/sovellustunnisteet, laitteen näytöltä kirjatut tyyppitiedot ja parametrien raakaluenta. Ota alkuperäisille tiedostoille SHA256-tarkisteet, esimerkiksi macOS:ssa `shasum -a 256 FILE` tai Linuxissa `sha256sum FILE`. Käyttöohjeen näytöltä käynnistettävän varmuuskopioinnin kohde ja palautuskelpoisuus on varmennettava täsmälleen tällä laiteversiolla ennen sen varaan laskemista.

CLI:n `backup` tallentaa vain kartan määrittämät luettavat rekisterit sekä kartan tarkistussumman, identiteetin ja yhteyskohteen. Se ei sisällä ohjelmakoodia, käyttöjärjestelmää, firmwarea, piilotettua muistia eikä välttämättä aikaohjelmien koko sisältöä. FTP-palvelun kuvauksien talteenotto ei korvaa Tool-projektia.

`write-test` tallentaa alkuperäiset sanat audit-lokiin ja yrittää takaisinlukua sekä palautusta `finally`-lohkossa myös silloin, kun kirjoitusvastaus katkeaa. Erillinen käsiajon alkuarvo palautetaan myös. Palautus voi epäonnistua verkkoyhteyden, virran, prosessin tai laitteen vian vuoksi. `restored: false` vaatii paikallista toimenpidettä; älä jatka seuraavaan testiin. Audit-virhe estää uuden testikirjoituksen. Jos lokitallennus rikkoutuu vasta testiarvon kirjoituksen jälkeen, alkuarvon palautusta ja takaisinlukua yritetään silti; tallennusvirhe kirjataan tulokseen eikä testiä merkitä onnistuneeksi.

## Jos Modbus vastaa edelleen

Vahvista ensin oikea laite ja kartta. Lue nykyinen arvo ja säilytä myös tämä havainto. Palauta vain erikseen dokumentoitu, sallittu ja rajojen sisällä oleva piste. `restore` tarkistaa snapshotin kartan, identiteetin sekä IP/portti/Unit ID -kohteen ja tekee kirjoituksen takaisinluvulla. Se palauttaa yhden pisteen, ei koko skannattua muistialuetta. Uuteen DHCP-osoitteeseen siirtynyt laite edellyttää yhteyden/identiteetin manuaalista varmennusta ja uuden palautusmenettelyn arviointia; tarkistusta ei ohiteta automaattisesti.

```sh
python3 tools/ouflex_lab.py restore --map ouflex-results/map.json --policy ouflex-results/reviewed-policy.json --snapshot ouflex-results/before-snapshot.json --key ACTUAL_VERIFIED_KEY --function 16 --enable-write-tests --confirm-disconnected --out ouflex-results/restore-result.json
```

Käsiajollisten pisteiden monivaiheiseen palautukseen `restore` ei tarjoa yleistä kirjoitusta. Käytä alkuperäisen testin talteen otettuja käsiajo-/arvotietoja ja laitekohtaisesti arvioitua paikallista palautusta.

## Jos säädin ei vastaa

1. Säilytä audit, viimeinen snapshot, viimeinen testiraportti ja tarkka viimeinen pyyntö (`request_hex`). Aikakatkaisu ei kerro, toteutuiko kirjoitus.
2. Tarkista paikallisesti virta, näyttö, verkkokaapeli sekä DHCP:n nykyinen osoite ja jo olemassa oleva Access/VPN-yhteys. Ympäristön `Operation not permitted` ei osoita säätimen jumittumista.
3. Mahdollinen uudelleenkäynnistys tehdään paikallisesti vasta, kun kytkennät ja varmuuskopion tila on tarkastettu. Työkalu ei lähetä arvausta resetti-/bootloaderrekisteristä.
4. Jos vain sovellus on vaurioitunut, palautukseen tarvitaan oikean sukupolven Tool, alkuperäinen sovellus ja valmistajan dokumentoima latausmenettely. USB-/Ethernet-palautusominaisuutta ei ole todistettu tälle yksilölle.
5. Jos bootloader tai firmware on vaurioitunut, tämän moduulin Modbus-palautus ei auta. Tarvitaan valmistajan mallikohtainen huoltomenetelmä. Älä käytä Ouflex A/XL -firmwarea vanhan LCD-Ouflexin palautuskuvana oletuksen perusteella.

Tehdasasetusten palautus ja muistin tyhjennys eivät ole varmuuskopion palauttamista. Niitä ei sisällytetä automaattiseen palautukseen.
