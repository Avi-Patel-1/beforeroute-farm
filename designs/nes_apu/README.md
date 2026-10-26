# nes_apu: NES audio processing unit: square/triangle/noise/DMC channels, length counters, lookup tables

Unmodified RTL copied (not symlinked) from https://github.com/efabless/openlane-ci-designs designs/APU (commit 6676a20db8775e0ca9a6df099e807b4951b8da6f); upstream strigeus/fpganes.
Author/copyright: Ludvig Strigeus (c) 2012-2013.
License: **GPL-3.0 (COPYING) -- NOT a permissive license**; see `src/LICENSE` (the original notices are retained in the source headers).

Top module: `APU`; single clock `clk`; no macros or SRAM.

## Local LibreLane 3 config (`config_sky130.json`)

CLOCK_PERIOD 17.0 ns, FP_CORE_UTIL 35, PL_TARGET_DENSITY_PCT 45, farm PDN block.
Original flow settings for reference: OpenLane v1 sky130: CLOCK_PERIOD 17, FP_CORE_UTIL 35, MAX_FANOUT_CONSTRAINT 6, heuristic diode insertion on input ports.

## Files

- `src/APU.v`  sha256 `9ce48bb719b6dec9c77b19e9a236f377d5d0fe9469eadb0243b1963879000fde`
- `src/LICENSE`  sha256 `8ceb4b9ee5adedde47b31e975c1d90c73ad27b6b165a1dcd80c7c545eb65b903`
