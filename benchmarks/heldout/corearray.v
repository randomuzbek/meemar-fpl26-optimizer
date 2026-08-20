// Array of picorv32 cores wired in a ring with a registered XOR reduction.
// Keeps all cores live (no pruning) and creates real inter-core timing paths.
module corearray #(parameter N=24) (
    input  wire        clk,
    input  wire        resetn,
    input  wire [31:0] feed_in,
    output reg  [31:0] result
);
    reg  [31:0] ring [0:N-1];
    wire [31:0] coreout [0:N-1];
    genvar i;
    generate
      for (i=0; i<N; i=i+1) begin : g
        wire [31:0] maddr, mwdata, eoi_w;
        wire        mvalid, trap_w;
        picorv32 #(
          .ENABLE_MUL(1), .ENABLE_DIV(1), .BARREL_SHIFTER(1),
          .ENABLE_IRQ(1), .COMPRESSED_ISA(1)
        ) u (
          .clk(clk), .resetn(resetn),
          .trap(trap_w),
          .mem_valid(mvalid),
          .mem_ready(1'b1),
          .mem_addr(maddr),
          .mem_wdata(mwdata),
          .mem_rdata(ring[(i+1)%N] ^ feed_in),
          .pcpi_wr(1'b0), .pcpi_rd(32'b0), .pcpi_wait(1'b0), .pcpi_ready(1'b0),
          .irq(ring[(i+N-1)%N]),
          .eoi(eoi_w)
        );
        assign coreout[i] = maddr ^ mwdata ^ eoi_w ^ {31'b0, trap_w};
      end
    endgenerate
    integer k;
    always @(posedge clk) begin
      for (k=0; k<N; k=k+1) ring[k] <= coreout[k];
    end
    reg [31:0] acc;
    always @(*) begin
      acc = 32'b0;
      for (k=0; k<N; k=k+1) acc = acc ^ ring[k];
    end
    always @(posedge clk) result <= acc;
endmodule
