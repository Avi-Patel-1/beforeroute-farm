You are improving the RTL of a hardware block so that it meets a faster clock after place-and-route. Use only what is
in this prompt; do not use tools, files or outside sources. Reply in the exact format given at the end.

THE BLOCK. An MD5 hash engine (the Verilog module `md5` below, from OpenCores). It is implemented with the open sky130 flow
(LibreLane 3.0.16: Yosys/ABC synthesis, OpenROAD placement, clock-tree synthesis, routing and repair; sky130_fd_sc_hd
standard cells) and judged by signoff static timing at nine corners after routing and parasitic extraction.

THE FLOW SETTING (fixed; you cannot change it, the constraints or the clock): synthesis script "AREA 3" with ABC buffering
and gate sizing on; core utilisation 29%, placement density 41%; timing-driven global placement;
timing repair and electrical repair again after global routing; setup margins 0.202 ns (placement) and
0.115 ns (after global routing); slew and capacitance repair aim 33% and 14% below the limits; wire
capacitance before routing taken as 2.13 times the library's per-layer values. Input and output delays are 20% of the clock
period; clock uncertainty is 0.25 ns. With the original RTL this setting passes signoff at a 16.05 ns clock (worst setup
slack +0.616 ns), at 97461 um2 of standard cells.


THE GOAL. Change the RTL so that, under the same setting, the block meets a shorter clock period than your round-2
rewrite (below), which passes at 10.60 ns. Your new rewrite will be run at the tightest clock your round-2 rewrite has
passed by the time the new one clears the gate (10.60 ns, or tighter if a re-run of the round-2 rewrite passes first), and
then at successively tighter clocks (each time at the clock the previous run's timing says it can meet; after a miss, at
most two runs step back up) until the chain ends; the result is the tightest clock that passes. Standard-cell area may be
at most 15% above the original's 97461 um2 (at most 112080 um2); your round-2 rewrite uses 106731 um2.

THE RULES (a rewrite that breaks any of them is rejected and not run):
1. Same module name (`md5`), same ports, widths and directions, same clock and same asynchronous active-low reset.
2. After reset, every output (`data_o`, `ready_o`) must have exactly the same value as the original's on every clock cycle,
   for every possible input sequence (including `newtext_i`, `load_i` and `data_i` changing at any time). Note that the
   original drives `data_o` on every cycle, not only when `ready_o` is high. You may add or remove registers, change
   encodings and restructure logic, as long as the outputs stay cycle-for-cycle identical.
3. Synthesizable Verilog-2005 (no SystemVerilog), one file, no initial blocks, no simulation-only constructs.
4. No change to the constraints, the clock or the flow setting.
It is checked by lockstep simulation of your module against the original under random stimulus (at least 200,000 cycles,
both outputs compared on every cycle, with resets in between) and by hashing at least 1,000 random messages through the
documented protocol and comparing the digests with a reference MD5.


THE SIGNOFF TIMING REPORT OF THE BASELINE RUN:
MD5 baseline run x7k-md5-004 (the setting of run x4c-md5-003, clock target 16.05 ns): signoff static timing at nine
corners after detailed routing and parasitic extraction.
Limiting corner: max_ss_100C_1v60 (slow-slow, 100 C, 1.60 V, maximum RC). Worst setup slack +0.616 ns. The worst
path is register-to-register.
Clock 16.05 ns; clock uncertainty 0.25 ns; endpoint library setup time 0.128 ns; the launching flop's clock pin
is reached at 2.06 ns (clock tree), so the data path runs from 2.94 ns to 16.96 ns.

