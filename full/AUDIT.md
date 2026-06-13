# Full audit — `diversitas_pro_v3_200ma.pine` vs `full/diversitas/`

Vrstica-za-vrstico primerjava med Pine virom (345 vrstic) in Python portom.
Status: ✅ = identično, ⚠️ = manjši odstop (sprejemljiv, dokumentiran),
❌ = napaka (treba popraviti), 🐛 = napaka v **Pine viru sami** (ne v portu).

**Glavni zaključek:**
- **0 napak v Python portu** strategije.
- **1 dejanska napaka v Pine viru sami** (`rsiThresh` input — mrtva koda).
- **2 sprejemljiva minor odstopa** (NaN handling, oba brez vpliva na signal).
- **2 oblikovni opazki** o Pine logiki (ne bugi, ampak vredne dokumentacije).

---

## 1. Inputs — Pine 18–54 vs `config.py`

| # | Pine input | Default | Python (Config) | Default | Status |
|---|---|---|---|---|---|
| 1 | `trackPeriod` | 75 | `track_period` | 75 | ✅ |
| 2 | `trackBuf` | 3.0 | `track_buf_pct` | 3.0 | ✅ |
| 3 | `rsiLen` | 14 | `rsi_len` | 14 | ✅ |
| 4 | `rsiThresh` | 45.0 | — | — | 🐛 (Pine dead code; Python opušča — glej §11) |
| 5 | `emaFast` | 21 | `ema_fast` | 21 | ✅ |
| 6 | `emaSlow` | 55 | `ema_slow` | 55 | ✅ |
| 7 | `adxLen` | 14 | `adx_len` | 14 | ✅ |
| 8 | `structLen` | 20 | `struct_len` | 20 | ✅ |
| 9 | `wkEmaLen` | 21 | `wk_ema_len` | 21 | ✅ |
| 10 | `wkSmaLen` | 30 | `wk_sma_len` | 30 | ✅ |
| 11 | `useBtcFilter` | true | `use_btc_filter` | True | ✅ |
| 12 | `volLen` | 20 | `vol_len` | 20 | ✅ |
| 13 | `volLookback` | 20 | `vol_lookback` | 20 | ✅ |
| 14 | `targetVol` | 25.0 | `target_vol_pct` | 25.0 | ✅ |
| 15 | `blowoffDist` | 25.0 | `blowoff_dist_pct` | 25.0 | ✅ |
| 16 | `volShockMul` | 1.5 | `vol_shock_mul` | 1.5 | ✅ |
| 17 | `confirmBars` | 3 | `confirm_bars` | 3 | ✅ |
| 18 | `reentryHold` | 15 | `reentry_hold` | 15 | ✅ |
| 19 | `graceBars` | 5 | `grace_bars` | 5 | ✅ |
| 20 | `exitGraceBars` | 3 | `exit_grace_bars` | 3 | ✅ |
| 21 | `convSmooth` | 5 | `conv_smooth` | 5 | ✅ |
| 22 | `skipWknd` | true | `skip_weekend` | True | ✅ |
| — | `showDots`/`showBG`/`showLabels` | true | (UI only — dashboard) | — | ✅ |

### 🐛 NAPAKA V PINE SAMI: `rsiThresh` je mrtva koda

Pine vrstica 23 deklarira:
```pine
rsiThresh = input.float(45.0, "RSI Threshold", minval=30.0, maxval=60.0, group="Momentum")
```

Vendar `rsiThresh` ni nikjer uporabljen v `.pine` datoteki. Verifikacija
z `grep -n rsiThresh full/diversitas_pro_v3_200ma.pine`:
```
23:rsiThresh = input.float(45.0, "RSI Threshold", ...)
```
**Samo 1 zadetek — deklaracija. Brez kakršnekoli uporabe.**

Pri `blowoff` (vrstica 143) je RSI threshold **hardcoded na 80**, ne
`rsiThresh`:
```pine
blowoff = distPct > blowoffDist and rsiVal > 80   // ← 80 ni rsiThresh!
```

**Posledica:** input v TradingView UI dovoli uporabniku spreminjati
"RSI Threshold" parameter (privzeto 45), ampak spreminjanje nima
nobenega učinka na signal. Zavajajoča UI control.

**Stanje Python porta (po commitu, ki odstrani polje):**
Python `Config` v `full/diversitas/config.py` polja `rsi_thresh` **ne
deklarira več**. Komentar v viru opozarja na Pine dead-input napako za
prihodnje prevajalce. To je edini načrtovani odstop od 1:1 mapinga
inputov — odstranili smo polje, ki bi tudi v Pythonu bilo mrtvo.

