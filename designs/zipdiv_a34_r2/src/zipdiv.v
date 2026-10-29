////////////////////////////////////////////////////////////////////////////////
//
// Filename:	div.v  (zipdiv, timing-restructured, rev 2)
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

	// {borrow, a-b} = a + ~b + 1.  Sklansky prefix tree on
	// (generate, transmit); the XNOR propagate only feeds the sum bits.
	function [BW:0] fast_sub;
		input	[BW-1:0]	a, b;
		reg	[BW-1:0]	x, gg, pp;
		integer			k, i, j;
		begin
			x  = ~(a ^ b);
			gg = a & ~b;
			pp = a | ~b;
			gg[0] = a[0] | ~b[0];	// carry-in of one folded in
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

	// One-hot state selects (all early: registers and i_reset)
	wire	s_ps, s_run, s_idle;
	assign	s_ps   = (!i_reset)&&(pre_sign);
	assign	s_run  = (!i_reset)&&(!pre_sign)&&(r_busy);
	assign	s_idle = (!i_reset)&&(!pre_sign)&&(!r_busy);

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

	// r_dividend: flat one-hot AND-OR legs, the late borrow drives
	// only the final mux
	wire	[(BW-1):0]	w_nneg;
	assign	w_nneg = fast_neg(r_dividend);
	wire	d_neg, d_keep, d_keepns, d_sub;
	assign	d_neg    = (s_ps)&&(r_dividend[BW-1]);
	assign	d_keep   = ((s_ps)&&(!r_dividend[BW-1]))||(s_run);
	assign	d_keepns = ((s_ps)&&(!r_dividend[BW-1]))||((s_run)&&(!r_uz));
	assign	d_sub    = (s_run)&&(r_uz);
	wire	[(BW-1):0]	div_a, div_b;
	assign	div_a = ({(BW){d_neg}} & w_nneg)
			| ({(BW){d_keep}} & r_dividend)
			| ({(BW){s_idle}} & i_numerator);
	assign	div_b = ({(BW){d_neg}} & w_nneg)
			| ({(BW){d_keepns}} & r_dividend)
			| ({(BW){s_idle}} & i_numerator)
			| ({(BW){d_sub}} & diff[(BW-1):0]);

	always @(posedge i_clk)
		r_dividend <= (diff[BW]) ? div_a : div_b;

	// r_divisor: flat one-hot AND-OR next state
	wire	[(BW-1):0]	w_dneg;
	assign	w_dneg = fast_neg(r_divisor[(2*BW-2):(BW-1)]);
	wire	v_neg, v_keep;
	assign	v_neg  = (s_ps)&&(r_divisor[2*BW-2]);
	assign	v_keep = (s_ps)&&(!r_divisor[2*BW-2]);

	always @(posedge i_clk)
	begin
		r_divisor[(2*BW-2):(BW-1)] <= ({(BW){v_neg}} & w_dneg)
			| ({(BW){v_keep}} & r_divisor[(2*BW-2):(BW-1)])
			| ({(BW){s_run}} & { 1'b0, r_divisor[(2*BW-2):BW] })
			| ({(BW){s_idle}} & i_denominator);
		r_divisor[(BW-2):0] <= ({(BW-1){s_ps}} & r_divisor[(BW-2):0])
			| ({(BW-1){s_run}} & r_divisor[(BW-1):1]);
	end

	always @(posedge i_clk)
	if (i_reset)
		r_sign <= 1'b0;
	else if (pre_sign)
		r_sign <= ((r_divisor[(2*BW-2)])^(r_dividend[(BW-1)]));
	else if (r_busy)
		r_sign <= (r_sign)&&(!zero_divisor);
	else
		r_sign <= 1'b0;

	// o_quotient: flat one-hot AND-OR next state
	wire	q_sh, q_ng;
	assign	q_sh = (!i_reset)&&(r_busy);
	assign	q_ng = (!i_reset)&&(!r_busy)&&(r_sign);

	always @(posedge i_clk)
		o_quotient <= ({(BW){q_sh}} & { o_quotient[(BW-2):0], w_q })
				| ({(BW){q_ng}} & fast_neg(o_quotient));

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
