You are tuning the settings of an open-source chip design flow (LibreLane/OpenROAD on the SkyWater sky130 130 nm
process) for one design. Use ONLY the information in this message: do not read files, run commands, search, or use
anything you may know about other runs or designs. Reply with the JSON described at the end and nothing else.

GOAL. Find settings that let this design pass signoff at the shortest clock period. Each run is scored by its effective
clock T_eff = (clock target it was given) - (worst setup slack over 9 signoff corners); lower is better. A run counts
only if it is FEASIBLE: hold slack >= 0 at every corner, zero router DRC errors, and no more slew/capacitance violation
pins (summed over the 9 corners) than the bar, which is set by the stock flow's run on this design. Note: T_eff from a
run aimed at a much looser or tighter target can be optimistic; the best run will later be re-checked at its T_eff.

DESIGN. zipdiv: ZipCPU integer divider. Default clock period 19.09 ns. Stock flow: about 1627 standard cells. Bar: 295
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
'round' runs are your own earlier proposals, with your rationale). Each run shows its setting and a signoff summary.
- start blabla [x6z-zipdiv-001] clock target 17.72 ns -> T_eff 8.246 ns, FEASIBLE
  setting {"period_frac": 0.928473063355609, "FP_CORE_UTIL": 27, "density_delta": 25, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": true, "SYNTH_SIZING": true, "PL_TIMING_DRIVEN": false, "PL_ROUTABILITY_DRIVEN": true, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": false, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.3734844189074291, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.16520668545533518, "DESIGN_REPAIR_MAX_SLEW_PCT": 39, "DESIGN_REPAIR_MAX_CAP_PCT": 18, "RC_MODEL": "orfs"}
  setup: worst slack +9.474 ns at ss 100C 1.60V max-RC (reg-to-reg worst +11.097 ns; the worst path touches an input/output port); TNS 0.00 ns; 0 violating endpoints at the target
  hold: worst slack +0.094 ns at ff -40C 1.95V min-RC; 0 violations; 0 hold buffers inserted
  electrical: 0 slew/cap pins summed over corners (bar 295); worst corner max-slew 0, max-cap 0; fanout violations 1
  cells: 2222 std cells, 282 timing-repair buffers; std-cell area 15,265 um2; utilisation 35%
  routing: wirelength 35,814 um (pre-route estimate 32,398); detailed-route DRC by iteration [422, 94, 111, 14, 0], final 0
  clock: skew 0.269 ns (setup) / -0.324 ns (hold); power 1.04 mW; flow runtime 2.3 min
