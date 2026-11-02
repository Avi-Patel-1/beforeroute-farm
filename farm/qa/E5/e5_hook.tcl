# E5 (Addendum 41): read-only measurement hook, sourced by ORFS as POST_FINAL_REPORT_TCL at the end of the finish
# report (after OpenRCX extraction and report_metrics). It does not change the design. It writes the worst setup slack
# per path group (register-to-register, from inputs, to outputs) and the worst hold slack to
# $REPORTS_DIR/e5_hook.json, so a run can be classified as port-limited or register-limited like the sky130 record.

# finite number in user time units (ps), or null
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

if { [catch {
  set ws_all [e5_ws max]
  set ws_r2r [e5_ws max -from [all_registers] -to [all_registers]]
  set ws_in [e5_ws max -from [all_inputs -no_clocks]]
  set ws_out [e5_ws max -to [all_outputs]]
  set hs_all [e5_ws min]
  set worst [lindex [find_timing_paths -path_delay max -sort_by_slack] 0]
  set sp [e5_pin_name $worst startpoint]
  set ep [e5_pin_name $worst endpoint]
  set f [open $::env(REPORTS_DIR)/e5_hook.json w]
  puts $f "{\"ws_all\": $ws_all, \"ws_r2r\": $ws_r2r, \"ws_in\": $ws_in, \"ws_out\": $ws_out,\
 \"hold_ws_all\": $hs_all, \"worst_start\": \"$sp\", \"worst_end\": \"$ep\"}"
  close $f
  puts "E5 hook: ws_all=$ws_all ws_r2r=$ws_r2r ws_in=$ws_in ws_out=$ws_out hold=$hs_all start=$sp end=$ep"
} err] } {
  puts "E5 hook error: $err"
}
