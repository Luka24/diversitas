"""Kaj optimizirati: Sharpe, Sortino, Calmar ali kaj drugega.

    python testing/scripts/etf_kriterij.py

Vprašanje se navadno postavi kot "katero merilo bolje opiše strategijo". To je
napačno vprašanje. Merilo tu ni opis, ampak **izbirnik**: iz mreže nastavitev
izbere eno, in edino, kar šteje, je, ali se izbrana obnese tudi zunaj okna, na
katerem je bila izbrana. Merilo, ki lepše opisuje in slabše izbira, je slabše
merilo.

Zato se tu ne primerja vrednosti meril, ampak njihova sposobnost izbire, in
sicer na štiri načine:

  A  ali se merila sploh ne strinjajo
     Če vsa izberejo isto nastavitev, je vprašanje brezpredmetno. Preveri se
     prvo, ker prihrani vse ostalo.

  B  ali se razvrstitev prenese iz enega okna v drugo
     Spearmanova korelacija med vrednostjo merila na oknu zasnove in na oknu
     validacije, čez vso mrežo. Nizka korelacija pomeni, da merilo razvršča
     šum.

  C  koliko je vredna izbira
     Nastavitev, ki jo merilo izbere na zasnovi, se odigra na validaciji in
     primerja z mediano mreže. Razlika je edina številka, ki pove, ali je
     optimiziranje po tem merilu prineslo kaj.

  D  koliko je merilo samo po sebi natančno
     Vezani blocni bootstrap na isti seriji. Merilo s široko porazdelitvijo
     razvršča po naključju, tudi če je teoretično pravilnejše.

Poleg tega se primerja **po davku**, ker je za zavezanca to edina številka, ki
jo dejansko dobi, in ker merila pred davkom sistematično favorizirajo obrat.

Izhod: testing/data/etf_kriterij.json
"""
from __future__ import annotations

import json
import sys
import warnings
from dataclasses import replace
from itertools import combinations, product
from pathlib import Path

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from scipy import stats as sps

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "etf"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from shared.costs import net_returns                              # noqa: E402
from shared.etf_data import load                                  # noqa: E402
from shared.etf_universe import UNIVERSE                          # noqa: E402
from shared.tax import SLOVENIA_2026, simulate_brokerage, summarise  # noqa: E402
from testing.scripts import etf_wfo as W                          # noqa: E402

from diversitas.config import DEFAULT_CONFIG                      # noqa: E402
from diversitas.strategy import run_strategy                      # noqa: E402

OUT = ROOT / "testing" / "data" / "etf_kriterij.json"
TD = 252
SLEEVE = "World"
NL = chr(10)

CUTS = ["2018-06-30", "2019-06-30", "2020-06-30", "2021-06-30",
        "2022-06-30", "2023-06-30", "2024-06-30"]

GRID = dict(
    track_period=[50, 75, 100, 150, 200],
    atr_buf_mult=[0.0, 0.5, 1.0],
    trail_atr_mult=[2.0, 3.0, 5.0],
    adx_thresh=[0.0, 18.0, 25.0],
)


# ── merila ────────────────────────────────────────────────────────────────────

def _eq(r: np.ndarray) -> np.ndarray:
    return np.cumprod(1.0 + r)


def cagr(r):
    r = np.asarray(r, float)
    return float(_eq(r)[-1] ** (TD / max(len(r), 1)) - 1) if len(r) else np.nan


def maxdd(r):
    e = _eq(np.asarray(r, float))
    return float((e / np.maximum.accumulate(e) - 1).min())


def sharpe(r):
    r = np.asarray(r, float)
    sd = r.std()
    return float(r.mean() * TD / (sd * np.sqrt(TD))) if sd > 1e-12 else np.nan


def sortino(r):
    r = np.asarray(r, float)
    dn = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(TD)
    return float(r.mean() * TD / dn) if dn > 1e-12 else np.nan


def calmar(r):
    m = maxdd(r)
    return float(cagr(r) / abs(m)) if m < -1e-6 else np.nan


def omega(r):
    r = np.asarray(r, float)
    neg = -r[r < 0].sum()
    return float(r[r > 0].sum() / neg) if neg > 1e-12 else np.nan


