"""ETF candle loading in a single base currency — the equity-side twin of
`shared/data_source.py`.

Crypto trades 24/7 in one quote currency on venues that all print at the same
instant. None of that is true here, and each difference is a way to get a wrong
number that still looks like a price. This module exists to close four of them.

**1. Currency.** Six of the eight instruments are quoted in USD on the LSE. A
EUR investor's return is the fund's return *plus* the FX move, and the two are
of the same order. Conversion happens here, explicitly, against a dated series —
never by fetching a differently-labelled line of the same ISIN (see
`shared/etf_universe` for why those sibling lines are unsafe).

**2. The FX series itself.** Yahoo's `EURUSD=X` is a 24-hour bar whose close
lands hours away from a 17:30 CET equity close, and a daily FX bar misaligned by
hours injects noise straight into every daily return. The ECB publishes a
reference rate fixed at 16:00 CET on every TARGET business day, free and
keyless. Ninety minutes before the European close beats six hours after it, so
ECB is the default and Yahoo the fallback, not the other way round.

**3. Adjusted close.** All eight are accumulating: they pay no distribution, so
`close` is already a total-return series and `adjclose` equals it. Verified on
2026-09-01 — maximum deviation across all eight, over full history, was 0.000 %.
That is a fact about today's share classes, not a law, so `load` re-checks it on
every fetch and raises if a distribution appears. A fund that starts
distributing while the loader assumes it does not would understate return by the
dividend yield, compounding, with nothing in the data to show for it.

**4. Non-trading days and stale prints.** Two failures, not one. A *gap* (the
venue was shut) must not become a zero return, or volatility is understated. A
*stale print* (venue open, this line did not trade, so the close repeats) is
worse: it is a price the strategy can act on that nobody could have traded. Both
are labelled rather than silently smoothed — `traded` is False on a stale or
filled bar, and the counts come back in `df.attrs` so a caller can refuse a
series that is too thin.

Public API:
    load(name, start=..., end=..., base="EUR", backfill=False) -> pd.DataFrame
    load_panel(portfolio_or_keys, ...) -> (close_panel, {key: df})
    fx_series(quote_ccy, base="EUR")   -> pd.Series  (base units per 1 quote unit)
    quality_report({key: df})          -> pd.DataFrame
"""
from __future__ import annotations

import io
import time
from pathlib import Path
from typing import Optional
from urllib.parse import quote as _urlquote

import numpy as np
import pandas as pd
import requests

from shared.etf_universe import PORTFOLIOS, UNIVERSE, Instrument, Proxy, resolve

CACHE_DIR = Path(__file__).resolve().parents[1] / "testing" / "data" / "etf"

MAX_FILL_DAYS = 3          # how long a hole may be carried forward before it is a hole
ADJ_CLOSE_TOL = 0.001      # 0.1 % — above this, treat the fund as distributing

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


class ETFDataError(RuntimeError):
    pass


# ── Yahoo, date-ranged, with adjclose kept ────────────────────────────────────

_session: Optional[requests.Session] = None
_crumb: str = ""


def _yahoo_session() -> requests.Session:
    """One crumbed session per process. Yahoo has required the crumb cookie
    since 2023, and re-seeding it per request is both slow and rate-limited."""
    global _session, _crumb
    if _session is not None:
        return _session
    s = requests.Session()
    s.headers.update({"User-Agent": _UA, "Accept": "application/json,text/html,*/*",
                      "Accept-Language": "en-US,en;q=0.9"})
    try:
        s.get("https://finance.yahoo.com", timeout=10)
    except Exception:  # noqa: BLE001 — a missing cookie is slower, not fatal
        pass
    for url in ("https://query1.finance.yahoo.com/v1/test/getcrumb",
                "https://query2.finance.yahoo.com/v1/test/getcrumb"):
        try:
            r = s.get(url, timeout=8)
            if r.status_code == 200 and r.text.strip():
                _crumb = r.text.strip()
                break
        except Exception:  # noqa: BLE001
            continue
    _session = s
    return s


