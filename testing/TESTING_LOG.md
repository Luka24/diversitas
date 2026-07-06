# Diversitas — Testing Log

Kronološki dnevnik vseh izvedenih testov. Faze v `TESTING_PLAN.md` (v2) in
`TESTING_PLAN_v3.md` (v3 — Lean + Momentum, statistična rigoroznost).

---

## 2026-07-05 — Faza 0 (v3): Harness + metrike ✅

- Zgrajen testni harness: `testing/scripts/{dataio,engine,metrics,stats}.py`.
- `pytest testing/tests/` → **16 passed** (metrike, trade ledger, look-ahead audit,
  DSR monotonost, block bootstrap, alpha/beta recovery, PBO na šumu).
- **Cross-check z live dashboardom** (BTC/momentum, design set): cagr/sharpe/sortino/
  max_dd/calmar se ujemajo na **< 1e-6**.
- Podatki zamrznjeni v `testing/data/` (design ≤ 2025-03-31, hold-out ≥ 2025-04-01 karantena).
- Poročilo: `testing/reports/phase0_report.md`.
- **Gate PASSED** → naprej na Fazo 1 (baseline vseh assetov).

## 2026-07-05 — Faza 1 (v3): Baseline ⚠️ REVIEW (pomembna ugotovitev)

- `run_baseline.py`: 8 assetov × {lean, momentum} na design setu, 4 kriteriji.
- **C1 (znižanje Max DD vs B&H) — primarni cilj — 100% (8/8 obe varianti).** BTC −38% vs −77% B&H.
- **C3 vs C4 v konfliktu po zasnovi:** lean konzervativen (C3 8/8, C4 2/8), momentum agresiven (C4 6/8, C3 2/8). Nobena varianta ne more obe hkrati.
- **Momentum dominira Calmar na 8/8 assetih** (ETH 1.28 vs 0.52, AVAX 0.97 vs 0.08, ADA 1.29 vs 0.87).
- Problematična: **LINK** šibek na obeh; **AVAX lean** pokvarjen (Calmar 0.08).
- Gate literalno REVIEW (0/5 all-4), a to je posledica konfliktnih kriterijev — glej priporočilo v `phase1_report.md`.
- Trial counter: 16 (1 default na asset×variant).
- Poročilo: `testing/reports/phase1_report.md`.

*Naslednje: uskladitev kriterijev (odločitev uporabnika) → Faza 2 (BTC dependence).*

## 2026-07-05 — Faza 2 (v3): BTC dependence ✅

- `run_btc_dependence.py`: OLS α/β (Newey–West HAC), rolling 90d β/corr, BTC-β-hedged re-score.
- **Kritika "high BTC beta" empirično ovržena:** β = 0.09–0.31 (median 0.15), R² 0.03–0.20, corr 0.17–0.45. Strategije NISO levered BTC.
- **Po hedgingu β edge preživi** (Momentum: ETH 1.13→0.83, SOL 1.17→0.99, ADA 1.37→1.17). Lean slabše.
- Pošten caveat: nizka β delno mehanska (~65% časa v cashu); per-asset α večinoma ni značilna pri 5% (samo ADA momentum t=2.33) — značilnost se dokaže čez več assetov + DSR v Fazah 4–5.
- **LINK izjema** — hedged Sharpe ≈ 0, njegov performance je večinoma beta.
- Poročilo: `testing/reports/phase2_report.md`.

## 2026-07-05 — Faza 3 (v3): Sensitivity ✅

- `run_sensitivity.py`: 1-parametrski sweepi (BTC primarno + ETH/SOL cross-asset), robustnost = Calmar plato.
- **Momentum: 0 fragilnih (interior-sharp) parametrov** — strukturno robusten. Lean: 1 (`track_buf_pct`), a ETH/SOL se ne strinjata (x-agree 0/2) → asset-specific šum → obdrži default 3.0.
- **Edge optima kažejo v smer agresije** (krajši trackline, manjši buffer, hitrejši re-entry, višji vol-target) — in-sample BTC pull. **Ne lovimo jih** — to je overfitting past; OOS test v Fazi 5 odloči.
- **Nizka cross-asset agreement (večinoma 0/2)** = BTC-specifičen šum, ne strukturno. Izjema: momentum `target_vol_pct=80` (2/2 agree) — edini edge signal vreden OOS testa.
- Phase 6 shortlist: `track_period`, `track_buf_pct`, `reentry_hold` (pod walk-forward + DSR kontrolo).
- Trial counter: 367.
- Poročilo: `testing/reports/phase3_report.md` + 18 PNG sweep grafov.

