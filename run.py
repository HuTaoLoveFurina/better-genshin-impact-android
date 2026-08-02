#!/usr/bin/env python3
"""Convenience entry point, equivalent to `python -m bgia.cli`."""

import sys

from bgia.cli import main

if __name__ == "__main__":
    sys.exit(main())
