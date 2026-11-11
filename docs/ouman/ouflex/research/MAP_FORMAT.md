# Rekisterikartan muoto

Tämä **synteettinen esimerkki** on testipalvelinta varten. Se ei ole oikean Ouflexin rekisterikartta.

```json
{
  "schema_version": 1,
  "identity": {"model": "SIMULATOR", "firmware": "test", "application": "fixture"},
  "points": [
    {"key": "flag", "name": "Synthetic U16", "address": 1, "address_base": 1,
     "kind": "u16", "area": "holding", "access": "RW", "entity": "switch",
     "minimum": 0, "maximum": 1, "source": "synthetic fixture"},
    {"key": "target", "name": "Synthetic S32", "address": 2, "address_base": 1,
     "kind": "s32", "decimals": 1, "area": "holding", "access": "RW", "entity": "number",
     "minimum": -100, "maximum": 100, "source": "synthetic fixture"}
  ]
}
```

Malli, firmware ja sovellustunniste ovat pakollisia. Jos todellisia tunnisteita ei vielä tunneta, merkitse se kirjaimellisesti `unknown`; tämä ei ole laitetunnistus eikä oikeuta kirjoitukseen. `address` on dokumentin osoite, `address_base` ilmoitetaan aina. PDU-offset on address − address_base. 3xxxx/4xxxx-viitenumerot eivät ole automaattisesti PDU-osoitteita: muunna ne vain lähteen osoitekäytännön perusteella.

`kind`: u16/s16/u32/s32. `decimals`: 0–6. `byte_order` ja `word_order`: big/little, oletus big. `area`: holding/input. `access`: R/RW; input vain R. `entity`: sensor/binary_sensor/alarm/number/select/switch. Binary/switch/arvojen on tarkoitus olla 0/1; alarm käsitellään bittikenttänä. `enums` on esim. `{"0":"Off","1":"On"}`. `manual_reg` on erillisen käsiajopisteen dokumentin mukainen osoite samalla osoitepohjalla, ei automaattisesti arvorekisterin naapuri.

`metadata.operation` asetetaan muotoon `command` tai `calendar`, jos piste on tapahtuma/kuittaus/ohjelmarakenne. Yleinen palautettava asetusarvokirjoitus hyväksyy vain `value`-operaation. Kuvaustiedoston tarkistaja vastaa semantiikan oikeellisuudesta. Automaattinen kartan tuonti ei tunnista tuntemattomien kenttien toimintaa nimistä.

## CSV ja XML

CSV-erottimet: pilkku, puolipiste tai tab. Tuetut normalisoidut sarakkeet vastaavat Point-kenttiä. Lisäksi eksplisiittiset aliasnimet:

| Lähdekenttä | Normalisoitu |
|---|---|
| Technicalname | key |
| Description | name |
| Modbus reg | address |
| Registertype | area |
| Address format | kind |
| Desimals | decimals |
| Min / Max | minimum / maximum |
| R/W | access |
| Manual Reg | manual_reg |

Välilyönnit ja välimerkit poistetaan sarakenimistä. Arvot `Holding Register` ja `Input Register` tunnistetaan. Muita osoite-, data-ID- tai datapolkusyntakseja ei päätellä automaattisesti. CSV:ssä `enums` on JSON-objekti tekstinä. Tuntemattomat sarakkeet jäävät metadataan. Tiedoston lähdepolku ja lähderivi säilyvät. 10 Mt tiedostoraja, 4096 pisteen karttaraja. XML:n DTD/entity-määrittelyt hylätään.

XML-adapteri käsittelee vain `Point`- tai `Register`-elementtejä, joissa samat kentät ovat attribuutteina tai suorina lehtilapsina. Nimiavaruuden etuliite ohitetaan tagista. Nested vendor-skeema edellyttää uuden testatun adapterin lisäämistä aidon esimerkin perusteella. Osittainen tuonti voi onnistua, mutta `rejected_rows` on aina tarkastettava ennen käyttöä. Kartta ei saa sisältää päällekkäisiä pisteavaimia.

## Erillinen kirjoituspolitiikka

`map-info --map map.json` tulostaa normalisoidun kartan SHA256:n. Politiikka on erillinen tiedosto, esimerkiksi seuraava **rakennetta kuvaava, käyttökelvottomilla paikkamerkeillä varustettu** JSON:

```json
{
  "map_sha256": "REPLACE_WITH_MAP_INFO_DIGEST",
  "identity": {"model": "EXACT_MODEL", "firmware": "EXACT_VERSION", "application": "EXACT_APPLICATION"},
  "points": {
    "CONFIRMED_POINT_KEY": {
      "documentation": "exact source/version/page and register",
      "reviewed_by": "actual reviewer",
      "physically_verified": false
    }
  }
}
```

CLI:n eristetty testilaite voi testata dokumentoitua pistettä ennen `physically_verified`-merkintää. HA vaatii aidon JSON-booleanin `true` vasta onnistuneen fyysisen varmennuksen jälkeen. Laitteen fyysinen irrotus, kartan identiteetti ja arvon rajat on varmistettava erikseen. Politiikka on käyttäjän paikallinen hyväksyntä, ei kryptografinen valmistajan sertifikaatti. Älä kopioi synteettisen testin merkintöjä oikeaan laitteeseen.
