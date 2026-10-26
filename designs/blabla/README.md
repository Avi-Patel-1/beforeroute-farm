# blabla: BlaBla stream cipher core (64-bit ARX, BLAKE2b-style G function)

Unmodified RTL copied (not symlinked) from https://github.com/efabless/openlane-ci-designs designs/blabla (commit 6676a20db8775e0ca9a6df099e807b4951b8da6f); upstream secworks/blabla.
Author/copyright: Joachim Strombergson / Assured AB (c) 2017.
License: **BSD-2-Clause (per source header)**; see `src/LICENSE` (the original notices are retained in the source headers).

Top module: `blabla`; single clock `clk`; no macros or SRAM.

## Local LibreLane 3 config (`config_sky130.json`)

CLOCK_PERIOD 65.0 ns, FP_CORE_UTIL 35, PL_TARGET_DENSITY_PCT 45, farm PDN block.
Original flow settings for reference: OpenLane v1 sky130: CLOCK_PERIOD 65, FP_CORE_UTIL 5, *_MAX_WIRE_LENGTH 500, heuristic diode insertion on input ports.

## Files

- `src/blabla.v`  sha256 `6820fa53123132a1253b1bb42c9585f13a856263ef36581f4cb93dee9ee76cd9`
- `src/LICENSE`  sha256 `b63d1146daed24c80f641cd9805ceb68aa7938c4b952e246807a80e463b1e78f`
