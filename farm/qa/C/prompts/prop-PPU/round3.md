You are tuning the settings of an open-source chip design flow (LibreLane/OpenROAD on the SkyWater sky130 130 nm
process) for one design. Use ONLY the information in this message: do not read files, run commands, search, or use
anything you may know about other runs or designs. Reply with the JSON described at the end and nothing else.

GOAL. Find settings that let this design pass signoff at the shortest clock period. Each run is scored by its effective
clock T_eff = (clock target it was given) - (worst setup slack over 9 signoff corners); lower is better. A run counts
only if it is FEASIBLE: hold slack >= 0 at every corner, zero router DRC errors, and no more slew/capacitance violation
pins (summed over the 9 corners) than the bar, which is set by the stock flow's run on this design. Note: T_eff from a
run aimed at a much looser or tighter target can be optimistic; the best run will later be re-checked at its T_eff.

DESIGN. PPU: NES picture processing unit. Default clock period 18.0 ns. Stock flow: about 18763 standard cells. Bar: 3053
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
- start blabla [x6z-PPU-001] clock target 16.71 ns -> T_eff 16.977 ns, FEASIBLE
  setting {"period_frac": 0.928473063355609, "FP_CORE_UTIL": 27, "density_delta": 25, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": true, "SYNTH_SIZING": true, "PL_TIMING_DRIVEN": false, "PL_ROUTABILITY_DRIVEN": true, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": false, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.3734844189074291, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.16520668545533518, "DESIGN_REPAIR_MAX_SLEW_PCT": 39, "DESIGN_REPAIR_MAX_CAP_PCT": 18, "RC_MODEL": "orfs"}
  scores: constraints [router DRC errors, minus the worst hold slack (ns), slew/cap pins minus the bar] = [0, -0.093, -3000]; FEASIBLE only if all three are <= 0
