"""Step 4 — does the 15-day re-entry pause earn its place?

Pre-registered in `testing/nacrt_korak4.md`, committed at e4cd595 BEFORE this
script was run. Thresholds and sub-periods come from that document and are not
to be edited to fit the output.

The one measurement that shaped the design was taken first: the pause blocks 118
days, but they cluster into 10 episodes, 8 of which ran the full 14 bars. The
effective sample is 10. Nothing here can be significant, and that is stated in
advance so "not significant" is not later reported as news.

Four variants, no new parameters:

    A  unconditional 15 days                     status quo, the control
    B  15 days only after a LOSING trade         uses reentry_hold + the sign of
                                                 the last closed trade
    C  0 days while ma_long_rising, else 15      ma_long_rising already exists
    D  no pause at all                           removes reentry_hold, 10 -> 9

The variants are implemented here rather than in `lean/`, so the frozen reference
from step 2 stays authoritative until a decision is actually taken. Variant A
must reproduce that reference bar for bar, including its SHA256 — if the harness
disagrees with the production engine on the control, the other three numbers mean
nothing and the run aborts.

Output: testing/data/reentry_pause_BTC.json
"""
from __future__ import annotations

import hashlib
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

SYMBOL, FEE, PPY = "BTC", 0.30, 365
SEED = 20260804
NBOOT, BLOCK = 5000, 20
N_PLACEBO = 1000

SRC = ROOT / "testing" / "data" / "sources" / f"{SYMBOL}_binance_warmup.parquet"
REF = ROOT / "testing" / "data" / "reference_positions.parquet"
REF_META = ROOT / "testing" / "data" / "reference_positions.json"
OUT = ROOT / "testing" / "data" / f"reentry_pause_{SYMBOL}.json"

# Fixed in the pre-registration. Not to be re-cut after seeing results.
SUBPERIODS = [("I",   "2019-03-09", "2021-01-31"),
              ("II",  "2021-02-01", "2022-11-30"),
              ("III", "2022-12-01", "2024-09-30"),
              ("IV",  "2024-10-01", "2026-07-29")]

VARIANTS = ("A", "B", "C", "D")
LABEL = {"A": "brezpogojnih 15 dni (danes)",
         "B": "15 dni samo po izgubljenem poslu",
         "C": "0 dni v uptrendu, sicer 15",
         "D": "brez premora"}


