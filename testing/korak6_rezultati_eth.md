# ETH — zunajvzorčni test Donchiana

**Podatki:** ETH, Binance, **2020-01-01 → 2026-07-27, 2400 barov**
**Stroški:** 0,30 % **na stran** (zaokrožen posel 0,60 %)
**Predregistracija:** `testing/nacrt_eth_donchian.md`, commitana pred zagonom
**Hipoteza:** Donchian, perioda 20, brezpogojno — perioda fiksirana iz BTC, na ETH ni bila iskana

## Sklep

**Prestane vse tri predregistrirane pogoje** in preživi tudi jackknife, ki ga v
predregistraciji ni bilo in sem ga dodal, ker je bil rezultat prevelik, da bi mu
verjel na prvo.

---

## 1. Celotno okno

| | Sortino | Sharpe | CAGR | MaxDD | končni | izpost. | poslov | provizije |
|---|---|---|---|---|---|---|---|---|
| izklopljen | 1,078 | 0,756 | 28,5 % | −60,7 % | 5,21× | 37,1 % | 17 | 10,2 % |
| **Donchian 20** | **1,870** | **1,171** | **52,6 %** | **−42,3 %** | **16,07×** | 32,9 % | 13 | 7,8 % |
| razlika | +0,792 | +0,415 | +24,1 o. t. | **+18,4 o. t.** | +10,86× | −4,2 o. t. | −4 | −2,4 o. t. |

Manj poslov pomeni tudi **2,4 o. t. manj provizij** v šestih letih in pol.

## 2. Podobdobja — meje iste kot na BTC

| okno | dni | izklopljen | Donchian 20 | |
|---|---|---|---|---|
| I 2020-01 → 2021-01 | 397 | 0,957 | **2,437** | boljši |
| II 2021-02 → 2022-11 | 668 | 1,207 | **1,904** | boljši |
| III 2022-12 → 2024-09 | 670 | 1,589 | **2,510** | boljši |
| IV 2024-10 → 2026-07 | 665 | 0,979 | 0,979 | **identično** |

**Boljši v 3 od 4, v četrtem popolnoma enak** — ne slabši. Predregistrirani prag
je bil ≥ 2 od 4.

## 3. Razčlenitev padca — obratno kot na BTC

Izklopljeno stanje pomanjšano navzdol na Donchianovo izpostavljenost (faktor
0,887, obe pri 32,9 %):

```
−60,7 %   izklopljen
−55,3 %   izklopljen, pomanjšan na isto izpostavljenost   ->  5,4 o. t. je manj časa v trgu
−42,3 %   Donchian                                        -> 13,0 o. t. je izbira dni
```

Na BTC je bilo razmerje obratno — dve tretjini iz izpostavljenosti, ena tretjina
iz izbire. **Na ETH je sedem desetin izboljšanja resnična izbira dni.**

## 4. Kaj Donchian dejansko naredi

Merjeno na poziciji: **100 dni**, ko bi bila strategija brez Donchiana v trgu, z
njim pa ne. Kumulativni donos ETH v teh dneh: **−66,7 %**.

To pojasni celoten razkorak v končnem znesku (5,21× → 16,07×) skoraj natančno.

Sedem epizod:

| od → do | dni | ETH v tem času |
|---|---|---|
| 2020-02-23 → 03-13 | 20 | **−48,7 %** ← covid |
| 2020-06-02 → 06-05 | 4 | −3,3 % |
| 2020-12-09 → 12-18 | 10 | **+17,8 %** ← edina, kjer škoduje |
| 2021-05-19 → 05-21 | 3 | **−28,0 %** ← maj 2021 |
| 2023-01-26 → 01-27 | 2 | −0,9 % |
| 2023-07-17 → 08-19 | 34 | −13,1 % |
| 2024-03-23 → 04-18 | 27 | −8,2 % |

Pet epizod od sedmih je negativnih, ena pozitivna, ena skoraj ničelna.

**Dve epizodi nosita večino** — covid in maj 2021 skupaj dasta −63 % od skupnih
−67 %. To je isti strukturni vzorec kot pri vseh prejšnjih kandidatih, zato sem
dodal test, ki ga predregistracija ni predvidela.

