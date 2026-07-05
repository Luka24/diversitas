# Diversitas — Full per-parameter results matrix

**Date:** 2026-07-05 · Pooled median across 8 assets. Design set (≤2025-03-31) vs hold-out (2025-04→2026-07). Every feature at EVERY swept value; %-improvement is design Calmar vs that variant's baseline. `holdout_better` = beats baseline hold-out Calmar.

## lean — baseline design Calmar 0.44, hold-out -0.09

| Feature | Param | Value | Design Calmar | Δ% | Design Sharpe | Design MaxDD | Hold-out Calmar | Hold-out MaxDD | HO better? |
|---|---|---|---|---|---|---|---|---|---|
| track_period | track_period | 45 | 0.64 | +43% | 0.83 | -58% | 0.01 | -20% | ★ |
| track_period | track_period | 50 | 0.48 | +9% | 0.76 | -57% | -0.01 | -23% | ★ |
| track_period | track_period | 55 | 0.50 | +13% | 0.78 | -61% | -0.05 | -24% | ★ |
| track_period | track_period | 60 | 0.36 | -18% | 0.69 | -57% | -0.17 | -23% |  |
| track_period | track_period | 65 | 0.60 | +35% | 0.84 | -53% | -0.17 | -23% |  |
| track_period | track_period | 70 | 0.56 | +27% | 0.85 | -58% | -0.16 | -23% |  |
| track_period | track_period | 75 | 0.44 | +0% | 0.76 | -61% | -0.09 | -26% |  |
| track_period | track_period | 80 | 0.51 | +16% | 0.76 | -53% | 0.12 | -26% | ★ |
| track_period | track_period | 85 | 0.42 | -5% | 0.69 | -57% | 0.21 | -28% |  |
| track_period | track_period | 90 | 0.33 | -25% | 0.65 | -66% | 0.23 | -28% |  |
| track_buf_pct | track_buf_pct | 1.0 | 0.52 | +17% | 0.83 | -58% | -0.02 | -23% | ★ |
| track_buf_pct | track_buf_pct | 1.5 | 0.43 | -3% | 0.75 | -61% | -0.05 | -23% |  |
| track_buf_pct | track_buf_pct | 2.0 | 0.43 | -3% | 0.75 | -61% | -0.05 | -24% |  |
| track_buf_pct | track_buf_pct | 2.5 | 0.42 | -5% | 0.74 | -61% | -0.07 | -26% |  |
| track_buf_pct | track_buf_pct | 3.0 | 0.44 | +0% | 0.76 | -61% | -0.09 | -26% |  |
| track_buf_pct | track_buf_pct | 3.5 | 0.44 | -2% | 0.75 | -61% | -0.09 | -26% |  |
| track_buf_pct | track_buf_pct | 4.0 | 0.41 | -9% | 0.71 | -60% | -0.10 | -26% |  |
| track_buf_pct | track_buf_pct | 4.5 | 0.49 | +11% | 0.76 | -56% | -0.04 | -26% | ★ |
| track_buf_pct | track_buf_pct | 5.0 | 0.51 | +16% | 0.77 | -58% | -0.07 | -26% | ★ |
| reentry_hold | reentry_hold | 5 | 0.41 | -7% | 0.73 | -65% | -0.25 | -26% |  |
| reentry_hold | reentry_hold | 8 | 0.30 | -32% | 0.61 | -63% | -0.25 | -26% |  |
| reentry_hold | reentry_hold | 10 | 0.35 | -22% | 0.67 | -63% | -0.25 | -26% |  |
| reentry_hold | reentry_hold | 12 | 0.38 | -13% | 0.68 | -61% | -0.25 | -26% |  |
| reentry_hold | reentry_hold | 15 | 0.44 | +0% | 0.76 | -61% | -0.09 | -26% |  |
| reentry_hold | reentry_hold | 18 | 0.40 | -11% | 0.69 | -61% | -0.09 | -26% |  |
| reentry_hold | reentry_hold | 20 | 0.41 | -8% | 0.70 | -61% | -0.09 | -26% |  |
| reentry_hold | reentry_hold | 25 | 0.27 | -38% | 0.57 | -61% | -0.09 | -26% |  |
| confirm_bars | confirm_bars | 1 | 0.39 | -13% | 0.70 | -66% | 0.09 | -26% |  |
| confirm_bars | confirm_bars | 2 | 0.39 | -11% | 0.70 | -65% | 0.07 | -26% |  |
| confirm_bars | confirm_bars | 3 | 0.44 | +0% | 0.76 | -61% | -0.09 | -26% |  |
| confirm_bars | confirm_bars | 4 | 0.44 | -1% | 0.69 | -57% | -0.20 | -26% |  |
| confirm_bars | confirm_bars | 5 | 0.33 | -25% | 0.62 | -60% | -0.27 | -26% |  |
| exit_grace_bars | exit_grace_bars | 1 | 0.46 | +4% | 0.79 | -56% | -0.05 | -24% | ✓ |
| exit_grace_bars | exit_grace_bars | 2 | 0.43 | -3% | 0.74 | -61% | -0.17 | -26% |  |
| exit_grace_bars | exit_grace_bars | 3 | 0.44 | +0% | 0.76 | -61% | -0.09 | -26% |  |
| exit_grace_bars | exit_grace_bars | 4 | 0.48 | +8% | 0.76 | -56% | -0.04 | -26% | ✓ |
| exit_grace_bars | exit_grace_bars | 5 | 0.43 | -3% | 0.72 | -56% | -0.02 | -26% |  |
| er_thresh | er_thresh | 0.1 | 0.42 | -5% | 0.74 | -64% | -0.00 | -26% |  |
| er_thresh | er_thresh | 0.15 | 0.42 | -4% | 0.75 | -65% | -0.00 | -26% |  |
| er_thresh | er_thresh | 0.2 | 0.38 | -14% | 0.70 | -66% | -0.00 | -26% |  |
| er_thresh | er_thresh | 0.25 | 0.36 | -18% | 0.68 | -63% | -0.00 | -26% |  |
| er_thresh | er_thresh | 0.3 | 0.44 | +0% | 0.76 | -61% | -0.09 | -26% |  |
| er_thresh | er_thresh | 0.35 | 0.40 | -10% | 0.70 | -62% | -0.24 | -26% |  |
| er_thresh | er_thresh | 0.4 | 0.40 | -10% | 0.67 | -54% | -0.08 | -26% |  |
| blowoff_dist_pct | blowoff_dist_pct | 15 | 0.50 | +12% | 0.74 | -60% | -0.24 | -25% |  |
| blowoff_dist_pct | blowoff_dist_pct | 20 | 0.37 | -17% | 0.68 | -61% | -0.13 | -25% |  |
| blowoff_dist_pct | blowoff_dist_pct | 25 | 0.44 | +0% | 0.76 | -61% | -0.09 | -26% |  |
| blowoff_dist_pct | blowoff_dist_pct | 30 | 0.54 | +22% | 0.85 | -61% | -0.05 | -26% | ★ |
| blowoff_dist_pct | blowoff_dist_pct | 35 | 0.53 | +19% | 0.83 | -61% | -0.05 | -26% | ★ |
| blowoff_dist_pct | blowoff_dist_pct | 40 | 0.49 | +11% | 0.73 | -62% | -0.05 | -26% | ★ |
| target_vol_pct | target_vol_pct | 40 | 0.44 | +0% | 0.76 | -61% | -0.09 | -26% |  |
| target_vol_pct | target_vol_pct | 50 | 0.44 | +0% | 0.76 | -61% | -0.09 | -26% |  |
| target_vol_pct | target_vol_pct | 60 | 0.44 | +0% | 0.76 | -61% | -0.09 | -26% |  |
| target_vol_pct | target_vol_pct | 70 | 0.44 | +0% | 0.76 | -61% | -0.09 | -26% |  |
| target_vol_pct | target_vol_pct | 80 | 0.44 | +0% | 0.76 | -61% | -0.09 | -26% |  |
| target_vol_pct | target_vol_pct | 90 | 0.44 | +0% | 0.76 | -61% | -0.09 | -26% |  |
| vol_shock_mul | vol_shock_mul | 1.2 | 0.53 | +20% | 0.82 | -60% | -0.07 | -26% | ★ |
| vol_shock_mul | vol_shock_mul | 1.5 | 0.44 | +0% | 0.76 | -61% | -0.09 | -26% |  |
| vol_shock_mul | vol_shock_mul | 1.8 | 0.43 | -3% | 0.74 | -61% | -0.07 | -26% |  |
| vol_shock_mul | vol_shock_mul | 2.0 | 0.44 | -1% | 0.75 | -61% | -0.07 | -26% |  |
| vol_shock_mul | vol_shock_mul | 2.5 | 0.44 | -0% | 0.75 | -61% | -0.07 | -26% |  |
| atr_buffer | k | 1.5 | 0.54 | +22% | 0.77 | -52% | 0.22 | -28% | ★ |
| atr_buffer | k | 2.0 | 0.26 | -42% | 0.54 | -59% | -0.13 | -33% |  |
| atr_buffer | k | 2.5 | 0.21 | -52% | 0.49 | -57% | -0.32 | -35% |  |
| atr_buffer | k | 3.0 | 0.31 | -31% | 0.55 | -56% | -0.44 | -35% |  |
| atr_buffer_asym | 2.5/1.5 | 2.5/1.5 | 0.41 | -7% | 0.61 | -49% | 0.17 | -28% |  |
| atr_blowoff | pct | 90.0 | 0.41 | -7% | 0.71 | -61% | -0.24 | -25% |  |
| atr_blowoff | pct | 95.0 | 0.37 | -17% | 0.68 | -61% | -0.24 | -26% |  |
| atr_blowoff | pct | 97.5 | 0.42 | -6% | 0.72 | -61% | -0.04 | -26% |  |
| atr_blowoff | pct | 99.0 | 0.61 | +38% | 0.87 | -64% | -0.05 | -26% | ★ |
| volz_buffer | coef | 0.3 | 0.46 | +3% | 0.77 | -61% | -0.21 | -26% |  |
| volz_buffer | coef | 0.5 | 0.45 | +2% | 0.77 | -61% | 0.03 | -24% | ✓ |
| volz_buffer | coef | 0.8 | 0.48 | +7% | 0.79 | -61% | 0.03 | -24% | ✓ |
| ema_volshock | - | on | 0.44 | +0% | 0.76 | -61% | -0.07 | -26% | ✓ |
| parkinson_vol | - | on | 0.48 | +8% | 0.77 | -60% | -0.07 | -26% | ✓ |
| kelly | fraction | 1.0 | 0.37 | -17% | 0.61 | -50% | 0.01 | -11% |  |
| kelly | fraction | 0.5 | 0.47 | +6% | 0.73 | -41% | 0.05 | -5% | ✓ |
| kelly | fraction | 0.25 | 0.47 | +5% | 0.71 | -38% | 0.08 | -3% | ✓ |
| weekend_skip | - | on | 0.51 | +15% | 0.79 | -61% | -0.02 | -26% | ★ |
| profit_taking | l1/l2 | 50/100 | 0.41 | -7% | 0.72 | -61% | -0.09 | -23% |  |
| profit_taking | l1/l2 | 30/60 | 0.40 | -11% | 0.70 | -60% | -0.08 | -23% |  |
| profit_taking | l1/l2 | 75/150 | 0.42 | -5% | 0.74 | -61% | -0.09 | -24% |  |
| dd_brake | dd/cut | 20/0.3 | 0.45 | +2% | 0.68 | -49% | -0.30 | -19% |  |
| dd_brake | dd/cut | 20/0.5 | 0.51 | +15% | 0.73 | -52% | -0.26 | -23% |  |
| dd_brake | dd/cut | 30/0.3 | 0.44 | -0% | 0.70 | -56% | -0.14 | -24% |  |
| dd_brake | dd/cut | 30/0.5 | 0.47 | +6% | 0.73 | -58% | -0.13 | -23% |  |
| dd_brake | dd/cut | 40/0.3 | 0.52 | +16% | 0.80 | -58% | -0.07 | -23% | ★ |
| dd_brake | dd/cut | 40/0.5 | 0.56 | +27% | 0.81 | -59% | -0.07 | -24% | ★ |
| dynamic_reentry | - | volz | 0.44 | +0% | 0.76 | -61% | -0.09 | -26% |  |