**Priporočilo za Pine vir:** `rsiThresh` morali bodisi uporabiti (npr.
`rsiVal > rsiThresh` v blowoff namesto hardcoded `80`), bodisi izbrisati.
Trenutno je zavajajoč UI element v TradingView.

---

## 2. Weekend mask (Pine 57)

| Pine | Python | Status |
|---|---|---|
| `isWeekend = skipWknd and (dayofweek == saturday or dayofweek == sunday)` | `if cfg.skip_weekend: dow = df.index.dayofweek; is_weekend = (dow == 5) \| (dow == 6)` (Mon=0…Sun=6) | ✅ |

---

## 3. Indicators — Pine 65–144 vs `strategy.py:51-140`

### 3.1 Trackline (Pine 65–72)
| Pine | Python | Status |
|---|---|---|
| `trackHigh = ta.highest(high, trackPeriod)` | `ind.highest(high, cfg.track_period)` | ✅ |
| `trackLow = ta.lowest(low, trackPeriod)` | `ind.lowest(low, cfg.track_period)` | ✅ |
| `trackline = (trackHigh + trackLow) / 2.0` | enako | ✅ |
| `trackRising = trackline > trackline[1]` | `df["trackline"] > df["trackline"].shift(1)` | ✅ |
| `bufAmt = trackline * (trackBuf / 100.0)` | enako | ✅ |
| `aboveTL = close > (trackline + bufAmt)` | enako | ✅ |
| `belowTL = close < (trackline - bufAmt)` | enako | ✅ |
| `distPct = (close - trackline) / trackline * 100` | enako | ✅ |

### 3.2 Osnovni momentum (Pine 74–78)
| Pine | Python | Status |
|---|---|---|
| `rsiVal = ta.rsi(close, rsiLen)` | `ind.rsi(close, cfg.rsi_len)` (Wilder) | ✅ |
| `fEMA = ta.ema(close, emaFast)` | `ind.ema(close, cfg.ema_fast)` | ✅ |
| `sEMA = ta.ema(close, emaSlow)` | `ind.ema(close, cfg.ema_slow)` | ✅ |
| `volMA = ta.sma(volume, volLen)` | `ind.sma(volume, cfg.vol_len)` | ✅ |
| `volRatio = volMA > 0 ? volume / volMA : 1.0` | `(volume / vol_ma).where(vol_ma > 0, 1.0)` | ✅ |

### 3.3 200 MA bear filter (Pine 84–87)
| Pine | Python | Status |
|---|---|---|
| `sma200 = ta.sma(close, 200)` | `ind.sma(close, 200)` (hardcoded 200) | ✅ |
| `sma200Falling = sma200 < sma200[1]` | `sma200 < sma200.shift(1)` | ✅ |
| `belowSma200 = close < sma200` | `close < sma200` | ✅ |
| `bearMarketRegime = belowSma200 and sma200Falling` | `df["below_sma200"] & df["sma200_falling"]` | ✅ |

### 3.4 ADX (Pine 90–104)
Pine custom function `calcADX(len)`:
```
up = ta.change(high)
down = -ta.change(low)
pDM = up > down and up > 0 ? up : 0
nDM = down > up and down > 0 ? down : 0
trur = ta.rma(ta.tr, len)
pDI = 100 * ta.rma(pDM, len) / trur
nDI = 100 * ta.rma(nDM, len) / trur
dx = sum == 0 ? 0 : 100 * |pDI - nDI| / sum
ta.rma(dx, len)
```

Python `shared/indicators.py:adx()`:
```python
up = high.diff(); down = -low.diff()
p_dm = where((up > down) & (up > 0), up, 0)
n_dm = where((down > up) & (down > 0), down, 0)
trur = rma(tr, length)
p_di = 100 * rma(p_dm, length) / trur
n_di = 100 * rma(n_dm, length) / trur
dx = (100 * |p_di - n_di| / sum).fillna(0)
return rma(dx, length)
```
✅ vse formule identične

Plus normalizacija:
| Pine | Python | Status |
|---|---|---|
| `adxMean = ta.sma(adxVal, 100)` | `ind.sma(adx_val, 100)` | ✅ |
| `adxOK = adxVal > adxMean` | `adx_val > df["adx_mean"]` | ✅ |

