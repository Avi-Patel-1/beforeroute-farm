You are tuning the settings of an open-source chip design flow (LibreLane/OpenROAD on the SkyWater sky130 130 nm
process) for one design. Use ONLY the information in this message: do not read files, run commands, search, or use
anything you may know about other runs or designs. Reply with the JSON described at the end and nothing else.

GOAL. Find settings that let this design pass signoff at the shortest clock period. Each run is scored by its effective
clock T_eff = (clock target it was given) - (worst setup slack over 9 signoff corners); lower is better. A run counts
only if it is FEASIBLE: hold slack >= 0 at every corner, zero router DRC errors, and no more slew/capacitance violation
pins (summed over the 9 corners) than the bar, which is set by the stock flow's run on this design. Note: T_eff from a
run aimed at a much looser or tighter target can be optimistic; the best run will later be re-checked at its T_eff.

DESIGN. usb_cdc_core: USB CDC device core (ultra-embedded). Default clock period 15.6 ns. Stock flow: about ? standard cells. Bar: 309
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
- start blabla [x6z-usb_cdc_core-009] clock target 14.48 ns -> T_eff 9.018 ns, FEASIBLE
  setting {"period_frac": 0.928473063355609, "FP_CORE_UTIL": 27, "density_delta": 25, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": true, "SYNTH_SIZING": true, "PL_TIMING_DRIVEN": false, "PL_ROUTABILITY_DRIVEN": true, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": false, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.3734844189074291, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.16520668545533518, "DESIGN_REPAIR_MAX_SLEW_PCT": 39, "DESIGN_REPAIR_MAX_CAP_PCT": 18, "RC_MODEL": "orfs"}
  scores: constraints [router DRC errors, minus the worst hold slack (ns), slew/cap pins minus the bar] = [0, -0.095, -298]; FEASIBLE only if all three are <= 0
