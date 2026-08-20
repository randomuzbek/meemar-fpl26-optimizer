// switchfab.v -- rotating NxN crossbar switch fabric (ROUTING-CONGESTED held-out design).
// Covers the interconnect/congestion-dominated class that NONE of our prior held-out designs hit
// (RISC cores = logic/pipeline-bound; systolic_mm = arithmetic dataflow). Here the bottleneck is
// NOT logic depth or pipeline balance -- it is wire routing: every input register fans out to every
// output mux (all-to-all), so the device routing fabric, not the LUTs, sets fmax. This is precisely
// the class where an aggressive from-scratch re-place into a dense pblock could BACKFIRE (raise
// congestion -> worse fmax), so it is the hardest stress test of the autosave/legality downside moat.
//
// I/O is kept tiny (seed in, one XOR-reduced word out) so a large fabric fits ffvc1517 pins, the same
// trick corearray.v / systolic_mm.v use. Inputs are driven by per-port LFSRs and a free-running phase
// counter rotates the crossbar permutation every cycle, so nothing constant-folds: the synthesizer
// must build a real N:1 wide mux per output and keep the whole fabric live.
//
// Synth: synth_design -top switchfab -generic N=32 -generic W=32  (xcvu3p, clk port `clk`).

module switchfab #(parameter N = 32, parameter W = 32) (
    input  wire           clk,
    input  wire           rst,
    input  wire [W-1:0]   seed,
    output wire [W-1:0]   result
);
    localparam SELW = $clog2(N);

    // Per-port input registers, each a distinct Galois LFSR so every port keeps toggling and the
    // fabric cannot be optimized away. Seeded distinctly off the primary `seed` input.
    reg [W-1:0] in_reg [0:N-1];

    // Free-running phase counter -> rotating crossbar permutation: out[o] reads in[(o+phase) mod N].
    reg [SELW-1:0] phase;

    // Output registers, each fed by an N:1 mux over all input registers (the congested all-to-all net).
    reg [W-1:0] out_reg [0:N-1];

    integer i;
    reg [W-1:0] lfsr_next;
    reg [SELW:0] sel;   // (o + phase) may need one extra bit before the mod-N fold

    always @(posedge clk) begin
        if (rst) begin
            phase <= {SELW{1'b0}};
            for (i = 0; i < N; i = i + 1)
                in_reg[i] <= seed ^ {W{1'b0}} ^ i[W-1:0] ^ 32'h9E3779B9;  // distinct nonzero seeds
        end else begin
            phase <= phase + 1'b1;
            // advance each port's LFSR (Galois, taps for a maximal-ish polynomial on low bits)
            for (i = 0; i < N; i = i + 1) begin
                lfsr_next = {in_reg[i][W-2:0], 1'b0} ^ (in_reg[i][W-1] ? 32'h04C11DB7 : 32'h0);
                in_reg[i] <= lfsr_next;
            end
        end
    end

    // The crossbar: each output selects one input via a variable index -> a true N:1 wide mux.
    // All N outputs reading all N inputs every cycle = the all-to-all congested routing pattern.
    genvar o;
    generate
        for (o = 0; o < N; o = o + 1) begin : XBAR
            always @(posedge clk) begin
                sel = o[SELW:0] + {1'b0, phase};
                if (sel >= N) sel = sel - N;          // rotation fold, keeps it a permutation
                out_reg[o] <= in_reg[sel[SELW-1:0]];
            end
        end
    endgenerate

    // Reduce all output registers to one word so the whole fabric drives a small I/O footprint.
    reg [W-1:0] xred;
    integer k;
    always @(*) begin
        xred = {W{1'b0}};
        for (k = 0; k < N; k = k + 1)
            xred = xred ^ out_reg[k];
    end
    assign result = xred;
endmodule
