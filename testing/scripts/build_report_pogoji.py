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
   "Na 60 dni +13 o. t. Varovalka pred dolgimi padci, ne izbirnik dobrih tednov.", "ok"),

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
   "enodnevni sunek vrže iz pozicije. Po odstranitvi blow-offa je to <b>edini preostali "
   "izstop</b> in nosi celotno izstopno stran strategije.",
   "track_period = 75 dni · track_buf_pct = 3 % · exit_grace_bars = 3 dni",
   "Pravi predznak, a razlika je premajhna glede na razpršenost.", "?"),

 "blowoff": (
   "Cena je <b>več kot 25 % nad</b> trackline <b>in</b> hkrati je RSI nad 80. RSI je "
   "kazalnik pregretosti od 0 do 100; nad 80 pomeni zelo hitro rast v kratkem času.<br><br>"
   "Naj bi ujel evforični skok tik pred zlomom. Izstop je <b>takojšen</b>, brez treh dni "
   "čakanja.<br><br><b>Ta graf ga postavlja proti vsem dnevom, kar je napačna primerjava</b> "
   "— izstopno pravilo se posvetuje samo, ko smo v poziciji in je cena že visoko. Pravilna "
   "primerjava je v razdelku spodaj in daje drugačen odgovor.",
   "blowoff_dist_pct = 25 % · RSI prag = 80 · rsi_len = 14 dni",
   "Ta graf je zavajajoč — glej popravljeno analizo spodaj.", "?"),

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


def card(r):
    rows = [(f"{h} dni", v["diff"], v["ci"], v["sig"])
            for h in ES["horizons"] if (v := r["m"]["donos"][str(h)])]
    what, params, txt, bk = READ[r["key"]]
    lab, col = BADGE[bk]
    gate = "" if r["gate"] == "all" else " · primerjano znotraj dni pod trackline"
    return (f'<div class="card"><h3>{r["key"]}'
            f'<span class="badge" style="background:{col}">{lab}</span></h3>'
            f'<p class="d">{r["label"]} · velja na {r["n_fire"]} dneh '
            f'({r["share"]} % vzorca){gate}</p>'
            f'<p class="long">{what}</p>'
            f'<p class="par">privzeto: {params}</p>'
            f'{ci_chart(rows)}<p class="read"><b>Sodba:</b> {txt}</p></div>')