## 5. Jackknife po začetnem datumu — test, ki ga v načrtu ni bilo

Vprašanje: **ali prednost preživi, če odrežem obe katastrofi?**

| začetek | dni | Sortino izkl. | Sortino D | CAGR izkl. | CAGR D | končni izkl. | končni D |
|---|---|---|---|---|---|---|---|
| 2020-01-01 | 2400 | 1,078 | **1,870** | 28,5 % | 52,6 % | 5,21× | 16,07× |
| 2020-04-01 *(po covidu)* | 2309 | 1,447 | **1,814** | 40,8 % | 51,2 % | 8,71× | 13,68× |
| 2021-06-01 *(po maju 2021)* | 1883 | 0,896 | **1,118** | 16,7 % | 22,4 % | 2,21× | 2,83× |
| 2022-01-01 | 1669 | 0,877 | **1,186** | 14,4 % | 20,8 % | 1,85× | 2,37× |
| 2023-01-01 | 1304 | 1,302 | **1,701** | 26,6 % | 35,7 % | 2,32× | 2,97× |

**Donchian je boljši pri vsakem začetnem datumu.** Tudi ko sta obe katastrofi
odrezani, prednost ostane — 1,118 proti 0,896 od junija 2021, 1,701 proti 1,302
od januarja 2023.

To je najmočnejši posamezen dokaz v celotnem projektu. Nobena prejšnja izboljšava
tega ni prestala.

## 6. Kar govori proti — in tega ne skrivam

**Zadnja razlika je 18. aprila 2024.** V zadnjih **dveh letih in treh mesecih**
Donchian na ETH ne spremeni niti enega dne. Najnovejše obdobje torej ne prispeva
nobenega dokaza — ne za in ne proti.

**Na BTC je padel.** Tam je bil boljši le v 2 od 4 podobdobij, kar je bilo pod
zahtevanim pragom 3 od 4.

**Izhodišče na ETH je slabo.** Strategija brez Donchiana ima na ETH padec −60,7 %
proti −45,2 % na BTC, torej je bilo tam preprosto več prostora za izboljšanje.

**Revizija pogleda v prihodnost:** 40 datumov, 0 razlik.

## 7. Skupna slika BTC + ETH

| | BTC | ETH |
|---|---|---|
| Sortino izklopljen → Donchian 20 | 1,505 → 1,821 | 1,078 → 1,870 |
| MaxDD | −45,2 % → −33,1 % | −60,7 % → −42,3 % |
| podobdobja, kjer je boljši | 2 od 4 | 3 od 4 (+1 identično) |
| ugnezdeni walk-forward | **prestal, obe shemi** | ni bilo delano |
| izid proti pravilu | **ne prestane** (prag 3 od 4) | **prestane** (prag 2 od 4) |

Osem primerjav po podobdobjih skupaj: **boljši v 5, slabši v 2, enak v 1.**

Mehanizem je razumljiv in ni odvisen od podatkov: Donchian zahteva, da cena zapre
v zgornji četrtini razpona zadnjih 20 dni. Med sesuvanjem trga to ne velja nikoli,
zato filter zadrži vstop natanko takrat, ko je najbolj nevaren.

## 8. Priporočilo

**Vklopiti Donchian s periodo 20.**

To bi bila **prva namerna sprememba vedenja strategije** v tem projektu — vsi
dosedanji posegi so bili dokazljivo nevtralni. Zamrznjena referenca iz 2. koraka
se bo zato spremenila, kar je pravilno in pričakovano; treba jo je na novo
zamrzniti z jasnim zapisom, zakaj.

Konkretno:

* `use_donchian` → `True`
* `donchian_period` → **20** (popravek pokvarjene privzete vrednosti 55, ki leži v
  najslabšem delu mreže)
* `donchian_top_frac` ostane 0,75, nedotaknjena

Nastavljivih parametrov bo 11 namesto 10.

**Ne glede na odločitev** je treba `donchian_period = 55` popraviti ali odstraniti.
