#!/usr/bin/env python3
"""便捷入口，等价于 python -m bgia.cli"""

import sys

from bgia.cli import main

if __name__ == "__main__":
    sys.exit(main())
