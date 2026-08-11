# Korak 6 — rezultati: Donchianova potrditev

**Podatki:** BTC, Binance, 2019-03-09 → 2026-07-29, 2700 barov · neto 0,30 % na stran
**Predregistracija:** `testing/nacrt_korak6_donchian.md`, commitana pred zagonom
**Skripta:** `testing/scripts/donchian_test.py` · **JSON:** `testing/data/donchian_BTC.json`

## Sklep

**Ne prestane predregistriranega pravila — pade na doslednosti po obdobjih (2 od 4).**

Je pa **daleč najmočnejši kandidat doslej** in edini, ki je prestal ugnezdeni
walk-forward. To ni isto kot »nič ni bilo«, in tako tudi ne bo predstavljeno.

`donchian_period = 55` se popravi ne glede na to.

---

## 1. Fiksne periode — vse prekašajo izklopljeno stanje

| N | Sortino | CAGR | MaxDD | končni | izpost. | poslov | I | II | III | IV |
|---|---|---|---|---|---|---|---|---|---|---|
| **izklopljen** | **1,505** | 33,6 % | −45,2 % | 8,55× | 41,9 % | 21 | 1,50 | **1,24** | 1,99 | **1,60** |
| 10 | 1,747 | 34,1 % | −33,1 % | 8,78× | 32,6 % | 17 | 2,16 | 1,20 | 2,80 | 1,16 |
| **12** | **1,897** | 38,1 % | **−30,2 %** | 10,90× | 33,7 % | 17 | **2,53** | 1,20 | **2,80** | 1,45 |
| 15 | 1,821 | 36,1 % | −33,1 % | 9,78× | 32,9 % | 17 | 2,39 | 1,09 | 2,80 | 1,45 |
| 20 | 1,821 | 36,1 % | −33,1 % | 9,78× | 32,9 % | 17 | 2,39 | 1,09 | 2,80 | 1,45 |
| 25 | 1,744 | 35,9 % | −39,8 % | 9,69× | 36,8 % | 18 | 2,51 | 0,70 | 2,80 | 1,54 |
| 30 | 1,604 | 32,3 % | −39,8 % | 7,92× | 37,0 % | 18 | 2,99 | 0,30 | 1,99 | 1,60 |
| 40 | 1,809 | 39,4 % | −39,8 % | 11,67× | 38,9 % | 18 | 2,59 | 1,11 | 2,14 | 1,60 |
| 55 (privzeta) | 1,720 | 37,5 % | −39,8 % | 10,56× | 40,1 % | 19 | 2,59 | 1,11 | 1,69 | 1,60 |

**Vseh osem period prekaša izklopljeno stanje.** To se v tem projektu še ni
zgodilo — pri premoru in pri mrtvem pasu je bila boljša ena sama nastavitev.

Hkrati Donchian **zmanjša izpostavljenost** (41,9 % → 32,6–40,1 %) in **število
poslov** (21 → 17–19), torej tudi stroške.

## 2. Ugnezdeni walk-forward — primarni test, in prestal je

Perioda izbrana **izključno iz učnega dela**, merjeno na testnem:

| shema | zavoji | izbrane periode | | Sortino | CAGR | MaxDD | končni |
|---|---|---|---|---|---|---|---|
| **3 leta / 1 leto** | 4 | 40 · 12 · 10 · 12 | izklopljen | 1,430 | 23,9 % | −23,6 % | 2,36× |
| | | | **refit** | **1,575** | 22,8 % | −23,6 % | 2,28× |
| | | | fiksna 20 | **2,074** | 30,3 % | −23,6 % | 2,88× |
| **2 leti / 1 leto** | 5 | 40 · 12 · 10 · 10 · 25 | izklopljen | 1,051 | 19,3 % | −39,8 % | 2,41× |
| | | | **refit** | **1,232** | 21,9 % | −29,0 % | 2,69× |
| | | | fiksna 20 | 1,269 | 22,8 % | −29,0 % | 2,79× |

**Refit prekaša izklopljeno v obeh shemah.** Pogoj 1 je izpolnjen — in to je
edini kandidat v celotnem projektu, ki mu je uspelo.

**Napoved v §5 predregistracije je bila napačna.** Napovedal sem, da bo
walk-forward izgubil, ker je enako vrtanje po štirih drugih parametrih izgubilo
v 0 od 4 shem.

Dva pridržka, ki ju je treba nositi zraven:

* **Fiksna 20 prekaša refit v obeh shemah.** Ponovno izbiranje periode torej ne
  doda ničesar nad tem, da izbereš eno vrednost in jo pustiš. Koristi filter, ne
  prilagajanje.
* **Izbrane periode so nestabilne** — 40, 12, 10, 12 oziroma 40, 12, 10, 10, 25.
  Tri do štiri različne izbire v štirih do petih zavojih.

## 3. Kje pade: doslednost po obdobjih

| obdobje | izklopljen | N = 12 | N = 20 | |
|---|---|---|---|---|
| I 2019-03 → 2021-01 | 1,50 | **2,53** | **2,39** | boljše |
| II 2021-02 → 2022-11 | **1,24** | 1,20 | 1,09 | **slabše** |
| III 2022-12 → 2024-09 | 1,99 | **2,80** | **2,80** | boljše |
| IV 2024-10 → 2026-07 | **1,60** | 1,45 | 1,45 | **slabše** |

