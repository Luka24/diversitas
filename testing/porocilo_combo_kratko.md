# Combo model (Zarattini, Pagani, Barbon 2025): pravila in številke

## Pravila

Vse na dnevnih svečah, odločitev na zaključku.

**Nakup**

```
close(danes) > max( high, zadnjih n dni, brez danasnjega )
```

Preboj n-dnevnega vrha. Nič drugega. Ni potrjevanja, ni premora, ni filtra režima.

**Prodaja**

```
close(danes) <= sledilni_stop
```

**Sledilni stop**

```
ob nakupu:      stop = ( vrh_n + dno_n ) / 2          sredina Donchian kanala
vsak dan nato:  stop = max( prejsnji_stop, trenutna_sredina_kanala )
```

Stop se samo dviguje, nikoli spušča.

**Velikost pozicije**

```
utez = min( 0,25 / sigma , 200 % )
```

`sigma` je letna volatilnost sredstva na zadnjih treh mesecih. Miren trg pomeni
večjo pozicijo, do dvakratnega vzvoda. Divji trg manjšo.

**Devet modelov hkrati**, z n = 5, 10, 20, 30, 60, 90, 150, 250, 360.
Končna pozicija je enakomerno povprečje vseh devetih, zato je zvezna in ne 0/100.

**Izbira sredstev**, konec vsakega meseca:

- uvrščeno vsaj 365 dni
- ni stabilni kovanec, zavit token ali NFT
- mediani dnevni promet vsaj 2 milijona USD v zadnjih 30 dneh
- razvrsti po medianem prometu, vzemi prvih B
- enakomerne uteži, 1/B na sredstvo
- uravnavanje mesečno, s 20 % pragom

## Številke

Objavljeno v članku, obdobje 1. 1. 2015 do 19. 3. 2025, stroški 10 bazičnih točk:

| | letno | Sharpe | MaxDD |
|---|---|---|---|
| top 20 sredstev | 18 % | 1,57 | −11 % |

Moja ponovitev na istih pravilih, obdobje 26. 8. 2023 do 25. 8. 2026. Nabor
kandidatov je vseh 386 USD parov na Coinbase, od tega 273 z dovolj podatki.
Stolpec zapolnjenost pove, kolikšen del mest je pravilo dejansko zasedlo.

Ista širina kot v njihovi objavljeni številki, torej top 20:

| | letno | vol | Sharpe | Sortino | MaxDD | zapolnjenost |
|---|---|---|---|---|---|---|
| top 20, stroški 10 bp | 7 % | 7 % | 1,06 | 1,62 | −10 % | 97 % |
| top 20, stroški 30 bp | 6 % | 7 % | 0,86 | 1,30 | −11 % | 97 % |

Zadnja tri leta so slabša od objavljenega obdobja: letno z 18 % na 6 do 7 %,
Sharpe s 1,57 na 0,86 do 1,06. Padec ostaja majhen, okoli 10 %.

Upravičenih sredstev je 14 do 48 na mesec, odvisno od obdobja. Avgusta 2023,
sredi medvedjega trga, jih je bilo 14, februarja 2025 pa 48. Isti prag dveh
milijonov je v mirnem trgu veliko višja ovira.

## Dvoje, kar je treba vedeti ob teh številkah

**Stroški.** Njihova osnovna predpostavka je 10 bazičnih točk na stran. Mi
računamo 30. Tabela za BTC v članku, tista s Sharpom 1,58, je brez stroškov.

**Moj filter prometa meri samo Coinbase**, oni pa sešteto čez vse borze prek
CoinMarketCap. Moj prag je zato strožji in nabor manjši od njihovega. Ni pa to
razlog za razliko pri širini, ker je top 20 zapolnjen 97 %.

(Prejšnja različica tega poročila je navajala nižje številke in trdila, da je
top 20 nepopolnjen. To je bila napaka: nabor kandidatov je bil odrezan na
prvih 120 po abecedi namesto na najbolj likvidne. Popravljeno.)

Ponovitev modela na BTC se sicer z njihovo tabelo ujema: Combo pri meni
Sharpe 1,65 in padec −16 %, v članku 1,58 in −19 %.

Članek: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5209907

---

## Naša strategija na istih zadnjih treh letih

