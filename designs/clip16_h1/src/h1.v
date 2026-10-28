module pipeline_dut(input clk,rst,input [22:0] x,output reg [8:0] y);
wire u=x[22];
wire [3:0] sh=x[19:16];
wire signed [17:0] p0={((~u)&x[15]),x[15:0],1'b0};
wire signed [17:0] p1=sh[0]?(p0 >>> 1):p0;
wire signed [17:0] p2=sh[1]?(p1 >>> 2):p1;
wire z2=sh[1]&(|p1[1:0]);
wire signed [17:0] p3=sh[2]?(p2 >>> 4):p2;
wire z3=z2|(sh[2]&(|p2[3:0]));
wire signed [17:0] p4=sh[3]?(p3 >>> 8):p3;
wire z4=z3|(sh[3]&(|p3[7:0]));
wire neg=p4[17];
wire upper_bad=neg?(~(&p4[17:9])):(|p4[17:9]);
reg [7:0] qlow;
reg qneg,qbad,qguard,qsticky,qu;
reg [1:0] qmode;
wire up=(qmode==2'd0)?qguard:
        (qmode==2'd1)?(qguard&(qsticky|qlow[0])):
        (qmode==2'd2)?1'b0:((qguard|qsticky)&~qlow[0]);
wire [8:0] rounded={1'b0,qlow}+{8'b0,up};
wire low_over=qneg&(qbad|((~rounded[8])&(~rounded[7])));
wire high_over=(~qneg)&(qbad|rounded[8]|((~qu)&rounded[7]));
wire [7:0] result=low_over?8'h80:
                         high_over?(qu?8'hff:8'h7f):rounded[7:0];
always @(posedge clk) begin
  if(rst) begin
    qlow<=8'd0;
    qneg<=1'b0;
    qbad<=1'b0;
    qguard<=1'b0;
    qsticky<=1'b0;
    qu<=1'b0;
    qmode<=2'd0;
    y<=9'd0;
  end else begin
    qlow<=p4[8:1];
    qneg<=neg;
    qbad<=upper_bad;
    qguard<=p4[0];
    qsticky<=z4;
    qu<=u;
    qmode<=x[21:20];
    y<={low_over|high_over,result};
  end
end
endmodule