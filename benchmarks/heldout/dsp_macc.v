// dsp_macc.v -- DSP48 + BRAM hard-macro held-out design (the finn / digit-rec / optical-flow class).
// Every prior held-out (PicoRV32, VexRiscv, systolic 8-bit MACs, crossbar) is LUT/FF-only. But our
// largest PUBLIC-13 gains come from DSP/BRAM-heavy arithmetic designs, whose placement regime is
// fundamentally different: DSP48 and block-RAM are HARD MACROS locked to fixed device columns, so
// they cannot be moved freely the way LUTs/FFs can. This tests whether the generic flow (pblock-shrink
// / pblock-free re-place / phys_opt) generalizes when the critical resources are column-locked macros.
//
// M independent FIR-style MAC lanes; each owns a block-RAM delay line + a block-RAM coefficient ROM
// and a DSP48 multiply-accumulate. A global write pointer streams `din` into every lane's RAM (lane-
// scrambled so nothing const-folds); a rotating read address keeps all DSPs busy every cycle. The M
// accumulators reduce to one output word so the macro-heavy core drives a tiny I/O footprint.
//
// Synth: synth_design -top dsp_macc -generic M=64 -generic DEPTH=1024  (xcvu3p, clk port `clk`).

module dsp_macc #(
    parameter M     = 64,     // MAC lanes  -> M DSP48 + 2*M BRAM
    parameter DEPTH = 1024,   // delay-line / coeff depth per lane (1024*18b ~= one 18K BRAM)
    parameter DW    = 18,     // sample width (fits DSP48 A port)
    parameter CW    = 18,     // coefficient width (fits DSP48 B port)
    parameter ACC   = 48      // accumulator width (DSP48 P)
) (
    input  wire                 clk,
    input  wire                 rst,
    input  wire signed [DW-1:0] din,
    output wire signed [ACC-1:0] result
);
    localparam AW = $clog2(DEPTH);

    reg [AW-1:0] wptr;
    reg [AW-1:0] phase;       // rotates read address so every lane keeps streaming
    always @(posedge clk) begin
        if (rst) begin wptr <= {AW{1'b0}}; phase <= {AW{1'b0}}; end
        else     begin wptr <= wptr + 1'b1; phase <= phase + 3; end
    end

    wire signed [ACC-1:0] lane_out [0:M-1];

    genvar l;
    generate
        for (l = 0; l < M; l = l + 1) begin : LANE
            (* ram_style = "block" *) reg signed [DW-1:0] dmem [0:DEPTH-1];
            (* ram_style = "block" *) reg signed [CW-1:0] cmem [0:DEPTH-1];
            integer j;
            initial begin
                // coefficient ROM: distinct nonzero pattern per lane so the MACs differ and stay live
                for (j = 0; j < DEPTH; j = j + 1)
                    cmem[j] = $signed((j * (l + 1) + 7) & ((1 << CW) - 1)) - (1 << (CW - 1));
            end

            reg [AW-1:0]        raddr;
            reg signed [DW-1:0] dq;
            reg signed [CW-1:0] cq;
            (* use_dsp = "yes" *) reg signed [ACC-1:0] acc;

            always @(posedge clk) begin
                dmem[wptr] <= din + l[DW-1:0];                 // lane-scrambled write
                raddr      <= phase + (l * 17);                 // lane-skewed rotating read
                dq         <= dmem[raddr];
                cq         <= cmem[raddr];
                if (rst) acc <= {ACC{1'b0}};
                else     acc <= acc + dq * cq;                  // DSP48 multiply-accumulate
            end
            assign lane_out[l] = acc;
        end
    endgenerate

    // Reduce all lane accumulators to one output word (registered) -> small I/O.
    integer k;
    reg signed [ACC-1:0] red;
    always @(posedge clk) begin
        red = {ACC{1'b0}};
        for (k = 0; k < M; k = k + 1)
            red = red ^ lane_out[k];
    end
    assign result = red;
endmodule
