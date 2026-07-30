"""Build testing/porocilo_pogoji_BTC.html — charts, what they show, what to test next.

Deliberately short. The long-form derivation lives in the scripts and the JSON;
this page is for a meeting, so it carries the pictures, one line of reading per
picture, and the open questions with a concrete test attached to each.

Charts are inline SVG rather than library-drawn, so the file opens anywhere and
cannot render stale numbers from a cached script.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ES = json.loads((ROOT / "testing" / "data" / "event_study_BTC.json").read_text(encoding="utf-8"))
AB = json.loads((ROOT / "testing" / "data" / "ablation_BTC.json").read_text(encoding="utf-8"))
EX = json.loads((ROOT / "testing" / "data" / "exit_rules_BTC.json").read_text(encoding="utf-8"))
AU = json.loads((ROOT / "testing" / "data" / "audit_BTC.json").read_text(encoding="utf-8"))
AF = json.loads((ROOT / "testing" / "data" / "ablation_full_BTC.json").read_text(encoding="utf-8"))
OUT = ROOT / "testing" / "porocilo_pogoji_BTC.html"


def ci_chart(rows, w=430) -> str:
    rows = [r for r in rows if r[1] is not None]
    if not rows:
        return '<p class="cap">Premalo opazovanj — test ni mogoč.</p>'
    pad_l, pad_r, row_h, top = 46, 12, 36, 16
    h = top + row_h * len(rows) + 24
    lim = max(max(abs(v) for v in (r[2][0], r[2][1], r[1])) for r in rows) * 1.12 or 1
    def x(v): return pad_l + (v + lim) / (2 * lim) * (w - pad_l - pad_r)
    p = [f'<svg viewBox="0 0 {w} {h}" role="img">']
    zx = x(0)
    p.append(f'<rect x="{pad_l}" y="{top-8}" width="{w-pad_l-pad_r}" '
             f'height="{row_h*len(rows)+2}" fill="var(--band)" rx="5"/>')
    p.append(f'<line x1="{zx:.1f}" y1="{top-8}" x2="{zx:.1f}" '
             f'y2="{top+row_h*len(rows)-6}" stroke="var(--axis)" stroke-width="1.5"/>')
    for i, (lab, d, ci, sig) in enumerate(rows):
        y = top + row_h * i + 8
        col = "var(--s1)" if sig and d > 0 else ("var(--crit)" if sig and d < 0 else "var(--muted)")
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



def mini_equity(base, alt, bench, idx, w=420, h=185) -> str:
    """Baseline against one ablation. Linear axis, full resolution, no log:
    a log axis would hide how much of the difference is one late run."""
    hi = max(max(base), max(alt), max(bench)) * 1.05
    pad_l, pad_r, pad_t, pad_b = 34, 12, 12, 26
    n = len(idx)

    def X(i): return pad_l + i / (n - 1) * (w - pad_l - pad_r)
    def Y(v): return pad_t + (1 - v / hi) * (h - pad_t - pad_b)

    out = [f'<svg viewBox="0 0 {w} {h}" role="img">']
    step = max(1, int(hi // 5))
    g = 0
    while g <= hi:
        out.append(f'<line x1="{pad_l}" y1="{Y(g):.1f}" x2="{w-pad_r}" y2="{Y(g):.1f}" '
                   f'stroke="var(--grid)"/>')
        out.append(f'<text x="{pad_l-5}" y="{Y(g)+4:.1f}" text-anchor="end">{g}×</text>')
        g += step
    seen = set()
    for i, d in enumerate(idx):
        if d[:4] not in seen:
            seen.add(d[:4])
            out.append(f'<text x="{X(i):.1f}" y="{h-8}" text-anchor="middle">'
                       f"'{d[2:4]}</text>")

    def path(v):
        return " ".join(f'{"M" if i == 0 else "L"}{X(i):.0f},{Y(x):.1f}'
                        for i, x in enumerate(v))

    out.append(f'<path d="{path(bench)}" fill="none" stroke="var(--muted)" '
               f'stroke-width="1" opacity=".4"/>')
    out.append(f'<path d="{path(base)}" fill="none" stroke="var(--crit)" '
               f'stroke-width="2.6"/>')
    out.append(f'<path d="{path(alt)}" fill="none" stroke="var(--s1)" '
               f'stroke-width="1.7" stroke-dasharray="4 3"/>')
    return "".join(out) + "</svg>"


def blowoff_chart(bm, w=860, h=150) -> str:
    pad_l, pad_r, pad_t = 30, 30, 30
    def X(v): return pad_l + v / 100 * (w - pad_l - pad_r)
    p = [f'<svg viewBox="0 0 {w} {h}" role="img">']
    p.append(f'<rect x="{X(0):.0f}" y="{pad_t}" width="{X(25)-X(0):.0f}" height="44" '
             f'fill="var(--crit)" opacity=".13" rx="4"/>')
    p.append(f'<rect x="{X(75):.0f}" y="{pad_t}" width="{X(100)-X(75):.0f}" height="44" '
             f'fill="var(--good)" opacity=".13" rx="4"/>')
    p.append(f'<line x1="{pad_l}" y1="{pad_t+44}" x2="{w-pad_r}" y2="{pad_t+44}" '
             f'stroke="var(--axis)"/>')
    for v in (0, 25, 50, 75, 100):
        p.append(f'<line x1="{X(v):.1f}" y1="{pad_t+44}" x2="{X(v):.1f}" y2="{pad_t+50}" '
                 f'stroke="var(--axis)"/>')
        p.append(f'<text x="{X(v):.1f}" y="{pad_t+64}" text-anchor="middle">{v}.</text>')
    seen: dict[int, int] = {}
    for v in bm["percentiles"]:
        k = int(round(v)); lvl = seen.get(k, 0); seen[k] = lvl + 1
        p.append(f'<circle cx="{X(v):.1f}" cy="{pad_t+36-lvl*9:.1f}" r="4.5" '
                 f'fill="var(--s2)" stroke="var(--surface)" stroke-width="1"/>')
    p.append(f'<text x="{X(12):.0f}" y="{pad_t-11}" text-anchor="middle" '
             f'style="fill:var(--crit);font-weight:600">tu bi morale biti sprožitve</text>')
    p.append(f'<text x="{X(87):.0f}" y="{pad_t-11}" text-anchor="middle" '
             f'style="fill:var(--good);font-weight:600">tu so</text>')
    p.append(f'<text x="{pad_l}" y="{h-6}">percentil 60-dnevnega donosa po sprožitvi · '
             f'0. = najslabše nadaljevanje v vzorcu, 100. = najboljše</text>')
    return "".join(p) + "</svg>"


# key -> (what the rule mechanically does, at the shipped defaults;
#         the parameters it uses; the one-line verdict; badge)
READ = {
 "above_tl": (
   "<b>Trackline</b> je sredina zadnjih 75 dni: vzemi najvišjo točko in najnižjo točko "
   "zadnjih 75 dni in ju povpreči. Pogoj velja, ko je zaključni tečaj <b>več kot 3 % nad "
   "to sredino</b>.<br><br>Pove, da je cena v zgornji polovici svojega tromesečnega "
   "razpona, in to z rezervo. Teh 3 % je <i>mrtvi pas</i> — brez njega bi se signal "
   "prižigal in ugašal ob vsakem drobnem nihaju okoli sredine.",
   "track_period = 75 dni · track_buf_pct = 3 %",
   "Predznak je pravi, a noben razpon ne izloči ničle.", "?"),

 "above_ma_med": (
   "Povprečje zaključnih tečajev zadnjih <b>50 dni</b>. Pogoj velja, ko je cena nad njim — "
   "tu brez kakršnekoli rezerve.<br><br>Najbolj običajen filter smeri srednjeročnega "
   "trenda, ki obstaja. Namenoma ni nič posebnega.",
   "ma_med_len = 50 dni",
   "Značilen na 5 dni — edini posamezni filter, ki je.", "ok"),

 "track_rising_window": (
   "Današnja vrednost trackline je <b>višja kot pred 10 dnevi</b>.<br><br>Ni dovolj, da je "
   "cena visoko. Sam razpon, v katerem se giblje, se mora premikati navzgor. To je pravilo, "
   "ki ubija stranski trg — tam cena niha gor in dol, a sredina razpona stoji na mestu.",
   "track_slope_bars = 10 dni",
   "Značilen na 20 dni. Najbolj trden posamezni filter.", "ok"),

 "regime_ok": (
   "Zapora nastopi <b>samo, če sta izpolnjena oba pogoja hkrati</b>: cena je pod "
   "200-dnevnim povprečjem <b>in</b> to povprečje pada (je nižje kot pred 5 dnevi). Če velja "
   "le eno od tega, zapore ni.<br><br>To je zapornik za medvedji trg. Namenoma zahteva "
   "oboje — sicer bi blokiral ob vsakem prvem prebitju navzdol sredi zdravega trenda.",
   "ma_long_len = 200 dni · ma_slope = 5 dni",
   "Blokira najhujše dni, a nad povprečnim dnevom doda le +0,4 o. t. — varovalka, ne izbirnik.", "ok"),

 "bull_condition": (
   "Vsi štirje zgornji pogoji izpolnjeni <b>hkrati, isti dan</b>.<br><br>Pozor: to še <b>ni "
   "nakup</b>. Pozicija nastane šele, ko je ta kombinacija izpolnjena <b>3 dni zapored</b> "
   "in je od zadnje spremembe signala minilo vsaj <b>15 dni</b>. Ti dve zamudi sta razlog, "
   "zakaj ima strategija 17 poslov in ne 200.",
   "confirm_bars = 3 dni · reentry_hold = 15 dni",
   "Kombinacija je močnejša od vsakega dela posebej — filtri se torej ne podvajajo.", "ok"),

 "below_tl": (
   "Zrcalna slika vstopa: cena je <b>več kot 3 % pod</b> sredino zadnjih 75 dni.<br><br>"
   "Izstop se ne zgodi takoj. Pogoj mora veljati <b>3 dni zapored</b>, sicer nas vsak "
   "enodnevni sunek vrže iz pozicije. To je <b>glavni izstop</b> — povzroči 13 od 21 poslov "
   "in nosi večino izstopne strani strategije.",
   "track_period = 75 dni · track_buf_pct = 3 % · exit_grace_bars = 3 dni",
   "Pravi predznak, a razlika je premajhna glede na razpršenost.", "?"),

 "blowoff": (
   "Cena je <b>več kot 25 % nad</b> trackline <b>in</b> hkrati je RSI nad 80. RSI je "
   "kazalnik pregretosti od 0 do 100; nad 80 pomeni zelo hitro rast v kratkem času.<br><br>"
   "Naj bi ujel evforični skok tik pred zlomom. Izstop je <b>takojšen</b>, brez treh dni "
   "čakanja.<br><br>Primerjan je z <b>drugimi enako raztegnjenimi dnevi</b>, ne z vsemi — "
   "pravilo se posvetuje samo, ko je cena že več kot 25 % nad trackline, zato je to edina "
   "smiselna primerjalna skupina.",
   "blowoff_dist_pct = 25 % · RSI prag = 80 · rsi_len = 14 dni",
   "Ob upoštevanju bazne stopnje in števila testov ostane nedokazan.", "?"),

 "vol_shock": (
   "Nihajnost zadnjih 20 dni je <b>več kot 1,5-krat višja</b> od svojega 50-dnevnega "
   "povprečja <b>in</b> je cena hkrati pod trackline.<br><br>Naj bi pospešil izstop ob "
   "paniki. Ker pa zahteva tudi pogoj <code>below_tl</code>, se <b>ne more sprožiti "
   "sam</b> — vedno ga prehiti navadni izstop. Zato ga primerjamo samo z drugimi dnevi pod "
   "trackline; primerjava z vsemi dnevi bi merila <code>below_tl</code>, ne njega.",
   "vol_shock_mul = 1,5 · vol_lookback = 20 dni",
   "Sproži se pred značilno BOLJŠIMI naslednjimi 60 dnevi. Smer je obrnjena.", "bad"),
}
BADGE = {"ok": ("dokazan", "var(--good)"), "?": ("nedokazan", "var(--warn)"),
         "bad": ("dela narobe", "var(--crit)")}


# Each exit rule is measured against the days on which it is actually consulted.
# blow-off only ever fires when price is already far above the trackline, so its
# peer group is the other extended days, not the whole sample; vol-shock is gated
# on below_tl in the code, so its peer group is the other below-trackline days.
PEER = {
    "blowoff":   (lambda: EX["blowoff_vs_extended"]["m"]["donos"],
                  "primerjano med dnevi &gt; 25 % nad trackline"),
    "vol_shock": (None, "primerjano med dnevi pod trackline"),
}


def _base_line(r):
    """How much the rule adds over an average day, not just over its complement.

    The complement of a bull filter is mostly bear market, so beating it is easy.
    Beating the unconditional average is the harder and more honest bar."""
    row = next((x for x in AU["entry_vs_base"] if x["key"] == r["key"]), None)
    if not row or "20" not in row["h"]:
        return ""
    v = row["h"]["20"]
    col = "var(--good)" if v["vs_base"] >= 1.0 else "var(--muted)"
    return (f'<p class="par" style="color:{col}">čez 20 dni: {v["mean_true"]:+.2f} % ob pogoju '
            f'proti {v["base"]:+.2f} % na povprečnem dnevu &rarr; '
            f'<b>{v["vs_base"]:+.2f} o. t. nad bazo</b></p>')


def card(r):
    src, note = PEER.get(r["key"], (None, ""))
    m = src() if src else r["m"]["donos"]
    rows = [(f"{h} dni", v["diff"], v["ci"], v["sig"])
            for h in ES["horizons"]
            if (v := m.get(str(h))) and not v.get("too_few")]
    what, params, txt, bk = READ[r["key"]]
    lab, col = BADGE[bk]
    gate = f" · {note}" if note else ""
    return (f'<div class="card"><h3>{r["key"]}'
            f'<span class="badge" style="background:{col}">{lab}</span></h3>'
            f'<p class="d">{r["label"]} · velja na {r["n_fire"]} dneh '
            f'({r["share"]} % vzorca){gate}</p>'
            f'<p class="long">{what}</p>'
            f'<p class="par">privzeto: {params}</p>'
            f'{ci_chart(rows)}{_base_line(r)}'
            f'<p class="read"><b>Sodba:</b> {txt}</p></div>')


def main():
    b_ = ES["blowoff_mechanism"]
    base = AB["baseline"]
    abl = {a["name"]: a for a in AB["ablations"]}
    entry = [c for c in ES["conditions"] if c["side"] == "vstop"]
    exit_ = [c for c in ES["conditions"] if c["side"] == "izstop"]
    vs = next(c for c in exit_ if c["key"] == "vol_shock")

    P: list[str] = []
    A = P.append
    A(f"""<!doctype html><html lang="sl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lean — ali je vsak pogoj smiseln (BTC)</title><style>
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
  font:15px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif}}
 main{{max-width:1120px;margin:0 auto;padding:36px 20px 70px}}
 h1{{font-size:25px;margin:0 0 4px;font-weight:650}}
 .sub{{color:var(--ink2);font-size:13.5px;margin:0 0 24px}}
 h2{{font-size:16.5px;font-weight:650;margin:34px 0 8px;padding-top:13px;
  border-top:1px solid var(--grid)}}
 h2:first-of-type{{border-top:0;margin-top:8px}}
 p{{margin:0 0 12px;max-width:78ch}}
 .cap{{color:var(--ink2);font-size:13px;margin:0 0 14px;max-width:82ch}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(420px,1fr));gap:14px}}
 .card{{background:var(--surface);border:1px solid var(--ring);border-radius:10px;padding:13px}}
 .card h3{{font:600 13.5px ui-monospace,SFMono-Regular,Menlo,monospace;margin:0 0 1px}}
 .card .d{{color:var(--muted);font-size:12px;margin:0 0 6px}}
 .card .long{{font-size:12.5px;line-height:1.6;color:var(--ink2);margin:0 0 8px}}
 .card .par{{font:11.5px ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--muted);
  margin:0 0 10px;padding:5px 8px;border-radius:6px;background:var(--band)}}
 .card .read{{font-size:12.5px;margin:8px 0 0;padding:7px 9px;border-radius:7px;
  background:var(--band);color:var(--ink2)}}
 .badge{{display:inline-block;font-size:10px;font-weight:700;letter-spacing:.04em;
  text-transform:uppercase;border-radius:999px;padding:2px 7px;margin-left:6px;color:#fff}}
 svg{{display:block;width:100%;height:auto;overflow:visible}}
 text{{font:11px system-ui;fill:var(--muted);font-variant-numeric:tabular-nums}}
 .fig{{background:var(--surface);border:1px solid var(--ring);border-radius:10px;
  padding:16px;margin:0 0 16px;overflow-x:auto}}
 table{{border-collapse:collapse;width:100%;font-size:13px;font-variant-numeric:tabular-nums}}
 th,td{{text-align:left;padding:7px 9px;border-bottom:1px solid var(--grid);vertical-align:top}}
 th{{color:var(--ink2);font-weight:600;font-size:12px}}
 code{{font:12.5px ui-monospace,SFMono-Regular,Menlo,monospace;background:var(--band);
  padding:1px 5px;border-radius:4px}}
 .note{{background:var(--band);border-left:3px solid var(--crit);border-radius:0 8px 8px 0;
  padding:11px 15px;margin:0 0 16px}}
 .note p:last-child{{margin-bottom:0}}
 footer{{margin-top:38px;padding-top:14px;border-top:1px solid var(--grid);
  color:var(--muted);font-size:12.5px}}
</style></head><body><main>

<h1>Ali je vsak vstopni in izstopni pogoj smiseln?</h1>
<p class="sub">Lean · BTC · Binance · {ES['from']} → {ES['to']} ({ES['n_days']} dni) ·
fee + slippage 0,30 % na stran</p>

<p>Strategija ima {base['trades']} poslov — premalo za sodbo o posameznem pravilu. Zato
vsako pravilo sodimo po <b>vseh dneh, ko velja</b> (700–1700 opazovanj namesto
{base['trades']}), in vprašamo eno stvar: <i>kaj je sledilo, ko je pravilo veljalo, v
primerjavi s tem, ko ni?</i></p>

<h2>Kako se bere graf</h2>
<div class="fig"><div class="grid" style="gap:22px">
<div>
<p style="margin:0 0 8px"><b>Kaj je številka</b></p>
<p class="cap" style="margin:0 0 10px">Vse dni v vzorcu razdelimo na dva kupa: dnevi, ko je
pravilo <b>izpolnjeno</b>, in dnevi, ko <b>ni</b>. Za oba kupa izračunamo, koliko je BTC v
povprečju zrasel v naslednjih N dneh. <b>Številka na grafu je razlika med tema dvema
povprečjema</b>, v odstotnih točkah.</p>
<p class="cap" style="margin:0 0 10px"><b>Primer.</b> Pri <code>bull_condition</code> piše
<b>+1,68</b> pri 5 dneh. Beri: v petih dneh po dnevih, ko so bili vsi vstopni pogoji
izpolnjeni, je BTC v povprečju zrasel za 1,68 odstotne točke <b>več</b> kot v petih dneh po
vseh ostalih dneh.</p>
<p class="cap" style="margin:0"><b>To ni donos strategije.</b> Je merilo, ali pravilo sploh
kaže v pravo smer. Vstopno pravilo naj bi bilo <b>pozitivno</b>, izstopno
<b>negativno</b>. Črta je razpon negotovosti — <b>če seka ničlo, razlike nismo
dokazali</b>, tudi če pika ni na ničli.</p>
</div>
<div>
<p style="margin:0 0 8px"><b>Zakaj tri različna števila dni</b></p>
<table style="margin:0 0 10px">
<tr><td><b>5 dni</b></td><td style="font-size:12.5px">približno teden. Ali pravilo pove kaj
<i>takoj</i>?</td></tr>
<tr><td><b>20 dni</b></td><td style="font-size:12.5px">približno mesec. To je merilo, na
katerem strategija dejansko živi — povprečen posel traja tedne.</td></tr>
<tr><td><b>60 dni</b></td><td style="font-size:12.5px">približno četrtletje. Se trend
nadaljuje ali se prelomi?</td></tr>
</table>
<p class="cap" style="margin:0 0 10px">Pravilo, ki deluje samo na enem od teh treh, je bolj
sumljivo kot pravilo, ki na vseh treh deluje šibkeje.</p>
<p class="cap" style="margin:0"><b>Zakaj so črte pri 60 dneh dosti daljše.</b> Ker je manj
<i>neodvisnih</i> opazovanj: 60-dnevni okni sosednjih dni se prekrivata v 59 dneh od 60, zato
{ES['n_days']} dni da le okoli 40 res ločenih 60-dnevnih obdobij. Manj dokazov pomeni širši
razpon. To ni napaka grafa — nasprotno, ožja črta bi bila laž.</p>
</div>
</div></div>""")

    A("""<h3 style="font-size:14.5px;margin:24px 0 8px">Zakaj ne navaden statistični
test — na konkretnem primeru</h3>""")
    A(f"""<p>To je edina tehnična podrobnost na strani, ki jo je vredno razumeti, ker
<b>spremeni sklep</b>, ne le decimalke.</p>

<p><b>Kaj bi naredil navaden test.</b> Vzame 747 dni, ko velja
<code>bull_condition</code>, in reče: imam 747 neodvisnih dokazov. Iz tega izračuna, da je
razlika +5,05 o. t. znana zelo natančno.</p>

<p><b>Zakaj to ni res.</b> Predstavljajte si, da merim donos naslednjih 20 dni. V ponedeljek
izmerim od ponedeljka do petka tri tedne naprej. V torek izmerim od torka do naslednjega
torka. <b>Ti dve številki opisujeta skoraj isto obdobje</b> — delita 19 dni od 20. Ko potem
oba dneva preštejem kot ločena dokaza, isto dogajanje preštejem dvakrat. In tako čez cel
vzorec.</p>

<p>Koliko točno se ponavlja, se da izmeriti. Spodaj je ujemanje med današnjo in jutrišnjo
meritvijo istega nadaljnjega donosa:</p>

<table style="max-width:560px;margin:0 0 14px">
<tr><th class="l">nadaljnji donos</th><th>ujemanje z jutrišnjo meritvijo</th>
<th>koliko dni do neodvisnosti</th></tr>
<tr><td>5-dnevni</td><td>{ES['autocorr']['5']['1']:.2f}</td><td>~5</td></tr>
<tr><td>20-dnevni</td><td><b>{ES['autocorr']['20']['1']:.2f}</b></td><td>~20</td></tr>
<tr><td>60-dnevni</td><td><b>{ES['autocorr']['60']['1']:.2f}</b></td><td>~60</td></tr>
</table>

<p>Pri 20-dnevnem donosu je jutrišnja meritev <b>95 % ista številka</b> kot današnja. Torej
747 dni <b>ni 747 dokazov, ampak približno 37</b> — toliko, kolikor je v njih ločenih
20-dnevnih obdobij.</p>

<p><b>Kaj naredi bločni bootstrap.</b> Namesto da bi jemal posamezne dni, jemlje
<b>cele bloke zaporednih dni</b>, dolge toliko kot horizont. Če se ista trotedenska epizoda
ponavlja, se v vzorcu pojavi kot ena epizoda, ne kot dvajset. Tako sestavi 2000 nadomestnih
vzorcev in razpršenost njihovih rezultatov je pošten razpon negotovosti.</p>

<p><b>In zdaj, zašto to spremeni sklep.</b> Ista razlika, ista strategija, isti podatki —
samo pošteno preštet:</p>

<table style="max-width:640px;margin:0 0 14px">
<tr><th class="l">razlika pri <code>bull_condition</code></th>
<th>navaden test</th><th>bločni bootstrap</th><th>koliko širše</th></tr>
{"".join(
  f'<tr><td>čez {h} dni: {v["diff"]:+.2f} o. t.</td>'
  f'<td>[{v["ci_naive"][0]:+.2f}, {v["ci_naive"][1]:+.2f}]</td>'
  f'<td><b>[{v["ci"][0]:+.2f}, {v["ci"][1]:+.2f}]</b></td>'
  f'<td>{v["widen"]:.1f}×</td></tr>'
  for h in ES["horizons"]
  if (v := next(c for c in ES["conditions"] if c["key"] == "bull_condition")["m"]["donos"][str(h)]))}
</table>

<p>Pri 60 dneh bi navaden test rekel »razlika je med +9 in +15 o. t., torej očitno resnična«.
Pošten razpon gre <b>od −5 do +32</b> in <b>zajema ničlo</b>. Ena metoda razglasi ugotovitev
za dokazano, druga za nedokazano. <b>Vse, kar je na tej strani označeno kot »značilno«,
je značilno po strožji metodi</b> — po ohlapni bi jih bilo označenih približno dvakrat
toliko.</p>""")

    A("<h2>Vstopni pogoji</h2>")
    A('<div class="grid">' + "".join(card(c) for c in entry) + "</div>")

    A("<h2>Izstopni pogoji</h2>")
    A('<div class="grid">' + "".join(card(c) for c in exit_) + "</div>")

    bx = EX["blowoff_vs_extended"]
    fired = EX["blowoff_exits"]
    fs = EX.get("blowoff_exits_summary", {})
    d20 = bx["m"]["donos"]["20"]
    dd5 = bx["m"]["maxdd"]["5"]
    vsw = EX["vol_shock_threshold_sweep"]
    va = EX["vol_shock_actionable"]

    A("<h2>Izstopni pogoji podrobneje</h2>")
    A(f"""<p><b>Blow-off ostaja nedokazan v obe smeri.</b> Vrha ne zna napovedati: mediana
sprožitve pristane na {b_['median_percentile_of_fwd60']}. percentilu nadaljnjega 60-dnevnega
donosa. Sledi mu sicer globlji vmesni padec kot drugim enako raztegnjenim dnevom, a ta
ugotovitev ne vzdrži pregleda: <b>{AU['dd_base_rate']['share_of_all_windows']:.0f} % vseh
60-dnevnih oken v tem vzorcu vsebuje padec vsaj 13 %</b>, zato je »po vsakem izstopu je sledil
padec« skoraj prazna trditev — mediana po sprožitvi je
{AU['dd_base_rate']['median_after_blowoff']:.1f} % proti
{AU['dd_base_rate']['median_all_windows']:.1f} % na povprečnem oknu. Od
{AU['multiple_testing_blowoff']['n_tests']} opravljenih testov je značilen
{AU['multiple_testing_blowoff']['n_significant']}, pri
{AU['multiple_testing_blowoff']['n_tests']} testih pa je verjetnost vsaj enega značilnega po
naključju <b>{AU['multiple_testing_blowoff']['p_at_least_one_by_chance']*100:.0f} %</b>.
Tudi ablacija ne pomaga: izklop premakne Sortino za
{AU['blowoff_ablation']['d_sortino']:+.2f} (razpon
[{AU['blowoff_ablation']['ci_d_sortino'][0]:+.2f}, {AU['blowoff_ablation']['ci_d_sortino'][1]:+.2f}])
in MaxDD za {AU['blowoff_ablation']['d_maxdd']:+.1f} o. t. (razpon
[{AU['blowoff_ablation']['ci_d_maxdd'][0]:+.1f}, {AU['blowoff_ablation']['ci_d_maxdd'][1]:+.1f}])
— <b>oba razpona zajemata ničlo</b>. Pri {len(EX['blowoff_exits'])} sprožitvah v sedmih letih
tega ni mogoče razrešiti. <b>Pustiti pri miru in ne uporabljati kot argument v nobeno
smer.</b></p>

<p><b>Vol-shock se ne sproži.</b> Od {base['trades']} izstopov strategije jih je povzročil
{base['exit_reasons']['vol_shock']}. Obstaja {EX['vol_shock_actionable']['n_window']} dni, ko
bi lahko deloval — v poziciji smo, cena je pod trackline, redni izstop še ni nastopil — in na
{EX['vol_shock_actionable']['n_fire_in_window']} od njih se sproži, ker ga izstop na
<code>below_tl</code> vedno prehiti; izklop spremeni Sortino za
{abl['brez_vol_shock']['d_sortino']:+.3f} in MaxDD za {abl['brez_vol_shock']['d_maxdd']:+.1f}
o. t. Ko prag znižamo toliko, da <b>res</b> začne izstopati, se poslabša vse: pri množitelju
1,0 Sortino pade z {EX['vol_shock_threshold_sweep'][6]['sortino']:.3f} na
{EX['vol_shock_threshold_sweep'][1]['sortino']:.3f} in padec z
{EX['vol_shock_threshold_sweep'][6]['maxdd']:.1f} % na
{EX['vol_shock_threshold_sweep'][1]['maxdd']:.1f} %, pri 0,8 pa na
{EX['vol_shock_threshold_sweep'][0]['sortino']:.3f} in
{EX['vol_shock_threshold_sweep'][0]['maxdd']:.1f} %. To je edina izstopna ugotovitev, ki ne
sloni na statistični značilnosti, ampak na mehaniki, in je zato edina trdna.
<b>Odstraniti.</b></p>""")

    B = AF["cases"]["izhodišče"]
    IDX = AF["index"]
    BENCH = AF["benchmark"]["equity"]

    A("<h2>Kaj predlagam odstraniti — in kaj to naredi</h2>")
    A(f"""<p>Vsak pogoj sem izklopil posebej in izmeril vse štiri številke, ne le Sortina.
Izhodišče: Sortino <b>{B['sortino']:.3f}</b>, Sharpe <b>{B['sharpe']:.3f}</b>, letni donos
<b>{B['cagr']:.1f} %</b>, največji padec <b>{B['maxdd']:.1f} %</b>, končni večkratnik
<b>{B['final']:.2f}×</b> pri {B['trades']} poslih.</p>
<p class="cap">Sharpe je dodan namenoma: Sortino kaznuje samo padce, zato lahko pravilo tam
izgleda dobro, medtem ko stane navaden donos. Končni večkratnik je zraven, ker se v odstotkih
letnega donosa slabo vidi, koliko denarja je to v sedmih letih.</p>""")

    A('<div class="fig"><table><tr><th>izklopimo</th><th>Sortino</th><th>Sharpe</th>'
      '<th>letni donos</th><th>največji padec</th><th>končni<br>večkratnik</th>'
      '<th>poslov</th><th>sodba</th></tr>')
    ROWS = [
      ("brez vol-shocka", "vol-shock", "odstraniti", "var(--crit)"),
      ("brez dist_entry_ok", "dist_entry_ok", "odstraniti", "var(--crit)"),
      ("brez above_ma_med", "above_ma_med (50 MA)", "odstraniti", "var(--crit)"),
      ("brez blow-offa", "blow-off", "nedokazan", "var(--warn)"),
      ("brez above_tl", "above_tl (trackline)", "obdržati", "var(--good)"),
      ("brez track_rising", "track_rising_window", "obdržati", "var(--good)"),
      ("brez regime_ok", "regime_ok (200 MA)", "obdržati", "var(--good)"),
    ]
    for key, nice, verdict, col in ROWS:
        r = B_ = AF["cases"][key]
        ident = r.get("identical")
        st = ' style="color:var(--muted)"' if ident else ""
        A(f'<tr><td><code>{nice}</code></td>'
          f'<td class="n"{st}>{r["sortino"]:.3f}</td><td class="n"{st}>{r["sharpe"]:.3f}</td>'
          f'<td class="n"{st}>{r["cagr"]:.1f} %</td><td class="n"{st}>{r["maxdd"]:.1f} %</td>'
          f'<td class="n"{st}>{r["final"]:.2f}×</td><td class="n"{st}>{r["trades"]}</td>'
          f'<td style="font-size:12.5px;color:{col};font-weight:600">{verdict}'
          f'{" · nič se ne spremeni" if ident else ""}</td></tr>')
    A(f'<tr style="border-top:2px solid var(--axis)"><td style="color:var(--muted)">'
      f'kupi in drži</td><td class="n" style="color:var(--muted)">'
      f'{AF["benchmark"]["sortino"]:.3f}</td>'
      f'<td class="n" style="color:var(--muted)">{AF["benchmark"]["sharpe"]:.3f}</td>'
      f'<td class="n" style="color:var(--muted)">{AF["benchmark"]["cagr"]:.1f} %</td>'
      f'<td class="n" style="color:var(--muted)">{AF["benchmark"]["maxdd"]:.1f} %</td>'
      f'<td class="n" style="color:var(--muted)">{BENCH[-1]:.2f}×</td>'
      f'<td class="n" style="color:var(--muted)">1</td><td></td></tr>')
    A("</table></div>")

    # ── group 1: the three that change nothing ────────────────────────────
    A("<h3 style='font-size:14.5px;margin:26px 0 8px'>Trije, ki jih odstranim: krivulja se "
      "ne premakne niti za piko</h3>")
    A(f"""<p class="cap">Modra črtkana črta je strategija <b>brez</b> vseh treh pravil, rdeča
z njimi. Popolnoma se prekrivata — največja razlika je <b>0,000000</b> na vseh
{AF['n']} dneh. Sivo je kupi-in-drži za merilo.</p>""")
    A('<div class="fig">'
      + mini_equity(B["equity"], AF["cases"]["brez obojega"]["equity"], BENCH, IDX,
                    w=860, h=250)
      + "</div>")
    A(f"""<div class="fig"><table>
<tr><th>pravilo</th><th style="width:46%">zakaj se nič ne spremeni</th>
<th>kako trdno je to</th></tr>
<tr><td><code>vol-shock</code></td>
    <td style="font-size:12.5px">V kodi zahteva <code>below_tl</code>, izstop na
    <code>below_tl</code> pa ga <b>vedno prehiti</b>. Od {B['trades']} izstopov jih je
    povzročil {base['exit_reasons']['vol_shock']}. Obstaja 41 dni, ko bi lahko deloval — na
    nobenem se ne sproži.</td>
    <td style="font-size:12.5px;color:var(--good)"><b>Strukturno.</b> Ne more se sprožiti prvi,
    ne glede na podatke.</td></tr>
<tr><td><code>dist_entry_ok</code></td>
    <td style="font-size:12.5px">Pri <code>min_dist_entry_pct = 0</code> je matematično isti
    pogoj kot <code>above_tl</code>, ki je v <code>bull_condition</code> že prisoten.
    {ES['dist_entry_disagreements']} dni razlike od {ES['n_days']}.</td>
    <td style="font-size:12.5px;color:var(--good)"><b>Matematično.</b> Ni odvisno od
    vzorca.</td></tr>
<tr><td><code>above_ma_med</code></td>
    <td style="font-size:12.5px">Blokira 65 dni, ki jih drugi filtri spustijo — a nobeden od
    teh 65 dni se nikoli ni prelevil v posel, ker ga prej pobereta zahteva po treh zaporednih
    dneh in 15-dnevni premor.</td>
    <td style="font-size:12.5px;color:var(--warn)"><b>Le empirično.</b> Na teh podatkih je
    učinek nič, strukturnega jamstva pa ni. Na drugem obdobju bi lahko zaleglo.</td></tr>
</table></div>""")
    A("""<p class="cap"><b>To razliko je vredno povedati na glas.</b> Prva dva izbrisa sta
varna po svoji naravi. Tretji je varen po meritvi. Če hočemo biti zelo previdni, se
<code>above_ma_med</code> pusti v kodi, a odstrani s seznama nastavljivih številk — učinek
na rezultat je tako in tako nič.</p>""")

    # ── group 2: the ones with a real effect ──────────────────────────────
    A("<h3 style='font-size:14.5px;margin:26px 0 8px'>Štirje, ki jih ne odstranim — in kaj bi "
      "izgubili ali pridobili</h3>")
    A("""<p class="cap">Pri nobenem od teh štirih <b>noben razpon ne izloči ničle</b>, torej
nobene razlike nismo dokazali. Točkovne ocene pa vseeno povejo, kaj bi bilo na kocki.
Rdeče je z pravilom (današnja strategija), modro črtkano brez njega.</p>""")
    A('<div class="grid">')
    CARDS = [
      ("brez blow-offa", "blow-off",
       "Daleč največji vpliv med vsemi. Brez njega bi bilo v sedmih letih "
       "<b>{final:.1f}×</b> namesto <b>{bfinal:.1f}×</b> — skoraj dvakrat toliko — za ceno "
       "{ddabs:.1f} o. t. globljega padca. Če je to dober posel, je odvisno od tega, kaj "
       "prodajamo. Nič od tega ni statistično dokazano.", "var(--warn)"),
      ("brez above_tl", "above_tl",
       "Presenetljivo: <b>brez jedra strategije je backtest boljši</b> "
       "({final:.1f}× proti {bfinal:.1f}×, Sortino {sortino:.2f} proti {bsortino:.2f}). "
       "Razpon Sortina [{cs0:+.2f}, {cs1:+.2f}] se ničle le dotakne. To ne pomeni odstraniti — "
       "pomeni, da trackline kot vstopni sprožilec ni dokazan in je to največja odprta "
       "neznanka.", "var(--good)"),
      ("brez track_rising", "track_rising_window",
       "Edini filter, pri katerem izklop <b>opazno poglobi padec</b>: "
       "{maxdd:.1f} % proti {bmaxdd:.1f} %, torej {ddabs:.1f} o. t. Donos bi bil rahlo višji. "
       "To je pravilo, ki dejansko kupuje mirnejšo vožnjo.", "var(--good)"),
      ("brez regime_ok", "regime_ok",
       "Edini, pri katerem je izklop <b>slabši na vsem</b>: Sortino "
       "{sortino:.2f} proti {bsortino:.2f}, donos {cagr:.1f} % proti {bcagr:.1f} %. "
       "Pozor na podrobnost, ki spremeni njegovo zgodbo: padca <b>ne izboljša</b> "
       "({maxdd:.1f} % proti {bmaxdd:.1f} %, razlika 0,0). Je filter donosa, ne varovalka "
       "pred padcem.", "var(--good)"),
    ]
    for key, nice, txt, col in CARDS:
        r = AF["cases"][key]
        body = txt.format(final=r["final"], bfinal=B["final"], sortino=r["sortino"],
                          bsortino=B["sortino"], cagr=r["cagr"], bcagr=B["cagr"],
                          maxdd=r["maxdd"], bmaxdd=B["maxdd"],
                          ddabs=abs(r["d_maxdd"]),
                          cs0=r["ci_sortino"][0], cs1=r["ci_sortino"][1])
        A(f'<div class="card"><h3><code>{nice}</code></h3>'
          f'<p class="d">rdeče: z pravilom · modro črtkano: brez njega</p>'
          f'{mini_equity(B["equity"], r["equity"], BENCH, IDX)}'
          f'<p class="par">ΔSortino {r["d_sortino"]:+.3f} [{r["ci_sortino"][0]:+.2f}, '
          f'{r["ci_sortino"][1]:+.2f}] · ΔSharpe {r["d_sharpe"]:+.3f} · '
          f'Δdonos {r["d_cagr"]:+.1f} o. t. · Δpadec {r["d_maxdd"]:+.1f} o. t.</p>'
          f'<p class="read">{body}</p></div>')
    A("</div>")

    A(f"""<div class="note" style="border-left-color:var(--good)">
<p><b>Skupaj: odstranim tri od sedmih.</b> Nastavljivih številk je s tem
{ES['n_days'] and 14} &rarr; <b>10</b> (<code>vol_shock_mul</code>,
<code>vol_lookback</code>, <code>min_dist_entry_pct</code>, <code>ma_med_len</code>).
Rezultat se ne spremeni za nobeno decimalko — in prav to je namen. <b>Ne izboljšujemo
strategije, zmanjšujemo število načinov, kako lahko zavedemo sami sebe.</b> Manj gumbov
neposredno zniža verjetnost prevelike prilagojenosti (PBO) in število poskusov v deflated
Sharpu.</p>
<p style="margin-top:9px">Ostalih štirih <b>ne odstranim</b>, ker pri nobenem noben razpon ne
izloči ničle. Za vsakega je razlog drugačen: blow-off je nedokazan v obe smeri,
<code>above_tl</code> je jedro brez dokaza, <code>track_rising_window</code> je edini, ki
dokazljivo kupuje plitvejši padec, <code>regime_ok</code> pa je edini, brez katerega je
slabše na vsem.</p></div>""")

    A("<h2>Povzetek</h2>")
    A('<div class="fig"><table><tr><th>pogoj</th><th>kaj dela</th><th>sodba</th></tr>')
    SUM = [
      ("regime_ok", "blokira 35 dni s povprečnim 20-dnevnim donosom −10 %", "obdržati", "var(--good)"),
      ("track_rising_window", "blokira 235 dni brez donosa; značilen na 20 dni", "obdržati", "var(--good)"),
      ("above_ma_med", "značilen na 5 dni; inkrementalno blokira le 65 dni", "obdržati, gumb zakleniti", "var(--good)"),
      ("above_tl", "jedro logike; noben razpon ne izloči ničle", "obdržati, a nedokazan", "var(--warn)"),
      ("dist_entry_ok", f"matematični dvojnik <code>above_tl</code> — {ES['dist_entry_disagreements']} dni razlike od {ES['n_days']}", "odstraniti", "var(--crit)"),
      ("below_tl", "pravi predznak, razlika ni dokazana", "obdržati — glavni izstop", "var(--warn)"),
      ("blowoff", f"{base['exit_reasons']['blowoff']} od {base['trades']} poslov; oba razpona "
                  f"(Sortino in MaxDD) zajemata ničlo", "nedokazan v obe smeri — pustiti pri miru",
              "var(--warn)"),
      ("vol_shock", f"{base['exit_reasons']['vol_shock']} sprožitev od {base['trades']} izstopov; smer obrnjena "
                    f"({vs['m']['donos']['60']['diff']:+.1f} o. t. na 60 dni)", "odstraniti", "var(--crit)"),
    ]
    for k, does, verdict, col in SUM:
        A(f'<tr><td><code>{k}</code></td><td style="font-size:12.5px">{does}</td>'
          f'<td style="font-size:12.5px;color:{col};font-weight:600">{verdict}</td></tr>')
    A("</table></div>")

    # ── the point of the document: what is still open, and how to close it ──
    A("<h2>Kaj ostaja odprto</h2>")
    A("""<p>Tri pravila niso ovržena, le premalo natančno izmerjena. Za vsako je spodaj test,
ki bi ga zaprl, po prioriteti.</p>""")
    A('<div class="fig"><table><tr><th style="width:16%">pogoj</th>'
      '<th style="width:30%">kaj ni jasno</th><th>test</th></tr>')
    OPEN = [
      ("below_tl", "Nosi večino izstopne strani (13 od 21 poslov), a razlika ni dokazana.",
       "Postaviti mu tekmece — ATR trailing stop, prebitje 50 MA, časovni izstop — in vse "
       "meriti z istim event studyjem, a na <b>nadaljnjem MaxDD</b> namesto na donosu. "
       "Izstop naj varuje pred padcem, ne pred izgubljenim donosom."),
      ("above_tl", "Jedro strategije, a nad povprečnim dnevom doda le +1,6 o. t. in noben "
       "razpon ne izloči ničle.",
       "Ločiti vstopni in izstopni mrtvi pas — danes sta oba 3 % zaradi simetrije, ne "
       "meritve. Prelet vstopnega 1–6 % neodvisno od izstopnega. Nato primerjava z Donchian "
       "prebojem (<code>use_donchian</code> je že v kodi)."),
      ("above_ma_med", "Značilen sam zase, a inkrementalno blokira le 65 dni. Sum prekrivanja "
       "s <code>track_rising_window</code>.",
       "Izmeriti dneve, na katerih se filtra <b>razhajata</b>, in nadaljnji donos tam. Če je "
       "odvečen, pade še en parameter."),
    ]
    for k, unclear, test in OPEN:
        A(f'<tr><td><code>{k}</code></td><td style="font-size:12.5px">{unclear}</td>'
          f'<td style="font-size:12.5px">{test}</td></tr>')
    A("</table></div>")
    A(f"""<p class="cap">Vsi trije so omejeni z istim: {base['trades']} poslov. Preverba na
4-urnih barih pokaže, da drobnejša ura tega <b>ne odpravi</b> — ob pomnoženih dolžinah
strategija naredi enako število poslov. Uporabna je za drugo vprašanje: ali je rezultat
odvisen od tega, kdaj po dogovoru konča dan.</p>""")

    A(f"""<footer>
Vir: Binance, zamrznjen posnetek <code>testing/data/sources/BTC_binance.parquet</code>.
Okno {ES['from']} → {ES['to']}, {ES['n_days']} dni po zavrženem ogrevanju.
fee + slippage {AB['fee_per_side_pct']} % na stran.
Razponi: krožni bločni bootstrap, {ES['nboot']} vzorcev, blok {ES['block_rule']}, seme {ES['seed']}.
Ponovljivo z <code>testing/scripts/event_study.py</code> in <code>ablation.py</code>.
</footer></main></body></html>""")

    OUT.write_text("".join(P), encoding="utf-8")
    print(f"-> {OUT}  ({OUT.stat().st_size/1024:.0f} kB)")


if __name__ == "__main__":
    main()
