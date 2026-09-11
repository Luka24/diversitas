"""Zgradi samostojno mapo diversitas-sestava za objavo na Streamlit Cloud.

    python testing/scripts/zgradi_sestavo.py

Izvirnik se ne dotakne. Nastane kopija, v kateri sta lean/ in shared/ zdruzena
v paket model/, dashboard pa v ui/, tako da mapa deluje sama zase.

Ciljno mapo prepise. Pozeni znova, kadar se kaj spremeni.

KLJUCNA SPREMEMBA PROTI RAZISKAVI
V raziskavi sta BNB in XRP prihajala neposredno z Binancea. Binance iz
Streamlit Clouda vrne HTTP 451, ker zavraca IP naslove podatkovnih centrov,
zato v objavljeni razlicici tega vira ni. Oba gresta na Yahoo, ki ju pokriva
v celoti.

Izmerjena razlika na BNB, 3217 skupnih dni:
    povprecna razlika cen  0,063 %
    pozicija se ujema na   99,0 % dni
    Sortino                1,25 (Binance) proti 1,22 (Yahoo)
Razlika je torej majhna, ni pa nicelna, in je zapisana v README.
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CILJ = ROOT.parent / "diversitas-sestava"

KODA = {
    "lean/diversitas/__init__.py": "model/__init__.py",
    "lean/diversitas/config.py": "model/config.py",
    "lean/diversitas/strategy.py": "model/strategy.py",
    "shared/indicators.py": "model/indicators.py",
    "shared/warmup.py": "model/warmup.py",
    "shared/costs.py": "model/costs.py",
    "shared/data_source.py": "model/data_source.py",
    "testing/dashboard_sestava.py": "ui/dashboard.py",
}

# uvozi, ki morajo kazati v nov paket. Oblika "from shared import X as Y" je
# svoja vrstica, ker je regex za "from shared." ne ujame.
PREPISI = [
    (r"^from diversitas\.", "from model."),
    (r"^import diversitas\.", "import model."),
    (r"^from shared\.", "from model."),
    (r"^import shared\.", "import model."),
    (r"^from shared import ", "from model import "),
    (r"^import shared\b", "import model"),
]

APP = '''"""Vstopna tocka za Streamlit Cloud.

    streamlit run app.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ui.dashboard import main

