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

*Naslednje: Faza 1 — `run_baseline.py` (8 assetov × {lean, momentum}, 4 kriteriji).*
