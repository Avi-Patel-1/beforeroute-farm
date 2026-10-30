You are guiding a Bayesian optimizer (Optuna's TPE sampler) that tunes the settings of an open-source chip design
flow (LibreLane/OpenROAD on the SkyWater sky130 130 nm process) for one design. Use ONLY the information in this message:
do not read files, run commands, search, or use anything you may know about other runs or designs. Reply with the JSON
described at the end and nothing else.

GOAL. Find settings that let this design pass signoff at the shortest clock period. Each run is scored by its effective
clock T_eff = (clock target it was given) - (worst setup slack over 9 signoff corners); lower is better. A run counts
only if it is FEASIBLE: hold slack >= 0 at every corner, zero router DRC errors, and no more slew/capacitance violation
pins (summed over the 9 corners) than the bar, which is set by the stock flow's run on this design. T_eff from a run
aimed at a much looser or tighter target can be optimistic: the best run will later be re-run at its T_eff, and then
again at the clock each passing re-run claims, and the result is the shortest clock that actually passes.

HOW THE SEARCH WORKS. The optimizer proposes 2 settings per round, for 4 rounds (8 runs), and learns from
every run's score and feasibility (including the start runs below). You do not propose settings. You write a POLICY:
you may PIN up to 8 knobs to fixed values. For every new proposal the optimizer uses your pinned values and
chooses all other knobs itself from the history. An empty policy {} leaves the optimizer unchanged. This is a revision: you see the
results of the rounds run under the earlier policies, and you may keep the policy, change pinned values, add pins or
remove pins.

DESIGN. zipdiv: ZipCPU integer divider. Default clock period 19.09 ns. Stock flow: about 1627 standard cells. Bar: 295
slew/cap pins.

KNOBS (pin only these, within these ranges):
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

HISTORY on this design (12 runs so far: 8 'start' runs are settings found on other designs and applied unchanged; 'round' runs were proposed by the optimizer under your policies).
Each run shows its setting and a signoff summary.
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
- round 1 [xah2-zipdiv-001] clock target 8.59 ns -> T_eff 7.594 ns, FEASIBLE
  pinned by the policy then: {"period_frac": 0.45, "SYNTH_STRATEGY": "AREA 3", "RC_MODEL": "cap213", "PL_TIMING_DRIVEN": true, "RUN_POST_GRT_RESIZER_TIMING": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.3, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.3}
  setting {"period_frac": 0.45, "FP_CORE_UTIL": 22, "density_delta": 16, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": false, "SYNTH_SIZING": false, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": false, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.3, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.3, "DESIGN_REPAIR_MAX_SLEW_PCT": 13, "DESIGN_REPAIR_MAX_CAP_PCT": 23, "RC_MODEL": "cap213"}
  setup: worst slack +0.996 ns at ss 100C 1.60V max-RC (reg-to-reg worst +0.996 ns); TNS 0.00 ns; 0 violating endpoints at the target
  hold: worst slack +0.086 ns at ff -40C 1.95V min-RC; 0 violations; 0 hold buffers inserted
  electrical: 0 slew/cap pins summed over corners (bar 295); worst corner max-slew 0, max-cap 0; fanout violations 1
  cells: 2268 std cells, 277 timing-repair buffers; std-cell area 15,118 um2; utilisation 29%
  routing: wirelength 36,488 um (pre-route estimate 33,147); detailed-route DRC by iteration [330, 30, 22, 1, 0], final 0
  clock: skew 0.269 ns (setup) / -0.332 ns (hold); power 2.12 mW; flow runtime 1.6 min
- round 1 [xah2-zipdiv-002] clock target 8.59 ns -> T_eff 7.477 ns, FEASIBLE
  pinned by the policy then: {"period_frac": 0.45, "SYNTH_STRATEGY": "AREA 3", "RC_MODEL": "cap213", "PL_TIMING_DRIVEN": true, "RUN_POST_GRT_RESIZER_TIMING": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.3, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.3}
  setting {"period_frac": 0.45, "FP_CORE_UTIL": 45, "density_delta": 20, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": false, "SYNTH_SIZING": false, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": false, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.3, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.3, "DESIGN_REPAIR_MAX_SLEW_PCT": 18, "DESIGN_REPAIR_MAX_CAP_PCT": 23, "RC_MODEL": "cap213"}
  setup: worst slack +1.113 ns at ss 100C 1.60V max-RC (reg-to-reg worst +1.113 ns); TNS 0.00 ns; 0 violating endpoints at the target
  hold: worst slack +0.098 ns at ff -40C 1.95V min-RC; 0 violations; 0 hold buffers inserted
  electrical: 0 slew/cap pins summed over corners (bar 295); worst corner max-slew 0, max-cap 0; fanout violations 1
  cells: 1907 std cells, 281 timing-repair buffers; std-cell area 14,722 um2; utilisation 57%
  routing: wirelength 29,716 um (pre-route estimate 27,343); detailed-route DRC by iteration [360, 104, 92, 0], final 0
  clock: skew 0.276 ns (setup) / -0.320 ns (hold); power 2.08 mW; flow runtime 2.3 min
- round 2 [xah2-zipdiv-003] clock target 8.59 ns -> T_eff 7.312 ns, FEASIBLE
  pinned by the policy then: {"period_frac": 0.45, "SYNTH_STRATEGY": "AREA 3", "RC_MODEL": "orfs", "DESIGN_REPAIR_MAX_SLEW_PCT": 40, "RUN_POST_GRT_RESIZER_TIMING": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.3, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.3, "PL_TIMING_DRIVEN": true}
  setting {"period_frac": 0.45, "FP_CORE_UTIL": 30, "density_delta": 12, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": false, "SYNTH_SIZING": false, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": false, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.3, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.3, "DESIGN_REPAIR_MAX_SLEW_PCT": 40, "DESIGN_REPAIR_MAX_CAP_PCT": 10, "RC_MODEL": "orfs"}
  setup: worst slack +1.278 ns at ss 100C 1.60V max-RC (reg-to-reg worst +1.278 ns); TNS 0.00 ns; 0 violating endpoints at the target
  hold: worst slack +0.094 ns at ff -40C 1.95V min-RC; 0 violations; 0 hold buffers inserted
  electrical: 0 slew/cap pins summed over corners (bar 295); worst corner max-slew 0, max-cap 0; fanout violations 1
  cells: 2142 std cells, 327 timing-repair buffers; std-cell area 15,046 um2; utilisation 39%
  routing: wirelength 33,890 um (pre-route estimate 31,132); detailed-route DRC by iteration [322, 50, 27, 0], final 0
  clock: skew 0.274 ns (setup) / -0.324 ns (hold); power 2.12 mW; flow runtime 1.6 min
- round 2 [xah2-zipdiv-004] clock target 8.59 ns -> T_eff 7.265 ns, FEASIBLE
  pinned by the policy then: {"period_frac": 0.45, "SYNTH_STRATEGY": "AREA 3", "RC_MODEL": "orfs", "DESIGN_REPAIR_MAX_SLEW_PCT": 40, "RUN_POST_GRT_RESIZER_TIMING": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.3, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.3, "PL_TIMING_DRIVEN": true}
  setting {"period_frac": 0.45, "FP_CORE_UTIL": 48, "density_delta": 30, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": false, "SYNTH_SIZING": false, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": true, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": false, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.3, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.3, "DESIGN_REPAIR_MAX_SLEW_PCT": 40, "DESIGN_REPAIR_MAX_CAP_PCT": 28, "RC_MODEL": "orfs"}
  setup: worst slack +1.325 ns at ss 100C 1.60V max-RC (reg-to-reg worst +1.325 ns); TNS 0.00 ns; 0 violating endpoints at the target
  hold: worst slack +0.099 ns at ff -40C 1.95V min-RC; 0 violations; 0 hold buffers inserted
  electrical: 0 slew/cap pins summed over corners (bar 295); worst corner max-slew 0, max-cap 0; fanout violations 1
  cells: 1944 std cells, 330 timing-repair buffers; std-cell area 14,857 um2; utilisation 61%
  routing: wirelength 33,454 um (pre-route estimate 30,239); detailed-route DRC by iteration [656, 236, 187, 45, 0], final 0
  clock: skew 0.270 ns (setup) / -0.319 ns (hold); power 2.10 mW; flow runtime 2.8 min

POLICIES SO FAR (yours, with your rationale then):
- round 1: pins {"period_frac": 0.45, "SYNTH_STRATEGY": "AREA 3", "RC_MODEL": "cap213", "PL_TIMING_DRIVEN": true, "RUN_POST_GRT_RESIZER_TIMING": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.3, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.3}; rationale: Setup always binds at ss/100C/1.60V max-RC, so wire RC matters; hold (+0.055 ns min), slew/cap (<=19 vs bar 295) and DRC (all 0) are non-issues. The five best runs all used AREA 3; DELAY 3/4 and AREA 2 were 1.4-4.9 ns worse. Only the loose-target runs (0.93/0.98) were port-limited (I/O delay scales with period) while their reg-to-reg was 6.6-7.5 ns, so pin the tightest target, 0.45 (8.59 ns), nearest the reachable clock. The two best runs combined cap213, timing-driven placement and post-GRT timing repair; stock-RC aes_cipher missed by 1.4 ns. Timing repair idles while the target exceeds natural delay, so margins can't be learned now but drive the re-run ratchet: pin 0.3.
- round 2: pins {"period_frac": 0.45, "SYNTH_STRATEGY": "AREA 3", "RC_MODEL": "orfs", "DESIGN_REPAIR_MAX_SLEW_PCT": 40, "RUN_POST_GRT_RESIZER_TIMING": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.3, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.3, "PL_TIMING_DRIVEN": true}; rationale: Setup binds at ss/100C max-RC; hold, slew/cap (0 vs bar 295) and DRC are clean. At 8.59 ns, AREA 3 runs keep ~+1 ns slack, so repair idles and T_eff (~7.5 ns) is natural delay. Outlier: blabla's reg-to-reg was 6.62 ns (port-limited only because I/O delay scales with its loose period). Versus y_huff (7.49 ns), which shares its synthesis and placement modes, its unique features are orfs RC and 39% slew margin, plausibly aggressive slew repair speeding critical nets. Test that at the tightest target with AREA 3. TPE's l/g now favours dropping post-GRT timing repair, so pin it, 0.3 margins and timing-driven placement to keep the T_eff re-run ratchet robust.

TASK. Write the policy for round 3 of 4, using what the signoff summaries tell you (for example which
corner limits setup, whether the worst path touches a port, hold-buffer counts, slew/cap pins against the bar,
congestion, wire length against the pre-route estimate). Reply with JSON only, in this form:
{"rationale": "<at most 120 words: what the reports suggest and why these pins>",
 "pins": {"<knob>": <value>, ...}}