main()
'''

# yfinance je OBVEZEN, ne izbiren. Neposredna pot na Yahoo prek requests danes
# ne dela vec, zato jo data_source.py preskoci in uporabi yfinance. Brez njega
# odpovejo BNB, XRP in SPY, torej tri od osmih sredstev. Preverjeno tako, da
# sem uvoz yfinance umetno blokiral.
#
# matplotlib NI potreben. Stran za barvanje tabel uporablja Plotly namesto
# Styler.background_gradient prav zato, da se mu izogne.
REQ = """pandas==3.0.3
numpy==2.4.6
requests==2.34.2
plotly==6.8.0
streamlit==1.58.0

# yfinance ni izbiren. Neposredna pot na Yahoo prek requests ne dela vec, zato
# jo data_source.py preskoci in uporabi tega. Brez njega odpovejo BNB, XRP in
# SPY, torej tri od osmih sredstev.
yfinance==1.4.1

# pyarrow ni nikjer uvozen, rabi pa ga streamlit za izris tabel. Pripet je zato,
# da se izid cez pol leta ne premakne zaradi njegove posodobitve.
pyarrow==24.0.0
"""

GITIGNORE = """__pycache__/
*.pyc
.pytest_cache/
.venv/
.streamlit/secrets.toml
"""

README = """# Diversitas Sestava

Kosarica sestih kripto sredstev, kjer vsako trguje po svojem signalu, primerjana
proti samemu BTC.

Privzeta razporeditev je BTC 50 % ter ETH, SOL, LINK, BNB in sesto mesto po
10 %. Utezi se dajo na strani spremeniti.

Strategija na posameznem sredstvu je ista kot v projektu **Diversitas Lean**.
Ta stran ne spreminja signala, ampak odgovarja na drugo vprasanje: ali se
splaca razporediti po vec sredstvih, ali je bolje ostati pri BTC.

## Zagon

Potrebuje **Python 3.11 ali novejsi**.

```
pip install -r requirements.txt

python scripts/preveri_vire.py     preveri knjiznice in dosegljivost virov cen
python scripts/preveri.py          preveri, da racun in izris drzita
streamlit run app.py               odpre stran
```

`preveri.py` pozene tudi celo stran brezglavo. To ujame napake, ki jih racun
sam ne more: manjkajoco knjiznico za izris, napacen tip stolpca, zlom v Plotly.
Ce ta preverba pade, stran v brskalniku ne bo delovala.

## Od kod pridejo cene

Vsako sredstvo ima **tocno en vir in nadomestnega ni**. Nadomestni vir bi tiho
spremenil vsako izracunano stevilko, zato stran raje pove, da nima podatkov.

| sredstvo | vir | zakaj ta |
|---|---|---|
| BTC, ETH, SOL, LINK | Coinbase | globoka zgodovina, isti vir kot lean |
| BNB | Yahoo | Coinbase ga ne kotira pred oktobrom 2025 |
| XRP | Yahoo | pri Coinbaseu je bil med 2021 in 2023 umaknjen |
| HYPE | Hyperliquid | drugje ga ni |
| SPY | Yahoo | za primerjavo z delnicami |

### yfinance ni izbiren

Naveden je v `requirements.txt` in mora tam ostati. Koda za Yahoo najprej
poskusi navaden HTTP klic prek `requests`, ta pa danes ne dela vec, zato pade
na `yfinance`.

Preveril sem tako, da sem uvoz `yfinance` umetno blokiral:

```
BNB   PADE: source 'yahoo' failed and strict=True
XRP   PADE: source 'yahoo' failed and strict=True
SPY   PADE: source 'yahoo' failed and strict=True
BTC   OK  4062 vrstic
```

Tri od osmih sredstev. Zato `scripts/preveri_vire.py` preveri tudi knjiznice,
ne le dosegljivost borz.

`pyarrow` prav tako ni nikjer uvozen, rabi pa ga Streamlit za izris tabel. Ne
odstranjuj ga.

### Zakaj Binancea ni

Raziskava, iz katere je ta stran nastala, je BNB in XRP jemala neposredno z
Binancea. Tu ga ni, ker iz Streamlit Clouda vrne `HTTP 451 Service unavailable
from a restricted location`. Zavraca IP naslove podatkovnih centrov, isti klic
z domacega racunalnika pa vrne 200. To ni izpad in ne bo minilo.

Razlika je izmerjena, ne ocenjena. Na BNB, 3217 skupnih dni od novembra 2017:

| | Sharpe | Sortino | letno | najhujsi padec |
|---|---|---|---|---|
| Binance | 0,83 | 1,25 | 31 % | -59 % |
| Yahoo | 0,81 | 1,22 | 30 % | -58 % |

Povprecna razlika cen je 0,063 %, mediana 0,018 %, in **pozicija se ujema na
99,0 % dni**. Razlika je torej majhna, ni pa nicelna. Ce primerjas stevilke s
starejsimi porocili iz raziskave, je to razlog za manjse odstopanje.

## Kaj stran pokaze

Zgoraj so nastavitve: datum vstopa in izstopa, utezi, provizija in zdrs,
pogostost uravnavanja, ter kdo zasede sesto mesto.

Pod njimi je glavna tabela s primerjavo sestave proti sami BTC strategiji,
proti obema kupi in drzi, ter proti S&P 500.

Nato pet zavihkov:

**Krivulja in padci** Vrednost skozi cas, graf pod vodo, in seznam najhujsih
padcev z datumom vrha, dna, okrevanja in trajanjem.

**Skozi cas** Kotaleci se Sharpe in donos po letih.

**Sredstva** Kaj prispeva vsako sredstvo posebej.

**Obcutljivost na vstop** Isti izracun pri razlicnih datumih vstopa. To je
najbolj posten pogled, ker pove, ali je rezultat odvisen od enega samega
srecnega zacetka.

**Stroski** Kam gre 100 vlozenih enot, obcutljivost na visino provizije, in
razclenitev po fazah cikla.

### Faze cikla

Faze so datirane po algoritmu Bry in Boschan v razlicici Pagan in Sossounov, ki
je akademski standard. Poisce lokalne vrhove in dna v oknu 90 dni, vsili
izmenjavanje vrh in dno, ter odvrze faze, krajse od 120 dni ali manjse od 25 %.

Meja torej ni rocno izbrana. To je pomembno, ker preprosta meja tipa cena nad
200-dnevnim povprecjem niha sem in tja in steje kratek prehod enako kot
dvoletni medvedji trg.

## Kako se racuna

Racun vodi **denar po nalozbah**, ne donosov. Vsaka nalozba je znesek, ki raste
in se manjsa, provizije se odbijejo od zneska, metrike pa se izracunajo sele iz
poti skupne vrednosti.

To ni pedantnost. Prejsnja razlicica je strosek uravnavanja odstela od donosa,
ne pa tudi od nalozbe, in je zato dala nekoliko previsoke stevilke.

Provizije so razclenjene na tri dele:

**signali** so vstopi in izstopi strategije po vsakem sredstvu posebej.

**uravnavanje** je vracanje na ciljne utezi. Zaracuna se samo tisto, kar se
dejansko premakne: ce BTC zdrsne s 50 % na 53 %, placas od tistih treh
odstotnih tock, ne od celega portfelja.

**zamenjava** je enkratna menjava sestega mesta, kadar HYPE dobi prvi signal.

## Kaj je 0,30 % na stran

Privzeta provizija in zdrs skupaj. **To je predpostavka, ne meritev**, in edini
vhod v celoten izracun, ki ga ne poznamo.

Zato je v zavihku Stroski tabela, ki pokaze, koliko se izid premakne med
brezplacnim trgovanjem in 0,60 % na stran. Manjsa ko je ta razlika, manj je
rezultat odvisen od necesa, cesar ne vemo.

## Objava na Streamlit Cloud

Glavna datoteka je `app.py` v korenu.

V naprednih nastavitvah **izberi Python 3.11 ali novejsi**. Na starejsem
namestitev pandasa pade z napako, ki ne kaze ocitno na verzijo.

Skrivnosti niso potrebne. Cene se predpomnijo za eno uro.

Prvo nalaganje traja dlje kot pri lean strani, ker prenese cene za osem
sredstev in na vsakem pozene strategijo.

Ce stran javi, da nima podatkov, pozeni `python scripts/preveri_vire.py`.

## Postavitev

```
app.py                  streamlit run app.py

model/                  strategija, ista kot v Diversitas Lean
  config.py             vsi parametri, z razlogom za vsakega
  strategy.py           avtomat stanj, pogoji, obrezovanje ogrevanja
  indicators.py         RSI, drseca povprecja, najvisje in najnizje
  warmup.py             obrezovanje ogrevanja
  costs.py              model stroskov
  data_source.py        pridobivanje cen

ui/
  dashboard.py          stran

scripts/
  preveri.py            racun in izris
  preveri_vire.py       knjiznice in dosegljivost virov cen
```

Mapa je zgrajena iz raziskovalnega repozitorija s skriptom
`testing/scripts/zgradi_sestavo.py`. Ta jo zna zgraditi znova, kadar se v
izvirniku kaj spremeni, in pri tem pobrise vse razen `.git`. **Rocne spremembe v
tej mapi bo prepisal**, zato popravljaj izvirnik.

## Kaj ta stran ni

Ni priporocilo za razporeditev. Raziskava, iz katere je nastala, je pokazala,
da kosarica sestih **ne** premaga samega BTC prepricljivo, in da razprsitev med
kripto sredstvi prinese manj, kot bi clovek pricakoval. Povprecna korelacija med
temi sestimi je 0,73, kar pomeni, da se vedejo skoraj kot eno sredstvo.

Stran obstaja zato, da to lahko vidis sam, na svojih datumih in svojih utezeh.
"""

PREVERI_VIRE = '''"""Preveri, ali so vsi viri cen dosegljivi.

    python scripts/preveri_vire.py

Pozeni to najprej, ce dashboard javi, da nima podatkov. Vsako sredstvo ima
tocno en vir in nadomestnega ni, ker bi tiho spremenil vse izracunane stevilke.
"""
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from model.config import LeanConfig
from model.data_source import fetch_candles
from ui.dashboard import VIRI, _symbol_map


