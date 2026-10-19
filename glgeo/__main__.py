import argparse
import os
import sys

from . import ROOT, __doc__ as DOC
from .errors import BuildError
from .pipeline import run
from .report import Report


def main(argv=None):
    ap = argparse.ArgumentParser(prog="glgeo", description=DOC, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=os.path.join(ROOT, "config.json"))
    ap.add_argument("--out", default=os.path.join(ROOT, "out"))
    ap.add_argument("--previous-index", help="path or URL of index.json from the last published build")
    ap.add_argument("--cache-dir", help="keep downloads here and reuse them: repeated builds run offline")
    ap.add_argument("--summary", help="append a Markdown summary of the build here, e.g. $GITHUB_STEP_SUMMARY")
    args = ap.parse_args(argv)
    report = Report()
    try:
        run(args.config, args.out, args.previous_index, args.cache_dir, report)
        return 0
    except BuildError as e:
        report.error(str(e))
        return 1
    except Exception as e:
        report.error(f"{type(e).__name__}: {e}")
        raise
    finally:
        if args.summary:
            report.write_summary(args.summary)


if __name__ == "__main__":
    sys.exit(main())