WORST SETUP PATH at the limiting corner (signoff report_checks, one path per corner is reported):
  startpoint: flop _14578_, output net round64[1]
  endpoint:   flop _14540_, D input net next_data_o[94]
  arrival 16.960 ns, required 17.576 ns, slack +0.616 ns
  60 cells from the launching flop to the endpoint (arrival at the cell output in ns, cell, output net,
  fanout):
      2.943  dfrtp_2      round64[1]  (fanout 2)
      3.209  buf_6        net920  (fanout 3)
      3.474  buf_12       net1551  (fanout 5)
      3.593  nand2_8      _00663_  (fanout 2)
      3.831  buf_12       net884  (fanout 5)
      4.006  nand2_8      _01267_  (fanout 4)
      4.327  o21ai_4      _01284_  (fanout 1)
      4.637  buf_8        net1499  (fanout 3)
      4.745  inv_16       _01319_  (fanout 6)
      5.145  nor2_4       _01320_  (fanout 4)
      5.576  nand3_4      _01321_  (fanout 3)
      5.910  buf_8        net658  (fanout 2)
      6.186  buf_12       net1443  (fanout 8)
      6.499  buf_6        net657  (fanout 4)
      6.725  nor2_2       _02891_  (fanout 1)
      6.859  nor2_4       _02892_  (fanout 1)
      6.961  nand3_4      _02895_  (fanout 1)
      7.071  nor2_4       _02903_  (fanout 1)
      7.250  nand2_8      _02904_  (fanout 2)
      7.560  nand3_4      _02916_  (fanout 3)
      7.795  nand2_8      _02918_  (fanout 4)
      7.895  inv_2        _02919_  (fanout 1)
      8.033  nand2_4      _02920_  (fanout 1)
      8.176  nand2_8      _02922_  (fanout 3)
      8.323  nand2_8      _02944_  (fanout 2)
      8.412  nor2_4       _02951_  (fanout 1)
      8.742  a21oi_4      _02959_  (fanout 1)
      8.991  nand2_8      _02960_  (fanout 5)
      9.504  a21o_4       _04158_  (fanout 2)
     10.060  or2_4        _04166_  (fanout 1)
     10.219  nand2_8      _04167_  (fanout 2)
     10.358  nand2_4      _04303_  (fanout 3)
     10.487  nand2_2      _05033_  (fanout 1)
     10.582  inv_2        _05034_  (fanout 2)
     11.164  mux2_4       _05035_  (fanout 2)
     11.462  o21ai_4      _05037_  (fanout 2)
     11.814  a21o_4       _05039_  (fanout 1)
     11.987  nand2_4      _05041_  (fanout 2)
     12.477  or2_4        _05042_  (fanout 1)
     12.680  nand2_2      _05044_  (fanout 3)
     12.857  inv_2        _05045_  (fanout 2)
     13.010  nand2_4      _05066_  (fanout 2)
     13.111  nor2_4       _05070_  (fanout 2)
     13.383  o21ai_2      _05197_  (fanout 1)
     13.752  nand3_4      _05200_  (fanout 4)
     13.956  nand2_4      _05202_  (fanout 2)
     14.079  nand2_2      _05232_  (fanout 2)
     14.580  or2_4        _05233_  (fanout 2)
     14.740  nand3_4      _05237_  (fanout 2)
     14.888  nand2_8      _05238_  (fanout 3)
     15.370  or2_4        _05314_  (fanout 1)
     15.542  nor2_4       _05316_  (fanout 1)
     15.661  nand2_4      _05317_  (fanout 1)
     15.804  nand2_4      _05323_  (fanout 3)
     15.921  nand2_2      _05368_  (fanout 1)
     16.045  nand2_2      _05370_  (fanout 2)
     16.264  or2_4        _05371_  (fanout 1)
     16.385  nand2_2      _05373_  (fanout 2)
     16.877  or2_4        _05748_  (fanout 1)
     16.960  inv_4        next_data_o[94]  (fanout 1)

WORST SETUP ENDPOINTS: the nets feeding flop D inputs with the lowest signoff slack (ns), worst corner. Names are the RTL
signal names where synthesis kept them:
   0.616  next_data_o[94]
   0.676  next_B[28]
   0.706  next_B[24]
   0.728  next_data_o[91]
   0.743  next_B[26]
   0.780  next_data_o[95]
   0.781  next_data_o[89]
   0.781  next_B[18]
   0.784  next_data_o[90]
   0.810  next_B[30]
   0.824  next_B[31]
   0.843  next_B[20]
   0.850  next_B[22]
   0.858  next_data_o[86]
   0.863  next_B[27]
   0.885  next_data_o[83]
   0.891  next_data_o[82]
   0.897  next_data_o[92]
   0.927  next_data_o[93]
   0.939  next_B[19]
   0.949  next_data_o[88]
   0.961  next_B[29]
   1.006  next_B[14]
   1.050  next_B[25]
   1.064  next_data_o[84]
   1.065  next_B[16]
   1.097  next_B[10]
   1.119  next_B[21]
   1.121  next_data_o[75]
   1.172  next_B[23]

WORST STARTPOINTS: flop output nets with the lowest signoff slack (ns), with cell type and fanout:
   0.616  round64[1]  (dfrtp_2, fanout 2)
   0.645  round64[4]  (dfrtp_2, fanout 2)
   0.650  round64[2]  (dfrtp_2, fanout 7)
   0.656  round64[0]  (dfrtp_2, fanout 4)
   0.671  round64[3]  (dfrtp_2, fanout 3)
   0.694  round64[5]  (dfrtp_2, fanout 3)
   0.719  round[0]  (dfrtp_2, fanout 5)
   0.756  round[2]  (dfrtp_2, fanout 5)
   0.781  br[25]  (dfstp_2, fanout 3)
   0.792  br[13]  (dfstp_2, fanout 4)
   0.798  round[1]  (dfrtp_2, fanout 4)
   0.817  cr[10]  (dfstp_2, fanout 5)
   0.930  br[20]  (dfrtp_2, fanout 4)
   0.948  br[15]  (dfstp_2, fanout 6)
   0.949  br[24]  (dfstp_2, fanout 6)
   0.949  br[10]  (dfrtp_2, fanout 4)
   0.960  br[22]  (dfstp_2, fanout 3)
   0.980  cr[14]  (dfstp_2, fanout 5)
   1.007  br[17]  (dfrtp_2, fanout 4)
   1.017  br[21]  (dfrtp_2, fanout 4)

