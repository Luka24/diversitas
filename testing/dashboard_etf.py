"""Sestava ETF proti samemu svetovnemu indeksu, z izbirnim datumom vstopa.

    streamlit run testing/dashboard_etf.py

Ista stran kot `dashboard_sestava.py`, samo za obe kombinaciji ETF namesto za
kripto knjigo. **Pogoji za nakup in prodajo so nedotaknjeni**: uporablja se
`lean` strategija s privzetim `LeanConfig`, torej trackline 75, MA 50 in 200,
vstopni pas 3 %, izstopna milost 3 dni, trajno dno 5 %. Nič od tega ni
prilagojeno delnicam ali davku. To je demo, ne predlog.

Racun vodi DENAR po nalozbah, ne donosov. Vsaka nalozba je znesek, ki raste in
se manjsa, provizije se odbijejo od zneska, metrike pa se izracunajo sele iz
poti skupne vrednosti. To je ista koda kot na kripto strani.

Dve stvari se glede na kripto stran nujno razlikujeta, in nobena ni pogoj za
nakup ali prodajo:

  1  Letno preracunavanje je 252 in ne 365. Delnice se trgujejo priblizno 252
     dni na leto; s 365 bi bili volatilnost, Sharpe in Sortino previsoki za
     faktor 1,204. Preverjeno je, da to ne spremeni nobenega posla: `lean` ima
     binarno alokacijo 0/100, `trading_days` pa vstopa le v `annual_vol`, ki se
     naprej uporablja kot razmerje do svojega povprecja, kjer se faktor skrajsa.
     Signali pri 365 in 252 so identicni na vseh osmih skladih.

  2  Merilo ni BTC, ampak svetovni indeks (IWDA). Vloga je ista: eno sredstvo,
     ki ga knjiga poskusa premagati, prikazano kot strategija in kot kupi in
     drzi.

Cene so v EUR prek `shared.etf_data`, torej z izrecno pretvorbo po dnevnem
referencnem tecaju ECB, ne prek evrsko oznacene vrstice istega ISIN.
"""
from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "lean"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from diversitas.config import LeanConfig
from diversitas.strategy import position, run_strategy, traded_fraction
from shared.etf_data import load
from shared.etf_universe import PORTFOLIOS, UNIVERSE
from shared.warmup import trim_warmup

PPY = 252
MERILO = "World"          # vloga, ki jo ima BTC na kripto strani

st.set_page_config(page_title="Sestava ETF", layout="wide",
                   initial_sidebar_state="expanded")


# ── podatki ───────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def _cena(k: str) -> pd.DataFrame:
    """Cene enega sklada. Predpomnjeno POSAMICNO in ne po celi koseri, zato da

      - napredek pri prvem nalaganju sploh obstaja: prej je bilo osem prenosov
        skrito za enim samim klicem in stran je 25 sekund samo stala;
      - en sklad, ki odpove, ne razveljavi ostalih sedmih.

    Prvi prenos traja priblizno 25 sekund za vseh osem, od tega 13 samo World,
    ki poleg cen prinese se tecajno serijo ECB. Nato je na disku parquet in v
    pomnilniku ura predpomnilnika, torej je vsak nadaljnji render hipen.
    """
    return load(k, start=UNIVERSE[k].usable_from)


@st.cache_data(ttl=3600, show_spinner=False)
def _signal(k: str) -> tuple:
    """Nedotaknjen lean na enem skladu.

    `trading_days` je edina spremenjena vrednost in ne spremeni nobenega posla
    (glej docstring modula). Vse ostalo je privzeti `LeanConfig`.
    """
    cfg = replace(LeanConfig(), trading_days=PPY)
    df = trim_warmup(run_strategy(_cena(k), config=cfg).df)
    return position(df, cfg), traded_fraction(df, cfg).fillna(0.0), df


