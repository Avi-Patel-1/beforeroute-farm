# Workstream L — pre-registration: the finished loop, hands-off, on blocks the project never ran

Written 2026-11-10 (UTC) before any run of this workstream. Branch qa-l-loop; workflow .github/workflows/l_loop.yml;
driver farm/qa/L/loop.py; scorer farm/qa/L/score.py. Main and the README are not touched.

## What is being tested
Slide 6 of the submitted deck lists "the full loop, hands-off" as future work. This runs it. The loop is three moves,
each already measured separately:
1. **Push**: ask for the tightest clock in the space. Implemented as workstream C's four-line rule
   (farm/qa/C clib.script_pins): clock target at the floor (0.45 of the default period) plus the synthesis strategy, RC
   model and utilization of the best start run.
2. **Prove**: rebuild the winner at the clock it claims; nothing counts until a rebuild passes the nine-corner judge.
3. **Harvest**: keep rebuilding at each new claim while it passes (at most 4 rebuilds, one step back after a failed
   first rebuild; farm/qa/B blib.chain_next on the 0.05 ns grid, stock I/O budget).
No model is called anywhere in this workstream, and no person or model acts between the push that starts it and the
uploaded results.

## Blocks (none was ever run in this project)
| key | block | source | default clock |
|---|---|---|---|
| x | xtea_live | OpenLane designs/xtea (v0.21) with its one-line state-machine bug repaired (line 74: loop exit to s15, was s14). On Yosys-synthesized logic the shipped RTL never raises all_done on 500 of 500 vectors; the repaired RTL deciphers 500 of 500 against a reference XTEA | 26.03 ns |
| u | usb | OpenLane designs/usb (v0.21), unmodified | 12.55 ns |
| s | sha3 | OpenLane designs/sha3 (v0.21), unmodified | 12.71 ns |
Each was checked with Yosys before registration: no output bit is constant (xtea_live 192 flip-flops, usb 194,
sha3 2,577). Configs use the local template of designs/xtea with OpenLane's sky130_fd_sc_hd clock period.
Source hashes are in each designs/<block>/provenance.json.

## Protocol (per block)
- prep: the stock reference run at the default clock (its max-slew + max-cap pin count is the electrical bar, as
  Amendment 24.1), then Addendum 30's 8 start settings (farm/qa/L/blocks.json, in the recorded order), each at its own
  clock target.
- Two arms, two seeds each (seed35(block, 1) and seed35(block, 2)), both warm-started with the same 8 start runs:
  - **b, plain Bayesian search**: Addendum 35's arm b exactly (Optuna 5.0.0 TPE, multivariate, group, constant liar,
    8 start-up trials, constraints = route DRC, hold, slew/cap against the bar): 4 rounds of 2 runs = 8 search runs.
  - **L, the loop**: the same TPE with the four-line rule's four knobs pinned: ONE round of 2 runs (a quarter of the
    search budget). If no start run is feasible, the rule takes the lowest-claim start run.
- Winner per arm: the best feasible claim among that arm's own search runs (A35 arm_best). No feasible run = no winner
  = no kept clock.
- Both winners go through the same chain. Kept clock = the fastest clock at which a build passed the judge: setup and
  hold met at nine corners, router DRC 0, slew + cap pins no more than the bar.
- For arm L only, the kept build is rebuilt once more at the kept clock with Magic DRC, KLayout DRC, LVS and XOR
  switched on.
- A flow with no metrics is retried once with the same tag. A job lost to the runner is re-run once from the same
  commit. A race still missing at scoring counts as not matched.
- A smoke pass (tags starting with q: 2 start runs, 1 round, 1 rebuild, on usb) runs first in the same workflow to
  exercise the code; it is not scored and its runs are not used.

## Registered predictions
- **P1.** The loop matches or beats plain Bayesian search in at least 4 of the 6 races, with 2 search runs against 8.
  Match = the loop's kept clock is no more than 2% slower. Beat = more than 2% faster. Prediction: holds (4 to 6).
- **P2.** Every kept build of the loop is signoff-clean: it passes the judge again and has 0 Magic DRC, 0 KLayout DRC,
  0 LVS errors and 0 antenna violations. Prediction: holds.
Descriptive, no criterion: how many races the loop beats outright; flows and flow-hours per arm; per-block reading;
the repaired XTEA's rebuild chain next to slide 4's.

## What would count against the loop
A pushed run that misses timing makes a claim from the failing side; if its first rebuild and the one step back both
fail, the loop keeps no clock and loses that race. That is part of the test, not an exclusion.

## Known limits, stated before the runs
Three small blocks (two under 2,000 cells), one PDK and flow (sky130, LibreLane), two seeds. The baseline is plain
TPE at this project's budget (8 start + 8 search runs), not a long tuning campaign. The chain rule is workstream B's,
which differs slightly from Addendum 35's. The start settings are the eight borrowed winners every held-out design
started from.

## Amendment L.1 (2026-11-10 03:2x UTC, before any sha3 result exists)
In run 42742364760 the sha3 block's stock reference run stopped after 12 s: LibreLane's synthesis lint reported
"640 Yosys check errors" on the shipped RTL, so no layout and no metrics were produced and no start or search run of
sha3 was attempted. Fix: `"ERROR_ON_SYNTH_CHECKS": false` in designs/sha3/config_sky130.json, the same config fix
Amendment 30.1 applied to cic_decimator and usb_cdc_core. Nothing else changes. Block s is re-launched alone (batch
l1s) from this commit; blocks x and u continue in run 42742364760 untouched. The workflow gains a plan job so a batch
can name its blocks; the driver and scorer are unchanged. If sha3 still cannot be built, it is reported as not
buildable and its two races count as not matched.
