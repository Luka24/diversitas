# Validation — Diversitas Lean (Python port)

_Zadnja osvežitev: 2026-07-27, po odstranitvi ER gatea._

## 1. Unit tests

```
$ cd lean && ../.venv/Scripts/python.exe -m pytest diversitas/tests/ -q
======================== 14 passed in 2.86s =========================
```

| Test | Kaj preverja |
|---|---|
| `test_default_is_donchian_off_and_identical` | `use_donchian=False` da identičen signal → Pine parity |
| `test_donchian_on_is_a_stricter_filter` | vklopljen Donchian samo zaostri, nikoli ne doda vstopov |
| `test_bull_condition_requires_all_components` | `bull_condition` je trdi AND |
| `test_bear_regime_blocks_bull` | trda regime blokada deluje |
| `test_uptrend_triggers_bull` | strategija odda BULL v trendu navzgor |
| `test_downtrend_stays_bear` | ostane BEAR v trendu navzdol |
| `test_state_codes_valid` | stanja ∈ {1,2,3} |
| `test_blowoff_triggers_bear_from_bull` | blow-off izhod se sproži |
| `test_reentry_lock_respected` | ≥ `reentry_hold` dni med ponovnimi vstopi |
| `test_confirm_bars_enforced` | BULL zahteva `bull_hold ≥ confirm_bars` |
| `test_bars_since_signal_resets_on_both_directions` | **lean-specifično:** reset na BULL IN BEAR |
| `test_alloc_zero_when_bear` | alokacija 0 ko BEAR |
| `test_alloc_capped_at_100` | alokacija ≤ 100 |
| `test_summary_has_required_keys` | summary dict popoln |

> Prejšnja različica tega dokumenta je navajala 21 testov. Indikatorski testi
> (SMA/EMA/RSI/ADX/stdev) so se preselili v `shared/tests/test_indicators.py`,
> ko je bil `shared/` izločen. V `lean/` jih je 14.

## 2. Backtest na zamrznjenih podatkih

Vir: `testing/data/BTC.parquet` in `ETH.parquet` (SHA v `manifest.json`).
Ogrevanje 199 barov izključeno, zato je prvi uporabni dan **2019-12-24**.

### BTC, 2019-12-24 → 2026-07-20 (2401 dni)

```
CAGR            36.0 %
Sortino          1.61
MaxDD          -39.1 %   (dno 2023-03-10)
izpostavljenost 43.4 %
tradov            17

Buy & hold:  CAGR 39.2 %,  MaxDD -76.6 %
```

**Drawdown je prepolovljen pri primerljivem donosu — to je jedro izdelka.**
Razlika v MaxDD proti buy & hold je +37,5 odstotne točke.

### Kontrola pravilnosti

`(1 + CAGR)^leta` natanko reproducira končno vrednost krivulje (5,647× pri ER,
7,553× brez), kar potrjuje, da metrike in krivulja izhajajo iz istih donosov.
Drawdown se nikoli ne obrne v pozitivno, začne pri 0 in se resetira ob vsakem
novem vrhu (400 takih dni od 2401).

## 3. Spremembe strategije

### 3.1 ER gate odstranjen (2026-07-27)

Commit `291d9b2` (2026-06-13) je dodal Kaufmanov Efficiency Ratio kot osmi pogoj
za vstop — v Python, ne pa v Pine. Odstranjen, ker se ni dalo pokazati, da kaj
počne:

- prag 0,30 leži na **mediani** porazdelitve ER (p50 = 0,29), torej reže polovico
  dni ne glede na trg;
- povprečen ER na dneh v BULL (0,35) je enak kot na dneh v BEAR (0,32) — filter
  ne loči režimov, kar naj bi bila njegova celotna funkcija;
- vseh 18 intervalov zaupanja (2 sredstvi × 3 okna × 3 metrike) prečka ničlo;
- če ER izklopiš in pozicije skaliraš na **isto povprečno izpostavljenost**,
  navadno skaliranje premaga ER na Ulcerju 6 : 0 in na MaxDD 4× (2× izenačeno).

Poročilo: `testing/porocilo_ER_lean.md` (BTC + ETH), grafi
`testing/porocilo_ER_BTC.html`.

Po odstranitvi je `bull_condition` spet Pine-jevih šest členov (plus neaktivni
`donchian_ok`) in izmerjeni signal se **natanko** ujema s tem, kar je bilo prej
izmerjeno kot varianta »ER izklopljen«.

### 3.2 Popravek ogrevanja v testnem motorju (2026-07-27)

Glej `lean/AUDIT.md` §11. Vse številke v `testing/reports/`, ki so nastale prej,
je treba brati s tem pridržkom.

## 4. Razlike proti Full (preverjeno)

| Lastnost | Full | Lean |
|---|---|---|
| Bear regime | mehko (+15 prag) | **trda blokada** |
| Odločitev o vstopu | conviction score 0–100 | trdi AND šestih pogojev |
| Nivoji stanj | 3 (raw / display / signal) | 1 (signal) + display |
| `barsSinceSignal` reset | samo na BULL | **na BULL IN BEAR** |
| Alokacija | `conv × volScale × trendPersistence` | binarno 100 / 0 |
| BTC filter privzeto | vklopljen | **izklopljen** |
| Vikendi | opcijski preskok | vedno trguje |
