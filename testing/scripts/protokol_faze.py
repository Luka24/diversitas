"""Protokol ocenjevanja cez VSE faze cikla, ne le na enem hold-outu.

    python testing/scripts/protokol_faze.py

TEZAVA Z ENIM HOLD-OUTOM
Nas hold-out se zacne 2025-04-01 in lezi v celoti znotraj padajoce faze, v
kateri je BTC izgubil 41 %. Kar smo tam izmerili, je odgovor na eno samo
vprasanje: kako se kandidat obnese v padcu. O rasti ne pove nicesar.

To ni napaka delitve, je njena meja. Delitev sluzi postenosti izbire, ne
pokritosti rezimov. Za pokritost je potreben drug postopek.

KAKO TO DELAJO PROFESIONALCI
Lopez de Prado: namesto ene delitve naredi KOMBINATORICNO precno preverjanje.
Podatke razrezi na N skupin, za testno mnozico vzemi vsako kombinacijo k skupin,
in dobis C(N,k) ocen namesto ene. Vsaka skupina je testna veckrat.

CTA panoga: locено merjenje zajema navzgor in navzdol, ter zahteva, da
kandidat ni odvisen od enega rezima.

TA PROTOKOL ZDRUZI OBOJE
Skupine niso poljubni bloki, ampak DATIRANE faze cikla po Bry-Boschanu v
razlicici Pagan-Sossounov. To je bolje od enakih blokov, ker vsaka skupina
ustreza resnicnemu trznemu stanju, ne koledarju.

Devet faz: 4 rastoce, 5 padajocih.

  A  po fazah        kandidat proti osnovi na vsaki fazi posebej, z intervalom
                     zaupanja iz blocnega bootstrapa znotraj faze
  B  kombinatoricno  vseh C(9,3) = 84 podmnozic treh faz. Za vsako se izracuna
                     razlika. Porazdelitev teh 84 razlik pove, kako pogosto
                     kandidat zmaga na nakljucni tretjini zgodovine
  C  razslojeno      zahteva, da zmaga v vecini RASTOCIH in v vecini PADAJOCIH
                     faz. Kandidat, ki zmaga samo v eni vrsti, je stava na rezim
  D  zajem           delez rasti BTC in delez padca BTC, ki ju kandidat zajame

MERILO ZA SPREJEM, doloceno vnaprej
    C1  zmaga v vsaj 3 od 4 rastocih faz
    C2  zmaga v vsaj 3 od 5 padajocih faz
    C3  v kombinatoricnem testu zmaga v vsaj 70 % od 84 podmnozic
    C4  95 % interval zaupanja na celi zgodovini izkljucuje niclo
Sprejme se le kandidat, ki izpolni vse stiri.

V padajocih fazah se primerja ZLOZEN DONOS, ne razmerja, ker so razmerja pri
negativnem stevcu obrnjena.

Izhod: testing/data/protokol_faze.json
"""
from __future__ import annotations

import json
import sys
import warnings
from dataclasses import replace
from itertools import combinations, product
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "lean", Path(__file__).resolve().parent):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import numpy as np
import pandas as pd

from graded_alti import FEE, PPY, _cfg, cene, pozicija
from ansambel import DC_MREZA, OSNOVA, TL_MREZA, ena_pozicija
from faze_ciklov import datiraj
from diversitas.strategy import position, run_strategy
from shared.warmup import trim_warmup

RNG = np.random.default_rng(20260831)
NBOOT, BLOK, K_TEST = 2000, 20, 3


def sestavi(raw) -> dict[str, pd.Series]:
    V = {"osnova (danes)": pozicija(raw, None)}
    for k in (1, 2, 3):
        V["stopnje k>=%d" % k] = pozicija(raw, k)
    P = {}
    for kk in {OSNOVA} | {(t, OSNOVA[1]) for t in TL_MREZA} \
            | {(OSNOVA[0], d) for d in DC_MREZA} | set(product(TL_MREZA, DC_MREZA)):
        P[kk] = ena_pozicija(raw, *kk)
    V["ansambel TL"] = pd.concat([P[(t, OSNOVA[1])] for t in TL_MREZA],
                                 axis=1).mean(axis=1)
    V["ansambel DC"] = pd.concat([P[(OSNOVA[0], d)] for d in DC_MREZA],
                                 axis=1).mean(axis=1)
    V["ansambel oba"] = pd.concat([P[k] for k in product(TL_MREZA, DC_MREZA)],
                                  axis=1).mean(axis=1)
    c0 = _cfg()
    for dno in (0.0, 10.0):
        c = replace(c0, bear_alloc_pct=dno)
        V["dno %.0f %%" % dno] = position(
            trim_warmup(run_strategy(raw, config=c).df), c).astype(float)
    for g in (1, 2, 4, 5):
        c = replace(c0, exit_grace_bars=g)
        V["izstop po %d dneh" % g] = position(
            trim_warmup(run_strategy(raw, config=c).df), c).astype(float)
    return V


