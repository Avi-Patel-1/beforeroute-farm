# usb_cdc_core: USB CDC device core (ultra-embedded)

Unmodified RTL copied (not symlinked) from https://github.com/The-OpenROAD-Project/OpenLane designs/usb_cdc_core (tag v0.21 (a6ac8cf836df4d776136a9d71b86bfa8e89aa695)).
License: **LGPL (per source header, Ultra-Embedded)**; the original notices are retained in the source headers.

Top module: `usb_cdc_core`; single clock `clk_i`; no macros or SRAM.

## Local LibreLane 3 config (`config_sky130.json`)

CLOCK_PERIOD 15.6 ns (OpenLane v0.21 sky130_fd_sc_hd setting), FP_CORE_UTIL 35, PL_TARGET_DENSITY_PCT 45, farm PDN block (as every other design here).
VERILOG_INCLUDE_DIRS = src (usbf_defs.v is `include`d, not compiled on its own).
Held-out design of Addendum 30 (no study had run it before).

ERROR_ON_SYNTH_CHECKS = false (Amendment 30.1): the original RTL trips Yosys's lint check — one undriven wire, ep2_tx_stall_w; the checks are reported as warnings, the RTL is unchanged.

## Files

- `src/usb_cdc_core.v`  sha256 `c79cb0e5510033caed0d81f9e760ba79757e8170d09298b65c409bd927f5a8a3`
- `src/usb_desc_rom.v`  sha256 `88ca70d23a44d25230723226e1c8a2a84de5b0f9cf85e65db13c60afb41f3c69`
- `src/usbf_crc16.v`  sha256 `ad478724e9e71c724788274c237a8324d27deb17724b39d0681740eda92f18d9`
- `src/usbf_device_core.v`  sha256 `1f58285528261cd78340a50df8126a0feb1b3692b230ab297c760c80f18479d5`
- `src/usbf_sie_rx.v`  sha256 `8b357ce23dfa2ad8ce418289be7056f6a1fd2af41afa0e088f7846cff7638464`
- `src/usbf_sie_tx.v`  sha256 `46d7fa236a8a03d1fab7f99ffb4b8b18e81c866d85ead4b849dd0c4556eaec59`
- `src/usbf_defs.v`  sha256 `5ea9871d316cea1a9b7f5faf33c0f9b3bb513594aacb33288638c2a64a28f484`
