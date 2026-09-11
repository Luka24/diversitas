"""Binarna pravila: za vsak ETF posebej -- ali noter ali v gotovino.

    python testing/scripts/binarno_klasika.py [P1|P2|oba]

Nic uteznega, nic delnih premikov. Vsak sklad je ali cel notri ali cel v
gotovini. To je tudi tisto, kar je za ETF-je klasika: Faberjev model iz 2007
dela natanko to.

PRAVILA, VSA IZ OBJAVLJENIH VIROV, NOBENO IZBRANO NA NASIH PODATKIH

  F10   Faber (2007): mesecni zakljucek > 10-mesecno drseco povprecje -> noter
  F10b  isto z 1 % pasom (vstop nad SMA*1,01, izstop pod SMA*0,99)
  TSM   Moskowitz-Ooi-Pedersen (2012): donos zadnjih 12 mesecev > 0 -> noter
  ABS   Antonacci: donos zadnjih 12 mesecev > donos gotovine -> noter
  ENS   Newfound: vecina glasov SMA 6/8/10/12 mesecev -> noter

RAZPOREDITEV, KO JE SIGNAL PRIZGAN

  slot  sklad obdrzi svojo utez iz knjige; ce je signal ugasnjen, gre TA utez
        v gotovino. Sestava knjige se ne spremeni. To je Faberjev nacin.
  gem   Antonacci: med vklopljenimi vzemi ENEGA najmocnejsega, 100 % vanj;
        ce ni nobenega vklopljenega, 100 % gotovina.
  top2  enako, a dva najmocnejsa po 50 %.

Vsa pravila se odlocajo na zadnji trgovalni dan v mesecu, iz podatkov do
vkljucno tega dne, in veljajo od naslednjega dne. Vsa se zacnejo na isti dan,
ko ima najpocasnejsi signal (12 mesecev) prve podatke -- da ogrevalno obdobje
nobenemu ne priprti prednosti.

Provizija 0,20 % na posel, brez davka, gotovina po dejanski meri ECB.
Izhod: testing/data/etf_binarno_klasika.json
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "etf"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import itertools                                                 # noqa: E402

from shared.etf_data import cash_rate, load                      # noqa: E402
from shared.etf_universe import PORTFOLIOS                       # noqa: E402
from testing.scripts import etf_wfo as W                         # noqa: E402
from testing.scripts import stats as ST                          # noqa: E402

OUT = ROOT / "testing" / "data" / "etf_binarno_klasika.json"
FEE = 0.20

KNJIGE = {
    "P1": ["World", "EM", "SmallCap", "Quality"],
    "P2": ["World", "EM", "SmallCap", "Quality", "GlobAgg", "InflLink",
           "Gold", "Commod"],
}


# -- mere ---------------------------------------------------------------------

def met(r, ppy):
    r = np.asarray(r, float)
    eq = np.cumprod(1.0 + r)
    dd = eq / np.maximum.accumulate(eq) - 1.0
    v = r.std() * np.sqrt(ppy)
    dn = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(ppy)
    c = eq[-1] ** (ppy / len(r)) - 1.0
    peak, worst, cur = eq[0], 0, 0
    for x in eq:
        if x >= peak:
            peak, cur = x, 0
        else:
            cur += 1
            worst = max(worst, cur)
    return dict(cagr=c * 100, vol=v * 100,
                sharpe=r.mean() * ppy / v if v > 0 else np.nan,
                sortino=r.mean() * ppy / dn if dn > 0 else np.nan,
                maxdd=dd.min() * 100,
                calmar=c / abs(dd.min()) if dd.min() < 0 else np.nan,
                okrevanje=int(worst), konec=10000.0 * eq[-1])


def pbo_cscv(mat, imena, blokov=10, ppy=252.0):
    """Verjetnost prilagajanja preteklosti (Bailey & Lopez de Prado, CSCV).

    Zgodovino razrezi na `blokov` kosov, vzemi vse mozne polovice, na eni
    izberi najboljso nastavitev po Sortinu in poglej njeno uvrstitev na drugi.
    Delez primerov, ko pade pod mediano, je PBO. Nizko je dobro.
    """
    def so(x):
        x = np.asarray(x, float)
        dn = np.sqrt(np.mean(np.minimum(x, 0.0) ** 2))
        return x.mean() / dn * np.sqrt(ppy) if dn > 0 else np.nan

    n = mat.shape[1]
    kosi = np.array_split(np.arange(n), blokov)
    pod, pot = 0, 0
    for sel in itertools.combinations(range(blokov), blokov // 2):
        i_is = np.concatenate([kosi[i] for i in sel])
        i_oos = np.concatenate([kosi[i] for i in range(blokov) if i not in sel])
        s_is = np.array([so(m[i_is]) for m in mat])
        s_oos = np.array([so(m[i_oos]) for m in mat])
        if not (np.isfinite(s_is).all() and np.isfinite(s_oos).all()):
            continue
        k = int(np.argmax(s_is))
        rang = float((s_oos < s_oos[k]).sum()) / (len(imena) - 1)
        pod += int(rang < 0.5)
        pot += 1
    return dict(pbo=round(pod / pot, 3) if pot else np.nan, poti=pot)


def leta_najslabse(r):
    s = pd.Series(np.asarray(r, float), index=r.index)
    g = (1 + s).groupby(s.index.year).prod() - 1
    return float(g.min() * 100), int(g.idxmin())


# -- signali, vsi na mesecnih zakljuckih --------------------------------------

def sig_sma(pm, n=10, pas=0.0):
    """Cena nad drsecim povprecjem. `pas` je Wildersov nacin proti zibanju:
    vstop sele nad SMA*(1+pas), izstop sele pod SMA*(1-pas). Ker je odlocitev
    odvisna od prejsnjega stanja, gre po vrsti in ne vektorsko."""
    ma = pm.rolling(n).mean()
    if pas <= 0:
        return (pm > ma).where(ma.notna(), other=False)
    out = pd.DataFrame(False, index=pm.index, columns=pm.columns)
    drzi = {c: False for c in pm.columns}
    for t in pm.index:
        m, p = ma.loc[t], pm.loc[t]
        for c in pm.columns:
            if not np.isfinite(m[c]):
                drzi[c] = False
            elif drzi[c]:
                drzi[c] = bool(p[c] > m[c] * (1.0 - pas))
            else:
                drzi[c] = bool(p[c] > m[c] * (1.0 + pas))
        out.loc[t] = [drzi[c] for c in pm.columns]
    return out


def sig_tsm(pm, n=12):
    r = pm / pm.shift(n) - 1.0
    return (r > 0.0).where(r.notna(), other=False)


def sig_abs(pm, cm, n=12):
    """Antonacci: donos sklada mora prekasati donos gotovine, ne le nicle."""
    r = pm / pm.shift(n) - 1.0
    g = cm.rolling(n).sum()
    d = r.sub(g, axis=0)
    return (d > 0.0).where(r.notna(), other=False)


def sig_ens(pm, dolzine=(6, 8, 10, 12)):
    glasovi = sum(sig_sma(pm, n).astype(float) for n in dolzine)
    return glasovi / len(dolzine) > 0.5


def moc(pm, n=12):
    return pm / pm.shift(n) - 1.0


# -- razporeditev -------------------------------------------------------------

OBRAMBNI = ("GlobAgg", "InflLink")


def cilj_slot(s, m, utezi, samo_tvegane=False):
    """Vsak sklad obdrzi svojo utez iz knjige, ce je signal prizgan; sicer gre
    ta utez v gotovino. Sestava knjige se s tem ne spremeni.

    `samo_tvegane`: obveznic ne casovno izbiraj, ampak jih drzi vedno. Razlog
    ni prilagajanje -- Faber sam opozarja, da je casovno izbiranje smiselno
    tam, kjer je trend, in obveznice v tej knjigi so zavetje, ne stava.
    """
    out = {"CASH": 0.0}
    for c, w in utezi.items():
        if (samo_tvegane and c in OBRAMBNI) or bool(s.get(c, False)):
            out[c] = out.get(c, 0.0) + w
        else:
            out["CASH"] += w
    return out


def cilj_top(s, m, utezi, k=1):
    kand = [c for c in utezi
            if bool(s.get(c, False)) and np.isfinite(m.get(c, np.nan))]
    if not kand:
        return {"CASH": 1.0}
    kand = sorted(kand, key=lambda c: m[c], reverse=True)[:k]
    return {c: 1.0 / len(kand) for c in kand}


CILJI = {"slot": cilj_slot,
         "slotR": lambda s, m, u: cilj_slot(s, m, u, samo_tvegane=True),
         "gem": lambda s, m, u: cilj_top(s, m, u, 1),
         "top2": lambda s, m, u: cilj_top(s, m, u, 2)}


# -- motor --------------------------------------------------------------------

def odigraj(px, cash_d, cilji, fee=FEE):
    """cilji: DataFrame ciljnih utezi po dnevih odlocanja (stolpci + CASH).

    Utezi za dan t so izracunane iz podatkov do t in veljajo od t+1 -- zato
    `shift(1)`. Strosek pade na dan spremembe, sorazmerno s premikom utezi.
    """
    idx = px.index
    R = px.pct_change().fillna(0.0)
    R["CASH"] = np.asarray(cash_d)
    Wt = cilji.reindex(idx).ffill().fillna(0.0)
    for c in Wt.columns:
        if c not in R.columns:
            R[c] = 0.0
    drzi = Wt.shift(1).fillna(0.0)
    port = (drzi * R[Wt.columns]).sum(axis=1)
    dw = Wt.diff().abs().sum(axis=1)
    dw.iloc[0] = float(Wt.iloc[0].abs().sum())
    net = (1.0 + port) * (1.0 - dw * fee / 100.0) - 1.0
    v_trgu = 1.0 - Wt["CASH"] if "CASH" in Wt.columns else pd.Series(1.0, index=idx)
    return net, Wt, dw, v_trgu


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
                    brez_davka=True, portfelja_locena=True))

    for knjiga in (["P1", "P2"] if kaj == "oba" else [kaj]):
        cols = KNJIGE[knjiga]
        px = px_all[cols].dropna()
        idx = px.index
        ppy = len(idx) / ((idx[-1] - idx[0]).days / 365.25)
        cash_d = (cr.reindex(idx.union(cr.index)).ffill().reindex(idx).fillna(0.0)
                  / 100.0 / ppy)
        utezi = {c: w for c, w in PORTFOLIOS[knjiga].items() if c in cols}
        vsota = sum(utezi.values())
        utezi = {c: w / vsota for c, w in utezi.items()}

        pos = pd.Series(np.arange(len(idx)), index=idx)
        dec = idx[pos.groupby([idx.year, idx.month]).max().values]
        pm = px.loc[dec]
        cm_mes = (pd.Series(np.asarray(cash_d), index=idx)
                  .groupby([idx.year, idx.month]).sum())
        cm_mes.index = dec

        SIG = {"F10  Faber 10-mes. SMA": sig_sma(pm, 10),
               "F10b Faber + 1 % pas": sig_sma(pm, 10, pas=0.01),
               "TSM  12-mes. donos > 0": sig_tsm(pm, 12),
               "ABS  12-mes. > gotovina": sig_abs(pm, cm_mes, 12),
               "ENS  vecina SMA 6/8/10/12": sig_ens(pm)}
        M = moc(pm, 12)
        prvi = M.dropna(how="all").index
        zac = prvi[0] if len(prvi) else dec[0]

        print("=" * 134)
        print(f"{knjiga}   {idx[0].date()} -> {idx[-1].date()}  "
              f"({len(idx)/ppy:.1f} let, {ppy:.0f} dni/leto)   "
              f"skladi: {', '.join(cols)}   signali od {pd.Timestamp(zac).date()}")
        print("=" * 134)

        m_all = idx >= zac
        bh = (px.pct_change().fillna(0.0) * pd.Series(utezi)).sum(axis=1)[m_all]
        mb = met(bh, ppy)
        nl_y, nl_l = leta_najslabse(bh)
        head = (f"{'kandidat':<38}{'CAGR':>7}{'vol':>6}{'Sharpe':>8}{'Sortino':>8}"
                f"{'MaxDD':>8}{'Calmar':>7}{'okrev':>7}{'v trgu':>8}{'poslov/l':>9}"
                f"{'najslabse leto':>17}{'10k ->':>11}")
        print(head)
        print(f"{knjiga + ' kupi in drzi':<38}{mb['cagr']:6.2f} {mb['vol']:5.1f}"
              f"{mb['sharpe']:8.2f}{mb['sortino']:8.2f}{mb['maxdd']:7.1f} "
              f"{mb['calmar']:6.2f}{mb['okrevanje']:7d}{100:7.0f} %{0:9.1f}"
              f"{nl_y:12.1f} % {nl_l:4d}{mb['konec']:11,.0f}")
        print("-" * 134)

        vrst, serije = [], {"kupi in drzi": bh}
        nacini = ("slot", "gem", "top2")
        if any(c in cols for c in OBRAMBNI):
            nacini = ("slot", "slotR", "gem", "top2")
        for nacin in nacini:
            for ime, S in SIG.items():
                Sd = S.reindex(dec)
                cilji = pd.DataFrame(
                    [CILJI[nacin](Sd.loc[t], M.loc[t], utezi) for t in dec],
                    index=dec).fillna(0.0)
                r, Wt, dw, vt = odigraj(px, cash_d, cilji)
                mm_ = r.index >= zac
                mm = met(r[mm_], ppy)
                nly, nll = leta_najslabse(r[mm_])
                let = mm_.sum() / ppy
                poslov = float((dw[mm_] > 1e-9).sum()) / let
                obrat = float(dw[mm_].sum()) / let * 100
                kljuc = f"{nacin:<5}{ime}"
                serije[kljuc] = r[mm_]
                vrst.append(dict(nacin=nacin, pravilo=ime, **mm,
                                 v_trgu=float(vt[mm_].mean()) * 100,
                                 poslov_na_leto=poslov, obrat=obrat,
                                 najslabse_leto=nly, najslabse_l=nll))
                print(f"{kljuc:<38}{mm['cagr']:6.2f} {mm['vol']:5.1f}"
                      f"{mm['sharpe']:8.2f}{mm['sortino']:8.2f}{mm['maxdd']:7.1f} "
                      f"{mm['calmar']:6.2f}{mm['okrevanje']:7d}"
                      f"{float(vt[mm_].mean())*100:7.0f} %{poslov:9.1f}"
                      f"{nly:12.1f} % {nll:4d}{mm['konec']:11,.0f}")
            print("-" * 134)

        # glavna ovira: isti povprecni delez v trgu, brez vsakega odlocanja
        print("GLAVNA OVIRA -- proti staticnemu delezu z ISTO povprecno izpostavljenostjo")
        ovire = {}
        for v in sorted(vrst, key=lambda x: -(x["sortino"] if np.isfinite(x["sortino"]) else -9))[:5]:
            kljuc = f"{v['nacin']:<5}{v['pravilo']}"
            s = serije[kljuc]
            izp = v["v_trgu"] / 100.0
            stat = bh * izp + (1 - izp) * pd.Series(np.asarray(cash_d), index=idx)[m_all]
            ms = met(stat, ppy)
            ci = W.paired_diff_ci(pd.Series(np.asarray(s), index=s.index),
                                  pd.Series(np.asarray(stat), index=s.index),
                                  n_boot=1500, td=int(round(ppy)))
            print(f"   {kljuc:<38} proti staticnim {izp*100:3.0f} % "
                  f"(CAGR {ms['cagr']:5.2f} %, Sh {ms['sharpe']:.2f}, "
                  f"So {ms['sortino']:.2f}, DD {ms['maxdd']:6.1f} %):  "
                  f"d Sortino {ci['point']:+.2f} [{ci['lo']:+.2f}, {ci['hi']:+.2f}]"
                  f"  -> {ci['verdict']}")
            ovire[kljuc] = dict(izpostavljenost=izp * 100, staticni=ms,
                                point=float(ci["point"]), lo=float(ci["lo"]),
                                hi=float(ci["hi"]), verdict=ci["verdict"])

        # zascita pred prilagajanjem preteklosti, cez VSE preizkusene nastavitve
        imena = [f"{v['nacin']:<5}{v['pravilo']}" for v in vrst]
        L = min(len(serije[k]) for k in imena)
        mat = np.array([np.asarray(serije[k])[-L:] for k in imena])
        pb = pbo_cscv(mat, imena, ppy=ppy)
        sr_vsi = np.array([np.asarray(serije[k]).mean() / np.asarray(serije[k]).std()
                           for k in imena])
        naj_k = max(imena, key=lambda k: met(serije[k], ppy)["sortino"])
        ds = ST.deflated_sharpe(np.asarray(serije[naj_k]), n_trials=len(imena),
                                trials_sharpe_std=float(np.std(sr_vsi)), td=ppy)
        print(f"ZASCITA PRED PRILAGAJANJEM ({len(imena)} preizkusenih nastavitev)")
        print(f"   PBO (verjetnost prilagajanja): {pb['pbo']*100:.1f} %   "
              f"[{pb['poti']} poti]")
        print(f"   najboljsi po Sortinu: {naj_k}")
        print(f"   Sharpe {ds['sr_ann']:.3f}, prag iz {len(imena)} poskusov "
              f"{ds['sr0_ann']:.3f}, deflated Sharpe {ds['dsr']:.3f} (prag 0,95)")
        print()

        res[knjiga] = dict(okno=[str(pd.Timestamp(zac).date()), str(idx[-1].date())],
                           let=float(m_all.sum() / ppy), ppy=ppy,
                           kupi_in_drzi=mb, vrstice=vrst, ovire=ovire,
                           pbo=pb, naj=naj_k,
                           deflated={k: float(v) for k, v in ds.items()})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    print(f"zapisano: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
