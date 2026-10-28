module pipeline_dut(input clk,rst,input [22:0] x,output reg [8:0] y);
wire unsigned_mode=x[22];wire [1:0] mode=x[21:20];wire [3:0] sh=x[19:16];
wire signed [16:0] value={(!unsigned_mode)&x[15],x[15:0]};
wire signed [32:0] packed_value={value,16'b0};
wire signed [32:0] shifted=packed_value >>> sh;
wire signed [16:0] base=shifted[32:16];
wire guard=shifted[15];wire sticky=|shifted[14:0];
wire up=(mode==0)?guard:((mode==1)?(guard&(sticky|base[0])):((mode==2)?1'b0:((guard|sticky)&~base[0])));
wire hi=unsigned_mode?(base>17'sd255):(base>17'sd127);
wire lo=(!unsigned_mode)&(base< -17'sd128);
wire at_hi=unsigned_mode?(base==17'sd255):(base==17'sd127);
wire rescued_low=(!unsigned_mode)&(base== -17'sd129)&up;
wire saturation=hi|(at_hi&up)|(lo&~rescued_low);
wire [7:0] clipped=hi?(unsigned_mode?8'hff:8'h7f):(lo?8'h80:base[7:0]);
wire allowed_up=up&~hi&~lo&~at_hi;
reg [7:0] qclip;reg qup,qsat;
always @(posedge clk)if(rst)begin qclip<=0;qup<=0;qsat<=0;y<=0;end
else begin qclip<=clipped;qup<=allowed_up;qsat<=saturation;y<={qsat,(qclip+{7'b0,qup})};end
endmodule
