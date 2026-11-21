module top;
  logic [3:0] q = 0;
  initial begin
    repeat (5) q = q + 1;
    $display("%0d", q);
  end
endmodule
