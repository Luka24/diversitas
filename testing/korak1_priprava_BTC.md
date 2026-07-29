# Korak 1 — Priprava: občutljivost parametrov in zaklep (samo BTC)

_Zapisano pred izvedbo. Obseg: samo BTC, varianta `momentum`._

---

## 0. Pošteno: kaj že obstaja

- `testing/scripts/run_sensitivity.py` je **že implementiran** in je bil že pognan — obstaja
  `testing/reports/phase3_report.md` (2026-07-05) z zaključkom: **momentum ima 0 krhkih (interior-sharp)
  parametrov**, edge-optimi vlečejo k agresiji, a jih ne lovimo.
- Torej Korak 1 **ni gradnja od nič**: je (a) reprodukcija na svežih zamrznjenih podatkih, (b) prilagoditev
  na **samo BTC**, (c) uporaba pravila zaklepa in (d) potrditev na hold-out.

## 1. Cilj

- Za vsak parameter ugotoviti tip: **plato (robusten)** / **oster vrh (krhek)** / **edge (vleče k robu =
  in-sample skušnjava)**.
- **Zakleniti** vrednosti po pravilu (sredina platoja), ne loviti vrhov/edge.
- Pošteno odgovoriti na overfitting skrb (15 ročnih parametrov).

## 2. Obseg

- **Asset:** samo BTC (zavestna izbira uporabnika).
- **Varianta:** `momentum`.
- **Parametri (9, ki jih harness sweepa):** `track_period`, `track_buf_pct`, `trail_pct`,
  `bear_size_cut`, `reentry_hold`, `er_thresh`, `blowoff_dist_pct`, `target_vol_pct`, `confirm_bars`
  (obstoječi razponi v `GRIDS["momentum"]`).
- **Izven obsega (konvencije, nizko tveganje):** `rsi_len=14`, `ma_fast_len=20`, `ma_reg_len=100`,
  `ema_slow_len=55`, `vol_lookback=20`, `ma_slope=5`, `er_len=10`, `exit_grace_bars=1`. Standardne
  vrednosti — ne sweepamo. **Kandidati za razširitev** (nekonvencijski, a nesweepani): `vol_shock_mul=1.5`,
  `track_slope_bars=7`. Če želiš, ju dodam.

## 3. Metoda (kaj in zakaj profesionalno)

- **OFAT (one-factor-at-a-time):** vsak parameter posebej, ostali na default.
  *Zakaj:* hitro, jasno pokaže občutljivost; standard za prvi robustness pass.
  *Omejitev:* ne ujame interakcij → te pokrijeta walk-forward + CPCV v kasnejši fazi (ne tu).
- **Metrika: Calmar** (donos / max drawdown) — ker je jedro produkta drawdown. Poročam tudi Sortino, MaxDD, št. trade-ov.
- **Train/hold-out rez:** `DESIGN_END = 2025-03-31`. Sweep na **design** (do 2025-03-31);
  **hold-out** (po 2025-03-31) ostane **v karanteni**.
- **Klasifikacija optimuma** (obstoječa logika): `interior-flat` (robust plato) · `interior-sharp`
  (krhek vrh = problem) · `edge-low/high` (vleče k robu = in-sample skušnjava k agresiji — **NE lovimo**).
- **Multiple testing:** vsak scored config šteje v trial counter → napaja Deflated Sharpe hurdle kasneje
  (zavedanje data-snoopinga).

## 4. Pravilo zaklepa + potrditev na hold-out

Za vsak parameter:
1. **`interior-flat`** → zakleni **sredino platoja** (ne najvišjo točko).
2. **`edge-*`** → NE sledimo; ostane pri **default/konvenciji**.
3. **`interior-sharp`** → rdeča zastava; diagnosticiramo posebej.

**Ključno proti peekingu:** plato in izbrano vrednost določim na **design**, nato **potrdim, da izbrana
vrednost leži v dobrem območju tudi na hold-out** (po 2025-03-31). Šele takrat zaklenem. Hold-out se
uporabi le za potrditev, nikoli za izbiro.

**Rezultat:** tabela `parameter → zaklenjena vrednost → tip optimuma → obrazložitev`.

## 5. Predpogoji za izvedbo

- **venv:** `.venv/Scripts/python.exe` (obstaja ✓).
- **Podatki:** `testing/data/` **ne obstaja** → najprej **zamrznemo BTC** (`dataio.freeze_all` /
  `freeze`), kar enkrat potegne candle s spleta in shrani `parquet` (frozen = reproducibilno).
  *To je edina outward (network) akcija.*
- **BTC-only izvedba:** obstoječa skripta ima `ASSETS=["BTC","ETH","SOL"]` in cross-asset agreement čez
  ETH/SOL. Za BTC-only naredim **tanko, ne-destruktivno različico** (ali BTC-scoped runner), ki obdrži
  robustnost-klasifikacijo, a izpusti cross-asset stolpec. **Deljene skripte ne spreminjam trajno.**

## 6. Izhod / sprejemni kriterij

- **Izhod:** osvežen BTC sensitivity summary (CSV + PNG-ji) in kratek povzetek: št. krhkih (cilj **0**),
  seznam edge, plato-sredine; **zaklenjen nabor parametrov (BTC)**, potrjen na hold-out.
- **Kriterij uspeha Koraka 1:** noben parameter `interior-sharp` na design **IN** izbrane vrednosti se ne
  sesujejo na hold-out. Če to velja → povemo: *"strategija je na parametrih robustna"* (močnejša izjava
  od "to so najboljši parametri").

## 7. Tveganja / iskrenost

- OFAT ne vidi **interakcij** parametrov (pozneje WFO/CPCV).
- **Konvencijskih parametrov ne testiramo** (nizko tveganje, a priznano).
- **Samo BTC → ni cross-asset kontrole** (prej ETH/SOL). To je zavestna izbira, a oslabi "one-lucky-coin"
  obrambo — eksplicitno omenim v zaključku.

## 8. Izvedbeno zaporedje (ko potrdiš)

1. **Zamrzni BTC** podatke (network, enkrat).
2. **Poženi BTC sensitivity** (design split) → summary + grafi.
3. **Interpretiraj:** krhki / edge / plato.
4. **Zakleni** vrednosti (sredina platoja) in **potrdi na hold-out**.
5. **Zapiši** BTC report + zaklenjen nabor; nato Korak 2 (Chow test).