## 2026-07-05 — Faza 4 (v3): Monte Carlo & stabilnost ✅

- `run_montecarlo.py`: block bootstrap (2000×, blok 20d), trade-shuffle (2000×), parameter-noise ±10% (300×).
- **Parameter-noise Calmar CV: momentum 0.14, lean 0.20** (oba < 0.35) → strategiji sta na platoju, ne na konici. Kvantitativno potrdi Fazo 3.
- **Sharpe 95% CI izključuje 0:** momentum 3/3 (BTC/ETH/SOL), lean 2/3 (SOL vključuje 0).
- **Trade-shuffle MDD percentil:** momentum visok (52/72/97%) → realiziran DD je konservativen, ne srečen; lean nizek (15/20/6%) → DD delno odvisen od zaporedja (caveat za lean).
- Momentum robustnejši na vseh oseh. Gate ✅.
- Poročilo: `testing/reports/phase4_report.md`.

## 2026-07-05 — Faza 5 (v3): Walk-forward + CPCV + Deflated Sharpe ✅ (ključna faza)

- `run_walkforward.py`: anchored WF (4×6mes OOS, 21d embargo), CPCV PBO (252 poti), dva DSR računa.
- **WFE > 1 povsod** (lean 2.9/2.0, momentum 3.9/1.3) → OOS Calmar presega IS → NASPROTJE overfittinga.
- **PBO:** momentum čist (BTC 0.22, ETH 0.46 ✅); **lean/ETH 0.87 ⚠️** — genuina overfitting past za lean.
- **Dva poštena Sharpe verdikta:**
  - PSR a-priori (N=3, default Pine ni bil izbran iz sweepa): **momentum BTC 0.980, ETH 0.973 ✅**; lean BTC 0.949 (borderline), ETH 0.870.
  - DSR data-mined (N≈385, brutalen counterfactual): 0.30–0.61 — objavljeno transparentno; rešitev = ne cherry-pickamo + hold-out (Faza 8).
- **Param stabilnost:** večinoma 1 (popolnoma stabilno čez folde).
- **Momentum je jasno močnejši, manj overfit kandidat na vsaki metriki.**
- Poročilo: `testing/reports/phase5_report.md`.

## 2026-07-05 — Faza 6 (v3): Poštena optimizacija ✅ (keep defaults)

- `run_optuna.py`: TPE 150 trialov, optimiziraj Calmar na train (≤2024-09-30), validiraj OOS + cross-asset.
- **Lean:** optimiziran train 0.74→1.40, a **OOS kolaps 7.11→1.11** — učbeniški overfitting. Default zmaga.
- **Momentum:** optimiziran zmaga BTC-OOS (5.87→7.04) a **slabši na ETH (1.24<1.28) IN SOL (0.98<1.12)** — ne generalizira.
- **Robustnih izboljšav: 0/2.** Data-mined DSR ostane <0.95 (N≈538).
- **Odločitev: obdrži Pine defaults za obe varianti.** "Optimizirali smo in namerno nič spremenili" = najmočnejši anti-overfitting dokaz.
- Poročilo: `testing/reports/phase6_report.md`.

**Analitični del (Faze 0–6) zaključen.** Naslednje: Faza 7 — A/B testi Q&A izboljšav (glavni fokus).

## 2026-07-05 — Faza 7 (v3): A/B testi Q&A izboljšav ✅ (glavni fokus)

- `run_feature_ab.py` + `features.py`: 11 idej × 2 varianti = 22 izoliranih A/B testov vs Pine default.
- Metoda: paired block-bootstrap ΔSharpe CI (2000×) + OOS + cross-asset sign. Accept = vse troje.
- **Rezultat: 0 sprejetih.** Nobena ideja ne premaga a-priori Pine dizajna po strogi izolirani presoji.
  - ATR buffer: škodi (delay entry/exit); momentum CI izključuje 0 → REJECT.
  - Kelly: škodi (MaxDD +20pp), noisy rolling ocene → over-lever. REJECT.
  - Weekend skip: škodi momentumu (kripto 24/7). REJECT.
  - EMA vol-shock: točno 0 (vol_shock že redundanten s trackline break).
  - Profit-taking / rolling-peak brake / lean-trailing: nevtralno.
  - Sanity: dodajanje 12% trail momentumu (že ima) = točno 0 → harness zvest.