def main() -> int:
    cfg = replace(LeanConfig(), symbol_map=_symbol_map())
    napak = 0
    print("KNJIZNICE")
    for p in ("pandas", "numpy", "requests", "plotly", "streamlit",
              "pyarrow", "yfinance"):
        try:
            __import__(p)
            print("  %-12s OK" % p)
        except ImportError:
            napak += 1
            print("  %-12s MANJKA" % p)
    print()
    print("  yfinance ni izbiren. Neposredna pot na Yahoo prek requests ne dela")
    print("  vec, zato brez njega odpovejo BNB, XRP in SPY.")
    print()
    print("VIRI CEN")
    print("%-6s%-14s%8s  %s" % ("simbol", "vir", "vrstic", "obdobje"))
    for s, vir in VIRI.items():
        try:
            d = fetch_candles(s, "1d", bars=5000, config=cfg, prefer=vir,
                              strict=True)
            print("%-6s%-14s%8d  %s do %s"
                  % (s, vir, len(d), d.index[0].date(), d.index[-1].date()))
        except Exception as e:
            napak += 1
            print("%-6s%-14s   NAPAKA  %s" % (s, vir, str(e)[:70]))
    print()
    if napak:
        print("nedosegljivih virov: %d" % napak)
        return 1
    print("vsi viri so dosegljivi")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''

