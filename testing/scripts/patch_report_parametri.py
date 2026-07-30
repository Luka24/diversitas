"""Insert the "what to do about the sharp peaks" section into the parameter report.

The parameter report diagnosed the problem — four knobs on a sharp peak, three of
them peaking exactly on the shipped default — and then stopped. This adds the
measured answer from ensemble.py, so the page ends with an instruction rather
than a worry.

Idempotent: re-running replaces the section instead of stacking copies.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "testing" / "porocilo_parametri_BTC.html"
EN = json.loads((ROOT / "testing" / "data" / "ensemble_BTC.json").read_text(encoding="utf-8"))

MARK_A = "<!-- KONICE:START -->"
MARK_B = "<!-- KONICE:END -->"
ANCHOR = "  <h2>Povzetek</h2>"

NAMES = {"ma_long_len": "dolzina rezimske MA", "confirm_bars": "barov potrditve pred vstopom",
         "reentry_hold": "barov premora pred ponovnim vstopom",
         "exit_grace_bars": "barov potrpezljivosti pred izstopom"}


def hist_chart(vals, point, ens, w=860, h=210) -> str:
    import math
    lo, hi = min(vals + [ens, point]), max(vals + [ens, point])
    pad = (hi - lo) * 0.08 or 0.1
    lo, hi = lo - pad, hi + pad
    nb = 22
    edges = [lo + (hi - lo) * i / nb for i in range(nb + 1)]
    counts = [0] * nb
    for v in vals:
        i = min(nb - 1, max(0, int((v - lo) / (hi - lo) * nb)))
        counts[i] += 1
    cmax = max(counts) or 1
    pl, pr, pt, pb = 34, 16, 34, 46

    def X(v): return pl + (v - lo) / (hi - lo) * (w - pl - pr)
    def Y(c): return h - pb - c / cmax * (h - pt - pb)

    p = [f'<svg viewBox="0 0 {w} {h}" role="img">']
    p.append(f'<line x1="{pl}" y1="{h-pb}" x2="{w-pr}" y2="{h-pb}" stroke="var(--axis)"/>')
    bw = (w - pl - pr) / nb
    for i, c in enumerate(counts):
        if not c:
            continue
        x0 = pl + i * bw
        p.append(f'<rect x="{x0+1:.1f}" y="{Y(c):.1f}" width="{bw-2:.1f}" '
                 f'height="{h-pb-Y(c):.1f}" fill="var(--s1)" opacity=".45" rx="2"/>')
    for v in (lo + (hi - lo) * f for f in (0, .25, .5, .75, 1)):
        p.append(f'<text x="{X(v):.1f}" y="{h-pb+16:.0f}" text-anchor="middle">{v:.2f}</text>')
    for val, col, lab, dy in ((ens, "var(--s2)", "ansambel 81 clanov", 0),
                              (point, "var(--crit)", "privzetki - ena tocka", -15)):
        p.append(f'<line x1="{X(val):.1f}" y1="{pt-6}" x2="{X(val):.1f}" y2="{h-pb}" '
                 f'stroke="{col}" stroke-width="2"/>')
        p.append(f'<text x="{X(val):.1f}" y="{pt-10+dy}" text-anchor="middle" '
                 f'style="fill:{col};font-weight:700">{lab} · {val:.2f}</text>')
    p.append(f'<text x="{pl}" y="{h-8}">Sortino vsakega od 81 sosedov · '
             f'vodoravno = kako dobra je posamezna nastavitev</text>')
    return "".join(p) + "</svg>"


def build() -> str:
    prem, ci = EN["peak_premium"], EN["ci_peak_premium"]
    pt, en = EN["point"], EN["ensemble"]
    ms = EN["member_sortino"]
    pctl = EN["default_percentile_among_members"]
    rank = sum(1 for v in ms["all"] if v < pt["sortino"])
    main = EN["main_effects"]
    inter = EN["interactions"]
    top_i = max(inter, key=inter.get)
    ratio = inter[top_i] / max(main.values()) * 100
    rob = EN["robust_values"]

    rows = ""
    for k, r in rob.items():
        note = ("<b>privzeta vrednost sploh ni vrh</b> — vrh je pri "
                f"{r['peak']}, sredina ravnine pri {r['robust']}"
                if r["peak"] != r["default"] else
                (f"vrh in privzetek sovpadata; sredina ravnine je {r['robust']}"
                 if r["robust"] != r["default"] else "vrh, privzetek in sredina ravnine sovpadajo"))
        rows += (f'<tr><td class="l"><code>{k}</code><br>'
                 f'<span style="font-size:11.5px;color:var(--muted)">{NAMES[k]}</span></td>'
                 f'<td>{r["default"]}</td><td>{r["peak"]}</td><td>{r["robust"]}</td>'
                 f'<td style="color:var(--crit)">{r["worst_neighbour_drop"]:+.3f}</td>'
                 f'<td class="l" style="font-size:12.5px">{note}</td></tr>')

    irows = "".join(
        f'<tr><td class="l"><code>{k.replace(" x ", "</code> × <code>")}</code></td>'
        f'<td>{v:.3f}</td></tr>' for k, v in sorted(inter.items(), key=lambda x: -x[1]))
    mrows = "".join(
        f'<tr><td class="l"><code>{k}</code></td><td>{v:.3f}</td></tr>'
        for k, v in sorted(main.items(), key=lambda x: -x[1]))

    return f"""{MARK_A}
  <h2>Kaj narediti z ostrimi konicami — izmerjeno</h2>

  <p>Zgornji zemljevid pove, da so stirje parametri na ostri konici in trije od njih
  natanko na privzeti vrednosti. To je diagnoza, ne recept. Tu je meritev, koliko to
  dejansko stane, in kaj z njo narediti.</p>

  <p><b>Poskus.</b> Vzeli smo stiri konicaste parametre in vsakega pognali pri treh
  sosednjih vrednostih — <code>ma_long_len</code> 150/200/250, <code>confirm_bars</code>
  2/3/4, <code>reentry_hold</code> 10/15/20, <code>exit_grace_bars</code> 2/3/4. To je
  {EN['members']} kombinacij. Vsako smo pognali posebej in nato <b>povprecili pozicijo</b>,
  ne rezultata. Meritev je na oknu {EN['window'][0]} do {EN['window'][1]}
  ({EN['n_days']} dni), na poenostavljeni strategiji (blow-off in vol-shock izklopljena),
  z 0,30 % na stran.</p>

  <div class="fig">{hist_chart(ms['all'], pt['sortino'], en['sortino'])}</div>

  <div class="fig" style="border-left:3px solid var(--crit)">
  <p style="margin:0 0 10px"><b>Rezultat, ki je pomembnejsi od vsega drugega na tej
  strani.</b></p>
  <table>
   <tr><th class="l">merilo</th><th>vrednost</th><th class="l">branje</th></tr>
   <tr><td class="l">privzetki, ena tocka</td><td>{pt['sortino']:.3f}</td>
       <td class="l">kar kaze backtest danes</td></tr>
   <tr><td class="l">ansambel {EN['members']} sosedov</td><td>{en['sortino']:.3f}</td>
       <td class="l">kar ostane, ko nehamo izbirati stevilko</td></tr>
   <tr><td class="l"><b>premija konice</b></td>
       <td><b>{prem:+.3f}</b></td>
       <td class="l">95 % razpon [{ci[0]:+.3f}, {ci[1]:+.3f}] —
       <b style="color:var(--crit)">ne zajema nicle</b></td></tr>
   <tr><td class="l">rang privzetkov med sosedi</td>
       <td><b>{rank}. od {EN['members']}</b></td>
       <td class="l">{pctl:.0f}. percentil</td></tr>
  </table>
  <p style="margin:12px 0 0"><b>Kaj to pomeni.</b> Nastavitev, izbrana brez gledanja teh
  podatkov, bi v povprecju pristala na sredini svoje soseske — priblizno 41. od
  {EN['members']}. Privzetki so <b>{rank}. od {EN['members']}</b>. Razlika
  {prem:+.3f} Sortina je statisticno znacilna. To ni sum in ni domneva:
  <b>privzete vrednosti so bile nastavljene na to zgodovino.</b></p>
  <p style="margin:10px 0 0">Prakticna posledica: <b>{en['sortino']:.2f} je stevilka, ki jo
  je posteno pricakovati naprej, ne {pt['sortino']:.2f}.</b> Razlika je del, ki je prisel
  iz izbire stevilk.</p>
  </div>

  <h2>Ali je treba testirati v kombinacijah?</h2>

  <p>Vsi preleti zgoraj premikajo <b>en parameter naenkrat</b>. To je veljavno samo, ce se
  parametri med seboj ne prepletajo. Na mrezi {EN['members']} kombinacij se to da izmeriti:
  koliko parameter premakne rezultat sam zase, in koliko je njegov ucinek odvisen od
  drugega.</p>

  <div class="grid" style="grid-template-columns:repeat(auto-fill,minmax(330px,1fr))">
   <div class="card"><h3>Glavni ucinki</h3>
    <p class="d">koliko parameter premakne Sortino sam zase</p>
    <table>{mrows}</table></div>
   <div class="card"><h3>Prepletanje</h3>
    <p class="d">koliko je ucinek enega odvisen od drugega</p>
    <table>{irows}</table></div>
  </div>

  <p>Najvecje prepletanje je <code>{top_i.replace(' x ', '</code> × <code>')}</code> pri
  {inter[top_i]:.3f}, kar je <b>{ratio:.0f} %</b> najvecjega glavnega ucinka
  ({max(main.values()):.3f}). Torej: preleti po en parameter naenkrat so bili <b>priblizno,
  ne pa povsem veljavni</b>.</p>

  <div class="fig" style="border-left:3px solid var(--warn)">
  <p style="margin:0"><b>Odgovor je bolj zanimiv od vprasanja.</b> Kombinacije je treba
  <b>izmeriti</b> — kar smo pravkar naredili — ni pa jih dovoljeno <b>preiskovati za
  najboljso</b>. Iskanje po stiridimenzionalni mrezi na 17 poslih bi verjetnost prevelike
  prilagojenosti (PBO, ze zdaj 0,694) samo dvignilo. Pravi odgovor na prepletanje ni
  boljsa kombinacija, ampak <b>povprecje cez vse kombinacije</b>. Ansambel to naredi po
  konstrukciji in se izogne izbiri.</p>
  </div>

  <h2>Konkretno: kaj spremeniti glede na zdaj</h2>

  <div class="fig"><table>
   <tr><th class="l">parameter</th><th>zdaj</th><th>vrh preleta</th>
       <th>sredina ravnine</th><th>padec na najslabsega soseda</th><th class="l">opomba</th></tr>
   {rows}
  </table></div>

  <p>Tri moznosti, po ceni:</p>

  <div class="grid" style="grid-template-columns:repeat(auto-fill,minmax(330px,1fr))">
   <div class="card" style="border-color:var(--good)">
    <h3>A · Ansambel <span class="badge" style="background:var(--good)">priporoceno</span></h3>
    <p class="long">Poganjaj vseh {EN['members']} kombinacij in povpreci pozicijo. Pozicija
    postane zvezna med 0 in 1 namesto vse-ali-nic.<br><br>
    <b>Za:</b> na konici se po konstrukciji ne da vec sedeti. Prehodi so postopni.<br>
    <b>Proti:</b> backtest pade na {en['sortino']:.2f}. Promet se rahlo <i>zvisa</i>
    ({pt['turnover']:.1f} → {en['turnover']:.1f}), ker se {EN['members']} clanov obraca ob
    razlicnih dnevih. MaxDD se rahlo poslabsa ({pt['maxdd']:.1f} % → {en['maxdd']:.1f} %).<br>
    <b>Pogoj:</b> produkt mora podpirati delne pozicije.</p></div>

   <div class="card">
    <h3>B · Ena vrednost, a sredina ravnine</h3>
    <p class="long">Ce delne pozicije niso izvedljive: obdrzi eno vrednost, a izberi
    <b>sredino najsirsega ravnega obmocja</b> namesto najvisje tocke —
    <code>ma_long_len</code> {rob['ma_long_len']['robust']},
    <code>confirm_bars</code> {rob['confirm_bars']['robust']},
    <code>reentry_hold</code> {rob['reentry_hold']['robust']},
    <code>exit_grace_bars</code> {rob['exit_grace_bars']['robust']}.<br><br>
    <b>Za:</b> nic novega v kodi.<br>
    <b>Proti:</b> se vedno izbira tocke, le manj obcutljiva. Ne odpravi problema, ga
    zmanjsa.</p></div>

   <div class="card">
    <h3>C · Ne spremeni nicesar, popravi pricakovanje</h3>
    <p class="long">Najmanjsi posteni ukrep: strategijo pusti pri miru, a povsod, kjer se
    navaja Sortino {pt['sortino']:.2f}, navedi tudi, da je <b>posteno pricakovanje
    {en['sortino']:.2f}</b>, ker je razlika prisla iz izbire stevilk.<br><br>
    <b>Za:</b> nic dela, takoj.<br>
    <b>Proti:</b> strategija ostane obcutljiva; naslednji, ki jo bo nastavljal, bo ponovil
    isto napako.</p></div>
  </div>

  <p><b>Priporocilo: A, s C kot obveznim dodatkom.</b> Tudi ce gremo na ansambel, mora biti
  {en['sortino']:.2f} stevilka, ki jo komuniciramo — ne {pt['sortino']:.2f}. In B ni slabsa
  izbira, ce delne pozicije v produktu niso izvedljive; je pa treba vedeti, da problema ne
  odpravi.</p>

  <p class="cap"><b>Ena opozorilna podrobnost.</b> Pri <code>confirm_bars</code> privzeta
  vrednost 3 sploh <i>ni</i> vrh — vrh je pri 2, sredina ravnine pa pri 1. Ta parameter
  torej ni bil prilagojen navzgor, ampak sedi na pobocju navzdol. To je edini od stirih, pri
  katerem bi ze sama sprememba na eno vrednost verjetno pomagala; a ker gre za isto vrsto
  izbire na istih podatkih, velja isto opozorilo kot za vse ostalo.</p>
{MARK_B}

"""


def main():
    s = PAGE.read_text(encoding="utf-8")
    if MARK_A in s:
        s = s[:s.index(MARK_A)] + s[s.index(MARK_B) + len(MARK_B):].lstrip("\n")
    if ANCHOR not in s:
        raise SystemExit(f"sidro {ANCHOR!r} ni najdeno — stran se je spremenila")
    s = s.replace(ANCHOR, build() + ANCHOR, 1)
    PAGE.write_text(s, encoding="utf-8")
    print(f"-> {PAGE}  ({PAGE.stat().st_size/1024:.0f} kB)")


if __name__ == "__main__":
    main()