Obdobje 25. 8. 2023 do 24. 8. 2026, stroški 0,30 % na stran. Uteži postavljene
na začetku in nato nikoli uravnavane, vsako sredstvo trguje samo zase, noter in
ven po svojem signalu.

| | skupaj | letno | vol | Sharpe | Sortino | MaxDD |
|---|---|---|---|---|---|---|
| samo BTC | 156 % | 37 % | 26 % | **1,32** | **2,30** | −16 % |
| samo ETH | 127 % | 31 % | 34 % | 0,98 | 1,61 | −25 % |
| sestava 50/10/10/10/10/10 | 133 % | 32 % | 23 % | **1,32** | 2,09 | **−15 %** |

Sestava se z BTC izenači po Sharpu in ga za las prekaša po padcu, zaostane pa
po donosu in po Sortinu. ETH sam je najslabši od treh.

### To okno je izjema, ne pravilo

Isti izračun na petih različnih začetkih, vsi do danes:

| okno | | letno | Sharpe | Sortino | MaxDD |
|---|---|---|---|---|---|
| od 2023-08 | sam BTC | 37 % | **1,32** | **2,30** | −16 % |
| | sestava | 32 % | **1,32** | 2,09 | −15 % |
| od 2022-08 | sam BTC | 30 % | **1,07** | **1,82** | −23 % |
| | sestava | 23 % | 1,02 | 1,62 | −19 % |
| od 2022-01 | sam BTC | 24 % | **0,97** | **1,65** | −23 % |
| | sestava | 18 % | 0,90 | 1,43 | −19 % |
| od 2021-08 | sam BTC | 23 % | **0,85** | **1,34** | −31 % |
| | sestava | 18 % | 0,80 | 1,21 | −30 % |
| od 2021-06 | sam BTC | 25 % | **0,89** | **1,41** | −31 % |
| | sestava | 19 % | 0,84 | 1,28 | −30 % |

Sestava zaostaja za samim BTC na **štirih od petih oken** in se izenači na enem,
po Sortinu pa zaostaja na vseh petih. Kar dosledno prinese, je za odstotek ali
dva manjši padec in nižja volatilnost.

Opozorilo o načinu izračuna: zgornje številke veljajo za **rokave, ki se
postavijo enkrat in nato tečejo**. Prejšnja različica tega poročila je za isto
sestavo navajala 0,90 proti 0,87 za BTC, kar je izhajalo iz izračuna, ki je
uteži vsak dan vračal na 50/10/10/10/10/10, in to brez stroška uravnavanja.
Tako se ne da trgovati, zato tista številka ne velja.

Kako so se rokavi razlezli v treh letih, ker se ne uravnavajo:

```
BTC    50,0 %  ->  55,1 %
BNB    10,0 %  ->  12,0 %
ETH    10,0 %  ->   9,8 %
SOL    10,0 %  ->   9,3 %
LINK   10,0 %  ->   7,4 %
HYPE   10,0 %  ->   6,4 %
```

HYPE je izgubil delež, ker je njegov rokav večino obdobja čakal v gotovini.
Podatki zanj se začnejo decembra 2024, prvi signal pa je mogoč šele po 220
barih ogrevanja, torej sredi 2025.

### Kaj če ta rokav ne čaka v gotovini

Preizkušeno: dokler sredstvo ni izračunljivo, njegov delež prevzame **naša BTC
strategija**, ne pasivni BTC. Ko BTC signal reče ven, gre tudi ta delež v
gotovino.

| | letno | Sharpe | Sortino | MaxDD |
|---|---|---|---|---|
| 3 leta, čaka v gotovini | 33 % | 1,33 | 2,12 | −15 % |
| 3 leta, čaka v BTC | 37 % | 1,37 | 2,19 | −16 % |
| 5 let, čaka v gotovini | 18 % | 0,81 | 1,22 | −30 % |
| 5 let, čaka v BTC | 21 % | **0,81** | 1,23 | **−34 %** |

Na treh letih pomaga, na petih pa se Sharpe **ne premakne**, padec pa se
poslabša za štiri točke. To ni izboljšava strategije, je odločitev o velikosti
BTC: ker je BTC že polovica knjige, ta poteg poveča koncentracijo na 60 % in
prinese tisto, kar večji delež BTC prinese, torej več donosa in več padca pri
istem razmerju.