### 3.5 Market structure (Pine 107–109)
| Pine | Python | Status |
|---|---|---|
| `barsLastHH = ta.barssince(high >= ta.highest(high, structLen)[1])` | `bars_since(high >= ind.highest(high, struct_len).shift(1))` | ✅ |
| `barsLastLL = ta.barssince(low <= ta.lowest(low, structLen)[1])` | `bars_since(low <= ind.lowest(low, struct_len).shift(1))` | ✅ |
| `structureBull = barsLastLL > barsLastHH` | enako | ✅ |

### 3.6 Weekly macro (Pine 112–117) — Subtle alignment
| Pine | Python | Status |
|---|---|---|
| `wkEMA = request.security(sym, "W", ta.ema(close, wkEmaLen))` | `_align_weekly(ind.ema(weekly["close"], cfg.wk_ema_len), df.index)` | ✅ |
| `wkEMAprev = request.security(sym, "W", ta.ema(close, wkEmaLen)[1])` | `_align_weekly(wk_ema.shift(1), df.index)` | ✅ |
| `wkSMA = request.security(sym, "W", ta.sma(close, wkSmaLen))` | analog | ✅ |
| `wkClose = request.security(sym, "W", close)` | `_align_weekly(weekly["close"], df.index)` | ✅ |
| `wkEmaRising = wkEMA > wkEMAprev` | `wk_ema_aligned > wk_ema_prev_aligned` | ✅ |
| `aboveWkSMA = wkClose > wkSMA` | enako | ✅ |

**Pomembna podrobnost o weekly alignment:**
`_align_weekly` v Pythonu naredi `weekly_value.shift(1)` PREJ kot reindex-a
na daily. Pine `request.security` z default `lookahead=barmerge.lookahead_off`
(Pine v6 default) vrne vrednost iz **zadnje zaprte** tedenske sveče (NE
trenutno-v-poteku). Python `shift(1)` to emulira: za vsako dnevno datumno
oznako vrne prejšnjo tedensko vrednost. ✅ Anti-repaint match.

### 3.7 BTC cross-asset filter (Pine 120–123)
| Pine | Python | Status |
|---|---|---|
| `btcClose = request.security("COINBASE:BTCUSD", "D", close)` | sprejme `btc_daily` parameter, uporabi `btc_daily["close"]` | ✅ |
| `btcEMA50 = request.security("COINBASE:BTCUSD", "D", ta.ema(close, 50))` | `ind.ema(btc_close, 50)` (hardcoded 50) | ✅ |
| `btcBull = btcClose > btcEMA50` | enako | ✅ |
| `btcFilterOK = not useBtcFilter or btcBull` | če `use_btc_filter AND btc_daily provided`: `btc_bull`; sicer `True` | ⚠️ |

⚠️ **Manjši odstop:** če `use_btc_filter=True` AMPAK `btc_daily=None`,
Python varno preskoči (vrne `True`). Pine vedno `request.security`. Brez
funkcionalne razlike.

### 3.8 Volatility (Pine 126–135)
| Pine | Python | Status |
|---|---|---|
| `logRet = math.log(close / close[1])` | `np.log(close / close.shift(1))` | ✅ |
| `dailyStd = ta.stdev(logRet, volLookback)` | `ind.stdev_pop(log_ret, cfg.vol_lookback)` (ddof=0) | ✅ |
| `annualVol = dailyStd * math.sqrt(365) * 100` | enako | ✅ |
| `volSMA100 = ta.sma(annualVol, 100)` | enako | ✅ |
| `volStd100 = ta.stdev(annualVol, 100)` | enako | ✅ |
| `volZ = volStd100 > 0 ? (annualVol - volSMA100) / volStd100 : 0.0` | `((annual_vol - vol_sma100) / vol_std100.replace(0, NaN)).fillna(0.0)` | ⚠️ |
| `highVolRegime = volZ > 1.0` | enako | ✅ |
| `lowVolRegime = volZ < -1.0` | enako | ✅ |

⚠️ **Manjši odstop pri `volZ`:**
- Pine: ternary preveri `volStd100 > 0`, sicer vrne 0.
- Python: računa division, kjer je 0 → NaN, nato `fillna(0)`.
- Razlika: kadar je `annualVol` ali `volSMA100` NaN (zgodnji bari), Pine
  vrne ali na/0 odvisno od `volStd100`; Python vrne 0 zaradi `fillna`.
