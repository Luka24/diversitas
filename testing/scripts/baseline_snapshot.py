"""Zamrzne trenutno vedenje Lean strategije za BTC in ETH.

Racuna se iz zamrznjenih posnetkov v testing/data/sources/, ne iz omrezja, zato
je izid vedno enak ne glede na to, kdaj se pozene in ali je Binance dosegljiv.

    python testing/scripts/baseline_snapshot.py            zapisi
    python testing/scripts/baseline_snapshot.py --preveri  primerjaj z zapisanim

Nastalo je kot slika stanja pred prepakiranjem za produkcijo, kar je ta skripta
tudi dokazala. Potem je zaostala za modelom in dobila tri napake naenkrat:

  merila je `signal_state` namesto `prev_signal_state`, torej je pozicijo drzala
  ze na zakljucku, ki jo je sele sprozil, kar je enodnevni pogled naprej;

  Sortino je delila s `neg.std()`, standardnim odklonom samo negativnih dni.
  Strategija je zunaj trga vec kot polovico casa in ti dnevi iz tiste podmnozice
  izpadejo, zato je stevilka merila, koliko casa smo zunaj, ne kako hude so
  izgube. Pravilna je koren povprecja kvadratov min(r, 0) cez VSE dni;

  praga 5 % ni poznala, ker ga takrat se ni bilo.

Poleg tega je javljala RAZLIKA in pod tem ni izpisala nicesar, ker je primerjalna
zanka hodila samo po `metrike` in `posli`, polje `config` pa je preskocila. Prav
tam je razlika tudi bila. Preverjanje, ki pove, da se je nekaj spremenilo, ne
zna pa povedati kaj, je slabse od nobenega.

Zdaj racuna po istih funkcijah kot lean/, torej position() in traded_fraction(),
da se glavni repozitorij in predajni ne moreta razhajati.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "lean"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import numpy as np
import pandas as pd

from shared.costs import net_returns
from shared.warmup import trim_warmup
from diversitas.config import LeanConfig
from diversitas.strategy import (S_BULL, position, run_strategy,
                                 traded_fraction)

FEE, PPY = 0.30, 365          # odstotek na stran
OUT_JSON = ROOT / "testing" / "data" / "baseline_lean.json"
OUT_TXT = ROOT / "testing" / "data" / "baseline_lean.txt"
ASSETS = (("BTC", "BTC_binance_warmup.parquet"), ("ETH", "ETH_binance.parquet"))


def trades(df: pd.DataFrame, pos: pd.Series, close: pd.Series) -> list:
    """Vsak posel posebej: vstop, izstop, cena, donos, razlog izstopa."""
    out = []
    chg = pos.diff().fillna(pos.iloc[0])
    starts = list(pos.index[chg > 0])
    ends = list(pos.index[chg < 0])
    if pos.iloc[0] > 0:
        starts.insert(0, pos.index[0])
    for i, s in enumerate(starts):
        e = next((x for x in ends if x > s), None)
        p_in = float(close.loc[s])
        p_out = float(close.loc[e]) if e is not None else float(close.iloc[-1])
        gross = p_out / p_in - 1.0
        net = (1 + gross) * (1 - FEE / 100) ** 2 - 1.0
        row = df.loc[e] if e is not None else df.iloc[-1]
        out.append({
            "st": i + 1,
            "vstop": str(s.date()),
            "izstop": str(e.date()) if e is not None else "odprt",
            "dni": int((e - s).days) if e is not None else int((pos.index[-1] - s).days),
            "cena_vstop": round(p_in, 2),
            "cena_izstop": round(p_out, 2),
            "bruto_pct": round(gross * 100, 2),
            "neto_pct": round(net * 100, 2),
            "razlog": ("pregretje" if bool(row.get("blowoff", False))
                       else "prelom trenda" if e is not None else "se odprt"),
        })
    return out


def metrics(pos: pd.Series, ret: pd.Series, traded: pd.Series,
            bull: pd.Series) -> dict:
    # `traded`, ne sprememba `pos`: s pragom ostanek plava s ceno, plavanje pa
    # ni transakcija in se zanj ne placa provizije.
    r = net_returns(pos, ret, FEE, traded=traded).to_numpy(float)
    eq = np.cumprod(1 + r)
    dd = eq / np.maximum.accumulate(eq) - 1
    down_dev = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(PPY)
    return {
        "dni": int(len(r)),
        "sortino": round(float(r.mean() * PPY / down_dev), 6),
        "cagr_pct": round(float((eq[-1] ** (PPY / len(r)) - 1) * 100), 4),
        "maxdd_pct": round(float(dd.min() * 100), 4),
        "koncni_mnozitelj": round(float(eq[-1]), 6),
        "izpostavljenost_pct": round(float(pos.mean() * 100), 4),
        # Vstope steje SIGNAL. Steti dvige v `pos` je delovalo, dokler se je
        # pozicija premikala samo ob poslu; s pragom se dvigne tudi vsak dan, ko
        # ostanek pridobi, kar ni vstop.
        "poslov": int((bull.diff().fillna(bull.iloc[0]) > 0).sum()),
        "promet": round(float(traded.sum()), 6),
    }


def build() -> dict:
    cfg = LeanConfig()
    snap = {"provizija_na_stran_pct": FEE, "vir": "zamrznjen posnetek Binance",
            "config": {k: v for k, v in vars(cfg).items() if k != "symbol_map"},
            "sredstva": {}}
    for sym, fname in ASSETS:
        raw = pd.read_parquet(ROOT / "testing" / "data" / "sources" / fname)
        df = trim_warmup(run_strategy(raw, config=cfg).df)
        # Dva razlicna niza, namenoma. Seznam poslov tece po SIGNALU, ker
        # strategija odloci na zakljucku in po tej ceni tudi trguje. Niz donosov
        # tece po VCERAJSNJEM signalu, ker kupljeno na zakljucku dneva T zasluzi
        # sele od T+1 naprej. position() poskrbi za oboje, zamik in prag.
        sig = (df["signal_state"] == S_BULL).astype(float)
        pos = position(df, cfg)
        trd = traded_fraction(df, cfg)
        close = raw["close"].reindex(df.index)
        # Donosi na CELI zgodovini, sele nato rezani na okno. Ce se reindeksira
        # prej in odvaja potem, prvi bar okna dobi NaN, ki postane nic, in en
        # resnicen dan donosa odpade.
        ret = raw["close"].pct_change().reindex(df.index).fillna(0.0)
        snap["sredstva"][sym] = {
            "od": str(df.index[0].date()), "do": str(df.index[-1].date()),
            "metrike": metrics(pos, ret, trd,
                               (df["prev_signal_state"] == S_BULL).astype(float)),
            "posli": trades(df, sig, close),
        }
    return snap


def to_text(snap: dict) -> str:
    L = []
    L.append("POSNETEK LEAN STRATEGIJE")
    L.append(f"provizija {snap['provizija_na_stran_pct']} % na stran, {snap['vir']}")
    for sym, d in snap["sredstva"].items():
        m = d["metrike"]
        L.append("")
        L.append("=" * 78)
        L.append(f"{sym}   {d['od']} do {d['do']}   {m['dni']} dni")
        L.append("=" * 78)
        L.append(f"  Sortino {m['sortino']:.6f}    CAGR {m['cagr_pct']:.4f} %"
                 f"    MaxDD {m['maxdd_pct']:.4f} %")
        L.append(f"  koncni mnozitelj {m['koncni_mnozitelj']:.6f}x"
                 f"    v trgu {m['izpostavljenost_pct']:.4f} %"
                 f"    poslov {m['poslov']}")
        L.append("")
        L.append(f"  {'st':>3}  {'vstop':<11}{'izstop':<11}{'dni':>5}"
                 f"{'cena vstop':>12}{'cena izstop':>13}{'bruto':>9}{'neto':>9}  razlog")
        for t in d["posli"]:
            L.append(f"  {t['st']:>3}  {t['vstop']:<11}{t['izstop']:<11}{t['dni']:>5}"
                     f"{t['cena_vstop']:>12,.2f}{t['cena_izstop']:>13,.2f}"
                     f"{t['bruto_pct']:>8.2f}%{t['neto_pct']:>8.2f}%  {t['razlog']}")
    return "\n".join(L) + "\n"


def main() -> int:
    snap = build()
    if "--preveri" in sys.argv:
        if not OUT_JSON.exists():
            print("Posnetka se ni. Pozeni brez --preveri.")
            return 2
        old = json.loads(OUT_JSON.read_text(encoding="utf-8"))
        if old == snap:
            print("Ujema se popolnoma. Vedenje strategije je nespremenjeno.")
            for sym, d in snap["sredstva"].items():
                m = d["metrike"]
                print(f"  {sym}: Sortino {m['sortino']:.6f}, {m['poslov']} poslov, "
                      f"koncni mnozitelj {m['koncni_mnozitelj']:.6f}x")
            return 0
        print("RAZLIKA. Nekaj se je spremenilo:")
        # Tudi nastavitve, ne samo metrike. Ko je bil dodan `bear_alloc_pct`, se
        # je razlikovalo prav to polje, izpis pa je ostal prazen in skripta je
        # javljala razliko, ki je ni znala pokazati.
        for k in ("provizija_na_stran_pct", "vir"):
            if old.get(k) != snap.get(k):
                print(f"  {k}: bilo {old.get(k)}  zdaj {snap.get(k)}")
        for k in sorted(set(old.get("config", {})) | set(snap["config"])):
            a, b = old.get("config", {}).get(k, "<ni ga bilo>"), snap["config"].get(k, "<odstranjeno>")
            if a != b:
                print(f"  config.{k}: bilo {a}  zdaj {b}")
        for sym in snap["sredstva"]:
            a = old["sredstva"].get(sym, {}).get("metrike", {})
            b = snap["sredstva"][sym]["metrike"]
            for k in b:
                if a.get(k) != b[k]:
                    print(f"  {sym}.{k}: bilo {a.get(k)}  zdaj {b[k]}")
            pa = old["sredstva"].get(sym, {}).get("posli", [])
            pb = snap["sredstva"][sym]["posli"]
            if pa != pb:
                print(f"  {sym}: posli se razlikujejo ({len(pa)} proti {len(pb)})")
        return 1

    OUT_JSON.write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")
    OUT_TXT.write_text(to_text(snap), encoding="utf-8")
    print(to_text(snap))
    print(f"zapisano v {OUT_JSON.name} in {OUT_TXT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
