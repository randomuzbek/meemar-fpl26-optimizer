# Bound the placement headroom on the DSP/BRAM held-out: try several strategies from the
# baseline synthesized DCP, route each, report routed fmax. Reference = flow best 370.64 MHz.
set base /home/heldout/heldout_dsp_macc.dcp
proc fmaxof {} {
  set tp [get_timing_paths -max_paths 1 -setup -to [get_clocks clk_fpl26contest]]
  set wns [get_property SLACK $tp]
  set per [get_property PERIOD [get_clocks clk_fpl26contest]]
  return [format "%.2f (WNS %.3f)" [expr {1000.0/($per-$wns)}] $wns]
}
foreach {tag dir} {A Explore B ExtraTimingOpt C AltSpreadLogic_high D SSI_SpreadLogic_high E WLDrivenBlockPlacement} {
  open_checkpoint $base
  if {[catch {place_design -directive $dir} e]} { puts "RESrun $tag: place FAIL $e"; close_design; continue }
  phys_opt_design -directive Explore
  route_design -directive Explore -tns_cleanup
  puts "RESrun $tag ($dir): [fmaxof]"
  close_design
}
