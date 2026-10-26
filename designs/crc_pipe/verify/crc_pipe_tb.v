`timescale 1ns/1ps

module crc_pipe_tb;
    reg clk = 1'b0;
    reg rst_n = 1'b1;
    reg enable = 1'b0;
    reg valid_i = 1'b0;
    reg [31:0] crc_i = 32'b0;
    reg [7:0] data_i = 8'b0;
    wire valid_o;
    wire [31:0] crc_o;
    crc_pipe dut (.*);
    always #5 clk = ~clk;

    reg [31:0] expected [0:3];
    reg [3:0] expected_valid = 4'b0;
    reg [31:0] previous_crc;
    reg previous_valid;
    reg [31:0] random_state = 32'h6c8e9cf5;
    reg [31:0] random_crc;
    reg [31:0] chain_crc;
    reg [71:0] message = "123456789";
    integer cycles = 0;
    integer accepted = 0;
    integer checked = 0;
    integer discarded_by_reset = 0;
    integer stalls = 0;
    integer reset_checks = 0;
    integer i, j;

    // Independent software-style reference: consume one data bit at a time.
    // It shares the standard polynomial, but no DUT function or stage logic.
    function [31:0] reference_byte;
        input [31:0] crc;
        input [7:0] data;
        reg [31:0] state;
        reg feedback;
        integer bit_index;
        begin
            state = crc;
            for (bit_index = 0; bit_index < 8; bit_index = bit_index + 1) begin
                feedback = state[0] ^ data[bit_index];
                state = {1'b0, state[31:1]};
                if (feedback)
                    state = state ^ 32'hEDB88320;
            end
            reference_byte = state;
        end
    endfunction

    task tick;
        input do_enable;
        input do_valid;
        input [31:0] input_crc;
        input [7:0] input_data;
        begin
            @(negedge clk);
            previous_crc = crc_o;
            previous_valid = valid_o;
            enable = do_enable;
            valid_i = do_valid;
            crc_i = input_crc;
            data_i = input_data;
            @(posedge clk);
            cycles = cycles + 1;
            if (do_enable) begin
                for (j = 3; j > 0; j = j - 1)
                    expected[j] = expected[j - 1];
                expected[0] = reference_byte(input_crc, input_data);
                expected_valid = {expected_valid[2:0], do_valid};
                if (do_valid)
                    accepted = accepted + 1;
            end else begin
                stalls = stalls + 1;
            end
            #1;
            if (valid_o !== expected_valid[3])
                $fatal(1, "valid/latency mismatch at cycle %0d", cycles);
            if (!do_enable && ((crc_o !== previous_crc) || (valid_o !== previous_valid)))
                $fatal(1, "enable=0 failed to freeze output at cycle %0d", cycles);
            if (do_enable && expected_valid[3]) begin
                checked = checked + 1;
                if (crc_o !== expected[3])
                    $fatal(1, "CRC mismatch cycle=%0d expected=%08x actual=%08x", cycles, expected[3], crc_o);
            end
        end
    endtask

    task pulse_reset;
        begin
            @(negedge clk);
            // In-flight stages 0..2 are discarded. Stage 3 was already checked.
            for (j = 0; j < 3; j = j + 1)
                if (expected_valid[j])
                    discarded_by_reset = discarded_by_reset + 1;
            rst_n = 1'b0;
            enable = 1'b0;
            valid_i = 1'b0;
            expected_valid = 4'b0;
            for (j = 0; j < 4; j = j + 1)
                expected[j] = 32'b0;
            // Check asynchronous reset before another rising clock edge.
            #1;
            if ((crc_o !== 32'b0) || (valid_o !== 1'b0))
                $fatal(1, "asynchronous reset failed");
            reset_checks = reset_checks + 1;
            @(negedge clk);
            rst_n = 1'b1;
        end
    endtask

    initial begin
        pulse_reset();
        // Published CRC-32/ISO-HDLC check value; exercises state chaining too.
        chain_crc = 32'hFFFFFFFF;
        for (i = 0; i < 9; i = i + 1) begin
            tick(1, 1, chain_crc, message[71 - 8*i -: 8]);
            tick(1, 0, 0, 0);
            tick(1, 0, 0, 0);
            tick(1, 0, 0, 0);
            chain_crc = crc_o;
        end
        if ((chain_crc ^ 32'hFFFFFFFF) !== 32'hCBF43926)
            $fatal(1, "known 123456789 CRC check failed: %08x", chain_crc ^ 32'hFFFFFFFF);

        // Full throughput, exhaustive byte values, alternating edge CRC states.
        for (i = 0; i < 256; i = i + 1)
            tick(1, 1, i[0] ? 32'hFFFFFFFF : 32'h00000000, i[7:0]);
        // Two resets intentionally flush outstanding work.
        pulse_reset();
        for (i = 0; i < 1200; i = i + 1) begin
            random_state = 1664525 * random_state + 1013904223;
            random_crc = random_state;
            random_state = 1664525 * random_state + 1013904223;
            tick(random_state[30:29] != 0, random_state[20:19] != 0, random_crc, random_state[15:8]);
            if (i == 613)
                pulse_reset();
        end
        // Flush all still-valid work, then verify bubbles and a stalled output.
        repeat (4) tick(1, 0, 0, 0);
        repeat (8) tick(0, 1, 32'hBAD0C0DE, 8'hFF);
        if (valid_o !== 0)
            $fatal(1, "valid remained asserted after pipeline flush");
        if (accepted != checked + discarded_by_reset)
            $fatal(1, "transaction accounting mismatch: accepted=%0d checked=%0d discarded=%0d", accepted, checked, discarded_by_reset);
        if (checked < 500 || stalls < 100 || reset_checks != 3)
            $fatal(1, "insufficient directed/random coverage");
        $display("PASS crc_pipe: cycles=%0d accepted=%0d checked=%0d discarded_by_reset=%0d stalls=%0d resets=%0d known_crc=CBF43926", cycles, accepted, checked, discarded_by_reset, stalls, reset_checks);
        $finish;
    end

    initial begin
        #100000;
        $fatal(1, "testbench timeout");
    end
endmodule
