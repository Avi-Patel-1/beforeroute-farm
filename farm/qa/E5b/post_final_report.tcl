# E5b: reporting-only hook, sourced by ORFS's final_report.tcl after report_metrics (POST_FINAL_REPORT_TCL).
# Writes the worst setup slack of each path class (register-to-register, input-to-register, register-to-output,
# input-to-output) on the extracted post-route timing graph. It changes nothing in the design.
if {[catch {
  proc e5b_ws {args} {
    set ends [find_timing_paths {*}$args -path_delay max -sort_by_slack]
    if {[llength $ends] == 0} { return "none" }
    return [format "%.4f" [get_property [lindex $ends 0] slack]]
  }
  set e5b_regs_ck [all_registers -clock_pins]
  set e5b_regs_d [all_registers -data_pins]
  set e5b_in [all_inputs -no_clocks]
  set e5b_out [all_outputs]
  set f [open $::env(REPORTS_DIR)/6_e5b_path_classes.txt w]
  puts $f "reg2reg [e5b_ws -from $e5b_regs_ck -to $e5b_regs_d]"
  puts $f "in2reg [e5b_ws -from $e5b_in -to $e5b_regs_d]"
  puts $f "reg2out [e5b_ws -from $e5b_regs_ck -to $e5b_out]"
  puts $f "in2out [e5b_ws -from $e5b_in -to $e5b_out]"
  puts $f "all [e5b_ws]"
  close $f
} err]} {
  puts "E5b post-final-report hook failed (reporting only): $err"
}