- Funkcionalno enako za `high_vol_regime`/`low_vol_regime` (NaN/0 > 1 = False
  vedno).

### 3.9 Drawdown (Pine 138–140)
| Pine | Python | Status |
|---|---|---|
| `var float peakPrice = na; peakPrice := na(peakPrice) ? close : math.max(peakPrice, close)` | `close.cummax()` | ✅ |
| `ddPct = (close - peakPrice) / peakPrice * 100` | enako | ✅ |

**Opomba o vedenju:** peakPrice se računa od prve dostopne sveče (NE od
fiksnega okna). Spremenljiv backtest window → spremenljiv peak. Tako v Pine
kot v Python. Pričakovano vedenje.

### 3.10 Emergency triggers (Pine 143–144)
| Pine | Python | Status |
|---|---|---|
| `blowoff = distPct > blowoffDist and rsiVal > 80` | `(dist_pct > blowoff_dist_pct) & (rsi > 80)` | ✅ |
| `volShock = annualVol > ta.sma(annualVol, 50) * volShockMul` | `annual_vol > (vol_avg50 * vol_shock_mul)` | ✅ |

**Pomembno:** Pine `volShock` NE vključuje `belowTL` (drugače kot Lean!).
`belowTL` check je v BEAR exit conditions (Pine vrstica 257), ne v
spremenljivki sami. Python ✓ matches.

---

## 4. Conviction score (Pine 150–175) vs `strategy.py:142-169`

### Trend score (0–30)
| Pine | Python | Status |
|---|---|---|
| `trendRaw = max(0, min(1, (distPct + 5) / 10))` | `((dist_pct + 5) / 10).clip(0, 1)` | ✅ |
| `trendBonus = trackRising ? 0.1 : 0.0` | `track_rising.astype(float) * 0.1` | ✅ |
| `trendScore = min(1, trendRaw + trendBonus) * 30` | `(trend_raw + trend_bonus).clip(upper=1) * 30` | ✅ |

### Momentum score (0–25)
| Pine | Python | Status |
|---|---|---|
| `rsiNorm = max(0, min(1, (rsiVal - 30) / 35))` | `((rsi - 30) / 35).clip(0, 1)` | ✅ |
| `emaSpread = (fEMA - sEMA) / sEMA * 100` | enako | ✅ |
| `emaNorm = max(0, min(1, (emaSpread + 2) / 5))` | `((ema_spread + 2) / 5).clip(0, 1)` | ✅ |
| `momScore = (rsiNorm * 0.5 + emaNorm * 0.5) * 25` | enako | ✅ |

### Macro score (0–20)
| Pine | Python | Status |
|---|---|---|
| `macroScore = ((wkEmaRising ? 0.4 : 0) + (aboveWkSMA ? 0.4 : 0) + (wkClose > wkEMA ? 0.2 : 0)) * 20` | `(wk_ema_rising * 0.4 + above_wk_sma * 0.4 + wk_close_above_wk_ema * 0.2) * 20` | ✅ |

### Volume score (0–15)
| Pine | Python | Status |
|---|---|---|
| `volNorm = max(0, min(1, (volRatio - 0.5) / 1.5))` | enako | ✅ |
| `volScore = volNorm * 15` | enako | ✅ |

### DD brake (0–10)
| Pine | Python | Status |
|---|---|---|
| `ddNorm = max(0, min(1, (ddPct + 30) / 30))` | enako | ✅ |
| `ddPenalty = trackRising ? 0.3 : 1.0` | `np.where(track_rising, 0.3, 1.0)` | ✅ |
| `ddScore = ddNorm * 10 * ddPenalty` | enako | ✅ |

### Smoothing
| Pine | Python | Status |
|---|---|---|
| `rawConviction = trendScore + momScore + macroScore + volScore + ddScore` | enako | ✅ |
| `conviction = ta.sma(rawConviction, convSmooth)` | `ind.sma(raw_conviction, conv_smooth)` | ✅ |

**Skupno:** 30 + 25 + 20 + 15 + 10 = 100. Max conviction = 100. ✓

---

## 5. Trend persistence, vol scaling, dynamic threshold

### Trend persistence (Pine 180)
| Pine | Python | Status |
|---|---|---|
| `trendPersistence = sum(close > close[1] ? 1 : 0, 10) / 10` | `(close > close.shift(1)).rolling(10).mean()` | ✅ |

