"""InputBridge wire protocol v1.

JSON lines over TCP. Every message after pairing is authenticated with an
HMAC-SHA256 tag over the canonical JSON bytes (keys sorted, no whitespace).
The protocol provides authentication and replay protection but no encryption;
use it only on a trusted local network (see docs/SECURITY.md).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

PROTOCOL_VERSION = 1
DEFAULT_PORT = 27123
MAX_MESSAGE_BYTES = 64 * 1024
HEARTBEAT_INTERVAL = 2.0
HEARTBEAT_TIMEOUT = 15.0
CAPABILITIES_REFRESH_INTERVAL = 5.0
MAX_CLOCK_SKEW_MS = 30_000

UNSIGNED_TYPES = {"hello", "error"}
PAIRING_TYPES = {"pair_request", "pair_approval"}


class ProtocolError(ValueError):
    pass


def pairing_token(code: str) -> bytes:
    return hashlib.sha256(("inputbridge-pair:" + code.strip()).encode("utf-8")).digest()


def new_session_id() -> str:
    return secrets.token_hex(16)


def new_pairing_secret() -> str:
    return secrets.token_hex(32)


def canonical_bytes(obj: Dict[str, Any]) -> bytes:
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sign(obj: Dict[str, Any], token: bytes) -> Dict[str, Any]:
    clone = dict(obj)
    clone.pop("sig", None)
    clone["sig"] = hmac.new(token, canonical_bytes(clone), hashlib.sha256).hexdigest()
    return clone


def make_message(
    msg_type: str,
    payload: Optional[Dict[str, Any]],
    session_id: str,
    seq: int,
    token: Optional[bytes],
) -> Dict[str, Any]:
    obj: Dict[str, Any] = {
        "v": PROTOCOL_VERSION,
        "type": msg_type,
        "sessionId": session_id,
        "seq": seq,
        "ts": int(time.time() * 1000),
        "payload": payload or {},
    }
    if token is None or msg_type in UNSIGNED_TYPES:
        return obj
    return sign(obj, token)


def encode_line(obj: Dict[str, Any]) -> bytes:
    data = canonical_bytes(obj) + b"\n"
    if len(data) > MAX_MESSAGE_BYTES:
        raise ProtocolError("message too large")
    return data


def decode_line(data: bytes) -> Dict[str, Any]:
    if len(data) > MAX_MESSAGE_BYTES:
        raise ProtocolError("message too large")
    try:
        obj = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError("invalid json") from exc
    if not isinstance(obj, dict):
        raise ProtocolError("envelope must be an object")
    if obj.get("v") != PROTOCOL_VERSION:
        raise ProtocolError("unsupported protocol version")
    if not isinstance(obj.get("type"), str):
        raise ProtocolError("missing message type")
    if not isinstance(obj.get("sessionId"), str):
        raise ProtocolError("missing session id")
    if not isinstance(obj.get("seq"), int) or obj["seq"] < 1:
        raise ProtocolError("invalid sequence")
    if not isinstance(obj.get("ts"), int):
        raise ProtocolError("invalid timestamp")
    if not isinstance(obj.get("payload"), dict):
        raise ProtocolError("invalid payload")
    return obj


@dataclass
class VerificationResult:
    ok: bool
    reason: str = ""


def verify(
    obj: Dict[str, Any],
    token: Optional[bytes],
    expected_session: Optional[str] = None,
    min_seq: int = 1,
) -> VerificationResult:
    msg_type = obj["type"]
    if msg_type in UNSIGNED_TYPES:
        return VerificationResult(True)
    if token is None:
        return VerificationResult(False, "not paired")
    if expected_session is not None and obj["sessionId"] != expected_session:
        return VerificationResult(False, "session mismatch")
    if obj["seq"] < min_seq:
        return VerificationResult(False, "stale sequence")
    if abs(int(time.time() * 1000) - obj["ts"]) > MAX_CLOCK_SKEW_MS:
        return VerificationResult(False, "stale timestamp")
    supplied = obj.get("sig")
    if not isinstance(supplied, str):
        return VerificationResult(False, "missing signature")
    clone = dict(obj)
    clone.pop("sig", None)
    expected = hmac.new(token, canonical_bytes(clone), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(supplied, expected):
        return VerificationResult(False, "bad signature")
    return VerificationResult(True)


class SequenceTracker:
    """Rejects duplicate/out-of-order messages within one session."""

    def __init__(self) -> None:
        self.session_id = ""
        self.last_seq = 0

    def reset(self, session_id: str = "") -> None:
        self.session_id = session_id
        self.last_seq = 0

    def check(self, obj: Dict[str, Any]) -> VerificationResult:
        sid = obj["sessionId"]
        seq = obj["seq"]
        if self.session_id and sid != self.session_id:
            return VerificationResult(False, "session mismatch")
        if seq <= self.last_seq:
            return VerificationResult(False, "duplicate or stale sequence")
        self.session_id = sid
        self.last_seq = seq
        return VerificationResult(True)
