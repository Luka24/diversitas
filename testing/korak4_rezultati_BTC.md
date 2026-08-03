# Korak 4 — rezultati: premor pred ponovnim vstopom

**Podatki:** BTC, Binance, 2019-03-09 → 2026-07-29, 2700 barov, neto 0,30 % na stran
**Predregistracija:** `testing/nacrt_korak4.md`, commit `e4cd595`, **pred** zagonom
**Skripta:** `testing/scripts/reentry_pause.py` · **JSON:** `testing/data/reentry_pause_BTC.json`

## Sklep

**Nobena različica ne prestane predregistriranih pragov. Ostane A — brezpogojnih
15 dni.** Ne zato, ker bi se izkazala za najboljšo, ampak ker nobena druga ni
prestala. Vprašanje »ali je premor koristen« na BTC **ni rešljivo** in gre med
odprta vprašanja, ne med potrjene odločitve.

`reentry_hold` ostane. Parametrov je še naprej 10.

---

## 1. Kontrola

Različica A reproducira zamrznjeno referenco iz 2. koraka bar za barom.
Harness se torej ujema s produkcijskim motorjem in preostale tri številke nekaj
pomenijo.

Revizija pogleda v prihodnost za B (edina različica z novim stanjem — izidom
zadnjega posla): 60 datumov, **0 razlik**.

## 2. Rezultati

| | Sortino | Sharpe | MaxDD | izpost. | zajem + | zajem − | poslov | obrat |
|---|---|---|---|---|---|---|---|---|
| **A** brezpogojnih 15 dni | 1,505 | 0,974 | −45,2 | 41,9 | 41,5 | 37,8 | 21 | 42,0 |
| **B** 15 dni po izgubi | **1,764** | 1,121 | −44,9 | 45,6 | 47,5 | 42,2 | 32 | 64,0 |
| **C** 0 dni v uptrendu | 1,565 | 1,010 | −47,9 | 46,1 | 47,9 | 43,6 | 32 | 64,0 |
| **D** brez premora | 1,603 | 1,031 | −47,9 | 46,2 | 48,3 | 43,8 | 32 | 64,0 |

Na prvi pogled B prepričljivo zmaga. Naslednja dva razdelka pokažeta, zakaj ta
vtis ne zdrži.

## 3. Zakaj B ni zmaga

### 3.1 Vsa razlika je v letih 2019–2020

| primerjava | dni razlike | obdobje |
|---|---|---|
| B proti D | **17** | 2019-08-08 → 2021-01-24 |
| C proti D | **6** | 2019-05-12 → 2019-05-17 |

**Po januarju 2021 so B, C in D dobesedno ista strategija.** Vse, po čemer se
razlikujejo, se je zgodilo v najstarejšem in najmanj reprezentativnem delu okna —
tistem, ki ga je bilo že prej dogovorjeno gledati z rezervo.

### 3.2 Po podobdobjih se predznak obrne

Sortino, okna določena vnaprej:

| okno | obdobje | A | B | C | D | zmaga |
|---|---|---|---|---|---|---|
| I | 2019-03 → 2021-01 | 1,505 | **2,837** | 2,175 | 2,290 | B |
| II | 2021-02 → 2022-11 | **1,239** | 1,139 | 1,139 | 1,139 | A |
| III | 2022-12 → 2024-09 | **1,990** | 1,773 | 1,773 | 1,773 | A |
| IV | 2024-10 → 2026-07 | **1,603** | 1,022 | 1,022 | 1,022 | A |

**A zmaga v treh oknih od štirih.** B zmaga izključno v prvem — in tam zmaga toliko,
da obrne celotno okno.

Premor je torej v obdobju I škodil (A −0,785 proti D), v obdobjih II, III in IV pa
koristil (+0,100 · +0,217 · +0,581). **Predznak se obrne.** To je definicija
učinka, ki ga ni.

### 3.3 Intervali zaupanja

Sparjeni blokovni bootstrap, 5000 vzorcev, blok 20:

| | ΔSortino | 95 % IZ |
|---|---|---|
| B − A | +0,260 | [−0,237, +0,756] |
| C − A | +0,060 | [−0,364, +0,422] |
| D − A | +0,098 | [−0,326, +0,471] |

Vsi trije objamejo ničlo. **To je bilo napovedano v §9 predregistracije**, zato ni
presenečenje in ni novica.

## 4. Placebo — čas premora ne nosi informacije

1000 naključnih razporeditev: 10 premorov po 12 dni, postavljenih naključno.

```
Sortino placeba: povprečje 1,555   5–95 % [1,324, 1,759]
A                        1,505  ->  33,8. percentil
```

Naključno postavljeni premori so v povprečju **rahlo boljši** od pravega. A leži
sredi porazdelitve. Ni torej nobenega dokaza, da bi bila postavitev premora
boljša od naključne — kar pomeni, da pravilo ne izbira trenutkov, ampak le
zmanjšuje čas v trgu.

## 5. Izenačena izpostavljenost

Vsaka različica pomanjšana na izpostavljenost A (41,9 %):

