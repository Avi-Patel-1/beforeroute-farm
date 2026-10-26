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


from typing import Optional  # noqa: E402
from librelane.config import Variable  # noqa: E402
from librelane.common import Path as LLPath  # noqa: E402
from librelane.steps.openroad import RepairDesignPostGRT  # noqa: E402


@Step.factory.register()
class TargetedRepairPostGRT(RepairDesignPostGRT):
    """Stock post-GRT design repair restricted to the nets listed in BR_FLAGGED_NETS_FILE
    (every other signal net is marked do-not-touch in the database for the duration of
    repair_design). With no file, behaves exactly like OpenROAD.RepairDesignPostGRT."""

    id = "BeforeRoute.TargetedRepairPostGRT"
    name = "Targeted Repair Design (Post-Global Routing)"

    config_vars = RepairDesignPostGRT.config_vars + [
        Variable(
            "BR_FLAGGED_NETS_FILE",
            Optional[LLPath],
            "JSON list of net names that repair_design may touch; all other signal nets are masked.",
        ),
        Variable(
            "BR_FLAGGED_TIERS_FILE",
            Optional[LLPath],
            "JSON {tiers:[{nets:[...], slew_pct, cap_pct}, ...]}: one masked repair pass per tier.",
        ),
        Variable(
            "BR_REPAIR_PASSES",
            int,
            "Masked repair_design passes per tier (a second pass cleans up violations the first pass created).",
            default=1,
        ),
    ]

    def get_script_path(self):
        return os.path.join(HERE, "targeted_repair.py")

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


@Step.factory.register()
class DumpNetsSignoff(DumpNetsPostGRT):
    """Same per-net dump, but on the final ODB with extracted (RCX) parasitics read for
    every corner: the signoff view, for estimate-versus-actual comparisons."""

    id = "BeforeRoute.DumpNetsSignoff"
    name = "Dump per-net values (signoff view)"

    config_vars = DumpNetsPostGRT.config_vars + [
        Variable("BR_MODE", Optional[str], "postgrt (default) or signoff"),
        Variable("BR_SPEF_MAP", Optional[LLPath], "JSON mapping corner wildcard -> SPEF path (signoff mode)"),
    ]