The endpoint and startpoint lists come from the run's per-net signoff dump: each net's slack is the worst slack of any
path through it. Unnamed nets (_NNNNN_, netNNN) were created by synthesis or by the flow's buffering and repair.


THE ORIGINAL RTL (designs/md5/src/md5.v):
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
// CVS Revision History
//
// $Log: not supported by cvs2svn $

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

reg ready_o, next_ready_o;
reg [127:0] data_o, next_data_o;

reg [5:0] round64, next_round64;
reg [43:0] t;


reg [31:0] ar,br,cr,dr,func_out, next_ar,next_br, next_cr, next_dr;
reg [31:0] A,B,C,D,next_A,next_B, next_C, next_D;
reg [511:0] message, next_message;
reg [2:0] round,next_round;
reg next_generate_hash,generate_hash;
reg hash_generated;

reg [2:0] next_getdata_state, getdata_state;

//rom process
always @(round64)
begin
	
   case(round64)
         0: t = 44'hD76AA478070; 
         1: t = 44'hE8C7B7560C1; 		
         2: t = 44'h242070DB112; 
         3: t = 44'hC1BDCEEE163; 
         4: t = 44'hF57C0FAF074; 
         5: t = 44'h4787C62A0C5; 
         6: t = 44'hA8304613116; 
         7: t = 44'hFD469501167; 
         8: t = 44'h698098D8078; 		
         9: t = 44'h8B44F7AF0C9; 
         10: t = 44'hFFFF5BB111A; 
         11: t = 44'h895CD7BE16B; 
         12: t = 44'h6B90112207C; 
         13: t = 44'hFD9871930CD; 
         14: t = 44'hA679438E11E; 
         15: t = 44'h49B4082116F; 		
	   
         16: t = 44'hf61e2562051; 
         17: t = 44'hc040b340096; 
         18: t = 44'h265e5a510EB; 
         19: t = 44'he9b6c7aa140; 
         20: t = 44'hd62f105d055; 
         21: t = 44'h0244145309A; 
         22: t = 44'hd8a1e6810EF; 		
         23: t = 44'he7d3fbc8144; 
         24: t = 44'h21e1cde6059; 
         25: t = 44'hc33707d609E; 
         26: t = 44'hf4d50d870E3; 
         27: t = 44'h455a14ed148; 
         28: t = 44'ha9e3e90505D; 
         29: t = 44'hfcefa3f8092; 		
         30: t = 44'h676f02d90E7; 
         31: t = 44'h8d2a4c8a14C; 
		   
         32: t = 44'hfffa3942045; 
         33: t = 44'h8771f6810B8; 
         34: t = 44'h6d9d612210B; 
         35: t = 44'hfde5380c17E; 
         36: t = 44'ha4beea44041; 		
         37: t = 44'h4bdecfa90B4; 
         38: t = 44'hf6bb4b60107; 
         39: t = 44'hbebfbc7017A; 
         40: t = 44'h289b7ec604D; 
         41: t = 44'heaa127fa0B0; 
         42: t = 44'hd4ef3085103; 
         43: t = 44'h04881d05176; 		
         44: t = 44'hd9d4d039049; 
         45: t = 44'he6db99e50BC; 
         46: t = 44'h1fa27cf810F; 
         47: t = 44'hc4ac5665172; 
		   
         48: t = 44'hf4292244060; 
         49: t = 44'h432aff970A7; 
         50: t = 44'hab9423a70FE; 		
         51: t = 44'hfc93a039155; 
         52: t = 44'h655b59c306C; 
         53: t = 44'h8f0ccc920A3; 
         54: t = 44'hffeff47d0FA; 
         55: t = 44'h85845dd1151; 
         56: t = 44'h6fa87e4f068; 
         57: t = 44'hfe2ce6e00AF; 		
         58: t = 44'ha30143140F6; 
         59: t = 44'h4e0811a115D; 
         60: t = 44'hf7537e82064; 
         61: t = 44'hbd3af2350AB; 
         62: t = 44'h2ad7d2bb0F2; 
         63: t = 44'heb86d391159;		 
    endcase
end
//end process rom


//funcs process


reg [31:0] aux31,fr_var,tr_var,rotate1,rotate2;	
reg [7:0] s_var;	
reg [3:0] nblock;
reg [31:0] message_var[15:0];	
   
