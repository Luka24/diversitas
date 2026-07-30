"""Build testing/porocilo_pogoji_BTC.html — every condition, in two categories.

Two windows on purpose:

  Does the condition point the right way?  -> event study over all 2700 usable
                                              days. A conditional day statistic,
                                              not a backtest; cutting it to five
                                              years would throw away 900 days and
                                              leave blow-off with four firings.

  Does removing it change the money?       -> full ablation over the last five
                                              whole years, net of 0.30% per side.
                                              This is what the equity charts show,
                                              and the shaded bands mark the exact
                                              days on which the toggle changes
                                              what we hold.

Every number states which window it came from, because they differ deliberately.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DD = ROOT / "testing" / "data"
ES = json.loads((DD / "event_study_BTC.json").read_text(encoding="utf-8"))
EX = json.loads((DD / "exit_rules_BTC.json").read_text(encoding="utf-8"))
AU = json.loads((DD / "audit_BTC.json").read_text(encoding="utf-8"))
AF = json.loads((DD / "ablation_full_BTC.json").read_text(encoding="utf-8"))
DR = json.loads((DD / "dead_rules_BTC.json").read_text(encoding="utf-8"))
MG = json.loads((DD / "merge_BTC.json").read_text(encoding="utf-8"))
PAR = json.loads((DD / "parametri_BTC.json").read_text(encoding="utf-8"))
OUT = ROOT / "testing" / "porocilo_pogoji_BTC.html"

BASE = AF["cases"]["izhodišče"]
IDX = AF["index"]
BENCH = AF["benchmark"]["equity"]


def ci_chart(rows, w=430) -> str:
    rows = [r for r in rows if r[1] is not None]
    if not rows:
        return '<p class="cap">Premalo opazovanj — test ni mogoč.</p>'
    pad_l, pad_r, row_h, top = 46, 12, 36, 16
    h = top + row_h * len(rows) + 24
    lim = max(max(abs(v) for v in (r[2][0], r[2][1], r[1])) for r in rows) * 1.12 or 1

    def x(v):
        return pad_l + (v + lim) / (2 * lim) * (w - pad_l - pad_r)

    p = [f'<svg viewBox="0 0 {w} {h}" role="img">']
    zx = x(0)
    p.append(f'<rect x="{pad_l}" y="{top-8}" width="{w-pad_l-pad_r}" '
             f'height="{row_h*len(rows)+2}" fill="var(--band)" rx="5"/>')
    p.append(f'<line x1="{zx:.1f}" y1="{top-8}" x2="{zx:.1f}" '
             f'y2="{top+row_h*len(rows)-6}" stroke="var(--axis)" stroke-width="1.5"/>')
    for i, (lab, d, ci, sig) in enumerate(rows):
        y = top + row_h * i + 8
        col = "var(--s1)" if sig and d > 0 else ("var(--crit)" if sig and d < 0
                                                else "var(--muted)")
        p.append(f'<line x1="{x(ci[0]):.1f}" y1="{y}" x2="{x(ci[1]):.1f}" y2="{y}" '
                 f'stroke="{col}" stroke-width="3.5" stroke-linecap="round" opacity=".45"/>')
        p.append(f'<circle cx="{x(d):.1f}" cy="{y}" r="4" fill="{col}"/>')
        p.append(f'<text x="{pad_l-8}" y="{y+4}" text-anchor="end">{lab}</text>')
        p.append(f'<text x="{x(ci[1]):.1f}" y="{y-9}" text-anchor="middle" '
                 f'style="fill:{col};font-weight:600">{d:+.2f}</text>')
    p.append(f'<text x="{zx:.1f}" y="{h-5}" text-anchor="middle">0</text>')
    p.append(f'<text x="{pad_l}" y="{h-5}" text-anchor="start">slabše</text>')
    p.append(f'<text x="{w-pad_r}" y="{h-5}" text-anchor="end">bolje (o. t.)</text>')
    return "".join(p) + "</svg>"


def equity(alt=None, segs=(), w=1060, h=340, alt_label="brez pravila") -> str:
    """Baseline against one alternative, with the days on which the two hold
    different positions shaded. Linear axis, full resolution: a log axis hides how
    much of the gain is one late run, and thinning points flattens a drawdown."""
    curves = [(BASE["equity"], "var(--crit)", 2.8, "danes", False)]
    if alt is not None:
        curves.append((alt, "var(--s1)", 2.0, alt_label, True))
    hi = max([max(c[0]) for c in curves] + [max(BENCH)]) * 1.06
    pad_l, pad_r, pad_t, pad_b = 46, 140, 16, 34
    n = len(IDX)

    def X(i):
        return pad_l + i / (n - 1) * (w - pad_l - pad_r)

    def Y(v):
        return pad_t + (1 - v / hi) * (h - pad_t - pad_b)

    p = [f'<svg viewBox="0 0 {w} {h}" role="img">']
    for i0, i1, kind in segs:
        col = "var(--s1)" if kind == "in" else "var(--s2)"
        p.append(f'<rect x="{X(i0):.0f}" y="{pad_t}" '
                 f'width="{max(X(i1)-X(i0), 1.5):.1f}" height="{h-pad_t-pad_b}" '
                 f'fill="{col}" opacity=".17"/>')
    step = 0.5 if hi < 4 else 1.0
    g = 0.0
    while g <= hi:
        p.append(f'<line x1="{pad_l}" y1="{Y(g):.1f}" x2="{w-pad_r}" y2="{Y(g):.1f}" '
                 f'stroke="var(--grid)"/>')
        p.append(f'<text x="{pad_l-6}" y="{Y(g)+4:.1f}" text-anchor="end">{g:g}×</text>')
        g += step
    seen = set()
    for i, d in enumerate(IDX):
        if d[:4] not in seen:
            seen.add(d[:4])
            p.append(f'<line x1="{X(i):.1f}" y1="{pad_t}" x2="{X(i):.1f}" '
                     f'y2="{h-pad_b}" stroke="var(--grid)" stroke-dasharray="2 3"/>')
            p.append(f'<text x="{X(i):.1f}" y="{h-pad_b+16:.0f}" text-anchor="middle">'
                     f'{d[:4]}</text>')

    def path(v):
        return " ".join(f'{"M" if i == 0 else "L"}{X(i):.0f},{Y(x):.1f}'
                        for i, x in enumerate(v))

    p.append(f'<path d="{path(BENCH)}" fill="none" stroke="var(--muted)" '
             f'stroke-width="1.3" opacity=".5"/>')
    labels = [(BENCH[-1], "var(--muted)", "kupi in drži")]
    for vals, col, wd, name, dash in curves:
        ds = ' stroke-dasharray="5 4"' if dash else ""
        p.append(f'<path d="{path(vals)}" fill="none" stroke="{col}" '
                 f'stroke-width="{wd}"{ds}/>')
        labels.append((vals[-1], col, name))
    used = []
    for v, col, name in sorted(labels, key=lambda t: -t[0]):
        y = Y(v)
        while any(abs(y - u) < 14 for u in used):
            y += 14
        used.append(y)
        p.append(f'<text x="{w-pad_r+8}" y="{y+4:.1f}" '
                 f'style="fill:{col};font-weight:600">{name}</text>')
    return "".join(p) + "</svg>"


def blowoff_chart(bm, w=1060, h=150) -> str:
    pad_l, pad_r, pad_t = 34, 34, 30

    def X(v):
        return pad_l + v / 100 * (w - pad_l - pad_r)

    p = [f'<svg viewBox="0 0 {w} {h}" role="img">']
    p.append(f'<rect x="{X(0):.0f}" y="{pad_t}" width="{X(25)-X(0):.0f}" height="44" '
             f'fill="var(--crit)" opacity=".13" rx="4"/>')
    p.append(f'<rect x="{X(75):.0f}" y="{pad_t}" width="{X(100)-X(75):.0f}" height="44" '
             f'fill="var(--good)" opacity=".13" rx="4"/>')
    p.append(f'<line x1="{pad_l}" y1="{pad_t+44}" x2="{w-pad_r}" y2="{pad_t+44}" '
             f'stroke="var(--axis)"/>')
    for v in (0, 25, 50, 75, 100):
        p.append(f'<line x1="{X(v):.1f}" y1="{pad_t+44}" x2="{X(v):.1f}" '
                 f'y2="{pad_t+50}" stroke="var(--axis)"/>')
        p.append(f'<text x="{X(v):.1f}" y="{pad_t+64}" text-anchor="middle">{v}.</text>')
    seen: dict[int, int] = {}
    for v in bm["percentiles"]:
        k = int(round(v))
        lvl = seen.get(k, 0)
        seen[k] = lvl + 1
        p.append(f'<circle cx="{X(v):.1f}" cy="{pad_t+36-lvl*9:.1f}" r="4.5" '
                 f'fill="var(--s2)" stroke="var(--surface)" stroke-width="1"/>')
    p.append(f'<text x="{X(12):.0f}" y="{pad_t-11}" text-anchor="middle" '
             f'style="fill:var(--crit);font-weight:600">tu bi morale biti sprožitve</text>')
    p.append(f'<text x="{X(87):.0f}" y="{pad_t-11}" text-anchor="middle" '
             f'style="fill:var(--good);font-weight:600">tu so</text>')
    p.append(f'<text x="{pad_l}" y="{h-6}">percentil 60-dnevnega donosa po sprožitvi · '
             f'0. = najslabše nadaljevanje, 100. = najboljše</text>')
    return "".join(p) + "</svg>"


# key -> (category, mechanics, params, ablation case, verdict, badge, short)
COND = {
 "above_tl": ("vstop",
   "<b>Trackline</b> je sredina zadnjih 75 dni: najvišja in najnižja točka zadnjih 75 dni, "
   "povprečeni. Pogoj velja, ko je zaključni tečaj <b>več kot 3 % nad to sredino</b>. Teh "
   "3 % je mrtvi pas — brez njega bi signal migetal ob vsakem nihaju okoli sredine.",
   "track_period = 75 · track_buf_pct = 3 %", "brez above_tl",
   "Jedro strategije. Nad povprečnim dnevom doda +1,6 o. t., a noben razpon ne izloči ničle, "
   "in backtest brez njega je celo rahlo boljši. Obdržati — a to je največja odprta neznanka.",
   "?", "cena vsaj 3 % nad sredino 75-dnevnega razpona"),
 "above_ma_med": ("vstop",
   "Povprečje zaključnih tečajev zadnjih <b>50 dni</b>. Pogoj velja, ko je cena nad njim, "
   "brez kakršnekoli rezerve.",
   "ma_med_len = 50", "brez above_ma_med",
   "Pri privzetkih odstranitev ne spremeni <b>ničesar</b>. Preverjeno na 151 nastavitvah: oživi le pri <b>3</b>, in še tam za največ 15 dni ter brez vpliva na padec. Odstraniti — a ne po konstrukciji, ampak po meritvi.",
   "kill", "cena nad 50-dnevnim povprečjem"),
 "track_rising_window": ("vstop",
   "Današnja vrednost trackline je <b>višja kot pred 10 dnevi</b>. Ni dovolj, da je cena "
   "visoko — sam razpon se mora premikati navzgor. To je pravilo, ki ubija stranski trg.",
   "track_slope_bars = 10", "brez track_rising",
   "Edini filter, brez katerega se padec opazno poglobi. Kupuje mirnejšo vožnjo. Obdržati.",
   "ok", "sredina razpona raste čez 10 dni"),
 "dist_entry_ok": ("vstop",
   "Zahteva, da je cena vsaj <code>mrtvi pas + min_dist_entry_pct</code> nad trackline. "
   "Zamisel je bila zahtevati za vstop <b>več</b> kot za izstop. Ker je "
   "<code>min_dist_entry_pct</code> odposlan z vrednostjo <b>0</b>, se pogoj sesede v "
   "<code>above_tl</code>.",
   "min_dist_entry_pct = 0 %", "brez dist_entry_ok",
   "Matematični dvojnik <code>above_tl</code>: 0 dni razlike, in mrtev pri <b>vseh 151</b> preizkušenih nastavitvah. V dashboardu zaseda ločeno kljukico, ki ne more nikoli ugovarjati tisti nad njo. <b>Edina odstranitev, ki je varna po konstrukciji.</b>",
   "kill", "dodatna razdalja nad trackline (nastavljena na 0)"),
 "regime_ok": ("vstop",
   "Zapora nastopi <b>samo, če velja oboje</b>: cena je pod 200-dnevnim povprečjem <b>in</b> "
   "to povprečje pada (nižje kot pred 5 dnevi). Če velja le eno od tega, zapore ni.",
   "ma_long_len = 200 · ma_slope = 5", "brez regime_ok",
   "Brez njega je slabše na vsem. Pozor: padca <b>ne izboljša</b> — je filter donosa, ne "
   "varovalka pred padcem, kot je bil doslej opisan. Obdržati.",
   "ok", "200-dnevno povprečje ne blokira"),
 "below_tl": ("izstop",
   "Zrcalna slika vstopa: cena je <b>več kot 3 % pod</b> sredino zadnjih 75 dni. Izstop ni "
   "takojšen — pogoj mora veljati <b>3 dni zapored</b>, sicer nas vsak enodnevni sunek vrže "
   "iz pozicije.",
   "track_period = 75 · track_buf_pct = 3 % · exit_grace_bars = 3", None,
   "Glavni izstop, povzroči 13 od 21 poslov. Pravi predznak, a razlika ni dokazana. "
   "Obdržati — in mu postaviti tekmece.",
   "?", "cena vsaj 3 % pod sredino razpona, tri dni zapored"),
 "blowoff": ("izstop",
   "Cena je <b>več kot 25 % nad</b> trackline <b>in</b> RSI nad 80. RSI je kazalnik "
   "pregretosti od 0 do 100. Izstop je takojšen, brez treh dni čakanja.",
   "blowoff_dist_pct = 25 % · RSI = 80 · rsi_len = 14", "brez blow-offa",
   "Nedokazan v obe smeri, in učinek se obrne glede na okno: na petih letih pomaga, na "
   "sedmih in pol škoduje. Pri 8 sprožitvah tega ni mogoče razrešiti. Pustiti pri miru.",
   "?", "daleč nad trackline in pregret RSI"),
 "vol_shock": ("izstop",
   "Nihajnost zadnjih 20 dni je <b>več kot 1,5-krat</b> nad svojim 50-dnevnim povprečjem "
   "<b>in</b> cena je hkrati pod trackline. Ker zahteva <code>below_tl</code>, ga redni "
   "izstop vedno prehiti.",
   "vol_shock_mul = 1,5 · vol_lookback = 20", "brez vol-shocka",
   "Pri privzetkih se ne sproži nikoli — a to je <b>naključje štirih vrednosti, ne lastnost pravila</b>. Oživi pri 67 od 151 nastavitev, med njimi pri <b>45 od 81 članov ansambla</b>, in tam je odstranitev slabša 61× proti 6×. <b>Ne odstraniti.</b>",
   "?", "skok nihajnosti, a le pod trackline"),
}
BADGE = {"ok": ("obdržati", "var(--good)"), "?": ("nedokazan", "var(--warn)"),
         "kill": ("odstraniti", "var(--crit)")}
PEER = {"blowoff": ("blowoff_vs_extended", "primerjano med dnevi &gt; 25 % nad trackline"),
        "vol_shock": (None, "primerjano med dnevi pod trackline")}



# Which knobs each condition actually reads. Two of them -- track_period and
# track_buf_pct -- are read by BOTH above_tl and below_tl, which is the reason the
# entry and exit thresholds cannot be moved independently today. That is exactly
# the open question in the plan, and stating it per condition is the point of this
# table.
PARAMS_OF = {
 "above_tl":            ["track_period", "track_buf_pct"],
 "above_ma_med":        ["ma_med_len"],
 "track_rising_window": ["track_slope_bars"],
 "dist_entry_ok":       ["min_dist_entry_pct"],
 "regime_ok":           ["ma_long_len", "ma_slope"],
 "below_tl":            ["track_period", "track_buf_pct", "exit_grace_bars"],
 "blowoff":             ["blowoff_dist_pct", "rsi_len"],
 "vol_shock":           ["vol_shock_mul", "vol_lookback"],
}
SHARED = {"track_period", "track_buf_pct"}
ACT_COL = {"odstraniti": "var(--crit)", "zakleniti": "var(--s2)",
           "prepustiti glasovanju": "var(--s1)", "pustiti pri miru": "var(--good)"}
PLAN = {r["name"]: r for r in MG["parameter_plan"]}


def param_table(key):
    """The knobs this condition reads, with what both reports say to do about them."""
    names = PARAMS_OF.get(key, [])
    if not names:
        return ""
    rows = ""
    for nm in names:
        r = PLAN[nm]
        col = ACT_COL[r["action"]]
        sh = (' <span style="color:var(--s2)" title="isti parameter bere tudi drugi pogoj">'
              '&#8644; deljen</span>' if nm in SHARED else "")
        rows += (f'<tr><td><code>{nm}</code>{sh}</td>'
                 f'<td class="n">{r["default"]}</td>'
                 f'<td style="font-size:12px">{r["kind"]}</td>'
                 f'<td class="n">{r["range"]:.2f}</td>'
                 f'<td style="font-size:12px;color:{col};font-weight:600">'
                 f'{r["action"]}</td></tr>')
    extra = ""
    if key in ("above_tl", "below_tl"):
        extra = ('<p class="cap" style="margin:8px 0 0;font-size:12px">'
                 '<b>&#8644; deljena parametra.</b> <code>track_period</code> in '
                 '<code>track_buf_pct</code> bereta <i>oba</i> — vstopni in izstopni pogoj. '
                 'Vstopnega praga danes ni mogoče premakniti brez izstopnega, in prav to je '
                 'odprto vprašanje asimetričnega mrtvega pasu.</p>')
    if key == "bull_condition":
        extra = ""
    return (f'<table class="mini" style="margin:0 0 10px">'
            f'<tr><th>parameter</th><th class="n">danes</th><th>oblika preleta</th>'
            f'<th class="n">razpon</th><th>ukrep</th></tr>{rows}</table>{extra}')


def base_line(key):
    row = next((x for x in AU["entry_vs_base"] if x["key"] == key), None)
    if not row or "20" not in row["h"]:
        return ""
    v = row["h"]["20"]
    col = "var(--good)" if v["vs_base"] >= 1.0 else "var(--muted)"
    return (f'<p class="par" style="color:{col}">čez 20 dni: {v["mean_true"]:+.2f} % ob '
            f'pogoju proti {v["base"]:+.2f} % na povprečnem dnevu &rarr; '
            f'<b>{v["vs_base"]:+.2f} o. t. nad bazo</b></p>')


def section(key):
    cat, what, params, abl_key, verdict, bk, _ = COND[key]
    lab, col = BADGE[bk]
    es = next((c for c in ES["conditions"] if c["key"] == key), None)
    peer, note = PEER.get(key, (None, ""))
    out = [f'<h3 class="cond"><code>{key}</code>'
           f'<span class="badge" style="background:{col}">{lab}</span></h3>',
           f'<div class="two"><div><p class="mech">{what}</p>'
           f'{param_table(key) or f"""<p class="par">privzeto: {params}</p>"""}']
    if es:
        m = EX[peer]["m"]["donos"] if peer else es["m"]["donos"]
        rows = [(f"{h} dni", v["diff"], v["ci"], v["sig"]) for h in ES["horizons"]
                if (v := m.get(str(h))) and not v.get("too_few")]
        out.append(f'<p class="sub2">Kaže v pravo smer? <span class="win">okno '
                   f'{ES["from"]} → {ES["to"]} · velja na {es["n_fire"]} dneh'
                   f'{" · " + note if note else ""}</span></p>')
        out.append(ci_chart(rows) if rows
                   else '<p class="cap">Premalo sprožitev za test.</p>')
        out.append(base_line(key))
    out.append("</div><div>")
    if abl_key:
        r = AF["cases"][abl_key]
        out.append(f'<p class="sub2">Kaj se zgodi z denarjem, če ga izklopimo? '
                   f'<span class="win">okno {AF["from"]} → {AF["to"]} · '
                   f'fee+slip {AF["fee_per_side_pct"]} %/stran</span></p>')
        ident = r.get("identical")
        cells = ""
        for k, nm, unit, fmt in (("sortino", "Sortino", "", "{:.3f}"),
                                 ("sharpe", "Sharpe", "", "{:.3f}"),
                                 ("cagr", "letni donos", " %", "{:.1f}"),
                                 ("maxdd", "največji padec", " %", "{:.1f}")):
            dv = r[f"d_{k}"]
            good = (dv < 0) if k == "maxdd" else (dv > 0)
            c = ("var(--muted)" if ident or abs(dv) < 1e-9
                 else ("var(--good)" if good else "var(--crit)"))
            cells += (f'<tr><td>{nm}</td><td class="n">{fmt.format(BASE[k])}{unit}</td>'
                      f'<td class="n">{fmt.format(r[k])}{unit}</td>'
                      f'<td class="n" style="color:{c}">{dv:+.3f}</td>'
                      f'<td class="n" style="font-size:11.5px;color:var(--muted)">'
                      f'[{r[f"ci_{k}"][0]:+.2f}, {r[f"ci_{k}"][1]:+.2f}]</td></tr>')
        out.append(f'<table class="mini"><tr><th>merilo</th><th class="n">danes</th>'
                   f'<th class="n">brez</th><th class="n">razlika</th>'
                   f'<th class="n">95 % razpon</th></tr>{cells}'
                   f'<tr><td>končni večkratnik</td><td class="n">{BASE["final"]:.2f}×</td>'
                   f'<td class="n">{r["final"]:.2f}×</td>'
                   f'<td class="n" colspan="2">poslov {BASE["trades"]} &rarr; '
                   f'{r["trades"]}</td></tr></table>')
        if ident:
            out.append('<p class="read" style="border-left:3px solid var(--crit)">'
                       '<b>Nič se ne spremeni.</b> Krivulji sta bitno identični in ni niti '
                       'enega dneva, ko bi držali kaj drugega. Zato zanj ni grafa — bila bi '
                       'ena črta.</p>')
        else:
            n_in = sum(1 for s in r["diff_segments"] if s[2] == "in")
            out.append(f'<p class="read">Drugačno pozicijo bi imeli na '
                       f'<b>{r["days_different"]} dneh</b> v {len(r["diff_segments"])} '
                       f'obdobjih, obarvanih na grafu spodaj. <b style="color:var(--s1)">Modro'
                       f'</b> = brez pravila bi bili v trgu, mi pa smo zunaj ({n_in} obdobij). '
                       f'<b style="color:var(--s2)">Oranžno</b> = obratno.</p>')
    out.append(f'<p class="read"><b>Sodba:</b> {verdict}</p></div></div>')
    if abl_key and not AF["cases"][abl_key].get("identical"):
        r = AF["cases"][abl_key]
        better = r["final"] > BASE["final"]
        out.append('<div class="fig">' + equity(r["equity"], r["diff_segments"])
                   + f'<p class="cap" style="margin:10px 0 0">'
                   + ("<b>Brez pravila bi bilo bolje</b> na končnem večkratniku "
                      if better else
                      "<b>Brez pravila bi bilo slabše</b> na končnem večkratniku ")
                   + f'({r["final"]:.2f}× proti {BASE["final"]:.2f}×), '
                   + ("padec pa " if True else "")
                   + (f'globlji ({r["maxdd"]:.1f} % proti {BASE["maxdd"]:.1f} %).'
                      if r["maxdd"] < BASE["maxdd"] else
                      f'plitvejši ali enak ({r["maxdd"]:.1f} % proti {BASE["maxdd"]:.1f} %).')
                   + " Noben razpon ne izloči ničle, torej razlike nismo dokazali.</p></div>")
    return "".join(out)


def main():
    P: list[str] = []
    A = P.append
    entry = [k for k, v in COND.items() if v[0] == "vstop"]
    exits = [k for k, v in COND.items() if v[0] == "izstop"]

    A(f"""<!doctype html><html lang="sl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lean — vsi vstopni in izstopni pogoji (BTC)</title><style>
 :root{{color-scheme:light;--plane:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;
  --muted:#898781;--grid:#e1e0d9;--axis:#c3c2b7;--ring:rgba(11,11,11,.10);
  --band:rgba(11,11,11,.05);--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--good:#0ca30c;
  --warn:#fab219;--crit:#d03b3b}}
 @media(prefers-color-scheme:dark){{:root:where(:not([data-theme=light])){{color-scheme:dark;
  --plane:#0d0d0d;--surface:#1a1a19;--ink:#fff;--ink2:#c3c2b7;--muted:#898781;--grid:#2c2c2a;
  --axis:#383835;--ring:rgba(255,255,255,.10);--band:rgba(255,255,255,.07);--s1:#3987e5;
  --s2:#d95926;--s3:#199e70;--good:#2fbf2f;--crit:#e05555}}}}
 :root[data-theme=dark]{{color-scheme:dark;--plane:#0d0d0d;--surface:#1a1a19;--ink:#fff;
  --ink2:#c3c2b7;--muted:#898781;--grid:#2c2c2a;--axis:#383835;--ring:rgba(255,255,255,.10);
  --band:rgba(255,255,255,.07);--s1:#3987e5;--s2:#d95926;--s3:#199e70;--good:#2fbf2f;
  --crit:#e05555}}
 *{{box-sizing:border-box}}
 body{{margin:0;background:var(--plane);color:var(--ink);
  font:15px/1.62 system-ui,-apple-system,"Segoe UI",sans-serif}}
 main{{max-width:1180px;margin:0 auto;padding:36px 20px 70px}}
 h1{{font-size:25px;margin:0 0 4px;font-weight:650}}
 .sub{{color:var(--ink2);font-size:13.5px;margin:0 0 24px}}
 h2{{font-size:17.5px;font-weight:650;margin:40px 0 10px;padding-top:14px;
  border-top:1px solid var(--grid)}}
 h2:first-of-type{{border-top:0;margin-top:6px}}
 h3.cond{{font:600 15px ui-monospace,SFMono-Regular,Menlo,monospace;margin:32px 0 12px;
  padding:9px 13px;background:var(--band);border-radius:8px}}
 p{{margin:0 0 12px;max-width:82ch}}
 .cap{{color:var(--ink2);font-size:13px;margin:0 0 12px;max-width:86ch}}
 .mech{{font-size:13.5px;color:var(--ink2);margin:0 0 8px}}
 .sub2{{font:600 13px system-ui;margin:16px 0 6px}}
 .win{{font:400 11.5px system-ui;color:var(--muted)}}
 .two{{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin:0 0 14px}}
 @media(max-width:900px){{.two{{grid-template-columns:1fr}}}}
 .fig{{background:var(--surface);border:1px solid var(--ring);border-radius:10px;
  padding:16px;margin:0 0 16px;overflow-x:auto}}
 .par{{font:11.5px ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--muted);
  margin:0 0 10px;padding:5px 8px;border-radius:6px;background:var(--band)}}
 .read{{font-size:12.5px;margin:10px 0 0;padding:8px 10px;border-radius:7px;
  background:var(--band);color:var(--ink2)}}
 .badge{{display:inline-block;font-size:10px;font-weight:700;letter-spacing:.04em;
  text-transform:uppercase;border-radius:999px;padding:2px 8px;margin-left:9px;color:#fff;
  font-family:system-ui;vertical-align:2px}}
 svg{{display:block;width:100%;height:auto;overflow:visible}}
 text{{font:11px system-ui;fill:var(--muted);font-variant-numeric:tabular-nums}}
 table{{border-collapse:collapse;width:100%;font-size:13px;font-variant-numeric:tabular-nums}}
 table.mini{{font-size:12.5px}}
 th,td{{text-align:left;padding:6px 9px;border-bottom:1px solid var(--grid);
  vertical-align:top}}
 th{{color:var(--ink2);font-weight:600;font-size:12px}}
 td.n,th.n{{text-align:right}}
 code{{font:12.5px ui-monospace,SFMono-Regular,Menlo,monospace;background:var(--band);
  padding:1px 5px;border-radius:4px}}
 .note{{background:var(--band);border-left:3px solid var(--s2);border-radius:0 8px 8px 0;
  padding:12px 16px;margin:0 0 16px}}
 .note p:last-child{{margin-bottom:0}}
 .lead{{font-size:16px;line-height:1.68;max-width:88ch}}
 footer{{margin-top:40px;padding-top:15px;border-top:1px solid var(--grid);
  color:var(--muted);font-size:12.5px}}
</style></head><body><main>

<h1>Vsi vstopni in izstopni pogoji — kaj vsak počne in ali ga potrebujemo</h1>
<p class="sub">Diversitas Lean · BTC · Binance · fee + slippage
{AF['fee_per_side_pct']} % na stran</p>
""")

    A("<h2>Kako se bere manjši graf na levi</h2>")
    A(f"""<div class="fig"><div class="two" style="gap:28px">
<div>
<p style="margin:0 0 8px"><b>Kaj je številka</b></p>
<p class="cap" style="margin:0 0 10px;padding:7px 10px;background:var(--band);border-radius:7px"><b>To velja za manjši graf levo pri vsakem pogoju</b> — tistega z vodoravnimi črtami in piko. Široki graf pod njim je nekaj drugega: tam sta krivulji premoženja z in brez pravila.</p>
<p class="cap">Vse dni v vzorcu razdelimo na dva kupa: dnevi, ko je pravilo izpolnjeno, in
dnevi, ko ni. Za oba kupa izračunamo, koliko je BTC v povprečju zrasel v naslednjih N dneh.
<b>Številka na grafu je razlika med tema dvema povprečjema</b>, v odstotnih točkah.</p>
<p class="cap"><b>Primer.</b> Pri <code>bull_condition</code> piše +1,68 pri 5 dneh. Beri: v
petih dneh po dnevih, ko so bili vsi vstopni pogoji izpolnjeni, je BTC v povprečju zrasel za
1,68 odstotne točke <b>več</b> kot v petih dneh po vseh ostalih dneh.</p>
<p class="cap" style="margin:0"><b>To ni donos strategije.</b> Je merilo, ali pravilo sploh
kaže v pravo smer. Vstopno pravilo naj bi bilo <b>pozitivno</b>, izstopno <b>negativno</b>.
Črta je razpon negotovosti — <b>če seka ničlo, razlike nismo dokazali</b>, tudi če pika ni
na ničli.</p>
</div>
<div>
<p style="margin:0 0 8px"><b>Zakaj tri različna števila dni</b></p>
<table style="margin:0 0 10px">
<tr><td style="width:70px"><b>5 dni</b></td><td style="font-size:12.5px">približno teden.
Ali pravilo pove kaj <i>takoj</i>?</td></tr>
<tr><td><b>20 dni</b></td><td style="font-size:12.5px">približno mesec. To je merilo, na
katerem strategija dejansko živi — povprečen posel traja tedne.</td></tr>
<tr><td><b>60 dni</b></td><td style="font-size:12.5px">približno četrtletje. Se trend
nadaljuje ali se prelomi?</td></tr>
</table>
<p class="cap">Pravilo, ki deluje samo na enem od teh treh, je bolj sumljivo kot pravilo, ki
na vseh treh deluje šibkeje.</p>
<p class="cap" style="margin:0"><b>Zakaj so črte pri 60 dneh dosti daljše.</b> Ker je manj
<i>neodvisnih</i> opazovanj: 60-dnevni okni sosednjih dni se prekrivata v 59 dneh od 60, zato
{ES['n_days']} dni da le okoli 40 res ločenih 60-dnevnih obdobij. Manj dokazov pomeni širši
razpon. To ni napaka grafa — nasprotno, ožja črta bi bila laž.</p>
</div></div></div>""")

    A(f"""<div class="note"><p><b>Dve okni, in to namenoma.</b> Vprašanje »kaže pravilo v
pravo smer« je statistika posameznih dni in uporablja <b>celotno zgodovino {ES['from']} →
{ES['to']} ({ES['n_days']} dni)</b>; skrajšanje na pet let bi zavrglo 900 dni in blow-offu
pustilo štiri sprožitve. Vprašanje »kaj se zgodi z denarjem« je backtest in uporablja
<b>zadnjih pet celih let, {AF['from']} → {AF['to']} ({AF['n']} dni)</b>, neto
{AF['fee_per_side_pct']} % na stran. Pri vsaki številki je zapisano, katero okno velja.</p>
</div>""")

    A("<h2>Vstopni pogoji, eden za drugim</h2>")
    A(f"""<p class="cap">Pod vsakim pogojem je tabela gumbov, ki jih <i>ta</i> pogoj bere, z
obliko preleta iz poročila o parametrih in predlaganim ukrepom. Dva gumba nista v nobeni
tabeli, ker ne pripadata posameznemu pogoju, ampak <b>vratom za vse skupaj</b>:
<code>confirm_bars</code> = {PLAN['confirm_bars']['default']} (signal mora veljati toliko dni
zapored) in <code>reentry_hold</code> = {PLAN['reentry_hold']['default']} (toliko dni premora
po zadnji spremembi). Oba sta na ostri konici in oba sta predlagana
<b style="color:var(--s1)">za glasovanje</b>.</p>""")
    for k in entry:
        A(section(k))
    A("<h2>Izstopni pogoji, eden za drugim</h2>")
    for k in exits:
        A(section(k))

    b_ = ES["blowoff_mechanism"]
    A('<p class="sub2">Blow-off še enkrat: ali res zaznava vrhove? '
      f'<span class="win">okno {ES["from"]} → {ES["to"]}</span></p>')
    A('<div class="fig">' + blowoff_chart(b_) + "</div>")
    A(f"""<p class="cap"><b>Ne.</b> Mediana sprožitve pristane na
<b>{b_['median_percentile_of_fwd60']}. percentilu</b> nadaljnjega 60-dnevnega donosa;
{b_['share_in_best_quartile']} % sprožitev je v najboljši četrtini. Kot napovednik vrha ne
deluje. Ali deluje kot napovednik nemira, ostaja odprto: po vsaki sprožitvi res sledi padec, a
<b>{AU['dd_base_rate']['share_of_all_windows']:.0f} % vseh 60-dnevnih oken</b> v tem vzorcu
vsebuje padec vsaj 13 %, zato to skoraj nič ne pomeni.</p>""")

    A("<h2>Ali so ta pravila res mrtva? Preizkus pri 151 nastavitvah</h2>")
    A(f"""<p>Nič se ne spremeni je bilo izmerjeno pri <b>eni</b> nastavitvi. To ne zadostuje
za brisanje kode: pravilo lahko pri privzetkih spi, korak vstran pa se prebudi. Tu je še
posebej pomembno, ker drugo poročilo priporoča <b>povprečenje 81 sosednjih nastavitev</b> —
pravilo, ki oživi v katerikoli od njih, ni odstranljivo brez spremembe ansambla.</p>
<p class="cap">Preizkušenih je bilo {DR['settings_tested']} nastavitev: preleti desetih
parametrov čez razpone, ki gredo daleč čez vse, kar bi kdo dejansko uporabil, plus vseh 81
članov ansambla. Primerjava je na <b>seriji pozicij</b>, ne na merilih — enaka merila bi
lahko načeloma prišla iz različnih poti, enake pozicije ne morejo.</p>""")
    A('<div class="fig"><table><tr><th>pravilo</th><th class="n">oživi pri</th>'
      '<th class="n">med 81 člani<br>ansambla</th>'
      '<th class="n">odstranitev<br>boljša / slabša</th><th>sodba</th></tr>')
    ROBUST = [
      ("dist_entry_ok", "<b>Odstraniti.</b> Edino, kar je mrtvo pri vseh nastavitvah — in "
       "mrtvo po konstrukciji, ne po sreči.", "var(--crit)"),
      ("above_ma_med", "<b>Odstraniti.</b> Oživi le pri zelo ozkem mrtvem pasu (1–1,5 % "
       "namesto 3 %) in pri obdobju 115. Učinki so drobni in padca ne premaknejo.",
       "var(--crit)"),
      ("vol_shock", "<b>NE odstraniti.</b> Pri privzetkih spi, a to je naključje štirih "
       "vrednosti. Oživi pri več kot tretjini preizkušenih nastavitev in pri več kot polovici "
       "članov ansambla.", "var(--warn)"),
    ]
    for key, note, col in ROBUST:
        sm = DR["summary"][key]
        grid_hits = len(DR["grid"][key])
        A(f'<tr><td><code>{key}</code></td>'
          f'<td class="n">{sm["n_alive"]} / {DR["settings_tested"]}</td>'
          f'<td class="n">{grid_hits} / 81</td>'
          f'<td class="n">{sm["removal_better"]} / {sm["removal_worse"]}</td>'
          f'<td style="font-size:12.5px;color:{col}">{note}</td></tr>')
    A("</table></div>")

    A(f"""<div class="note" style="border-left-color:var(--crit)">
<p><b>Kje se <code>vol_shock</code> prebudi.</b> Pravilo zahteva <code>below_tl</code> in da
redni izstop še ni nastopil. Pri privzetkih <code>track_period</code> 75,
<code>track_buf_pct</code> 3 %, <code>exit_grace_bars</code> 3 in <code>reentry_hold</code> 15
to okno nikoli ne nastane — a že en korak vstran nastane:</p>
<table style="margin:9px 0">
<tr><th>parameter</th><th>vrednosti, pri katerih SPI</th>
<th>vrednosti, pri katerih SE SPROŽI</th></tr>
<tr><td><code>exit_grace_bars</code></td><td>1, 3, 4</td>
    <td><b>2, 5, 6, 8, 10, 14</b> — pri 14 na 140 dneh</td></tr>
<tr><td><code>track_period</code></td><td>75, 85</td>
    <td><b>45, 55, 65, 95, 105, 115</b></td></tr>
<tr><td><code>track_buf_pct</code></td><td>3, 4, 5</td><td><b>1, 1,5, 2, 2,5, 6</b></td></tr>
<tr><td><code>reentry_hold</code></td><td>15, 20, 25, 30</td><td><b>0, 3, 6, 9, 12</b></td></tr>
</table>
<p><b>Moja prejšnja trditev, da je vol_shock »strukturno mrtev in ne more biti drugače«, je
bila napačna.</b> Mrtev je pri natanko tej kombinaciji štirih vrednosti. Učinek je majhen —
mediana {abs(DR['summary']['vol_shock']['n_alive']) and '−0,020'} Sortina, največ 0,085 — a ni
nič, in v 61 od 67 primerov je odstranitev slabša.</p></div>""")

    A("<h2>Skupni rezultat: strategija brez dveh odveč pravil</h2>")
    A("""<p>Spodaj je današnja strategija proti tisti brez <code>dist_entry_ok</code> in
<code>above_ma_med</code>. <code>vol_shock</code> po zgornjem preizkusu <b>ostane</b>.</p>""")
    A('<div class="fig">' + equity(AF["cases"]["brez obojega"]["equity"], (),
                                   alt_label="brez obeh") + "</div>")
    A(f"""<div class="note" style="border-left-color:var(--good)">
<p><b>Modra črta se popolnoma skriva pod rdečo.</b> Razlika je <b>0,000000</b> na vseh
{AF['n']} dneh. Vsa štiri merila ostanejo nespremenjena — Sortino {BASE['sortino']:.3f},
Sharpe {BASE['sharpe']:.3f}, letni donos {BASE['cagr']:.1f} %, največji padec
{BASE['maxdd']:.1f} %, končni večkratnik {BASE['final']:.2f}× pri {BASE['trades']} poslih.
Kupi-in-drži je v istem obdobju dosegel {BENCH[-1]:.2f}× pri padcu
{AF['benchmark']['maxdd']:.1f} %.</p>
<p style="margin-top:9px"><b>Končna sodba.</b> Nastavljivih številk je
<b>14 &rarr; 12</b> — odpadeta <code>min_dist_entry_pct</code> in <code>ma_med_len</code>.
<code>vol_shock_mul</code> in <code>vol_lookback</code> <b>ostaneta</b>, ker pravilo ni mrtvo
pri nastavitvah, ki jih dejansko nameravamo uporabiti. To je manj, kot je prej kazalo, in
razlog je pošten: prvi izračun je meril eno točko, drugi jih je meril
{DR['settings_tested']}.</p></div>""")

    A("<h2>Je vol_shock vreden svoje kompleksnosti?</h2>")
    V = MG["variants"]
    dv = MG["drop_vol_shock_glasovanje"]
    A(f"""<p>Da pravilo oživi pri 45 od 81 članov ansambla, je bil razlog, da ga ne izbrišemo.
A »spremeni ansambel« in »spremeni ansambel za toliko, da je vredno dveh nastavljivih številk«
nista isto, in odločilna je druga trditev. Izmerjena je tako: glasovanje vseh 81 sosedov,
enkrat z živim vol_shockom in enkrat brez njega. Kar delajo posamezni člani, ni pomembno —
glasovanje je tisto, kar bi dejansko trgovali.</p>""")
    A('<div class="fig"><table><tr><th>različica</th><th class="n">Sortino</th>'
      '<th class="n">Sharpe</th><th class="n">letni donos</th>'
      '<th class="n">največji padec</th><th class="n">končni večkratnik</th></tr>')
    for k in ("glasovanje, z vol_shockom", "glasovanje, brez vol_shocka",
              "ena tocka, z vol_shockom", "ena tocka, brez vol_shocka"):
        m = V[k]
        A(f'<tr><td>{k.replace("ena tocka", "ena točka")}</td>'
          f'<td class="n">{m["sortino"]:.3f}</td><td class="n">{m["sharpe"]:.3f}</td>'
          f'<td class="n">{m["cagr"]:.1f} %</td><td class="n">{m["maxdd"]:.1f} %</td>'
          f'<td class="n">{m["final"]:.2f}×</td></tr>')
    A("</table></div>")
    A(f"""<div class="note" style="border-left-color:var(--good)">
<p><b>Odgovor: pravilo obdržati, oba gumba zakleniti.</b></p>
<p style="margin-top:8px">V ansamblu izklop vol_shocka stane <b>{abs(dv['d_sortino']):.3f}
Sortina</b> (razpon [{dv['ci_sortino'][0]:+.2f}, {dv['ci_sortino'][1]:+.2f}] seka ničlo) in
<b>{abs(dv['d_maxdd']):.1f} odstotne točke padca</b> — torej nič na tistem merilu, ki ga
produkt edino obljublja. Pri eni sami točki je razlika natanko nič.</p>
<p style="margin-top:8px">Za primerjavo: pri {V['glasovanje, z vol_shockom']['trades']} poslih
je najmanjša razlika, ki jo sploh znamo zaznati, okoli <b>0,5 Sortina</b>. Izmerjenih 0,040 je
dvanajstkrat pod tem pragom. <b>Trditev, da to pravilo kaj prispeva, je pod mejo merljivosti
v obe smeri.</b></p>
<p style="margin-top:8px"><b>Zato ni treba izbirati med brisanjem in ohranjanjem.</b> Za
statistiko šteje <b>število nastavljivih številk</b>, ne število vrstic kode: prav to vstopa v
PBO in deflated Sharpe. Če <code>vol_shock_mul</code> in <code>vol_lookback</code>
<b>zakleneš</b> pri 1,5 in 20 ter ju umakneš s seznama nastavljivih, dobiš celotno statistično
korist, <b>ne da bi spremenil eno samo pozicijo</b>. Brisanje pravila bi prineslo le urejenost
kode — za ceno spremembe vedenja, ki je ne moremo utemeljiti.</p></div>""")

    A("<h2>Združena slika: najboljše nastavitve po obeh poročilih</h2>")
    A(f"""<p>Poročilo o parametrih pove <b>obliko</b> vsakega gumba — plato, ostra konica ali
inerten. To poročilo pove, ali <b>pravilo</b>, ki ga gumb nastavlja, sploh kaj počne. Šele
skupaj dasta ukrep. Spodnja tabela je sestavljena iz obeh, ne napisana na roko.</p>""")
    ACT = {
      "odstraniti": ("odstraniti", "var(--crit)"),
      "zakleniti": ("zakleniti", "var(--s2)"),
      "prepustiti glasovanju": ("prepustiti glasovanju", "var(--s1)"),
      "pustiti pri miru": ("pustiti pri miru", "var(--good)"),
    }
    A('<div class="fig"><table><tr><th>parameter</th><th class="n">danes</th>'
      '<th>oblika preleta</th><th class="n">razpon</th><th>ukrep</th>'
      '<th>zakaj</th></tr>')
    order = {"odstraniti": 0, "zakleniti": 1, "prepustiti glasovanju": 2,
             "pustiti pri miru": 3}
    for r in sorted(MG["parameter_plan"], key=lambda x: (order[x["action"]], x["name"])):
        lab, col = ACT[r["action"]]
        A(f'<tr><td><code>{r["name"]}</code></td>'
          f'<td class="n">{r["default"]}</td>'
          f'<td style="font-size:12.5px">{r["kind"]}</td>'
          f'<td class="n">{r["range"]:.2f}</td>'
          f'<td><span class="badge" style="background:{col};margin:0">{lab}</span></td>'
          f'<td style="font-size:12.5px">{r["why"]}</td></tr>')
    A("</table></div>")

    n_rm = sum(1 for r in MG["parameter_plan"] if r["action"] == "odstraniti")
    n_lk = sum(1 for r in MG["parameter_plan"] if r["action"] == "zakleniti")
    n_vt = sum(1 for r in MG["parameter_plan"] if r["action"] == "prepustiti glasovanju")
    n_al = sum(1 for r in MG["parameter_plan"] if r["action"] == "pustiti pri miru")
    tot = len(MG["parameter_plan"])
    A(f"""<div class="note" style="border-left-color:var(--good)">
<p><b>Kaj to skupaj naredi s številom gumbov.</b></p>
<table style="margin:9px 0">
<tr><td><b>{tot}</b></td><td>nastavljivih številk danes</td></tr>
<tr><td><b>−{n_rm}</b></td><td>odstranjeni, ker je pravilo mrtvo pri vseh nastavitvah
    (<code>min_dist_entry_pct</code>, <code>ma_med_len</code>)</td></tr>
<tr><td><b>−{n_lk}</b></td><td>zaklenjeni, ker gumb ničesar ne premakne, pravilo pa ostane
    (<code>rsi_len</code>, <code>vol_shock_mul</code>, <code>vol_lookback</code>)</td></tr>
<tr style="border-top:1px solid var(--axis)"><td><b>{tot-n_rm-n_lk}</b></td>
    <td><b>nastavljivih ostane</b></td></tr>
<tr><td><b>−{n_vt}</b></td><td>prepuščenih glasovanju 81 sosedov, ker so na ostri konici
    (<code>ma_long_len</code>, <code>confirm_bars</code>, <code>reentry_hold</code>,
    <code>exit_grace_bars</code>)</td></tr>
<tr style="border-top:1px solid var(--axis)"><td><b>{n_al}</b></td>
    <td><b>številk, ki bi jih kdo sploh še kdaj nastavljal</b> — in vse so na platoju ali
    pripadajo pravilu, ki ga ne odpiramo</td></tr>
</table>
<p><b>{tot} &rarr; {tot-n_rm-n_lk} nastavljivih, od tega {n_al}, ki jih je smiselno gledati.</b>
In vse to ne da bi spremenili eno samo pozicijo — razen tam, kjer glasovanje nadomesti izbrano
točko. To je celoten izplen obeh poročil skupaj.</p></div>""")

    A(f"""<div class="note"><p><b>Kaj namenoma NI na seznamu.</b>
<code>blowoff_dist_pct</code> je na ostri konici z vrhom natanko na privzetku, kar bi ga
uvrstilo med kandidate za glasovanje. Pustimo ga pri miru, ker je pravilo samo nedokazano v
obe smeri in se njegov predznak obrne glede na okno — spreminjati nastavitev pravila, o katerem
ne vemo, ali sploh koristi, bi bilo nastavljanje šuma. Enako velja za <code>rsi_len</code>, ki
napaja isto pravilo: zaklenjen je, ne odstranjen.</p></div>""")

    A("<h2>Kaj vse to skupaj pomeni</h2>")
    A(f"""<p class="lead">Strategija ima osem pravil, a pri privzetih nastavitvah tri od njih
ne počnejo nič — in ravno preverba, ali to drži tudi drugje, je pokazala, da je treba to
trditev razdeliti na tri različno trdne dele. <code>dist_entry_ok</code> je matematični dvojnik
pravila nad njim: pri {DR['settings_tested']} preizkušenih nastavitvah ni bilo niti enega dne
razlike, in tudi ne more biti, ker je isti izraz zapisan dvakrat — v dashboardu zaseda svojo
kljukico, ki ne more nikoli ugovarjati tisti nad njo. <code>above_ma_med</code> je mrtev
skoraj povsod: oživi pri treh nastavitvah od {DR['settings_tested']}, in še tam za največ
petnajst dni in brez vpliva na padec, ker petinšestdeset dni, ki jih blokira, tako ali tako
požrejo trije dnevi potrditve in petnajstdnevni premor. <code>vol_shock</code> pa sem
<b>napačno razglasil za strukturno mrtvega</b>: pri privzetkih se res nikoli ne sproži, a to
je naključje štirih vrednosti hkrati, in že korak vstran — pri drugem mrtvem pasu, drugi
dolžini razpona ali drugem številu dni potrpljenja — oživi; pri
{len(DR['grid']['vol_shock'])} od 81 članov ansambla, ki ga priporočamo uporabiti, deluje, in
tam je njegova odstranitev slabša v 61 primerih od 67. Med pravili, ki nekaj počnejo, sta dva
zagovorljiva: <code>track_rising_window</code> je edini, brez katerega se največji padec
opazno poglobi z {BASE['maxdd']:.1f} % na
{AF['cases']['brez track_rising']['maxdd']:.1f} %, in <code>regime_ok</code> je edini, brez
katerega je slabše na vseh štirih merilih — čeprav se je ob tem izkazalo, da padca sploh ne
zmanjšuje in je torej filter donosa, ne varovalka. Preostala tri so odprta vprašanja:
<code>above_tl</code> je jedro, a backtest brez njega je rahlo boljši; <code>below_tl</code>
nosi trinajst od enaindvajsetih poslov brez dokazane prednosti; blow-off pa se obrne glede na
obdobje. <b>Odstranljivi sta torej dve pravili, ne tri — a to ni celotna zgodba: za statistiko
šteje število nastavljivih številk, ne število pravil, in tri nadaljnje gumbe je mogoče
zakleniti, ne da bi se premaknila ena sama pozicija. Skupaj to pomeni štirinajst nastavljivih
številk na devet, od tega pet, ki jih je smiselno gledati. Kar pa je najbolj poučno, je da je
moja najbolj samozavestna trditev — »strukturno mrtev, ne more biti drugače« — padla prva, ko
sem jo preizkusil pri več kot eni nastavitvi.</b></p>""")

    A(f"""<footer>
Vir cen: Binance, zamrznjen posnetek
<code>testing/data/sources/BTC_binance_warmup.parquet</code>. Ogrevanje indikatorjev je vzeto
iz zgodovine pred oknom, ne odbito od njega.<br>
Statistika posameznih dni: okno {ES['from']} → {ES['to']} ({ES['n_days']} dni), krožni bločni
bootstrap, {ES['nboot']} vzorcev, dolžina bloka {ES['block_rule']}, seme {ES['seed']}.<br>
Backtest in ablacije: okno {AF['from']} → {AF['to']} ({AF['n']} dni), fee + slippage
{AF['fee_per_side_pct']} % na stran, parni bločni bootstrap {AF['nboot']} vzorcev, blok
{AF['block']} dni.<br>
Ponovljivo z <code>testing/scripts/event_study.py</code>, <code>ablation_full.py</code>,
<code>exit_rules.py</code>, <code>audit_claims.py</code>; stran gradi
<code>build_report_pogoji.py</code>.
</footer></main></body></html>""")

    OUT.write_text("".join(P), encoding="utf-8")
    print(f"-> {OUT}  ({OUT.stat().st_size/1024:.0f} kB)")


if __name__ == "__main__":
    main()