def ulcer_perf(r):
    """Martinov indeks: donos na enoto povprecne globine padca. Med praktiki
    priljubljen, ker kaznuje dolge padce, ne le globokih."""
    e = _eq(np.asarray(r, float))
    dd = e / np.maximum.accumulate(e) - 1.0
    u = float(np.sqrt(np.mean(dd ** 2)))
    return float(cagr(r) / u) if u > 1e-9 else np.nan


def terminal(r):
    return float(_eq(np.asarray(r, float))[-1])


OBJECTIVES = {
    "Sharpe": sharpe, "Sortino": sortino, "Calmar": calmar,
    "Omega": omega, "Martin": ulcer_perf, "CAGR": cagr,
    "koncna vrednost": terminal,
}


# ── mreza ─────────────────────────────────────────────────────────────────────

def build_grid(daily: pd.DataFrame) -> dict[str, pd.Series]:
    keys = list(GRID)
    out: dict[str, pd.Series] = {}
    ret = daily["close"].pct_change().fillna(0.0)
    fee = DEFAULT_CONFIG.fee_per_side_pct
    for combo in product(*(GRID[k] for k in keys)):
        cfg = replace(DEFAULT_CONFIG, **dict(zip(keys, combo)),
                      use_adx=(combo[keys.index("adx_thresh")] > 0))
        df = run_strategy(daily, config=cfg).df
        pos = (df["target_alloc"] / 100.0).shift(1).fillna(0.0)
        label = "tp{} buf{} trail{} adx{}".format(*combo)
        s = net_returns(pos, ret, fee)
        s.attrs["pos"] = pos
        out[label] = s
    return out


def after_tax_cagr(pos: pd.Series, price: pd.Series) -> float:
    """CAGR po davku in po unovcenju, za eno sredstvo."""
    w = pd.DataFrame({SLEEVE: pos})
    px = pd.DataFrame({SLEEVE: price})
    # trguje se takrat, ko se cilj spremeni
    msk = (w.diff().abs().sum(axis=1) > 1e-9)
    msk.iloc[0] = True
    res = simulate_brokerage(w, px, SLOVENIA_2026,
                             fee_per_side_pct=DEFAULT_CONFIG.fee_per_side_pct,
                             rebalance_mask=msk)
    return summarise(res)["cagr_after_liquidation"]


# ── analiza ───────────────────────────────────────────────────────────────────

