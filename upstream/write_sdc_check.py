#############################################################################
##
## BSD 3-Clause License (as the rest of tools/AutoTuner)
##
#############################################################################
"""Unit test for write_sdc (tools/AutoTuner/src/autotuner/utils.py): a tuned clock period must not rescale the I/O
budget, and _SDC_IO_DELAY must reach SDCs that budget I/O as clk_period * clk_io_pct.

Run from the ORFS root: python3 -m unittest tools/AutoTuner/test/write_sdc_check.py
"""
import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from autotuner.utils import SDC_TEMPLATE, write_sdc  # noqa: E402


def number(sdc, name):
    return float(re.search(rf"^set {name}\s+(\S+)\s*$", sdc, flags=re.M).group(1))


class WriteSdcCheck(unittest.TestCase):
    def write(self, variables, sdc=SDC_TEMPLATE):
        with tempfile.TemporaryDirectory() as d:
            with open(write_sdc(variables, d, sdc, "constraint.sdc")) as f:
                return f.read()

    def io_delay(self, sdc):
        return number(sdc, "clk_period") * number(sdc, "clk_io_pct")

    def test_tuned_period_holds_io_delay(self):
        for period in (500, 1000, 1999.5, 4000):
            out = self.write({"CLK_PERIOD": period})
            self.assertEqual(number(out, "clk_period"), period)
            self.assertAlmostEqual(self.io_delay(out), 2000 * 0.2, places=4)

    def test_period_at_reference_is_byte_identical(self):
        self.assertEqual(self.write({"CLK_PERIOD": 2000}), SDC_TEMPLATE)

    def test_io_delay_sets_clk_io_pct(self):
        out = self.write({"CLK_PERIOD": 500, "IO_DELAY": 100})
        self.assertAlmostEqual(number(out, "clk_io_pct"), 0.2)
        self.assertAlmostEqual(self.io_delay(out), 100, places=4)
        out = self.write({"IO_DELAY": 300})
        self.assertAlmostEqual(self.io_delay(out), 300, places=4)
        self.assertNotIn("set io_delay", out)

    def test_sdc_with_io_delay_variable_unchanged(self):
        sdc = "set clk_period 1000\nset io_delay 50\nset_input_delay $io_delay -clock clk [all_inputs]\n"
        out = self.write({"IO_DELAY": 80}, sdc)
        self.assertEqual(number(out, "io_delay"), 80)

    def test_sdc_without_clk_io_pct_unchanged(self):
        sdc = "set clk_period 910\nset input_delay 0.46\ncreate_clock -period $clk_period [get_ports clk]\n"
        out = self.write({"CLK_PERIOD": 800}, sdc)
        self.assertEqual(out, sdc.replace("set clk_period 910", "set clk_period 800"))


if __name__ == "__main__":
    unittest.main()