# ── state machine, with the pause as the only thing that varies ─────────────
def run_variant(df: pd.DataFrame, cfg, variant: str, hold: int | None = None
                ) -> pd.DataFrame:
    """Replay Lean's state machine with a pluggable re-entry rule.

    Mirrors `lean/diversitas/strategy.py:run_state_machine` exactly apart from the
    pause test. Kept as an explicit copy rather than a hook into the production
    loop so that running this script can never alter live behaviour.

    `hold` overrides reentry_hold for the sensitivity arm of variant B; the
    variants themselves introduce no new number.
    """
    hold = cfg.reentry_hold if hold is None else hold
    n = len(df)
    below = df["below_tl"].fillna(False).to_numpy()
    above = df["above_tl"].fillna(False).to_numpy()
    bull = df["bull_condition"].fillna(False).to_numpy()
    blow = df["blowoff"].fillna(False).to_numpy()
    rising = df["ma_long_rising"].fillna(False).to_numpy()
    close = df["close"].to_numpy(float)

    S_BULL, S_NEUTRAL, S_BEAR = 1, 2, 3
    sig = np.full(n, S_BEAR, np.int8)
    disp = np.full(n, S_BEAR, np.int8)
    alloc = np.zeros(n, np.float32)
    changed = np.zeros(n, bool)

    cur, cur_disp, prev = S_BEAR, S_BEAR, S_BEAR
    bsig, below_c, hold_c = 999, 0, 0
    entry_px = np.nan
    # No trade has closed yet, so there is no loss to react to. B therefore does
    # not pause on the very first entry — which is moot anyway, since bsig starts
    # at 999 and clears every pause.
    last_loss = False
    blocked, entries, exits = [], [], []
    # First bar on which the entry was READY while flat — every entry condition
    # and confirm_bars satisfied, nothing left but the pause. The lag is measured
    # from here, not from the start of the bull_condition run: a blow-off exit
    # leaves bull_condition true, so a run-based lag would count the days we were
    # already IN the trade and report tens of days for a variant that has no
    # pause at all.
    ready_since = -1

    for i in range(n):
        bsig += 1
        below_c = below_c + 1 if below[i] else 0
        hold_c = hold_c + 1 if bull[i] else 0

        if cur == S_BULL:
            if (below[i] and below_c >= cfg.exit_grace_bars) or blow[i]:
                # Net of a round trip: a 0.3 % gain is a loss once both sides are
                # paid, and B is meant to react to what the account did.
                pnl = (close[i] / entry_px) * (1 - FEE / 100) ** 2 - 1
                last_loss = pnl < 0
                exits.append((df.index[i], float(pnl)))
                cur, bsig, entry_px = S_BEAR, 0, np.nan
                ready_since = -1
        elif cur == S_BEAR:
            ready = bull[i] and hold_c >= cfg.confirm_bars
            if not ready:
                ready_since = -1
            else:
                if ready_since < 0:
                    ready_since = i
                if variant == "A":
                    ok = bsig >= hold
                elif variant == "B":
                    ok = bsig >= hold if last_loss else True
                elif variant == "C":
                    ok = True if rising[i] else bsig >= hold
                elif variant == "D":
                    ok = True
                else:
                    raise ValueError(variant)
                if ok:
                    entries.append((df.index[i], i - ready_since))
                    cur, bsig, entry_px = S_BULL, 0, close[i]
                    ready_since = -1
                else:
                    blocked.append(df.index[i])

        if below[i] and below_c >= cfg.exit_grace_bars:
            cur_disp = S_BEAR
        elif above[i] and bull[i]:
            cur_disp = S_BULL
        elif above[i] and not bull[i]:
            cur_disp = S_NEUTRAL

        alloc[i] = 100.0 if cur == S_BULL else 0.0
        changed[i] = cur != prev
        prev = cur
        sig[i], disp[i] = cur, cur_disp

    out = df.copy()
    out["signal_state"] = sig
    out["display_state"] = disp
    out["target_alloc"] = alloc
    out["signal_changed"] = changed
    out.attrs["blocked"] = blocked
    out.attrs["entries"] = entries
    out.attrs["exits"] = exits
    return out


def positions(raw: pd.DataFrame, variant: str, hold: int | None = None):
    smod = engine.strategy_module("lean")
    cfg = engine.make_config("lean")
    feat = smod.compute_features(raw, None, cfg)
    st = run_variant(feat, cfg, variant, hold)
    attrs = dict(st.attrs)
    df = trim_warmup(st)
    df.attrs.update(attrs)
    pos = pd.Series(engine.position(df, s_bull_code=1), index=df.index, dtype=float)
    return pos, df


# ── metrics ─────────────────────────────────────────────────────────────────
def sortino(r):
    d = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(PPY)
    return float(r.mean() * PPY / d) if d > 1e-12 else np.nan


def sharpe(r):
    sd = r.std(ddof=1) * np.sqrt(PPY)
    return float(r.mean() * PPY / sd) if sd > 1e-12 else np.nan


def maxdd(r):
    eq = np.cumprod(1.0 + r)
    return float((eq / np.maximum.accumulate(eq) - 1.0).min() * 100.0)


def capture(pos: pd.Series, bench: pd.Series):
    """Share of the benchmark's up-moves and down-moves that we take part in.

    Gross of costs on purpose: this measures participation, and charging fees
    would mix in turnover, which is reported separately.
    """
    b = bench.reindex(pos.index).fillna(0.0).to_numpy()
    s = pos.to_numpy() * b
    up, dn = b > 0, b < 0
    u = float(s[up].sum() / b[up].sum() * 100) if b[up].sum() else np.nan
    d = float(s[dn].sum() / b[dn].sum() * 100) if b[dn].sum() else np.nan
    return round(u, 1), round(d, 1)


