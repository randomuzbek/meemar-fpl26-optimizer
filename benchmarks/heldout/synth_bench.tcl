# args: file1[,file2,...] top period_ns out.dcp clkport [generics]
set files   [lindex $argv 0]
set top     [lindex $argv 1]
set period  [lindex $argv 2]
set out     [lindex $argv 3]
set clkport [lindex $argv 4]
set generics ""
if {[llength $argv] > 5} { set generics [lindex $argv 5] }
foreach f [split $files ","] { read_verilog -sv $f }
if {$generics ne ""} {
    set gargs {}
    foreach g [split $generics " "] { lappend gargs -generic $g }
    synth_design -top $top -part xcvu3p-ffvc1517-2-e {*}$gargs
} else {
    synth_design -top $top -part xcvu3p-ffvc1517-2-e
}
create_clock -name clk_fpl26contest -period $period [get_ports $clkport]
opt_design
place_design
phys_opt_design
route_design
set tp [get_timing_paths -max_paths 1 -setup -to [get_clocks clk_fpl26contest]]
set wns [get_property SLACK $tp]
set per [get_property PERIOD [get_clocks clk_fpl26contest]]
puts "RESULT_WNS $wns PERIOD $per FMAX [expr {1000.0/($per-$wns)}]"
puts "RESULT_CELLS [llength [get_cells -hier -filter {IS_PRIMITIVE}]]"
report_design_analysis -timing
write_checkpoint -force $out
puts "WROTE $out"