def fetch_yahoo(ticker: str, start: str = "2005-01-01",
                end: Optional[str] = None) -> pd.DataFrame:
    """Daily OHLCV + adjclose for one listing, UTC-normalised index.

    Date-ranged rather than bar-counted. Yahoo silently downsamples to monthly
    when asked for `range=max` over a long history — 17 years of IWDA came back
    as 205 bars — and a monthly series still labelled `interval=1d` is exactly
    the input that produces a plausible, wrong backtest.
    """
    s = _yahoo_session()
    p1 = int(pd.Timestamp(start, tz="UTC").timestamp())
    p2 = int(pd.Timestamp(end, tz="UTC").timestamp()) if end else int(time.time())
    params: dict = {"interval": "1d", "period1": p1, "period2": p2,
                    "events": "div,splits"}
    if _crumb:
        params["crumb"] = _crumb
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{_urlquote(ticker)}"
    r = s.get(url, params=params, timeout=25)
    if r.status_code != 200:
        raise ETFDataError(f"Yahoo HTTP {r.status_code} for {ticker}: {r.text[:160]}")
    payload = r.json()
    res = (payload.get("chart") or {}).get("result")
    if not res:
        err = (payload.get("chart") or {}).get("error") or "empty response"
        raise ETFDataError(f"Yahoo returned no data for {ticker}: {err}")
    c = res[0]
    ts = c.get("timestamp") or []
    if not ts:
        raise ETFDataError(f"Yahoo returned no bars for {ticker}")
    q = (c.get("indicators") or {}).get("quote", [{}])[0]
    n = len(ts)
    df = pd.DataFrame(
        {"open": q.get("open") or [np.nan] * n,
         "high": q.get("high") or [np.nan] * n,
         "low": q.get("low") or [np.nan] * n,
         "close": q.get("close") or [np.nan] * n,
         "volume": q.get("volume") or [0.0] * n},
        index=pd.to_datetime(ts, unit="s", utc=True).normalize(),
    )
    ac = (c.get("indicators") or {}).get("adjclose") or [{}]
    df["adjclose"] = (ac[0].get("adjclose") or [np.nan] * n) if ac else np.nan
    df.index.name = "time"
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df.attrs["currency"] = (c.get("meta") or {}).get("currency")
    df.attrs["ticker"] = ticker
    return df


# ── FX: ECB reference rates, Yahoo as fallback ────────────────────────────────

_fx_cache: dict = {}


def fx_series(quote_ccy: str, base: str = "EUR",
              start: str = "2005-01-01") -> pd.Series:
    """`base` units per 1 unit of `quote_ccy`, daily.

    ECB publishes `quote per 1 EUR` on TARGET business days at a 16:00 CET fix;
    we invert. Forward-filling this series is correct, and it is the only place
    forward-filling is: on a day the ECB does not fix, yesterday's rate really is
    the last official rate, whereas a forward-filled *price* is a trade that
    never happened.
    """
    quote_ccy, base = quote_ccy.upper(), base.upper()
    if quote_ccy == base:
        raise ValueError("fx_series called for identical currencies")
    if base != "EUR":
        raise NotImplementedError("only EUR base implemented; add a cross if needed")
    ck = (quote_ccy, base, start)
    if ck in _fx_cache:
        return _fx_cache[ck]

    s: Optional[pd.Series] = None
    try:
        r = requests.get(
            f"https://data-api.ecb.europa.eu/service/data/EXR/D.{quote_ccy}.EUR.SP00.A",
            params={"format": "csvdata", "startPeriod": start},
            headers={"User-Agent": "diversitas/1.0"}, timeout=30)
        if r.status_code == 200 and r.text.strip():
            raw = pd.read_csv(io.StringIO(r.text))
            v = pd.to_numeric(raw["OBS_VALUE"], errors="coerce")
            idx = pd.to_datetime(raw["TIME_PERIOD"], utc=True)
            s = pd.Series(v.to_numpy(), index=idx).dropna().sort_index()
            s.attrs["source"] = "ecb"
    except Exception:  # noqa: BLE001 — fall through to Yahoo
        s = None

    if s is None or s.empty:
        y = fetch_yahoo(f"{base}{quote_ccy}=X", start=start)["close"].dropna()
        if y.empty:
            raise ETFDataError(f"no FX series for {quote_ccy}/{base}")
        s = y
        s.attrs["source"] = "yahoo"

    src = s.attrs.get("source", "?")
    out = (1.0 / s).rename(f"{quote_ccy}{base}")     # EUR per 1 unit of quote_ccy
    out.attrs["source"] = src
    _fx_cache[ck] = out
    return out


