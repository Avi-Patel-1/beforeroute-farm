//////////////////////////////////////////////////////////////////////
////                                                              ////
////  MD5 implementation                                          ////
////                                                              ////
////  This file is part of the SystemC MD5                        ////
////                                                              ////
////  Description:                                                ////
////  MD5 implementation                                          ////
////                                                              ////
////  To Do:                                                      ////
////   - done                                                     ////
////                                                              ////
////  Author(s):                                                  ////
////      - Javier Castillo, jcastilo@opencores.org               ////
////                                                              ////
//////////////////////////////////////////////////////////////////////
////                                                              ////
//// Copyright (C) 2000 Authors and OPENCORES.ORG                 ////
////                                                              ////
//// This source file may be used and distributed without         ////
//// restriction provided that this copyright statement is not    ////
//// removed from the file and that any derivative work contains  ////
//// the original copyright notice and the associated disclaimer. ////
////                                                              ////
//// This source file is free software; you can redistribute it   ////
//// and/or modify it under the terms of the GNU Lesser General   ////
//// Public License as published by the Free Software Foundation; ////
//// either version 2.1 of the License, or (at your option) any   ////
//// later version.                                               ////
////                                                              ////
//// This source is distributed in the hope that it will be       ////
//// useful, but WITHOUT ANY WARRANTY; without even the implied   ////
//// warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR      ////
//// PURPOSE.  See the GNU Lesser General Public License for more ////
//// details.                                                     ////
////                                                              ////
//// You should have received a copy of the GNU Lesser General    ////
//// Public License along with this source; if not, download it   ////
//// from http://www.opencores.org/lgpl.shtml                     ////
////                                                              ////
//////////////////////////////////////////////////////////////////////
//
// Timing-restructured version, cycle-exact with the original.