def _nalozi(kljuci: tuple[str, ...]) -> tuple[dict, dict]:
    """Naloz vse in sproti povej, kje si. Racun je zanemarljiv, cas je prenos."""
    CENE, SIG = {}, {}
    with st.status("Nalagam podatke", expanded=True) as sts:
        vrstica = st.empty()
        bar = st.progress(0.0)
        for i, k in enumerate(kljuci):
            vrstica.write(f"**{k}** — {UNIVERSE[k].yahoo} · {UNIVERSE[k].name[:44]}")
            CENE[k] = _cena(k)
            SIG[k] = _signal(k)
            bar.progress((i + 1) / len(kljuci))
        vrstica.empty()
        bar.empty()
        naj = min(CENE[k].index.min() for k in kljuci)
        sts.update(label=f"Naloženo {len(kljuci)} skladov, najstarejši od {naj.date()}",
                   state="complete", expanded=False)
    return CENE, SIG


# ── racun ─────────────────────────────────────────────────────────────────────

def _ppy(idx) -> float:
    """Trgovalnih dni na leto, prestetih iz indeksa in ne vzetih iz konstante.

    252 je pravilno za eno borzo, ta indeks pa je UNIJA koledarjev: dan, ki je
    britanski praznik in nemski trgovalni dan, je v uniji. Izmerjeno je 256,2 za
    Portfelj 1 in 256,0 za Portfelj 2. Razlika je majhna — Sharpe 0,501 proti
    0,505 — a je iste vrste kot 365 proti 252, in tam je bila velika. Bolje je
    prestet kot predpostaviti.
    """
    let = (idx[-1] - idx[0]).days / 365.25
    return len(idx) / let if let > 0 else float(PPY)


def _metrike(r: np.ndarray, ppy: float = PPY) -> dict:
    eq = np.cumprod(1 + r)
    dd = eq / np.maximum.accumulate(eq) - 1
    vol = r.std() * np.sqrt(ppy)
    dn = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(ppy)
    return {
        "skupaj": (eq[-1] - 1) * 100,
        "letno": (eq[-1] ** (ppy / len(r)) - 1) * 100,
        "vol": vol * 100,
        "sharpe": r.mean() * ppy / vol if vol > 0 else float("nan"),
        "sortino": r.mean() * ppy / dn if dn > 0 else float("nan"),
        "maxdd": dd.min() * 100,
    }


def _knjiga(idx, CENE, SIG, utezi, bps, uravnavaj, vsak_n_mesecev=1):
    """Vsaka nalozba je znesek. Vrne (donosi, provizije, koncna, pot).

    Enaka oblika kot na kripto strani: provizija se odsteje ZNOTRAJ dnevnega
    faktorja, torej E x (1 + p*r - t*f), ker je to oblika, ki jo uporablja
    `shared/costs.py` in s katero so izracunane vse dosedanje tabele.
    """
    E = {k: 100.0 * w for k, w in utezi.items()}
    zgod = [sum(E.values())]
    prov = {"signali": 0.0, "uravnavanje": 0.0}
    _s = pd.Series(idx, index=idx)
    _mes = sorted(_s.groupby([idx.year, idx.month]).last())
    konci = set(_mes[vsak_n_mesecev - 1::vsak_n_mesecev])
    P = {k: (SIG[k][0].reindex(idx), SIG[k][1].reindex(idx).fillna(0.0)) for k in SIG}
    RT = {k: CENE[k]["close"].pct_change().reindex(idx).fillna(0.0) for k in CENE}

    for i, t in enumerate(idx):
        for k in utezi:
            p = P[k][0].iloc[i]
            if pd.isna(p):
                continue                    # sklad se nima signala, nalozba caka
            tr = P[k][1].iloc[i]
            prov["signali"] += E[k] * tr * bps / 10000
            E[k] *= 1 + p * RT[k].iloc[i] - tr * bps / 10000
        if uravnavaj and (t in konci) and i < len(idx) - 1:
            sk = sum(E.values())
            c = sum(abs(E[k] - utezi[k] * sk) for k in utezi) * bps / 10000
            prov["uravnavanje"] += c
            sk -= c
            E = {k: utezi[k] * sk for k in utezi}
        zgod.append(sum(E.values()))

    v = np.array(zgod)
    return v[1:] / v[:-1] - 1, prov, v[-1], v


