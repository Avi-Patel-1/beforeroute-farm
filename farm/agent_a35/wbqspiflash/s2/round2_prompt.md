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

DESIGN. wbqspiflash: Wishbone quad-SPI flash controller (ZipCPU). Default clock period 18.86 ns. Stock flow: about 2808 standard cells. Bar: 953
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

HISTORY on this design (10 runs so far: 8 'start' runs are settings found on other designs and applied unchanged; 'round' runs were proposed by the optimizer under your policies).
Each run shows its setting and a signoff summary.
- start blabla [x6z-wbqspiflash-001] clock target 17.51 ns -> T_eff 9.920 ns, FEASIBLE
  setting {"period_frac": 0.928473063355609, "FP_CORE_UTIL": 27, "density_delta": 25, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": true, "SYNTH_SIZING": true, "PL_TIMING_DRIVEN": false, "PL_ROUTABILITY_DRIVEN": true, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": false, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.3734844189074291, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.16520668545533518, "DESIGN_REPAIR_MAX_SLEW_PCT": 39, "DESIGN_REPAIR_MAX_CAP_PCT": 18, "RC_MODEL": "orfs"}
  setup: worst slack +7.590 ns at ss 100C 1.60V max-RC (reg-to-reg worst +10.535 ns; the worst path touches an input/output port); TNS 0.00 ns; 0 violating endpoints at the target
  hold: worst slack +0.093 ns at ff -40C 1.95V min-RC; 0 violations; 0 hold buffers inserted
  electrical: 0 slew/cap pins summed over corners (bar 953); worst corner max-slew 0, max-cap 0; fanout violations 0
  cells: 3860 std cells, 403 timing-repair buffers; std-cell area 27,584 um2; utilisation 34%
  routing: wirelength 90,137 um (pre-route estimate 82,338); detailed-route DRC by iteration [19, 2, 2, 0, 0], final 0
  clock: skew 0.288 ns (setup) / -0.349 ns (hold); power 6.62 mW; flow runtime 4.4 min
