# heldout/h1h2_vivado_probe.tcl
# Lean Vivado-ONLY probe for the beta-endgame guards (no pipeline/MCP/RapidWright, so it
# runs on a bare Vivado instance). Reproduces the pipeline's EXACT derived-box math
# (dcp_optimizer.py _derive_pblock_range) + application (_deterministic_pblock_shrink) to
# answer the two empirical questions the unit tests can't:
#   H1: for the pipeline's best-of-K densities, does confining a SLICEM-heavy design to the
#       generic (SLICEM-blind) box make place_design THROW? A forfeit needs EVERY candidate
#       to throw; if any succeeds the pipeline banks it (guard is then inert but harmless).
#   H2: does phys_opt_design DECREASE the primitive cell count? (the #36 gate trigger)
# args: <src.v> <top> <period_ns> <NB>
set src    [lindex $argv 0]
set top    [lindex $argv 1]
set period [lindex $argv 2]
set nb     [lindex $argv 3]

read_verilog -sv $src
synth_design -top $top -part xcvu3p-ffvc1517-2-e -generic NB=$nb
create_clock -name clk_fpl26contest -period $period [get_ports clk]
opt_design

set n_prim   [llength [get_cells -hier -filter {IS_PRIMITIVE}]]
set n_slicem [llength [get_cells -hier -filter {IS_PRIMITIVE && (REF_NAME =~ RAMD* || REF_NAME =~ RAMS* || REF_NAME =~ SRL*)}]]
puts "PROBE_CELLS prim=$n_prim slicem=$n_slicem ratio=[expr {$n_prim>0?double($n_slicem)/$n_prim:0}]"

# ---- Initial free placement (establishes IS_USED utilisation for box derivation; also the
#      free/unboxed fallback the H1 guard defers to) ----
if {[catch {place_design} perr]} {
    puts "PROBE_FREE free place_design THREW: $perr"
} else {
    puts "PROBE_FREE free place_design OK nused_slice=[llength [get_sites -filter {SITE_TYPE=~SLICE* && IS_USED}]]"
}

# ---- Device geometry (fixed) for the box derivation ----
set xs {}; set ys {}
foreach s [get_sites -filter {SITE_TYPE=~SLICE*}] { if {[regexp {X(\d+)Y(\d+)} [get_property NAME $s] -> x y]} { lappend xs $x; lappend ys $y } }
set xmax [lindex [lsort -integer $xs] end]; set ymax [lindex [lsort -integer $ys] end]
set crx {}; set cry {}
foreach cr [get_clock_regions] { if {[regexp {X(\d+)Y(\d+)} [get_property NAME $cr] -> a c]} { lappend crx $a; lappend cry $c } }
set ncol [expr {[lindex [lsort -integer $crx] end]+1}]; set nrow [expr {[lindex [lsort -integer $cry] end]+1}]
set crw [expr {int(ceil(($xmax+1.0)/$ncol))}]; set crh [expr {int(ceil(($ymax+1.0)/$nrow))}]
set nused [llength [get_sites -filter {SITE_TYPE=~SLICE* && IS_USED}]]

proc derive_box {density nused ncol nrow crw crh xmax ymax} {
    set needed [expr {int(ceil($nused/$density))}]
    set crcols [expr {int(ceil(double($needed)/($nrow*$crh*$crw)))}]; if {$crcols<1} {set crcols 1}; if {$crcols>$ncol} {set crcols $ncol}
    set crrows [expr {int(ceil(double($needed)/($crcols*$crw)/$crh))}]; if {$crrows<1} {set crrows 1}; if {$crrows>$nrow} {set crrows $nrow}
    set c0 [expr {($ncol-$crcols)/2}]; set r0 [expr {($nrow-$crrows+1)/2}]
    set x0 [expr {$c0*$crw}]; set x1 [expr {($c0+$crcols)*$crw-1}]
    set y0 [expr {$r0*$crh}]; set y1 [expr {($r0+$crrows)*$crh-1}]
    if {$x1>$xmax} {set x1 $xmax}; if {$y1>$ymax} {set y1 $ymax}
    return "SLICE_X${x0}Y${y0}:SLICE_X${x1}Y${y1}"
}

# ---- H1 best-of-K: the pipeline's 3 densities, each on the CLEAN netlist (place/unplace
#      don't mutate cells; phys_opt runs only afterwards for H2) ----
foreach density {0.42 0.50 0.58} {
    set prange [derive_box $density $nused $ncol $nrow $crw $crh $xmax $ymax]
    place_design -unplace
    if {[llength [get_pblocks -quiet]]} { delete_pblocks [get_pblocks] }
    create_pblock pb_meemar
    resize_pblock pb_meemar -add $prange
    set box_slicem [llength [get_sites -quiet -of_objects [get_pblocks pb_meemar] -filter {SITE_TYPE==SLICEM}]]
    puts "PROBE_BOX density=$density range=$prange box_slicem=$box_slicem slicem_demand=$n_slicem oversub=[expr {$box_slicem>0?double($n_slicem)/$box_slicem:999}]"
    add_cells_to_pblock pb_meemar [get_cells -hier -filter {IS_PRIMITIVE}] -clear_locs
    if {[catch {place_design} err]} {
        puts "PROBE_H1 density=$density BOXED place_design THREW: [string range $err 0 200]"
    } else {
        puts "PROBE_H1 density=$density BOXED place_design SUCCEEDED (no throw)"
    }
}

# ---- H2: does phys_opt_design DECREASE primitive cell count? (fresh clean placement first) ----
place_design -unplace
if {[llength [get_pblocks -quiet]]} { delete_pblocks [get_pblocks] }
if {[catch {place_design} fp2]} { puts "PROBE_H2 pre-place THREW: $fp2" }
set n_before [llength [get_cells -hier -filter {IS_PRIMITIVE}]]
if {[catch {phys_opt_design} oerr]} {
    puts "PROBE_H2 phys_opt_design THREW: $oerr"
} else {
    set n_after [llength [get_cells -hier -filter {IS_PRIMITIVE}]]
    puts "PROBE_H2 physopt prim before=$n_before after=$n_after delta=[expr {$n_after-$n_before}] pct=[expr {$n_before>0?100.0*($n_after-$n_before)/$n_before:0}]"
}
puts "PROBE_DONE"
