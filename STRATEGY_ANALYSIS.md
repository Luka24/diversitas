# Diversitas Pro v3 — strategy analysis (Pine → Python mapping)

Source: `diversitas_pro_v3_200ma.pine` (Pine Script v6, 345 lines).
Indicator type: overlay on price chart. Output: BULL / HEDGED / BEAR signal + conviction score + final allocation %.

---

## 1. Inputs (→ `Config` dataclass)

| Pine input | Default | Range | Group | Purpose |
|---|---|---|---|---|
| `trackPeriod` | 75 | 20–120 | Trackline | Kijun-sen window (bars) |
| `trackBuf` | 3.0 | 0–5 step 0.25 | Trackline | Buffer % around trackline |
| `rsiLen` | 14 | 5–30 | Momentum | RSI period |
| `rsiThresh` | 45.0 | 30–60 | Momentum | RSI threshold (used in conviction) |
| `emaFast` | 21 | 5–50 | Momentum | Fast EMA |
| `emaSlow` | 55 | 20–100 | Momentum | Slow EMA |
| `adxLen` | 14 | 5–30 | Momentum | ADX period |
| `structLen` | 20 | 10–50 | Momentum | Lookback for HH/LL structure |
| `wkEmaLen` | 21 | 10–50 | Macro | Weekly EMA |
| `wkSmaLen` | 30 | 10–50 | Macro | Weekly SMA |
| `useBtcFilter` | true | bool | Macro | Require BTC > daily EMA50 on alts |
| `volLen` | 20 | 5–50 | Volume | Volume MA |
| `volLookback` | 20 | 5–60 | Volatility | Stdev window (days) |
| `targetVol` | 25.0 | 5–60 step 5 | Volatility | Target portfolio vol % |
| `blowoffDist` | 25.0 | 10–40 step 1 | Volatility | Distance % above TL for blow-off |
| `volShockMul` | 1.5 | 1.2–3.0 step 0.1 | Volatility | Vol shock multiplier vs 50-bar avg |
| `confirmBars` | 3 | 1–5 | Anti-Churn | Bars rawState must hold |
| `reentryHold` | 15 | 1–30 | Anti-Churn | Re-entry lock |
| `graceBars` | 5 | 1–10 | Anti-Churn | Bars without green dot before displayState→2 |
| `exitGraceBars` | 3 | 1–5 | Anti-Churn | Bars below TL before exit |
| `convSmooth` | 5 | 1–7 | Anti-Churn | Conviction SMA |
| `skipWknd` | true | bool | Display | Ignore weekends |

---

## 2. Indicators

### 2.1 Trackline (Kijun-sen)
```
trackHigh    = rolling max(high, trackPeriod)
trackLow     = rolling min(low,  trackPeriod)
trackline    = (trackHigh + trackLow) / 2
trackRising  = trackline > trackline.shift(1)
bufAmt       = trackline * (trackBuf / 100)
aboveTL      = close > trackline + bufAmt
belowTL      = close < trackline - bufAmt
distPct      = (close - trackline) / trackline * 100
```
Python: `df['high'].rolling(trackPeriod).max()`, `df['low'].rolling(trackPeriod).min()`.

### 2.2 Basic indicators
- `rsiVal = RSI(close, rsiLen)` — Wilder's smoothing
- `fEMA = EMA(close, emaFast)`
- `sEMA = EMA(close, emaSlow)`
- `volMA = SMA(volume, volLen)`
- `volRatio = volume / volMA` (1.0 if volMA == 0)

### 2.3 200MA bear market filter
```
sma200          = SMA(close, 200)
sma200Falling   = sma200 < sma200.shift(1)
belowSma200     = close < sma200
bearMarketRegime = belowSma200 AND sma200Falling
```
Effect: adds +15 to dynamic threshold (does NOT hard-block).

### 2.4 ADX (normalized to its own mean)
Wilder's ADX, then `adxOK = adxVal > SMA(adxVal, 100)`. Relative trend strength.

```
up      = high.diff()
down    = -low.diff()
pDM     = up   where (up > down  AND up   > 0) else 0
nDM     = down where (down > up  AND down > 0) else 0
trur    = RMA(TR, len)
pDI     = 100 * RMA(pDM, len) / trur
nDI     = 100 * RMA(nDM, len) / trur
dx      = 100 * |pDI - nDI| / (pDI + nDI)
adxVal  = RMA(dx, len)
adxMean = SMA(adxVal, 100)
adxOK   = adxVal > adxMean
```
RMA = Wilder's moving average = EMA with alpha = 1/N.

