"""InputBridge wire protocol v2.

JSON lines over TCP. Pairing messages remain HMAC-signed v1 envelopes derived
from the QR token. All other messages use AES-256-GCM with a key derived from
the same token, providing confidentiality, integrity and replay metadata.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

PROTOCOL_VERSION = 2
LEGACY_PROTOCOL_VERSION = 1
AEAD_NAME = "AES-256-GCM"
DEFAULT_PORT = 27123
MAX_MESSAGE_BYTES = 64 * 1024
HEARTBEAT_INTERVAL = 2.0
HEARTBEAT_TIMEOUT = 15.0
CAPABILITIES_REFRESH_INTERVAL = 5.0
MAX_CLOCK_SKEW_MS = 30_000
IV_BYTES = 12

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


def derive_key(token: bytes) -> bytes:
    return hashlib.sha256(b"inputbridge-aead-v2" + token).digest()


def canonical_bytes(obj: Dict[str, Any]) -> bytes:
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sign(obj: Dict[str, Any], token: bytes) -> Dict[str, Any]:
    clone = dict(obj)
    clone.pop("sig", None)
    clone["sig"] = hmac.new(token, canonical_bytes(clone), hashlib.sha256).hexdigest()
    return clone


def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64d(text: str) -> bytes:
    if not isinstance(text, str) or not text:
        raise ProtocolError("invalid base64")
    try:
        return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
    except Exception as exc:
        raise ProtocolError("invalid base64") from exc


def _aad_bytes(meta: Dict[str, Any]) -> bytes:
    return canonical_bytes(dict(meta))


def make_message(
    msg_type: str,
    payload: Optional[Dict[str, Any]],
    session_id: str,
    seq: int,
    token: Optional[bytes],
) -> Dict[str, Any]:
    plain = token is None or msg_type in UNSIGNED_TYPES or msg_type in PAIRING_TYPES
    obj: Dict[str, Any] = {
        "v": LEGACY_PROTOCOL_VERSION if plain else PROTOCOL_VERSION,
        "type": msg_type,
        "sessionId": session_id,
        "seq": seq,
        "ts": int(time.time() * 1000),
        "payload": payload or {},
    }
    if plain:
        return sign(obj, token) if token is not None and msg_type in PAIRING_TYPES else obj

    meta = {
        "v": PROTOCOL_VERSION,
        "type": msg_type,
        "sessionId": session_id,
        "seq": seq,
        "ts": obj["ts"],
        "enc": AEAD_NAME,
    }
    iv = os.urandom(IV_BYTES)
    ciphertext = AESGCM(derive_key(token)).encrypt(
        iv, canonical_bytes(obj["payload"]), _aad_bytes(meta)
    )
    envelope = dict(meta)
    envelope["iv"] = _b64e(iv)
    envelope["ct"] = _b64e(ciphertext)
    return envelope


def encode_line(obj: Dict[str, Any]) -> bytes:
    data = canonical_bytes(obj) + b"\n"
    if len(data) > MAX_MESSAGE_BYTES:
        raise ProtocolError("message too large")
    return data


def _validate_inner(obj: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(obj, dict):
        raise ProtocolError("envelope must be an object")
    if not isinstance(obj.get("type"), str) or not obj["type"]:
        raise ProtocolError("missing message type")
    if not isinstance(obj.get("sessionId"), str) or not obj["sessionId"]:
        raise ProtocolError("missing session id")
    if not isinstance(obj.get("seq"), int) or obj["seq"] < 1:
        raise ProtocolError("invalid sequence")
    if not isinstance(obj.get("ts"), int):
        raise ProtocolError("invalid timestamp")
    if not isinstance(obj.get("payload"), dict):
        raise ProtocolError("invalid payload")
    return obj


def decode_line(data: bytes, token: Optional[bytes] = None) -> Dict[str, Any]:
    if len(data) > MAX_MESSAGE_BYTES:
        raise ProtocolError("message too large")
    try:
        obj = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError("invalid json") from exc
    if not isinstance(obj, dict):
        raise ProtocolError("envelope must be an object")
    version = obj.get("v")
    if version == LEGACY_PROTOCOL_VERSION:
        return _validate_inner(obj)
    if version != PROTOCOL_VERSION:
        raise ProtocolError("unsupported protocol version")
    if token is None:
        raise ProtocolError("encrypted message without key")
    if obj.get("enc") != AEAD_NAME:
        raise ProtocolError("unsupported cipher")
    meta = {
        "v": PROTOCOL_VERSION,
        "type": obj.get("type"),
        "sessionId": obj.get("sessionId"),
        "seq": obj.get("seq"),
        "ts": obj.get("ts"),
        "enc": AEAD_NAME,
    }
    _validate_inner({**meta, "payload": {}})
    iv = _b64d(obj.get("iv", ""))
    ciphertext = _b64d(obj.get("ct", ""))
    if len(iv) != IV_BYTES:
        raise ProtocolError("invalid iv")
    try:
        payload_bytes = AESGCM(derive_key(token)).decrypt(
            iv, ciphertext, _aad_bytes(meta)
        )
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception as exc:
        raise ProtocolError("decryption failed") from exc
    if not isinstance(payload, dict):
        raise ProtocolError("invalid payload")
    return _validate_inner(
        {
            "v": PROTOCOL_VERSION,
            "type": meta["type"],
            "sessionId": meta["sessionId"],
            "seq": meta["seq"],
            "ts": meta["ts"],
            "payload": payload,
        }
    )


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
    if obj.get("v") == PROTOCOL_VERSION:
        return VerificationResult(True)
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