- start des [x6z-usb_cdc_core-010] clock target 7.54 ns -> T_eff 7.300 ns, FEASIBLE
  setting {"period_frac": 0.48352759747215784, "FP_CORE_UTIL": 27, "density_delta": 19, "SYNTH_STRATEGY": "DELAY 4", "SYNTH_ABC_BUFFERING": false, "SYNTH_SIZING": false, "PL_TIMING_DRIVEN": false, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": false, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.16636921385131967, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.25116636617682997, "DESIGN_REPAIR_MAX_SLEW_PCT": 25, "DESIGN_REPAIR_MAX_CAP_PCT": 40, "RC_MODEL": "cap213"}
  scores: constraints [router DRC errors, minus the worst hold slack (ns), slew/cap pins minus the bar] = [0, -0.093, -309]; FEASIBLE only if all three are <= 0
- start bm64 [x6z-usb_cdc_core-011] clock target 7.86 ns -> T_eff 7.638 ns, FEASIBLE
  setting {"period_frac": 0.503863953041454, "FP_CORE_UTIL": 21, "density_delta": 14, "SYNTH_STRATEGY": "DELAY 3", "SYNTH_ABC_BUFFERING": false, "SYNTH_SIZING": true, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": false, "RUN_POST_GRT_DESIGN_REPAIR": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.24619915855228341, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.10560593983481525, "DESIGN_REPAIR_MAX_SLEW_PCT": 30, "DESIGN_REPAIR_MAX_CAP_PCT": 11, "RC_MODEL": "orfs"}
  scores: constraints [router DRC errors, minus the worst hold slack (ns), slew/cap pins minus the bar] = [0, -0.091, -309]; FEASIBLE only if all three are <= 0
- start ocs_blitter [x6z-usb_cdc_core-012] clock target 9.63 ns -> T_eff 7.804 ns, FEASIBLE
  setting {"period_frac": 0.6171955706800487, "FP_CORE_UTIL": 40, "density_delta": 15, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": false, "SYNTH_SIZING": false, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": false, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.32283309180712455, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.21234668380681754, "DESIGN_REPAIR_MAX_SLEW_PCT": 22, "DESIGN_REPAIR_MAX_CAP_PCT": 29, "RC_MODEL": "cap213"}
  scores: constraints [router DRC errors, minus the worst hold slack (ns), slew/cap pins minus the bar] = [0, -0.093, -309]; FEASIBLE only if all three are <= 0
- start md5 [x6z-usb_cdc_core-013] clock target 7.75 ns -> T_eff 6.955 ns, FEASIBLE
  setting {"period_frac": 0.49666758392155613, "FP_CORE_UTIL": 30, "density_delta": 11, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": true, "SYNTH_SIZING": true, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.17835233972832615, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.09022060448969806, "DESIGN_REPAIR_MAX_SLEW_PCT": 25, "DESIGN_REPAIR_MAX_CAP_PCT": 20, "RC_MODEL": "cap213"}
  scores: constraints [router DRC errors, minus the worst hold slack (ns), slew/cap pins minus the bar] = [0, -0.085, -309]; FEASIBLE only if all three are <= 0
- start picorv32 [x6z-usb_cdc_core-014] clock target 8.15 ns -> T_eff 7.556 ns, FEASIBLE
  setting {"period_frac": 0.5222176203433402, "FP_CORE_UTIL": 38, "density_delta": 5, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": false, "SYNTH_SIZING": false, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": true, "RUN_POST_GRT_RESIZER_TIMING": false, "RUN_POST_GRT_DESIGN_REPAIR": false, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.2585143226133421, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.0285628051553697, "DESIGN_REPAIR_MAX_SLEW_PCT": 22, "DESIGN_REPAIR_MAX_CAP_PCT": 20, "RC_MODEL": "stock"}
  scores: constraints [router DRC errors, minus the worst hold slack (ns), slew/cap pins minus the bar] = [0, -0.073, -309]; FEASIBLE only if all three are <= 0
- start y_huff [x6z-usb_cdc_core-015] clock target 15.23 ns -> T_eff 10.052 ns, FEASIBLE
  setting {"period_frac": 0.976013443761732, "FP_CORE_UTIL": 37, "density_delta": 18, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": true, "SYNTH_SIZING": true, "PL_TIMING_DRIVEN": false, "PL_ROUTABILITY_DRIVEN": true, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.041485267124613805, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.03869271067313256, "DESIGN_REPAIR_MAX_SLEW_PCT": 22, "DESIGN_REPAIR_MAX_CAP_PCT": 27, "RC_MODEL": "stock"}
  scores: constraints [router DRC errors, minus the worst hold slack (ns), slew/cap pins minus the bar] = [0, -0.103, -276]; FEASIBLE only if all three are <= 0
- start aes_cipher [x6z-usb_cdc_core-016] clock target 8.98 ns -> T_eff 9.032 ns, FEASIBLE
  setting {"period_frac": 0.5759360256713374, "FP_CORE_UTIL": 23, "density_delta": 7, "SYNTH_STRATEGY": "AREA 2", "SYNTH_ABC_BUFFERING": true, "SYNTH_SIZING": false, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.09845674949215728, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.3225578512156802, "DESIGN_REPAIR_MAX_SLEW_PCT": 38, "DESIGN_REPAIR_MAX_CAP_PCT": 26, "RC_MODEL": "stock"}
  scores: constraints [router DRC errors, minus the worst hold slack (ns), slew/cap pins minus the bar] = [0, -0.104, -309]; FEASIBLE only if all three are <= 0
- round 1 [xnp-usb_cdc_core-001] clock target 7.02 ns -> T_eff 6.637 ns, FEASIBLE
  setting {"period_frac": 0.45, "FP_CORE_UTIL": 30, "density_delta": 11, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": true, "SYNTH_SIZING": true, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.18, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.09, "DESIGN_REPAIR_MAX_SLEW_PCT": 25, "DESIGN_REPAIR_MAX_CAP_PCT": 20, "RC_MODEL": "cap213"}
  scores: constraints [router DRC errors, minus the worst hold slack (ns), slew/cap pins minus the bar] = [0, -0.091, -309]; FEASIBLE only if all three are <= 0
  (your rationale then: All 8 runs are feasible with wide hold (>=0.07 ns) and slew/cap headroom, so constraints are not binding; T_eff tracks the target and the recipe. AREA 3 runs beat DELAY runs at similar targets (md5 6.955 at 7.75, picorv32 7.556 at 8.15 vs DELAY 7.30 and 7.64), and the best run, md5, uniquely combines AREA 3 with ABC buffering+sizing, timing-driven placement, both post-GRT repairs and cap213. Setting 1: md5 recipe at the tightest allowed target (0.45 = 7.02 ns), close to the 6.955 already reached, so T_eff should survive re-check. Setting 2: same, but larger setup margins (0.35/0.25) so repair aims below the 7.02 ns floor of period_frac.)
- round 1 [xnp-usb_cdc_core-002] clock target 7.02 ns -> T_eff 6.408 ns, FEASIBLE
  setting {"period_frac": 0.45, "FP_CORE_UTIL": 30, "density_delta": 11, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": true, "SYNTH_SIZING": true, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.35, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.25, "DESIGN_REPAIR_MAX_SLEW_PCT": 25, "DESIGN_REPAIR_MAX_CAP_PCT": 20, "RC_MODEL": "cap213"}
  scores: constraints [router DRC errors, minus the worst hold slack (ns), slew/cap pins minus the bar] = [0, -0.089, -309]; FEASIBLE only if all three are <= 0
  (your rationale then: All 8 runs are feasible with wide hold (>=0.07 ns) and slew/cap headroom, so constraints are not binding; T_eff tracks the target and the recipe. AREA 3 runs beat DELAY runs at similar targets (md5 6.955 at 7.75, picorv32 7.556 at 8.15 vs DELAY 7.30 and 7.64), and the best run, md5, uniquely combines AREA 3 with ABC buffering+sizing, timing-driven placement, both post-GRT repairs and cap213. Setting 1: md5 recipe at the tightest allowed target (0.45 = 7.02 ns), close to the 6.955 already reached, so T_eff should survive re-check. Setting 2: same, but larger setup margins (0.35/0.25) so repair aims below the 7.02 ns floor of period_frac.)
- round 2 [xnp-usb_cdc_core-003] clock target 7.02 ns -> T_eff 6.258 ns, FEASIBLE
  setting {"period_frac": 0.45, "FP_CORE_UTIL": 30, "density_delta": 11, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": true, "SYNTH_SIZING": true, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.4, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.4, "DESIGN_REPAIR_MAX_SLEW_PCT": 25, "DESIGN_REPAIR_MAX_CAP_PCT": 20, "RC_MODEL": "cap213"}
  scores: constraints [router DRC errors, minus the worst hold slack (ns), slew/cap pins minus the bar] = [0, -0.091, -309]; FEASIBLE only if all three are <= 0
  (your rationale then: All runs are feasible (hold >= +0.07 ns, slew/cap far under the bar), so constraints are not binding. period_frac is already at its 0.45 floor (7.02 ns), so gains must come from repair over-achieving: raising setup margins 0.18/0.09 to 0.35/0.25 cut T_eff 6.637 to 6.408, and runs beat their repair aim by 0.2-0.7 ns. Setting 1: the same best recipe (AREA 3, ABC buffering+sizing, timing-driven placement, both post-GRT repairs, cap213) with both margins maxed at 0.4. Setting 2: identical but a more compact floorplan (util 40, density 55%, which routed cleanly on this design in ocs_blitter) to cut wire load on critical nets, testing floorplan as the next lever once margins are exhausted.)
- round 2 [xnp-usb_cdc_core-004] clock target 7.02 ns -> T_eff 6.356 ns, FEASIBLE
  setting {"period_frac": 0.45, "FP_CORE_UTIL": 40, "density_delta": 15, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": true, "SYNTH_SIZING": true, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.4, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.4, "DESIGN_REPAIR_MAX_SLEW_PCT": 25, "DESIGN_REPAIR_MAX_CAP_PCT": 20, "RC_MODEL": "cap213"}
  scores: constraints [router DRC errors, minus the worst hold slack (ns), slew/cap pins minus the bar] = [0, -0.088, -309]; FEASIBLE only if all three are <= 0
  (your rationale then: All runs are feasible (hold >= +0.07 ns, slew/cap far under the bar), so constraints are not binding. period_frac is already at its 0.45 floor (7.02 ns), so gains must come from repair over-achieving: raising setup margins 0.18/0.09 to 0.35/0.25 cut T_eff 6.637 to 6.408, and runs beat their repair aim by 0.2-0.7 ns. Setting 1: the same best recipe (AREA 3, ABC buffering+sizing, timing-driven placement, both post-GRT repairs, cap213) with both margins maxed at 0.4. Setting 2: identical but a more compact floorplan (util 40, density 55%, which routed cleanly on this design in ocs_blitter) to cut wire load on critical nets, testing floorplan as the next lever once margins are exhausted.)

TASK. Round 3 of 4. Propose exactly 2 NEW settings for this design (different from every setting above),
chosen to lower the best feasible T_eff, using what the scores tell you. Reply with JSON only, in this form:
{"rationale": "<at most 120 words: what the scores suggest and why these settings>",
 "settings": [{<all 15 knobs>}, {<all 15 knobs>}]}
