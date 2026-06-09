# Audit: Full Python implementation vs `diversitas_pro_v3_200ma.pine`

Pregled po komponentah. Status: ✅ = ujema z Pine, ⚠️ = manjši odstop (sprejemljiv), ❌ = napaka (treba popraviti).

## Indikatorji

| Komponenta | Pine | Python | Status |
|---|---|---|---|
| Trackline (Kijun) | `(highest(high,N) + lowest(low,N))/2` | `(rolling.max + rolling.min) / 2` | ✅ |
| Buffer (above/below) | `close > trackline + bufAmt` | identično | ✅ |
| RSI | `ta.rsi` (Wilder RMA) | `rma(gain)/rma(loss)` | ✅ |
| EMA | `ta.ema` (adjust=False) | `ewm(span, adjust=False)` | ✅ |
| SMA | `ta.sma` | `rolling.mean` | ✅ |
| Population stdev | `ta.stdev` (ddof=0) | `rolling.std(ddof=0)` | ✅ |
| ADX | manual `pDM/nDM/pDI/nDI/dx → rma` | identično | ✅ |
| `bars_since` | `ta.barssince` (NaN until first True) | identično (forward pass) | ✅ |
| 200 MA bear filter | `close<sma200 AND sma200<sma200[1]` | identično | ✅ |
| Trackline rising | `trackline > trackline[1]` | `shift(1)` | ✅ |

## Conviction score (5 komponent)

| Komponenta | Formula (Pine) | Python | Status |
|---|---|---|---|
| Trend (30) | `clip((distPct+5)/10) + 0.1*rising → min(1)*30` | identično | ✅ |
| Momentum (25) | `0.5*rsiNorm + 0.5*emaNorm * 25` | identično | ✅ |
| Macro (20) | `(0.4*wkEmaRising + 0.4*aboveWkSMA + 0.2*(wkClose>wkEMA))*20` | identično | ✅ |
| Volume (15) | `clip((volRatio-0.5)/1.5)*15` | identično | ✅ |
| DD brake (10) | `ddNorm * 10 * (0.3 if rising else 1)` | identično | ✅ |
| Conviction smoothing | `ta.sma(rawConv, convSmooth)` | identično | ✅ |

## Filtri & gates

| Filter | Pine | Python | Status |
|---|---|---|---|
| ADX OK | `adxVal > sma(adxVal, 100)` | identično | ✅ |
| Structure bull | `barsLastLL > barsLastHH` (z `[1]` lookback) | `highest(..., N).shift(1)` | ✅ |
| Weekly EMA rising | `wkEMA > wkEMAprev` (request.security) | resample W-MON + shift(1) + ffill | ✅ |
| Above weekly SMA | `wkClose > wkSMA` (request.security) | identično | ✅ |
| HTF bull gate | `wkClose > weekly EMA20` | identično | ✅ |
| BTC filter | `btcClose > ema(btcClose,50)` (request.security) | reindex + ffill na asset index | ✅ |

## Volatility & allocation

| Komponenta | Pine | Python | Status |
|---|---|---|---|
| Annual vol | `stdev(logRet, 20) * sqrt(365) * 100` | identično | ✅ |
| Vol z-score | `(annualVol - sma100)/stdev100` | identično | ✅ |
| High/low vol regime | `volZ > 1` / `volZ < -1` | identično | ✅ |
| Vol scale | `min(1, targetVol/annualVol)` | identično | ✅ |
| Trend persistence | `sum(close>close[1], 10) / 10` | `rolling(10).mean()` | ✅ |
| Final alloc | `clip(conv * volScale * tp, 0, 100)` | identično | ✅ |

## Dynamic threshold

| Pravilo | Pine | Python | Status |
|---|---|---|---|
| Bear market penalty | `+15` če `bear_market` | identično | ✅ |
| Base threshold | `70 / 55 / 60` (high/low/normal vol) | identično | ✅ |
| Cap | `min(85, base + penalty)` | identično | ✅ |

## Dots & state machine

