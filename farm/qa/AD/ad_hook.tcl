# AD (TrueClock overnight, A and D): read-only measurement hook, sourced by ORFS as POST_FINAL_REPORT_TCL at the end
# of the finish report (after OpenRCX extraction or the platform's fallback, and after report_metrics). Part 1 is
# farm/qa/E5/e5_hook.tcl unchanged: worst setup slack per path group (register-to-register, from inputs, to
# outputs) and worst hold slack, to $REPORTS_DIR/e5_hook.json. Part 2 runs only with AD_RETIME=1 (T3): it re-times
# the finished layout (no change to the design) at two clocks and writes $REPORTS_DIR/ad_retime.json:
#   t0    the run's own clock, re-applied the same way as below: a check that re-reading the constraints reproduces the
#         flow's own finish numbers;
#   tstar the corrected claim T* = ceil5(max(T0 - ws_r2r, T0 - ws_port / 0.8)), ws_port = min(ws_in, ws_out): the
#         register-to-register claim, and port paths corrected for their I/O budget (20% of the clock at each port,
#         so a port path's slack moves 0.8 per unit of clock).
# Re-timing re-reads the run's own constraint.sdc with `set clk_period` replaced (the substitution the flow used to
# build it), then `set_propagated_clock [all_clocks]` as ORFS's final_connect.tcl does; parasitics stay as loaded.

proc e5_num { v } {
  if { [regexp {^-?[0-9]+(\.[0-9]+)?([eE][-+]?[0-9]+)?$} [string trim $v]] } {
    return [string trim $v]
  }
  return "null"
}

proc e5_pe_slack { pe } {
  if { ![catch { set s [$pe slack] }] } {
    return [e5_num [sta::format_time $s 4]]
  }
  if { ![catch { set s [get_property $pe slack] }] } {
    return [e5_num $s]
  }
  return "null"
}

proc e5_ws { min_max args } {
  set pes [find_timing_paths -path_delay $min_max -sort_by_slack {*}$args]
  if { [llength $pes] == 0 } {
    return "null"
  }
  return [e5_pe_slack [lindex $pes 0]]
}

proc e5_pin_name { pe which } {
  if { [catch { set p [get_property $pe $which] } err] } {
    return "?"
  }
  if { [catch { set n [get_full_name $p] } err] } {
    return "?"
  }
  return $n
}

proc ad_measure { } {
  set ws_all [e5_ws max]
  set ws_r2r [e5_ws max -from [all_registers] -to [all_registers]]
  set ws_in [e5_ws max -from [all_inputs -no_clocks]]
  set ws_out [e5_ws max -to [all_outputs]]
  set hs_all [e5_ws min]
  set worst [lindex [find_timing_paths -path_delay max -sort_by_slack] 0]
  set sp [e5_pin_name $worst startpoint]
  set ep [e5_pin_name $worst endpoint]
  return [list $ws_all $ws_r2r $ws_in $ws_out $hs_all $sp $ep]
}

proc ad_json { m } {
  lassign $m ws_all ws_r2r ws_in ws_out hs_all sp ep
  return "{\"ws_all\": $ws_all, \"ws_r2r\": $ws_r2r, \"ws_in\": $ws_in, \"ws_out\": $ws_out,\
 \"hold_ws_all\": $hs_all, \"worst_start\": \"$sp\", \"worst_end\": \"$ep\"}"
}

# ---- part 1: E5's measurement at the run's own clock
set ad_m0 {}
if { [catch {
  set ad_m0 [ad_measure]
  set f [open $::env(REPORTS_DIR)/e5_hook.json w]
  puts $f [ad_json $ad_m0]
  close $f
  puts "E5 hook: [ad_json $ad_m0]"
} err] } {
  puts "E5 hook error: $err"
}

# ---- part 2 (T3 only): re-time the finished layout
proc ad_reconstrain { period_u } {
  set src [file join $::env(AD_RESULTS_DIR) constraint.sdc]
  set fh [open $src r]
  set txt [read $fh]
  close $fh
  set n [regsub -line {^set clk_period .*$} $txt "set clk_period $period_u" txt2]
  if { $n != 1 } {
    error "expected one 'set clk_period' line in $src"
  }
  set dst [file join $::env(REPORTS_DIR) ad_retime_$period_u.sdc]
  set fh [open $dst w]
  puts -nonewline $fh $txt2
  close $fh
  read_sdc $dst
  set_propagated_clock [all_clocks]
}

if { [info exists ::env(AD_RETIME)] && $::env(AD_RETIME) == 1 && [llength $ad_m0] == 7 } {
  if { [catch {
    lassign $ad_m0 ws_all ws_r2r ws_in ws_out hs_all sp ep
    set T0 $::env(AD_PERIOD_U)
    set port [expr { min($ws_in, $ws_out) }]
    set c_r2r [expr { $T0 - $ws_r2r }]
    set c_port [expr { $T0 - $port / 0.8 }]
    set cstar [expr { max($c_r2r, $c_port) }]
    # ceil to the 5 ps grid (in the SDC's unit; asap7 and gt2n: ps, sky130hd: ns)
    set g [expr { 5.0 / $::env(AD_UNIT_PS) }]
    set tstar [expr { ceil(($cstar - 1e-3 / $::env(AD_UNIT_PS)) / $g) * $g }]
    if { $::env(AD_UNIT_PS) == 1 } {
      set tstar [expr { int($tstar) }]
    } else {
      set tstar [format %.3f $tstar]
    }
    set out "{\"T0\": $T0, \"c_r2r\": $c_r2r, \"c_port\": $c_port, \"cstar\": $cstar, \"tstar\": $tstar"
    foreach {lab per} [list t0 $T0 tstar $tstar] {
      ad_reconstrain $per
      set m [ad_measure]
      append out ", \"$lab\": [ad_json $m]"
      puts "AD retime $lab ($per): [ad_json $m]"
    }
    append out "}"
    set f [open $::env(REPORTS_DIR)/ad_retime.json w]
    puts $f $out
    close $f
  } err] } {
    puts "AD retime error: $err"
    set f [open $::env(REPORTS_DIR)/ad_retime.json w]
    puts $f "{\"error\": \"[string map {\" '} $err]\"}"
    close $f
  }
}
