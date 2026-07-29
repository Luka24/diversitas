# Korak 1 — popis parametrov Lean in seznam za testiranje

_Zadnja osvežitev 2026-07-29 · zamrznjeni podatki Binance, ogrevanje izključeno,
vse neto 0,30 % na stran_

> **Kako brati ta dokument.** Del ugotovitev v §1 je bil izmerjen na celotnem
> vzorcu in je bil pozneje ob poštenem izvenvzorčnem testu **ovržen**. Kjer se to
> zgodi, je popravek zapisan v obliki citata pri tisti ugotovitvi, izvirno besedilo
> pa ostane — da je vidno, kaj smo mislili in zakaj je bilo narobe. Najnovejši
> povzetek je v §2.7 in §2.8.

Namen koraka ni bil izboljšati strategijo, ampak **vedeti, kaj vsak parameter
dejansko počne** — kateri so živi, kateri so konvencija, kateri ne naredijo nič.
Manj parametrov, ki jih smemo premikati, pomeni manj priložnosti za prilagajanje
preteklosti.

Izhodišče po Koraku 0 (odstranjen ER): **21 polj** v `LeanConfig`.

---

## 1. Popis

### 1.1 Živi — nosijo signal

| parameter | privzeto | kaj počne |
|---|---|---|
| `track_period` | 75 | okno za Kijun trackline: `(najvišji high + najnižji low) / 2` |
| `track_buf_pct` | 3,0 | **simetričen** mrtvi pas: vstop nad `+3 %`, izstop pod `−3 %` |
| `ma_med_len` | 50 | trendna MA — cena mora biti nad njo |
| `ma_long_len` | 200 | režimska MA — trda blokada pod njo ob padanju |
| `ma_slope` | 5 | koliko barov nazaj se meri naklon režimske MA |
| `track_slope_bars` | 10 | trackline mora rasti čez toliko barov (filter proti stranskemu gibanju) |
| `confirm_bars` | 3 | toliko zaporednih barov mora veljati `bull_condition` pred vstopom |
| `reentry_hold` | 15 | najmanj toliko barov med izstopom in naslednjim vstopom |
| `exit_grace_bars` | 3 | toliko barov pod tracklineom pred izstopom |
| `blowoff_dist_pct` | 25,0 | izstop, ko je cena toliko % nad tracklineom **in** RSI > 80 |
| `vol_shock_mul` | 1,5 | izstop, ko letna vol preseže 50-dnevno povprečje krat toliko **in** je cena pod TL |
| `vol_lookback` | 20 | okno za izračun volatilnosti |
| `rsi_len` | 14 | RSI za blow-off |
| `trading_days` | 365 | koledar za anualizacijo (252 za delnice) |

### 1.2 Konvencija — zamrznjeni, ne sweepamo jih

`rsi_len`, `vol_lookback`, `ma_slope`, `ma_med_len`, `ma_long_len` so standardne
vrednosti iz literature. Njihovo premikanje je prostostna stopnja brez teorije.

### 1.3 Inerten — deluje, a pri privzeti vrednosti nikoli ne zagrize

| parameter | privzeto | ugotovitev |
|---|---|---|
| `min_dist_entry_pct` | 0,0 | pri 0 je `dist_entry_ok` **matematično identičen** `above_tl` — razlika na 0 od 2401 barov, na obeh sredstvih |

**Zakaj sploh obstaja, če imamo že buffer:** buffer je simetričen in nastavlja
tudi izstop. Če hočeš z njim zaostriti vstop, hkrati zrahljaš izstop.
`min_dist_entry_pct` to razklopi — vpliva samo na vstop.

Dokaz, isti vstopni prag 5 %, trije različni izstopni pragovi:

| | vstop | izstop | CAGR | Sortino | MaxDD |
|---|---|---|---|---|---|
| BTC buf 3 + min 2 | 5 % | −3 % | 35,7 | 1,61 | −39,1 |
| BTC buf 5 + min 0 | 5 % | −5 % | 38,0 | 1,63 | −40,6 |
| BTC buf 1 + min 4 | 5 % | −1 % | 27,8 | 1,35 | −48,1 |
| ETH buf 3 + min 2 | 5 % | −3 % | 27,2 | 1,05 | −65,0 |
| ETH buf 5 + min 0 | 5 % | −5 % | 23,8 | 0,96 | −65,0 |
| ETH buf 1 + min 4 | 5 % | −1 % | 37,3 | 1,37 | **−40,7** |

