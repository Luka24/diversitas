# Predlog v2 — ob omejitvi, da pozicija ostane binarna

Nadomešča `PREDLOG.md`, ki je predlagal stopnjevano velikost. Ta odpade.

---

## 1. Kaj odpade in zakaj

**Stopnjevana velikost pozicije (33 / 67 / 100 %) je izven igre** — pozicija mora
ostati 0 ali 100 %. To je operativna omejitev, ne rezultat testa, in jo
sprejemam.

**Različica, ki si jo dejansko mislil — večina pogojev, polna pozicija — je bila
testirana trikrat:**

| | Sortino | MaxDD | zajem navzdol | zamuda vstopa |
|---|---|---|---|---|
| danes: vsi trije | 1,505 | **−45,2 %** | **37,8** | **3,5 dni** |
| 2 od 3, polna pozicija | 1,563 | −53,3 % | 43,5 | 5,7 dni |

Sortino je za las boljši (+0,058), **padec pa za 8 odstotnih točk slabši**, zajem
padcev za 5,7 o. t. slabši, zamuda daljša. Interval zaupanja objame ničlo.

Razlog je razumljiv: **večina dovoli nakup takrat, ko je odpovedal ravno cenovni
pogoj** — torej ko je cena pod razponom. To je natanko trenutek, ko se ne kupuje.

**Zaostrovanje je delovalo, rahljanje ne.**

---

## 2. Kaj torej predlagam: Donchian

Ker stopnjevana velikost odpade, je **Donchian najmočnejši preostali kandidat** —
in zdrži binarno pozicijo.

| | danes | z Donchianom |
|---|---|---|
| Sortino | 1,505 | **1,821** |
| CAGR | 33,6 % | 36,1 % |
| najhujši padec | −45,2 % | **−33,1 %** |
| končni mnogokratnik | 8,55× | 9,78× |
| čas v trgu | 41,9 % | 32,9 % |
| **poslov** | 21 | **17** |
| **obrat** | 42,0 | **34,0** |

**Stroški se znižajo**, ne zvišajo. To je redko — večina dodatkov k strategiji
denar stane.

### Kaj je Donchian prestal

| test | izid |
|---|---|
| ugnezdeni walk-forward, obe shemi | **✔ edini kandidat v projektu** |
| ETH zunaj vzorca, vsi trije pogoji | ✔ |
| CSCV: premaga izklopljeno v 97,5 % zunajvzorčnih polovic | ✔ |
| naključni zamik | ✔ 96. percentil |
| stroški | ✔ nižji |

### Kaj ni prestal

**Doslednost po obdobjih: boljši v 2 od 4.** Pomaga v trendnih obdobjih (I, III),
ne pomaga v stranskih (II je medvedji trg 2022, IV zadnji dve leti).

In: **v letih 2025–2026 ni spremenil nobenega dne.**

### Poštena presoja

Donchian ni prestal najstrožjega merila, je pa prestal **več neodvisnih preverb
kot karkoli drugega v projektu**, znižuje stroške in izboljša padec za 12
odstotnih točk.

Mehanizem ni prilagojen podatkom: med sesuvanjem cena po definiciji ni na vrhu
20-dnevnega razpona, zato filter zadrži nakup natanko takrat, ko je najnevarneje.

**Priporočam sprejem** — kot zavarovanje pred padci, ne kot izboljšavo donosa.

---

## 3. Kako se ATR stop testira profesionalno — in kaj sem naredil narobe

### 3.1 Teoretični okvir: Kaminski & Lo

**Kaminski & Lo, *When Do Stop-Loss Rules Stop Losses?*, Journal of Financial
Markets 18 (2014)** — merodajen prispevek na tem vprašanju.

Ključna ugotovitev: **pri naključnem hodu preprosta 0/1 stop pravila VEDNO
zmanjšajo pričakovani donos.** Vrednost dodajo samo ob prisotnosti **momentuma
ali menjave režimov**.

To je teoretična razlaga, zakaj je naš ATR stop padel — in hkrati pove, **kaj bi
bilo treba meriti**: ne donosa strategije, ampak **premijo ustavitve** — razliko v
pričakovanem donosu med obdobji, ko nas stop drži zunaj, in tem, kar bi se
zgodilo, če bi ostali.

To je bolj načelno od tega, kar sem meril, in bom to popravil.

### 3.2 Napaka, ki sem jo pravkar odkril

Moj test je preverjal `zaključek < vrh − N × ATR`. **Pravi stop se sproži, ko ga
dnevno DNO doseže med dnevom.**

| | Sortino | CAGR | MaxDD | sprožitev |
|---|---|---|---|---|
| ATR × 3, samo zaključek | 1,483 | 29,4 % | −46,2 % | 19 |
| ATR × 3, **dotik dnevnega dna** | **0,733** | 10,5 % | −42,0 % | 29 |

