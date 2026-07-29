# Korak 1 — Rezultati in interpretacija (samo BTC)

_Kritičen pregled: ali je bil postopek pravilen, ali so podatki pričakovani._

---

## 1. Kaj smo naredili

- **Obseg:** BTC, varianta `momentum`, metrika Calmar (drawdown-fokus).
- **Rez:** design 2019-06-08 → 2025-03-31 (2124 dni) · hold-out 2025-04-01 → 2026-07-20 (476 dni, karantena).
- **Koraki:** OFAT sweep **vseh 19 parametrov** → klasifikacija robustnosti → SD-pas diagnostika → hold-out potrditev → analiza mrtve kode → **odstranitev `volShock`**.

## 2. Rezultati (podatki)

**Default profil (design):** Calmar **1.03** · Sharpe **1.19** · Sortino **1.62** · MaxDD **−38 %** · 31 trade-ov · izpostavljenost **35 %**.
→ Ustreza nizko-izpostavljenemu trend-overlayu. **Pričakovano.**

**Občutljivost:** **0 krhkih (interior-sharp) parametrov** čez vseh 19.
- ⚠ Prvotna metrika ("2 soseda znotraj 70 %") je bila groba. SD-pas diagnostika pokaže bolj pošteno sliko:
  - **6 inertnih parametrov** (Calmar-razpon < 0.10 — komaj kaj počnejo).
  - Večina "najboljših" vrednosti je v sivi coni **1–2 SD** (ne čisti platoji).
  - **Ključno: defaulti ležijo znotraj ~1 SD povprečja** (z_def majhen) → **niso cherry-picked vrhovi.**

**Redundanca (test skrajnih vrednosti + koda):**
- `vol_shock` — **dokazljivo mrtvo** (izhod `else if volShock` je nedosegljiv, ker `volShock` zahteva `belowTL`, ta pa izstopi prej). Potrjeno na BTC/ETH/SOL, vsa zgodovina (ΔCalmar 0.000). → **odstranjeno** (Pine + Python; rezultat identičen).
- `ma_slope` — skoraj mrtvo, a smiselno (prepreči lažni bear ob plitvem dipu). → **obdržano + zamrznjeno**, ne tuniramo.

**Hold-out (karantena):** default Calmar −0.22 / Sortino −0.29 · predlagane spremembe 0.02 / 0.16 — oboje plosko/negativno, **n=6 trade-ov** → prešibko za potrditev sprememb.

## 3. Je bil postopek pravilen? (kritična presoja)

**Kar je dobro:**
- Pravilna train/hold-out karantena (rez 2025-03).
- Sweep **vseh** parametrov (po popravku).
- Mrtva koda preverjena čez več coinov + vso zgodovino, in odstranjena z dokazom ničelnega vpliva.
- Disciplina: edge/agresijskih vrednosti nismo lovili; ohranili defaulte.

**Omejitve (iskreno):**
- **OFAT ne vidi interakcij** parametrov → "noben ni krhek posamično" ≠ "robusten skupaj". Skupna robustnost = CPCV/površina (pozneje).
- Prvotna metrika robustnosti je bila groba; popravljena s SD-pasom + inert flag. Naslov "0 krhkih" je sprva preveč obljubljal.
- **Samo BTC** → ni cross-asset kontrole (zavestna izbira).
- Sweep je Calmar-only, in-sample.
- **Hold-out prešibek** (1.3 leta, post-ETF, brez zime) za potrjevanje majhnih izboljšav — njegova vloga je **lovljenje katastrof**, ne potrjevanje.
- Okno podedovano (2019+, `_BARS` cap → brez zime 2018); relevantnost stare zgodovine je odprto vprašanje (→ Korak 2).

## 4. So podatki pričakovani?

**Da, večinoma:**
- Design profil (Calmar ~1, MaxDD −38 %, ~31 trade-ov, expo ~35 %) = tipičen za low-exposure trend overlay.
- **Hold-out slabost (plosko/negativno) je PRIČAKOVANA** — post-ETF, brez zime → zaščita nima kje "izplačati"; momentum se je morda oslabil (→ Korak 2). Ni alarmantno.
- **Edge parametri vsi vlečejo k agresiji** = klasičen in-sample BTC vzorec. Pričakovano.
- **0 nožastih parametrov** = verjetno za multi-filter momentum overlay (mnogo parametrov so glajenja/filtri z majhnim posamičnim učinkom).
- Mrtva `vol_shock` / skoraj-mrtva `ma_slope` = pričakovano ob pregledu logike kode.

## 5. Sklep Koraka 1

- **Odločitev:** ohranimo vse privzete vrednosti; **odstranili** mrtvi `vol_shock` (−1 parameter, ničelni vpliv); `ma_slope` zamrznjen.
- **Poštena izjava:** *"Ni nožastih parametrov; defaulti so sredinski (ne cherry-picked); ena mrtva veja odstranjena. To PODPIRA — a OFAT sam ne DOKAŽE — parametrsko robustnost. Skupna robustnost in OOS zaupanje prideta pozneje."*
- Skladno z WF ugotovitvijo (tuning ≈ default ≈ B&H).

## 6. Česa Korak 1 NE dokaže (da smo pošteni)

- Da ima strategija **edge** (donos/tveganje značilnost → Korak 3: bootstrap CI).
- Da je stara zgodovina **relevantna** / ni strukturnega preloma (→ Korak 2: Chow/regime).
- **Skupne (multi-param) robustnosti** (→ CPCV, če kdaj optimiziramo).
