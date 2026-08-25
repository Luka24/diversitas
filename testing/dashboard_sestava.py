"""Sestava proti samemu BTC, z izbirnim datumom vstopa.

    streamlit run testing/dashboard_sestava.py

Racun vodi DENAR po rokavih, ne donosov. Vsak rokav je znesek, ki se veca in
manjsa, provizije se odbijejo od zneska, metrike pa se izracunajo sele iz poti
skupne vrednosti. To je ista koda, s katero je bila tabela v porocilu
preverjena, in ne tista, ki je strosek uravnavanja odstela od donosa, ne pa
tudi od rokavov.
"""
from __future__ import annotations

import sys
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "lean"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

from diversitas.config import LeanConfig
from diversitas.strategy import position, run_strategy, traded_fraction
from shared.data_source import DEFAULT_SYMBOL_MAP, fetch_candles
from shared.warmup import trim_warmup

PPY = 365
# BNB in XRP z Binance: Coinbase ima BNB sele od 2025-10, XRP pa je bil med
# 2021 in 2023 umaknjen, torej bi manjkala prav leta, ki nas zanimajo.
BINANCE = {"BNB": "BNBUSDT", "XRP": "XRPUSDT"}

st.set_page_config(page_title="Sestava proti BTC", layout="wide")


@st.cache_data(ttl=3600, show_spinner=False)
def _binance(sym: str) -> pd.DataFrame:
    out, start = [], 1_400_000_000_000
    while True:
        r = requests.get(
            "https://api.binance.com/api/v3/klines", timeout=30,
            params={"symbol": sym, "interval": "1d", "startTime": start, "limit": 1000},
        ).json()
        if not r:
            break
        out += r
        if len(r) < 1000:
            break
        start = r[-1][0] + 86_400_000
        time.sleep(0.2)
    d = pd.DataFrame(out, columns=["t", "open", "high", "low", "close", "volume"] + ["x"] * 6)
    d["time"] = pd.to_datetime(d["t"], unit="ms", utc=True)
    return d.set_index("time")[["open", "high", "low", "close", "volume"]].astype(float)


@st.cache_data(ttl=3600, show_spinner=False)
def _cene(simboli: tuple[str, ...]) -> dict:
    sm = dict(DEFAULT_SYMBOL_MAP)
    sm["HYPE"] = {"hyperliquid": "HYPE"}
    cfg = replace(LeanConfig(), symbol_map=sm)
    out = {}
    for s in simboli:
        if s in BINANCE:
            out[s] = _binance(BINANCE[s])
        else:
            vir = "hyperliquid" if s == "HYPE" else "coinbase"
            out[s] = fetch_candles(s, "1d", bars=5000, config=cfg, prefer=vir, strict=True)
    return out


@st.cache_data(ttl=3600, show_spinner=False)
def _signali(simboli: tuple[str, ...], _cene_d: dict) -> dict:
    sm = dict(DEFAULT_SYMBOL_MAP)
    sm["HYPE"] = {"hyperliquid": "HYPE"}
    cfg = replace(LeanConfig(), symbol_map=sm)
    out = {}
    for s in simboli:
        df = trim_warmup(run_strategy(_cene_d[s], config=cfg).df)
        out[s] = (position(df, cfg), traded_fraction(df, cfg).fillna(0.0))
    return out


def _metrike(r: np.ndarray) -> dict:
    eq = np.cumprod(1 + r)
    dd = eq / np.maximum.accumulate(eq) - 1
    vol = r.std() * np.sqrt(PPY)
    dn = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(PPY)
    return {
        "skupaj": (eq[-1] - 1) * 100,
        "letno": (eq[-1] ** (PPY / len(r)) - 1) * 100,
        "vol": vol * 100,
        "sharpe": r.mean() * PPY / vol if vol > 0 else float("nan"),
        "sortino": r.mean() * PPY / dn if dn > 0 else float("nan"),
        "maxdd": dd.min() * 100,
    }


