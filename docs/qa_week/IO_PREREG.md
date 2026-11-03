# IO1 — pre-registration: does Claude's I/O pin plan beat the tool's pins and a nearest-side rule?

Written 2026-11-03 (UTC) by the IO1 workstream of the TrueClock overnight push (Claude Opus 5.5, autonomous; Avi Patel
is asleep and has not seen this file), after the smoke runs below and **before any non-smoke run** (tags `io-cap-*`,
`io-<case>-<arm>`). Branch `qa-io-pins` of github.com/Avi-Patel-1/beforeroute-farm. Its SHA-256 is appended to
`farm/prereg_hashes.txt` in the same branch before the first capture is dispatched. Code frozen at the commit that adds
this file: `farm/qa/IO/{iolib.py, apply_pin_plan.py, plugin/librelane_plugin_iopins/__init__.py, io_run.py,
capture.py, capture_run.py, cases.py, cases.json, packet.py, phase2.py, score.py}` and `.github/workflows/farm.yml`
(the IO1 branch of its "Run job" step). Result (later): `docs/qa_week/IO_RESULT.md`.

## Question
Addendum 39 (E2) found that 17 of the 50 rebuilt winners behind slide 5 were limited by a port path at their first
passing rebuild. For such a block the I/O pin positions set how much wire lies between the pins and the logic. Can a
fresh, blind Claude that reads the routed record of one run choose pin positions that **verify** a faster clock than
(a) the tool's own pin placement and (b) a simple nearest-side rule, when all three are judged by the same rebuild
chain at the winner's settings?

## Registered prediction (from the task, verbatim)
> Claude's pins beat stock on at least 6 of 10 designs with a median kept-clock gain of at least 3%, and beat the script
> on at least 5 of 10.

"Designs" here are the 10 cases below (10 winners on 4 designs). Noise threshold: E4's measured chaos floor, **2.3%**
(claims moved at most 2.3% under 1–40 ps target nudges, docs/qa_week/E4_RESULT.md), kept because the smoke's no-op
replay through the pin machinery was bit-identical to the record (below).

## Toolchain (frozen, as the record)
- LibreLane 3.0.16 image `ghcr.io/librelane/librelane@sha256:4bc9042b…5051`, sky130A PDK 8afc8346, sky130_fd_sc_hd;
  GitHub Actions ubuntu-latest, 4 vCPU, `-j 4`; every run goes through `br/run_job.py` exactly as the record's jobs.
- Corners, SDC, judge: LibreLane's base.sdc (input and output delay 20% of the clock period on every port except the
  clock, inputs driven by sky130_fd_sc_hd__inv_2/Y, outputs loaded with 33.442 fF, clock uncertainty 0.25 ns), nine
  STA corners (min/nom/max RC × tt/ss/ff), OpenRCX parasitics.

## Cases (10; `farm/qa/IO/cases.py` → `cases.json`)
Population: the 17 E2 winners whose first passing rebuild was port-limited (worst setup slack below the
register-to-register worst slack), recomputed with docs/qa_week/E2_analysis.py. Winners with identical settings count
once (xah2-/xag2-usb_cdc_core-002 are one setting; neither was chosen). Per design, sort by SHA-256 of the winner's
search-run tag and keep the first three; case ids follow the same order across designs. Avi did not see this choice.

| case | design | winner (search run) | from | T0 (ns) | claim C0 in the record (ns) | record's kept clock (ns, reference only) | slew+cap bar |
|---|---|---|---|---|---|---|---|
| c01 | cic_decimator | xag2-cic_decimator-004 | A35 g2 | 4.6 | 4.0952 | 4.1 | 89 |
| c02 | xtea | xaf1-xtea-004 | A35 f1 | 11.71 | 6.2128 | 4.6 | 0 |
| c03 | usb_cdc_core | xah1-usb_cdc_core-008 | A35 h1 | 7.02 | 6.1867 | 5.9 | 309 |
| c04 | usb_cdc_core | xaf1-usb_cdc_core-001 | A35 f1 | 7.02 | 6.3407 | 5.7 | 309 |
| c05 | usb_cdc_core | x8a-usb_cdc_core-002 | A32 agent | 7.02 | 6.3020 | 5.85 | 309 |
| c06 | xtea | xag2-xtea-004 | A35 g2 | 11.71 | 5.9272 | 4.25 | 0 |
| c07 | xtea | xah1-xtea-007 | A35 h1 | 11.71 | 6.0076 | 4.2 | 0 |
| c08 | wbqspiflash | x8b-wbqspiflash-006 | A32 tpe | 8.52 | 8.0376 | 7.65 | 953 |
| c09 | wbqspiflash | xag2-wbqspiflash-008 | A35 g2 | 8.49 | 7.9797 | 7.7 | 953 |
| c10 | wbqspiflash | xah1-wbqspiflash-003 | A35 h1 | 8.49 | 7.9572 | 7.6 | 953 |

T0 = the winner's search target; settings = the winner's job spec (`farm/jobs/<winner>.json`), unchanged.

