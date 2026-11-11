# Paikallinen Ouflex Tool

Python 3.9+, vain vakiokirjasto. Ei OuflexToolia, HA-tokenia tai pilvipalvelua.
Aja repon juuresta Macissa tai Linuxissa / HAOS Terminalin Python-ympäristössä:

```sh
python3 -m tools.ouflex_tool --host 192.168.10.105 fetch-map \
  --out ouflex-results/tool/ounet.xml
python3 -m tools.ouflex_tool --host 192.168.10.105 \
  --map ouflex-results/tool/ounet.xml serve
```

Avaa **http://127.0.0.1:8765**. HTTP-palvelin kuuntelee vain loopbackia.
Etäkoneelta (esim. HAOS, jos SSH ja Python ovat saatavilla) tee SSH-tunneli:
`ssh -L 8765:127.0.0.1:8765 käyttäjä@192.168.10.231` ja avaa sama paikallinen URL.
HA:n Terminal-lisäosan verkko voi poiketa HA-palvelimesta. Tarkista lähde-IP.
Laite sallii määritellyn lähde-IP:n (aiemmin Mac 192.168.10.224).
Työkalu ei muuta IP-asetuksia. `--transport nc` on saatavilla Modbusille, jos
Macissa Pythonin socket-yhteys estyy mutta `/usr/bin/nc` toimii. FTP käyttää socketia.

UI:n näkymät:

| Näkymä | Sisältö |
|---|---|
| Laiteyhteys | IP, TCP-portti, Unit ID, firmware/sovellus ja XML/JSON-tuonti |
| Mittaukset | Kaikki 240 pistettä, nimihaku, osoite, PDU, tyyppi ja valittujen lukemat |
| Numeerinen kirjoitus | Varmennetun pisteen rajat, irrotusvahvistus, tallenna tai testaa/palauta |
| Nimet ja tutkimus | LCD-nimeämisen tuen tila ja erillinen HA-nimivaihtoehto |
| Audit | Aikaleimat, raakapaketit, alkuarvo, takaisinluku ja palautus |

Valitse 1–32 pistettä, paina **Lue valitut** tai käynnistä 5 sekunnin päivitys.
Lukemat haetaan peräkkäin: ne eivät ole atominen otos. Yhteysvirhe katkaisee
lukusarjan. JSON-rajapinta (`state`, `import`, `read`, `write`, `audit`) käyttää
samaa Workbench-palvelua kuin CLI, joten HA-sovittimen voi lisätä myöhemmin
muuttamatta Modbus-koodia. Nykyisten integraatioiden domeeneja ei muuteta.

## Kirjoituksen käyttöönotto

Oletus on vain luku. XML:n käyttöoikeuskenttä ei yksin salli kirjoitusta.
Vain issuen #34 käyttäjän raportoimat vuosi (1-pohjainen 2, U16, FC06) ja
huonelämpötilan asetusarvo (395 / PDU 394, S32, 1 desimaali, FC16) voivat
saada politiikan. Firmware 2.3.3 ja sovellus 1.1.2 vaaditaan. Mittaukset,
käsiajot ja muut osoitteet estetään myös politiikkatiedostoa muokkaamalla.

```sh
python3 -m tools.ouflex_tool --map ouflex-results/tool/ounet.xml \
  policy-template > ouflex-results/tool/policy.json
```

Tarkista tiedoston nimet, tyypit, min/max, ohjausmerkitys, todisteet ja endpoint.
Aseta `reviewed_by` omaan nimeesi ja `physically_verified` arvoksi `true` vain,
kun käyttäjän aiempi testi koskee juuri tätä laitetta ja pistettä. Kartan tai
endpointin muutos mitätöi politiikan. Mallipolitiikka ei ole automaattinen lupa.

```sh
python3 -m tools.ouflex_tool --map ouflex-results/tool/ounet.xml \
  --policy ouflex-results/tool/policy.json serve
# Avain näkyy list-komennossa. Testi palauttaa alkuarvon automaattisesti:
python3 -m tools.ouflex_tool --map ouflex-results/tool/ounet.xml \
  --policy ouflex-results/tool/policy.json \
  write-test PISTEEN_AVAIN 21.1 --confirm-disconnected
```

`write` jättää varmennetun asetuksen voimaan. Se lukee ja lokittaa alkuarvon
ennen kirjoitusta; virhe tai epävarma kuittaus käynnistää raw-palautuksen ja
takaisinluvun. `write-test` palauttaa aina alkuarvon, myös onnistumisen jälkeen.
Palautuksen epäonnistuminen näkyy tuloksessa. Verkkokatko tai prosessin tappaminen
voi estää palautuksen: tarkista loki ja laite ennen käytön jatkamista.
Fyysinen irrotus vahvistetaan joka kirjoitukseen erikseen. Tätä toteutusta ei
ole käytetty tämän työn aikana fyysisiin kirjoituksiin.

Audit tallentuu `ouflex-results/tool-audit.jsonl`-tiedostoon fsyncillä; se sisältää
paikalliset laitetiedot. Älä julkaise XML:ää tai audit-lokia. HTTP-palvelu ei lataa
ulkoisia resursseja. Sivulla on istuntokohtainen toimintotunniste ja origin/Host-
tarkistus. Ei etäkuuntelua eikä CORS-oikeuksia.

## Tutkimus ja testit

```sh
python3 -m tools.ouflex_tool probe
python3 -m unittest discover -s tests -p 'test_ouflex_tool.py' -v
python3 -m unittest discover -s tests -p 'test_ouflex*.py' -v
```

`probe` avaa portit 503–505 ja lukee mahdollisen bannerin lähettämättä dataa.
Hiljainen portti jää tuntemattomaksi. Ei arvattuja ohjelmointi-/RPC-komentoja.
Passiivinen kaappaus voidaan tehdä Macilla (korvaa en0 oikealla LAN-liitännällä):

```sh
sudo tcpdump -i en0 -s 0 -w ouflex-results/tool/local.pcap \
  'host 192.168.10.105 and (tcp port 502 or tcp port 503 or tcp port 504 or tcp port 505)'
tcpdump -nn -r ouflex-results/tool/local.pcap -X
```

Kaappaa omaa työkalua ja laitteen paikallista käyttöä; valmistajan sovellusta ei
tarvita. PCAP ei yksin todista tekstikirjoituksen semantiikkaa. Tutkimustulos:
[ISSUE34.md](../../docs/ouman/ouflex/research/ISSUE34.md).
