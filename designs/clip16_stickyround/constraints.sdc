# Clock and I/O constraints of the clip study (2 ns input/output delay); the period follows CLOCK_PERIOD.
create_clock -name clk -period $::env(CLOCK_PERIOD) [get_ports clk]
set_input_delay 2 -clock clk [get_ports {x* rst}]
set_output_delay 2 -clock clk [get_ports y*]
set_driving_cell -lib_cell sky130_fd_sc_hd__inv_2 [get_ports {x* rst}]
set_input_transition 0.1 [get_ports clk]
set_load 0.033442 [get_ports y*]
