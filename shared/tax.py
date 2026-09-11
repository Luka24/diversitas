"""Davek kot strošek, izračunan in ne ocenjen.

Zakaj to sploh obstaja: obrat 325 % na leto in držanje petnajst let sta v
Sloveniji dva različna davčna izdelka, in razlika je večja od vseh razmikov in
provizij v tem projektu skupaj. Dokler davka ni v modelu, primerjava aktivne
strategije s kupi in drži ni primerjava dveh strategij, ampak primerjava dveh
davčnih obravnav, na kateri ena stran ne plača.

KAKO TO DELAJO DRUGI

Standard obstaja in ni sporen. Ameriški SEC od skladov zahteva objavo donosov
**pred obdavčitvijo, po obdavčitvi pred unovčenjem in po obdavčitvi po
unovčenju** — troje številk na isti strani, po predpisani metodologiji.
Morningstar iz istega izračuna izpelje `tax cost ratio`, torej koliko odstotnih
točk letnega donosa pojé davek. Russell Investments isto meri kot `tax drag` in
poudarja, da je pri strategijah z visokim obratom to največja posamična
postavka, večja od provizij.

Ta modul dela isto: vrne donos pred davkom, po davku pred unovčenjem in po
davku z unovčenjem, ter razliko med prvim in zadnjim kot `tax_cost_ratio`.

DVE SLOVENSKI UREDITVI

`SloveniaBrokerage` — navaden borzni račun. Davčna obveznost nastane ob vsaki
odsvojitvi. Stopnja pada z dobo imetja posameznega svežnja, zaporedje pa je
FIFO. To je mehanizem, ki aktivno strategijo kaznuje dvakrat: enkrat, ker
plača davek prej, in drugič, ker vsaka prodaja **ponastavi uro** in tako
prepreči, da bi kateri koli sveženj kdaj dosegel ničelno stopnjo.

`SloveniaINR` — individualni naložbeni račun po ZINR, v uporabi od 2026.
Trgovanje znotraj računa ni davčni dogodek. Ob izplačilu je stopnja enotnih
15 %, po petnajstih letih brez izplačil pa 0 %. To je edina ureditev, v kateri
je visok obrat davčno nevtralen.

Stopnje so parametri in ne konstante, ker se predpisi spreminjajo, številke pa
morajo biti preverljive pri davčnem svetovalcu. Privzetki so zapisani v
`SLOVENIA_2026` in `INR_2026`; oba nosita datum, iz katerega izhajata.

ČESA TA MODUL NE DELA

Ne pozna posameznikovega položaja: drugih dobičkov in izgub, pobota izgub,
dedovanja, spremembe rezidentstva. Ne modelira dividend, ker je vseh osem
skladov akumulativnih in med držanjem ne izplačajo ničesar. Ne modelira
davčnega odloga na ravni sklada. Za odločitev je dovolj, za napoved ne.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


# ── ureditvi ──────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class BrokerageTax:
    """Davek od dobička iz kapitala na navadnem računu, stopnja po dobi imetja.

    `brackets` je zaporedje (dopolnjena leta imetja, stopnja). Sveženj, držan
    `h` let, plača stopnjo prvega praga, katerega meja je <= h, pri čemer se bere
    od zadaj. Privzetek ustreza shemi 25 / 20 / 15 / 0, kot jo za leto 2026
    navajajo javno dostopni viri; potrdi jo pri svetovalcu, preden se po njej
    odloči karkoli.
    """
    name: str = "Slovenija, navaden racun"
    brackets: Tuple[Tuple[float, float], ...] = ((0.0, 0.25), (5.0, 0.20),
                                                 (10.0, 0.15), (15.0, 0.00))
    as_of: str = "2026-09"

    def rate(self, holding_years: float) -> float:
        r = self.brackets[0][1]
        for edge, rate in self.brackets:
            if holding_years >= edge:
                r = rate
        return r


@dataclass(frozen=True)
class INRTax:
    """Individualni naložbeni račun (ZINR).

    Trgovanje znotraj računa ni obdavčeno. Ob izplačilu se obdavči dobiček po
    enotni stopnji; če v `tax_free_years` ni bilo nobenega izplačila, je stopnja
    nič. Vplačila so omejena: prvo leto `first_year_limit`, nato `annual_limit`
    na leto, skupno največ `lifetime_limit`.

    Omejitve niso podrobnost. Pri 5.000 EUR letno in 150.000 EUR skupno INR ne
    more nositi poljubno velikega portfelja, zato je za večji kapital vprašanje
    vedno mešano: del v INR, del na navadnem računu.
    """
    name: str = "Slovenija, INR"
    rate_on_withdrawal: float = 0.15
    tax_free_years: float = 15.0
    annual_limit: float = 5_000.0
    first_year_limit: float = 20_000.0
    lifetime_limit: float = 150_000.0
    as_of: str = "2026-09"


SLOVENIA_2026 = BrokerageTax()
INR_2026 = INRTax()
NO_TAX = BrokerageTax(name="brez davka", brackets=((0.0, 0.0),))


# ── knjiženje svežnjev ────────────────────────────────────────────────────────

@dataclass
class _Lot:
    date: pd.Timestamp
    units: float
    cost: float          # nabavna vrednost na enoto


def _sell_fifo(lots: List[_Lot], units: float, price: float, when: pd.Timestamp,
               tax: BrokerageTax) -> Tuple[float, List[Tuple[float, float]]]:
    """Prodaj `units` po FIFO. Vrne (iztrzek, [(dobicek, stopnja), ...]).

    FIFO je predpisano zaporedje in ni nedolžna podrobnost: ravno zato aktivna
    strategija nikoli ne pride do ničelne stopnje. Vsak nakup ustvari nov
    sveženj, vsaka prodaja pa pobere najstarejšega — torej tistega, ki je bil
    najbližje ugodnejši stopnji.

    Vrne posamezne odsvojitve in ne že obračunanega davka, ker se izgube pobotajo
    z dobički **po koledarskem letu** in ne po poslu. Če bi vsak posel obdavčili
    posebej in izgube spregledali, bi strategija z velikim obratom plačala davek
    tudi v letu, v katerem je izgubila — kar ni res in bi aktivne kandidate
    krivično pokopalo.
    """
    proceeds = units * price
    events: List[Tuple[float, float]] = []
    left = units
    while left > 1e-12 and lots:
        lot = lots[0]
        take = min(left, lot.units)
        gain = take * (price - lot.cost)
        years = (when - lot.date).days / 365.25
        events.append((gain, tax.rate(years)))
        lot.units -= take
        left -= take
        if lot.units <= 1e-12:
            lots.pop(0)
    return proceeds, events


def _net_year_tax(events: List[Tuple[float, float]]) -> float:
    """Davek za eno koledarsko leto: izgube pobotaj z dobički, najprej z
    najvišje obdavčenimi.

    Pobot znotraj leta je pravilo, ki ga zakon dopušča; prenos izgube v
    naslednje leto tu ni modeliran, ker za dobičke iz kapitala ni predviden.
    Vrstni red pobota — najprej proti najvišji stopnji — je za zavezanca
    najugodnejši in je zato konservativna izbira za oceno *aktivne* strategije,
    saj ji ne pripiše več davka, kot bi ga v resnici plačala.
    """
    gains = sorted([e for e in events if e[0] > 0], key=lambda e: -e[1])
    losses = -sum(g for g, _ in events if g < 0)
    total = 0.0
    for g, rate in gains:
        used = min(g, losses)
        losses -= used
        total += (g - used) * rate
    return total


# ── simulacija ────────────────────────────────────────────────────────────────

@dataclass
class AfterTaxResult:
    pre_tax: pd.Series           # dnevni donos pred davkom
    after_tax: pd.Series         # dnevni donos po davku, brez unovčenja na koncu
    equity_pre: pd.Series
    equity_after: pd.Series
    tax_paid: pd.Series          # davek, plačan na dan (letni obračun)
    realised_gain: pd.Series
    terminal_tax: float          # davek ob unovčenju vsega na zadnji dan
    meta: dict = field(default_factory=dict)


def simulate_brokerage(weights: pd.DataFrame, prices: pd.DataFrame,
                       tax: BrokerageTax = SLOVENIA_2026,
                       fee_per_side_pct: float = 0.20,
                       initial: float = 100_000.0,
                       pay_month: int = 3,
                       rebalance_mask: Optional[pd.Series] = None) -> AfterTaxResult:
    """Odigraj pot uteži na navadnem računu in obračunaj davek po svežnjih.

    `weights` so ciljni deleži kapitala po rokavih na vsak dan, `prices` cene v
    isti valuti. Simulacija hrani enote in svežnje, ne le deležev, ker je davek
    funkcija nabavne cene in datuma nakupa — teh dveh podatkov v seriji donosov
    ni in ju ni mogoče rekonstruirati za nazaj.

    `rebalance_mask` pove, na katere dneve se sme trgovati. Brez njega je pot
    uteži pri kupi in drži konstantna in simulacija ne more ločiti "cilj je še
    vedno 55 %" od "danes uravnavamo na 55 %", zato bi vsak dan trgovala nazaj na
    cilj. To ni majhna razlika: davek in provizije bi se zaračunali 252-krat na
    leto namesto enkrat, in ravno kupi in drži, ki naj bi bil davčno najbolj
    učinkovit, bi izpadel kot najdražji. Če maske ni, se trguje takrat, ko se
    cilj spremeni, plus na prvi dan.

    Davek se obračuna po koledarskem letu in plača iz gotovine v `pay_month`
    naslednjega leta, kar ustreza roku za odmero. Plačilo zmanjša premoženje in
    s tem naprej sestavlja — to je razlog, zakaj davčni zaostanek raste hitreje
    od same stopnje.
    """
    idx = weights.index
    cols = [c for c in weights.columns if c in prices.columns]
    P = prices[cols].reindex(idx).ffill()
    W = weights[cols].reindex(idx).fillna(0.0)

    lots: Dict[str, List[_Lot]] = {c: [] for c in cols}
    units: Dict[str, float] = {c: 0.0 for c in cols}
    cash = initial
    fee = fee_per_side_pct / 100.0

    if rebalance_mask is None:
        changed = W.diff().abs().sum(axis=1) > 1e-9
        changed.iloc[0] = True
        trade_today = changed.to_numpy()
    else:
        # An owned array, not a view. pandas hands back a read-only buffer for a
        # constant Series, and writing the first bar into it raises.
        trade_today = rebalance_mask.reindex(idx).fillna(False).to_numpy(dtype=bool, copy=True)
        trade_today[0] = True

    eq_pre = np.empty(len(idx))
    eq_after = np.empty(len(idx))
    tax_paid = np.zeros(len(idx))
    realised = np.zeros(len(idx))
    events: Dict[int, List[Tuple[float, float]]] = {}   # leto -> odsvojitve
    settled: set = set()                    # leta, za katera je davek že plačan
    pre_units: Dict[str, float] = {c: 0.0 for c in cols}
    pre_cash = initial

    for i, ts in enumerate(idx):
        px = P.iloc[i]
        # --- vrednost pred davkom: ista pot, brez plačil davka ---------------
        value_pre = pre_cash + sum(pre_units[c] * px[c] for c in cols)
        value = cash + sum(units[c] * px[c] for c in cols)

        # --- plačilo lanskega davka -----------------------------------------
        if ts.month == pay_month and (i == 0 or idx[i - 1].month != pay_month):
            y = ts.year - 1
            due = 0.0 if y in settled else _net_year_tax(events.get(y, []))
            settled.add(y)
            if due > 0:
                # pobere se iz gotovine; če je ni dovolj, se proda sorazmerno
                if cash < due:
                    need = due - cash
                    for c in cols:
                        hold = units[c] * px[c]
                        if hold <= 0 or value <= 0:
                            continue
                        sell_val = min(hold, need * hold / max(value - cash, 1e-9))
                        u = sell_val / px[c]
                        proc, ev = _sell_fifo(lots[c], u, px[c], ts, tax)
                        units[c] -= u
                        cash += proc * (1 - fee)
                        events.setdefault(ts.year, []).extend(ev)
                cash -= due
                tax_paid[i] = due
                value = cash + sum(units[c] * px[c] for c in cols)

        # --- preuteži na cilj, a le na dan uravnavanja -----------------------
        if not trade_today[i]:
            eq_after[i] = cash + sum(units[c] * px[c] for c in cols)
            eq_pre[i] = pre_cash + sum(pre_units[c] * px[c] for c in cols)
            continue
        for c in cols:
            target_val = W.iloc[i][c] * value
            cur_val = units[c] * px[c]
            diff = target_val - cur_val
            if abs(diff) < value * 1e-6:
                continue
            if diff < 0:
                u = min(units[c], -diff / px[c])
                proc, ev = _sell_fifo(lots[c], u, px[c], ts, tax)
                units[c] -= u
                cash += proc * (1 - fee)
                events.setdefault(ts.year, []).extend(ev)
                realised[i] += sum(g for g, _ in ev)
            else:
                spend = min(diff, max(cash, 0.0))
                u = spend / px[c] * (1 - fee)
                if u > 0:
                    units[c] += u
                    lots[c].append(_Lot(ts, u, px[c] / (1 - fee)))
                    cash -= spend
            # ista poteza na poti brez davka
            tv = W.iloc[i][c] * value_pre
            cv = pre_units[c] * px[c]
            d = tv - cv
            if abs(d) >= value_pre * 1e-6:
                if d < 0:
                    u = min(pre_units[c], -d / px[c])
                    pre_units[c] -= u
                    pre_cash += u * px[c] * (1 - fee)
                else:
                    spend = min(d, max(pre_cash, 0.0))
                    pre_units[c] += spend / px[c] * (1 - fee)
                    pre_cash -= spend

        eq_after[i] = cash + sum(units[c] * px[c] for c in cols)
        eq_pre[i] = pre_cash + sum(pre_units[c] * px[c] for c in cols)

    # --- davek ob unovčenju vsega na zadnji dan ------------------------------
    last = idx[-1]
    px = P.iloc[-1]
    unpaid = [ev for y, ev in events.items() if y not in settled]
    final_events: List[Tuple[float, float]] = [e for ev in unpaid for e in ev]
    for c in cols:
        if units[c] > 0:
            _, ev = _sell_fifo(list(lots[c]), units[c], px[c], last, tax)
            final_events.extend(ev)
    terminal = _net_year_tax(final_events)

    e_pre = pd.Series(eq_pre, index=idx) / initial
    e_aft = pd.Series(eq_after, index=idx) / initial
    return AfterTaxResult(
        pre_tax=e_pre.pct_change().fillna(0.0),
        after_tax=e_aft.pct_change().fillna(0.0),
        equity_pre=e_pre, equity_after=e_aft,
        tax_paid=pd.Series(tax_paid, index=idx),
        realised_gain=pd.Series(realised, index=idx),
        terminal_tax=float(terminal),
        meta=dict(regime=tax.name, as_of=tax.as_of, initial=initial,
                  fee_per_side_pct=fee_per_side_pct))


def simulate_inr(weights: pd.DataFrame, prices: pd.DataFrame,
                 inr: INRTax = INR_2026, fee_per_side_pct: float = 0.20,
                 initial: float = 100_000.0, hold_years: float = 15.0,
                 rebalance_mask: Optional[pd.Series] = None) -> AfterTaxResult:
    """Ista pot na INR: med potjo brez davka, ob koncu enkrat.

    Kapital se tu jemlje kot dan (`initial`), kar je zavestna poenostavitev:
    prava dinamika vplačil je omejena na 20.000 EUR prvo leto in 5.000 EUR nato,
    zato INR v resnici ne more takoj prevzeti večjega zneska. Za primerjavo
    *davčnih ureditev* pri isti poti je to prav; za načrtovanje dejanskega
    portfelja je treba upoštevati `annual_limit` in `lifetime_limit`, ki sta
    zato v tem objektu in ne skrita v kodi.
    """
    idx = weights.index
    cols = [c for c in weights.columns if c in prices.columns]
    P = prices[cols].reindex(idx).ffill()
    W = weights[cols].reindex(idx).fillna(0.0)
    fee = fee_per_side_pct / 100.0

    if rebalance_mask is None:
        changed = W.diff().abs().sum(axis=1) > 1e-9
        changed.iloc[0] = True
        trade_today = changed.to_numpy()
    else:
        # An owned array, not a view. pandas hands back a read-only buffer for a
        # constant Series, and writing the first bar into it raises.
        trade_today = rebalance_mask.reindex(idx).fillna(False).to_numpy(dtype=bool, copy=True)
        trade_today[0] = True

    units = {c: 0.0 for c in cols}
    cash = initial
    eq = np.empty(len(idx))
    for i, ts in enumerate(idx):
        px = P.iloc[i]
        value = cash + sum(units[c] * px[c] for c in cols)
        if not trade_today[i]:
            eq[i] = value
            continue
        for c in cols:
            diff = W.iloc[i][c] * value - units[c] * px[c]
            if abs(diff) < value * 1e-6:
                continue
            if diff < 0:
                u = min(units[c], -diff / px[c])
                units[c] -= u
                cash += u * px[c] * (1 - fee)
            else:
                spend = min(diff, max(cash, 0.0))
                units[c] += spend / px[c] * (1 - fee)
                cash -= spend
        eq[i] = cash + sum(units[c] * px[c] for c in cols)

    e = pd.Series(eq, index=idx) / initial
    years = (idx[-1] - idx[0]).days / 365.25
    rate = 0.0 if years >= inr.tax_free_years else inr.rate_on_withdrawal
    gain = max(float(e.iloc[-1]) - 1.0, 0.0) * initial
    return AfterTaxResult(
        pre_tax=e.pct_change().fillna(0.0), after_tax=e.pct_change().fillna(0.0),
        equity_pre=e, equity_after=e,
        tax_paid=pd.Series(0.0, index=idx), realised_gain=pd.Series(0.0, index=idx),
        terminal_tax=float(gain * rate),
        meta=dict(regime=inr.name, as_of=inr.as_of, initial=initial,
                  years=round(years, 2), terminal_rate=rate,
                  annual_limit=inr.annual_limit, lifetime_limit=inr.lifetime_limit,
                  note=("brez izplačil 15 let -> 0 %" if rate == 0
                        else f"izplačilo pred 15 leti -> {rate:.0%}")))


def summarise(res: AfterTaxResult, td: int = 252) -> dict:
    """Troje številk, kot jih zahteva ameriški standard, plus davčni zaostanek."""
    n = len(res.equity_pre)
    yrs = max(n / td, 1e-9)
    pre = float(res.equity_pre.iloc[-1]) ** (1 / yrs) - 1
    aft = float(res.equity_after.iloc[-1]) ** (1 / yrs) - 1
    liq_val = float(res.equity_after.iloc[-1]) - res.terminal_tax / res.meta["initial"]
    liq = max(liq_val, 1e-9) ** (1 / yrs) - 1
    return dict(regime=res.meta.get("regime"),
                cagr_pre_tax=pre, cagr_after_tax=aft, cagr_after_liquidation=liq,
                tax_cost_ratio_pp=(pre - liq) * 100,
                tax_paid_during=float(res.tax_paid.sum()),
                terminal_tax=res.terminal_tax,
                years=round(yrs, 2), note=res.meta.get("note", ""))
