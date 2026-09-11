"""The eight UCITS instruments and the two portfolios, as data.

Kept apart from the loader for one reason: **the ticker is the least stable
thing in this project and the most damaging when wrong.**

Yahoo lists the same ISIN on several venues. Those sibling lines are not
independent quotes of the same fund — they are Yahoo's re-labelling of one
series. Measured on 2026-09-01:

    IGLN.L (USD) and EGLN.L (EUR) both start at exactly 29.39 on 2011-04-08
    CMOD.L (USD) and CMOD.MI (EUR) both start at exactly 17.46 on 2017-01-09
    IWQU.L (USD) and IS3Q.DE (EUR) start at 25.13 / 25.06 on 2014-10-06

Identical inception levels under different currency labels cannot both be
right. They then drift apart: the gold pair differs by 110 percentage points
of cumulative return since 2011, the quality pair by 80 points since 2014.

So: one venue per ISIN, chosen here, verified, and never silently swapped.
A currency conversion is done explicitly against a dated FX series
(`shared.etf_data.fx_series`), never by picking a differently-labelled line.

`PRIMARY` was chosen per instrument by measuring, over the last three years,
the share of missing closes and of repeated closes (a repeat is a stale print,
which is a price the strategy can act on but nobody could have traded):

    ticker    ccy  missing  repeated        ticker    ccy  missing  repeated
    IWDA.L    USD     0.0%      0.1%        EUNL.DE   EUR     0.4%      0.8%
    EIMI.L    USD     0.0%      1.5%        IS3N.DE   EUR     0.4%      0.4%
    WSML.L    USD     0.0%      0.3%        IUSN.DE   EUR     0.4%      0.8%
    IWQU.L    USD     0.0%      0.5%        IS3Q.DE   EUR     0.4%      1.2%
    EUNA.DE   EUR     0.1%      0.9%        0GGH.L    EUR     4.7%      0.4%
    IBCI.AS   EUR     0.3%      0.7%        IBCI.MI   EUR     0.4%      0.7%
    IGLN.L    USD     0.0%      0.3%        EGLN.L    EUR     0.1%      0.7%
    CMOD.L    USD     0.0%      0.3%        CMOD.MI   EUR     0.3%      1.2%

The LSE lines win on both counts wherever they exist for the ISIN. The two
bond funds have no usable LSE line (0GGH.L is missing 4.7 % of its closes), so
they come from Xetra and Amsterdam. LSE, Xetra, Euronext and Borsa Italiana all
close within ten minutes of 17:30 CET, so mixing these venues costs no
meaningful synchronicity; mixing in a US listing would.

`usable_from` is NOT the inception date, and the gap matters. Yahoo carries the
line from listing, but the early bars are stale: IWDA.L repeats its previous
close on 78 % of 2009 bars, 81 % of 2010, 40 % of 2011-2012, then 0.4 % in 2013
and 0.0 % from 2014. EUNA.DE repeats on 21 % of 2018 bars and 0 % from 2019.
A trend rule fed stale closes reports trades at prices nobody could fill, and
the effect is largest exactly where the history looks most valuable — the extra
years at the front. So each instrument records the first year its own data is
tradable, and `etf_data.load_panel(min_quality=True)` starts there.

`PROXIES` are index-equivalent US-listed funds with longer history, used ONLY by
the explicit backfill path in `etf_data.load`. They are never spliced silently.
The World chain ends in SPY deliberately: SPY is US-only and therefore a poor
stand-in for MSCI World in level terms, but it reaches 1993 and so covers the
dot-com unwind and 2008. Those two episodes are the only bear markets of the
slow, grinding kind in the whole record, and the tradable ETF sample (2013-2026)
contains none of them. A backfilled series is evidence about robustness across
regimes; it is never a performance figure.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class Proxy:
    """A longer-history stand-in for one sleeve, with its measured fitness.

    The numbers are not decoration and not guesses: they are written here by
    `testing/scripts/etf_data_audit.py`, which measures every candidate against
    the real sleeve over their overlap. A proxy chain nobody measured is how a
    backtest ends up reporting the proxy's behaviour under the sleeve's name.

    `corr_1d` vs `corr_1m` is the field that decides how a proxy may be used.
    A US-listed fund prices at 22:00 CET and a London line at 17:30 CET, so on
    a daily series they disagree about which day a move belongs to — but the
    disagreement washes out over a month. When `corr_1d` is poor and `corr_1m`
    is good, the proxy is sound and only the daily alignment is broken, so it is
    usable at monthly frequency and must not be used daily. When *both* are
    poor, the proxy is simply a different asset.
    """
    ticker: str
    ccy: str
    corr_1d: float = float("nan")
    corr_1m: float = float("nan")
    te_ann_pct: float = float("nan")     # annualised tracking error of daily returns
    d_cagr_pp: float = float("nan")      # sleeve CAGR minus proxy CAGR, points
    grade: str = "unmeasured"            # daily | monthly | reject | unmeasured
    drift_correct: Optional[str] = None  # None | "measured" | "cash" — see below
    note: str = ""


@dataclass(frozen=True)
class Instrument:
    isin: str
    key: str                    # short internal name, used as a column label
    name: str
    asset_class: str            # equity | equity_factor | bonds | bonds_il | real
    yahoo: str                  # THE line. See module docstring.
    quote_ccy: str              # currency the chosen line is quoted in
    venue: str
    inception: str              # first Yahoo bar on the chosen line
    usable_from: str            # first bar with real liquidity — see note below
    accumulating: bool          # True -> close is already total return
    proxies: Tuple[Proxy, ...] = ()             # longest history last


UNIVERSE: Dict[str, Instrument] = {
    i.key: i for i in [
        Instrument("IE00B4L5Y983", "World", "iShares Core MSCI World UCITS ETF",
                   "equity", "IWDA.L", "USD", "LSE", "2009-09-25", "2013-01-01", True,
                   (Proxy("URTH", "USD"), Proxy("ACWI", "USD"), Proxy("VT", "USD"),
                    Proxy("EFA", "USD"), Proxy("SPY", "USD"), Proxy("VTSMX", "USD"),
                    Proxy("^990100-USD-STRD", "USD", drift_correct="measured",
                          note="MSCI World PRICE index from 1985 — excludes dividends"))),
        Instrument("IE00BKM4GZ66", "EM", "iShares Core MSCI EM IMI UCITS ETF",
                   "equity", "EIMI.L", "USD", "LSE", "2014-05-30", "2014-05-30", True,
                   (Proxy("IEMG", "USD"), Proxy("VWO", "USD"), Proxy("EEM", "USD"),
                    Proxy("VEIEX", "USD", note="Vanguard EM fund from 1994"))),
        Instrument("IE00BF4RFH31", "SmallCap", "iShares MSCI World Small Cap UCITS ETF",
                   "equity", "WSML.L", "USD", "LSE", "2018-03-27", "2018-03-27", True,
                   (Proxy("VSS", "USD"), Proxy("SCZ", "USD"), Proxy("IWM", "USD"),
                    Proxy("NAESX", "USD", note="US small cap from 1985 — wrong region"),
                    Proxy("^RUT", "USD", drift_correct="measured", note="Russell 2000 price index, US only"))),
        Instrument("IE00BP3QZ601", "Quality", "iShares Edge MSCI World Quality Factor UCITS ETF",
                   "equity_factor", "IWQU.L", "USD", "LSE", "2014-10-06", "2014-10-06", True,
                   (Proxy("QUAL", "USD"), Proxy("SPHQ", "USD", note="US quality from 2005"))),
        Instrument("IE00BDBRDM35", "GlobAgg", "iShares Core Global Aggregate Bond UCITS ETF EUR Hedged",
                   "bonds", "EUNA.DE", "EUR", "XETRA", "2017-11-21", "2019-01-01", True,
                   (Proxy("AGGH.MI", "EUR", note="same fund, Milan line"),
                    Proxy("IEAG.AS", "EUR", note="iShares EUR Aggregate ESG (Dist) from 2009"),
                    Proxy("IEGA.AS", "EUR", note="iShares Core EUR Govt Bond (Dist) from 2014"),
                    Proxy("IBGM.AS", "EUR", note="iShares EUR Govt 7-10y (Dist) from 2008"),
                    Proxy("AGG", "USD", note="US aggregate — unhedged, different curve"),
                    Proxy("VBMFX", "USD", note="US total bond from 1986"))),
        Instrument("IE00B0M62X26", "InflLink", "iShares EUR Inflation Linked Govt Bond UCITS ETF",
                   "bonds_il", "IBCI.AS", "EUR", "EURONEXT-AMS", "2008-01-02", "2008-01-02", True,
                   (Proxy("TIP", "USD", note="US TIPS — different currency and curve"),
                    Proxy("VIPSX", "USD", note="US TIPS fund from 2000"))),
        Instrument("IE00B4ND3602", "Gold", "iShares Physical Gold ETC",
                   "real", "IGLN.L", "USD", "LSE", "2011-04-08", "2011-04-08", True,
                   (Proxy("GLD", "USD"), Proxy("IAU", "USD"),
                    Proxy("GC=F", "USD", note="COMEX gold future, near-24h, from 2000"))),
        Instrument("IE00BD6FTQ80", "Commod", "Invesco Bloomberg Commodity UCITS ETF (Acc)",
                   "real", "CMOD.L", "USD", "LSE", "2017-01-09", "2017-01-09", True,
                   (Proxy("DJP", "USD"), Proxy("DBC", "USD"), Proxy("GSG", "USD"),
                    Proxy("^BCOM", "USD", drift_correct="cash", note="Bloomberg Commodity index from 1991"),
                    Proxy("^SPGSCI", "USD", drift_correct="cash", note="S&P GSCI from 1985 — energy-heavy, different index"))),
    ]
}


BY_ISIN: Dict[str, Instrument] = {i.isin: i for i in UNIVERSE.values()}

# The two target books, as given. Weights are fractions of capital, not of risk;
# `etf.diversitas.universe.risk_shares` reports the difference, which is large.
PORTFOLIOS: Dict[str, Dict[str, float]] = {
    "P1": {"World": 0.55, "EM": 0.15, "SmallCap": 0.15, "Quality": 0.15},
    "P2": {"World": 0.23, "EM": 0.07, "GlobAgg": 0.35, "InflLink": 0.20,
           "Gold": 0.10, "Commod": 0.05},
}

# Earliest date on which every member of the book has a real (non-backfilled)
# price. Recorded rather than computed so a silent data change is visible.
JOINT_START = {"P1": "2018-03-27", "P2": "2019-01-02"}


def usable_start(portfolio: str) -> str:
    """Latest `usable_from` among the book's members — the first date on which
    every sleeve has data anyone could have traded."""
    return max(UNIVERSE[k].usable_from for k in members(portfolio))


def members(portfolio: str) -> List[str]:
    if portfolio not in PORTFOLIOS:
        raise KeyError(f"unknown portfolio {portfolio!r}; known: {sorted(PORTFOLIOS)}")
    return list(PORTFOLIOS[portfolio])


def resolve(name: str) -> Instrument:
    """Accept a key ('World'), an ISIN, or the Yahoo ticker."""
    if name in UNIVERSE:
        return UNIVERSE[name]
    if name in BY_ISIN:
        return BY_ISIN[name]
    for inst in UNIVERSE.values():
        if inst.yahoo == name:
            return inst
    raise KeyError(f"unknown instrument {name!r}")
