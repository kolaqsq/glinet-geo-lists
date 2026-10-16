#!/usr/bin/env python3
"""Entry point kept for the workflow and README; the code lives in the glgeo package."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from glgeo.__main__ import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
