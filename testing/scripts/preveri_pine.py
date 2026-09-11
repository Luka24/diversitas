"""Preveri, da `lean/diversitas_lean.pine` racuna isto kot Python.

    python testing/scripts/preveri_pine.py [BTC ETH SOL ...]

Pine ni mogoce pognati brez TradingView. Mogoce pa je preveriti PREPIS: ta
skripta prebere pravila IZ .pine datoteke, jih implementira se enkrat, na roko
in neodvisno od `lean/diversitas/strategy.py`, in obe seriji primerja bar za
barom.

To ne dokazuje, da se Pine na TradingView izvede brez napake -- to mora
preveriti tisti, ki ga tja prilepi. Dokazuje pa, da so PRAVILA v .pine enaka
pravilom v Pythonu, kar je edina napaka, ki jo je pri rocnem prepisu res lahko
narediti in najtezje opaziti.

Skripta hkrati bere .pine kot besedilo in preveri, da v njem NI vec vrstic,
ki so bile iz modela odstranjene. Brez tega bi lahko kdo pravilo vrnil nazaj,
serija pa bi se se vedno ujemala na tem vzorcu -- ker so bila ravno ta pravila
odstranjena zato, ker na tem vzorcu nicesar ne spremenijo.
"""
from __future__ import annotations

import re
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
from testing.scripts import engine as E                          # noqa: E402
from testing.scripts import pine_eval as PE                       # noqa: E402

PINE = ROOT / "lean" / "diversitas_lean.pine"

# Vrednosti so prebrane iz input.* vrstic v .pine, ne prepisane sem na roko --
# tako se privzetek v Pine ne more tiho raziti s tem, kar tu preverjamo.
_INPUT = re.compile(
    r"^\s*(\w+)\s*=\s*input\.(?:int|float|bool)\(\s*([^,)]+)", re.M)


def pine_privzetki() -> dict:
    txt = PINE.read_text(encoding="utf-8")
    out = {}
    for ime, val in _INPUT.findall(txt):
        v = val.strip()
        if v in ("true", "false"):
            out[ime] = (v == "true")
        else:
            try:
                out[ime] = float(v) if "." in v else int(v)
            except ValueError:
                pass
    return out


# ── indikatorji, prepisani iz .pine ───────────────────────────────────────────

