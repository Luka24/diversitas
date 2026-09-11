"""Profesionalna konstrukcija portfelja na knjigi sestih, skozi protokol faz.

    python testing/scripts/knjiga_profesionalno.py

NACRT, IZPELJAN IZ LITERATURE
Man Group in Carver opisujeta HIERARHICNO zaporedje, ne enega samega posega:

  1  skaliranje po sredstvu     vsako sredstvo se skalira po SVOJI volatilnosti
  2  mnozitelj razprsitve       ker se tveganja delno iztecejo, se knjiga
                                lahko poveca. IDM = 1 / sqrt(w' C w), kjer je C
                                korelacijska matrika. Carver ga omeji na 2,5
  3  ciljanje na ravni knjige   celotna knjiga se skalira na ciljno
                                volatilnost portfelja

Man Group: "po skaliranju po sredstvu se lahko uporabi ciljanje na ravni
portfelja, ki zmanjsa izpostavljenost, ko korelacije narastejo."

To je pomembno prav za kripto, kjer so korelacije 0,7 do 0,8. Pri taksnih
korelacijah je IDM nizek in razprsitev prinese malo. Ta skript to tudi izmeri,
namesto da bi predpostavljal.

RAZLICICE
  0  danes                     binarni signal, fiksne utezi, mesecno uravnavanje
  1  po sredstvu X %           p_i = signal_i * clip(X / sigma_i, 0, kapa)
  2  knjiga X %                cela knjiga * clip(X / sigma_knjige, 0, kapa)
  3  hierarhicno               1 nato 2, kot priporocata Man Group in Carver
  4  hierarhicno + IDM         3 z mnoziteljem razprsitve

Vse sigme so 60-dnevne, do vceraj. Kapa 1 pomeni brez vzvoda, kapa 2 dovoli
dvakratnik.

MERILO je protokol faz, isto kot povsod:
  C1 zmaga v vsaj 3 od 4 rastocih faz     C3 zmaga v vsaj 70 % od 84 podmnozic
  C2 zmaga v vsaj 3 od 5 padajocih faz    C4 interval izkljucuje niclo navzgor

Ker sta Sharpe in Sortino neodvisna od obsega, se zmage v fazah stejejo po
Sortinu v rasteh in po zlozenem donosu v padcih.

Izhod: testing/data/knjiga_profesionalno.json
"""
from __future__ import annotations

import json
import sys
import warnings
from itertools import combinations
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "lean", Path(__file__).resolve().parent):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import numpy as np
import pandas as pd

from graded_alti import FEE, PPY, SREDSTVA, UTEZI, cene, pozicija
from faze_ciklov import datiraj

RNG = np.random.default_rng(20260901)
NBOOT, BLOK, K_TEST = 5000, 20, 3
OKNO_SIG = 60
IDM_KAPA = 2.5


def sig_sredstva(C: dict, idx) -> pd.DataFrame:
    out = {}
    for s in SREDSTVA:
        r = C[s]["close"].pct_change()
        out[s] = (r.rolling(OKNO_SIG).std() * np.sqrt(PPY)).shift(1).reindex(idx)
    return pd.DataFrame(out).ffill().bfill()


def idm_niz(C: dict, idx, okno: int = 250) -> pd.Series:
    """IDM = 1 / sqrt(w' C w), drsece, z zamikom enega dne."""
    R = pd.DataFrame({s: C[s]["close"].pct_change() for s in SREDSTVA}).reindex(idx)
    w = np.array([UTEZI[s] for s in SREDSTVA])
    w = w / w.sum()
    vals = np.full(len(idx), np.nan)
    for i in range(okno, len(idx)):
        sub = R.iloc[i - okno:i]
        Cm = sub.corr().to_numpy(float)
        Cm = np.nan_to_num(Cm, nan=0.0)
        np.fill_diagonal(Cm, 1.0)
        v = float(w @ Cm @ w)
        vals[i] = min(1.0 / np.sqrt(v), IDM_KAPA) if v > 0 else 1.0
    return pd.Series(vals, index=idx).shift(1).ffill().fillna(1.0)


def knjiga(idx, POS, RET) -> np.ndarray:
    """Denarna knjiga, mesecno uravnavanje na ciljne utezi."""
    E = {k: 100.0 * w for k, w in UTEZI.items()}
    pot, zm = [], None
    # vse serije so ze poravnane na idx, sredstvo pred kotacijo ima pozicijo 0
    PV = {k: POS[k].reindex(idx).fillna(0.0).to_numpy(float) for k in UTEZI}
    RV = {k: RET[k].reindex(idx).fillna(0.0).to_numpy(float) for k in UTEZI}
    for j, d in enumerate(idx):
        for k in UTEZI:
            pv = PV[k][j]
            tv = abs(pv - PV[k][j - 1]) if j else 0.0
            E[k] *= 1 + pv * RV[k][j] - tv * FEE
        sk = sum(E.values())
        if zm is not None and d.month != zm:
            c = {k: sk * w for k, w in UTEZI.items()}
            E = {k: v - abs(v - E[k]) * FEE for k, v in c.items()}
        zm = d.month
        pot.append(sum(E.values()))
    pot = np.array(pot)
    return np.diff(pot, prepend=100.0) / np.concatenate([[100.0], pot[:-1]])


