# nvdla_csc: NVDLA nv_small Convolution Sequence Controller (`NV_NVDLA_csc`)

One block of NVIDIA's open-source NVDLA accelerator, nv_small configuration (INT8, MAC atomic
C=8/K=8, 32-bank CBUF, no Winograd/batch). CSC is the sequencer between the convolution buffer
and the MAC array: it loads feature data and weights from CBUF (data loader `dl`, weight loader
`wl` + `WL_dec`), generates the MAC sequence (`sg`, with two 4-deep flop FIFOs), and holds
the CSB register file. In nv_small it has no SRAM macros: the only storage is flops
(the two FIFO RAMs are in-file `flopram_rwsa_4x20/4x33` models).

**The NVDLA RTL is not in this repository.** `fetch_rtl.py` downloads it at job time into
`rtl/` (git-ignored) and checks every file against a pinned SHA-256; job specs run it through
`prefetch` (see `br/run_job.py`). Nothing downloaded is executed; it is Verilog text read by
Yosys/OpenROAD.

## Provenance

- Generated RTL: `ucb-bar/nvdla-wrapper` @ `d99ffdc79bbf9b86c6cad0c278a785d5802c8209`
  (UC Berkeley BAR; the NVDLA generator used by Chipyard), path
  `src/main/resources/vsrc/small/vmod/`, which is a copy of nvdla/hw `outdir/nv_small/vmod`
  made by its `build-hw-vmod.sh` (`tools/bin/tmake -build vmod`, `tree.make` project nv_small).
  nvdla/hw itself ships only the un-generated sources (C-preprocessor macros + embedded
  `//:` Perl that `vcp`/`eperl` expand); its `nv_small` branch has no `outdir`.
- Upstream source: `nvdla/hw` master @ `1a65f1f5b48268accaa47c95f95c2601918be095` (NVDLA_2).
  nvdla-wrapper's own `hw` submodule pointer (8e06b1b, nvdlav1) is stale (nvdlav1 has no
  nv_small spec), so the generating commit was checked instead: for all 14 files, the
  identifier stream of the generated file outside its `//| eperl: generated_beg/end`
  blocks (comments stripped, `//:` Perl kept) matches the nvdla/hw master source except for
  cpp-macro literals (`'h08` ...) and the `#ifdef NVDLA_WINOGRAD_ENABLE` / `NVDLA_BATCH_ENABLE`
  branches that nv_small disables (CSC_sg.v). The `nv_small` branch tip (771f20c) does not
  match (older `NV_NVDLA_CSC_dl.v`).
- License: **NVIDIA Open NVDLA License and Agreement v1.0** (nvdla/hw `LICENSE`, fetched to
  `rtl/LICENSE.NVDLA`; every RTL file keeps NVIDIA's header). Royalty-free patent and
  copyright license; redistribution must include the license, mark modified files and keep
  notices; it has a waiver/indemnity clause (sec. 10). We do not redistribute the RTL.

## Files fetched (relative to `vmod/`)

`nvdla/csc/`: `NV_NVDLA_csc.v` (top), `NV_NVDLA_CSC_slcg.v`, `NV_NVDLA_CSC_dl.v`,
`NV_NVDLA_CSC_wl.v`, `NV_NVDLA_CSC_WL_dec.v`, `NV_NVDLA_CSC_sg.v`, `NV_NVDLA_CSC_SG_wt_fifo.v`,
`NV_NVDLA_CSC_SG_dat_fifo.v`, `NV_NVDLA_CSC_regfile.v`, `NV_NVDLA_CSC_dual_reg.v`,
`NV_NVDLA_CSC_single_reg.v`; `vlibs/NV_CLK_gate_power.v`, `vlibs/NV_BLKBOX_SINK.v` (empty sink
cell for unused `pwrbus_ram_pd` bits); `include/simulate_x_tick.vh`. SHA-256s in `fetch_rtl.py`.
Unmodified; no local edits to the RTL.

## Local LibreLane 3 config (`config_sky130.json`)

- Top `NV_NVDLA_csc`, single clock `nvdla_core_clk`, async active-low reset `nvdla_core_rstn`.
- `VERILOG_DEFINES`: `SYNTHESIS` (drops simulation/assertion code), `VLIB_BYPASS_POWER_CG`
  (the SLCG clock gates become `assign clk_gated = clk`, so every flop is on
  `nvdla_core_clk`; no latch-based ICGs in the netlist), `DESIGNWARE_NOEXIST`, `VERILINT`
  (only skips two `nv_assert_no_x` instances in `NV_CLK_gate_power.v` that are hidden from
  Yosys by `synopsys translate_off` but not from Verilator; without it lint fails MODMISSING).
- CLOCK_PERIOD 25 ns, FP_CORE_UTIL 35, PL_TARGET_DENSITY_PCT 45, farm PDN block.
- 783 port bits (sc2mac data/weight buses for both MAC halves, CBUF read ports, CSB).
- Yosys warnings are benign: "wire X is assigned in a block" (outputs re-declared as `reg`,
  legal Verilog-1995 style) and one `translate_off` hot-comment notice.

## Size (LibreLane 3.0.16, sky130_fd_sc_hd, base config)

- `Yosys.Synthesis`: **21,399 cells**, 0.283 mm² cell area; 4,962 flops (3,392 `dfrtp`,
  1,444 `dfxtp`, 126 `dfstp`), 0 latches, `check` clean; 1 min 51 s on a 2-vCPU machine
  (lint through `OpenROAD.STAPrePNR`: 163 s).
- Pre-PnR STA (ideal clocks, unbuffered nets) at 25 ns: reg-to-reg worst setup slack
  +9.7 ns at nom_tt_025C_1v80, -2.9 ns at nom_ss_100C_1v60 (the -40 ns overall WNS is the
  unbuffered `nvdla_core_rstn` recovery check, fixed by repair_design).