- **Zaključek: strategiji sta na robustni operativni točki; intuitivne izboljšave ne zdržijo strogega testa.** Konsistentno s Fazo 6.
- Poročilo: `testing/reports/phase7_report.md`.

## 2026-07-05 — Faza 8 (v3): Fees + hold-out + master report ✅ (zaključek)

- `run_final.py`: fee sensitivity (3 scenariji), break-the-glass hold-out (2025-04→2026-07, prvič in edinkrat), master report.
- **Hold-out je bil pravi kripto bear market** (B&H padel povsod: BTC −19%, ADA −62%).
- **Drawdown control zdržal OOS: 16/16 asset-varianta kombinacij reže DD vs B&H** (lean BTC −12% vs −53%, momentum ADA −21% vs −85%). Primarni cilj potrjen na nikoli videnih podatkih.
- **Pošten preobrat regimov:** v bear hold-outu **Lean prekaša Momentum** po donosu (lean median CAGR > momentum) — previdnost se je izplačala. V (bull) design setu je vodil Momentum. Nobena varianta ne dominira čez vse regime → **ladjaj obe**.
- Fees ne razbijejo: realist ~0.03–0.08 Calmar; momentum plača več (več tradanja).
- Priporočilo: obe varianti s Pine defaults, LINK izloči, paper trading z realist fees.
- Poročilo: `testing/reports/final_report.md`.

**KAMPANJA (Faze 0–8) ZAKLJUČENA.**

## 2026-07-05 — Izboljšave Part A: strukturne kombinacije ✅ (najdene prave izboljšave!)

- `improvements.py` + `run_improvements.py`: ensemble, regime-switch, agreement, rotation, vol-weighted. Pooled 8 assetov + hold-out.
- **ZMAGOVALEC — cross-sectional rotation (top-K najmočnejših signalov):**
  - k=3 momentum: design Calmar **1.39** (vs equal-weight 1.07, +30%), **hold-out +0.64** (vs 0.05).
  - k=2 momentum: design **1.94** (+81%), hold-out **0.75** — agresivneje, večji DD (-48%).
  - Ni k=2 fluke: k=2/3/4 vsi premagajo equal-weight. Kompleksnost Med. **Vredno.**
- **Regime-switch (BTC-200MA / vol): obrambna izboljšava** — hold-out Calmar -0.2→+0.03…+0.17, MaxDD -16% vs -23%. Design malenkost slabši. Vredno za bear-robustnost.
- Ensemble/agreement/vol-weighted: zmanjšajo varianco a ne premagajo najboljše single variante → SKIP.
- Že samo equal-weight diverzifikacija čez assete pomaga (holdout -0.03/+0.05 vs per-asset -0.21).
- Poročilo: `testing/reports/improvements_report.md`.

## 2026-07-05 — Izboljšave Part B: Q&A sizing/signal tweaki (swept, pooled) ✅

- Vsak tweak swept + pooled čez 8 assetov + hold-out (popravek Phase 7, ki je bil BTC-only/unswept/prestrog).
- **Kredibilni zmagovalci (design gain IN hold-out izboljšava):**
  - **Momentum + graded_entry** (RSI-scaled sizing): design 1.24 (+24%), hold-out -0.21→-0.01.
  - **Lean + ATR buffer k=1.5**: design 0.54 (+22%), hold-out -0.09→+0.22.
- Design-driven (šibkejši hold-out): Lean DD-brake (+27%), Lean weekend-skip (+15%), Momentum vol_target=90 (+13%).
- **Potrjeni gubitniki:** Kelly (momentum -42%, lean marginal), weekend-skip na momentumu (-26%), ATR buffer na momentumu (-14%). Konsistentno s Phase 7.
- Vzorec: **Lean ima korist od bolj konzervativnih dodatkov** (ATR buffer, DD brake, weekend skip), **Momentum od graded sizinga**.
- Poročilo: `testing/reports/improvements_report.md` (Part B dodan).

## 2026-07-05 — Izboljšave Part C: stacking zmagovalcev ✅ (glavni rezultat)

- Rotation (Part A) + graded-entry momentum (Part B) sta **aditivna in se odlično dopolnjujeta**:
  - **rotation k=3 + graded: design Calmar 1.49, hold-out +0.73, MaxDD samo -18%** (vs equal-weight 1.07 / -0.03 / -31%).
  - Rotation doda donos, graded entry zreže drawdown ki ga rotacija vnese (-46%→-18%).
  - rotation k=2 + graded: design 2.21, hold-out 0.75, DD -33% (agresivneje).
