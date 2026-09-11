"""Poroclo in dashboard morata na istih vhodih dati isto stevilko.

    python testing/scripts/uskladi_dashboard.py

ZAKAJ TO OBSTAJA
Poroclo o knjiznem stikalu je racunal en motor (`knjizno_stikalo.py`),
objavljena stran pa drug (`diversitas-sestava/ui/dashboard.py`). Ko sta dala
razlicni stevilki, ni bilo mogoce reci, ali gre za napako v enem od njiju ali
le za drugacne nastavitve. Iskanje vzroka je vzelo cel krog vprasanj in vmes
sem dvakrat trdil napacno stvar -- enkrat, da Yahoo vraca razlicne cene (ni res,
primerjal sem posnetka ob razlicnih trenutkih), in enkrat, da je vzrok v
plavanju trajnega dna (tudi ni bilo).

Ta skripta to zapre. Oba motorja dobita ISTE cene, ISTE signale in ISTE posle,
in rezultat mora biti enak do strojne natancnosti. Vsaka prihodnja razlika je
potem nujno v vhodih, ne v modelu -- in to je vprasanje, na katero je mogoce
odgovoriti v minuti namesto v uri.

Preverja se tudi tisto, kar je razliko dejansko povzrocilo:

  * OGREVANJE. Dokler 200 SMA ne obstaja, pandas primerja `close > NaN` kot
    neresnicno in rezimski filter se TIHO izklopi. Dashboard te bare odreze,
    prva razlicica testa pa ne -- zato je SOL trgoval pol leta prezgodaj.
  * POSLI. `preveri_pine.py` primerja pozicije, ne pa poslov, zato je razlika
    v obratu na SOL sla skozi vseh 58 preverb neopazeno.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SESTAVA = ROOT.parent / "diversitas-sestava"
for p in (ROOT, ROOT / "lean", SESTAVA):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

OD = "2021-06-17"
# SESTO (XRP -> HYPE sredi poti, s stroskom zamenjave) je posebnost dashboarda.
# Motor porocila je nima, zato bi njena vkljucitev primerjala DVE RAZLICNI
# knjigi namesto dveh motorjev. Tu je zato sesto mesto kar XRP; razlika, ki jo
# to prinese, je izmerjena loceno in znasa 0,16 odstotne tocke letnega donosa.
UTEZI = {"BTC": 0.50, "ETH": 0.10, "SOL": 0.10,
         "LINK": 0.10, "BNB": 0.10, "XRP": 0.10}
VIRI_TEST = {"BTC": "coinbase", "ETH": "coinbase", "SOL": "coinbase",
             "LINK": "coinbase", "BNB": "yahoo", "XRP": "yahoo"}
# ogrevanje pride iz shared/warmup.py, ne z roke


def main() -> int:
    if not SESTAVA.exists():
        print(f"repozitorija {SESTAVA} ni -- preverbe ni mogoce izvesti")
        return 0
    from ui import dashboard as D                                # noqa: E402
    from shared.data_source import fetch_candles                 # noqa: E402
    from testing.scripts import knjizno_stikalo as K             # noqa: E402
    from shared.warmup import warmup_bars                        # noqa: E402
    from testing.scripts.preveri_pine import (                   # noqa: E402
        avtomat_po_pine, pine_privzetki, po_pine, pozicija_po_pine)

    def sesto(k):
        """Kateri simbol je na sestem mestu -- za posle in donose enako kot
        za pozicije. Prva razlicica te preverbe je za SESTO jemala pozicijo
        XRP->HYPE, posle in donose pa samo XRP; neujemanje je bilo v preverbi,
        ne v motorjih."""
        return "XRP" if k != "SESTO" else None

    vsi = tuple(D.VIRI)
    CENE = D._cene.__wrapped__(vsi)
    SIG = D._signali.__wrapped__(vsi, CENE)
    so = SIG["HYPE"][0].index[0]
    idx = CENE["BTC"].loc[pd.Timestamp(OD, tz="UTC"):].index
    vse = []

    # ── 1. ISTI VHODI: motorja se morata ujemati do strojne natancnosti ──────
    print("1  ISTI VHODI -- oba motorja na istih cenah, signalih in poslih")
    P = pd.DataFrame({k: SIG[k][0].reindex(idx) for k in UTEZI})
    TR = pd.DataFrame({k: SIG[k][1].reindex(idx).fillna(0.0) for k in UTEZI})
    RET = pd.DataFrame({k: CENE[k]["close"].pct_change().reindex(idx).fillna(0.0)
                        for k in UTEZI})
    K.UTEZI = UTEZI
    for st in (False, True):
        # dashboard
        r_d, _, _, _ = D._knjiga(idx, CENE, SIG, UTEZI, 30, False, so, 1,
                                 stikalo=st)
        # motor porocila, na istih vhodih
        if st:
            # `z_stikalom` signal zamakne SAM. `SIG["BTC"][0]` pa je ze
            # pozicija, torej ze vcerajsnji signal -- podati njo bi pomenilo
            # DVOJNI zamik. Zato se surovo stanje avtomata izracuna znova.
            px_btc = fetch_candles("BTC", "1d", bars=3000, prefer="coinbase")
            f_btc = po_pine(px_btc, pine_privzetki())
            sig_btc = avtomat_po_pine(f_btc, pine_privzetki())["signalState"]
            s = (sig_btc.reindex(idx) == 1).fillna(False)
            r_m, _, _ = K.z_stikalom(P, RET, s, TR, fee=0.30)
        else:
            r_m = K._pot_knjige(P.fillna(0.0), RET, TR, fee=0.30)
        d = np.abs(np.asarray(r_d) - r_m.to_numpy())
        ok = bool(d.max() < 1e-12)
        vse.append(ok)
        print(f"   stikalo={str(st):<6} max razlika dnevnega donosa {d.max():.2e}"
              f"   {'OK' if ok else 'RAZLIKA'}")

    # ── 2. OGREVANJE: brez odreza SOL trguje prezgodaj ──────────────────────
    print("\n2  OGREVANJE -- 200 SMA in tiho izklopljen rezimski filter")
    p0 = pine_privzetki()
    px = fetch_candles("SOL", "1d", bars=3000, prefer="coinbase")
    f = po_pine(px, p0)
    sig = avtomat_po_pine(f, p0)["signalState"].to_numpy()
    h, tr = pozicija_po_pine(px, sig, p0)
    brez = pd.Series(tr, index=px.index).reindex(idx).fillna(0.0).sum()
    n_ogr = warmup_bars(f)
    _, t_t = pozicija_po_pine(
        px.iloc[n_ogr:], sig[n_ogr:], p0,
        prev_sig=(int(sig[n_ogr - 1]) if n_ogr else None),
        prev_close=(float(px["close"].iloc[n_ogr - 1]) if n_ogr else None))
    tr2 = np.zeros(len(px)); tr2[n_ogr:] = t_t
    z = pd.Series(tr2, index=px.index).reindex(idx).fillna(0.0).sum()
    dash = SIG["SOL"][1].reindex(idx).fillna(0.0).sum()
    ok = abs(z - dash) < 1e-9
    vse.append(ok)
    print(f"   SOL, vsota poslov: brez odreza {brez:.4f}, z odrezom {z:.4f}, "
          f"dashboard {dash:.4f}   {'OK' if ok else 'RAZLIKA'}")

    # ── 3. POSLI po sredstvih, ne le pozicije ───────────────────────────────
    print("\n3  POSLI po sredstvih -- vrzel, ki je prvo razliko spustila skozi")
    for sym, vir in VIRI_TEST.items():
        px = fetch_candles(sym, "1d", bars=3000, prefer=vir)
        f = po_pine(px, p0)
        sig = avtomat_po_pine(f, p0)["signalState"].to_numpy()
        n_ogr = warmup_bars(f)
        h_t, t_t = pozicija_po_pine(
            px.iloc[n_ogr:], sig[n_ogr:], p0,
            prev_sig=(int(sig[n_ogr - 1]) if n_ogr else None),
            prev_close=(float(px["close"].iloc[n_ogr - 1]) if n_ogr else None))
        h2 = np.zeros(len(px)); tr = np.zeros(len(px))
        h2[n_ogr:], tr[n_ogr:] = h_t, t_t
        a_t = pd.Series(tr, index=px.index).reindex(idx).fillna(0.0)
        b_t = SIG[sym][1].reindex(idx).fillna(0.0)
        a_p = pd.Series(h2, index=px.index).reindex(idx).fillna(0.0)
        b_p = SIG[sym][0].reindex(idx).fillna(0.0)
        dt = float(np.abs(a_t - b_t).max())
        dp = float(np.abs(a_p - b_p).max())
        ok = dt < 1e-9 and dp < 1e-9
        vse.append(ok)
        print(f"   {sym:<6} posli {dt:.2e}   pozicije {dp:.2e}   "
              f"{'OK' if ok else 'RAZLIKA'}")

    print()
    if all(vse):
        print(f"vseh {len(vse)} preverb je uspelo -- porocilo in dashboard "
              f"racunata isto")
        return 0
    print(f"NEUSPESNIH: {sum(1 for x in vse if not x)} od {len(vse)}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