PREVERI = '''"""Preveri, da racun v dashboardu drzi.

    python scripts/preveri.py

Osem preverb racuna in ena preverba izrisa. Zadnja pozene celo stran brezglavo
in ujame napake, ki jih racun ne more: manjkajoco knjiznico za izris, napacen
tip stolpca, zlom v Plotly.
"""
import sys
import warnings
from dataclasses import replace
from pathlib import Path

warnings.filterwarnings("ignore")
KOREN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOREN))

import pandas as pd

from ui import dashboard as D
from model.config import LeanConfig
from model.strategy import position, run_strategy, traded_fraction
from model.warmup import trim_warmup


def racun() -> list[tuple[str, bool]]:
    vsi = tuple(D.VIRI)
    CENE = D._cene.__wrapped__(vsi)
    SIG = D._signali.__wrapped__(vsi, CENE)
    so = SIG["HYPE"][0].index[0]
    UT = {"BTC": .50, "ETH": .10, "SOL": .10, "LINK": .10, "BNB": .10,
          "SESTO": .10}
    kon = CENE["BTC"].index[-1]
    idx = CENE["BTC"].loc[pd.Timestamp("2021-01-01", tz="UTC"):kon].index
    out = []

    r, prov, konc, pot = D._knjiga(idx, CENE, SIG, UT, 30, True, so, 1)
    m = D._metrike(r)
    out.append(("koncna vrednost = 100 x (1 + skupaj)",
                abs(konc - 100 * (1 + m["skupaj"] / 100)) < 1e-6))

    _, p0, k0, _ = D._knjiga(idx, CENE, SIG, UT, 0, True, so, 1)
    out.append(("brez provizij je koncna vrednost visja", k0 > konc))
    out.append(("pri 0 bp so provizije nic", sum(p0.values()) < 1e-9))

    _, pu, _, _ = D._knjiga(idx, CENE, SIG, UT, 30, False, so)
    out.append(("brez uravnavanja ni stroska uravnavanja",
                pu["uravnavanje"] < 1e-9))

    cfg = replace(LeanConfig(), symbol_map=D._symbol_map())
    _, _, kb, _ = D._knjiga(idx, CENE, SIG, {"BTC": 1.0}, 30, False, None)
    df = trim_warmup(run_strategy(CENE["BTC"], config=cfg).df)
    p = position(df, cfg).reindex(idx)
    t = traded_fraction(df, cfg).reindex(idx).fillna(0)
    ret = CENE["BTC"]["close"].pct_change().reindex(idx).fillna(0.0)
    v = 100.0
    for i in range(len(idx)):
        v *= 1 + p.iloc[i] * ret.iloc[i] - t.iloc[i] * 0.003
    out.append(("knjiga z enim sredstvom = neposreden izracun",
                abs(kb - v) < 0.01))

    pod = D._podvodni(pot)
    out.append(("podvodni graf ni nikoli nad niclo", pod.max() <= 1e-9))
    pad = D._najhujsi_padci(idx, pot)
    out.append(("najhujsi padec se ujema z MaxDD",
                abs(float(pad["globina"].iloc[0]) - m["maxdd"]) < 0.1))
    faze = D._datiraj(CENE["BTC"]["close"])
    out.append(("datiranje faz da izmenjujoce se faze",
                all(faze[i][2] != faze[i + 1][2] for i in range(len(faze) - 1))))
    return out


def izris() -> list[tuple[str, bool]]:
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(KOREN / "app.py"), default_timeout=300)
    at.run()
    if at.exception:
        for e in at.exception:
            print("   NAPAKA NA STRANI: %s" % str(e.value)[:300])
        return [("stran se izrise brez napake", False)]
    return [("stran se izrise brez napake", True),
            ("ima tabele", len(at.dataframe) >= 3),
            ("ima zavihke", len(at.tabs) >= 5)]


def main() -> int:
    vse = []
    print("RACUN")
    for ime, ok in racun():
        print("   %-46s %s" % (ime, "OK" if ok else "NAPAKA"))
        vse.append(ok)
    print("\\nIZRIS")
    for ime, ok in izris():
        print("   %-46s %s" % (ime, "OK" if ok else "NAPAKA"))
        vse.append(ok)
    print()
    if all(vse):
        print("vseh %d preverb je uspelo" % len(vse))
        return 0
    print("NEUSPESNIH: %d od %d" % (sum(1 for x in vse if not x), len(vse)))
    return 1


if __name__ == "__main__":
    sys.exit(main())
'''


