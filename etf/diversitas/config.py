"""Configuration for the ETF sleeve.

Deliberately the same *shape* as `MomentumConfig` — same field names for the
same concepts — so `testing/scripts/engine.py`, `shared/warmup.py` and the whole
validation harness work on it without a special case. Only the values differ,
and every difference below is there because an equity ETF is not an altcoin.

Why each number moved
---------------------

**`trading_days` 365 -> 252.** The single highest-impact line in the file. Every
annualised figure in the project multiplies by sqrt(trading_days); leaving 365
in place inflates volatility, Sharpe and Sortino on equities by a factor of
sqrt(365/252) = 1.20. Nothing about that error looks wrong on a chart.

**Lookbacks converted by calendar time, not by bar count.** A 75-bar trackline
on a 24/7 asset spans 75 calendar days. The same 75 bars on an ETF span 109
calendar days — the rule becomes half again as slow without anyone choosing
that. Converting at 252/365 gives 52, which is then rounded to the nearest
convention the equity literature already uses, because the equity horizons are
not arbitrary: 50 and 200 days are the two most heavily-populated trend
lookbacks in published work, and choosing them is one fewer free parameter to
overfit. `track_period` 100 sits between the two.

**The entry buffer is measured in ATR, not in percent.** `track_buf_pct = 2.0`
on BTC is roughly a third of a daily range. The same 2 % on the Global Aggregate
bond sleeve, whose annualised volatility is 4 %, is a move it makes twice a
year — the buffer would not filter noise, it would forbid trading. With
`use_atr_buffer` the threshold is `atr_buf_mult x ATR`, which is the same
statistical distance on every instrument in the book. `track_buf_pct` is kept as
the fallback for like-for-like comparison against the crypto ports.

**The trailing stop likewise.** `trail_pct = 12` is a normal week in BTC and a
crash in bonds. `trail_atr_mult = 3.0` is the Chandelier convention and adapts
per instrument and per regime.

**`target_vol_pct` 60 -> 12, and it now actually binds.** Momentum's 60 % target
never bit on equities: `min(1, 60/15)` is 1 on every calm day, so the vol sizing
silently switched itself off — the same failure the altcoin report found in
Lean, where the built-in path was inert and only an overlay measured anything.
At 12 % the scale is below 1 whenever realised volatility exceeds the target,
which on this universe means the stressed periods and only those.

**`max_leverage = 1.0`.** The altcoin campaign's one statistically significant
positive result was that volatility targeting reduces drawdown, with the return
benefit unproven. Leverage would trade that proven benefit away for the unproven
one. Cash is the only alternative asset here.

**`fee_per_side_pct` 0.30 -> 0.20, charged on every execution.** A round trip
therefore costs 0.40 %. This is set by instruction rather than derived, and it is
close to what Slovenian venues actually publish: the INR providers (NLB, BKS,
Ilirika, OTP) all list 0.30 % per order with a 1-4 EUR minimum, so 0.20 % is the
right order of magnitude for a plain brokerage account and is not obviously
generous. It is applied uniformly — `fee_overrides` is now empty rather than
carrying a guess per sleeve, because a made-up spread difference between
SmallCap and World is not more accurate than one honest number, it is only more
detailed. Replace it with measured fills when they exist.

Tax is a separate and larger cost and lives in `shared/tax.py`; nothing in this
file models it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class ETFConfig:
    # ── trend anchor (the "trackline": Donchian midline) ──────────────────────
    track_period: int = 100         # ~5 months; between the 50/200 conventions
    track_buf_pct: float = 0.75     # fallback when use_atr_buffer is False
    track_slope_bars: int = 10      # slope window, was 7 crypto bars

    use_atr_buffer: bool = True
    atr_len: int = 14
    atr_buf_mult: float = 0.5       # entry needs close > trackline + 0.5 x ATR

    # ── moving averages ───────────────────────────────────────────────────────
    ma_fast_len: int = 50           # trend MA
    ma_reg_len: int = 200           # regime MA — the equity standard
    ma_slope: int = 20              # ~1 month, was 5 crypto bars

    # ── momentum filter ───────────────────────────────────────────────────────
    rsi_len: int = 14
    ema_slow_len: int = 100
    rsi_entry: float = 50.0

    # ── trend-quality filter: ADX instead of the Efficiency Ratio ─────────────
    # ER was tuned on crypto's noise profile. ADX is the equity-side convention
    # and is what the brief asks for; both measure "is this a trend or a drift".
    use_adx: bool = True
    adx_len: int = 14
    adx_thresh: float = 18.0        # below this the tape is directionless

    use_er: bool = False            # kept so the crypto filter can be A/B'd
    er_len: int = 20
    er_thresh: float = 0.20

    # ── exits ─────────────────────────────────────────────────────────────────
    use_trail: bool = True
    trail_atr_mult: float = 3.0     # Chandelier: exit at peak - 3 x ATR
    trail_pct: float = 0.0          # 0 disables the fixed-percent trail
    blowoff_dist_pct: float = 0.0   # 0 disables; equities rarely blow off like alts
    vol_lookback: int = 60          # 60 trading days ~ 3 months

    # ── regime handling ───────────────────────────────────────────────────────
    # Soft, like Momentum: a bear regime halves size rather than blocking. On a
    # diversified book a hard block is a bet that the regime filter is never
    # wrong, and on 8 years of data that is not something we can claim.
    bear_size_cut: float = 50.0

    # ── anti-churn ────────────────────────────────────────────────────────────
    confirm_bars: int = 1
    reentry_hold: int = 5           # trading days
    exit_grace_bars: int = 3        # the altcoin campaign's measured plateau

    # ── sizing ────────────────────────────────────────────────────────────────
    use_vol_sizing: bool = True
    target_vol_pct: float = 12.0
    max_leverage: float = 1.0
    vol_floor_pct: float = 3.0      # never divide by a near-zero bond vol

    # ── calendar and costs ────────────────────────────────────────────────────
    trading_days: int = 252
    fee_per_side_pct: float = 0.20
    # Empty on purpose: one honest number beats four invented ones. Put real
    # measured spreads here when the broker statements exist.
    fee_overrides: Dict[str, float] = field(default_factory=dict)

    # ── cross-asset filter ────────────────────────────────────────────────────
    # The crypto ports gate altcoins on BTC. The equity analogue is gating every
    # sleeve on the broad market. Off by default: on a book that already holds
    # World at 55 %, gating the other sleeves on World mostly duplicates the
    # signal the book already has.
    use_anchor_filter: bool = False
    anchor_key: str = "World"
    anchor_ma_len: int = 200

    # Present so `shared.data_source` and the crypto dashboards can consume this
    # config object unchanged. ETF prices come from `shared.etf_data`, which uses
    # `shared.etf_universe` instead.
    symbol_map: Dict[str, Dict[str, str]] = field(default_factory=dict)


DEFAULT_CONFIG = ETFConfig()


# A deliberately slower, lower-turnover variant for the defensive book. Bonds and
# inflation-linked paper trend on a longer clock than equities and cannot pay for
# frequent trading out of a 4 % volatility budget.
DEFENSIVE_CONFIG = ETFConfig(
    track_period=150,
    ma_fast_len=100,
    reentry_hold=10,
    exit_grace_bars=5,
    target_vol_pct=8.0,
    atr_buf_mult=0.75,
    trail_atr_mult=4.0,
)
