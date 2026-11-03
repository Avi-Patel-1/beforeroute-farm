# IO — result: does a blind Claude's I/O pin plan verify a faster clock than the tool's pins or a nearest-side rule?

**Final.** Scored 2026-11-03 06:59:56Z (`date -u`) with the registered `farm/qa/IO/score.py`, once all 30 registered
chains had landed (workflow run 41574123655 completed 06:59:26Z, 30 of 30 jobs successful). Nothing is still running.
Written by the IO2 workstream of the TrueClock overnight push (Claude Opus 5.5, autonomous); Avi Patel was asleep and
saw none of this before launch.
- Pre-registration: docs/qa_week/IO_PREREG.md, commit c8e81f2, SHA-256
  `5977e649f0a02753bab708c54b5bf2f5d03690f18ffdb703790e31db94f9bca4`, appended to farm/prereg_hashes.txt in 0e7c368
  at 02:46:21Z, before the first non-smoke run (captures, run 41568169751, created 02:46:31Z).
- Script arm locked before any arm chain: 10 pin files in c36f9c3, SHA-256 of their SHA256SUMS
  (`cfcd7033…b153`) in farm/prereg_hashes.txt at 03:14:55Z (4bfa383).
- Claude arm locked before any arm chain: the 10 readers' files, validated and translated, in **2564c73**; SHA-256 of
  farm/qa/IO/arms/claude/SHA256SUMS `06c730aaa189afb1a335bb17369c99c245f99d128028775497dc4ff0f8fcd16c` appended at
  03:45:27Z (9ec1531) and pushed; pseudonym maps 9b10673; job specs 4eb0eec. Run 41574123655 was created at 03:45:52Z
  and ran at 4eb0eec.
- Verdict: `score.py` → farm/qa/IO/io_result.json. Reported-beside tables: `describe.py` (written after the files were
  locked; not registered) → farm/qa/IO/io_describe.json.

## Bottom line
- **Registered prediction: does not hold. P1, P2 and P3 all fail.** Claude's pins beat the tool's on **1 of 10** cases
  (needed 6), the median gain over the tool's pins was **+0.0%** (needed ≥ 3%), and Claude beat the nearest-side
  script on **2 of 10** (needed 5).
- **P1 could not pass once the pin files were locked.** Five of the ten readers abstained (kept the tool's pins). An
  abstaining arm runs a no-op plan that is identical to stock by construction: all 23 no-op builds here matched the
  stock arm's build at the same clock on every metrics.json key. So g = 0 on those five cases, at most 5 of 10 beats
  were possible, and P1 needs 6. The prediction (P1 and P2 and P3) was therefore decided by the readers' choices
  before any chain ran.
- **The five cases where Claude moved pins (descriptive, not registered):** it beat the tool's pins once (c09,
  wbqspiflash: 7.5 vs 7.7 ns, +2.7%, 0.4 points above the 2.3% noise threshold) and stayed within ±2.3% on the
  other four (+1.7%, 0.0%, −0.6%, −1.3%), median 0.0%. Against the script on the same five: 1 beat (c09),
  no loss beyond 2.3%, median +0.9%.
- **The nearest-side rule did no better** (reported beside, no criterion): 1 win (c01, +2.5%) and 1 loss (c02, XTEA,
  −4.2%) against the tool's pins, median −0.3% over the 10 cases.
- **What it means (as registered):** no evidence that a blind Claude's pin plans beat the tool's at this budget, and
  no evidence that a simple rule does either. Across all 15 moved plans (Claude's 5, the script's 10) the kept clock
  moved between −4.2% and +2.7% against the tool's pins: twice above +2.3%, once below −2.3%, median 0.0%. With the
  I/O delays fixed at 20% of the clock, pin positions inside these four small blocks are not where their port-limited
  speed is.
