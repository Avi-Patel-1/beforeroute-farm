module pipeline_dut(input clk,rst,input [22:0] x,output reg [8:0] y);
wire neg=(~x[22])&x[15];
wire [3:0] sh=x[19:16];
wire [1:0] mode=x[21:20];
wire [16:0] p0={x[15:0],1'b0};
wire [16:0] p1=sh[0]?{neg,p0[16:1]}:p0;
wire z1=sh[0]&p0[0];
wire [16:0] p2=sh[1]?{{2{neg}},p1[16:2]}:p1;
wire z2=z1|(sh[1]&(|p1[1:0]));
wire [16:0] p3=sh[2]?{{4{neg}},p2[16:4]}:p2;
wire z3=z2|(sh[2]&(|p2[3:0]));
wire [16:0] p4=sh[3]?{{8{neg}},p3[16:8]}:p3;
wire sticky=z3|(sh[3]&(|p3[7:0]));
wire [15:0] base=p4[16:1];
wire guard=p4[0];
wire up=(mode==2'b00)?guard:
        (mode==2'b01)?(guard&(sticky|base[0])):
        (mode==2'b10)?1'b0:((guard|sticky)&~base[0]);
wire far_overflow=neg?(~(&base[15:8])):(|base[15:8]);
reg [7:0] qlow;
reg qup,qfar,qneg,qunsigned;
wire [8:0] rounded_low={1'b0,qlow}+{8'b0,qup};
wire near_overflow=qneg?((~rounded_low[7])&(~rounded_low[8])):
                       (qunsigned?rounded_low[8]:(rounded_low[7]|rounded_low[8]));
wire saturation=qfar|near_overflow;
wire [7:0] limit=qneg?8'h80:(qunsigned?8'hff:8'h7f);
wire [7:0] result=saturation?limit:rounded_low[7:0];
always @(posedge clk) begin
  if(rst) begin
    qlow<=8'b0;
    qup<=1'b0;
    qfar<=1'b0;
    qneg<=1'b0;
    qunsigned<=1'b0;
    y<=9'b0;
  end else begin
    qlow<=base[7:0];
    qup<=up;
    qfar<=far_overflow;
    qneg<=neg;
    qunsigned<=x[22];
    y<={saturation,result};
  end
end
endmodule