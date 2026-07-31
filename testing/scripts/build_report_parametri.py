"""Build testing/porocilo_parametri_BTC.html — the fourteen sweeps and what to do.

Cut back to what only this page can show: one chart per parameter, what each knob
does, and the action proposed for it. The randomness tests, the ensemble question,
the walk-forward comparison and the equity curves have moved out -- they are about
the strategy rather than about its parameters, and they live in
testing/nacrt_poenostavitve_lean.txt (steps 6 and 8) with their data still in
testing/data/ and their scripts unchanged.

Data in:  testing/data/parametri_BTC.json   (the 14 sweeps, PBO, trial count)
          testing/data/merge_BTC.json       (the derived action per parameter)
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DD = ROOT / "testing" / "data"
D = json.loads((DD / "parametri_BTC.json").read_text(encoding="utf-8"))
MG = json.loads((DD / "merge_BTC.json").read_text(encoding="utf-8"))
OUT = ROOT / "testing" / "porocilo_parametri_BTC.html"

SL = {
 "track_period":       "koliko dni nazaj gledamo razpon cene",
 "track_buf_pct":      "kolikšna rezerva, da signal ne migeta",
 "ma_med_len":         "dolžina srednjega povprečja",
 "ma_long_len":        "dolžina dolgega povprečja (zapornik za medvedji trg)",
 "ma_slope":           "čez koliko dni merimo naklon dolgega povprečja",
 "track_slope_bars":   "čez koliko dni mora razpon rasti",
 "confirm_bars":       "koliko dni mora signal držati pred nakupom",
 "reentry_hold":       "koliko dni premora pred ponovnim nakupom",
 "exit_grace_bars":    "koliko dni potrpimo, preden prodamo",
 "blowoff_dist_pct":   "kako visoko nad razponom velja za pregretost",
 "rsi_len":            "dolžina kazalnika pregretosti",
 "vol_shock_mul":      "kolikšen skok nihajnosti velja za šok",
 "vol_lookback":       "iz koliko dni računamo nihajnost",
 "min_dist_entry_pct": "dodatna razdalja nad razponom ob nakupu",
}
GROUP = {
 "plato": ("Široka ravnina", "var(--good)",
           "Premakni ga za četrtino in se skoraj nič ne zgodi. Natančna vrednost torej ni "
           "pomembna, kar je dobro: pomeni, da ni bila izbrana na srečo."),
 "ostra konica": ("Ozka konica", "var(--crit)",
           "Deluje pri točno tej vrednosti, korak vstran pa pade. To je opozorilo, ne "
           "dosežek — in pri štirih od petih je vrh natanko na vrednosti, ki jo uporabljamo."),
 "inerten": ("Ne naredi ničesar", "var(--muted)",
           "Premakni ga kamorkoli in rezultat se ne spremeni. Pozor: to velja za gumb, ne "
           "nujno za pravilo, ki ga uporablja."),
}
ACT_COL = {"odstraniti": "var(--crit)", "zakleniti": "var(--s2)",
           "pustiti pri miru": "var(--good)"}


def sweep_chart(p, w=430, h=168) -> str:
    xs, ys = p["values"], p["sortino"]
    pad_l, pad_r, pad_t, pad_b = 42, 14, 16, 30
    lo, hi = min(ys), max(ys)
    span = max(hi - lo, 0.05)
    lo, hi = lo - span * .22, hi + span * .22

    def X(i): return pad_l + i / max(len(xs) - 1, 1) * (w - pad_l - pad_r)
    def Y(v): return pad_t + (1 - (v - lo) / (hi - lo)) * (h - pad_t - pad_b)

    out = [f'<svg viewBox="0 0 {w} {h}" role="img">']
    for f in (0.0, 0.5, 1.0):
        gv = lo + (hi - lo) * f
        out.append(f'<line x1="{pad_l}" y1="{Y(gv):.1f}" x2="{w-pad_r}" y2="{Y(gv):.1f}" '
                   f'stroke="var(--grid)"/>')
        out.append(f'<text x="{pad_l-7}" y="{Y(gv)+4:.1f}" text-anchor="end">{gv:.2f}</text>')
    d = " ".join(f'{"M" if i == 0 else "L"}{X(i):.0f},{Y(v):.1f}' for i, v in enumerate(ys))
    out.append(f'<path d="{d}" fill="none" stroke="var(--s1)" stroke-width="2"/>')
    step = max(1, len(xs) // 8)
    for i, (xv, yv) in enumerate(zip(xs, ys)):
        isd = abs(float(xv) - float(p["default"])) < 1e-9
        out.append(f'<circle cx="{X(i):.1f}" cy="{Y(yv):.1f}" r="{5 if isd else 3}" '
                   f'fill="{"var(--s2)" if isd else "var(--s1)"}"/>')
        if isd or i % step == 0:
            st = ' style="fill:var(--s2);font-weight:700"' if isd else ""
            out.append(f'<text x="{X(i):.1f}" y="{h-10}" text-anchor="middle"{st}>'
                       f'{xv:g}</text>')
    out.append(f'<text x="{pad_l-7}" y="{pad_t-4}" text-anchor="end" '
               f'style="font-size:10px">Sortino</text>')
    return "".join(out) + "</svg>"


def main():
    pbo = D["pbo"]
    PLAN = {r["name"]: r for r in MG["parameter_plan"]}
    groups = {k: [p for p in D["params"] if p["kind"] == k] for k in GROUP}

    P: list[str] = []
    A = P.append
    A(f"""<!doctype html><html lang="sl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lean — vseh 14 parametrov (BTC)</title><style>
 :root{{color-scheme:light;--plane:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;
  --muted:#898781;--grid:#e1e0d9;--axis:#c3c2b7;--ring:rgba(11,11,11,.10);
  --band:rgba(11,11,11,.05);--s1:#2a78d6;--s2:#eb6834;--good:#0ca30c;--crit:#d03b3b}}
 @media(prefers-color-scheme:dark){{:root:where(:not([data-theme=light])){{color-scheme:dark;
  --plane:#0d0d0d;--surface:#1a1a19;--ink:#fff;--ink2:#c3c2b7;--muted:#898781;--grid:#2c2c2a;
  --axis:#383835;--ring:rgba(255,255,255,.10);--band:rgba(255,255,255,.07);--s1:#3987e5;
  --s2:#d95926;--good:#2fbf2f;--crit:#e05555}}}}
 :root[data-theme=dark]{{color-scheme:dark;--plane:#0d0d0d;--surface:#1a1a19;--ink:#fff;
  --ink2:#c3c2b7;--muted:#898781;--grid:#2c2c2a;--axis:#383835;--ring:rgba(255,255,255,.10);
  --band:rgba(255,255,255,.07);--s1:#3987e5;--s2:#d95926;--good:#2fbf2f;--crit:#e05555}}
 *{{box-sizing:border-box}}
 body{{margin:0;background:var(--plane);color:var(--ink);
  font:15px/1.62 system-ui,-apple-system,"Segoe UI",sans-serif}}
 main{{max-width:1080px;margin:0 auto;padding:36px 20px 70px}}
 h1{{font-size:25px;margin:0 0 4px;font-weight:650}}
 .sub{{color:var(--ink2);font-size:13.5px;margin:0 0 24px}}
 h2{{font-size:17px;font-weight:650;margin:36px 0 10px;padding-top:14px;
  border-top:1px solid var(--grid)}}
 h2:first-of-type{{border-top:0;margin-top:6px}}
 p{{margin:0 0 12px;max-width:80ch}}
 .cap{{color:var(--ink2);font-size:13px;margin:0 0 12px;max-width:84ch}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(420px,1fr));gap:14px;
  margin:0 0 20px}}
 .card{{background:var(--surface);border:1px solid var(--ring);border-radius:10px;padding:14px}}
 .card h3{{font:600 13.5px ui-monospace,SFMono-Regular,Menlo,monospace;margin:0 0 1px}}
 .card .d{{color:var(--muted);font-size:12px;margin:0 0 8px}}
 .card .read{{font-size:12.5px;margin:9px 0 0;padding:7px 9px;border-radius:7px;
  background:var(--band);color:var(--ink2)}}
 .fig{{background:var(--surface);border:1px solid var(--ring);border-radius:10px;
  padding:16px;margin:0 0 16px;overflow-x:auto}}
 svg{{display:block;width:100%;height:auto;overflow:visible}}
 text{{font:11px system-ui;fill:var(--muted);font-variant-numeric:tabular-nums}}
 table{{border-collapse:collapse;width:100%;font-size:13px;font-variant-numeric:tabular-nums}}
 th,td{{text-align:left;padding:7px 9px;border-bottom:1px solid var(--grid)}}
 th{{color:var(--ink2);font-weight:600;font-size:12px}}
 td.n,th.n{{text-align:right}}
 code{{font:12.5px ui-monospace,SFMono-Regular,Menlo,monospace;background:var(--band);
  padding:1px 5px;border-radius:4px}}
 .tag{{display:inline-block;font-size:10.5px;font-weight:700;letter-spacing:.04em;
  text-transform:uppercase;border-radius:999px;padding:2px 9px;color:#fff}}
 .box{{background:var(--surface);border:1px solid var(--ring);
  border-left:3px solid var(--s2);border-radius:0 10px 10px 0;padding:14px 18px;
  margin:0 0 18px}}
 .box p:last-child{{margin-bottom:0}}
 footer{{margin-top:38px;padding-top:15px;border-top:1px solid var(--grid);
  color:var(--muted);font-size:12.5px}}
</style></head><body><main>

<h1>Vseh {len(D['params'])} parametrov: kaj vsak dela in kako trdna je njegova vrednost</h1>
<p class="sub">Diversitas Lean · BTC · Binance · okno {D['oos_from']} → {D['oos_to']} ·
fee + slippage {D['fee']} % na stran</p>

<p>Vsako od {len(D['params'])} nastavljivih številk smo premikali čez cel razpon, ostale pa
puščali pri miru, in gledali, kaj se zgodi s Sortinom. Skupaj {D['trials_total']} preizkusov.
Oranžna pika na vsakem grafu je vrednost, ki jo strategija uporablja danes.</p>
<p class="cap">Analiza posameznih vstopnih in izstopnih pogojev je v
<code>porocilo_pogoji_BTC.html</code>; načrt dela, testi naključja in preizkušene alternative
so v <code>testing/nacrt_poenostavitve_lean.txt</code>.</p>""")

    # ── the charts ─────────────────────────────────────────────────────────
    for kind, (title, col, expl) in GROUP.items():
        ps = groups[kind]
        if not ps:
            continue
        A(f'<h2><span class="tag" style="background:{col}">{len(ps)} od '
          f'{len(D["params"])}</span>&ensp;{title}</h2>')
        A(f'<p class="cap">{expl}</p>')
        A('<div class="grid">')
        for p in ps:
            r = PLAN[p["name"]]
            acol = ACT_COL[r["action"]]
            edge = ('<span class="tag" style="background:var(--crit);margin-left:8px">'
                    'vrh na privzetku</span>'
                    if kind == "ostra konica"
                    and abs(float(p["best_value"]) - float(p["default"])) < 1e-9 else "")
            A(f'<div class="card"><h3><code>{p["name"]}</code>{edge}</h3>'
              f'<p class="d">{SL[p["name"]]}</p>'
              f'{sweep_chart(p)}'
              f'<p class="read">danes <b>{p["default"]}</b> · najboljša vrednost v preletu '
              f'<b>{p["best_value"]:g}</b> · razpon rezultata čez cel prelet '
              f'<b>{p["rng"]:.2f}</b><br>'
              f'ukrep: <b style="color:{acol}">{r["action"]}</b> — {r["why"]}</p></div>')
        A("</div>")

    A(f"""<footer>
Vir cen: Binance, zamrznjen posnetek. Okno {D['oos_from']} → {D['oos_to']},
fee + slippage {D['fee']} % na stran. {D['trials_total']} preizkusov nastavitev ·
PBO {pbo['value']} ({pbo['paths']} poti, purge/embargo {pbo['purge_embargo']} dni).<br>
Analiza posameznih pogojev: <code>porocilo_pogoji_BTC.html</code>.
Načrt dela, testi naključja in preizkušene alternative:
<code>testing/nacrt_poenostavitve_lean.txt</code>.<br>
Stran gradi <code>testing/scripts/build_report_parametri.py</code>.
</footer></main></body></html>""")

    OUT.write_text("".join(P), encoding="utf-8")
    print(f"-> {OUT}  ({OUT.stat().st_size/1024:.0f} kB)")


if __name__ == "__main__":
    main()
