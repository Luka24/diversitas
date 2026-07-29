"""Build testing/porocilo_pogoji_BTC.html from the two result files.

Charts are emitted as inline SVG rather than drawn by a chart library, so the
report is a single file that opens anywhere and cannot silently render stale
numbers from a cached script.
"""
from __future__ import annotations

import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ES = json.loads((ROOT / "testing" / "data" / "event_study_BTC.json").read_text(encoding="utf-8"))
AB = json.loads((ROOT / "testing" / "data" / "ablation_BTC.json").read_text(encoding="utf-8"))
OUT = ROOT / "testing" / "porocilo_pogoji_BTC.html"

DEFAULTS = {"ma_med_len": 50, "rsi_len": 14, "vol_shock_mul": 1.5,
            "vol_lookback": 20, "min_dist_entry_pct": 0.0, "blowoff_dist_pct": 25.0}


# ── chart helpers ───────────────────────────────────────────────────────────
def ci_chart(rows, w=430, unit="o. t.") -> str:
    """rows: (label, diff, [lo,hi], [nlo,nhi], sig). Horizontal interval plot."""
    rows = [r for r in rows if r[1] is not None]
    if not rows:
        return '<p class="cap">Premalo opazovanj za primerjavo.</p>'
    pad_l, pad_r, row_h, top = 46, 12, 38, 16
    h = top + row_h * len(rows) + 26
    lim = max(max(abs(v) for v in (r[2][0], r[2][1], r[1])) for r in rows) * 1.12 or 1
    def x(v): return pad_l + (v + lim) / (2 * lim) * (w - pad_l - pad_r)
    p = [f'<svg viewBox="0 0 {w} {h}" role="img">']
    zx = x(0)
    p.append(f'<rect x="{pad_l}" y="{top-8}" width="{w-pad_l-pad_r}" height="{row_h*len(rows)+4}" '
             f'fill="var(--band)" rx="5"/>')
    p.append(f'<line x1="{zx:.1f}" y1="{top-8}" x2="{zx:.1f}" y2="{top+row_h*len(rows)-4}" '
             f'stroke="var(--axis)" stroke-width="1.5"/>')
    for i, (lab, d, ci, nci, sig) in enumerate(rows):
        y = top + row_h * i + 8
        col = "var(--s1)" if sig and d > 0 else ("var(--crit)" if sig and d < 0 else "var(--muted)")
        p.append(f'<line x1="{x(ci[0]):.1f}" y1="{y}" x2="{x(ci[1]):.1f}" y2="{y}" '
                 f'stroke="{col}" stroke-width="3.5" stroke-linecap="round" opacity=".45"/>')
        p.append(f'<line x1="{x(nci[0]):.1f}" y1="{y}" x2="{x(nci[1]):.1f}" y2="{y}" '
                 f'stroke="{col}" stroke-width="1.2" stroke-dasharray="2 2"/>')
        p.append(f'<circle cx="{x(d):.1f}" cy="{y}" r="4" fill="{col}"/>')
        p.append(f'<text x="{pad_l-8}" y="{y+4}" text-anchor="end">{lab}</text>')
        p.append(f'<text x="{x(ci[1]):.1f}" y="{y-9}" text-anchor="middle" '
                 f'style="fill:{col};font-weight:600">{d:+.2f}</text>')
    p.append(f'<text x="{zx:.1f}" y="{h-6}" text-anchor="middle">0 — brez razlike</text>')
    p.append(f'<text x="{pad_l}" y="{h-6}" text-anchor="start">slabše</text>')
    p.append(f'<text x="{w-pad_r}" y="{h-6}" text-anchor="end">bolje ({unit})</text>')
    return "".join(p) + "</svg>"


def sweep_chart(points, default, w=430, h=150) -> str:
    xs = [p["value"] for p in points]
    ys = [p["sortino"] for p in points]
    pad_l, pad_r, pad_t, pad_b = 40, 12, 14, 26
    lo, hi = min(ys), max(ys)
    span = max(hi - lo, 0.05)
    lo, hi = lo - span * 0.25, hi + span * 0.25
    def X(i): return pad_l + i / max(len(xs) - 1, 1) * (w - pad_l - pad_r)
    def Y(v): return pad_t + (1 - (v - lo) / (hi - lo)) * (h - pad_t - pad_b)
    p = [f'<svg viewBox="0 0 {w} {h}" role="img">']
    for gv in (lo + (hi - lo) * f for f in (0.0, 0.5, 1.0)):
        p.append(f'<line x1="{pad_l}" y1="{Y(gv):.1f}" x2="{w-pad_r}" y2="{Y(gv):.1f}" '
                 f'stroke="var(--grid)"/>')
        p.append(f'<text x="{pad_l-6}" y="{Y(gv)+4:.1f}" text-anchor="end">{gv:.2f}</text>')
    d = " ".join(f'{"M" if i==0 else "L"}{X(i):.1f},{Y(v):.1f}' for i, v in enumerate(ys))
    p.append(f'<path d="{d}" fill="none" stroke="var(--s1)" stroke-width="2"/>')
    for i, (xv, yv) in enumerate(zip(xs, ys)):
        isd = abs(float(xv) - float(default)) < 1e-9
        p.append(f'<circle cx="{X(i):.1f}" cy="{Y(yv):.1f}" r="{4.5 if isd else 3}" '
                 f'fill="{"var(--s2)" if isd else "var(--s1)"}"/>')
        p.append(f'<text x="{X(i):.1f}" y="{h-8}" text-anchor="middle"'
                 f'{" style=\"fill:var(--s2);font-weight:700\"" if isd else ""}>'
                 f'{xv:g}</text>')
    return "".join(p) + "</svg>"


