"""Dokoncna preverba binarnega pravila, LOCENO za vsak portfelj.

    python testing/scripts/faber_koncno.py [P1|P2|oba]

Pravilo je Faberjevo (2007) in binarno: vsak sklad zase, ali cel notri pri
svoji utezi iz knjige, ali cel v gotovini. Nic uteznega, nic delnih premikov.

KAJ SE TU PREVERJA -- sest zascit, vsaka proti drugi vrsti samoprevare

  A  MREZA, ne ena nastavitev. Dolzina povprecja 6/8/10/12/14 mesecev krat
     pas 0 % / 1 %. Zakamulin je na 155 letih pokazal, da ene same najboljse
     dolzine ni mogoce zanesljivo najti; zato se ne isce najboljse, ampak
     pogleda, ali je celo obmocje uporabno.

  B  PLATO, ne vrh. Izbere se nastavitev, katere sosedje dajejo podobne
     rezultate. Ce je nastavitev dobra samo zato, ker so njeni sosedje slabi,
     je to podpis prilagajanja sumu.

  C  GLAVNA OVIRA. Vsaka strategija, ki je del casa zunaj trga, izgleda
     mirnejsa ze zato. Zato se primerja s tem, da bi preprosto imeli stalno
     manj denarja v knjigi, z ISTO povprecno izpostavljenostjo.

  D  SRECA PRI DATUMU. Faberjevo pravilo se odloca enkrat na mesec; Newfound
     je pokazal do 220 bazicnih tock razlike v CAGR samo glede na to, kateri
     dan v mesecu izberes. Tu se odigra vseh 21 moznih dni.

  E  PO OKNIH. Zasnova / validacija / hold-out, da se vidi, ali rezultat
     stoji na enem obdobju.

  F  POPRAVEK ZA STEVILO POSKUSOV. PBO po CSCV, deflated Sharpe in
     Harvey-Liu odbitek, steti cez VSO mrezo.

Provizija 0,20 % na posel, brez davka, gotovina po dejanski meri ECB.
Portfelja sta obravnavana strogo loceno.

Izhod: testing/data/etf_faber_koncno.json
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

OUT = ROOT / "testing" / "data" / "etf_faber_koncno.json"
FEE = 0.20

DOLZINE = (6, 8, 10, 12, 14)
PASOVI = (0.0, 0.01)


def dec_dnevi(idx, k=None):
    """Dnevi odlocanja. k=None pomeni zadnji trgovalni dan v mesecu (Faberjeva
    konvencija); k=0..20 je k-ti trgovalni dan od zacetka meseca, za merjenje
    srece pri datumu."""
    pos = pd.Series(np.arange(len(idx)), index=idx)
    g = pos.groupby([idx.year, idx.month])
    if k is None:
        return idx[g.max().values]
    sel = g.apply(lambda s: s.iloc[min(k, len(s) - 1)])
    return idx[np.asarray(sel.values)]


def plato(params, values, prostor, k=3):
    """Sredina najboljsega platoja namesto najboljse posamicne nastavitve."""
    kljuci = list(prostor)
    P = np.array([[float(t[c]) for c in kljuci] for t in params], float)
    v = np.array(values, float)
    ok = np.isfinite(v)
    if not ok.any():
        return params[0]
    P, v = P[ok], v[ok]
    tp = [t for t, o in zip(params, ok) if o]
    span = np.array([(prostor[c][1] - prostor[c][0]) or 1.0 for c in kljuci], float)
    lo = np.array([prostor[c][0] for c in kljuci], float)
    Pn = (P - lo) / span
    pl = np.empty(len(v))
    for i in range(len(v)):
        d = np.sqrt(((Pn - Pn[i]) ** 2).sum(axis=1))
        pl[i] = np.nanmean(v[np.argsort(d)[:min(k, len(v))]])
    return dict(tp[int(np.argmax(pl))])


def odigraj_eno(px, cash_d, utezi, n, pas, samo_tvegane, k=None):
    idx = px.index
    dec = dec_dnevi(idx, k)
    pm = px.loc[dec]
    S = sig_sma(pm, n, pas)
    cilji = pd.DataFrame(
        [cilj_slot(S.loc[t], None, utezi, samo_tvegane=samo_tvegane) for t in dec],
        index=dec).fillna(0.0)
    return odigraj(px, cash_d, cilji, fee=FEE)


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
                    mreza=dict(dolzine=list(DOLZINE), pasovi=list(PASOVI))))

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
        ima_obr = any(c in cols for c in OBRAMBNI)
        nacini = [False, True] if ima_obr else [False]

        # skupen zacetek: ko ima najdaljse povprecje prve podatke
        dec0 = dec_dnevi(idx)
        zac = px.loc[dec0].rolling(max(DOLZINE)).mean().dropna(how="all").index
        zac = zac[0] if len(zac) else dec0[0]
        m_all = idx >= zac
        let = float(m_all.sum() / ppy)

        bh = (px.pct_change().fillna(0.0) * pd.Series(utezi)).sum(axis=1)[m_all]
        mb = met(bh, ppy)
        nly_b, nll_b = leta_najslabse(bh)

        print("=" * 128)
        print(f"{knjiga}   {pd.Timestamp(zac).date()} -> {idx[-1].date()}  "
              f"({let:.1f} let)   skladi: {', '.join(cols)}")
        print("=" * 128)
        print(f"{'nastavitev':<28}{'CAGR':>7}{'vol':>6}{'Sharpe':>8}{'Sortino':>8}"
              f"{'MaxDD':>8}{'Calmar':>7}{'v trgu':>8}{'poslov/l':>9}"
              f"{'najslabse leto':>17}{'10k ->':>11}")
        print(f"{knjiga + ' kupi in drzi':<28}{mb['cagr']:6.2f} {mb['vol']:5.1f}"
              f"{mb['sharpe']:8.2f}{mb['sortino']:8.2f}{mb['maxdd']:7.1f} "
              f"{mb['calmar']:6.2f}{100:7.0f} %{0:9.1f}"
              f"{nly_b:12.1f} % {nll_b:4d}{mb['konec']:11,.0f}")

        vrst, serije, params, so_vals = [], {}, [], []
        for samo_tv in nacini:
            tag = "slotR" if samo_tv else "slot "
            print("-" * 128)
            for n in DOLZINE:
                for pas in PASOVI:
                    r, Wt, dw, vt = odigraj_eno(px, cash_d, utezi, n, pas, samo_tv)
                    rr = r[m_all]
                    mm = met(rr, ppy)
                    nly, nll = leta_najslabse(rr)
                    poslov = float((dw[m_all] > 1e-9).sum()) / let
                    ime = f"{tag} SMA{n:>2} pas{pas*100:.0f}%"
                    serije[ime] = rr
                    params.append(dict(n=n, pas=pas * 100, nacin=1.0 if samo_tv else 0.0))
                    so_vals.append(mm["sortino"])
                    vrst.append(dict(ime=ime, nacin=tag.strip(), n=n, pas=pas * 100,
                                     **mm, v_trgu=float(vt[m_all].mean()) * 100,
                                     poslov_na_leto=poslov,
                                     najslabse_leto=nly, najslabse_l=nll))
                    print(f"{ime:<28}{mm['cagr']:6.2f} {mm['vol']:5.1f}"
                          f"{mm['sharpe']:8.2f}{mm['sortino']:8.2f}{mm['maxdd']:7.1f} "
                          f"{mm['calmar']:6.2f}{float(vt[m_all].mean())*100:7.0f} %"
                          f"{poslov:9.1f}{nly:12.1f} % {nll:4d}{mm['konec']:11,.0f}")

        print("-" * 128)
        # ── B: plato znotraj vsakega nacina ──────────────────────────────────
        prostor = dict(n=(min(DOLZINE), max(DOLZINE)), pas=(0.0, 1.0))
        izbrane = {}
        for samo_tv in nacini:
            tag = "slotR" if samo_tv else "slot"
            i_sel = [i for i, v in enumerate(vrst) if v["nacin"] == tag]
            pl = plato([params[i] for i in i_sel], [so_vals[i] for i in i_sel],
                       prostor, k=3)
            vrh = max(i_sel, key=lambda i: so_vals[i])
            ime_pl = next(v["ime"] for i, v in enumerate(vrst)
                          if i in i_sel and v["n"] == pl["n"] and abs(v["pas"] - pl["pas"]) < 1e-9)
            izbrane[tag] = ime_pl
            print(f"PLATO ({tag:<5}): {ime_pl}      vrh mreze: {vrst[vrh]['ime']}"
                  f"      {'ENAKA' if ime_pl == vrst[vrh]['ime'] else 'RAZLICNA'}")

        # ── C, D, E za vsako izbrano ─────────────────────────────────────────
        podrobno = {}
        for tag, ime in izbrane.items():
            v = next(x for x in vrst if x["ime"] == ime)
            s = serije[ime]
            izp = v["v_trgu"] / 100.0
            stat = bh * izp + (1 - izp) * cash_s[m_all]
            ms = met(stat, ppy)
            ci = W.paired_diff_ci(pd.Series(np.asarray(s), index=s.index),
                                  pd.Series(np.asarray(stat), index=s.index),
                                  n_boot=2000, td=int(round(ppy)))
            print()
            print(f"IZBRANA: {ime}")
            print(f"   C glavna ovira -- staticnih {izp*100:.0f} % knjige: "
                  f"CAGR {ms['cagr']:.2f} %, Sharpe {ms['sharpe']:.2f}, "
                  f"Sortino {ms['sortino']:.2f}, MaxDD {ms['maxdd']:.1f} %")
            print(f"     d Sortino {ci['point']:+.2f} [{ci['lo']:+.2f}, {ci['hi']:+.2f}]"
                  f"  P(boljsi) {ci['p_better']*100:.0f} %  -> {ci['verdict']}")

            # D: sreca pri datumu
            luck = []
            for k in range(21):
                rk, _, _, _ = odigraj_eno(px, cash_d, utezi, v["n"], v["pas"] / 100.0,
                                          tag == "slotR", k=k)
                mk = met(rk[m_all], ppy)
                luck.append((mk["cagr"], mk["sortino"], mk["maxdd"]))
            lc = np.array([x[0] for x in luck])
            ls = np.array([x[1] for x in luck])
            ld = np.array([x[2] for x in luck])
            print(f"   D sreca pri datumu (21 moznih dni v mesecu): "
                  f"CAGR {lc.min():.2f}-{lc.max():.2f} % (razpon {lc.max()-lc.min():.2f} pp), "
                  f"Sortino {ls.min():.2f}-{ls.max():.2f}, MaxDD {ld.min():.1f}..{ld.max():.1f} %")

            # E: po oknih
            okna = {}
            for sp in ("design", "validation", "holdout"):
                x = W.split(pd.Series(np.asarray(s), index=s.index), sp)
                okna[sp] = met(x, ppy) if len(x) > 60 else None
            print("   E po oknih (Sharpe / Sortino / CAGR):  " + "   ".join(
                f"{sp}: {okna[sp]['sharpe']:.2f} / {okna[sp]['sortino']:.2f} / "
                f"{okna[sp]['cagr']:.1f} %" if okna[sp] else f"{sp}: -"
                for sp in okna))

            podrobno[tag] = dict(
                izbrana=ime, metrike=v, staticni=ms,
                vs_static={k: (float(x) if isinstance(x, (int, float)) else x)
                           for k, x in ci.items()},
                sreca_datum=dict(cagr_min=float(lc.min()), cagr_max=float(lc.max()),
                                 cagr_razpon=float(lc.max() - lc.min()),
                                 sortino_min=float(ls.min()), sortino_max=float(ls.max()),
                                 maxdd_min=float(ld.min()), maxdd_max=float(ld.max())),
                okna={k: (x if x is None else {a: float(b) for a, b in x.items()})
                      for k, x in okna.items()})

        # ── F: popravek za stevilo poskusov, cez VSO mrezo ───────────────────
        imena = [v["ime"] for v in vrst]
        L = min(len(serije[k]) for k in imena)
        M = np.array([np.asarray(serije[k])[-L:] for k in imena])
        pb = pbo_cscv(M, imena, ppy=ppy)
        sr_bar = np.array([np.asarray(serije[k]).mean() / np.asarray(serije[k]).std()
                           for k in imena])
        naj_tag = "slotR" if ima_obr else "slot"
        r_sel = np.asarray(serije[izbrane[naj_tag]])
        ds = ST.deflated_sharpe(r_sel, n_trials=len(imena),
                                trials_sharpe_std=float(np.std(sr_bar)), td=ppy)
        sh = met(r_sel, ppy)["sharpe"]
        t = sh * np.sqrt(len(r_sel) / ppy)
        p_bonf = min(1.0, 2 * (1 - sps.norm.cdf(abs(t))) * len(imena))
        t_bonf = sps.norm.ppf(1 - p_bonf / 2) if p_bonf < 1 else 0.0
        odbitek = 1 - (t_bonf / t) if t > 0 else 1.0
        print()
        print(f"F POPRAVEK ZA STEVILO POSKUSOV ({len(imena)} nastavitev v mrezi)")
        print(f"   PBO (verjetnost prilagajanja preteklosti): {pb['pbo']*100:.1f} %"
              f"   [{pb['poti']} poti]   -- nizko je dobro")
        print(f"   deflated Sharpe za {izbrane[naj_tag]}: {ds['dsr']:.3f} (prag 0,95),"
              f" prag iz {len(imena)} poskusov {ds['sr0_ann']:.3f}")
        print(f"   Harvey-Liu: t = {t:.2f}, po Bonferroniju t = {t_bonf:.2f}, "
              f"odbitek Sharpa {odbitek*100:.0f} %  ->  {sh*(1-odbitek):.2f}")
        print()

        res[knjiga] = dict(
            okno=[str(pd.Timestamp(zac).date()), str(idx[-1].date())],
            let=let, ppy=ppy, utezi=utezi, kupi_in_drzi=mb,
            najslabse_leto_bh=[nly_b, nll_b], mreza=vrst, izbrane=izbrane,
            podrobno=podrobno, pbo=pb,
            deflated={k: float(v) for k, v in ds.items()},
            haircut=float(odbitek), sharpe_po_odbitku=float(sh * (1 - odbitek)))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    print(f"zapisano: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
