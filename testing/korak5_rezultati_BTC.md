# Korak 5 — rezultati: prilagodljivi mrtvi pas

**Podatki:** BTC, Binance, 2019-03-09 → 2026-07-29, 2700 barov, neto 0,30 % na stran
**Predregistracija:** `testing/nacrt_korak5.md` (`dc702b1`, dopolnjena `c5534d6` in za moč pred izvedbo)
**Skripta:** `testing/scripts/adaptive_buffer.py` · **JSON:** `testing/data/adaptive_buffer_BTC.json`

## Sklep

**Nobena različica ne prestane predregistriranih pogojev. Ostane A — fiksnih 3 %.**

Smer je pravilna in to je vredno zapisati: dnevi, ki bi jih ožji pas spustil noter,
so res nadpovprečni. Ampak na ravni strategije se **F premakne na 10 dneh v sedmih
letih**, E pa zmaga le v najstarejšem od štirih obdobij.

Nova ugotovitev za naprej: **prilagodljivost na izstopni strani škoduje.**

---

## 1. Kontrola in pas

Različica A reproducira zamrznjeno referenco bar za barom. Revizija pogleda v
prihodnost za E in F: 40 datumov, **0 razlik**.

Realizirani pas: povprečje **3,05 %** (sidro 3 % se ohrani), po letih stabilno med
3,0 in 3,2 %. Pod 1 % pade na **2 dneh**, čez 10 % na **5**. Ne uide v absurd.

## 2. Metrike

| | Sortino | Sharpe | MaxDD | izpost. | zajem + | zajem − | poslov | obrat |
|---|---|---|---|---|---|---|---|---|
| **A** fiksnih 3 % | 1,505 | 0,974 | −45,2 | 41,9 | 41,5 | 37,8 | 21 | 42,0 |
| **E** prilagodljiv, obe strani | 1,537 | 0,996 | −45,2 | 43,0 | 42,4 | 38,5 | 21 | 42,0 |
| **F** prilagodljiv, samo vstop | **1,576** | 1,017 | −45,2 | 42,3 | 42,0 | 37,9 | 21 | 42,0 |

**Stroškovne kazni ni.** Vse tri imajo 21 poslov in enak obrat 42,0 — pas premakne
*časovnico*, ne števila poslov. MaxDD je pri vseh treh enak.

## 3. Dnevna študija — smer je pravilna

Donos BTC v naslednjih 20 dneh:

| skupina | dni | epizod | donos | proti izhodišču |
|---|---|---|---|---|
| izhodišče, vsi dnevi | 2680 | — | +3,27 % | — |
| **ožji pas nas spusti noter, A ne** | 26 | 17 | **+9,17 %** | **+5,90** |
| **širši pas nas zadrži, A vstopi** | 14 | 12 | **−4,84 %** | **−8,11** |

Obe smeri kažeta isto: kadar je pas ožji od 3 %, so dnevi, ki jih spusti, res
boljši od povprečja; kadar je širši, so dnevi, ki jih zadrži, res slabši.

**Interval zaupanja tu ni mogoč in tega ne skrivam.** Napovedni donos se prekriva
20 dni, zato mora biti blok 20 dolg — pri n = 26 to pomeni 1,3 bloka, pri n = 14
pa 0,7. Prva različica te skripte je izpisala `[−4,84, −4,84]`, kar je izgledalo
kot izjemno tesen interval, v resnici pa je bil vsak vzorec isti niz, le zavrten.
Skripta zdaj interval **zavrne**, namesto da bi ga izpisala.

## 4. Kje se sploh kaj premakne

| | dni razlike | obdobje | po letih |
|---|---|---|---|
| A proti **E** | 76 | 2020-09-11 → 2025-10-18 | 2020:43 · 2024:11 · 2025:22 |
| A proti **F** | **10** | 2020-10-14 → 2020-10-23 | 2020:10 |

F se od današnje strategije razlikuje na **desetih dneh oktobra 2020**. Vseh
0,071 Sortina razlike izvira od tam.

Vstopni prag se sicer razlikuje na 40 dneh, a stroj stanj in `confirm_bars` večino
teh preobratov požreta, preden postanejo posel.

## 5. Podobdobja — okna določena vnaprej

| okno | obdobje | A | E | F |
|---|---|---|---|---|
| I | 2019-03 → 2021-01 | 1,505 | **1,903** | 1,729 |
| II | 2021-02 → 2022-11 | **1,239** | 1,239 | 1,239 |
| III | 2022-12 → 2024-09 | **1,990** | 1,839 | 1,990 |
| IV | 2024-10 → 2026-07 | **1,603** | 1,173 | 1,603 |

**E zmaga v enem oknu in izgubi v dveh** — v IV precej (1,173 proti 1,603).