- start des [x6z-wbqspiflash-002] clock target 9.12 ns -> T_eff 8.574 ns, FEASIBLE
  setting {"period_frac": 0.48352759747215784, "FP_CORE_UTIL": 27, "density_delta": 19, "SYNTH_STRATEGY": "DELAY 4", "SYNTH_ABC_BUFFERING": false, "SYNTH_SIZING": false, "PL_TIMING_DRIVEN": false, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": false, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.16636921385131967, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.25116636617682997, "DESIGN_REPAIR_MAX_SLEW_PCT": 25, "DESIGN_REPAIR_MAX_CAP_PCT": 40, "RC_MODEL": "cap213"}
  setup: worst slack +0.546 ns at ss 100C 1.60V max-RC (reg-to-reg worst +0.546 ns); TNS 0.00 ns; 0 violating endpoints at the target
  hold: worst slack +0.083 ns at ff -40C 1.95V min-RC; 0 violations; 0 hold buffers inserted
  electrical: 0 slew/cap pins summed over corners (bar 953); worst corner max-slew 0, max-cap 0; fanout violations 2
  cells: 3832 std cells, 378 timing-repair buffers; std-cell area 28,436 um2; utilisation 35%
  routing: wirelength 93,232 um (pre-route estimate 81,441); detailed-route DRC by iteration [47, 10, 16, 0, 1, 0], final 0
  clock: skew 0.288 ns (setup) / -0.349 ns (hold); power 3.29 mW; flow runtime 5.1 min
- start bm64 [x6z-wbqspiflash-003] clock target 9.5 ns -> T_eff 9.283 ns, FEASIBLE
  setting {"period_frac": 0.503863953041454, "FP_CORE_UTIL": 21, "density_delta": 14, "SYNTH_STRATEGY": "DELAY 3", "SYNTH_ABC_BUFFERING": false, "SYNTH_SIZING": true, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": false, "RUN_POST_GRT_DESIGN_REPAIR": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.24619915855228341, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.10560593983481525, "DESIGN_REPAIR_MAX_SLEW_PCT": 30, "DESIGN_REPAIR_MAX_CAP_PCT": 11, "RC_MODEL": "orfs"}
  setup: worst slack +0.217 ns at ss 100C 1.60V max-RC (reg-to-reg worst +0.217 ns); TNS 0.00 ns; 0 violating endpoints at the target
  hold: worst slack +0.094 ns at ff -40C 1.95V min-RC; 0 violations; 82 hold buffers inserted
  electrical: 0 slew/cap pins summed over corners (bar 953); worst corner max-slew 0, max-cap 0; fanout violations 0
  cells: 3488 std cells, 625 timing-repair buffers; std-cell area 26,096 um2; utilisation 30%
  routing: wirelength 91,488 um (pre-route estimate 80,026); detailed-route DRC by iteration [58, 10, 4, 0, 0], final 0
  clock: skew 0.288 ns (setup) / -0.350 ns (hold); power 3.20 mW; flow runtime 3.6 min
- start ocs_blitter [x6z-wbqspiflash-004] clock target 11.64 ns -> T_eff 9.454 ns, FEASIBLE
  setting {"period_frac": 0.6171955706800487, "FP_CORE_UTIL": 40, "density_delta": 15, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": false, "SYNTH_SIZING": false, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": false, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.32283309180712455, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.21234668380681754, "DESIGN_REPAIR_MAX_SLEW_PCT": 22, "DESIGN_REPAIR_MAX_CAP_PCT": 29, "RC_MODEL": "cap213"}
  setup: worst slack +2.186 ns at ss 100C 1.60V max-RC (reg-to-reg worst +3.854 ns; the worst path touches an input/output port); TNS 0.00 ns; 0 violating endpoints at the target
  hold: worst slack +0.091 ns at ff -40C 1.95V min-RC; 0 violations; 0 hold buffers inserted
  electrical: 0 slew/cap pins summed over corners (bar 953); worst corner max-slew 0, max-cap 0; fanout violations 0
  cells: 3255 std cells, 445 timing-repair buffers; std-cell area 26,188 um2; utilisation 49%
  routing: wirelength 75,745 um (pre-route estimate 67,430); detailed-route DRC by iteration [67, 16, 11, 0, 0], final 0
  clock: skew 0.294 ns (setup) / -0.349 ns (hold); power 9.28 mW; flow runtime 4.6 min
- start md5 [x6z-wbqspiflash-005] clock target 9.37 ns -> T_eff 8.807 ns, FEASIBLE
  setting {"period_frac": 0.49666758392155613, "FP_CORE_UTIL": 30, "density_delta": 11, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": true, "SYNTH_SIZING": true, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.17835233972832615, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.09022060448969806, "DESIGN_REPAIR_MAX_SLEW_PCT": 25, "DESIGN_REPAIR_MAX_CAP_PCT": 20, "RC_MODEL": "cap213"}
  setup: worst slack +0.563 ns at ss 100C 1.60V max-RC (reg-to-reg worst +0.563 ns); TNS 0.00 ns; 0 violating endpoints at the target
  hold: worst slack +0.085 ns at ff -40C 1.95V min-RC; 0 violations; 0 hold buffers inserted
  electrical: 0 slew/cap pins summed over corners (bar 953); worst corner max-slew 0, max-cap 0; fanout violations 0
  cells: 3520 std cells, 452 timing-repair buffers; std-cell area 26,495 um2; utilisation 37%
  routing: wirelength 83,945 um (pre-route estimate 75,680); detailed-route DRC by iteration [18, 1, 0, 2, 0], final 0
  clock: skew 0.302 ns (setup) / -0.355 ns (hold); power 11.65 mW; flow runtime 4.4 min
- start picorv32 [x6z-wbqspiflash-006] clock target 9.85 ns -> T_eff 9.552 ns, FEASIBLE
  setting {"period_frac": 0.5222176203433402, "FP_CORE_UTIL": 38, "density_delta": 5, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": false, "SYNTH_SIZING": false, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": true, "RUN_POST_GRT_RESIZER_TIMING": false, "RUN_POST_GRT_DESIGN_REPAIR": false, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.2585143226133421, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.0285628051553697, "DESIGN_REPAIR_MAX_SLEW_PCT": 22, "DESIGN_REPAIR_MAX_CAP_PCT": 20, "RC_MODEL": "stock"}
  setup: worst slack +0.298 ns at ss 100C 1.60V max-RC (reg-to-reg worst +0.298 ns); TNS 0.00 ns; 0 violating endpoints at the target
  hold: worst slack +0.107 ns at ff -40C 1.95V min-RC; 0 violations; 242 hold buffers inserted
  electrical: 51 slew/cap pins summed over corners (bar 953); worst corner max-slew 51, max-cap 0; fanout violations 5
  cells: 3287 std cells, 454 timing-repair buffers; std-cell area 25,969 um2; utilisation 46%
  routing: wirelength 87,255 um (pre-route estimate 76,125); detailed-route DRC by iteration [9, 1, 1, 0, 0], final 0
  clock: skew 0.298 ns (setup) / -0.351 ns (hold); power 10.87 mW; flow runtime 3.7 min
- start y_huff [x6z-wbqspiflash-007] clock target 18.41 ns -> T_eff 10.149 ns, FEASIBLE
  setting {"period_frac": 0.976013443761732, "FP_CORE_UTIL": 37, "density_delta": 18, "SYNTH_STRATEGY": "AREA 3", "SYNTH_ABC_BUFFERING": true, "SYNTH_SIZING": true, "PL_TIMING_DRIVEN": false, "PL_ROUTABILITY_DRIVEN": true, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.041485267124613805, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.03869271067313256, "DESIGN_REPAIR_MAX_SLEW_PCT": 22, "DESIGN_REPAIR_MAX_CAP_PCT": 27, "RC_MODEL": "stock"}
  setup: worst slack +8.261 ns at ss 100C 1.60V max-RC (reg-to-reg worst +11.446 ns; the worst path touches an input/output port); TNS 0.00 ns; 0 violating endpoints at the target
  hold: worst slack +0.113 ns at ff -40C 1.95V min-RC; 0 violations; 0 hold buffers inserted
  electrical: 101 slew/cap pins summed over corners (bar 953); worst corner max-slew 101, max-cap 0; fanout violations 5
  cells: 3509 std cells, 385 timing-repair buffers; std-cell area 26,906 um2; utilisation 47%
  routing: wirelength 88,775 um (pre-route estimate 80,553); detailed-route DRC by iteration [8, 7, 7, 0, 2, 2]..., final 0
  clock: skew 0.309 ns (setup) / -0.356 ns (hold); power 6.11 mW; flow runtime 5.5 min
- start aes_cipher [x6z-wbqspiflash-008] clock target 10.86 ns -> T_eff 10.743 ns, FEASIBLE
  setting {"period_frac": 0.5759360256713374, "FP_CORE_UTIL": 23, "density_delta": 7, "SYNTH_STRATEGY": "AREA 2", "SYNTH_ABC_BUFFERING": true, "SYNTH_SIZING": false, "PL_TIMING_DRIVEN": true, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": true, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.09845674949215728, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.3225578512156802, "DESIGN_REPAIR_MAX_SLEW_PCT": 38, "DESIGN_REPAIR_MAX_CAP_PCT": 26, "RC_MODEL": "stock"}
  setup: worst slack +0.117 ns at ss 100C 1.60V max-RC (reg-to-reg worst +0.117 ns); TNS 0.00 ns; 0 violating endpoints at the target
  hold: worst slack +0.105 ns at ff -40C 1.95V min-RC; 0 violations; 0 hold buffers inserted
  electrical: 0 slew/cap pins summed over corners (bar 953); worst corner max-slew 0, max-cap 0; fanout violations 1
  cells: 3179 std cells, 528 timing-repair buffers; std-cell area 23,665 um2; utilisation 30%
  routing: wirelength 77,318 um (pre-route estimate 69,036); detailed-route DRC by iteration [542, 178, 116, 14, 0], final 0
  clock: skew 0.293 ns (setup) / -0.349 ns (hold); power 2.54 mW; flow runtime 2.4 min
- round 1 [xah2-wbqspiflash-001] clock target 8.49 ns -> T_eff 8.034 ns, FEASIBLE
  pinned by the policy then: {"period_frac": 0.45, "RC_MODEL": "cap213", "RUN_POST_GRT_RESIZER_TIMING": true, "SYNTH_STRATEGY": "DELAY 4", "PL_ROUTABILITY_DRIVEN": false}
  setting {"period_frac": 0.45, "FP_CORE_UTIL": 25, "density_delta": 19, "SYNTH_STRATEGY": "DELAY 4", "SYNTH_ABC_BUFFERING": false, "SYNTH_SIZING": false, "PL_TIMING_DRIVEN": false, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": false, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.32631207981118027, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.3290938747721384, "DESIGN_REPAIR_MAX_SLEW_PCT": 35, "DESIGN_REPAIR_MAX_CAP_PCT": 31, "RC_MODEL": "cap213"}
  setup: worst slack +0.456 ns at ss 100C 1.60V max-RC (reg-to-reg worst +0.521 ns; the worst path touches an input/output port); TNS 0.00 ns; 0 violating endpoints at the target
  hold: worst slack +0.091 ns at ff -40C 1.95V min-RC; 0 violations; 0 hold buffers inserted
  electrical: 0 slew/cap pins summed over corners (bar 953); worst corner max-slew 0, max-cap 0; fanout violations 0
  cells: 3990 std cells, 435 timing-repair buffers; std-cell area 29,075 um2; utilisation 33%
  routing: wirelength 94,772 um (pre-route estimate 83,910); detailed-route DRC by iteration [39, 4, 7, 0, 0], final 0
  clock: skew 0.291 ns (setup) / -0.349 ns (hold); power 3.63 mW; flow runtime 5.9 min
- round 1 [xah2-wbqspiflash-002] clock target 8.49 ns -> T_eff 8.039 ns, FEASIBLE
  pinned by the policy then: {"period_frac": 0.45, "RC_MODEL": "cap213", "RUN_POST_GRT_RESIZER_TIMING": true, "SYNTH_STRATEGY": "DELAY 4", "PL_ROUTABILITY_DRIVEN": false}
  setting {"period_frac": 0.45, "FP_CORE_UTIL": 23, "density_delta": 22, "SYNTH_STRATEGY": "DELAY 4", "SYNTH_ABC_BUFFERING": false, "SYNTH_SIZING": false, "PL_TIMING_DRIVEN": false, "PL_ROUTABILITY_DRIVEN": false, "RUN_POST_GRT_RESIZER_TIMING": true, "RUN_POST_GRT_DESIGN_REPAIR": false, "PL_RESIZER_SETUP_SLACK_MARGIN": 0.12157915226384125, "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.3499842549643576, "DESIGN_REPAIR_MAX_SLEW_PCT": 34, "DESIGN_REPAIR_MAX_CAP_PCT": 40, "RC_MODEL": "cap213"}
  setup: worst slack +0.451 ns at ss 100C 1.60V max-RC (reg-to-reg worst +0.451 ns); TNS 0.00 ns; 0 violating endpoints at the target
  hold: worst slack +0.087 ns at ff -40C 1.95V min-RC; 0 violations; 0 hold buffers inserted
  electrical: 0 slew/cap pins summed over corners (bar 953); worst corner max-slew 0, max-cap 0; fanout violations 0
  cells: 4058 std cells, 446 timing-repair buffers; std-cell area 29,180 um2; utilisation 30%
  routing: wirelength 95,530 um (pre-route estimate 84,528); detailed-route DRC by iteration [15, 5, 5, 0, 11, 1]..., final 0
  clock: skew 0.297 ns (setup) / -0.352 ns (hold); power 3.55 mW; flow runtime 6.0 min

POLICIES SO FAR (yours, with your rationale then):
- round 1: pins {"period_frac": 0.45, "RC_MODEL": "cap213", "RUN_POST_GRT_RESIZER_TIMING": true, "SYNTH_STRATEGY": "DELAY 4", "PL_ROUTABILITY_DRIVEN": false}; rationale: Every tight-target run met timing with positive slack (T_eff = target minus 0.12-0.56 ns), so T_eff tracks the target; loose targets turn I/O-port-limited (T_eff 9.5-10.1). Push the target to the range floor (0.45 -> 8.49 ns, just under the best T_eff 8.57). The two best runs (des, md5) both used cap213 (largest signoff margin ~+0.55 ns, 0 hold buffers) and post-GRT timing repair; tight stock/orfs runs kept only +0.12-0.30 ns, two needing 82-242 hold buffers. Keep DELAY 4 (best run) for faster logic at the tighter target, and skip routability-driven spreading since congestion is low (DRC converges to 0). Hold, DRC and slew/cap (bar 953) are not binding; other knobs left to TPE.

TASK. Write the policy for round 2 of 4, using what the signoff summaries tell you (for example which
corner limits setup, whether the worst path touches a port, hold-buffer counts, slew/cap pins against the bar,
congestion, wire length against the pre-route estimate). Reply with JSON only, in this form:
{"rationale": "<at most 120 words: what the reports suggest and why these pins>",
 "pins": {"<knob>": <value>, ...}}
