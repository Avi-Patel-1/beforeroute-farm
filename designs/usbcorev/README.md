# usbcorev: USB 1.1/2.0 full-speed device SIE (usbcorev): clock recovery, NRZI/bit-destuff, CRC5/16, endpoint logic

Unmodified RTL copied (not symlinked) from https://github.com/efabless/openlane-ci-designs designs/usb (commit 6676a20db8775e0ca9a6df099e807b4951b8da6f); upstream avakar/usbcorev.
Author/copyright: Martin Vejnar (c) 2017.
License: **MIT (per source header)**; see `src/LICENSE` (the original notices are retained in the source headers).

Top module: `usb`; single clock `clk_48`; no macros or SRAM.

## Local LibreLane 3 config (`config_sky130.json`)

CLOCK_PERIOD 15.0 ns, FP_CORE_UTIL 40, PL_TARGET_DENSITY_PCT 50, farm PDN block.
Original flow settings for reference: OpenLane v1 sky130_fd_sc_hd: CLOCK_PERIOD 15, FP_CORE_UTIL 40, MAX_FANOUT_CONSTRAINT 6, SYNTH_STRATEGY DELAY 0.

## Files

- `src/usb2p0_core.v`  sha256 `6bfa2e3e48369a21767936e29096dbc6f9d99e2441800e80cd9d380b2429f7b8`
- `src/LICENSE`  sha256 `227286b8a0bd3d020e3a5256de5cb427b8a1bd8f76d8cba53e4a85621e08b5fe`
