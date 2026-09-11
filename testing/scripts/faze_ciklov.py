"""Ovrednoti vse kandidate po DATIRANIH fazah cikla, ne le na hold-outu.

    python testing/scripts/faze_ciklov.py

ZAKAJ
Trojna delitev na trening, validacijo in hold-out odgovarja na vprasanje "ali
sem izbiral posteno". NE odgovarja na vprasanje "ali to dela tudi v padcu",
ker vsako od treh oken vsebuje mesanico faz. Hold-out je poleg tega eno samo
obdobje in po nakljucju je zajel eno najslabsih obdobij za sledenje trendu v
zgodovini panoge.

Delitev po 200-dnevnem povprecju, ki sem jo uporabljal doslej, je za to
premalo. Meja se krizajo sem in tja, faze so razdrobljene, in kratki prehodi
se stejejo enako kot dvoletni medvedji trg.

KAKO TO DELAJO PROFESIONALCI
Akademski standard za datiranje faz je algoritem Bry in Boschan (1971) v
razlicici Pagan in Sossounov za financne trge. Postopek:

  1  najdi lokalne vrhove in dna v oknu +/- K dni
  2  vsili izmenjavanje: za vrhom mora priti dno in obratno
  3  vsili najkrajso dolzino faze, da se odstrani sum
  4  vsili najmanjso amplitudo, da se odstranijo nepomembni premiki

Rezultat so datirane faze rasti (dno do vrha) in padca (vrh do dna), ki so
objektivne in ponovljive.

Nastavitve tu, prilagojene kriptu, ki je hitrejsi od delnic:
  K = 90 dni, najkrajsa faza 120 dni, najmanjsa amplituda 25 %

KAJ SE MERI
Za vsako fazo posebej, za vsakega kandidata: donos, najhujsi padec,
izpostavljenost, provizije. V padajocih fazah se primerja ZLOZEN DONOS in ne
razmerja, ker so razmerja pri negativnem stevcu obrnjena.

Na koncu: v koliko rastocih in v koliko padajocih fazah kandidat premaga
osnovo. To je merilo, ki ga hold-out sam ne more dati.

Izhod: testing/data/faze_ciklov.json
"""
from __future__ import annotations

import json
import sys
import warnings
from dataclasses import replace
from itertools import product
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "lean", Path(__file__).resolve().parent):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import numpy as np
import pandas as pd

from graded_alti import FEE, PPY, SREDSTVA, UTEZI, _cfg, cene, pozicija
from ansambel import DC_MREZA, OSNOVA, TL_MREZA, ena_pozicija

K_OKNO, MIN_FAZA, MIN_AMPL = 90, 120, 0.25


def datiraj(cena: pd.Series) -> list[tuple]:
    """Bry-Boschan v razlicici Pagan-Sossounov. Vrne [(od, do, 'rast'|'padec')]."""
    x = np.log(cena.to_numpy(float))
    n = len(x)

    # 1) lokalni ekstremi v oknu +/- K
    vrh, dno = [], []
    for i in range(K_OKNO, n - K_OKNO):
        okno = x[i - K_OKNO:i + K_OKNO + 1]
        if x[i] == okno.max():
            vrh.append(i)
        elif x[i] == okno.min():
            dno.append(i)

    # 2) izmenjavanje: med dvema vrhovoma obdrzi visjega, med dnoma nizjega
    tocke = sorted([(i, "V") for i in vrh] + [(i, "D") for i in dno])
    ocisceno = []
    for i, t in tocke:
        if ocisceno and ocisceno[-1][1] == t:
            j, _ = ocisceno[-1]
            boljsi = (x[i] > x[j]) if t == "V" else (x[i] < x[j])
            if boljsi:
                ocisceno[-1] = (i, t)
            continue
        ocisceno.append((i, t))

    # 3) in 4) najkrajsa dolzina in najmanjsa amplituda
    spremenjeno = True
    while spremenjeno and len(ocisceno) > 2:
        spremenjeno = False
        for a in range(len(ocisceno) - 1):
            i, ti = ocisceno[a]
            j, _ = ocisceno[a + 1]
            if (j - i) < MIN_FAZA or abs(x[j] - x[i]) < np.log(1 + MIN_AMPL):
                # odstrani sibkejso od obeh mejnih tock
                del ocisceno[a + 1]
                if a + 1 < len(ocisceno) and ocisceno[a][1] == ocisceno[a + 1][1]:
                    del ocisceno[a + 1]
                spremenjeno = True
                break

    faze = []
    for a in range(len(ocisceno) - 1):
        i, ti = ocisceno[a]
        j, _ = ocisceno[a + 1]
        faze.append((cena.index[i], cena.index[j], "rast" if ti == "D" else "padec"))
    return faze


