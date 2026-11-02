# E5b (Addendum 42): ORFS design config for ORFS's gcd on the GT2N 2 nm kit, BSPDN-proxy router view.
#
# Adapted from the GT2N kit's example run config
#   gt2n_openroad_run/AES_128/GT2_2nm_PDK/03_spnr/tt/w31_svtlvt/1000ps_gt2n_compat_bspdn_proxy_u35_c48/config.mk
# in github.com/azadnaeemi/GT2N (Openroad_example/gt2n_openroad_runscripts_no_work_20260601.tar.gz, commit 5bc689f).
# Copyright (c) 2025, azadnaeemi. BSD-3-Clause; the license text is in farm/qa/E5b/GT2N_LICENSE.
# The kit itself is downloaded on the runner (farm/qa/E5b/setup_runner.sh); nothing else from it is vendored.
#
# Changes from the kit's file (design plumbing only):
#   - design: ORFS's gcd (flow/designs/src/gcd/gcd.v inside the pinned ORFS image) instead of AES-128;
#   - SDC: the kit's constraint.sdc with the design name and clock period substituted, one file per run;
#   - the kit's PDN stub and pre-final-report hook are referenced in place in the downloaded kit;
#   - NUM_CORES comes from the runner; the post-GDS BSPDN/DRC/LVS variables are dropped (those steps are not run).
#   - added: a reporting-only POST_FINAL_REPORT_TCL hook (farm/qa/E5b/post_final_report.tcl, worst slack per path class).
#   - LEC_CHECK=0: the image's formal-equivalence checker (kepler-formal, a check that changes nothing) dies
#     with SIGILL (illegal instruction) on GitHub-hosted runner CPUs; pipeline smoke run 41487719368.
# Every other setting (libraries, router-view tech LEF, tap cell, utilization, density, routing layers, RC and
# OpenRCX decks) is the kit's value, unchanged.

export RUN_DIR := $(patsubst %/,%,$(dir $(abspath $(lastword $(MAKEFILE_LIST)))))
export GT2N_KIT ?= /work/kit/gt2n_openroad_run
export CONTAINER_PROJ ?= $(GT2N_KIT)
export GT2N_EXAMPLE_RUN = $(GT2N_KIT)/AES_128/GT2_2nm_PDK/03_spnr/tt/w31_svtlvt/1000ps_gt2n_compat_bspdn_proxy_u35_c48

export DESIGN_NAME = gcd
export DESIGN_NICKNAME = gcd
export VERILOG_FILES = /OpenROAD-flow-scripts/flow/designs/src/gcd/gcd.v
export SDC_FILE = $(RUN_DIR)/constraint.sdc
export CORE_UTILIZATION ?= 35
export NUM_CORES ?= 4

export PLATFORM = gt2n_compat_bspdn_proxy
export PLATFORM_DIR = $(CONTAINER_PROJ)/OpenROAD-flow-scripts/flow/platforms/$(PLATFORM)
export SCRIPTS_DIR = /OpenROAD-flow-scripts/flow/scripts

export CORE_ASPECT_RATIO ?= 1
export CORE_MARGIN ?= 5.04
export PROCESS ?= 2

# Router view: BPR is masterslice, backside BM* layers are not routed by DRT (the kit's BSPDN-proxy method).
export TECH_LEF = $(PLATFORM_DIR)/techlib/gt2_fspdn_tech.lef
export SC_LEF = $(PLATFORM_DIR)/lef/gt2_6t_w31_svt.lef
export ADDITIONAL_LEFS = $(PLATFORM_DIR)/lef/gt2_6t_w31_lvt.lef

export GT2N_LIB_DIR ?= $(PLATFORM_DIR)/lib
export LIB_FILES = $(GT2N_LIB_DIR)/gt2_6t_w31_svt_tt_0p7v25c.lib \
                   $(GT2N_LIB_DIR)/gt2_6t_w31_lvt_tt_0p7v25c.lib
export GDS_FILES = $(wildcard $(PLATFORM_DIR)/gds/*.gds)
export DONT_USE_CELLS +=
export FILL_CELLS ?= gt2_6t_filler_w31_lvt

export TIEHI_CELL_AND_PORT = gt2_6t_tiehigh_w31_lvt Y
export TIELO_CELL_AND_PORT = gt2_6t_tielow_w31_lvt Y
export MIN_BUF_CELL_AND_PORTS = gt2_6t_buf_x1_w31_lvt A Y
export ABC_DRIVER_CELL = gt2_6t_buf_x1_w31_svt
export ABC_LOAD_IN_FF = 5
export LATCH_MAP_FILE :=
export CLKGATE_MAP_FILE :=
export ADDER_MAP_FILE :=
export MATCH_CELL_FOOTPRINT = 1

export PLACE_SITE = gt2_6t
export IO_PLACER_H ?= M2
export IO_PLACER_V ?= M3
export PDN_TCL ?= $(GT2N_EXAMPLE_RUN)/pdn_bspdn_proxy_router_view.tcl
export POST_PDN_TCL ?=
export TAP_CELL_NAME = gt2_6t_tapbspdn_w31_lvt
export TAPCELL_DISTANCE ?= 28
export TAPCELL_TCL ?= $(PLATFORM_DIR)/tapcell.tcl
export MACRO_PLACE_HALO ?= 40 40

export PLACE_DENSITY ?= 0.58
export CELL_PAD_IN_SITES_GLOBAL_PLACEMENT ?= 1
export CELL_PAD_IN_SITES_DETAIL_PLACEMENT ?= 0
export ENABLE_DPO ?= 0
export DETAIL_PLACEMENT_ARGS ?= -max_displacement {50 10}

export ROUTING_LAYER_ADJUSTMENT ?= 0.25
export DETAILED_ROUTE_END_ITERATION ?= 20
export MIN_ROUTING_LAYER ?= M1
export MIN_CLK_ROUTING_LAYER ?= M3
export MAX_ROUTING_LAYER ?= M9
export FASTROUTE_TCL ?= $(PLATFORM_DIR)/fastroute.tcl

export KLAYOUT_TECH_FILE = $(PLATFORM_DIR)/$(PLATFORM).lyt
export GDS_LAYER_MAP = $(PLATFORM_DIR)/techlib/gt2_techfile.layermap
export FILL_CONFIG = $(PLATFORM_DIR)/fill.json
export RCX_RULES = $(PLATFORM_DIR)/rcx_patterns.rules
export LAYER_PARASITICS_FILE ?= $(PLATFORM_DIR)/setRC_fspdn.tcl
export MAKE_TRACKS ?= $(PLATFORM_DIR)/make_tracks_fspdn.tcl
export POWER_ACTIVITY_TCL ?= $(PLATFORM_DIR)/scripts/power_activity_vectorless.tcl

# The router-view ODB has no physical BSPDN grid, so IR-drop analysis is off (as in the kit).
export PWR_NETS_VOLTAGES ?=
export GND_NETS_VOLTAGES ?=
export IR_DROP_LAYER ?= BPR
export PDNSIM_DONT_REQUIRE_TERMINALS ?= 0
export PDNSIM_SOURCE_TYPE ?= STRAPS

export PRE_FINAL_REPORT_TCL ?= $(GT2N_EXAMPLE_RUN)/pre_final_report_clear_psm.tcl
export E5B_DIR ?= /work/farm/qa/E5b
export POST_FINAL_REPORT_TCL ?= $(E5B_DIR)/post_final_report.tcl
export SAVE_FINAL_IMAGES ?= 0
export LEC_CHECK = 0