`timescale 10ns/1ns

module md5(clk,reset,load_i,ready_o,newtext_i,data_i,data_o);

input clk;
input reset;
input load_i;
output ready_o;
input newtext_i;
//Input must be padded and in little endian mode
input [127:0] data_i;
output [127:0] data_o;

reg ready_o;
reg [127:0] data_o;

localparam [31:0] KA = 32'h67452301, KB = 32'hEFCDAB89,
                  KC = 32'h98BADCFE, KD = 32'h10325476;

reg [5:0]   round64;
reg [31:0]  ar, br, cr, dr, A, B, C, D;
reg [511:0] message;
reg [2:0]   getdata_state;
reg         generate_hash;
// added state (original "round" always equals round64[5:4])
reg [31:0]  pre;       // == ar + message_var[nblock(round64)] + T(round64)
reg [15:0]  iq;        // == one-hot nblock(round64+1)
reg [31:0]  fc0, fc1;  // == F with b=0 / b=1 for the current cr, dr, round

// T constant of the NEXT step: tnf(k) = T((k+1) mod 64)
function [31:0] tnf;
input [5:0] k;
case (k)
  0: tnf=32'hE8C7B756;  1: tnf=32'h242070DB;  2: tnf=32'hC1BDCEEE;  3: tnf=32'hF57C0FAF;
  4: tnf=32'h4787C62A;  5: tnf=32'hA8304613;  6: tnf=32'hFD469501;  7: tnf=32'h698098D8;
  8: tnf=32'h8B44F7AF;  9: tnf=32'hFFFF5BB1; 10: tnf=32'h895CD7BE; 11: tnf=32'h6B901122;
 12: tnf=32'hFD987193; 13: tnf=32'hA679438E; 14: tnf=32'h49B40821; 15: tnf=32'hF61E2562;
 16: tnf=32'hC040B340; 17: tnf=32'h265E5A51; 18: tnf=32'hE9B6C7AA; 19: tnf=32'hD62F105D;
 20: tnf=32'h02441453; 21: tnf=32'hD8A1E681; 22: tnf=32'hE7D3FBC8; 23: tnf=32'h21E1CDE6;
 24: tnf=32'hC33707D6; 25: tnf=32'hF4D50D87; 26: tnf=32'h455A14ED; 27: tnf=32'hA9E3E905;
 28: tnf=32'hFCEFA3F8; 29: tnf=32'h676F02D9; 30: tnf=32'h8D2A4C8A; 31: tnf=32'hFFFA3942;
 32: tnf=32'h8771F681; 33: tnf=32'h6D9D6122; 34: tnf=32'hFDE5380C; 35: tnf=32'hA4BEEA44;
 36: tnf=32'h4BDECFA9; 37: tnf=32'hF6BB4B60; 38: tnf=32'hBEBFBC70; 39: tnf=32'h289B7EC6;
 40: tnf=32'hEAA127FA; 41: tnf=32'hD4EF3085; 42: tnf=32'h04881D05; 43: tnf=32'hD9D4D039;
 44: tnf=32'hE6DB99E5; 45: tnf=32'h1FA27CF8; 46: tnf=32'hC4AC5665; 47: tnf=32'hF4292244;
 48: tnf=32'h432AFF97; 49: tnf=32'hAB9423A7; 50: tnf=32'hFC93A039; 51: tnf=32'h655B59C3;
 52: tnf=32'h8F0CCC92; 53: tnf=32'hFFEFF47D; 54: tnf=32'h85845DD1; 55: tnf=32'h6FA87E4F;
 56: tnf=32'hFE2CE6E0; 57: tnf=32'hA3014314; 58: tnf=32'h4E0811A1; 59: tnf=32'hF7537E82;
 60: tnf=32'hBD3AF235; 61: tnf=32'h2AD7D2BB; 62: tnf=32'hEB86D391; default: tnf=32'hD76AA478;
endcase
endfunction

// message word index (nblock)
function [3:0] nbf;
input [5:0] k;
case (k[5:4])
  2'd0:    nbf = k[3:0];
  2'd1:    nbf = k[3:0]*4'd5 + 4'd1;
  2'd2:    nbf = k[3:0]*4'd3 + 4'd5;
  default: nbf = k[3:0]*4'd7;
endcase
endfunction

// rotate left by s(round, round64[1:0])
function [31:0] rotf;
input [31:0] x;
input [3:0] k;
case (k)
  4'd0:  rotf = {x[24:0],x[31:25]};  // 7
  4'd1:  rotf = {x[19:0],x[31:20]};  // 12
  4'd2:  rotf = {x[14:0],x[31:15]};  // 17
  4'd3:  rotf = {x[9:0], x[31:10]};  // 22
  4'd4:  rotf = {x[26:0],x[31:27]};  // 5
  4'd5:  rotf = {x[22:0],x[31:23]};  // 9
  4'd6:  rotf = {x[17:0],x[31:18]};  // 14
  4'd7:  rotf = {x[11:0],x[31:12]};  // 20
  4'd8:  rotf = {x[27:0],x[31:28]};  // 4
  4'd9:  rotf = {x[20:0],x[31:21]};  // 11
  4'd10: rotf = {x[15:0],x[31:16]};  // 16
  4'd11: rotf = {x[8:0], x[31:9]};   // 23
  4'd12: rotf = {x[25:0],x[31:26]};  // 6
  4'd13: rotf = {x[21:0],x[31:22]};  // 10
  4'd14: rotf = {x[16:0],x[31:17]};  // 15
  default: rotf = {x[10:0],x[31:11]}; // 21
endcase
endfunction

// F written as a mux on b: {F(b=1), F(b=0)} from c, d and round
function [63:0] fsplit;
input [31:0] c, d;
input [1:0]  g;
case (g)
  2'd0:    fsplit = {c, d};
  2'd1:    fsplit = {c | d, c & ~d};
  2'd2:    fsplit = {~(c ^ d), c ^ d};
  default: fsplit = {~c, ~(c ^ d)};
endcase
endfunction

// 32-bit Kogge-Stone adder (OR-transmit prefix)
function [31:0] ksa;
input [31:0] x, y;
reg [31:0] g, p, h;
integer i, j;
begin
  h = x ^ y;
  g = x & y;
  p = x | y;
  for (j = 1; j < 32; j = j + j)
    for (i = 31; i >= j; i = i - 1) begin
      g[i] = g[i] | (p[i] & g[i-j]);
      p[i] = p[i] & p[i-j];
    end
  ksa = h ^ {g[30:0], 1'b0};
end
endfunction

// ---------------- step datapath ----------------
wire [31:0] fr  = (br & fc1) | (~br & fc0);   // F(br, cr, dr) of the current round
wire [31:0] aux = ksa(pre, fr);
wire [31:0] rot = rotf(aux, {round64[5:4], round64[1:0]});
wire [31:0] fo  = ksa(br, rot);    // func_out
wire [31:0] brB = ksa(br, B);      // br + B, ready before rot
wire [31:0] bt  = ksa(brB, rot);   // B_t = func_out + B
wire [31:0] At  = dr + A;
wire [31:0] Ct  = br + C;
wire [31:0] Dt  = cr + D;

wire st0  = (getdata_state == 3'd0);
wire st4  = (getdata_state == 3'd4);
wire hg   = (round64 == 6'd63);   // hash_generated
wire zero = newtext_i | ((round64 == 6'd0) & ~generate_hash);
wire step = ~st0 & ~newtext_i & generate_hash;
wire [5:0] r64_n = zero ? 6'd0 : round64 + 6'd1;

// ---------------- ar..dr ----------------
reg [31:0] ar_n, bro, cr_n, dr_n;
always @* begin
  if (st0) begin
    ar_n = A;  bro = B;  cr_n = C;  dr_n = D;
  end else if (newtext_i) begin
    ar_n = KA; bro = KB; cr_n = KC; dr_n = KD;
  end else if (generate_hash) begin
    ar_n = dr; bro = br; cr_n = br; dr_n = cr;
  end else begin
    ar_n = ar; bro = br; cr_n = cr; dr_n = dr;
  end
end
wire [31:0] br_n = step ? fo : bro;

// ---------------- getdata ----------------
reg [2:0]  gs_n;
reg        gh_n, rdy_n;
reg [31:0] A_n, Bo, C_n, D_n;
always @* begin
  gs_n = getdata_state; gh_n = generate_hash; rdy_n = 1'b0;
  A_n = A; Bo = B; C_n = C; D_n = D;
  if (newtext_i) begin
    A_n = KA; Bo = KB; C_n = KC; D_n = KD; gs_n = 3'd0;
  end
  case (getdata_state)
    3'd0: if (load_i) gs_n = 3'd1;
    3'd1: if (load_i) gs_n = 3'd2;
    3'd2: if (load_i) gs_n = 3'd3;
    3'd3: if (load_i) begin gs_n = 3'd4; gh_n = 1'b1; end
    3'd4: begin
      gh_n = 1'b1;
      if (hg) begin
        A_n = At; C_n = Ct; D_n = Dt;
        gs_n = 3'd0; rdy_n = 1'b1; gh_n = 1'b0;
      end
    end
    default: ;
  endcase
end
wire [31:0]  B_n  = (st4 & hg) ? bt : Bo;
wire [127:0] do_n = st4 ? {At, bt, Ct, Dt} : 128'd0;

// ---------------- message and lookahead ----------------
reg [511:0] nmsg;
always @* begin
  nmsg = message;
  if (load_i)
    case (getdata_state)
      3'd0: nmsg[511:384] = data_i;
      3'd1: nmsg[383:256] = data_i;
      3'd2: nmsg[255:128] = data_i;
      3'd3: nmsg[127:0]   = data_i;
      default: ;
    endcase
end

reg [31:0] wq;
integer k;
always @* begin
  wq = 32'd0;
  for (k = 0; k < 16; k = k + 1)
    wq = wq | (nmsg[511-32*k -: 32] & {32{iq[k]}});
end

wire [31:0] wn    = zero ? nmsg[511:480] : wq;
wire [31:0] tn    = zero ? 32'hD76AA478 : tnf(round64);
wire [31:0] s3    = ar_n ^ wn ^ tn;
wire [31:0] c3    = (ar_n & wn) | (ar_n & tn) | (wn & tn);
wire [31:0] pre_n = ksa(s3, {c3[30:0], 1'b0});
wire [15:0] iq_n  = zero ? 16'h0002 : (16'd1 << nbf(round64 + 6'd2));
wire [63:0] fc_n  = fsplit(cr_n, dr_n, r64_n[5:4]);

// ---------------- registers ----------------
always @(posedge clk or negedge reset)
begin
  if (!reset) begin
    ready_o <= 1'b0;
    data_o <= 128'd0;
    message <= 512'd0;
    ar <= KA; br <= KB; cr <= KC; dr <= KD;
    A <= KA;  B <= KB;  C <= KC;  D <= KD;
    getdata_state <= 3'd0;
    generate_hash <= 1'b0;
    round64 <= 6'd0;
    pre <= 32'h3EAFC779;   // KA + 0 + T(0)
    iq  <= 16'h0002;       // nblock(1) = 1
    fc1 <= KC;             // round 0: F = b ? c : d
    fc0 <= KD;
  end else begin
    ready_o <= rdy_n;
    data_o <= do_n;
    message <= nmsg;
    ar <= ar_n; br <= br_n; cr <= cr_n; dr <= dr_n;
    A <= A_n;   B <= B_n;   C <= C_n;   D <= D_n;
    getdata_state <= gs_n;
    generate_hash <= gh_n;
    round64 <= r64_n;
    pre <= pre_n;
    iq  <= iq_n;
    fc1 <= fc_n[63:32];
    fc0 <= fc_n[31:0];
  end
end

endmodule