### HTF bull gate (Pine 184)
| Pine | Python | Status |
|---|---|---|
| `htfBull = request.security(sym, "W", close > ta.ema(close, 20))` | `wk_close_aligned > wk_ema20_aligned` (hardcoded 20) | ✅ |

**Opomba:** Pine uporablja **hardcoded `20`** (ne `wkEmaLen=21`). Python
pravilno odraža. To je samostojen weekly gate poleg conviction-ove macro
komponente, ki uporablja `wkEmaLen`. Dva razlikovalna weekly checka — by design.

### Vol scale + final alloc (Pine 187–188)
| Pine | Python | Status |
|---|---|---|
| `volScale = annualVol > 0 ? min(1, targetVol / annualVol) : 1.0` | `np.where(annual_vol > 0, min(1, target_vol_pct / annual_vol), 1.0)` | ✅ |
| `finalAlloc = max(0, min(100, conviction * volScale * trendPersistence))` | `100.0 if signal_state == BULL else 0.0` (binary) | ⚠️ namerni odstop (glej §12) |

### Dynamic threshold (Pine 191–192)
| Pine | Python | Status |
|---|---|---|
| `bearMarketPenalty = bearMarketRegime ? 15.0 : 0.0` | `np.where(bear_market, 15.0, 0.0)` | ✅ |
| `dynamicThresh = min(85, (highVolRegime ? 70 : lowVolRegime ? 55 : 60) + bearMarketPenalty)` | `np.minimum(85, base_thresh + bear_penalty)` kjer je base_thresh nested where | ✅ |

**Pine ternary precedence:** `a ? b : c ? d : e` je `a ? b : (c ? d : e)`.
Python `np.where(high, 70, np.where(low, 55, 60))` mirrors točno.

---

## 6. Green / Red dot (Pine 200–201)

```pine
greenDot = aboveTL and conviction >= dynamicThresh and adxOK and structureBull and btcFilterOK and htfBull and not isWeekend
redDot = belowTL and not isWeekend
```

Python:
```python
green_dot = above_tl & (conviction >= dynamic_threshold) & adx_ok & structure_bull & btc_filter_ok & htf_bull & ~is_weekend
red_dot = below_tl & ~is_weekend
```
✅ vseh 7 pogojev za green_dot, 2 za red_dot

**Opazka:** Pine komentar (vrstica 196–198) navaja: "Green dot requires:
above TL + conviction + ADX + structure + BTC filter". **Komentar ne omeni
`htfBull` in `not isWeekend`**, čeprav sta v kodi prisotna. Manjša
dokumentacijska netočnost v Pine — Python implementira polno verzijo
(7 pogojev) po kodi.

---

## 7. State machine — Pine 207–267 vs `strategy.py:214-326`

### 7.1 Var init (Pine 207, 217–221, 247–248, 265)
| Pine var | Python var | Status |
|---|---|---|
| `var int rawState = 3` | `cur_raw = S_BEAR` | ✅ |
| `var int displayState = 3` | `cur_disp = S_BEAR` | ✅ |
| `var int rawHoldCount = 0` | `raw_hold_c = 0` | ✅ |
| `var int prevRaw = 3` | `prev_raw = S_BEAR` | ✅ |
| `var int greenAbsentCount = 0` | `green_absent_c = 0` | ✅ |
| `var int belowCount = 0` | `below_c = 0` | ✅ |
| `var int signalState = 3` | `cur_sig = S_BEAR` | ✅ |
| `var int barsSinceSignal = 999` | `bars_since_sig = 999` | ✅ |
| `var int prevSignal = 3` | `prev_sig = S_BEAR` | ✅ |

Empirično preverjeno z probe ✅.

### 7.2 Pre-iteration (Pine 249)
| Pine | Python | Status |
|---|---|---|
| `barsSinceSignal := barsSinceSignal + 1` ***unconditionally*** (zunaj `if not isWeekend`) | `bars_since_sig += 1` na vrhu zanke, pred `if not is_we` | ✅ |

**Pomembno:** counter se inkrementira **TUDI ob vikendih**. Vse druge
transitions in counters so gated z `not isWeekend`. To pomeni: `barsSinceSignal`
predstavlja koledarske dni od zadnjega signala, ne trgovalnih dni.

