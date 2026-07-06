# Diversitas — Predlog naslednjih korakov (sinteza)

**Datum:** 2026-07-06 · Sinteza vsega testiranja (validacijska kampanja + izboljšave +
napredne tehnike + walk-forward optimizacija + root-cause diagnoza).

---

## 1. Kaj smo dokazali (dejstva, ne mnenja)

1. **Parameter tuning obstoječih lean/momentum featurjev NE premaga defaults.** Grid
   sensitivity, Optuna (enkratna in per-fold), plateau selection, 5 seedov, rolling okna —
   vse pristopi. Rezultat: 0–2/6 zmag na OOS, in te ne zdržijo hold-outa.
2. **Zakaj:** optimalni parametri so **nestacionarni**. Train-best `track_period` == OOS-best
   le 1/5. BTC režim se je spremenil (2017–21 hiper-bull @70% vol → 2022 bear → 2023–25
   ETF-era @40–55% vol). Kar je bilo optimalno na preteklosti je sistematično napačno naprej.
3. **Pine defaults so na robustnem platoju** — kompromis ki ni nikoli per-period optimum, a
   nikoli daleč. To je zaželeno pri nestacionarnem trgu.
4. **Edina robustna izboljšava = adaptacija čez režime, ne tuning.** Cross-sectional rotacija
   je bila edini velik, hold-out-potrjen win. Regime-switch pomaga v bear trgu.
5. **BTC odvisnost ni problem:** β 0.09–0.31, edge preživi β-hedging (za momentum).
6. **Primarni cilj (rez drawdowna) dosežen OOS:** 16/16 asset-varianta kombinacij v pravem
   bear hold-outu (lean BTC −12% vs B&H −53%).

---

## 2. Kaj predlagam (rangiran, z utemeljitvijo)

### A) OBDRŽI Pine defaults za lean in momentum — ne optimiziraj parametrov
**Zakaj:** dokazano da tuning ne preživi OOS (nestacionarnost). Sprememba parametrov bi
**znižala** živo performanso. "Optimizirali smo in namerno nič spremenili" je najmočnejši
anti-overfitting dokaz za sodelavca.

### B) DODAJ cross-sectional rotacijo (top-3) — glavna izboljšava *(Med kompleksnost)*
Namesto da tržiš vse assete enako, vsak dan drži 3 najmočnejše po signalu (graded-momentum
sleeve). **Design Calmar 1.49 vs equal-weight 1.07 (+40%), bear hold-out +0.73 vs −0.03.**
To je edina sprememba ki pomaga v obeh režimih (bull design + bear hold-out) — ker se
*adaptira* čez assete, ne fiksira parametrov.

### C) DODAJ regime-switch (Lean↔Momentum) kot bear zavarovanje *(Med, opcijsko)*
Detektor (BTC vs 200-MA ali vol režim), lagged 1 dan: bull → Momentum, bear → Lean.
Izboljša bear hold-out (Calmar −0.2 → +0.03…+0.17) za majhno ceno v bull. Vklopi če je
zaščita pred padci prioriteta.

### D) LEAN sleeve: dodaj Donchian-55 breakout confirmation *(Low)*
Edini signal-level tweak ki preživi čisto validacijo z **monotonim** odzivom (period 20/34/55
→ +0.27/+0.38/+0.52 validation Calmar). Nizka kompleksnost (en kanal).

### E) NE dodajaj: Kelly sizing, weekend-skip (momentum), SuperTrend, meta-labeling,
HRP, macro/on-chain pipe-i. Vsi testirani, nobeden ne preživi (variance-only ali škodljivi).

---

## 3. Konkreten plan izvedbe

### Faza 1 — Produkcijski rotacijski sloj (1–2 dni)
- Nov modul `portfolio/rotation.py` nad obstoječimi strategijami (Pine ports nedotaknjeni).
- Vsak dan: rangiraj assete po `moč = (#variant BULL) + clip(dist_nad_trackline/20, 0, ∞)` z
  **včerajšnjimi** vrednostmi; drži top-3 z močjo ≥1, equal-weight, ostalo cash.
- Sleeve = Momentum z graded RSI sizingom (`pozicija × clip((RSI−50)/20, 0.5, 1)`).
- Unit testi: no-lookahead (shift(1)), rotacija=equal-weight ko K=št. assetov.

### Faza 2 — Regime-switch + Lean Donchian (1 dan)
- Config flag (default off) za regime detektor in Lean Donchian-55.
- Regression test: default off → identično obstoječemu (dokaz da ničesar ne pokvarimo).

### Faza 3 — Dashboard integracija (1 dan)
- Rotacijski portfelj kot nov "način" v dashboardih (poleg single-asset), s KPI karticami
  (vključno z "Vrednost 100" ki smo jo dodali), equity krivuljo, per-asset alokacijo v času.

### Faza 4 — Ongoing validacija / ops (kontinuirano)
- **Paper trading** rotacije z realist fees pred povečanjem kapitala.
- **Rolling walk-forward monitoring**: mesečno preveri stitched-OOS Sortino/Calmar vs
  hold-out baseline; opozori če se degradira.
- **Regime-conditional tracking**: loči performanso po bull/bear/sideways; zahtevaj robustnost.
- **Re-deflate** ko se nabere več trialov; ponovno potrdi z CPCV.

### Faza 5 (kasneje, opcijsko) — širitev
- Dodatni asseti (survivor-bias kontrola: XRP/BNB/ADA že testirani).
- CPCV kot standardni validacijski test za vsako novo idejo.
- Meta-labeling kot *drawdown-reduction* sloj nad rotacijo (le če mandat postane
  minimizacija drawdowna, ne donos).

---

## 4. Za sodelavca — enostavčni povzetek

> "Obstoječih parametrov ne moremo zanesljivo bolje nastaviti — dokazali smo, da so optimalni
> parametri nestacionarni (BTC režim se je spremenil), zato vsak tuning propade out-of-sample.
> Zato ohranjamo robustne defaults. Vrednost dodamo **strukturno**: cross-sectional rotacija
> (drži najmočnejše assete) je edina sprememba ki robustno pomaga v bull IN bear — ker se
> adaptira čez režime namesto da fiksira parametre. To je tudi točno kar profesionalna
> literatura priporoča za nestacionarne trge (regime-adaptacija, ne parameter-optimizacija)."

---

## 5. Česa NE delati (in zakaj)

- ❌ Ne optimiziraj lean/momentum parametrov naprej — dokazano overfitting (nestacionarnost).
- ❌ Ne dodajaj Kelly/weekend-skip/SuperTrend/meta-labeling — testirani, ne pomagajo.
- ❌ Ne zaupaj enemu anchored walk-forwardu — pokriva ~en cikel; uporabi rolling + CPCV.
- ❌ Ne poganjaj v živo brez paper tradinga — hold-out je zdaj opazovan, ni več pristojen.
