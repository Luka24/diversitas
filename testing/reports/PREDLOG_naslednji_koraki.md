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

### B) DODAJ cross-sectional rotacijo (top-3, tedenski rebalans) — glavna izboljšava *(Med)*
Namesto da tržiš vse assete enako, drži 3 najmočnejše po signalu (graded-momentum sleeve),
rebalansiraj tedensko. **Poštena slika (kalibrirano, ne napihnjeno):**
- Prednost je **kontrola drawdowna + bear robustnost**, NE premagovanje diverzificiranega
  holda v vsakem oknu. Full-period design Calmar ≈1.58 vs equal-weight ≈1.07, bear hold-out
  Sortino ~1.8 vs ~0, max drawdown ~prepolovljen. **A izgubi nekaj mirnih bull oken** (koncentrira
  se / gre v cash, zamudi široke rallyje) — zmaga ~2/5 design oken po Sortinu.
- **Turnover je visok in fee-občutljiv:** ~1500%/leto (tedensko; dnevno je bilo ~3400%).
  Vse številke NETO po fees; rabi poceni izvedbo.
- Pozicioniraj kot **risk-controlled portfelj**, ne univerzalni zmagovalec.
- Implementirano: `momentum/diversitas/rotation.py` (+ CLI, dashboard način, live signal export).

### C) DODAJ regime-switch (Lean↔Momentum) kot bear zavarovanje *(Med, opcijsko)*
Detektor (BTC vs 200-MA ali vol režim), lagged 1 dan: bull → Momentum, bear → Lean.
Izboljša bear hold-out (Calmar −0.2 → +0.03…+0.17) za majhno ceno v bull. Vklopi če je
zaščita pred padci prioriteta.

### D) LEAN sleeve: Donchian-55 breakout confirmation — OPCIJSKO, marginalno *(Low)*
Na validacijskem *slicu* je kazal +0.52 Calmar (monoton odziv 20/34/55), a na **poolani
leakage-safe evalvaciji je učinek marginalen** (+0.02 design, 0.00 hold-out). Implementiran
za config flagom (default OFF — a-priori Lean nespremenjen). Vključi le če hočeš, ni jasen win.

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
> (drži najmočnejše assete). Poštено: njena prednost je **kontrola drawdowna in bear robustnost**
> (design Calmar 1.58 vs 1.07, bear hold-out močan, DD ~prepolovljen), NE premagovanje
> diverzificiranega holda v vsakem oknu — v mirnih bull obdobjih včasih zaostane. Turnover je
> visok (~1500%/leto), zato rabi poceni izvedbo. To je regime-adaptacija (kar literatura
> priporoča za nestacionarne trge), ne parameter-optimizacija — in jo pozicioniramo kot
> risk-controlled portfelj, ne univerzalni zmagovalec."

---

## 5. Česa NE delati (in zakaj)

- ❌ Ne optimiziraj lean/momentum parametrov naprej — dokazano overfitting (nestacionarnost).
- ❌ Ne dodajaj Kelly/weekend-skip/SuperTrend/meta-labeling — testirani, ne pomagajo.
- ❌ Ne zaupaj enemu anchored walk-forwardu — pokriva ~en cikel; uporabi rolling + CPCV.
- ❌ Ne poganjaj v živo brez paper tradinga — hold-out je zdaj opazovan, ni več pristojen.
