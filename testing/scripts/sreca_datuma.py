"""Odprava srece pri datumu, brez izgube binarnosti.

    python testing/scripts/sreca_datuma.py [P1|P2|oba]

IZHODISCE

Faberjevo pravilo se odloci enkrat na mesec. Kateri dan v mesecu, ni doloceno.
Na P1 se donos giblje med 4,84 % in 8,19 % na leto zgolj glede na to, kateri od
21 moznih dni izberes -- razpon 3,35 odstotne tocke, v katerem ni nobene
vescine. Newfound to imenuje `rebalance timing luck` in na Faberjevi strategiji
dokumentira do 220 bazicnih tock.

Njihova resitev je razdelitev na trance, a ta da delne pozicije (`3 od 4 transe
pravijo noter` = 75 % sklada). To pokvari binarnost, ki je zahtevana. Tu so
zato preizkusene resitve, ki datumsko sreco odpravijo in izhod pustijo binaren.

════════════════════════════════════════════════════════════════════════════
VNAPREJ ZAPISANO MERILO USPEHA  --  zapisano PRED prvim zagonom

Ta razdelek je tu zato, da rezultata ni mogoce izbrati potem, ko je viden.
Brez tega bi bila celotna vaja le se en krog prilagajanja preteklosti.

  1  POSTENA IZHODISCNA STEVILKA NI 8,48 %, AMPAK MEDIANA.
     Vnaprej ni mogoce vedeti, kateri dan v mesecu bo srecen. Zato je posteno
     pricakovanje osnovnega pravila MEDIANA cez vseh 21 dni, ne vrednost, ki
     jo da konvencija `zadnji dan v mesecu`. Vsak popravek se meri proti tej
     mediani.

  2  MERILO NI DONOS, AMPAK ODPRAVA RAZPONA.
     Popravek je uspesen, ce datumsko sreco odpravi (razpon -> 0) IN ce se
     njegov rezultat ne uvrsti pod mediano osnovnega pravila. Merilo je
     stabilnost; donosa ni mogoce napihniti z izbiro srecne poti.

  3  KJE V PORAZDELITVI PADE.
     Za vsak popravek se poroca, na katerem percentilu porazdelitve osnovnega
     pravila pristane. Pod 50 = skodljiv. Okoli 50 = odstrani tveganje, donosa
     ne doda (ze to je uspeh). Nad 50 = doda tudi nekaj donosa.

  4  NOBENEGA NOVEGA PARAMETRA, IZBRANEGA NA NASIH PODATKIH.
     Dolzina 10 mesecev je Faberjeva. Pas 1 % je iz prejsnje mreze. Glasovanje
     uporablja VSEH 21 mrez -- najvecjo mozno mnozico, torej ni izbrana.
     Dnevna razlicica uporablja 210 trgovalnih dni = 10 mesecev x 21.

  5  P2 JE KONTROLA.
     Za P2 je ze ugotovljeno, da pravilo ne prinese nicesar. Ce se kaksen
     popravek tam nenadoma izkaze za odlicnega, je to znak, da merim sum, in
     ne odkritja.

  6  POPRAVEK ZA STEVILO POSKUSOV SE SESTEVA.
     PBO in deflated Sharpe stejeta vse tu preizkusene razlicice skupaj s
     30 iz prejsnjega kroga.
════════════════════════════════════════════════════════════════════════════

PREIZKUSENI POPRAVKI

  C0  osnova: Faber SMA10 na mesecni mrezi          (21 razlicic, ena na dan)
  C1  glasovanje 21 mrez, vecina odloci             (deterministicen, binaren)
  C2  dnevno na 210-dnevnem povprecju, pas 1 %      (mesecne mreze sploh ni)
  C3  dnevno na 210-dnevnem povprecju, brez pasu    (za izolacijo prispevka pasu)
  C4  mesecno, a cena = povprecje cen tega meseca   (21 razlicic, ena na dan)

C1, C2 in C3 datumsko sreco odpravijo PO KONSTRUKCIJI: nimajo mesecne mreze,
ki bi jo bilo treba izbrati. C4 jo le zmanjsa, zato se meri z razponom.

Provizija 0,20 % na posel, brez davka, gotovina po meri ECB. Portfelja loceno.
Izhod: testing/data/etf_sreca_datuma.json
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from scipy import stats as sps

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "etf"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from shared.etf_data import cash_rate, load                      # noqa: E402
from shared.etf_universe import PORTFOLIOS                       # noqa: E402
from testing.scripts import etf_wfo as W                         # noqa: E402
from testing.scripts import stats as ST                          # noqa: E402
from testing.scripts.binarno_klasika import (                    # noqa: E402
    KNJIGE, OBRAMBNI, cilj_slot, leta_najslabse, met, odigraj, pbo_cscv,
    sig_sma)
from testing.scripts.faber_koncno import dec_dnevi               # noqa: E402

OUT = ROOT / "testing" / "data" / "etf_sreca_datuma.json"
FEE = 0.20
N_MES = 10          # Faberjevih 10 mesecev
PPM = 21            # trgovalnih dni v mesecu
N_DNI = N_MES * PPM  # 210
PAS = 0.01          # iz prejsnje mreze, ne izbran tu
N_PREJ = 30         # razlicice, preizkusene v prejsnjem krogu


def _cilji(S, utezi, samo_tv):
    return pd.DataFrame(
        [cilj_slot(S.loc[t], None, utezi, samo_tvegane=samo_tv) for t in S.index],
        index=S.index).fillna(0.0)


def c0(px, k, pas=0.0):
    """Faber na mesecni mrezi z zamikom k. Vrne (signal po dnevih, prvi veljaven)."""
    dec = dec_dnevi(px.index, k)
    pm = px.loc[dec]
    S = sig_sma(pm, N_MES, pas)
    prva = pm.rolling(N_MES).mean().dropna(how="all").index
    return S, (prva[0] if len(prva) else dec[0])


def c4(px, k):
    """Kot C0, a cena obdobja je POVPRECJE dnevnih cen v njem, ne en sam dan.

    Zakamulin opozarja, da je vsak signal iz ene same cene obcutljiv na to,
    katero ceno vzames. Povprecje obdobja to obcutljivost odpravi, ne da bi
    spremenilo naravo pravila.
    """
    idx = px.index
    dec = dec_dnevi(idx, k)
    grp = pd.Series(np.searchsorted(dec, idx, side="left"), index=idx)
    pa = px.groupby(grp).mean()
    n = min(len(pa), len(dec))
    pa = pa.iloc[:n]
    pa.index = dec[:n]
    S = sig_sma(pa, N_MES, 0.0)
    prva = pa.rolling(N_MES).mean().dropna(how="all").index
    return S, (prva[0] if len(prva) else dec[0])


def c1(px, pasovi=(0.0,)):
    """Glasovanje vseh 21 mesecnih mrez; drzi, ce vec kot polovica pravi noter.

    Izhod je binaren: sklad je ali cel notri ali cel v gotovini. Datumske srece
    ni, ker ni izbranega dneva -- uporabljeni so vsi.
    """
    idx = px.index
    glasovi, prve = [], []
    for k in range(PPM):
        S, prva = c0(px, k, pasovi[0])
        glasovi.append(S.reindex(idx).ffill().fillna(False).astype(float))
        prve.append(prva)
    V = sum(glasovi) / len(glasovi)
    return (V > 0.5), max(prve)


def c23(px, pas):
    """Dnevno odlocanje na 210-dnevnem povprecju. Mesecne mreze sploh ni."""
    S = sig_sma(px, N_DNI, pas)
    return S, px.index[N_DNI]


def main() -> int:
    kaj = sys.argv[1] if len(sys.argv) > 1 else "oba"
    keys = sorted({k for v in KNJIGE.values() for k in v})
    px_all = pd.DataFrame({k: load(k, start="1999-01-01", backfill=True)["close"]
                           for k in keys})
    cr = cash_rate()
    res = {}
    if OUT.exists():
        try:
            res = json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:
            res = {}
    res.update(dict(generated=str(pd.Timestamp.utcnow()), fee=FEE,
                    brez_davka=True, portfelja_locena=True,
                    merilo="mediana C0 cez 21 dni; popravek mora odpraviti razpon "
                           "in ne pasti pod to mediano"))

    for knjiga in (["P1", "P2"] if kaj == "oba" else [kaj]):
        cols = KNJIGE[knjiga]
        px = px_all[cols].dropna()
        idx = px.index
        ppy = len(idx) / ((idx[-1] - idx[0]).days / 365.25)
        cash_d = (cr.reindex(idx.union(cr.index)).ffill().reindex(idx).fillna(0.0)
                  / 100.0 / ppy)
        cash_s = pd.Series(np.asarray(cash_d), index=idx)
        utezi = {c: w for c, w in PORTFOLIOS[knjiga].items() if c in cols}
        vs = sum(utezi.values())
        utezi = {c: w / vs for c, w in utezi.items()}
        samo_tv = any(c in cols for c in OBRAMBNI)   # P2: obveznic ne timaj

        # ── zberi vse signale in skupen zacetek ──────────────────────────────
        sig, prve = {}, []
        for k in range(PPM):
            S, p0 = c0(px, k)
            sig[f"C0 dan {k:02d}"] = S
            prve.append(p0)
        for k in range(PPM):
            S, p0 = c4(px, k)
            sig[f"C4 dan {k:02d}"] = S
            prve.append(p0)
        for ime, (S, p0) in {"C1 glasovanje 21 mrez": c1(px),
                             "C2 dnevno SMA210 pas 1 %": c23(px, PAS),
                             "C3 dnevno SMA210 brez pasu": c23(px, 0.0)}.items():
            sig[ime] = S
            prve.append(p0)
        zac = max(prve)
        m = idx >= zac
        let = float(m.sum() / ppy)

        bh = (px.pct_change().fillna(0.0) * pd.Series(utezi)).sum(axis=1)[m]
        mb = met(bh, ppy)

        print("=" * 122)
        print(f"{knjiga}   {pd.Timestamp(zac).date()} -> {idx[-1].date()}  "
              f"({let:.1f} let)   {'obveznic ne timamo' if samo_tv else 'vsi skladi se timajo'}")
        print("=" * 122)
        print(f"{knjiga} kupi in drzi: CAGR {mb['cagr']:.2f} %, Sharpe {mb['sharpe']:.2f}, "
              f"Sortino {mb['sortino']:.2f}, MaxDD {mb['maxdd']:.1f} %, "
              f"10k -> {mb['konec']:,.0f} EUR")
        print()

        vrst, serije = {}, {}
        for ime, S in sig.items():
            Sd = S.reindex(idx).ffill().fillna(False).astype(bool)
            r, Wt, dw, vt = odigraj(px, cash_d, _cilji(Sd, utezi, samo_tv), fee=FEE)
            rr = r[m]
            mm = met(rr, ppy)
            serije[ime] = rr
            vrst[ime] = dict(**mm, v_trgu=float(vt[m].mean()) * 100,
                             poslov_na_leto=float((dw[m] > 1e-9).sum()) / let,
                             obrat=float(dw[m].sum()) / let * 100)

        # ── porazdelitev osnovnega pravila cez 21 dni ────────────────────────
        def dist(pref):
            ks = [k for k in vrst if k.startswith(pref)]
            return {mera: np.array([vrst[k][mera] for k in ks])
                    for mera in ("cagr", "sharpe", "sortino", "maxdd",
                                 "poslov_na_leto")}

        d0, d4 = dist("C0"), dist("C4")
        print("POROZDELITEV CEZ VSEH 21 MOZNIH DNI ODLOCANJA")
        print(f"{'':<30}{'min':>8}{'mediana':>10}{'max':>8}{'razpon':>9}")
        for ime, d in (("C0 Faber, ena cena", d0), ("C4 Faber, cena = povprecje", d4)):
            for mera in ("cagr", "sortino", "maxdd"):
                v = d[mera]
                print(f"{(ime + '  ' + mera):<30}{v.min():8.2f}{np.median(v):10.2f}"
                      f"{v.max():8.2f}{v.max()-v.min():9.2f}")
        kon = "C0 dan 20"
        print(f"   (konvencija `zadnji dan v mesecu` da CAGR "
              f"{vrst[kon]['cagr']:.2f} %, percentil "
              f"{(d0['cagr'] < vrst[kon]['cagr']).mean()*100:.0f})")
        print()

        # ── popravki proti mediani osnove ────────────────────────────────────
        med_c, med_s, med_d = (np.median(d0["cagr"]), np.median(d0["sortino"]),
                               np.median(d0["maxdd"]))
        print("POPRAVKI, MERJENI PROTI MEDIANI OSNOVE  "
              f"(CAGR {med_c:.2f} %, Sortino {med_s:.2f}, MaxDD {med_d:.1f} %)")
        print(f"{'popravek':<30}{'CAGR':>7}{'Sharpe':>8}{'Sortino':>8}{'MaxDD':>8}"
              f"{'poslov/l':>10}{'v trgu':>8}{'perc.':>7}{'razpon':>8}{'10k ->':>11}")
        sodba = {}
        for ime in ("C1 glasovanje 21 mrez", "C2 dnevno SMA210 pas 1 %",
                    "C3 dnevno SMA210 brez pasu"):
            v = vrst[ime]
            perc = (d0["cagr"] < v["cagr"]).mean() * 100
            print(f"{ime:<30}{v['cagr']:6.2f} {v['sharpe']:8.2f}{v['sortino']:8.2f}"
                  f"{v['maxdd']:7.1f} {v['poslov_na_leto']:9.1f}"
                  f"{v['v_trgu']:7.0f} %{perc:7.0f}{0.0:8.2f}{v['konec']:11,.0f}")
            sodba[ime] = dict(**v, percentil=float(perc), razpon=0.0,
                              nad_mediano=bool(v["sortino"] >= med_s))
        # C4 je se vedno porazdelitev; poroca se njena mediana
        i_med = int(np.argsort(d4["cagr"])[len(d4["cagr"]) // 2])
        ime4 = sorted([k for k in vrst if k.startswith("C4")])[i_med]
        v4 = vrst[ime4]
        perc4 = (d0["cagr"] < np.median(d4["cagr"])).mean() * 100
        print(f"{'C4 cena=povprecje (mediana)':<30}{np.median(d4['cagr']):6.2f} "
              f"{v4['sharpe']:8.2f}{np.median(d4['sortino']):8.2f}"
              f"{np.median(d4['maxdd']):7.1f} {np.median(d4['poslov_na_leto']):9.1f}"
              f"{v4['v_trgu']:7.0f} %{perc4:7.0f}"
              f"{d4['cagr'].max()-d4['cagr'].min():8.2f}{v4['konec']:11,.0f}")
        sodba["C4 cena=povprecje"] = dict(
            cagr=float(np.median(d4["cagr"])), sortino=float(np.median(d4["sortino"])),
            maxdd=float(np.median(d4["maxdd"])), percentil=float(perc4),
            razpon=float(d4["cagr"].max() - d4["cagr"].min()),
            nad_mediano=bool(np.median(d4["sortino"]) >= med_s))
        print()

        # ── vnaprejsnje merilo, izrecno ovrednoteno ──────────────────────────
        print("SODBA PO VNAPREJ ZAPISANEM MERILU")
        razpon0 = d0["cagr"].max() - d0["cagr"].min()
        for ime, s in sodba.items():
            odpr = s["razpon"] <= razpon0 * 0.5
            ok = odpr and s["nad_mediano"]
            print(f"   {ime:<30} razpon {s['razpon']:.2f} pp "
                  f"({'odpravljen' if odpr else 'NI odpravljen'}), "
                  f"Sortino {s['sortino']:.2f} vs mediana {med_s:.2f} "
                  f"({'nad' if s['nad_mediano'] else 'POD'})  ->  "
                  f"{'USPESEN' if ok else 'zavrnjen'}")
            s["uspesen"] = bool(ok)
        print()

        # ── glavna ovira + popravek za stevilo poskusov za najboljsega ───────
        kand = [k for k, s in sodba.items() if s["uspesen"]]
        if not kand:
            kand = list(sodba)
        naj = max(kand, key=lambda k: sodba[k]["sortino"])
        naj_ime = ime4 if naj.startswith("C4") else naj
        s = serije[naj_ime]
        izp = vrst[naj_ime]["v_trgu"] / 100.0
        stat = bh * izp + (1 - izp) * cash_s[m]
        ms = met(stat, ppy)
        ci = W.paired_diff_ci(pd.Series(np.asarray(s), index=s.index),
                              pd.Series(np.asarray(stat), index=s.index),
                              n_boot=2000, td=int(round(ppy)))
        print(f"IZBRANI POPRAVEK: {naj}")
        print(f"   glavna ovira -- staticnih {izp*100:.0f} % knjige: "
              f"CAGR {ms['cagr']:.2f} %, Sharpe {ms['sharpe']:.2f}, "
              f"Sortino {ms['sortino']:.2f}, MaxDD {ms['maxdd']:.1f} %")
        print(f"     d Sortino {ci['point']:+.2f} [{ci['lo']:+.2f}, {ci['hi']:+.2f}]"
              f"  P(boljsi) {ci['p_better']*100:.0f} %  -> {ci['verdict']}")
        okna = {}
        for sp in ("design", "validation", "holdout"):
            x = W.split(pd.Series(np.asarray(s), index=s.index), sp)
            okna[sp] = met(x, ppy) if len(x) > 60 else None
        print("   po oknih (Sharpe): " + "  ".join(
            f"{sp} {okna[sp]['sharpe']:.2f}" if okna[sp] else f"{sp} -" for sp in okna))

        imena = list(vrst)
        L = min(len(serije[k]) for k in imena)
        M = np.array([np.asarray(serije[k])[-L:] for k in imena])
        pb = pbo_cscv(M, imena, ppy=ppy)
        sr_bar = np.array([np.asarray(serije[k]).mean() / np.asarray(serije[k]).std()
                           for k in imena])
        n_tot = len(imena) + N_PREJ
        ds = ST.deflated_sharpe(np.asarray(s), n_trials=n_tot,
                                trials_sharpe_std=float(np.std(sr_bar)), td=ppy)
        sh = met(s, ppy)["sharpe"]
        t = sh * np.sqrt(len(s) / ppy)
        p_b = min(1.0, 2 * (1 - sps.norm.cdf(abs(t))) * n_tot)
        t_b = sps.norm.ppf(1 - p_b / 2) if p_b < 1 else 0.0
        odb = 1 - (t_b / t) if t > 0 else 1.0
        print(f"   PBO {pb['pbo']*100:.1f} %   deflated Sharpe {ds['dsr']:.3f} "
              f"(prag 0,95, {n_tot} poskusov s prejsnjim krogom)")
        print(f"   Harvey-Liu: t = {t:.2f} -> po Bonferroniju {t_b:.2f}, "
              f"odbitek {odb*100:.0f} %  ->  Sharpe {sh*(1-odb):.2f}")
        print()

        res[knjiga] = dict(
            okno=[str(pd.Timestamp(zac).date()), str(idx[-1].date())], let=let,
            kupi_in_drzi=mb, konvencija=vrst[kon],
            porazdelitev_C0={k: dict(min=float(v.min()), mediana=float(np.median(v)),
                                     max=float(v.max()),
                                     razpon=float(v.max() - v.min()))
                             for k, v in d0.items()},
            porazdelitev_C4={k: dict(min=float(v.min()), mediana=float(np.median(v)),
                                     max=float(v.max()),
                                     razpon=float(v.max() - v.min()))
                             for k, v in d4.items()},
            popravki=sodba, izbrani=naj, metrike=vrst[naj_ime], staticni=ms,
            vs_static={k: (float(x) if isinstance(x, (int, float)) else x)
                       for k, x in ci.items()},
            okna={k: (x if x is None else {a: float(b) for a, b in x.items()})
                  for k, x in okna.items()},
            pbo=pb, deflated={k: float(v) for k, v in ds.items()},
            haircut=float(odb), sharpe_po_odbitku=float(sh * (1 - odb)),
            vse_vrstice=vrst)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    print(f"zapisano: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
