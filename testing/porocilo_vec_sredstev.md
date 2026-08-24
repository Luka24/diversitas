# BTC plus pet altcoinov: kaj je bilo izmerjeno

Vprašanje: ali se splača razširiti strategijo z BTC na šest sredstev, BTC 50 %
in pet altcoinov po 10 %, z ločenim naborom pravil za alte in z vstopi ter
izstopi po posameznem sredstvu.

Vse meritve so na dnevnih svečah, stroški 0,30 % na stran, torej 0,60 % na cel
obrat. Sortino je koren povprečja kvadratov negativnih dni čez vse dni, krat
koren iz 365.

---

## 1. Podatki: dve sredstvi je bilo treba najprej sploh dobiti

Strategija porabi prvih 220 barov za ogrevanje, ker gleda 200-dnevno povprečje.
Šele nato da prvi signal.

| sredstvo | vir | prvi bar | uporabnih dni |
|---|---|---|---|
| BTC | Coinbase | 2015-09-12 | 3801 |
| ETH | Coinbase | 2016-05-18 | 3550 |
| LINK | Coinbase | 2019-06-27 | 2417 |
| SOL | Coinbase | 2021-06-17 | 1696 |
| HYPE | **Hyperliquid** | 2024-12-05 | 429 |
| BNB | Coinbase | 2025-10-22 | 108 |

HYPE je bil sprva razglašen za nemogočega, ker ima Coinbase le 198 barov,
Kraken 205, Binance pa ga sploh nima. To je bila napaka v iskanju, ne v
podatkih. Hyperliquid ima lastno borzo in lasten API, tam je HYPE od 5. 12.
2024, kar je 627 barov.

Preverjeno proti Coinbase na 200 skupnih dneh: povprečna razlika cene 0,052 %.
Preverjeno proti trem drugim borzam na zadnji ceni: Coinbase, Bybit in OKX vsi
znotraj 0,05 %.

**Past, ki jo je treba poznati:** Yahoo pod oznako `HYPE-USD` ponuja drug,
mrtev token iz leta 2021 z razponom 0,000002 do 5,78 in zadnjo ceno 0,0000.
Zato HYPE v nastavitvah namerno nima ključa za Yahoo.

BNB s 108 uporabnimi dnevi ostaja prešibak za kakršenkoli sklep.

---

## 2. Osnovna meritev: sestava izgubi proti samemu BTC

Okno 2022-01 do 2026-08, ker prej ni SOL:

| | Sortino | letno | najhujši padec |
|---|---|---|---|
| **sam BTC, 100 %** | **1,616** | 23,9 % | −23,3 % |
| sam BTC, 50 %, ostalo gotovina | 1,497 | 14,2 % | −13,6 % |
| BTC 50 + ETH/SOL/LINK 10, ista pravila | 1,385 | 16,3 % | −17,8 % |
| BTC 50 + ETH/SOL/LINK 10, ločena pravila za alte | 1,443 | 17,2 % | −19,3 % |

Daljše okno 2020-01 do 2026-08, brez SOL:

| | Sortino | letno | najhujši padec |
|---|---|---|---|
| **sam BTC, 100 %** | **1,799** | 37,5 % | −30,7 % |
| sam BTC, 50 %, ostalo gotovina | 1,680 | 26,0 % | −24,7 % |
| BTC 50 + ETH 10 + LINK 10 | 1,661 | 31,9 % | **−36,5 %** |

### Zakaj

Sredstva so slabša vsako zase: BTC 1,616, ETH 0,970, SOL 0,854, LINK 0,310, kar
je −0,2 % na leto.

Kapital večino časa leži: SOL je v trgu 12,4 % dni, LINK 20,9 %.

Korelacije med sredstvi so 0,70 do 0,84, torej to ni razpršitev, ampak vzvod na
isto stavo. Znano je tudi, da korelacija altcoinov do BTC naraste prav med
padci, kar pomeni, da razpršitev odpove takrat, ko bi jo najbolj potreboval.

### Kar utež ni kriva

Razčlenitev po prispevku k tveganju pokaže, da je razdelitev 50/10/10/10/10 že
skoraj uravnotežena, ker so altcoinski rokavi večino časa zunaj trga:

