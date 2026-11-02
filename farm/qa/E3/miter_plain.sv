// Addendum 40 / E3 miter without helper invariants (output equality only), for an unassisted PDR attempt.
module miter(input clk, input reset, input load_i, input newtext_i, input [127:0] data_i);
  wire [127:0] o_data_o, c_data_o;
  wire         o_ready_o, c_ready_o;
  md5_orig o(.clk(clk), .reset(reset), .load_i(load_i), .newtext_i(newtext_i), .data_i(data_i),
             .ready_o(o_ready_o), .data_o(o_data_o));
  md5      c(.clk(clk), .reset(reset), .load_i(load_i), .newtext_i(newtext_i), .data_i(data_i),
             .ready_o(c_ready_o), .data_o(c_data_o));
  reg init = 1'b1;
  always @(posedge clk) init <= 1'b0;
  always @(*) begin
    if (init) assume (!reset);
    if (!init) begin
      assert (o_data_o == c_data_o);
      assert (o_ready_o == c_ready_o);
    end
  end
endmodule
