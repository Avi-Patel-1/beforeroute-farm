# APU: NES audio processing unit

Unmodified RTL copied (not symlinked) from https://github.com/The-OpenROAD-Project/OpenLane designs/APU (tag v0.21 (a6ac8cf836df4d776136a9d71b86bfa8e89aa695)).
License: **GPL (per source header, Ludvig Strigeus)**; the original notices are retained in the source headers.

Top module: `APU`; single clock `clk`; no macros or SRAM.

## Local LibreLane 3 config (`config_sky130.json`)

CLOCK_PERIOD 17.0 ns (OpenLane v0.21 sky130_fd_sc_hd setting), FP_CORE_UTIL 35, PL_TARGET_DENSITY_PCT 45, farm PDN block (as every other design here).
Held-out design of Addendum 30 (no study had run it before).

## Files

- `src/APU.v`  sha256 `cf43298615a95558c2b594938dc05a05c6a85428434111ba9e158a7fa8f53fbf`