- **Finalna priporočila (rangiran benefit-vs-kompleksnost):**
  1. Rotation top-3 + graded momentum (Med, NAJVEČJI učinek)
  2. Rotation sam (Med)
  3. Momentum graded entry / Lean ATR buffer k≈1.5 (Low)
  4. Regime-switch (Med, obrambno)
  SKIP: Kelly, weekend-skip na momentumu, ensembles/agreement.
- Pošten caveat: zmagovalci izbrani iz sweepa (selection bias) — zaupamo tistim ki izboljšajo tudi hold-out (rotation, graded, lean ATR buffer vsi to naredijo). Paper trading pred povečanjem.
- Poročilo: `testing/reports/improvements_report.md` (kompletno A+B+C + implementacijske opombe).

**IZBOLJŠAVE (Part A+B+C) ZAKLJUČENE.** Produkcijska koda nedotaknjena; poročilo vsebuje natančne recepte za implementacijo.

## 2026-07-05 — Coverage audit + metodologija ✅

- `coverage_and_methodology.md`: popoln pregled VSEH idej iz Q&A dokumenta → status + parametri.
- **Vse ideje applicable za Lean/Momentum stestirane** (večina s parameter sweepom).
- Netestirano: (a) Full-variant conviction-score družina (⛔ arhitekturno odsotna iz lean/momentum), (b) on-chain/macro (⏸ user-excluded).
- Zaprte vrzeli: vol_z buffer (marginal), dynamic re-entry (škodi momentumu -58%), BTC filter A/B (ON pomaga momentum altcoinom 0.97→1.12).
- **Metodologija proti overfittingu** (grounded v web research): karantiniran hold-out ≥20%, purge+embargo 200 bars, anchored WF 4 folds, CPCV+PBO, regime-segmented (bull/bear/sideways), Deflated Sharpe (N-trials), pooled cross-asset, red-flag tripwires (WR>80%/PF>5).
- Ključno spoznanje iz raziskave: **walk-forward sam validira v enem regimu → potreben regime coverage + CPCV**.

## 2026-07-05 — Full per-parameter results matrix ✅

- `run_feature_matrix.py`: VSAK feature pri VSAKI parameter vrednosti → pooled design + hold-out (185 config-ov, 8 assetov).
- Poročilo `feature_matrix_results.md`: polne per-parameter tabele za lean & momentum + winners + correctness notes + key findings.
- **Verificirani genuini no-opi (ne bugi):** target_vol_pct na lean (binary target_alloc, vol-sizing off-path), vol_shock_mul/ema_volshock (vol_shock zadane le 2/2600 barov v BULL).
- **Ship-grade zmagovalca:** Momentum graded_entry (+24% design, hold-out -0.21→-0.01, DD -38%→-27%), Lean ATR buffer k=1.5 (+22%, hold-out -0.09→+0.22).
- **Regime trade-off surface:** obrambne nastavitve žrtvujejo design a močno izboljšajo bear hold-out (Momentum atr_buffer k=2.5 → hold-out +0.43!, trail_pct=6 → +0.18, daljši lean track_period → +0.21/+0.23).
- Kelly močno reže DD a škodi Calmar. Večina parametrov flat-topped (robustno, potrjuje Ph3/4).
- Multiple-testing caveat: ~50 config/varianta → nekateri ★ so šum; zaupaj tistim z mehanizmom + hold-out.

## 2026-07-05 — Leakage-safe validacija + nove ideje (raziskava) ✅ (POMEMBEN POPRAVEK)

- Spletna raziskava potrdila overfitting tveganje: **feature selection mora biti samo na train/validation, ne hold-out.** Moje izboljšave (Part A/B/C, matrix) so hold-out uporabile večkrat kot selection filter → leakage.
- `run_validation.py`: 3-way split (TRAIN ≤2023-06, VALIDATION 2023-07→2025-03 za selekcijo, HOLD-OUT ≥2025-04 enkrat). Retest zmagovalcev + nove ideje.
- **HONEST POPRAVEK:**
  - **Rotation je EDINI robusten zmagovalec:** validation Calmar 2.48 (plain) / 3.21 (graded) vs momentum baseline 1.51, hold-out zdrži (0.64/0.73). NI leakage artifact.
  - **graded_entry napihnjen:** izgledal +24% na design, a le **+0.03 na validation** (1.54 vs 1.51).
  - **lean atr_buffer napihnjen:** izgledal +22%, a **slabši na validation** (0.80 vs 0.88) — dobiček je bil hold-out sreča.
