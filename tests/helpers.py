import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(ROOT, "tests", "fixtures")
sys.path.insert(0, ROOT)
# Tests must not print GitHub annotations: in Actions they would show up on the run page as real warnings.
os.environ.pop("GITHUB_ACTIONS", None)


def pb(num, value):
    """Encode one protobuf field: int -> varint, bytes -> length-delimited."""
    def varint(n):
        out = b""
        while True:
            b, n = n & 0x7F, n >> 7
            out += bytes([b | (0x80 if n else 0)])
            if not n:
                return out
    if isinstance(value, int):
        return varint(num << 3) + varint(value)
    return varint(num << 3 | 2) + varint(len(value)) + value
