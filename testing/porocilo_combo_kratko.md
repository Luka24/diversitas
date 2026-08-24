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

Moja ponovitev na istih pravilih, obdobje 25. 8. 2023 do 24. 8. 2026:

| | letno | vol | Sharpe | Sortino | MaxDD |
|---|---|---|---|---|---|
| top 5, stroški 10 bp | 10 % | 9 % | 1,14 | 1,74 | −9 % |
| top 10, stroški 10 bp | 6 % | 7 % | 0,96 | 1,44 | −8 % |
| top 5, stroški 30 bp | 9 % | 9 % | 0,99 | 1,50 | −10 % |
| top 10, stroški 30 bp | 5 % | 7 % | 0,77 | 1,14 | −10 % |

Zadnja tri leta so slabša od objavljenega obdobja: letno z 18 % na 9 do 10 %,
Sharpe s 1,57 na okoli 1,0. Padec ostaja majhen, pod 10 %.

Za primerjavo, isto obdobje ni, a naša strategija od 2021: na Lukovi sestavi
20 % letno pri Sharpu 0,89 in padcu −28 %, sam BTC 24 % pri 0,87 in −31 %.

## Dvoje, kar je treba vedeti ob teh številkah

**Stroški.** Njihova osnovna predpostavka je 10 bazičnih točk na stran. Mi
računamo 30. Tabela za BTC v članku, tista s Sharpom 1,58, je brez stroškov.

**Moj filter prometa je strožji od njihovega.** Oni merijo promet sešteto čez
vse borze prek CoinMarketCap, jaz samo na Coinbase. Zato filter prepusti le 6
do 23 sredstev namesto več deset, in moj top 20 je nepopolnjen, kar ga potisne
navzdol. Merodajni sta vrstici top 5 in top 10.

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
| sestava 50/10/10/10/10/10 | 132 % | 32 % | 23 % | **1,32** | 2,09 | **−15 %** |

Sestava se z BTC izenači po Sharpu in ga za las prekaša po padcu, zaostane pa
po donosu in po Sortinu. ETH sam je najslabši od treh.

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

Opomba glede okna: teh zadnjih treh let se začne po zlomu 2022, zato so
številke lepše od tistih na petletnem oknu od junija 2021, kjer je sestava dala
Sharpe 0,90 in padec −28 %, sam BTC pa 0,87 in −31 %. Na obeh oknih velja isto:
sestava je približno enaka samemu BTC, ne bistveno boljša.