### Isto na petih letih

Zadnja tri leta se začnejo po zlomu 2022 in so zato prijazno okno. Na petih
letih, torej od avgusta 2021, ista sestava in ista pravila:

| | letno | vol | Sharpe | Sortino | MaxDD |
|---|---|---|---|---|---|
| sestava 50/10/10/10/10/10 | 18 % | 24 % | 0,81 | 1,22 | −30 % |
| brez LINK, ostali alti na 12,5 % | 19 % | 24 % | 0,86 | 1,32 | −29 % |
| brez LINK, njegovih 10 % na BTC | 20 % | 25 % | **0,87** | **1,34** | −29 % |

Na obeh oknih velja isto: sestava je približno enaka samemu BTC, ne bistveno
boljša. Razlika med oknoma je velika, 1,32 proti 0,81, in je odvisna zgolj od
tega, ali je medvedji trg 2022 znotraj okna ali ne. To je treba povedati ob
vsaki predstavljeni številki.

### Vsako sredstvo posebej na petih letih

| | letno | vol | Sharpe | Sortino | MaxDD | v trgu |
|---|---|---|---|---|---|---|
| BTC | 23 % | 30 % | 0,85 | 1,35 | −31 % | 38 % |
| HYPE | 40 % | 62 % | 0,85 | 1,34 | −36 % | 50 % |
| ETH | 19 % | 37 % | 0,65 | 0,99 | −45 % | 30 % |
| BNB | 16 % | 35 % | 0,61 | 0,92 | −53 % | 36 % |
| SOL | 14 % | 30 % | 0,59 | 0,94 | −38 % | 12 % |
| **LINK** | **−5 %** | 46 % | **0,11** | **0,17** | **−62 %** | 20 % |

HYPE ima le eno leto zgodovine, zato njegovih 40 % ni primerljivih z ostalimi.

---

## Zakaj LINK ven

LINK sam, z našo strategijo, po osmih različnih začetkih, vsi do danes, ob
njem BTC za primerjavo:

| začetek | LINK letno | LINK Sharpe | BTC letno | BTC Sharpe |
|---|---|---|---|---|
| 2020-01 | 1 % | 0,33 | 38 % | 1,12 |
| 2020-08 | 4 % | 0,36 | 43 % | 1,21 |
| 2021-01 | 0 % | 0,30 | 28 % | 0,92 |
| 2021-08 | −5 % | 0,11 | 25 % | 0,90 |
| 2022-01 | 1 % | 0,22 | 25 % | 0,98 |
| 2023-01 | 1 % | 0,26 | 34 % | 1,14 |
| 2023-08 | 12 % | 0,46 | 31 % | 1,16 |
| 2024-01 | 11 % | 0,45 | 26 % | 1,04 |

Številke se z oknom močno premikajo, Sharpe od 0,11 do 0,46. Navesti eno samo
najslabšo bi bilo izbiranje, zato so tu vse.

Sklep pa se ne premakne: LINK v **nobenem** od osmih oken ne pride blizu BTC.
Njegov najboljši rezultat, 0,46, je slabši od najslabšega BTC, 0,90. Razmerje
je med dva- in osemkratnim. To je argument, ki ne visi na izbiri obdobja.

Najbolj zgovorna pa je cela zgodovina, od januarja 2020 do danes:

```
poslov               18
dni v trgu           22 %
kupi in drzi LINK    +425 %
strategija na LINK   +9 %
```

Strategija je od gibanja +425 % ujela **+9 %**. Ne gre za to, da bi LINK padal,
gre za to, da ga naša pravila na njem premetavajo.

Donos po letih, štiri od sedmih let negativna:

```
2020   +6,9 %
2021   -0,8 %
2022   -2,5 %
2023  -20,1 %
2024  +15,5 %
2025   -6,6 %
2026  +22,3 %
```

Kaj se zgodi s knjigo, če ga odstranimo:

| | 3 leta | 5 let |
|---|---|---|
| z LINK | 1,34 | 0,81 |
| brez LINK, ostali alti na 12,5 % | 1,38 | 0,86 |
| brez LINK, njegovih 10 % na BTC | **1,39** | **0,87** |

Izboljšanje na obeh oknih, v obeh različicah. Boljša je tista, kjer njegovih
10 % pripade BTC.