- **XTEA:** all three XTEA readers found, blind, that the 64 data outputs are buffered copies of one flip-flop
  (separately confirmed by the RTL audit: synthesis removed XTEA's datapath) and kept the tool's pins. The rule's
  XTEA moves lost 4.2% on c02 and tied on c06 and c07.
- **Determinism, again:** the stock arm reproduced the record's claim at T0 (to 4 decimals) and its kept clock on all
  10 winners.

## Q&A line (if asked "can Claude do placement-level work, like pin planning?")
> "I tested it on I/O pins. For ten port-limited winners, a fresh Claude that saw only the routed record, with every
> name hidden, chose where the block's pins go; OpenROAD's own pins and a nearest-edge rule were the baselines, and
> all three were judged by the same rebuild chain. It failed its pre-registered test. Claude kept the tool's pins on
> five of the ten, three of them XTEA blocks where it worked out that all 64 outputs come from one flip-flop, and on
> the other five it beat the tool once, by 2.7 percent. Moving pins inside these blocks shifted the verified clock by
> a few percent either way, for the simple rule as much as for Claude."

Do not say:
- "Claude places pins better than the tool", or any gain as a headline: 1 of 10, by 0.4 points over the noise floor;
- "a pin rule helps": 1 win, 1 loss, median −0.3%;
- "pin placement doesn't matter": only the wire inside the block was at stake (I/O delays fixed at 20% of the clock);
  the top-level wire a real pin plan changes was not modeled; 4 small sky130 designs;
- "Claude was right to abstain" as a measured result: no alternative move was tested on those cases except the
  script's;
- anything about significance: 10 cases on 4 designs.

## What ran
- Workflow run **41574123655** (farm.yml, branch qa-io-pins, commit 4eb0eec), 30 jobs `io-<case>-<arm>`, max_parallel 3,
  03:45:52Z → 06:59:26Z (3 h 14 min wall). Each job ran its source run at T0 and its rebuild chain on the runner
  (`io_run.py`, mode chain). 30 of 30 jobs successful; no infrastructure retry, no re-dispatch.
- **137 builds** (stock 43, script 47, claude 47); all completed the flow. Flow time (sum of build wall times)
  **8.19 h** (stock 2.41, script 2.78, claude 3.00); runner time 8.94 job-hours; longest job 38 min. Phase 1 (IO1:
  smoke + captures) used about 0.6 h more.
- Pins: every plan was applied at every build; no group was dropped in any build for not fitting. Moved pins sit off
  their stock slots in every build except where a plan put a pin on its stock slot (c03 Claude: 1 of 10, deliberately;
  c04 script: 1 of 11; c06 script: 1 of 64).
- 7 of 137 builds failed, all on setup (worst setup slack −0.02 to −0.10 ns); worst hold slack ≥ +0.041 ns and router
  DRC 0 in every build; slew+cap pins within the bar in every build; all 30 source runs passed at T0.
- Local records: /home/claude/qa/io-results (20 MB: chain.json and per-build metrics/job/pins_applied/resolved).
  Each job's artifact (result-io-<case>-<arm>, about 2 MB, with every build's final DEF) stays on the run.

## Registered verdict (`score.py` output; units added to the header)
| case | design | T0 (ns) | K stock (ns) | K script | K claude | g claude/stock | g claude/script | g script/stock |
|---|---|---|---|---|---|---|---|---|
| c01 | cic_decimator | 4.6 | 4.1 | 4.0 | 4.1 | +0.0% | -2.4% | +2.5% |
| c02 | xtea | 11.71 | 4.6 | 4.8 | 4.6 | +0.0% | +4.3% | -4.2% |
| c03 | usb_cdc_core | 7.02 | 5.9 | 5.85 | 5.8 | +1.7% | +0.9% | +0.9% |
| c04 | usb_cdc_core | 7.02 | 5.7 | 5.75 | 5.7 | +0.0% | +0.9% | -0.9% |
| c05 | usb_cdc_core | 7.02 | 5.85 | 5.8 | 5.85 | +0.0% | -0.9% | +0.9% |
| c06 | xtea | 11.71 | 4.25 | 4.25 | 4.25 | +0.0% | +0.0% | +0.0% |
| c07 | xtea | 11.71 | 4.2 | 4.2 | 4.2 | +0.0% | +0.0% | +0.0% |
| c08 | wbqspiflash | 8.52 | 7.65 | 7.7 | 7.7 | -0.6% | +0.0% | -0.6% |
| c09 | wbqspiflash | 8.49 | 7.7 | 7.75 | 7.5 | +2.7% | +3.3% | -0.6% |
| c10 | wbqspiflash | 8.49 | 7.6 | 7.7 | 7.7 | -1.3% | +0.0% | -1.3% |

