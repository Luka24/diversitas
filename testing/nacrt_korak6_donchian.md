# Korak 6 — Donchianova potrditev vstopa

**Status:** predregistracija, pred izvedbo
**Podatki:** BTC, Binance, 2019-03-09 → 2026-07-29, 2700 barov · 0,30 % na stran
**Novi parametri:** 1 (`donchian_period`), če se sprejme

---

## 0. Zakaj to in ne korak 6 iz prvotnega načrta

Donchian je **že napisan** v `lean/diversitas/strategy.py`, privzeto izklopljen.
Zahteva, da cena zapre v zgornji četrtini razpona zadnjih N dni — torej pravi
preboj, ne le prečkanje trackline.

Iz `korak1_lean_parametri.md`, BTC Sortino po periodi:

| perioda | 12 | 15 | 18 | 20 | 22 | 25 | 30 | 55 (privzeta) | izklopljen |
|---|---|---|---|---|---|---|---|---|---|
| | 1,76 | 1,72 | 1,72 | 1,72 | 1,70 | 1,64 | 1,36 | **1,47** | **1,55** |

Trije razlogi, da gre pred vse ostalo:

1. **Plato od 12 do 22**, ne konica — oblika, ki jo ta projekt šteje za robustno.
2. **Učinek je večji od vsega, kar je našel korak 5** — +0,17 proti +0,07 Sortina.
3. **Privzeta vrednost 55 leži v najslabšem območju** (1,47, slabše od
   izklopljenega 1,55). To je odprta napaka: kdor bi zastavico vklopil, bi ga
   zavedla. Popraviti jo je treba **ne glede na izid testa**.

Pridržek, ki ga je treba nositi skozi ves korak: **prvotna utemeljitev za
Donchian je bila ovržena.** Vključen je bil, ker naj bi validacijski Calmar
monotono rasel s periodo; na popravljenih podatkih pada. Da smo zdaj tu, je torej
posledica sweepa, ne hipoteze.

---

## 1. Osrednji problem in odgovor nanj

Številke zgoraj so **sweep**. Vzeti periodo 20, ker leži v platoju, je še vedno
izbira iz mreže — natanko to, kar smo v koraku 5 zavrnili.

Zato je **primarni test ugnezdeni walk-forward**, kjer se perioda izbere
**izključno iz učnega dela**, meri pa se, kaj se zgodi naprej. To spremeni
vprašanje iz »katera perioda je bila najboljša« v »ali postopek, ki periodo
izbere iz preteklosti, prinese kaj v prihodnosti«.

Fiksni sweep se še vedno požene, a **samo za obliko** — plato proti konici.
Argmaks se ne izbira.

---

## 2. Kaj se testira

**Kontrola A** — Donchian izklopljen, današnja strategija. Mora reproducirati
zamrznjeno referenco bar za barom, sicer se korak ustavi.

**Fiksne periode** — 10 · 12 · 15 · 20 · 25 · 30 · 40 · 55, pri
`donchian_top_frac = 0,75` (obstoječa privzeta vrednost, **ne** se prevrta —
prevrtati oboje bi pomenilo mrežo in podvojilo število poskusov).

**Ugnezdeni walk-forward** — dve shemi, obe določeni vnaprej:

```
učno 3 leta / testno 1 leto   (4 zavoji)
učno 2 leti / testno 1 leto   (5 zavojev)
```

V vsakem zavoju se perioda izbere iz učnega dela po Sortinu, nato uporabi na
testnem. Testni deli se zlepijo v eno serijo zunaj vzorca. Primerja se s tremi
stvarmi: **izklopljen**, **fiksna perioda 20** in **fiksna 55**.

---

## 3. Kaj se meri

Sortino, Sharpe, CAGR, MaxDD, končni mnogokratnik, izpostavljenost, obrat,
število poslov — na celotnem oknu in po istih štirih podobdobjih kot v korakih
4 in 5.

Poleg tega:

* **koliko dni Donchian blokira** vstop, ki bi sicer bil veljaven, in **kakšen je
  donos BTC v naslednjih 20 dneh** na teh dnevih — ali blokira dobre ali slabe dni
* **izenačena izpostavljenost** — Donchian doda pogoj, torej bo zmanjšal čas v
  trgu; prednost, ki izgine ob izenačenju, ni prednost
* **revizija pogleda v prihodnost** — Donchian uporablja `highest(high, N)` in
  `lowest(low, N)`, kar sta zaostali okni, a to je argument in ne meritev

---

## 4. Odločitveno pravilo — vnaprej

### Sprejmi Donchian, če velja VSE:

| | pogoj |
|---|---|
| 1 | **ugnezdeni walk-forward** prekaša izklopljeno stanje zunaj vzorca, v **obeh** shemah |
| 2 | boljši v **≥ 3 od 4** podobdobij |
| 3 | prednost preživi **izenačeno izpostavljenost** |
| 4 | fiksni sweep kaže **plato, ne konice**, in izbrana perioda ni na robu mreže |

### Če pogoj 1 pade, ostala tri ne štejejo

Perioda, ki v učnem delu zmaga, v testnem pa ne, je definicija prilagajanja
preteklosti. Ostala tri merijo obliko in artefakte, ne prenosljivosti.

### Ne glede na izid

`donchian_period = 55` se **popravi ali odstrani**. Leži v najslabšem območju
mreže in slabše od izklopljenega stanja.

---

## 5. Kaj pričakujem — zapisano vnaprej

1. **Ugnezdeni walk-forward bo izgubil.** Vsak učni del ima ~8–12 poslov, izbira
   pa poteka med osmimi kandidati. Prav ta postavitev je dala PBO 0,694. Enako
   vrtanje po `ma_long_len`, `confirm_bars`, `reentry_hold` in `exit_grace_bars`
   je izgubilo v **0 od 4** shem.
2. Fiksna perioda okoli 20 bo na celotnem oknu izgledala dobro — a to je isti
   sweep, iz katerega je hipoteza prišla, torej ne nov dokaz.
3. Izpostavljenost bo padla za nekaj o. t., ker Donchian doda pogoj.
4. **Najverjetnejši izid: ne prestane, a popravimo privzeto 55.**

Če se to uresniči, je bil ta korak vseeno vreden — odpravi odprto napako v
configu in zapre kandidata, ki je bil doslej odprt na podlagi ovržene
utemeljitve.