def main() -> int:
    pd.set_option("display.width", 220)
    daily = load(SLEEVE, start=UNIVERSE[SLEEVE].usable_from)
    price = daily["close"]
    grid = build_grid(daily)
    labels = list(grid)
    print(f"mreza: {len(labels)} nastavitev na {SLEEVE}, "
          f"{daily.index.min().date()} -> {daily.index.max().date()}, "
          f"provizija {DEFAULT_CONFIG.fee_per_side_pct} % na posel\n")

    des = {k: W.split(v, "design") for k, v in grid.items()}
    val = {k: W.split(v, "validation") for k, v in grid.items()}
    res: dict = {"generated": str(pd.Timestamp.utcnow()), "n_configs": len(labels),
                 "sleeve": SLEEVE, "grid": GRID}

    # ── A: se merila strinjajo? ───────────────────────────────────────────────
    print("A  IZBIRA NA OKNU ZASNOVE — se merila sploh strinjajo?\n" + "-" * 96)
    picks = {}
    for name, fn in OBJECTIVES.items():
        vals = {k: fn(des[k].to_numpy()) for k in labels}
        best = max(vals, key=lambda k: (vals[k] if np.isfinite(vals[k]) else -1e18))
        picks[name] = best
        print(f"   {name:<18} izbere  {best:<28} (vrednost {vals[best]:.3f})")
    # after-tax objective
    at_des = {}
    for k in labels:
        pos = grid[k].attrs["pos"]
        m = pos.index <= W.DESIGN_END
        at_des[k] = after_tax_cagr(pos[m], price.reindex(pos.index)[m])
    best_at = max(at_des, key=lambda k: at_des[k] if np.isfinite(at_des[k]) else -1e18)
    picks["CAGR po davku"] = best_at
    print(f"   {'CAGR po davku':<18} izbere  {best_at:<28} (vrednost {at_des[best_at]*100:.2f} %)")
    n_distinct = len(set(picks.values()))
    print(f"\n   razlicnih izbir: {n_distinct} od {len(picks)} meril")
    res["picks_design"] = picks

    # -- B: prenos razvrstitve, na vec rezih --------------------------------
    print(NL + "B  ALI SE RAZVRSTITEV PRENESE (Spearman pred rezom -> po rezu)" + NL + "-" * 96)
    print("   En sam rez zavede: na rezu 2023-06-30 dajo vsa razmerja rho okoli nic.")
    print("   Spodaj sedem rezov, in loceno primerjava med posameznimi leti." + NL)
    idx0 = grid[labels[0]].index
    print(f"   {'rez':<12}" + "".join(f"{n[:11]:>12}" for n in OBJECTIVES))
    per_cut = {n: [] for n in OBJECTIVES}
    for c in CUTS:
        t = pd.Timestamp(c, tz="UTC")
        line = f"   {c:<12}"
        for name, fn in OBJECTIVES.items():
            a = np.array([fn(grid[k].loc[:t].to_numpy()) for k in labels])
            b = np.array([fn(grid[k].loc[t:].to_numpy()) for k in labels])
            ok = np.isfinite(a) & np.isfinite(b)
            rho = float(sps.spearmanr(a[ok], b[ok]).statistic) if ok.sum() > 5 else np.nan
            per_cut[name].append(rho)
            line += f"{rho:>+12.3f}"
        print(line)
    stability = {n: float(np.nanmean(v)) for n, v in per_cut.items()}
    print(f"   {'POVPRECJE':<12}" + "".join(f"{stability[n]:>+12.3f}" for n in OBJECTIVES))
    print(f"   {'pozitivnih':<12}"
          + "".join(f"{sum(1 for x in per_cut[n] if x > 0):>9} od 7" for n in OBJECTIVES))

    years = sorted(set(idx0.year))[1:-1]
    per_year = {n: {y: np.array([fn(grid[k].to_numpy()[idx0.year == y]) for k in labels])
                    for y in years} for n, fn in OBJECTIVES.items()}
    print(NL + "   med posameznimi leti (neprekrivajoca okna):")
    print(f"   {'merilo':<18}{'povp. rho':>11}{'delez > 0':>11}")
    year_rho = {}
    for name in OBJECTIVES:
        rs = []
        for y1, y2 in combinations(years, 2):
            a, b = per_year[name][y1], per_year[name][y2]
            ok = np.isfinite(a) & np.isfinite(b)
            if ok.sum() > 5:
                rs.append(float(sps.spearmanr(a[ok], b[ok]).statistic))
        year_rho[name] = dict(mean=float(np.nanmean(rs)),
                              share_pos=float(sum(1 for x in rs if x > 0) / len(rs)))
        print(f"   {name:<18}{year_rho[name]['mean']:>+11.3f}{year_rho[name]['share_pos']:>10.0%}")
    res["rank_stability"] = stability
    res["rank_stability_per_cut"] = per_cut
    res["rank_stability_year_pairs"] = year_rho

    # ── C: koliko je vredna izbira ────────────────────────────────────────────
    print("\nC  KOLIKO JE VREDNA IZBIRA — izbrana na zasnovi, odigrana na validaciji\n" + "-" * 96)
    med_val_sortino = float(np.nanmedian([sortino(val[k].to_numpy()) for k in labels]))
    med_val_cagr = float(np.nanmedian([cagr(val[k].to_numpy()) for k in labels]))
    print(f"   mediana mreze na validaciji:  Sortino {med_val_sortino:+.3f}   "
          f"CAGR {med_val_cagr*100:+.2f} %\n")
    print(f"   {'merilo':<18} {'izbrana nastavitev':<28} {'Sortino val':>12} {'CAGR val':>10} {'nad mediano':>12}")
    value = {}
    for name, best in picks.items():
        s_v = sortino(val[best].to_numpy())
        c_v = cagr(val[best].to_numpy())
        value[name] = dict(config=best, val_sortino=s_v, val_cagr=c_v,
                           edge_sortino=s_v - med_val_sortino)
        print(f"   {name:<18} {best:<28} {s_v:>+12.3f} {c_v*100:>9.2f} % "
              f"{s_v - med_val_sortino:>+12.3f}")
    res["selection_value"] = value

    # ── D: natancnost merila ──────────────────────────────────────────────────
    print("\nD  NATANCNOST MERILA — vezani blocni bootstrap na isti seriji\n" + "-" * 96)
    base = grid[picks["Sharpe"]]
    idx = W._stationary_index(len(base), 2000, 20, 42)
    arr = base.to_numpy()
    print(f"   {'merilo':<18} {'ocena':>10} {'95 % interval':>26} {'sirina/ocena':>14}")
    noise = {}
    for name, fn in OBJECTIVES.items():
        vals = np.array([fn(arr[row]) for row in idx])
        vals = vals[np.isfinite(vals)]
        if len(vals) < 100:
            continue
        lo, hi = np.percentile(vals, [2.5, 97.5])
        pt = fn(arr)
        rel = (hi - lo) / abs(pt) if abs(pt) > 1e-9 else np.nan
        noise[name] = dict(point=pt, lo=float(lo), hi=float(hi), rel_width=float(rel))
        print(f"   {name:<18} {pt:>10.3f}  [{lo:>+9.3f}, {hi:>+9.3f}] {rel:>13.2f}")
    res["noise"] = noise

    # -- E: mnogokratno testiranje ------------------------------------------
    print(NL + "E  KAJ OSTANE OD NAJBOLJSEGA PO POPRAVKU ZA %d POSKUSOV" % len(labels) + NL + "-" * 96)
    from testing.scripts import stats as ST
    full = {k: grid[k].to_numpy() for k in labels}
    sr_all = np.array([sharpe(v) for v in full.values()])
    sr_all = sr_all[np.isfinite(sr_all)]
    best_lbl = max(labels, key=lambda k: (sharpe(full[k]) if np.isfinite(sharpe(full[k])) else -9))
    # PER-BAR std, and td=252. Passing the annualised std here inflates the
    # benchmark by a factor of td and returns a confident, meaningless zero.
    ds = ST.deflated_sharpe(full[best_lbl], n_trials=len(labels),
                            trials_sharpe_std=float(np.std(sr_all)) / np.sqrt(TD),
                            td=TD)
    print(f"   najboljsi po Sharpu na celi zgodovini : {best_lbl}")
    print(f"   njegov Sharpe                        : {sharpe(full[best_lbl]):.3f}")
    print(f"   razpon Sharpov cez mrezo             : {sr_all.min():.3f} do {sr_all.max():.3f}"
          f"   (sd {np.std(sr_all):.3f})")
    for k, v in ds.items():
        if isinstance(v, (int, float)):
            print(f"   {k:<37}: {float(v):.4f}")
    res["deflated_sharpe"] = {k: (float(v) if isinstance(v, (int, float)) else str(v))
                              for k, v in ds.items()}
    print(NL + "   Branje: ce je popravljena verjetnost pod 0,95, najboljsi rezultat v mrezi")
    print("   ni locljiv od tega, kar bi %d poskusov dalo tudi brez vsakega ucinka." % len(labels))

    # ── sklep ─────────────────────────────────────────────────────────────────
    print("\nSKLEP\n" + "-" * 96)
    best_stab = max(stability, key=lambda k: stability[k] if np.isfinite(stability[k]) else -9)
    tight = min(noise, key=lambda k: noise[k]["rel_width"])
    pos_edge = [n for n, v in value.items() if np.isfinite(v["edge_sortino"])
                and v["edge_sortino"] > 0]
    print(f"   najbolj prenosljiva razvrstitev : {best_stab} (rho {stability[best_stab]:+.3f})")
    print(f"   najozji interval               : {tight} (sirina/ocena {noise[tight]['rel_width']:.2f})")
    print(f"   meril, ki na validaciji presezejo mediano mreze: {len(pos_edge)} od {len(value)}"
          + (f"  ({', '.join(pos_edge)})" if pos_edge else ""))
    res["summary"] = dict(most_transferable=best_stab, tightest=tight,
                          beat_median=pos_edge)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    print(f"\nzapisano: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