| | k | Sortino | MaxDD | zajem − |
|---|---|---|---|---|
| A | 1,000 | 1,505 | −45,2 | 37,8 |
| B | 0,919 | 1,764 | −41,9 | 38,7 |
| C | 0,909 | 1,565 | −44,5 | 39,7 |
| D | 0,907 | 1,603 | −44,4 | 39,7 |

**Slabši padec pri C in D je bil artefakt izpostavljenosti.** Surovo je D imela
−47,9 % proti A −45,2 %; izenačeno je −44,4 % proti −45,2 %, torej **boljše**.
To je tretjič v tem projektu, ko se prednost oziroma slabost pri padcu izkaže za
posledico časa v trgu.

## 6. Epizode in jackknife

118 blokiranih dni v **10 epizodah**, od tega 8 polnih 14-dnevnih.

```
zamujeni gib:  povprečje +4,8 %   mediana +1,9 %   sd 10,3
jackknife:     povprečje niha med +2,04 % in +5,93 %
nosilna:       2020-12-31 (brez nje povprečje pade na +2,04 %)
```

Ena epizoda — januar 2021 — nosi več kot polovico povprečja. Sklep, ki bi slonel
na tem povprečju, sloni na enem dogodku izpred petih let.

## 7. Zamuda, ki jo dejansko povzroči premor

| | povpr. dni | najv. | zakasnjenih vstopov | blokiranih dni |
|---|---|---|---|---|
| A | 5,5 | 14 | 9 | 118 |
| B | 0,5 | 14 | 2 | 17 |
| C | 0,1 | 2 | 1 | 2 |
| D | 0,0 | 0 | 0 | 0 |

**To popravlja prvotno diagnozo.** Ocena »vstopi zamujajo 16 dni« je merila vse
skupaj — pogoje, `confirm_bars` in premor. Premor sam prispeva **5,5 dneva
povprečno** in zakasni **9 od 21 vstopov**. Je torej manjši del problema, kot je
bilo videti.

## 8. Občutljivost B

| dni | 10 | 15 | 20 | 25 |
|---|---|---|---|---|
| Sortino | 1,648 | 1,764 | 1,772 | 1,694 |

Nazobčano, razpon 0,124, vrh pri 20 in ne pri 15. Nobene strukture.
**Argmaksa nisem izbral**, kot je bilo zapisano vnaprej.

## 9. Uporaba odločitvenega pravila

### D — dovolj bi bilo, da ni slabša (potrebno vse troje)

| | prag | izmerjeno | |
|---|---|---|---|
| 1 | spodnja meja IZ > −0,15 | **−0,326** | ✘ |
| 2 | izpostavljenost < +5 o. t. | +4,3 | ✔ |
| 3 | zajem − izenačeno < +1,0 o. t. | **+1,9** | ✘ |

Pade na dveh od treh.

### B — mora jasno zmagati (potrebno vse štiri)

| | prag | izmerjeno | |
|---|---|---|---|
| 1 | boljša od A **in** D | 1,764 > 1,603 | ✔ |
| 2 | IZ izključuje ničlo | [−0,237, +0,756] | ✘ |
| 3 | isti predznak v ≥ 3 od 4 obdobij | **1 od 4** | ✘ |
| 4 | preživi izenačenje izpostavljenosti | 1,764 · −41,9 | ✔ |

Pade na dveh od štirih, od tega je pogoj 3 odločilen.

### C — pade takoj

Točkovna ocena 1,565 je nižja od D (1,603). Pogoj 1 ni izpolnjen.

### Izid

Nič ne prestane. **Ostane A.**

## 10. Napovedi proti izidu

Predregistracija §9 je vsebovala pet napovedi. Zapisane so bile pred zagonom:

| napoved | izid |
|---|---|
| 1. vsi IZ objamejo ničlo | ✔ vsi trije |
| 2. D poveča izpostavljenost 2–5 o. t., poslabša MaxDD, izenačeno razlika izgine | ✔ delno — +4,3 o. t. in slabši MaxDD držita; izenačeno se je MaxDD **obrnil v prid D**, prednost pri Sortinu pa ni izginila |
| 3. krivulja premora ravna | ✔ nazobčana, brez strukture |
| 4. B se od A razlikuje na manjšini epizod | ✔ 2 zakasnjena vstopa proti 9 |
| 5. nič ne prestane, ostane A | ✔ |

## 11. Kaj to pomeni za naprej

**Premor ni problem.** Prispeva 5,5 dneva zamude na vstop in prihrani 11 obratov
(21 poslov proti 32), kar je pri 0,30 % na stran ~6,6 % kapitala v sedmih letih.
To je edini zanesljiv, v vseh obdobjih enak učinek, ki ga premor ima.

**Težišče zamude je drugje.** Ostane pri tem, kdaj se pogoji sploh prižgejo, in
pri `confirm_bars`. Tega koraka 4 ne dotakne.

Naslednja sta zato **korak 5** (prilagodljivi mrtvi pas, umerjen tako, da
zgodovinsko povprečje ostane 3 %) in **korak 6** (vstop po večini pogojev
namesto po vseh). Oba naslavljata prižig pogojev, ne čakanja po izstopu.

**Korak 7 ne odpade.** Predregistracija je predvidela, da odpade, če katerakoli
različica prestane vse tri pogoje. Nobena ni.
