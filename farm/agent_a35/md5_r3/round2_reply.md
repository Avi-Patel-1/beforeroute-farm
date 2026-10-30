RATIONALE: Round 3 failed because of one line. c3 was written as {maj,0}>>1<<1, which already shifts it, and c3s shifted it again. pre (a+M+T) was therefore wrong. That is fixed. I re-checked every other round-3 change line by line against the verified round-2 logic. At 10.60 ns two paths tie: the pre lookahead, slowed by fanout from the getdata_state selects (fixed by the registered decodes), and the step loop br->F->add->rotate->add. This version also removes the muxes at the end of that loop. The rotate selects are registered and pre-gated by ~st0&gh, so that one rotate serves both func_out and B_t. newtext's force-to-KB now works by killing the generates and setting the half-sums inside the br adder. The st4 gating of B_t works the same way. B is updated lazily from data_o[95:64], so no mux follows either adder. br, pre and the F operands stay XOR-encoded on fast reset flops.
```verilog
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
                  KC = 32'h98BADCFE, KD = 32'h10325476,
                  T0 = 32'hD76AA478, KP = 32'h3EAFC779;   // KP = KA + T(0)

reg [5:0]   round64;
reg [31:0]  ar, cr, dr, A, C, D;
reg [31:0]  Bs;         // B, except right after a finish (then B == data_o[95:64])
reg         finq;       // the previous cycle finished a hash
reg [511:0] message;
reg [2:0]   getdata_state;
reg         generate_hash;
// step-loop state stored XOR its reset value (so all are reset-to-0 flops)
reg [31:0]  brx;        // br  ^ KB
reg [31:0]  prx;        // pre ^ KP ; pre == ar + M[nblock(round64)] + T(round64)
reg [31:0]  f1x, f0x;   // F(b=1)^KC, F(b=0)^KD for the current cr, dr, round
// registered decodes of the current state
reg [15:0]  rsg;        // one-hot {round64[5:4],round64[1:0]}, zero unless ~st0 & gh
reg [15:0]  ws;         // one-hot word of the next pre: z0 ? 0 : nblock(round64+1)
reg [3:0]   wm;         // position of that word inside its 128-bit chunk
reg         wh;         // that word's chunk == getdata_state
reg         z0;         // round64 == 0 && !generate_hash
reg         s0a, s0b;   // ~st0, st0
reg         sha, shc, shd;        // ~st0&gh, st0|gh, ~st0&~gh
reg         s4a, s4b, fin;        // st4, ~st4, st4 && round64==63

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

// 32-bit Kogge-Stone carries from per-bit generate gi and OR-propagate pi:
// kcy[i] = carry out of bit i (carry-in 0)
function [31:0] kcy;
input [31:0] gi, pi;
reg [31:0] g, p;
integer i, j;
begin
  g = gi;
  p = pi;
  for (j = 1; j < 32; j = j + j)
    for (i = 31; i >= j; i = i - 1) begin
      g[i] = g[i] | (p[i] & g[i-j]);
      p[i] = p[i] & p[i-j];
    end
  kcy = g;
end
endfunction

// ---------------- decoded / encoded state ----------------
wire        nt    = newtext_i;
wire [31:0] br    = brx ^ KB;
wire [31:0] pre   = prx ^ KP;
wire [31:0] fc1   = f1x ^ KC;
wire [31:0] fc0   = f0x ^ KD;
wire [31:0] Bv    = finq ? data_o[95:64] : Bs;   // == original B
wire        hg    = (round64 == 6'd63);          // hash_generated
wire        zero  = nt | z0;
wire [5:0]  r64_n = zero ? 6'd0 : round64 + 6'd1;

// ---------------- step datapath ----------------
// aux = pre + F(br,cr,dr), F folded into the generate/propagate terms
wire [31:0] ga  = (br & pre & fc1) | (~br & pre & fc0);
wire [31:0] pa  = (br & (pre | fc1)) | (~br & (pre | fc0));
wire [31:0] ac  = kcy(ga, pa);
wire [31:0] aux = (pa & ~ga) ^ {ac[30:0], 1'b0};
reg  [31:0] rot;   // rotated aux; zero unless ~st0 & gh
integer k;
always @* begin
  rot = 32'd0;
  for (k = 0; k < 16; k = k + 1)
    rot = rot | ({32{rsg[k]}} & rotf(aux, k));
end
// br_n = (~st0 & newtext) ? KB : xr + rot ; xr = st0 ? B : br
wire        bk    = nt & s0a;
wire [31:0] xr    = s0b ? Bv : br;
wire [31:0] fcy   = kcy(xr & rot & {32{~bk}}, xr | rot);
wire [31:0] fh    = bk ? KB : (xr ^ rot);
wire [31:0] brx_n = fh ^ {fcy[30:0], 1'b0} ^ KB;
// B_t = (br + B) + rot, forced to 0 unless st4
wire [31:0] bcy   = kcy(br & Bv, br | Bv);
wire [31:0] bb    = (br ^ Bv) ^ {bcy[30:0], 1'b0};
wire [31:0] tcy   = kcy(bb & rot & {32{s4a}}, bb | rot);
wire [31:0] btg   = ((bb ^ rot) & {32{s4a}}) ^ {tcy[30:0], 1'b0};
wire [31:0] At    = dr + A;
wire [31:0] Ct    = br + C;
wire [31:0] Dt    = cr + D;

// ---------------- ar, cr, dr ----------------
wire [31:0] ar_n = ~s0a ? A : nt ? KA : sha ? dr : ar;
wire [31:0] cr_n = ~s0a ? C : nt ? KC : shc ? br : cr;
wire [31:0] dr_n = s0b  ? D : nt ? KD : shd ? dr : cr;

// ---------------- getdata ----------------
reg [2:0] gs_n;
reg       gh_n, rdy_n;
always @* begin
  gs_n = getdata_state; gh_n = generate_hash; rdy_n = 1'b0;
  if (nt) gs_n = 3'd0;
  case (getdata_state)
    3'd0: if (load_i) gs_n = 3'd1;
    3'd1: if (load_i) gs_n = 3'd2;
    3'd2: if (load_i) gs_n = 3'd3;
    3'd3: if (load_i) begin gs_n = 3'd4; gh_n = 1'b1; end
    3'd4: begin
      gh_n = 1'b1;
      if (hg) begin gs_n = 3'd0; rdy_n = 1'b1; gh_n = 1'b0; end
    end
    default: ;
  endcase
end
wire [31:0]  A_n  = fin ? At : nt ? KA : A;
wire [31:0]  C_n  = fin ? Ct : nt ? KC : C;
wire [31:0]  D_n  = fin ? Dt : nt ? KD : D;
wire [31:0]  Bs_n = nt ? KB : Bv;
wire [127:0] do_n = {s4a ? At : 32'd0, btg,
                     s4b ? 32'd0 : Ct, s4b ? 32'd0 : Dt};

// ---------------- message ----------------
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

// ---------------- lookahead: next pre and F operands ----------------
reg [31:0] msel, dsel;
integer q;
always @* begin
  msel = 32'd0;
  for (q = 0; q < 16; q = q + 1)
    msel = msel | (message[511-32*q -: 32] & {32{ws[q]}});
  dsel = 32'd0;
  for (q = 0; q < 4; q = q + 1)
    dsel = dsel | (data_i[127-32*q -: 32] & {32{wm[q]}});
end
wire [31:0] w0    = (load_i & s0b) ? data_i[127:96] : message[511:480];
wire [31:0] wsq   = (load_i & wh) ? dsel : msel;
wire [31:0] wn    = nt ? w0 : wsq;
wire [31:0] tn    = zero ? T0 : tnf(round64);
wire [31:0] s3    = ar_n ^ wn ^ tn;
wire [31:0] c3    = (ar_n & wn) | (ar_n & tn) | (wn & tn);
wire [31:0] c3s   = {c3[30:0], 1'b0};
wire [31:0] pcy   = kcy(s3 & c3s, s3 | c3s);
wire [31:0] pre_n = (s3 ^ c3s) ^ {pcy[30:0], 1'b0};
wire [63:0] fc_n  = fsplit(cr_n, dr_n, r64_n[5:4]);

// ---------------- next-state decodes ----------------
wire        st0_n = (gs_n == 3'd0);
wire        st4_n = (gs_n == 3'd4);
wire        z0_n  = (r64_n == 6'd0) & ~gh_n;
wire [3:0]  nb_n  = nbf(r64_n + 6'd1);
wire [15:0] ws_n  = z0_n ? 16'h0001 : (16'd1 << nb_n);
wire [3:0]  wm_n  = ws_n[3:0] | ws_n[7:4] | ws_n[11:8] | ws_n[15:12];
wire        wh_n  = ((gs_n == 3'd0) & (|ws_n[3:0]))  | ((gs_n == 3'd1) & (|ws_n[7:4]))
                  | ((gs_n == 3'd2) & (|ws_n[11:8])) | ((gs_n == 3'd3) & (|ws_n[15:12]));
wire [15:0] rsg_n = (16'd1 << {r64_n[5:4], r64_n[1:0]}) & {16{~st0_n & gh_n}};

// ---------------- registers ----------------
always @(posedge clk or negedge reset)
begin
  if (!reset) begin
    ready_o <= 1'b0;
    data_o <= 128'd0;
    message <= 512'd0;
    ar <= KA; cr <= KC; dr <= KD;
    A <= KA;  Bs <= KB; C <= KC;  D <= KD; finq <= 1'b0;
    brx <= 32'd0; prx <= 32'd0; f1x <= 32'd0; f0x <= 32'd0;
    getdata_state <= 3'd0;
    generate_hash <= 1'b0;
    round64 <= 6'd0;
    rsg <= 16'd0; ws <= 16'h0001; wm <= 4'h1; wh <= 1'b1; z0 <= 1'b1;
    s0a <= 1'b0; s0b <= 1'b1;
    sha <= 1'b0; shc <= 1'b1; shd <= 1'b0;
    s4a <= 1'b0; s4b <= 1'b1; fin <= 1'b0;
  end else begin
    ready_o <= rdy_n;
    data_o <= do_n;
    message <= nmsg;
    ar <= ar_n; cr <= cr_n; dr <= dr_n;
    A <= A_n;   Bs <= Bs_n; C <= C_n;   D <= D_n; finq <= fin;
    brx <= brx_n;
    prx <= pre_n ^ KP;
    f1x <= fc_n[63:32] ^ KC;
    f0x <= fc_n[31:0] ^ KD;
    getdata_state <= gs_n;
    generate_hash <= gh_n;
    round64 <= r64_n;
    rsg <= rsg_n; ws <= ws_n; wm <= wm_n; wh <= wh_n; z0 <= z0_n;
    s0a <= ~st0_n; s0b <= st0_n;
    sha <= ~st0_n & gh_n; shc <= st0_n | gh_n; shd <= ~st0_n & ~gh_n;
    s4a <= st4_n; s4b <= ~st4_n;
    fin <= st4_n & (r64_n == 6'd63);
  end
end

endmodule
```