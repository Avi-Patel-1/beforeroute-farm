You are tuning the settings of an open-source chip design flow (LibreLane/OpenROAD on the SkyWater sky130 130 nm
process) for one design. Use ONLY the information in this message: do not read files, run commands, search, or use
anything you may know about other runs or designs. Reply with the JSON described at the end and nothing else.

GOAL. Find settings that let this design pass signoff at the shortest clock period. Each run is scored by its effective
clock T_eff = (clock target it was given) - (worst setup slack over 9 signoff corners); lower is better. A run counts
only if it is FEASIBLE: hold slack >= 0 at every corner, zero router DRC errors, and no more slew/capacitance violation
pins (summed over the 9 corners) than the bar, which is set by the stock flow's run on this design. Note: T_eff from a
run aimed at a much looser or tighter target can be optimistic; the best run will later be re-checked at its T_eff.

DESIGN. wbqspiflash: Wishbone quad-SPI flash controller (ZipCPU). Default clock period 18.86 ns. Stock flow: about 2808 standard cells. Bar: 953
slew/cap pins.

KNOBS (the only things you can set; give every knob, within these ranges):
- period_frac (float: 0.45 to 1.0): clock target as a fraction of the design's default clock period
- FP_CORE_UTIL (int: 20 to 50): core utilisation, % (lower leaves room for wires and late repairs)
- density_delta (int: 5 to 30): placement density = utilisation + this many points (capped at 80)
- SYNTH_STRATEGY (cat: AREA 0 | AREA 1 | AREA 2 | AREA 3 | DELAY 0 | DELAY 1 | DELAY 2 | DELAY 3 | DELAY 4): Yosys/ABC synthesis script (AREA = smaller, DELAY = faster logic)
- SYNTH_ABC_BUFFERING (bool: true | false): insert buffers during synthesis
- SYNTH_SIZING (bool: true | false): resize gates during synthesis
- PL_TIMING_DRIVEN (bool: true | false): timing-driven global placement
- PL_ROUTABILITY_DRIVEN (bool: true | false): routability-driven global placement (spreads cells in crowded areas)
- RUN_POST_GRT_RESIZER_TIMING (bool: true | false): timing repair again after global routing
- RUN_POST_GRT_DESIGN_REPAIR (bool: true | false): slew/cap/fanout repair again after global routing
- PL_RESIZER_SETUP_SLACK_MARGIN (float: 0.0 to 0.4): extra setup margin (ns) placement-stage repair aims for
- GRT_RESIZER_SETUP_SLACK_MARGIN (float: 0.0 to 0.4): extra setup margin (ns) post-global-route repair aims for
- DESIGN_REPAIR_MAX_SLEW_PCT (int: 10 to 40): repair aims this % below the slew limit
- DESIGN_REPAIR_MAX_CAP_PCT (int: 10 to 40): repair aims this % below the capacitance limit
- RC_MODEL (cat: stock | cap213 | orfs): wire R/C assumed before routing: stock LEF values; cap213 = wire capacitance x2.13 (measured gap to signoff extraction in this flow); orfs = OpenROAD-flow-scripts per-layer values

HISTORY on this design (12 runs so far: 8 'start' runs are settings found on other designs and applied unchanged;
'round' runs are your own earlier proposals, with your rationale). Each run shows its setting and its scores (T_eff and the three constraint values the optimizer sees).
- start blabla [x6z-wbqspiflash-001] clock target 17.51 ns -> T_eff 9.920 ns, FEASIBLE
  setting {"period_frac": 0.928473063355609, "FP_CORE_UTIL": 27, "density_delta": 25, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": true, "SYNTH_SIZING": true, "PL_TIMING_DRIVEN": false, "PL_ROUTABILITY_DRIVEN": true, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": false, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.3734844189074291, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.16520668545533518, "DESIGN_REPAIR_MAX_SLEW_PCT": 39, "DESIGN_REPAIR_MAX_CAP_PCT": 18, "RC_MODEL": "orfs"}
  scores: constraints [router DRC errors, minus the worst hold slack (ns), slew/cap pins minus the bar] = [0, -0.093, -953]; FEASIBLE only if all three are <= 0
