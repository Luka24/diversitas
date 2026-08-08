# Predlog: spremeni eno stvar

**Stopnjevana velikost pozicije.** Nič drugega.

---

## 1. Kaj se spremeni

**Danes:** strategija je v trgu s 100 % ali z 0 %. Vstopi, ko so izpolnjeni **vsi
trije** pogoji — cena nad razponom + 3 %, razpon se dviguje, režim ni medvedji.

**Predlog:** vstopi, ko je izpolnjen **vsaj eden**, velikost pozicije pa je delež
izpolnjenih:

| izpolnjeni pogoji | pozicija |
|---|---|
| 0 od 3 | 0 % |
| 1 od 3 | 33 % |
| 2 od 3 | 67 % |
| 3 od 3 | 100 % |

Vse ostalo ostane nedotaknjeno: isti trije pogoji, isti izstop, isti blow-off,
ista prizanesljivost, isti premor.

## 2. Kaj to prinese in kaj stane

| | danes | stopnjevano |
|---|---|---|
| Sortino | 1,505 | **1,949** |
| CAGR | 33,6 % | **42,7 %** |
| najhujši padec | −45,2 % | **−36,2 %** |
| končni mnogokratnik | 8,55× | **13,86×** |
| **čas v trgu** | **41,9 %** | **41,8 %** |
| obrat | 42,0 | **99,3** |
| provizije v 7 letih | 12,6 % | **29,8 %** |

**Čas v trgu je enak.** To ni artefakt izpostavljenosti, ki je v tem projektu
obrnil pet prejšnjih sklepov.

**Cena je obrat.** Podvoji se. Provizije narastejo za 17 odstotnih točk kapitala —
in vse zgornje številke so **že po tem odbitku**.

## 3. Zakaj to in ne kaj drugega

Prestalo je **vseh pet** vnaprej postavljenih pogojev, edino v celotnem projektu:

| | pogoj | izid |
|---|---|---|
| 1 | Sortino boljši od današnjega | ✔ 1,949 |
| 2 | boljši v ≥ 3 od 4 podobdobij | ✔ **4 od 4** |
| 3 | walk-forward ga izbere v obeh shemah | ✔ |
| 4 | naključni zamik nad 90. percentilom | ✔ **98,2.** |
| 5 | prednost zdrži do 0,50 % provizije na stran | ✔ **zdrži do 1,00 %** |

Peti pogoj je bil napisan prav zato, ker se obrat podvoji. Prednost je +0,444 pri
0,30 % in še vedno **+0,155 pri 1,00 %**.

## 4. Česa ne predlagam in zakaj

| | razlog |
|---|---|
| **Donchian** | 2 od 4 podobdobij po enotnem merilu; dodan k stopnjevanju ga poslabša s 4/4 na 2/4 |
| **krajša perioda tracklina** | BTC pravi 40, ETH pravi 25; na BTC je 40 konica, sosedi padejo |
| **ATR trailing stop** | zavrnjen trikrat, nazadnje pri izenačeni izpostavljenosti |
| **večina pogojev (pragovno)** | zavrnjeno trikrat; poveča zamudo in zajem navzdol |

---

## 5. Načrt izvedbe

### Faza 0 — poenoti merilo ~1 h

Merila med testi **niso bila enotna**. Donchian je prestal svoje (2 od 4 na ETH),
stopnjevana velikost pa strožje (3 od 4). Po enotnem merilu Donchian **ne
prestane**.

Uporabim pet pogojev iz §3 na **vseh** kandidatih in izdelam eno tabelo. Brez tega
je izbira odvisna od tega, kateri test je bil kdaj napisan.

### Faza 1 — izvedba ~3 h

| | kaj |
|---|---|
| 1a | `strategy.py`: `target_alloc` postane `100 × k/3`, ne 0/100 |
| 1b | vstopni prag z »vsi trije« na »vsaj eden« |
| 1c | **razčistiti `use_vol_sizing` in `target_vol_pct`** — sta v configu in ju stroj stanj ignorira; stopnjevanje je oblika velikosti pozicije, zato to razmerje ne sme ostati nejasno |
| 1d | **dashboard prikazuje binarno alokacijo** — popraviti na 0/33/67/100 % |
| 1e | referenco **na novo zamrzniti** z zapisom, zakaj — prva namerna sprememba vedenja |

### Faza 2 — preveriti izvedbo ~1 h

- `test_reference.py` zelen proti **novi** referenci
- negativna kontrola mora še vedno zaznati spremembo
- revizija pogleda v prihodnost na novi različici
- produkcijski motor mora dati **iste številke kot harness** — če ne, ustaviti

### Faza 3 — robustnost brez novih pravil ~5 h

Na **novi** strategiji, ne na stari:

| | kaj |
|---|---|
| 3a | 4-urni bari |
| 3b | obdobje po ETF (od 2024-01) |
| 3c | izvedba po **odprtju naslednjega dne** namesto po zaključku |
| 3d | vir podatkov: Binance / Coinbase / Yahoo |

**3c je pri tej spremembi pomembnejša kot prej**, ker je poslov dvakrat več.

### Faza 4 — poštena karakterizacija ~4 h

- deflacionirani Sharpe pri ~225 poskusih
- sodelovanje v padcih proti statičnemu 40 % BTC / 60 % gotovina
- MinTRL
- pošteno pričakovanje naprej z intervalom

### Faza 5 — poročilo in konec ~3 h

Končno poročilo, **izrecen seznam nedokazanega**, pravilo za ponovno odpiranje.

**Skupaj ~17 ur.**

---

## 6. Kaj je treba povedati sodelavcem

**Operativno:** poslov je dvakrat več in so manjši. Namesto »noter ali ven« bo
portfelj pogosto na 33 ali 67 %. To je sprememba v izvedbi, ne le v backtestu.

**Statistično:** interval zaupanja **še vedno objame ničlo** ([−0,030, +1,002]) in
MCS ne loči med različicami. Primer je **pet neodvisnih preverb, ki kažejo isto**,
ne dokazan učinek. Stoji na ~20 poslih.

**Zakaj vseeno:** ker je edino, kar je prestalo vsa merila hkrati, ker je čas v
trgu enak in torej ni artefakt, in ker zdrži tudi trikratno provizijo.

---

## 7. Kaj bi me ustavilo

- če produkcijska izvedba ne da **istih številk** kot harness
- če se pri izvedbi po odprtju naslednjega dne (3c) prednost sesuje
- če deflacionirani Sharpe pri 225 poskusih pade pod 0