## momentum — baseline design Calmar 1.00, hold-out -0.21

| Feature | Param | Value | Design Calmar | Δ% | Design Sharpe | Design MaxDD | Hold-out Calmar | Hold-out MaxDD | HO better? |
|---|---|---|---|---|---|---|---|---|---|
| track_period | track_period | 25 | 1.03 | +4% | 1.05 | -35% | -0.30 | -28% |  |
| track_period | track_period | 30 | 0.99 | -1% | 1.13 | -39% | -0.06 | -26% |  |
| track_period | track_period | 35 | 1.00 | +0% | 1.05 | -38% | -0.21 | -24% |  |
| track_period | track_period | 40 | 0.95 | -5% | 1.02 | -42% | -0.17 | -23% |  |
| track_period | track_period | 45 | 0.82 | -17% | 1.00 | -42% | -0.31 | -25% |  |
| track_period | track_period | 50 | 0.75 | -25% | 0.99 | -41% | -0.45 | -21% |  |
| track_period | track_period | 55 | 0.87 | -12% | 0.98 | -35% | -0.44 | -26% |  |
| track_buf_pct | track_buf_pct | 1.0 | 0.99 | -0% | 1.04 | -38% | -0.19 | -26% |  |
| track_buf_pct | track_buf_pct | 1.5 | 0.96 | -4% | 1.02 | -38% | -0.17 | -23% |  |
| track_buf_pct | track_buf_pct | 2.0 | 1.00 | +0% | 1.05 | -38% | -0.21 | -24% |  |
| track_buf_pct | track_buf_pct | 2.5 | 0.95 | -5% | 1.03 | -39% | -0.25 | -25% |  |
| track_buf_pct | track_buf_pct | 3.0 | 0.91 | -9% | 1.00 | -39% | -0.27 | -25% |  |
| track_buf_pct | track_buf_pct | 3.5 | 0.87 | -13% | 0.99 | -40% | -0.34 | -27% |  |
| track_buf_pct | track_buf_pct | 4.0 | 0.86 | -14% | 0.98 | -42% | -0.31 | -26% |  |
| reentry_hold | reentry_hold | 2 | 0.92 | -8% | 1.02 | -41% | -0.23 | -24% |  |
| reentry_hold | reentry_hold | 3 | 1.00 | -0% | 0.98 | -39% | -0.21 | -24% |  |
| reentry_hold | reentry_hold | 4 | 1.00 | +0% | 1.05 | -38% | -0.21 | -24% |  |
| reentry_hold | reentry_hold | 6 | 0.67 | -33% | 0.89 | -41% | -0.23 | -24% |  |
| reentry_hold | reentry_hold | 8 | 0.47 | -53% | 0.70 | -40% | -0.21 | -24% |  |
| reentry_hold | reentry_hold | 10 | 0.59 | -41% | 0.85 | -43% | -0.23 | -24% |  |
| confirm_bars | confirm_bars | 1 | 1.00 | +0% | 1.05 | -38% | -0.21 | -24% |  |
| confirm_bars | confirm_bars | 2 | 0.65 | -35% | 0.88 | -38% | -0.27 | -25% |  |
| confirm_bars | confirm_bars | 3 | 0.48 | -52% | 0.73 | -39% | -0.04 | -20% |  |
| confirm_bars | confirm_bars | 4 | 0.56 | -44% | 0.84 | -42% | -0.01 | -20% |  |
| confirm_bars | confirm_bars | 5 | 0.51 | -49% | 0.77 | -38% | -0.29 | -18% |  |
| exit_grace_bars | exit_grace_bars | 1 | 1.00 | +0% | 1.05 | -38% | -0.21 | -24% |  |
| exit_grace_bars | exit_grace_bars | 2 | 1.05 | +5% | 1.09 | -39% | -0.24 | -25% |  |
| exit_grace_bars | exit_grace_bars | 3 | 0.96 | -3% | 1.08 | -42% | -0.37 | -27% |  |
| exit_grace_bars | exit_grace_bars | 4 | 0.94 | -6% | 1.08 | -42% | -0.34 | -27% |  |
| exit_grace_bars | exit_grace_bars | 5 | 0.85 | -15% | 1.05 | -42% | -0.38 | -27% |  |
| er_thresh | er_thresh | 0.1 | 0.78 | -22% | 0.97 | -42% | -0.12 | -24% |  |
| er_thresh | er_thresh | 0.15 | 0.94 | -6% | 1.05 | -40% | -0.12 | -22% |  |
| er_thresh | er_thresh | 0.2 | 0.94 | -6% | 1.03 | -38% | -0.19 | -23% |  |
| er_thresh | er_thresh | 0.25 | 1.00 | +0% | 1.05 | -38% | -0.21 | -24% |  |
| er_thresh | er_thresh | 0.3 | 0.91 | -9% | 1.00 | -39% | -0.27 | -24% |  |
| er_thresh | er_thresh | 0.35 | 0.86 | -14% | 0.98 | -39% | -0.25 | -24% |  |
| er_thresh | er_thresh | 0.4 | 0.81 | -19% | 0.88 | -40% | -0.24 | -23% |  |
| blowoff_dist_pct | blowoff_dist_pct | 15 | 0.95 | -5% | 1.06 | -38% | -0.27 | -24% |  |
| blowoff_dist_pct | blowoff_dist_pct | 20 | 1.00 | +0% | 1.05 | -38% | -0.21 | -24% |  |
| blowoff_dist_pct | blowoff_dist_pct | 25 | 0.96 | -3% | 1.04 | -38% | 0.01 | -24% |  |
| blowoff_dist_pct | blowoff_dist_pct | 30 | 1.06 | +6% | 1.09 | -38% | -0.14 | -24% | ✓ |
| blowoff_dist_pct | blowoff_dist_pct | 35 | 1.08 | +9% | 1.10 | -39% | -0.14 | -24% | ★ |
| blowoff_dist_pct | blowoff_dist_pct | 40 | 1.07 | +7% | 1.10 | -39% | -0.14 | -24% | ✓ |
| target_vol_pct | target_vol_pct | 40 | 0.93 | -7% | 1.04 | -32% | -0.24 | -21% |  |
| target_vol_pct | target_vol_pct | 50 | 0.96 | -4% | 1.05 | -36% | -0.23 | -23% |  |
| target_vol_pct | target_vol_pct | 60 | 1.00 | +0% | 1.05 | -38% | -0.21 | -24% |  |
| target_vol_pct | target_vol_pct | 70 | 1.03 | +3% | 1.07 | -41% | -0.24 | -25% |  |
| target_vol_pct | target_vol_pct | 80 | 1.08 | +8% | 1.09 | -43% | -0.26 | -26% |  |
| target_vol_pct | target_vol_pct | 90 | 1.13 | +13% | 1.11 | -44% | -0.28 | -26% |  |
| trail_pct | trail_pct | 6 | 0.74 | -26% | 1.00 | -36% | 0.18 | -20% |  |
| trail_pct | trail_pct | 8 | 0.94 | -6% | 1.08 | -36% | -0.01 | -23% |  |
| trail_pct | trail_pct | 10 | 0.86 | -14% | 0.96 | -39% | -0.19 | -24% |  |
| trail_pct | trail_pct | 12 | 1.00 | +0% | 1.05 | -38% | -0.21 | -24% |  |
| trail_pct | trail_pct | 14 | 0.88 | -12% | 1.02 | -41% | -0.23 | -25% |  |
| trail_pct | trail_pct | 16 | 0.75 | -25% | 0.97 | -44% | -0.21 | -24% |  |
| trail_pct | trail_pct | 18 | 0.84 | -16% | 1.01 | -44% | -0.21 | -24% |  |
| trail_pct | trail_pct | 20 | 0.86 | -14% | 1.01 | -46% | -0.21 | -24% |  |
| bear_size_cut | bear_size_cut | 0 | 0.93 | -7% | 1.02 | -43% | -0.16 | -21% |  |
| bear_size_cut | bear_size_cut | 25 | 1.08 | +8% | 1.07 | -39% | -0.21 | -22% | ★ |
| bear_size_cut | bear_size_cut | 50 | 1.00 | +0% | 1.05 | -38% | -0.21 | -24% |  |
| bear_size_cut | bear_size_cut | 75 | 0.88 | -12% | 1.02 | -40% | -0.25 | -27% |  |
| bear_size_cut | bear_size_cut | 100 | 0.78 | -22% | 0.97 | -41% | -0.29 | -30% |  |
| vol_shock_mul | vol_shock_mul | 1.2 | 1.00 | +0% | 1.05 | -38% | -0.21 | -24% |  |
| vol_shock_mul | vol_shock_mul | 1.5 | 1.00 | +0% | 1.05 | -38% | -0.21 | -24% |  |
| vol_shock_mul | vol_shock_mul | 1.8 | 1.00 | +0% | 1.05 | -38% | -0.21 | -24% |  |
| vol_shock_mul | vol_shock_mul | 2.0 | 1.00 | +0% | 1.05 | -38% | -0.21 | -24% |  |
| vol_shock_mul | vol_shock_mul | 2.5 | 1.00 | +0% | 1.05 | -38% | -0.21 | -24% |  |
| atr_buffer | k | 1.5 | 0.85 | -14% | 0.98 | -40% | -0.15 | -24% |  |
| atr_buffer | k | 2.0 | 0.70 | -29% | 0.90 | -41% | 0.13 | -19% |  |
| atr_buffer | k | 2.5 | 0.60 | -40% | 0.83 | -44% | 0.43 | -16% |  |
| atr_buffer | k | 3.0 | 0.66 | -34% | 0.77 | -29% | -0.06 | -15% |  |
| atr_buffer_asym | 2.5/1.5 | 2.5/1.5 | 0.63 | -37% | 0.86 | -43% | 0.43 | -16% |  |
| atr_blowoff | pct | 90.0 | 0.88 | -12% | 1.01 | -38% | -0.27 | -24% |  |
| atr_blowoff | pct | 95.0 | 0.95 | -5% | 1.07 | -38% | -0.21 | -24% |  |
| atr_blowoff | pct | 97.5 | 1.01 | +1% | 1.07 | -38% | -0.18 | -24% | ✓ |
| atr_blowoff | pct | 99.0 | 1.01 | +1% | 1.12 | -40% | -0.09 | -24% | ✓ |
| volz_buffer | coef | 0.3 | 1.01 | +1% | 1.05 | -38% | -0.19 | -25% | ✓ |
| volz_buffer | coef | 0.5 | 1.02 | +3% | 1.06 | -38% | -0.16 | -23% | ✓ |
| volz_buffer | coef | 0.8 | 0.94 | -5% | 1.05 | -39% | -0.10 | -22% |  |
| ema_volshock | - | on | 1.00 | +0% | 1.05 | -38% | -0.21 | -24% |  |
| parkinson_vol | - | on | 0.95 | -4% | 1.01 | -37% | -0.22 | -23% |  |
| kelly | fraction | 1.0 | 0.73 | -27% | 0.82 | -17% | -0.16 | -6% |  |
| kelly | fraction | 0.5 | 0.58 | -42% | 0.79 | -16% | -0.15 | -3% |  |
| kelly | fraction | 0.25 | 0.51 | -49% | 0.73 | -16% | -0.14 | -1% |  |
| weekend_skip | - | on | 0.74 | -26% | 0.91 | -39% | 0.00 | -22% |  |
| profit_taking | l1/l2 | 50/100 | 1.03 | +3% | 1.06 | -38% | -0.21 | -24% |  |
| profit_taking | l1/l2 | 30/60 | 1.01 | +1% | 1.08 | -38% | -0.21 | -24% |  |
| profit_taking | l1/l2 | 75/150 | 1.00 | +0% | 1.05 | -38% | -0.21 | -24% |  |
| dd_brake | dd/cut | 20/0.3 | 0.93 | -7% | 1.05 | -34% | -0.16 | -16% |  |
| dd_brake | dd/cut | 20/0.5 | 1.03 | +3% | 1.08 | -33% | -0.15 | -17% | ✓ |
| dd_brake | dd/cut | 30/0.3 | 0.95 | -5% | 1.02 | -33% | -0.13 | -20% |  |
| dd_brake | dd/cut | 30/0.5 | 1.02 | +2% | 1.05 | -33% | -0.17 | -22% | ✓ |
| dd_brake | dd/cut | 40/0.3 | 0.90 | -9% | 1.03 | -33% | -0.20 | -19% |  |
| dd_brake | dd/cut | 40/0.5 | 1.01 | +1% | 1.05 | -33% | -0.21 | -20% | ✓ |
| dynamic_reentry | - | volz | 0.42 | -58% | 0.66 | -40% | -0.14 | -21% |  |
| graded_entry | - | RSI | 1.24 | +24% | 1.07 | -27% | -0.01 | -17% | ★ |

