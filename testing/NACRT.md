# Diversitas Lean — enotni načrt

Ta dokument nadomešča vse prejšnje načrte. Starejši ostanejo v repozitoriju kot
zapis, kaj je bilo zapisano **pred** posameznim testom, a za usmerjanje dela velja
samo ta.

**Nadomešča:** `nacrt_izvedbe_v2.txt` · `nacrt_korak4.md` · `nacrt_korak5.md` ·
`nacrt_korak6_donchian.md` · `nacrt_eth_donchian.md` · `nacrt_dva_trackline.md` ·
`nacrt_izstop.md` · `nacrt_koraka_6_in_8.md` · `nacrt_do_konca.md`

---

## 1. Kaj je odločeno

| | izid |
|---|---|
| revizija pogleda v prihodnost | čisto, 200 datumov, dve kontroli |
| zamrznjena referenca | SHA256 `957d3bc9…`, 2700 barov |
| poenostavitev | 14 → 10 parametrov, pozicije nespremenjene |
| pregretje blokira tudi vstop | **sprejeto**, dokazljivo nevtralno |
| `exit_grace_bars = 3` | **potrjen** — brez njega −0,325 Sortina |
| `regime_ok` | **potrjen** — brez njega najslabša celica (1,378) |

## 2. Kaj je zavrnjeno in zakaj

| | razlog |
|---|---|
| premor pred ponovnim vstopom (4 različice) | 10 epizod v 7 letih, vsi IZ objamejo ničlo; naključno postavljen premor je boljši |
| prilagodljivi mrtvi pas (23 nastavitev) | cena je 70 % dni predaleč od razpona, da bi pas odločal |
| vstop po večini pogojev | poveča zamudo 3,5 → 5,7 dni, zajem navzdol +5,7 o. t. |
| ATR trailing stop | pri izenačeni izpostavljenosti **slabši** od današnjega; −22 do −72 % premoženja |
| Turtlovi izstopi (10/20/55) | noben ne prekaša današnjega; prilagajanje izstopa slabše od nespreminjanja v 4/4 shemah |
| ansambel čez parametre | izgubil v 0/4 walk-forward shem |
| skaliranje pozicije z nihajnostjo | placebo slabši od nespreminjanja |

## 3. Ena odprta odločitev

**Donchianov filter** (`use_donchian = True`, `donchian_period = 20`).

| za | proti |
|---|---|
| edini kandidat, ki je prestal ugnezdeni walk-forward (obe shemi) | mejni prispevek ob obstoječih pravilih majhen |
| ETH zunaj vzorca prestal vse tri pogoje | na BTC petkrat prihrani, petkrat stane |
| CSCV: 97,5 % zunajvzorčnih polovic | v 2025–2026 ni spremenil nobenega dne |
| naključni zamik na 96. percentilu | cena 9 o. t. manj časa v trgu |
| **zniža stroške** — 4 posli manj | parametrov 10 → 11 |

**Priporočilo: dodati, ne zamenjati.** Odstranitev `above_tl` ima tri neodvisne
znake v prid in enega z intervalom, ki izključuje ničlo — a sem na istih podatkih
dvakrat sklenil nasprotno, in ETH je porabljen, zato medsredstvene potrditve ni.

---

## 4. Kaj pravijo viri, in kaj od tega še ni preizkušeno

| ugotovitev | naš status |
|---|---|
| CTA-ji kombinirajo **več horizontov** (1, 3, 6, 12 mesecev), ne enega | ansambel testiran in zavrnjen — a na anti-churn parametrih, **ne na horizontih** |
| Zakamulin (*Quantitative Finance* 2020): pravila na **drsečih povprečjih** so robustnejša od momentum pravil | naš trackline je razpon, ne MA — **ni primerjano** |
| Donchian + dolgo MA kot filter je priporočena kombinacija | to bi imeli (Donchian + 200 MA režim) |
| **časovni izstop** (npr. po 80 dneh) kot alternativa stopom | **ni testirano** — korak 9 |

**Dve stvari torej ostajata odprti tudi po virih:** kombinacija horizontov trendnega
signala in časovni izstop.

---

## 5. Preostalo delo

