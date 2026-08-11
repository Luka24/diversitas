# Koraka 6 in 8 — izvedba po izvirnem načrtu

**Status:** predregistracija, pred izvedbo
**Izvirna specifikacija:** `testing/nacrt_izvedbe_v2.txt`, koraka 6 in 8
**Stroški:** 0,30 % na stran · **BTC primarno, ETH se ne uporablja** (porabljen)

---

## 0. Zakaj to ne krši pravila o ustavitvi

V `nacrt_do_konca.md` sem zapisal, da se iskanje izboljšav konča. To pravilo
velja za **naknadno izmišljene** hipoteze.

Koraka 6 in 8 sta bila **v načrtu od začetka**, zapisana pred vsemi rezultati.
Preizkusiti vnaprej zapisano hipotezo ni isto kot dodati novo, ker ne razširja
družine poskusov za nazaj — je le dokončanje tega, kar je bilo že registrirano.

Po teh dveh je seznam vnaprej zapisanih hipotez **izčrpan**.

---

## 1. Korak 6 — vstop, ko velja večina pogojev

### Kaj je bilo narejeno napačno

Moj prejšnji test (`majority_vote.py`) je glasoval o `{above_tl, Donchian, naklon}`
in ohranil `regime_ok` kot trdo zahtevo. Izvirna specifikacija zahteva glasovanje
o **treh dejanskih vstopnih pogojih**:

```
above_tl · track_rising_window · regime_ok
```

Poleg tega manjka del D: **izpad vsakega pogoja posebej**.

### Celice

| | pravilo |
|---|---|
| **3/3** | vsi trije — **današnje stanje, kontrola** |
| **2/3** | vsaj dva od treh |
| **1/3** | vsaj eden od treh |
| **−above_tl** | brez cenovnega pogoja, druga dva obvezna |
| **−naklon** | brez naklona |
| **−regime** | brez režimskega bloka |

Blow-off ostane trda zahteva v vseh — je izstopno pravilo, ki od 2026-08-04
blokira tudi vstop.

### Opozorilo, ki ga je treba nositi

Celice `2/3`, `1/3` in `−regime` **dovolijo nakup v potrjenem medvedjem trgu**.
To ni sprememba časovnice vstopa, ampak **spremenjen profil tveganja**. Izvirni
načrt je to zahteval in bom izvedel, a rezultat je treba brati s to vednostjo,
ne kot navadno izboljšavo.

### Kaj se meri

Zamuda vstopa · zajem navzdol · izpostavljenost · Sortino · MaxDD · poslov ·
podobdobja.

### Sprejemni kriterij (izvirni)

`2/3` mora **zmanjšati zamudo IN ohraniti zajem navzdol znotraj 1,0 o. t.**

### Kaj bi bilo najpomembnejše odkritje

Izvirni načrt to pove sam: **če `1/3` ni bistveno slabši od `3/3`, vstopni pogoji
skupaj ne nosijo informacije.** To bi bilo pomembnejše od izbire praga in bo
zapisano kot tako.

---

## 2. Korak 8 — ATR trailing stop

### Sprememba

```
peak  = najvišji close od vstopa
izstop, ko  close < peak − N × ATR(14)
```

Nadomesti izstop na trackline. Blow-off ostane.

### Vrednosti N

Izvirno `{1,5 · 2 · 2,5 · 3 · 4}`.

**Argmaksa ne bom izbral** — PBO 0,672 in 0,694 sta pokazala, da se izbira
parametra na teh podatkih ne prenaša. Gleda se **oblika** krivulje. Če bo
sprejeto, se uporabi **N = 3**, ker je to Chandelierjeva konvencija
(`najvišji vrh − 3 × ATR(22)`), izbrana zunaj naših podatkov.

### Kaj se meri — po izvirni specifikaciji

**Primarno nadaljnji padec, ne donos.** Izstop naj varuje pred padcem.

**Primerjalna skupina: samo dnevi, ko SMO V POZICIJI.** Ne vsi dnevi v vzorcu —
to je bila napaka, ki jo je izvirni načrt izrecno predvidel.

### Sprejemni kriterij (izvirni)

Zajem navzdol se izboljša za **več kot 2 o. t.** IN uvrstitev **zdrži na
4-urnih barih**.

### Kaj vem vnaprej

Izvirni načrt je temu koraku dal **najnižjo prioriteto** z utemeljitvijo, da so
izstopi že v redu. Test izstopnih različic to potrjuje: nobena Turtlova
alternativa ni prekašala današnjega izstopa, prilagajanje izstopa pa je bilo
**slabše od nespreminjanja v vseh štirih walk-forward shemah**.

Pričakovati je torej, da tudi ta ne bo prestal. Vseeno se izvede, ker je
industrijski standard in ker je bil obljubljen.

---

## 3. Kontrola v obeh testih

Kontrolna celica mora reproducirati **zamrznjeno referenco bar za barom**. Če se
ne, se test ustavi.

## 4. ETH

**Ne uporabljam.** Obe vnaprej zapisani uporabi sta porabljeni. Vse je na BTC,
z izrecno navedbo, da medsredstvene potrditve ni.

## 5. Rezultati

| datoteka | vsebina |
|---|---|
| `testing/scripts/entry_vote_orig.py` | korak 6 po izvirni specifikaciji |
| `testing/scripts/atr_trailing.py` | korak 8 |
| `testing/data/entry_vote_orig.json`, `atr_trailing.json` | meritve |