**2 od 4.** Predregistrirano pravilo zahteva ≥ 3. Pogoj 2 pade.

Vzorec ni naključen: Donchian pomaga v **trendnih obdobjih** (I in III) in škoduje
v **stranskih** (II je medvedji trg 2022, IV zadnji dve leti). To je razumljivo —
zahteva preboj, teh pa v stranskem trgu ni.

## 4. Padec ni artefakt izpostavljenosti

Donchian **zmanjša** čas v trgu, zato je bilo treba pomanjšati izklopljeno stanje
navzdol do njegove ravni, ne obratno:

| N | izpost. | MaxDD Donchian | MaxDD izklopljeno, pomanjšano na isto izpost. |
|---|---|---|---|
| 12 | 33,7 % | **−30,2 %** | −37,8 % |
| 15 | 32,9 % | −33,1 % | −37,1 % |
| 20 | 32,9 % | −33,1 % | −37,1 % |
| 40 | 38,9 % | −39,8 % | −42,6 % |
| 55 | 40,1 % | −39,8 % | −43,6 % |

Pri vsaki periodi je Donchianov padec **plitkejši od preprostega zmanjšanja
pozicije**. Izboljšanje padca je torej resnično in ne posledica manj časa v trgu.

### Metodološka ugotovitev o mojih dosedanjih testih

Pomanjšano izklopljeno stanje da **Sortino 1,505 pri vsakem faktorju** — od 0,78
do 0,96. Razlog: Sortino je razmerje, in enakomerno skaliranje pozicij deli
števec in imenovalec z istim številom.

To pomeni, da **»izenačena izpostavljenost« pri Sortinu sploh ne more ničesar
pokazati** — in tudi v korakih 4 in 5 ni. Tam so bile izenačene številke enake
neizenačenim, česar nisem opazil. Test je vseskozi preverjal **samo MaxDD in
zajem navzdol**, kar je še vedno smiselno, a manj, kot sem trdil.

## 5. Kaj Donchian dejansko naredi

Merjeno na **poziciji**, ne na pogoju — blokiran signal na dan, ko smo že v trgu,
ne spremeni ničesar:

| | dni | donos BTC +20 dni |
|---|---|---|
| izhodišče, vsi dnevi | 2680 | +3,27 % |
| **Donchian nas drži zunaj** | 244 | **+5,15 %** |
| Donchian nas drži notri | 1 | −15,25 % |

**Donchian nas drži zunaj na dnevih, ki so v povprečju nadpovprečni.** In vendar
se CAGR izboljša (33,6 % → 36,1 %) in padec zmanjša.

To ni protislovje, je pa vredno razumeti: povprečje +5,15 % skriva porazdelitev.
Sortino in MaxDD se odzivata na levi rep, ne na povprečje. Donchian se torej
odpove nekaj povprečnega donosa v zameno za izogib najhujšim izidom — plus
prihrani štiri posle.

## 6. Napovedi proti izidu

| napoved (§5) | izid |
|---|---|
| 1. ugnezdeni walk-forward bo izgubil | **✘ ni** — prestal je v obeh shemah |
| 2. fiksna perioda okoli 20 bo izgledala dobro | ✔ 1,821 |
| 3. izpostavljenost bo padla | ✔ 41,9 % → 32,9 % |
| 4. ne prestane, popravimo 55 | ✔ ne prestane, a iz drugega razloga |

## 7. Odločitev

| | pogoj | izid |
|---|---|---|
| 1 | walk-forward prekaša izklopljeno v obeh shemah | **✔** |
| 2 | boljši v ≥ 3 od 4 podobdobij | **✘ 2 od 4** |
| 3 | prednost preživi izenačeno izpostavljenost | **✔** (za MaxDD) |
| 4 | plato, ne konica, izbrana perioda ni na robu | **delno** — razpon 0,293, najboljša 12 je tik ob robu mreže (10) |

**Ne prestane.** Donchian ostane izklopljen.

## 8. Kaj naprej

Trije razlogi, da to **ni** zaključena zadeva:

1. **Edini kandidat, ki je prestal walk-forward.** Vsi doslej so padli tam.
2. **Vseh osem period prekaša izklopljeno stanje** — to ni ena nastavitev, ki bi
   izstopala, ampak celoten razpon.
3. **Padec se izboljša za 7,6 o. t. tudi pri izenačeni izpostavljenosti.**

Kar ga ustavi, je jasen in razumljiv vzorec: **pomaga v trendu, škoduje v
stranskem trgu.** To je hipoteza, ki se jo da preveriti neposredno — in bolje jo
je preveriti kot obiti.

**Predlog:** naslednji test naj bo pogojni Donchian — vklopljen samo, kadar je
režim trenden. Za »trenden« se uporabi `ma_long_rising`, ki že obstaja, torej
brez novega parametra. Če vzorec iz §3 drži, mora to popraviti obdobji II in IV.

**Ne glede na vse:** `donchian_period = 55` je treba popraviti. Leži v najslabšem
delu mreže in bi vsakogar, ki zastavico vklopi, pripeljal do slabšega rezultata,
kot ga ponuja plato.
