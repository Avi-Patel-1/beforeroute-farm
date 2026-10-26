`timescale 1ns/10ps
module testbench;
  reg clk = 0;
  reg rst = 0;
  reg ld = 0;
  reg [127:0] key = 0;
  reg [127:0] text_in = 0;
  wire done;
  wire [127:0] text_out;
  integer passed = 0;
  always #5 clk = ~clk;

  aes_cipher_top dut(.clk(clk), .rst(rst), .ld(ld), .done(done),
                     .key(key), .text_in(text_in), .text_out(text_out));

  task check_block;
    input [127:0] plaintext;
    input [127:0] expected;
    integer cycles;
    begin
      // The upstream core has a synchronous active-low counter reset. Loading
      // key and plaintext initializes the datapath for this bounded example.
      @(negedge clk); rst = 0; ld = 0;
      repeat (3) @(negedge clk);
      rst = 1;
      key = 128'h2b7e151628aed2a6abf7158809cf4f3c;
      text_in = plaintext;
      ld = 1;
      @(negedge clk); ld = 0;
      cycles = 0;
      while (cycles < 24 && done !== 1'b1) begin
        @(posedge clk); #2;
        cycles = cycles + 1;
      end
      if (done !== 1'b1 || text_out !== expected) begin
        $display("AES_VECTOR_FAIL index=%0d cycles=%0d done=%b actual=%032x expected=%032x",
                 passed, cycles, done, text_out, expected);
        $fatal(1, "Known-answer vector failed");
      end
      $display("AES_VECTOR_PASS index=%0d cycles=%0d ciphertext=%032x", passed, cycles, text_out);
      passed = passed + 1;
    end
  endtask

  initial begin
    // Four independent AES-128 encryption blocks from NIST AES_Core128.pdf.
    check_block(128'h6bc1bee22e409f96e93d7e117393172a, 128'h3ad77bb40d7a3660a89ecaf32466ef97);
    check_block(128'hae2d8a571e03ac9c9eb76fac45af8e51, 128'hf5d3d58503b9699de785895a96fdbaaf);
    check_block(128'h30c81c46a35ce411e5fbc1191a0a52ef, 128'h43b1cd7f598ece23881b00e3ed030688);
    check_block(128'hf69f2445df4f9b17ad2b417be66c3710, 128'h7b0c785e27e8ad3f8223207104725dd4);
    $display("AES_SMOKE_PASS vectors=%0d", passed);
    $finish;
  end

  initial begin
    #10000;
    $fatal(1, "Simulation wall-clock guard");
  end
endmodule