def _knjiga(idx, CENE, SIG, utezi, bps, uravnavaj, sesto_od):
    """Rokavi kot zneski. Vrne pot vrednosti in razclenjene provizije."""
    E = {k: 100.0 * w for k, w in utezi.items()}
    zgod = [sum(E.values())]
    prov = {"signali": 0.0, "uravnavanje": 0.0, "zamenjava": 0.0}
    ima_sesto = "SESTO" in utezi
    prej6 = None
    if ima_sesto:
        prej6 = "HYPE" if (sesto_od is not None and idx[0] >= sesto_od) else "XRP"
    _s = pd.Series(idx, index=idx)
    konci = set(_s.groupby([idx.year, idx.month]).last())
    P = {s: (SIG[s][0].reindex(idx), SIG[s][1].reindex(idx).fillna(0.0)) for s in SIG}
    RT = {s: CENE[s]["close"].pct_change().reindex(idx).fillna(0.0) for s in CENE}

    for i, t in enumerate(idx):
        s6 = None
        if ima_sesto:
            s6 = "HYPE" if (sesto_od is not None and t >= sesto_od) else "XRP"
            if s6 != prej6:
                c = E["SESTO"] * 2 * bps / 10000
                E["SESTO"] -= c
                prov["zamenjava"] += c
                prej6 = s6
        for k in utezi:
            s = s6 if k == "SESTO" else k
            p = P[s][0].iloc[i]
            if pd.isna(p):
                continue                       # sredstvo se nima signala, rokav caka
            # Provizija je odsteta ZNOTRAJ dnevnega faktorja, ne pred njim, torej
            # E x (1 + p*r - t*f) in ne (E - E*t*f) x (1 + p*r). Razlika je le
            # krizni clen t*f*p*r, a to je oblika, ki jo uporablja shared/costs.py
            # in z njo so izracunane vse dosedanje tabele. Kontrola "sam BTC prek
            # knjige proti neposrednemu izracunu" je prej odstopala za 0,07 %.
            tr = P[s][1].iloc[i]
            prov["signali"] += E[k] * tr * bps / 10000
            E[k] *= 1 + p * RT[s].iloc[i] - tr * bps / 10000
        if uravnavaj and (t in konci) and i < len(idx) - 1:
            sk = sum(E.values())
            c = sum(abs(E[k] - utezi[k] * sk) for k in utezi) * bps / 10000
            prov["uravnavanje"] += c
            sk -= c
            E = {k: utezi[k] * sk for k in utezi}
        zgod.append(sum(E.values()))

    v = np.array(zgod)
    return v[1:] / v[:-1] - 1, prov, v[-1], v


