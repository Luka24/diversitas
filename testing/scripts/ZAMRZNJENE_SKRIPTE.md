# Skripte, ki merijo motor PRED poenostavitvijo

Poenostavitev (3. korak, 2026-08-03) je iz `LeanConfig` odstranila štiri
parametre — `min_dist_entry_pct`, `ma_med_len`, `vol_shock_mul`, `vol_lookback` —
in iz strategije tri pogoje: `dist_entry_ok`, `above_ma_med` v `bull_condition`
ter izstop `vol_shock`.

Spodnje skripte so te parametre in stolpce uporabljale, ker so **prav njih
merile**. Njihovi rezultati so že zapisani v `testing/data/*.json` in v obeh
poročilih. Skripte namenoma **niso** predelane: če bi jim odstranjene pogoje
odvzel, ne bi več merile tistega, kar so izmerile, številke v poročilih pa se ne
bi več ujemale z ničimer, kar bi kdo lahko pognal.

Če jih hočeš pognati znova, jih poženi na stanju pred poenostavitvijo:

    git stash            # ali: git checkout -b arhiv 26e2d71
    git checkout 26e2d71 -- lean/diversitas/

Zadnji commit pred poenostavitvijo je **`26e2d71`**.

## Kako se pokvarijo

Pokvarijo se **glasno**, ne tiho — to je bilo namerno preverjeno:

* `engine.make_config` vrže `ValueError: unknown config keys {...}` takoj, ko mu
  podaš odstranjen parameter. Nobena skripta torej ne more več izpisati številke
  za »vol-shock izklopljen«, medtem ko bi bil vol-shock v resnici prižgan.
  Ravno to bi se zgodilo, če bi neznane ključe tiho spregledal.
  Zavarovano v `testing/tests/test_simplification.py`.
* Skripte, ki berejo stolpca `df["vol_shock"]` ali `df["dist_entry_ok"]`, vržejo
  `KeyError`.

## Seznam

| Skripta | Kaj je merila |
|---|---|
| `ablation.py` | vklop/izklop posameznega pravila + pometanje po ključih |
| `ablation_full.py` | ablacija vseh pogojev; vir sprejemnih številk 3. koraka |
| `dead_rules_robust.py` | 151 nastavitev — dokaz, da vol_shock ni mrtev povsod |
| `merge_verdict.py` | ali si vol_shock zasluži svoja dva parametra na ravni ansambla |
| `event_study.py` | pogojni donosi naprej po posameznem pogoju |
| `exit_rules.py` | blow-off proti raztegnjenim dnevom; prag vol-shocka |
| `ensemble.py`, `curves.py`, `intraday_check.py`, `wf_refit.py` | uporabljajo `vol_shock_mul=999` kot izklop |
| `features.py`, `improvements.py`, `run_*.py` | starejša vzporedna izvedba značilk |
| `build_report_pogoji.py`, `build_report_parametri.py` | zgradita poročili iz že izračunanih JSON-ov |

## Kaj ostaja živo

`engine.py`, `freeze_reference.py`, `lookahead_audit.py` in vse v
`testing/tests/` delujejo na poenostavljenem motorju in so bili po posegu
pognani znova.
