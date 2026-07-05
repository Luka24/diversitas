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