| | letna nihajnost | delež kapitala | delež tveganja |
|---|---|---|---|
| BTC | 63 % | 50 % | 56 % |
| ETH | 84 % | 10 % | 13 % |
| SOL | 98 % | 10 % | 8 % |
| BNB | 94 % | 10 % | 10 % |
| LINK | 104 % | 10 % | 12 % |

---

## 3. Preizkus: več Donchian dolžin namesto ene

Utemeljitev: strategija naredi dva do tri posle na leto, kar je premalo, da bi
ujela obrate na sredstvih, ki se gibljejo hitreje od BTC.

Izvedba: ne en signal z več pragovi, ampak več ločenih modelov, vsak s svojim
avtomatom stanj, potrjevanjem in premorom, na koncu se drži povprečje njihovih
pozicij.

```python
def model(raw, dolzine):
    P, T, idx = [], [], None
    for d in dolzine:
        cfg = replace(base, donchian_period=d)
        df = trim_warmup(run_strategy(raw, config=cfg).df)
        idx = df.index if idx is None else idx.intersection(df.index)
        P.append(position(df, cfg))
        T.append(traded_fraction(df, cfg))
    pos = sum(p.reindex(idx) for p in P) / len(P)
    trd = sum(t.reindex(idx).fillna(0) for t in T) / len(T)
    return pos, trd
```

Pogoj za sprejem je bil zapisan vnaprej: izboljšanje na BTC **in** ETH hkrati.

| BTC | Sortino | | ETH | Sortino |
|---|---|---|---|---|
| ena, 20 | **2,232** | | ena, 20 | **2,097** |
| 10+20+40 | 2,198 | | 10+20+40 | 1,733 |
| 20+55+100 | 2,162 | | 20+55+100 | 1,712 |

**Pade na obeh, torej zavrnjeno.**

Dve stvari sta se pri tem izkazali za pomembnejši od samega rezultata.

**Utemeljitev je bila napačna.** Število poslov se ne spremeni: HYPE ostane pri
treh, SOL pri desetih, BNB pri nič. Povprečenje modelov ustvari delne pozicije,
ne več poslov. Pogostost poganjajo potrjevanje treh dni, premor petnajstih dni
in vstopni pogoji, ne dolžina kanala.

**Na altih pomaga, na čistih sredstvih škodi.** HYPE 1,266 na 1,402, SOL 0,861
na 1,073. To je natanko slika, ki nastane pri izbiri zmagovalca za nazaj, in pri
treh do desetih poslih na sredstvo je to skoraj gotovo šum.

---

## 4. Preizkus: pravilo za izbiro sredstev namesto seznama

### Pravilo, korak za korakom

Vsakega **1. januarja in 1. julija**:

1. Za vsako sredstvo izračunaj **dnevni promet v dolarjih** = volumen krat
   zaključna cena.
2. Vzemi zadnjih **90 dni** in izračunaj **mediano**, ne povprečja.
3. Sredstvo mora imeti **vsaj 90 dni zgodovine**, sicer ni upravičeno.
4. Razvrsti padajoče, vzemi **prvih pet**. BTC je izven razvrstitve, ker ima
   fiksnih 50 %.
5. **Blažilec 10 %:** sredstvo, ki je že v knjigi in je padlo s petega mesta,
   ostane, če je znotraj 10 % petouvrščenega.
6. Ob obnovi se rokavi izpadlih sredstev prodajo in kapital preseli na nova,
   obračunano po 0,30 % na stran.

### Zakaj tako, in od kod je vsaka odločitev

Nobena od teh številk ni izmišljena. Vsaka posnema, kar delajo ponudniki
kripto indeksov, ker so ti edini, ki izbiro sredstev opravljajo javno in
zapisano.

| odločitev | od kod |
|---|---|
| rang po prometu | CoinDesk 20 rangira po **90-dnevnem medianem dnevnem prometu** |
| mediana namesto povprečja | en sam dan z ogromnim prometom, na primer ob uvrstitvi na borzo, ne sme potegniti sredstva v izbor |
| 90 dni | ista dolžina kot pri CoinDesk; S&P uporablja trimesečni mediani promet nad 100.000 USD |
| pogoj zgodovine | Bitwise zahteva 30 dni cene nad 0,01 USD in promet nad 1 % lastne vrednosti v 30 dneh |
| blažilec | Bitwise zamenja sredstvo le, če ga izzivalec prekaša **pet dni zapored**; namen je preprečiti nenehno menjavanje na robu |
| obnova po urniku | vsi trije ponudniki obnavljajo po koledarju, ne po presoji |
| strop na utež | CoinDesk 20 omeji največje sredstvo na **30 %**, ostala na 20 %; naših 10 % na alt ima isti namen |