def neto(p: pd.Series, ret: pd.Series) -> pd.Series:
    t = p.diff().abs().fillna(0.0)
    return (p * ret - t * FEE).fillna(0.0)


def na_fazi(p: pd.Series, ret: pd.Series, od, do) -> dict:
    w = (p.index >= od) & (p.index <= do)
    if w.sum() < 30:
        return {}
    r = neto(p, ret)[w].to_numpy(float)
    t = p.diff().abs().fillna(0.0)[w]
    eq = np.cumprod(1 + r)
    dd = eq / np.maximum.accumulate(eq) - 1
    return {"donos": round(float((eq[-1] - 1) * 100), 1),
            "maxdd": round(float(dd.min() * 100), 1),
            "izpost": round(float(p[w].mean() * 100), 1),
            "provizije": round(float(t.sum() * FEE * 100), 2),
            "dni": int(w.sum())}


def main() -> int:
    C = cene()
    raw = C["BTC"]
    cena = raw["close"]

    faze = datiraj(cena)
    print("DATIRANE FAZE BTC, Bry-Boschan / Pagan-Sossounov")
    print("okno +/- %d dni, najkrajsa faza %d dni, najmanjsa amplituda %d %%\n"
          % (K_OKNO, MIN_FAZA, MIN_AMPL * 100))
    print("  %-4s%-13s%-13s%8s%10s%12s" % ("vrsta", "od", "do", "dni",
                                           "sprem.", "BTC kupi-drzi"))
    opis = []
    for od, do, vr in faze:
        d = (do - od).days
        s = float(cena.loc[do] / cena.loc[od] - 1) * 100
        opis.append({"od": str(od.date()), "do": str(do.date()), "vrsta": vr,
                     "dni": d, "sprememba": round(s, 1)})
        print("  %-4s  %-13s%-13s%8d%9.0f%%%12.0f %%"
              % ("^" if vr == "rast" else "v", str(od.date()), str(do.date()),
                 d, s, s))

    # ---- kandidati ----
    print("\n\nSESTAVLJAM KANDIDATE")
    V = {"osnova (danes)": pozicija(raw, None), "stopnje k>=2": pozicija(raw, 2)}
    P = {}
    for k in {OSNOVA} | {(t, OSNOVA[1]) for t in TL_MREZA} \
            | {(OSNOVA[0], d) for d in DC_MREZA} | set(product(TL_MREZA, DC_MREZA)):
        P[k] = ena_pozicija(raw, *k)
    V["ansambel TL"] = pd.concat([P[(t, OSNOVA[1])] for t in TL_MREZA],
                                 axis=1).mean(axis=1)
    V["ansambel DC"] = pd.concat([P[(OSNOVA[0], d)] for d in DC_MREZA],
                                 axis=1).mean(axis=1)
    cfg0 = _cfg()
    for dno in (0.0, 10.0):
        c = replace(cfg0, bear_alloc_pct=dno)
        from diversitas.strategy import position, run_strategy
        from shared.warmup import trim_warmup
        V["dno %.0f %%" % dno] = position(
            trim_warmup(run_strategy(raw, config=c).df), c).astype(float)
    V["BTC kupi in drzi"] = pd.Series(1.0, index=V["osnova (danes)"].index)

    idx = V["osnova (danes)"].index
    for v in V.values():
        idx = idx.intersection(v.index)
    V = {k: v.reindex(idx) for k, v in V.items()}
    ret = cena.pct_change().reindex(idx).fillna(0.0)
    print("   %d kandidatov, %d skupnih dni" % (len(V), len(idx)))

    out = {"faze": opis, "po_fazah": {}}

    for vrsta in ("rast", "padec"):
        izbrane = [f for f in faze if f[2] == vrsta
                   and (f[1] >= idx[0]) and (f[0] <= idx[-1])]
        print("\n\n%s FAZE, donos v odstotkih" % vrsta.upper())
        glava = "  %-18s" % "kandidat" + "".join(
            "%12s" % str(od.date())[2:] for od, _, _ in izbrane) + "%10s" % "povprecje"
        print(glava)
        for n, p in V.items():
            vrst, ime_v = [], []
            for od, do, _ in izbrane:
                m = na_fazi(p, ret, od, do)
                if m:
                    vrst.append(m["donos"])
                    ime_v.append(str(od.date()))
                    out["po_fazah"].setdefault(n, {})[str(od.date())] = m
            if vrst:
                print("  %-18s" % n + "".join("%11.0f%%" % x for x in vrst)
                      + "%9.0f%%" % float(np.mean(vrst)))

        print("\n  izpostavljenost v teh fazah, odstotek dni")
        for n, p in V.items():
            vrst = [na_fazi(p, ret, od, do).get("izpost", np.nan)
                    for od, do, _ in izbrane]
            vrst = [x for x in vrst if np.isfinite(x)]
            if vrst:
                print("  %-18s" % n + "".join("%11.0f%%" % x for x in vrst)
                      + "%9.0f%%" % float(np.mean(vrst)))

    # ---- zmage proti osnovi ----
    print("\n\nKOLIKOKRAT KANDIDAT PREMAGA OSNOVO, po fazah")
    print("  %-18s%14s%14s%12s" % ("kandidat", "rastoce faze", "padajoce faze",
                                   "skupaj"))
    for n, p in V.items():
        if n == "osnova (danes)":
            continue
        z = {"rast": [0, 0], "padec": [0, 0]}
        for od, do, vr in faze:
            a = na_fazi(V["osnova (danes)"], ret, od, do)
            b = na_fazi(p, ret, od, do)
            if not a or not b:
                continue
            z[vr][1] += 1
            z[vr][0] += int(b["donos"] > a["donos"])
        sk = (z["rast"][0] + z["padec"][0], z["rast"][1] + z["padec"][1])
        out.setdefault("zmage", {})[n] = {"rast": z["rast"], "padec": z["padec"]}
        print("  %-18s%10d od %d%10d od %d%8d od %d"
              % (n, z["rast"][0], z["rast"][1], z["padec"][0], z["padec"][1],
                 sk[0], sk[1]))

    # ---- provizije po vrsti faze ----
    print("\n\nPROVIZIJE, odstotek kapitala, povprecno na fazo")
    print("  %-18s%14s%14s%14s" % ("kandidat", "rastoca faza", "padajoca faza",
                                   "razmerje"))
    for n, p in V.items():
        a = [na_fazi(p, ret, od, do).get("provizije", np.nan)
             for od, do, vr in faze if vr == "rast"]
        b = [na_fazi(p, ret, od, do).get("provizije", np.nan)
             for od, do, vr in faze if vr == "padec"]
        a = [x for x in a if np.isfinite(x)]
        b = [x for x in b if np.isfinite(x)]
        if a and b:
            print("  %-18s%13.2f%%%13.2f%%%14.2f"
                  % (n, np.mean(a), np.mean(b), np.mean(b) / np.mean(a)))

    (ROOT / "testing" / "data" / "faze_ciklov.json").write_text(
        json.dumps(out, indent=1, default=str), encoding="utf-8")
    print("\nzapisano v testing/data/faze_ciklov.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
