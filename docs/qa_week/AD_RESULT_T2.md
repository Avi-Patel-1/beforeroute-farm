# Workstream AD — T2 result: is the claim's response to the ask a property of the flow or of the node?

Pre-registration: docs/qa_week/AD_PREREG.md with Amendment 1 (SHA-256 760b49c6…3869c; hash line 753295e in
farm/prereg_hashes.txt, branch qa-ad-law of Avi-Patel-1/beforeroute-farm), written and hashed before any non-smoke
run. Scored by the committed script `python3 farm/qa/AD/ad.py analyze` (ad.py at fbed433, adlib.py at 286e4aa);
numbers in farm/qa/AD/ad_analyze_t2a.json. Workflow run 41574461473 (batch m01).

## Verdicts
- **T2(a), ORFS on sky130hd — COMPLETE (30 of 30 grid runs), scored 2026-11-03 10:25 UTC (05:25 ET).
  Registered prediction (s⁻ ≤ 0.35 and s⁺ ≥ 0.45): FAILED. Outcome: "node, not flow" (s⁻ ≥ 0.45).**
  s⁻ = **0.601** (15 runs below their F), s⁺ = **0.579** (15 runs above). Same flow as E5 (ORFS, same image), node
  changed from ASAP7 to sky130hd: the tight-side slope went from ORFS-at-7-nm's 0.20–0.26 to LibreLane-at-130-nm's
  0.59.
- **T2(b), ORFS on ASAP7 with ABC told the clock — NOT YET COMPLETE at this writing: 20 of 30 grid runs landed (gcd and aes); its 10 ibex runs were still running (expected ~12:10 UTC / 07:10 ET). The partial fit on the 20 (s⁻ 0.300, s⁺ 0.600) is not a verdict.****

## What was run (units ps; one corner per platform; OpenROAD-flow-scripts commit 202c7fccb in one pinned image)
- **T2a:** ORFS's own sky130hd gcd, aes, ibex configs (sky130_fd_sc_hd, TT 25 °C 1.80 V, OpenRCX), E5's grid shape:
  per design S0 = shipped config at {0.70, 0.85, 1.00, 1.40}·P0; S1 (CORE_UTILIZATION −15/−15/−10 points) and S2
  (density +0.20 or PLACE_DENSITY 0.90) at {0.80, 1.20, 1.45}·P0. P0 anchored at the pilot-estimated clock of the
  shipped setting (registered rule; Amendment 1): gcd 2635 ps, aes 4190 ps, ibex 9320 ps (the shipped periods were
  1100, 3600 and 8000 ps). All 30 runs completed, detailed-route DRC 0, hold met; 9 of 30 port-limited.
- **Synthesis was clock-blind in T2a:** Yosys/ABC with no target; every sky130hd design's mapped netlist is
  byte-identical at all ten of its targets (sha1 d8294783 gcd, 31d2f278 aes, 7d9cd1b4 ibex). Every difference between
  targets comes from floorplan-to-route optimization.
