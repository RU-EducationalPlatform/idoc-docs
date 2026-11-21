module tb;
  logic clk = 0;
  logic [1:0] n = 0;
  always #1 clk = ~clk;
  always @(posedge clk) n <= n + 1;
  initial #20 $finish;
endmodule
