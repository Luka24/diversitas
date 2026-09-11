"""Out-of-sample protocol for the ETF sleeve.

The altcoin campaign converged on a specific answer to "how do I stop fooling
myself", and it is not a train/test split. It is four things, and this module
carries all four across to equities:

  1. a design / validation / hold-out split, with the hold-out quarantined;
  2. anchored walk-forward with an embargo, so a fold never sees its own future;
  3. evaluation on **dated market phases** rather than calendar blocks, plus the
     combinatorial subsets of them (Lopez de Prado's CPCV, with phases as groups);
  4. a paired block-bootstrap confidence interval on every comparison, with the
     rule that an interval containing zero is not a result.

**The thing to face before running any of it.** The altcoin campaign had 3861
daily bars and nine dated phases. Portfolio 1 has 2158 bars from 2018-03-27 and
Portfolio 2 has 1963 from 2019-01-02. Dating MSCI World in EUR over that window
with equity settings yields **three** drawdown phases, not five. Criterion C2 of
the altcoin protocol — win in at least 3 of 5 falling phases — cannot even be
expressed. The honest consequences:

  - The acceptance bar has to be restated for the number of phases that exist
    (`ACCEPT` below), and it is weaker than the crypto one. That is a fact about
    the data, not a choice.
  - Any candidate that survives this should still be treated as unproven. With
    three bear phases, the bootstrap interval on almost any sensible difference
    will contain zero, and the correct reading of that is "we cannot tell",
    not "it works".
  - Statistical power is the strongest argument for the proxy backfill in
    `shared/etf_data.load(backfill=True)`: it buys 2000-2018, which contains the
    dot-com unwind and 2008. Numbers from a backfilled series are not quotable as
    performance, but they are quotable as evidence about robustness — which is
    the question the phase protocol is asking anyway.

Nothing here re-implements a statistic. `testing/scripts/stats.py` supplies the
stationary bootstrap, the deflated Sharpe and PBO; this module supplies the
splits, the phases and the accounting, with `td=252` passed everywhere.
"""
from __future__ import annotations

import sys
from itertools import combinations
from pathlib import Path
from typing import Callable, Iterable, Optional, Sequence

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from testing.scripts import stats as ST  # noqa: E402

TD = 252

# ── the split, fixed before any result is looked at ───────────────────────────
# Chosen on the calendar, not on the data. Design ends before the 2024 rally so
# that the hold-out contains at least one full round trip rather than only a
# drawdown — the mistake the crypto hold-out made by accident, where the whole
# window sat inside one falling phase and could therefore answer only half the
# question.
DESIGN_END      = pd.Timestamp("2023-06-30", tz="UTC")
VALIDATION_END  = pd.Timestamp("2025-06-30", tz="UTC")
HOLDOUT_START   = pd.Timestamp("2025-07-01", tz="UTC")

EMBARGO_DAYS = 21          # one month; longest indicator lookback is 200 bars,
                           # so also purge that many bars before each OOS block


def split(series: pd.Series, which: str) -> pd.Series:
    if which == "design":
        return series.loc[series.index <= DESIGN_END]
    if which == "validation":
        return series.loc[(series.index > DESIGN_END) & (series.index <= VALIDATION_END)]
    if which == "holdout":
        return series.loc[series.index >= HOLDOUT_START]
    if which == "all":
        return series
    raise ValueError(f"unknown split {which!r}")


# ── phase dating, calibrated for equities on a short sample ───────────────────
# Pagan-Sossounov's published settings are monthly: window +/- 8 months, minimum
# phase 4 months, amplitude filter ~20 %. Translated to daily bars that is
# K = 126, min phase 84, amplitude 0.15 — and on this sample those settings find
# one rising and two falling phases, because they **censor the COVID crash
# entirely**: -34.0 % in 33 trading days is below the 84-bar minimum duration.
# Throwing away the deepest and fastest drawdown in the sample, on a sample this
# short, would make the whole protocol meaningless.
#
# So the defaults are the short-sample settings, K = 63 / 21 bars / 10 %, which
# date 8 rising and 9 falling phases over 2013-2026 and include 2018 Q4, COVID,
# 2022 and the April 2025 drop. The published settings remain available and are
# reported as a robustness check — a candidate whose verdict depends on which of
# the two is used has not been shown to work.
#
#   K = 63,  min 21,  ampl 0.10  ->  8 rising, 9 falling   (default)
#   K = 126, min 84,  ampl 0.15  ->  1 rising, 2 falling   (PS_SETTINGS)
#   crypto (faze_ciklov.py): 90 / 120 / 0.25, right for crypto, finds almost
#   nothing on equities
K_WINDOW, MIN_PHASE, MIN_AMPL = 63, 21, 0.10
PS_SETTINGS = dict(k=126, min_phase=84, min_ampl=0.15)   # published, for the check


