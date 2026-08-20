// systolic_mm.v — weight-stationary systolic matrix-multiply array (NON-RISC held-out design).
// Mirrors the dataflow/arithmetic-dense class (finn / digit-rec / optical-flow) that our public-13
// gains came from, on a design the optimizer has NEVER seen. Fully registered/pipelined =>
// latency-deterministic (retiming-safe). Critical path = MAC (a*w + psum) between PE registers,
// so inter-PE register-to-register routing is the bottleneck => placement-improvable, the class
// where the generic free-replace / pblock-shrink flow should generalize.
//
// Synth: synth_design -top systolic_mm -generic N=16 -generic W=8  (xcvu3p, clk port `clk`).
// I/O for N=16,W=8,ACC=24: a_west 128 + w_north 128 + psum_south 384 + clk + w_load = 642 < 832 pins.

module pe #(parameter W=8, parameter ACC=24) (
    input  wire                  clk,
    input  wire                  w_load,
    input  wire signed [W-1:0]   a_in,
    input  wire signed [ACC-1:0] psum_in,
    input  wire signed [W-1:0]   w_in,
    output reg  signed [W-1:0]   a_out,
    output reg  signed [ACC-1:0] psum_out,
    output reg  signed [W-1:0]   w_out
);
    reg signed [W-1:0] weight;
    always @(posedge clk) begin
        if (w_load) begin
            weight <= w_in;
            w_out  <= weight;            // weights shift down each column during load
        end
        a_out    <= a_in;                // activations flow west -> east
        psum_out <= psum_in + a_in * weight;  // partial sums flow north -> south
    end
endmodule

module systolic_mm #(parameter N=24, parameter W=8, parameter ACC=24) (
    input  wire                   clk,
    input  wire                   w_load,
    input  wire signed [N*W-1:0]  a_west,      // activations entering the left column
    input  wire signed [N*W-1:0]  w_north,     // weights entering the top row (during load)
    output wire signed [ACC+5-1:0] result      // registered reduction of bottom-row partial sums
);
    wire signed [W-1:0]   a_h [0:N-1][0:N];   // horizontal activation links
    wire signed [ACC-1:0] p_v [0:N][0:N-1];   // vertical partial-sum links
    wire signed [W-1:0]   w_v [0:N][0:N-1];   // vertical weight-load links

    genvar r, c;
    generate
        for (r = 0; r < N; r = r + 1) begin : ROW_IN
            assign a_h[r][0] = a_west[r*W +: W];
        end
        for (c = 0; c < N; c = c + 1) begin : COL_IO
            assign p_v[0][c]   = {ACC{1'b0}};
            assign w_v[0][c]   = w_north[c*W +: W];
        end
    endgenerate

    // Registered reduction of the N bottom-row partial sums into one output word. The N inputs
    // come from PE registers spread across the device, so this gather is a long, placement-
    // sensitive path -- exactly the kind of routing a from-scratch re-place can shorten.
    integer k;
    reg signed [ACC+5-1:0] acc_sum;
    always @(posedge clk) begin
        acc_sum = {(ACC+5){1'b0}};
        for (k = 0; k < N; k = k + 1)
            acc_sum = acc_sum + $signed(p_v[N][k]);
    end
    assign result = acc_sum;

    generate
        for (r = 0; r < N; r = r + 1) begin : PR
            for (c = 0; c < N; c = c + 1) begin : PC
                pe #(.W(W), .ACC(ACC)) u_pe (
                    .clk(clk), .w_load(w_load),
                    .a_in(a_h[r][c]), .psum_in(p_v[r][c]), .w_in(w_v[r][c]),
                    .a_out(a_h[r][c+1]), .psum_out(p_v[r+1][c]), .w_out(w_v[r+1][c])
                );
            end
        end
    endgenerate
endmodule