def metrics(pos: pd.Series, raw: pd.DataFrame) -> dict:
    ret = raw["close"].pct_change().fillna(0.0)
    r = net_returns(pos, ret, FEE).to_numpy(float)
    eq = np.cumprod(1.0 + r)
    p = pos.to_numpy()
    u, d = capture(pos, ret)
    return {"sortino": round(sortino(r), 3), "sharpe": round(sharpe(r), 3),
            "cagr": round(float((float(eq[-1]) ** (PPY / len(r)) - 1) * 100), 1),
            "maxdd": round(maxdd(r), 1), "final": round(float(eq[-1]), 3),
            "exposure": round(float(p.mean() * 100), 1),
            "upside_capture": u, "downside_capture": d,
            "trades": int((np.diff(p, prepend=p[0]) > 0).sum()),
            "turnover": round(float(turnover(pos).sum()), 1)}


def digest(pos: pd.Series) -> str:
    h = hashlib.sha256()
    h.update(np.asarray(pos.index.view("int64")).tobytes())
    h.update(np.ascontiguousarray(pos.to_numpy()).tobytes())
    return h.hexdigest()


# ── paired block bootstrap ──────────────────────────────────────────────────
def paired_ci(a: np.ndarray, b: np.ndarray, rng, fn=sortino):
    """Same resampled days on both series, so market movement cancels."""
    n = len(a)
    nb = int(np.ceil(n / BLOCK))
    diffs = []
    for lo in range(0, NBOOT, 500):
        k = min(500, NBOOT - lo)
        st = rng.integers(0, n, size=(k, nb))
        idx = (st[:, :, None] + np.arange(BLOCK)[None, None, :]
               ).reshape(k, nb * BLOCK)[:, :n] % n
        diffs.append(np.array([fn(a[i]) - fn(b[i]) for i in idx]))
    d = np.concatenate(diffs)
    d = d[np.isfinite(d)]
    lo_, hi_ = np.percentile(d, [2.5, 97.5])
    return {"delta": round(float(fn(a) - fn(b)), 3),
            "ci_lo": round(float(lo_), 3), "ci_hi": round(float(hi_), 3),
            "excludes_zero": bool(lo_ > 0 or hi_ < 0)}