def prepisi_dashboard(vsebina: str) -> str:
    """Zamenja Binance z Yahoo in popravi korena poti."""
    # 0) v tej mapi se stran zaganja prek app.py
    vsebina = vsebina.replace("    streamlit run testing/dashboard_sestava.py",
                              "    streamlit run app.py")
    # 1) glava: pot do korena je zdaj eno mapo visje
    vsebina = vsebina.replace(
        'ROOT = Path(__file__).resolve().parents[1]\n'
        'for p in (ROOT, ROOT / "lean"):\n'
        '    if str(p) not in sys.path:\n'
        '        sys.path.insert(0, str(p))',
        'ROOT = Path(__file__).resolve().parents[1]\n'
        'if str(ROOT) not in sys.path:\n'
        '    sys.path.insert(0, str(ROOT))')

    # 2) Binance ven, viri po sredstvu noter
    star_blok = vsebina[vsebina.index("PPY = 365"):vsebina.index("@st.cache_data(ttl=3600, show_spinner=False)\ndef _cene")]
    nov_blok = '''PPY = 365

# Vsako sredstvo ima tocno en vir in nadomestnega ni. Nadomestni vir bi tiho
# spremenil vsako izracunano stevilko, zato stran raje pove, da nima podatkov.
#
# Binancea tu ni, ceprav je bila raziskava narejena z njim. Iz Streamlit Clouda
# vrne HTTP 451, ker zavraca IP naslove podatkovnih centrov. BNB in XRP zato
# prideta z Yahooja, ki ju pokriva v celoti. Razlika je merjena in majhna:
# na BNB se pozicija ujema na 99,0 % od 3217 skupnih dni, Sortino 1,22 proti
# 1,25. Podrobno v README.
#
# Coinbase ne kotira BNB pred oktobrom 2025, XRP pa je bil pri njem med 2021 in
# 2023 umaknjen, torej bi manjkala prav leta, ki nas zanimajo.
VIRI = {
    "BTC": "coinbase",
    "ETH": "coinbase",
    "SOL": "coinbase",
    "LINK": "coinbase",
    "BNB": "yahoo",
    "XRP": "yahoo",
    "HYPE": "hyperliquid",
    "SPY": "yahoo",
}


def _symbol_map() -> dict:
    sm = dict(DEFAULT_SYMBOL_MAP)
    sm.setdefault("BNB", {})
    sm["BNB"] = dict(sm["BNB"], yahoo="BNB-USD")
    sm["HYPE"] = {"hyperliquid": "HYPE"}
    return sm


st.set_page_config(page_title="Sestava proti BTC", layout="wide")


'''
    vsebina = vsebina.replace(star_blok, nov_blok)

    # 3) _cene brez Binancea
    zac = vsebina.index("@st.cache_data(ttl=3600, show_spinner=False)\ndef _cene")
    kon = vsebina.index("@st.cache_data(ttl=3600, show_spinner=False)\ndef _signali")
    vsebina = vsebina[:zac] + '''@st.cache_data(ttl=3600, show_spinner=False)
def _cene(simboli: tuple[str, ...]) -> dict:
    cfg = replace(LeanConfig(), symbol_map=_symbol_map())
    out = {}
    for s in simboli:
        out[s] = fetch_candles(s, "1d", bars=5000, config=cfg,
                               prefer=VIRI[s], strict=True)
    return out


''' + vsebina[kon:]

    # 4) simbol map tudi v _signali
    vsebina = vsebina.replace(
        '    sm = dict(DEFAULT_SYMBOL_MAP)\n'
        '    sm["HYPE"] = {"hyperliquid": "HYPE"}\n'
        '    cfg = replace(LeanConfig(), symbol_map=sm)',
        '    cfg = replace(LeanConfig(), symbol_map=_symbol_map())')

    # 5) neuporabljena uvoza
    vsebina = vsebina.replace("import time\n", "")
    vsebina = vsebina.replace("import requests\n", "")
    return vsebina


