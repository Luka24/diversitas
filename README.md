# Diversitas — Python ports + live dashboards

Two Python implementations of the **Diversitas** family of Pine Script trading
indicators, each with its own live Streamlit dashboard backed by Binance public
market data.

```
.
├── full/    # Diversitas Pro v3 — full model with conviction score (0-100)
└── lean/    # Diversitas Lean — minimalist variant, hard regime block
```

## Quick start

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Full dashboard (Pro v3 — conviction-based)
.venv/bin/streamlit run full/diversitas/dashboard.py --server.port 8501

# Lean dashboard (minimalist — entry gates as PASS/FAIL)
.venv/bin/streamlit run lean/diversitas/dashboard.py --server.port 8502
```

Open <http://localhost:8501> (Full) or <http://localhost:8502> (Lean).

## Backtest from terminal

```bash
# Full
cd full
../.venv/bin/python -m diversitas.backtest BTC 1500
../.venv/bin/python -m diversitas.backtest ETH 1000

# Lean
cd lean
../.venv/bin/python -m diversitas.backtest BTC 1500
../.venv/bin/python -m diversitas.backtest ETH 1000 --btc-filter
```

## Tests

```bash
.venv/bin/python -m pytest shared/tests/ -v        # 9 indicator tests
cd full && ../.venv/bin/python -m pytest diversitas/tests/ -v   # 9 strategy tests
cd lean && ../.venv/bin/python -m pytest diversitas/tests/ -v   # 12 strategy tests
```
Total: **30 tests**, all passing.

## What's the difference?

| Property | Full (Pro v3) | Lean |
|---|---|---|
| Entry decision | **Conviction score 0–100** (Trend 30 + Momentum 25 + Macro 20 + Volume 15 + DD 10) | **Hard AND** of 5–6 gates |
| Bear regime | Soft (+15 threshold penalty) | **Hard block** — no entries at all |
| Filters | Trackline, ADX, market structure (HH/LL), weekly EMA gate, 200 MA, BTC | Trackline (+ slope filter), 50 MA, 200 MA |
| State machines | 3 (raw / display / signal) with grace bars | 1 (signal) + display tint |
| `barsSinceSignal` reset | On BULL only | On both directions |
| Allocation | `conviction × volScale × trendPersistence` | `100 × volScale` when BULL |
| Default target vol | 25 % | 50 % |
| BTC filter default | ON | OFF |
| Weekend filter | Optional | None (24/7) |
| Pine source | 345 lines | 242 lines |

**When to use which:**
- **Full** — when you want gradual sizing, defensive behaviour in bear markets,
  and explicit cross-asset / cross-timeframe confirmation.
- **Lean** — when you want fewer parameters, transparent yes/no entries, and
  more aggressive sizing during clear trends.

## Data sources

Primary: **Binance** public REST (`/api/v3/klines`, no key, 6000 weight/min).
Fallback: **yfinance**.

See `API_RESEARCH.md` for the full evaluation.

## Documents

| File | Purpose |
|---|---|
| `full/STRATEGY_ANALYSIS.md` | Pine → Python mapping for Pro v3 |
| `full/AUDIT.md` | Line-by-line fidelity check vs Pine |
| `full/VALIDATION.md` | Tests + backtest + dashboard verification |
| `lean/STRATEGY_ANALYSIS.md` | Pine → Python mapping for Lean |
| `lean/VALIDATION.md` | Lean validation + diff vs Full |
| `lean/CLAUDE_PROMPT.md` | Re-runnable prompt to regenerate the Lean port |
| `API_RESEARCH.md` | Evaluation of 6 crypto data APIs |

## Project layout

```
DIVERSITAS/
├── API_RESEARCH.md
├── README.md
├── requirements.txt
├── conftest.py             # adds project root to sys.path for pytest
├── shared/                 # code used by BOTH variants — single source of truth
│   ├── indicators.py       # RSI, EMA, SMA, RMA, ADX, bars_since, stdev
│   ├── data_source.py      # Binance + yfinance fetching, weekly resample
│   └── tests/
│       └── test_indicators.py
├── full/
│   ├── AUDIT.md
│   ├── STRATEGY_ANALYSIS.md
│   ├── VALIDATION.md
│   ├── conftest.py         # adds full/ + project root to sys.path
│   ├── diversitas_pro_v3_200ma.pine
│   └── diversitas/         # variant-specific Python package
│       ├── config.py       # Config dataclass
│       ├── strategy.py     # imports from `shared`
│       ├── backtest.py
│       ├── dashboard.py
│       └── tests/
│           └── test_strategy.py
└── lean/
    ├── CLAUDE_PROMPT.md
    ├── STRATEGY_ANALYSIS.md
    ├── VALIDATION.md
    ├── conftest.py
    ├── diversitas_lean.pine
    └── diversitas/
        ├── config.py       # LeanConfig dataclass
        ├── strategy.py     # imports from `shared`
        ├── backtest.py
        ├── dashboard.py
        └── tests/
            └── test_strategy.py
```

Indicators and the data layer live in `shared/` — a bug fix in one place
benefits both variants. Each variant directory contains only what is
variant-specific (config, strategy, backtest, dashboard, tests). Both Python
packages are named `diversitas` but resolve to the correct subdir via the
`sys.path` setup in each `conftest.py` / `dashboard.py`.
