import hashlib
import json


def fingerprint(content):
    raw = json.dumps(
        {"items": content["items"], "mode": content["mode"]},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode()).hexdigest()
