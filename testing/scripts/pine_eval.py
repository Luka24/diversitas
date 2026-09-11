"""Ovrednoti izraze NEPOSREDNO iz .pine datoteke.

Zakaj to obstaja. `preveri_pine.py` primerja Python z rocnim prepisom Pine
kode -- a oboje sem napisal jaz, iz istega razumevanja. Ce se dvakrat enako
zmotim, se strani ujemata in preverba je zadovoljna. To je edina luknja, ki je
ta preverba ni mogla zapreti.

Tu je zaprta: modul prebere `.pine`, PARSIRA prireditve in jih ovrednoti v
pandas. Racuna torej besedilo datoteke, ne moje predstave o njej. Ce se v
datoteki spremeni en znak, se spremeni tudi rezultat tukaj.

Prevaja se namenoma OZEK del Pine: prireditve na globalni ravni, aritmetika,
primerjave, `and`/`or`/`not`, indeks `[n]`, trojiski operator brez gnezdenja in
peščica funkcij `ta.*` / `math.*`. Vse drugo **sproži napako** in se ne ugiba --
tiho priblizevanje bi bilo huje od nobene preverbe.
"""
from __future__ import annotations

import re
from typing import Any, Dict

import numpy as np
import pandas as pd


class PineNeprevedljivo(Exception):
    """Konstrukt, ki ga ta ozki prevajalnik ne obvlada. Nikoli ne ugibaj."""


# ── pomozne funkcije, na katere se prevede Pine ──────────────────────────────

