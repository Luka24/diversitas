# Korak 1 — popis parametrov Lean in seznam za testiranje

_2026-07-27 · BTC in ETH · zamrznjeni podatki, ogrevanje izključeno_

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
| BTC binarno | **36,0** | **1,61** | −39,1 | 19,4 | 43,4 |
| BTC vol-target 50 | 26,5 | 1,40 | **−37,0** | **18,4** | 39,1 |
| ETH binarno | 27,2 | 1,05 | −65,0 | 29,4 | 36,2 |
| ETH vol-target 50 | **28,7** | **1,38** | **−39,7** | **19,4** | 27,8 |

Na ETH zreže drawdown za 25 odstotnih točk **in** dvigne donos. Na BTC stane
donos za skromen prihranek pri tveganju.

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
| izklopljen | 1,61 | −39,1 | 1,05 | −65,0 |
| 20 | **1,79** | **−29,1** | **1,97** | **−41,6** |
| 34 | 1,56 | −39,1 | 1,21 | −65,0 |
| **55 (privzeta)** | 1,54 | −39,1 | 1,25 | −65,0 |
| 90 | 1,54 | −39,1 | 1,35 | −65,0 |

Zapisana privzeta perioda 55 je **slabša od izklopljenega** na obeh sredstvih.
Perioda 20 je opazno boljša na obeh, a je rob testiranega razpona in osamljena
konica — natanko vzorec, pred katerim je kampanja sama svarila.

**Odprto vprašanje:** odstraniti speči feature (in s tem doseči popolno Pine
skladnost) ali periodo 20 pošteno testirati v nested walk-forwardu.

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

**Kaj testirati:** `track_buf_pct` (izstopna stran), `exit_grace_bars`,
`blowoff_dist_pct` — kot izstopne vzvode, ne kot vstopne.

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

### 2.3 Vol-sizing — odločitev, ne test

Glej §1.4. Ni vprašanje meritve, ampak vprašanje, katera specifikacija velja.

### 2.4 Donchian perioda 20

Glej §1.5. Samo pod nested walk-forwardom; sicer odstraniti.

### 2.5 Česa NE testiramo

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
