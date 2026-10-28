# cic_decimator: CIC decimation filter (verilog-dsp)

Unmodified RTL copied (not symlinked) from https://github.com/The-OpenROAD-Project/OpenLane designs/cic_decimator (tag v0.21 (a6ac8cf836df4d776136a9d71b86bfa8e89aa695)).
License: **MIT (per source header, Alex Forencich)**; the original notices are retained in the source headers.

Top module: `cic_decimator` (default parameters); single clock `clk`; no macros or SRAM.

## Local LibreLane 3 config (`config_sky130.json`)

CLOCK_PERIOD 10.0 ns (OpenLane v0.21 sky130_fd_sc_hd setting), FP_CORE_UTIL 35, PL_TARGET_DENSITY_PCT 45, farm PDN block (as every other design here).
Held-out design of Addendum 30 (no study had run it before).

ERROR_ON_SYNTH_CHECKS = false (Amendment 30.1): the original RTL trips Yosys's lint check — module-level loop-index registers driven from two always blocks (dead after unrolling); the checks are reported as warnings, the RTL is unchanged.

## Files

- `src/cic_decimator.v`  sha256 `17d1e2d1c5dc89ba5a4d1b93f2c2b27c1021181fb9412c2ef4201c6b5816d26d`