always @(t or ar or br or cr or dr or round or message or func_out or message_var[0] or message_var[1] or message_var[2] or message_var[3] 
         or message_var[4] or message_var[5] or message_var[6] or message_var[7] or message_var[8] or message_var[9] or message_var[10]
         or message_var[11] or message_var[12] or message_var[13] or message_var[14] or message_var[15])
begin

   message_var[0]=message[511:480]; 
   message_var[1]=message[479:448]; 
   message_var[2]=message[447:416]; 
   message_var[3]=message[415:384]; 
   message_var[4]=message[383:352]; 
   message_var[5]=message[351:320]; 
   message_var[6]=message[319:288]; 
   message_var[7]=message[287:256]; 
   message_var[8]=message[255:224]; 
   message_var[9]=message[223:192]; 
   message_var[10]=message[191:160]; 
   message_var[11]=message[159:128]; 
   message_var[12]=message[127:96]; 
   message_var[13]=message[95:64]; 
   message_var[14]=message[63:32]; 
   message_var[15]=message[31:0];
	
   fr_var=0;	
	
   case(round)
      0: fr_var=((br&cr)|(~br&dr));
      1: fr_var=((br&dr)|(cr& (~dr)));
      2: fr_var=(br^cr^dr);
      3: fr_var=(cr^(br|~dr));
   endcase
   
  
   tr_var=t[43:12];
   s_var=t[11:4];
   nblock=t[3:0];
   
   aux31=(ar+fr_var+message_var[nblock]+tr_var);
       
   rotate1=aux31 << s_var;
   rotate2=aux31 >> (32-s_var);
   func_out=br+(rotate1 | rotate2);
   
end
//end process funcs


//process round64FSM
always @(newtext_i or round or round64 or ar or br or cr or dr or generate_hash or func_out or getdata_state or A or B or C or D)
begin

      next_ar=ar;
      next_br=br;
      next_cr=cr;
      next_dr=dr;
      next_round64=round64;
      next_round=round;	
      hash_generated=0;
	
      if(generate_hash!=0)
      begin	
        next_ar=dr;		  
        next_br=func_out;
        next_cr=br; 
        next_dr=cr;
      end
			
      case(round64)
        0:
        begin
          next_round=0;
          if(generate_hash) next_round64=1;
        end 
	
        15,31,47:
        begin
          next_round=round+1;
          next_round64=round64+1;
        end

        63:
        begin
          next_round=0;
          next_round64=0;
          hash_generated=1;
        end
	
        default: next_round64=round64+1;

    endcase	  
	

    if(newtext_i)
    begin
      next_ar=32'h67452301;
      next_br=32'hEFCDAB89;
      next_cr=32'h98BADCFE;
      next_dr=32'h10325476;
      next_round=0;
      next_round64=0;		
    end
	
    if(!getdata_state)
    begin
      next_ar=A;
      next_br=B;
      next_cr=C;
      next_dr=D;
    end
	
end
//end round64FSM process

//regsignal process
always @(posedge clk or negedge reset)
begin

   if(!reset)
   begin
     ready_o=0;
     data_o=0;  
     message=0;

     ar=32'h67452301;
     br=32'hEFCDAB89;
     cr=32'h98BADCFE;
     dr=32'h10325476;
	 
     getdata_state=0;  
     generate_hash=0;
	 
     round=0;
     round64=0;	 
     A=32'h67452301;
     B=32'hEFCDAB89;
     C=32'h98BADCFE;
     D=32'h10325476;

   end 	   
   else
   begin
     ready_o=next_ready_o;
     data_o=next_data_o;
     message=next_message;
	 
     ar=next_ar;	   
     br=next_br;
     cr=next_cr;
     dr=next_dr;
	 
     A=next_A;	   
     B=next_B;
     C=next_C;
     D=next_D;
	 
     generate_hash=next_generate_hash;  
     getdata_state=next_getdata_state;
	 
     round=next_round;
     round64=next_round64;
   end
end   
//end regsignals process
	
   
//getdata process

reg [127:0] data_o_var;
reg [511:0] aux; 
wire [31:0] A_t,B_t,C_t,D_t;

assign A_t=dr+A;
assign B_t=func_out+B;
assign C_t=br+C;
assign D_t=cr+D; 