def blowoff_chart(bm, w=860, h=170) -> str:
    pcts = bm["percentiles"]
    pad_l, pad_r, pad_t = 30, 30, 34
    def X(v): return pad_l + v / 100 * (w - pad_l - pad_r)
    p = [f'<svg viewBox="0 0 {w} {h}" role="img">']
    p.append(f'<rect x="{X(0):.0f}" y="{pad_t}" width="{X(25)-X(0):.0f}" height="46" '
             f'fill="var(--crit)" opacity=".13" rx="4"/>')
    p.append(f'<rect x="{X(75):.0f}" y="{pad_t}" width="{X(100)-X(75):.0f}" height="46" '
             f'fill="var(--good)" opacity=".13" rx="4"/>')
    p.append(f'<line x1="{pad_l}" y1="{pad_t+46}" x2="{w-pad_r}" y2="{pad_t+46}" '
             f'stroke="var(--axis)"/>')
    for v in (0, 25, 50, 75, 100):
        p.append(f'<line x1="{X(v):.1f}" y1="{pad_t+46}" x2="{X(v):.1f}" y2="{pad_t+52}" '
                 f'stroke="var(--axis)"/>')
        p.append(f'<text x="{X(v):.1f}" y="{pad_t+66}" text-anchor="middle">{v}.</text>')
    seen: dict[int, int] = {}
    for v in pcts:
        k = int(round(v))
        lvl = seen.get(k, 0); seen[k] = lvl + 1
        p.append(f'<circle cx="{X(v):.1f}" cy="{pad_t+38-lvl*9:.1f}" r="4.5" '
                 f'fill="var(--s2)" stroke="var(--surface)" stroke-width="1"/>')
    p.append(f'<text x="{X(12):.0f}" y="{pad_t-12}" text-anchor="middle" '
             f'style="fill:var(--crit);font-weight:600">tu bi moral biti vrh</text>')
    p.append(f'<text x="{X(87):.0f}" y="{pad_t-12}" text-anchor="middle" '
             f'style="fill:var(--good);font-weight:600">tu je dejansko</text>')
    p.append(f'<text x="{pad_l}" y="{h-8}" text-anchor="start">'
             f'percentil 60-dnevnega donosa po sprožitvi — 0. = najslabši dan v vzorcu, '
             f'100. = najboljši</text>')
    return "".join(p) + "</svg>"


def incremental_chart(inc, w=430, h=190) -> str:
    rows = [r for r in inc if r.get("m")]
    if not rows:
        return ""
    pad_l, pad_t, pad_b = 130, 14, 26
    bw = (h - pad_t - pad_b) / len(rows)
    vals = []
    for r in rows:
        v = r["m"]["20"]
        vals += [v["mean_true"], v["mean_false"]]
    lim = max(abs(v) for v in vals) * 1.15
    def X(v): return pad_l + (v + lim) / (2 * lim) * (w - pad_l - 14)
    p = [f'<svg viewBox="0 0 {w} {h}" role="img">']
    p.append(f'<line x1="{X(0):.1f}" y1="{pad_t}" x2="{X(0):.1f}" y2="{h-pad_b}" '
             f'stroke="var(--axis)"/>')
    for i, r in enumerate(rows):
        v = r["m"]["20"]; y = pad_t + bw * i + bw / 2
        col = "var(--crit)" if v["mean_true"] < v["mean_false"] else "var(--s1)"
        x0, x1 = X(0), X(v["mean_true"])
        p.append(f'<rect x="{min(x0,x1):.1f}" y="{y-7:.1f}" width="{abs(x1-x0):.1f}" '
                 f'height="14" fill="{col}" opacity=".65" rx="2"/>')
        p.append(f'<text x="{pad_l-8}" y="{y+4:.1f}" text-anchor="end">{r["key"]}</text>')
        p.append(f'<text x="{x1 + (6 if v["mean_true"]>=0 else -6):.1f}" y="{y+4:.1f}" '
                 f'text-anchor="{"start" if v["mean_true"]>=0 else "end"}" '
                 f'style="font-weight:600">{v["mean_true"]:+.1f} %</text>')
    p.append(f'<text x="{X(0):.1f}" y="{h-8}" text-anchor="middle">'
             f'povprečen 20-dnevni donos na dneh, ki jih filter blokira</text>')
    return "".join(p) + "</svg>"


# ── page ────────────────────────────────────────────────────────────────────
def badge(txt, col):
    return f'<span class="badge" style="background:{col}">{txt}</span>'


BADGE = {
    "ok":    ("dokazan", "var(--good)"),
    "weak":  ("šibek", "var(--warn)"),
    "none":  ("brez dokaza", "var(--muted)"),
    "bad":   ("dela narobe", "var(--crit)"),
    "dead":  ("nikoli ne sproži", "var(--serious)"),
}