def _kupi_drzi(idx, CENE, utezi):
    """Kupis na dan vstopa in se nikoli ne dotaknes. Sklad, ki na dan vstopa se
    ne obstaja, pocaka v gotovini in se kupi na svoj prvi dan."""
    E = {k: 100.0 * w for k, w in utezi.items()}
    zac = {k: None for k in utezi}
    zgod = [sum(E.values())]
    for t in idx:
        for k in utezi:
            c = CENE[k]["close"]
            if t not in c.index or pd.isna(c.loc[t]):
                continue
            if zac[k] is None:
                zac[k] = float(c.loc[t])
                continue                    # kupimo na zakljucek, rast sele jutri
            E[k] = 100.0 * utezi[k] * float(c.loc[t]) / zac[k]
        zgod.append(sum(E.values()))
    v = np.array(zgod)
    return v[1:] / v[:-1] - 1, v


def _eno_kupi_drzi(idx, cene):
    c = cene["close"]
    c = c.reindex(c.index.union(idx)).ffill().reindex(idx)
    if pd.isna(c.iloc[0]):
        return np.zeros(len(idx)), np.full(len(idx) + 1, 100.0)
    c = c / c.iloc[0] * 100.0
    v = np.concatenate([[100.0], c.to_numpy(float)])
    return v[1:] / v[:-1] - 1, v


# ── izris ─────────────────────────────────────────────────────────────────────

BARVE = {
    "uravnavana": "#17646D", "puščena": "#5FB6BE", "merilo strategija": "#B8860B",
    "sestava B&H": "#7E8B93", "merilo B&H": "#A63A28", "druga knjiga": "#6B5B95",
    "druga strategija": "#9B7EBD", "statični": "#C08A2E",
}


def _postavi(fig, visina=340, naslov=""):
    fig.update_layout(
        height=visina, title=naslov, template="plotly_white",
        margin=dict(l=10, r=10, t=40 if naslov else 10, b=10),
        hovermode="x unified", legend=dict(orientation="h", yanchor="bottom",
                                           y=1.02, xanchor="left", x=0),
        paper_bgcolor="white", plot_bgcolor="white",
    )
    fig.update_xaxes(showgrid=True, gridcolor="#EEF2F4")
    fig.update_yaxes(showgrid=True, gridcolor="#EEF2F4")
    return fig


def _podvodni(pot: np.ndarray) -> np.ndarray:
    return (pot / np.maximum.accumulate(pot) - 1) * 100


def _najhujsi_padci(idx, pot: np.ndarray, n: int = 5) -> pd.DataFrame:
    dd = pot / np.maximum.accumulate(pot) - 1
    x = [idx[0] - pd.Timedelta(days=1)] + list(idx)
    v = dd < -1e-12
    epizode, zac = [], None
    for i, f in enumerate(v):
        if f and zac is None:
            zac = i
        elif not f and zac is not None:
            epizode.append((zac, i))
            zac = None
    if zac is not None:
        epizode.append((zac, None))
    vrst = []
    for a, b in epizode:
        seg = dd[a:(b if b is not None else len(dd))]
        g = float(seg.min())
        if g > -0.02:
            continue
        dno = a + int(np.argmin(seg))
        vrh = int(np.argmax(pot[:a])) if a > 0 else 0
        vrst.append({
            "od": x[vrh].date(), "dno": x[dno].date(),
            "okrevano": x[b].date() if b is not None else None,
            "globina": g * 100,
            "dni do dna": (x[dno] - x[vrh]).days,
            "dni do okrevanja": (x[b] - x[dno]).days if b is not None else None,
        })
    if not vrst:
        return pd.DataFrame()
    return pd.DataFrame(vrst).sort_values("globina").head(n).reset_index(drop=True)


def _kotalec(r: np.ndarray, idx, okno: int = PPY):
    s = pd.Series(r, index=idx)
    m = s.rolling(okno).mean() * PPY
    v = s.rolling(okno).std() * np.sqrt(PPY)
    return m / v.replace(0, np.nan)


def _mesecna_karta(r: np.ndarray, idx) -> go.Figure:
    s = pd.Series(r, index=idx)
    m = (1 + s).groupby([idx.year, idx.month]).prod() - 1
    t = m.unstack() * 100
    t.columns = [pd.Timestamp(2000, c, 1).strftime("%b") for c in t.columns]
    fig = go.Figure(go.Heatmap(
        z=t.values, x=list(t.columns), y=[str(i) for i in t.index],
        colorscale=[[0, "#A63A28"], [0.5, "#FFFFFF"], [1, "#2C6E4B"]], zmid=0,
        text=np.round(t.values, 1), texttemplate="%{text}", showscale=False))
    return _postavi(fig, visina=max(220, 34 * len(t)), naslov="Mesečni donos, %")


