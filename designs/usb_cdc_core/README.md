# usb_cdc_core: USB full-speed CDC device core (UTMI interface): SIE rx/tx, CRC16, descriptor ROM, control FSMs

Unmodified RTL copied (not symlinked) from https://github.com/efabless/openlane-ci-designs designs/usb_cdc_core (commit 6676a20db8775e0ca9a6df099e807b4951b8da6f); upstream ultraembedded/core_usb_cdc.
Author/copyright: Ultra-Embedded.com (c) 2014-2019.
License: **LGPL-2.1-or-later**; see `src/LICENSE` (the original notices are retained in the source headers).

Top module: `usb_cdc_core`; single clock `clk_i`; no macros or SRAM.

## Local LibreLane 3 config (`config_sky130.json`)

CLOCK_PERIOD 15.6 ns, FP_CORE_UTIL 35, PL_TARGET_DENSITY_PCT 45, farm PDN block.
Original flow settings for reference: OpenLane v1 sky130_fd_sc_hd: CLOCK_PERIOD 15.6, FP_CORE_UTIL 30, PL_TARGET_DENSITY 0.32, MAX_FANOUT_CONSTRAINT 6.

## Files

- `src/usb_cdc_core.v`  sha256 `33906ba6319c44fed3bdcab8a807e5522834f00cdbf4025cd1c092c54671e002`
- `src/usb_desc_rom.v`  sha256 `88ca70d23a44d25230723226e1c8a2a84de5b0f9cf85e65db13c60afb41f3c69`
- `src/usbf_crc16.v`  sha256 `ad478724e9e71c724788274c237a8324d27deb17724b39d0681740eda92f18d9`
- `src/usbf_device_core.v`  sha256 `1f58285528261cd78340a50df8126a0feb1b3692b230ab297c760c80f18479d5`
- `src/usbf_sie_rx.v`  sha256 `8b357ce23dfa2ad8ce418289be7056f6a1fd2af41afa0e088f7846cff7638464`
- `src/usbf_sie_tx.v`  sha256 `46d7fa236a8a03d1fab7f99ffb4b8b18e81c866d85ead4b849dd0c4556eaec59`
- `src/usbf_defs.v`  sha256 `5ea9871d316cea1a9b7f5faf33c0f9b3bb513594aacb33288638c2a64a28f484`
- `src/LICENSE`  sha256 `dc626520dcd53a22f727af3ee42c770e56c97a64fe3adb063799d8ab032fe551`