def _rma(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()


def _rsi(s: pd.Series, n: int) -> pd.Series:
    d = s.diff()
    ag, al = _rma(d.clip(lower=0.0), n), _rma((-d).clip(lower=0.0), n)
    rs = ag / al.replace(0, np.nan)
    return (100.0 - 100.0 / (1.0 + rs)).where(al != 0, 100.0)


def _ite(c, a, b):
    """Trojiski operator. Poravna skalarje na indeks pogoja."""
    idx = None
    for x in (c, a, b):
        if isinstance(x, pd.Series):
            idx = x.index
            break
    if idx is None:
        return a if c else b
    def ser(x):
        if isinstance(x, pd.Series):
            return x
        return pd.Series([x] * len(idx), index=idx, dtype="float64"
                         if not isinstance(x, bool) else "object")
    cond = c if isinstance(c, pd.Series) else pd.Series([bool(c)] * len(idx), index=idx)
    return ser(a).where(cond.fillna(False).astype(bool), ser(b))


def _na(x):
    return x.isna() if isinstance(x, pd.Series) else (x != x)


def _nz(x, repl=0.0):
    return x.fillna(repl) if isinstance(x, pd.Series) else (repl if x != x else x)


OKOLJE: Dict[str, Any] = {
    "_rsi": _rsi, "_ite": _ite, "_na": _na, "_nz": _nz,
    "np": np, "pd": pd, "nan": np.nan,
}


# ── prevod Pine -> pandas ────────────────────────────────────────────────────

_TA = {
    "ta.highest": lambda a, n: f"({a}).rolling(int({n}), min_periods=int({n})).max()",
    "ta.lowest":  lambda a, n: f"({a}).rolling(int({n}), min_periods=int({n})).min()",
    "ta.sma":     lambda a, n: f"({a}).rolling(int({n}), min_periods=int({n})).mean()",
    "ta.stdev":   lambda a, n: f"({a}).rolling(int({n}), min_periods=int({n})).std(ddof=0)",
    "ta.rsi":     lambda a, n: f"_rsi({a}, int({n}))",
    "ta.ema":     lambda a, n: f"({a}).ewm(span=int({n}), adjust=False).mean()",
}

_MATH = {"math.sqrt": "np.sqrt", "math.log": "np.log", "math.abs": "np.abs",
         "math.min": "np.minimum", "math.max": "np.maximum",
         "math.round": "np.round"}

# Kar sme nastopati. Karkoli drugega pomeni, da izraza ne razumemo.
_DOVOLJENO = re.compile(
    r"^[\w\s\.\(\)\[\]\+\-\*/><=!%\?:,&|#'\"]+$")


def _deli_argumente(s: str) -> list[str]:
    """Razdeli `a, b` na vrhnji ravni oklepajev."""
    out, glob, zad = [], 0, 0
    for i, ch in enumerate(s):
        if ch in "([":
            glob += 1
        elif ch in ")]":
            glob -= 1
        elif ch == "," and glob == 0:
            out.append(s[zad:i])
            zad = i + 1
    out.append(s[zad:])
    return [x.strip() for x in out]


def _najdi_klic(izraz: str, ime: str):
    """Vrne (zacetek, konec, argumenti) prvega klica `ime(...)`."""
    i = izraz.find(ime + "(")
    if i < 0:
        return None
    j = i + len(ime)
    glob, k = 0, j
    while k < len(izraz):
        if izraz[k] == "(":
            glob += 1
        elif izraz[k] == ")":
            glob -= 1
            if glob == 0:
                return i, k + 1, _deli_argumente(izraz[j + 1:k])
        k += 1
    raise PineNeprevedljivo(f"nezakljucen klic {ime} v: {izraz}")


def prevedi(izraz: str) -> str:
    """Pine izraz -> Python izraz nad pandas serijami."""
    e = izraz.strip()
    if not _DOVOLJENO.match(e):
        raise PineNeprevedljivo(f"nedovoljeni znaki: {e}")

    # 1) klici ta.* in math.*, od znotraj navzven
    for ime, gradi in _TA.items():
        while True:
            n = _najdi_klic(e, ime)
            if n is None:
                break
            i, j, args = n
            if len(args) != 2:
                raise PineNeprevedljivo(f"{ime} pricakuje 2 argumenta: {e}")
            e = e[:i] + gradi(prevedi(args[0]), prevedi(args[1])) + e[j:]
    for ime, zamenjava in _MATH.items():
        e = e.replace(ime + "(", zamenjava + "(")
    for ime, zamenjava in (("na(", "_na("), ("nz(", "_nz(")):
        e = re.sub(r"(?<![\w.])" + re.escape(ime), zamenjava, e)

    # 2) trojiski operator, ena raven. Gnezdenja ne ugibamo.
    if "?" in e:
        if e.count("?") > 1:
            raise PineNeprevedljivo(f"gnezden trojiski operator: {e}")
        glob = 0
        q = c = -1
        for i, ch in enumerate(e):
            if ch in "([":
                glob += 1
            elif ch in ")]":
                glob -= 1
            elif glob == 0 and ch == "?" and q < 0:
                q = i
            elif glob == 0 and ch == ":" and q >= 0 and c < 0:
                c = i
        if q < 0 or c < 0:
            raise PineNeprevedljivo(f"trojiskega operatorja ni mogoce razbrati: {e}")
        return (f"_ite({prevedi(e[:q])}, {prevedi(e[q+1:c])}, {prevedi(e[c+1:])})")

    # 3) indeks [n] -> shift(n)
    def _shift(m):
        return f".shift(int({m.group(2)}))"
    prej = None
    while prej != e:
        prej = e
        e = re.sub(r"(\w+)\[([^\[\]]+)\]", lambda m: f"{m.group(1)}.shift(int({m.group(2)}))", e)

    # 4) logika. `not X` -> ~(X), and/or -> &/|  (oklepaji zaradi prednosti)
    e = re.sub(r"(?<![\w.])not\s+([\w\.\(\)]+)", r"~(\1)", e)
    e = re.sub(r"\s+and\s+", ") & (", e)
    e = re.sub(r"\s+or\s+", ") | (", e)
    if "&" in e or "|" in e:
        e = "(" + e + ")"

    # 5) konstante
    e = re.sub(r"(?<![\w.])true(?![\w])", "True", e)
    e = re.sub(r"(?<![\w.])false(?![\w])", "False", e)
    e = re.sub(r"(?<![\w.])na(?![\w(])", "nan", e)
    return e


_PRIREDITEV = re.compile(r"^(\w+)\s*=\s*(.+?)\s*$")


def preberi_prireditve(pot) -> dict:
    """Globalne prireditve iz .pine, v vrstnem redu pojavljanja.

    Preskoci: komentarje, `input.*`, `:=` (te obravnava stanjski avtomat),
    vrstice v blokih (zamaknjene) in `var` deklaracije.
    """
    out = {}
    for vrstica in pot.read_text(encoding="utf-8").splitlines():
        if vrstica[:1] in (" ", "\t"):          # znotraj bloka
            continue
        v = re.sub(r"//.*$", "", vrstica).strip()
        if not v or ":=" in v or v.startswith("var ") or "input." in v:
            continue
        m = _PRIREDITEV.match(v)
        if m and not v.startswith(("plot", "table", "if", "alertcondition",
                                   "bgcolor", "indicator")):
            out.setdefault(m.group(1), m.group(2))
    return out


def ovrednoti(pot, px: pd.DataFrame, vhodi: dict, hoceno: list[str]) -> dict:
    """Ovrednoti zahtevana imena iz .pine nad danimi cenami."""
    izrazi = preberi_prireditve(pot)
    okolje = dict(OKOLJE)
    okolje.update({"open": px["open"], "high": px["high"], "low": px["low"],
                   "close": px["close"]})
    okolje.update(vhodi)

    def resi(ime: str, globina=0):
        if ime in okolje:
            return okolje[ime]
        if globina > 40:
            raise PineNeprevedljivo(f"ciklicna odvisnost pri {ime}")
        if ime not in izrazi:
            raise PineNeprevedljivo(f"ime `{ime}` v .pine ni definirano")
        py = prevedi(izrazi[ime])
        for odv in sorted(set(re.findall(r"(?<![\w.])([A-Za-z_]\w*)", py)),
                          key=len, reverse=True):
            if odv in okolje or odv in ("int", "True", "False", "nan"):
                continue
            if odv in izrazi:
                resi(odv, globina + 1)
        try:
            okolje[ime] = eval(py, {"__builtins__": {"int": int}}, okolje)  # noqa: S307
        except Exception as e:                                    # noqa: BLE001
            raise PineNeprevedljivo(f"{ime}: {izrazi[ime]}  ->  {py}  ({e})") from e
        return okolje[ime]

    return {k: resi(k) for k in hoceno}
