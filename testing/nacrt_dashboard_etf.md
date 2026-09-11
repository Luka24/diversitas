# Dashboard ETF: kaj je narejeno in kaj sledi

Stanje 2. septembra 2026.

```bash
streamlit run testing/dashboard_etf.py
python testing/scripts/preveri_dashboard_etf.py      # 11 preverb, vse OK
```

---

## Del 1: kaj je narejeno

Stran `testing/dashboard_etf.py` je enaka `dashboard_sestava.py`, samo za obe
kombinaciji ETF. Isti račun, isti zavihki, isti način vodenja denarja: vsaka
naložba je znesek, ki raste in se manjša, provizije se odbijejo od zneska,
metrike se izračunajo šele iz poti skupne vrednosti.

| kripto stran | ETF stran |
|---|---|
| BTC 50 %, ETH/SOL/LINK/BNB/HYPE po 10 % | Portfelj 1 ali Portfelj 2, izbirno v stranski vrstici |
| merilo je BTC | merilo je World (IWDA) |
| primerjava s S&P 500 | primerjava z drugo knjigo |
| šesto mesto XRP → HYPE | ni potrebno |
| provizija privzeto 30 bps | privzeto **20 bps na posel** |
| uravnavanje privzeto mesečno | privzeto **letno** |
| cene s Coinbasea | cene z Yahooja, v EUR prek tečaja ECB |

Zavihki so isti: krivulja in padci, skozi čas, skladi, občutljivost na vstop,
stroški.

### Pogoji za nakup in prodajo so nedotaknjeni

Uporablja se `lean` s privzetim `LeanConfig`: trackline 75, MA 50 in 200,
vstopni pas 3 %, izstopna milost 3 dni, trajno dno 5 %, brez filtra BTC.
Nobenega pogoja nisem prilagodil delnicam.

**Ena sama vrednost je drugačna, in ni pogoj.** Letno preračunavanje je 252 in
ne 365. Preveril sem, da to ne spremeni nobenega posla:

- `lean` ima binarno alokacijo 0/100, torej `target_alloc` ni odvisen od
  volatilnosti;
- `trading_days` vstopa samo v `annual_vol`, ta pa se naprej uporablja kot
  razmerje do svojega 50-dnevnega povprečja, kjer se faktor skrajša;
- empirično: signali pri 365 in 252 so **identični** na World, GlobAgg in Gold.

To je v `preveri_dashboard_etf.py` kot trajen test, ker je od tega odvisna
trditev, da je strategija nespremenjena.

### Kaj stran pokaže

Privzete nastavitve, 20 bps na posel, letno uravnavanje:

**Portfelj 1**, 2019-01-08 do 2026-09-01 (7,8 let):

| | letno | vol | Sharpe | Sortino | MaxDD | Calmar |
|---|---|---|---|---|---|---|
| sestava, uravnavana | 4,53 % | 9,9 % | 0,50 | 0,68 | −19,4 % | 0,23 |
| sestava, puščena | 4,70 % | 9,9 % | 0,51 | 0,70 | −19,9 % | 0,24 |
| sam World, strategija | 5,49 % | 10,4 % | 0,57 | 0,78 | −22,2 % | 0,25 |
| **sestava, kupi in drži** | **13,31 %** | 16,8 % | 0,83 | 1,15 | −34,4 % | 0,39 |
| **sam World, kupi in drži** | **14,49 %** | 16,8 % | **0,89** | **1,24** | −34,0 % | **0,43** |

**Portfelj 2**, 2019-10-11 do 2026-09-01 (7,0 let):

| | letno | vol | Sharpe | Sortino | MaxDD | Calmar |
|---|---|---|---|---|---|---|
| sestava, uravnavana | 2,67 % | 4,5 % | 0,60 | 0,84 | −9,3 % | 0,29 |
| sestava, puščena | 3,17 % | 5,0 % | 0,65 | 0,90 | −9,3 % | 0,34 |
| sam World, strategija | 4,88 % | 10,3 % | 0,52 | 0,71 | −22,2 % | 0,22 |
| **sestava, kupi in drži** | **6,97 %** | 8,1 % | **0,88** | **1,21** | −16,0 % | **0,44** |
| sam World, kupi in drži | 13,21 % | 17,2 % | 0,81 | 1,12 | −34,0 % | 0,39 |

Vzorec je isti kot povsod v tem projektu: **padec se prepolovi, donos pade
bolj.** Izpostavljenost sestave je 61 % oziroma 64 %, provizije 0,40 oziroma
0,21 enote na leto.

### Neprijetna ugotovitev, ki jo je ta stran razkrila

Nedotaknjen `lean` se na ETF obnese **bolje kot moja "prilagojena"
`ETFConfig`**:

| | izpostavljenost | letno |
|---|---|---|
| nedotaknjen lean na World | 61 % | 5,49 % |
| moja ETFConfig na World | 34 % | −0,42 % |

Krivec je filter ADX, ki sem ga dodal kot delniško konvencijo. Na razpršenem
indeksu je ADX nizek tudi sredi mirne rasti, zato je vstop dovolil skoraj samo
po hitrih odbojih. Ablacija je to pokazala že prej (`brez filtra ADX` je bila
najboljša posamična odstranitev), a šele ta stran pokaže, koliko stane v celoti.

