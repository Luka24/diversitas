# Diversitas Lean — strategy analysis (Pine → Python)

Source: `diversitas_lean.pine` (242 lines, Pine Script v6).
Filozofija: ohrani le, kar se je v Full izkazalo za vredno; izpusti vse dodatke.

---

## 1. Filozofija (iz komentarja v Pine, vrstice 4–21)

Lean obdrži:
- Kijun trackline (smer)
- 50 MA (trend confirmation) + 200 MA (regime filter, **hard block**)
- Blow-off top detection (izhod)
- Vol shock (izhod)
- Anti-churn state machine
- Vol-targeted sizing (opcionalno)

Lean izpusti:
- Conviction score (0–100 sistem)
- ADX
- Market structure (HH/LL)
- Weekly higher-timeframe gate
- On-chain / macro pipes
- BTC filter privzeto OFF

Cilj: **manj parametrov, manj filtrov, bolj transparenten signal.**

---

## 2. Inputi (→ `LeanConfig` dataclass)

| Pine input | Default | Group | Pomen |
|---|---|---|---|
| `trackPeriod` | 75 | Core | Kijun window |
| `trackBuf` | 3.0 | Core | Buffer % |
| `maMedLen` | 50 | MA | Trend MA — cena MORA biti nad njo |
| `maLongLen` | 200 | MA | Regime MA — bear filter |
| `maSlope` | 5 | MA | Lookback za regime MA slope (`maLong > maLong[5]`) |
| `blowoffDist` | 25.0 | Exits | Razdalja % nad TL za blowoff |
| `rsiLen` | 14 | Exits | RSI za blowoff |
| `volShockMul` | 1.5 | Exits | Vol shock multiplier |
| `volLookback` | 20 | Exits | Vol stdev window |
| `trackSlopeBars` | 10 | Range | Trackline mora biti rising preko N barov |
| `minDistEntry` | 0.0 | Range | Dodaten min distance % nad TL za entry (default 0) |
| `confirmBars` | 3 | Anti-churn | bullHoldCount ≥ N |
| `reentryHold` | 15 | Anti-churn | barsSinceSignal ≥ N |
| `exitGraceBars` | 3 | Anti-churn | belowCount ≥ N pred BEAR |
| `useVolSizing` | true | Sizing | Vklopi vol-target |
| `targetVol` | 50.0 | Sizing | Target portfolio vol % |
| `useBtcFilter` | false | Optional | BTC > daily EMA50 |

---

## 3. Indikatorji

### Trackline (enako kot Full)
```
trackHigh         = highest(high, trackPeriod)
trackLow          = lowest(low,  trackPeriod)
trackline         = (trackHigh + trackLow) / 2
trackRising       = trackline > trackline.shift(1)               # 1-bar
trackRisingWindow = trackline > trackline.shift(trackSlopeBars)  # 10-bar slope (range filter)
bufAmt            = trackline * (trackBuf / 100)
aboveTL           = close > trackline + bufAmt
belowTL           = close < trackline - bufAmt
distPct           = (close - trackline) / trackline * 100
```

### Moving averages
```
maMed         = SMA(close, 50)
maLong        = SMA(close, 200)
maLongRising  = maLong > maLong.shift(5)        # slope!
maLongFalling = maLong < maLong.shift(5)
aboveMaLong   = close > maLong
bearRegime    = !aboveMaLong AND maLongFalling
regimeOK      = !bearRegime
```
**Razlika:** v Lean je slope merjen preko 5 barov (Full je 1 bar `[1]`). Bolj stabilen filter.

### Volatility (enako)
```
logRet       = ln(close / close.shift(1))
dailyStd     = stdev(logRet, 20)
annualVol    = dailyStd * sqrt(365) * 100
```

### BTC filter (enako, le default false)
```
btcClose    = daily BTC close
btcEMA50    = daily EMA(btcClose, 50)
btcFilterOK = !useBtcFilter OR (btcClose > btcEMA50)
```

---

## 4. Entry / exit conditions

```
distEntryOK    = distPct >= (trackBuf + minDistEntry)
bullCondition  = aboveTL
                AND close > maMed
                AND trackRisingWindow
                AND distEntryOK
                AND regimeOK
                AND btcFilterOK

trendBreak     = belowTL
blowoff        = distPct > blowoffDist AND rsi > 80
volShock       = annualVol > SMA(annualVol, 50) * volShockMul AND belowTL
```

`bullCondition` je hard AND — nobenega "delno OK" scoringa. Ali so vsi pogoji izpolnjeni ali ne.

---

## 5. State machine