### 2.5 Market structure (HH/LL)
```
barsLastHH    = bars since (high >= highest(high, structLen).shift(1))
barsLastLL    = bars since (low  <= lowest(low,   structLen).shift(1))
structureBull = barsLastLL > barsLastHH
```
"Time since last higher high vs lower low" — bullish if HH happened more recently.

### 2.6 Weekly macro (HTF resample)
```
wkEMA       = weekly EMA(close, wkEmaLen)
wkEMAprev   = wkEMA.shift(1)        # previous *weekly* bar
wkSMA       = weekly SMA(close, wkSmaLen)
wkClose     = weekly close
wkEmaRising = wkEMA > wkEMAprev
aboveWkSMA  = wkClose > wkSMA
htfBull     = wkClose > weekly EMA(close, 20)   # hard gate
```
Python: `df.resample('W').last()` for close, then compute on weekly index, then **forward-fill back to daily index** to align (mimics `request.security` repaint-free behaviour on closed bars).

### 2.7 BTC filter (cross-asset)
```
btcClose    = daily BTC close (COINBASE:BTCUSD)
btcEMA50    = daily EMA(btcClose, 50)
btcBull     = btcClose > btcEMA50
btcFilterOK = (not useBtcFilter) OR btcBull
```

### 2.8 Volatility
```
logRet       = ln(close / close.shift(1))
dailyStd     = stdev(logRet, volLookback)
annualVol    = dailyStd * sqrt(365) * 100
volSMA100    = SMA(annualVol, 100)
volStd100    = stdev(annualVol, 100)
volZ         = (annualVol - volSMA100) / volStd100
highVolRegime = volZ > 1.0
lowVolRegime  = volZ < -1.0
```

### 2.9 Drawdown (running peak from close)
```
peakPrice = cummax(close)
ddPct     = (close - peakPrice) / peakPrice * 100
```

### 2.10 Emergency triggers
```
blowoff   = distPct > blowoffDist AND rsiVal > 80
volShock  = annualVol > SMA(annualVol, 50) * volShockMul
```

---

## 3. Conviction score (0–100, weighted sum)

| Component | Weight | Formula (raw normalized 0–1, then × weight) |
|---|---|---|
| Trend | 30 | `clip((distPct + 5) / 10, 0, 1) + (0.1 if trackRising else 0)`, then `min(1)` |
| Momentum | 25 | `0.5 * clip((rsi-30)/35, 0, 1) + 0.5 * clip((emaSpread+2)/5, 0, 1)` where `emaSpread = (fEMA-sEMA)/sEMA*100` |
| Macro | 20 | `0.4*wkEmaRising + 0.4*aboveWkSMA + 0.2*(wkClose>wkEMA)` |
| Volume | 15 | `clip((volRatio-0.5)/1.5, 0, 1)` |
| DD brake | 10 | `clip((ddPct+30)/30, 0, 1) * (0.3 if trackRising else 1.0)` |

Then:
```
rawConviction = sum of all 5
conviction    = SMA(rawConviction, convSmooth)         # smoothed
```

### Trend persistence (used in allocation only)
```
trendPersistence = mean(close > close.shift(1) over last 10 bars)
```

### Final allocation (vol-targeting)
```
volScale   = min(1, targetVol / annualVol)             if annualVol > 0 else 1
finalAlloc = clip(conviction * volScale * trendPersistence, 0, 100)
```

### Dynamic threshold
```
bearMarketPenalty = 15.0 if bearMarketRegime else 0.0
baseThresh = 70 if highVolRegime else 55 if lowVolRegime else 60
dynamicThresh = min(85, baseThresh + bearMarketPenalty)
```

---

## 4. Green / Red dot

```
greenDot = aboveTL
       AND conviction >= dynamicThresh
       AND adxOK
       AND structureBull
       AND btcFilterOK
       AND htfBull
       AND not isWeekend

redDot   = belowTL AND not isWeekend
```

---

## 5. State machines (the tricky bit)

There are THREE state variables:
- `rawState`     ∈ {1=BULL, 2=NEUTRAL, 3=BEAR}  — instantaneous
- `displayState` ∈ {1=BULL, 2=HEDGED, 3=BEAR}    — UI background (uses grace bars)
- `signalState`  ∈ {1=BULL, 3=BEAR}              — actual trade signal (uses confirmBars + reentryHold)