## Runs
1. **Captures (now):** one stock run per case at the winner's settings and T0 (`io-cap-<case>`, mode single, no pin
   plan), with the per-net dump (post-global-route and signoff views, as every record run), the final DEF, and
   `capture.py`'s port table and OpenSTA JSON path reports. 10 runs, one workflow run, `max_parallel` 3.
2. **Script arm (now, deterministic):** `packet.py script` on each case's packet.
3. **Claude arm (coordinator, later):** one fresh Claude instance per case reads only its packet and writes `pins.txt`.
4. **Phase 2 (after Claude's 10 files are hashed and committed):** 30 jobs `io-<case>-<arm>`, arm ∈ {stock, script,
   claude}: each runs its source run at T0 and its rebuild chain on the runner (`io_run.py`, mode chain). One workflow
   run, `max_parallel` 3. No other runs. Budget: ≤ 10 + 150 runs (measured smoke: XTEA ≈ 1 min of flow per run).

## The three arms
- **stock**: the record's job, unchanged: OpenROAD `place_pins` in matching mode after a preliminary placement
  (LibreLane's default). The smoke showed this reproduces the record bit for bit.
- **script** (Avi's hand baseline, written by Claude tonight because Avi is asleep; `packet.py nearest_side_plan`):
  critical groups = movable port groups whose worst setup slack at T0 is within 10% of T0 of the worst group's, at
  most the 4 most critical; each goes to the die edge nearest the centroid of the logic it connects to (cells on its
  port nets, looked through up to 8 buffers, from the stock run's per-net dump, signoff view, and the DEF's cell
  positions), in the third of that edge containing the centroid's projection; if it does not fit there, the next
  nearest edge; if none, it stays. It reads the same pseudonymous packet the Claude reader gets.
- **claude**: a fresh Claude (Opus 5.5) per case, given only its packet (README, contract, menu, floor, validator, the
  run's metrics, port table, path reports, both per-net dumps, the DEF), no network, no other files. One selection; no
  rescue after any outcome (it sees none). If its file fails `validate_pins.py`, the coordinator shows it the
  validator's message once (format only); a file still invalid then counts as ABSTAIN. ABSTAIN is allowed.

## What is fixed in every arm (the legal menu)
- Mechanism: a LibreLane plugin step `IOPins.ApplyPinPlan`, inserted right after `OpenROAD.IOPlacement` through the
  run config's `meta.substituting_steps` (plugin on PYTHONPATH, plan in `IOPINS_PLAN`). It moves only the listed
  groups; every other pin keeps the position the tool's placer gave it. Stock runs do not load the plugin.
- Groups: all bits of a bus (same base name) or one scalar port. The clock port and reset ports are fixed. Logical
  pin assignment is fixed; bus order is fixed (a moved group is one run of pins in ascending bit order along the
  edge, low to high coordinate).
- Options per movable group: KEEP, or one of 12 segments (edge N/E/S/W × third 1/2/3). Pins go on the edge's own
  layer (met2 on N/S, met3 on E/W, LibreLane's sky130 layers), with the stock pin shape, on even-numbered routing
  tracks (2-track pitch, as the stock placer), at least 1.5 µm from a corner and 2 tracks from any other pin.
- Placement rule (`iolib.place_groups`): the stock positions of every moved pin are freed first; groups are placed in
  file order, each at the window of consecutive free slots whose mean is nearest its segment's centre. A pin file must
  fit as a whole on the T0 floorplan (`validate_pins.py`, strict). Inside each build the positions are recomputed on
  that build's floorplan; a group that does not fit there keeps the tool's pins in that build (recorded).
- I/O delays stay 20% of the clock on every port in every arm, so **only the wire and cells inside the block are at
  stake**; the top-level wire a real pin plan also changes is not modeled. This is the honest limit of the test.

## Judge, chain and metric (`iolib.judge`, `iolib.chain_next`, `iolib.kept_clock`)
- **Pass:** flow completed; worst setup slack ≥ 0 and worst hold slack ≥ 0 over the nine corners; router DRC 0;
  max-slew + max-cap violation pins ≤ the design's stock bar (table). As the record (farm/tune.py, tune_a32.passed).
- **Chain:** source run at T0 (claim C0 = T0 − worst setup slack); first rebuild at ceil05(C0); after a passing
  rebuild with claim C, rebuild at ceil05(C) while that is below the chain's smallest passing clock and above every
  failed clock below it; if the first rebuild fails, step back once to max(ceil05(C1), R1 + 0.05 ns) unless that is
  not below the smallest passing clock; a failure after that ends the chain; at most 4 rebuilds; a clock already built
  is not rebuilt. The pin plan applies at every build.
- **Kept clock** K(case, arm) = the smallest passing clock of the chain (source included); none if nothing passed.

## Registered tests (`farm/qa/IO/score.py`)
Gain of arm a over arm b: g = K_b / K_a − 1 (positive = a verified a faster clock; both none → 0; a none → −1;
b none → +∞). A **beat** is g > θ = 0.023.
- **P1:** Claude beats stock on ≥ 6 of the 10 cases.
- **P2:** median over the 10 cases of g(claude over stock) ≥ 0.03.
- **P3:** Claude beats the script on ≥ 5 of the 10 cases.
- **The prediction holds iff P1, P2 and P3 all hold.** A case whose chain did not land for an arm (after the one
  infrastructure retry) counts as no beat in the tests that need that arm and is left out of the median; the result
  says so. An abstaining arm is run anyway (its no-op plan is bit-identical to stock, so g = 0).
Reported beside, with no criterion: script vs stock (beats, median gain); the stock arm's kept clock against the
record's (the record's E2 chains allowed up to two step-backs); first-rebuild pass/fail per arm; claims at T0; which
groups moved and where; Claude's own stated expectations (rationale.md) against the outcome.

## What each outcome means
- **Holds:** on these 10 winners a blind Claude reading one routed record chose pin plans that verified faster clocks
  than the tool's pins and a simple rule. Scope: 4 small sky130 designs, I/O-internal wire only.
- **P1 and P2 hold, P3 fails:** Claude's pins beat the tool's, but a one-line rule does about as well; the product
  should ship the rule, and the AI contribution is not shown.
- **P1 or P2 fails:** no evidence that Claude's pins beat the tool's at this budget; reported as such. If the script
  beats stock instead, pin placement matters and a rule captures it.
- **Nothing moves the kept clock beyond 2.3%:** pin positions inside these blocks are not where the port-limited speed
  is; E2's "port-limited" winners are limited by the I/O budget arithmetic, not by pin wire.

## Smoke (tags `smoke-io-*`, excluded from every analysis; subject xah2-xtea-001, an XTEA winner not chosen above)
- Run 41566584515: `smoke-io-stock` (stock replay + capture) and `smoke-io-noop` (plugin loaded, plan with no move)
  both reproduced the record's metrics.json for xah2-xtea-001 **bit for bit (280 of 280 keys)**. The first
  `smoke-io-move` plan (data_out1 → N2) failed: edge N had 18 free slots for 32 pins. This forced two changes before
  this registration: the slot lattice now uses even-numbered tracks counted from the track-grid origin (where the stock
  placer puts pins; the first version started at the first track past the corner margin, so each kept pin blocked two
  slots), the corner margin is 1.5 µm (the stock placer came to 1.7 µm), and a group that no longer fits inside a
  later build keeps its stock pins there instead of failing the build.
- Run 41567116620: `smoke-io-move` as a chain (data_out1 → W2, mode → W1, all_done → N1): the plan was applied at all
  5 builds; all 34 moved pins sit exactly at their planned coordinates in the final DEF; the chain ran source + 4
  rebuilds as the rule says; every build passed with DRC 0.
- Run 41567854743: `smoke-io-stock` again after the capture fix (OpenSTA here rejects the `nets` field of
  `report_checks -fields`, and printed a warning before the JSON): bit-identical to the record again (280 of 280 keys); all 261 path reports (76 worst paths, 195 from-input, 65
  to-output) parse as JSON; 68 of 260 ports are connected; ports without a timing path carry no slack.
- Facts seen in the smoke that bear on the cases: XTEA's die (95 × 106 µm) holds 260 pins in about 352 legal slots;
  the stock placer filled edges N, E and S and left W nearly empty, so few XTEA moves fit unless groups trade places.
  In the record's XTEA netlist 192 of the 260 inputs are unconnected after synthesis, and all 64 data outputs are
  driven by one flip-flop through a buffer tree up to 6 deep (all_done is a tie cell); XTEA's port paths are that tree.

## Decision times and handling
- Phase 2 is dispatched only after Claude's 10 pin files and the script's 10 are hashed into this branch. The verdict
  is computed when all 30 chains have landed, and in any case on Thu Nov 5 23:00 UTC on what has landed then.
- Infrastructure failures: a run without job.json is repeated once inside its job; a job lost by GitHub is
  re-dispatched once with the same spec. A flow error that repeats is a failed build.
- Nothing in the cases, arms, menu, chain, judge, threshold or tests changes after this file is hashed. Deviations go
  into IO_RESULT.md with their reason.
- At most 3 of these Actions jobs run at a time (shared farm).

## Caveats known in advance
1. Only wire inside the block is at stake (fixed 20% I/O delays both sides); pin plans that help the block can hurt
   the parent, and this test cannot see that.
2. 10 cases on 4 designs (3 usb_cdc_core, 3 XTEA, 3 wbqspiflash, 1 cic_decimator); cases of one design share RTL.
3. The stock pins are a tool default that often scatters a bus over several edges, not a designer's pin plan.
4. The script baseline was written by Claude tonight, not by Avi; Avi saw none of this before launch.
5. Crowded perimeters (XTEA) leave few legal moves; the menu shows them.
6. A pin move changes the whole downstream placement, so part of any difference is the flow's response to a new
   starting point; θ = 2.3% was measured only for 1–40 ps target nudges (E4).
7. The chain's 4-rebuild cap truncates chains that are still improving.
8. Pseudonyms remove names and tags, but a reader could still recognise a structure (e.g. a 128-bit bus); the packets
   carry no later result.