READ = {
 "above_tl": ("Sam po sebi ne pove veliko. Točkovna ocena je povsod pozitivna, a nobeden "
              "interval ne izloči ničle. Ko trg že prefiltrira 200-dnevno povprečje, pri "
              "60 dneh celo obrne predznak.", "none"),
 "above_ma_med": ("Edini posamezni filter, ki je značilen sam zase — na kratkem horizontu. "
                  "Cena nad 50-dnevnim povprečjem res napove boljših naslednjih pet dni.", "ok"),
 "track_rising_window": ("Najmočnejši posamezni filter. Značilen pri 20 dneh in ostane "
                         "značilen tudi znotraj že prefiltriranega trga.", "ok"),
 "regime_ok": ("Na kratek rok ne naredi nič, na 60 dni pa največ od vseh: +13 o. t. "
               "Deluje kot varovalka pred dolgimi padci, ne kot izbirnik dobrih tednov.", "ok"),
 "bull_condition": ("Kombinacija je močnejša od vsakega dela posebej. To pomeni, da se "
                    "filtri ne podvajajo — vsak prispeva nekaj svojega.", "ok"),
 "below_tl": ("Predznak je pravi — po sprožitvi trg v povprečju pada — a razlika je "
              "premajhna glede na razpršenost. Kot izstopni signal ni ovržen, tudi ne potrjen.", "weak"),
 "blowoff": ("Sproži se 22-krat v šestih letih in pol. Za statistični test je to premalo, "
             "zato ga presojamo po mehanizmu — glej razdelek spodaj.", "bad"),
 "vol_shock": ("Primerjan pošteno, torej proti drugim dnevom pod trackline, se sproži "
               "natanko na tistih, ki jim sledi značilno BOLJŠIH naslednjih 60 dni.", "bad"),
}


def cond_card(r):
    rows = []
    for h in ES["horizons"]:
        v = r["m"]["donos"][str(h)]
        if v is None:
            continue
        rows.append((f"{h} dni", v["diff"], v["ci"], v["ci_naive"], v["sig"]))
    txt, bk = READ.get(r["key"], ("", "none"))
    lab, col = BADGE[bk]
    gate = ("" if r["gate"] == "all" else
            f' <span style="color:var(--s2)">primerjano znotraj dni <code>{r["gate"]}</code></span>')
    return (f'<div class="card"><h3>{escape(r["key"])}{badge(lab, col)}</h3>'
            f'<p class="d">{escape(r["label"])} · sproži se {r["n_fire"]}× '
            f'({r["share"]} % dni){gate}</p>'
            f'{ci_chart(rows) if rows else "<p class=cap>Premalo opazovanj — test ni mogoč.</p>"}'
            f'<p class="read">{txt}</p></div>')