# ── the euro cash rate: the series the rotation layer needs and nobody had ────

_ECB = "https://data-api.ecb.europa.eu/service/data"


def _ecb_series(key: str, start: str) -> pd.Series:
    r = requests.get(f"{_ECB}/{key}", params={"format": "csvdata", "startPeriod": start},
                     headers={"User-Agent": "diversitas/1.0"}, timeout=30)
    if r.status_code != 200 or not r.text.strip():
        raise ETFDataError(f"ECB {key}: HTTP {r.status_code}")
    raw = pd.read_csv(io.StringIO(r.text))
    v = pd.to_numeric(raw["OBS_VALUE"], errors="coerce")
    idx = pd.to_datetime(raw["TIME_PERIOD"], utc=True)
    return pd.Series(v.to_numpy(), index=idx).dropna().sort_index()


def cash_rate(start: str = "1999-01-01", kind: str = "overnight") -> pd.Series:
    """Annual percentage rate earned on uninvested cash, daily, from 1999.

    Why this exists at all: every strategy here parks capital in cash, and
    crediting that cash 0 % is not neutral — it is a dated assumption that was
    roughly right from 2015 to 2022 and badly wrong on both sides of it. Cash
    paid over 4 % in 2000-2001 and again in 2023-2024. A trend rule that sits out
    a year is under-measured by four points when cash earns nothing, and a rule
    credited today's rate across the whole history is over-measured for a decade.
    Neither error is small next to the differences this project tries to detect.

    `overnight` splices the two official ECB series, the standard way to get a
    continuous euro overnight rate:

        EONIA    1999-01-04 .. 2019-09-30
        EUR STR  2019-10-01 .. today

    EONIA was recalibrated to STR + 8.5 bp on exactly that date, so the handover
    is a definition change rather than a jump in the underlying rate.

    `deposit` returns the ECB deposit facility rate instead: what a bank earns at
    the central bank, so a floor rather than a market rate, and the more
    conservative assumption for a retail account that in practice earns less.

    Returned as an annual percentage; divide by `trading_days` for a daily accrual.
    """
    if kind == "deposit":
        s = _ecb_series("FM/D.U2.EUR.4F.KR.DFR.LEV", start)
        s.attrs["source"] = "ecb:deposit_facility"
        return s.rename("cash_rate_pct")
    if kind != "overnight":
        raise ValueError(f"unknown cash rate kind {kind!r}")

    cut = pd.Timestamp("2019-10-01", tz="UTC")
    parts, sources = [], []
    try:
        eonia = _ecb_series("EON/D.EONIA_TO.RATE", start)
        parts.append(eonia.loc[eonia.index < cut])
        sources.append("eonia")
    except Exception:  # noqa: BLE001
        pass
    try:
        estr = _ecb_series("EST/B.EU000A2X2A25.WT", start)
        parts.append(estr.loc[estr.index >= cut])
        sources.append("estr")
    except Exception:  # noqa: BLE001
        pass
    if not parts:
        raise ETFDataError("no ECB cash rate available")
    out = pd.concat(parts).sort_index()
    out = out[~out.index.duplicated(keep="last")]
    out.attrs["source"] = "ecb:" + "+".join(sources)
    return out.rename("cash_rate_pct")


# ── measured proxy quality ────────────────────────────────────────────────────

QUALITY_FILE = (Path(__file__).resolve().parents[1] / "testing" / "data"
                / "etf_proxy_quality.json")


def proxy_quality() -> dict:
    """Measured grades for every backfill candidate, keyed 'sleeve|ticker'.

    Written by `testing/scripts/etf_data_audit.py`. Kept in a file rather than in
    the registry so a grade is always the output of a measurement someone can
    re-run, never a number typed in once that then drifted away from the data.
    """
    if not QUALITY_FILE.exists():
        return {}
    import json
    return json.loads(QUALITY_FILE.read_text(encoding="utf-8")).get("proxies", {})



# ── calendar, staleness, validation ───────────────────────────────────────────

