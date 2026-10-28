module pipeline_dut(input clk,rst,input [22:0] x,output reg [8:0] y);
wire unsigned_mode=x[22];wire [1:0] mode=x[21:20];wire [3:0] sh=x[19:16];
wire signed [16:0] value={(!unsigned_mode)&x[15],x[15:0]};
wire signed [17:0] p0={value,1'b0};wire z0=0;
wire signed [17:0] p1=sh[0]?(p0 >>> 1):p0;
wire z1=z0|(sh[0]&(|p0[0:0]));
wire signed [17:0] p2=sh[1]?(p1 >>> 2):p1;
wire z2=z1|(sh[1]&(|p1[1:0]));
wire signed [17:0] p3=sh[2]?(p2 >>> 4):p2;
wire z3=z2|(sh[2]&(|p2[3:0]));
wire signed [17:0] p4=sh[3]?(p3 >>> 8):p3;
wire z4=z3|(sh[3]&(|p3[7:0]));
wire signed [16:0] base=p4[17:1];wire guard=p4[0];wire sticky=z4;
wire up=(mode==0)?guard:((mode==1)?(guard&(sticky|base[0])):((mode==2)?1'b0:((guard|sticky)&~base[0])));
reg signed [16:0] qbase;reg qup,qunsigned;
wire signed [17:0] wide_base={qbase[16],qbase};
wire signed [17:0] increment={17'b0,qup};
wire u=qunsigned;
wire signed [17:0] rounded=wide_base+increment;
wire hi=u?(rounded>18'sd255):(rounded>18'sd127);
wire lo=(!u)&(rounded< -18'sd128);
wire [7:0] clipped=hi?(u?8'hff:8'h7f):(lo?8'h80:rounded[7:0]);
always @(posedge clk)if(rst)begin qbase<=0;qup<=0;qunsigned<=0;y<=0;end else begin qbase<=base;qup<=up;qunsigned<=unsigned_mode;y<={hi|lo,clipped};end
endmodule