**F je v treh oknih identična A** in boljša samo v prvem. Nikoli ni slabša, kar je
drugače kot pri različici B v 4. koraku — a njena prednost stoji na desetih dneh
izpred petih let in pol.

Sparjeni bootstrap na dnevnih donosih: E−A = +0,032 [−0,227, +0,305], F−A = +0,072
[−0,005, +0,243]. Oba objameta ničlo, kot je bilo napovedano.

## 6. Placebo z nihajnostjo — moja napoved je padla

| pri izenačeni izpostavljenosti 41,9 % | Sortino | MaxDD | zajem − |
|---|---|---|---|
| A | 1,505 | −45,2 | 37,8 |
| E | 1,537 | −44,3 | 37,5 |
| F | **1,576** | −44,9 | 37,5 |
| **placebo — A, pravila nespremenjena, pozicija skalirana z 1/nihajnost** | **1,439** | −44,2 | 36,7 |

Napovedal sem (§8.3), da bo placebo ujel **velik del** razlike, ker je prilagodljiv
pas po Kim/Tse/Wald skaliranje z nihajnostjo v preobleki.

**Ni ga ujel — placebo je slabši od same A.** Golo skaliranje pozicije z obratno
nihajnostjo v tej strategiji škoduje. Kar E in F počneta, torej **ni** skaliranje z
nihajnostjo po ovinku. Ta pomislek tu ne velja.

To ne reši E in F — padeta na doslednosti — pomeni pa, da mehanizem ni artefakt.

## 7. Uporaba odločitvenega pravila

| | E | F |
|---|---|---|
| 1. pravilna smer dnevno | ✔ | ✔ |
| 2. Sortino boljši od A | ✔ 1,537 | ✔ 1,576 |
| 3. **boljši v ≥ 3 od 4 obdobij** | **✘ 1 od 4** | **✘ 1 od 4** (v treh identična) |
| 4. preživi izenačeno izpostavljenost | ✔ | ✔ |
| 5. prekaša placebo | ✔ | ✔ |

Obe padeta na tretjem pogoju. **Ostane A.**

## 8. Napovedi proti izidu

| napoved (§8) | izid |
|---|---|
| 1. dnevna študija bo imela dovolj moči | **✘ ne** — 26 in 14 dni, interval ni mogoč |
| 2. E bo imela **višjo** izpostavljenost od A, F nižjo *(popravljeno §9)* | **✔ E 43,0** · ✘ F 42,3, tudi višja od A |
| 3. placebo bo ujel velik del razlike | **✘ ne** — placebo 1,439 je slabši od A |
| 4. F bo bližje A kot E | **✔** — 10 dni proti 76 |
| 5. mehanizem obstoja, a ga pojedo stroški in skaliranje | **delno** — stroškov ni (enak obrat), skaliranje ni razlog; pade na doslednosti |

Tri od petih napovedi so padle. Najbolj pomembna je tretja: **pomislek iz
literature se na naših podatkih ni uresničil.**

## 9. Dopolnitev — profesionalna oblika pasu (G, H)

Vprašanje po prvem zagonu: **ali je moja formula preveč dušena?** Deli namreč z
lastnim 50-dnevnim povprečjem, ki nihajnosti sledi z zamikom, zato razmerje večino
časa visi okoli 1.

Kako to delajo profesionalci:

| | formula |
|---|---|
| Keltnerjev kanal | `EMA ± 2 × ATR(20)` |
| Chandelier izstop | `najvišji vrh − 3 × ATR(22)` |
| Turtle (N) | stop pri `2 × ATR`, velikost pozicije `tveganje / ATR` |

Vsi uporabljajo nihajnost **neposredno**. Ko se ATR podvoji, se pas podvoji.

Obe obliki sta pravzaprav ista družina z drugačnim oknom normalizacije:
`pas = sidro × vol_t / povprečje_w(vol)`. Pri E in F je w = 50 dni, pri
Keltnerju je w = ves čas. Testirana sta zato **le konca spektra**; karkoli
vmes bi pomenilo izbirati okno ob pogledu na odgovor.

Za G in H je uporabljeno **razširjajoče se povprečje** (samo pretekli podatki),
ne konstanta, umerjena na celem vzorcu — ta bi bila tiho uporaba prihodnosti:
množitelj iz cele zgodovine je 0,0545, iz prvih dveh let 0,0445, **18 % narazen**.

### Odzivnost je res večja

| | povpr. pas | 1.–99. pct | dni pod 1 % | dni nad 10 % | dni razlike v vstopnem pragu |
|---|---|---|---|---|---|
| E, F (50-dnevno) | 3,05 % | 1,42–6,66 % | 2 | 5 | 40 |
| G, H (Keltner) | 2,65 % | 0,97–6,18 % | 33 | 20 | 52 |

Dnevna študija to potrdi: G spusti noter **45 dni** (proti 26 pri E), z donosom
+8,07 % proti izhodišču +3,27 %.

