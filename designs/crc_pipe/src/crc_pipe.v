// Original benchmark RTL: one reflected CRC-32 byte update per transaction.
// Polynomial: x^32 + x^26 + ... + 1, reflected representation 32'hEDB88320.
// Four register stages each advance two bits. This is not a packet controller:
// crc_i is an independent incoming CRC state for every accepted byte.
`timescale 1ns/1ps
module crc_pipe (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        enable,
    input  wire        valid_i,
    input  wire [31:0] crc_i,
    input  wire [7:0]  data_i,
    output reg         valid_o,
    output reg  [31:0] crc_o
);
    reg [31:0] crc_s0, crc_s1, crc_s2;
    reg [5:0] data_s0;
    reg [3:0] data_s1;
    reg [1:0] data_s2;
    reg valid_s0, valid_s1, valid_s2;

    // A two-bit combinational update. Delayed byte bits travel with each CRC.
    function [31:0] advance_two;
        input [31:0] state;
        input [1:0] bits;
        reg [31:0] mixed;
        reg [31:0] first;
        begin
            mixed = state ^ {30'b0, bits};
            first = (mixed >> 1) ^ (32'hEDB88320 & {32{mixed[0]}});
            advance_two = (first >> 1) ^ (32'hEDB88320 & {32{first[0]}});
        end
    endfunction

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            crc_s0 <= 32'b0;
            crc_s1 <= 32'b0;
            crc_s2 <= 32'b0;
            crc_o <= 32'b0;
            data_s0 <= 6'b0;
            data_s1 <= 4'b0;
            data_s2 <= 2'b0;
            valid_s0 <= 1'b0;
            valid_s1 <= 1'b0;
            valid_s2 <= 1'b0;
            valid_o <= 1'b0;
        end else if (enable) begin
            crc_s0 <= advance_two(crc_i, data_i[1:0]);
            data_s0 <= data_i[7:2];
            valid_s0 <= valid_i;

            crc_s1 <= advance_two(crc_s0, data_s0[1:0]);
            data_s1 <= data_s0[5:2];
            valid_s1 <= valid_s0;

            crc_s2 <= advance_two(crc_s1, data_s1[1:0]);
            data_s2 <= data_s1[3:2];
            valid_s2 <= valid_s1;

            crc_o <= advance_two(crc_s2, data_s2);
            valid_o <= valid_s2;
        end
    end
endmodule