### Faza A — zapri odločitev (2 h)

1. Odločitev o Donchianu
2. Če da: `use_donchian = True`, `donchian_period = 20`, zaklep periode v `config.py` z razlogom (PBO 0,672)
3. Referenco na novo zamrzniti z zapisom, zakaj — **prva namerna sprememba vedenja**
4. `test_reference.py` zelen proti novi referenci, negativna kontrola mora še vedno zaznati

### Faza B — preostale vnaprej zapisane hipoteze (6 h)

Te so bile v izvirnem načrtu in **še niso izvedene**. Prej sem napačno trdil, da je
seznam izčrpan.

| | kaj | opomba |
|---|---|---|
| **B1** | **korak 9** — časovni izstop kot kontrola | viri ga omenjajo; +1 parameter |
| **B2** | **korak 7** — ločen pas za vstop in izstop | pogojen na neuspeh 4 in 5, oba sta padla, torej je živ; +1 parameter |
| **B3** | ansambel čez **horizonte** trendnega signala | institucionalni standard; ni isto kot prej zavrnjeni ansambel |

Pri vseh treh velja: **argmaks se ne izbira**, kontrola mora reproducirati
referenco, in odloča izenačena izpostavljenost.

### Faza C — preverjanja brez novih pravil (5 h)

| | kaj |
|---|---|
| **C1** | **korak 10** — 4-urni bari, vsi pogledi × 6 |
| **C2** | obdobje po ETF (od 2024-01) — se je režim spremenil? |
| **C3** | časovnica izvedbe — trgovanje po odprtju naslednjega dne |
| **C4** | vir podatkov — Binance / Coinbase / Yahoo |

### Faza D — poštena karakterizacija (4 h)

| | kaj |
|---|---|
| **D1** | **deflacionirani Sharpe** s polnim številom poskusov (~210) |
| **D2** | **korak 12** — sodelovanje v padcih proti statičnemu 40/60 |
| **D3** | MinTRL — prej izmerjeno 25 do 1200 let proti kupi-in-drži |
| **D4** | pošteno pričakovanje naprej, z intervalom |

### Faza E — zaključek (3 h)

Končno poročilo, **izrecen seznam nedokazanega**, pravilo za ponovno odpiranje.

---

## 6. Pravila, ki veljajo za vse nadaljnje teste

1. **Predregistracija pred zagonom.** Pragovi se po tem ne popravljajo.
2. **Kontrolna celica mora reproducirati zamrznjeno referenco.** Če ne, stop.
3. **Izenačena izpostavljenost je obvezna.** V tem projektu je **petkrat** obrnila sklep.
4. **Argmaks se ne izbira.** Bere se oblika krivulje.
5. **ETH se ne uporablja.** Obe vnaprej zapisani uporabi sta porabljeni.
6. **Meri se pozicija, ne pogoj.** Trikrat je ta razlika spremenila sliko.
7. **Nobene naknadno izmišljene hipoteze** brez novih podatkov.

## 7. Kdaj se ustaviti

Po fazi E, dokler ne nastopi eden od teh:

- **12 mesecev novih podatkov** — edini vir, ki ga ni mogoče izčrpati
- **tretje sredstvo** z novo predregistracijo
- **sprememba stroškov ali likvidnosti**, ki spremeni predpostavke

**Ne** upravičuje: slabše četrtletje.

## 8. Kaj vemo o kakovosti dokazov

| meritev | vrednost | pomen |
|---|---|---|
| PBO, zgodnji parametri | 0,694 | izbira nastavitve slabša od meta kovanca |
| PBO, Donchianova perioda | 0,672 | izbira periode se ne prenaša |
| PBO, izbira med vstopom/izstopom | **0,974** | izbira med temi celicami je skoraj zagotovo napačna |
| PBO, izbira med trackline celicami | 0,167 | **ta izbira se prenaša** |
| preizkušenih konfiguracij | ~210 | vhod v deflacionirani Sharpe |
| poslov v vzorcu | 13–49 | vse sloni na tem |

**Zadnja vrstica je najpomembnejša.** Karkoli od tu naprej stoji na dvajsetih
poslih, in nobena statistika tega ne popravi.
