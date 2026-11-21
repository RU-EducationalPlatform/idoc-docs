module tb;
  logic a, b, y;
  and2 dut(.a(a), .b(b), .y(y));
  initial begin
    a = 0; b = 0; #1 assert (y == 0);
    a = 1; b = 0; #1 assert (y == 0);
    a = 1; b = 1; #1 assert (y == 1);
    $display("PASS");
  end
endmodule