- start des [x6z-wbqspiflash-002] clock target 9.12 ns -> T_eff 8.574 ns, FEASIBLE
  setting {"period_frac": 0.48352759747215784, "FP_CORE_UTIL": 27, "density_delta": 19, "SYNTH_STRATEGY": "DELAY 4", "SYNTH_ABC_BUFFERING": false, "SYNTH_SIZING": false, "PL_TIMING_DRIVEN": false, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": false, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.16636921385131967, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.25116636617682997, "DESIGN_REPAIR_MAX_SLEW_PCT": 25, "DESIGN_REPAIR_MAX_CAP_PCT": 40, "RC_MODEL": "cap213"}
  scores: constraints [router DRC errors, minus the worst hold slack (ns), slew/cap pins minus the bar] = [0, -0.083, -953]; FEASIBLE only if all three are <= 0
- start bm64 [x6z-wbqspiflash-003] clock target 9.5 ns -> T_eff 9.283 ns, FEASIBLE
  setting {"period_frac": 0.503863953041454, "FP_CORE_UTIL": 21, "density_delta": 14, "SYNTH_STRATEGY": "DELAY 3", "SYNTH_ABC_BUFFERING": false, "SYNTH_SIZING": true, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": false, "RUN_POST_GRT_DESIGN_REPAIR": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.24619915855228341, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.10560593983481525, "DESIGN_REPAIR_MAX_SLEW_PCT": 30, "DESIGN_REPAIR_MAX_CAP_PCT": 11, "RC_MODEL": "orfs"}
  scores: constraints [router DRC errors, minus the worst hold slack (ns), slew/cap pins minus the bar] = [0, -0.094, -953]; FEASIBLE only if all three are <= 0
- start ocs_blitter [x6z-wbqspiflash-004] clock target 11.64 ns -> T_eff 9.454 ns, FEASIBLE
  setting {"period_frac": 0.6171955706800487, "FP_CORE_UTIL": 40, "density_delta": 15, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": false, "SYNTH_SIZING": false, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": false, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.32283309180712455, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.21234668380681754, "DESIGN_REPAIR_MAX_SLEW_PCT": 22, "DESIGN_REPAIR_MAX_CAP_PCT": 29, "RC_MODEL": "cap213"}
  scores: constraints [router DRC errors, minus the worst hold slack (ns), slew/cap pins minus the bar] = [0, -0.091, -953]; FEASIBLE only if all three are <= 0
- start md5 [x6z-wbqspiflash-005] clock target 9.37 ns -> T_eff 8.807 ns, FEASIBLE
  setting {"period_frac": 0.49666758392155613, "FP_CORE_UTIL": 30, "density_delta": 11, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": true, "SYNTH_SIZING": true, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.17835233972832615, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.09022060448969806, "DESIGN_REPAIR_MAX_SLEW_PCT": 25, "DESIGN_REPAIR_MAX_CAP_PCT": 20, "RC_MODEL": "cap213"}
  scores: constraints [router DRC errors, minus the worst hold slack (ns), slew/cap pins minus the bar] = [0, -0.085, -953]; FEASIBLE only if all three are <= 0
- start picorv32 [x6z-wbqspiflash-006] clock target 9.85 ns -> T_eff 9.552 ns, FEASIBLE
  setting {"period_frac": 0.5222176203433402, "FP_CORE_UTIL": 38, "density_delta": 5, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": false, "SYNTH_SIZING": false, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": true, "RUN_POST_GRT_RESIZER_TIMING": false, "RUN_POST_GRT_DESIGN_REPAIR": false, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.2585143226133421, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.0285628051553697, "DESIGN_REPAIR_MAX_SLEW_PCT": 22, "DESIGN_REPAIR_MAX_CAP_PCT": 20, "RC_MODEL": "stock"}
  scores: constraints [router DRC errors, minus the worst hold slack (ns), slew/cap pins minus the bar] = [0, -0.107, -902]; FEASIBLE only if all three are <= 0
- start y_huff [x6z-wbqspiflash-007] clock target 18.41 ns -> T_eff 10.149 ns, FEASIBLE
  setting {"period_frac": 0.976013443761732, "FP_CORE_UTIL": 37, "density_delta": 18, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": true, "SYNTH_SIZING": true, "PL_TIMING_DRIVEN": false, "PL_ROUTABILITY_DRIVEN": true, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.041485267124613805, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.03869271067313256, "DESIGN_REPAIR_MAX_SLEW_PCT": 22, "DESIGN_REPAIR_MAX_CAP_PCT": 27, "RC_MODEL": "stock"}
  scores: constraints [router DRC errors, minus the worst hold slack (ns), slew/cap pins minus the bar] = [0, -0.113, -852]; FEASIBLE only if all three are <= 0
- start aes_cipher [x6z-wbqspiflash-008] clock target 10.86 ns -> T_eff 10.743 ns, FEASIBLE
  setting {"period_frac": 0.5759360256713374, "FP_CORE_UTIL": 23, "density_delta": 7, "SYNTH_STRATEGY": "AREA 2", "SYNTH_ABC_BUFFERING": true, "SYNTH_SIZING": false, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.09845674949215728, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.3225578512156802, "DESIGN_REPAIR_MAX_SLEW_PCT": 38, "DESIGN_REPAIR_MAX_CAP_PCT": 26, "RC_MODEL": "stock"}
  scores: constraints [router DRC errors, minus the worst hold slack (ns), slew/cap pins minus the bar] = [0, -0.105, -953]; FEASIBLE only if all three are <= 0
- round 1 [xnp-wbqspiflash-001] clock target 8.49 ns -> T_eff 8.060 ns, FEASIBLE
  setting {"period_frac": 0.45, "FP_CORE_UTIL": 27, "density_delta": 19, "SYNTH_STRATEGY": "DELAY 4", "SYNTH_ABC_BUFFERING": false, "SYNTH_SIZING": false, "PL_TIMING_DRIVEN": false, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": false, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.166, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.251, "DESIGN_REPAIR_MAX_SLEW_PCT": 25, "DESIGN_REPAIR_MAX_CAP_PCT": 40, "RC_MODEL": "cap213"}
  scores: constraints [router DRC errors, minus the worst hold slack (ns), slew/cap pins minus the bar] = [0, -0.081, -953]; FEASIBLE only if all three are <= 0
  (your rationale then: All 8 starts are feasible with wide margins (0 DRC, hold slack >= +0.08 ns, <=101 slew/cap pins vs bar 953), so only setup matters. The tightest targets (frac 0.48-0.50) gave the best T_eff and still had +0.22 to +0.56 ns slack, so the design is not yet at its limit: push the target to the 0.45 floor (8.49 ns). Setting 1 is the best run (des: DELAY 4, cap213, post-GRT timing repair) with only the target tightened, a clean exploit. Setting 2 grafts the second-best run's (md5) timing-driven placement, ABC sizing/buffering and post-GRT design repair onto DELAY 4 + cap213 at similar density, to test whether they stack.)
- round 1 [xnp-wbqspiflash-002] clock target 8.49 ns -> T_eff 8.241 ns, FEASIBLE
  setting {"period_frac": 0.45, "FP_CORE_UTIL": 28, "density_delta": 17, "SYNTH_STRATEGY": "DELAY 4", "SYNTH_ABC_BUFFERING": true, "SYNTH_SIZING": true, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.2, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.2, "DESIGN_REPAIR_MAX_SLEW_PCT": 25, "DESIGN_REPAIR_MAX_CAP_PCT": 25, "RC_MODEL": "cap213"}
  scores: constraints [router DRC errors, minus the worst hold slack (ns), slew/cap pins minus the bar] = [0, -0.085, -953]; FEASIBLE only if all three are <= 0
  (your rationale then: All 8 starts are feasible with wide margins (0 DRC, hold slack >= +0.08 ns, <=101 slew/cap pins vs bar 953), so only setup matters. The tightest targets (frac 0.48-0.50) gave the best T_eff and still had +0.22 to +0.56 ns slack, so the design is not yet at its limit: push the target to the 0.45 floor (8.49 ns). Setting 1 is the best run (des: DELAY 4, cap213, post-GRT timing repair) with only the target tightened, a clean exploit. Setting 2 grafts the second-best run's (md5) timing-driven placement, ABC sizing/buffering and post-GRT design repair onto DELAY 4 + cap213 at similar density, to test whether they stack.)
- round 2 [xnp-wbqspiflash-003] clock target 8.49 ns -> T_eff 7.893 ns, FEASIBLE
  setting {"period_frac": 0.45, "FP_CORE_UTIL": 27, "density_delta": 19, "SYNTH_STRATEGY": "DELAY 4", "SYNTH_ABC_BUFFERING": false, "SYNTH_SIZING": false, "PL_TIMING_DRIVEN": false, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": false, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.4, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.4, "DESIGN_REPAIR_MAX_SLEW_PCT": 25, "DESIGN_REPAIR_MAX_CAP_PCT": 40, "RC_MODEL": "cap213"}
  scores: constraints [router DRC errors, minus the worst hold slack (ns), slew/cap pins minus the bar] = [0, -0.083, -953]; FEASIBLE only if all three are <= 0
  (your rationale then: All 10 runs are feasible with wide margins (0 DRC, hold >= +0.08 ns, slew/cap far below the bar), so only setup matters. T_eff tracks the target: the des config fell 8.57 -> 8.06 ns when the target hit the 0.45 floor, yet kept +0.43 ns slack, so the design is not at its wall. Grafting md5's buffering/sizing/TD/post-GRT repair onto it hurt (8.24). With the target floored, the remaining lever is repair margin: setting 1 is the best run with both setup margins at the 0.4 maximum (effective target ~8.09 ns). Setting 2 also packs the floorplan (util 40, density 55%, DRC-clean here in ocs_blitter) to shorten wires, which cap213 shows are costly.)
- round 2 [xnp-wbqspiflash-004] clock target 8.49 ns -> T_eff 8.149 ns, FEASIBLE
  setting {"period_frac": 0.45, "FP_CORE_UTIL": 40, "density_delta": 15, "SYNTH_STRATEGY": "DELAY 4", "SYNTH_ABC_BUFFERING": false, "SYNTH_SIZING": false, "PL_TIMING_DRIVEN": false, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": false, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.4, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.4, "DESIGN_REPAIR_MAX_SLEW_PCT": 25, "DESIGN_REPAIR_MAX_CAP_PCT": 40, "RC_MODEL": "cap213"}
  scores: constraints [router DRC errors, minus the worst hold slack (ns), slew/cap pins minus the bar] = [0, -0.092, -936]; FEASIBLE only if all three are <= 0
  (your rationale then: All 10 runs are feasible with wide margins (0 DRC, hold >= +0.08 ns, slew/cap far below the bar), so only setup matters. T_eff tracks the target: the des config fell 8.57 -> 8.06 ns when the target hit the 0.45 floor, yet kept +0.43 ns slack, so the design is not at its wall. Grafting md5's buffering/sizing/TD/post-GRT repair onto it hurt (8.24). With the target floored, the remaining lever is repair margin: setting 1 is the best run with both setup margins at the 0.4 maximum (effective target ~8.09 ns). Setting 2 also packs the floorplan (util 40, density 55%, DRC-clean here in ocs_blitter) to shorten wires, which cap213 shows are costly.)

TASK. Round 3 of 4. Propose exactly 2 NEW settings for this design (different from every setting above),
chosen to lower the best feasible T_eff, using what the scores tell you. Reply with JSON only, in this form:
{"rationale": "<at most 120 words: what the scores suggest and why these settings>",
 "settings": [{<all 15 knobs>}, {<all 15 knobs>}]}
