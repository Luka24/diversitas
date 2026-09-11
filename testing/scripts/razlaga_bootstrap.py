"""Zakaj se metrike sploh spremenijo, ce prerazporedim dneve. Delovni primer.

    python testing/scripts/razlaga_bootstrap.py

Vprasanje je upraviceno: ce donose samo premesam, se vsota in povprecje ne
spremenita, torej se ne bi smel spremeniti niti Sharpe.

To DRZI, in prav zato bootstrap NI mesanje.

  premesaj        vsak dan se pojavi natanko enkrat, samo v drugem vrstnem redu
  bootstrap       bloki se vlecejo Z VRACANJEM, torej se nekateri pojavijo
                  dvakrat ali trikrat, drugi pa niti enkrat

Prvo ne spremeni nicesar razen poti. Drugo spremeni sestavo vzorca, in prav
zato lahko odgovori na vprasanje "kako drugacna bi lahko bila zgodovina".

Skript to pokaze na desetih izmisljenih dneh, kjer se da vse presteti na roko,
nato pa se na pravih podatkih BTC.

Izhod: samo izpis.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "lean", Path(__file__).resolve().parent):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import numpy as np

PPY = 365
RNG = np.random.default_rng(7)


def metrike(r: np.ndarray, ppy=PPY) -> dict:
    """Vse stiri metrike, tocno tako, kot so definirane v projektu."""
    povp = r.mean()
    odklon = r.std()
    navzdol = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2))
    eq = np.cumprod(1 + r)
    dd = eq / np.maximum.accumulate(eq) - 1
    return {
        "povprecje": povp,
        "odklon": odklon,
        "navzdol": navzdol,
        "sharpe": povp * ppy / (odklon * np.sqrt(ppy)) if odklon else np.nan,
        "sortino": povp * ppy / (navzdol * np.sqrt(ppy)) if navzdol else np.nan,
        "zlozen": (eq[-1] - 1) * 100,
        "maxdd": dd.min() * 100,
    }


def izpis(ime, r, m):
    print("  %-22s %s" % (ime, " ".join("%+6.1f" % (x * 100) for x in r)))
    print("  %-22s povp %+.4f  odklon %.4f  navzdol %.4f"
          % ("", m["povprecje"], m["odklon"], m["navzdol"]))
    print("  %-22s Sharpe %+.3f  Sortino %+.3f  zlozen %+.2f %%  MaxDD %.2f %%\n"
          % ("", m["sharpe"], m["sortino"], m["zlozen"], m["maxdd"]))


def main() -> int:
    # ---------- 1) deset izmisljenih dni, da se da presteti na roko ----------
    r = np.array([2.0, -1.0, 3.0, -4.0, 1.0, 5.0, -2.0, 1.0, -3.0, 4.0]) / 100
    print("=" * 78)
    print("1) DESET DNI, DA SE DA PRESTETI NA ROKO   (donosi v odstotkih)")
    print("=" * 78)
    print("""
Formule, ki jih uporabljam povsod:

    povprecje   m  = (r1 + r2 + ... + rn) / n
    odklon      s  = sqrt( povprecje kvadratov odmikov od m )
    nihanje
    navzdol     d  = sqrt( povprecje od min(ri, 0)^2 )     nicle se stejejo!
    Sharpe         = m * 365 / ( s * sqrt(365) )
    Sortino        = m * 365 / ( d * sqrt(365) )
    zlozen         = (1+r1)(1+r2)...(1+rn) - 1
    MaxDD          = najnizja vrednost od  tekoca / dosedanji vrh - 1
""")
    m0 = metrike(r)
    izpis("izvirnik", r, m0)

    print("  Rocno za izvirnik:")
    print("     vsota = %+.2f %%,  n = %d,  torej povprecje = %+.4f %%"
          % (r.sum() * 100, len(r), r.mean() * 100))
    neg = np.minimum(r, 0.0)
    print("     negativni dnevi: %s"
          % " ".join("%.1f" % (x * 100) for x in neg if x < 0))
    print("     kvadrati vseh min(ri,0), tudi niclastih, povprecje = %.6f"
          % np.mean(neg ** 2))
    print("     koren tega = %.4f, kar je nihanje navzdol\n" % np.sqrt(np.mean(neg ** 2)))

    # ---------- 2) premesaj ----------
    print("=" * 78)
    print("2) SAMO PREMESAJ  (vsak dan natanko enkrat, drug vrstni red)")
    print("=" * 78 + "\n")
    for k in range(3):
        p = RNG.permutation(r)
        izpis("premesano %d" % (k + 1), p, metrike(p))

    print("""  Poglej stolpce. Povprecje, odklon, nihanje navzdol, Sharpe, Sortino in
  zlozen donos so PRI VSEH ENAKI. To ni nakljucje:

     povprecje je vsota deljena z n, in vsota se ob mesanju ne spremeni
     odklon in nihanje navzdol sta prav tako le povprecji, neodvisni od reda
     zlozen donos je zmnozek, mnozenje pa je komutativno

  Spremeni se SAMO MaxDD, ker ta edini bere zaporedje. Ce vse slabe dneve
  postavis skupaj, dobis globlji padec, tudi ce so dnevi isti.

  Zato mesanje ne more odgovoriti na vprasanje o Sharpu. Za to je treba
  spremeniti SESTAVO vzorca, ne le vrstnega reda.