def _alternate(points: list[tuple[int, str]], x: np.ndarray) -> list[tuple[int, str]]:
    """Collapse runs of same-type turning points, keeping the most extreme."""
    out: list[tuple[int, str]] = []
    for i, t in points:
        if out and out[-1][1] == t:
            j, _ = out[-1]
            if (x[i] > x[j]) if t == "V" else (x[i] < x[j]):
                out[-1] = (i, t)
            continue
        out.append((i, t))
    return out


def date_phases(price: pd.Series, k: int = K_WINDOW, min_phase: int = MIN_PHASE,
                min_ampl: float = MIN_AMPL) -> list[tuple]:
    """Bry-Boschan / Pagan-Sossounov turning points. Returns [(from, to, kind)]
    with kind in {'rast', 'padec'} — the vocabulary of `faze_ciklov.py`, so the
    crypto and equity reports read side by side.

    The censoring step deletes **both** ends of an offending phase and then
    re-imposes alternation, rather than deleting the later point alone. Deleting
    one end leaves a peak followed by a peak; the crypto version then deletes the
    next point blindly, which on a long equity series merges a real trough away
    and produces phases labelled 'falling' that end 48 % higher than they began.
    That is not a cosmetic bug: those labels are the groups the whole protocol in
    this module partitions on. The postcondition below now fails loudly instead.
    """
    s = price.dropna()
    x = np.log(s.to_numpy(float))
    idx = s.index
    n = len(x)
    if n < 2 * k + 2:
        return []

    pts: list[tuple[int, str]] = []
    for i in range(k, n - k):
        w = x[i - k:i + k + 1]
        if x[i] == w.max():
            pts.append((i, "V"))
        elif x[i] == w.min():
            pts.append((i, "D"))
    clean = _alternate(sorted(pts), x)

    while len(clean) > 2:
        worst = None
        for a in range(len(clean) - 1):
            i, _ = clean[a]
            j, _ = clean[a + 1]
            too_short = (j - i) < min_phase
            too_small = abs(x[j] - x[i]) < np.log(1 + min_ampl)
            if too_short or too_small:
                # break the *smallest* offender first, so a marginal phase never
                # takes a large neighbour down with it
                score = abs(x[j] - x[i])
                if worst is None or score < worst[0]:
                    worst = (score, a)
        if worst is None:
            break
        a = worst[1]
        clean = _alternate([p for q, p in enumerate(clean) if q not in (a, a + 1)], x)

    out = []
    for a in range(len(clean) - 1):
        i, ti = clean[a]
        j, _ = clean[a + 1]
        kind = "rast" if ti == "D" else "padec"
        move = x[j] - x[i]
        # postcondition: a rising phase rises. If this ever trips, the censoring
        # merged two turning points of the same type and every group below is wrong.
        if (kind == "rast") != (move > 0):
            raise AssertionError(
                f"phase dating produced a {kind} phase of {np.expm1(move):+.1%} "
                f"between {idx[i].date()} and {idx[j].date()}")
        out.append((idx[i], idx[j], kind))
    return out


def phase_table(price: pd.Series, **kw) -> pd.DataFrame:
    rows = []
    for a, b, kind in date_phases(price, **kw):
        rows.append(dict(kind=kind, start=a.date(), end=b.date(),
                         days=int((b - a).days),
                         move_pct=round(float(price.loc[b] / price.loc[a] - 1) * 100, 1)))
    return pd.DataFrame(rows)


# ── per-phase and combinatorial evaluation ────────────────────────────────────

def compounded(r: np.ndarray) -> float:
    """Compounded return. Used instead of a ratio inside falling phases: when the
    mean is negative, Sortino inverts — the same loss scores *better* the more it
    oscillates — so ratios cannot be compared there. This trap cost the altcoin
    campaign a round of wrong conclusions."""
    r = np.asarray(r, float)
    return float(np.prod(1.0 + r[np.isfinite(r)]) - 1.0)