always @(newtext_i or A_t or B_t or C_t or D_t or data_i or load_i or getdata_state or generate_hash or hash_generated or message or func_out or A or B or C or D or ar or br or cr or dr)
begin

   next_A=A;	
   next_B=B;
   next_C=C;
   next_D=D;
	
   next_generate_hash=generate_hash;
   next_ready_o=0;
   next_getdata_state=getdata_state;

   next_data_o=0;
   aux=message;	
   next_message=message;
	
   if(newtext_i)
   begin
     next_A=32'h67452301;
     next_B=32'hEFCDAB89;
     next_C=32'h98BADCFE;
     next_D=32'h10325476;
     next_getdata_state=0;
   end
	
   case(getdata_state)

      0 :
      begin
        if(load_i)
        begin
          aux[511:384]=data_i;	 
          next_message=aux;
          next_getdata_state=1;
        end
      end
		 
      1 :
      begin
       if(load_i)
       begin
         aux[383:256]=data_i;	 
         next_message=aux;
         next_getdata_state=2;
       end
      end
		 
      2 :
      begin 
       if(load_i) 
       begin
         aux[255:128]=data_i;	 
         next_message=aux;
         next_getdata_state=3;
       end
      end
	
      3 :
      begin
        if(load_i)
        begin
          aux[127:0]=data_i;	 
          next_message=aux;
          next_getdata_state=4;
          next_generate_hash=1;
        end
      end
	  
	  4 :
      begin
	  
	    next_generate_hash=1;
	  	      	  
        data_o_var[127:96]=A_t;
        data_o_var[95:64]=B_t;
        data_o_var[63:32]=C_t;
        data_o_var[31:0]=D_t;
        next_data_o=data_o_var;
	  
        if(hash_generated)
        begin
		  next_A=A_t;
          next_B=B_t;
          next_C=C_t;
          next_D=D_t;
          next_getdata_state=0;
          next_ready_o=1;
          next_generate_hash=0;
        end
      end
   endcase
end
//end getdata process
	

endmodule


```


YOUR EARLIER ROUNDS AND WHAT HAPPENED TO THEM. This is a new rewrite; one revision round is allowed if it fails the gate or
the flow.

Round 1: your first rewrite passed the equivalence gate, but the flow stopped inside OpenROAD's electrical repair after
global placement, so no timing was measured.

Round 2: your reply, verbatim:
<<<
RATIONALE: The clock is set by the one-cycle MD5 step: round64 -> T/s/index ROM -> 16:1 message mux -> 4-operand add -> variable rotate -> +br -> +B into next_B/next_data_o (about 14 ns). My round-1 design passed equivalence but hit a deterministic repair_design stop, so this keeps its verified architecture with a changed netlist and a shorter loop. pre = a+M[k]+T is still registered one step ahead (now CSA plus Kogge-Stone, with the next-step T table indexed directly by round64, no incrementer). F is split into registered F(b=0)/F(b=1), computed from the exact next c, d and round, so F is a single mux on br. The rotate is a 16-way constant mux keyed by round64. br+B is computed combinationally in parallel (brB register removed), so B_t=(br+B)+rot runs beside func_out. Loop adders use OR-transmit Kogge-Stone.
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
```
>>>

Equivalence gate on that file: PASS. Lockstep simulation against the original, 250,000 cycles with 132 asynchronous
resets, both outputs equal on every cycle; 1,200 of 1,200 random messages hashed to the same digests as a reference MD5;
bounded formal equivalence found no counterexample in the first 6 cycles after reset before its 900 s limit.

Flow results under the same setting, each run at the clock the previous run's timing said it could meet:
  16.05 ns: passed, worst setup slack +4.239 ns, 106098 um2 (run x9r-md5-002)
  11.85 ns: passed, worst setup slack +0.696 ns, 105965 um2 (run x9r-md5-003)
  11.20 ns: passed, worst setup slack +0.628 ns, 106398 um2 (run x9r-md5-004)
  10.60 ns: passed, worst setup slack +0.564 ns, 106731 um2, 9.5% above the original (run x9r-md5-005)

THE SIGNOFF TIMING REPORT OF YOUR ROUND-2 REWRITE AT 10.60 ns:
MD5 round-2 rewrite run x9r-md5-005 (the same setting, clock target 10.60 ns): signoff static timing at nine
corners after detailed routing and parasitic extraction.
Limiting corner: max_ss_100C_1v60 (slow-slow, 100 C, 1.60 V, maximum RC). Worst setup slack +0.564 ns. The worst
path is register-to-register.
Clock 10.60 ns; clock uncertainty 0.25 ns; endpoint library setup time 0.121 ns; the launching flop's clock pin
is reached at 2.32 ns (clock tree), so the data path runs from 3.66 ns to 11.93 ns.