K = kept clock (smallest passing clock of the chain); g(a over b) = K_b / K_a − 1; a beat is g > 2.3%.
- **P1** Claude beats stock on **1** of 10 (c09); needed 6. **Fail.** Could not pass after the files were locked (above).
- **P2** median g(Claude over stock) = **+0.0%**; needed ≥ +3.0%. **Fail.** (With five exact zeros, P2 needed every
  one of the five moved cases to gain ≥ 6%.)
- **P3** Claude beats the script on **2** of 10 (c02: Claude kept the tool's pins and the script's XTEA move lost
  4.3%; c09: +3.3%); needed 5. **Fail.**
- **Prediction holds: no.** No chain missing; every chain's plan hash matches its committed plan.
- Predicted (task, verbatim): "Claude's pins beat stock on at least 6 of 10 designs with a median kept-clock gain of
  at least 3%, and beat the script on at least 5 of 10." Outcome: 1 of 10, +0.0%, 2 of 10.

## Secondary view, NOT registered: the five cases where Claude moved pins
Asked for by the coordinator after the pin files were locked, when it was known that five readers had abstained.
Same kept clocks and gains as above, restricted to c03, c04, c08, c09, c10.

| case | Claude's moves (real names; edge third) | script's moves | K stock | K claude | g claude/stock | K script | g claude/script |
|---|---|---|---|---|---|---|---|
| c03 usb_cdc_core | inport_accept_o, utmi_txvalid_o, utmi_data_out_o[7:0] → E2 | utmi_data_out_o, utmi_txvalid_o, inport_accept_o → E2; outport_valid_o → N2 | 5.9 | 5.8 | +1.7% | 5.85 | +0.9% |
| c04 usb_cdc_core | utmi_txvalid_o → E2 | utmi_data_out_o → E3; utmi_txvalid_o, inport_accept_o → E2; outport_valid_o → W2 | 5.7 | 5.7 | 0.0% | 5.75 | +0.9% |
| c08 wbqspiflash | i_wb_data[31:0] → S1 | i_wb_we, i_wb_data_stb → N2; i_wb_addr → W2; i_wb_cyc → S2 | 7.65 | 7.7 | −0.6% | 7.7 | 0.0% |
| c09 wbqspiflash | i_wb_addr[19:0] → W2; i_wb_data[31:0] → S1 | i_wb_we, i_wb_data_stb → N2; i_wb_addr → W2 | 7.7 | 7.5 | **+2.7%** | 7.75 | **+3.3%** |
| c10 wbqspiflash | i_wb_addr[19:0], i_wb_we, i_wb_data_stb → W2 | i_wb_addr → W2; i_wb_we, i_wb_data_stb → N2 | 7.6 | 7.7 | −1.3% | 7.7 | 0.0% |

- Claude vs stock: 1 beat, 0 losses beyond 2.3%, median 0.0%. Claude vs script: 1 beat, 0 losses, median +0.9%.
  Script vs stock on the same five: no beat either way, median −0.6%.
- Even restricted to its own moves, Claude's median gain over the tool's pins (0.0%) is below the registered 3% bar.
- Edge thirds: N/E/S/W edge, third 1/2/3 of its length (2 = middle). Groups move as one run of pins in bit order.

## Reported beside (registered, no criterion)
- **Script vs stock (all 10):** 1 beat (c01, +2.5%), 1 loss (c02, −4.2%), median −0.3%.
- **Stock arm vs the record:** kept clock equal to the record's on 10 of 10 (4.1, 4.6, 5.9, 5.7, 5.85, 4.25, 4.2, 7.65,
  7.7, 7.6 ns); claim at T0 equal to the record's to 4 decimals on 10 of 10. The record's E2 chains allowed two
  step-backs; none was needed here.
- **First rebuild:** passed in 30 of 30 chains (every source run had positive slack at T0, as the law expects).
- **4-rebuild cap:** chains still passing and still improving when the cap stopped them: stock 2 (c02, c06), script 4
  (c02, c04, c06, c07), Claude 3 (c02, c06, c08; c02 and c06 are no-op chains identical to stock).
- **Claims at T0 (source run, ns; + = slower than stock):**

