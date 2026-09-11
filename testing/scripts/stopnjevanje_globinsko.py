"""Stopnjevana velikost pozicije: koliko je zmaga na celi zgodovini res vredna.

    python testing/scripts/stopnjevanje_globinsko.py

Na celi zgodovini BTC stopnjevanje k>=2 premaga danasnjo obliko: Sortino 2,54
proti 2,20, koncni mnogokratnik 123 proti 101. To je edini zavrnjeni kandidat z
opazno prednostjo, zato si zasluzi natancnejso obravnavo od "pade na validaciji".

KAJ SE MERI
  1  vezani blocni bootstrap na razliki, 5000 vzorcev, blok 20 dni
  2  razclenitev prednosti po letih, koliko prispeva vsako leto
  3  kaj ostane, ce se odstrani najboljse leto
  4  prag provizije, pri katerem se prednost izgubi, na vsakem oknu posebej
  5  stevilo poslov in povprecno trajanje pozicije
  6  isto na kosarici sestih

Vprasanje, na katerega je treba odgovoriti: je zmaga na celi zgodovini prava
lastnost, ki jo je validacija le slucajno zgresila, ali je zmaga sama slucaj?

Izhod: testing/data/stopnjevanje_globinsko.json
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

from graded_alti import DELITEV, FEE, PPY, SREDSTVA, cene, pozicija

RNG = np.random.default_rng(20260831)
NBOOT, BLOK = 5000, 20


def neto(p: pd.Series, ret: pd.Series, fee=FEE) -> np.ndarray:
    t = p.diff().abs().fillna(0.0)
    return (p * ret - t * fee).fillna(0.0).to_numpy(float)


def sortino(r: np.ndarray) -> float:
    dn = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(PPY)
    return float(r.mean() * PPY / dn) if dn > 0 else np.nan


def sharpe(r: np.ndarray) -> float:
    v = r.std() * np.sqrt(PPY)
    return float(r.mean() * PPY / v) if v > 0 else np.nan


def boot(ra, rb, f):
    n, nb = len(ra), int(np.ceil(len(ra) / BLOK))
    d = []
    for _ in range(NBOOT):
        z = RNG.integers(0, n - BLOK, nb)
        i = np.concatenate([np.arange(s, s + BLOK) for s in z])[:n]
        d.append(f(rb[i]) - f(ra[i]))
    d = np.array(d)
    lo, hi = np.percentile(d, [2.5, 97.5])
    return float(d.mean()), float(lo), float(hi), float((d > 0).mean())


def posli(p: pd.Series) -> tuple[int, float]:
    v = (p > 0.06).astype(int)
    vstopi = int(((v.diff() == 1)).sum())
    return vstopi, float(v.sum() / vstopi) if vstopi else np.nan


def main() -> int:
    C = cene()
    raw = C["BTC"]
    A = pozicija(raw, None)
    B = pozicija(raw, 2)
    idx = A.index.intersection(B.index)
    A, B = A.reindex(idx), B.reindex(idx)
    ret = raw["close"].pct_change().reindex(idx).fillna(0.0)
    ra, rb = neto(A, ret), neto(B, ret)
    out = {}

    print("BTC, %s do %s, %d dni, 0,30 %% na stran"
          % (idx[0].date(), idx[-1].date(), len(idx)))
    print("primerjava: danasnja binarna oblika proti stopnjevanju k>=2\n")

    # 1 bootstrap
    print("1) VEZANI BLOCNI BOOTSTRAP, 5000 vzorcev, blok 20 dni")
    for ime, f in (("Sortino", sortino), ("Sharpe", sharpe)):
        m, lo, hi, p = boot(ra, rb, f)
        out.setdefault("bootstrap_cela", {})[ime] = {
            "razlika": round(m, 3), "iz": [round(lo, 3), round(hi, 3)],
            "p_boljsi": round(p, 3), "izkljucuje_nic": bool(lo > 0 or hi < 0)}
        print("   d%-9s %+6.3f   95 %% IZ [%+.3f, %+.3f]   P(boljsi) %3.0f %%   %s"
              % (ime, m, lo, hi, p * 100,
                 "IZKLJUCUJE NIC" if lo > 0 else "vsebuje nic"))

    # 2 po letih
    print("\n2) RAZCLENITEV PO LETIH")
    print("   %-6s%10s%10s%10s%12s" % ("leto", "binarno", "k>=2", "razlika",
                                       "prispevek"))
    leta = sorted({d.year for d in idx})
    vr = {}
    for l in leta:
        w = idx.year == l
        if w.sum() < 60:
            continue
        sa, sb = sortino(ra[w]), sortino(rb[w])
        vr[l] = (sa, sb, sb - sa)
        print("   %-6d%10.2f%10.2f%+10.2f%12s"
              % (l, sa, sb, sb - sa, "*" * int(abs(sb - sa) * 4)))
    out["po_letih"] = {str(k): [round(x, 2) for x in v] for k, v in vr.items()}

    raz = sorted(vr.items(), key=lambda x: -abs(x[1][2]))
    print("\n   najvecji prispevki: " + ", ".join(
        "%d (%+.2f)" % (k, v[2]) for k, v in raz[:3]))

    # 3 brez najboljsega leta
    najb = raz[0][0]
    print("\n3) KAJ OSTANE BREZ LETA %d" % najb)
    w = idx.year != najb
    print("   %-22s%10s%10s%10s" % ("", "binarno", "k>=2", "razlika"))
    print("   %-22s%10.2f%10.2f%+10.2f"
          % ("cela zgodovina", sortino(ra), sortino(rb), sortino(rb) - sortino(ra)))
    print("   %-22s%10.2f%10.2f%+10.2f"
          % ("brez %d" % najb, sortino(ra[w]), sortino(rb[w]),
             sortino(rb[w]) - sortino(ra[w])))
    m, lo, hi, p = boot(ra[w], rb[w], sortino)
    print("   bootstrap brez %d: %+.3f  95 %% IZ [%+.3f, %+.3f]  P %3.0f %%"
          % (najb, m, lo, hi, p * 100))
    out["brez_najboljsega_leta"] = {
        "leto": najb, "razlika": round(sortino(rb[w]) - sortino(ra[w]), 3),
        "iz": [round(lo, 3), round(hi, 3)], "p_boljsi": round(p, 3)}

    # 4 prag provizije po oknih
    print("\n4) PRAG PROVIZIJE, pri katerem prednost izgine, po oknih")
    print("   %-14s" % "okno" + "".join("%9s" % ("%.2f%%" % (f * 100))
                                        for f in (0.0, 0.001, 0.003, 0.005, 0.01)))
    for okno, a, b in (("cela zgodovina", None, None),) + DELITEV:
        w = idx
        if a:
            w = w[w >= pd.Timestamp(a, tz="UTC")]
        if b:
            w = w[w <= pd.Timestamp(b, tz="UTC")]
        vrsta = []
        for f in (0.0, 0.001, 0.003, 0.005, 0.01):
            d = sortino(neto(B.reindex(w), ret.reindex(w), f)) \
                - sortino(neto(A.reindex(w), ret.reindex(w), f))
            vrsta.append(d)
        out.setdefault("provizije_po_oknih", {})[okno] = [round(x, 2) for x in vrsta]
        print("   %-14s" % okno + "".join("%+9.2f" % x for x in vrsta))

    # 5 posli
    print("\n5) POSLI IN TRAJANJE")
    for ime, p in (("binarno", A), ("k>=2", B)):
        n, tr = posli(p)
        t = p.diff().abs().fillna(0.0).sum()
        print("   %-10s vstopov %3d   povprecno trajanje %5.1f dni   "
              "obrat %6.1f   provizije %5.1f %%"
              % (ime, n, tr, t, t * FEE * 100))

    # 6 kosarica
    print("\n6) KOSARICA SESTIH, bootstrap po oknih")
    POS = {"binarno": {s: pozicija(C[s], None) for s in SREDSTVA},
           "k>=2": {s: pozicija(C[s], 2) for s in SREDSTVA}}
    RET = {s: C[s]["close"].pct_change().fillna(0.0) for s in SREDSTVA}
    from utezi_ali_se_splaca import knjiga
    print("   %-14s%9s%9s%22s%11s"
          % ("okno", "binarno", "k>=2", "d Sharpe [95 % IZ]", "P(boljsi)"))
    for okno, a, b in DELITEV:
        w = POS["binarno"]["BTC"].index
        if a:
            w = w[w >= pd.Timestamp(a, tz="UTC")]
        if b:
            w = w[w <= pd.Timestamp(b, tz="UTC")]
        r1 = knjiga(w, POS["binarno"], RET, "danes")
        r2 = knjiga(w, POS["k>=2"], RET, "danes")
        m, lo, hi, p = boot(r1, r2, sharpe)
        out.setdefault("knjiga", {})[okno] = {
            "binarno": round(sharpe(r1), 2), "k2": round(sharpe(r2), 2),
            "razlika": round(m, 3), "iz": [round(lo, 3), round(hi, 3)],
            "p_boljsi": round(p, 3)}
        print("   %-14s%9.2f%9.2f%9.3f [%+.2f,%+.2f]%10.0f %%"
              % (okno, sharpe(r1), sharpe(r2), m, lo, hi, p * 100))

    (ROOT / "testing" / "data" / "stopnjevanje_globinsko.json").write_text(
        json.dumps(out, indent=1, default=str), encoding="utf-8")
    print("\nzapisano v testing/data/stopnjevanje_globinsko.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
