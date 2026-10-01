#!/usr/bin/env python3
"""Compatibility entry point: python3 eval.py runs the classification baseline."""

import sys
from eval_lab.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["run", *sys.argv[1:]]))
