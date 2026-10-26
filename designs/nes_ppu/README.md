# nes_ppu: NES picture processing unit: sprite RAM/evaluation, background painter, palette RAM, loopy scroll generator

Unmodified RTL copied (not symlinked) from https://github.com/efabless/openlane-ci-designs designs/PPU (commit 6676a20db8775e0ca9a6df099e807b4951b8da6f); upstream strigeus/fpganes.
Author/copyright: Ludvig Strigeus (c) 2012-2013.
License: **GPL-3.0 (COPYING) -- NOT a permissive license**; see `src/LICENSE` (the original notices are retained in the source headers).

Top module: `PPU`; single clock `clk`; no macros or SRAM.

## Local LibreLane 3 config (`config_sky130.json`)

CLOCK_PERIOD 18.0 ns, FP_CORE_UTIL 35, PL_TARGET_DENSITY_PCT 45, farm PDN block.
Original flow settings for reference: OpenLane v1 sky130: CLOCK_PERIOD 18, FP_CORE_UTIL 20, GPL/DPL_CELL_PADDING 4, MAX_FANOUT_CONSTRAINT 8, heuristic diode insertion on input ports.

## Files

- `src/PPU.v`  sha256 `0c43cc5ca0f0236bd6d12845cd2351e308bf6f42bed35c451c5077611062a784`
- `src/LICENSE`  sha256 `8ceb4b9ee5adedde47b31e975c1d90c73ad27b6b165a1dcd80c7c545eb65b903`
