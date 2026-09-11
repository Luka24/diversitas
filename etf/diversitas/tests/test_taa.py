"""Testi za taktično razporeditev.

Poudarek je na treh stvareh, ki bi tiho pokvarile rezultat: pogled v prihodnost,
napačna meja pri ansamblu uvrstitev, in tranše, ki bi se izrodile v eno samo.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from diversitas.taa import (TAAConfig, mom_13612w, mom_ensemble, inverse_vol,
                            min_variance, run_taa)


def _px(n=700, seed=3):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2015-01-01", periods=n, tz="UTC")
    out = {}
    for i, k in enumerate(["A", "B", "C", "D"]):
        drift = 0.0002 * (i + 1)
        vol = 0.004 * (i + 1)
        out[k] = 100 * np.exp(np.cumsum(rng.normal(drift, vol, n)))
    return pd.DataFrame(out, index=idx)


def test_no_lookahead_truncating_does_not_change_the_past():
    """Odrez zadnjih dni ne sme premakniti nobenega prejšnjega donosa."""
    px = _px()
    cfg = TAAConfig(tvegana=("A", "B", "C"), obrambna=("D",), kanarcek=("A", "D"))
    full = run_taa(px, cfg, fee_per_trade_pct=0.2).returns
    cut = run_taa(px.iloc[:-60], cfg, fee_per_trade_pct=0.2).returns
    j = cut.index[:-1]
    assert np.abs(full.reindex(j) - cut.reindex(j)).max() < 1e-12


def test_ranking_and_absolute_filter_are_separate_questions():
    """Razvrstitev pove, katero sredstvo je najboljše; absolutni filter pove, ali
    sploh pridobiva. Najboljše med štirimi padajočimi še vedno pada, zato mora
    biti to dvoje ločeno — sicer Kellerjevo pravilo tiho odpade."""
    from diversitas.taa import abs_pozitiven
    idx = pd.bdate_range("2018-01-01", periods=400, tz="UTC")
    pada = pd.DataFrame({k: 100 * np.exp(np.linspace(0, -0.4 - 0.1 * i, 400))
                         for i, k in enumerate("ABCD")}, index=idx)
    r = mom_ensemble(pada).iloc[-1]
    assert r.max() > 0.9, "razvrstitev mora nekoga postaviti na vrh tudi pri padanju"
    assert not abs_pozitiven(pada).iloc[-1].any(),         "absolutni filter ne sme nobenega padajocega razglasiti za pozitivnega"


def test_13612w_weights_the_recent_month_most():
    """Uteži 12/4/2/1 pomenijo, da zadnji mesec prevlada."""
    idx = pd.bdate_range("2020-01-01", periods=300, tz="UTC")
    flat = pd.Series(100.0, index=idx)
    skok = flat.copy()
    skok.iloc[-21:] = 110.0
    assert mom_13612w(skok).iloc[-1] > mom_13612w(flat).iloc[-1] + 0.1


def test_weights_are_long_only_and_sum_to_one():
    px = _px()
    rets = px.pct_change().fillna(0.0)
    for fn in (inverse_vol, min_variance):
        w = fn(rets, ["A", "B", "C"])
        assert w.min() >= -1e-12
        assert abs(w.sum() - 1.0) < 1e-9


def test_risk_cap_is_respected():
    """Zgornja meja tveganja je deklarirana izbira in mora dejansko držati."""
    px = _px()
    cfg = TAAConfig(tvegana=("A", "B", "C"), obrambna=("D",), kanarcek=("A", "D"),
                    max_tvegano=0.60)
    r = run_taa(px, cfg, fee_per_trade_pct=0.2)
    assert r.risk_on.max() <= 0.60 + 1e-9


def test_partial_move_lowers_turnover_without_changing_average_exposure():
    px = _px()
    base = dict(tvegana=("A", "B", "C"), obrambna=("D",), kanarcek=("A", "D"))
    polna = run_taa(px, TAAConfig(delni_premik=1.0, **base), fee_per_trade_pct=0.2)
    delna = run_taa(px, TAAConfig(delni_premik=0.5, **base), fee_per_trade_pct=0.2)
    assert delna.turnover.sum() < polna.turnover.sum()
    assert abs(delna.risk_on.mean() - polna.risk_on.mean()) < 0.12


def test_more_tranches_reduce_dependence_on_the_start_day():
    """Sreča pri datumu: z več tranšami se razpon rezultatov čez zamike zoži."""
    px = _px()
    base = dict(tvegana=("A", "B", "C"), obrambna=("D",), kanarcek=("A", "D"))

    def razpon(n_transe):
        konci = []
        for zam in (0, 7, 14):
            r = run_taa(px.iloc[zam:], TAAConfig(transe=n_transe, **base),
                        fee_per_trade_pct=0.2).returns
            konci.append(float(np.prod(1 + np.asarray(r))))
        return max(konci) - min(konci)

    assert razpon(12) < razpon(1)


def test_weights_never_exceed_one_hundred_percent():
    px = _px()
    cfg = TAAConfig(tvegana=("A", "B", "C"), obrambna=("D",), kanarcek=("A", "D"))
    r = run_taa(px, cfg, fee_per_trade_pct=0.2)
    assert r.weights.sum(axis=1).max() < 1.0 + 1e-6
