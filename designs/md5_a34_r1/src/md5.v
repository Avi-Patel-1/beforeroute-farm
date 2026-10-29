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
reg [31:0]  pre;  // == ar + message_var[nblock(round64)] + T(round64)
reg [31:0]  brB;  // == br + B whenever getdata_state != 0
reg [15:0]  iq;   // == one-hot nblock(round64+1)

// T constants
function [31:0] tf;
input [5:0] k;
case (k)
  0: tf=32'hD76AA478;  1: tf=32'hE8C7B756;  2: tf=32'h242070DB;  3: tf=32'hC1BDCEEE;
  4: tf=32'hF57C0FAF;  5: tf=32'h4787C62A;  6: tf=32'hA8304613;  7: tf=32'hFD469501;
  8: tf=32'h698098D8;  9: tf=32'h8B44F7AF; 10: tf=32'hFFFF5BB1; 11: tf=32'h895CD7BE;
 12: tf=32'h6B901122; 13: tf=32'hFD987193; 14: tf=32'hA679438E; 15: tf=32'h49B40821;
 16: tf=32'hF61E2562; 17: tf=32'hC040B340; 18: tf=32'h265E5A51; 19: tf=32'hE9B6C7AA;
 20: tf=32'hD62F105D; 21: tf=32'h02441453; 22: tf=32'hD8A1E681; 23: tf=32'hE7D3FBC8;
 24: tf=32'h21E1CDE6; 25: tf=32'hC33707D6; 26: tf=32'hF4D50D87; 27: tf=32'h455A14ED;
 28: tf=32'hA9E3E905; 29: tf=32'hFCEFA3F8; 30: tf=32'h676F02D9; 31: tf=32'h8D2A4C8A;
 32: tf=32'hFFFA3942; 33: tf=32'h8771F681; 34: tf=32'h6D9D6122; 35: tf=32'hFDE5380C;
 36: tf=32'hA4BEEA44; 37: tf=32'h4BDECFA9; 38: tf=32'hF6BB4B60; 39: tf=32'hBEBFBC70;
 40: tf=32'h289B7EC6; 41: tf=32'hEAA127FA; 42: tf=32'hD4EF3085; 43: tf=32'h04881D05;
 44: tf=32'hD9D4D039; 45: tf=32'hE6DB99E5; 46: tf=32'h1FA27CF8; 47: tf=32'hC4AC5665;
 48: tf=32'hF4292244; 49: tf=32'h432AFF97; 50: tf=32'hAB9423A7; 51: tf=32'hFC93A039;
 52: tf=32'h655B59C3; 53: tf=32'h8F0CCC92; 54: tf=32'hFFEFF47D; 55: tf=32'h85845DD1;
 56: tf=32'h6FA87E4F; 57: tf=32'hFE2CE6E0; 58: tf=32'hA3014314; 59: tf=32'h4E0811A1;
 60: tf=32'hF7537E82; 61: tf=32'hBD3AF235; 62: tf=32'h2AD7D2BB; default: tf=32'hEB86D391;
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

// 32-bit Kogge-Stone adder
function [31:0] ksa;
input [31:0] x, y;
reg [31:0] g, p, h;
integer i, d;
begin
  h = x ^ y;
  g = x & y;
  p = h;
  for (d = 1; d < 32; d = d + d)
    for (i = 31; i >= d; i = i - 1) begin
      g[i] = g[i] | (p[i] & g[i-d]);
      p[i] = p[i] & p[i-d];
    end
  ksa = h ^ {g[30:0], 1'b0};
end
endfunction

// ---------------- step datapath ----------------
reg [31:0] fr;
always @* begin
  case (round64[5:4])
    2'd0:    fr = (br & cr) | (~br & dr);
    2'd1:    fr = (br & dr) | (cr & ~dr);
    2'd2:    fr = br ^ cr ^ dr;
    default: fr = cr ^ (br | ~dr);
  endcase
end

wire [31:0] aux = ksa(pre, fr);
wire [31:0] rot = rotf(aux, {round64[5:4], round64[1:0]});
wire [31:0] fo  = ksa(br, rot);    // func_out
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
wire [31:0]  B_n   = (st4 & hg) ? bt : Bo;
wire [127:0] do_n  = st4 ? {At, bt, Ct, Dt} : 128'd0;
wire [31:0]  brB_n = step ? bt :
                     st0 ? (newtext_i ? (B + KB) : {B[30:0], 1'b0}) :
                     (newtext_i ? 32'hDF9B5712 : brB);

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
wire [31:0] tn    = zero ? 32'hD76AA478 : tf(round64 + 6'd1);
wire [31:0] pre_n = ar_n + wn + tn;
wire [15:0] iq_n  = zero ? 16'h0002 : (16'd1 << nbf(round64 + 6'd2));

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
    brB <= 32'hDF9B5712;   // KB + KB
    iq  <= 16'h0002;       // nblock(1) = 1
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
    brB <= brB_n;
    iq  <= iq_n;
  end
end

endmodule
