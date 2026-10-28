# PPU: NES picture processing unit

Unmodified RTL copied (not symlinked) from https://github.com/The-OpenROAD-Project/OpenLane designs/PPU (tag v0.21 (a6ac8cf836df4d776136a9d71b86bfa8e89aa695)).
License: **GPL (per source header, Ludvig Strigeus)**; the original notices are retained in the source headers.

Top module: `PPU`; single clock `clk`; no macros or SRAM.

## Local LibreLane 3 config (`config_sky130.json`)

CLOCK_PERIOD 18.0 ns (OpenLane v0.21 sky130_fd_sc_hd setting), FP_CORE_UTIL 35, PL_TARGET_DENSITY_PCT 45, farm PDN block (as every other design here).
Held-out design of Addendum 30 (no study had run it before).

## Files

- `src/PPU.v`  sha256 `0c43cc5ca0f0236bd6d12845cd2351e308bf6f42bed35c451c5077611062a784`
