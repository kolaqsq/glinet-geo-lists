"""Minimal protobuf wire-format reader, enough for v2ray .dat files."""

from ..errors import BuildError


def varint(buf, pos):
    result = shift = 0
    while True:
        b = buf[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if b < 0x80:
            return result, pos
        shift += 7


def fields(buf, start, end):
    """Yield (field number, wire type, value) of a protobuf message in buf[start:end].
    value is an int for varints and a (start, end) span for length-delimited fields."""
    pos = start
    while pos < end:
        key, pos = varint(buf, pos)
        num, wire = key >> 3, key & 7
        if wire == 0:
            val, pos = varint(buf, pos)
        elif wire == 2:
            n, pos = varint(buf, pos)
            val = (pos, pos + n)
            pos += n
        elif wire in (1, 5):
            val = None
            pos += 8 if wire == 1 else 4
        else:
            raise BuildError(f"protobuf: unsupported wire type {wire}")
        yield num, wire, val
    if pos != end:
        raise BuildError("protobuf: truncated message")