**Za naprej to pomeni: privzeta izhodiščna točka za ETF naj bo nedotaknjen
lean, ne moja ETFConfig.** Prilagoditve se dokazujejo posamično proti njej.

---

## Del 2: česa v demu namenoma ni

| ni v njem | zakaj | kje je |
|---|---|---|
| davek | stran vodi denar, ne davčnih svežnjev; simulacija po svežnjih je prepočasna za vsak premik drsnika | `testing/scripts/etf_davek.py` |
| podaljšana zgodovina | sedem od osmih verig je uporabnih le mesečno, stran pa je dnevna | `shared/etf_data.load(backfill=True)` |
| obrestovanje gotovine | ko je signal zunaj trga, denar leži pri nič | `shared.etf_data.cash_rate()` |
| protokol faz in bootstrap | to je stran za gledanje, ne za sodbo | `testing/scripts/etf_baseline.py` |
| rotacija med knjigama | dnevnih podatkov je premalo za en sam prehod med režimoma | `etf/diversitas/rotation.dual_book` |

---

## Del 3: načrt, po stopnjah

### Stopnja A — da bo demo uporaben (nekaj ur)

1. **Obrestuj gotovino.** Serija ECB je že v sistemu. Pri izpostavljenosti 61 %
   in meri 3,2 % v letih 2023–24 je to približno 1,2 odstotne točke letno, ki jo
   stran zdaj podarja. To je največja posamična napaka na strani.
2. **Vrstica po davku** v glavni tabeli, izračunana enkrat na render in ne ob
   vsakem premiku drsnika (gumb "izračunaj davek").
3. **Zavihek Skladi**: dodaj datum zadnjega signala in trenutno stanje
   (BULL/BEAR) za vsak sklad, da se stran da uporabiti tudi za odločitev "kaj
   danes".

### Stopnja B — da bo primerjava poštena (dan)

4. **Merilo naj bo izbirno**: World, 60/40, ali druga knjiga. Zdaj je World
   trdo vpisan.
5. **Statični delež kot dodatna vrstica.** Na kripto strani je to manjkalo, v
   altcoinskem poročilu pa se je izkazalo za najbolj pošteno merilo: knjiga,
   držana s tolikšnim stalnim deležem, kot je povprečna izpostavljenost
   strategije. Pri 61 % bi to takoj pokazalo, ali je razlika veščina ali le
   manj tveganja.
6. **Mesečni pogled** kot preklop, ki uporabi podaljšano zgodovino do 2005
   oziroma 2008. Dnevni signali tam ne veljajo, zato bi bil to ločen način:
   samo kupi in drži in ciljanje volatilnosti, brez trendnih signalov.

### Stopnja C — da bo to lahko produkcija (teden)

7. **Drugi vir cen.** Vsa stran visi na Yahooju. Kripto stran ima trojno
   verigo, ETF stran nima nobene. Če gre na Streamlit Cloud, je to prva stvar,
   ki lahko odpove tiho.
8. **Zamrznjen posnetek** za stran, kot ga imajo poročila, da render ne bo
   odvisen od omrežja in da bosta dve osebi videli isto številko.
9. **Test poravnave** med stranjo in `etf_baseline.py`: isti vhod mora dati
   isto številko. Kripto stran ima to prek `preveri_dashboard_sestava.py`,
   ETF stran ima za zdaj le notranjo skladnost.

---

## Del 4: kaj rabim od tebe

| vprašanje | moja privzeta izbira | kdaj je treba spremeniti |
|---|---|---|
| **Katera različica strategije?** | `lean`, ker jo uporablja kripto stran | če hočeš `momentum`, je to ena vrstica |
| **Katero merilo?** | World (IWDA), v vlogi, ki jo ima BTC na kripto strani | če je pravo merilo 60/40 ali tvoj obstoječi portfelj, povej — to spremeni vsako primerjavo na strani |
| **Privzeto uravnavanje?** | letno | mesečno je bližje kripto strani, a davčno dražje |
| **Privzet datum vstopa?** | najzgodnejši možen | kripto stran ima trdo vpisan 2021-01-01 |
| **Ali gre to na Streamlit Cloud?** | predpostavljam, da lokalno | če na oblak, moram najprej preveriti, ali Yahoo odgovarja iz podatkovnega centra — kripto stran je prav zaradi tega pinjena na Coinbase |
| **Naj bo davek na strani ali ločeno?** | ločeno | če na strani, potrebujem tvoj davčni položaj: obzorje, ali bo vmes izplačilo, ali uravnavaš z novimi vplačili |
| **Ali smem uteži spreminjati?** | da, urejevalne so, s tvojimi vrednostmi kot privzetimi | če morajo biti fiksne, jih zaklenem |

Odgovori nista nujna za to, da stran teče — vse zgornje je v stranski vrstici.
Nujna sta samo dva, ker spremenita, kaj stran sploh meri: **merilo** in
**ali gre na oblak**.