- **Nove ideje iz raziskave (SuperTrend, dynamic trailing, TSMOM):** NE premagajo baseline na validation (1.35/1.30/1.27 < 1.51). Nevtralno-obrambne.
- **Obrambni vzvodi** (regime-switch, TSMOM-120): izgubijo na bull validation, izboljšajo bear hold-out — regime tradeoff.
- **Bottom line: po popravku leakage samo rotacija robustno izboljša rezultat.** Manjši tweaki ne preživijo čiste selekcije. Poročilo: `validation_report.md`.

## 2026-07-05 — Nove ideje: temeljit sweep (leakage-safe) ✅

- `run_new_ideas.py`: SuperTrend (period×mult, 12 combos), TSMOM filter+sizing (lookback), dynamic vol-trailing (base×coef, 12), Donchian (period) — vse pod 3-way split (selekcija na validation, holdout enkrat).
- **LEAN pridobi (šibkejši baseline 0.88, prostor za izboljšavo):**
  - **Donchian breakout — standout:** validation Calmar monotono raste s periodo (20/34/55 → +0.27/+0.38/+0.52), holdout nespremenjen. Monotona (ne-spike) odzivnost = pravi efekt, ne curve-fit. Low complexity.
  - Dynamic vol-trailing: dvigne lean na validation (10/2 → +0.20) + močno izboljša bear holdout pri tesnejših nastavitvah.
- **MOMENTUM (1.51) težko premagati:** novi filtri večinoma obrambni — TSMOM-120/Donchian pomagajo bear holdout a stanejo bull validation. TSMOM-30 +0.17 (verjetno šum).
- **SuperTrend: večinoma no-op ali negativno** na obeh (drop).
- **Rotation ostaja glavni strukturni win** (val 2.48 plain, 3.21 graded sleeve); × TSMOM sizing = obrambna varianta (val 2.08, holdout 0.78).
- 11 survivors od ~80 config-ov; multiple-testing caveat — prednost monotonim (Donchian) pred single-corner (dynamic_trail 14/6).
- Poročilo: `testing/reports/new_ideas_report.md`.

## 2026-07-05 — On-chain (§6) + Macro (§7) pipes ✅ (zadnje netestirano)

- `external_data.py` + `run_external.py`: zamrznjeni DXY+BBB (FRED) in Coinbase premium (Coinbase vs Binance BTC). MVRV rabi plačljiv on-chain feed → dokumentiran, ne testiran.
- **Macro pipe (DXY+BBB) kot specificiran: TOČNO 0 učinka** (fires 11/2600 barov = 0.4%). Potrjuje doc-ovo napoved "mostly neutral".
- Bolj agresivno (DXY-only 0%): -0.93/-1.30 (blokira dobre entry-je).
- **Premium filter BTC** (spec thr): 0 učinka; thr=0 nekonsistentno (momentum +0.33, lean -1.72) → ne robustno.
- **Zaključek: eksterni pipe-i so obrambni context filtri z majhnim učinkom** — konsistentno z doc-ovim pričakovanjem — NISO med izboljšavami vrednimi dodajanja.
- **Coverage complete:** vse iz Q&A dokumenta testabilno na free podatkih je zdaj testirano. Ostaja le MVRV (plačljivo).
- Poročilo: `testing/reports/external_report.md`.

## 2026-07-06 — Napredne tehnike (Part D): meta-labeling, HRP, HMM, ensemble, lead-lag ✅

- Spletna raziskava → ML/portfolio tehnike onkraj rule-tweakov. `ml.py` (triple-barrier + Purged K-Fold CV), `portfolio.py` (HRP), D3-D5 v improvements.py. Vse pod leakage-safe 3-way split.
- **D1 Meta-labeling:** sekundarni model zmanjša exposure (filtrira šibke signale) → nižji bull Calmar. NE premaga baseline. **Poučen overfit:** lean_logit_thr0.5 val 1.61 a holdout -0.37 — val-lucky config, purged CV sam ne zadošča ker še vedno selektiramo threshold na validation.
- **D2 HRP:** val 2.51 ≈ rotation 2.48 a holdout -0.34 vs +0.64 → NE premaga rotacije (skladno z literaturo).
- **D3 HMM (2/3-state):** 2-state ≈ baseline, 3-state obrambno.
- **D4 Ensemble majority:** val 1.54 ≈ baseline, holdout +0.01 (marginalno).
- **D5 Lead-lag:** ≤ baseline.
- **Zaključek: nobena napredna tehnika ne izpodrine rotacije.** Meta-labeling = drawdown-reduction vzvod, ne return-booster.
- 6 novih unit testov (triple-barrier, PurgedKFold, HRP). Poročilo: `advanced_report.md`; summary posodobljen.