""")

    # ---------- 3) bootstrap ----------
    print("=" * 78)
    print("3) BOOTSTRAP  (bloki po 3 dni, vleceni Z VRACANJEM)")
    print("=" * 78 + "\n")
    for k in range(4):
        zac = RNG.integers(0, len(r) - 3, 4)
        i = np.concatenate([np.arange(s, s + 3) for s in zac])[:len(r)]
        b = r[i]
        print("  izbrani zacetki blokov: %s  ->  indeksi dni: %s"
              % (list(zac), list(i)))
        st = np.bincount(i, minlength=len(r))
        print("  kolikokrat je vsak dan vzet: %s" % list(st))
        izpis("bootstrap %d" % (k + 1), b, metrike(b))

    print("""  Tu se spremeni VSE. Razlog je v vrstici "kolikokrat je vsak dan vzet":
  nekateri dnevi se pojavijo dvakrat, drugi niti enkrat. To ni ista zgodovina
  v drugem vrstnem redu, to je DRUGACNA zgodovina, sestavljena iz istih kosov.

  Prav to je vprasanje, na katerega hocem odgovor: ce bi se zgodovina odvila
  malo drugace, a iz istega materiala, ali bi bila razlika med razlicicama se
  vedno pozitivna?
""")

    # ---------- 4) na pravih podatkih ----------
    print("=" * 78)
    print("4) ISTO NA PRAVIH PODATKIH: lean na BTC proti stopnjevanju k>=2")
    print("=" * 78 + "\n")
    from graded_alti import cene, pozicija
    from protokol_faze import neto

    C = cene()
    raw = C["BTC"]
    A, B = pozicija(raw, None), pozicija(raw, 2)
    idx = A.index.intersection(B.index)
    ret = raw["close"].pct_change().reindex(idx).fillna(0.0)
    ra = neto(A.reindex(idx), ret).to_numpy(float)
    rb = neto(B.reindex(idx), ret).to_numpy(float)
    n = len(ra)
    print("  %d dni.  izvirni Sharpe: osnova %.3f, stopnjevano %.3f, razlika %+.3f"
          % (n, metrike(ra)["sharpe"], metrike(rb)["sharpe"],
             metrike(rb)["sharpe"] - metrike(ra)["sharpe"]))

    print("\n  a) 2000 premesanj, isti dnevi v drugem vrstnem redu:")
    d = []
    for _ in range(2000):
        p = RNG.permutation(n)
        d.append(metrike(rb[p])["sharpe"] - metrike(ra[p])["sharpe"])
    d = np.array(d)
    print("     razlika Sharpa:  min %+.6f   max %+.6f   razpon %.2e"
          % (d.min(), d.max(), d.max() - d.min()))
    print("     torej vedno ista. Mesanje o Sharpu ne pove nicesar.")

    print("\n  b) 2000 bootstrapov, bloki po 20 dni, z vracanjem:")
    d = []
    for _ in range(2000):
        zac = RNG.integers(0, n - 20, int(np.ceil(n / 20)))
        i = np.concatenate([np.arange(s, s + 20) for s in zac])[:n]
        d.append(metrike(rb[i])["sharpe"] - metrike(ra[i])["sharpe"])
    d = np.array(d)
    lo, hi = np.percentile(d, [2.5, 97.5])
    print("     razlika Sharpa:  povprecje %+.3f   min %+.3f   max %+.3f"
          % (d.mean(), d.min(), d.max()))
    print("     95 %% interval:  [%+.3f, %+.3f]" % (lo, hi))
    print("     delez pozitivnih: %.0f %%" % ((d > 0).mean() * 100))
    print("     interval %s niclo -> razlika %s"
          % ("VSEBUJE" if lo < 0 < hi else "IZKLJUCUJE",
             "NI dokazana" if lo < 0 < hi else "JE dokazana"))

    print("""
  c) In koliko dni se sploh ponovi ali izpusti pri enem bootstrapu:""")
    zac = RNG.integers(0, n - 20, int(np.ceil(n / 20)))
    i = np.concatenate([np.arange(s, s + 20) for s in zac])[:n]
    st = np.bincount(i, minlength=n)
    print("     dni, ki se ne pojavijo:  %d od %d  (%.0f %%)"
          % ((st == 0).sum(), n, (st == 0).mean() * 100))
    print("     dni, vzeti enkrat:       %d" % (st == 1).sum())
    print("     dni, vzeti dvakrat:      %d" % (st == 2).sum())
    print("     dni, vzeti trikrat ali vec: %d" % (st >= 3).sum())
    print("""
     Priblizno tretjina zgodovine v vsakem poskusu izpade. Ravno zato je
     vsaka od 5000 nadomestnih zgodovin verodostojna, a drugacna.
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
