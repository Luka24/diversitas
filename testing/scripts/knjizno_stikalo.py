"""Knjizno stikalo na BTC: podroben test na vec obdobjih.

    python testing/scripts/knjizno_stikalo.py

IDEJA
Ko BTC ni v trendu, gre CELA knjiga ven -- ne le BTC. Uporablja signal, ki v
strategiji ze obstaja, samo na ravni knjige namesto vsakega sredstva posebej.
Nobenega novega parametra ni: ni kaj optimizirati, torej ni kaj pokvariti.

════════════════════════════════════════════════════════════════════════════
VNAPREJ ZAPISANO MERILO  --  zapisano PRED prvim zagonom

Sodi se na CELEM oknu, ne na najboljsem podobdobju. Razdelitev po letih je za
pogled v porazdelitev, ne za izbiro.

  1  Padec mora biti manjsi za vsaj 5 odstotnih tock.
  2  Sortino ne sme pasti pod izhodisce.
  3  Mora prekasati STATICNI DELEZ z isto povprecno izpostavljenostjo
     (tockovno >= 0). To je ovira, ki je v tem projektu ubila vec strategij
     kot vse ostalo skupaj: vsaka strategija, ki je del casa zunaj trga,
     izgleda mirnejsa ze zato, in primerjati jo je treba s tem, da bi
     preprosto imeli manj denarja v knjigi.

Ce pade na katerem koli od treh, je zavrnjena. Vec razlicic stikala se poroca,
a PRIMARNA je ena in je dolocena vnaprej: `BTC signal je BULL`. Ostale so
obcutljivostna analiza in se stejejo v popravek za stevilo poskusov.
════════════════════════════════════════════════════════════════════════════

STROSKI STIKALA SE OBRACUNAJO. Ob vsakem preklopu se proda oziroma kupi ves
tedaj drzani del knjige, po 0,30 % na stran. Prvi, hitri test tega ni delal in
je stikalo prikazal lepse, kot je.

Izhod: testing/data/knjizno_stikalo.json
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
for p in (ROOT, ROOT / "lean"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from shared.data_source import fetch_candles                    # noqa: E402
from testing.scripts.alti_parametri2 import (                   # noqa: E402
    FEE, PPY, VIRI, blok_bootstrap, sortino)
from testing.scripts.preveri_pine import (                      # noqa: E402
    avtomat_po_pine, pine_privzetki, po_pine, pozicija_po_pine)

OUT = ROOT / "testing" / "data" / "knjizno_stikalo.json"
MIN_DD = 5.0          # zahtevano zmanjsanje padca, odstotnih tock
# Ogrevanja NE vpisuj na roko. `shared/warmup.py` je skupna definicija, ki jo
# uporabljata tudi dashboard in raziskovalni pogon, in njen komentar je izrecen:
# "a disagreement between the live dashboard and a report must not be caused by
# two different definitions of usable history". Prva razlicica tega testa je
# vpisala 220, dejansko pa je 199 -- in razlika enega bara je bila dovolj, da se
# SOL ni ujel.
from shared.warmup import warmup_bars                            # noqa: E402

# Utezi so VASE dejanske, ne enake. Prva razlicica tega testa je racunala enako
# uteZeno knjigo, kar je dalo stevilke, ki jih na dashboardu ni bilo mogoce
# najti -- razlika je bila okoli 5 odstotnih tock letnega donosa.
UTEZI = {"BTC": 0.50, "ETH": 0.10, "SOL": 0.10,
         "LINK": 0.10, "BNB": 0.10, "XRP": 0.10}


def panel(r: np.ndarray) -> dict:
    r = np.asarray(r, float)
    if len(r) < 30:
        return {k: np.nan for k in
                ("cagr", "sharpe", "sortino", "maxdd", "calmar", "mult", "okrev")}
    eq = np.cumprod(1.0 + r)
    dd = eq / np.maximum.accumulate(eq) - 1.0
    v = r.std() * np.sqrt(PPY)
    c = eq[-1] ** (PPY / len(r)) - 1.0
    peak, worst, cur = eq[0], 0, 0
    for x in eq:
        if x >= peak:
            peak, cur = x, 0
        else:
            cur += 1
            worst = max(worst, cur)
    return dict(cagr=c * 100, sharpe=float(r.mean() * PPY / v) if v > 0 else np.nan,
                sortino=sortino(r), maxdd=dd.min() * 100,
                calmar=c / abs(dd.min()) if dd.min() < 0 else np.nan,
                mult=float(eq[-1]), okrev=int(worst))


DNO = 0.05          # trajno dno, isto kot bear_alloc_pct v strategiji


def z_stikalom(P: pd.DataFrame, RET: pd.DataFrame, s: pd.Series,
               TRAD: pd.DataFrame, fee=FEE, dno=DNO):
    """Knjiga s stikalom, po SREDSTVIH, s trajnim dnom in stroskom preklopa.

    Racuna se po sredstvih in ne na skupnem donosu knjige, ker mora ob
    izklopljenem stikalu v vsakem sredstvu ostati `dno` -- ta del je se vedno
    izpostavljen ceni tistega sredstva in mora rasti oziroma padati z njo.
    Prejsnja razlicica je ob izklopu postavila donos knjige na nic, kar je
    pomenilo, da se proda tudi dno; to ni bilo v skladu s strategijo, kjer dno
    ostane vedno.

    `P` so drzani delezi po sredstvih (ze zamaknjeni za en dan), `RET` dnevni
    donosi, `s` stanje stikala. Ob preklopu se placa celoten premik pozicije;
    ko je stikalo izklopljeno, se ne trguje, ker dno miruje.
    """
    s_prej = s.reindex(P.index).shift(1).fillna(False).astype(bool)
    # Sredstvo, ki se nima signala (ogrevanje ali kasnejsi zacetek kotacije),
    # NI na dnu -- v knjigi ga se ni. Brez te maske bi mu stikalo ob izklopu
    # pripisalo 5 %, dashboard pa mu ne pripise nicesar.
    ima = P.notna()
    ucin = P.where(s_prej, dno).where(ima, 0.0)       # ob izklopu ostane dno
    prej = ucin.shift(1)
    # Prvi dan okna: dashboard predpostavi, da vstopis v celoti v knjigo, in ce
    # je stikalo tisti dan ze izklopljeno, prvi dan placas prodajo do dna. Ta
    # motor je prej predpostavil, da si ze pravilno postavljen. Razlika je en
    # sam bar (0,0135 % donosa), a je razlika -- in konvencija naj bo ista kot
    # na objavljeni strani, ne moja.
    prej.iloc[0] = 0.0
    preklop = s_prej.ne(s_prej.shift(1).fillna(True))

    # Obicajni obrat sredstva velja le, ko je stikalo vklopljeno; na dan
    # preklopa ga nadomesti celoten premik; ko je izklopljeno, obrata ni.
    #
    # `TRAD` so DEJANSKI posli strategije, ne `P.diff().abs()`. Slednje bi
    # zaracunalo tudi plavanje trajnega dna, ki se nikoli ne uravnava -- torej
    # transakcijo, ki se ne zgodi. Prva razlicica je delala prav to in je zato
    # dajala nekoliko drugacne stevilke kot dashboard.
    obrat = ((ucin - prej).abs().where(preklop, TRAD.where(s_prej, 0.0))
             .where(ima, 0.0))
    return _pot_knjige(ucin, RET, obrat, fee), s_prej, _tehtano(ucin)


def _tehtano(X: pd.DataFrame) -> pd.Series:
    w = pd.Series({k: UTEZI[k] for k in X.columns})
    return (X * w).sum(axis=1) / w.sum()


def _pot_knjige(poz: pd.DataFrame, RET: pd.DataFrame, obrat: pd.DataFrame,
                fee=FEE) -> pd.Series:
    """Donos knjige iz ZNESKOV po nalozbah, ne iz povprecja donosov.

    Povprecje dnevnih donosov je matematicno DNEVNO uravnavanje nazaj na ciljne
    utezi -- kar je nekaj drugega kot pustiti vsako nalozbo pri miru. Dashboard
    dela drugo, zato mora tudi ta test, sicer se stevilki ne moreta ujeti.
    """
    stolpci = list(poz.columns)
    E = np.array([UTEZI[k] for k in stolpci], float)
    E = E / E.sum()
    P = poz[stolpci].to_numpy(float)
    R_ = RET[stolpci].to_numpy(float)
    O = obrat[stolpci].to_numpy(float)
    pot = np.empty(len(P))
    for i in range(len(P)):
        E = E * (1.0 + P[i] * R_[i] - O[i] * fee / 100.0)
        pot[i] = E.sum()
    return pd.Series(np.r_[pot[0] - 1.0, pot[1:] / pot[:-1] - 1.0], index=poz.index)


def main() -> int:
    p0 = pine_privzetki()
    r_sym, pos_sym, sig_sym, trad_sym = {}, {}, {}, {}
    for sym, vir in VIRI.items():
        px = fetch_candles(sym, "1d", bars=3000, prefer=vir)
        ret = px["close"].pct_change().fillna(0.0)
        f = po_pine(px, p0)
        sig = avtomat_po_pine(f, p0)["signalState"].to_numpy()
        held, traded = pozicija_po_pine(px, sig, p0)
        # OGREVANJE. Dokler najpocasnejsi indikator (200 SMA) ne obstaja,
        # pandas primerja `close > NaN` kot False in rezimski filter se TIHO
        # izklopi -- signal tece brez svoje glavne varovalke. Dashboard te bare
        # odreze (`trim_warmup`), ta test jih prej ni, in prav zato je SOL
        # zacel trgovati pol leta prezgodaj: obrat 20,75 namesto 18,98.
        # Nalozba do takrat caka v gotovini, tako kot v dashboardu.
        n_ogr = warmup_bars(f)
        held[:n_ogr] = 0.0
        traded[:n_ogr] = 0.0
        r_sym[sym] = pd.Series(held * ret.to_numpy(float) - traded * FEE / 100.0,
                               index=px.index)
        pos_sym[sym] = pd.Series(held, index=px.index)
        trad_sym[sym] = pd.Series(traded, index=px.index)
        sig_sym[sym] = pd.Series(sig, index=px.index)

    R = pd.DataFrame(r_sym).dropna(how="all")
    P = pd.DataFrame(pos_sym).reindex(R.index)
    okno = R.dropna().index                      # vsa sredstva imajo podatke
    R, P = R.loc[okno], P.loc[okno]
    TRAD = pd.DataFrame(trad_sym).reindex(okno).fillna(0.0)[P.columns]
    izp = None      # dolocena spodaj, ko so na voljo RET

    btc_px = fetch_candles("BTC", "1d", bars=3000, prefer="coinbase")
    btc_sig = sig_sym["BTC"].reindex(okno)
    sma200 = btc_px["close"].rolling(200, min_periods=200).mean()
    stikala = {
        "BTC signal BULL": (btc_sig == 1),                       # PRIMARNO
        "BTC nad 200 SMA": (btc_px["close"] > sma200).reindex(okno).fillna(False),
        "vecina sredstev BULL": (pd.DataFrame(sig_sym).reindex(okno) == 1)
                                .mean(axis=1) > 0.5,
    }
    PRIMARNO = "BTC signal BULL"

    print(f"provizija {FEE} % na stran, strosek preklopa se obracuna")
    print(f"okno {okno[0].date()} -> {okno[-1].date()}   {len(okno)} barov, "
          f"{len(R.columns)} sredstev\n")

    RET = pd.DataFrame({k: fetch_candles(k, "1d", prefer=VIRI[k], bars=3000)
                        ["close"].pct_change().reindex(okno).fillna(0.0)
                        for k in R.columns})
    osnova = _pot_knjige(P, RET, TRAD)
    izp = _tehtano(P)
    serije = {"brez stikala": osnova}
    izp_ser = {"brez stikala": izp}
    for ime, s in stikala.items():
        r, s_prej, e = z_stikalom(P, RET, s.reindex(okno).fillna(False), TRAD)
        serije[ime] = r
        izp_ser[ime] = e

    # ── celo okno ────────────────────────────────────────────────────────────
    print("=" * 104)
    print("CELO OKNO -- na tem se sodi")
    print("=" * 104)
    print(f"{'razlicica':<24}{'CAGR':>8}{'Sharpe':>8}{'Sortino':>9}{'MaxDD':>9}"
          f"{'Calmar':>8}{'okrev':>7}{'v trgu':>8}{'preklopov':>11}{'1 EUR ->':>10}")
    tab = {}
    for ime, r in serije.items():
        q = panel(r.to_numpy())
        vt = float(izp_ser[ime].mean() * 100)
        if ime == "brez stikala":
            n_pre = 0
        else:
            s = stikala[ime].reindex(okno).fillna(False).shift(1).fillna(False)
            n_pre = int(s.ne(s.shift(1)).sum())
        tab[ime] = dict(**q, v_trgu=vt, preklopov=n_pre)
        print(f"{ime:<24}{q['cagr']:>7.2f}%{q['sharpe']:>8.2f}{q['sortino']:>9.2f}"
              f"{q['maxdd']:>8.1f}%{q['calmar']:>8.2f}{q['okrev']:>7}"
              f"{vt:>7.0f}%{n_pre:>11}{q['mult']:>9.2f}x")

    # ── glavna ovira: staticni delez z isto izpostavljenostjo ───────────────
    print("\n" + "=" * 104)
    print("GLAVNA OVIRA -- proti staticnemu delezu z ISTO povprecno izpostavljenostjo")
    print("=" * 104)
    osn_izp = float(izp.mean())
    ovire = {}
    for ime in stikala:
        cilj = float(izp_ser[ime].mean())
        delez = cilj / osn_izp if osn_izp > 0 else 1.0
        stat = osnova * delez
        a, b = sortino(serije[ime].to_numpy()), sortino(stat.to_numpy())
        d = (serije[ime] - stat).to_numpy()
        bs = blok_bootstrap(d)
        lo, hi = np.nanpercentile(bs, [5, 95])
        sodba = "BOLJSI" if lo > 0 else "SLABSI" if hi < 0 else "nedokazano"
        qs = panel(stat.to_numpy())
        ovire[ime] = dict(delez=delez * 100, staticni=qs, d_sortino=a - b,
                          lo=float(lo), hi=float(hi), sodba=sodba)
        print(f"   {ime:<24} staticnih {delez*100:5.1f} % knjige: "
              f"CAGR {qs['cagr']:5.2f} %, Sortino {qs['sortino']:.2f}, "
              f"MaxDD {qs['maxdd']:6.1f} %")
        print(f"   {'':<24} d Sortino {a - b:+.2f}  [{lo:+.2f}, {hi:+.2f}]"
              f"  -> {sodba}")

    # ── proti izhodiscu ─────────────────────────────────────────────────────
    print("\n" + "=" * 104)
    print("PROTI IZHODISCU (brez stikala)")
    print("=" * 104)
    proti = {}
    for ime in stikala:
        d = (serije[ime] - osnova).to_numpy()
        a, b = sortino(serije[ime].to_numpy()), sortino(osnova.to_numpy())
        bs = blok_bootstrap(d)
        lo, hi = np.nanpercentile(bs, [5, 95])
        sodba = "BOLJSI" if lo > 0 else "SLABSI" if hi < 0 else "nedokazano"
        proti[ime] = dict(d_sortino=a - b, lo=float(lo), hi=float(hi), sodba=sodba)
        print(f"   {ime:<24} d Sortino {a - b:+.2f}  [{lo:+.2f}, {hi:+.2f}]"
              f"  -> {sodba}")

    # ── po obdobjih ─────────────────────────────────────────────────────────
    print("\n" + "=" * 104)
    print("PO OBDOBJIH  (pogled v porazdelitev, NE osnova za izbiro)")
    print("=" * 104)
    obdobja = []
    for leto in sorted({t.year for t in okno}):
        m = np.asarray([t.year == leto for t in okno])
        if m.sum() > 60:
            obdobja.append((str(leto), m))
    for n_let in (1, 2, 3, 5):
        zac = okno[-1] - pd.Timedelta(days=int(365.25 * n_let))
        m = np.asarray(okno >= zac)
        if m.sum() > 60:
            obdobja.append((f"zadnjih {n_let} let", m))

    po_obd = {}
    for ime in serije:
        po_obd[ime] = {}
    print(f"{'obdobje':<16}" + "".join(
        f"{k:>26}" for k in ("brez stikala", PRIMARNO)))
    print(f"{'':<16}" + "".join(
        f"{'CAGR':>7}{'Sh':>6}{'So':>6}{'DD':>7}" for _ in range(2)))
    for ime_o, m in obdobja:
        vrstica = f"{ime_o:<16}"
        for ime in ("brez stikala", PRIMARNO):
            q = panel(serije[ime].to_numpy()[m])
            po_obd[ime][ime_o] = q
            vrstica += (f"{q['cagr']:>6.1f}%{q['sharpe']:>6.2f}"
                        f"{q['sortino']:>6.2f}{q['maxdd']:>6.0f}%")
        print(vrstica)

    # ── ali korist visi na enem samem letu? ─────────────────────────────────
    # Stikalo je bilo vse leto 2022 zunaj. Ce je vsa prednost od tam, potem to
    # ni dvajset neodvisnih odlocitev, ampak ena -- in vzorec je n = 1.
    print("\n" + "=" * 104)
    print("VISI KORIST NA ENEM LETU?  (isti izracun brez 2022)")
    print("=" * 104)
    brez22 = np.asarray([t.year != 2022 for t in okno])
    delez_zunaj_22 = float(1.0 - stikala[PRIMARNO].reindex(okno).fillna(False)
                           .to_numpy()[np.asarray([t.year == 2022 for t in okno])].mean())
    print(f"   delez leta 2022, ko je bilo stikalo IZKLOPLJENO: "
          f"{delez_zunaj_22*100:.0f} %")
    print(f"{'razlicica':<24}{'CAGR':>8}{'Sharpe':>8}{'Sortino':>9}{'MaxDD':>9}"
          f"{'1 EUR ->':>10}")
    b22 = {}
    for ime in ("brez stikala", PRIMARNO):
        q = panel(serije[ime].to_numpy()[brez22])
        b22[ime] = q
        print(f"{ime:<24}{q['cagr']:>7.2f}%{q['sharpe']:>8.2f}{q['sortino']:>9.2f}"
              f"{q['maxdd']:>8.1f}%{q['mult']:>9.2f}x")
    d22 = (serije[PRIMARNO] - osnova).to_numpy()[brez22]
    bs22 = blok_bootstrap(d22)
    lo22, hi22 = np.nanpercentile(bs22, [5, 95])
    print(f"   d Sortino brez 2022: "
          f"{b22[PRIMARNO]['sortino'] - b22['brez stikala']['sortino']:+.2f}  "
          f"[{lo22:+.2f}, {hi22:+.2f}]")

    # ── sodba po vnaprejsnjem merilu ────────────────────────────────────────
    print("\n" + "=" * 104)
    print("SODBA PO VNAPREJ ZAPISANEM MERILU  (primarna razlicica, celo okno)")
    print("=" * 104)
    b0, b1 = tab["brez stikala"], tab[PRIMARNO]
    # Oba padca sta NEGATIVNA. Zmanjsanje padca je zato `b1 - b0`, ne obratno:
    # -22.9 - (-35.2) = +12.3. Prvi zapis je imel obrnjen predznak in je
    # 12-odstotno izboljsanje javil kot neizpolnjen pogoj.
    izboljsanje_dd = b1["maxdd"] - b0["maxdd"]
    p1 = izboljsanje_dd >= MIN_DD
    p2 = b1["sortino"] >= b0["sortino"]
    p3 = ovire[PRIMARNO]["d_sortino"] >= 0
    print(f"   1 padec manjsi za >= {MIN_DD:.0f} pp: "
          f"{b0['maxdd']:.1f} % -> {b1['maxdd']:.1f} %  "
          f"(za {izboljsanje_dd:+.1f} pp)   {'DA' if p1 else 'NE'}")
    print(f"   2 Sortino ne pade:              "
          f"{b0['sortino']:.2f} -> {b1['sortino']:.2f}   {'DA' if p2 else 'NE'}")
    print(f"   3 prekasa staticni delez:       "
          f"d Sortino {ovire[PRIMARNO]['d_sortino']:+.2f}   {'DA' if p3 else 'NE'}")
    print(f"\n   -> {'SPREJETA' if (p1 and p2 and p3) else 'ZAVRNJENA'}")

    res = dict(generated=str(pd.Timestamp.utcnow()), fee=FEE,
               okno=[str(okno[0].date()), str(okno[-1].date())],
               primarno=PRIMARNO, celo_okno=tab, ovire=ovire, proti_izhodiscu=proti,
               po_obdobjih=po_obd,
               merilo=dict(padec=bool(p1), sortino=bool(p2), ovira=bool(p3),
                           sprejeta=bool(p1 and p2 and p3)))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    print(f"\nzapisano: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
