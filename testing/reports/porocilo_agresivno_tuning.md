# Momentum — testiranje predlogov za več upside-a

## Slovarček (na hitro)

- **Exposure** — kolikšen del kapitala je v povprečju v coinu (ostalo v cashu/stablecoinu).
  35 % = v povprečju 35 % v BTC. Nizko, ker strategija večino časa čaka ali drži zmanjšano
  pozicijo. Nizek exposure = ujameš manj rasti, a manj tvegaš.
- **Trailing stop** — stop-loss ki sledi ceni navzgor. Zapomni si najvišjo ceno od vstopa;
  če cena pade za X % pod ta vrh, izstopiš. Zaklene dobiček. Primer (12 %): vstop 100,
  vrh 150 → stop na 132; pade na 132 → izstop. Širši = daš več prostora, izstopiš kasneje.
- **Re-entry lock** — koliko dni po izstopu moraš počakati preden lahko spet vstopiš. Manjši
  = hitreje nazaj v trend.
- **Bear-cut** — kolikšno pozicijo držiš, ko je trg v medvedjem režimu (pod padajočo 200MA).
  50 = pol pozicije. Nižji = manj izpostavljen v bear trgu.
- **Holdout (HO)** — obdobje 2025+ ki ga pri nastavljanju NISMO gledali. Ločen test na
  svežih podatkih (proti overfittingu). CAGR tam je negativen, ker je bilo bear obdobje —
  pomembna je relativna primerjava med variantami.
- **CAGR** letni donos · **Sharpe** donos/volatilnost · **Sortino** donos/negativna
  volatilnost · **Calmar** CAGR/max drawdown · **MaxDD** največji padec od vrha.

Vsaka vrstica spodaj = **cela baseline strategija, spremenjen samo tisti en parameter** (razen
kombinacij "Agresivno"/"Priporočeno", kjer sta 2–3). Baseline = trailing 12, re-entry 4,
bear-cut 50 (kot v Pine).

---

## Kje se parameter sploh premakne (širok sweep, BTC, cela zgodovina)

Prva stvar ki jo je treba vedeti: **ne testiraj vrednosti kjer se nič ne premakne.** Tu je
kje ima vsak vzvod dejanski učinek:

**Trailing stop** — nad 20 se **nasiti** (20 = 25 = 30 identično; tako širok stop nikoli ne
sproži, prej izstopiš iz drugih razlogov). Med 12 in 20 je skoraj ravno. Akcija je pri
**tesnem koncu**:
| trailing | 8 | 10 | 12 | 15 | 20 | 25 | 30 |
|---|---|---|---|---|---|---|---|
| Calmar | 0.80 | **0.85** | 0.78 | 0.76 | 0.81 | 0.81 | 0.81 |
| MaxDD | −33% | −37% | −38% | −38% | −38% | −38% | −38% |

→ tvoji 15/18/20 so bili ravno v ravni coni — zato skoraj brez razlike. Smiselno testirati:
**8, 10, 12, 15** (in ne nič nad 20). Iskreno: to je **šibek vzvod**, premika malo.

**Re-entry lock** — oster prelom med 2 in 4:
| re-entry | 1 | 2 | 4 | 6 | 8 | 12 |
|---|---|---|---|---|---|---|
| CAGR | 36% | **36%** | 30% | 31% | 30% | 28% |
| Calmar | 0.94 | **0.95** | 0.78 | 0.82 | 0.80 | 0.75 |

→ to je **pravi vzvod**. Hitro (1–2) je jasno boljše od 4. Smiselno testirati: **1, 2, 3, 4**
(nad 4 je ravno in slabše).

**Bear-cut** — monotono, **nižje je bolje**:
| bear-cut | 0 | 25 | 50 | 75 | 100 |
|---|---|---|---|---|---|
| Calmar | 0.83 | **0.92** | 0.78 | 0.67 | 0.59 |
| MaxDD | −36% | **−33%** | −38% | −43% | −48% |

→ **25 % je sweet spot** (višji Calmar, nižji drawdown). Kolegov predlog (60–70) je točno
narobe — več bear-exposure = večji drawdown. Smiselno testirati: **0, 25, 50** (in NE višje).

---

## Priporočilo (popravljeno glede na širok sweep)

1. **Re-entry lock 4 → 2** — glavna sprememba. CAGR 30 → 36 %, Calmar 0.78 → 0.95, drawdown
   isti. Jasen win na BTC in drži tudi na holdoutu.
2. **Bear-cut 50 → 25** — vredno resno pogledati. Calmar 0.78 → 0.92, drawdown se celo
   izboljša (−38 → −33 %). Obratna smer od kolegovega predloga, a številke so jasne.
3. **Trailing stop** — pusti pri miru ali daj 10. Šibek vzvod, nad 20 mrtev. Ne izgubljaj
   časa s 15/18/20 (ravna cona).

Torej: **re-entry 2 + bear-cut 25** je bolj obetavna kombinacija kot karkoli s širšim trailing
stopom. Naslednji korak — testiram to kombinacijo pooled + holdout, da potrdim da drži čez
vse coine, ne le BTC.

Opomba: vse te številke so BTC/cela zgodovina za jasnost učinka; končno odločitev vzamemo iz
pooled + holdout. In 12/4/50 so iz Pine — če kaj sprejmemo, popravim še Pine.