| case | record | stock | script | Claude |
|---|---|---|---|---|
| c01 | 4.0952 | 4.0952 | 4.0982 (+0.1%) | = stock |
| c02 | 6.2128 | 6.2128 | 6.5185 (+4.9%) | = stock |
| c03 | 6.1867 | 6.1867 | 6.3143 (+2.1%) | 6.3040 (+1.9%) |
| c04 | 6.3407 | 6.3407 | 6.4025 (+1.0%) | 6.3581 (+0.3%) |
| c05 | 6.3020 | 6.3020 | 6.3414 (+0.6%) | = stock |
| c06 | 5.9272 | 5.9272 | 6.0038 (+1.3%) | = stock |
| c07 | 6.0076 | 6.0076 | 5.9973 (−0.2%) | = stock |
| c08 | 8.0376 | 8.0376 | 8.2058 (+2.1%) | 8.2040 (+2.1%) |
| c09 | 7.9797 | 7.9797 | 8.0413 (+0.8%) | 8.1115 (+1.7%) |
| c10 | 7.9572 | 7.9572 | 8.1187 (+2.0%) | 7.8970 (−0.8%) |

  Moving pins made the claim at T0 slower in 13 of the 15 moved plans. The claim at T0 ordered a moved plan against
  stock the opposite way from the kept clock in 6 of the 12 comparisons where both differ (Claude 3 of 4: c03, c09,
  c10; script 3 of 8: c01, c03, c05). c09, Claude's one beat, started from a claim 1.7% slower than stock's.
- **Claude's stated expectations (rationale.md) against the outcome:**

| case (packet) | reader expected | T0 claim vs stock | kept vs stock |
|---|---|---|---|
| c03 (p114b56) | G18 and four G10 bits 0.03–0.08 ns earlier; "T0 WNS may not move"; confidence 0.55–0.6 | +0.117 ns slower | +1.7% (within θ) |
| c04 (p6dbefa) | G15 slack +0.03–0.06 ns; "confidence the final score improves: 0.35" | +0.017 ns slower | 0.0% |
| c08 (pbae019) | 0.1–0.25 ns off the enable tail; "better final clock 0.55" | +0.166 ns slower | −0.6% |
| c09 (p0ba4e7) | +0.008 to +0.034 ns of worst slack, "below the flow's noise"; confidence 0.55 per move | +0.132 ns slower | **+2.7% (beat)** |
| c10 (p10bfb9) | input cone 0.05–0.3 ns faster; confidence 0.5–0.65 | −0.060 ns faster | −1.3% |
| 5 ABSTAIN | "the same result as the tool's pins"; three state 0.6–0.65 confidence that no move beats stock | = stock | = stock (by construction) |

  The one plan whose T0 claim improved (c10) ended slower; the one plan that won (c09) was the one whose reader
  expected an effect below the noise.