def _rma(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()


def _rsi(close: pd.Series, n: int) -> pd.Series:
    d = close.diff()
    ag, al = _rma(d.clip(lower=0.0), n), _rma((-d).clip(lower=0.0), n)
    rs = ag / al.replace(0, np.nan)
    return (100.0 - 100.0 / (1.0 + rs)).where(al != 0, 100.0)


def po_pine(px: pd.DataFrame, p: dict) -> pd.DataFrame:
    """Vsaka vrstica tu ustreza eni vrstici v .pine, v istem vrstnem redu."""
    high, low, close = px["high"], px["low"], px["close"]

    trackHigh = high.rolling(p["trackPeriod"], min_periods=p["trackPeriod"]).max()
    trackLow = low.rolling(p["trackPeriod"], min_periods=p["trackPeriod"]).min()
    trackline = (trackHigh + trackLow) / 2.0
    trackRisingWindow = trackline > trackline.shift(p["trackSlopeBars"])
    bufAmt = trackline * (p["trackBuf"] / 100.0)
    aboveTL = close > (trackline + bufAmt)
    belowTL = close < (trackline - bufAmt)
    distPct = (close - trackline) / trackline * 100.0

    maLong = close.rolling(p["maLongLen"], min_periods=p["maLongLen"]).mean()
    maLongFalling = maLong < maLong.shift(p["maSlope"])
    aboveMaLong = close > maLong
    bearRegime = (~aboveMaLong) & maLongFalling
    regimeOK = ~bearRegime

    rsiVal = _rsi(close, p["rsiLen"])

    dcHi = high.rolling(p["donchianPeriod"], min_periods=p["donchianPeriod"]).max()
    dcLo = low.rolling(p["donchianPeriod"], min_periods=p["donchianPeriod"]).min()
    dcRange = dcHi - dcLo
    donchianPos = (close - dcLo) / dcRange.where(dcRange > 0)
    donchianRaw = (donchianPos > p["donchianTopFrac"]).fillna(False)
    # `: true`, ne `: aboveTL`. Izklop odstrani cenovni prag v celoti, kot to
    # dela Python (`donchian_ok = True`). Prvotni zapis je bil `aboveTL`, kar je
    # izklopu tiho dalo pomen, ki ga Python nikoli ni imel -- najdeno sele s
    # sweepom, pri privzetkih se ta veja sploh ne izvede.
    donchianOK = donchianRaw if p["useDonchian"] else pd.Series(True, index=px.index)

    blowoff = (distPct > p["blowoffDist"]) & (rsiVal > 80)
    btcFilterOK = True if not p["useBtcFilter"] else True   # v Lean izklopljen

    bullCondition = (donchianOK & trackRisingWindow & regimeOK
                     & btcFilterOK & ~blowoff).fillna(False)

    # `ma_long`, `trackline` in `rsi` so tu zato, da `shared.warmup.warmup_bars`
    # lahko izmeri ogrevanje iz TE tabele. Brez njih vrne 0, ker ne najde
    # nobenega znanega indikatorskega stolpca -- in odrez se tiho ne zgodi.
    return pd.DataFrame(dict(belowTL=belowTL.fillna(False),
                             aboveTL=aboveTL.fillna(False),
                             blowoff=blowoff.fillna(False),
                             bullCondition=bullCondition,
                             ma_long=maLong, trackline=trackline,
                             rsi=rsiVal), index=px.index)


def avtomat_po_pine(f: pd.DataFrame, p: dict) -> pd.DataFrame:
    below = f["belowTL"].to_numpy()
    bull = f["bullCondition"].to_numpy()
    blow = f["blowoff"].to_numpy()
    n = len(f)
    sig = np.full(n, 3, dtype=np.int8)
    st, since, below_c, hold_c = 3, 999, 0, 0
    for i in range(n):
        since += 1
        below_c = below_c + 1 if below[i] else 0
        hold_c = hold_c + 1 if bull[i] else 0
        if st == 1:
            if below[i] and below_c >= p["exitGraceBars"]:
                st, since = 3, 0
            elif blow[i]:
                st, since = 3, 0
        elif st == 3:
            if (bull[i] and hold_c >= p["confirmBars"]
                    and since >= p["reentryHold"]):
                st, since = 1, 0
        sig[i] = st
    return pd.DataFrame(dict(signalState=sig), index=f.index)


def pozicija_po_pine(px: pd.DataFrame, sig: np.ndarray, p: dict,
                     prev_sig=None, prev_close=None):
    """Prepis odseka POSITION iz .pine, vkljucno s plavajocim dnom.

    `prev_sig` in `prev_close` sta tu zaradi meje okna, ne zaradi pravila.
    Python zavrze ogrevalne bare in prek meje prenese oba, zato ima prvi bar
    njegovega okna pravi donos in pravi prejsnji signal. Na TradingView tega
    ni: skripta se zacne pri prvem baru grafa, kjer je `close[1]` na in
    `nz()` da 0.

    Ce se to tu ne poravna, se en sam manjkajoc donos na prvem baru mnozi
    naprej skozi plavajoce dno in ostane viden do konca serije -- izmerjeno
    najvec 0,018 odstotne tocke, torej brez pomena za odlocanje, a dovolj, da
    primerjava pravil ni vec cista. Poravnamo zato, da vsaka PREOSTALA razlika
    pomeni razliko v pravilih.
    """
    floor = p["bearAlloc"] / 100.0
    prvi = bool(prev_sig == 1) if prev_sig is not None else False
    posBull = np.concatenate([[prvi], sig[:-1] == 1])     # signalState[1]
    ret = px["close"].pct_change()
    if prev_close is not None and np.isfinite(prev_close):
        ret.iloc[0] = px["close"].iloc[0] / prev_close - 1.0
    ret = ret.fillna(0.0).to_numpy(float)
    n = len(sig)
    held = np.empty(n)
    traded = np.zeros(n)
    vA = 1.0 if posBull[0] else floor
    vC = 0.0 if posBull[0] else 1.0 - floor
    prev = posBull[0]
    for i in range(n):
        if posBull[i] != prev:
            tot = vA + vC
            tgt = tot if posBull[i] else floor * tot
            traded[i] = abs(tgt - vA) / tot
            vA, vC, prev = tgt, tot - tgt, posBull[i]
        tot = vA + vC
        held[i] = vA / tot
        vA *= (1.0 + ret[i])
    return held, traded


# ── odstranjena pravila se ne smejo vrniti ────────────────────────────────────

PREPOVEDANO = {
    "close > maMed v vstopnem pogoju": r"bullCondition[^\n]*\bmaMed\b",
    "distEntryOK":                     r"\bdistEntryOK\b",
    "volShock kot izstop":             r"signalState\s*:=\s*3[\s\S]{0,80}volShock|volShock[\s\S]{0,80}signalState\s*:=\s*3",
    "alokacija skalirana po vol":      r"targetAlloc\s*=\s*[^\n]*volScale",
    "aboveTL kot vstop":               r"bullCondition\s*=\s*aboveTL",
}


# Pine ime -> Python ime. Sweep spreminja oba hkrati; ce se pravili razideta
# le pri neki nastavitvi, se to tu pokaze, pri privzetkih pa ne bi.
IMENA = {"trackPeriod": "track_period", "trackBuf": "track_buf_pct",
         "trackSlopeBars": "track_slope_bars", "maLongLen": "ma_long_len",
         "maSlope": "ma_slope", "donchianPeriod": "donchian_period",
         "donchianTopFrac": "donchian_top_frac",
         "blowoffDist": "blowoff_dist_pct", "rsiLen": "rsi_len",
         "confirmBars": "confirm_bars", "reentryHold": "reentry_hold",
         "exitGraceBars": "exit_grace_bars", "bearAlloc": "bear_alloc_pct",
         "useDonchian": "use_donchian"}

# Vsaka vrstica je ena sprememba proti privzetku. Vkljucno z `useDonchian=False`,
# ker je bila prav ta veja mesto, kjer sta se .pine in Python ze enkrat razsla.
SWEEP = [
    {}, {"trackPeriod": 50}, {"trackPeriod": 100}, {"trackBuf": 0.0},
    {"trackBuf": 5.0}, {"trackSlopeBars": 1}, {"trackSlopeBars": 25},
    {"maLongLen": 100}, {"maSlope": 1}, {"maSlope": 20},
    {"donchianPeriod": 12}, {"donchianPeriod": 55},
    {"donchianTopFrac": 0.5}, {"donchianTopFrac": 0.95},
    {"blowoffDist": 10.0}, {"blowoffDist": 40.0},
    {"rsiLen": 7}, {"confirmBars": 1}, {"confirmBars": 5},
    {"reentryHold": 1}, {"reentryHold": 30},
    {"exitGraceBars": 1}, {"exitGraceBars": 5},
    {"bearAlloc": 0.0}, {"bearAlloc": 20.0},
    {"useDonchian": False},
    {"useDonchian": False, "exitGraceBars": 2},     # kjer se volShock zbudi
    {"donchianPeriod": 12, "confirmBars": 1, "reentryHold": 1},
    {"trackPeriod": 50, "trackBuf": 0.0, "exitGraceBars": 1},
]


def sweep(px: pd.DataFrame, p0: dict) -> tuple[int, int, list]:
    """Primerjaj .pine in Python pri vsaki nastavitvi iz SWEEP."""
    from diversitas.config import LeanConfig
    from diversitas.strategy import position as py_pos

    ok = 0
    razlike = []
    for sprem in SWEEP:
        p = dict(p0)
        p.update(sprem)
        py_kw = {IMENA[k]: v for k, v in sprem.items()}
        for k, v in list(py_kw.items()):
            if k in ("track_period", "ma_long_len", "ma_slope", "rsi_len",
                     "donchian_period", "confirm_bars", "reentry_hold",
                     "exit_grace_bars", "track_slope_bars"):
                py_kw[k] = int(v)
        df = E.run("lean", px, **py_kw)
        cfg = LeanConfig(**py_kw)
        f = po_pine(px, p)
        a = avtomat_po_pine(f, p).reindex(df.index)
        held, _ = pozicija_po_pine(
            px.reindex(a.index), a["signalState"].to_numpy(), p,
            prev_sig=(df["prev_signal_state"].iloc[0]
                      if "prev_signal_state" in df else None),
            prev_close=(df["prev_close"].iloc[0]
                        if "prev_close" in df else None))
        s_ok = bool((a["signalState"].to_numpy()
                     == df["signal_state"].to_numpy()).all())
        p_ok = bool(np.allclose(held, py_pos(df, cfg).to_numpy(), atol=1e-9))
        if s_ok and p_ok:
            ok += 1
        else:
            n_raz = int((a["signalState"].to_numpy()
                         != df["signal_state"].to_numpy()).sum())
            razlike.append((sprem or {"privzetki": True},
                            "signal" if not s_ok else "pozicija", n_raz))
    return ok, len(SWEEP), razlike


# Izrazi, ki morajo v .pine stati natanko tako. Primerja se BESEDILO datoteke,
# ne moje predstave o njej -- to je edini del preverbe, ki ga ne more zadovoljiti
# napaka, ponovljena dvakrat v isti glavi.
IZRAZI = {
    "bullCondition": "bullCondition = donchianOK and trackRisingWindow and "
                     "regimeOK and btcFilterOK and not blowoff",
    "belowTL":       "belowTL = close < (trackline - bufAmt)",
    "trackline":     "trackline = (trackHigh + trackLow) / 2.0",
    "trackRisingWindow": "trackRisingWindow = trackline > trackline[trackSlopeBars]",
    "bearRegime":    "bearRegime = not aboveMaLong and maLongFalling",
    "blowoff":       "blowoff = distPct > blowoffDist and rsiVal > 80",
    "donchianOK":    "donchianOK = useDonchian ? donchianRaw : true",
    "donchianRaw":   "donchianRaw = not na(donchianPos) and donchianPos > donchianTopFrac",
    "targetAlloc":   "targetAlloc = signalState == 1 ? 100 : 0",
    "posBull":       "posBull = nz(signalState[1], 3) == 1",
}


def izrazi(txt: str) -> list[tuple[str, bool]]:
    vrstice = {}
    for v in txt.splitlines():
        v = v.strip()
        m = re.match(r"^(\w+)\s*=\s*(.+)$", v)
        if m and "input." not in v:
            vrstice.setdefault(m.group(1), v)
    out = []
    for ime, pricakovano in IZRAZI.items():
        dobljeno = vrstice.get(ime, "<ni ga>")
        norm = lambda s: re.sub(r"\s+", " ", s).strip()
        out.append((ime, norm(dobljeno) == norm(pricakovano)))
        if norm(dobljeno) != norm(pricakovano):
            out[-1] = (f"{ime}  ->  {dobljeno[:80]}", False)
    return out


def oklepaji(txt: str) -> bool:
    par = {"(": ")", "[": "]"}
    sklad = []
    for ch in txt:
        if ch in par:
            sklad.append(par[ch])
        elif ch in par.values():
            if not sklad or sklad.pop() != ch:
                return False
    return not sklad


def main() -> int:
    simboli = sys.argv[1:] or ["BTC", "ETH", "SOL"]
    p = pine_privzetki()
    print(f"privzetki, prebrani iz {PINE.name}:")
    print("   " + "  ".join(f"{k}={v}" for k, v in sorted(p.items())
                            if k in ("trackPeriod", "trackBuf", "donchianPeriod",
                                     "donchianTopFrac", "maLongLen", "confirmBars",
                                     "reentryHold", "exitGraceBars", "bearAlloc",
                                     "useDonchian")))
    # Komentarje odstrani PRED iskanjem: glava datoteke odstranjena pravila
    # nasteje po imenu in razlozi, zakaj so sla ven. Iskanje po surovem
    # besedilu bi ta pojasnila prijavilo kot vrnjena pravila.
    txt = re.sub(r"//.*$", "", PINE.read_text(encoding="utf-8"), flags=re.M)

    print("\nODSTRANJENA PRAVILA SE NISO VRNILA  (komentarji izloceni)")
    vse = []
    for ime, vzorec in PREPOVEDANO.items():
        naslo = re.search(vzorec, txt)
        print(f"   {ime:<38}{'NAJDENO -- NAPAKA' if naslo else 'ni ga, ok'}")
        vse.append(naslo is None)

    podatki: dict = {}
    print("\nUJEMANJE PRAVIL: .pine proti lean/diversitas/strategy.py")
    print(f"   {'simbol':<8}{'barov':>7}{'signal':>10}{'pozicija':>11}"
          f"{'preklopov':>11}")
    for s in simboli:
        try:
            px = fetch_candles(s, "1d", bars=3000, prefer="coinbase")
        except Exception as e:                                    # noqa: BLE001
            print(f"   {s:<8}vira ni: {type(e).__name__}")
            vse.append(False)
            continue
        df = E.run("lean", px)                    # prava strategija (obrezana)
        f = po_pine(px, p)
        a = avtomat_po_pine(f, p)
        # obrezi na isto okno, kot ga uporablja Python
        a = a.reindex(df.index)
        held, _ = pozicija_po_pine(
            px.reindex(a.index), a["signalState"].to_numpy(), p,
            prev_sig=(df["prev_signal_state"].iloc[0]
                      if "prev_signal_state" in df else None),
            prev_close=(df["prev_close"].iloc[0]
                        if "prev_close" in df else None))

        ujem_sig = bool((a["signalState"].to_numpy()
                         == df["signal_state"].to_numpy()).all())
        from diversitas.strategy import position as py_pos
        from diversitas.config import LeanConfig
        py_h = py_pos(df, LeanConfig()).to_numpy()
        ujem_pos = bool(np.allclose(held, py_h, atol=1e-9))
        n_pre = int((np.diff(a["signalState"].to_numpy()) != 0).sum())
        print(f"   {s:<8}{len(df):>7}{'ujema' if ujem_sig else 'RAZLIKA':>10}"
              f"{'ujema' if ujem_pos else 'RAZLIKA':>11}{n_pre:>11}")
        vse += [ujem_sig, ujem_pos]
        podatki[s] = px

    # ── ujemanje ne sme sloneti na privzetkih ────────────────────────────────
    print(f"\nUJEMANJE PRI {len(SWEEP)} RAZLICNIH NASTAVITVAH")
    print("   (ce se ujemata le pri privzetkih, je ujemanje lahko nakljucje)")
    for s, px in podatki.items():
        n_ok, n_vse, razlike = sweep(px, p)
        print(f"   {s:<8}{n_ok:>3} od {n_vse}")
        for sprem, kaj, n in razlike:
            print(f"      RAZLIKA v {kaj} pri {sprem}  ({n} barov)")
        vse.append(n_ok == n_vse)

    # ── BESEDILO .pine proti Pythonu, brez mojega prepisa vmes ───────────────
    # Najmocnejsa preverba v tem naboru. `po_pine()` zgoraj je moj rocni prepis
    # Pine kode -- ce sem se pri pisanju .pine in pri pisanju prepisa zmotil
    # enako, se ujemata in nihce ni nic pametnejsi. Tu izraze PARSIRA in
    # ovrednoti `pine_eval` neposredno iz datoteke, zato moje branje ni vec del
    # verige: ce se v .pine spremeni en znak, se spremeni tudi ta rezultat.
    print("\nBESEDILO .pine PROTI PYTHONU  (izrazi ovrednoteni iz datoteke)")
    PARI = [("trackline", "trackline"), ("distPct", "dist_pct"),
            ("rsiVal", "rsi"), ("trackRisingWindow", "track_rising_window"),
            ("belowTL", "below_tl"), ("aboveTL", "above_tl"),
            ("bearRegime", "bear_regime"), ("regimeOK", "regime_ok"),
            ("donchianOK", "donchian_ok"), ("blowoff", "blowoff"),
            ("bullCondition", "bull_condition")]
    for s, px in podatki.items():
        vhodi = dict(p)
        vhodi["btcFilterOK"] = True     # request.security ni dosegljiv lokalno
        try:
            got = PE.ovrednoti(PINE, px, vhodi, [a for a, _ in PARI])
        except PE.PineNeprevedljivo as e:
            print(f"   {s}: NEPREVEDLJIVO -- {e}")
            vse.append(False)
            continue
        df = E.run("lean", px)
        vrstica = []
        for pine_ime, py_ime in PARI:
            a = got[pine_ime]
            b = df[py_ime]
            a = a.reindex(df.index)
            if b.dtype == bool:
                uj = bool((a.fillna(False).astype(bool).to_numpy()
                           == b.to_numpy()).all())
            else:
                uj = bool(np.allclose(a.to_numpy(float), b.to_numpy(float),
                                      rtol=1e-9, atol=1e-9, equal_nan=True))
            vrstica.append((pine_ime, uj))
            vse.append(uj)
        slabi = [n for n, u in vrstica if not u]
        print(f"   {s:<6}{len(vrstica) - len(slabi):>2} od {len(vrstica)} izrazov"
              + (f"   RAZLIKA: {', '.join(slabi)}" if slabi else ""))

    # ── izrazi v .pine morajo stati natanko tako ─────────────────────────────
    print("\nIZRAZI V .pine  (primerja se besedilo datoteke)")
    for ime, ok in izrazi(txt):
        print(f"   {ime:<62}{'ok' if ok else 'NE UJEMA'}")
        vse.append(ok)
    ur = oklepaji(txt)
    print(f"   {'oklepaji so uravnotezeni':<62}{'ok' if ur else 'NAPAKA'}")
    vse.append(ur)

    print()
    if all(vse):
        print(f"vseh {len(vse)} preverb je uspelo -- .pine in Python racunata isto")
        return 0
    print(f"NEUSPESNIH: {sum(1 for x in vse if not x)} od {len(vse)}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
