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

THE GOAL. Change the RTL so that, under the same setting, the block meets a shorter clock period. Your rewrite will be run
at 16.05 ns and then at successively tighter clocks (each time at the clock the previous run's timing says it can meet)
until a run fails; the result is the tightest clock that passes. Standard-cell area may grow by at most 15%.

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

REPLY FORMAT (exactly this, nothing before or after):
RATIONALE: <at most 150 words: what limits the clock in this report, and what you changed and why>
```verilog
<the complete modified md5.v>
```
