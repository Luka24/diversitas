"""Buffer izstopa, prilagojen volatilnosti kovanca. Test 2 iz testing/nacrt_word_ideje.md.

    python testing/scripts/buffer_volatilnost.py

MERILA, ZAPISANA PRED PRVIM ZAGONOM (nacrt v commitu ba50fda)

Kandidat (samo eden)
    B1  buffer kovanca = 3 % x (sigma kovanca / sigma BTC). Sigma je standardni
        odklon dnevnih log donosov zadnjih 365 dni, zamaknjen za en dan. BTC ima
        vedno tocno 3 %. Dokler kovanec ali BTC nima 365 dni, velja 3 %. Brez
        spodnje in zgornje meje. Drugih oken ne poganjamo.
Buffer odloca samo o izstopu (tri zaporedna zaprtja pod trackline - buffer).
Vstop, blow-off in vse ostalo ostane kot danes. Alti z BTC filtrom, kot v
produkciji.

Kontrole
    pozitivna  BTC pod B1 mora biti bit za bit enak osnovi; pot s prepisanim
               bufferjem, ki ji damo razmerje 1, mora dati osnovo na vseh altih
    negativna  B-  obrnjeno pravilo, 3 % x (sigma BTC / sigma kovanca): ozji pas pri
               bolj nihajocih kovancih. Ce tudi B- izpolni C1-C4 na knjigi, ucinek
               ni volatilnost, ampak katerakoli sprememba bufferja, in B1 je
               zavrnjen.
    mehanizem  delez izstopov, po katerih se lean v 30 dneh vrne po visji ceni,
               sesteto cez vse alte. Pri B1 mora biti nizji kot pri osnovi.

Sprejem B1 (vse):
    C1-C4 na knjigi, kot v blowoff_izstop.py (C4 z 98,3 % intervalom)
    preverba mehanizma zdrzi
    B- ne izpolni C1-C4
Sprememba Sortina knjige manjsa od 0,4 se poroca kot "v sumu" (meja iz testa ure
zakljucka), tudi ce gre skozi merila.

Produkcija se ne spremeni ne glede na izid.

Izhod: testing/data/buffer_volatilnost.json
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

from graded_alti import SREDSTVA, UTEZI, _cfg, cene
from fantomska_gotovina import knjiga
from faze_ciklov import datiraj
from blowoff_izstop import izpis_sodbe, maxdd, neto, sodba, sortino
from diversitas.strategy import compute_features, position, run_state_machine
from shared.warmup import trim_warmup

OKNO, OSNOVNI = 365, 3.0
IMENA = ("osnova", "B1 po volatilnosti", "B- obrnjeno")
ALTI = [s for s in SREDSTVA if s != "BTC"]


def sigma(close: pd.Series) -> pd.Series:
    r = np.log(close).diff()
    return r.rolling(OKNO, min_periods=OKNO).std().shift(1)


def razmerje(raw, btc, kand: str) -> pd.Series:
    if kand == "osnova" or btc is None:
        return pd.Series(1.0, index=raw.index)
    sk = sigma(raw["close"])
    sb = sigma(btc["close"]).reindex(raw.index)
    q = sk / sb if kand == "B1 po volatilnosti" else sb / sk
    return q.fillna(1.0)


def zagon(raw, btc, cfg, kand: str, q: pd.Series | None = None) -> pd.DataFrame:
    df = compute_features(raw, btc, cfg)
    if kand == "osnova" and q is None:
        return trim_warmup(run_state_machine(df, cfg))
    if q is None:
        q = razmerje(raw, btc, kand)
    buf = OSNOVNI * q.reindex(df.index).fillna(1.0)
    df["tl_lower"] = df["trackline"] - df["trackline"] * (buf / 100.0)
    df["below_tl"] = df["close"] < df["tl_lower"]
    df["buffer_pct"] = buf
    return trim_warmup(run_state_machine(df, cfg))


def ponovni_visje(df) -> tuple[int, int]:
    s, c = df["signal_state"], df["close"]
    vst = list(df.index[(s == 1) & (s.shift(1) != 1)])
    izs = df.index[(s != 1) & (s.shift(1) == 1)]
    n = 0
    for t in izs:
        nx = [v for v in vst if v > t and (v - t).days <= 30]
        n += bool(nx and c[nx[0]] > c[t])
    return n, len(izs)


def main() -> int:
    cfg = _cfg()
    C = cene()
    btc = C["BTC"]
    faze = datiraj(btc["close"])
    out = {}

    # pozitivni kontroli
    osn_btc = trim_warmup(run_state_machine(compute_features(btc, None, cfg), cfg))
    b1_btc = zagon(btc, None, cfg, "B1 po volatilnosti")
    ok1 = b1_btc["signal_state"].equals(osn_btc["signal_state"])
    ok2 = True
    for s in ALTI:
        a = trim_warmup(run_state_machine(compute_features(C[s], btc, cfg), cfg))
        b = zagon(C[s], btc, cfg, "B1 po volatilnosti", pd.Series(1.0, index=C[s].index))
        ok2 &= a["signal_state"].equals(b["signal_state"])
    print("Pozitivna kontrola: BTC pod B1 = osnova %s, prepisan buffer z razmerjem 1 = "
          "osnova na altih %s" % ("OK" if ok1 else "NAPAKA", "OK" if ok2 else "NAPAKA"))
    if not (ok1 and ok2):
        return 1

    RUN = {k: {} for k in IMENA}
    for k in IMENA:
        RUN[k]["BTC"] = osn_btc
        for s in ALTI:
            RUN[k][s] = zagon(C[s], btc, cfg, k)

    print("\nBUFFER PO KOVANCIH (mediana cez zgodovino) IN SORTINO POSAMEZNO")
    out["kovanci"] = {}
    for s in ALTI:
        v = {k: sortino(neto(RUN[k][s], cfg).to_numpy()) for k in IMENA}
        bb = float(RUN["B1 po volatilnosti"][s]["buffer_pct"].median())
        bm = float(RUN["B- obrnjeno"][s]["buffer_pct"].median())
        out["kovanci"][s] = {"buffer_B1": round(bb, 2), "buffer_B-": round(bm, 2),
                             **{k: round(x, 2) for k, x in v.items()}}
        print("  %-5s buffer B1 %4.1f %%  B- %4.1f %%   Sortino osnova %.2f  B1 %.2f  B- %.2f"
              % (s, bb, bm, v["osnova"], v["B1 po volatilnosti"], v["B- obrnjeno"]))

    print("\nMEHANIZEM: izstopi, po katerih lean v 30 dneh kupi drazje (vsi alti skupaj)")
    out["mehanizem"] = {}
    for k in IMENA:
        n = sum(ponovni_visje(RUN[k][s])[0] for s in ALTI)
        m = sum(ponovni_visje(RUN[k][s])[1] for s in ALTI)
        out["mehanizem"][k] = [n, m]
        print("  %-20s %2d od %2d izstopov (%.0f %%)" % (k, n, m, 100 * n / max(m, 1)))
    meh = (out["mehanizem"]["B1 po volatilnosti"][0] / max(out["mehanizem"]["B1 po volatilnosti"][1], 1)
           < out["mehanizem"]["osnova"][0] / max(out["mehanizem"]["osnova"][1], 1))

    print("\nKNJIGA (normalizirane utezi, mesecno uravnavanje)")
    idx = osn_btc.index
    RET = {s: C[s]["close"].pct_change() for s in SREDSTVA}
    K = {}
    for k in IMENA:
        POS = {s: position(RUN[k][s], cfg).astype(float) for s in SREDSTVA}
        K[k] = knjiga(idx, POS, RET, UTEZI, True)[0]
        print("  %-20s Sortino %.2f  MaxDD %5.1f %%" % (k, sortino(K[k]), maxdd(K[k])))
    out["knjiga"] = {}
    for k in IMENA[1:]:
        sd = sodba(K["osnova"], K[k], idx, faze)
        sd["dSortino"] = round(sortino(K[k]) - sortino(K["osnova"]), 2)
        out["knjiga"][k] = sd
        izpis_sodbe(k, sd)
        print("    %-20s dSortino %+.2f %s" % ("", sd["dSortino"],
              "(v sumu, |d| < 0,4)" if abs(sd["dSortino"]) < 0.4 else ""))

    sp = out["knjiga"]["B1 po volatilnosti"]["vsi"] and meh \
        and not out["knjiga"]["B- obrnjeno"]["vsi"]
    out["sodba"] = {"knjiga_C1_C4": out["knjiga"]["B1 po volatilnosti"]["vsi"],
                    "mehanizem": meh, "B-_ne_zmaga": not out["knjiga"]["B- obrnjeno"]["vsi"],
                    "sprejet": sp}
    print("\nSKUPNA SODBA B1: knjiga C1-C4 %s, mehanizem %s, B- ne zmaga %s  ->  %s" % (
        *["DA" if v else "ne" for v in (out["sodba"]["knjiga_C1_C4"], meh,
                                         out["sodba"]["B-_ne_zmaga"])],
        "SPREJET" if sp else "zavrnjen"))

    pot = ROOT / "testing" / "data" / "buffer_volatilnost.json"
    pot.write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str),
                   encoding="utf-8")
    print("Zapisano: %s" % pot.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
