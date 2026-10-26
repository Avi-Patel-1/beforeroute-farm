# chacha: ChaCha stream cipher core (ARX, 32-bit words) with 32-bit register API

Unmodified RTL copied (not symlinked) from https://github.com/The-OpenROAD-Project/OpenLane designs/chacha (tag v0.21 (a6ac8cf836df4d776136a9d71b86bfa8e89aa695)); upstream secworks/chacha.
Author/copyright: Secworks Sweden AB (c) 2013.
License: **BSD-2-Clause (per source header)**; see `src/LICENSE` (the original notices are retained in the source headers).

Top module: `chacha`; single clock `clk`; no macros or SRAM.

## Local LibreLane 3 config (`config_sky130.json`)

CLOCK_PERIOD 26.01 ns, FP_CORE_UTIL 35, PL_TARGET_DENSITY_PCT 45, farm PDN block.
Original flow settings for reference: OpenLane v0.21 sky130_fd_sc_hd: CLOCK_PERIOD 26.01, FP_CORE_UTIL 25, PL_TARGET_DENSITY 0.30, SYNTH_MAX_FANOUT 6.

## Files

- `src/chacha.v`  sha256 `67b8e5fac4da862aa5fdf0136cf67c69fa67e1a4674268abc617105fc7a3791c`
- `src/LICENSE`  sha256 `55e9419ccd331d8f4319753546b1e09701330a3037a11aa59ebd95334cfd4c88`
