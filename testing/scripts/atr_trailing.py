"""Step 8: an ATR trailing stop instead of the trackline exit.

Pre-registered in `testing/nacrt_koraka_6_in_8.md`, specification from
`nacrt_izvedbe_v2.txt`.

    peak = highest close since entry
    exit when close < peak - N * ATR(14)

replacing the trend-break exit. Blow-off is untouched.

Two things the original spec insisted on, and both are easy to get wrong:

  The primary metric is FURTHER DRAWDOWN, not return. A stop is there to protect
  against falls, so it is judged on falls.

  The comparison group is days IN POSITION, not every day in the sample. Judging
  an exit rule on days it cannot act is the same error that made the blow-off
  analysis wrong early in this project.

N is swept over the original {1.5, 2, 2.5, 3, 4} to read the SHAPE. The argmax is
not taken — PBO of 0.672 and 0.694 established that parameter selection does not
transfer here. If this were adopted the value would be 3, the Chandelier
convention, chosen outside this data.

Output: testing/data/atr_trailing.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "testing", ROOT / "lean"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import numpy as np
import pandas as pd

from shared import indicators as ind
from shared.costs import net_returns, turnover
from shared.warmup import trim_warmup
from testing.scripts import engine
from testing.scripts.two_tracklines import sortino, maxdd, FEE, PPY, SUBPERIODS

np.seterr(all="ignore")

SRC = ROOT / "testing" / "data" / "sources"
REF = ROOT / "testing" / "data" / "reference_positions.parquet"
OUT = ROOT / "testing" / "data" / "atr_trailing.json"
N_GRID = [1.5, 2.0, 2.5, 3.0, 4.0]
ATR_LEN = 14


def atr(raw, n=ATR_LEN):
    h, l, c = raw["high"], raw["low"], raw["close"].shift(1)
    tr = pd.concat([h - l, (h - c).abs(), (l - c).abs()], axis=1).max(axis=1)
    return tr.rolling(n, min_periods=n).mean()


def run_stop(df, cfg, a, mult):
    """State machine with the trend break replaced by a trailing ATR stop."""
    n = len(df)
    bull = df["bull_condition"].fillna(False).to_numpy()
    blow = df["blowoff"].fillna(False).to_numpy()
    close = df["close"].to_numpy(float)
    av = a.reindex(df.index).to_numpy(float)
    S_BULL, S_BEAR = 1, 3
    sig = np.full(n, S_BEAR, np.int8)
    alloc = np.zeros(n, np.float32)
    chg = np.zeros(n, bool)
    cur, prev, bsig, hold, peak = S_BEAR, S_BEAR, 999, 0, np.nan
    for i in range(n):
        bsig += 1
        hold = hold + 1 if bull[i] else 0
        if cur == S_BULL:
            peak = max(peak, close[i])
            stop = peak - mult * (av[i] if np.isfinite(av[i]) else 0.0)
            if (np.isfinite(av[i]) and close[i] < stop) or blow[i]:
                cur, bsig, peak = S_BEAR, 0, np.nan
        elif cur == S_BEAR:
            if bull[i] and hold >= cfg.confirm_bars and bsig >= cfg.reentry_hold:
                cur, bsig, peak = S_BULL, 0, close[i]
        alloc[i] = 100.0 if cur == S_BULL else 0.0
        chg[i] = cur != prev
        prev = cur
        sig[i] = cur
    out = df.copy()
    out["signal_state"] = sig
    out["target_alloc"] = alloc
    out["signal_changed"] = chg
    out["display_state"] = sig
    out["bars_since_signal"] = 0
    out["below_count"] = 0
    out["bull_hold"] = 0
    return out


def evaluate(raw, mult):
    cfg = engine.make_config("lean")
    smod = engine.strategy_module("lean")
    df = smod.compute_features(raw, None, cfg)
    if mult is None:
        st = smod.run_state_machine(df, cfg)
    else:
        st = run_stop(df, cfg, atr(raw), mult)
    st = trim_warmup(st)
    pos = pd.Series(engine.position(st, s_bull_code=1), index=st.index, dtype=float)
    return pos


def in_position_stats(pos, ret):
    """Downside capture and further drawdown measured ONLY while long."""
    m = pos.to_numpy() > 0.5
    b = ret.reindex(pos.index).fillna(0.0).to_numpy()
    if m.sum() < 30:
        return None
    dn = b < 0
    both = m & dn
    # share of the market's down-moves we take, counted over days in position
    cap = float(b[both].sum() / b[dn].sum() * 100)
    # worst run-down while holding
    eq = np.cumprod(1 + np.where(m, b, 0.0))
    return {"days_long": int(m.sum()),
            "downside_capture_in_pos": round(cap, 1),
            "worst_drawdown_while_long": round(
                float((eq / np.maximum.accumulate(eq) - 1).min() * 100), 1)}


def main() -> int:
    out = {"atr_len": ATR_LEN, "grid": N_GRID}
    for sym, f, tag in (("BTC", "BTC_binance_warmup.parquet", "dnevni"),
                        ("BTC 4h", "BTC_binance_4h.parquet", "4-urni")):
        p = SRC / f
        if not p.exists():
            continue
        raw = pd.read_parquet(p)
        ret = raw["close"].pct_change().fillna(0.0)
        print(f"\n{'='*94}\n{sym} ({tag}) · {len(raw)} barov\n{'='*94}")
        cells = {"trackline (danes)": evaluate(raw, None)}
        for nmul in N_GRID:
            cells[f"ATR × {nmul}"] = evaluate(raw, nmul)

        if sym == "BTC":
            ref = pd.read_parquet(REF)["position"]
            base = cells["trackline (danes)"]
            ok = (base.index.equals(ref.index)
                  and np.allclose(base.to_numpy(), ref.to_numpy(), atol=1e-12))
            print(f"  KONTROLA: trackline = referenca? {'DA' if ok else 'NE'}")
            if not ok:
                print("  USTAVLJAM.")
                return 2

        print(f"\n  {'celica':<18}{'Sortino':>9}{'CAGR':>7}{'MaxDD':>8}{'konec':>7}"
              f"{'izpost':>8}{'posl':>6}{'zajem− v poz':>14}{'najh. padec v poz':>19}")
        res = {}
        for nm, pos in cells.items():
            r = net_returns(pos, ret, FEE).to_numpy(float)
            eq = np.cumprod(1 + r)
            ip = in_position_stats(pos, ret)
            m = {"sortino": round(sortino(r), 3),
                 "cagr": round(float((float(eq[-1]) ** (PPY / len(r)) - 1) * 100), 1)
                 if tag == "dnevni" else None,
                 "maxdd": round(maxdd(r), 1), "final": round(float(eq[-1]), 2),
                 "exposure": round(float(pos.mean() * 100), 1),
                 "trades": int((np.diff(pos.to_numpy(), prepend=pos.iloc[0]) > 0).sum()),
                 "turnover": round(float(turnover(pos).sum()), 1), **(ip or {})}
            res[nm] = m
            cg = f"{m['cagr']:>6.1f}%" if m["cagr"] is not None else "     —"
            print(f"  {nm:<18}{m['sortino']:>9.3f}{cg}{m['maxdd']:>7.1f}%"
                  f"{m['final']:>6.2f}x{m['exposure']:>7.1f}%{m['trades']:>6d}"
                  f"{m.get('downside_capture_in_pos', float('nan')):>14.1f}"
                  f"{m.get('worst_drawdown_while_long', float('nan')):>19.1f}")
        out[sym] = res

        b = res["trackline (danes)"]
        print(f"\n  SPREJEMNI KRITERIJ (izvirni): zajem navzdol v poziciji se mora")
        print(f"  izboljšati za VEČ KOT 2 o. t. proti {b['downside_capture_in_pos']:.1f}")
        best = None
        for nm, m in res.items():
            if nm == "trackline (danes)":
                continue
            d = b["downside_capture_in_pos"] - m["downside_capture_in_pos"]
            flag = "PRESTANE" if d > 2.0 else ""
            if d > 2.0:
                best = nm
            print(f"    {nm:<18}{m['downside_capture_in_pos']:>7.1f}   "
                  f"izboljšanje {d:+5.1f} o. t.   {flag}")
        out[f"{sym}_passes"] = best

    sh = [k for k in out if k.endswith("_passes")]
    print(f"\n  IZID: " + ("NE PRESTANE — noben ATR množitelj ne izboljša zajema "
                           "navzdol za več kot 2 o. t."
                           if all(out[k] is None for k in sh) else
                           "prestane pri: " + ", ".join(f"{k}: {out[k]}" for k in sh)))
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nJSON -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
