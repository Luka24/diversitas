"""Stopnjevana velikost pozicije na BTC, podrobno, na danasnjem motorju.

    python testing/scripts/graded_btc_podrobno.py

Zakaj se enkrat. Stevilki 1,505 in 1,949 iz graded_full.json prihajata iz
celice, ki je imela Donchian IZKLOPLJEN. Danasnji lean ga ima vklopljenega, zato
tisti par ni primerjava z danasnjo obliko. Tu se vse racuna z danasnjo
konfiguracijo, brez izjeme.

Meri se: cela zgodovina, po koledarskih letih, po rezimih (200-dnevno
povprecje), po treh oknih delitve, obcutljivost na provizijo, in porazdelitev
posameznih poslov.

Provizija in zdrs 0,30 % na stran. Cene Coinbase.

Izhod: testing/data/graded_btc_podrobno.json
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "lean", Path(__file__).resolve().parent):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import numpy as np
import pandas as pd

from graded_alti import FEE, PPY, TERMS, _cfg, cene, pozicija
from diversitas.strategy import compute_features

RAZLICICE = {"danes (binarno)": None, "k>=1": 1, "k>=2": 2, "k>=3": 3}


def metrike(p: pd.Series, ret: pd.Series, fee=FEE) -> dict:
    t = p.diff().abs().fillna(0.0)
    r = (p * ret - t * fee).fillna(0.0).to_numpy(float)
    eq = np.cumprod(1 + r)
    dd = eq / np.maximum.accumulate(eq) - 1
    vol = r.std() * np.sqrt(PPY)
    dn = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(PPY)
    cagr = float((eq[-1] ** (PPY / len(r)) - 1) * 100)
    mdd = float(dd.min() * 100)
    # dnevi z dobickom med dnevi, ko smo bili v trgu
    v_trgu = p.shift(1).fillna(0) > 0.06
    poz = int(((r > 0) & v_trgu).sum())
    n_v = int(v_trgu.sum())
    return {
        "sharpe": round(float(r.mean() * PPY / vol), 2) if vol > 0 else np.nan,
        "sortino": round(float(r.mean() * PPY / dn), 2) if dn > 0 else np.nan,
        "cagr": round(cagr, 1),
        "maxdd": round(mdd, 1),
        "calmar": round(cagr / abs(mdd), 2) if mdd < 0 else np.nan,
        "vol": round(float(vol * 100), 1),
        "skupaj": round(float((eq[-1] - 1) * 100), 0),
        "izpost": round(float(p.mean() * 100), 1),
        "obrat": round(float(t.sum()), 1),
        "provizije": round(float(t.sum() * fee * 100), 1),
        "delez_dobrih_dni": round(poz / n_v * 100, 1) if n_v else np.nan,
        "dni": len(r),
    }


def izpis(naslov, vrstice):
    print("\n%s" % naslov)
    print("  %-17s%8s%9s%8s%8s%8s%8s%9s%10s"
          % ("razlicica", "Sharpe", "Sortino", "CAGR", "MaxDD", "Calmar",
             "vol", "izpost", "provizije"))
    for ime, m in vrstice:
        print("  %-17s%8.2f%9.2f%7.0f%%%7.0f%%%8.2f%7.0f%%%8.0f%%%9.1f%%"
              % (ime, m["sharpe"], m["sortino"], m["cagr"], m["maxdd"],
                 m["calmar"], m["vol"], m["izpost"], m["provizije"]))


def main() -> int:
    C = cene()
    raw = C["BTC"]
    cfg = _cfg()
    ret = raw["close"].pct_change().fillna(0.0)

    POS = {ime: pozicija(raw, prag) for ime, prag in RAZLICICE.items()}
    idx = POS["danes (binarno)"].index
    ret = ret.reindex(idx).fillna(0.0)
    out = {}

    print("BTC, Coinbase, %s do %s, %d dni, 0,30 %% na stran"
          % (idx[0].date(), idx[-1].date(), len(idx)))
    print("konfiguracija: use_donchian=%s, donchian_period=%s, confirm=%s, "
          "reentry=%s, dno=%s %%"
          % (cfg.use_donchian, cfg.donchian_period, cfg.confirm_bars,
             cfg.reentry_hold, cfg.bear_alloc_pct))

    # --- 1) cela zgodovina -------------------------------------------------
    v = [(n, metrike(POS[n], ret)) for n in RAZLICICE]
    out["cela_zgodovina"] = {n: m for n, m in v}
    izpis("1) CELA ZGODOVINA", v)
    print("\n  %-17s%12s%12s%14s" % ("razlicica", "konec x", "obrat", "dobri dnevi"))
    for n, m in v:
        print("  %-17s%11.1fx%11.1f%13.1f %%"
              % (n, 1 + m["skupaj"] / 100, m["obrat"], m["delez_dobrih_dni"]))

    # --- 2) po koledarskih letih ------------------------------------------
    print("\n\n2) PO KOLEDARSKIH LETIH, Sortino")
    leta = sorted({d.year for d in idx})
    print("  %-17s" % "razlicica" + "".join("%8d" % l for l in leta))
    tab = {}
    for n in RAZLICICE:
        vrsta = []
        for l in leta:
            w = idx[idx.year == l]
            vrsta.append(metrike(POS[n].reindex(w), ret.reindex(w))["sortino"]
                         if len(w) > 60 else np.nan)
        tab[n] = vrsta
        print("  %-17s" % n + "".join(
            "%8s" % ("%.2f" % x if np.isfinite(x) else "-") for x in vrsta))
    out["po_letih"] = {"leta": leta, "sortino": tab}
    zmage = sum(1 for i in range(len(leta))
                if np.isfinite(tab["k>=2"][i])
                and tab["k>=2"][i] > tab["danes (binarno)"][i])
    vseh = sum(1 for i in range(len(leta)) if np.isfinite(tab["k>=2"][i]))
    print("\n  k>=2 premaga binarno v %d od %d let" % (zmage, vseh))

    # --- 3) po rezimu ------------------------------------------------------
    ma200 = raw["close"].rolling(200).mean().reindex(idx)
    bik = (raw["close"].reindex(idx) > ma200)
    print("\n\n3) PO REZIMU (cena nad/pod 200-dnevnim povprecjem), Sortino")
    print("  %-17s%12s%12s" % ("razlicica", "bikovski", "medvedji"))
    rez = {}
    for n in RAZLICICE:
        a = metrike(POS[n][bik.fillna(False)], ret[bik.fillna(False)])["sortino"]
        b = metrike(POS[n][~bik.fillna(True)], ret[~bik.fillna(True)])["sortino"]
        rez[n] = {"bik": a, "medved": b}
        print("  %-17s%12.2f%12.2f" % (n, a, b))
    out["po_rezimu"] = rez

    # --- 4) tri okna -------------------------------------------------------
    print("\n\n4) TRI OKNA DELITVE")
    okna = (("trening", None, "2023-06-30"),
            ("validacija", "2023-07-01", "2025-03-31"),
            ("hold-out", "2025-04-01", None))
    for okno, a, b in okna:
        w = idx
        if a:
            w = w[w >= pd.Timestamp(a, tz="UTC")]
        if b:
            w = w[w <= pd.Timestamp(b, tz="UTC")]
        v = [(n, metrike(POS[n].reindex(w), ret.reindex(w))) for n in RAZLICICE]
        out.setdefault("okna", {})[okno] = {n: m for n, m in v}
        izpis("  %s, %s do %s, %d dni"
              % (okno.upper(), a or "zacetek", b or "danes", len(w)), v)

    # --- 5) obcutljivost na provizijo -------------------------------------
    print("\n\n5) OBCUTLJIVOST NA PROVIZIJO, Sortino na celi zgodovini")
    stopnje = (0.0, 0.001, 0.002, 0.003, 0.005, 0.0075, 0.010)
    print("  %-17s" % "razlicica" + "".join("%9s" % ("%.2f %%" % (f * 100))
                                            for f in stopnje))
    ob = {}
    for n in RAZLICICE:
        vrsta = [metrike(POS[n], ret, f)["sortino"] for f in stopnje]
        ob[n] = vrsta
        print("  %-17s" % n + "".join("%9.2f" % x for x in vrsta))
    out["provizije"] = {"stopnje": list(stopnje), "sortino": ob}
    prelom = None
    for f, a, b in zip(stopnje, ob["k>=2"], ob["danes (binarno)"]):
        if a < b:
            prelom = f
            break
    print("\n  k>=2 pade pod binarno pri proviziji: %s"
          % ("%.2f %%" % (prelom * 100) if prelom is not None
             else "nikoli v tem razponu"))

    # --- 6) porazdelitev k -------------------------------------------------
    df = compute_features(raw, None, cfg)
    k = sum(df[t].fillna(False).astype(int) for t in TERMS).reindex(idx)
    print("\n\n6) KOLIKO POGOJEV DRZI, cela zgodovina")
    for val in range(5):
        n = int((k == val).sum())
        print("   k=%d  %5d dni  %5.1f %%" % (val, n, n / len(k) * 100))
    out["porazdelitev_k"] = {str(v): int((k == v).sum()) for v in range(5)}

    (ROOT / "testing" / "data" / "graded_btc_podrobno.json").write_text(
        json.dumps(out, indent=1, default=str), encoding="utf-8")
    print("\nzapisano v testing/data/graded_btc_podrobno.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
