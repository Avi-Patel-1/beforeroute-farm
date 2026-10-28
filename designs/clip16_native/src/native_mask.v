module pipeline_dut(input clk,rst,input [22:0] x,output reg [8:0] y);
reg [22:0] q;
wire unsigned_mode=q[22];wire [1:0] mode=q[21:20];wire [3:0] sh=q[19:16];
wire signed [16:0] value={(!unsigned_mode)&q[15],q[15:0]};
wire signed [16:0] base=value >>> sh;
wire [16:0] mask=(17'd1 << sh)-17'd1;
wire [16:0] rem=value&mask;
wire [16:0] half=(17'd1 << sh) >> 1;
wire guard=(sh!=0)&((rem&half)!=0);
wire sticky=(sh!=0)&((rem&(half-17'd1))!=0);
wire up=(mode==0)?guard:((mode==1)?(guard&(sticky|base[0])):((mode==2)?1'b0:((guard|sticky)&~base[0])));
wire signed [17:0] wide_base={base[16],base};
wire signed [17:0] increment={17'b0,up};
wire u=unsigned_mode;
wire signed [17:0] rounded=wide_base+increment;
wire hi=u?(rounded>18'sd255):(rounded>18'sd127);
wire lo=(!u)&(rounded< -18'sd128);
wire [7:0] clipped=hi?(u?8'hff:8'h7f):(lo?8'h80:rounded[7:0]);
always @(posedge clk)if(rst)begin q<=0;y<=0;end else begin q<=x;y<={hi|lo,clipped};end
endmodule
