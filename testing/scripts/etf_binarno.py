"""Binarno in skoncentrirano: 100 % v enem skladu, noter in ven.

    python testing/scripts/etf_binarno.py

OMEJITEV, KI JO TA SKRIPTA SPOSTUJE

Sestave knjige se ne sme spreminjati in nobenega novega sklada se ne kupuje.
Vseh osem instrumentov je ze izbranih in odobrenih; edino, kar se tu spreminja,
je **v katerem od njih kapital sedi ta trenutek**. Pozicija je 100 % ali 0 %,
nikoli vmes.

Pogoji za nakup in prodajo ostanejo nedotaknjeni: `lean` s privzetim
`LeanConfig` odloca, ali je sklad sploh kupljiv. Ko jih je kupljivih vec, je
treba enega izbrati, in za to je uporabljen momentum, deljen z volatilnostjo —
brez tega bi bil vsak dan izbran najbolj nihajoc sklad, kar je stava na
volatilnost z etiketo momentuma.

DVOJE, KI JU BREZ TEGA NI MOGOCE POSTENO OCENITI

  1  Gotovina se obrestuje po dejanski meri ECB. Binarna strategija je pogosto
     v celoti zunaj trga, in pripisati ji nic je pri meri 3,2 % v letih 2023-24
     napaka velikosti nekaj odstotnih tock na leto. Serija je EONIA + STR.

  2  Trajno dno v `lean` (5 %) je izklopljeno, ker zahteva binarnost. S
     `bear_alloc_pct = 0` je pozicija res 0 ali 1.

MERILO NI KUPI IN DRZI, AMPAK STATICEN DELEZ

Vsaka strategija, ki je del casa zunaj trga, polepsa razmerja ze s tem. Zato je
poleg kupi in drzi izracunan tudi staticen delez z ISTO povprecno
izpostavljenostjo. Samo ta vrstica loci vescino od odsotnosti.

Izhod: testing/data/etf_binarno.json
"""
from __future__ import annotations

import json
import sys
import warnings
from dataclasses import replace
from pathlib import Path

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "lean"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from diversitas.config import LeanConfig                       # noqa: E402
from diversitas.strategy import S_BULL, run_strategy           # noqa: E402
from shared.etf_data import cash_rate, load                    # noqa: E402
from shared.etf_universe import PORTFOLIOS, UNIVERSE           # noqa: E402
from shared.warmup import trim_warmup                          # noqa: E402
from testing.scripts import etf_wfo as W                       # noqa: E402

OUT = ROOT / "testing" / "data" / "etf_binarno.json"
FEE = 0.20 / 100.0          # na vsak posel
MOM_LEN = 252               # 12 mesecev, standard v literaturi
VOL_LEN = 60


def _priprava():
    """Cene, binarni signal in ocena moci za vsak sklad."""
    cfg = replace(LeanConfig(), trading_days=252, bear_alloc_pct=0.0)
    cene, bull, moc = {}, {}, {}
    for k in UNIVERSE:
        d = load(k, start=UNIVERSE[k].usable_from)
        df = trim_warmup(run_strategy(d, config=cfg).df)
        cene[k] = d["close"]
        # signal je od vceraj: odlocitev pade na zakljucek, drzi se lahko sele jutri
        bull[k] = (df["signal_state"] == S_BULL).shift(1).fillna(False)
        r = d["close"].pct_change()
        mom = d["close"] / d["close"].shift(MOM_LEN) - 1.0
        vol = r.rolling(VOL_LEN).std() * np.sqrt(252)
        moc[k] = (mom / vol.replace(0, np.nan)).shift(1)
    return cene, bull, moc


def _okno(kljuci):
    idx = None
    for k in kljuci:
        i = CENE[k].index
        idx = i if idx is None else idx.union(i)
    zac = max(BULL[k].index[0] for k in kljuci)
    return idx[idx >= zac]


