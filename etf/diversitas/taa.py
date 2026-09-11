"""Taktična razporeditev sredstev, zgrajena od začetka po strokovni praksi.

Nič od tega ni preneseno iz kripta. Trackline, Donchian, ADX in dnevno
odločanje tu ne nastopajo. Vsak sestavni del ima vir in razlog.

────────────────────────────────────────────────────────────────────────────
ZAKAJ TA DRUŽINA IN NE TRENDNA

Trendno sledenje, kot ga delajo CTA, potrebuje 40 do 60 trgov, dolge in kratke
pozicije in terminske pogodbe. Knjiga z osmimi dolgimi ETF-ji ima po meritvi
1,1 oziroma 2,3 neodvisne stave. Za tak problem obstaja druga, prav tako
uveljavljena družina: **taktična razporeditev sredstev (TAA)**, ki jo je
zasnoval Faber (2007) in razvila Keller in Keuning (VAA 2017, DAA 2018,
HAA 2023) ter ReSolve (Adaptive Asset Allocation). Vsi delajo z desetimi do
petnajstimi razredi sredstev, dolgo-le, mesečno.

────────────────────────────────────────────────────────────────────────────
ŠTIRJE SESTAVNI DELI, VSAK Z VIROM

**1. Momentum 13612W namesto drsečih povprečij.** Keller uporablja uteženo
povprečje donosov za 1, 3, 6 in 12 mesecev z utežmi 12, 4, 2 in 1. Prednost
pred križanjem drsečih povprečij: ni praga, ki bi ga bilo treba izbrati, in ne
niha ob eni sami ceni. To je najbolj standardna oblika momentuma v tej
literaturi.

**2. Kanarček za vklop tveganja, ne signal na vsakem rokavu.** Kellerjeva DAA
uporablja majhno „kanarčkovo" množico — VWO in BND, torej trgi v razvoju in
agregatne obveznice — ki odloči, koliko tveganja sme knjiga nositi. Ideja je,
da sta ta dva razreda zgodnja opozorilnika, in da je ena odločitev na ravni
knjige boljša od osmih neodvisnih. Ta knjiga ima natanko oba: EM in GlobAgg.

**3. Utežitev po tveganju, ne enakomerna.** ReSolve izbere najboljših pet po
šestmesečnem momentumu in jih uteži po najmanjši varianci, z 20-dnevno
volatilnostjo in 126-dnevno korelacijo. Tu je privzeta obratna volatilnost, ker
je robustnejša od optimizacije na kratkem vzorcu, najmanjša varianca pa je na
voljo kot možnost.

**4. Razdelitev na tranše proti sreči pri datumu.** Faberjeva strategija pokaže
do **220 bazičnih točk** razlike v CAGR med najboljšim in najslabšim dnevom
uravnavanja — brez vsake veščine. Popravek, ki ga uporablja Newfound Research:
razdeli knjigo na N tranš in vsako uravnavaj v drugem tednu. Tu privzeto 4.

────────────────────────────────────────────────────────────────────────────
KAJ JE TREBA VEDETI, PREDEN SE TEMU VERJAME

Ta družina je močno objavljena in ima dokumentirano upadanje po objavi.
Faberjeva GTAA je imela v izvirniku 1972–2005 Sharpe 0,81 in CAGR 11,7 %; na
podatkih 2006–2025 Sharpe 0,68 in CAGR 6,05 %. Kellerjeve številke izvirajo iz
iskanja po zgodovini, ki je bila takrat že znana. Zato tu ni nobene nastavitve,
ki bi bila izbrana na naših podatkih: vse vrednosti so privzetki iz izvirnih
člankov.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd


# ── momentum ──────────────────────────────────────────────────────────────────

def mom_13612w(px: pd.Series, ppm: int = 21) -> pd.Series:
    """Kellerjev uteženi momentum: 12·r1 + 4·r3 + 2·r6 + 1·r12, deljeno s 4.

    `ppm` je število trgovalnih dni v mesecu. Uteži so iz izvirnika in niso
    predmet prilagajanja — ravno to je razlog, da so uporabljene.
    """
    r1 = px / px.shift(1 * ppm) - 1.0
    r3 = px / px.shift(3 * ppm) - 1.0
    r6 = px / px.shift(6 * ppm) - 1.0
    r12 = px / px.shift(12 * ppm) - 1.0
    return (12.0 * r1 + 4.0 * r3 + 2.0 * r6 + 1.0 * r12) / 4.0


def mom_simple(px: pd.Series, months: int = 6, ppm: int = 21) -> pd.Series:
    """Preprost donos čez N mesecev — ReSolve uporablja šest."""
    return px / px.shift(months * ppm) - 1.0


ENSEMBLE_MESECI = (1, 3, 6, 9, 12)


def mom_ensemble(px: pd.DataFrame, ppm: int = 21,
                 meseci: Sequence[int] = ENSEMBLE_MESECI) -> pd.DataFrame:
    """Povprečje UVRSTITEV čez več hitrosti namesto ene izbrane.

    Zakaj uvrstitve in ne donosi: donos za en mesec in donos za dvanajst
    mesecev sta različno velika, zato bi povprečje donosov tiho dalo največjo
    utež najdaljši hitrosti. Povprečje uvrstitev tega ne počne.

    Zakaj sploh: ReSolve in Newfound ugotavljata isto — izbira ene same hitrosti
    je nepotrebno tveganje specifikacije, mešanica hitrosti pa zmanjša
    razpršenost rezultata glede na srednjo specifikacijo. Pri nas to tudi pomeni,
    da šestmesečnega momentuma ni treba izbrati po ogledu rezultata, kar je bila
    prava metodološka pomanjkljivost prejšnjega kroga.
    """
    r = [px / px.shift(m * ppm) - 1.0 for m in meseci]
    ranks = [x.rank(axis=1, pct=True) for x in r]
    out = sum(ranks) / len(ranks)
    # tam, kjer katera koli hitrost še nima podatkov, ostane NaN
    mask = r[-1].notna()
    return out.where(mask)


# ── utežitev ──────────────────────────────────────────────────────────────────

def inverse_vol(rets: pd.DataFrame, cols: Sequence[str], lookback: int = 60) -> np.ndarray:
    """Uteži po obratni volatilnosti. Robustnejše od optimizacije na kratkem
    vzorcu, ker ne potrebuje korelacijske matrike, ki je pri malo podatkih
    najbolj nezanesljiv del ocene."""
    v = rets[list(cols)].tail(lookback).std().to_numpy()
    v = np.where(v > 1e-9, v, np.nan)
    w = 1.0 / v
    w = np.nan_to_num(w, nan=0.0)
    return w / w.sum() if w.sum() > 0 else np.ones(len(cols)) / len(cols)


def min_variance(rets: pd.DataFrame, cols: Sequence[str], lookback_corr: int = 126,
                 lookback_vol: int = 20, ridge: float = 1e-4) -> np.ndarray:
    """Najmanjša varianca po ReSolve: 126-dnevna korelacija, 20-dnevna
    volatilnost, brez kratkih pozicij.

    `ridge` je nujen. Kovariančna matrika iz 126 opazovanj za šest sredstev je
    skoraj singularna, in brez regularizacije optimizacija vrne uteži, ki so
    posledica šuma v zadnji decimalki.
    """
    cols = list(cols)
    if len(cols) == 1:
        return np.array([1.0])
    C = rets[cols].tail(lookback_corr).corr().to_numpy()
    s = rets[cols].tail(lookback_vol).std().to_numpy()
    S = np.outer(s, s) * C + np.eye(len(cols)) * ridge
    try:
        inv = np.linalg.pinv(S)
    except np.linalg.LinAlgError:
        return np.ones(len(cols)) / len(cols)
    w = inv @ np.ones(len(cols))
    w = np.clip(w, 0.0, None)                 # brez kratkih pozicij
    return w / w.sum() if w.sum() > 0 else np.ones(len(cols)) / len(cols)


def hrp(rets: pd.DataFrame, cols: Sequence[str], lookback: int = 252) -> np.ndarray:
    """Hierarhična pariteta tveganja (López de Prado).

    Namesto obračanja kovariančne matrike, kar je pri malo podatkih najbolj
    nestabilen korak, sredstva najprej razvrsti v gruče po korelaciji in tveganje
    razdeli po drevesu navzdol. Raffinot ugotavlja, da je „hierarhični 1/N zelo
    težko premagati" — zato je tu, in zato je enaka utež med kandidati.
    """
    cols = list(cols)
    if len(cols) < 3:
        return inverse_vol(rets, cols, min(lookback, 60))
    try:
        from testing.scripts.portfolio import hrp_weights
    except Exception:  # noqa: BLE001 — če pot ni na voljo, pade nazaj
        return inverse_vol(rets, cols, min(lookback, 60))
    w = hrp_weights(rets[cols].tail(lookback))
    v = w.reindex(cols).fillna(0.0).to_numpy()
    return v / v.sum() if v.sum() > 0 else np.ones(len(cols)) / len(cols)


WEIGHTERS = {"obratna_vol": inverse_vol, "min_var": min_variance, "hrp": hrp,
             "enake": lambda r, c, **kw: np.ones(len(list(c))) / len(list(c))}


# ── strategija ────────────────────────────────────────────────────────────────

@dataclass
class TAAConfig:
    """Privzetki so iz izvirnih člankov, ne iz naših podatkov."""
    tvegana: Sequence[str] = ("World", "EM", "SmallCap", "Quality", "Gold", "Commod")
    obrambna: Sequence[str] = ("GlobAgg", "InflLink")
    kanarcek: Sequence[str] = ("EM", "GlobAgg")     # Kellerjev VWO + BND
    top_n: int = 3                                   # koliko tveganih drži
    utezitev: str = "obratna_vol"
    momentum: str = "13612w"
    ppm: int = 21                                    # trgovalnih dni v mesecu
    transe: int = 4                                  # proti sreči pri datumu
    uporabi_kanarcka: bool = True
    zahtevaj_pozitiven_momentum: bool = True         # Kellerjevo pravilo

    # ── posegi za manjši obrat. Vsi znani, noben ne spreminja signala. ────────
    histereza: float = 0.0
    """Koliko mora izzivalec prekašati sedanjega, da ga zamenja, v enotah
    uvrstitve (0 do 1) oziroma momentuma. Nič pomeni brez histereze. Namen je
    odstraniti zamenjave, ki nastanejo iz drobne razlike v uvrstitvi in nato
    naslednji mesec obrnejo nazaj."""

    delni_premik: float = 1.0
    """Kolikšen del poti proti novim utežem se naredi ob eni odločitvi. 1,0 je
    polna zamenjava. Newfound to imenuje „a little but frequently": manjši
    premiki, pogosteje, dajo isto povprečno pozicijo pri nižjem obratu."""

    max_tvegano: float = 1.0
    """Zgornja meja deleža v tveganih sredstvih. To je **izbira o tveganju in ne
    prilagojena vrednost**: 1,0 pomeni, da sme knjiga biti v celoti v tveganih,
    0,6 pa da najmanj 40 % vedno stoji v obrambnem delu. Ravno zato, ker je to
    preferenca in ne ocena, se ne sme iskati po podatkih — postavi se vnaprej in
    se poroča kot dana."""

    fiksni_obrambni: bool = False
    """Če je True, se obrambni del vedno deli na pol med obrambnimi sredstvi
    namesto mesečnega izbiranja najboljšega. Razlika med njima je majhna, obrat
    pa ne."""


@dataclass
class TAAResult:
    returns: pd.Series
    weights: pd.DataFrame
    risk_on: pd.Series
    turnover: pd.Series
    meta: dict = field(default_factory=dict)


def _mom(px: pd.DataFrame, cfg: TAAConfig) -> pd.DataFrame:
    if cfg.momentum == "ansambel":
        return mom_ensemble(px, cfg.ppm)
    f = (mom_13612w if cfg.momentum == "13612w"
         else lambda s, ppm=cfg.ppm: mom_simple(s, 6, ppm))
    return pd.DataFrame({c: f(px[c], cfg.ppm) for c in px.columns})


def abs_pozitiven(px: pd.DataFrame, ppm: int = 21,
                  meseci: Sequence[int] = ENSEMBLE_MESECI) -> pd.DataFrame:
    """Ali je momentum sredstva ABSOLUTNO pozitiven — vecina hitrosti nad niclo.

    To je loceno od razvrscanja in mora biti. Kellerjevo pravilo „momentum mora
    biti pozitiven" spravsuje, ali je sredstvo pridobilo vrednost, kar je
    vprasanje o donosu. Razvrstitev pa sprasuje, katero je bilo najboljse — in
    najboljse med stirimi padajocimi je se vedno padajoce.

    Prvotna razlicica je oboje merila z isto stevilko in kot mejo vzela 0,5.
    Pri stirih sredstvih `rank(pct=True)` vrne 0,25, 0,50, 0,75 in 1,00, torej
    povprecje 0,625 — meja 0,5 bi tri od stirih vedno razglasila za pozitivna,
    tudi ce bi vsa stiri padala. Filter bi tiho odpadel, kanarcek pa bi skoraj
    vedno pel.
    """
    r = [px / px.shift(m * ppm) - 1.0 for m in meseci]
    stev = sum((x > 0).astype(float) for x in r)
    out = stev / len(meseci) > 0.5
    return out.where(r[-1].notna(), other=False)


def _en_izbor(px, rets, mom, poz, t, cfg,
              prejsnji: Optional[List[str]] = None) -> Dict[str, float]:
    """Ciljne uteži za en dan odločanja. Vse iz podatkov do vključno t."""
    m = mom.loc[t]
    p = poz.loc[t]

    def je_poz(c: str) -> bool:
        return bool(p.get(c, False))

    # 1) kanarček odloči, koliko tveganja
    if cfg.uporabi_kanarcka:
        kan = [c for c in cfg.kanarcek if c in mom.columns]
        n_dobrih = sum(1 for c in kan if je_poz(c))
        delez_tvegan = n_dobrih / max(len(kan), 1)
    else:
        delez_tvegan = 1.0
    delez_tvegan = min(delez_tvegan, cfg.max_tvegano)

    out: Dict[str, float] = {}

    # 2) tvegani del: najboljših N po momentumu, in vsak mora biti pozitiven
    if delez_tvegan > 0:
        kand = [c for c in cfg.tvegana if c in mom.columns and pd.notna(m.get(c))]
        kand_vsi = sorted(kand, key=lambda c: m[c], reverse=True)
        kand = kand_vsi[:cfg.top_n]

        # Histereza: sedanjega ne zamenjaj, dokler ga izzivalec ne prekaša za
        # `histereza`. Brez tega se par mest vsak mesec izmenja zaradi razlike v
        # tretji decimalki, kar je čist obrat brez vsebine.
        if cfg.histereza > 0 and prejsnji:
            drzi = [c for c in prejsnji if c in kand_vsi]
            for c in drzi:
                if c in kand:
                    continue
                naj_slabsi = min(kand, key=lambda x: m[x]) if kand else None
                if naj_slabsi is not None and (m[naj_slabsi] - m[c]) < cfg.histereza:
                    kand = [x for x in kand if x != naj_slabsi] + [c]

        if cfg.zahtevaj_pozitiven_momentum:
            izbrani = [c for c in kand if je_poz(c)]
        else:
            izbrani = kand
        # Kellerjevo pravilo: mesto, ki ga tvegano sredstvo ne zasluži, gre
        # obrambnemu, ne v gotovino. Sredstva so že v knjigi, zato je to
        # naravno in ne zahteva novega instrumenta.
        praznih = cfg.top_n - len(izbrani)
        if izbrani:
            w = WEIGHTERS[cfg.utezitev](rets.loc[:t], izbrani)
            for c, wi in zip(izbrani, w):
                out[c] = out.get(c, 0.0) + delez_tvegan * wi * (len(izbrani) / cfg.top_n)
        delez_tvegan_ostanek = delez_tvegan * (praznih / cfg.top_n)
    else:
        delez_tvegan_ostanek = 0.0

    # 3) obrambni del: najboljši obrambni sredstvi po momentumu
    obr_delez = (1.0 - delez_tvegan) + delez_tvegan_ostanek
    if obr_delez > 1e-9:
        obr = [c for c in cfg.obrambna if c in mom.columns and pd.notna(m.get(c))]
        if obr and cfg.fiksni_obrambni:
            for c in obr:
                out[c] = out.get(c, 0.0) + obr_delez / len(obr)
        elif obr:
            naj = max(obr, key=lambda c: m[c])
            out[naj] = out.get(naj, 0.0) + obr_delez
        else:
            out["CASH"] = out.get("CASH", 0.0) + obr_delez
    return out


def run_taa(px: pd.DataFrame, cfg: TAAConfig = TAAConfig(),
            fee_per_trade_pct: float = 0.20,
            cash_daily: Optional[pd.Series] = None) -> TAAResult:
    """Odigraj strategijo. Odločitve so mesečne, po tranšah.

    Brez pogleda v prihodnost: uteži za dan t so izračunane iz podatkov do t-1
    in veljajo od t naprej.
    """
    px = px.dropna()
    rets = px.pct_change().fillna(0.0)
    mom = _mom(px, cfg)
    poz = abs_pozitiven(px, cfg.ppm)
    idx = px.index
    cols = list(px.columns) + ["CASH"]
    cash_d = (pd.Series(0.0, index=idx) if cash_daily is None
              else cash_daily.reindex(idx).fillna(0.0))

    # dnevi odločanja za vsako tranšo: mesečno, zamaknjeno po tednih
    korak = cfg.ppm
    zamik = max(korak // max(cfg.transe, 1), 1)
    transe_dni = [set(idx[i::korak]) for i in
                  range(0, korak, zamik)][:max(cfg.transe, 1)]
    n_tr = len(transe_dni)

    stanje = [dict() for _ in range(n_tr)]        # ciljne uteži vsake tranše
    vred = np.full(n_tr, 100.0 / n_tr)
    zgod, w_zgod, ro_zgod, obrat = [], [], [], []

    prva_vel = mom.dropna(how="all").index
    zac = prva_vel[0] if len(prva_vel) else idx[0]

    for i, t in enumerate(idx):
        dnevni_obrat = 0.0
        for j in range(n_tr):
            if t in transe_dni[j] and t >= zac and i > 0:
                staro = stanje[j]
                prej_izbor = [c for c in staro if c not in cfg.obrambna and c != "CASH"]
                nov = _en_izbor(px, rets, mom, poz, idx[i - 1], cfg, prej_izbor)
                if cfg.delni_premik < 1.0:
                    # Newfoundov „a little but frequently": premakni se le del
                    # poti proti cilju. Povprečna pozicija ostane ista, obrat pade.
                    k = cfg.delni_premik
                    vsi = set(nov) | set(staro)
                    nov = {c: (1 - k) * staro.get(c, 0.0) + k * nov.get(c, 0.0)
                           for c in vsi}
                    nov = {c: w for c, w in nov.items() if w > 1e-6}
                sprem = sum(abs(nov.get(c, 0.0) - staro.get(c, 0.0)) for c in cols)
                vred[j] *= (1.0 - sprem * fee_per_trade_pct / 100.0)
                dnevni_obrat += sprem * vred[j]
                stanje[j] = nov
            # rast tranše
            r = 0.0
            for c, w in stanje[j].items():
                r += w * (cash_d.iloc[i] if c == "CASH" else rets[c].iloc[i])
            vred[j] *= (1.0 + r)
        zgod.append(vred.sum())
        skupne = {}
        for j in range(n_tr):
            for c, w in stanje[j].items():
                skupne[c] = skupne.get(c, 0.0) + w / n_tr
        w_zgod.append(skupne)
        # Sesteti tvegano NEPOSREDNO. Prvotno je bilo 1 - gotovina - obrambno,
        # kar je pred prvo odlocitvijo, ko se ni drzano nic, vrnilo 1,0 namesto
        # 0,0 — in ker ta stevilka doloca primerjavo s staticnim delezem, je
        # bila izpostavljenost sistematicno precenjena.
        ro_zgod.append(sum(w for c, w in skupne.items() if c in cfg.tvegana))
        obrat.append(dnevni_obrat / max(vred.sum(), 1e-9))

    v = np.array([100.0] + zgod)
    r = v[1:] / v[:-1] - 1.0
    W = pd.DataFrame(w_zgod, index=idx).fillna(0.0)
    return TAAResult(returns=pd.Series(r, index=idx), weights=W,
                     risk_on=pd.Series(ro_zgod, index=idx),
                     turnover=pd.Series(obrat, index=idx),
                     meta=dict(cfg=cfg.__dict__, transe=n_tr))