**Zakaj kljub temu ne zagrize:** razdalja od trackline **na dan vstopa** je
mediano 16,8 % (BTC) in 21,3 % (ETH), najmanj 7,7 % oziroma 5,2 %. Nobenega
vstopa ni bilo pod 5 %. Anti-churn mehanika (`confirm_bars`, `track_slope_bars`)
cena potisne daleč mimo praga, preden se vstop sploh sproži.

**Odločitev: obdržati in zamrzniti pri 0.** Brisanje bi ustvarilo novo razhajanje
s Pine (`minDistEntry`, `diversitas_lean.pine:40`) — natanko tista napaka, ki smo
jo v Koraku 0 odpravljali.

### 1.4 Mrtvi v Pythonu, a živi v Pine — odprta odločitev

| parameter | privzeto | stanje |
|---|---|---|
| `use_vol_sizing` | True | v Pythonu se ne uporablja |
| `target_vol_pct` | 50,0 | v Pythonu se ne uporablja |

Pine (`:166-167`) računa `volScale = min(1, targetVol / annualVol)` in
`targetAlloc = 100 × volScale`. Python od odločitve o binarni alokaciji naprej
vedno javi 100 % ali 0 %.

**To ni kozmetika.** Delež dni, ko bi Pine javil manj kot 100 %:

| | mediana letne vol | delež dni z `volScale < 1` |
|---|---|---|
| BTC | 49 % | **48 %** |
| ETH | 67 % | **76 %** |

Učinek Pine formule pri privzetem `targetVol = 50` (cela zgodovina):

| | CAGR | Sortino | MaxDD | Ulcer | izpost. |
|---|---|---|---|---|---|
| BTC binarno | **33,9** | **1,55** | −39,8 | 19,9 | 43,5 |
| BTC vol-target 50 | 24,1 | 1,31 | **−37,9** | **19,1** | 39,1 |
| ETH binarno | 25,2 | 1,00 | −65,3 | 29,9 | 36,2 |
| ETH vol-target 50 | **26,3** | **1,29** | **−40,1** | **20,2** | 27,8 |

Na ETH zreže drawdown za 25 odstotnih točk **in** dvigne donos. Na BTC stane
donos brez sorazmerne koristi. Podrobna obravnava z odločilno kontrolo (ista
izpostavljenost, dosežena z navadno konstanto) je v §2.4.

**Odprto vprašanje:** ali naj Python sledi Pine (skaliranje po volatilnosti), ali
naj Pine sledi Pythonu (binarno). Ena od obeh strani se mora premakniti.

### 1.5 Speči — vklopljiva zastavica, privzeto izklopljena

| parameter | privzeto |
|---|---|
| `use_donchian` | False |
| `donchian_period` | 55 |
| `donchian_top_frac` | 0,75 |

**Kaj počne:** zahteva, da cena ob vstopu sedi v zgornji četrtini kanala med
najvišjo in najnižjo ceno zadnjih N dni.

**Zakaj je bil vključen:** commit `eb89558` po fazi »nove ideje« (5. 7. 2026).
`run_new_ideas.py` je poročal, da validacijski Calmar **monotono raste s periodo**
(20/34/55 → +0,27/+0,38/+0,52), in sklenil, da monotoni odziv pomeni pravi učinek
in ne curve-fit.

**Ta utemeljitev ne drži več.** Na popravljeni osnovi (brez ogrevanja, brez ER) je
odziv obraten in nemonotón:

| perioda | BTC Sortino | BTC MaxDD | ETH Sortino | ETH MaxDD |
|---|---|---|---|---|
| izklopljen | 1,55 | −39,8 | 1,00 | −65,3 |
| 20 | **1,72** | **−29,6** | **1,92** | **−42,3** |
| 34 | 1,50 | −39,8 | 1,17 | −65,3 |
| **55 (privzeta)** | 1,47 | −39,8 | 1,21 | −65,3 |
| 90 | 1,47 | −39,8 | 1,31 | −65,3 |

Zapisana privzeta perioda 55 je **slabša od izklopljenega** na BTC. Skeniranje
sosednjih vrednosti (§2.3) pokaže, da kratke periode na BTC tvorijo **plato**, ne
konice — kar je bilo v prvi različici tega dokumenta napačno zapisano.

