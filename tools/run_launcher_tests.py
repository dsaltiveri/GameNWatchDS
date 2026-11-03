#!/usr/bin/env python3
"""Compatibility entry point; maintained implementation: tests/run_launcher_tests.py."""
import runpy
import sys
from pathlib import Path

_target = Path(__file__).resolve().parents[1] / "tests" / "run_launcher_tests.py"
sys.path.insert(0, str(_target.parent))
globals().update(runpy.run_path(str(_target), run_name=__name__))
