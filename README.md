# TrueClock

**Recursive AI for chip design, proven by rebuilding at every predicted speed.**

AI flow tuners rank a run by the clock it predicts: the period it asked for minus its worst slack.
Nobody builds the design at that clock, and a new clock target builds a different circuit, so the
prediction can miss in either direction. This repository holds my code and the full record behind
that finding on an open RTL-to-GDS flow, and behind AI that improves itself once every winner is
rebuilt at its predicted speed.

## Results at a glance (as of Oct 30, 2026)

- **The audit:** 3 of 8 Bayesian-tuned winners failed when rebuilt at their predicted clock, and
  33 of 40 later winners passed rebuilds faster than they predicted (median 1.12×, up to 1.50×).
- **Rebuilding again** after the first passing rebuild gained a median 1.10× more verified
  frequency (up to 1.50×) across 50 winners.
- **Report-reading AI:** Claude Opus 5.5, reading every run's timing report, beat Bayesian search
  on 6 of 7 held-out designs. Search rules it wrote from the reports beat plain Bayesian search in
  9 of 10 races, and 8 of 10 with a quarter of the search runs.
- **One layer up:** a rewrite of the MD5 core's RTL from its routed critical path reached 1.75× the
  clock with the same cycles per hash (+47% performance per area).

## The method: rebuild at the predicted speed

1. Take a winner and its predicted clock (asked clock minus slack), rounded up to 0.05 ns.
2. Rebuild the same settings at that clock and judge the result.
3. While it passes, rebuild at the new prediction, at most four rebuilds per winner.
4. Keep the last clock that passed.

One extra run per top winner catches a false prediction; the later rebuilds are optional upside.
The rule wraps any tuner or sweep.

## The judge

Every clock I report passed post-route static timing at nine corners (3 process, voltage and
temperature corners × 3 RC extraction corners) with setup and hold met, router DRC clean, and slew
and capacitance no worse than the stock flow. Signoff DRC and LVS were switched off in tuning runs
to save time.

## Layout

- `farm/` — job specs (`jobs/`), dispatcher, collectors, local worker, and the tuners with their
  rebuild chains (`tune_a32.py` to `tune_a36.py`).
- `farm/agent_a32/`, `farm/agent_a35/` — every LLM prompt and reply, per design, seed and round.
- `farm/agent_a34/`, `farm/rtl34/`, `farm/rtl35/` — RTL rewrites: prompts, replies, rewritten
  Verilog, critical-path extraction and equivalence-check logs.
- `farm/prereg_hashes.txt` — SHA-256 commitments of my pre-registration document, appended before
  each pre-registered dispatch.
- `designs/` — open benchmark designs with SKY130 HD configs, including the MD5 rewrites
  (`md5_a34_r1`, `md5_a34_r2`, `md5_a35_r3`).
- `br/`, `models/` — the project's first phase, BeforeRoute (predicting pre-route parasitic errors
  and targeted repair), plus analysis and figure code. The repository keeps that name.
- `.github/workflows/` — workflows that run each job spec on the pinned LibreLane image.

## Toolchain

`ghcr.io/librelane/librelane:3.0.16` (OpenROAD `dcf36133a`, Yosys 0.62); SKY130 PDK at ciel
`8afc8346a57fe1ab7934ba5a6056ea8b43078e71`; Optuna for Bayesian search.

## Designs and licenses

Designs come from OpenLane v0.21 (commit a6ac8cf8) and other open repositories, each under its own
license; the MD5 core is by J. Castillo (OpenCores, LGPL).