- start des [x6z-zipdiv-002] clock target 9.23 ns -> T_eff 8.912 ns, FEASIBLE
  setting {"period_frac": 0.48352759747215784, "FP_CORE_UTIL": 27, "density_delta": 19, "SYNTH_STRATEGY": "DELAY 4", "SYNTH_ABC_BUFFERING": false, "SYNTH_SIZING": false, "PL_TIMING_DRIVEN": false, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": false, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.16636921385131967, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.25116636617682997, "DESIGN_REPAIR_MAX_SLEW_PCT": 25, "DESIGN_REPAIR_MAX_CAP_PCT": 40, "RC_MODEL": "cap213"}
  setup: worst slack +0.318 ns at ss 100C 1.60V max-RC (reg-to-reg worst +0.318 ns); TNS 0.00 ns; 0 violating endpoints at the target
  hold: worst slack +0.071 ns at ff -40C 1.95V min-RC; 0 violations; 0 hold buffers inserted
  electrical: 0 slew/cap pins summed over corners (bar 295); worst corner max-slew 0, max-cap 0; fanout violations 1
  cells: 2050 std cells, 248 timing-repair buffers; std-cell area 15,605 um2; utilisation 35%
  routing: wirelength 40,338 um (pre-route estimate 35,335); detailed-route DRC by iteration [509, 157, 122, 26, 0], final 0
  clock: skew 0.271 ns (setup) / -0.326 ns (hold); power 2.03 mW; flow runtime 2.9 min
- start bm64 [x6z-zipdiv-003] clock target 9.62 ns -> T_eff 9.362 ns, FEASIBLE
  setting {"period_frac": 0.503863953041454, "FP_CORE_UTIL": 21, "density_delta": 14, "SYNTH_STRATEGY": "DELAY 3", "SYNTH_ABC_BUFFERING": false, "SYNTH_SIZING": true, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": false, "RUN_POST_GRT_DESIGN_REPAIR": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.24619915855228341, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.10560593983481525, "DESIGN_REPAIR_MAX_SLEW_PCT": 30, "DESIGN_REPAIR_MAX_CAP_PCT": 11, "RC_MODEL": "orfs"}
  setup: worst slack +0.258 ns at ss 100C 1.60V max-RC (reg-to-reg worst +0.258 ns); TNS 0.00 ns; 0 violating endpoints at the target
  hold: worst slack +0.093 ns at ff -40C 1.95V min-RC; 0 violations; 32 hold buffers inserted
  electrical: 0 slew/cap pins summed over corners (bar 295); worst corner max-slew 0, max-cap 0; fanout violations 1
  cells: 2216 std cells, 343 timing-repair buffers; std-cell area 15,672 um2; utilisation 28%
  routing: wirelength 44,656 um (pre-route estimate 38,986); detailed-route DRC by iteration [439, 76, 90, 2, 2, 0], final 0
  clock: skew 0.274 ns (setup) / -0.332 ns (hold); power 2.07 mW; flow runtime 2.5 min
- start ocs_blitter [x6z-zipdiv-004] clock target 11.78 ns -> T_eff 7.548 ns, FEASIBLE
  setting {"period_frac": 0.6171955706800487, "FP_CORE_UTIL": 40, "density_delta": 15, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": false, "SYNTH_SIZING": false, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": false, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.32283309180712455, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.21234668380681754, "DESIGN_REPAIR_MAX_SLEW_PCT": 22, "DESIGN_REPAIR_MAX_CAP_PCT": 29, "RC_MODEL": "cap213"}
  setup: worst slack +4.232 ns at ss 100C 1.60V max-RC (reg-to-reg worst +4.232 ns); TNS 0.00 ns; 0 violating endpoints at the target
  hold: worst slack +0.095 ns at ff -40C 1.95V min-RC; 0 violations; 0 hold buffers inserted
  electrical: 0 slew/cap pins summed over corners (bar 295); worst corner max-slew 0, max-cap 0; fanout violations 1
  cells: 1959 std cells, 277 timing-repair buffers; std-cell area 14,735 um2; utilisation 50%
  routing: wirelength 30,569 um (pre-route estimate 27,999); detailed-route DRC by iteration [352, 102, 74, 0], final 0
  clock: skew 0.271 ns (setup) / -0.319 ns (hold); power 1.53 mW; flow runtime 1.4 min
- start md5 [x6z-zipdiv-005] clock target 9.48 ns -> T_eff 7.640 ns, FEASIBLE
  setting {"period_frac": 0.49666758392155613, "FP_CORE_UTIL": 30, "density_delta": 11, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": true, "SYNTH_SIZING": true, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.17835233972832615, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.09022060448969806, "DESIGN_REPAIR_MAX_SLEW_PCT": 25, "DESIGN_REPAIR_MAX_CAP_PCT": 20, "RC_MODEL": "cap213"}
  setup: worst slack +1.840 ns at ss 100C 1.60V max-RC (reg-to-reg worst +1.840 ns); TNS 0.00 ns; 0 violating endpoints at the target
  hold: worst slack +0.086 ns at ff -40C 1.95V min-RC; 0 violations; 0 hold buffers inserted
  electrical: 0 slew/cap pins summed over corners (bar 295); worst corner max-slew 0, max-cap 0; fanout violations 1
  cells: 2092 std cells, 277 timing-repair buffers; std-cell area 14,898 um2; utilisation 38%
  routing: wirelength 33,971 um (pre-route estimate 31,038); detailed-route DRC by iteration [313, 51, 22, 2, 0], final 0
  clock: skew 0.275 ns (setup) / -0.323 ns (hold); power 1.91 mW; flow runtime 1.7 min
- start picorv32 [x6z-zipdiv-006] clock target 9.97 ns -> T_eff 7.942 ns, FEASIBLE
  setting {"period_frac": 0.5222176203433402, "FP_CORE_UTIL": 38, "density_delta": 5, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": false, "SYNTH_SIZING": false, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": true, "RUN_POST_GRT_RESIZER_TIMING": false, "RUN_POST_GRT_DESIGN_REPAIR": false, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.2585143226133421, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.0285628051553697, "DESIGN_REPAIR_MAX_SLEW_PCT": 22, "DESIGN_REPAIR_MAX_CAP_PCT": 20, "RC_MODEL": "stock"}
  setup: worst slack +2.028 ns at ss 100C 1.60V max-RC (reg-to-reg worst +2.028 ns); TNS 0.00 ns; 0 violating endpoints at the target
  hold: worst slack +0.107 ns at ff -40C 1.95V min-RC; 0 violations; 126 hold buffers inserted
  electrical: 0 slew/cap pins summed over corners (bar 295); worst corner max-slew 0, max-cap 0; fanout violations 1
  cells: 1977 std cells, 288 timing-repair buffers; std-cell area 14,887 um2; utilisation 49%
  routing: wirelength 32,624 um (pre-route estimate 29,667); detailed-route DRC by iteration [222, 67, 70, 0], final 0
  clock: skew 0.274 ns (setup) / -0.322 ns (hold); power 1.81 mW; flow runtime 2.0 min
- start y_huff [x6z-zipdiv-007] clock target 18.63 ns -> T_eff 8.394 ns, FEASIBLE
  setting {"period_frac": 0.976013443761732, "FP_CORE_UTIL": 37, "density_delta": 18, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": true, "SYNTH_SIZING": true, "PL_TIMING_DRIVEN": false, "PL_ROUTABILITY_DRIVEN": true, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.041485267124613805, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.03869271067313256, "DESIGN_REPAIR_MAX_SLEW_PCT": 22, "DESIGN_REPAIR_MAX_CAP_PCT": 27, "RC_MODEL": "stock"}
  setup: worst slack +10.236 ns at ss 100C 1.60V max-RC (reg-to-reg worst +11.144 ns; the worst path touches an input/output port); TNS 0.00 ns; 0 violating endpoints at the target
  hold: worst slack +0.108 ns at ff -40C 1.95V min-RC; 0 violations; 0 hold buffers inserted
  electrical: 19 slew/cap pins summed over corners (bar 295); worst corner max-slew 19, max-cap 0; fanout violations 1
  cells: 2008 std cells, 257 timing-repair buffers; std-cell area 15,027 um2; utilisation 48%
  routing: wirelength 33,297 um (pre-route estimate 30,324); detailed-route DRC by iteration [342, 73, 87, 0], final 0
  clock: skew 0.274 ns (setup) / -0.322 ns (hold); power 0.98 mW; flow runtime 2.3 min
- start aes_cipher [x6z-zipdiv-008] clock target 10.99 ns -> T_eff 12.406 ns, FEASIBLE
  setting {"period_frac": 0.5759360256713374, "FP_CORE_UTIL": 23, "density_delta": 7, "SYNTH_STRATEGY": "AREA 2", "SYNTH_ABC_BUFFERING": true, "SYNTH_SIZING": false, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.09845674949215728, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.3225578512156802, "DESIGN_REPAIR_MAX_SLEW_PCT": 38, "DESIGN_REPAIR_MAX_CAP_PCT": 26, "RC_MODEL": "stock"}
  setup: worst slack -1.416 ns at ss 100C 1.60V max-RC (reg-to-reg worst -1.416 ns); TNS -11.33 ns; 42 violating endpoints at the target
  hold: worst slack +0.055 ns at ff -40C 1.95V min-RC; 0 violations; 1 hold buffers inserted
  electrical: 0 slew/cap pins summed over corners (bar 295); worst corner max-slew 0, max-cap 0; fanout violations 1
  cells: 1933 std cells, 397 timing-repair buffers; std-cell area 14,169 um2; utilisation 33%
  routing: wirelength 33,241 um (pre-route estimate 30,321); detailed-route DRC by iteration [0, 78, 48, 0], final 0
  clock: skew 0.275 ns (setup) / -0.325 ns (hold); power 1.62 mW; flow runtime 2.8 min
- round 1 [x8a-zipdiv-001] clock target 8.59 ns -> T_eff 6.763 ns, FEASIBLE
  setting {"period_frac": 0.45, "FP_CORE_UTIL": 27, "density_delta": 25, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": true, "SYNTH_SIZING": true, "PL_TIMING_DRIVEN": false, "PL_ROUTABILITY_DRIVEN": true, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": false, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.4, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.2, "DESIGN_REPAIR_MAX_SLEW_PCT": 40, "DESIGN_REPAIR_MAX_CAP_PCT": 18, "RC_MODEL": "orfs"}
  setup: worst slack +1.827 ns at ss 100C 1.60V max-RC (reg-to-reg worst +1.827 ns); TNS 0.00 ns; 0 violating endpoints at the target
  hold: worst slack +0.094 ns at ff -40C 1.95V min-RC; 0 violations; 0 hold buffers inserted
  electrical: 0 slew/cap pins summed over corners (bar 295); worst corner max-slew 0, max-cap 0; fanout violations 1
  cells: 2223 std cells, 283 timing-repair buffers; std-cell area 15,293 um2; utilisation 36%
  routing: wirelength 35,834 um (pre-route estimate 32,385); detailed-route DRC by iteration [478, 140, 116, 0], final 0
  clock: skew 0.269 ns (setup) / -0.325 ns (hold); power 2.14 mW; flow runtime 2.3 min
  (your rationale then: AREA 3 is the netlist to keep: AREA 2 and DELAY 3/4 needed timing repair and stalled at 8.9-12.4 ns, while every AREA 3 run kept large positive slack, so T_eff there is natural delay shaped by electrical repair. Blabla (orfs RC, 39% slew margin) had the fastest reg-to-reg path (6.62 ns), but its loose 17.7 ns target inflated port delays, so an I/O path set T_eff=8.25. Setting 1 reruns blabla at the minimum target (8.59 ns), where port delays shrink and reg-to-reg should limit. Setting 2 keeps AREA 3 and maximal slew margin but adds cap213, timing-driven placement, post-GRT design repair and stronger cap repair.)
- round 1 [x8a-zipdiv-002] clock target 8.59 ns -> T_eff 7.779 ns, FEASIBLE
  setting {"period_frac": 0.45, "FP_CORE_UTIL": 27, "density_delta": 25, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": true, "SYNTH_SIZING": true, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": true, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.4, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.4, "DESIGN_REPAIR_MAX_SLEW_PCT": 40, "DESIGN_REPAIR_MAX_CAP_PCT": 35, "RC_MODEL": "cap213"}
  setup: worst slack +0.811 ns at ss 100C 1.60V max-RC (reg-to-reg worst +0.811 ns); TNS 0.00 ns; 0 violating endpoints at the target
  hold: worst slack +0.096 ns at ff -40C 1.95V min-RC; 0 violations; 0 hold buffers inserted
  electrical: 0 slew/cap pins summed over corners (bar 295); worst corner max-slew 0, max-cap 0; fanout violations 1
  cells: 2212 std cells, 328 timing-repair buffers; std-cell area 15,156 um2; utilisation 35%
  routing: wirelength 33,313 um (pre-route estimate 30,766); detailed-route DRC by iteration [318, 75, 68, 2, 2, 0], final 0
  clock: skew 0.270 ns (setup) / -0.327 ns (hold); power 2.11 mW; flow runtime 2.5 min
  (your rationale then: AREA 3 is the netlist to keep: AREA 2 and DELAY 3/4 needed timing repair and stalled at 8.9-12.4 ns, while every AREA 3 run kept large positive slack, so T_eff there is natural delay shaped by electrical repair. Blabla (orfs RC, 39% slew margin) had the fastest reg-to-reg path (6.62 ns), but its loose 17.7 ns target inflated port delays, so an I/O path set T_eff=8.25. Setting 1 reruns blabla at the minimum target (8.59 ns), where port delays shrink and reg-to-reg should limit. Setting 2 keeps AREA 3 and maximal slew margin but adds cap213, timing-driven placement, post-GRT design repair and stronger cap repair.)
- round 2 [x8a-zipdiv-003] clock target 8.59 ns -> T_eff 6.927 ns, FEASIBLE
  setting {"period_frac": 0.45, "FP_CORE_UTIL": 35, "density_delta": 25, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": true, "SYNTH_SIZING": true, "PL_TIMING_DRIVEN": false, "PL_ROUTABILITY_DRIVEN": true, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": false, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.4, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.2, "DESIGN_REPAIR_MAX_SLEW_PCT": 40, "DESIGN_REPAIR_MAX_CAP_PCT": 12, "RC_MODEL": "orfs"}
  setup: worst slack +1.663 ns at ss 100C 1.60V max-RC (reg-to-reg worst +1.663 ns); TNS 0.00 ns; 0 violating endpoints at the target
  hold: worst slack +0.097 ns at ff -40C 1.95V min-RC; 0 violations; 0 hold buffers inserted
  electrical: 0 slew/cap pins summed over corners (bar 295); worst corner max-slew 0, max-cap 0; fanout violations 1
  cells: 2078 std cells, 279 timing-repair buffers; std-cell area 15,047 um2; utilisation 45%
  routing: wirelength 34,191 um (pre-route estimate 30,816); detailed-route DRC by iteration [335, 146, 118, 0], final 0
  clock: skew 0.271 ns (setup) / -0.321 ns (hold); power 2.12 mW; flow runtime 2.2 min
  (your rationale then: At the 8.59 ns floor target, AREA 3 keeps +0.8 to +1.8 ns slack at ss 100C, so setup repair (margin <=0.4 ns) has nothing to fix: T_eff is natural reg-to-reg delay, and ports no longer limit. Among AREA 3 runs, only the two fastest (6.62/6.76 ns) used orfs RC. Round-1 setting 2 (same synthesis; cap213, timing-driven placement, post-GRT repair, cap 35%) was 1 ns slower, with 45 more repair buffers yet less cell area. Setting 1 keeps the best recipe but compacts placement (util 35, density 60) to shorten wires and trims cap-driven buffering (cap 12%); slew/cap headroom against the 295 bar is large. Setting 2 adds only timing-driven placement, isolating whether it caused that regression.)
- round 2 [x8a-zipdiv-004] clock target 8.59 ns -> T_eff 7.475 ns, FEASIBLE
  setting {"period_frac": 0.45, "FP_CORE_UTIL": 27, "density_delta": 25, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": true, "SYNTH_SIZING": true, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": true, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": false, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.4, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.2, "DESIGN_REPAIR_MAX_SLEW_PCT": 40, "DESIGN_REPAIR_MAX_CAP_PCT": 18, "RC_MODEL": "orfs"}
  setup: worst slack +1.115 ns at ss 100C 1.60V max-RC (reg-to-reg worst +1.115 ns); TNS 0.00 ns; 0 violating endpoints at the target
  hold: worst slack +0.095 ns at ff -40C 1.95V min-RC; 0 violations; 0 hold buffers inserted
  electrical: 0 slew/cap pins summed over corners (bar 295); worst corner max-slew 0, max-cap 0; fanout violations 1
  cells: 2209 std cells, 325 timing-repair buffers; std-cell area 15,098 um2; utilisation 35%
  routing: wirelength 33,379 um (pre-route estimate 30,672); detailed-route DRC by iteration [337, 127, 107, 1, 0], final 0
  clock: skew 0.272 ns (setup) / -0.325 ns (hold); power 2.11 mW; flow runtime 1.4 min
  (your rationale then: At the 8.59 ns floor target, AREA 3 keeps +0.8 to +1.8 ns slack at ss 100C, so setup repair (margin <=0.4 ns) has nothing to fix: T_eff is natural reg-to-reg delay, and ports no longer limit. Among AREA 3 runs, only the two fastest (6.62/6.76 ns) used orfs RC. Round-1 setting 2 (same synthesis; cap213, timing-driven placement, post-GRT repair, cap 35%) was 1 ns slower, with 45 more repair buffers yet less cell area. Setting 1 keeps the best recipe but compacts placement (util 35, density 60) to shorten wires and trims cap-driven buffering (cap 12%); slew/cap headroom against the 295 bar is large. Setting 2 adds only timing-driven placement, isolating whether it caused that regression.)

TASK. Round 3 of 4. Propose exactly 2 NEW settings for this design (different from every setting above),
chosen to lower the best feasible T_eff, using what the signoff summaries tell you (for example which corner limits
setup, whether the worst path touches a port, hold-buffer counts, slew/cap pins against the bar, congestion, wire length
against the pre-route estimate). Reply with JSON only, in this form:
{"rationale": "<at most 120 words: what the reports suggest and why these settings>",
 "settings": [{<all 15 knobs>}, {<all 15 knobs>}]}