**Spremenljivke:**
```
signalState     ∈ {1=BULL, 3=BEAR}    — privzeto 3
barsSinceSignal = 999 (init)
belowCount      = 0
bullHoldCount   = 0
displayState    ∈ {1=BULL, 2=HEDGED, 3=BEAR} — privzeto 3
```

**Vsak bar (NI weekend filtra, teče vsak dan):**
```python
barsSinceSignal += 1

# counters
belowCount     = belowCount + 1 if belowTL else 0
bullHoldCount  = bullHoldCount + 1 if bullCondition else 0   # reset na 0 (NE 1!)

# BEAR exits (only when currently BULL) — instant
if signalState == 1:
    if trendBreak and belowCount >= exitGraceBars:
        signalState, barsSinceSignal = 3, 0   # reset!
    elif blowoff:
        signalState, barsSinceSignal = 3, 0   # reset!
    elif volShock:
        signalState, barsSinceSignal = 3, 0   # reset!

# BULL entry (only when currently BEAR) — confirmation + re-entry lock
elif signalState == 3:
    if bullCondition and bullHoldCount >= confirmBars and barsSinceSignal >= reentryHold:
        signalState, barsSinceSignal = 1, 0

# Display state — no grace bars for BULL/NEUTRAL transitions
if belowTL and belowCount >= exitGraceBars:
    displayState = 3
elif aboveTL and bullCondition:
    displayState = 1
elif aboveTL and not bullCondition:
    displayState = 2
```

**Ključne razlike od Full:**
1. `barsSinceSignal := 0` se izvede **tako na BULL kot na BEAR** (Full le na BULL).
2. `bullHoldCount` se resetira na **0** kadar ni bullCondition (Full's rawHoldCount na 1 ob state change).
3. **NI** ločenega rawState — signalState se direktno iz bullCondition + grace.
4. Display state je evaluiran vsak bar brez `greenAbsentCount` (Full uses grace bars for displayState NEUTRAL).
5. BEAR exits najprej, in vsi resetirajo barsSinceSignal — naslednji entry je vedno reentryHold stran.

---

## 6. Sizing (additive — applied AFTER signal)

```
volScale    = min(1.0, targetVol / annualVol)   if (useVolSizing AND annualVol > 0) else 1.0
targetAlloc = round(100 * volScale)             if signalState == 1 else 0
```

Allocation je **100 % vol-scaled** ko BULL, **0 %** ko BEAR. Brez conviction score, brez trend persistence.
Default `targetVol = 50%` — bolj agresivno od Full (25 %).

---

## 7. Outputs (replica Pine table)

| Vrstica | Vsebina |
|---|---|
| Title | "DIVERSITAS LEAN" + signal (BULL/BEAR) |
| Regime | displayState (BULL/HEDGED/BEAR) |
| Allocation | `{targetAlloc}%` |
| Regime MA | `BEAR (blocked)` / `ABOVE` / `BELOW` |
| Trend MA | `ABOVE` / `BELOW` (50 MA) |
| Trackline | `{trackline} RISING/FLAT-FALLING` |
| Price vs TL | `{distPct}%` |

---

## 8. Pine → Python mapping

| Pine | Python (pandas) |
|---|---|
| `ta.highest/lowest(x, N)` | `rolling(N).max()/min()` |
| `ta.sma(close, N)` | `rolling(N).mean()` |
| `ta.ema(close, N)` | `ewm(span=N, adjust=False).mean()` |
| `ta.rsi(close, N)` | Wilder RSI (manual; reuse `indicators.rsi`) |
| `ta.stdev(x, N)` | `rolling(N).std(ddof=0)` (population) |
| `x[N]` | `x.shift(N)` |
| `x[1]` (previous bar) | `x.shift(1)` |
| `request.security("COINBASE:BTCUSD", "D", expr)` | `fetch BTC` + reindex + ffill |
| State machine | forward pass over `df.itertuples()` |

---

## 9. Python implementation plan

Struktura (mirrors `full/`):
```
lean/diversitas/
├── config.py        # LeanConfig dataclass
├── data_source.py   # (copy of full/) Binance + yfinance
├── indicators.py    # (copy of full/) RSI, SMA, EMA, stdev
├── strategy.py      # NEW: lean compute_features + run_state_machine + summary
├── backtest.py      # NEW: lean CLI
├── dashboard.py     # NEW: lean Streamlit (simpler than full)
└── tests/
    ├── test_indicators.py  # (copy)
    └── test_strategy.py    # NEW: lean state machine + bullCondition tests
```

Splošne zahteve enako kot v full:
- Vse v pandas/numpy
- State machine v eni forward pass
- Test za vsak prehod (BULL/BEAR/blowoff/volShock/bear regime block)
- Backtest CLI ki izpiše signal stats + naive equity vs B&H
