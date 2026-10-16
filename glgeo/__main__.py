import argparse
import os
import sys

from . import ROOT, __doc__ as DOC
from .errors import BuildError
from .log import log
from .pipeline import run


def main(argv=None):
    ap = argparse.ArgumentParser(prog="glgeo", description=DOC, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=os.path.join(ROOT, "config.json"))
    ap.add_argument("--out", default=os.path.join(ROOT, "out"))
    ap.add_argument("--previous-index", help="path or URL of index.json from the last published build")
    ap.add_argument("--cache-dir", help="keep downloads here and reuse them: repeated builds run offline")
    args = ap.parse_args(argv)
    try:
        run(args.config, args.out, args.previous_index, args.cache_dir)
    except BuildError as e:
        log(f"ERROR: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
