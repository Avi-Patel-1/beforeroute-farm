"""BeforeRoute custom LibreLane steps.

DumpNetsPostGRT: re-creates the flow's post-global-route view (same nine-corner
libraries, same layer RC, same global route, same parasitic estimation that
`OpenROAD.RepairDesignPostGRT` would see) and dumps one row per signal net with
topology and the tool's own estimated slews / caps / limits. It changes nothing
and writes no views.
"""
from __future__ import annotations

import os

from librelane.steps import Step
from librelane.steps.openroad import ResizerStep

HERE = os.path.dirname(os.path.abspath(__file__))


@Step.factory.register()
class DumpNetsPostGRT(ResizerStep):
    id = "BeforeRoute.DumpNetsPostGRT"
    name = "Dump per-net features (post-GRT view)"
    long_name = "BeforeRoute per-net feature dump at the post-global-route repair point"

    outputs = []  # read-only: no views are produced

    def get_script_path(self):
        return os.path.join(HERE, "dump_nets.py")

    def get_command(self):
        metrics_path = os.path.join(self.step_dir, "or_metrics_out.json")
        return [
            self.get_openroad_path(),
            "-exit",
            "-no_splash",
            "-metrics",
            metrics_path,
            "-python",
            self.get_script_path(),
        ]