**Moj test je bil preveč prizanesljiv.** S pravilno izvedbo je ATR stop še slabši —
polovica Sortina. Sklep se ne spremeni, dokaz zanj pa je zdaj močnejši.

### 3.3 Kaj literatura navaja kot pasti

Formalna taksonomija napak pri testiranju stopov navaja tri razrede:

1. **kršitve zaporedja izstopa** — če se v istem baru sprožita dve pravili, katero
   prvo? Naša strategija ima blow-off in trend-break; treba je izrecno določiti.
2. **puščanje cenovnih podatkov naprej** — uporaba dnevnega dna zahteva previdnost,
   da se ne uporabi podatek, ki ga v trenutku odločitve še ni bilo
3. **kontaminacija vzorca**

Za nas je relevantna prva in druga. Prvo bom določil izrecno, drugo je s
`.shift(1)` že rešeno.

---

## 4. Odgovor na sodelavčevo vprašanje o periodi

Test, ki ga predlaga, sem pognal — periode 20 do 75, pas fiksnih 3 %:

| dni | BTC | ETH |
|---|---|---|
| 20 | 1,606 | 2,211 |
| 25 | 1,525 | **2,267** |
| 30 | 1,485 | 1,829 |
| 35 | 1,701 | 1,500 |
| **40** | **2,016** | 1,450 |
| 45 | 1,585 | 1,578 |
| 50 | 1,313 | 1,439 |
| 75 (danes) | 1,505 | 1,078 |

**Na BTC je 40 osamljena konica** — 35 da 1,701, 45 da 1,585, 50 pade na 1,313.
**Na ETH je najboljša 25**, in krivulja pada gladko proti 75.

**Sredstvi se ne strinjata, kje je optimum.** PBO izbire periode je na BTC 0,429,
in izbira v vzorcu se izmenjuje med **40 in 75** — dvakratna razlika.

**Skupno obema je smer, ne vrednost:** krajše od 75 je boljše na obeh.

Zato **ne priporočam iskanja optimalne periode**. Če bi periodo skrajšali, naj bo
to na uveljavljeno vrednost (20) ali povprečje čez 20–40, ne pa najboljša iz
mreže.

### In popravek sodelavčeve intuicije o tesnem razponu

Prilagodljivi pas dela **nasprotno** od tega, kar želi. V tesnem razponu
98–102k je pas 25 % od 4.000 = **1.000**, torej prag 101.000; fiksni 3 % bi dal
103.000. **V tesnem razponu prilagodljivi pas vstopi PREJ, ne pozneje.**

Za to, kar opisuje — izogib vstopom v tesnem razponu — bi potreboval pravilo, ki
zahteva **širino** razpona. To je bližje njegovemu ER filtru kot Donchianu.

---

## 5. Načrt

### Faza 0 · 1 h — poenoti merilo

Merila med testi niso bila enotna. Uporabim isto merilo na vseh kandidatih in
izdelam eno tabelo, preden se karkoli sprejme.

### Faza 1 · 2 h — ATR stop po Kaminski-Lo

Ne zato, ker pričakujem drugačen izid, ampak ker je bil dosedanji test
metodološko šibek in ker je bil sodelavcu obljubljen:

- **premija ustavitve** namesto donosa strategije
- **dotik dnevnega dna**, ne zaključek
- izrecno določeno zaporedje, če se sprožita dve pravili hkrati
- preveriti, ali BTC sploh ima momentum na tem horizontu — to je pogoj, pod
  katerim stopi po Kaminski-Lo sploh lahko delujejo

### Faza 2 · 3 h — sprejem Donchiana

- `use_donchian = True`, `donchian_period = 20`
- perioda **zaklenjena** v `config.py` z razlogom (PBO 0,672)
- referenco na novo zamrzniti z zapisom, zakaj
- test proti novi referenci, negativna kontrola mora še vedno zaznati
- revizija pogleda v prihodnost

### Faza 3 · 5 h — robustnost na novi strategiji

4-urni bari · obdobje po ETF · **trgovanje po odprtju naslednjega dne** · vir podatkov

### Faza 4 · 4 h — karakterizacija

deflacionirani Sharpe pri ~230 poskusih · sodelovanje v padcih · MinTRL ·
pošteno pričakovanje

### Faza 5 · 3 h — poročilo in konec

**Skupaj ~18 ur.**

---

## 6. Kaj je treba povedati odkrito

**O Donchianu:** izboljša padec za 12 odstotnih točk in zniža stroške, a **v
zadnjih dveh letih ni spremenil nobenega dne** in v stranskem trgu ne pomaga.
Sprejemamo ga kot zavarovanje, ne kot izboljšavo donosa.

**O merilih:** ni prestal najstrožjega, ki smo ga uporabili drugje. Faza 0
obstaja prav zato, da to razčistimo, preden se odločimo.

**O dokazni moči:** vse skupaj stoji na približno dvajsetih poslih. Nobena
statistika tega ne popravi.
