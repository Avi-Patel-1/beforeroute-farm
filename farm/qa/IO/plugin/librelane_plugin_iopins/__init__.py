"""LibreLane plugin for IO1 (the I/O pin-placement test): one step, IOPins.ApplyPinPlan.

Discovered by LibreLane (librelane/plugins.py) when farm/qa/IO/plugin is on PYTHONPATH; only arm runs set that.
The step is inserted right after OpenROAD.IOPlacement through the run config's meta.substituting_steps
({"+OpenROAD.IOPlacement": "IOPins.ApplyPinPlan"}). With IOPINS_PLAN unset it does nothing.
"""
import os
from typing import List, Optional, Tuple

from librelane.common import Path
from librelane.config import Variable
from librelane.logging import info
from librelane.state import State
from librelane.steps import Step
from librelane.steps.common_variables import io_layer_variables
from librelane.steps.odb import OdbpyStep

__version__ = "1.0.0"
IO_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))


@Step.factory.register()
class ApplyPinPlan(OdbpyStep):
    """Moves the port groups named in IOPINS_PLAN to legal slots on their planned die-edge segment (iolib.place_groups);
    every other pin keeps the position OpenROAD's I/O placer gave it."""

    id = "IOPins.ApplyPinPlan"
    name = "Apply I/O pin plan (IO1)"

    config_vars = io_layer_variables + [
        Variable(
            "IOPINS_PLAN",
            Optional[Path],
            "JSON pin plan (farm/qa/IO/iolib.py load_plan). Unset: the step is skipped.",
        ),
    ]

    def get_script_path(self):
        return os.path.join(IO_DIR, "apply_pin_plan.py")

    def get_command(self) -> List[str]:
        return super().get_command() + [
            "--plan", str(self.config["IOPINS_PLAN"]),
            "--hor-layer", self.config["IO_PIN_H_LAYER"],
            "--ver-layer", self.config["IO_PIN_V_LAYER"],
            "--hor-width-mult", str(self.config["IO_PIN_H_THICKNESS_MULT"]),
            "--ver-width-mult", str(self.config["IO_PIN_V_THICKNESS_MULT"]),
            "--report", os.path.join(self.step_dir, "pins_applied.json"),
        ]

    def run(self, state_in: State, **kwargs) -> Tuple[dict, dict]:
        if self.config["IOPINS_PLAN"] is None:
            info(f"IOPINS_PLAN is not set; skipping '{self.id}'.")
            return {}, {}
        return super().run(state_in, **kwargs)