def main():
    ac = ES["autocorr"]
    b = ES["blowoff_mechanism"]
    abl = {a["name"]: a for a in AB["ablations"]}
    base = AB["baseline"]
    sw = {s["knob"]: s for s in AB["sweeps"]}

    entry = [c for c in ES["conditions"] if c["side"] == "vstop"]
    exit_ = [c for c in ES["conditions"] if c["side"] == "izstop"]

    widen = []
    for c in ES["conditions"]:
        for h in ES["horizons"]:
            v = c["m"]["donos"][str(h)]
            if v:
                widen.append((h, v["widen"]))
    wmax = {h: max(w for hh, w in widen if hh == h) for h in ES["horizons"]}

    P: list[str] = []
    A = P.append

    A(f"""<!doctype html><html lang="sl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lean — ali je vsak vstopni in izstopni pogoj sploh smiseln (BTC)</title>
<style>
  :root{{color-scheme:light;--plane:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;
    --muted:#898781;--grid:#e1e0d9;--axis:#c3c2b7;--ring:rgba(11,11,11,0.10);
    --band:rgba(11,11,11,0.05);--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;
    --good:#0ca30c;--warn:#fab219;--serious:#ec835a;--crit:#d03b3b;}}
  @media (prefers-color-scheme:dark){{:root:where(:not([data-theme="light"])){{color-scheme:dark;
    --plane:#0d0d0d;--surface:#1a1a19;--ink:#fff;--ink2:#c3c2b7;--muted:#898781;
    --grid:#2c2c2a;--axis:#383835;--ring:rgba(255,255,255,0.10);--band:rgba(255,255,255,0.07);
    --s1:#3987e5;--s2:#d95926;--s3:#199e70;--good:#2fbf2f;--crit:#e05555;}}}}
  :root[data-theme="dark"]{{color-scheme:dark;--plane:#0d0d0d;--surface:#1a1a19;--ink:#fff;
    --ink2:#c3c2b7;--muted:#898781;--grid:#2c2c2a;--axis:#383835;--ring:rgba(255,255,255,0.10);
    --band:rgba(255,255,255,0.07);--s1:#3987e5;--s2:#d95926;--s3:#199e70;
    --good:#2fbf2f;--crit:#e05555;}}
  *{{box-sizing:border-box}}
  body{{margin:0;background:var(--plane);color:var(--ink);
       font:15px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif}}
  main{{max-width:1120px;margin:0 auto;padding:40px 20px 80px}}
  h1{{font-size:26px;line-height:1.25;margin:0 0 4px;font-weight:650}}
  .sub{{color:var(--ink2);font-size:14px;margin:0 0 26px}}
  h2{{font-size:17px;font-weight:650;margin:38px 0 10px;padding-top:14px;
     border-top:1px solid var(--grid)}}
  h2:first-of-type{{border-top:0}}
  h3.s{{font-size:14.5px;font-weight:650;margin:22px 0 8px}}
  p{{margin:0 0 14px;max-width:76ch}}
  .cap{{color:var(--ink2);font-size:13px;margin:0 0 14px;max-width:82ch}}
  .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(430px,1fr));gap:16px}}
  .grid3{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px}}
  .card{{background:var(--surface);border:1px solid var(--ring);border-radius:10px;padding:14px}}
  .card h3{{font:600 13.5px system-ui;margin:0 0 1px}}
  .card .d{{color:var(--muted);font-size:12px;margin:0 0 8px}}
  .card .read{{font-size:12.5px;margin:10px 0 0;padding:8px 10px;border-radius:7px;
              background:var(--band);color:var(--ink2)}}
  .badge{{display:inline-block;font-size:10px;font-weight:700;letter-spacing:.04em;
         text-transform:uppercase;border-radius:999px;padding:2px 8px;margin-left:6px;
         color:#fff;vertical-align:2px}}
  svg{{display:block;width:100%;height:auto;overflow:visible}}
  text{{font:11px system-ui;fill:var(--muted);font-variant-numeric:tabular-nums}}
  .fig{{background:var(--surface);border:1px solid var(--ring);border-radius:10px;
       padding:18px;margin:0 0 18px;overflow-x:auto}}
  table{{border-collapse:collapse;width:100%;font-size:13px;font-variant-numeric:tabular-nums}}
  th,td{{text-align:right;padding:7px 9px;border-bottom:1px solid var(--grid);
        vertical-align:top}}
  th{{color:var(--ink2);font-weight:600;font-size:12px}}
  td.l,th.l{{text-align:left;font-variant-numeric:normal}}
  code{{font:12.5px ui-monospace,SFMono-Regular,Menlo,monospace;background:var(--band);
       padding:1px 5px;border-radius:4px}}
  .note{{background:var(--band);border-left:3px solid var(--s2);border-radius:0 8px 8px 0;
        padding:12px 16px;margin:0 0 18px}}
  .note p:last-child{{margin-bottom:0}}
  .kill{{border-left-color:var(--crit)}}
  .keep{{border-left-color:var(--good)}}
  footer{{margin-top:44px;padding-top:16px;border-top:1px solid var(--grid);
         color:var(--muted);font-size:12.5px}}
</style></head><body><main>""")

    A(f"""<h1>Ali je vsak vstopni in izstopni pogoj sploh smiseln?</h1>
<p class="sub">Diversitas Lean · samo BTC · vir cen Binance · okno
{ES['from']} → {ES['to']} ({ES['n_days']} dni po zavrženem ogrevanju) ·
fee + slippage 0,30 % na stran</p>""")

    # ── the question ────────────────────────────────────────────────────────
    A("<h2>1. Zakaj tega nismo mogli izmeriti prej</h2>")
    A(f"""<p>Strategija je v šestih letih in pol naredila <b>{base['trades']} poslov</b>. To je
premalo za kakršenkoli zaključek — s sedemnajstimi opazovanji ni mogoče ločiti spretnosti
od sreče. Doslej smo vsa pravila sodili posredno: vklopili ali izklopili smo eno pravilo in
gledali, kaj se zgodi s temi sedemnajstimi posli.</p>
<p>Tu naredimo nekaj drugega. <b>Vsako pravilo je vsak dan bodisi izpolnjeno bodisi ne.</b>
Namesto sedemnajstih poslov dobimo od 700 do 1700 opazovanj na pravilo. Za vsako pravilo
vprašamo eno preprosto stvar:</p>
<div class="note"><p><i>Kaj se je s ceno zgodilo v naslednjih 5, 20 in 60 dneh takrat, ko je
pravilo veljalo — v primerjavi s tem, ko ni veljalo?</i></p></div>
<p>Vstopno pravilo je smiselno, če mu sledi <b>boljše</b> nadaljevanje. Izstopno pravilo je
smiselno, če mu sledi <b>slabše</b>. Če je obratno, pravilo dela nasprotno od namena — ne
glede na to, kaj kaže backtest.</p>""")

    # ── how to read ─────────────────────────────────────────────────────────
    A("<h2>2. Kako se bere graf</h2>")
    A(f"""<p>Vsak graf ima navpično črto pri ničli — to je »ni razlike«. Pika je izmerjena
razlika. <b>Debela svetla črta je razpon negotovosti</b>: če seka ničlo, razlike nismo
dokazali, tudi če pika ni na ničli. Tanka črtkana črta je isti izračun po naivni metodi
in je tam samo zato, da vidite, koliko bi nas ta zavedla.</p>
<div class="note"><p><b>Zakaj naivna metoda laže.</b> Če danes gledam donos naslednjih 20
dni in jutri spet donos naslednjih 20 dni, se ti dve okni prekrivata v 19 dneh od 20. To je
skoraj ista številka, prešteta dvakrat. Izmerjeno na naših podatkih:</p>
<table style="margin-top:8px"><tr><th class="l">nadaljnji donos</th>
<th>ujemanje s prejšnjim dnem</th><th>čez 5 dni</th><th>čez 20 dni</th>
<th>naivni razpon je preozek za</th></tr>
{"".join(f'<tr><td class="l">{h}-dnevni</td><td>{ac[str(h)]["1"]:.2f}</td>'
         f'<td>{ac[str(h)]["5"]:.2f}</td><td>{ac[str(h)]["20"]:.2f}</td>'
         f'<td><b>{wmax[h]:.0f}×</b></td></tr>' for h in ES["horizons"])}
</table>
<p style="margin-top:10px">Pri 20-dnevnem donosu je sosednji dan 95 % ista številka. 747 dni
torej ni 747 dokazov, ampak približno 37. Zato so vsi razponi tu izračunani tako, da se
podatki jemljejo v <b>celih blokih</b>, dolgih toliko kot horizont — nikoli po posameznih
dneh. Naivna metoda bi razpone naredila do {max(wmax.values()):.0f}-krat preozke in bi
polovico spodnjih ugotovitev razglasila za dokazane.</p></div>""")

    # ── entry ───────────────────────────────────────────────────────────────
    A("<h2>3. Vstopni pogoji</h2>")
    A('<p class="cap">Pozitivno = po pravilu sledi boljši donos, torej pravilo dela to, '
      'kar naj bi. Vseh dvanajst vstopnih meritev kaže v pravo smer.</p>')
    A('<div class="grid">' + "".join(cond_card(c) for c in entry) + "</div>")

    # ── conditional ─────────────────────────────────────────────────────────
    A("<h3 class='s'>Ali filter kaj doda, ko je trg že prefiltriran?</h3>")
    A("""<p class="cap">Zgornji graf primerja dobre dni z vsemi ostalimi, vključno s sredino
medvedjega trga. To je prenizka letvica. Tu isto vprašanje ponovimo <b>samo znotraj dni,
ki jih 200-dnevno povprečje že spusti skozi</b> — torej: ali filter še vedno loči, ko je
najlažje delo že opravljeno?</p>""")
    A('<div class="fig"><table><tr><th class="l">filter</th>'
      + "".join(f"<th>{h} dni</th>" for h in ES["horizons"]) + "<th class='l'>branje</th></tr>")
    CR = {"above_tl": "Ne doda ničesar. Pri 60 dneh predznak celo obrne.",
          "dist_entry_ok": "Isti stolpec kot zgoraj — <b>to pravilo je matematični dvojnik</b> "
                           "<code>above_tl</code>.",
          "above_ma_med": "Ostane značilen na kratkem horizontu.",
          "track_rising_window": "Ostane značilen pri 5 in 20 dneh — najbolj trden filter."}
    for r in ES["conditional_on_regime"]:
        cells = ""
        for h in ES["horizons"]:
            v = r["m"][str(h)]
            if not v:
                cells += "<td>—</td>"; continue
            st = "font-weight:700;color:var(--good)" if v["sig"] else "color:var(--muted)"
            cells += (f'<td><span style="{st}">{v["diff"]:+.2f}</span><br>'
                      f'<span style="font-size:11px;color:var(--muted)">'
                      f'[{v["ci"][0]:+.1f}, {v["ci"][1]:+.1f}]</span></td>')
        A(f'<tr><td class="l"><code>{r["key"]}</code></td>{cells}'
          f'<td class="l" style="font-size:12.5px">{CR.get(r["key"],"")}</td></tr>')
    A("</table></div>")

    A(f"""<div class="note kill"><p><b>Prva najdba: eno pravilo je čisto podvajanje.</b>
<code>dist_entry_ok</code> zahteva, da je cena vsaj <code>mrtvi pas + min_dist_entry_pct</code>
nad trackline. Ker je <code>min_dist_entry_pct</code> nastavljen na 0, je to isti pogoj kot
<code>above_tl</code>. Preverjeno na vseh {ES['n_days']} dneh:
<b>{ES['dist_entry_disagreements']} dni razlike</b>. Pravilo v strategiji stoji dvakrat.</p></div>""")

    # ── incremental ─────────────────────────────────────────────────────────
    A("<h2>4. Kaj vsak filter dejansko blokira</h2>")
    A("""<p>Drugačen kot: filter odstranimo in pogledamo <b>samo tiste dneve, ki bi jih s tem
na novo vpustili</b>. Če je bilo blokiranje smiselno, so ti dnevi slabši od dni, ki jih
strategija tako ali tako sprejme (povprečno <b>+6,3 %</b> v 20 dneh).</p>""")
    A('<div class="fig">' + incremental_chart(ES["incremental"]) + "</div>")
    A('<div class="fig"><table><tr><th class="l">filter</th><th>dni, ki jih blokira</th>'
      '<th>20-dnevni donos na njih</th><th>razlika proti vstopnim dnem</th>'
      '<th class="l">sodba</th></tr>')
    IJ = {"regime_ok": ("<b>Odločno upravičen.</b> Blokira 35 dni s povprečnim donosom "
                        "−10 % — najbolj toksične dni v vzorcu.", "var(--good)"),
          "track_rising_window": ("<b>Upravičen.</b> Blokira 235 dni, ki v povprečju "
                                  "ne prinesejo nič.", "var(--good)"),
          "above_ma_med": ("Blokira le 65 dni in razlika ni dokazana — večino dela "
                           "opravita že druga dva.", "var(--warn)"),
          "above_tl": ("Blokira 0 dni, ker ima dvojnika, ki blokira iste.", "var(--muted)"),
          "dist_entry_ok": ("Blokira 0 dni iz istega razloga.", "var(--muted)")}
    for r in ES["incremental"]:
        j, col = IJ.get(r["key"], ("", "var(--muted)"))
        if r.get("m"):
            v = r["m"]["20"]
            A(f'<tr><td class="l"><code>{r["key"]}</code></td><td>{r["n_added"]}</td>'
              f'<td>{v["mean_true"]:+.2f} %</td>'
              f'<td>{v["diff"]:+.2f}<br><span style="font-size:11px;color:var(--muted)">'
              f'[{v["ci"][0]:+.1f}, {v["ci"][1]:+.1f}]</span></td>'
              f'<td class="l" style="font-size:12.5px;color:{col}">{j}</td></tr>')
        else:
            A(f'<tr><td class="l"><code>{r["key"]}</code></td><td>{r["n_added"]}</td>'
              f'<td>—</td><td>—</td><td class="l" style="font-size:12.5px;color:{col}">{j}</td></tr>')
    A("</table></div>")

    # ── exits ───────────────────────────────────────────────────────────────
    A("<h2>5. Izstopni pogoji</h2>")
    A('<p class="cap">Tu je pravi predznak <b>negativen</b>: po izstopnem signalu bi moral '
      'slediti slabši donos. Dva od treh izstopov tega ne naredita.</p>')
    A('<div class="grid">' + "".join(cond_card(c) for c in exit_) + "</div>")

    # ── blow-off ────────────────────────────────────────────────────────────
    A("<h2>6. Blow-off: pravilo, ki dela natanko nasprotno od svojega namena</h2>")
    A(f"""<p>Blow-off naj bi zaznal pregret vrh in nas spravil ven, preden se sesuje. V
{ES['n_days']} dneh se je sprožil <b>{b['n_fire']}-krat</b>. To je premalo za statistični
test, zato ga presodimo drugače: pogledamo, <b>kje v zgodovini ležijo ti dnevi</b> glede na
to, kaj je sledilo v naslednjih 60 dneh. Če pravilo zaznava vrhove, morajo njegove
sprožitve pristati levo — med dnevi z najslabšim nadaljevanjem.</p>""")
    A('<div class="fig">' + blowoff_chart(b) + "</div>")
    A(f"""<div class="note kill"><p><b>Vseh {b['n_fire']} sprožitev, in nobena ni blizu vrha.</b>
Mediana pristane na <b>{b['median_percentile_of_fwd60']}. percentilu</b> — po povprečni
sprožitvi je sledilo boljših 60 dni kot po {b['median_percentile_of_fwd60']:.0f} % vseh
ostalih dni v vzorcu. <b>{b['share_in_best_quartile']} % sprožitev je v najboljši četrtini,
{b['share_in_worst_quartile']} % v najslabši.</b> Datumi to potrdijo brez statistike: november
2020, prvi teden januarja 2021 in november 2024 — vsi trije so <i>začetki</i> največjih
rastih tega vzorca, ne konci.</p>
<p style="margin-top:10px">To pravilo je povzročilo <b>{base['exit_reasons']['blowoff']} od
{base['trades']} vseh poslov</b> — več kot tretjino. Ko ga izklopimo, ostane
{abl['brez_blowoff']['trades']} poslov, Sortino se dvigne z {base['sortino']} na
{abl['brez_blowoff']['sortino']}, MaxDD pa se ne spremeni za niti desetinko.</p></div>""")

    A("<h3 class='s'>In gumb kaže isto</h3>")
    A(f"""<p class="cap">Prag blow-offa ima vrh natanko na privzeti vrednosti 25 — kar je samo
po sebi sumljivo. Ključno pa je: <b>popolna odstranitev pravila (Sortino
{abl['brez_blowoff']['sortino']}) je boljša od vsake preizkušene vrednosti praga.</b> Vrh pri
25 je torej lokalni artefakt, ne optimum.</p>""")
    A('<div class="fig" style="max-width:520px">' +
      sweep_chart(sw["blowoff_dist_pct"]["points"], 25.0) + "</div>")

    # ── vol shock ───────────────────────────────────────────────────────────
    A("<h2>7. Vol-shock: pravilo, ki se v šestih letih ni sprožilo niti enkrat</h2>")
    A(f"""<p>Vol-shock naj bi ob nenadnem skoku nihajnosti pospešil izstop. V kodi je vezan na
pogoj <code>below_tl</code> — sproži se lahko samo takrat, ko je cena že pod trackline.
Zato ga ni pošteno primerjati z vsemi ostalimi dnevi; primerjati ga je treba <b>z drugimi
dnevi pod trackline</b>. Takrat se pokaže tole:</p>
<ul class="cap">
<li>Sproži se na <b>{next(c for c in exit_ if c['key']=='vol_shock')['n_fire']} dneh</b>.</li>
<li>Od {base['trades']} izstopov strategije je povzročil <b>točno {base['exit_reasons']['vol_shock']}</b>.</li>
<li>Izklop pravila spremeni Sortino za <b>{abl['brez_vol_shock']['d_sortino']:+.3f}</b> in
MaxDD za <b>{abl['brez_vol_shock']['d_maxdd']:+.1f} o. t.</b> — torej za nič, do tretje
decimalke.</li>
<li>Dnevom, na katerih se sproži, sledi <b>značilno boljših</b> naslednjih 60 dni kot
ostalim dnevom pod trackline: {next(c for c in exit_ if c['key']=='vol_shock')['m']['donos']['60']['diff']:+.2f} o. t.,
razpon [{next(c for c in exit_ if c['key']=='vol_shock')['m']['donos']['60']['ci'][0]:+.2f},
{next(c for c in exit_ if c['key']=='vol_shock')['m']['donos']['60']['ci'][1]:+.2f}].</li>
</ul>
<div class="note kill"><p>Pravilo torej hkrati <b>ne naredi ničesar</b> in <b>meri v napačno
smer</b>. Dve leti bi ga lahko imeli v produkciji in tega ne bi opazili — ker se nikoli ne
sproži prvi, saj ga izstop na <code>below_tl</code> vedno prehiti.</p></div>""")

    # ── evidence table ──────────────────────────────────────────────────────
    A("<h2>8. Dokazi za vsako predlagano odstranitev</h2>")
    A("""<p>To je odgovor na vprašanje »iz katere analize to veš«. Vsaka vrstica navaja
<b>vse</b> neodvisne dokaze, ne le tistega, ki je bil najbolj priročen.</p>""")
    A('<div class="fig"><table><tr><th class="l" style="width:15%">kaj</th>'
      '<th class="l" style="width:52%">dokazi</th><th class="l">sodba</th></tr>')

    vs = next(c for c in exit_ if c["key"] == "vol_shock")
    rows_ev = [
      ("vol-shock<br><code>vol_shock_mul</code>, <code>vol_lookback</code>",
       f"<b>1.</b> Povzročil je 0 od {base['trades']} izstopov v {ES['n_days']} dneh."
       f"<br><b>2.</b> Izklop spremeni Sortino za {abl['brez_vol_shock']['d_sortino']:+.3f}, "
       f"MaxDD za {abl['brez_vol_shock']['d_maxdd']:+.1f} o. t., število poslov za 0."
       f"<br><b>3.</b> Prelet <code>vol_shock_mul</code> od 1,2 do 3,0 premakne Sortino za "
       f"{sw['vol_shock_mul']['range_sortino']:.3f}; <code>vol_lookback</code> od 10 do 40 za "
       f"{sw['vol_lookback']['range_sortino']:.3f}."
       f"<br><b>4.</b> Dnevom sprožitve sledi značilno <i>boljših</i> 60 dni "
       f"({vs['m']['donos']['60']['diff']:+.2f} o. t.) kot ostalim dnevom pod trackline.",
       '<span style="color:var(--crit);font-weight:700">Odstraniti.</span><br>'
       'Mrtvo v backtestu in obrnjeno v smeri.'),

      ("blow-off<br><code>blowoff_dist_pct</code>, RSI prag, <code>rsi_len</code>",
       f"<b>1.</b> {b['n_fire']} sprožitev v {ES['n_days']} dneh — pod mejo testljivosti."
       f"<br><b>2.</b> Mediana sprožitve na {b['median_percentile_of_fwd60']}. percentilu "
       f"nadaljnjega 60-dnevnega donosa; {b['share_in_worst_quartile']} % v najslabši četrtini. "
       f"Zaznava dna rasti, ne vrhov."
       f"<br><b>3.</b> Povzroči {base['exit_reasons']['blowoff']} od {base['trades']} poslov — 35 % vse trgovalne aktivnosti."
       f"<br><b>4.</b> Izklop dvigne Sortino {base['sortino']} → {abl['brez_blowoff']['sortino']} "
       f"in ne poslabša MaxDD ({abl['brez_blowoff']['d_maxdd']:+.1f} o. t.). Razpon "
       f"[{abl['brez_blowoff']['ci_d_sortino'][0]:+.2f}, {abl['brez_blowoff']['ci_d_sortino'][1]:+.2f}] "
       f"seka ničlo — <i>izboljšanje ni dokazano</i>."
       f"<br><b>5.</b> Popoln izklop je boljši od vseh petih preizkušenih vrednosti praga.",
       '<span style="color:var(--crit);font-weight:700">Odstraniti.</span><br>'
       'Ne zaradi statistike, ampak ker mehanizem dokazljivo ne dela tega, kar trdi.'),

      ("<code>min_dist_entry_pct</code>",
       f"<b>1.</b> Pri vrednosti 0 je <code>dist_entry_ok</code> matematično isti pogoj kot "
       f"<code>above_tl</code>; preverjeno na {ES['n_days']} dneh — "
       f"{ES['dist_entry_disagreements']} dni razlike."
       f"<br><b>2.</b> Zato v inkrementalnem testu blokira 0 dni."
       f"<br><b>3.</b> Prelet 0 → 3 premakne Sortino za {sw['min_dist_entry_pct']['range_sortino']:.3f}.",
       '<span style="color:var(--crit);font-weight:700">Odstraniti.</span><br>'
       'Čista poenostavitev kode, brez spremembe vedenja.'),

      ("<code>ma_med_len</code><br>(50-dnevno povprečje)",
       f"<b>1.</b> Prelet od 40 do 120 premakne Sortino za manj kot 0,01 — "
       f"celoten razpon 20–120 je {sw['ma_med_len']['range_sortino']:.3f}."
       f"<br><b>2.</b> <i>Ampak</i>: <code>above_ma_med</code> je edini posamezni filter, "
       f"ki je značilen sam zase (+{next(c for c in entry if c['key']=='above_ma_med')['m']['donos']['5']['diff']:.2f} "
       f"o. t. na 5 dni), in ostane značilen tudi znotraj prefiltriranega trga.",
       '<span style="color:var(--good);font-weight:700">Pravilo obdržati, gumb zakleniti.</span>'
       '<br>Vrednost 50 fiksirati in je ne uvrščati med nastavljive parametre.'),
    ]
    for a, bb, c in rows_ev:
        A(f'<tr><td class="l">{a}</td><td class="l" style="font-size:12.5px">{bb}</td>'
          f'<td class="l" style="font-size:12.5px">{c}</td></tr>')
    A("</table></div>")

    A(f"""<div class="note keep"><p><b>Popravek prejšnjega priporočila.</b> V prvi različici
tega seznama je bilo <code>ma_med_len</code> navedeno med stvarmi za odstranitev, z
utemeljitvijo »premakni ga kamorkoli, rezultat se ne spremeni«. Prelet to res pokaže — a
meri <b>gumb</b>, ne <b>pravilo</b>. Ko je bilo isto pravilo testirano po lastni predpostavki,
se je izkazalo za edini posamezni filter z značilnim učinkom. Pravilno je torej: gumb je
mrtev, pravilo ni. Ti dve vprašanji sta ločeni in ju je treba ločeno testirati.</p></div>""")

    # ── knobs ───────────────────────────────────────────────────────────────
    A("<h2>9. Preleti gumbov</h2>")
    A('<p class="cap">Vodoravna črta pomeni, da gumba ni vredno nastavljati. Oranžna pika je '
      'privzeta vrednost. Pravilo ostaja ves čas vklopljeno — meri se samo občutljivost na '
      'nastavitev.</p>')
    A('<div class="grid3">')
    for k, s in sw.items():
        tag = (badge("mrtev gumb", "var(--muted)") if s["inert"] else "")
        A(f'<div class="card"><h3><code>{k}</code>{tag}</h3>'
          f'<p class="d">razpon Sortina čez cel prelet: {s["range_sortino"]:.3f}</p>'
          f'{sweep_chart(s["points"], DEFAULTS[k])}</div>')
    A("</div>")

    # ── summary ─────────────────────────────────────────────────────────────
    A("<h2>10. Povzetek</h2>")
    A('<div class="fig"><table><tr><th class="l">pogoj</th><th class="l">kaj naj bi delal</th>'
      '<th class="l">kaj dela</th><th class="l">sodba</th></tr>')
    SUM = [
      ("regime_ok", "blokira vstop v medvedjem trgu",
       "blokira 35 dni s povprečnim donosom −10 %; +13 o. t. na 60 dni",
       ("obdržati — najbolje dokazan", "var(--good)")),
      ("track_rising_window", "zahteva, da trend res raste",
       "značilen pri 20 dneh, ostane značilen tudi znotraj bikovskega trga",
       ("obdržati — najbolje dokazan", "var(--good)")),
      ("above_ma_med", "zahteva ceno nad srednjim trendom",
       "značilen na 5 dni; inkrementalno šibek, a nikoli škodljiv",
       ("obdržati, gumb zakleniti", "var(--good)")),
      ("above_tl", "zahteva ceno nad trackline",
       "pozitiven predznak, a noben razpon ne izloči ničle",
       ("obdržati — je jedro logike", "var(--warn)")),
      ("dist_entry_ok", "dodatna razdalja nad trackline",
       "matematični dvojnik zgornjega; 0 dni razlike",
       ("odstraniti", "var(--crit)")),
      ("below_tl", "izstop ob prebitju navzdol",
       "pravi predznak, a razlika premajhna glede na razpršenost",
       ("obdržati — edini pravi izstop", "var(--warn)")),
      ("blowoff", "izstop na pregretem vrhu",
       f"sproži na {b['median_percentile_of_fwd60']}. percentilu nadaljnjih donosov — na dnu rasti",
       ("odstraniti", "var(--crit)")),
      ("vol_shock", "izstop ob skoku nihajnosti",
       f"{base['exit_reasons']['vol_shock']} sprožitev od {base['trades']} izstopov; smer obrnjena",
       ("odstraniti", "var(--crit)")),
    ]
    for k, should, does, (verdict, col) in SUM:
        A(f'<tr><td class="l"><code>{k}</code></td>'
          f'<td class="l" style="font-size:12.5px">{should}</td>'
          f'<td class="l" style="font-size:12.5px">{does}</td>'
          f'<td class="l" style="font-size:12.5px;color:{col};font-weight:600">{verdict}</td></tr>')
    A("</table></div>")

    # ── limits ──────────────────────────────────────────────────────────────
    A("<h2>11. Česa ta analiza NE dokaže</h2>")
    A(f"""<p>Merjeno je na istem BTC, na katerem so bili privzetki nekoč nastavljeni. Ta test
odpravi <b>pomanjkanje moči</b> — namesto {base['trades']} opazovanj jih imamo do 1700 — ne
odpravi pa <b>kontaminacije</b>. To sta dve različni težavi in nobena količina računanja na
teh podatkih ne reši druge.</p>
<p>Konkretno to pomeni:</p>
<ul class="cap">
<li>Ugotovitve o <b>napačni smeri</b> (blow-off, vol-shock) so trdne, ker ne slonijo na
statistični značilnosti, ampak na mehanizmu: pravilo trdi, da zaznava vrh, in dokazljivo
ne zaznava vrha.</li>
<li>Ugotovitve o <b>koristnosti</b> (regime_ok, track_rising_window) so šibkejše. Lahko
držijo, lahko pa gre za lastnost tega konkretnega obdobja.</li>
<li>Nič od tega ne pove, ali bo strategija delovala naprej.</li>
</ul>
<p>Poštena trditev, ki jo ta dokument podpira, je torej ozka in se glasi:
<b>štiri pravila ne prestanejo preizkusa lastne predpostavke in jih je zato mogoče
odstraniti, ne da bi kaj izgubili.</b></p>""")

    A(f"""<footer>
Vir cen: Binance (zamrznjen posnetek <code>testing/data/sources/BTC_binance.parquet</code>) ·
okno {ES['from']} → {ES['to']}, {ES['n_days']} dni po zavrženem ogrevanju ·
fee + slippage {AB['fee_per_side_pct']} % na stran.<br>
Razponi negotovosti: krožni bločni bootstrap, {ES['nboot']} vzorcev, dolžina bloka
{ES['block_rule']}, seme {ES['seed']}. Ablacijski razponi: parni bločni bootstrap,
{AB['nboot']} vzorcev, blok {AB['block']} dni — isti prevzorčeni dnevi na obeh serijah, tako
da se skupno tržno gibanje odšteje.<br>
Ponovljivo z <code>testing/scripts/event_study.py</code> in
<code>testing/scripts/ablation.py</code>; ta stran je zgrajena z
<code>testing/scripts/build_report_pogoji.py</code>.
</footer></main></body></html>""")

    OUT.write_text("".join(P), encoding="utf-8")
    print(f"-> {OUT}  ({OUT.stat().st_size/1024:.0f} kB)")


if __name__ == "__main__":
    main()