def sortino(r: np.ndarray, td: int = TD) -> float:
    r = np.asarray(r, float)
    r = r[np.isfinite(r)]
    if len(r) < 10:
        return np.nan
    dn = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(td)
    return float(r.mean() * td / dn) if dn > 1e-12 else np.nan


def per_phase(cand: pd.Series, base: pd.Series, phases: Sequence[tuple],
              td: int = TD) -> pd.DataFrame:
    """Candidate vs base on every dated phase, using the right statistic for the
    phase direction."""
    rows = []
    for a, b, kind in phases:
        m = (cand.index >= a) & (cand.index <= b)
        if m.sum() < 30:
            continue
        c, s = cand[m].to_numpy(), base.reindex(cand.index)[m].to_numpy()
        if kind == "padec":
            vc, vs = compounded(c), compounded(s)
        else:
            vc, vs = sortino(c, td), sortino(s, td)
        rows.append(dict(kind=kind, start=a.date(), end=b.date(), days=int(m.sum()),
                         cand=round(vc, 3), base=round(vs, 3),
                         wins=bool(vc > vs)))
    return pd.DataFrame(rows)


def combinatorial(cand: pd.Series, base: pd.Series, phases: Sequence[tuple],
                  k: int = 3, td: int = TD) -> dict:
    """Lopez de Prado's CPCV with dated phases as the groups.

    Every C(n, k) subset of phases becomes a test set; the share of subsets the
    candidate wins is far more stable than one hold-out. With three or four
    phases, C(n,k) is small and this is weak evidence — reported anyway, with the
    count, so nobody reads 67 % off two subsets as a result.
    """
    n = len(phases)
    if n < k:
        return dict(n_phases=n, n_subsets=0, win_rate=np.nan, median_diff=np.nan)
    wins, diffs = 0, []
    subsets = list(combinations(range(n), k))
    for combo in subsets:
        m = np.zeros(len(cand), dtype=bool)
        falling = False
        for pi in combo:
            a, b, kind = phases[pi]
            m |= np.asarray((cand.index >= a) & (cand.index <= b))
            falling |= (kind == "padec")
        c = cand[m].to_numpy()
        s = base.reindex(cand.index)[m].to_numpy()
        vc, vs = ((compounded(c), compounded(s)) if falling
                  else (sortino(c, td), sortino(s, td)))
        if np.isfinite(vc) and np.isfinite(vs):
            diffs.append(vc - vs)
            wins += int(vc > vs)
    return dict(n_phases=n, n_subsets=len(subsets),
                win_rate=round(wins / max(len(subsets), 1) * 100, 1),
                median_diff=round(float(np.median(diffs)), 4) if diffs else np.nan)


# ── paired bootstrap: the rule that an interval containing zero is no result ──

def _stationary_index(n: int, n_boot: int, mean_block: int, seed: int) -> np.ndarray:
    """(n_boot, n) resampling indices for the Politis-Romano stationary bootstrap.

    Same construction as `stats.stationary_bootstrap`, built with array ops
    instead of a double Python loop. That version costs n_boot x n interpreter
    steps — five thousand resamples of two thousand bars is ten million — which
    on this sample turns a routine check into something nobody runs. The output
    is one index matrix, so the *same* blocks can be applied to both series,
    which is what makes the difference paired.
    """
    rng = np.random.default_rng(seed)
    ar = np.arange(n)
    restart = rng.random((n_boot, n)) < (1.0 / mean_block)
    restart[:, 0] = True
    starts = np.where(restart, rng.integers(0, n, (n_boot, n)), 0)
    last = np.maximum.accumulate(np.where(restart, ar, -1), axis=1)
    return (np.take_along_axis(starts, last, axis=1) + (ar - last)) % n