> **Pridržek:** G ima povprečen pas 2,65 %, ne 3 % — sidro se pri razširjajočem
> se povprečju ne ohrani, ker je nihajnost v vzorcu upadala. G torej ni čist test
> odzivnosti, ampak odzivnosti **in** nekoliko ožjega pasu. Sweep iz
> `parametri_BTC.json` kaže, da sta 2,5 % (1,229) in 3,0 % (1,219) praktično
> izenačena, zato razlika v ravni verjetno ni gonilo — a to je sklep iz drugega
> testa, ne iz tega.

### Izid je isti

| | Sortino | MaxDD | izpost. | poslov | dni razlike proti A |
|---|---|---|---|---|---|
| A | 1,505 | −45,2 | 41,9 | 21 | — |
| E | 1,537 | −45,2 | 43,0 | 21 | 76 |
| F | 1,576 | −45,2 | 42,3 | 21 | 10 |
| **G** Keltner, obe strani | 1,538 | **−41,4** | 41,1 | 21 | 66 |
| **H** Keltner, samo vstop | 1,576 | −45,2 | 42,3 | 21 | **10** |

Podobdobja:

| okno | A | E | F | G | H |
|---|---|---|---|---|---|
| I | 1,505 | **1,903** | 1,729 | 1,880 | 1,729 |
| II | **1,239** | 1,239 | 1,239 | 1,239 | 1,239 |
| III | **1,990** | 1,839 | 1,990 | 1,990 | 1,990 |
| IV | **1,603** | 1,173 | 1,603 | **1,004** | 1,603 |

Zmag: **A = 3**, E = 1, F = 0, G = 0, H = 0. Revizija pogleda v prihodnost: 0 razlik
pri vseh štirih.

### Dve stvari, ki jih je vredno zabeležiti

**H je natanko enaka F.** Isti Sortino, isti MaxDD, istih 10 dni razlike (oktober
2020). Vstopna stran torej da **isti odgovor ne glede na to, katero normalizacijo
nihajnosti izbereš** — kar je bolj robustno, kot bi bilo, če bi se odgovora
razlikovala.

**G ima najboljši padec** (−41,4 % proti −45,2 %, tudi pri izenačeni
izpostavljenosti), a se v zadnjem obdobju sesuje na 1,004 proti 1,603. Prednost
pri padcu je plačana z zadnjimi dvema letoma.

### Odgovor na vprašanje

**Dušenost ni bila razlog.** Popolnoma odzivna, profesionalno standardna oblika
poveča število prizadetih dni (40 → 52 pri pragu, 26 → 45 v dnevni študiji), a
**ne spremeni izida**. Ozko grlo je drugje — glej §10.

## 10. Zakaj noben pas ne premakne veliko

Porazdelitev oddaljenosti cene od razpona čez vseh 2700 dni:

| kje leži cena | dni | delež |
|---|---|---|
| nad +7 % | 1112 | **41,2 %** |
| med +1 in +7 % ← **cona, kjer pas odloča** | 355 | **13,1 %** |
| med −1 in +1 % | 117 | 4,3 % |
| med −7 in −1 % | 341 | 12,6 % |
| pod −7 % | 775 | **28,7 %** |

Pas se giblje med ~1 in ~7 %. **Na 70 % dni je cena tako daleč od razpona, da je
vseeno, kje je prag.** Le 13 % dni sploh leži v coni, kjer lahko odloča — in še
tam mora prag pasti natanko med ceno in razpon.

To pojasni vse troje hkrati: zakaj je sweep pasu plato med 2 in 3 %, zakaj se
prilagodljiv pas premakne na 10 dneh, in zakaj bolj odzivna oblika tega ne reši.
**Oddaljenost od razpona je dvovrhna** — cena je v trendnem sredstvu redko blizu
sredine. To ni napaka nastavitve, ampak lastnost podatkov.

## 11. Kaj to pomeni za naprej

**Prilagodljivost na izstopni strani škoduje.** F (fiksni izstop) je boljša od E
(prilagodljivi izstop) — 1,576 proti 1,537 — in razlika med njima je natanko
izstopna stran, 66 dni razlike. Če se kdaj lotimo ločenega pasu za vstop in
izstop, mora izstopni **ostati fiksen**.

**Korak 7 ostaja v igri, a z ozko nalogo.** Ločen pas ni več vprašanje »ali
prilagodljiv«, ampak »ali naj bo izstopni pas širši od vstopnega«. To je ena sama
številka in en sam test.

**Vstopni pas premakne premalo, da bi ga bilo vredno prilagajati.** 40 preobratov
praga se prelevi v 10 dni drugačne pozicije. Če je težišče problema res v tem,
kdaj se pogoji prižgejo, ga mrtvi pas sam ne bo rešil — kar kaže na **korak 6**
(vstop po večini pogojev) kot naslednjo smiselno potezo.