def _pot(idx, izbor: pd.Series, cash_d: pd.Series) -> tuple:
    """Odigraj zaporedje izbir. `izbor` je ime sklada ali None za gotovino.

    Provizija se zaracuna ob VSAKI zamenjavi: prodaja starega in nakup novega,
    torej dvakrat, razen ob prehodu v gotovino ali iz nje, kjer je posel en.
    """
    v = 100.0
    pot = [v]
    prej = None
    n_zamenjav = 0
    v_trgu = []
    for t in idx:
        s = izbor.loc[t]
        # pd.NA in np.nan se ne dasta primerjati z != , zato se vse odsotno
        # najprej prevede v None. Brez tega se dan brez signala ne da razlociti
        # od dneva, ko je bil izbran sklad.
        if s is None or (not isinstance(s, str)) or s == GOTOVINA:
            s = None
        if s != prej:
            posli = int(prej is not None) + int(s is not None)
            v *= (1 - FEE) ** posli
            n_zamenjav += 1
            prej = s
        if s is None:
            v *= 1 + cash_d.loc[t]
        else:
            r = RET[s].get(t, 0.0)
            v *= 1 + (0.0 if pd.isna(r) else r)
        v_trgu.append(0.0 if s is None else 1.0)
        pot.append(v)
    a = np.array(pot)
    return a[1:] / a[:-1] - 1, a, n_zamenjav, float(np.mean(v_trgu))


GOTOVINA = "CASH"          # izrecna oznaka, ne None. Razlog spodaj.


def _drzi_med(izbor: pd.Series, vsak: int) -> pd.Series:
    """Odlocaj le vsak N-ti dan, vmes drzi. Manj poslov, manj davka.

    Gotovina mora biti IZRECNA oznaka in ne None. Prva razlicica te funkcije je
    dan brez signala pustila kot None, nato pa je `ffill` cez njega prenesel ime
    prejsnjega sklada — ker je None za pandas manjkajoca vrednost, ne vrednost.
    Posledica: mesecna razlicica ni mogla nikoli v gotovino, izpostavljenost je
    bila 98 do 100 %, na World pa je cez trinajst let naredila **eno samo**
    zamenjavo. To ni bila strategija, bil je kupi in drzi z drugim imenom, in
    izgledal je bolje od merila.
    """
    izbor = izbor.fillna(GOTOVINA)
    if vsak <= 1:
        return izbor
    keep = np.zeros(len(izbor), dtype=bool)
    keep[::vsak] = True
    return izbor.where(pd.Series(keep, index=izbor.index)).ffill().fillna(GOTOVINA)


def _izberi(idx, meni, k=1) -> pd.Series:
    """Med skladi z BULL signalom vzemi k najmocnejsih. Pri k=1 je izhod ime
    sklada ali None; to je edina resnicno binarna oblika."""
    B = pd.DataFrame({s: BULL[s].reindex(idx).fillna(False) for s in meni})
    M = pd.DataFrame({s: MOC[s].reindex(idx) for s in meni})
    M = M.where(B)
    if k == 1:
        # idxmax pade, kadar je cela vrstica NaN, in taka vrstica je natanko dan,
        # ko ni kupljiv noben sklad — torej dan, ki nas najbolj zanima.
        ima = M.notna().any(axis=1)
        naj = pd.Series([None] * len(M), index=M.index, dtype="object")
        if ima.any():
            naj.loc[ima] = M.loc[ima].idxmax(axis=1)
        return naj
    rang = M.rank(axis=1, ascending=False, method="first")
    return (rang.le(k) & M.notna())


def _met(r, idx):
    r = np.asarray(r, float)
    ppy = len(idx) / ((idx[-1] - idx[0]).days / 365.25)
    eq = np.cumprod(1 + r)
    dd = eq / np.maximum.accumulate(eq) - 1
    vol = r.std() * np.sqrt(ppy)
    dn = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(ppy)
    c = eq[-1] ** (ppy / len(r)) - 1
    return dict(letno=c * 100, vol=vol * 100, sharpe=r.mean() * ppy / vol,
                sortino=r.mean() * ppy / dn, maxdd=dd.min() * 100,
                calmar=c / abs(dd.min()) if dd.min() < 0 else np.nan)


def _kupi_drzi(idx, utezi):
    px = pd.DataFrame({k: CENE[k].reindex(idx).ffill() for k in utezi})
    w = np.array([utezi[k] for k in utezi])
    return (px.pct_change().fillna(0.0) * w).sum(axis=1).to_numpy()


