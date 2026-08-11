"""Donchian on ETH — one pre-registered hypothesis, one shot.

Pre-registered in `testing/nacrt_eth_donchian.md`, committed before this ran.

    Donchian confirmation, period 20, unconditional, improves the strategy on ETH.

Period 20 was fixed from the BTC evidence — middle of the 12-22 plateau, and
unlike BTC's best (12) it is not adjacent to the grid edge. NO sweep is run here.
The entire value of an out-of-sample test is that the choice was made elsewhere;
searching ETH for a good period would turn this into a second sweep and prove
nothing.

Costs are 0.30 % PER SIDE — 0.30 % to buy, 0.30 % to sell, 0.60 % per round trip.

The ETH file has no warm-up buffer, so trimming eats 199 bars of real history and
the usable window is 2020-01-01 to 2026-07-27. Sub-period I is 397 days rather
than ~700. Since window I is where Donchian helped most on BTC, that makes this a
stricter test, not a softer one.

Output: testing/data/donchian_eth.json
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

from shared.costs import net_returns, turnover
from shared.warmup import trim_warmup
from testing.scripts import engine

np.seterr(all="ignore")

FEE, PPY, H = 0.30, 365, 20            # FEE is per side
PERIOD = 20
SRC = ROOT / "testing" / "data" / "sources" / "ETH_binance.parquet"
OUT = ROOT / "testing" / "data" / "donchian_eth.json"
SUBPERIODS = [("I", "2019-03-09", "2021-01-31"), ("II", "2021-02-01", "2022-11-30"),
              ("III", "2022-12-01", "2024-09-30"), ("IV", "2024-10-01", "2026-07-29")]


def positions(raw, period):
    kw = ({} if period is None
          else {"use_donchian": True, "donchian_period": int(period)})
    cfg = engine.make_config("lean", **kw)
    smod = engine.strategy_module("lean")
    df = trim_warmup(smod.run_strategy(raw, btc_daily=None, config=cfg).df)
    return pd.Series(engine.position(df, s_bull_code=1), index=df.index,
                     dtype=float), df


def sortino(r):
    d = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(PPY)
    return float(r.mean() * PPY / d) if d > 1e-12 else np.nan


def maxdd(r):
    eq = np.cumprod(1.0 + r)
    return float((eq / np.maximum.accumulate(eq) - 1.0).min() * 100.0)


def capture(pos, bench):
    b = bench.reindex(pos.index).fillna(0.0).to_numpy()
    s = pos.to_numpy() * b
    up, dn = b > 0, b < 0
    return (round(float(s[up].sum() / b[up].sum() * 100), 1),
            round(float(s[dn].sum() / b[dn].sum() * 100), 1))


def metrics(pos, ret):
    r = net_returns(pos, ret, FEE).to_numpy(float)
    eq = np.cumprod(1.0 + r)
    p = pos.to_numpy()
    u, d = capture(pos, ret)
    sd = r.std(ddof=1) * np.sqrt(PPY)
    return {"sortino": round(sortino(r), 3),
            "sharpe": round(float(r.mean() * PPY / sd), 3),
            "cagr": round(float((float(eq[-1]) ** (PPY / len(r)) - 1) * 100), 1),
            "maxdd": round(maxdd(r), 1), "final": round(float(eq[-1]), 2),
            "exposure": round(float(p.mean() * 100), 1),
            "upside_capture": u, "downside_capture": d,
            "trades": int((np.diff(p, prepend=p[0]) > 0).sum()),
            "turnover": round(float(turnover(pos).sum()), 1),
            "fees_pct_of_capital": round(float(turnover(pos).sum()) * FEE, 1)}


def main() -> int:
    raw = pd.read_parquet(SRC)
    ret = raw["close"].pct_change().fillna(0.0)
    rng = np.random.default_rng(20260806)

    p_off, d_off = positions(raw, None)
    p_on, d_on = positions(raw, PERIOD)
    out = {"symbol": "ETH", "fee_per_side_pct": FEE, "period": PERIOD,
           "window": [str(p_off.index[0].date()), str(p_off.index[-1].date())],
           "n_bars": len(p_off),
           "preregistered": "testing/nacrt_eth_donchian.md"}
    print(f"ETH · {len(p_off)} barov · {p_off.index[0].date()} → "
          f"{p_off.index[-1].date()} · 0,30 % NA STRAN")
    print(f"hipoteza: Donchian perioda {PERIOD}, brezpogojno\n")

    m_off, m_on = metrics(p_off, ret), metrics(p_on, ret)
    out["off"], out["on"] = m_off, m_on
    print("CELOTNO OKNO")
    print(f"  {'':14}{'Sortino':>9}{'Sharpe':>8}{'CAGR':>8}{'MaxDD':>8}{'konec':>8}"
          f"{'izpost':>8}{'posl':>6}{'provizije':>11}")
    for lbl, m in (("izklopljen", m_off), (f"Donchian {PERIOD}", m_on)):
        print(f"  {lbl:<14}{m['sortino']:>9.3f}{m['sharpe']:>8.3f}{m['cagr']:>7.1f}%"
              f"{m['maxdd']:>7.1f}%{m['final']:>7.2f}x{m['exposure']:>7.1f}%"
              f"{m['trades']:>6d}{m['fees_pct_of_capital']:>10.1f}%")
    print(f"  {'razlika':<14}{m_on['sortino']-m_off['sortino']:>+9.3f}"
          f"{m_on['sharpe']-m_off['sharpe']:>+8.3f}"
          f"{m_on['cagr']-m_off['cagr']:>+7.1f}o{m_on['maxdd']-m_off['maxdd']:>+7.1f}o"
          f"{m_on['final']-m_off['final']:>+7.2f}x"
          f"{m_on['exposure']-m_off['exposure']:>+7.1f}o"
          f"{m_on['trades']-m_off['trades']:>+6d}")

    # ── sub-periods ───────────────────────────────────────────────────────
    print("\nPODOBDOBJA — meje iste kot na BTC")
    print(f"  {'okno':4}{'dni':>6}{'izklopljen':>12}{'Donchian':>10}   ")
    subs, wins = {}, 0
    for name, a, b in SUBPERIODS:
        w = p_off.index[(p_off.index >= a) & (p_off.index <= b)]
        if len(w) < 60:
            continue
        s0 = sortino(net_returns(p_off.reindex(w), ret, FEE).to_numpy(float))
        s1 = sortino(net_returns(p_on.reindex(w), ret, FEE).to_numpy(float))
        better = s1 > s0
        wins += int(better)
        subs[name] = {"days": len(w), "off": round(float(s0), 3),
                      "on": round(float(s1), 3), "better": bool(better)}
        print(f"  {name:4}{len(w):>6}{s0:>12.3f}{s1:>10.3f}   "
              f"{'boljši' if better else 'slabši'}")
    out["subperiods"] = {"windows": subs, "wins": wins, "n": len(subs)}
    print(f"  boljši v {wins} od {len(subs)}")

    # ── exposure matching: scale the BASELINE DOWN ────────────────────────
    print("\nIZENAČENA IZPOSTAVLJENOST — izklopljeno pomanjšano na Donchianovo")
    k = m_on["exposure"] / m_off["exposure"]
    p_ref = (p_off * k).clip(0.0, 1.0)
    r_ref = net_returns(p_ref, ret, FEE).to_numpy(float)
    _, dn_ref = capture(p_ref, ret)
    em = {"scale": round(float(k), 3),
          "off_scaled_sortino": round(sortino(r_ref), 3),
          "off_scaled_maxdd": round(maxdd(r_ref), 1),
          "off_scaled_downside_capture": dn_ref,
          "off_scaled_exposure": round(float(p_ref.mean() * 100), 1),
          "donchian_maxdd": m_on["maxdd"],
          "donchian_downside_capture": m_on["downside_capture"]}
    print(f"  faktor {k:.3f}   izpostavljenost obeh {em['off_scaled_exposure']:.1f} %")
    print(f"  MaxDD    izklopljeno pomanjšano {em['off_scaled_maxdd']:>7.1f} %   "
          f"Donchian {m_on['maxdd']:>7.1f} %")
    print(f"  zajem-   izklopljeno pomanjšano {dn_ref:>7.1f} %   "
          f"Donchian {m_on['downside_capture']:>7.1f} %")
    total = m_on["maxdd"] - m_off["maxdd"]
    from_expo = em["off_scaled_maxdd"] - m_off["maxdd"]
    em["dd_total"] = round(total, 1)
    em["dd_from_exposure"] = round(from_expo, 1)
    em["dd_from_selection"] = round(total - from_expo, 1)
    print(f"  razčlenitev padca: skupaj {total:+.1f} o. t.  = "
          f"{from_expo:+.1f} manj časa v trgu  {total-from_expo:+.1f} izbira dni")
    out["exposure_matched"] = em

    # ── what does it change, measured on the position ─────────────────────
    print("\nKAJ DONCHIAN SPREMENI (merjeno na poziciji)")
    cl = d_off["close"].to_numpy(float)
    n = len(p_off)
    fwd = np.full(n, np.nan)
    fwd[:n - H] = (cl[H:] / cl[:n - H] - 1) * 100
    ok = np.isfinite(fwd)
    outof = (p_off.to_numpy() > .5) & (p_on.to_numpy() < .5)
    into = (p_off.to_numpy() < .5) & (p_on.to_numpy() > .5)
    pe = {"baseline": round(float(fwd[ok].mean()), 2)}
    print(f"  izhodišče, vsi dnevi: {fwd[ok].mean():+.2f} %")
    for tag, m in (("drži nas ZUNAJ", outof), ("drži nas NOTRI", into)):
        x = fwd[m & ok]
        pe[tag] = {"n": int(m.sum()),
                   "mean_fwd20": round(float(x.mean()), 2) if len(x) else None}
        if len(x):
            print(f"  {tag:16} {int(m.sum()):>4} dni   {x.mean():+6.2f} %"
                  f"   proti izhodišču {x.mean()-fwd[ok].mean():+.2f}")
    out["position_effect"] = pe

    # ── lookahead ─────────────────────────────────────────────────────────
    cand = p_on.index[(p_on.index >= "2020-06-01") & (p_on.index <= "2026-06-30")]
    dates = pd.DatetimeIndex(sorted(rng.choice(cand, size=40, replace=False)))
    bad = []
    for t in dates:
        pt, _ = positions(raw.loc[:t], PERIOD)
        if pt.index[-1] != t or abs(float(pt.iloc[-1]) - float(p_on.loc[t])) > 1e-12:
            bad.append(str(t.date()))
    out["lookahead"] = {"n_dates": len(dates), "n_differing": len(bad)}
    print(f"\nREVIZIJA POGLEDA V PRIHODNOST: {len(dates)} datumov · razlik {len(bad)}")

    # ── verdict against the pre-registered rule ───────────────────────────
    c1 = m_on["sortino"] > m_off["sortino"]
    c2 = wins >= 2
    c3 = m_on["maxdd"] >= em["off_scaled_maxdd"]        # not worse (less negative)
    out["verdict"] = {"c1_sortino": bool(c1), "c2_subperiods": bool(c2),
                      "c3_drawdown": bool(c3), "passes": bool(c1 and c2 and c3)}
    print("\nODLOČITVENO PRAVILO")
    print(f"  1  Sortino boljši od izklopljenega            {'DA' if c1 else 'NE'}")
    print(f"  2  boljši v >= 2 od 4 podobdobij              "
          f"{'DA' if c2 else 'NE'}  ({wins} od {len(subs)})")
    print(f"  3  padec se ne poslabša ob izenačeni izpost.  {'DA' if c3 else 'NE'}")
    print(f"\n  IZID: {'PRESTANE' if (c1 and c2 and c3) else 'NE PRESTANE'}")

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nJSON -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