**Pomembna omejitev tega prenosa:** to so **indeksi**, ki kupijo in držijo.
Nikoli ne prodajo zaradi preloma trenda. Zato je za nas uporabno samo pravilo,
katera sredstva sploh pridejo v poštev. Njihove uteži in urnik obnove rešujeta
sledenje trgu, kar ni naš cilj, in bi našemu trend sistemu škodila.

### Kaj bi pravilo izbralo

| datum | izbor | ujemanje s seznamom ETH/SOL/HYPE/LINK/BNB |
|---|---|---|
| 2021-01 | ETH LINK LTC UNI BCH | 2 od 5 |
| 2021-07 | ETH ADA MATIC LTC LINK | 2 od 5 |
| 2022-01 | ETH SOL ADA MATIC AVAX | 2 od 5 |
| 2023-01 | ETH DOGE SOL MATIC ADA | 2 od 5 |
| 2024-01 | ETH SOL LINK XRP AVAX | 3 od 5 |
| 2025-01 | ETH XRP DOGE SOL SUI | 2 od 5 |
| 2025-07 | ETH HYPE SOL XRP SUI | 3 od 5 |

Praviloma dva od petih. Stalna sta samo ETH in SOL. Pravilo bi silo držati LTC,
BCH, UNI, ADA, MATIC in DOGE. BNB se ne pojavi nikoli, ker ga Coinbase do
oktobra 2025 ni imel.

### Rezultat, okno 2021-01 do 2026-08, 2062 dni

| | Sortino | letno | najhujši padec |
|---|---|---|---|
| **sam BTC, 100 %** | **1,459** | 27,3 % | −30,7 % |
| **sam BTC, 50 %, ostalo gotovina** | **1,459** | 14,4 % | −16,0 % |
| fiksni seznam petih, izbran za nazaj | 1,101 | 16,0 % | −28,2 % |
| A: top 5 po **prometu** | 0,976 | 15,8 % | −34,4 % |
| B: top 5 po **donosu zadnjih 12 mesecev** | 0,725 | 10,0 % | −29,9 % |
| C: top 5 po **Sortinu strategije 12 mesecev** | 0,644 | 8,9 % | −38,0 % |

### Ugovor "indeks hoče velike, jaz hočem profitabilne"

Ugovor je upravičen kot kritika pravila A, ker promet res ne napoveduje donosa.
Zato sta bili preizkušeni še dve pravili, ki iščeta prav donosnost. Obe sta
**slabši**.

Razlog je viden iz izbora: pravilo po donosu januarja 2025 naloži SUI, XRP,
DOGE, XLM in HBAR, torej natanko tisto, kar je zraslo konec 2024. Kupuješ
lanske zmagovalce po tem, ko so zrasli. Trend strategija je že sama momentum,
in izbira po momentumu na vrhu momentuma da dvojno zamudo, ne dvojne koristi.

Promet je boljši prav zato, ker ničesar ne lovi. Pove le, ali je sredstvo dovolj
resno za trgovanje, časovno odločitev pa v celoti prepusti strategiji.

### Kaj to pove o seznamu

Fiksni seznam s 1,101 prekaša najboljše zapisljivo pravilo z 0,976. Razlika
**0,125 Sortina** ni znak dobre presoje, ampak mera prednosti za nazaj, ki je
naprej ni mogoče ponoviti.

Ta ocena je še optimistična. Nabor kandidatov so sredstva, ki jih Coinbase
**danes** ima. Tistih, ki so medtem umrla in bila umaknjena, v izračunu ni.

---

## 5. Sklep

Na vsakem preizkušenem oknu in pri vsaki preizkušeni sestavi je **sam BTC
boljši** od knjige s petimi altcoini.

Najbolj neprijetna posamezna vrstica: BTC pri **polovični velikosti**, z drugo
polovico v gotovini, da skoraj enak letni donos kot celotna petsredstvena
knjiga, 14,4 % proti 16,0 %, pri skoraj polovičnem padcu, −16,0 % proti
−28,2 %. Vseh pet altcoinov skupaj torej ne prispeva ničesar, česar ne bi
dosegel z gotovino.