**Odprto vprašanje:** odstraniti speči feature (in s tem doseči popolno Pine
skladnost) ali kratke periode pošteno testirati v nested walk-forwardu — glej §2.3.

### 1.6 Izračunani stolpci

| stolpec | stanje |
|---|---|
| `ma_long_falling` | živ — nosi `bear_regime` |
| `track_rising` | Pine ga uporablja za barvo trackline (`:173`); Python ga je računal in **ni uporabljal**, dashboard je barval po 10-barnem naklonu → **popravljeno 2026-07-27** |
| `ma_long_rising` | Pine ga uporablja za barvo 200 MA (`:175`); Python ga je računal, dashboard pa je isti izraz **pisal še enkrat** in pri tem trdo zakodiral 5 namesto `cfg.ma_slope` → **popravljeno 2026-07-27** |

Nobeden ni bil mrtev. Prvi je bil neuporabljen, drugi podvojen.

---

## 2. Seznam za pošteno testiranje

Vrstni red po pričakovani vrednosti, ne po enostavnosti.

### 2.1 Izstopna stran — najvišja prioriteta ⭐

**Ugotovitev, ki to utemeljuje:** na tveganje vpliva izključno izstopna stran.
Sprememba **vstopnega** praga s 3 na 5 % ne premakne MaxDD niti za desetinko
odstotne točke. Sprememba **izstopnega** praga z −3 na −1 % ga na ETH premakne s
−65,0 na −40,7 %.

Isto so pokazale tri neodvisne meritve:

1. MaxDD je bil **identičen pri vseh vstopnih variantah** — ER vklopljen/izklopljen,
   Donchian 20/34/55 — na BTC vedno −39,1 %.
2. Najhujši drawdown BTC (−39,1 %, november 2021 → marec 2023) je nastal ob
   povprečni izpostavljenosti 21 %. Ni prišel iz prevelike izpostavljenosti, ampak
   iz **zamude izstopa** na cikličnem vrhu.
3. Sprememba `exit_grace_bars` premakne MaxDD, sprememba vstopnih filtrov ne.

> **Popravek 2026-07-29.** Točki 1 in 2 zdržita. Smer pri `exit_grace_bars` pa se je
> ob poštenem testu **obrnila**, in to trikrat zapored: na celotnem vzorcu je
> skrajšanje s 3 na 1 izgledalo boljše, izven vzorca na petih sredstvih je bilo
> slabše na štirih, na BTC pod polnim protokolom pa je edina sprememba, katere
> interval **ne zajema ničle** — Sortino 1,22 → 0,70, MaxDD −39,8 → −49,6 %,
> interval [−1,23, −0,01]. **Tri-barna potrpežljivost pred izstopom je torej
> potrebna, ne odveč.** Izstopna stran ostaja prava smer za raziskovanje; ta
> konkretni parameter pa ni kandidat za spremembo, ampak edina komponenta z dokazom.

**Kaj testirati:** `track_buf_pct` (izstopna stran) in `blowoff_dist_pct` kot
izstopna vzvoda. `exit_grace_bars` je iz tega seznama umaknjen — glej popravek zgoraj.

**Kako:** obvezno **nested walk-forward** (izbira samo iz train dela). Vrednosti,
najdene na celotnem vzorcu, so brez vrednosti — to je pokazal `aggressive_nested_btc.md`,
kjer je prednost 1,62 → 1,92 ob pošteni izbiri padla na Δ 0,00.

**Vnaprej zapisan MDE:** parni block bootstrap daje širino intervala okoli
±0,4 do ±0,6 Sortino točke. Karkoli manjšega od tega ni dokazljivo in se ne
sprejme, ne glede na to, kako lepo izgleda v backtestu.

### 2.2 Občutljivost na zamik in ceno izvedbe ⭐ *(dodano 2026-07-27)*

**Ugotovitev, ki to utemeljuje:** primerjava dveh cenovnih virov je pokazala, da
**0,1 % šuma v vhodnih cenah premakne CAGR za 3 odstotne točke** (Binance 33,92 %
proti Yahoo 37,01 % na istem obdobju, isti kodi, istih stroških).

Vzrok ni v podatkih, ampak v strategiji: vstopni pogoj je **prag**
(`cena > trackline × 1,03`), torej binarna odločitev na zvezni spremenljivki. Ko
cena leži tik ob pragu, desetinka odstotka odloči, ali se posel sproži tisti dan,
tri dni kasneje ali sploh ne — in ker posli trajajo povprečno 60 dni, ena taka
odločitev odnese krivuljo kapitala za mesece narazen.