## Per-build chains (`describe.py`; clock ns, P = pass / F = fail, claim ns in brackets)
| case | arm | builds | K (ns) | pins off stock slot / placed, per build |
|---|---|---|---|---|
| c01 | stock | 4.6 P (4.095); 4.1 P (3.930); 3.95 F (3.978) | 4.1 | – |
| c01 | script | 4.6 P (4.098); 4.1 P (4.031); 4.05 P (3.975); 4.0 P (3.894); 3.9 F (3.999) | 4.0 | 4/4 ×5 |
| c01 | claude | as stock (no-op, identical) | 4.1 | 0/0 |
| c02 | stock | 11.71 P (6.213); 6.25 P (5.121); 5.15 P (4.851); 4.9 P (4.586); 4.6 P (4.293) | 4.6 | – |
| c02 | script | 11.71 P (6.519); 6.55 P (5.487); 5.5 P (5.009); 5.05 P (4.758); 4.8 P (4.513) | 4.8 | 64/64 ×5 |
| c02 | claude | as stock (no-op, identical) | 4.6 | 0/0 |
| c03 | stock | 7.02 P (6.187); 6.2 P (5.879); 5.9 P (5.868) | 5.9 | – |
| c03 | script | 7.02 P (6.314); 6.35 P (5.968); 6.0 P (5.808); 5.85 P (5.827) | 5.85 | 11/11 ×4 |
| c03 | claude | 7.02 P (6.304); 6.35 P (6.051); 6.1 P (5.879); 5.9 P (5.785); 5.8 P (5.773) | 5.8 | 9/10 ×5 |
| c04 | stock | 7.02 P (6.341); 6.35 P (6.026); 6.05 P (5.882); 5.9 P (5.659); 5.7 P (5.656) | 5.7 | – |
| c04 | script | 7.02 P (6.403); 6.45 P (6.152); 6.2 P (5.971); 6.0 P (5.749); 5.75 P (5.655) | 5.75 | 10/11 ×5 |
| c04 | claude | 7.02 P (6.358); 6.4 P (6.093); 6.1 P (5.833); 5.85 P (5.651); 5.7 P (5.695) | 5.7 | 1/1 ×5 |
| c05 | stock | 7.02 P (6.302); 6.35 P (5.885); 5.9 P (5.813); 5.85 P (5.778); 5.8 F (5.841) | 5.85 | – |
| c05 | script | 7.02 P (6.341); 6.35 P (5.924); 5.95 P (5.774); 5.8 P (5.733); 5.75 F (5.785) | 5.8 | 11/11 ×5 |
| c05 | claude | as stock (no-op, identical) | 5.85 | 0/0 |
| c06 | stock | 11.71 P (5.927); 5.95 P (4.775); 4.8 P (4.457); 4.5 P (4.215); 4.25 P (4.069) | 4.25 | – |
| c06 | script | 11.71 P (6.004); 6.05 P (4.872); 4.9 P (4.503); 4.55 P (4.245); 4.25 P (4.039) | 4.25 | 63/64 ×5 |
| c06 | claude | as stock (no-op, identical) | 4.25 | 0/0 |
| c07 | stock | 11.71 P (6.008); 6.05 P (4.877); 4.9 P (4.540); 4.55 P (4.161); 4.2 P (4.152) | 4.2 | – |
| c07 | script | 11.71 P (5.997); 6.0 P (4.855); 4.9 P (4.504); 4.55 P (4.155); 4.2 P (4.029) | 4.2 | 64/64 ×5 |
| c07 | claude | as stock (no-op, identical) | 4.2 | 0/0 |
| c08 | stock | 8.52 P (8.038); 8.05 P (7.681); 7.7 P (7.617); 7.65 P (7.648) | 7.65 | – |
| c08 | script | 8.52 P (8.206); 8.25 P (7.975); 8.0 P (7.767); 7.8 P (7.697); 7.7 P (7.657) | 7.7 | 23/23 ×5 |
| c08 | claude | 8.52 P (8.204); 8.25 P (7.852); 7.9 P (7.800); 7.8 P (7.666); 7.7 P (7.602) | 7.7 | 32/32 ×5 |
| c09 | stock | 8.49 P (7.980); 8.0 P (7.845); 7.85 P (7.690); 7.7 P (7.668) | 7.7 | – |
| c09 | script | 8.49 P (8.041); 8.05 P (7.745); 7.75 P (7.742) | 7.75 | 22/22 ×3 |
| c09 | claude | 8.49 P (8.111); 8.15 P (7.776); 7.8 P (7.515); 7.55 P (7.500); 7.5 P (7.489) | 7.5 | 52/52 ×5 |
| c10 | stock | 8.49 P (7.957); 8.0 P (7.607); 7.65 P (7.589); 7.6 P (7.558) | 7.6 | – |
| c10 | script | 8.49 P (8.119); 8.15 P (7.886); 7.9 P (7.654); 7.7 P (7.599); 7.6 F (7.622) | 7.7 | 22/22 ×5 |
| c10 | claude | 8.49 P (7.897); 7.9 P (7.722); 7.75 P (7.689); 7.7 P (7.658) | 7.7 | 22/22 ×4 |

A chain ends when ceil05 of the last claim is a clock already built (e.g. c03 stock: claim 5.868 → 5.9), after a
failed rebuild that is not the first, or at 4 rebuilds.

## Blindness and integrity of the Claude arm (for the record; not a registered test)
- **Readers.** 10 fresh Claude Opus 5.5 instances, one per packet, each given IO1's prompt verbatim
  (farm/qa/IO/READER_PROMPT.md) and only its packet folder. All 10 files pass their packet's validator (the
  coordinator's run and IO2's re-run). Transcripts: 25–53 tool calls each, all on claude-opus-5-5.
