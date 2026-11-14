"""Bounded diagnostics of unavailable checkpoints; never executed as a preset."""
import copy
import hashlib
import json
import base64
import zlib


def archive(value):
    try:
        encoded = json.dumps(value, ensure_ascii=False, default=str, allow_nan=False)
    except (ValueError, TypeError):
        value = repr(value)[:4096]
        encoded = json.dumps(value, ensure_ascii=False)
    if len(encoded) <= 4096:
        return copy.deepcopy(value)
    compressed = base64.b64encode(zlib.compress(encoded.encode('utf-8'))).decode('ascii')
    digest = hashlib.sha256(encoded.encode('utf-8')).hexdigest()
    if len(compressed) <= 4096:
        return dict(encoding='zlib+base64', data=compressed, sha256=digest)
    return dict(truncated=True, sha256=digest,
                preview=encoded[:2048])
