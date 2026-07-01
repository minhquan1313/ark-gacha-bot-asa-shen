"""Shen GBot launcher UI package."""

import sys

from source.launcher.components import helper_window
from source.launcher.utils import deposit_helper_capture, system

sys.modules.setdefault(__name__ + ".deposit_helper_capture", deposit_helper_capture)
sys.modules.setdefault(__name__ + ".helper_window", helper_window)
sys.modules.setdefault(__name__ + ".system", system)