### 7.3 rawState (Pine 208–214)
| Pine | Python | Status |
|---|---|---|
| `if not isWeekend:` | `if not is_we:` | ✅ |
| `  if belowTL: rawState := 3` | `  if below_arr[i]: cur_raw = S_BEAR` | ✅ |
| `  else if greenDot: rawState := 1` | `  elif green_arr[i]: cur_raw = S_BULL` | ✅ |
| `  else if aboveTL: rawState := 2` | `  elif above_arr[i]: cur_raw = S_NEUTRAL` | ✅ |
| (no else — hold previous) | (no else — hold previous) | ✅ |

### 7.4 Counters (Pine 223–236)
| Pine | Python | Status |
|---|---|---|
| `if not greenDot and aboveTL: greenAbsentCount++` | `if not green_arr[i] and above_arr[i]: green_absent_c += 1` | ✅ |
| `else: greenAbsentCount := 0` | `else: green_absent_c = 0` | ✅ |
| `if belowTL: belowCount++` | `if below_arr[i]: below_c += 1` | ✅ |
| `else: belowCount := 0` | `else: below_c = 0` | ✅ |
| `if rawState == prevRaw: rawHoldCount++` | `if cur_raw == prev_raw: raw_hold_c += 1` | ✅ |
| `else: rawHoldCount := 1` | `else: raw_hold_c = 1` | ✅ (**reset na 1, ne 0 — drugače kot Lean!**) |
| `prevRaw := rawState` | `prev_raw = cur_raw` | ✅ |

### 7.5 displayState (Pine 238–244)
| Pine | Python | Status |
|---|---|---|
| `if belowTL and belowCount >= exitGraceBars: displayState := 3` | enako | ✅ |
| `else if aboveTL and greenDot: displayState := 1` | enako | ✅ |
| `else if aboveTL and not greenDot and greenAbsentCount >= graceBars: displayState := 2` | enako | ✅ |
| (no else — hold previous) | (no else — hold previous) | ✅ |

### 7.6 signalState — KLJUČNI del

Pine (251–263):
```pine
if not isWeekend
    if rawState == 3 and belowCount >= exitGraceBars and signalState != 3
        signalState := 3
    else if blowoff and signalState == 1
        signalState := 3
    else if volShock and belowTL and signalState != 3
        signalState := 3
    else if rawState == 1 and signalState != 1 and rawHoldCount >= confirmBars and barsSinceSignal >= reentryHold
        signalState := 1
        barsSinceSignal := 0
```

Python (289–303):
```python
if cur_raw == S_BEAR and below_c >= exit_grace_bars and cur_sig != S_BEAR:
    cur_sig = S_BEAR
elif blowoff_arr[i] and cur_sig == S_BULL:
    cur_sig = S_BEAR
elif vol_shock_arr[i] and below_arr[i] and cur_sig != S_BEAR:
    cur_sig = S_BEAR
elif (cur_raw == S_BULL
      and cur_sig != S_BULL
      and raw_hold_c >= confirm_bars
      and bars_since_sig >= reentry_hold):
    cur_sig = S_BULL
    bars_since_sig = 0
```
✅ Vse 4 branch-i identične.

**KLJUČNI POMEMBNI VPOGLED:** `barsSinceSignal := 0` je IZVRŠEN **SAMO**
v BULL entry branchi. BEAR exiti tega NE resetirajo. To je glavna razlika
od Lean (kjer se resetira na obeh smereh).

Posledica: po BULL → blowoff BEAR → naslednji BULL se lahko zgodi
že 3 dni kasneje, če je `bars_since_sig` od prvega BULL že čez 15.

Empirično pri BTC backtestu:
```
2024-02-21 BULL ($51,849)     → bars_since reset to 0
...
2024-03-04 BEAR ($68,246) blowoff → bars_since = 12 (no reset!)
2024-03-07 BULL ($66,823)     → bars_since = 15 ≥ 15, re-entry OK
```

To je **NAMERNO** v Pine designu, ne bug. Python pravilno reproduces.

### 7.7 signalChanged (Pine 265–267)
| Pine | Python | Status |
|---|---|---|
| `signalChanged = signalState != prevSignal` | `signal_changed[i] = (cur_sig != prev_sig)` | ✅ |
| `prevSignal := signalState` (po) | `prev_sig = cur_sig` (po) | ✅ |
| Obeh izračunov **zunaj** `if not isWeekend` | obeh izračunov **zunaj** `if not is_we` | ✅ |

Empirično: `signalChanged == (signalState != signalState[-1])` za vse bare ✅.

---

## 8. Plots & UI (Pine 273–295) — Dashboard equivalents