WORST SETUP PATH at the limiting corner (signoff report_checks, one path per corner is reported):
  startpoint: flop _16495_, output net getdata_state[0]
  endpoint:   flop _16347_, D input net ksa$func$/work/designs/md5_a34_r2/src/md5.v:249$10.$result[29]
  arrival 11.930 ns, required 12.494 ns, slack +0.564 ns
  26 cells from the launching flop to the endpoint (arrival at the cell output in ns, cell, output net,
  fanout):
      3.661  dfstp_2      getdata_state[0]  (fanout 3)
      4.025  buf_6        net1837  (fanout 8)
      4.276  nand2_4      _00605_  (fanout 7)
      4.663  buf_2        net845  (fanout 2)
      4.978  buf_6        net1654  (fanout 8)
      5.474  buf_2        net844  (fanout 10)
      5.990  clkbuf_4     net843  (fanout 10)
      6.465  buf_2        net842  (fanout 8)
      7.305  mux2_1       _00742_  (fanout 2)
      7.813  a22o_2       _01890_  (fanout 1)
      7.981  nor2_2       _01891_  (fanout 1)
      8.136  nand3_2      _01893_  (fanout 1)
      8.342  o22ai_2      _01910_  (fanout 1)
      8.796  buf_2        net661  (fanout 2)
      9.150  or2_2        _01911_  (fanout 2)
      9.333  nand2_2      _01925_  (fanout 3)
      9.826  or2_4        _01926_  (fanout 1)
     10.039  nand3_2      _01964_  (fanout 4)
     10.304  nand2_2      _01965_  (fanout 3)
     10.694  nor2_2       _03148_  (fanout 2)
     11.121  and2_2       _03149_  (fanout 2)
     11.421  and2_2       _03150_  (fanout 1)
     11.569  nand2_2      _03151_  (fanout 2)
     11.688  nand2_2      _03156_  (fanout 1)
     11.818  nand2_2      _03158_  (fanout 1)
     11.929  nand2_4      ksa$func$/work/designs/md5_a34_r2/src/md5.v:249$10.$result[29]  (fanout 1)

WORST SETUP ENDPOINTS: the nets feeding flop D inputs with the lowest signoff slack (ns), worst corner. Names are the RTL
signal names where synthesis kept them:
   0.564  _00742_
   0.564  ksa$func$/work/designs/md5_a34_r2/src/md5.v:249$10.$result[29]
   0.574  do_n[95]
   0.602  _01068_
   0.602  ksa$func$/work/designs/md5_a34_r2/src/md5.v:249$10.$result[30]
   0.602  ksa$func$/work/designs/md5_a34_r2/src/md5.v:249$10.$result[28]
   0.602  _01040_
   0.604  nmsg[104]
   0.604  ksa$func$/work/designs/md5_a34_r2/src/md5.v:249$10.$result[20]
   0.616  do_n[79]
   0.623  do_n[72]
   0.623  _01026_
   0.630  _01115_
   0.633  ksa$func$/work/designs/md5_a34_r2/src/md5.v:249$10.$result[31]
   0.636  _01116_
   0.646  _00800_
   0.646  _00049_
   0.655  _00045_
   0.658  _01113_
   0.658  _01069_
   0.660  _00035_
   0.661  _01114_
   0.667  _00017_
   0.670  _01225_
   0.670  _00744_
   0.670  _00019_
   0.673  _01119_
   0.674  nmsg[492]
   0.680  _01143_
   0.688  _00801_

WORST STARTPOINTS: flop output nets with the lowest signoff slack (ns), with cell type and fanout:
   0.564  getdata_state[0]  (dfstp_2, fanout 3)
   0.574  br[29]  (dfstp_2, fanout 4)
   0.602  getdata_state[4]  (dfrtp_2, fanout 4)
   0.607  br[10]  (dfrtp_2, fanout 3)
   0.610  br[11]  (dfstp_2, fanout 3)
   0.638  br[12]  (dfrtp_2, fanout 4)
   0.647  round64[1]  (dfrtp_2, fanout 5)
   0.655  round64[3]  (dfrtp_2, fanout 6)
   0.656  br[25]  (dfstp_2, fanout 2)
   0.658  br[5]  (dfrtp_2, fanout 5)
   0.669  round64[0]  (dfrtp_2, fanout 7)
   0.670  getdata_state[3]  (dfrtp_2, fanout 3)
   0.673  round64[2]  (dfrtp_2, fanout 2)
   0.680  br[1]  (dfrtp_2, fanout 7)
   0.688  br[3]  (dfstp_4, fanout 7)
   0.692  br[9]  (dfstp_2, fanout 3)
   0.692  br[20]  (dfrtp_2, fanout 5)
   0.693  br[15]  (dfstp_2, fanout 4)
   0.700  br[13]  (dfstp_2, fanout 3)
   0.702  br[22]  (dfstp_2, fanout 3)

The endpoint and startpoint lists come from the run's per-net signoff dump: each net's slack is the worst slack of any
path through it. Unnamed nets (_NNNNN_, netNNN) were created by synthesis or by the flow's buffering and repair.

YOUR ROUND-3 REWRITE (THIS ROUND) AND WHAT HAPPENED TO IT. This is your one revision round.

