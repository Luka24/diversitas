"""Preveri stran testing/dashboard_etf.py, tudi izris.

    python testing/scripts/preveri_dashboard_etf.py

Isto dvoje kot pri kripto strani, in drugo je tisto, ki navadno pade.

Racun: identiteta med potjo vrednosti in donosi, obnasanje pri niclnih
stroskih, ujemanje knjige z eno samo nalozbo proti neposrednemu izracunu, in
posebej za to stran: da `trading_days` ne spremeni nobenega posla, ker je na
tem sloni odlocitev, da se poroca s 252 ob nedotaknjeni strategiji.

Izris: cela stran se pozene brezglavo prek streamlit.testing.v1.AppTest.
"""
from __future__ import annotations

import sys
import warnings
from dataclasses import replace
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "lean"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import importlib.util

import numpy as np
import pandas as pd

STRAN = ROOT / "testing" / "dashboard_etf.py"


def _nalozi():
    spec = importlib.util.spec_from_file_location("dash_etf", STRAN)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def racun(D) -> list[tuple[str, bool]]:
    from shared.etf_universe import PORTFOLIOS, UNIVERSE

    vsi = tuple(UNIVERSE)
    CENE = {k: D._cena.__wrapped__(k) for k in vsi}
    SIG = {k: D._signal.__wrapped__(k) for k in vsi}
    out = []

    utezi = dict(PORTFOLIOS["P1"])
    idx = None
    for k in utezi:
        i = CENE[k].index
        idx = i if idx is None else idx.union(i)
    idx = idx[idx >= pd.Timestamp(D.SIG_ZAC if hasattr(D, "SIG_ZAC") else "2019-01-02",
                                  tz="UTC")]

    r, prov, konc, pot = D._knjiga(idx, CENE, SIG, utezi, 20, True, 1)

    # 1) pot in donosi morata biti isto
    rekon = np.concatenate([[100.0], 100.0 * np.cumprod(1 + r)])
    out.append(("pot vrednosti se ujema z donosi",
                bool(np.allclose(rekon, pot, rtol=1e-9, atol=1e-9))))

    # 2) brez stroskov ni provizij
    _, prov0, _, _ = D._knjiga(idx, CENE, SIG, utezi, 0, True, 1)
    out.append(("pri nic bazicnih tockah so provizije nic",
                bool(all(abs(v) < 1e-12 for v in prov0.values()))))

    # 3) vecji strosek nikoli ne da vecje koncne vrednosti
    _, _, konc_drag, _ = D._knjiga(idx, CENE, SIG, utezi, 60, True, 1)
    _, _, konc_poc, _ = D._knjiga(idx, CENE, SIG, utezi, 0, True, 1)
    out.append(("drazje trgovanje ne da vec kot zastonj", bool(konc_drag <= konc_poc)))

    # 4) knjiga z enim skladom se ujema z neposrednim izracunom
    k = "World"
    r1, _, _, _ = D._knjiga(idx, CENE, SIG, {k: 1.0}, 0, False)
    p = SIG[k][0].reindex(idx).fillna(0.0)
    rr = CENE[k]["close"].pct_change().reindex(idx).fillna(0.0)
    neposredno = (p * rr).to_numpy()
    out.append(("knjiga z enim skladom = neposreden izracun",
                bool(np.allclose(r1, neposredno, atol=1e-12))))

    # 5) uteži se ohranijo ob uravnavanju
    out.append(("koncna vrednost je koncna tocka poti",
                bool(abs(konc - pot[-1]) < 1e-9)))

    # 6) TO JE ODLOCILNO ZA TO STRAN: koledar ne spremeni poslov
    from diversitas.config import LeanConfig
    from diversitas.strategy import run_strategy
    from shared.warmup import trim_warmup
    enako = True
    for k in ("World", "GlobAgg", "Gold"):
        a = trim_warmup(run_strategy(CENE[k], config=LeanConfig(trading_days=365)).df)
        b = trim_warmup(run_strategy(CENE[k], config=LeanConfig(trading_days=252)).df)
        enako &= bool((a["signal_state"].to_numpy() == b["signal_state"].to_numpy()).all())
    out.append(("trading_days 365 proti 252 ne spremeni signalov", enako))

    # 7) strategija je res nedotaknjena: privzeti LeanConfig razen koledarja
    cfg = replace(LeanConfig(), trading_days=D.PPY)
    priv = LeanConfig()
    razlike = [f.name for f in cfg.__dataclass_fields__.values()
               if f.name not in ("symbol_map",)
               and getattr(cfg, f.name) != getattr(priv, f.name)]
    out.append(("edina sprememba konfiguracije je trading_days",
                razlike == ["trading_days"]))

    return out


def izris() -> list[tuple[str, bool]]:
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(STRAN), default_timeout=600)
    at.run()
    if at.exception:
        for e in at.exception:
            print("   NAPAKA NA STRANI: %s" % str(e.value)[:400])
        return [("stran se izrise brez napake", False)]
    res = [("stran se izrise brez napake", True),
           ("ima tabele", len(at.dataframe) >= 3),
           ("ima zavihke", len(at.tabs) >= 5)]
    # preklop na drugo knjigo mora tudi delovati
    try:
        at.radio[0].set_value("Portfelj 2").run()
        res.append(("preklop na Portfelj 2 deluje", not at.exception))
    except Exception as e:  # noqa: BLE001
        print("   NAPAKA PRI PREKLOPU: %s" % str(e)[:300])
        res.append(("preklop na Portfelj 2 deluje", False))
    return res


def main() -> int:
    D = _nalozi()
    vse = []
    print("RACUN")
    for ime, ok in racun(D):
        print("   %-52s %s" % (ime, "OK" if ok else "NAPAKA"))
        vse.append(ok)
    print("\nIZRIS")
    for ime, ok in izris():
        print("   %-52s %s" % (ime, "OK" if ok else "NAPAKA"))
        vse.append(ok)
    print()
    if all(vse):
        print("vseh %d preverb je uspelo" % len(vse))
        return 0
    print("NEUSPESNIH: %d od %d" % (sum(1 for x in vse if not x), len(vse)))
    return 1


if __name__ == "__main__":
    sys.exit(main())