def main():
    b = ES["blowoff_mechanism"]
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

    A("<h2>Vstopni pogoji — vseh 12 meritev kaže v pravo smer</h2>")
    A('<div class="grid">' + "".join(card(c) for c in entry) + "</div>")

    A("<h2>Izstopni pogoji</h2>")
    A('<div class="grid">' + "".join(card(c) for c in exit_) + "</div>")

    A("<h2>Blow-off: prva analiza je bila napačno zastavljena</h2>")
    A("""<p>Zgornji graf primerja dneve, ko se blow-off sproži, z <b>vsemi ostalimi dnevi v
vzorcu</b>. Videti je bilo, da se sproža ob dobrih trenutkih. <b>Ta primerjava je napačna</b>
— in to je ista napaka, ki je bila pri vol-shocku že popravljena.</p>
<p>Izstopno pravilo se nikoli ne posvetuje na povprečnem dnevu. Posvetuje se <b>samo takrat,
ko smo v poziciji in je cena že daleč nad trackline</b>. Primerjati ga je torej treba z
<b>drugimi enako raztegnjenimi dnevi</b>, ne s celim vzorcem, ki je večinoma nekaj
popolnoma drugega.</p>""")
    bx = EX["blowoff_vs_extended"]
    A(f"""<p class="cap">Pravi primerjalni vzorec: <b>{bx['n_extended']} dni</b>, ko je bila
cena več kot 25 % nad trackline. Od teh se jih <b>{bx['n_fire']}</b> sproži (RSI &gt; 80).
Vprašanje je ozko: <i>ali RSI nad 80 doda karkoli k temu, da je cena že raztegnjena?</i></p>""")
    A('<div class="grid">')
    for lab, title, hint in (
        ("donos", "Nadaljnji donos", "za izstopno pravilo je pravi predznak <b>negativen</b>"),
        ("maxdd", "Najgloblji vmesni padec",
         "bolj negativno = po sprožitvi sledi hujši padec, kar je <b>razlog za izstop</b>")):
        rows = [(f"{h} dni", v["diff"], v["ci"], v["sig"])
                for h in ES["horizons"]
                if (v := bx["m"][lab][str(h)]) and not v.get("too_few")]
        A(f'<div class="card"><h3>{title}</h3><p class="d">{hint}</p>{ci_chart(rows)}</div>')
    A("</div>")
    d20 = bx["m"]["donos"]["20"]
    dd5 = bx["m"]["maxdd"]["5"]
    A(f"""<div class="note" style="border-left-color:var(--warn)">
<p><b>Slika se obrne.</b> Proti pravemu primerjalnemu vzorcu blow-off <b>ni</b> narobe
obrnjen:</p>
<ul style="margin:8px 0 0"><li>na <b>20 dni</b> mu sledi donos <b>{d20['diff']:+.1f} o. t.</b>
slabši kot drugim raztegnjenim dnevom ({d20['mean_true']:+.1f} % proti
{d20['mean_false']:+.1f} %) — to je prava smer za izstopno pravilo;</li>
<li>na <b>5 dni</b> mu sledi <b>značilno globlji</b> vmesni padec
({dd5['diff']:+.2f} o. t., razpon [{dd5['ci'][0]:+.2f}, {dd5['ci'][1]:+.2f}]).</li></ul>
</div>""")

    fired = EX["blowoff_exits"]
    fs = EX.get("blowoff_exits_summary", {})
    A("<h3 style='font-size:14.5px;margin:24px 0 8px'>Kaj se je zgodilo po vsakem dejanskem "
      "izstopu</h3>")
    A(f'<p class="cap">Vseh {len(fired)} izstopov, ki jih je blow-off res povzročil. Osem '
      f'opazovanj samo zase ničesar ne dokaže — pokažejo pa, ali agregat govori resnico.</p>')
    A('<div class="fig"><table><tr><th>datum</th><th>% nad trackline</th><th>RSI</th>'
      '<th>cena čez 20 dni</th><th>cena čez 60 dni</th>'
      '<th>najgloblji padec v 60 dneh</th></tr>')
    for r in fired:
        c20 = "var(--crit)" if (r["ret20"] or 0) < 0 else "var(--ink2)"
        c60 = "var(--crit)" if (r["ret60"] or 0) < 0 else "var(--ink2)"
        A(f'<tr><td>{r["date"]}</td><td>{r["dist_pct"]:.0f} %</td><td>{r["rsi"]:.0f}</td>'
          f'<td style="color:{c20}">{r["ret20"]:+.1f} %</td>'
          f'<td style="color:{c60}">{r["ret60"]:+.1f} %</td>'
          f'<td style="color:var(--crit)">{r["dd60"]:+.1f} %</td></tr>')
    A("</table></div>")
    A(f"""<div class="note" style="border-left-color:var(--good)">
<p><b>Blow-off ni detektor vrhov. Je detektor turbulence — in to nam ustreza.</b></p>
<p style="margin-top:8px">Cena je v 60 dneh padla po <b>{fs.get('n_price_fell_60d','?')} od
{fs.get('n','?')}</b> izstopov, kar pomeni, da pravilo <i>ne</i> zna napovedati vrha. Ampak:
po <b>vsakem</b> od {len(fired)} izstopov je v naslednjih 60 dneh sledil padec med 13 in 28 %
(mediana {fs.get('median_dd60','?')} %). Pravilo zanesljivo izstopi pred nemirom, tudi kadar
se cena na koncu pobere.</p>
<p style="margin-top:8px">Backtest to potrdi z druge strani: <b>izklop blow-offa dvigne
Sortino za {abl['brez_blowoff']['d_sortino']:+.2f}, a poglobi največji padec za
{abs(abl['brez_blowoff']['d_maxdd']):.1f} odstotne točke</b> ({base['maxdd']:.1f} % &rarr;
{abl['brez_blowoff']['maxdd']:.1f} %). Pravilo stane donos in kupi mirnejšo vožnjo — kar je
natanko posel, ki ga produkt obljublja.</p>
<p style="margin-top:8px"><b>Popravek priporočila: blow-off OBDRŽATI.</b> Prejšnja različica
te strani ga je uvrščala med odstranitve. Podlaga za to je bila napačna primerjalna
skupina.</p></div>""")

    A("<h2>Vol-shock: sodba potrjena, in močneje kot prej</h2>")
    vsw = EX["vol_shock_threshold_sweep"]
    va = EX["vol_shock_actionable"]
    A(f"""<p>Pri vol-shocku je bila primerjava prava že od začetka. Sodba se ni spremenila, je
pa zdaj podprta s treh strani.</p>
<ul class="cap"><li>Od {base['trades']} izstopov strategije jih je povzročil
<b>{base['exit_reasons']['vol_shock']}</b>.</li>
<li>Obstaja <b>{va['n_window']} dni</b>, ko bi lahko deloval — v poziciji smo, cena je pod
trackline, redni izstop še ni nastopil. Na <b>{va['n_fire_in_window']}</b> od njih se
sproži.</li>
<li>Izklop spremeni Sortino za <b>{abl['brez_vol_shock']['d_sortino']:+.3f}</b> in MaxDD za
<b>{abl['brez_vol_shock']['d_maxdd']:+.1f} o. t.</b></li></ul>
<p>Najbolj poveden je zadnji test: kaj se zgodi, če prag <b>znižamo</b> toliko, da se pravilo
sploh začne sprožati?</p>""")
    A('<div class="fig"><table><tr><th>množitelj praga</th><th>sprožitev</th>'
      '<th>izstopov</th><th>Sortino</th><th>največji padec</th></tr>')
    for r in vsw:
        if r["mul"] > 100:
            lab = "izklopljen"
        elif abs(r["mul"] - 1.5) < 1e-9:
            lab = "1,5 &larr; danes"
        else:
            lab = f'{r["mul"]:g}'.replace(".", ",")
        A(f'<tr><td>{lab}</td><td>{r["fires"]}</td><td>{r["exits"]}</td>'
          f'<td>{r["sortino"]:.3f}</td><td>{r["maxdd"]:.1f} %</td></tr>')
    A("</table></div>")
    A(f"""<div class="note"><p>Pri današnji nastavitvi se pravilo sproži
{vsw[4]['fires']}-krat, a nikoli prvo — redni izstop ga vedno prehiti, zato je rezultat
enak izklopu do tretje decimalke. Ko prag znižamo toliko, da <b>res začne izstopati</b>, se
poslabša vse: pri množitelju 1,0 Sortino pade na {vsw[1]['sortino']:.3f} in padec se poglobi
na {vsw[1]['maxdd']:.1f} %, pri 0,8 pa na {vsw[0]['sortino']:.3f} in {vsw[0]['maxdd']:.1f} %.
<b>Pravilo ni le nedejavno — kadar je prisiljeno delovati, škoduje.</b></p></div>""")

    A("<h2>Povzetek</h2>")
    A('<div class="fig"><table><tr><th>pogoj</th><th>kaj dela</th><th>sodba</th></tr>')
    SUM = [
      ("regime_ok", "blokira 35 dni s povprečnim 20-dnevnim donosom −10 %", "obdržati", "var(--good)"),
      ("track_rising_window", "blokira 235 dni brez donosa; značilen na 20 dni", "obdržati", "var(--good)"),
      ("above_ma_med", "značilen na 5 dni; inkrementalno blokira le 65 dni", "obdržati, gumb zakleniti", "var(--good)"),
      ("above_tl", "jedro logike; noben razpon ne izloči ničle", "obdržati, a nedokazan", "var(--warn)"),
      ("dist_entry_ok", f"matematični dvojnik <code>above_tl</code> — {ES['dist_entry_disagreements']} dni razlike od {ES['n_days']}", "odstraniti", "var(--crit)"),
      ("below_tl", "pravi predznak, razlika ni dokazana", "obdržati — glavni izstop", "var(--warn)"),
      ("blowoff", f"{base['exit_reasons']['blowoff']} od {base['trades']} poslov; stane "
                  f"{abl['brez_blowoff']['d_sortino']:+.2f} Sortina, prihrani "
                  f"{abs(abl['brez_blowoff']['d_maxdd']):.1f} o. t. padca", "obdržati", "var(--good)"),
      ("vol_shock", f"{base['exit_reasons']['vol_shock']} sprožitev od {base['trades']} izstopov; smer obrnjena "
                    f"({vs['m']['donos']['60']['diff']:+.1f} o. t. na 60 dni)", "odstraniti", "var(--crit)"),
    ]
    for k, does, verdict, col in SUM:
        A(f'<tr><td><code>{k}</code></td><td style="font-size:12.5px">{does}</td>'
          f'<td style="font-size:12.5px;color:{col};font-weight:600">{verdict}</td></tr>')
    A("</table></div>")

    # ── the point of the document: what is still open, and how to close it ──
    A("<h2>Kaj ni dokazano in kako to preveriti</h2>")
    A("""<p>Tri pravila ostajajo <b>nedokazana</b> — ne ovržena, samo neizmerjena z dovolj
natančnosti. Za vsako je spodaj konkreten test, ki bi ga zaprl.</p>""")
    A('<div class="fig"><table>'
      '<tr><th style="width:14%">pogoj</th><th style="width:24%">kaj natanko ni jasno</th>'
      '<th style="width:38%">test</th><th>kaj bi to rešilo</th></tr>')
    OPEN = [
      ("above_tl",
       "Pozitiven predznak na vseh horizontih, a noben razpon ne izloči ničle. Znotraj "
       "bikovskega režima pri 60 dneh celo obrne predznak.",
       "<b>1.</b> Ločiti vstopni in izstopni mrtvi pas. Danes sta oba 3 %, kar je bila "
       "odločitev za simetrijo, ne meritev. Prelet vstopnega 1–6 % neodvisno od izstopnega, "
       "z event studyjem na vsaki kombinaciji.<br>"
       "<b>2.</b> Zamenjati z Donchian prebojem (<code>use_donchian</code> je že v kodi, "
       "privzeto izklopljen) in ju primerjati na isti podlagi — ne po backtestu, ampak po "
       "nadaljnjem donosu na dneh sprožitve.",
       "Ali je trackline sploh pravi sprožilec vstopa, ali le pravi sprožilec izstopa. To je "
       "trenutno največja neznanka v strategiji, ker je <code>above_tl</code> njeno jedro."),
      ("below_tl",
       "Pravi predznak (−4,6 o. t. na 60 dni), a razpršenost je prevelika. Hkrati je to "
       "edini preostali izstop, torej nosi celotno izstopno stran.",
       "<b>1.</b> Postaviti mu tekmece in vse meriti z istim event studyjem: izstop na "
       "ATR trailing stopu, izstop ob prebitju 50 MA, časovni izstop po N dneh.<br>"
       "<b>2.</b> Meriti ne donosa, ampak <b>nadaljnji MaxDD</b> — izstop naj bi varoval "
       "pred padcem, ne pred izgubljenim donosom. Ta stolpec je že izračunan v "
       "<code>event_study.py</code>, a ga ta stran ne prikazuje.",
       "Ali je trackline najboljši razpoložljivi izstop ali le prvi, ki smo ga napisali. "
       "Ker po odstranitvi blow-offa ostane sam, je to zdaj kritično."),
      ("above_ma_med",
       "Značilen sam zase, a inkrementalno blokira le 65 dni in razlika tam ni dokazana. "
       "Sum: prekriva se s <code>track_rising_window</code>.",
       "<b>1.</b> Izmeriti prekrivanje: na koliko dni sta oba resnična hkrati, in kakšen je "
       "nadaljnji donos na dneh, kjer se <b>razhajata</b>.<br>"
       "<b>2.</b> Izklopiti ga in pognati poln protokol — vključno s PBO, ker odstranitev "
       "filtra spremeni število poskusov.",
       "Ali potrebujemo dva trend filtra ali enega. Če je odvečen, pade še en parameter."),
    ]
    for k, unclear, test, solves in OPEN:
        A(f'<tr><td><code>{k}</code></td><td style="font-size:12.5px">{unclear}</td>'
          f'<td style="font-size:12.5px">{test}</td>'
          f'<td style="font-size:12.5px">{solves}</td></tr>')
    A("</table></div>")

    A(f"""<p class="cap"><b>Kako vse tri izvesti hkrati in ceneje.</b> Vsi trije testi so
omejeni z istim: {base['trades']} poslov in {ES['n_days']} dni. Iste rutine pognane na
<b>4-urnih barih istega BTC-ja v istem obdobju</b> dajo približno šestkrat več opazovanj.
Pogoj je, da se vsi lookbacki pomnožijo s 6 — sicer ne testiramo drobnejše ure, ampak drugo
strategijo. To je edini način, da vzorec zraste brez novih trgov in brez čakanja.</p>""")

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