Your reply, verbatim:
<<<
RATIONALE: At 10.60 ns two paths tie. The worst one is the lookahead pre=ar+M+T. There, getdata_state[0], a slow set flop, drives about 200 ar..dr mux selects through a buffer chain six deep (3.6 ns before the mux), then the CSA and the adder. Close behind is the step loop br->F->add->rotate->add->br/B_t (do_n[95]). Changes: every wide select now comes from registered decodes (st0, shift/hold, st4, last step, z0), split into logically distinct copies of at most about 96 loads each. The next-step message word now comes from the message register and data_i through registered one-hot word/chunk selects, instead of through the 512-bit next-message mux. The rotate uses a registered one-hot select. F is folded into the first adder's generate/propagate. br, pre and the F operands are stored XOR their reset constants, so they become fast reset flops instead of dfstp set flops. Cycle behaviour is unchanged.
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
reg [31:0]  ar, cr, dr, A, B, C, D;
reg [511:0] message;
reg [2:0]   getdata_state;
reg         generate_hash;
// step-loop state stored XOR its reset value (so all are reset-to-0 flops)
reg [31:0]  brx;        // br  ^ KB
reg [31:0]  prx;        // pre ^ KP ; pre == ar + M[nblock(round64)] + T(round64)
reg [31:0]  f1x, f0x;   // F(b=1)^KC, F(b=0)^KD for the current cr, dr, round
// registered decodes of the current state
reg [15:0]  rs;         // one-hot {round64[5:4],round64[1:0]} (rotate amount)
reg [15:0]  ws;         // one-hot word of the next pre: z0 ? 0 : nblock(round64+1)
reg [3:0]   wm;         // position of that word inside its 128-bit chunk
reg         wh;         // that word's chunk == getdata_state
reg         z0;         // round64 == 0 && !generate_hash
reg         s0a, s0b;   // ~st0, st0
reg         sha, shb, shc, shd;   // ~st0&gh, st0|~gh, st0|gh, ~st0&~gh
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

