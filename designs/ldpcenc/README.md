# ldpcenc: IEEE 802.11n/ac LDPC encoder: control unit, parity datapath with XOR trees, cyclic shifters, parity-check tables

Unmodified RTL copied (not symlinked) from https://github.com/The-OpenROAD-Project/OpenLane designs/ldpcenc (tag v0.21 (a6ac8cf836df4d776136a9d71b86bfa8e89aa695)); upstream Guangxi Liu Wi-Fi LDPC encoder.
Author/copyright: Guangxi Liu (c) 2019.
License: **MIT (per source header; upstream LICENSE file not bundled)**; see `src/LICENSE` (the original notices are retained in the source headers).

Top module: `ldpcenc`; single clock `clk`; no macros or SRAM.

## Local LibreLane 3 config (`config_sky130.json`)

CLOCK_PERIOD 12.9 ns, FP_CORE_UTIL 35, PL_TARGET_DENSITY_PCT 45, farm PDN block.
Original flow settings for reference: OpenLane v0.21 sky130_fd_sc_hd: CLOCK_PERIOD 12.9, FP_CORE_UTIL 25, PL_TARGET_DENSITY 0.30, SYNTH_MAX_FANOUT 6.

## Files

- `src/ldpcenc.v`  sha256 `a2503d0fcdce89c28482778ae79e7413f9159618ccead007602f540801eca116`
- `src/LICENSE`  sha256 `58d43ca3312c7826aabb6a9886f04270eb23d5f2bf4fb42b5e2d1ef7b73d0438`