- **Transcript audit** (coordinator's audit_reader.py, re-run by IO2): no reader named any path outside its packet,
  its output folder and the session scratchpad. None of the four designs' names (cic_decimator, xtea, usb_cdc_core,
  wbqspiflash) appears anywhere in any tool output a reader saw (farm/qa/IO/reader_scratch.py, substring scan).
- **Shared scratchpad (deviation from the intended isolation).** The readers ran as sub-agents of one session and
  shared its scratchpad folder, which also holds older files of other sessions. Several readers wrote helper files
  under the same names (`work/`, `graph.py`, `paths.py`, `work/tree.py`, `work/parse_def.py`, `work/graph.py`), so
  one reader's parsed file could replace another's; several readers reported this, and all said they redid the
  work in a private sub-folder. One reader (p114b56, c03) once loaded another packet's parsed file by accident; the
  command failed and its output was not used (coordinator's audit). Three readers (p00d863, p0ba4e7, p3d0074)
  listed the scratchpad root; that listing showed one file name containing another study's design name (md5), and
  no name of the four designs in this test. Every scratchpad path any reader named (73) is a helper file or folder
  with a generic name (graph.py, def.pkl, work/tree.py, a private sub-folder…); none is named after a design or study.
- **Integrity check** (farm/qa/IO/integrity_check.py → integrity_check.json; run and committed in fab915c while the
  chains ran, before any moved plan's chain had landed). For every packet, every pseudonymous name its rationale.md
  and pin-file comments cite exists in its own packet: **115 of 115** (67 in the 5 moved packets, 48 in the 5
  abstaining ones). Every specific claim the rationales make about those names (cell type, position, connectivity,
  path role, slack; 36 claims hand-coded from the text) holds in the reader's own packet: **36 of 36** (24 in the
  moved packets). As a control each claim was also evaluated in the other nine packets: no specific claim holds in
  any other packet. Two generic ones also match elsewhere: a worst slack of 0.51 ns (also in p00d863) and four port
  directions shared by another wbqspiflash case (p0ba4e7). So the 5 moved plans were reasoned from their own
  packets' data. The 3 XTEA readers' finding that one flip-flop drives all 64 data outputs holds in each one's own
  packet (i1330, i976 and i394 reach all 64 output bits; the same name in the other packets does not).
- Packet ↔ case: p00d863 c01, p89c9e8 c02, p114b56 c03, p6dbefa c04, p3d0074 c05, pdc9e8d c06, p7a494d c07,
  pbae019 c08, p0ba4e7 c09, p10bfb9 c10 (farm/qa/IO/private/index.json).

## Setup (as registered; IO_PREREG.md)
- **Cases:** 10 of E2's 17 port-limited winners (worst setup slack at the first passing rebuild below the
  register-to-register worst slack), up to 3 per design by SHA-256 of the winner tag: c01 cic_decimator; c02, c06,
  c07 XTEA; c03, c04, c05 usb_cdc_core; c08, c09, c10 wbqspiflash. Each case keeps the winner's settings and its
  search target T0. sky130A, LibreLane 3.0.16 (pinned image), 9 STA corners, OpenRCX.
- **Arms:** stock (the record's job, OpenROAD's pin placer); script (nearest-side rule: up to 4 critical port groups
  to the die edge nearest their logic, written by Claude as Avi's hand baseline because Avi was asleep); claude (one
  fresh blind Opus 5.5 per case, one pin file each). Menu per port group: KEEP or one of 12 edge thirds; clock and
  reset fixed; bus order, layers, pin shape, 2-track pitch fixed. I/O delays stay 20% of the clock on every port, so
  only wire and cells inside the block are at stake. A plan is applied by a LibreLane step right after OpenROAD's
  IOPlacement, at every build of the chain.
- **Chain and judge:** source run at T0 (claim C0 = T0 − worst setup slack); rebuild at ceil05(C0); keep rebuilding
  at each new claim while it passes; one step back if the first rebuild fails; ≤ 4 rebuilds. Pass = flow complete,
  setup and hold ≥ 0 at all 9 corners, router DRC 0, slew+cap pins ≤ the design's stock bar. Kept clock K = smallest
  passing clock of the chain (source included).
