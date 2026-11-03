"""Small helpers for identifiers, timestamps and amounts.

Same logic as tools/generate_examples.py (UUIDv7, timestamp format, SIMENC),
copied on purpose: apps never share code (CONTRIBUTING.md, "one app, one folder").
"""
import base64
import json
import os
import re
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
BIC_RE = re.compile(r"^[A-Z0-9]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?$")
# INTERPRETATION C10: always UTC ("Z") or an explicit offset; local time without offset is rejected.
DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?(Z|[+-]\d{2}:\d{2})$")
CENT = Decimal("0.01")


def now_ts() -> str:
    """UTC timestamp with milliseconds, e.g. 2026-11-02T10:15:00.360Z (INTERPRETATION C10)."""
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def uuid4() -> str:
    return str(uuid.uuid4())


def uuid7() -> str:
    """UUID version 7: 48-bit Unix time in ms + random bits (INTERPRETATION C5, D2-8)."""
    ms = time.time_ns() // 1_000_000
    r = bytearray(os.urandom(10))
    b = ms.to_bytes(6, "big") + bytes([0x70 | (r[0] & 0x0F), r[1], 0x80 | (r[2] & 0x3F)]) + bytes(r[3:10])
    h = b.hex()
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def money(value) -> Decimal:
    return Decimal(str(value)).quantize(CENT)


def amount_obj(value) -> dict:
    """I3 amount: string with dot decimal (INTERPRETATION C6)."""
    return {"currency": "EUR", "amount": f"{money(value):.2f}"}


def fmt(value) -> str:
    return f"{money(value):.2f}"


def sim_encrypt(obj: dict) -> str:
    """SIMULATED encryption (INTERPRETATION C7): "SIMENC:" + base64 of the JSON.
    Deliberately not secure, so the observer can show the content (ADR 0003)."""
    raw = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode()
    return "SIMENC:" + base64.b64encode(raw).decode()


def sim_decrypt(blob: str) -> dict:
    """Counterpart of sim_encrypt. Raises ValueError if the blob is not SIMENC."""
    if not blob.startswith("SIMENC:"):
        raise ValueError("not a SIMENC blob")
    return json.loads(base64.b64decode(blob[len("SIMENC:"):], validate=True))
