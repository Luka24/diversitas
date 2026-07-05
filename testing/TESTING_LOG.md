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