- start des [x6z-PPU-002] clock target 8.7 ns -> T_eff 15.910 ns, FEASIBLE
  setting {"period_frac": 0.48352759747215784, "FP_CORE_UTIL": 27, "density_delta": 19, "SYNTH_STRATEGY": "DELAY 4", "SYNTH_ABC_BUFFERING": false, "SYNTH_SIZING": false, "PL_TIMING_DRIVEN": false, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": false, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.16636921385131967, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.25116636617682997, "DESIGN_REPAIR_MAX_SLEW_PCT": 25, "DESIGN_REPAIR_MAX_CAP_PCT": 40, "RC_MODEL": "cap213"}
  scores: constraints [router DRC errors, minus the worst hold slack (ns), slew/cap pins minus the bar] = [0, -0.091, -3043]; FEASIBLE only if all three are <= 0
- start bm64 [x6z-PPU-003] clock target 9.07 ns -> T_eff 14.583 ns, FEASIBLE
  setting {"period_frac": 0.503863953041454, "FP_CORE_UTIL": 21, "density_delta": 14, "SYNTH_STRATEGY": "DELAY 3", "SYNTH_ABC_BUFFERING": false, "SYNTH_SIZING": true, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": false, "RUN_POST_GRT_DESIGN_REPAIR": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.24619915855228341, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.10560593983481525, "DESIGN_REPAIR_MAX_SLEW_PCT": 30, "DESIGN_REPAIR_MAX_CAP_PCT": 11, "RC_MODEL": "orfs"}
  scores: constraints [router DRC errors, minus the worst hold slack (ns), slew/cap pins minus the bar] = [0, -0.089, -3047]; FEASIBLE only if all three are <= 0
- start ocs_blitter [x6z-PPU-004] clock target 11.11 ns -> T_eff 12.847 ns, FEASIBLE
  setting {"period_frac": 0.6171955706800487, "FP_CORE_UTIL": 40, "density_delta": 15, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": false, "SYNTH_SIZING": false, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": false, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.32283309180712455, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.21234668380681754, "DESIGN_REPAIR_MAX_SLEW_PCT": 22, "DESIGN_REPAIR_MAX_CAP_PCT": 29, "RC_MODEL": "cap213"}
  scores: constraints [router DRC errors, minus the worst hold slack (ns), slew/cap pins minus the bar] = [0, -0.094, -3045]; FEASIBLE only if all three are <= 0
- start md5 [x6z-PPU-005] clock target 8.94 ns -> T_eff 12.629 ns, FEASIBLE
  setting {"period_frac": 0.49666758392155613, "FP_CORE_UTIL": 30, "density_delta": 11, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": true, "SYNTH_SIZING": true, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.17835233972832615, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.09022060448969806, "DESIGN_REPAIR_MAX_SLEW_PCT": 25, "DESIGN_REPAIR_MAX_CAP_PCT": 20, "RC_MODEL": "cap213"}
  scores: constraints [router DRC errors, minus the worst hold slack (ns), slew/cap pins minus the bar] = [0, -0.083, -3049]; FEASIBLE only if all three are <= 0
- start picorv32 [x6z-PPU-006] clock target 9.4 ns -> T_eff 14.034 ns, INFEASIBLE (hold violated)
  setting {"period_frac": 0.5222176203433402, "FP_CORE_UTIL": 38, "density_delta": 5, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": false, "SYNTH_SIZING": false, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": true, "RUN_POST_GRT_RESIZER_TIMING": false, "RUN_POST_GRT_DESIGN_REPAIR": false, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.2585143226133421, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.0285628051553697, "DESIGN_REPAIR_MAX_SLEW_PCT": 22, "DESIGN_REPAIR_MAX_CAP_PCT": 20, "RC_MODEL": "stock"}
  scores: constraints [router DRC errors, minus the worst hold slack (ns), slew/cap pins minus the bar] = [0, +0.526, -799]; FEASIBLE only if all three are <= 0
- start y_huff [x6z-PPU-007] clock target 17.57 ns -> T_eff 20.452 ns, INFEASIBLE (more slew/cap pins than the bar)
  setting {"period_frac": 0.976013443761732, "FP_CORE_UTIL": 37, "density_delta": 18, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": true, "SYNTH_SIZING": true, "PL_TIMING_DRIVEN": false, "PL_ROUTABILITY_DRIVEN": true, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.041485267124613805, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.03869271067313256, "DESIGN_REPAIR_MAX_SLEW_PCT": 22, "DESIGN_REPAIR_MAX_CAP_PCT": 27, "RC_MODEL": "stock"}
  scores: constraints [router DRC errors, minus the worst hold slack (ns), slew/cap pins minus the bar] = [0, -0.084, 749]; FEASIBLE only if all three are <= 0
- start aes_cipher [x6z-PPU-008] clock target 10.37 ns -> T_eff 16.837 ns, INFEASIBLE (hold violated)
  setting {"period_frac": 0.5759360256713374, "FP_CORE_UTIL": 23, "density_delta": 7, "SYNTH_STRATEGY": "AREA 2", "SYNTH_ABC_BUFFERING": true, "SYNTH_SIZING": false, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.09845674949215728, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.3225578512156802, "DESIGN_REPAIR_MAX_SLEW_PCT": 38, "DESIGN_REPAIR_MAX_CAP_PCT": 26, "RC_MODEL": "stock"}
  scores: constraints [router DRC errors, minus the worst hold slack (ns), slew/cap pins minus the bar] = [0, +0.307, -2849]; FEASIBLE only if all three are <= 0
- round 1 [xnp-PPU-001] clock target 9.0 ns -> T_eff 12.585 ns, FEASIBLE
  setting {"period_frac": 0.5, "FP_CORE_UTIL": 38, "density_delta": 14, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": true, "SYNTH_SIZING": true, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.3, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.3, "DESIGN_REPAIR_MAX_SLEW_PCT": 30, "DESIGN_REPAIR_MAX_CAP_PCT": 20, "RC_MODEL": "cap213"}
  scores: constraints [router DRC errors, minus the worst hold slack (ns), slew/cap pins minus the bar] = [0, -0.087, -3049]; FEASIBLE only if all three are <= 0
  (your rationale then: With realistic RC the constraints aren't binding: 'stock' RC runs failed hold or slew/cap, while cap213/orfs runs pass easily (hold +0.09 ns, slew/cap far under bar, 0 DRC). Both best runs (12.63, 12.85) used AREA 3, timing-driven placement, post-GRT timing repair, cap213 and a tight target; the rest, each missing at least one of these or with very low utilisation, landed at 14.0-20.5. Setting 1 merges the two best: md5's ABC buffering/sizing, post-GRT design repair and ~9 ns target with ocs_blitter's denser floorplan (util 38), plus more slew repair and larger margins. Setting 2 tests an untried DELAY script under that physical recipe; earlier DELAY runs were confounded by weak physical settings.)
- round 1 [xnp-PPU-002] clock target 9.9 ns -> T_eff 13.353 ns, FEASIBLE
  setting {"period_frac": 0.55, "FP_CORE_UTIL": 30, "density_delta": 11, "SYNTH_STRATEGY": "DELAY 2", "SYNTH_ABC_BUFFERING": true, "SYNTH_SIZING": true, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.25, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.2, "DESIGN_REPAIR_MAX_SLEW_PCT": 25, "DESIGN_REPAIR_MAX_CAP_PCT": 20, "RC_MODEL": "cap213"}
  scores: constraints [router DRC errors, minus the worst hold slack (ns), slew/cap pins minus the bar] = [0, -0.084, -3046]; FEASIBLE only if all three are <= 0
  (your rationale then: With realistic RC the constraints aren't binding: 'stock' RC runs failed hold or slew/cap, while cap213/orfs runs pass easily (hold +0.09 ns, slew/cap far under bar, 0 DRC). Both best runs (12.63, 12.85) used AREA 3, timing-driven placement, post-GRT timing repair, cap213 and a tight target; the rest, each missing at least one of these or with very low utilisation, landed at 14.0-20.5. Setting 1 merges the two best: md5's ABC buffering/sizing, post-GRT design repair and ~9 ns target with ocs_blitter's denser floorplan (util 38), plus more slew repair and larger margins. Setting 2 tests an untried DELAY script under that physical recipe; earlier DELAY runs were confounded by weak physical settings.)
- round 2 [xnp-PPU-003] clock target 9.0 ns -> T_eff 12.387 ns, FEASIBLE
  setting {"period_frac": 0.5, "FP_CORE_UTIL": 40, "density_delta": 15, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": false, "SYNTH_SIZING": false, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": false, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.3228, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.2123, "DESIGN_REPAIR_MAX_SLEW_PCT": 22, "DESIGN_REPAIR_MAX_CAP_PCT": 29, "RC_MODEL": "cap213"}
  scores: constraints [router DRC errors, minus the worst hold slack (ns), slew/cap pins minus the bar] = [0, -0.093, -3049]; FEASIBLE only if all three are <= 0
  (your rationale then: Every AREA 3, cap213, timing-driven run with post-GRT timing repair lands at 12.59-12.85 ns, and constraints are far from binding (hold +0.08 ns, <=10 slew/cap pins, 0 DRC); DELAY scripts, stock RC and low-utilisation runs did worse. ocs_blitter reached 12.85 from an 11.1 ns target (slack only -1.7 ns) without ABC buffering/sizing or post-GRT design repair, while the 9 ns runs ended near -3.6 ns. Setting 1 reruns ocs_blitter changing only the target to 9 ns: it separates target effect from recipe effect and could beat 12.585. Setting 2 keeps the best run's recipe and target but compacts placement (util 46, density 62) for shorter wires and repairs slew/cap harder (35/25%) to cut wire delay.)
- round 2 [xnp-PPU-004] clock target 9.0 ns -> T_eff 12.485 ns, FEASIBLE
  setting {"period_frac": 0.5, "FP_CORE_UTIL": 46, "density_delta": 16, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": true, "SYNTH_SIZING": true, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.3, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.3, "DESIGN_REPAIR_MAX_SLEW_PCT": 35, "DESIGN_REPAIR_MAX_CAP_PCT": 25, "RC_MODEL": "cap213"}
  scores: constraints [router DRC errors, minus the worst hold slack (ns), slew/cap pins minus the bar] = [0, -0.092, -3049]; FEASIBLE only if all three are <= 0
  (your rationale then: Every AREA 3, cap213, timing-driven run with post-GRT timing repair lands at 12.59-12.85 ns, and constraints are far from binding (hold +0.08 ns, <=10 slew/cap pins, 0 DRC); DELAY scripts, stock RC and low-utilisation runs did worse. ocs_blitter reached 12.85 from an 11.1 ns target (slack only -1.7 ns) without ABC buffering/sizing or post-GRT design repair, while the 9 ns runs ended near -3.6 ns. Setting 1 reruns ocs_blitter changing only the target to 9 ns: it separates target effect from recipe effect and could beat 12.585. Setting 2 keeps the best run's recipe and target but compacts placement (util 46, density 62) for shorter wires and repairs slew/cap harder (35/25%) to cut wire delay.)

TASK. Round 3 of 4. Propose exactly 2 NEW settings for this design (different from every setting above),
chosen to lower the best feasible T_eff, using what the scores tell you. Reply with JSON only, in this form:
{"rationale": "<at most 120 words: what the scores suggest and why these settings>",
 "settings": [{<all 15 knobs>}, {<all 15 knobs>}]}