def neto(p, ret):
    return (p * ret - p.diff().abs().fillna(0.0) * FEE).fillna(0.0)


def zlozen(r: np.ndarray) -> float:
    return float((np.prod(1 + r) - 1) * 100)


def boot_zlozen(ra, rb):
    n, nb = len(ra), int(np.ceil(len(ra) / BLOK))
    d = []
    for _ in range(NBOOT):
        z = RNG.integers(0, max(1, n - BLOK), nb)
        i = np.concatenate([np.arange(s, min(s + BLOK, n)) for s in z])[:n]
        d.append(zlozen(rb[i]) - zlozen(ra[i]))
    d = np.array(d)
    return float(d.mean()), float(np.percentile(d, 2.5)), \
        float(np.percentile(d, 97.5)), float((d > 0).mean())


def main() -> int:
    C = cene()
    raw = C["BTC"]
    cena = raw["close"]
    faze = datiraj(cena)

    V = sestavi(raw)
    idx = V["osnova (danes)"].index
    for v in V.values():
        idx = idx.intersection(v.index)
    V = {k: v.reindex(idx) for k, v in V.items()}
    ret = cena.pct_change().reindex(idx).fillna(0.0)
    R = {n: neto(p, ret).to_numpy(float) for n, p in V.items()}

    faze = [(o, d, v) for o, d, v in faze if d >= idx[0] and o <= idx[-1]]
    maske = [((idx >= o) & (idx <= d)) for o, d, v in faze]
    vrste = [v for _, _, v in faze]
    print("BTC, %s do %s, %d dni. %d faz: %d rastocih, %d padajocih."
          % (idx[0].date(), idx[-1].date(), len(idx), len(faze),
             vrste.count("rast"), vrste.count("padec")))
    print("Provizija 0,30 %% na stran. V padcih se primerja zlozen donos.\n")

    osn = R["osnova (danes)"]
    out = {"faze": [{"od": str(o.date()), "do": str(d.date()), "vrsta": v,
                     "dni": int(m.sum())}
                    for (o, d, v), m in zip(faze, maske)]}

    # ---- A po fazah ----
    print("A) DONOS PO FAZAH, odstotki. Krepko = premaga osnovo")
    glava = "  %-18s" % "kandidat"
    for (o, _, v), m in zip(faze, maske):
        glava += "%9s" % (("+" if v == "rast" else "-") + str(o.date())[2:7])
    print(glava)
    for n, r in R.items():
        vr = [zlozen(r[m]) for m in maske]
        out.setdefault("po_fazah", {})[n] = [round(x, 1) for x in vr]
        s = "  %-18s" % n
        for x, m in zip(vr, maske):
            b = zlozen(osn[m])
            s += "%8.0f%s" % (x, "*" if (n != "osnova (danes)" and x > b) else " ")
        print(s)

    # ---- C razslojeno ----
    print("\n\nC) RAZSLOJENO STETJE ZMAG")
    print("  %-18s%13s%14s%9s" % ("kandidat", "rastoce", "padajoce", "C1 in C2"))
    zmage = {}
    for n, r in R.items():
        if n == "osnova (danes)":
            continue
        zr = sum(1 for m, v in zip(maske, vrste)
                 if v == "rast" and zlozen(r[m]) > zlozen(osn[m]))
        zp = sum(1 for m, v in zip(maske, vrste)
                 if v == "padec" and zlozen(r[m]) > zlozen(osn[m]))
        nr, np_ = vrste.count("rast"), vrste.count("padec")
        ok = (zr >= 3) and (zp >= 3)
        zmage[n] = {"rast": [zr, nr], "padec": [zp, np_], "izpolnjuje": ok}
        print("  %-18s%8d od %d%9d od %d%9s"
              % (n, zr, nr, zp, np_, "DA" if ok else "ne"))
    out["razslojeno"] = zmage

    # ---- B kombinatoricno ----
    kombi = list(combinations(range(len(faze)), K_TEST))
    print("\n\nB) KOMBINATORICNO, vseh %d podmnozic po %d faz" % (len(kombi), K_TEST))
    print("  %-18s%12s%12s%12s%14s"
          % ("kandidat", "zmaga v", "mediana d", "najslabsa", "najboljsa"))
    for n, r in R.items():
        if n == "osnova (danes)":
            continue
        d = []
        for kmb in kombi:
            m = np.zeros(len(idx), bool)
            for i in kmb:
                m |= maske[i]
            d.append(zlozen(r[m]) - zlozen(osn[m]))
        d = np.array(d)
        delez = float((d > 0).mean())
        out.setdefault("kombinatoricno", {})[n] = {
            "delez_zmag": round(delez * 100, 0), "mediana": round(float(np.median(d)), 1),
            "min": round(float(d.min()), 1), "max": round(float(d.max()), 1),
            "izpolnjuje": bool(delez >= 0.70)}
        print("  %-18s%10.0f %%%12.1f%12.1f%14.1f"
              % (n, delez * 100, np.median(d), d.min(), d.max()))

    # ---- D zajem in celotni bootstrap ----
    print("\n\nD) ZAJEM IN INTERVAL ZAUPANJA NA CELI ZGODOVINI")
    bh = np.array([float(cena.loc[d] / cena.loc[o] - 1) * 100 for o, d, _ in faze])
    r_i = [i for i, v in enumerate(vrste) if v == "rast"]
    p_i = [i for i, v in enumerate(vrste) if v == "padec"]
    print("  %-18s%10s%10s%9s%24s%9s"
          % ("kandidat", "zajem+", "zajem-", "razmerje", "d zlozen [95 % IZ]", "C4"))
    for n, r in R.items():
        vr = np.array([zlozen(r[m]) for m in maske])
        zp = float(vr[r_i].mean() / bh[r_i].mean())
        zm = float(vr[p_i].mean() / bh[p_i].mean())
        if n == "osnova (danes)":
            print("  %-18s%9.0f%%%9.0f%%%9.2f%24s%9s"
                  % (n, zp * 100, zm * 100, zp / zm, "referenca", ""))
            continue
        m_, lo, hi, p = boot_zlozen(osn, r)
        ok = bool(lo > 0 or hi < 0)
        out.setdefault("zajem", {})[n] = {
            "zajem_rast": round(zp * 100, 0), "zajem_padec": round(zm * 100, 0),
            "razmerje": round(zp / zm, 2), "d": round(m_, 1),
            "iz": [round(lo, 1), round(hi, 1)], "C4": ok}
        print("  %-18s%9.0f%%%9.0f%%%9.2f%11.0f [%7.0f,%7.0f]%9s"
              % (n, zp * 100, zm * 100, zp / zm, m_, lo, hi,
                 "DA" if ok else "ne"))

    # ---- skupna sodba ----
    print("\n\nSKUPNA SODBA, vsi stirje pogoji")
    print("  %-18s%6s%6s%6s%6s%10s" % ("kandidat", "C1", "C2", "C3", "C4", "sprejet"))
    for n in R:
        if n == "osnova (danes)":
            continue
        z = out["razslojeno"][n]
        c1 = z["rast"][0] >= 3
        c2 = z["padec"][0] >= 3
        c3 = out["kombinatoricno"][n]["izpolnjuje"]
        c4 = out["zajem"][n]["C4"]
        vsi = c1 and c2 and c3 and c4
        out.setdefault("sodba", {})[n] = {"C1": c1, "C2": c2, "C3": c3,
                                          "C4": c4, "sprejet": vsi}
        print("  %-18s%6s%6s%6s%6s%10s"
              % (n, "DA" if c1 else "ne", "DA" if c2 else "ne",
                 "DA" if c3 else "ne", "DA" if c4 else "ne",
                 "SPREJET" if vsi else "zavrnjen"))

    n_ok = sum(1 for v in out["sodba"].values() if v["sprejet"])
    print("\n  sprejetih: %d od %d" % (n_ok, len(out["sodba"])))

    (ROOT / "testing" / "data" / "protokol_faze.json").write_text(
        json.dumps(out, indent=1, default=str), encoding="utf-8")
    print("\nzapisano v testing/data/protokol_faze.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