def main() -> None:
    st.title("Sestava proti samemu BTC")
    st.caption(
        "Uteži se postavijo na dan vstopa. Vsako sredstvo nato trguje po svojem "
        "signalu, neodvisno od ostalih. Provizije se obračunajo po dejanski "
        "vrednosti rokava tistega dne, ne po številu poslov."
    )

    with st.sidebar:
        st.header("Nastavitve")
        vsi = ["BTC", "ETH", "SOL", "LINK", "BNB", "HYPE", "XRP"]
        CENE = _cene(tuple(vsi))
        SIG = _signali(tuple(vsi), CENE)
        kon_max = min(d.index[-1] for d in CENE.values()).date()
        zac_min = SIG["BTC"][0].index[0].date()

        c1, c2 = st.columns(2)
        vstop = c1.date_input("Vstop", value=pd.Timestamp("2021-01-01").date(),
                              min_value=zac_min, max_value=kon_max - pd.Timedelta(days=120))
        izstop = c2.date_input("Izstop", value=kon_max,
                               min_value=zac_min, max_value=kon_max)

        st.divider()
        bps = st.slider("Provizija in zdrs, bazičnih točk na stran", 0, 60, 30, 5,
                        help="30 = 0,30 % na stran, torej 0,60 % na cel obrat")
        uravnavaj = st.checkbox("Mesečno uravnavanje nazaj na ciljne uteži", value=True)

        st.divider()
        st.caption("Uteži v odstotkih, skupaj naj bo 100")
        w_btc = st.number_input("BTC", 0, 100, 50, 5)
        w_eth = st.number_input("ETH", 0, 100, 10, 5)
        st.caption("SOL")
        w_sol = st.number_input("SOL", 0, 100, 10, 5, label_visibility="collapsed")
        w_link = st.number_input("LINK", 0, 100, 10, 5)
        w_bnb = st.number_input("BNB", 0, 100, 10, 5)
        w_6 = st.number_input("Šesto mesto: XRP, nato HYPE", 0, 100, 10, 5)

    utezi = {"BTC": w_btc, "ETH": w_eth, "SOL": w_sol,
             "LINK": w_link, "BNB": w_bnb, "SESTO": w_6}
    utezi = {k: v / 100.0 for k, v in utezi.items() if v > 0}
    vsota = sum(utezi.values())
    if abs(vsota - 1.0) > 1e-9:
        st.warning(f"Uteži se seštejejo v {vsota*100:.0f} %, ne 100 %. "
                   f"Preračunano sorazmerno.")
        utezi = {k: v / vsota for k, v in utezi.items()}

    zac = pd.Timestamp(vstop, tz="UTC")
    kon = pd.Timestamp(izstop, tz="UTC")
    idx = CENE["BTC"].loc[zac:kon].index
    if len(idx) < 60:
        st.error("Izbrano obdobje je prekratko, izberi vsaj dva meseca.")
        st.stop()

    sesto_od = SIG["HYPE"][0].index[0]
    r_ura, prov_ura, konc_ura, pot_ura = _knjiga(idx, CENE, SIG, utezi, bps, True, sesto_od)
    r_pus, prov_pus, konc_pus, pot_pus = _knjiga(idx, CENE, SIG, utezi, bps, False, sesto_od)
    r_btc, prov_btc, konc_btc, pot_btc = _knjiga(idx, CENE, SIG, {"BTC": 1.0}, bps, False, None)

    st.subheader(f"{idx[0].date()} do {idx[-1].date()}, {len(idx)} dni")
    if idx[-1].date() >= pd.Timestamp.now(tz="UTC").date():
        st.caption(
            "Zadnji dan je današnji in še ni zaključen, zato se te številke med "
            "dnevom premikajo. Za stabilen izpis izberi izstop na včeraj."
        )

    tab = pd.DataFrame(
        [_metrike(r_ura), _metrike(r_pus), _metrike(r_btc)],
        index=["sestava, uravnavana", "sestava, puščena", "sam BTC"],
    )
    st.dataframe(
        tab.style.format({"skupaj": "{:.0f} %", "letno": "{:.1f} %", "vol": "{:.0f} %",
                          "sharpe": "{:.2f}", "sortino": "{:.2f}", "maxdd": "{:.0f} %"})
           .highlight_max(subset=["skupaj", "letno", "sharpe", "sortino", "maxdd"],
                          color="#0e4429"),
        use_container_width=True,
    )

    fig = go.Figure()
    for ime, pot, barva in (("sestava, uravnavana", pot_ura, "#2962ff"),
                            ("sestava, puščena", pot_pus, "#ffb74d"),
                            ("sam BTC", pot_btc, "#089981")):
        fig.add_trace(go.Scatter(x=[idx[0] - pd.Timedelta(days=1)] + list(idx), y=pot,
                                 name=ime, line=dict(color=barva, width=2)))
    fig.update_layout(height=420, template="plotly_dark", yaxis_title="vrednost 100 vloženih",
                      margin=dict(l=0, r=0, t=10, b=0), legend=dict(orientation="h", y=1.08))
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Kam gre 100 vloženih enot")
    st.caption(
        "Vsaka provizija je preštета v denarju tistega dne, ko je bila plačana. "
        "Ker portfelj med potjo raste, je posel iz leta 2025 v absolutnem znesku "
        "večji od posla iz 2021."
    )
    vrst = []
    for ime, prov, konc in (("sestava, uravnavana", prov_ura, konc_ura),
                            ("sestava, puščena", prov_pus, konc_pus),
                            ("sam BTC", prov_btc, konc_btc)):
        sk = sum(prov.values())
        vrst.append({"signali": prov["signali"], "uravnavanje": prov["uravnavanje"],
                     "zamenjava": prov["zamenjava"], "skupaj": sk,
                     "končna vrednost": konc, "delež končne": sk / konc * 100})
    st.dataframe(
        pd.DataFrame(vrst, index=["sestava, uravnavana", "sestava, puščena", "sam BTC"])
          .style.format({"signali": "{:.1f}", "uravnavanje": "{:.1f}", "zamenjava": "{:.1f}",
                         "skupaj": "{:.1f}", "končna vrednost": "{:.0f}", "delež končne": "{:.1f} %"}),
        use_container_width=True,
    )
    with st.expander("Kaj pomeni vsak stolpec"):
        st.markdown(
            "**signali** so provizije od vstopov in izstopov strategije po vsakem "
            "sredstvu posebej. Ko signal reče kupi, plačaš od zneska, ki ga kupiš, "
            "in enako ob prodaji.\n\n"
            "**uravnavanje** so provizije od mesečnega vračanja na ciljne uteži. "
            "Zaračuna se samo tisto, kar se dejansko premakne: če BTC zdrsne s 50 % "
            "na 53 %, plačaš od tistih treh odstotnih točk, ne od celega portfelja.\n\n"
            "**zamenjava** je enkratna menjava XRP v HYPE na dan, ko HYPE dobi prvi "
            "signal. Prodaš ves XRP in kupiš HYPE.\n\n"
            "**delež končne** pove, koliko odstotkov končne vrednosti so pojedle "
            "provizije. Pravi ekonomski strošek je še večji, ker zgodaj plačana "
            "provizija ne raste več s portfeljem."
        )

    st.subheader("Kaj so rokavi počeli")
    zad = {}
    for k in utezi:
        s = "HYPE" if (k == "SESTO" and idx[-1] >= sesto_od) else ("XRP" if k == "SESTO" else k)
        p = SIG[s][0].reindex(idx)
        zad[k if k != "SESTO" else f"SESTO ({s})"] = {
            "sredstvo": s,
            "ciljna utež": f"{utezi[k]*100:.0f} %",
            "dni v trgu": f"{float((p > 0.5).mean()*100):.0f} %",
            "dni brez signala": f"{float(p.isna().mean()*100):.0f} %",
            "stanje danes": "V TRGU" if (not pd.isna(p.iloc[-1]) and p.iloc[-1] > 0.5) else "zunaj",
        }
    st.dataframe(pd.DataFrame(zad).T, use_container_width=True)


# Streamlit poganja skripto kot __main__, zato se stran normalno izrise. Straza
# je tu zato, da se modul da uvoziti in preizkusiti brez risanja.
if __name__ == "__main__":
    main()
