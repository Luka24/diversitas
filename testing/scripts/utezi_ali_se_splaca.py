"""Ali se utezi po tveganju sploh splacajo? Test pomembnosti + enostavnejsa pot.

    python testing/scripts/utezi_ali_se_splaca.py

VPRASANJE
Razlika med danasnjimi utezmi in utezmi po tveganju je majhna: Sharpe povsod
skoraj enak, najhujsi padec na hold-outu -12 % proti -16 %. Preden se karkoli
uveljavi, je treba odgovoriti na dvoje:

  1  je razlika sploh vecja od suma?
  2  ce je, ali se da isto dobiti brez mesecnega racunanja volatilnosti?

Druga tocka je pomembnejsa. Dinamicne utezi zahtevajo drsece okno, mesecno
prevrednotenje in nov vir napake. Ce STATICNE utezi, izracunane enkrat, dajo
skoraj isto, je zapletenost odvec.

RAZLICICE
    danes            50/10/10/10/10/10, kapitalske
    staticno         fiksne utezi, izracunane iz POVPRECNE volatilnosti SAMO
                     na treningu, torej brez pogleda naprej, in nato zamrznjene
    dinamicno        utez = cilj / sigma(60 dni), mesecno prevrednoteno

METODA
Vezani blocni bootstrap, blok 20 dni, 5000 vzorcev, na dnevnih donosih obeh
knjig hkrati, da se ohrani soodvisnost. Interval zaupanja na razliki Sharpa in
na razliki najhujsega padca.

Plus drsece leto: v koliksnem delu 365-dnevnih oken je razlika pozitivna.

0,30 % na stran. Delitev kot povsod.

Izhod: testing/data/utezi_ali_se_splaca.json
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

from graded_alti import DELITEV, FEE, PPY, SREDSTVA, UTEZI, cene, pozicija
from knjiga_stroski_tveganje import sigme

RNG = np.random.default_rng(20260831)
NBOOT, BLOK = 5000, 20
KONEC_TRENINGA = pd.Timestamp("2023-06-30", tz="UTC")


def knjiga(idx, POS, RET, nacin: str, SIG=None, stat_w=None):
    E = {k: 100.0 * w for k, w in UTEZI.items()}
    pot, zm = [], None
    for d in idx:
        for k in UTEZI:
            p = POS[k]
            if d not in p.index:
                continue
            i = p.index.get_loc(d)
            pv = float(p.iloc[i])
            tv = abs(pv - float(p.iloc[i - 1])) if i else 0.0
            E[k] *= 1 + pv * float(RET[k].loc[d]) - tv * FEE
        sk = sum(E.values())
        if zm is not None and d.month != zm:
            if nacin == "danes":
                w = dict(UTEZI)
            elif nacin == "staticno":
                w = stat_w
            else:
                s = SIG.loc[d]
                sur = {k: UTEZI[k] / s[k] if np.isfinite(s.get(k, np.nan))
                       and s[k] > 0 else UTEZI[k] for k in UTEZI}
                vs = sum(sur.values())
                w = {k: v / vs for k, v in sur.items()}
            c = {k: sk * w[k] for k in UTEZI}
            E = {k: v - abs(v - E[k]) * FEE for k, v in c.items()}
        zm = d.month
        pot.append(sum(E.values()))
    pot = np.array(pot)
    return np.diff(pot, prepend=100.0) / np.concatenate([[100.0], pot[:-1]])


def met(r):
    eq = np.cumprod(1 + r)
    dd = eq / np.maximum.accumulate(eq) - 1
    vol = r.std() * np.sqrt(PPY)
    dn = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(PPY)
    cg = float((eq[-1] ** (PPY / len(r)) - 1) * 100)
    md = float(dd.min() * 100)
    return {"sharpe": float(r.mean() * PPY / vol),
            "sortino": float(r.mean() * PPY / dn),
            "cagr": cg, "maxdd": md, "calmar": cg / abs(md)}


def bootstrap(ra, rb):
    """Vezani blocni bootstrap na razliki. Isti bloki za obe seriji."""
    n = len(ra)
    nb = int(np.ceil(n / BLOK))
    ds, dm = [], []
    for _ in range(NBOOT):
        z = RNG.integers(0, n - BLOK, nb)
        i = np.concatenate([np.arange(s, s + BLOK) for s in z])[:n]
        a, b = met(ra[i]), met(rb[i])
        ds.append(b["sharpe"] - a["sharpe"])
        dm.append(b["maxdd"] - a["maxdd"])
    return np.array(ds), np.array(dm)


def main() -> int:
    C = cene()
    RET = {s: C[s]["close"].pct_change().fillna(0.0) for s in SREDSTVA}
    POS = {s: pozicija(C[s], None) for s in SREDSTVA}
    idx_vse = POS["BTC"].index
    SIG = sigme(C, idx_vse)

    # staticne utezi SAMO iz treninga, brez pogleda naprej
    tren = SIG.loc[SIG.index <= KONEC_TRENINGA]
    povp = tren.mean()
    # HYPE v treningu se ne obstaja (prva kotacija 2024-12), zato ne more imeti
    # utezi brez pogleda naprej. Dobi povprecje ostalih altcoinov, kar je
    # posteno vnaprejsnje ugibanje in je tako tudi navedeno.
    alti = [k for k in UTEZI if k not in ("BTC", "HYPE")]
    if not np.isfinite(povp.get("HYPE", np.nan)):
        povp["HYPE"] = float(np.mean([povp[k] for k in alti]))
        print("   (HYPE nima treninga, dobi povprecje altcoinov: %.0f %%)"
              % (povp["HYPE"] * 100))
    sur = {k: UTEZI[k] / float(povp[k]) for k in UTEZI}
    vs = sum(sur.values())
    STAT = {k: v / vs for k, v in sur.items()}

    print("VOLATILNOST, povprecje SAMO na treningu (do 2023-06-30)")
    for k in UTEZI:
        print("   %-5s %5.0f %%" % (k, float(povp[k]) * 100))
    print("\nSTATICNE UTEZI, zamrznjene iz teh volatilnosti")
    for k in UTEZI:
        print("   %-5s danes %3.0f %%  ->  staticno %4.1f %%"
              % (k, UTEZI[k] * 100, STAT[k] * 100))

    out = {"staticne_utezi": {k: round(v * 100, 1) for k, v in STAT.items()}}

    for okno, a, b in DELITEV:
        idx = idx_vse
        if a:
            idx = idx[idx >= pd.Timestamp(a, tz="UTC")]
        if b:
            idx = idx[idx <= pd.Timestamp(b, tz="UTC")]
        R = {n: knjiga(idx, POS, RET, n, SIG, STAT)
             for n in ("danes", "staticno", "dinamicno")}

        print("\n\n%s  %s do %s, %d dni"
              % (okno.upper(), a or "zacetek", b or "danes", len(idx)))
        print("  %-12s%9s%10s%8s%9s%9s"
              % ("razlicica", "Sharpe", "Sortino", "CAGR", "MaxDD", "Calmar"))
        for n, r in R.items():
            m = met(r)
            out.setdefault(okno, {}).setdefault("metrike", {})[n] = {
                k: round(v, 2) for k, v in m.items()}
            print("  %-12s%9.2f%10.2f%7.0f%%%8.0f%%%9.2f"
                  % (n, m["sharpe"], m["sortino"], m["cagr"], m["maxdd"],
                     m["calmar"]))

        print("\n  BOOTSTRAP proti danasnjim utezem, 5000 vzorcev, blok 20 dni")
        print("  %-12s%22s%24s%12s"
              % ("razlicica", "d Sharpe [95 % IZ]", "d MaxDD [95 % IZ]",
                 "P(boljsi)"))
        for n in ("staticno", "dinamicno"):
            ds, dm = bootstrap(R["danes"], R[n])
            lo, hi = np.percentile(ds, [2.5, 97.5])
            mlo, mhi = np.percentile(dm, [2.5, 97.5])
            p = float((ds > 0).mean())
            out.setdefault(okno, {}).setdefault("bootstrap", {})[n] = {
                "dsharpe": round(float(ds.mean()), 3),
                "iz": [round(float(lo), 3), round(float(hi), 3)],
                "dmaxdd": round(float(dm.mean()), 2),
                "iz_maxdd": [round(float(mlo), 2), round(float(mhi), 2)],
                "p_boljsi": round(p, 3),
                "izkljucuje_nic": bool(lo > 0 or hi < 0)}
            print("  %-12s%8.3f [%6.2f,%6.2f]%9.2f [%6.1f,%6.1f]%11.0f %%"
                  % (n, ds.mean(), lo, hi, dm.mean(), mlo, mhi, p * 100))

        # drsece leto
        if len(idx) > 400:
            print("\n  DRSECE LETO, delez 365-dnevnih oken, kjer je boljsi")
            for n in ("staticno", "dinamicno"):
                z = 0
                tot = 0
                for i in range(0, len(idx) - 365, 20):
                    ma = met(R["danes"][i:i + 365])["sharpe"]
                    mb = met(R[n][i:i + 365])["sharpe"]
                    z += int(mb > ma)
                    tot += 1
                out.setdefault(okno, {}).setdefault("drsece", {})[n] = \
                    round(z / tot * 100, 0)
                print("     %-12s %3.0f %% od %d oken" % (n, z / tot * 100, tot))

    (ROOT / "testing" / "data" / "utezi_ali_se_splaca.json").write_text(
        json.dumps(out, indent=1, default=str), encoding="utf-8")
    print("\nzapisano v testing/data/utezi_ali_se_splaca.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
