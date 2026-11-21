// A 4-bit counter and its testbench, invented for this demo.
module counter(input logic clk, rst, output logic [3:0] q);
  always_ff @(posedge clk) q <= rst ? 4'd0 : q + 4'd1;
endmodule
module tb;
  logic clk = 0, rst = 1; logic [3:0] q;
  counter dut(.clk(clk), .rst(rst), .q(q));
  always #5 clk = ~clk;
  initial begin #12 rst = 0; #200 $finish; end
endmodule