| Pine | Pomen | Python dashboard | Status |
|---|---|---|---|
| `plot(trackline, color=trackRising ? green : red, width=3)` | TL z barvno smerjo | Segmentiran trace po `track_rising` | ✅ |
| `plot(sma200, color=orange transparent50, width=1)` | 200 MA | Neutralna siva, dash="dot" | ✅ (rahla razlika v barvi — namenska "manj kričeča" paleta) |
| `plotshape(greenDot, location=belowbar, color=green)` | Zelene pike | Green circle markers | ✅ |
| `plotshape(redDot, location=abovebar, color=red)` | Rdeče pike | Red circle markers | ✅ |
| `bgcolor` glede na displayState | Pasovi ozadja | `add_vrect` z barvanjem po displayState | ✅ |
| `label.new("BULL"/"BEAR")` na signalChanged | Etikete prehodov | Triangle markers + text | ✅ |

---

## 9. Status table (Pine 301–335) — 7 vrstic, vse v dashboardu

| Pine cell | Vsebina | Python dashboard | Status |
|---|---|---|---|
| (0,0) | "DIVERSITAS" + signal | Hero card "Signal" | ✅ |
| (1,*) | "Regime" + displayState | Hero card "Regime" + Status detail | ✅ |
| (2,*) | "200 MA" + status | Status detail "200 MA" | ✅ |
| (3,*) | "Threshold" + dynamicThresh + conviction | Hero card "Allocation" sub | ✅ |
| (4,*) | "Trackline" + value + RISING/FALLING | Status detail "Trackline" | ✅ |
| (5,*) | "Price vs TL" + distPct | Hero card "Price vs Trackline" | ✅ |
| (6,*) | "Trend Quality" + tpPct | Status detail "Trend quality" | ✅ |

Vse 7 vrstic prikazanih.

---

## 10. Alerts (Pine 341–344)

Pine `alertcondition()` za: BULL, BEAR, BLOW-OFF, VOL SHOCK.

Python: warnings panel v dashboardu pri `blowoff`/`vol_shock` aktivih,
ne push notifications (Streamlit nima 1:1 alerting). Brez napake — design
odločitev (dashboard ≠ alert-routing sistem).

---

## 11. NAJDENE NAPAKE V PINE SAMI

### 🐛 BUG #1 — `rsiThresh` mrtva koda (Pine vrstica 23)

`rsiThresh = input.float(45.0, "RSI Threshold", minval=30.0, maxval=60.0)`

Spremenljivka deklarirana, ampak nikjer uporabljena. Blowoff (vrstica 143)
uporablja **hardcoded 80**, ne `rsiThresh`. Uporabnik lahko spreminja
parameter v UI ampak ne vpliva nič.

**Priporočilo:** ali uporabiti `rsiThresh` v blowoff (npr. `rsiVal > rsiThresh`
ko bi to imelo smisel, sicer hardcoded `80` z drugačnim imenom), ali izbrisati
input. Python `config.py` faithful reproducira mrtvo polje — možno odstraniti
tudi tam.

### 📝 Opazka #1 — Pine komentar na vrstici 196–198 ni popoln

Komentar: "Green dot requires: above TL + conviction >= dynamic threshold +
ADX trending + market structure bullish + BTC filter (on alts)"

Dejanska koda (vrstica 200) zahteva 7 stvari: ABOVE_TL + CONVICTION + ADX_OK
+ STRUCTURE_BULL + BTC_OK + **HTF_BULL** + **!IS_WEEKEND**.

Komentar manjkata `htfBull` in `!isWeekend`. Manjša dokumentacijska napaka,
brez učinka na logiko.

### 📝 Opazka #2 — Dva podobna weekly EMA gate-a

- `wkEMA` v macro score uporablja `wkEmaLen` (default 21)
- `htfBull` uporablja **hardcoded 20**

Dve podobni weekly EMA preverbi (20 vs 21). Verjetno nameren oz. naključen
duplikat. Python faithful reproduces oboje.

---

## 12. Sprejemljivi minor odstopi Python vs Pine

### ⚠️ Odstop #1 — BTC filter NULL safety (strategy.py:112)

Python:
```python
if cfg.use_btc_filter and btc_daily is not None and not btc_daily.empty:
    ...
else:
    df["btc_filter_ok"] = True
```

Pine vedno kliče `request.security`. Python doda check za `btc_daily=None`.
Defenzivnost, ne posega v logiko.

### ⚠️ Odstop #3 — `final_alloc` je BINARNI 0/100, ne kontinuiran