## Winners (≥8% design Calmar AND hold-out improves) — marked ★ above

| Variant | Feature | Value | Δ design Calmar | Hold-out Calmar |
|---|---|---|---|---|
| lean | track_period | 45 | +43% | 0.01 |
| lean | atr_blowoff | 99.0 | +38% | -0.05 |
| lean | dd_brake | 40/0.5 | +27% | -0.07 |
| momentum | graded_entry | RSI | +24% | -0.01 |
| lean | atr_buffer | 1.5 | +22% | 0.22 |
| lean | blowoff_dist_pct | 30 | +22% | -0.05 |
| lean | vol_shock_mul | 1.2 | +20% | -0.07 |
| lean | blowoff_dist_pct | 35 | +19% | -0.05 |
| lean | track_buf_pct | 1.0 | +17% | -0.02 |
| lean | dd_brake | 40/0.3 | +16% | -0.07 |
| lean | track_period | 80 | +16% | 0.12 |
| lean | track_buf_pct | 5.0 | +16% | -0.07 |
| lean | weekend_skip | on | +15% | -0.02 |
| lean | track_period | 55 | +13% | -0.05 |
| lean | track_buf_pct | 4.5 | +11% | -0.04 |
| lean | blowoff_dist_pct | 40 | +11% | -0.05 |
| lean | track_period | 50 | +9% | -0.01 |
| momentum | blowoff_dist_pct | 35 | +9% | -0.14 |
| momentum | bear_size_cut | 25 | +8% | -0.21 |

