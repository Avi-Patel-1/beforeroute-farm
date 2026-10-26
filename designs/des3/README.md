# des3: Pipelined Triple-DES (3 x 16-round DES, S-box lookup, key schedule)

Unmodified RTL copied (not symlinked) from https://github.com/The-OpenROAD-Project/OpenLane designs/des3 (tag v0.21 (a6ac8cf836df4d776136a9d71b86bfa8e89aa695)); upstream OpenCores DES/3DES by Rudolf Usselmann (ASICs World Services).
Author/copyright: Rudolf Usselmann (c) 2001.
License: **Permissive OpenCores/ASICs-ws notice (per source header)**; see `src/LICENSE` (the original notices are retained in the source headers).

Top module: `des3`; single clock `clk`; no macros or SRAM.

## Local LibreLane 3 config (`config_sky130.json`)

CLOCK_PERIOD 7.59 ns, FP_CORE_UTIL 35, PL_TARGET_DENSITY_PCT 45, farm PDN block.
Original flow settings for reference: OpenLane v0.21 sky130_fd_sc_hd: CLOCK_PERIOD 7.59, FP_CORE_UTIL 20, PL_TARGET_DENSITY 0.25, SYNTH_MAX_FANOUT 7, SYNTH_STRAT 2.

## Files

- `src/3des.v`  sha256 `eea6dd0612db20e5c367e52b0fe1044b90ef38393aea860103af68cd74e4c150`
- `src/LICENSE`  sha256 `129c22dc37d671ffe405173d5d6086c7f440313a99cbc9f990e1b7cd50e261ff`