Pine vrstica 188 računa `finalAlloc = conviction × volScale × trendPersistence`
neodvisno od `signalState`. To pomeni, da je `finalAlloc` lahko npr. 0.7 %
medtem ko je `signalState == BEAR` — vidno v dashboardu, zmedeno.

Python od commit-a `<binary-alloc>` dalje: `final_alloc = 100.0 if signal_state == BULL else 0.0`.
Signal je vir resnice; alokacija je all-in ali all-out. To je **namerna**
odločitev po user feedbacku ("0 % ali 100 %"). `vol_scale` in
`trend_persistence` še vedno obstajata kot ločeni stolpci za prikaz v dashboardu.

### ⚠️ Odstop #4 — volZ NaN handling (strategy.py:129)

Pine: ternary preverja `volStd100 > 0`.
Python: division ki postane NaN ko je delitelj 0, nato `fillna(0)`.

Funkcionalno enako za regime flags (NaN/0 > 1 vedno False).

---

## 13. Empirično preverjanje

```
Full state machine init values (mirror Pine var defaults):
  rawState init: 3 (BEAR)                ✓
  signalState init: 3 (BEAR)             ✓
  barsSinceSignal init: 999              ✓
  prevRaw init: 3, prevSignal init: 3    ✓
  rawHoldCount init: 0                   ✓
  greenAbsentCount init: 0               ✓
  belowCount init: 0                     ✓
  displayState init: 3                   ✓

signalChanged == (signalState != signalState[-1]) for all bars: True
bars_since_signal monotonic when no BULL entry occurs: True
Full-vs-Lean key diff: bars_since reset ONLY on BULL (validated)
```

---

## 14. Zaključek

| Kategorija | Pine vrstic | Najdb v Python portu | Najdb v Pine viru |
|---|---|---|---|
| Inputs (22 ne-display) | 18–54 | 0 (vsi defaulti ujemajo) | **1 mrtev (rsiThresh)** |
| Indicators | 65–144 | 0 | 0 |
| Conviction score (5 komponent) | 150–175 | 0 | 0 |
| Trend persistence / vol scaling / threshold | 180–192 | 0 | 0 |
| Green/red dot | 200–201 | 0 | komentar nepopoln |
| State machine (3 ravni) | 207–267 | 0 | 0 |
| Plots / status table / alerts | 273–344 | dashboard ekvivalenti | 0 |

**Skupaj v Python portu: 0 napak v logiki.** Vsi inputi, indikatorji,
conviction score, dynamic threshold, state mašine in display so faithful
preneseni.

**Skupaj v Pine viru: 1 dejanska napaka** (`rsiThresh` input je dead code)
+ 2 dokumentacijski opazki.

**Najpomembnejša pridobitev iz revizije:**

1. **Pine ima 1 dead input (`rsiThresh`)** ki ne vpliva na nič. UI control
   v TradingView je zavajajoč — uporabnik misli da nastavlja RSI threshold,
   ampak blowoff uporablja hardcoded `80`. Python od tega commita dalje
   **opušča to mrtvo polje** (komentar v viru opozarja na Pine napako).

2. **`barsSinceSignal` reset SAMO na BULL** (ne na BEAR) je namerno
   v Full designu — dovoljuje hitre BULL→BEAR(blowoff)→BULL whipsawe.
   Lean to spreminja (reset na obeh smereh). Python Full pravilno
   reproduces Pine semantiko.

3. **Pine v6 default `request.security` z `lookahead_off`** vrača
   prejšnjo zaprto HTF sveco. Python `_align_weekly` to emulira
   z `shift(1)` pred reindex+ffill. ✓ anti-repaint match.

4. **`max_bars_back=5000` + running peak (`var float peakPrice`)** pomeni
   da je `ddPct` odvisen od količine naložene zgodovine. Tako v Pine
   kot v Python. Pričakovano vedenje, ni bug.

**Status v Pythonu:** Polje `rsi_thresh` je odstranjeno iz `Config`
(eden namernih odstop od 1:1 inputov, ker bi tudi tu bilo mrtvo).
**Pine vir** še vedno vsebuje dead input — priporočamo, da ga ali
uporabite v blowoff (`rsiVal > rsiThresh`) ali izbrišete.

**Strategija v Pythonu je pravilno (in faithfully) implementirana.**
Nobenega popravka v `strategy.py` ali `config.py` ni potrebno za skladnost
s Pine.