Konkretno na BTC: posel maja 2020 se na Binance zapre 10. 9. z **+10,2 %**, na
Yahoo pa isti posel teče naprej do 17. 11. in se zapre z **+88,2 %**. En prag,
78 odstotnih točk razlike.

To je lastnost, ki jo je treba izmeriti **pred živim trgovanjem**, ker je v
resničnem izvajanju ta negotovost vedno prisotna: signal nastane na zaključku
dneva, posel se sklene naslednji dan ob neki drugi ceni.

**Kaj testirati:**

| scenarij | kako |
|---|---|
| zamik izvedbe | izvedi na +1, +2, +3 dni namesto naslednji dan |
| ura izvedbe | izvedi po open, po VWAP, po close naslednjega dne (rabi urne podatke) |
| šum v ceni | dodaj ±0,05 / ±0,1 / ±0,25 % naključnega šuma ceni, 500 ponovitev, poglej porazdelitev CAGR in MaxDD |
| zamujen prag | kaj če se vstop sproži šele, ko je cena 0,25 % nad pragom |
| cross-venue | isti test na Binance, Coinbase in Yahoo kot tri neodvisne realizacije |

**Sprejemni kriterij:** razpon CAGR pri ±0,1 % šuma naj ne presega MDE
(±0,4 do 0,6 Sortino točke). Če ga presega — kar zaenkrat kaže, da ga —
je strategija **prekomerno občutljiva na izvedbo** in to je treba
poročati kot lastnost izdelka, ne skriti za eno številko.

**Zakaj je to pomembnejše od tuninga:** vse doslejšnje izboljšave, ki smo jih
merili, so bile manjše od te občutljivosti. Nima smisla iskati +0,1 Sortino
točke, dokler izbira borze premakne rezultat za 0,1.

### 2.3 Donchian — kratke periode ⭐ *(razširjeno 2026-07-29)*

**Kaj je:** pogledaš najvišjo in najnižjo ceno zadnjih N dni (»kanal«) in zahtevaš,
da je cena ob vstopu v zgornji četrtini tega kanala. Kupuješ torej ob preboju
navzgor, ne kjer koli sredi razpona.

```
kje v kanalu = (cena − najnižji low N dni) ÷ (najvišji high N dni − najnižji low N dni)
vstop dovoljen, če je > 0,75
```

Primer, BTC 19. 3. 2024: cena 61.937, zadnjih dvajset dni razpon 59.005–73.777,
torej **20 % od dna kanala** — kupovala bi po padcu s 73.777, ne ob preboju.
Donchian(20) tak vstop zavrne. Od sedemnajstih vstopov na BTC bi jih zavrnil štiri.

**Popravek prejšnje ocene.** V prvi različici tega dokumenta je pisalo, da je
perioda 20 »osamljena konica«. **To ne drži.** Skeniranje sosednjih vrednosti
(Sortino, čist Binance, neto 0,30 %/stran):

| perioda | 12 | 15 | 18 | **20** | 22 | 25 | 30 | 55 (privzeta) |
|---|---|---|---|---|---|---|---|---|
| BTC | 1,76 | 1,72 | 1,72 | **1,72** | 1,70 | 1,64 | 1,36 | 1,47 |
| ETH | 1,64 | 1,84 | 1,92 | **1,92** | **1,20** | 1,18 | 1,17 | 1,21 |

Na **BTC je to plato** od 12 do 22 — natanko oblika, ki jo metodologija projekta
šteje za robustno, in 20 sploh ni rob. Na **ETH je plato 15–20, nato prepad**
(1,92 → 1,20 med 20 in 22); tak skok pomeni, da se prevrne en sam posel, in temu
ne gre zaupati.

Za primerjavo izklopljeno stanje: BTC Sortino 1,55, ETH 1,00.

**Zakaj je bil sploh vključen:** commit `eb89558` na podlagi ugotovitve, da
validacijski Calmar **monotono raste s periodo** (20/34/55 → +0,27/+0,38/+0,52).
Na popravljenih podatkih je odziv **obraten** — pada s periodo. Prvotna
utemeljitev je torej ovržena, kar pa ne pomeni, da je učinek pri kratkih periodah
ničeln; pomeni le, da o njem ne vemo nič zanesljivega.

