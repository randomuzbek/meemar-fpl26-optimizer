// heldout/lutram_bank.v
// LUTRAM/SLICEM stress design for the FPL'26 held-out corpus. Dominated by
// distributed-RAM banks (RAMD*/RAMS* -> SLICEM only) and SRL shift chains
// (SRLC32E -> SLICEM only): the one archetype the pblock-shrink box (generic
// SLICE geometry, SLICEM-blind) has never been stress-tested against.
// Build (see heldout/README.md), period below achievable delay -> negative WNS:
//   vivado -mode batch -source synth_bench.tcl -tclargs \
//     lutram_bank.v lutram_bank <period_ns> out.dcp clk "NB=<n>"
module lutram_bank #(
    parameter NB   = 48,   // number of distributed-RAM banks (scales cell count)
    parameter AW   = 6,    // addr width -> depth 64 (RAMD64E), async read
    parameter DW   = 32,   // data width per bank
    parameter SRLW = 32    // SRL shift-chain length (SRLC32E)
) (
    input  wire          clk,
    input  wire          we,
    input  wire [AW-1:0] waddr,
    input  wire [AW-1:0] raddr,
    input  wire [DW-1:0] din,
    output reg  [DW-1:0] dout
);
    wire [DW-1:0] bank_q [0:NB-1];
    wire [DW-1:0] srl_q  [0:NB-1];
    genvar b;
    generate
      for (b = 0; b < NB; b = b + 1) begin : gbank
        // Distributed RAM bank -> RAMD64E/RAMS (SLICEM only).
        (* ram_style = "distributed" *) reg [DW-1:0] mem [0:(1<<AW)-1];
        wire [DW-1:0] wd = din ^ (din << (b % DW)) ^ b;   // per-bank rotate: no dedup
        always @(posedge clk) if (we) mem[waddr] <= wd;
        assign bank_q[b] = mem[raddr];
        // SRL shift chain -> SRLC32E (SLICEM only).
        (* srl_style = "srl" *) reg [SRLW-1:0] sh;
        always @(posedge clk) sh <= {sh[SRLW-2:0], bank_q[b][0]};
        assign srl_q[b] = {DW{sh[SRLW-1]}} ^ bank_q[b];
      end
    endgenerate
    // Registered XOR reduction of all outputs -> real timing paths.
    integer k;
    reg [DW-1:0] acc;
    always @(*) begin
      acc = {DW{1'b0}};
      for (k = 0; k < NB; k = k + 1) acc = acc ^ srl_q[k];
    end
    always @(posedge clk) dout <= acc;
endmodule