def main() -> int:
    global CENE, BULL, MOC, RET
    pd.set_option("display.width", 200)
    CENE, BULL, MOC = _priprava()
    RET = {k: v.pct_change() for k, v in CENE.items()}

    cr = cash_rate()
    res = {"generated": str(pd.Timestamp.utcnow()), "fee_per_trade_pct": FEE * 100,
           "cash_source": cr.attrs.get("source"), "kandidati": {}}

    MENIJI = {
        "vseh 8": list(UNIVERSE),
        "samo P1": list(PORTFOLIOS["P1"]),
        "samo P2": list(PORTFOLIOS["P2"]),
        "trije nekorelirani (World, Gold, GlobAgg)": ["World", "Gold", "GlobAgg"],
        "samo World": ["World"],
    }

    for ime_meni, meni in MENIJI.items():
        idx = _okno(meni)
        ppy = len(idx) / ((idx[-1] - idx[0]).days / 365.25)
        cash_d = (cr.reindex(idx.union(cr.index)).ffill().reindex(idx).fillna(0.0)
                  / 100.0 / ppy)
        print(f"\n=== meni: {ime_meni} ===")
        print(f"    {idx[0].date()} -> {idx[-1].date()}  ({len(idx)/ppy:.1f} let, "
              f"{ppy:.0f} dni/leto)")
        print(f"    {'kandidat':<34} {'letno':>7} {'Sharpe':>7} {'Sortino':>8} "
              f"{'MaxDD':>8} {'Calmar':>7} {'v trgu':>7} {'zamenjav':>9}")

        vrst = {}
        for vsak, oz in ((1, "dnevno"), (21, "mesecno")):
            izbor = _drzi_med(_izberi(idx, meni, k=1), vsak)
            r, pot, nz, izp = _pot(idx, izbor, cash_d)
            m = _met(r, idx)
            vrst[f"100 % najmocnejsi, {oz}"] = (r, izp)
            print(f"    {'100 % najmocnejsi, '+oz:<34} {m['letno']:6.2f} % {m['sharpe']:7.2f} "
                  f"{m['sortino']:8.2f} {m['maxdd']:7.1f} % {m['calmar']:7.2f} "
                  f"{izp*100:6.0f} % {nz:9d}")

        # merila
        if ime_meni in ("samo P1", "samo P2"):
            utezi = PORTFOLIOS["P1" if ime_meni.endswith("P1") else "P2"]
        else:
            utezi = {k: 1.0 / len(meni) for k in meni}
        r_bh = _kupi_drzi(idx, utezi)
        m = _met(r_bh, idx)
        print(f"    {'kupi in drzi (merilo)':<34} {m['letno']:6.2f} % {m['sharpe']:7.2f} "
              f"{m['sortino']:8.2f} {m['maxdd']:7.1f} % {m['calmar']:7.2f} {100:6.0f} %")
        for ime, (r, izp) in vrst.items():
            r_stat = r_bh * izp
            ms = _met(r_stat, idx)
            print(f"    {'staticnih '+f'{izp*100:.0f}'+' % (za '+ime.split(',')[1].strip()+')':<34} "
                  f"{ms['letno']:6.2f} % {ms['sharpe']:7.2f} {ms['sortino']:8.2f} "
                  f"{ms['maxdd']:7.1f} % {ms['calmar']:7.2f} {izp*100:6.0f} %")
            ci = W.paired_diff_ci(pd.Series(r, index=idx), pd.Series(r_stat, index=idx),
                                  n_boot=1500, td=int(round(ppy)))
            print(f"        d Sortino proti staticnemu: {ci['point']:+.2f} "
                  f"[{ci['lo']:+.2f}, {ci['hi']:+.2f}]  P(boljsi) {ci['p_better']:.0%}  "
                  f"-> {ci['verdict']}")
            res["kandidati"][f"{ime_meni} | {ime}"] = dict(
                metrics=_met(r, idx), exposure=izp,
                vs_static=dict(point=ci["point"], lo=ci["lo"], hi=ci["hi"],
                               verdict=ci["verdict"]))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    print(f"\nzapisano: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
