"""Freeze today's behaviour so the simplification can be proved neutral.

The simplification in step 3 removes three rules that are claimed to do nothing.
The only way to prove that claim is to compare against what the strategy does
right now, and the comparison has to be on the POSITION SERIES rather than on
metrics: identical Sortino and MaxDD can come from different paths, identical
positions cannot.

So this writes the series, its SHA256, and the commit it was taken at, before
anything is touched.

    freeze   write the reference. Refuses to overwrite an existing one without
             --force, because silently replacing it destroys the entire point.
    verify   rebuild from today's code and compare, bar by bar. Exit code 0 if
             identical, 2 if not.

testing/tests/test_reference.py calls verify, so the check runs with the suite
rather than only when someone remembers.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "testing", ROOT / "lean"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import numpy as np
import pandas as pd

from shared.costs import net_returns
from shared.warmup import trim_warmup
from testing.scripts import engine

np.seterr(all="ignore")

SYMBOL, FEE, PPY = "BTC", 0.30, 365
SRC = ROOT / "testing" / "data" / "sources" / f"{SYMBOL}_binance_warmup.parquet"
REF = ROOT / "testing" / "data" / "reference_positions.parquet"
META = ROOT / "testing" / "data" / "reference_positions.json"


def build() -> pd.DataFrame:
    """Today's strategy, on the canonical snapshot. Positions and raw state."""
    raw = pd.read_parquet(SRC)
    cfg = engine.make_config("lean")
    df = trim_warmup(engine.strategy_module("lean")
                     .run_strategy(raw, btc_daily=None, config=cfg).df)
    return pd.DataFrame({
        "position": pd.Series(engine.position(df, s_bull_code=1),
                              index=df.index, dtype="float64"),
        "signal_state": df["signal_state"].astype("int8"),
        "target_alloc": df["target_alloc"].astype("float32"),
    })


def digest(ref: pd.DataFrame) -> str:
    """Hash of the values AND the dates, so a shifted series cannot match."""
    h = hashlib.sha256()
    h.update(np.asarray(ref.index.view("int64")).tobytes())
    for c in sorted(ref.columns):
        h.update(np.ascontiguousarray(ref[c].to_numpy()).tobytes())
    return h.hexdigest()


def metrics(ref: pd.DataFrame) -> dict:
    raw = pd.read_parquet(SRC)
    r = net_returns(ref["position"], raw["close"].pct_change().fillna(0.0),
                    FEE).to_numpy(float)
    eq = np.cumprod(1.0 + r)
    d = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(PPY)
    sd = r.std(ddof=1) * np.sqrt(PPY)
    p = ref["position"].to_numpy()
    return {"sortino": round(float(r.mean() * PPY / d), 3),
            "sharpe": round(float(r.mean() * PPY / sd), 3),
            "cagr": round(float((float(eq[-1]) ** (PPY / len(r)) - 1) * 100), 1),
            "maxdd": round(float((eq / np.maximum.accumulate(eq) - 1).min() * 100), 1),
            "final": round(float(eq[-1]), 3),
            "exposure": round(float(p.mean() * 100), 1),
            "trades": int((np.diff(p, prepend=p[0]) > 0).sum())}


def git_hash() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                              capture_output=True, text=True,
                              timeout=20).stdout.strip() or "?"
    except Exception:
        return "?"


def do_freeze(force: bool) -> int:
    if REF.exists() and not force:
        print(f"Referenca že obstaja: {REF.name}")
        print("Tihi prepis bi uničil ves smisel. Uporabi --force, če to res hočeš.")
        return 1
    ref = build()
    cfg = engine.make_config("lean")
    meta = {
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git": git_hash(),
        "source": SRC.name,
        "symbol": SYMBOL, "fee_per_side_pct": FEE,
        "from": str(ref.index[0].date()), "to": str(ref.index[-1].date()),
        "n_bars": len(ref),
        "sha256": digest(ref),
        "metrics": metrics(ref),
        "config": {k: v for k, v in vars(cfg).items() if not k.startswith("_")
                   and isinstance(v, (int, float, bool, str))},
    }
    REF.parent.mkdir(parents=True, exist_ok=True)
    ref.to_parquet(REF)
    META.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Zamrznjeno  {ref.index[0].date()} → {ref.index[-1].date()}  "
          f"({len(ref)} barov)")
    print(f"  SHA256    {meta['sha256'][:32]}…")
    print(f"  commit    {meta['git'][:12]}")
    m = meta["metrics"]
    print(f"  Sortino {m['sortino']} · Sharpe {m['sharpe']} · CAGR {m['cagr']} % · "
          f"MaxDD {m['maxdd']} % · {m['final']}× · {m['trades']} poslov")
    print(f"  -> {REF.name}, {META.name}")
    return 0


def do_verify(quiet: bool = False) -> int:
    if not REF.exists():
        print("Reference ni. Poženi najprej: freeze_reference.py freeze")
        return 1
    old = pd.read_parquet(REF)
    new = build()
    meta = json.loads(META.read_text(encoding="utf-8"))

    problems = []
    if len(old) != len(new):
        problems.append(f"dolžina {len(old)} → {len(new)}")
    if not old.index.equals(new.index):
        problems.append("indeks se ne ujema")
    if not problems:
        for c in old.columns:
            diff = np.flatnonzero(
                np.abs(old[c].to_numpy(float) - new[c].to_numpy(float)) > 1e-12)
            if len(diff):
                first = old.index[diff[0]].date()
                problems.append(f"{c}: {len(diff)} barov se razlikuje, prvi {first}")

    if problems:
        print("REFERENCA SE NE UJEMA — vedenje se je spremenilo:")
        for p in problems:
            print(f"  {p}")
        print("\nTo pomeni spremenjeno logiko, ne odstranjene mrtve kode.")
        print("USTAVI in poišči vzrok. Ne popravljaj reference.")
        return 2

    now = digest(new)
    if now != meta["sha256"]:
        print(f"SHA256 se ne ujema, čeprav so vrednosti enake — "
              f"{meta['sha256'][:16]}… proti {now[:16]}…")
        return 2
    if not quiet:
        print(f"Ujema se.  {len(new)} barov  {new.index[0].date()} → "
              f"{new.index[-1].date()}")
        print(f"  SHA256 {now[:32]}…")
        print(f"  referenca zamrznjena {meta['created_utc']} pri {meta['git'][:12]}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mode", choices=["freeze", "verify"])
    ap.add_argument("--force", action="store_true",
                    help="dovoli prepis obstoječe reference")
    a = ap.parse_args()
    return do_freeze(a.force) if a.mode == "freeze" else do_verify()


if __name__ == "__main__":
    sys.exit(main())