def paired_diff_ci(cand: pd.Series, base: pd.Series,
                   metric: Callable[[np.ndarray], float] = None,
                   n_boot: int = 5000, mean_block: int = 20,
                   seed: int = 42, alpha: float = 0.05, td: int = TD) -> dict:
    """CI for metric(cand) - metric(base), resampling **the same blocks** from
    both series.

    Resampling them independently would compare two different histories and
    inflate the interval; the pairing is what makes the difference meaningful.
    """
    metric = metric or (lambda r: sortino(r, td))
    c, b = cand.align(base, join="inner")
    C, B = c.to_numpy(float), b.to_numpy(float)
    idx = _stationary_index(len(C), n_boot, mean_block, seed)
    diffs = np.array([metric(C[row]) - metric(B[row]) for row in idx])
    diffs = diffs[np.isfinite(diffs)]
    lo, hi = np.percentile(diffs, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    point = metric(C) - metric(B)
    return dict(point=float(point), lo=float(lo), hi=float(hi),
                p_better=float((diffs > 0).mean()),
                excludes_zero=bool(lo > 0 or hi < 0),
                verdict=("boljsi" if lo > 0 else "slabsi" if hi < 0 else "nedokazano"))


# ── anchored walk-forward ─────────────────────────────────────────────────────

def oos_blocks(index: pd.DatetimeIndex, n_blocks: int = 5,
               first_train_years: float = 2.0, td: int = TD) -> list[tuple]:
    """Equal-length OOS blocks after an initial training period.

    Anchored, not rolling: each fold trains on everything up to the block minus
    the embargo. With eight years of data a rolling window would leave under two
    years to fit a 200-bar indicator on, which is not a fit, it is a coin toss.
    """
    start = index[0] + pd.Timedelta(days=int(first_train_years * 365.25))
    rest = index[index >= start]
    if len(rest) < n_blocks * 60:
        n_blocks = max(1, len(rest) // 60)
    edges = np.array_split(rest, n_blocks)
    return [(e[0], e[-1]) for e in edges if len(e)]


def walk_forward(returns_for: Callable[[dict], pd.Series],
                 optimise: Callable[[pd.Timestamp], dict],
                 index: pd.DatetimeIndex, blocks: Optional[list] = None,
                 embargo_days: int = EMBARGO_DAYS) -> tuple[pd.Series, list[dict]]:
    """Fit on train, apply to the next unseen block as-is, stitch the OOS pieces.

    `optimise(train_end)` must look at nothing after `train_end`; `returns_for(cfg)`
    returns the full-history series for a config, from which only the OOS slice is
    taken. The embargo removes the bars between train end and block start, which
    is what stops a 200-bar moving average from carrying the block's own data
    back into the training window.
    """
    blocks = blocks or oos_blocks(index)
    parts, fold_params = [], []
    for (b0, b1) in blocks:
        train_end = b0 - pd.Timedelta(days=embargo_days)
        cfg = optimise(train_end)
        fold_params.append(dict(block_start=str(b0.date()), block_end=str(b1.date()),
                                train_end=str(train_end.date()), params=cfg))
        r = returns_for(cfg)
        parts.append(r.loc[b0:b1])
    return (pd.concat(parts) if parts else pd.Series(dtype=float)), fold_params


# ── acceptance criteria, restated for the data that exists ────────────────────

ACCEPT = dict(
    C1="wins in a majority of RISING phases",
    C2="wins in a majority of FALLING phases",
    C3="wins in >= 60 % of the C(n,3) phase subsets  (crypto used 70 % over 84 "
       "subsets; with 3-4 phases there are 1-4 subsets, so this criterion is "
       "reported for completeness and carries almost no weight)",
    C4="the 95 % paired block-bootstrap interval on full history excludes zero "
       "in the favourable direction",
    C5="it still holds after costs at 2x the assumed spread, because the whole "
       "cost estimate here is an assumption until real fills exist",
)


def verdict(phase_df: pd.DataFrame, comb: dict, ci: dict,
            comb_threshold: float = 60.0) -> dict:
    """Apply ACCEPT and return which criteria passed. Deliberately returns the
    detail rather than a single boolean: 'rejected' and 'rejected because there
    were two falling phases' are different findings."""
    rising = phase_df[phase_df["kind"] == "rast"]
    falling = phase_df[phase_df["kind"] == "padec"]
    c1 = bool(len(rising)) and rising["wins"].sum() > len(rising) / 2
    c2 = bool(len(falling)) and falling["wins"].sum() > len(falling) / 2
    c3 = bool(np.isfinite(comb.get("win_rate", np.nan))
              and comb["win_rate"] >= comb_threshold)
    c4 = bool(ci.get("excludes_zero") and ci.get("point", 0) > 0)
    return dict(C1=c1, C2=c2, C3=c3, C4=c4,
                rising=f"{int(rising['wins'].sum())}/{len(rising)}" if len(rising) else "0/0",
                falling=f"{int(falling['wins'].sum())}/{len(falling)}" if len(falling) else "0/0",
                subsets=comb.get("n_subsets"),
                accepted=bool(c1 and c2 and c4))