def _easter(year: int) -> pd.Timestamp:
    """Anonymous Gregorian algorithm. Good Friday and Easter Monday are the only
    moving TARGET holidays."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    ll = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ll) // 451
    month, day = divmod(h + ll - 7 * m + 114, 31)
    return pd.Timestamp(year=year, month=month, day=day + 1, tz="UTC")


def target_calendar(start: str, end: Optional[str] = None) -> pd.DatetimeIndex:
    """TARGET business days: the days the ECB fixes and European venues open.

    Mon-Fri minus the fixed TARGET closing days. Deliberately not
    `pandas_market_calendars`: one more dependency, and the residual error (a few
    national venue holidays a year) is caught by the `filled` flag anyway.
    """
    idx = pd.bdate_range(start=start,
                         end=end or pd.Timestamp.utcnow().normalize().tz_localize(None),
                         tz="UTC")
    fixed: list[str] = []
    for y in range(idx[0].year, idx[-1].year + 1):
        fixed += [f"{y}-01-01", f"{y}-05-01", f"{y}-12-25", f"{y}-12-26"]
        e = _easter(y)
        fixed += [str((e - pd.Timedelta(days=2)).date()),
                  str((e + pd.Timedelta(days=1)).date())]
    drop = pd.DatetimeIndex(pd.to_datetime(sorted(set(fixed)), utc=True))
    return idx.difference(drop)


def _mark_quality(df: pd.DataFrame, calendar: pd.DatetimeIndex) -> pd.DataFrame:
    """Reindex onto `calendar`, forward-fill short holes, label every bar.

    Three states, and the distinction is the whole point:
      traded — a real print on a day the venue was open
      stale  — venue open, this line neither moved nor traded
      filled — no print at all; carried forward up to MAX_FILL_DAYS
    Only `traded` bars are safe to treat as executable.
    """
    out = df.reindex(calendar)
    missing = out["close"].isna()
    prev = out["close"].ffill().shift(1)
    vol = out["volume"].fillna(0.0)
    repeated = ((~missing) & (out["close"] == prev) & (vol <= 0)).fillna(False)

    for col in ("open", "high", "low", "close", "adjclose"):
        if col in out.columns:
            out[col] = out[col].ffill(limit=MAX_FILL_DAYS)
    out["volume"] = out["volume"].fillna(0.0)

    out["filled"] = missing & out["close"].notna()
    out["stale"] = repeated
    out["traded"] = (~out["filled"]) & (~out["stale"]) & out["close"].notna()
    return out.dropna(subset=["close"])


def _check_accumulating(df: pd.DataFrame, inst: Instrument) -> float:
    """Largest |adjclose/close - 1|; raise if an Acc fund has started distributing."""
    if "adjclose" not in df.columns or df["adjclose"].isna().all():
        return float("nan")
    both = df[["close", "adjclose"]].dropna()
    if both.empty:
        return float("nan")
    dev = float((both["adjclose"] / both["close"] - 1.0).abs().max())
    if inst.accumulating and dev > ADJ_CLOSE_TOL:
        raise ETFDataError(
            f"{inst.key} ({inst.yahoo}) is registered as accumulating but adjclose "
            f"deviates from close by up to {dev * 100:.2f} % — it is distributing. "
            f"Switch to adjclose and set accumulating=False in shared/etf_universe.py, "
            f"or every backtest silently loses the dividend.")
    return dev


# ── the loader ────────────────────────────────────────────────────────────────

def load(name: str, start: str = "2005-01-01", end: Optional[str] = None,
         base: str = "EUR", backfill: bool = False,
         use_cache: bool = True) -> pd.DataFrame:
    """One instrument, OHLCV converted to `base`, quality-flagged.

    Returns [open, high, low, close, volume, traded, stale, filled] and fills
    `df.attrs` with source, currencies, FX source, and the counts a caller needs
    to judge whether the series is fit to trade.

    `backfill=True` splices the registered proxy chain onto the front, joined on
    level at the handover so the proxy contributes only its returns, and records
    the handover in `df.attrs["backfilled_before"]`. Off by default: a proxy is a
    different fund tracking a different index, so the join is a modelling choice,
    not data. Use it to buy statistical power for phase-level testing, never to
    quote a headline number.
    """
    inst = resolve(name)
    cache = CACHE_DIR / f"{inst.key}_{base}_{'bf' if backfill else 'raw'}.parquet"
    # The snapshot is always the FULL history; `start` only slices what is
    # returned. Caching whatever the first caller happened to ask for poisons
    # every later request: a `load_panel("P1")` asking from 2018-03-27 wrote a
    # 2018 snapshot, and the next call asking from 2013 silently got 2018 back —
    # which quietly cut five years off the ablation without any error.
    fetch_start = min(start, inst.inception) if not backfill else min(start, "1985-01-01")
    if use_cache and cache.exists():
        df = pd.read_parquet(cache)
        df = df.loc[df.index >= pd.Timestamp(start, tz="UTC")]
        if end:
            df = df.loc[df.index <= pd.Timestamp(end, tz="UTC")]
        # Recount on the slice. The cached attrs describe the whole file, and a
        # quality report that says "10.75 % stale" for a window whose stale bars
        # were all trimmed away is worse than no report: it argues against data
        # that is in fact clean.
        return _restate(df, inst, base)

    raw = fetch_yahoo(inst.yahoo, start=fetch_start, end=end)
    reported = (raw.attrs.get("currency") or "").upper()
    if reported and reported != inst.quote_ccy.upper():
        # GBp vs GBP is the classic: a hundred-fold error dressed as a label.
        raise ETFDataError(
            f"{inst.key}: registry says {inst.quote_ccy}, Yahoo says {reported!r} for "
            f"{inst.yahoo}. Fix shared/etf_universe.py before trusting this series.")
    adj_dev = _check_accumulating(raw, inst)

    cal = target_calendar(str(raw.index.min().date()), end)
    df = _mark_quality(raw, cal)
    full_from = df.index.min()

    fx_src = "none"
    if inst.quote_ccy != base:
        fx = fx_series(inst.quote_ccy, base, start=str(df.index.min().date()))
        fx_src = fx.attrs.get("source", "?")
        rate = fx.reindex(df.index.union(fx.index)).ffill().reindex(df.index)
        if rate.isna().any():
            raise ETFDataError(
                f"{inst.key}: FX {inst.quote_ccy}->{base} missing on "
                f"{int(rate.isna().sum())} of {len(rate)} bars")
        for col in ("open", "high", "low", "close"):
            df[col] = df[col] * rate

    attrs = dict(key=inst.key, isin=inst.isin, ticker=inst.yahoo, venue=inst.venue,
                 quote_ccy=inst.quote_ccy, base_ccy=base, fx_source=fx_src,
                 adj_close_max_dev=adj_dev, source="yahoo")
    if backfill:
        # Splice onto the *trustworthy* part of the real series, not onto its
        # listing date. Joining a proxy to IWDA's 2009-2012 stretch would anchor
        # the whole reconstruction to bars that repeat the previous close on 40
        # to 81 % of days — exactly the data `usable_from` exists to discard.
        floor = pd.Timestamp(inst.usable_from, tz="UTC")
        if df.index.min() < floor and len(df.loc[df.index >= floor]):
            attrs["trimmed_to_usable"] = inst.usable_from
            df = df.loc[df.index >= floor]
        df, attrs = _splice_proxies(df, inst, base, start, attrs)

    df = df[["open", "high", "low", "close", "volume", "traded", "stale", "filled"]]
    attrs.update(n_bars=int(len(df)), n_stale=int(df["stale"].sum()),
                 n_filled=int(df["filled"].sum()),
                 stale_pct=round(float(df["stale"].mean() * 100), 2),
                 filled_pct=round(float(df["filled"].mean() * 100), 2))
    df.attrs.update(attrs)
    if use_cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        df.to_parquet(cache)
    out = df.loc[df.index >= pd.Timestamp(start, tz="UTC")]
    if end:
        out = out.loc[out.index <= pd.Timestamp(end, tz="UTC")]
    return _restate(out, inst, base) if len(out) != len(df) else df


def _restate(df: pd.DataFrame, inst: Instrument, base: str) -> pd.DataFrame:
    """Attach attrs describing the frame as it stands now."""
    df = df.copy()
    df.attrs.update(
        key=inst.key, isin=inst.isin, ticker=inst.yahoo, venue=inst.venue,
        quote_ccy=inst.quote_ccy, base_ccy=base, source="yahoo",
        fx_source=("none" if inst.quote_ccy == base else "ecb"),
        adj_close_max_dev=0.0,
        n_bars=int(len(df)), n_stale=int(df["stale"].sum()),
        n_filled=int(df["filled"].sum()),
        stale_pct=round(float(df["stale"].mean() * 100), 2),
        filled_pct=round(float(df["filled"].mean() * 100), 2))
    return df


def recommend_chain(sleeve: str, quality: Optional[dict] = None,
                    corr_tolerance: float = 0.03) -> list[dict]:
    """The proxy chain to use for one sleeve, chosen from measured quality.

    The obvious rule — take the candidate with the longest history — is wrong,
    and the measurements show exactly how. For World, both SPY and the MSCI World
    index reach 1999. SPY tracks at monthly correlation 0.964 and runs 3.00
    points a year *ahead* of the sleeve, because US equities beat world equities
    over the window; that gap is a real difference in what the two things hold
    and no adjustment fixes it. The MSCI World index tracks at 0.983 and runs
    2.03 points *behind*, because it is the price index of the very benchmark the
    fund tracks and the gap is the dividend yield. Same reach, opposite quality.

    So the rule here is: among proxies that extend the window, keep those within
    `corr_tolerance` of the best monthly correlation, then take the deepest of
    those, breaking ties on correlation. Repeat from the new start, so a sleeve
    can be covered by several links — EM ends up as EEM back to 2003 and then
    VEIEX to 1999 rather than one weaker series for the whole stretch.
    """
    quality = proxy_quality() if quality is None else quality
    inst = resolve(sleeve)
    accepted = [dict(ticker=k.split("|", 1)[1], **v)
                for k, v in quality.items()
                if k.startswith(inst.key + "|") and v.get("grade") != "zavrni"]
    chain: list[dict] = []
    cursor = inst.usable_from
    while True:
        ext = [m for m in accepted if m["first"] < cursor and m not in chain]
        if not ext:
            break
        best = max(m["corr_1m"] for m in ext)
        near = [m for m in ext if m["corr_1m"] >= best - corr_tolerance]
        pick = sorted(near, key=lambda m: (m["first"], -m["corr_1m"]))[0]
        chain.append(pick)
        cursor = pick["first"]
    return chain


def _drift_adjustment(m: dict, index: pd.DatetimeIndex,
                      trading_days: int = 252) -> pd.Series:
    """Daily return to add to a proxy so its level is comparable to the sleeve.

    Only two causes are mechanical enough to correct, and both are declared in
    the registry rather than inferred from the size of the gap:

      `cash`     the proxy is an excess-return commodity index. Bloomberg
                 Commodity and S&P GSCI in their excess-return form exclude the
                 yield on the collateral the fund actually holds, and the ETF
                 includes it. The correction is the real euro cash rate, which
                 this module now has, not a constant.
      `measured` the proxy is a price index of the sleeve's own benchmark, so the
                 gap is the dividend yield. The overlap measurement is the best
                 estimate of it we have.

    Everything else is left alone. A gap that comes from holding different
    companies is not an error to be corrected; correcting it would manufacture a
    series that never existed.
    """
    mode = m.get("drift_correct")
    if mode == "cash":
        cr = cash_rate(start=str(index.min().date()))
        daily = (cr.reindex(index.union(cr.index)).ffill().reindex(index).fillna(0.0)
                 / 100.0 / trading_days)
        return daily
    if mode == "measured":
        return pd.Series(m.get("drift_pp", 0.0) / 100.0 / trading_days, index=index)
    return pd.Series(0.0, index=index)


def _splice_proxies(df: pd.DataFrame, inst: Instrument, base: str, start: str,
                    attrs: dict, quality: Optional[dict] = None) -> tuple[pd.DataFrame, dict]:
    """Extend `df` backwards along the recommended chain, joined on level.

    Three rules, each of which exists because breaking it produces a series that
    looks fine and is wrong:

    1. The join is multiplicative at the handover, so a proxy contributes only
       its *returns* and never its price level.
    2. A proxy graded `mesecno` is spliced, but the frame is stamped
       `daily_valid_from`. Its daily alignment is broken — a US fund prices at
       22:00 CET against a London close at 17:30 — so a daily-bar strategy run
       over the spliced region measures the closing-time offset, not the
       strategy. Consumers must respect that stamp.
    3. The drift correction is applied per `_drift_adjustment`, and only where a
       mechanical cause is declared.
    """
    quality = proxy_quality() if quality is None else quality
    chain = recommend_chain(inst.key, quality)
    if not chain:
        attrs["backfill_chain"] = []
        attrs["daily_valid_from"] = str(df.index.min().date())
        return df, attrs

    declared = {p.ticker: p for p in inst.proxies}
    first = df.index.min()
    used: list[str] = []
    for m in chain:
        if first <= pd.Timestamp(start, tz="UTC"):
            break
        ticker = m["ticker"]
        pr = declared.get(ticker)
        try:
            p = fetch_yahoo(ticker, start=start, end=str(first.date()))
        except ETFDataError:
            continue
        p = p[p.index < first]
        if p.empty:
            continue
        px = p["adjclose"].where(p["adjclose"].notna(), p["close"]).dropna()
        ccy = (p.attrs.get("currency") or (pr.ccy if pr else "USD")).upper()
        if ccy != base:
            fx = fx_series(ccy, base, start=start)
            px = (px * fx.reindex(px.index.union(fx.index)).ffill().reindex(px.index)).dropna()
        if px.empty:
            continue

        ret = px.pct_change().fillna(0.0)
        adj = _drift_adjustment({**m, "drift_correct": getattr(pr, "drift_correct", None)},
                                px.index)
        level = (1.0 + ret + adj).cumprod()
        level = level / level.iloc[-1] * float(df["close"].iloc[0])

        add = pd.DataFrame(index=px.index)
        for col in ("open", "high", "low", "close"):
            add[col] = level
        add["volume"] = 0.0
        add["traded"], add["stale"], add["filled"] = True, False, False
        df = pd.concat([add, df])
        used.append(f"{ticker}({m['grade']})")
        if m["grade"] != "dnevno":
            attrs["daily_valid_from"] = str(first.date())
        first = df.index.min()

    attrs["backfilled_before"] = str(attrs.get("daily_valid_from") or first.date())
    attrs["backfill_chain"] = used
    attrs.setdefault("daily_valid_from", str(df.index.min().date()))
    return df, attrs


def load_panel(which, start: str = "2005-01-01", end: Optional[str] = None,
               base: str = "EUR", backfill: bool = False,
               join: str = "inner", min_quality: bool = True) -> tuple[pd.DataFrame, dict]:
    """Close-price panel for a portfolio name ('P1'/'P2') or a list of keys.

    `join='inner'` (default) starts the panel where every member has real data —
    the honest window. `join='outer'` keeps each series' own history and leaves
    NaN, for per-instrument work.

    `min_quality=True` moves `start` forward to `usable_start(...)`, past the
    years in which a line's closes are mostly stale repeats. That is not a
    cosmetic trim: on IWDA.L it discards 2009-2012, where 40-81 % of bars repeat
    the previous close, and those are precisely the bars on which a trend rule
    would report fills nobody could have got.
    """
    keys = (list(PORTFOLIOS[which]) if isinstance(which, str) and which in PORTFOLIOS
            else list(which))
    if min_quality:
        floor = max(UNIVERSE[k].usable_from for k in keys)
        start = max(start, floor)
    frames = {k: load(k, start=start, end=end, base=base, backfill=backfill)
              for k in keys}
    panel = pd.DataFrame({k: f["close"] for k, f in frames.items()})
    if join == "inner":
        panel = panel.dropna()
    return panel, frames


def quality_report(frames: dict) -> pd.DataFrame:
    """One row per instrument: what the loader had to do to the data."""
    rows = []
    for k, f in frames.items():
        a = f.attrs
        rows.append(dict(
            key=k, ticker=a.get("ticker"), venue=a.get("venue"),
            ccy=a.get("quote_ccy"), fx=a.get("fx_source"),
            first=str(f.index.min().date()), last=str(f.index.max().date()),
            bars=a.get("n_bars"), stale_pct=a.get("stale_pct"),
            filled_pct=a.get("filled_pct"),
            adj_dev_pct=round((a.get("adj_close_max_dev") or 0.0) * 100, 3),
            backfill=a.get("backfilled_before", "-")))
    return pd.DataFrame(rows).set_index("key")
