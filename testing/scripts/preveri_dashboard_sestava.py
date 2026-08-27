"""Preveri stran testing/dashboard_sestava.py, tudi izris.

    python testing/scripts/preveri_dashboard_sestava.py

Dvoje preverja, in drugo je tisto, ki je prej manjkalo.

Racun: identiteta med potjo vrednosti in donosi, obnasanje pri niclnih
stroskih, in ujemanje knjige z eno samo nalozbo proti neposrednemu izracunu.

Izris: cela stran se pozene brezglavo prek streamlit.testing.v1.AppTest. Prej
so se preverjale samo pomozne funkcije, zato je stran padla sele v brskalniku,
ko je Styler.background_gradient zahteval matplotlib, ki ga v okolju ni.
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

STRAN = ROOT / "testing" / "dashboard_sestava.py"


def _nalozi():
    spec = importlib.util.spec_from_file_location("dash", STRAN)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def racun(D) -> list[tuple[str, bool]]:
    vsi = ("BTC", "ETH", "SOL", "LINK", "BNB", "HYPE", "XRP", "SPY")
    CENE = D._cene.__wrapped__(vsi)
    SIG = D._signali.__wrapped__(vsi, CENE)
    so = SIG["HYPE"][0].index[0]
    UT = {"BTC": .50, "ETH": .10, "SOL": .10, "LINK": .10, "BNB": .10, "SESTO": .10}
    kon = pd.Timestamp("2026-08-24", tz="UTC")
    idx = CENE["BTC"].loc[pd.Timestamp("2021-01-01", tz="UTC"):kon].index
    out = []

    r, prov, konc, pot = D._knjiga(idx, CENE, SIG, UT, 30, True, so, 1)
    m = D._metrike(r)
    out.append(("koncna vrednost = 100 x (1 + skupaj)",
                abs(konc - 100 * (1 + m["skupaj"] / 100)) < 1e-6))

    _, p0, k0, _ = D._knjiga(idx, CENE, SIG, UT, 0, True, so, 1)
    out.append(("brez provizij je koncna vrednost visja", k0 > konc))
    out.append(("pri 0 bp so provizije nic", sum(p0.values()) < 1e-9))

    _, pu, _, _ = D._knjiga(idx, CENE, SIG, UT, 30, False, so)
    out.append(("brez uravnavanja ni stroska uravnavanja", pu["uravnavanje"] < 1e-9))

    # knjiga z eno samo nalozbo mora dati isto kot neposreden izracun
    from diversitas.config import LeanConfig
    from diversitas.strategy import position, run_strategy, traded_fraction
    from shared.data_source import DEFAULT_SYMBOL_MAP
    from shared.warmup import trim_warmup
    sm = dict(DEFAULT_SYMBOL_MAP)
    sm["HYPE"] = {"hyperliquid": "HYPE"}
    cfg = replace(LeanConfig(), symbol_map=sm)
    _, _, kb, _ = D._knjiga(idx, CENE, SIG, {"BTC": 1.0}, 30, False, None)
    df = trim_warmup(run_strategy(CENE["BTC"], config=cfg).df)
    p = position(df, cfg).reindex(idx)
    t = traded_fraction(df, cfg).reindex(idx).fillna(0)
    ret = CENE["BTC"]["close"].pct_change().reindex(idx).fillna(0.0)
    v = 100.0
    for i in range(len(idx)):
        v *= 1 + p.iloc[i] * ret.iloc[i] - t.iloc[i] * 0.003
    out.append(("knjiga z enim sredstvom = neposreden izracun", abs(kb - v) < 0.01))

    pod = D._podvodni(pot)
    out.append(("podvodni graf ni nikoli nad niclo", pod.max() <= 1e-9))
    pad = D._najhujsi_padci(idx, pot)
    out.append(("najhujsi padec se ujema z MaxDD",
                abs(float(pad["globina"].iloc[0]) - m["maxdd"]) < 0.1))
    rb, _ = D._eno_kupi_drzi(idx, CENE["BTC"])
    b, k = D._beta_korelacija(r, rb)
    out.append(("beta in korelacija sta stevili", np.isfinite(b) and np.isfinite(k)))
    return out


def izris() -> list[tuple[str, bool]]:
    """Pozeni celo stran brezglavo. To ujame napake, ki jih racun ne."""
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(STRAN), default_timeout=300)
    at.run()
    if at.exception:
        for e in at.exception:
            print("   NAPAKA NA STRANI: %s" % str(e.value)[:300])
        return [("stran se izrise brez napake", False)]
    return [
        ("stran se izrise brez napake", True),
        ("ima tabele", len(at.dataframe) >= 3),
        ("ima zavihke", len(at.tabs) >= 5),
    ]


def main() -> int:
    D = _nalozi()
    vse = []
    print("RACUN")
    for ime, ok in racun(D):
        print("   %-46s %s" % (ime, "OK" if ok else "NAPAKA"))
        vse.append(ok)
    print("\nIZRIS")
    for ime, ok in izris():
        print("   %-46s %s" % (ime, "OK" if ok else "NAPAKA"))
        vse.append(ok)
    print()
    if all(vse):
        print("vseh %d preverb je uspelo" % len(vse))
        return 0
    print("NEUSPESNIH: %d od %d" % (sum(1 for x in vse if not x), len(vse)))
    return 1


if __name__ == "__main__":
    sys.exit(main())