- **Tests (score.py):** g(a over b) = K_b / K_a − 1; a beat is g > θ = 2.3% (E4's chaos floor). P1: Claude beats stock
  on ≥ 6 of 10. P2: median g(Claude over stock) ≥ 3%. P3: Claude beats the script on ≥ 5 of 10. The prediction
  holds iff P1, P2 and P3 all hold. An abstaining arm is run anyway (no-op plan).

## Caveats
- **The abstentions decided P1.** Abstaining was allowed by the registration; with 5 of 10 abstentions the registered
  test could no longer pass. The test measured "a blind Claude's pin choices, including the choice not to move",
  which is what was registered, but it gives only five cases of actual moves.
- **Small n:** 10 cases on 4 designs (3 + 3 + 3 + 1); cases of one design share RTL. One beat in ten is not
  distinguishable from the flow's response to any perturbation.
- **θ = 2.3% was measured for 1–40 ps target nudges (E4).** A pin move perturbs the flow far more. The 15 moved plans
  spread from −4.2% to +2.7% around a median of 0.0%, so c09's +2.7% and the script's +2.5% on c01 sit inside the
  range that moved plans produce in both directions.
- **Only the block's internal wire is at stake.** I/O delays are fixed at 20% of the clock on both sides; a real pin
  plan also changes top-level wire, which this test cannot see. Pins that help the block can hurt the parent.
- **The stock pins are a tool default**, not a designer's plan. The script baseline was written by Claude, not Avi.
- **XTEA's netlist is degenerate** (one flip-flop drives every output; the RTL audit found its outputs constant), so 3
  of the 10 cases have only a buffer tree for a port path. Without XTEA the Claude arm has 7 cases, 2 abstentions.
- **The 4-rebuild cap** stopped 9 of 30 chains that were still passing and improving (above): 7 XTEA chains (c02
  and c06 in all three arms, c07 script), c04 script and c08 Claude. Longer chains could move some kept clocks; the
  cap applied equally to every arm.
- **Blindness was imperfect:** the readers shared a scratch folder (above). The integrity check found every cited
  fact in the reader's own packet, but it cannot rule out an unstated influence.

## Deviations and notes
1. **After the PREREG hash, before any arm chain (IO1):** commit **bfcd14e** moved the private maps and the script
   arm's answers out of the reader-visible `pins/` tree and added one README line telling readers how the stock placer
   works ("each pin goes to a free slot near the cells it connects to in a preliminary placement made without pins;
   then all cells are placed again with the pins fixed"); commit **ceb0f82** made the packet builder read the
   collector's directory layout and added the reader instructions for the coordinator. No case, arm, menu, chain,
   judge, threshold or test changed.
2. **Shared scratchpad** (above): the readers were meant to see only their packet; they also shared a scratch folder.
   The integrity check found no sign that any plan was reasoned from another packet's data.
3. **Added after the Claude files were locked (analysis only, nothing registered):** farm/qa/IO/integrity_check.py and
   reader_scratch.py (committed fab915c while the chains ran) and describe.py (the reported-beside tables). The
   secondary view of the 5 moved cases was asked for after the files were locked; it is labelled as not registered.
4. The pseudonym salt and maps were committed (9b10673) after all readers had finished, as IO1 planned.
5. One workflow run, max_parallel 3, as registered; no smoke or other run was added in phase 2.

## Files
- Registration and locks: docs/qa_week/IO_PREREG.md; farm/prereg_hashes.txt; farm/qa/IO/arms/{script,claude}/
  (pin files, SHA256SUMS, the readers' rationale.md); farm/qa/IO/plans/c*-{script,claude}.json; farm/jobs/io-c*-*.json.
- Verdict: farm/qa/IO/score.py → farm/qa/IO/io_result.json. Beside: farm/qa/IO/describe.py → io_describe.json.
- Integrity: farm/qa/IO/integrity_check.py → integrity_check.json; farm/qa/IO/reader_scratch.py → reader_scratch.json.
- Smoke receipt and phase 1: SMOKE_IO (outbox), /home/claude/ideas/overnight/reports/IO1.md; phase 2:
  /home/claude/ideas/overnight/reports/IO2.md.
- Data: run 41574123655 artifacts `result-io-<case>-<arm>`; local copy /home/claude/qa/io-results.