★ = ship-grade (design gain + hold-out confirm) · ✓ = hold-out improves but small design gain · blank = no improvement or hold-out degrades. Structural combinations (rotation, regime-switch, ensemble) are in `improvements_report.md`.

## Correctness notes (verified genuine no-ops, not bugs)

- **`target_vol_pct` has zero effect on Lean** (all values → 0.44). Lean's `target_alloc` is binary 0/100 — its vol-sizing is 'off the signal path' by design (config comment). Vol-target only affects **Momentum** (49 distinct alloc levels), where it sweeps 40→90 with real effect (+13% at 90). Verified directly.
- **`vol_shock_mul` is a near-no-op** on both variants: the vol-shock exit fires while actually in a BULL position only ~2/2600 bars (it requires price below the trackline, where the strategy has usually already exited). Same reason `ema_volshock` = exactly 0.
- These are correct behaviours; they tell us the vol-shock machinery is redundant with the trackline-break exit, and Lean's vol-sizing lever is inert in this return model.

## Key findings from the full surface

1. **Two robust ship-grade wins** (large design gain + hold-out confirmed): **Momentum graded entry** (+24% design, hold-out −0.21→−0.01, MaxDD −38%→−27%) and **Lean ATR buffer k=1.5** (+22%, hold-out −0.09→+0.22).
2. **A clear regime trade-off surface:** several *defensive* settings sacrifice design Calmar but sharply improve the bear hold-out — e.g. Momentum `atr_buffer k=2.5` (design −40% but **hold-out +0.43**, the best hold-out of any Momentum config), `trail_pct=6` (hold-out +0.18), and longer Lean `track_period` (85→90 gives hold-out +0.21/+0.23). These are the levers to pull if bear-market protection matters more than bull-market return — exactly the Lean↔Momentum regime story.
3. **Kelly cuts drawdown hard but hurts Calmar** (Lean MaxDD −61%→−38% at ¼-Kelly, but only +5% Calmar; Momentum MaxDD −38%→−16% but −42% Calmar). Useful only if the mandate is drawdown-minimisation over return.
4. **Most single parameters are flat-topped near their defaults** (Sharpe barely moves across the swept range) — confirming the Phase 3/4 robustness result: the strategies are not perched on fragile parameter spikes.

**Multiple-testing caveat:** ~50 configs per variant were scored here, so some ★ marks are selection noise. Trust the ones with a *mechanism* and a *hold-out* improvement (graded entry, Lean ATR buffer, the defensive settings); treat lone design-only spikes (e.g. `atr_blowoff pct=99` +38%) as unproven until confirmed in paper trading.
