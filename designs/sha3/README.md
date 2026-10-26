# sha3: SHA-3 (Keccak-f[1600]) hash core with 32-bit register API: 1600-bit state, theta/rho/pi/chi/iota rounds

Unmodified RTL copied (not symlinked) from https://github.com/The-OpenROAD-Project/OpenLane designs/sha3 (tag v0.21 (a6ac8cf836df4d776136a9d71b86bfa8e89aa695)); upstream Assured AB / secworks-style sha3 core.
Author/copyright: Joachim Strombergson / Assured AB (c) 2015.
License: **BSD-2-Clause (per source header)**; see `src/LICENSE` (the original notices are retained in the source headers).

Top module: `sha3`; single clock `clk`; no macros or SRAM.

## Local LibreLane 3 config (`config_sky130.json`)

CLOCK_PERIOD 12.71 ns, FP_CORE_UTIL 35, PL_TARGET_DENSITY_PCT 45, farm PDN block.
Original flow settings for reference: OpenLane v0.21 sky130_fd_sc_hd: CLOCK_PERIOD 12.71, FP_CORE_UTIL 35, PL_TARGET_DENSITY 0.40, SYNTH_MAX_FANOUT 6; src/sha3.sdc not used.

## Files

- `src/sha3.v`  sha256 `9573f0715b2b1f943e04eb62ea7216784f8b95fb05085db5223225fb6b61a4ec`
- `src/LICENSE`  sha256 `2a027bbe6bb7d78cce6f902d8738927898db6ec1aa59aeb33158f2e2a8f963ea`
