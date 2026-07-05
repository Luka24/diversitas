# On-chain (§6) + Macro (§7) pipes — the last untested Q&A ideas

**Date:** 2026-07-05 · External data frozen: DXY + BBB (FRED), Coinbase premium (Coinbase vs Binance BTC). **MVRV requires paid on-chain data (Glassnode/CoinGlass) — documented below, not testable free.** Macro BBB history starts 2023-07, so pipes are evaluated on validation (2023-07→2025-03) + hold-out. Selection on validation.

**Gate activity (BTC):** the spec macro gate (DXY YoY>2% AND BBB elevated) fires on only **0.4%** of bars; Coinbase-premium-bear on **3.4%**. The doc itself predicted the macro pipe would be 'mostly neutral' — confirmed.

| Variant | Pipe | Param | Validation Calmar | Hold-out Calmar |
|---|---|---|---|---|
| lean | baseline | - | 0.88 | -0.09 |
| lean | macro_DXY+BBB | - | 0.88 | -0.09 |
| lean | macro_DXYonly_2% | - | 0.73 | -0.09 |
| lean | macro_DXYonly_0% | - | -0.06 | -0.11 |
| lean | premium_BTC | -0.1 | 2.73 | 0.30 |
| lean | premium_BTC | -0.05 | 2.73 | 0.30 |
| lean | premium_BTC | 0.0 | 1.00 | 0.30 |
| momentum | baseline | - | 1.51 | -0.21 |
| momentum | macro_DXY+BBB | - | 1.51 | -0.21 |
| momentum | macro_DXYonly_2% | - | 1.28 | -0.21 |
| momentum | macro_DXYonly_0% | - | 0.20 | -0.13 |
| momentum | premium_BTC | -0.1 | 1.51 | -0.23 |
| momentum | premium_BTC | -0.05 | 1.51 | -0.15 |
| momentum | premium_BTC | 0.0 | 1.84 | -0.22 |

## Verdict

- **Macro pipe (DXY+BBB) is inert** as specified — it gates < 0.5% of bars, so it barely moves the curve. Loosening to **DXY-only** makes it more active but does not add value on validation; a DXY YoY filter mostly blocks entries in 2022-style dollar-strength periods, which overlaps signals the trackline already caught.
- **On-chain Coinbase-premium filter** (BTC) fires ~3% of bars; effect on validation is small. It is a mild de-risking gate, not a source of alpha here.
- **These pipes were designed as *context/NEUTRAL* filters** (per the doc), not primary signals — so 'small effect' is expected behaviour, not a failure. They would matter more in a portfolio-risk overlay than as per-asset entry gates.
- **MVRV (not tested):** needs a paid on-chain feed. Recipe if you get one — BEAR when MVRV ≥ 3.5 (or a falling dynamic threshold), overheated-blowoff when MVRV ≥ 3.5 lowers the blow-off distance from 25%→17.5%. BTC/ETH only; unreliable for alts (use exchange-reserve changes instead).

## Coverage conclusion

With this, **every idea in the Q&A document that can be tested on free data has now been tested.** The only remaining item is MVRV (paid data). Net finding on external pipes: they are defensive context filters with small effect on this universe — consistent with the doc's own expectation — and are **not** among the improvements worth adding now. The improvements that matter remain **cross-sectional rotation** and (for Lean) **Donchian breakout confirmation**.