# ── stran ─────────────────────────────────────────────────────────────────────

def main() -> None:
    st.title("Sestava ETF proti svetovnemu indeksu")
    st.caption(
        "Pogoji za nakup in prodajo so **nespremenjeni** glede na kripto stran: "
        "privzeti `LeanConfig`, trackline 75, MA 50 in 200, vstopni pas 3 %, "
        "izstopna milost 3 dni, trajno dno 5 %. Nič ni prilagojeno delnicam ali "
        "davku — to je demo, ne predlog."
    )

    vsi = tuple(UNIVERSE)
    CENE, SIG = _nalozi(vsi)

    with st.expander("Od kdaj so podatki"):
        vr = []
        for k in vsi:
            vr.append({
                "sklad": k, "oznaka": UNIVERSE[k].yahoo,
                "kotira od": UNIVERSE[k].inception,
                "uporabno od": UNIVERSE[k].usable_from,
                "cene od": str(CENE[k].index.min().date()),
                "signal od": str(SIG[k][2].index.min().date()),
                "palic": len(CENE[k]),
            })
        st.dataframe(pd.DataFrame(vr).set_index("sklad"), width="stretch")
        st.caption(
            "**kotira od** je prvi dan, ki ga Yahoo sploh ima. **uporabno od** je prvi "
            "dan, ki mu verjamem: pred tem se zaključek ponavlja ob ničelnem prometu "
            "(IWDA.L na 78 % dni v 2009, EUNA.DE na 21 % v 2018), kar so cene, po "
            "katerih nihče ne bi mogel izpolniti naročila. **signal od** je približno "
            "devet mesecev pozneje, ker mora 200-dnevno povprečje najprej obstajati. "
            "Knjiga se začne, ko ima signal **zadnji** njen član: Portfelj 1 ga omejuje "
            "SmallCap, Portfelj 2 pa GlobAgg.")

    # Izbirnik knjige stoji v GLAVNI vrstici in ne v stranski. V stranski ga ni
    # bilo mogoce najti, kadar je bila zaprta, in prav to se je zgodilo.
    knjiga = st.radio("Katero sestavo poganjamo", ["Portfelj 1", "Portfelj 2"],
                      horizontal=True, key="knjiga")
    pf = "P1" if knjiga.endswith("1") else "P2"
    druga = "P2" if pf == "P1" else "P1"
    clani = list(PORTFOLIOS[pf])
    st.caption("**" + pf + "**: "
               + " · ".join(f"{k} {PORTFOLIOS[pf][k]:.0%}" for k in clani)
               + f"   |   druga sestava **{druga}** je spodaj kot primerjava, "
                 "tudi z algoritmom")

    with st.sidebar:
        st.header("Nastavitve")

        kon_max = min(CENE[k].index[-1] for k in clani).date()
        zac_min = max(SIG[k][0].index[0] for k in clani).date()
        st.caption(f"Ta knjiga ima signal od **{zac_min}** — omejuje jo "
                   + ", ".join(k for k in clani if SIG[k][0].index[0].date() == zac_min))

        c1, c2 = st.columns(2)
        vstop = c1.date_input("Vstop", value=zac_min, min_value=zac_min,
                              max_value=kon_max - pd.Timedelta(days=120))
        izstop = c2.date_input("Izstop", value=kon_max, min_value=zac_min,
                               max_value=kon_max)

        st.divider()
        bps = st.slider("Provizija in zdrs, bazičnih točk na posel", 0, 60, 20, 5,
                        help="20 = 0,20 % na posel, torej 0,40 % na cel obrat")
        POGOSTOST = {"mesečno": 1, "četrtletno": 3, "polletno": 6, "letno": 12}
        pog_ime = st.selectbox("Kako pogosto uravnavati nazaj na ciljne uteži",
                               list(POGOSTOST), index=3,
                               help="Druga vrstica v tabeli je vedno različica "
                                    "brez uravnavanja, da imaš primerjavo.")
        pog = POGOSTOST[pog_ime]

        st.divider()
        st.caption("Uteži v odstotkih, skupaj naj bo 100")
        utezi_in = {}
        for k in clani:
            utezi_in[k] = st.number_input(
                f"{k} — {UNIVERSE[k].name[:38]}",
                0, 100, int(round(PORTFOLIOS[pf][k] * 100)), 1, key=f"w_{pf}_{k}")

    utezi = {k: v / 100.0 for k, v in utezi_in.items() if v > 0}
    if not utezi:
        st.error("Vse uteži so nič.")
        st.stop()
    vsota = sum(utezi.values())
    if abs(vsota - 1.0) > 1e-9:
        st.warning(f"Uteži se seštejejo v {vsota*100:.0f} %, ne 100 %. Preračunano sorazmerno.")
        utezi = {k: v / vsota for k, v in utezi.items()}

    zac = pd.Timestamp(vstop, tz="UTC")
    kon = pd.Timestamp(izstop, tz="UTC")
    skupni = None
    for k in utezi:
        i = CENE[k].loc[zac:kon].index
        skupni = i if skupni is None else skupni.union(i)
    idx = skupni
    if len(idx) < 60:
        st.error("Izbrano obdobje je prekratko, izberi vsaj tri mesece.")
        st.stop()

    r_ura, prov_ura, _, pot_ura = _knjiga(idx, CENE, SIG, utezi, bps, True, pog)
    r_pus, prov_pus, _, pot_pus = _knjiga(idx, CENE, SIG, utezi, bps, False)
    r_mer, prov_mer, _, pot_mer = _knjiga(idx, CENE, SIG, {MERILO: 1.0}, bps, False)
    r_kd, pot_kd = _kupi_drzi(idx, CENE, utezi)
    r_bh, pot_bh = _eno_kupi_drzi(idx, CENE[MERILO])
    w2 = PORTFOLIOS[druga]
    r_d2, pot_d2 = _kupi_drzi(idx, CENE, w2)
    # Druga knjiga tudi PO STRATEGIJI, ne le kupi in drzi. Brez tega stran
    # pokaze algoritem samo na eni sestavi naenkrat, drugo pa le kot pasivno
    # primerjavo — in prav vprasanje "kje sta sploh obe sestavi z algoritmom"
    # je pokazalo, da je to narobe postavljeno.
    r_s2, _, _, pot_s2 = _knjiga(idx, CENE, SIG, w2, bps, True, pog)

    # Staticni delez z ISTO povprecno izpostavljenostjo. To je najostrejsa
    # primerjava, ki obstaja: vsaka obrambna strategija polepsa razmerja ze s
    # tem, da je manj v trgu, in samo ta vrstica loci vescino od odsotnosti.
    # Altcoinsko porocilo je isti test uporabilo kot glavni dokaz, da lean na
    # BTC dela; tu ga je posteno pokazati tudi takrat, ko odgovor ni tak.
    izp = float(np.mean([SIG[k][0].reindex(idx).fillna(0.0).mean() for k in utezi]))
    r_stat = r_kd * izp
    pot_stat = np.concatenate([[100.0], 100.0 * np.cumprod(1 + r_stat)])

    ppy = _ppy(idx)
    IME_URA = f"sestava, uravnavana {pog_ime}"
    VRSTE = [(IME_URA, r_ura, pot_ura, "uravnavana"),
             ("sestava, puščena", r_pus, pot_pus, "puščena"),
             (f"sam {MERILO}, strategija", r_mer, pot_mer, "merilo strategija"),
             (f"statičnih {izp*100:.0f} % sestave, brez signala", r_stat, pot_stat, "statični"),
             ("sestava, kupi in drži", r_kd, pot_kd, "sestava B&H"),
             (f"sam {MERILO}, kupi in drži", r_bh, pot_bh, "merilo B&H"),
             (f"{druga}, strategija", r_s2, pot_s2, "druga strategija"),
             (f"{druga}, kupi in drži", r_d2, pot_d2, "druga knjiga")]

    st.subheader(f"{knjiga}: {idx[0].date()} do {idx[-1].date()}, {len(idx)} trgovalnih dni")
    st.caption(f"Provizija in zdrs {bps/100:.2f} % na posel. Uravnavanje {pog_ime}. "
               f"Vsak sklad trguje po svojem signalu, neodvisno od ostalih. "
               f"Letno preračunavanje s {ppy:.1f} dnevi, prešteto iz indeksa: unija "
               f"koledarjev LSE, Xetre in Euronexta ima nekaj dni več kot ena sama borza.")
    manjka = [k for k in utezi if SIG[k][0].index[0] > zac]
    if manjka:
        st.caption("Ti skladi na dan vstopa še nimajo signala in njihova naložba "
                   "počaka v gotovini: " + ", ".join(
                       f"{k} od {SIG[k][0].index[0].date()}" for k in manjka))

    vrstice = []
    for ime, r, pot, kljuc in VRSTE:
        m = _metrike(r, ppy)
        m["calmar"] = m["letno"] / abs(m["maxdd"]) if m["maxdd"] else float("nan")
        vrstice.append(m)
    tab = pd.DataFrame(vrstice, index=[v[0] for v in VRSTE])
    st.dataframe(
        tab.style.format({"skupaj": "{:.0f} %", "letno": "{:.1f} %", "vol": "{:.1f} %",
                          "sharpe": "{:.2f}", "sortino": "{:.2f}", "maxdd": "{:.0f} %",
                          "calmar": "{:.2f}"})
           .highlight_max(subset=["skupaj", "letno", "sharpe", "sortino", "maxdd", "calmar"],
                          props="background-color:#c6f6d5; color:#111; font-weight:700"),
        width="stretch")
    st.caption(
        "**vol** je letna volatilnost. **calmar** je letni donos deljen z največjim padcem. "
        "Zeleno je najboljša vrednost v stolpcu. Pri delnicah je letno preračunavanje s "
        "252 dnevi in ne s 365 kot pri kriptu; s 365 bi bili vol, Sharpe in Sortino "
        "previsoki za faktor 1,20. " + chr(10) + chr(10) +
        "**Vrstica „statičnih X %" + chr(34) + "** je knjiga, držana s stalnim deležem, ki je enak "
        "povprečni izpostavljenosti strategije, ostalo v gotovini pri nič. Je "
        "najostrejša primerjava, ki obstaja: vsaka obrambna strategija polepša razmerja "
        "že s tem, da je manj v trgu, in šele ta vrstica loči veščino od odsotnosti.")

    c1, c2, c3 = st.columns(3)
    m_te = _metrike(r_ura, ppy)
    m_dr = _metrike(r_s2, ppy)
    m_kd = _metrike(r_kd, ppy)
    c1.metric(f"{pf} z algoritmom, letno", f"{m_te['letno']:.2f} %",
              f"{m_te['letno'] - m_kd['letno']:+.2f} pp proti kupi in drži")
    c2.metric(f"{druga} z algoritmom, letno", f"{m_dr['letno']:.2f} %",
              help="Ista strategija, druga sestava, isto obdobje in isti stroški.")
    c3.metric(f"{pf} z algoritmom, MaxDD", f"{m_te['maxdd']:.1f} %",
              f"{m_te['maxdd'] - m_kd['maxdd']:+.1f} pp proti kupi in drži",
              delta_color="inverse")
    st.caption(
        "Obe sestavi sta izračunani na **istem oknu**, ki ga določa izbrana knjiga. "
        "Zato se številka za isto sestavo premakne, ko zamenjaš izbiro: Portfelj 2 ima "
        "signal šele od 2019-10-11, Portfelj 1 pa od 2019-01-08, in primerjava vedno "
        "teče od poznejšega od obeh datumov izbrane knjige.")

    t1, t2, t3, t4, t5 = st.tabs(
        ["Krivulja in padci", "Skozi čas", "Skladi", "Občutljivost na vstop", "Stroški"])

    with t1:
        x = [idx[0] - pd.Timedelta(days=1)] + list(idx)
        fig = go.Figure()
        for ime, r, pot, kljuc in VRSTE:
            trdna = kljuc in ("uravnavana", "puščena", "merilo strategija",
                              "druga strategija")
            fig.add_trace(go.Scatter(
                x=x, y=pot, name=ime, line=dict(color=BARVE[kljuc], width=2 if trdna else 1.4,
                                                dash=None if trdna else "dot"),
                visible=True if trdna else "legendonly"))
        _postavi(fig, 420, "Vrednost 100 enot ob vstopu")
        fig.update_yaxes(type="log")
        st.plotly_chart(fig, width="stretch")
        st.caption("Kupi in drži so ob odprtju skriti. Klikni jih v legendi, da se "
                   "prikažejo. Os je logaritemska, zato je enak navpični odmik enak "
                   "odstotek povsod.")

        fig2 = go.Figure()
        for ime, r, pot, kljuc in VRSTE:
            if kljuc not in ("uravnavana", "merilo strategija", "merilo B&H"):
                continue
            fig2.add_trace(go.Scatter(x=x, y=_podvodni(pot), name=ime, fill="tozeroy",
                                      line=dict(color=BARVE[kljuc], width=1.2)))
        _postavi(fig2, 260, "Pod vodo, % od vrha")
        st.plotly_chart(fig2, width="stretch")

        pad = _najhujsi_padci(idx, pot_ura)
        if len(pad):
            st.markdown("**Najhujši padci uravnavane sestave**")
            st.dataframe(pad.style.format({"globina": "{:.1f} %"}), width="stretch")
            st.caption("Stolpec **dni do okrevanja** je tisti, ki ga en sam MaxDD skrije.")

        st.plotly_chart(_mesecna_karta(r_ura, idx), width="stretch")

    with t2:
        okno = st.slider("Okno za kotaleče mere, trgovalnih dni", 63, 756, PPY, 21)
        fig = go.Figure()
        for ime, r, pot, kljuc in VRSTE:
            if kljuc in ("puščena", "sestava B&H", "druga knjiga"):
                continue                       # obe strategiji ostaneta
            fig.add_trace(go.Scatter(x=idx, y=_kotalec(r, idx, okno), name=ime,
                                     line=dict(color=BARVE[kljuc], width=1.6)))
        fig.add_hline(y=0, line_color="#B4C3C9", line_width=1)
        _postavi(fig, 340, f"Kotaleči Sharpe, okno {okno} dni")
        st.plotly_chart(fig, width="stretch")

        s_u = pd.Series(r_ura, index=idx)
        s_m = pd.Series(r_bh, index=idx)
        beta = (s_u.rolling(okno).cov(s_m) / s_m.rolling(okno).var())
        fig = go.Figure(go.Scatter(x=idx, y=beta, name="beta proti merilu",
                                   line=dict(color=BARVE["uravnavana"], width=1.6)))
        fig.add_hline(y=1.0, line_color="#A63A28", line_width=1, line_dash="dot")
        _postavi(fig, 300, f"Kotaleča beta proti {MERILO}, okno {okno} dni")
        st.plotly_chart(fig, width="stretch")
        st.caption("Rdeča črta je beta 1,0, torej isto gibanje kot merilo. Nižje pomeni, "
                   "da sestava sledi manj.")

    with t3:
        vrst = []
        for k in utezi:
            p, tr, df = SIG[k]
            p = p.reindex(idx)
            c = CENE[k]["close"].reindex(idx).ffill()
            rr = c.pct_change().fillna(0.0)
            sam = float((1 + rr).prod() - 1) * 100
            m = _metrike((p.fillna(0.0) * rr).to_numpy())
            vrst.append({
                "sklad": k, "ISIN": UNIVERSE[k].isin, "utež %": utezi[k] * 100,
                "sam, cel kapital %": sam,
                "v trgu %": float(p.mean(skipna=True) * 100),
                "vstopov": int(df["signal_changed"].reindex(idx).fillna(False).sum()),
                "signal letno %": m["letno"], "signal maxdd %": m["maxdd"],
            })
        pr = pd.DataFrame(vrst).set_index("sklad")
        st.dataframe(pr.style.format({
            "utež %": "{:.0f}", "sam, cel kapital %": "{:+.0f}", "v trgu %": "{:.0f}",
            "signal letno %": "{:+.1f}", "signal maxdd %": "{:.0f}"}), width="stretch")
        st.caption("**sam, cel kapital** je donos sklada, če bi vanj vložil vse in nič ne "
                   "trgoval. **signal letno** je donos, ki ga da lean na tem skladu.")

        px = pd.DataFrame({k: CENE[k]["close"].reindex(idx).ffill() for k in utezi})
        korel = px.pct_change().corr()
        fig = go.Figure(go.Heatmap(
            z=korel.values, x=list(korel.columns), y=list(korel.index),
            colorscale=[[0, "#FFFFFF"], [1, "#A63A28"]], zmin=0, zmax=1,
            text=np.round(korel.values, 2), texttemplate="%{text}", showscale=False))
        _postavi(fig, 60 + 34 * len(korel), "Korelacija dnevnih donosov")
        st.plotly_chart(fig, width="stretch")

    with t4:
        st.caption("Vsak možen vstop na 30 dni, vsi do istega izstopa. To vnaprej "
                   "odgovori na vprašanje, ali je rezultat odvisen od enega datuma.")
        koraki = list(range(0, max(len(idx) - 4 * PPY, 1), 30))
        if len(koraki) < 3:
            st.info("Za to vajo je izbrano obdobje prekratko.")
        else:
            vrst = []
            for k0 in koraki:
                sub = idx[k0:]
                ru, _, _, _ = _knjiga(sub, CENE, SIG, utezi, bps, True, pog)
                rb, _ = _eno_kupi_drzi(sub, CENE[MERILO])
                mu, mb = _metrike(ru), _metrike(rb)
                vrst.append({"vstop": sub[0].date(), "sestava Sharpe": mu["sharpe"],
                             f"{MERILO} Sharpe": mb["sharpe"],
                             "sestava letno %": mu["letno"], f"{MERILO} letno %": mb["letno"]})
            ob = pd.DataFrame(vrst).set_index("vstop")
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=ob.index, y=ob["sestava Sharpe"], name="sestava",
                                     line=dict(color=BARVE["uravnavana"], width=2)))
            fig.add_trace(go.Scatter(x=ob.index, y=ob[f"{MERILO} Sharpe"], name=MERILO,
                                     line=dict(color=BARVE["merilo B&H"], width=1.6, dash="dot")))
            _postavi(fig, 340, "Sharpe glede na datum vstopa")
            st.plotly_chart(fig, width="stretch")
            zmag = float((ob["sestava Sharpe"] > ob[f"{MERILO} Sharpe"]).mean() * 100)
            st.metric("Delež vstopnih datumov, kjer sestava premaga merilo po Sharpu",
                      f"{zmag:.0f} %")
            st.dataframe(ob.style.format("{:.2f}"), width="stretch")

    with t5:
        st.markdown("**Kam gredo provizije**")
        raz = pd.DataFrame({
            IME_URA: prov_ura, "sestava, puščena": prov_pus,
            f"sam {MERILO}": prov_mer}).T
        raz["skupaj"] = raz.sum(axis=1)
        raz["na leto"] = raz["skupaj"] / (len(idx) / PPY)
        st.dataframe(raz.style.format("{:.2f}"), width="stretch")
        st.caption("Enote so odstotki začetnega kapitala 100. "
                   f"{bps/100:.2f} % na posel je predpostavka, ne izmerjena vrednost.")

        st.markdown("**Občutljivost na provizijo**")
        vrst = []
        for b in (0, 10, 20, 30, 40, 60):
            ru, _, _, _ = _knjiga(idx, CENE, SIG, utezi, b, True, pog)
            m = _metrike(ru)
            vrst.append({"bps na posel": b, "letno %": m["letno"], "Sharpe": m["sharpe"],
                         "Sortino": m["sortino"], "maxdd %": m["maxdd"]})
        t = pd.DataFrame(vrst).set_index("bps na posel")
        st.dataframe(t.style.format({"letno %": "{:+.2f}", "Sharpe": "{:.2f}",
                                     "Sortino": "{:.2f}", "maxdd %": "{:.0f}"}),
                     width="stretch")
        raz_l = t.loc[0, "letno %"] - t.loc[60, "letno %"]
        st.caption(f"Med brezplačnim trgovanjem in 0,60 % na posel je razlika "
                   f"{raz_l:.2f} odstotne točke letnega donosa.")

        st.warning(
            "**Davek v tej številki ni.** Na navadnem računu je za to knjigo približno "
            "1,2 do 1,8 odstotne točke letno, in vsaka prodaja ponastavi uro dobe "
            "imetja. Izračun je v `testing/scripts/etf_davek.py`, ta stran ga ne "
            "upošteva.", icon="⚠️")


if __name__ == "__main__":
    main()
