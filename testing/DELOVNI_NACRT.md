# Delovni načrt — kaj točno bom naredil

Konkretni koraki, ne strategija. Za širši kontekst glej `NACRT.md`.

---

## Korak 1 — Polna baterija na ocenjeni različici ~3 h

**Zakaj prvi:** ocenjena velikost pozicije (`k/3`) je najmočnejši kandidat v
projektu — Sortino 1,949 proti 1,505, **enaka izpostavljenost**, boljša v vseh
štirih podobdobjih. Vse ostalo je odvisno od tega, ali zdrži.

**Skripta:** `testing/scripts/graded_full.py`

**Štiri celice**, da se preveri tudi, ali se ocenjevanje in Donchian **prekrivata**:

| | vstop | velikost |
|---|---|---|
| 1 | vsi trije | binarno — **kontrola, mora reproducirati referenco** |
| 2 | vsaj eden | `k/3` |
| 3 | vsi trije + Donchian | binarno |
| 4 | vsaj eden + Donchian | `k/4` |

**Testi:**

1. kontrola proti zamrznjeni referenci — če pade, stop
2. metrike + štiri vnaprej določena podobdobja
3. sparjeni blokovni bootstrap ΔSortino, blok 20, 5000 vzorcev
4. MCS z obema funkcijama izgube
5. ugnezdeni walk-forward, shemi 3/1 in 2/1
6. **PBO s purge 21 dni**
7. naključni zamik, 1000 rotacij
8. **prelomna provizija** — pri kateri višini stroška prednost izgine

**Točka 8 je za ocenjeno različico ključna.** Obrat naraste z 42 na 99, provizije
z 12,6 % na 29,8 % kapitala. Če prednost izgine že pri 0,35 % na stran, je
rezultat odvisen od predpostavke o stroških in ne od signala.

**Sprejemni kriterij, zapisan vnaprej — potrebno vse:**

| | |
|---|---|
| 1 | Sortino boljši od kontrole |
| 2 | boljši v **≥ 3 od 4** podobdobij |
| 3 | ugnezdeni walk-forward ga izbere v **obeh** shemah |
| 4 | naključni zamik nad **90. percentilom** |
| 5 | prednost zdrži do **0,50 % na stran** |

---

## Korak 2 — Ponovni izračun vseh PBO s purge ~1 h

**Zakaj:** nobena moja izvedba CSCV ni imela purge, značilke pa nosijo 200-dnevna
okna. Na ocenjeni različici je razlika 0,192 → 0,239. **Vsi doslej navedeni PBO
so optimistični.**

**Skripta:** `testing/scripts/pbo_recompute.py`

Ponovno izračunam vse in izdelam popravljeno tabelo:

| kaj | doslej navedeno | s purge |
|---|---|---|
| izbira med trackline celicami | 0,167 | ? |
| Donchianova perioda | 0,672 | ? |
| izbira izstopa | 0,324 | ? |
| izbira vstop/izstop | 0,974 | ? |

Popravljene številke zamenjajo stare v `NACRT.md`.

---

## Korak 3 — ETH kot opis, ne kot potrditev ~1 h

Obe vnaprej zapisani uporabi sta porabljeni. **Pravila ne bom obšel s tem, da si
premislim, ko bi mi prav prišlo.**

Ocenjeno različico bom na ETH **izračunal in poročal**, izrecno označeno kot
**tretji zajem, ki ne šteje kot dokaz**. Če se izid ujema, to poveča zaupanje;
če se ne, je to opozorilo — a nobeno ni dokaz.

---

## Korak 4 — Odločitev in izvedba ~2 h

Odvisno od korakov 1–3. Tri možnosti:

**A. Ocenjeno prestane** → `target_alloc` postane 0 / 33 / 67 / 100 %.
To ni majhna sprememba:
- referenco na novo zamrznem z zapisom, zakaj
- `test_reference.py` mora ostati zelen proti novi referenci
- **dashboard prikazuje binarno alokacijo** — treba popraviti
- `use_vol_sizing` / `target_vol_pct` v configu sta danes ignorirana; ocenjevanje
  je oblika velikosti pozicije, zato je treba to razmerje razčistiti
- izvedba: delne prilagoditve namesto celih vstopov

**B. Prestane samo Donchian** → `use_donchian = True`, `donchian_period = 20`,
perioda zaklenjena z razlogom.

**C. Nobeden** → nič se ne spremeni, oboje gre med zavrnjeno z razlogom.

---

## Korak 5 — Preostale vnaprej zapisane hipoteze ~5 h

Te so bile v izvirnem načrtu in **niso izvedene**.

| | kaj | +param |
|---|---|---|
| **5a** | **korak 9** — časovni izstop kot kontrola (npr. po N dneh) | +1 |
| **5b** | **korak 7** — ločen pas za vstop in izstop | +1 |
| **5c** | ansambel čez **horizonte** trendnega signala (ne čez anti-churn parametre, kot prej) | 0 |

Pri vseh: argmaks se ne izbira, kontrola mora reproducirati referenco, izenačena
izpostavljenost je obvezna, PBO s purge.

---

## Korak 6 — Robustnost brez novih pravil ~5 h

| | kaj |
|---|---|
| **6a** | **korak 10** — 4-urni bari, vsi pogledi × 6 |
| **6b** | obdobje po ETF (od 2024-01) — se je režim spremenil? |
| **6c** | časovnica izvedbe — trgovanje po **odprtju naslednjega dne** namesto po zaključku |
| **6d** | vir podatkov — Binance / Coinbase / Yahoo na istem oknu |

Nobeno ne uvaja parametra. Vsa preverjajo, ali obstoječi rezultat drži.

---

## Korak 7 — Poštena karakterizacija ~4 h

| | kaj |
|---|---|
| **7a** | **deflacionirani Sharpe** s polnim številom poskusov (~215) |
| **7b** | **korak 12** — sodelovanje v padcih proti statičnemu 40 % BTC / 60 % gotovina |
| **7c** | MinTRL — koliko let bi rabili, da to ločimo od kupi-in-drži |
| **7d** | pošteno pričakovanje naprej, ena številka z intervalom |

---

## Korak 8 — Zaključek ~3 h

- končno poročilo za sodelavce
- **izrecen seznam nedokazanega**
- pravilo za ponovno odpiranje
- posodobljen `NACRT.md`

---

## Skupaj ~24 ur

| korak | ure |
|---|---|
| 1 baterija na ocenjeni | 3 |
| 2 PBO s purge | 1 |
| 3 ETH opisno | 1 |
| 4 odločitev in izvedba | 2 |
| 5 preostale hipoteze | 5 |
| 6 robustnost | 5 |
| 7 karakterizacija | 4 |
| 8 zaključek | 3 |

---

## Kaj bi me ustavilo prej

**Če ocenjena različica pade na koraku 1**, koraki 2–4 se skrajšajo na odločitev
o Donchianu, ostalo ostane isto.

**Če se PBO s purge izkažejo bistveno višji**, je to samo po sebi ugotovitev:
pomeni, da so bili vsi dosedanji sklepi o prenosljivosti preveč optimistični, in
to je treba povedati pred vsem drugim.

**Če prelomna provizija pade pod 0,50 %**, ocenjena različica odpade ne glede na
vse ostalo — ker bi bila odvisna od predpostavke, ki je nimamo pod nadzorom.