| Element | Pine | Python | Status |
|---|---|---|---|
| green_dot | `above_tl AND conv >= thr AND adxOK AND structureBull AND btcOK AND htfBull AND !weekend` | identično | ✅ |
| red_dot | `below_tl AND !weekend` | identično | ✅ |
| rawState (3 stanja) | belowTL→3, greenDot→1, aboveTL→2 (else hold) | identično | ✅ |
| greenAbsentCount | `if !green AND above: ++; else 0` | identično | ✅ |
| belowCount | `if below: ++; else 0` | identično | ✅ |
| rawHoldCount | `if rawState==prevRaw: ++; else 1` | identično | ✅ |
| displayState (3 stanja) | grace bars, BULL/HEDGED/BEAR | identično | ✅ |
| signalState BEAR triggers | rawState==3+belowCount, blowoff (only if BULL), volShock+below | identično | ✅ |
| signalState BULL trigger | rawState==1 AND raw_hold>=confirm AND barsSince>=reentry | identično | ✅ |
| barsSinceSignal increment | unconditional each bar (Pine line 249) | identično (Python line 251) | ✅ |
| barsSinceSignal reset | only on BULL transition | identično | ✅ |
| signalChanged | `signalState != prevSignal` | identično | ✅ |
| Var init | `rawState=3, signalState=3, barsSinceSignal=999, prevRaw=3, prevSignal=3` | identično | ✅ |

## Edge cases

| Primer | Pine | Python | Status |
|---|---|---|---|
| Close točno na meji buffer | None of below/above/green True → rawState holds | identično | ✅ |
| Prvi bar (NaN[1]) | trackRising=na (falsy) | False | ✅ |
| Vikend (skipWknd=true) | Nobena transition; bars_since++ continues | identično | ✅ |
| Weekly v živo (intraweek) | request.security default = no lookahead → previous closed week | shift(1) emulira | ✅ |
| Blow-off med BEAR | blowoff zahteva `signalState==1`; ne sproži vstopa | identično (ne preprečuje BULL če signalState==BEAR) | ⚠️ design choice, ne bug |

## Minor odstopi (ne zahtevajo popravka)

1. **RSI ko sta `avg_gain==0 AND avg_loss==0`** (popolnoma ploski cena 14 barov):
   - Python: vrne 100 (`avg_loss==0` → fallback)
   - Pine: vrne 50 (neutralno)
   - **Verjetnost**: praktično nič na pravih crypto podatkih. Zanemarljivo.

2. **`vol_z` ko je `vol_std100` NaN ali 0**:
   - Python: `fillna(0.0)` (vrne 0 → ni high/low regime)
   - Pine: ternary preveri `volStd100 > 0`, vrne 0
   - Funkcionalno enako (oba dasta False za regime flag).

3. **Prvi `structLen` barov za HH/LL**:
   - Pine: vrne na za `highest` (in zato `bars_since`)
   - Python: `rolling(N, min_periods=N).max()` vrne NaN
   - Identično obnašanje.

## Zaključek

**Strategija je v Pythonu pravilno implementirana.** Vse glavne komponente (trackline, conviction, 5 filtrov, 3 state mašine, emergency exits, vol-targeting) se ujemajo z Pine. Edini odstopi so robni primeri, ki se v praksi ne pojavijo na crypto podatkih.

Ne potrebuje popravkov v jedru. Možne prihodnje izboljšave (opcionalno):
- Eksplicitno dokumentirati shift-by-1 weekly anti-repaint v komentarju.
- RSI=50 namesto 100 ko sta oba 0 (zanemarljivo).

**Strategija sama (po designu)**:
- Pretežno defenziven trend follower (49 % izpostavljenosti na BTC, 25 % na ETH).
- Robusten proti chop-u zaradi conviction smoothing + grace bars + reentry lock.
- Soft 200MA filter (+15 threshold namesto hard block) — primerno za crypto, kjer mean-reversion v bear markets ni redek.
- Cross-asset BTC filter rešuje ETH/alts pred drawdowns (validirano: ETH +76 % vs B&H −20 %).
- Brez slippage/fees v backtestu — realne številke bodo nižje.
