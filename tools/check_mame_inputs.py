#!/usr/bin/env python3
"""Compatibility entry point; maintained implementation: tests/check_mame_inputs.py."""
import runpy
import sys
from pathlib import Path

_target = Path(__file__).resolve().parents[1] / "tests" / "check_mame_inputs.py"
sys.path.insert(0, str(_target.parent))
globals().update(runpy.run_path(str(_target), run_name=__name__))
