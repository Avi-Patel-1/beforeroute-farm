# des: Pipelined single DES (16-round, S-box lookup, key schedule)

Unmodified RTL copied (not symlinked) from https://github.com/The-OpenROAD-Project/OpenLane designs/des (tag v0.21 (a6ac8cf836df4d776136a9d71b86bfa8e89aa695)); upstream OpenCores DES/3DES by Rudolf Usselmann (ASICs World Services).
Author/copyright: Rudolf Usselmann (c) 2001.
License: **Permissive OpenCores/ASICs-ws notice (per source header)**; see `src/LICENSE` (the original notices are retained in the source headers).

Top module: `des`; single clock `clk`; no macros or SRAM.

## Local LibreLane 3 config (`config_sky130.json`)

CLOCK_PERIOD 20.0 ns, FP_CORE_UTIL 35, PL_TARGET_DENSITY_PCT 45, farm PDN block.
Original flow settings for reference: OpenLane v0.21 sky130_fd_sc_hd: CLOCK_PERIOD 20.0, FP_CORE_UTIL 35, PL_TARGET_DENSITY 0.40, SYNTH_MAX_FANOUT 6.

## Files

- `src/3des.v`  sha256 `eea6dd0612db20e5c367e52b0fe1044b90ef38393aea860103af68cd74e4c150`
- `src/LICENSE`  sha256 `ceb898163d203383c9291ace85e7624648be7f1fa5a96cae8550ca9241bb2fc1`