- **The law's slopes** (registered method, the one behind the plan's constants): per setting, F = the interpolated
  crossing of claim = target (E5's method; all 9 settings bracketed); r = T/F, e = (C − F)/F; least-squares slope of e
  on (r − 1) through the origin, separately below and above F.

| population | runs | settings with F | s⁻ (runs) | s⁺ (runs) | tight-bin median (r < 0.9) | loose-bin median (1.1–1.5) |
|---|---|---|---|---|---|---|
| **ORFS, sky130hd (T2a, grid)** | 30 | 9 | **0.601** (15) | **0.579** (15) | **−15.0%** (11) | **+14.3%** (11) |
| ORFS, sky130hd, grid + D's rebuilds (beside) | 38 | 9 | 0.586 (21) | 0.596 (17) | −16.4% (10)\* | +18.9% (10)\* |
| LibreLane, sky130 (record, 328 runs; the plan) | 328 | 60 | 0.59 | 0.29 | −14.5% (111) | +8.2% (48) |
| ORFS, ASAP7 (E5 grid only, recomputed) | 30 | 9 | 0.259 (16) | 0.566 (14) | −7.7% (13) | +12.8% (9) |
| ORFS, ASAP7 (E5 grid + rebuilds; the plan's 0.20/0.65) | 44 | 9 | 0.201 (25) | 0.649 (19) | −5.6% (13) | +15.2% (10) |

\* D's bins (grid + the rebuild chains landed so far; E5's S1 method). k = 1/(1 − s): ORFS-sky130hd k⁻ ≈ 2.5,
k⁺ ≈ 2.4 slacks.

Per design (T2a grid): gcd s⁻ 0.398 / s⁺ 0.437; aes 0.748 / 0.675; ibex 0.581 / 0.605. All three designs are above
ORFS-ASAP7's 0.20–0.26 on the tight side.

Every T2a run (target T → claim C; r = T/F; e = claim error):
- gcd S0 (F 2520): 1845→2325 (r 0.73, −7.7%), 2240→2407 (0.89, −4.5%), 2635→2566 (1.05, +1.8%), 3690→3171 (1.46, +25.9%)
- gcd S1 (F 2831): 2110→2407 (0.75, −15.0%), 3160→3025 (1.12, +6.8%), 3820→3142 (1.35, +11.0%)
- gcd S2 (F 2753): 2110→2552 (0.77, −7.3%), 3160→2880 (1.15, +4.6%), 3820→3148 (1.39, +14.3%)
- aes S0 (F 4602): 2935→3673 (0.64, −20.2%), 3560→3695 (0.77, −19.7%), 4190→4306 (0.91, −6.4%), 5865→5510 (1.27, +19.7%)
- aes S1 (F 3619): 3350→3410 (0.93, −5.8%), 5030→4717 (1.39, +30.3%), 6075→5268 (1.68, +45.6%)
- aes S2 (F 5234): 3350→3536 (0.64, −32.4%), 5030→5235 (0.96, +0.0%), 6075→5230 (1.16, −0.1%)
- ibex S0 (F 9868): 6525→8518 (0.66, −13.7%), 7920→8494 (0.80, −13.9%), 9320→9531 (0.94, −3.4%), 13050→11825 (1.32, +19.8%)
- ibex S1 (F 10542): 7455→8561 (0.71, −18.8%), 11185→10954 (1.06, +3.9%), 13515→12450 (1.28, +18.1%)
- ibex S2 (F 11062): 7455→8617 (0.67, −22.1%), 11185→11145 (1.01, +0.8%), 13515→12338 (1.22, +11.5%)

## What T2(a) means (as registered, plus one descriptive observation)
- Registered reading of "node, not flow": ORFS at 130 nm looks like LibreLane at 130 nm on the tight side; the
  constants are per node — still a law, but the 7 nm asymmetry is the node, not the flow.
- It is the node *with clock-blind synthesis*: T2a's netlists never changed with the target, yet the tight-side slope
  is LibreLane's. So the plan's conjecture that ASAP7's shallow tight side comes from "synthesis never sees the
  clock" is not supported by T2a; T2(b) tests the converse directly.
- Descriptive (no criterion): the loose side did *not* follow the node — ORFS-sky130hd underclaims +14.3% at loose
  asks, like ORFS-ASAP7 (+12.8% / +15.2%) and unlike LibreLane-sky130 (+8.2%). Read together: the tight side follows
  the node, the loose side follows the flow.
- Say it as: "I re-ran my 7 nm audit on a 130 nm library inside the very same OpenROAD flow and image. On the tight
  side the claim moved with the ask at 0.60 — exactly my LibreLane number, 0.59 — not the 0.20 I saw at 7 nm. So that
  constant belongs to the node, not the tool; and it happens with synthesis blind to the clock."
- Do not say: "flow-independent" without "on the tight side"; "a 130 nm foundry signoff" (one TT corner, no margins);
  anything about significance (9 settings, 3 small designs).

## Caveats
1. One corner per platform (sky130hd TT; ASAP7 FF), no SDC margins; LibreLane's record used 9 corners and margins.
2. Three designs (gcd 222 cells, aes ~11k, ibex ~14k after synthesis), 9 settings; the slopes are least-squares lines
   through few settings; aes's two non-shipped settings sit at the ends of the spread (s⁻ 0.75 for aes overall).
3. The sky130hd grids were anchored at a pilot-estimated F (Amendment 1); the shipped periods were not used.
4. The flow is not monotonic near F (e.g. aes S2: 5030 → 5235 fails, 6075 → 5230 passes).

## T2(b) so far (partial; the verdict needs all 30)
- The patch reached ABC in every run (the `abc ... -D <target>` command is in each synthesis log; `abc_d_log_hits` ≥ 1
  in all 20).
- Registered netlist check: **gcd's mapped netlist is identical at all 10 targets** ("patch ran but ABC's mapping did
  not depend on the target"); **aes's varied** (4 distinct netlists: different at 265, 305 and 325 ps, the same from
  380 ps up), so on aes ABC's target bound at the tight asks.
- Partial fit (gcd + aes, 20 runs, 6 settings bracketed): s⁻ 0.300, s⁺ 0.600; per design gcd 0.137 / 0.439, aes
  0.472 / 0.825. ibex (10 runs) completes the registered population; smoke showed ibex's netlist does not change with
  the target, so its runs should reproduce E5's ibex claims.