# Sklici na datoteke, ki jih v tej mapi ni. Ugotovitev ostane zapisana, spremeni
# se le navedba vira: namesto poti na datoteko se pove, kaj je bilo izmerjeno.
# Enako je bilo narejeno pri predaji lean projekta.
SKLICI = [
    ("`testing/porocilo_ER_lean.md` and `testing/porocilo_ER_BTC.html`.",
     "a separate report in the research repository."),
    ("back bit-identical on all 2700 bars — see `testing/data/reference_positions.*`\n"
     "    # and `testing/tests/test_simplification.py`.",
     "back bit-identical on all 2700 bars, verified against a frozen position\n"
     "    # snapshot in the research repository."),
    ("`testing/scripts/dead_rules_robust.py`.",
     "a dedicated robustness script in the research repository."),
    ("overrides `shared.data_source.DEFAULT_SYMBOL_MAP`",
     "overrides `model.data_source.DEFAULT_SYMBOL_MAP`"),
    ("The dashboards and `testing/scripts/engine.py` both import from here so they can",
     "The dashboard and the research harness both import from here so they can"),
]


def main() -> int:
    # Vsebino pobrisem, .git pa pustim, da se zgodovina ohrani. Windows objektov
    # v .git tako ali tako ne pusti brisati, ker so samo za branje.
    if CILJ.exists():
        for p in CILJ.iterdir():
            if p.name == ".git":
                continue
            shutil.rmtree(p) if p.is_dir() else p.unlink()
    else:
        CILJ.mkdir(parents=True)

    for izv, cil in KODA.items():
        p = ROOT / izv
        if not p.exists():
            print("MANJKA: %s" % izv)
            return 1
        t = CILJ / cil
        t.parent.mkdir(parents=True, exist_ok=True)
        v = p.read_text(encoding="utf-8")
        if cil == "ui/dashboard.py":
            v = prepisi_dashboard(v)
        for vzorec, nadomestek in PREPISI:
            v = re.sub(vzorec, nadomestek, v, flags=re.M)
        for staro, novo in SKLICI:
            v = v.replace(staro, novo)
        if re.search(r"^\s*(from|import) shared\b", v, re.M) or \
                re.search(r"^\s*(from|import) diversitas\b", v, re.M):
            print("OPOZORILO: v %s je ostal uvoz iz izvirnega repozitorija" % cil)
        t.write_text(v, encoding="utf-8")
        print("  %-34s -> %s" % (izv, cil))

    (CILJ / "ui" / "__init__.py").write_text("", encoding="utf-8")
    (CILJ / "scripts").mkdir(exist_ok=True)
    (CILJ / "app.py").write_text(APP, encoding="utf-8")
    (CILJ / "README.md").write_text(README, encoding="utf-8")
    (CILJ / "requirements.txt").write_text(REQ, encoding="utf-8")
    (CILJ / ".gitignore").write_text(GITIGNORE, encoding="utf-8")
    (CILJ / "scripts" / "preveri.py").write_text(PREVERI, encoding="utf-8")
    (CILJ / "scripts" / "preveri_vire.py").write_text(PREVERI_VIRE,
                                                      encoding="utf-8")
    print("\nzgrajeno v %s" % CILJ)
    return 0


if __name__ == "__main__":
    sys.exit(main())
