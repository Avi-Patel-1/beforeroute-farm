RATIONALE: The limiting path goes from one register to another through the 33-bit r_dividend - r_divisor[31:0] subtraction. Yosys's default Brent-Kung carry tree computes the borrow diff[32] last, at its deepest level. The "can subtract" decision then fans out to more than 32 dividend-mux selects, and that is roughly 14 cells. Changes: (1) The subtractor is now an explicit Sklansky parallel-prefix tree, so the borrow and the sum bits come out after about 6 levels. (2) The test r_divisor[62:32]==0 is computed one clock ahead into a register (r_uz), so the select logic settles early. (3) The dividend next-state logic is restructured so the late borrow drives only the last mux. (4) r_c uses the equality test r_dividend==r_divisor[31:0] in place of diff==0. (5) The three negations use a log-depth prefix-OR. Everything is cycle-for-cycle identical; I expect the area to grow by about 5%.
```verilog
////////////////////////////////////////////////////////////////////////////////
//
// Filename:	div.v  (zipdiv, timing-restructured)
//
// Project:	Zip CPU -- a small, lightweight, RISC CPU soft core
//
// Creator:	Dan Gisselquist, Ph.D.
//		Gisselquist Technology, LLC
//
// Copyright (C) 2015-2018, Gisselquist Technology, LLC
//
// License:	GPL, v3, as defined and found on www.gnu.org,
//		http://www.gnu.org/licenses/gpl.html
//
////////////////////////////////////////////////////////////////////////////////
`default_nettype	none
module	zipdiv(i_clk, i_reset, i_wr, i_signed, i_numerator, i_denominator,
		o_busy, o_valid, o_err, o_quotient, o_flags);
	parameter		BW=32, LGBW = 5;
	input	wire		i_clk, i_reset;
	input	wire		i_wr, i_signed;
	input	wire [(BW-1):0]	i_numerator, i_denominator;
	output	reg		o_busy, o_valid, o_err;
	output	reg [(BW-1):0]	o_quotient;
	output	wire	[3:0]	o_flags;

	// {borrow, a-b}: a + ~b + 1 with a Sklansky parallel-prefix carry tree
	function [BW:0] fast_sub;
		input	[BW-1:0]	a, b;
		reg	[BW-1:0]	x, gg, pp;
		integer			k, i, j;
		begin
			x  = ~(a ^ b);
			gg = a & ~b;
			gg[0] = a[0] | ~b[0];	// carry-in of one folded in
			pp = x;
			for (k = 0; k < LGBW; k = k + 1)
				for (i = 0; i < BW; i = i + 1)
					if (((i >> k) & 1) == 1)
					begin
						j = ((i >> (k+1)) << (k+1)) + (1 << k) - 1;
						gg[i] = gg[i] | (pp[i] & gg[j]);
						pp[i] = pp[i] & pp[j];
					end
			fast_sub[0] = ~x[0];
			for (i = 1; i < BW; i = i + 1)
				fast_sub[i] = x[i] ^ gg[i-1];
			fast_sub[BW] = ~gg[BW-1];
		end
	endfunction

	// Two's complement negation: bit i = a[i] ^ |a[i-1:0] (prefix-OR)
	function [BW-1:0] fast_neg;
		input	[BW-1:0]	a;
		reg	[BW-1:0]	y;
		integer			k, i, j;
		begin
			y = a;
			for (k = 0; k < LGBW; k = k + 1)
				for (i = 0; i < BW; i = i + 1)
					if (((i >> k) & 1) == 1)
					begin
						j = ((i >> (k+1)) << (k+1)) + (1 << k) - 1;
						y[i] = y[i] | y[j];
					end
			fast_neg[0] = a[0];
			for (i = 1; i < BW; i = i + 1)
				fast_neg[i] = a[i] ^ y[i-1];
		end
	endfunction

	reg			r_busy;
	reg	[(2*BW-2):0]	r_divisor;
	reg	[(BW-1):0]	r_dividend;
	reg		r_sign, pre_sign, r_z, r_c, last_bit;
	reg	[(LGBW-1):0]	r_bit;
	reg	zero_divisor;
	// r_uz always equals (r_divisor[(2*BW-2):BW] == 0)
	reg	r_uz;

	wire	[(BW):0]	diff;
	assign	diff = fast_sub(r_dividend, r_divisor[(BW-1):0]);
	wire	w_q;
	assign	w_q = (r_uz)&&(!diff[BW]);

	always @(posedge i_clk)
		if (i_reset)
			r_busy <= 1'b0;
		else if (i_wr)
			r_busy <= 1'b1;
		else if ((last_bit)||(zero_divisor))
			r_busy <= 1'b0;

	always @(posedge i_clk)
		if (i_reset)
			o_busy <= 1'b0;
		else if (i_wr)
			o_busy <= 1'b1;
		else if (((last_bit)&&(!r_sign))||(zero_divisor))
			o_busy <= 1'b0;
		else if (!r_busy)
			o_busy <= 1'b0;

	always @(posedge i_clk)
		if (i_reset)
			zero_divisor <= 1'b0;
		else if (i_wr)
			zero_divisor <= (i_denominator == 0);
		else if (!r_busy)
			zero_divisor <= 1'b0;

	always @(posedge i_clk)
	if (i_reset)
		o_valid <= 1'b0;
	else if (r_busy)
	begin
		if ((last_bit)||(zero_divisor))
			o_valid <= (zero_divisor)||(!r_sign);
	end else if (r_sign)
	begin
		o_valid <= (!zero_divisor);
	end else
		o_valid <= 1'b0;

	always @(posedge i_clk)
	if (i_reset)
		o_err <= 1'b0;
	else if (o_valid)
		o_err <= 1'b0;
	else if (((r_busy)||(r_sign))&&(zero_divisor))
		o_err <= 1'b1;
	else
		o_err <= 1'b0;

	always @(posedge i_clk)
	if (i_reset)
		r_bit <= 0;
	else if ((r_busy)&&(!pre_sign))
		r_bit <= r_bit + 1'b1;
	else
		r_bit <= 0;

	always @(posedge i_clk)
	if (i_reset)
		last_bit <= 1'b0;
	else if (r_busy)
		last_bit <= (r_bit == {(LGBW){1'b1}}-1'b1);
	else
		last_bit <= 1'b0;

	always @(posedge i_clk)
	if (i_reset)
		pre_sign <= 1'b0;
	else if (i_wr)
		pre_sign <= (i_signed)&&((i_numerator[BW-1])||(i_denominator[BW-1]));
	else
		pre_sign <= 1'b0;

	// Upper-divisor-zero flag, computed one clock ahead
	always @(posedge i_clk)
	if (i_reset)
		r_uz <= 1'b1;
	else if (pre_sign)
	begin
		if (r_divisor[(2*BW-2)])
			r_uz <= &r_divisor[(2*BW-2):(BW-1)];
	end else if (r_busy)
		r_uz <= (r_divisor[(2*BW-2):(BW+1)] == 0);
	else
		r_uz <= (i_denominator[(BW-1):1] == 0);

	always @(posedge i_clk)
	if (i_reset)
		r_z <= 1'b0;
	else if ((r_busy)&&(w_q))
		r_z <= 1'b0;
	else if (i_wr)
		r_z <= 1'b1;

	// r_dividend: the late borrow only drives the final mux
	reg	[(BW-1):0]	div_other;
	always @(*)
	if (i_reset)
		div_other = 0;
	else if (pre_sign)
		div_other = (r_dividend[BW-1]) ? fast_neg(r_dividend) : r_dividend;
	else if (!r_busy)
		div_other = i_numerator;
	else
		div_other = r_dividend;

	wire			sub_ok;
	assign	sub_ok = (!i_reset)&&(!pre_sign)&&(r_busy)&&(r_uz);
	wire	[(BW-1):0]	div_sub;
	assign	div_sub = (sub_ok) ? diff[(BW-1):0] : div_other;

	always @(posedge i_clk)
		r_dividend <= (diff[BW]) ? div_other : div_sub;

	always @(posedge i_clk)
	if (i_reset)
		r_divisor <= 0;
	else if (pre_sign)
	begin
		if (r_divisor[(2*BW-2)])
			r_divisor[(2*BW-2):(BW-1)]
				<= fast_neg(r_divisor[(2*BW-2):(BW-1)]);
	end else if (r_busy)
		r_divisor <= { 1'b0, r_divisor[(2*BW-2):1] };
	else
		r_divisor <= {  i_denominator, {(BW-1){1'b0}} };

	always @(posedge i_clk)
	if (i_reset)
		r_sign <= 1'b0;
	else if (pre_sign)
		r_sign <= ((r_divisor[(2*BW-2)])^(r_dividend[(BW-1)]));
	else if (r_busy)
		r_sign <= (r_sign)&&(!zero_divisor);
	else
		r_sign <= 1'b0;

	always @(posedge i_clk)
	if (i_reset)
		o_quotient <= 0;
	else if (r_busy)
		o_quotient <= { o_quotient[(BW-2):0], w_q };
	else if (r_sign)
		o_quotient <= fast_neg(o_quotient);
	else
		o_quotient <= 0;

	// diff == 0 exactly when r_dividend == r_divisor[BW-1:0]
	always @(posedge i_clk)
	if (i_reset)
		r_c <= 1'b0;
	else
		r_c <= (r_busy)&&((r_dividend == r_divisor[(BW-1):0])
				||(r_dividend == 0));

	wire	w_n;
	assign w_n = o_quotient[(BW-1)];

	assign o_flags = { 1'b0, w_n, r_c, r_z };

endmodule
```