"""Pristranskost prezivelih: ali alt del knjige sloni na izbiri kovancev.
Test 4 iz testing/nacrt_word_ideje.md.

    python testing/scripts/prezivetje_altov.py

To ni kandidat, to je meritev. Lean ostane nespremenjen.

PRAVILA, ZAPISANA PRED PRVIM PRENOSOM PODATKOV (nacrt v commitu ba50fda)

Univerzum. Vsak 1. januar pet USDT parov na Binance z najvecjim prometom v USDT
v zadnjem cetrtletju prejsnjega leta (oktober do december, mesecni arhivi
data.binance.vision). Izloceni so:
    BTC sam
    stablecoini in fiat: USDC BUSD TUSD PAX USDP USDS USDSB DAI FDUSD UST USTC
        SUSD EUR GBP AUD AEUR EURI USDE USD1 RLUSD XUSD BFUSD PYUSD
    zlato: PAXG XAUT
    zaviti in zastavljeni: WBTC WBETH BETH WETH
    vzvodni zetoni: osnova oblike X+UP, X+DOWN, X+BULL, X+BEAR, kjer je X tudi
        sam USDT par
Ni izlocen noben kovanec, ki je kasneje propadel.
Dodatek k nacrtu, dolocen pred prvim prenosom: par mora imeti 1. januarja vsaj
365 dni zgodovine na Binance. To je pogoj iz clanka Concretum in hkrati
zagotovi, da je lean ogret (potrebuje okoli 205 dni). Ker se Binance zacne
julija 2017, je prvi univerzum 1. 1. 2019, okno meritve je 2019 do danes.
Ce ima par v arhivu luknjo daljso od 7 dni (npr. LUNA: stara do maja 2022, nova
od jeseni 2022), sta dela dva razlicna kovanca; drugi dobi oznako "#2".
Kovanec, ki med letom izgine, gre v gotovino in se ob naslednjem mesecnem
uravnavanju porazdeli med zive.

Tri knjige, vse BTC 50 % (Coinbase, kot danes) in alti po 10 %, normalizirane
utezi, mesecno uravnavanje, 0,30 % na stran, lean z BTC filtrom kot v produkciji:
    (i)   danasnja fiksna knjiga (ETH, SOL, LINK, BNB iz istega arhiva; HYPE ga
          na Binance spot nima, zato iz danasnjega vira)
    (ii)  dinamicna knjiga iz letnega univerzuma
    (iii) dinamicna knjiga, kupi in drzi
Razlika (i) - (ii) je ocena napihnjenosti zaradi izbire kovancev.
Razlika (ii) - (iii) je prednost lean na posteni mnozici.

Odlocitev (iz nacrta): ce C4 za (ii) proti (iii) izkljucuje nic v korist lean,
alt del ne sloni na izbiri kovancev. Ce ne, izbire altov ne utemeljujemo z
backtestom. C1-C3 se porocajo. Opomba, zapisana pred zagonom: C1 (zmaga v
rastocih fazah proti kupi in drzi) bo za trendno strategijo verjetno padel,
ker v rasti po zasnovi zaostaja; zato odloca C4, kot pravi nacrt.

Studiji primera (samo porocilo): LUNA 2022 in FTT 2022, ce sta v arhivu.
Ce LUNA izpade slabo, v tem krogu ne dodajamo pravila zanjo.

Pozitivna kontrola: BNB iz arhiva se mora ujemati z BNB iz graded_alti.cene()
(oba z Binance), zaprtja na skupnih dneh. Popravek po prvem zagonu: kontrola
je padla samo na zadnjem dnevu predpomnilnika (2026-08-30, -1,3 %), ker je bil
shranjen pred zaprtjem dneva. Ostalih 3219 dni se ujema natancno, zato se
zadnji dan pri primerjavi izpusti.

Podatki se shranijo v testing/data/sources/binance_arhiv/ (zip se ne razpakira
na disk, prebere se v pomnilniku kot CSV). Za izbrane kovance se preveri SHA256
iz .CHECKSUM.

Izhod: testing/data/prezivetje_altov.json
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import sys
import time
import warnings
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "lean", Path(__file__).resolve().parent):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import numpy as np
import pandas as pd
import requests

from graded_alti import _cfg, cene
from fantomska_gotovina import knjiga
from faze_ciklov import datiraj
from blowoff_izstop import izpis_sodbe, maxdd, sodba, sortino
from diversitas.strategy import compute_features, position, run_state_machine
from shared.warmup import trim_warmup

ARHIV = ROOT / "testing" / "data" / "sources" / "binance_arhiv"
S3 = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
DL = "https://data.binance.vision/data/spot/monthly/klines/%s/1d/%s-1d-%d-%02d.zip"
LETA = range(2019, 2027)
N_ALTOV = 5
IZLOCI = set("BTC USDC BUSD TUSD PAX USDP USDS USDSB DAI FDUSD UST USTC SUSD EUR GBP "
             "AUD AEUR EURI USDE USD1 RLUSD XUSD BFUSD PYUSD PAXG XAUT WBTC WBETH "
             "BETH WETH".split())
FIKSNA = ("ETH", "SOL", "LINK", "BNB")
STOLPCI = ["t", "open", "high", "low", "close", "volume", "ct", "qvol",
           "n", "tb", "tq", "x"]
SEJA = requests.Session()


# ---------------------------------------------------------------- podatki
def simboli() -> list[str]:
    pot = ARHIV / "simboli.json"
    if pot.exists():
        return json.loads(pot.read_text())
    out, marker = [], ""
    while True:
        r = SEJA.get(S3, params={"prefix": "data/spot/monthly/klines/",
                                 "delimiter": "/", "marker": marker}, timeout=60).text
        out += re.findall(r"<Prefix>data/spot/monthly/klines/([^/<]+)/</Prefix>", r)
        m = re.search(r"<NextMarker>([^<]+)</NextMarker>", r)
        if "<IsTruncated>true</IsTruncated>" not in r or not m:
            break
        marker = m.group(1)
    usdt = sorted(s for s in set(out) if s.endswith("USDT"))
    ARHIV.mkdir(parents=True, exist_ok=True)
    pot.write_text(json.dumps(usdt))
    return usdt


def _mesec(sym: str, y: int, m: int, preveri: bool) -> pd.DataFrame | None:
    pot = ARHIV / sym / ("%d-%02d.parquet" % (y, m))
    prazno = ARHIV / sym / ("%d-%02d.none" % (y, m))
    if pot.exists():
        return pd.read_parquet(pot)
    if prazno.exists() and not preveri:
        return None
    url = DL % (sym, sym, y, m)
    for poskus in range(4):
        try:
            r = SEJA.get(url, timeout=30)
            break
        except requests.RequestException:
            time.sleep(2 * (poskus + 1))
    else:
        raise RuntimeError("prenos ni uspel: %s" % url)
    pot.parent.mkdir(parents=True, exist_ok=True)
    if r.status_code == 404:
        prazno.touch()
        return None
    r.raise_for_status()
    if preveri:
        ck = SEJA.get(url + ".CHECKSUM", timeout=30).text.split()[0]
        if hashlib.sha256(r.content).hexdigest() != ck:
            raise RuntimeError("SHA256 se ne ujema: %s" % url)
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        d = pd.read_csv(z.open(z.namelist()[0]), header=None)
    if not str(d.iloc[0, 0]).isdigit():          # nekateri arhivi imajo glavo
        d = d.iloc[1:]
    d = d.iloc[:, :12]
    d.columns = STOLPCI
    t = d["t"].astype("int64")
    enota = np.where(t > 10**14, "us", "ms")      # od 2025 so casi v mikrosekundah
    d.index = pd.DatetimeIndex([pd.Timestamp(int(v), unit=str(u), tz="UTC")
                                for v, u in zip(t, enota)]).normalize()
    d = d[["open", "high", "low", "close", "volume", "qvol"]].astype(float)
    d.to_parquet(pot)
    return d


def zgodovina(sym: str, od=(2017, 7), preveri=True) -> pd.DataFrame | None:
    deli = []
    y, m = od
    konec = pd.Timestamp.now(tz="UTC")
    while (y, m) < (konec.year, konec.month):
        d = _mesec(sym, y, m, preveri)
        if d is not None:
            deli.append(d)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    if not deli:
        return None
    d = pd.concat(deli).sort_index()
    return d[~d.index.duplicated(keep="last")]


def segmenti(d: pd.DataFrame, osnova: str) -> dict[str, pd.DataFrame]:
    luknje = np.where(d.index.to_series().diff().dt.days > 7)[0]
    meje = [0, *luknje, len(d)]
    return {osnova + ("" if i == 0 else "#%d" % (i + 1)): d.iloc[a:b]
            for i, (a, b) in enumerate(zip(meje[:-1], meje[1:]))}


# ---------------------------------------------------------------- univerzum
def kandidati(vsi: list[str]) -> list[str]:
    osnove = {s[:-4] for s in vsi}
    out = []
    for s in vsi:
        b = s[:-4]
        if b in IZLOCI:
            continue
        if any(b.endswith(k) and b[:-len(k)] in osnove
               for k in ("UP", "DOWN", "BULL", "BEAR")):
            continue
        out.append(s)
    return out


def univerzum(kand: list[str]) -> dict[int, list[str]]:
    pot = ARHIV / "univerzum.json"
    if pot.exists():
        return {int(k): v for k, v in json.loads(pot.read_text()).items()}
    out = {}
    for leto in LETA:
        def promet(sym):
            vol, prvi = 0.0, None
            for m in (10, 11, 12):
                d = _mesec(sym, leto - 1, m, False)
                if d is not None:
                    vol += float(d["qvol"].sum())
            return sym, vol
        with ThreadPoolExecutor(16) as ex:
            pr = dict(ex.map(promet, kand))
        vrsta = sorted((s for s in pr if pr[s] > 0), key=lambda s: -pr[s])
        izbrani = []
        for s in vrsta:
            # vsaj 365 dni zgodovine: mesec 13 mesecev pred 1. januarjem mora obstajati
            y0, m0 = leto - 2, 12
            if _mesec(s, y0, m0, False) is None:
                continue
            izbrani.append(s)
            if len(izbrani) == N_ALTOV:
                break
        out[leto] = izbrani
        print("   %d: %s" % (leto, ", ".join(x[:-4] for x in izbrani)))
    pot.write_text(json.dumps(out, indent=1))
    return out


# ---------------------------------------------------------------- lean
def lean_pozicija(raw, btc, cfg) -> pd.Series:
    df = trim_warmup(run_state_machine(compute_features(raw, btc, cfg), cfg))
    return position(df, cfg).astype(float)


def potek_posla(raw, btc, cfg) -> list[dict]:
    df = trim_warmup(run_state_machine(compute_features(raw, btc, cfg), cfg))
    s, c = df["signal_state"], df["close"]
    vst = df.index[(s == 1) & (s.shift(1) != 1)]
    izs = df.index[(s != 1) & (s.shift(1) == 1)]
    out = []
    for a in vst:
        b = [x for x in izs if x > a]
        b = b[0] if b else df.index[-1]
        seg = c.loc[a:b]
        out.append({"vstop": str(a.date()), "izstop": str(b.date()),
                    "donos": round(float(c[b] / c[a] - 1) * 100, 1),
                    "od_vrha_posla": round(float(c[b] / seg.max() - 1) * 100, 1)})
    return out


def main() -> int:
    cfg = _cfg()
    C = cene()
    btc = C["BTC"]
    out = {}

    print("Seznam USDT parov v arhivu ...")
    vsi = simboli()
    kand = kandidati(vsi)
    print("   %d USDT parov, %d po izlocitvah" % (len(vsi), len(kand)))

    print("Univerzum po letih (to traja ob prvem zagonu):")
    U = univerzum(kand)
    out["univerzum"] = {k: [s[:-4] for s in v] for k, v in U.items()}

    # cene izbranih in fiksnih, s preverbo SHA256
    potrebni = sorted({s for v in U.values() for s in v} | {f + "USDT" for f in FIKSNA})
    print("\nPrenos celotne zgodovine %d parov (SHA256 preverjen) ..." % len(potrebni))
    with ThreadPoolExecutor(4) as ex:
        Z = dict(zip(potrebni, ex.map(zgodovina, potrebni)))

    # pozitivna kontrola
    bnb = Z["BNBUSDT"]["close"]
    ref = C["BNB"]["close"]
    ref.index = ref.index.normalize()
    # zadnji dan v predpomnilniku cene() je bil shranjen, ko dan se ni bil zaprt
    # (polovicna sveca); primerjamo samo zaprte dni
    sk = bnb.index.intersection(ref.index[:-1])
    odst = float((bnb[sk] / ref[sk] - 1).abs().max())
    ok = odst < 1e-9
    print("Pozitivna kontrola (BNB arhiv = BNB API na %d dneh): najvecje odstopanje %.2e  %s"
          % (len(sk), odst, "OK" if ok else "NAPAKA"))
    if not ok:
        return 1

    # segmenti: kateri del para je bil clan v katerem letu
    SEG = {}
    for s, d in Z.items():
        if d is not None:
            SEG.update(segmenti(d, s[:-4]))

    def segment_za(sym, datum):
        b = sym[:-4]
        for ime, d in SEG.items():
            if ime.split("#")[0] == b and d.index[0] <= datum <= d.index[-1]:
                return ime
        return None

    # pozicije lean na vsakem segmentu
    POS_L, RET = {}, {}
    for ime, d in SEG.items():
        if len(d) < 260:
            continue
        RET[ime] = d["close"].pct_change()
        POS_L[ime] = lean_pozicija(d, btc, cfg)

    zacetek = pd.Timestamp("%d-01-01" % LETA[0], tz="UTC")
    p_btc = lean_pozicija(btc, None, cfg)
    p_btc.index = p_btc.index.normalize()
    idx = p_btc.index[p_btc.index >= zacetek]
    RET["BTC"] = btc["close"].set_axis(btc.index.normalize()).pct_change()

    # clanstvo: (ii) in (iii)
    POS_D, POS_BH = {"BTC": p_btc}, {"BTC": pd.Series(1.0, index=p_btc.index)}
    utezi = {"BTC": 0.5}
    manjka = 0
    for leto, izbr in U.items():
        od = pd.Timestamp("%d-01-01" % leto, tz="UTC")
        do = pd.Timestamp("%d-12-31" % leto, tz="UTC")
        for sym in izbr:
            ime = segment_za(sym, od)
            if ime is None or ime not in POS_L:
                manjka += 1
                continue
            kljuc = "%s@%d" % (ime, leto)
            pl = POS_L[ime].loc[od:do]
            pb = SEG[ime]["close"].loc[od:do] * 0 + 1.0
            POS_D[kljuc], POS_BH[kljuc] = pl, pb
            RET[kljuc] = RET[ime]
            utezi[kljuc] = 0.1
    print("Clanov brez podatkov ali brez ogrete pozicije: %d" % manjka)

    # (i) fiksna
    POS_F, uf = {"BTC": p_btc}, {"BTC": 0.5}
    for f in FIKSNA:
        ime = f
        POS_F[ime] = POS_L[ime]
        uf[ime] = 0.1
    hype = C["HYPE"].copy()
    hype.index = hype.index.normalize()
    POS_F["HYPE"] = lean_pozicija(hype, btc, cfg)
    RET["HYPE"] = hype["close"].pct_change()
    uf["HYPE"] = 0.1

    def kn(POS, ut):
        P = {k: POS[k] for k in ut}
        R = {k: RET[k] for k in ut}
        return knjiga(idx, P, R, ut, True)[0]

    K = {"(i) fiksna, lean": kn(POS_F, uf),
         "(ii) dinamicna, lean": kn(POS_D, utezi),
         "(iii) dinamicna, kupi in drzi": kn(POS_BH, utezi)}
    print("\nKNJIGE %s do %s" % (idx[0].date(), idx[-1].date()))
    out["knjige"] = {}
    for k, r in K.items():
        sz = float((np.prod(1 + r) ** (365 / len(r)) - 1) * 100)
        out["knjige"][k] = {"sortino": round(sortino(r), 2), "maxdd": round(maxdd(r), 1),
                            "cagr": round(sz, 1)}
        print("  %-32s Sortino %.2f  MaxDD %6.1f %%  CAGR %6.1f %%" % (k, sortino(r), maxdd(r), sz))

    print("\n(i) - (ii), napihnjenost zaradi izbire: Sortino %+.2f, CAGR %+.1f t.t."
          % (out["knjige"]["(i) fiksna, lean"]["sortino"] - out["knjige"]["(ii) dinamicna, lean"]["sortino"],
             out["knjige"]["(i) fiksna, lean"]["cagr"] - out["knjige"]["(ii) dinamicna, lean"]["cagr"]))

    faze = datiraj(btc["close"].set_axis(btc.index.normalize()))
    print("\n(ii) lean proti (iii) kupi in drzi, fazni protokol:")
    sd = sodba(K["(iii) dinamicna, kupi in drzi"], K["(ii) dinamicna, lean"], idx, faze)
    izpis_sodbe("(ii) proti (iii)", sd)
    out["ii_proti_iii"] = sd
    print("ODLOCITEV (C4): %s" % ("lean ohrani prednost na posteni mnozici" if sd["C4"]
                                 else "prednost lean na posteni mnozici ni dokazana"))

    print("\nSTUDIJE PRIMERA")
    out["primeri"] = {}
    for ime in ("LUNA", "FTT"):
        if ime not in SEG:
            d = zgodovina(ime + "USDT")
            if d is None:
                print("  %s ni v arhivu" % ime)
                continue
            SEG.update(segmenti(d, ime))
        d = SEG[ime]
        posli = potek_posla(d, btc, cfg)
        bh = float(d["close"].iloc[-1] / d["close"].max() - 1) * 100
        out["primeri"][ime] = {"do": str(d.index[-1].date()), "kupi_in_drzi_od_vrha": round(bh, 1),
                               "posli": posli[-4:]}
        print("  %s (podatki do %s), kupi in drzi od vrha do konca: %.1f %%"
              % (ime, d.index[-1].date(), bh))
        for p in posli[-4:]:
            print("     vstop %s  izstop %s  donos %+.1f %%  od vrha posla %+.1f %%"
                  % (p["vstop"], p["izstop"], p["donos"], p["od_vrha_posla"]))

    pot = ROOT / "testing" / "data" / "prezivetje_altov.json"
    pot.write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str),
                   encoding="utf-8")
    print("\nZapisano: %s" % pot.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