**Kaj testirati:** `donchian_period` v razponu 10–30 (tam je plato), pod nested
walk-forwardom, z izbiro periode **samo iz train dela**. Če prednost preživi,
vklopimo; če izpuhti kot pri agresivnem tuningu (1,62 → 1,92 → Δ 0,00), feature
odstranimo dokončno in bomo imeli za to dokaz.

**Ne glede na izid testa:** privzeto `donchian_period = 55` je treba popraviti ali
odstraniti. Leži v najslabšem območju in bi vsakogar, ki zastavico vklopi,
zavedla — na BTC je slabša od izklopljenega (1,47 proti 1,55).

### 2.4 Vol-sizing — najprej uskladitev, šele nato test

Glej §1.5. Samo pod nested walk-forwardom; sicer odstraniti.

### 2.5 Blow-off izstop — ugotovitev iz Koraka 5 je bila ovržena

Ablacija je pokazala, da izklop blow-off izstopa (`blowoff_dist_pct = 999`)
**izboljša donos na obeh sredstvih in ne poslabša drawdowna**:

| | CAGR | Sortino | MaxDD | DD-gap |
|---|---|---|---|---|
| BTC cel Lean | 30,9 | 1,43 | −38,9 | 37,7 |
| BTC brez blow-offa | **40,0** | **1,64** | −38,9 | 37,7 |
| ETH cel Lean | 35,8 | 1,39 | −40,9 | 38,4 |
| ETH brez blow-offa | **67,3** | **2,02** | −40,9 | 38,4 |

Blow-off izstop torej **proda pred vrhom in ne kupi nič pri tveganju** — DD-gap se
ne premakne niti za desetinko. Na ETH stane 31 odstotnih točk CAGR.

> **Popravek 2026-07-29 — zgornja ugotovitev NE zdrži.** Tabela je bila merjena na
> celotnem vzorcu. Ob merjenju izven vzorca se sesuje:
>
> | | BTC | ETH | XRP | BNB | ADA | poolan CI ΔSortino |
> |---|---|---|---|---|---|---|
> | izklop blow-offa | −0,12 | +0,01 | +0,63 | −0,06 | +0,60 | [−0,05, +0,54] |
>
> Dve sredstvi škoda, dve korist, interval čez ničlo. Na BTC pod polnim protokolom
> izklop Sortino celo **poslabša** (1,22 → 1,10). Torej: blow-off **ni dokazano
> škodljiv**, in moje priporočilo za odstranitev je bilo napačno. Ostane nedokazan,
> tako kot skoraj vse ostalo.
>
> Poučno je, zakaj sem se zmotil: ugotovitev je bila konsistentna čez obe sredstvi
> in imela je prepričljiv mehanizem. Oboje se je zdelo dovolj. Ni bilo — merjena je
> bila na podatkih, na katerih so bili privzetki nastavljeni.

**Kaj testirati, če se kdaj vrnemo:** `blowoff_dist_pct` in RSI prag pod nested
walk-forwardom. Zaenkrat **ne spreminjati ničesar**.

### 2.6 Vol-shock izstop — na BTC dokazljivo mrtev

| | CAGR | Sortino | MaxDD |
|---|---|---|---|
| BTC cel Lean | 30,9 | 1,43 | −38,9 |
| BTC brez vol-shocka | 30,9 | 1,43 | −38,9 |
| ETH cel Lean | 35,8 | 1,39 | −40,9 |
| ETH brez vol-shocka | **18,4** | **0,83** | **−62,7** |

Na BTC je **popolnoma brez učinka** — številke so identične do decimalke. Na ETH
je **bistven**: brez njega drawdown pade s −40,9 na −62,7 %.

To je pomembno, ker je ravno obratno od blow-offa. Dve izstopni pravili, eno je
odveč na BTC in nujno na ETH, drugo škodi na obeh.

> **Popravek 2026-07-29.** Odvisnost na ETH je bila prav tako artefakt celotnega
> vzorca. Izven vzorca je učinek izklopa na ETH **točno 0,00**, na vseh petih
> sredstvih pa v razponu 0,00 do 0,08. Sweep na BTC potrdi isto z druge strani:
> `vol_shock_mul` premakne Sortino za **0,02 čez celoten razpon od 1,2 do 3,0**.
>
> **Vol-shock je na BTC dokazljivo mrtev** — ne le pri privzeti vrednosti, ampak pri
> vseh. Odvisnost na ETH izvira iz obdobja pred julijem 2021.

