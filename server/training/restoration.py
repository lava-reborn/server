"""Bounded diagnostics of unavailable checkpoints; never executed as a preset."""
import copy
import hashlib
import json


def archive(value):
    try:
        encoded = json.dumps(value, ensure_ascii=False, default=str, allow_nan=False)
    except (ValueError, TypeError):
        value = repr(value)[:4096]
        encoded = json.dumps(value, ensure_ascii=False)
    if len(encoded) <= 4096:
        return copy.deepcopy(value)
    return dict(truncated=True, sha256=hashlib.sha256(encoded.encode('utf-8')).hexdigest(),
                preview=encoded[:2048])