All updates are **only on non-weekend bars** (when `skipWknd` is true).

### 5.1 rawState (per bar)
```
if belowTL:        rawState = 3
elif greenDot:     rawState = 1
elif aboveTL:      rawState = 2
# (else: hold previous, e.g. on exact buffer edge)
```

### 5.2 Counters maintained each (non-weekend) bar
```
greenAbsentCount += 1 if (aboveTL and not greenDot) else reset 0
belowCount       += 1 if belowTL else reset 0
rawHoldCount     += 1 if rawState == prevRaw else reset to 1
prevRaw          = rawState
```

### 5.3 displayState
```
if belowTL and belowCount >= exitGraceBars:
    displayState = 3
elif aboveTL and greenDot:
    displayState = 1
elif aboveTL and not greenDot and greenAbsentCount >= graceBars:
    displayState = 2
# else: hold previous
```

### 5.4 signalState (BULL/BEAR only)
Initial value = 3 (BEAR). Track `barsSinceSignal` (incremented every bar).

```
# BEAR conditions (checked first)
if rawState == 3 and belowCount >= exitGraceBars and signalState != 3:
    signalState = 3
elif blowoff and signalState == 1:
    signalState = 3
elif volShock and belowTL and signalState != 3:
    signalState = 3

# BULL condition (only if no BEAR fired this bar)
elif (rawState == 1
      and signalState != 1
      and rawHoldCount >= confirmBars
      and barsSinceSignal >= reentryHold):
    signalState = 1
    barsSinceSignal = 0
```

`signalChanged = signalState != prevSignal` (computed each bar, then `prevSignal = signalState`).

---

## 6. Outputs (for dashboard)

Replica of Pine status table (7 rows):

| Label | Value |
|---|---|
| DIVERSITAS | signal (BULL/BEAR), green/red bg |
| Regime | displayState (BULL/HEDGED/BEAR) |
| 200 MA | `BEAR MKT (thr +15)` / `BELOW` / `ABOVE` |
| Threshold | `{dynamicThresh} (conv {conviction})` |
| Trackline | `{trackline} RISING/FALLING` |
| Price vs TL | `{distPct}%` |
| Trend Quality | `{trendPersistence*100}%` |

Plus on chart:
- Trackline line (green if rising, red if falling)
- 200 MA (orange)
- Green dots below bar / red dots above bar
- BULL/BEAR labels on signal changes
- Background tint by displayState

---

## 7. Python implementation notes

1. **Vectorize everything except state machines.** State machines need a single forward pass (Python loop over `df.itertuples()` or numba).
2. **Weekly resample correctness.** Pine's `request.security` returns the *current* weekly value during the live week, but only finalized weekly bars are stable. For backtesting, use `resample('W-MON', closed='left', label='left').last()` and forward-fill — this matches what Pine sees on a closed weekly bar.
3. **BTC filter.** Fetch BTC daily separately, align on date index, forward-fill.
4. **Weekend handling.** If skipWknd, set `isWeekend = day in {Sat, Sun}`. Crypto markets trade 24/7 so weekends still have candles — the filter only suppresses state transitions.
5. **Wilder's RMA.** `pandas.Series.ewm(alpha=1/N, adjust=False).mean()`.
6. **First-bar edge cases.** Pine fills `na` for early bars; we use `min_periods=N` and accept NaN until enough history.

---

## 8. Pine constructs → Python

| Pine | Python (pandas) |
|---|---|
| `ta.highest(high, N)` | `df['high'].rolling(N).max()` |
| `ta.lowest(low, N)` | `df['low'].rolling(N).min()` |
| `ta.rsi(close, N)` | Wilder RSI (manual) |
| `ta.ema(close, N)` | `close.ewm(span=N, adjust=False).mean()` |
| `ta.sma(close, N)` | `close.rolling(N).mean()` |
| `ta.stdev(x, N)` | `x.rolling(N).std(ddof=0)` (Pine uses population stdev) |
| `ta.rma(x, N)` | `x.ewm(alpha=1/N, adjust=False).mean()` |
| `ta.barssince(cond)` | custom: cumulative count since True |
| `ta.change(x)` | `x.diff()` |
| `math.sum(x, N)` | `x.rolling(N).sum()` |
| `request.security(tf, expr)` | resample + ffill |
| `var int x = N` | initialize once before loop |
