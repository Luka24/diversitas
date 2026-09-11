# Končna ugotovitev: nobeno pravilo ne prekaša manjše pozicije

Merjeno z `testing/scripts/sreca_datuma.py` (odprava sreče pri datumu),
`faber_koncno.py` (mreža nastavitev) in `binarno_klasika.py` (klasična pravila).
Provizija 0,20 % na posel, brez davka, gotovina po dejanski meri ECB.
Portfelja strogo ločena.

## Kaj je razkrilo vnaprej zapisano merilo

Prejšnji krog je poročal, da Faberjevo pravilo na P1 da CAGR 8,48 % in
Sortino 1,07. Ti številki sta izhajali iz **enega samega izbranega dneva
odločanja v mesecu** — konvencije »zadnji trgovalni dan«.

Preizkus vseh 21 možnih dni pokaže, da je ta konvencija na **86. percentilu**
porazdelitve. Poštena pričakovana vrednost je **mediana, ne konvencija**:

| P1, čez 21 možnih dni odločanja | min | **mediana** | max | razpon |
|---|---:|---:|---:|---:|
| CAGR | 5,00 % | **6,13 %** | 8,36 % | 3,36 pp |
| Sortino | 0,61 | **0,76** | 1,06 | 0,45 |
| MaxDD | −36,1 % | **−30,0 %** | −19,6 % | 16,6 pp |

Na P2 je konvencija na 90. percentilu; razpon je manjši (0,94 pp).

## Vnaprej zapisano merilo (pred prvim zagonom, v docstringu skripte)

> Popravek je uspešen, če datumsko srečo odpravi (razpon → 0) **in** če se
> njegov rezultat ne uvrsti pod mediano osnovnega pravila. Merilo je
> stabilnost, ne donos — donosa ni mogoče napihniti z izbiro srečne poti.

| popravek | razpon | Sortino | sodba P1 | sodba P2 |
|---|---:|---:|---|---|
| C1 glasovanje vseh 21 mrež, večina odloči | 0,00 | 0,76 | **uspešen** | zavrnjen (1,20 < 1,24) |
| C2 dnevno SMA210 s pasom 1 % | 0,00 | 0,69 | zavrnjen | zavrnjen |
| C3 dnevno SMA210 brez pasu | 0,00 | 0,51 | zavrnjen | zavrnjen |
| C4 cena = povprečje meseca | 2,24 pp | 0,77 | zavrnjen (razpon ostane) | zavrnjen |

---

## P1 — World 55 %, EM 15 %, SmallCap 15 %, Quality 15 %

Okno 2006-10-06 → 2026-09-04, 19,9 leta. 10.000 € začetka.

| | CAGR | Sharpe | Sortino | MaxDD | v trgu | poslov/l | 10k → |
|---|---:|---:|---:|---:|---:|---:|---:|
| kupi in drži | **9,19 %** | 0,57 | 0,80 | **−51,9 %** | 100 % | 0 | **57.564 €** |
| statičnih 75 % (ovira) | 7,40 % | 0,59 | **0,82** | −40,5 % | 75 % | 0 | — |
| Faber brez datumske sreče (C1) | 6,13 % | 0,55 | 0,76 | **−28,6 %** | 75 % | 6,1 | 32.720 € |

- **proti statičnemu deležu: d Sortino −0,07 [−0,49, +0,37]** — prejšnjih +0,26 je bila datumska sreča
- Sortino je nižji tudi od navadnega držanja (0,76 proti 0,80)
- PBO 6,7 %, deflated Sharpe **0,946 — pod pragom 0,95**
- Harvey-Liu s 75 poskusi: t = 2,46 → po Bonferroniju 0,00, **odbitek 100 %**

Edino, kar pravilo še vedno prinese, je **najnižji padec od vseh treh možnosti**
(−28,6 % proti −40,5 % pri statičnem deležu in −51,9 % pri držanju). To ni
veščina, ampak orodje za zniževanje padca z znano ceno: 1,3 odstotne točke
donosa na leto v primerjavi s statičnim deležem.

## P2 — World 23 %, EM 7 %, GlobAgg 35 %, InflLink 20 %, Gold 10 %, Commod 5 %

Kontrolni portfelj. **Vsi štirje popravki zavrnjeni.**

| | CAGR | Sharpe | Sortino | MaxDD | 10k → |
|---|---:|---:|---:|---:|---:|
| kupi in drži | 6,64 % | 1,00 | 1,43 | −16,0 % | 30.871 € |
| statičnih 88 % (ovira) | 5,82 % | 0,97 | 1,38 | −14,2 % | — |
| najboljši popravek (C4) | 4,90 % | 0,91 | 1,27 | −15,0 % | 23.493 € |

d Sortino −0,10 [−0,42, +0,25]. PBO 40,1 %. Sodba nespremenjena: **ne uporabljaj**.

---

## Kaj je preživelo vse preizkuse

Ena sama ugotovitev, a je robustna na obeh knjigah in v vseh krogih:

**Mesečno odločanje je bistveno boljše od dnevnega.** Na P1: C1 (mesečna
evidenca) 6,13 % proti C3 (dnevno, brez pasu) 3,58 %. Ko se že odloča dnevno,
je zaščitni pas nujen: C2 (s pasom) 5,09 % proti C3 (brez) 3,58 %, in obrat
pade s 25,9 na 12,0 poslov na leto.

## Kaj je bilo v prejšnjih krogih napačno, in zakaj

| trditev | vir napake |
|---|---|
| »P2 agresivna ima boljše najslabše leto (−7,4 % proti −9,4 %)« | strategija leta 2008 ni tekla — 12 mesecev ogrevanja momentuma |
| »Faber na P1 da 8,48 % in Sortino 1,07« | konvencija »zadnji dan v mesecu« je na 86. percentilu datumske sreče |
| »d Sortino +0,26 proti statičnemu deležu« | ista datumska sreča; po odpravi −0,07 |
| »utežena TAA prekaša statični delež« | rang namesto donosa v filtru; napačen izračun deleža v tveganem |

Vse štiri napake so bile odkrite z zaščitami, ne s ponovnim gledanjem
rezultatov: prva z izpisom razporeditve, druga in tretja z vnaprej zapisanim
merilom, četrta z enotskimi testi.

## Zaključek za obe knjigi

**Na teh osmih skladih ni pravila za časovno izbiranje, ki bi prekašalo to,
da preprosto naložiš manj in se ne dotikaš.** Vsaka navidezna zmaga v tem
projektu je izvirala iz enega od treh virov: (1) obdobja, ki ga strategija ni
odigrala, (2) srečno izbranega dneva uravnavanja, (3) nižje povprečne
izpostavljenosti.

Odločitev, ki jo je treba sprejeti, je zato **velikost pozicije, ne trenutek
vstopa** — z eno izjemo: če je cilj izrecno najmanjši možni padec, Faberjevo
pravilo brez datumske sreče da −28,6 % namesto −40,5 %, in to za ceno
1,3 odstotne točke donosa na leto.