// 32-bit Kogge-Stone sum from per-bit generate gi and OR-propagate pi
function [31:0] ksgp;
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
  ksgp = (pi & ~gi) ^ {g[30:0], 1'b0};
end
endfunction

// ---------------- decoded / encoded state ----------------
wire        nt    = newtext_i;
wire [31:0] br    = brx ^ KB;
wire [31:0] pre   = prx ^ KP;
wire [31:0] fc1   = f1x ^ KC;
wire [31:0] fc0   = f0x ^ KD;
wire        st0   = (getdata_state == 3'd0);
wire        hg    = (round64 == 6'd63);      // hash_generated
wire        zero  = nt | z0;
wire [5:0]  r64_n = zero ? 6'd0 : round64 + 6'd1;

// ---------------- step datapath ----------------
// aux = pre + F(br,cr,dr), F folded into the generate/propagate terms
wire [31:0] ga  = (br & pre & fc1) | (~br & pre & fc0);
wire [31:0] pa  = (br & (pre | fc1)) | (~br & (pre | fc0));
wire [31:0] aux = ksgp(ga, pa);
reg  [31:0] rot;
integer k;
always @* begin
  rot = 32'd0;
  for (k = 0; k < 16; k = k + 1)
    rot = rot | ({32{rs[k]}} & rotf(aux, k));
end
wire [31:0] fo  = ksgp(br & rot, br | rot);     // func_out
wire [31:0] brB = ksgp(br & B, br | B);         // br + B, ready before rot
wire [31:0] bt  = ksgp(brB & rot, brB | rot);   // B_t = func_out + B
wire [31:0] At  = dr + A;
wire [31:0] Ct  = br + C;
wire [31:0] Dt  = cr + D;

// ---------------- ar..dr ----------------
wire [31:0] ar_n = ~s0a ? A : nt ? KA : sha ? dr : ar;
wire [31:0] bro  = s0b  ? B : nt ? KB : br;
wire        step = ~shb & ~nt;
wire [31:0] br_n = step ? fo : bro;
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
wire [31:0]  B_n  = fin ? bt : nt ? KB : B;
wire [31:0]  C_n  = fin ? Ct : nt ? KC : C;
wire [31:0]  D_n  = fin ? Dt : nt ? KD : D;
wire [127:0] do_n = {s4a ? At : 32'd0, s4a ? bt : 32'd0,
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
integer m;
always @* begin
  msel = 32'd0;
  for (m = 0; m < 16; m = m + 1)
    msel = msel | (message[511-32*m -: 32] & {32{ws[m]}});
  dsel = 32'd0;
  for (m = 0; m < 4; m = m + 1)
    dsel = dsel | (data_i[127-32*m -: 32] & {32{wm[m]}});
end
wire [31:0] w0    = (load_i & s0b) ? data_i[127:96] : message[511:480];
wire [31:0] wsq   = (load_i & wh) ? dsel : msel;
wire [31:0] wn    = nt ? w0 : wsq;
wire [31:0] tn    = zero ? T0 : tnf(round64);
wire [31:0] s3    = ar_n ^ wn ^ tn;
wire [31:0] c3    = {((ar_n & wn) | (ar_n & tn) | (wn & tn)), 1'b0} >> 1 << 1;
wire [31:0] c3s   = {c3[30:0], 1'b0};
wire [31:0] pre_n = ksgp(s3 & c3s, s3 | c3s);
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
wire [15:0] rs_n  = 16'd1 << {r64_n[5:4], r64_n[1:0]};

// ---------------- registers ----------------
always @(posedge clk or negedge reset)
begin
  if (!reset) begin
    ready_o <= 1'b0;
    data_o <= 128'd0;
    message <= 512'd0;
    ar <= KA; cr <= KC; dr <= KD;
    A <= KA;  B <= KB;  C <= KC;  D <= KD;
    brx <= 32'd0; prx <= 32'd0; f1x <= 32'd0; f0x <= 32'd0;
    getdata_state <= 3'd0;
    generate_hash <= 1'b0;
    round64 <= 6'd0;
    rs <= 16'h0001; ws <= 16'h0001; wm <= 4'h1; wh <= 1'b1; z0 <= 1'b1;
    s0a <= 1'b0; s0b <= 1'b1;
    sha <= 1'b0; shb <= 1'b1; shc <= 1'b1; shd <= 1'b0;
    s4a <= 1'b0; s4b <= 1'b1; fin <= 1'b0;
  end else begin
    ready_o <= rdy_n;
    data_o <= do_n;
    message <= nmsg;
    ar <= ar_n; cr <= cr_n; dr <= dr_n;
    A <= A_n;   B <= B_n;   C <= C_n;   D <= D_n;
    brx <= br_n ^ KB;
    prx <= pre_n ^ KP;
    f1x <= fc_n[63:32] ^ KC;
    f0x <= fc_n[31:0] ^ KD;
    getdata_state <= gs_n;
    generate_hash <= gh_n;
    round64 <= r64_n;
    rs <= rs_n; ws <= ws_n; wm <= wm_n; wh <= wh_n; z0 <= z0_n;
    s0a <= ~st0_n; s0b <= st0_n;
    sha <= ~st0_n & gh_n; shb <= st0_n | ~gh_n;
    shc <= st0_n | gh_n;  shd <= ~st0_n & ~gh_n;
    s4a <= st4_n; s4b <= ~st4_n;
    fin <= st4_n & (r64_n == 6'd63);
  end
end

endmodule
```
>>>

Equivalence gate on that file: FAIL; it was not run in the flow.
(a) Lockstep simulation against the original (outputs compared after each clock edge): first mismatch at cycle 67 after
reset. Original: ready_o=0, data_o=777777773258b3dc88888887a8ed3174. Yours: ready_o=0, data_o=777777779cfef3d388888887a8ed3174
(data_o[95:64] differs). The last 12 inputs before that cycle, oldest first (data_i in hex):
  input[-12]: reset=1 load=0 newtext=0 data=7fa5793ac6b341f93a1a4de20cbb7d18
  input[-11]: reset=1 load=0 newtext=0 data=3fab96aef5f9b4462a311ab31c213803
  input[-10]: reset=1 load=0 newtext=0 data=a70230368fef22b3ed1578c2a4110c5a
  input[-9]: reset=1 load=0 newtext=0 data=1171636d2d1cfe90a2bb8902369af7ad
  input[-8]: reset=1 load=0 newtext=0 data=c1662a9b46ae1fa45e9fb14621b81f78
  input[-7]: reset=1 load=0 newtext=0 data=c24ae7d0414a65db509e2a4fa65d624b
  input[-6]: reset=1 load=0 newtext=0 data=8a6357f37cb24ae64c3afb108b2ebc68
  input[-5]: reset=1 load=0 newtext=0 data=54b56cc66bb6df786f07cb6ec55cb10c
  input[-4]: reset=1 load=0 newtext=0 data=57656562cf4bacfb28db67754b09cee8
  input[-3]: reset=1 load=0 newtext=0 data=3db1123fd52aaf2128a5d74fc22e706f
  input[-2]: reset=1 load=1 newtext=0 data=47dc4077beb9d41f4248a31956ec494b
  input[-1]: reset=1 load=0 newtext=0 data=f50a661a2f33441259070b04510d9e38  [0 s]
(b) Digests through the documented protocol: message 0 (the empty message, one block): expected
d98c1dd404b2008f980980e97e42f8ec; yours 0c406fd11d098c97f7cb65545b70d08e. (The digest check stopped at this first failure.)
Interface and synthesizability: PASS. The bounded formal check was not run.

Return a complete md5.v under the same rules that meets a shorter clock than your round-2 rewrite. You may keep your
round-3 design and fix it, go back to your round-2 design and change it, or return something different; what is run is
exactly the file you return. It goes through the same gate, then the same flow.

REPLY FORMAT (exactly this, nothing before or after):
RATIONALE: <at most 150 words: what limits the clock in this report, and what you changed and why>
```verilog
<the complete modified md5.v>
```