def main() -> int:
    raw = pd.read_parquet(SRC)
    ret = raw["close"].pct_change().fillna(0.0)
    rng = np.random.default_rng(SEED)
    out: dict = {"symbol": SYMBOL, "fee_per_side_pct": FEE, "seed": SEED,
                 "nboot": NBOOT, "block": BLOCK,
                 "preregistered": "testing/nacrt_korak4.md @ e4cd595"}

    # ── gate: the control must reproduce the frozen reference ──────────────
    print("KONTROLA — različica A proti zamrznjeni referenci iz 2. koraka")
    pos = {v: positions(raw, v) for v in VARIANTS}
    posA, dfA = pos["A"]
    ref = pd.read_parquet(REF)["position"]
    meta = json.loads(REF_META.read_text(encoding="utf-8"))
    same = posA.index.equals(ref.index) and np.allclose(posA.to_numpy(),
                                                        ref.to_numpy(), atol=1e-12)
    print(f"  serija pozicij enaka        {same}")
    print(f"  SHA256 A                    {digest(posA)[:32]}…")
    if not same:
        print("\n  Harness se ne ujema s produkcijskim motorjem NA KONTROLI.")
        print("  Preostale tri številke so brez pomena. USTAVLJAM.")
        return 2
    print(f"  referenca zamrznjena pri    {meta['git'][:12]}\n")
    out["control_matches_reference"] = True

    # ── episodes the pause actually blocked ────────────────────────────────
    # The state machine runs over the UNTRIMMED frame (2899 bars) because that is
    # what production does; the reported window is the trimmed one (2700). Dates
    # are therefore carried through rather than positions, and episodes are cut to
    # the reported window — indexing one frame with the other's positions is a
    # silent 199-bar shift.
    blocked = [t for t in dfA.attrs["blocked"] if t >= dfA.index[0]]
    eps: list[list[pd.Timestamp]] = []
    for t in blocked:
        if eps and (t - eps[-1][1]).days == 1:
            eps[-1][1] = t
        else:
            eps.append([t, t])
    cl = raw["close"]
    episodes = [{"from": str(a.date()), "to": str(b.date()),
                 "days": int((b - a).days) + 1,
                 "foregone_pct": round(float((cl.loc[b] / cl.loc[a] - 1) * 100), 1)}
                for a, b in eps]
    fg = np.array([e["foregone_pct"] for e in episodes])
    jack = [{"without": episodes[k]["from"],
             "mean": round(float(np.delete(fg, k).mean()), 2)}
            for k in range(len(fg))]
    out["episodes"] = {"n_blocked_days": len(blocked), "n_episodes": len(episodes),
                       "list": episodes, "mean_foregone": round(float(fg.mean()), 2),
                       "median_foregone": round(float(np.median(fg)), 2),
                       "sd_foregone": round(float(fg.std(ddof=1)), 2),
                       "jackknife": jack}
    print(f"EPIZODE — {len(blocked)} blokiranih dni v {len(episodes)} epizodah")
    print(f"  zamujeni gib: povprečje {fg.mean():+.1f} %  mediana "
          f"{np.median(fg):+.1f} %  sd {fg.std(ddof=1):.1f}")
    lo_j = min(j["mean"] for j in jack)
    hi_j = max(j["mean"] for j in jack)
    print(f"  jackknife: povprečje niha med {lo_j:+.2f} % in {hi_j:+.2f} %, "
          f"odvisno od tega, katero epizodo izpustim")
    worst = min(jack, key=lambda j: j["mean"])
    print(f"  najbolj nosilna epizoda: {worst['without']} "
          f"(brez nje povprečje pade na {worst['mean']:+.2f} %)\n")

    # ── the four variants ──────────────────────────────────────────────────
    print("RAZLIČICE — celotno okno, neto 0,30 % na stran")
    hdr = (f"  {'':2} {'Sortino':>8}{'Sharpe':>8}{'MaxDD':>8}{'izpost':>8}"
           f"{'zajem+':>8}{'zajem-':>8}{'poslov':>8}{'obrat':>8}")
    print(hdr)
    res = {}
    for v in VARIANTS:
        p, d = pos[v]
        m = metrics(p, raw)
        m["sha256"] = digest(p)
        m["label"] = LABEL[v]
        t0 = d.index[0]
        m["n_blocked_days"] = sum(1 for t in d.attrs["blocked"] if t >= t0)
        # Entry lag: bars the entry was READY but held back by the pause. Zero by
        # construction for D, which is the point — it isolates the pause instead
        # of mixing in confirm_bars and the conditions' own timing.
        lags = [k for t, k in d.attrs["entries"] if t >= t0]
        m["entry_lag_mean"] = round(float(np.mean(lags)), 1) if lags else None
        m["entry_lag_max"] = int(max(lags)) if lags else None
        m["entries_delayed"] = int(sum(1 for k in lags if k > 0))
        res[v] = m
        print(f"  {v:2} {m['sortino']:>8.3f}{m['sharpe']:>8.3f}{m['maxdd']:>8.1f}"
              f"{m['exposure']:>8.1f}{m['upside_capture']:>8.1f}"
              f"{m['downside_capture']:>8.1f}{m['trades']:>8d}{m['turnover']:>8.1f}")
    out["variants"] = res
    print(f"\n  zamuda, ki jo povzroči PREMOR (dni; brez confirm_bars):")
    print(f"  {'':4}{'povpr.':>8}{'najv.':>8}{'zakasnjenih vstopov':>22}"
          f"{'blok. dni':>11}")
    for v in VARIANTS:
        m = res[v]
        print(f"    {v} {m['entry_lag_mean']:>7}{m['entry_lag_max']:>8}"
              f"{m['entries_delayed']:>22}{m['n_blocked_days']:>11}")

    # identical position series would make a "difference" meaningless
    dupes = [(a, b) for i, a in enumerate(VARIANTS) for b in VARIANTS[i + 1:]
             if res[a]["sha256"] == res[b]["sha256"]]
    out["identical_pairs"] = [list(t) for t in dupes]
    if dupes:
        print(f"\n  POZOR: enaka serija pozicij: {dupes}")

    # ── where do the variants actually differ? ─────────────────────────────
    # A difference concentrated in one stretch of history is not a general
    # finding about the rule, it is a finding about that stretch.
    print("\nKJE SE RAZLIČICE SPLOH RAZLIKUJEJO")
    div = {}
    for a, b in (("A", "B"), ("A", "C"), ("A", "D"), ("B", "D"), ("C", "D")):
        pa, pb = pos[a][0], pos[b][0]
        m_ = np.abs(pa.to_numpy() - pb.to_numpy()) > 1e-12
        k = int(m_.sum())
        if k:
            dts = pa.index[m_]
            div[f"{a}-{b}"] = {"n_days": k, "first": str(dts[0].date()),
                               "last": str(dts[-1].date())}
            print(f"  {a} proti {b}   {k:4d} dni   {dts[0].date()} → {dts[-1].date()}")
        else:
            div[f"{a}-{b}"] = {"n_days": 0}
            print(f"  {a} proti {b}      0 dni   IDENTIČNI")
    out["divergence"] = div

    # ── bootstrap vs A ─────────────────────────────────────────────────────
    print("\nSPARJENI BLOKOVNI BOOTSTRAP — ΔSortino proti A (5000, blok 20)")
    rA = net_returns(posA, ret, FEE).to_numpy(float)
    boot = {}
    for v in ("B", "C", "D"):
        rV = net_returns(pos[v][0], ret, FEE).to_numpy(float)
        boot[v] = paired_ci(rV, rA, rng)
        c = boot[v]
        print(f"  {v} - A   Δ {c['delta']:+.3f}   95 % CI "
              f"[{c['ci_lo']:+.3f}, {c['ci_hi']:+.3f}]   "
              f"{'IZKLJUČUJE ničlo' if c['excludes_zero'] else 'objame ničlo'}")
    out["bootstrap_vs_A"] = boot

    # ── sub-periods ────────────────────────────────────────────────────────
    print("\nPODOBDOBJA — Sortino, okna določena vnaprej")
    print(f"  {'okno':4} {'A':>8}{'B':>8}{'C':>8}{'D':>8}   zmagovalec")
    subs = {}
    for name, a, b in SUBPERIODS:
        row = {}
        for v in VARIANTS:
            p = pos[v][0]
            w = p.index[(p.index >= a) & (p.index <= b)]
            r = net_returns(p.reindex(w), ret, FEE).to_numpy(float)
            row[v] = round(sortino(r), 3)
        win = max(row, key=lambda k: row[k])
        subs[name] = {"from": a, "to": b, "sortino": row, "winner": win}
        print(f"  {name:4} " + "".join(f"{row[v]:>8.3f}" for v in VARIANTS)
              + f"   {win}")
    wins = {v: sum(1 for s in subs.values() if s["winner"] == v) for v in VARIANTS}
    out["subperiods"] = {"windows": subs, "wins": wins}
    print(f"  zmag: " + "  ".join(f"{v}={wins[v]}" for v in VARIANTS))

    # ── exposure matching — the gate that caught two earlier artifacts ─────
    print("\nIZENAČENA IZPOSTAVLJENOST — vsaka različica pomanjšana na izpost. A")
    eA = res["A"]["exposure"]
    print(f"  {'':2} {'k':>6}{'Sortino':>9}{'MaxDD':>8}{'zajem-':>8}")
    match = {}
    for v in VARIANTS:
        p = pos[v][0]
        k = eA / res[v]["exposure"]
        ps = (p * k).clip(0.0, 1.0)
        r = net_returns(ps, ret, FEE).to_numpy(float)
        _, dn = capture(ps, ret)
        match[v] = {"scale": round(float(k), 3), "sortino": round(sortino(r), 3),
                    "maxdd": round(maxdd(r), 1), "downside_capture": dn,
                    "exposure": round(float(ps.mean() * 100), 1)}
        print(f"  {v:2} {k:>6.3f}{match[v]['sortino']:>9.3f}"
              f"{match[v]['maxdd']:>8.1f}{dn:>8.1f}")
    out["exposure_matched"] = match

    # ── placebo: is it the timing, or just less time in the market? ────────
    print(f"\nPLACEBO — {N_PLACEBO} naključnih razporeditev premora")
    posD = pos["D"][0]
    nD = len(posD)
    n_ep = len(episodes)
    ep_len = int(round(float(np.mean([e["days"] for e in episodes]))))
    sim = np.empty(N_PLACEBO)
    for t in range(N_PLACEBO):
        q = posD.to_numpy().copy()
        for s in rng.integers(0, nD - ep_len, size=n_ep):
            q[s:s + ep_len] = 0.0
        sim[t] = sortino(net_returns(pd.Series(q, index=posD.index), ret,
                                     FEE).to_numpy(float))
    sim = sim[np.isfinite(sim)]
    pct = float((sim < res["A"]["sortino"]).mean() * 100)
    out["placebo"] = {"n": int(sim.size), "n_pauses": n_ep, "pause_len": ep_len,
                      "mean": round(float(sim.mean()), 3),
                      "p05": round(float(np.percentile(sim, 5)), 3),
                      "p95": round(float(np.percentile(sim, 95)), 3),
                      "A_sortino": res["A"]["sortino"],
                      "A_percentile": round(pct, 1)}
    print(f"  {n_ep} premorov po {ep_len} dni, naključno postavljenih na D")
    print(f"  Sortino placeba: povprečje {sim.mean():.3f}  "
          f"5–95 % [{np.percentile(sim, 5):.3f}, {np.percentile(sim, 95):.3f}]")
    print(f"  A = {res['A']['sortino']:.3f}  ->  {pct:.1f}. percentil placeba")
    print("  Če A ni visoko v tej porazdelitvi, čas premora ne nosi informacije")
    print("  in gre le za manj časa v trgu.")

    # ── B sensitivity: shape only, argmax deliberately not chosen ──────────
    print("\nOBČUTLJIVOST B — 10 · 15 · 20 · 25 dni (oblika, ne izbira)")
    sensB = {}
    for h in (10, 15, 20, 25):
        p, _ = positions(raw, "B", hold=h)
        m = metrics(p, raw)
        sensB[h] = {"sortino": m["sortino"], "exposure": m["exposure"],
                    "trades": m["trades"]}
        print(f"  {h:3d} dni   Sortino {m['sortino']:.3f}   "
              f"izpost. {m['exposure']:.1f} %   poslov {m['trades']}")
    out["sensitivity_B"] = sensB

    # ── §5.7 lookahead check for B, which is the only variant with new state ──
    # B reacts to the P&L of the last CLOSED trade. That is known at the exit bar,
    # so the forward loop cannot leak — but "cannot leak" is an argument, and the
    # pre-registration asked for a measurement. Truncate at T, rebuild, compare
    # the position on T against the same day computed from the full history.
    print("\nREVIZIJA POGLEDA V PRIHODNOST — različica B")
    full_B = pos["B"][0]
    cand = full_B.index[(full_B.index >= "2019-06-01") & (full_B.index <= "2026-06-30")]
    dates = pd.DatetimeIndex(sorted(rng.choice(cand, size=60, replace=False)))
    bad = []
    for t in dates:
        p_t, _ = positions(raw.loc[:t], "B")
        if p_t.index[-1] != t or abs(float(p_t.iloc[-1]) - float(full_B.loc[t])) > 1e-12:
            bad.append(str(t.date()))
    out["lookahead_B"] = {"n_dates": len(dates), "n_differing": len(bad),
                          "dates": bad[:20]}
    print(f"  {len(dates)} datumov · razlik: {len(bad)}")
    print("  Vrednost na dan T se ne spremeni, ko postanejo znani podatki po T."
          if not bad else "  POGLED V PRIHODNOST — B ne sme naprej.")

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nJSON -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