Če je cilj najboljše razmerje med donosom in tveganjem, je odgovor sam BTC, po
potrebi pri manjši velikosti.

Če je cilj produkt s šestimi sredstvi, kar je legitimen poslovni razlog, potem
je najboljša izmerjena izvedba ta: BTC 50 %, alti po 10 % s stropom, LINK
izpuščen, izbira po pravilu iz razdelka 4 in ne po seznamu, ter zavedanje, da
bo rezultat verjetno okoli 0,12 Sortina slabši od tega, kar kaže backtest s
seznamom.

### Kaj ni bilo preizkušeno in bi bilo naslednje

Kombinacija hitrosti je bila preizkušena v preprosti obliki, torej kot
povprečje binarnih modelov. Profesionalna izvedba je drugačna in bi jo bilo
pošteno preizkusiti, preden se ideja dokončno zavrže: napoved se izračuna kot
razlika dveh eksponentnih povprečij, **deljena z volatilnostjo**, pomnožena s
faktorjem, da je povprečna absolutna vrednost 10, in **omejena na ±20**, šele
nato se napovedi različnih hitrosti seštejejo z utežmi in množiteljem
razpršitve. To je zvezna napoved, ne povprečje vklopov in izklopov, in je lahko
bistvena razlika.

---

## Viri

Kripto trend s Donchianom, edini najden članek, ki rešuje isti problem:

- Zarattini, Pagani, Barbon, *Catching Crypto Trends: A Tactical Approach for
  Bitcoin and Altcoins*, 8. 4. 2025.
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5209907
  Poroča Sharpe nad 1,5 in 10,8 % letne nadpovprečnosti nad Bitcoinom na
  rotacijskem portfelju dvajsetih najbolj likvidnih, na bazi brez preživetvene
  pristranskosti od 2015. Uporablja kombinacijo Donchian dolžin in velikost
  pozicije po volatilnosti. **Kode ne objavlja.** Točnih dolžin, ciljne
  volatilnosti in pogostosti rotacije iz javnih povzetkov ni mogoče izvedeti.

Profesionalna izvedba kombinacije hitrosti, z odprto kodo:

- `pysystemtrade` Roba Carverja, bivšega upravljavca pri AHL (Man Group).
  https://github.com/robcarver17/pysystemtrade
  https://github.com/robcarver17/systematictradingexamples/blob/master/ewmac.py
  Napoved deljena z volatilnostjo (25-dnevna), skalirana na povprečno absolutno
  vrednost 10, omejena na ±20, hitrosti sestavljene z utežmi in množiteljem
  razpršitve, pozicija skalirana na ciljno volatilnost.

Ali kombinacija hitrosti sploh pomaga, obe strani:

- Graham Capital, *Trend-Following Primer*: kombinacija 1, 3, 6 in 12 mesecev
  je pri velikih upravljavcih standard.
  https://www.grahamcapital.com/blog/trend-following-primer/
- *Revisiting the Structure of Trend Premia: When Diversification Hides
  Redundancy*, oktober 2025: hitrosti so večinoma odvečne, zadostita ena ali
  dve. https://arxiv.org/pdf/2510.23150

Pravila za izbiro sredstev:

- CoinDesk 20 Index Methodology, rang po 90-dnevnem medianem prometu, strop
  30 % na največje sredstvo.
  https://downloads.coindesk.com/cd3/CDI/CoinDesk-20-Index-Methodology.pdf
- Bitwise Crypto Asset Index Methodology, promet nad 1 % lastne vrednosti v 30
  dneh, mesečna obnova, blažilec pet zaporednih dni.
  https://bitwiseinvestments.com/indexes/methodologies/bitwise-crypto-asset-index-methodology
- S&P Digital Assets Indices Methodology, trimesečni mediani promet nad
  100.000 USD, vsaj dva skrbnika.
  https://www.spglobal.com/spdji/en/documents/methodologies/methodology-sp-digital-assets-indices.pdf

Korelacije v padcih:

- Coinbase Institutional, *Crypto's role in portfolio diversification*.
  https://www.coinbase.com/institutional/research-insights/research/market-intelligence/cryptos-role-in-portfolio-diversification

Skripte, s katerimi so bile te številke izračunane, so v
`testing/scripts/`, podatki za HYPE pa se berejo prek novega vira
`hyperliquid` v `shared/data_source.py`.