## 2026-07-06 — Profesionalna walk-forward optimizacija (Part E) ✅

- Spletna raziskava → profesionalni WFO recept: per-fold reoptimizacija + stitched OOS, plateau selection (ne peak), multi-seed. `wfo.py` + `run_wfo.py`.
- Metoda: 5 anchored foldov, Optuna TPE (plateau-selected), 5 seedov, stitched OOS, hold-out potrditev. Lean+Momentum × BTC/ETH/SOL.
- **Rezultat: optimizirano premaga defaults na stitched OOS le 2/6**, in ti "zmagi" ne zdržita hold-out (lean/SOL: stitched 1.52 vs 0.44 ampak hold-out -0.99 vs -0.09 = kolaps). Samo momentum/ETH konsistenten (1/6 = naključje pri 6 poskusih).
- **Parameter instability visok** (track_buf_pct 6-7 distinct vrednosti čez 25 fitov, reentry_hold 8-10) = optimizer lovi šum, ne konvergira na stabilno nastavitev.
- **Optimum drifta v agresijo** (kratek trackline, tesen buffer, visok vol-target) ki zmaga in-sample a propade forward — učbeniški overfit signature.
- **Zaključek: tudi z najstrožjim profesionalnim WFO originalne parametre ni mogoče zanesljivo premagati.** Defaults so na robustnem platoju.
- 4 novi unit testi (plateau_select, folds). Poročilo: `testing/reports/wfo_report.md`.

## 2026-07-06 — Root-cause: ZAKAJ optimizacija ne premaga defaults ✅

- `run_wfo_diagnosis.py`: za vsak fold skenira grid na train IN na OOS, primerja argmax + regime stats.
- **H2 (distribution shift) POTRJEN:** train-best track_period == OOS-best le **1/5**. Train VEDNO reče TP=30 (dominira ga eksplozivni 2017-2021 bull), a OOS-optimal variira 25→55. Kar je bilo najboljše na preteklosti NI najboljše na naslednjem oknu.
- **H1 (regime) je mehanizem:** train okna = ogromen bull (+271% do +786%, vol 67-76%); OOS bloki = tamer (+30-80%, vol 38-56%). Param nastavljen na divje bull nihanje je mis-sized za mirnejši ETF-era režim.
- **Regret povprečno 1.24 Sortino točk** (2024-07: best-possible 3.76 vs realized 0.98!) — boljši config JE obstajal a le vidno PO testu = hindsight.
- **Zakaj defaults zmagajo:** so kompromis ki ni nikoli per-period optimum a nikoli daleč — robusten sredina platoja čez režime.
- **Zaključek:** optimalni parametri so NESTACIONARNI (BTC režim se spremenil), zato train-optimal je sistematično napačen za naslednje obdobje. Vrednost dodaš z regime-switch / rotacijo (adaptirata čez režime), ne s finejšim tuningom.
- Poročilo: `testing/reports/wfo_diagnosis_report.md`.

## 2026-07-06 — Rolling vs anchored WF: profesionalni fix za non-stationarity ✅

- Sodelavčeva opazka pravilna: anchored WF pokriva ~en cikel prehod (train = 2017-2021 bull, test = 2022-25).
- `run_wfo_rolling.py`: rolling okno (train = zadnjih 730 dni) vs anchored vs default, stitched OOS.
- **Rolling pomaga vs anchored na BTC** (momentum 1.63 vs 1.50, lean 2.02 vs 1.57) — pozabi stale 2017 bull, ujame recent regime. Na ETH mešano.
- **A rolling premaga default le 1/4** — na BTC default še vedno zmaga (momentum 1.88, lean 2.28). Kripto režimi se obrnejo hitreje kot okno → 6-mes test blok je še vedno drug režim kot 2-letno train okno. **Ujemanje okna zoži vrzel, a je ne zapre.**
- **Profesionalne rešitve za "en del cikla":** (1) rolling okna [demonstrirano], (2) CPCV [imamo PBO], (3) regime-switching [Part D/A], (4) test čez ≥1 boom-bust cikel, (5) parameter/model ensembli.
- **Zaključek: durable edge = adaptacija čez režime (rotacija/regime-switch), NE finejši tuning parametrov.**
- Poročilo: `testing/reports/wfo_rolling_report.md`.