def sortino(r):
    dn = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(PPY)
    return float(r.mean() * PPY / dn) if dn > 0 else np.nan


def sharpe(r):
    v = r.std() * np.sqrt(PPY)
    return float(r.mean() * PPY / v) if v > 0 else np.nan


def mdd(r):
    eq = np.cumprod(1 + r)
    return float((eq / np.maximum.accumulate(eq) - 1).min() * 100)


def zlozen(r):
    return float((np.prod(1 + r) - 1) * 100)


def boot(ra, rb, f):
    n, nb = len(ra), int(np.ceil(len(ra) / BLOK))
    d = []
    for _ in range(NBOOT):
        z = RNG.integers(0, n - BLOK, nb)
        i = np.concatenate([np.arange(x, x + BLOK) for x in z])[:n]
        d.append(f(rb[i]) - f(ra[i]))
    d = np.array(d)
    return float(d.mean()), float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))


def main() -> int:
    C = cene()
    P0 = {s: pozicija(C[s], None) for s in SREDSTVA}
    idx = P0["BTC"].index
    RET = {s: C[s]["close"].pct_change().fillna(0.0) for s in SREDSTVA}
    SIG = sig_sredstva(C, idx)
    IDM = idm_niz(C, idx)

    print("KNJIGA SESTIH, %s do %s, %d dni, 0,30 %% na stran"
          % (idx[0].date(), idx[-1].date(), len(idx)))
    print("\nKORELACIJE med sredstvi, zadnjih 250 dni")
    Rm = pd.DataFrame({s: C[s]["close"].pct_change() for s in SREDSTVA}).reindex(idx)
    Cm = Rm.iloc[-250:].corr()
    print("        " + "".join("%7s" % s for s in SREDSTVA))
    for s in SREDSTVA:
        print("  %-6s" % s + "".join("%7.2f" % Cm.loc[s, t] for t in SREDSTVA))
    povp = float((Cm.to_numpy()[np.triu_indices(len(SREDSTVA), 1)]).mean())
    print("\n  povprecna korelacija: %.2f" % povp)
    print("  IDM danes: %.2f  (Carver ga omeji na %.1f)" % (IDM.iloc[-1], IDM_KAPA))
    print("  IDM povprecje: %.2f" % IDM.mean())

    # ---- razlicice ----
    V = {"0 danes": P0}
    for cilj in (50.0, 70.0):
        for kapa, ozn in ((1.0, "brez vzvoda"), (2.0, "do 2x")):
            V["1 po sredstvu %d %%, %s" % (cilj, ozn)] = {
                s: (P0[s] * (cilj / 100.0 / SIG[s]).clip(0, kapa)).fillna(0.0)
                for s in SREDSTVA}

    # knjizna volatilnost osnovne knjige, za razlicici 2 in 3
    r0 = knjiga(idx, P0, RET)
    sig_k = pd.Series(r0, index=idx).rolling(OKNO_SIG).std().mul(
        np.sqrt(PPY)).shift(1).ffill().bfill()

    for cilj in (20.0, 30.0):
        for kapa, ozn in ((1.0, "brez vzvoda"), (2.0, "do 2x")):
            sk = (cilj / 100.0 / sig_k).clip(0, kapa)
            V["2 knjiga %d %%, %s" % (cilj, ozn)] = {
                s: (P0[s] * sk).fillna(0.0) for s in SREDSTVA}

    # hierarhicno: po sredstvu 50 %, nato knjiga na 20 %
    baza = {s: (P0[s] * (0.50 / SIG[s]).clip(0, 1.0)).fillna(0.0) for s in SREDSTVA}
    rh = knjiga(idx, baza, RET)
    sig_h = pd.Series(rh, index=idx).rolling(OKNO_SIG).std().mul(
        np.sqrt(PPY)).shift(1).ffill().bfill()
    for kapa, ozn in ((1.0, "brez vzvoda"), (2.0, "do 2x")):
        sk = (0.20 / sig_h).clip(0, kapa)
        V["3 hierarhicno, %s" % ozn] = {s: (baza[s] * sk).fillna(0.0)
                                        for s in SREDSTVA}
        V["4 hierarhicno + IDM, %s" % ozn] = {
            s: (baza[s] * sk * IDM).clip(0, kapa * 2).fillna(0.0)
            for s in SREDSTVA}

    R = {n: knjiga(idx, POS, RET) for n, POS in V.items()}
    IZP = {n: float(np.mean([POS[s].reindex(idx).fillna(0).mean()
                             for s in SREDSTVA])) for n, POS in V.items()}

    print("\n\n1) CELA ZGODOVINA KNJIGE")
    print("  %-30s%8s%9s%8s%8s%9s"
          % ("razlicica", "Sharpe", "Sortino", "CAGR", "MaxDD", "izpost"))
    out = {"korelacija": round(povp, 2), "idm": round(float(IDM.iloc[-1]), 2)}
    for n, r in R.items():
        eq = np.cumprod(1 + r)
        m = {"sharpe": round(sharpe(r), 2), "sortino": round(sortino(r), 2),
             "cagr": round(float((eq[-1] ** (PPY / len(r)) - 1) * 100), 1),
             "maxdd": round(mdd(r), 1), "izpost": round(IZP[n] * 100, 1),
             "konec": round(float(eq[-1]), 1)}
        out.setdefault("cela", {})[n] = m
        print("  %-30s%8.2f%9.2f%7.0f%%%7.0f%%%8.0f%%"
              % (n, m["sharpe"], m["sortino"], m["cagr"], m["maxdd"], m["izpost"]))

    # ---- protokol faz ----
    faze = [(o, d, v) for o, d, v in datiraj(C["BTC"]["close"])
            if d >= idx[0] and o <= idx[-1]]
    maske = [((idx >= o) & (idx <= d)) for o, d, v in faze]
    vrste = [v for _, _, v in faze]
    osn = R["0 danes"]
    kombi = list(combinations(range(len(faze)), K_TEST))
    print("\n  faze v tem obdobju: %d rastocih, %d padajocih"
          % (vrste.count("rast"), vrste.count("padec")))

    print("\n2) PROTOKOL FAZ")
    print("  %-30s%9s%10s%9s%24s%22s"
          % ("razlicica", "rast", "padec", "kombi", "d Sortino [95 % IZ]",
             "d MaxDD [95 % IZ]"))
    for n, r in R.items():
        if n == "0 danes":
            continue
        zr = sum(1 for m, v in zip(maske, vrste)
                 if v == "rast" and sortino(r[m]) > sortino(osn[m]))
        zp = sum(1 for m, v in zip(maske, vrste)
                 if v == "padec" and zlozen(r[m]) > zlozen(osn[m]))
        dd = []
        for k in kombi:
            m = np.zeros(len(idx), bool)
            for i in k:
                m |= maske[i]
            dd.append(sortino(r[m]) - sortino(osn[m]))
        c3 = float((np.array(dd) > 0).mean())
        m1, l1, h1 = boot(osn, r, sortino)
        m2, l2, h2 = boot(osn, r, mdd)
        out.setdefault("protokol", {})[n] = {
            "rast": zr, "padec": zp, "kombi": round(c3 * 100, 0),
            "dsortino": round(m1, 2), "iz_s": [round(l1, 2), round(h1, 2)],
            "dmaxdd": round(m2, 1), "iz_m": [round(l2, 1), round(h2, 1)],
            "C1": zr >= 3, "C2": zp >= 3, "C3": c3 >= 0.70, "C4": l1 > 0}
        print("  %-30s%6d od %d%7d od %d%7.0f %%%9.2f [%+.2f,%+.2f]%9.1f [%+.1f,%+.1f]"
              % (n, zr, vrste.count("rast"), zp, vrste.count("padec"),
                 c3 * 100, m1, l1, h1, m2, l2, h2))

    print("\n3) SODBA")
    print("  %-30s%6s%6s%6s%6s%11s" % ("razlicica", "C1", "C2", "C3", "C4", "izid"))
    n_ok = 0
    for n in R:
        if n == "0 danes":
            continue
        z = out["protokol"][n]
        vsi = z["C1"] and z["C2"] and z["C3"] and z["C4"]
        n_ok += int(vsi)
        print("  %-30s%6s%6s%6s%6s%11s"
              % (n, *["DA" if z[c] else "ne" for c in ("C1", "C2", "C3", "C4")],
                 "SPREJET" if vsi else "zavrnjen"))
    print("\n  sprejetih: %d od %d" % (n_ok, len(R) - 1))
    print("\n  opomba: kjer d MaxDD izkljucuje niclo navzgor, je padec dokazano "
          "plitvejsi,\n  tudi ce Sortino ni dokazan. To je menjava, ne izboljsava.")

    (ROOT / "testing" / "data" / "knjiga_profesionalno.json").write_text(
        json.dumps(out, indent=1, default=str), encoding="utf-8")
    print("\nzapisano v testing/data/knjiga_profesionalno.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
