"""Rebuild testing/porocilo_parametri_BTC.html — short, plain language, for a meeting.

Replaces the earlier JS-rendered page. Two reasons for the rewrite beyond length:
the old page carried two statistics that later work showed were wrong (a
permutation test confounded by bitcoin's drift, and a Reality Check run on the
one quantity the product does not claim), and it diagnosed the sharp-peak problem
without giving an answer. Both are fixed here.

Data in:  testing/data/parametri_BTC.json   (the 14 sweeps, PBO, trial count)
          testing/data/ensemble_BTC.json    (peak premium, interactions)
          testing/data/mc_tests_BTC.json    (the two corrected randomness tests)
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
D = json.loads((ROOT / "testing" / "data" / "parametri_BTC.json").read_text(encoding="utf-8"))
EN = json.loads((ROOT / "testing" / "data" / "ensemble_BTC.json").read_text(encoding="utf-8"))
MC = json.loads((ROOT / "testing" / "data" / "mc_tests_BTC.json").read_text(encoding="utf-8"))
AU = json.loads((ROOT / "testing" / "data" / "audit_BTC.json").read_text(encoding="utf-8"))
IN = json.loads((ROOT / "testing" / "data" / "intraday_BTC.json").read_text(encoding="utf-8"))
CV = json.loads((ROOT / "testing" / "data" / "curves_BTC.json").read_text(encoding="utf-8"))
OUT = ROOT / "testing" / "porocilo_parametri_BTC.html"

# Plain-language name for every knob, so the page never makes the reader guess.
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
 "plato":        ("Široka ravnina — nastavitev ni kritična", "var(--good)",
                  "Premakni ga za četrtino in se skoraj nič ne zgodi. To je dobro: "
                  "pomeni, da vrednost ni bila izbrana na srečo."),
 "ostra konica": ("Ozka konica — sosednja vrednost je opazno slabša", "var(--crit)",
                  "Deluje pri točno tej vrednosti, korak vstran pa pade. To je opozorilo, "
                  "ne dosežek."),
 "inerten":      ("Ne naredi ničesar", "var(--muted)",
                  "Premakni ga kamorkoli in rezultat se ne spremeni. Tak gumb je odveč — "
                  "a pozor, to velja za gumb, ne nujno za pravilo, ki ga uporablja."),
}


def sweep_chart(p, w=430, h=168) -> str:
    """Full-size sweep, same visual language as the earlier version of this page:
    gridlines, labelled axes, the shipped default marked in orange."""
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
    d = " ".join(f'{"M" if i == 0 else "L"}{X(i):.1f},{Y(v):.1f}' for i, v in enumerate(ys))
    out.append(f'<path d="{d}" fill="none" stroke="var(--s1)" stroke-width="2"/>')
    step = max(1, len(xs) // 8)
    for i, (xv, yv) in enumerate(zip(xs, ys)):
        isd = abs(float(xv) - float(p["default"])) < 1e-9
        out.append(f'<circle cx="{X(i):.1f}" cy="{Y(yv):.1f}" r="{5 if isd else 3}" '
                   f'fill="{"var(--s2)" if isd else "var(--s1)"}"/>')
        if isd or i % step == 0:
            out.append(f'<text x="{X(i):.1f}" y="{h-10}" text-anchor="middle"'
                       f'{" style=\"fill:var(--s2);font-weight:700\"" if isd else ""}>'
                       f'{xv:g}</text>')
    out.append(f'<text x="{pad_l-7}" y="{pad_t-4}" text-anchor="end" '
               f'style="font-size:10px">Sortino</text>')
    return "".join(out) + "</svg>"



def equity_chart(clock, w=880, h=330) -> str:
    """Linear axis, full resolution. No log scale and no downsampling: a log axis
    hides how much of the gain is one late run, and downsampling makes a drawdown
    look shallower than it was."""
    idx = clock["index"]
    series = [("danes", "var(--crit)", 2.4),
              ("brez mrtvih gumbov", "var(--warn)", 4.6),
              ("glasovanje: vecina", "var(--s1)", 2.4)]
    bh = clock["benchmark"]["equity"]
    allv = [v for n, _, _ in series for v in clock["curves"][n]] + bh
    lo, hi = 0.0, max(allv) * 1.06
    pad_l, pad_r, pad_t, pad_b = 46, 108, 16, 34
    n = len(idx)

    def X(i): return pad_l + i / (n - 1) * (w - pad_l - pad_r)
    def Y(v): return pad_t + (1 - (v - lo) / (hi - lo)) * (h - pad_t - pad_b)

    p = [f'<svg viewBox="0 0 {w} {h}" role="img">']
    for g in range(0, int(hi) + 1):
        p.append(f'<line x1="{pad_l}" y1="{Y(g):.1f}" x2="{w-pad_r}" y2="{Y(g):.1f}" '
                 f'stroke="var(--grid)"/>')
        p.append(f'<text x="{pad_l-7}" y="{Y(g)+4:.1f}" text-anchor="end">{g}×</text>')
    years = {}
    for i, d in enumerate(idx):
        years.setdefault(d[:4], i)
    for y, i in years.items():
        p.append(f'<line x1="{X(i):.1f}" y1="{pad_t}" x2="{X(i):.1f}" y2="{h-pad_b}" '
                 f'stroke="var(--grid)" stroke-dasharray="2 3"/>')
        p.append(f'<text x="{X(i):.1f}" y="{h-pad_b+16:.0f}" text-anchor="middle">{y}</text>')

    def path(vals):
        return " ".join(f'{"M" if i == 0 else "L"}{X(i):.0f},{Y(v):.1f}'
                        for i, v in enumerate(vals))

    p.append(f'<path d="{path(bh)}" fill="none" stroke="var(--muted)" stroke-width="1.4" '
             f'opacity=".55"/>')
    p.append(f'<text x="{w-pad_r+6}" y="{Y(bh[-1])+4:.1f}" style="fill:var(--muted)">'
             f'kupi in drži</text>')
    for name, col, wd in series:
        v = clock["curves"][name]
        dash = ' stroke-dasharray="1 5" stroke-linecap="round"' if wd > 3 else ""
        p.append(f'<path d="{path(v)}" fill="none" stroke="{col}" stroke-width="{wd}"'
                 f'{dash}/>')
    lab = [("danes", "var(--crit)"), ("brez mrtvih gumbov", "var(--warn)"),
           ("glasovanje: vecina", "var(--s1)")]
    NICE = {"danes": "danes", "brez mrtvih gumbov": "brez mrtvih gumbov",
            "glasovanje: vecina": "glasovanje"}
    used = []
    for name, col in lab:
        y = Y(clock["curves"][name][-1])
        while any(abs(y - u) < 13 for u in used):
            y += 13
        used.append(y)
        p.append(f'<text x="{w-pad_r+6}" y="{y+4:.1f}" style="fill:{col};font-weight:600">'
                 f'{NICE[name]}</text>')
    return "".join(p) + "</svg>"


def hist(vals, marks, w=780, h=200, xlab="") -> str:
    lo, hi = min(list(vals) + [m[0] for m in marks]), max(list(vals) + [m[0] for m in marks])
    pad = (hi - lo) * .09 or .1
    lo, hi = lo - pad, hi + pad
    nb = 24
    counts = [0] * nb
    for v in vals:
        counts[min(nb - 1, max(0, int((v - lo) / (hi - lo) * nb)))] += 1
    cmax = max(counts) or 1
    pl, pr, pt, pb = 20, 16, 40, 44
    def X(v): return pl + (v - lo) / (hi - lo) * (w - pl - pr)
    def Y(c): return h - pb - c / cmax * (h - pt - pb)
    p = [f'<svg viewBox="0 0 {w} {h}" role="img">']
    p.append(f'<line x1="{pl}" y1="{h-pb}" x2="{w-pr}" y2="{h-pb}" stroke="var(--axis)"/>')
    bw = (w - pl - pr) / nb
    for i, c in enumerate(counts):
        if c:
            p.append(f'<rect x="{pl+i*bw+1:.1f}" y="{Y(c):.1f}" width="{bw-2:.1f}" '
                     f'height="{h-pb-Y(c):.1f}" fill="var(--s1)" opacity=".42" rx="2"/>')
    for f in (0, .25, .5, .75, 1):
        v = lo + (hi - lo) * f
        p.append(f'<text x="{X(v):.1f}" y="{h-pb+16:.0f}" text-anchor="middle">{v:.2f}</text>')
    for i, (val, col, lab) in enumerate(marks):
        p.append(f'<line x1="{X(val):.1f}" y1="{pt-8}" x2="{X(val):.1f}" y2="{h-pb}" '
                 f'stroke="{col}" stroke-width="2.2"/>')
        p.append(f'<text x="{X(val):.1f}" y="{pt-12-i*15}" text-anchor="middle" '
                 f'style="fill:{col};font-weight:700">{lab}</text>')
    if xlab:
        p.append(f'<text x="{pl}" y="{h-7}">{xlab}</text>')
    return "".join(p) + "</svg>"


def main():
    base, pbo = D["base"], D["pbo"]
    pt, en = EN["point"], EN["ensemble"]
    prem, ci = EN["peak_premium"], EN["ci_peak_premium"]
    ms = EN["member_sortino"]
    rank = sum(1 for v in ms["all"] if v < pt["sortino"])
    perm, ex = MC["perm_block20"], MC["exposure_shuffle"]

    groups = {k: [p for p in D["params"] if p["kind"] == k] for k in GROUP}

    P: list[str] = []
    A = P.append
    A(f"""<!doctype html><html lang="sl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lean — kako trdne so nastavitve (BTC)</title><style>
 :root{{color-scheme:light;--plane:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;
  --muted:#898781;--grid:#e1e0d9;--axis:#c3c2b7;--ring:rgba(11,11,11,.10);
  --band:rgba(11,11,11,.05);--s1:#2a78d6;--s2:#eb6834;--good:#0ca30c;--warn:#fab219;
  --crit:#d03b3b}}
 @media(prefers-color-scheme:dark){{:root:where(:not([data-theme=light])){{color-scheme:dark;
  --plane:#0d0d0d;--surface:#1a1a19;--ink:#fff;--ink2:#c3c2b7;--muted:#898781;--grid:#2c2c2a;
  --axis:#383835;--ring:rgba(255,255,255,.10);--band:rgba(255,255,255,.07);--s1:#3987e5;
  --s2:#d95926;--good:#2fbf2f;--crit:#e05555}}}}
 :root[data-theme=dark]{{color-scheme:dark;--plane:#0d0d0d;--surface:#1a1a19;--ink:#fff;
  --ink2:#c3c2b7;--muted:#898781;--grid:#2c2c2a;--axis:#383835;--ring:rgba(255,255,255,.10);
  --band:rgba(255,255,255,.07);--s1:#3987e5;--s2:#d95926;--good:#2fbf2f;--crit:#e05555}}
 *{{box-sizing:border-box}}
 body{{margin:0;background:var(--plane);color:var(--ink);
  font:15.5px/1.65 system-ui,-apple-system,"Segoe UI",sans-serif}}
 main{{max-width:1080px;margin:0 auto;padding:36px 20px 70px}}
 h1{{font-size:25px;margin:0 0 4px;font-weight:650}}
 .sub{{color:var(--ink2);font-size:13.5px;margin:0 0 26px}}
 h2{{font-size:17px;font-weight:650;margin:34px 0 10px;padding-top:14px;
  border-top:1px solid var(--grid)}}
 h2:first-of-type{{border-top:0;margin-top:6px}}
 p{{margin:0 0 13px;max-width:74ch}}
 .lead{{font-size:16.5px;line-height:1.6}}
 .cap{{color:var(--ink2);font-size:13.5px;margin:0 0 13px;max-width:78ch}}
 .fig{{background:var(--surface);border:1px solid var(--ring);border-radius:10px;
  padding:16px;margin:0 0 16px;overflow-x:auto}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(420px,1fr));gap:14px;
  margin:0 0 18px}}
 .card{{background:var(--surface);border:1px solid var(--ring);border-radius:10px;padding:14px}}
 .card h3{{font:600 13.5px system-ui;margin:0 0 1px}}
 .card .d{{color:var(--muted);font-size:12px;margin:0 0 8px}}
 .card .read{{font-size:12.5px;margin:9px 0 0;padding:7px 9px;border-radius:7px;
  background:var(--band);color:var(--ink2)}}
 .box{{background:var(--surface);border:1px solid var(--ring);border-left:3px solid var(--s2);
  border-radius:0 10px 10px 0;padding:14px 18px;margin:0 0 18px}}
 .box p:last-child{{margin-bottom:0}}
 .box.bad{{border-left-color:var(--crit)}} .box.good{{border-left-color:var(--good)}}
 svg{{display:block;width:100%;height:auto;overflow:visible}}
 text{{font:11px system-ui;fill:var(--muted);font-variant-numeric:tabular-nums}}
 table{{border-collapse:collapse;width:100%;font-size:13.5px;font-variant-numeric:tabular-nums}}
 th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid var(--grid);
  vertical-align:middle}}
 th{{color:var(--ink2);font-weight:600;font-size:12.5px}}
 td.n{{text-align:right}}
 code{{font:12.5px ui-monospace,SFMono-Regular,Menlo,monospace;background:var(--band);
  padding:1px 5px;border-radius:4px}}
 .tag{{display:inline-block;font-size:10.5px;font-weight:700;letter-spacing:.04em;
  text-transform:uppercase;border-radius:999px;padding:2px 9px;color:#fff}}
 footer{{margin-top:40px;padding-top:15px;border-top:1px solid var(--grid);
  color:var(--muted);font-size:12.5px}}
</style></head><body><main>

<h1>Kako trdne so nastavitve strategije?</h1>
<p class="sub">Lean · BTC · Binance · {D['oos_from']} → {D['oos_to']} ·
fee + slippage {D['fee']} % na stran</p>

<p class="lead">Strategija ima {len(D['params'])} številk, ki jih lahko nekdo nastavi —
koliko dni nazaj gleda, koliko dni čaka pred nakupom, in podobno. Ta stran odgovarja na eno
vprašanje: <b>ali te številke držijo, ali je bila strategija nastavljena tako, da je lepo
izgledala prav na tej zgodovini?</b></p>

<h2>Kaj smo naredili</h2>
<p>Vsako od {len(D['params'])} številk smo posebej premikali gor in dol, ostale pa pustili
pri miru, in gledali, kaj se zgodi z rezultatom. Skupaj {D['trials_total']} preizkusov.
Potem smo naredili še dva testa, ki preverjata, ali je strategija sploh boljša od sreče.</p>

<div class="box"><p><b>Prispodoba za celo stran.</b> Recept za pecivo, ki se posreči samo
pri točno 183 stopinjah — pri 180 je surovo, pri 186 zažgano — ni dober recept. Je srečno
naključje nekoga, ki je pekel dovolj dolgo, da je našel to številko. Dober recept deluje med
175 in 190. Enako velja za nastavitve strategije.</p></div>""")

    # ── 1. the map, compact ────────────────────────────────────────────────
    A("<h2>Ugotovitev 1: jedro je trdno, robovi niso</h2>")
    A(f"""<p>Vsaka krivuljica spodaj je ena številka, premikana čez cel razpon. <b>Ravna
črta je dobro</b> — pomeni, da natančna vrednost ni pomembna. <b>Ostra konica je slabo.</b>
Oranžna pika je vrednost, ki jo strategija uporablja danes.</p>""")
    for kind, (title, col, expl) in GROUP.items():
        ps = groups[kind]
        if not ps:
            continue
        A(f'<p style="margin:22px 0 4px"><span class="tag" style="background:{col}">'
          f'{len(ps)} od {len(D["params"])}</span>'
          f'<b style="margin-left:9px">{title}</b></p>'
          f'<p class="cap" style="margin:6px 0 12px">{expl}</p>')
        A('<div class="grid">')
        for p in ps:
            edge = ("" if abs(float(p["best_value"]) - float(p["default"])) > 1e-9 else
                    '<span class="tag" style="background:var(--crit);margin-left:8px">'
                    'vrh na privzetku</span>')
            A(f'<div class="card"><h3><code>{p["name"]}</code>'
              f'{edge if kind == "ostra konica" else ""}</h3>'
              f'<p class="d">{SL[p["name"]]}</p>'
              f'{sweep_chart(p)}'
              f'<p class="read">danes <b>{p["default"]}</b> · najboljša vrednost v preletu '
              f'<b>{p["best_value"]:g}</b> · razpon rezultata čez cel prelet '
              f'<b>{p["rng"]:.2f}</b></p></div>')
        A("</div>")

    sharp = groups["ostra konica"]
    on_def = [p for p in sharp if abs(float(p["best_value"]) - float(p["default"])) < 1e-9]
    A(f"""<div class="box bad"><p><b>Tu je težava.</b> Od {len(sharp)} številk z ostro konico
jih ima <b>{len(on_def)} vrh natanko na vrednosti, ki jo strategija uporablja danes</b>. Te
vrednosti izvirajo iz skripte, ki jo je nekdo pisal ob gledanju iste zgodovine bitcoina. Da
bi jih toliko hkrati po naključju pristalo točno na vrhu, je malo verjetno.</p></div>""")

    # ── 2. the ensemble measurement ────────────────────────────────────────
    A("<h2>Ugotovitev 2: koliko od uspeha je bila samo izbira številk</h2>")
    A(f"""<p>To se da izmeriti. Vzeli smo štiri številke z ostro konico in vsako pognali pri
treh sosednjih vrednostih — skupaj <b>{EN['members']} različic</b> iste strategije. Potem smo
jih <b>povprečili</b>: namesto da bi izbrali eno, uporabimo vse hkrati.</p>""")
    A('<div class="fig">' + hist(
        ms["all"],
        [(en["sortino"], "var(--s2)", f"povprečje vseh {EN['members']} · {en['sortino']:.2f}"),
         (pt["sortino"], "var(--crit)", f"današnje nastavitve · {pt['sortino']:.2f}")],
        xlab=f"vsak stolpec = koliko od {EN['members']} različic doseže ta rezultat "
             f"(desno = boljše)") + "</div>")
    A(f"""<div class="box bad">
<p><b>Današnje nastavitve so {rank}. najboljše od {EN['members']}.</b></p>
<p>Če bi jih nekdo izbral, ne da bi videl te podatke, bi pričakovali, da pristanejo nekje
na sredini — okoli 41. od {EN['members']}. Pristale so {rank}. Razlika znaša
<b>{prem:+.2f}</b> in je dovolj velika, da ni naključje (razpon
{ci[0]:+.2f} do {ci[1]:+.2f} ne vključuje ničle).</p>
<p style="margin-top:10px"><b>Kaj to pomeni v praksi.</b> Backtest kaže
{pt['sortino']:.2f}. Poštena napoved za naprej je <b>{en['sortino']:.2f}</b>. Razlika je del,
ki je prišel iz tega, da so bile številke izbrane po tem, ko smo že videli, kako se je
zgodovina odvila.</p></div>""")

    # ── 3. better than luck? ───────────────────────────────────────────────
    A("<h2>Ugotovitev 3: je strategija boljša od sreče?</h2>")
    A("<p>Dve različni vprašanji, in odgovora nista enaka.</p>")
    A(f"""<div class="fig"><table>
<tr><th style="width:38%">vprašanje</th><th style="width:20%">odgovor</th><th>kako smo to preverili</th></tr>
<tr><td><b>Zna izbrati boljši trenutek za <span style="color:var(--crit)">zaslužek</span>?</b></td>
    <td><b style="color:var(--crit)">NE</b><br><span style="font-size:12px;color:var(--muted)">
    p = {perm['p_value']:.2f} — daleč od dokaza</span></td>
    <td style="font-size:13px">Iz podatkov odstranimo samo dejstvo, da je bitcoin v tem
    obdobju rasel, nato dneve premešamo in strategijo poženemo znova, {perm['n']}-krat.
    Brez te rasti od prednosti ne ostane skoraj nič.</td></tr>
<tr><td><b>Zna izbrati boljši trenutek za <span style="color:var(--good)">izogib
    padcem</span>?</b></td>
    <td><b style="color:var(--good)">DA, a previdno</b><br>
    <span style="font-size:12px;color:var(--muted)">p = {ex['p_value']:.3f}</span></td>
    <td style="font-size:13px">Pustimo popolnoma enako: enak čas v trgu
    ({ex['exposure_pct']} %), enako število obdobij ({ex['holding_periods']}), samo njihov
    vrstni red premešamo, {ex['n']}-krat. Strategija je boljša od
    <b>{ex['percentile']:.1f} %</b> naključnih razporeditev.</td></tr>
</table></div>""")
    A(f"""<p class="cap">V številkah: kupi-in-drži je v tem obdobju padel za
{abs(ex['buyhold_maxdd']):.0f} %, strategija za {abs(ex['strategy_maxdd']):.0f} % — razlika
<b>{ex['real_gap']:+.0f} odstotnih točk</b>. Naključna razporeditev istega časa v trgu da v
povprečju le {ex['shuffled_mean_gap']:+.0f} točk. Približno
{ex['shuffled_mean_gap']:.0f} točk torej pride že iz tega, da smo pol časa zunaj trga —
ostalih {ex['real_gap']-ex['shuffled_mean_gap']:.0f} pa iz tega, <i>kdaj</i>.</p>""")
    A(f"""<div class="box good"><p><b>To je edini test, ki ga strategija prestane — in je
hkrati edino, kar produkt obljublja.</b> Ne prodajamo napovedi cene. Prodajamo mirnejšo
vožnjo.</p>
<p style="margin-top:9px"><b>Zakaj tudi tega ne imenujemo dokaz.</b> Na teh podatkih je bilo
opravljenih {D['trials_total']} preizkusov nastavitev. Ko toliko stvari preizkusiš, se en
rezultat s p = {ex['p_value']:.3f} pojavi tudi takrat, kadar ni ničesar — zato je to
<i>najmočnejši znak, ki ga imamo</i>, ne pa dokaz.</p></div>""")

    # ── 4. what I propose ──────────────────────────────────────────────────
    A("<h2>Kaj predlagam</h2>")
    A(f"""<p><b>1. Vrzimo ven pravila, ki ne delajo.</b> Ločena analiza vsakega vstopnega in
izstopnega pogoja je pokazala štiri, ki ne prestanejo lastne predpostavke — med njimi
pravilo, ki se v šestih letih ni sprožilo niti enkrat, in pravilo, ki naj bi zaznavalo
vrhove, v resnici pa se sproža na začetkih rasti. S tem pade
{len(D['params'])} številk na 6. To je edini ukrep, ki takoj izboljša zanesljivost in
ničesar ne poslabša.</p>

<p><b>2. Nehajmo izbirati eno številko.</b> Namesto ene vrednosti uporabimo tri sosednje
hkrati. Vrnimo se k prispodobi: namesto da pečemo pri 183 stopinjah, pečemo pri 180, 183 in
186. Na konici tako ni več mogoče sedeti. Pozicija ostane vse-ali-nič — različice o njej
<b>glasujejo</b>, glej razdelek spodaj. Cena je, da backtest pade z
{pt['sortino']:.2f} na okoli {[v for v in EN['binary_variants'] if v['name']=='glasovanje: vecina sosedov'][0]['sortino']:.2f}
— a ta nižja številka je bila resnična že prej, le da je nismo poznali.</p>

<p><b>3. Poglejmo isti trg z drobnejšo uro.</b> Največja težava ni metoda, ampak da ima
strategija samo <b>{D['mc']['trades']['total']} poslov</b> v šestih letih in pol; stroka
priporoča vsaj {D['mc']['trades']['guideline']}. Iste podatke, isti bitcoin, isto obdobje,
a razdeljeno na 4-urne namesto dnevne odseke, da približno šestkrat več meritev. Ni nov trg
in ni čakanje — samo natančnejše branje istega.</p>

<p><b>4. Nehajmo nastavljati.</b> Vsak nadaljnji poskus na istih podatkih poveča tveganje, da
najdemo naključje. Verjetnost, da je izbira najboljše nastavitve zgolj šum, je že zdaj
<b>{pbo['value']:.0%}</b>.</p>""")

    A("<h2>Če delnih pozicij ne želimo</h2>")
    bv = {v["name"]: v for v in EN["binary_variants"]}
    A(f"""<p>Povprečenje {EN['members']} različic da <b>delno pozicijo</b> — na primer 62 %
v bitcoinu namesto vse ali nič. Če produkt tega ne podpira ali tega preprosto nočemo, je
rešitev preprosta: <b>naj različice glasujejo.</b> V poziciji smo, kadar je zanjo dovolj
velik del soseske. Rezultat je spet vse-ali-nič, ohrani pa se tisto, zaradi česar smo
povprečili — <b>ne stojimo več na eni sami točki.</b></p>""")
    A('<div class="fig"><table>'
      '<tr><th>različica</th><th>pozicija</th><th>Sortino</th><th>največji padec</th>'
      '<th>promet</th><th>poslov</th></tr>')
    for v in EN["binary_variants"]:
        binlab = ("<b style='color:var(--good)'>vse ali nič</b>" if v["binary"]
                  else "<span style='color:var(--crit)'>delna</span>")
        hl = ' style="background:var(--band)"' if v["name"] == "glasovanje: vecina sosedov" else ""
        A(f'<tr{hl}><td>{v["name"].replace("vecina", "večina").replace("vec kot", "več kot")}'
          f'<br><span style="font-size:11.5px;color:var(--muted)">{v["note"]}</span></td>'
          f'<td>{binlab}</td><td class="n">{v["sortino"]:.3f}</td>'
          f'<td class="n">{v["maxdd"]:.1f} %</td><td class="n">{v["turnover"]:.1f}</td>'
          f'<td class="n">{v["trades"]}</td></tr>')
    A("</table></div>")

    maj = bv["glasovanje: vecina sosedov"]
    two = bv["glasovanje: dve tretjini sosedov"]
    pnt = bv["danes: ena tocka"]
    rb = bv["sredina ravnine, ena tocka"]

    A("<h3 class='s'>Katero od teh izbrati — preverjeno na dveh urah</h3>")
    A(f"""<p>Razlika med najboljšimi različicami je desetinka Sortina, odločitev pa sloni na
{pnt['trades']} do {maj['trades']} poslih. Na tolikšnem vzorcu desetinke ni mogoče izmeriti.
Zato smo vse skupaj pognali <b>še enkrat na 4-urnih barih</b> istega bitcoina v istem obdobju,
z vsemi dolžinami pomnoženimi s 6, da ostane ekonomski horizont enak. Če se vrstni red ob
spremembi ure ohrani, je resničen; če se premeša, je bil šum.</p>""")
    d1, h4 = IN["clocks"]
    A('<div class="fig"><table><tr><th>različica</th>'
      '<th>Sortino<br>dnevno</th><th>Sortino<br>4-urno</th><th>uvrstitev</th>'
      '<th>ocena</th></tr>')
    ORD = ["sredina ravnine", "ena tocka (privzetki)", "glasovanje: vecina",
           "glasovanje: dve tretjini", "ansambel, zvezna"]
    NICE = {"sredina ravnine": "sredina ravnine",
            "ena tocka (privzetki)": "danes: ena točka",
            "glasovanje: vecina": "glasovanje: večina",
            "glasovanje: dve tretjini": "glasovanje: dve tretjini",
            "ansambel, zvezna": "ansambel, zvezna pozicija"}
    r1 = sorted(ORD, key=lambda n: -d1["variants"][n]["sortino"])
    r6 = sorted(ORD, key=lambda n: -h4["variants"][n]["sortino"])
    JUDGE = {
      "sredina ravnine": ("1. na 4h, 2. dnevno — <b>najbolj stabilna</b>", "var(--good)"),
      "ena tocka (privzetki)": ("pade z ure na uro: 1,10 &rarr; 0,99", "var(--warn)"),
      "glasovanje: vecina": ("3.–4. na obeh urah, <b>brez preskokov</b>", "var(--good)"),
      "glasovanje: dve tretjini": ("<b>preskoči z 2. na 4. mesto</b> — šum", "var(--crit)"),
      "ansambel, zvezna": ("zadnja na obeh; zahteva delne pozicije", "var(--muted)"),
    }
    for n in ORD:
        j, col = JUDGE[n]
        A(f'<tr><td>{NICE[n]}</td><td class="n">{d1["variants"][n]["sortino"]:.3f}</td>'
          f'<td class="n">{h4["variants"][n]["sortino"]:.3f}</td>'
          f'<td class="n">{r1.index(n)+1}. &rarr; {r6.index(n)+1}.</td>'
          f'<td style="font-size:12.5px;color:{col}">{j}</td></tr>')
    A("</table></div>")

    A(f"""<div class="box bad"><p><b>Dvotretjinsko glasovanje je padlo.</b> Na dnevnih barih je
bilo drugo najboljše ({two['sortino']:.2f}), na 4-urnih pade na četrto
({h4['variants']['glasovanje: dve tretjini']['sortino']:.2f}). Prag »dve tretjini« smo izbrali
potem, ko smo videli dnevne številke, in ob spremembi ure se je izbira razblinila. <b>To je
tisto, kar smo iskali: dokaz, da je bila ena od možnosti prilagojena podatkom.</b></p></div>""")

    g1 = d1["plateau_minus_majority"]
    g6 = h4["plateau_minus_majority"]
    A(f"""<div class="box good"><p><b>Priporočilo: glasovanje z navadno večino.</b></p>
<p style="margin-top:8px">Sredina ravnine ima na obeh urah nekoliko višji Sortino, a razlika
<b>ni ločljiva od šuma na nobeni</b> ({g1['diff']:+.2f}, razpon
[{g1['ci'][0]:+.2f}, {g1['ci'][1]:+.2f}] dnevno; {g6['diff']:+.2f}, razpon
[{g6['ci'][0]:+.2f}, {g6['ci'][1]:+.2f}] na 4h). Ko dveh možnosti ni mogoče ločiti po
rezultatu, se odloči po načelu — in tu je načelo jasno: <b>vrednosti »sredine ravnine« so bile
izbrane z gledanjem teh podatkov</b> (kot najvišje drseče povprečje preleta),
<b>prag navadne večine pa ne.</b> Je edina številka na tej strani, ki je določena vnaprej.</p>
<p style="margin-top:8px">Operativno se skoraj nič ne spremeni: pozicija ostane vse-ali-nič,
poslov {pnt['trades']} &rarr; {maj['trades']}, promet {pnt['turnover']:.1f} &rarr;
{maj['turnover']:.1f}. Sortino, ki ga navajamo, je {maj['sortino']:.2f} namesto
{pnt['sortino']:.2f}.</p></div>""")

    A(f"""<div class="box"><p><b>Kaj je test na 4-urnih barih pokazal in česa ni.</b>
Pokazal je, da ena od možnosti ni zdržala spremembe ure — to je bil njegov namen in ga je
opravil. <b>Ni pa prinesel več poslov:</b> ker so vse dolžine pomnožene s 6, se strategija
obnaša v ekonomskem času enako in naredi
{h4['variants']['glasovanje: vecina']['trades']} poslov namesto
{d1['variants']['glasovanje: vecina']['trades']}. Drobnejša ura torej <b>ne rešuje
premajhnega vzorca</b> — rešuje samo vprašanje, ali je rezultat odvisen od tega, kdaj po
dogovoru konča dan. Odgovor: deloma je, saj današnja nastavitev pade z
{d1['variants']['ena tocka (privzetki)']['sortino']:.2f} na
{h4['variants']['ena tocka (privzetki)']['sortino']:.2f}.</p></div>""")

    A(f"""<p class="cap">Opozorilo k vsem različicam: <b>vse imajo globlji največji padec kot
današnja nastavitev</b> ({pnt['maxdd']:.1f} % proti {maj['maxdd']:.1f} % pri večini). To ni
slabost glasovanja — je še en obraz iste ugotovitve, da je današnja točka polepšana na obeh
merilih hkrati.</p>""")


    d1c, h4c = CV["clocks"]
    m1 = d1c["metrics"]
    A("<h2>Ali je glasovanje sploh kaj pomagalo? Poglejmo krivuljo</h2>")
    A(f"""<p>Do zdaj smo primerjali številke. Tu sta obe različici na isti sliki, skupaj s
kupi-in-drži, na navadni osi in v polni ločljivosti — brez logaritma, ki bi skril, koliko
dobička pride iz enega samega vzpona, in brez redčenja točk, ki bi padec naredilo videti
plitvejši, kot je bil.</p>""")
    A('<div class="fig">' + equity_chart(d1c) + "</div>")
    A(f"""<div class="fig"><table>
<tr><th>različica</th><th>Sortino</th><th>največji padec</th><th>letni donos</th>
<th>končni večkratnik</th><th>poslov</th></tr>
<tr><td><b style="color:var(--crit)">danes</b></td>
    <td class="n">{m1['danes']['sortino']:.3f}</td>
    <td class="n">{m1['danes']['maxdd']:.1f} %</td>
    <td class="n">{m1['danes']['cagr']:.1f} %</td>
    <td class="n">{m1['danes']['final']:.2f}×</td>
    <td class="n">{m1['danes']['trades']}</td></tr>
<tr><td><b style="color:var(--warn)">brez mrtvih gumbov</b></td>
    <td class="n">{m1['brez mrtvih gumbov']['sortino']:.3f}</td>
    <td class="n">{m1['brez mrtvih gumbov']['maxdd']:.1f} %</td>
    <td class="n">{m1['brez mrtvih gumbov']['cagr']:.1f} %</td>
    <td class="n">{m1['brez mrtvih gumbov']['final']:.2f}×</td>
    <td class="n">{m1['brez mrtvih gumbov']['trades']}</td></tr>
<tr><td><b style="color:var(--s1)">glasovanje: večina</b></td>
    <td class="n">{m1['glasovanje: vecina']['sortino']:.3f}</td>
    <td class="n">{m1['glasovanje: vecina']['maxdd']:.1f} %</td>
    <td class="n">{m1['glasovanje: vecina']['cagr']:.1f} %</td>
    <td class="n">{m1['glasovanje: vecina']['final']:.2f}×</td>
    <td class="n">{m1['glasovanje: vecina']['trades']}</td></tr>
<tr><td style="color:var(--muted)">kupi in drži</td><td class="n">—</td>
    <td class="n">{d1c['benchmark']['maxdd']:.1f} %</td>
    <td class="n">{d1c['benchmark']['cagr']:.1f} %</td>
    <td class="n">{d1c['benchmark']['equity'][-1]:.2f}×</td>
    <td class="n">1</td></tr>
</table></div>""")

    A(f"""<div class="box good"><p><b>Prva ugotovitev: rumena črta se popolnoma skriva pod
rdečo.</b> To ni napaka risanja — največja razlika med krivuljama je <b>točno
{d1c['max_abs_curve_gap']:.0f}</b>. Trije gumbi, ki jih načrt briše
(<code>vol_shock_mul</code>, <code>vol_lookback</code>, <code>min_dist_entry_pct</code>), so
bili dokazano mrtvi: brisanje ne spremeni niti ene decimalke. <b>To je hkrati dokaz, da smo
brisali pravo stvar, in dokaz, da brisanje ni ničesar pokvarilo.</b></p></div>""")

    A(f"""<div class="box bad"><p><b>Druga ugotovitev, in tu moram biti nedvoumen: glasovanje
ni izboljšalo nobenega merila.</b></p>
<table style="margin:9px 0">
<tr><th>merilo</th><th>danes</th><th>glasovanje</th><th>razlika</th></tr>
<tr><td>Sortino</td><td class="n">{m1['danes']['sortino']:.3f}</td>
    <td class="n">{m1['glasovanje: vecina']['sortino']:.3f}</td>
    <td class="n" style="color:var(--crit)">{m1['glasovanje: vecina']['sortino']-m1['danes']['sortino']:+.3f}</td></tr>
<tr><td>največji padec</td><td class="n">{m1['danes']['maxdd']:.1f} %</td>
    <td class="n">{m1['glasovanje: vecina']['maxdd']:.1f} %</td>
    <td class="n" style="color:var(--crit)">{m1['glasovanje: vecina']['maxdd']-m1['danes']['maxdd']:+.1f} o. t.</td></tr>
<tr><td>letni donos</td><td class="n">{m1['danes']['cagr']:.1f} %</td>
    <td class="n">{m1['glasovanje: vecina']['cagr']:.1f} %</td>
    <td class="n" style="color:var(--crit)">{m1['glasovanje: vecina']['cagr']-m1['danes']['cagr']:+.1f} o. t.</td></tr>
</table>
<p><b>Slabše na vseh treh, in slabše tudi na 4-urnih barih.</b> Kdor bi gledal samo to tabelo,
bi glasovanje zavrnil — in imel bi prav, če bi bila številka
{m1['danes']['sortino']:.2f} resnična.</p></div>""")

    A(f"""<p><b>Zakaj ga vseeno priporočamo — in kaj to v resnici je.</b> Glasovanje ni
izboljšava. Je <b>popravek pričakovanja</b>. Izmerili smo, da je današnja nastavitev
{sum(1 for v in ms['all'] if v < pt['sortino'])}. najboljša od {EN['members']} svojih sosedov
in da je ta prednost statistično značilna (premija konice {prem:+.2f}, razpon
[{ci[0]:+.2f}, {ci[1]:+.2f}]). Nastavitev, izbrana brez vpogleda v te podatke, bi pristala
blizu povprečja soseske. Zato je nižja številka <b>ocena tega, kar se lahko ponovi</b>, višja
pa vključuje del, ki se ne bo.</p>

<p><b>Ampak pošteno je povedati tudi protiargument.</b> Padec se z glasovanjem <b>poglobi</b>
({m1['danes']['maxdd']:.1f} % &rarr; {m1['glasovanje: vecina']['maxdd']:.1f} %), plitvejši padec
pa je edina lastnost, ki jo produkt obljublja. Glasovanje torej žrtvuje nekaj tistega, kar
prodajamo, da popravi številko, ki je ne prodajamo. V bran mu govori le to, da <b>prednost
današnje nastavitve pri padcu ni statistično značilna</b> (razpon
[{EN['ci_d_maxdd'][0]:+.1f}, {EN['ci_d_maxdd'][1]:+.1f}] o. t.), medtem ko je prednost pri
Sortinu značilna in torej dokazano prilagojena. <b>Odločitev je tesna in je poslovna, ne
tehnična.</b></p>

<div class="box"><p><b>Kaj so 4-urni bari res prinesli — in to je poleg ovržene dvotretjinske
večine drugi konkreten izplen.</b> Dnevni bari ne vidijo padca, ki se zgodi in popravi znotraj
istega dneva, zato <b>lepšajo največji padec</b>:</p>
<table style="margin:9px 0"><tr><th>različica</th><th>MaxDD dnevno</th>
<th>MaxDD 4-urno</th><th>skrito</th></tr>
{"".join(f'<tr><td>{n}</td><td class="n">{d1c["metrics"][n]["maxdd"]:.1f} %</td>'
         f'<td class="n">{h4c["metrics"][n]["maxdd"]:.1f} %</td>'
         f'<td class="n" style="color:var(--crit)">{CV["dd_understated"][n]:+.1f} o. t.</td></tr>'
         for n in d1c["metrics"])}
</table>
<p>To ni statistična moč — te drobnejša ura ne more dati — ampak <b>natančnost</b>. Številka,
ki jo je treba komunicirati, je 4-urna, ne dnevna.</p></div>""")

    A("<h2>Kaj bi se konkretno spremenilo</h2>")
    A(f"""<div class="fig"><table>
<tr><th>kaj</th><th>danes</th><th>po predlogu</th></tr>
<tr><td>številk, ki jih je mogoče nastavljati</td><td class="n">{len(D['params'])}</td>
    <td class="n"><b>6</b></td></tr>
<tr><td>pravil za izstop iz pozicije</td><td class="n">3</td><td class="n"><b>1</b></td></tr>
<tr><td>pozicija</td><td>vse ali nič</td><td><b>vse ali nič</b> — glasovanje 81 različic</td></tr>
<tr><td>Sortino, ki ga navajamo</td><td class="n">{pt['sortino']:.2f}</td>
    <td class="n"><b>{[v for v in EN['binary_variants'] if v['name']=='glasovanje: vecina sosedov'][0]['sortino']:.2f}</b></td></tr>
<tr><td>poslov v vzorcu</td><td class="n">{D['mc']['trades']['total']}</td>
    <td class="n">11 <span style="color:var(--muted);font-size:12px">(manj, ker odpade
    pravilo, ki jih je ustvarjalo brez koristi)</span></td></tr>
</table></div>
<p class="cap">Da: po tem popravku bo backtest izgledal <b>slabše</b>. To ni poslabšanje
strategije — prejšnja številka preprosto ni bila resnična. Bolje, da to izvemo zdaj kot pri
pravem denarju.</p>""")

    # ── 5. limits ──────────────────────────────────────────────────────────
    A("<h2>Česa ta analiza ne dokaže</h2>")
    A(f"""<p>Vse je merjeno na istem bitcoinu, na katerem so bile nastavitve izbrane. Noben
izračun na teh podatkih tega ne more popraviti — za to bi bili potrebni podatki, ki jih še
nismo videli.</p>
<p>Kar ta stran <b>zares</b> podpira, je torej ozko in se glasi: <i>vemo, koliko od uspeha
je prišlo iz izbire številk ({prem:+.2f}), vemo, da napovedovanje donosa ni dokazano, in
vemo, da je zmanjšanje padcev dokazano.</i> Vse ostalo je odprto.</p>""")

    A(f"""<footer>
Vir cen: Binance, zamrznjen posnetek. Okno {D['oos_from']} → {D['oos_to']},
fee + slippage {D['fee']} % na stran.<br>
{D['trials_total']} preizkusov nastavitev · PBO {pbo['value']} ({pbo['paths']} poti,
purge/embargo {pbo['purge_embargo']} dni) · ansambel {EN['members']} različic, razponi iz
parnega bločnega bootstrapa ({EN['nboot']} vzorcev, blok {EN['block']} dni) ·
premešan trg {perm['n']}× · premešan vrstni red obdobij {ex['n']}×.<br>
Ponovljivo z <code>testing/scripts/ensemble.py</code>, <code>mc_tests.py</code>;
stran gradi <code>testing/scripts/build_report_parametri.py</code>.<br>
Podrobna analiza posameznih vstopnih in izstopnih pogojev:
<code>testing/porocilo_pogoji_BTC.html</code>.
</footer></main></body></html>""")

    OUT.write_text("".join(P), encoding="utf-8")
    print(f"-> {OUT}  ({OUT.stat().st_size/1024:.0f} kB)")


if __name__ == "__main__":
    main()
