# xtea: XTEA block cipher (64-bit block, 128-bit key, 32 iterative rounds)

Unmodified RTL copied (not symlinked) from https://github.com/efabless/openlane-ci-designs designs/xtea (commit 6676a20db8775e0ca9a6df099e807b4951b8da6f); upstream OpenCores xtea (David Johnson).
Author/copyright: David Johnson (c) 2006.
License: **LGPL-2.1-or-later**; see `src/LICENSE` (the original notices are retained in the source headers).

Top module: `xtea`; single clock `clock`; no macros or SRAM.

## Local LibreLane 3 config (`config_sky130.json`)

CLOCK_PERIOD 26.03 ns, FP_CORE_UTIL 45, PL_TARGET_DENSITY_PCT 50, farm PDN block.
Original flow settings for reference: OpenLane v1 sky130_fd_sc_hd: CLOCK_PERIOD 26.03, FP_CORE_UTIL 45, PL_TARGET_DENSITY 0.50, MAX_FANOUT_CONSTRAINT 6, heuristic diode insertion on input ports; src/xtea.sdc not used (flow-generated SDC instead).

## Files

- `src/xtea.v`  sha256 `27e302c760660bad28d0e72533e65a2af1a482cd39313ca174b00f1fd7ab4ece`
- `src/LICENSE`  sha256 `dc626520dcd53a22f727af3ee42c770e56c97a64fe3adb063799d8ab032fe551`