**Kaj narediti:** kandidat za odstranitev, a šele po preverbi na sredstvih, ki jih
nismo uporabljali za nastavljanje.


### 2.7 Zemljevid parametrov — kaj sploh smemo premikati *(2026-07-29)*

Vseh štirinajst nastavljivih parametrov je bilo prečesanih posamično čez razpon
vsaj ±25 % okoli privzete vrednosti, ostali pri miru, merjeno **izven vzorca** in
neto 0,30 % na stran. Poln zapis z grafom za vsak parameter:
`testing/porocilo_parametri_BTC.html`.

| razvrstitev | parametri | pomen |
|---|---|---|
| **plato** | `track_period`, `track_buf_pct`, `ma_slope`, `track_slope_bars` | okolica privzete vrednosti je ravna — nastavitev ni kritična |
| **ostra konica** | `ma_long_len`, `confirm_bars`, `reentry_hold`, `exit_grace_bars`, `blowoff_dist_pct` | sosednja vrednost opazno pade |
| **inerten** | `ma_med_len`, `rsi_len`, `vol_shock_mul`, `vol_lookback`, `min_dist_entry_pct` | parameter skoraj nič ne spremeni |

**Dobra novica:** jedro strategije — dolžina trackline in mrtvi pas — je na platoju.

**Slaba novica, ki jo je treba povedati na glas:** **štirje od petih parametrov z
ostro konico imajo vrh natanko na privzeti vrednosti** — `ma_long_len` pri 200,
`reentry_hold` pri 15, `exit_grace_bars` pri 3, `blowoff_dist_pct` pri 25.

To ni razlog za veselje. Privzetki prihajajo iz Pine skripte, ki je bila napisana ob
gledanju zgodovine bitcoina. Da so štirje hkrati na lokalnem vrhu z ostrim padcem ob
strani, je bolj skladno s tem, da so bili nekoč nastavljeni na te podatke, kot s
srečnim naključjem. **Iz enega sredstva tega ni mogoče ločiti** — potrebna bi bila
sredstva, ki na nastavitev niso mogla vplivati.

### 2.8 Kje strategija stoji po vseh testih *(2026-07-29)*

| test | rezultat | branje |
|---|---|---|
| permutacija, popolnoma premešan trg | p = 0,032 | **edge obstaja** proti čistemu naključju |
| permutacija, 20-dnevni bloki | p = 0,081 | edge **izgine**, ko ohranimo večtedenski moment |
| White's Reality Check (13 nastavitev) | p = 0,911 | po donosu ne premaga kupi-in-drži |
| PBO s purgom in embargom | 0,694 | izbiranje najboljše nastavitve je pretežno šum |
| deflated Sharpe (10 poskusov) | p = 0,075 | najboljša varianta ni značilna pri 5 % |

Skupaj: strategija **lovi moment na lestvici nekaj tednov**, kar je znan tržni pojav,
in ne dosti več. Na povsem naključnem trgu doseže povprečen Sortino **+0,61** —
precejšen del videza uspešnosti pride že iz tega, da bitcoin dolgoročno raste.

**Strukturna omejitev, ki je z več računanja ni mogoče odpraviti:** literatura za
zanesljivo oceno priporoča 100 do 200 poslov čez več režimov. Lean jih ima v šestih
letih in pol **sedemnajst**. Vsi testi tu merijo na robu svoje moči — zaznati je
mogoče šele razliko okoli pol Sortino točke, kar je več, kot znaša katerakoli
obravnavana izboljšava.

### 2.9 Česa NE testiramo

- vstopnih filtrov — dokazano ne premaknejo primarnega KPI;
- novih indikatorjev (ATR buffer, SuperTrend, dinamični trailing) — vsi so že
  padli na čisti leakage-safe selekciji;
- konvencijskih parametrov iz §1.2.

---

## 3. Kaj je bilo v tem koraku spremenjeno v kodi

| datoteka | sprememba |
|---|---|
| `lean/diversitas/dashboard.py` | trackline se barva po `track_rising` (1 bar) kot v Pine, ne po 10-barnem naklonu |
| `lean/diversitas/dashboard.py` | 200 MA uporabi obstoječi `ma_long_rising` namesto podvojenega izraza s trdo zakodirano 5 |

Nobenega parametra nismo izbrisali. Signal je nespremenjen.
