"""Ali je lean-ova prednost odlocen izstop? Test v obe smeri.

    python testing/scripts/ostrina_izstopa.py

VZOREC, KI GA JE TREBA PREVERITI
Trije neodvisni kandidati so padli na isti nacin. Vsi trije MEHCAJO izstop, ker
namesto vsega ali nic drzijo delno pozicijo. Sortino na BTC v padajocem trgu:

    osnova, binarno         -1,40
    ansambel Donchianov     -1,51
    ansambel tracklinov     -1,69
    ansambel obojega        -1,81
    stopnjevanje k>=2       -2,12

Vrstni red se ujema s tem, koliko posamezna razlicica zmehca pozicijo. To je
mehanizem, ne nakljucje.

Ce mehcanje skoduje, mora ostrenje pomagati. Ce ne pomaga, potem je danasnja
nastavitev ze na pravem mestu in je sporocilo, naj se je nihce ne dotika v
NOBENO smer. Oboje je uporabno.

KAJ SE MERI
    exit_grace_bars   1, 2, 3, 4, 5     danes 3, koliko zaporednih dni pod
                                        pasom je potrebnih za izstop
    bear_alloc_pct    0, 5, 10          danes 5, trajno dno

Nizji exit_grace pomeni hitrejsi, bolj odlocen izstop. Nizje dno pomeni
popolnejsi izstop.

Merjeno na BTC in na knjigi sestih, pod trojno delitvijo, 0,30 % na stran.

Izhod: testing/data/ostrina_izstopa.json
"""
from __future__ import annotations

import json
import sys
import warnings
from dataclasses import replace
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "lean", Path(__file__).resolve().parent):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import numpy as np
import pandas as pd

from graded_alti import FEE, PPY, SREDSTVA, UTEZI, _cfg, cene
from ansambel import OKNA, izpis, metrike, rezi
from diversitas.strategy import position, run_strategy
from shared.warmup import trim_warmup

GRACE = (1, 2, 3, 4, 5)
DNO = (0.0, 5.0, 10.0)


def poz(raw, grace: int, dno: float) -> pd.Series:
    cfg = replace(_cfg(), exit_grace_bars=grace, bear_alloc_pct=dno)
    df = trim_warmup(run_strategy(raw, config=cfg).df)
    return position(df, cfg).astype(float)


def main() -> int:
    C = cene()
    raw = C["BTC"]
    out = {}

    V = {}
    for g in GRACE:
        V["izstop po %d dneh" % g] = poz(raw, g, 5.0)
    for d in DNO:
        if d != 5.0:
            V["dno %.0f %%" % d] = poz(raw, 3, d)
    V["dno 5 % (danes)"] = V["izstop po 3 dneh"]

    idx = V["izstop po 3 dneh"].index
    V = {k: v.reindex(idx) for k, v in V.items()}
    ret = raw["close"].pct_change().reindex(idx).fillna(0.0)

    print("BTC, %s do %s, %d dni, 0,30 %% na stran"
          % (idx[0].date(), idx[-1].date(), len(idx)))
    print("danasnja nastavitev: exit_grace_bars=3, bear_alloc_pct=5")

    izpis("1) BTC, CELA ZGODOVINA", [(n, metrike(v, ret)) for n, v in V.items()])
    out["btc_cela"] = {n: metrike(v, ret) for n, v in V.items()}

    ma200 = raw["close"].rolling(200).mean().reindex(idx)
    bik = (raw["close"].reindex(idx) > ma200).fillna(False)
    print("\n\n2) BTC PO REZIMU, Sortino")
    print("  %-20s%12s%12s%12s" % ("razlicica", "bikovski", "medvedji",
                                   "izpost medv"))
    for n, v in V.items():
        a = metrike(v[bik], ret[bik])["sortino"]
        b = metrike(v[~bik], ret[~bik])
        out.setdefault("btc_rezim", {})[n] = {"bik": a, "medved": b["sortino"]}
        print("  %-20s%12.2f%12.2f%11.0f %%"
              % (n, a, b["sortino"], b["izpost"]))

    print("\n\n3) BTC, TRI OKNA, Sortino")
    print("  %-20s%12s%12s%12s" % ("razlicica", "trening", "validacija",
                                   "hold-out"))
    for n, v in V.items():
        vr = []
        for okno, a, b in OKNA:
            m = metrike(rezi(v, a, b), rezi(ret, a, b))
            vr.append(m["sortino"])
            out.setdefault("btc_okna", {}).setdefault(n, {})[okno] = m
        print("  %-20s%12.2f%12.2f%12.2f" % (n, *vr))

    # ---- knjiga sestih ----
    print("\n\n4) KNJIGA 50/10/10/10/10/10, Sharpe po oknih")
    VS = {}
    for s in SREDSTVA:
        d = {}
        for g in GRACE:
            d["izstop po %d dneh" % g] = poz(C[s], g, 5.0)
        for dd in DNO:
            if dd != 5.0:
                d["dno %.0f %%" % dd] = poz(C[s], 3, dd)
        d["dno 5 % (danes)"] = d["izstop po 3 dneh"]
        VS[s] = d
    RET = {s: C[s]["close"].pct_change().fillna(0.0) for s in SREDSTVA}

    print("  %-20s%12s%12s%12s%12s" % ("razlicica", "trening", "validacija",
                                       "hold-out", "MaxDD h-o"))
    for n in V:
        vr, md = [], None
        for okno, a, b in OKNA:
            idxb = rezi(VS["BTC"][n], a, b).index
            E = {k: 100.0 * w for k, w in UTEZI.items()}
            pot, zm = [], None
            for dt in idxb:
                for k in UTEZI:
                    p = VS[k][n]
                    if dt not in p.index:
                        continue
                    i = p.index.get_loc(dt)
                    pv = float(p.iloc[i])
                    tv = abs(pv - float(p.iloc[i - 1])) if i else 0.0
                    E[k] *= 1 + pv * float(RET[k].loc[dt]) - tv * FEE
                sk = sum(E.values())
                if zm is not None and dt.month != zm:
                    c = {k: sk * w for k, w in UTEZI.items()}
                    E = {k: v2 - abs(v2 - E[k]) * FEE for k, v2 in c.items()}
                zm = dt.month
                pot.append(sum(E.values()))
            pot = np.array(pot)
            r = np.diff(pot, prepend=100.0) / np.concatenate([[100.0], pot[:-1]])
            eq = np.cumprod(1 + r)
            vol = r.std() * np.sqrt(PPY)
            vr.append(float(r.mean() * PPY / vol))
            if okno == "hold-out":
                md = float((eq / np.maximum.accumulate(eq) - 1).min() * 100)
            out.setdefault("knjiga", {}).setdefault(n, {})[okno] = round(vr[-1], 2)
        print("  %-20s%12.2f%12.2f%12.2f%11.0f %%" % (n, *vr, md))

    (ROOT / "testing" / "data" / "ostrina_izstopa.json").write_text(
        json.dumps(out, indent=1, default=str), encoding="utf-8")
    print("\nzapisano v testing/data/ostrina_izstopa.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
