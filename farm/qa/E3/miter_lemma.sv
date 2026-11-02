// Addendum 40 / E3 decomposed proof, part D1 (combinational lemma): in ANY state where the property and every helper
// invariant of miter_inv2.sv hold, the rewrite's aux (pre + F) equals the original's aux31 (ar + F + M[g] + K).
// Run as a one-step check from an unconstrained state (no reset assumption). The two designs are the unmodified source files; the Yosys script
// renames the original module to md5_orig and exposes the listed internal registers as extra output ports (`expose`),
// which changes no logic. Only assumption: reset is asserted (low) in the first cycle. The property is that data_o and
// ready_o are equal in every later cycle. The other assertions are helper invariants (a strengthening that makes the
// property inductive); they are proven together with the property, so a wrong one can only make the proof fail.
module miter(input clk, input reset, input load_i, input newtext_i, input [127:0] data_i);
  wire [127:0] o_data_o, c_data_o;
  wire         o_ready_o, c_ready_o;
  wire [511:0] o_message, c_message;
  wire [31:0]  o_ar, o_br, o_cr, o_dr, o_A, o_B, o_C, o_D;
  wire [31:0]  c_ar, c_br, c_cr, c_dr, c_A, c_B, c_C, c_D;
  wire [2:0]   o_gs, c_gs, o_round;
  wire         o_gh, c_gh;
  wire [5:0]   o_r64, c_r64;
  wire [31:0]  c_pre, c_fc0, c_fc1;
  wire [15:0]  c_iq;
  wire [3:0]   o_nblock;
  wire [31:0]  o_tr;
  wire [31:0]  o_aux31, c_aux;

  md5_orig o(.clk(clk), .reset(reset), .load_i(load_i), .newtext_i(newtext_i), .data_i(data_i),
             .ready_o(o_ready_o), .data_o(o_data_o),
             .message(o_message), .ar(o_ar), .br(o_br), .cr(o_cr), .dr(o_dr), .A(o_A), .B(o_B), .C(o_C), .D(o_D),
             .getdata_state(o_gs), .generate_hash(o_gh), .round64(o_r64), .round(o_round),
             .nblock(o_nblock), .tr_var(o_tr), .aux31(o_aux31));
  md5      c(.clk(clk), .reset(reset), .load_i(load_i), .newtext_i(newtext_i), .data_i(data_i),
             .ready_o(c_ready_o), .data_o(c_data_o),
             .message(c_message), .ar(c_ar), .br(c_br), .cr(c_cr), .dr(c_dr), .A(c_A), .B(c_B), .C(c_C), .D(c_D),
             .getdata_state(c_gs), .generate_hash(c_gh), .round64(c_r64), .pre(c_pre), .iq(c_iq), .fc0(c_fc0), .fc1(c_fc1), .aux(c_aux));


  // MD5 reference (RFC 1321): step constant K[i] = floor(2^32 |sin(i+1)|), message word index g(i), round function.
  function [31:0] K;
    input [5:0] i;
    case (i)
       0: K = 32'hd76aa478;
       1: K = 32'he8c7b756;
       2: K = 32'h242070db;
       3: K = 32'hc1bdceee;
       4: K = 32'hf57c0faf;
       5: K = 32'h4787c62a;
       6: K = 32'ha8304613;
       7: K = 32'hfd469501;
       8: K = 32'h698098d8;
       9: K = 32'h8b44f7af;
      10: K = 32'hffff5bb1;
      11: K = 32'h895cd7be;
      12: K = 32'h6b901122;
      13: K = 32'hfd987193;
      14: K = 32'ha679438e;
      15: K = 32'h49b40821;
      16: K = 32'hf61e2562;
      17: K = 32'hc040b340;
      18: K = 32'h265e5a51;
      19: K = 32'he9b6c7aa;
      20: K = 32'hd62f105d;
      21: K = 32'h02441453;
      22: K = 32'hd8a1e681;
      23: K = 32'he7d3fbc8;
      24: K = 32'h21e1cde6;
      25: K = 32'hc33707d6;
      26: K = 32'hf4d50d87;
      27: K = 32'h455a14ed;
      28: K = 32'ha9e3e905;
      29: K = 32'hfcefa3f8;
      30: K = 32'h676f02d9;
      31: K = 32'h8d2a4c8a;
      32: K = 32'hfffa3942;
      33: K = 32'h8771f681;
      34: K = 32'h6d9d6122;
      35: K = 32'hfde5380c;
      36: K = 32'ha4beea44;
      37: K = 32'h4bdecfa9;
      38: K = 32'hf6bb4b60;
      39: K = 32'hbebfbc70;
      40: K = 32'h289b7ec6;
      41: K = 32'heaa127fa;
      42: K = 32'hd4ef3085;
      43: K = 32'h04881d05;
      44: K = 32'hd9d4d039;
      45: K = 32'he6db99e5;
      46: K = 32'h1fa27cf8;
      47: K = 32'hc4ac5665;
      48: K = 32'hf4292244;
      49: K = 32'h432aff97;
      50: K = 32'hab9423a7;
      51: K = 32'hfc93a039;
      52: K = 32'h655b59c3;
      53: K = 32'h8f0ccc92;
      54: K = 32'hffeff47d;
      55: K = 32'h85845dd1;
      56: K = 32'h6fa87e4f;
      57: K = 32'hfe2ce6e0;
      58: K = 32'ha3014314;
      59: K = 32'h4e0811a1;
      60: K = 32'hf7537e82;
      61: K = 32'hbd3af235;
      62: K = 32'h2ad7d2bb;
      63: K = 32'heb86d391;
    endcase
  endfunction
  function [3:0] G;
    input [5:0] i;
    case (i[5:4])
      2'd0: G = i[3:0];
      2'd1: G = i[3:0] * 4'd5 + 4'd1;
      2'd2: G = i[3:0] * 4'd3 + 4'd5;
      2'd3: G = i[3:0] * 4'd7;
    endcase
  endfunction
  function [31:0] W;            // message word g of the 512-bit block register (word 0 = bits 511:480)
    input [511:0] m;
    input [3:0] g;
    case (g)
      4'd0: W = m[511:480];
      4'd1: W = m[479:448];
      4'd2: W = m[447:416];
      4'd3: W = m[415:384];
      4'd4: W = m[383:352];
      4'd5: W = m[351:320];
      4'd6: W = m[319:288];
      4'd7: W = m[287:256];
      4'd8: W = m[255:224];
      4'd9: W = m[223:192];
      4'd10: W = m[191:160];
      4'd11: W = m[159:128];
      4'd12: W = m[127:96];
      4'd13: W = m[95:64];
      4'd14: W = m[63:32];
      4'd15: W = m[31:0];
    endcase
  endfunction
  function [31:0] FN;
    input [1:0] r;
    input [31:0] b, c, d;
    case (r)
      2'd0: FN = (b & c) | (~b & d);
      2'd1: FN = (b & d) | (c & ~d);
      2'd2: FN = b ^ c ^ d;
      2'd3: FN = c ^ (b | ~d);
    endcase
  endfunction

  always @(*) begin
    begin
      // ---- the property: identical outputs in every cycle after the first
      assume (o_data_o == c_data_o);
      assume (o_ready_o == c_ready_o);
      // ---- helper invariants
      assume (c_message == o_message);
      assume (c_ar == o_ar);
      assume (c_br == o_br);
      assume (c_cr == o_cr);
      assume (c_dr == o_dr);
      assume (c_A == o_A);
      assume (c_B == o_B);
      assume (c_C == o_C);
      assume (c_D == o_D);
      assume (c_gs == o_gs);
      assume (c_gh == o_gh);
      assume (c_r64 == o_r64);
      assume (o_round == {1'b0, o_r64[5:4]});
      assume (o_nblock == G(o_r64));
      assume (o_tr == K(o_r64));
      assume (c_pre == o_ar + W(o_message, o_nblock) + o_tr);
      assume (c_iq == (16'd1 << G(o_r64 + 6'd1)));
      assume (c_fc1 == FN(o_r64[5:4], 32'hffffffff, o_cr, o_dr));
      assume (c_fc0 == FN(o_r64[5:4], 32'h00000000, o_cr, o_dr));
    end
    assert (c_aux == o_aux31);
  end
endmodule
