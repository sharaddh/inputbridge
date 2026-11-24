from __future__ import annotations

import socket
import threading
import time
import uuid
from typing import Any, Callable, Dict, Optional

from inputbridge.protocol import (
    CAPABILITIES_REFRESH_INTERVAL,
    DEFAULT_PORT,
    HEARTBEAT_INTERVAL,
    HEARTBEAT_TIMEOUT,
    ProtocolError,
    SequenceTracker,
    decode_line,
    encode_line,
    make_message,
    verify,
)


class BridgeServer:
    def __init__(
        self,
        port: int = DEFAULT_PORT,
        token_hex: str = "",
        device_id: str = "",
        device_name: str = "Windows laptop",
        on_status: Optional[Callable[[str], None]] = None,
        on_message: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_state: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.port = port
        self.device_id = device_id or str(uuid.uuid4())
        self.device_name = device_name
        self.on_status = on_status
        self.on_message = on_message
        self.on_state = on_state
        self._token = self._decode_token(token_hex)
        self._server_sock: Optional[socket.socket] = None
        self._sock: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._lock = threading.RLock()
        self._seq = 0
        self._session_id = ""
        self._paired = False
        self._last_rx = 0.0
        self._last_caps_request = 0.0
        self._rx_tracker = SequenceTracker()

    @property
    def connected(self) -> bool:
        return self._sock is not None and self._thread is not None and self._thread.is_alive()

    @property
    def paired(self) -> bool:
        return self._paired

    def token_hex(self) -> str:
        return self._token.hex() if self._token else ""

    def set_token(self, token_hex: str) -> None:
        self.stop()
        self._token = self._decode_token(token_hex)

    def start(self) -> None:
        if not self._token:
            self._status("No QR token configured")
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="bridge-server", daemon=True)
        self._thread.start()
        self._status(f"Waiting for QR scan on port {self.port}...")
        self._set_state("listening")

    def stop(self) -> None:
        self._stop.set()
        sock = self._sock
        self._sock = None
        if sock:
            self._close_socket(sock)
        server = self._server_sock
        self._server_sock = None
        if server:
            self._close_socket(server)
        if self._thread:
            self._thread.join(timeout=2)
        self._thread = None
        self._paired = False
        self._set_state("disconnected")

    def send(self, msg_type: str, payload: Optional[Dict[str, Any]] = None) -> bool:
        if not self._paired or not self._token:
            return False
        return self._send_raw(
            make_message(msg_type, payload, self._session_id, self._next_seq(), self._token)
        )

    def _decode_token(self, token_hex: str) -> bytes:
        try:
            token = bytes.fromhex(token_hex.strip())
        except ValueError:
            return b""
        return token if len(token) in (16, 32) else b""

    def _close_socket(self, sock: socket.socket) -> None:
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            sock.close()
        except OSError:
            pass

    def _next_seq(self) -> int:
        with self._lock:
            self._seq += 1
            return self._seq

    def _send_raw(self, obj: Dict[str, Any]) -> bool:
        sock = self._sock
        if not sock:
            return False
        try:
            with self._lock:
                sock.sendall(encode_line(obj))
            return True
        except (OSError, ProtocolError) as exc:
            self._status(f"Send failed: {exc}")
            return False

    def _status(self, text: str) -> None:
        if self.on_status:
            try:
                self.on_status(text)
            except Exception:
                pass

    def _set_state(self, state: str) -> None:
        if self.on_state:
            try:
                self.on_state(state)
            except Exception:
                pass

    def _run(self) -> None:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
                server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server.bind(("", self.port))
                server.listen(1)
                server.settimeout(0.5)
                self._server_sock = server
                while not self._stop.is_set():
                    try:
                        client, _ = server.accept()
                    except socket.timeout:
                        continue
                    except OSError:
                        break
                    self._handle_client(client)
        except Exception as exc:
            self._status(f"Server error: {exc}")
        finally:
            self._server_sock = None
            self._sock = None
            self._paired = False
            self._set_state("disconnected")
            self._stop.set()

    def _handle_client(self, client: socket.socket) -> None:
        with client:
            client.settimeout(0.5)
            self._sock = client
            self._paired = False
            self._session_id = ""
            self._seq = 0
            self._last_rx = time.monotonic()
            self._rx_tracker.reset()
            last_tx = time.monotonic()
            self._last_caps_request = time.monotonic()
            try:
                while not self._stop.is_set():
                    try:
                        chunk = client.recv(4096)
                        if not chunk:
                            break
                        buffer = getattr(self, "_buffer", b"") + chunk
                        while b"\n" in buffer:
                            line, buffer = buffer.split(b"\n", 1)
                            if line.strip():
                                self._handle_line(line)
                        self._buffer = buffer
                    except socket.timeout:
                        pass
                    except OSError:
                        break

                    now = time.monotonic()
                    if self._paired and now - last_tx >= HEARTBEAT_INTERVAL:
                        if self.send("heartbeat", {}):
                            last_tx = now
                    if self._paired and now - self._last_caps_request >= CAPABILITIES_REFRESH_INTERVAL:
                        if self.send("capabilities_request", {"deviceId": self.device_id}):
                            self._last_caps_request = now
                    if self._paired and now - self._last_rx > HEARTBEAT_TIMEOUT:
                        self._status("Heartbeat timeout")
                        break
            finally:
                self._buffer = b""
                self._sock = None
                self._paired = False
                self._set_state("disconnected")
                self._status("Phone disconnected")

    def _handle_line(self, line: bytes) -> None:
        try:
            obj = decode_line(line, self._token if self._paired else None)
        except ProtocolError as exc:
            self._status(f"Bad message: {exc}")
            return
        self._last_rx = time.monotonic()
        msg_type = obj["type"]
        payload = obj["payload"]

        if msg_type == "pair_request":
            if self._paired or not self._token:
                self._send_error("Already paired or no QR token")
                return
            result = verify(obj, self._token, obj["sessionId"], min_seq=1)
            if not result.ok:
                self._status(f"QR pairing rejected: {result.reason}")
                self._send_error("Bad QR pairing signature")
                return
            self._session_id = obj["sessionId"]
            self._seq = 0
            self._rx_tracker.reset(self._session_id)
            self._paired = True
            self._status(f"Paired with {payload.get('deviceName', 'phone')}")
            self._set_state("connected")
            self.send(
                "pair_approval",
                {"token": self.token_hex(), "deviceName": self.device_name},
            )
            self.send("capabilities_request", {"deviceId": self.device_id})
            self._last_caps_request = time.monotonic()
            return

        if not self._paired:
            self._send_error("Scan the QR code first")
            return
        result = verify(obj, self._token, min_seq=1)
        if not result.ok:
            self._status(f"Rejected message: {result.reason}")
            return
        if not self._rx_tracker.check(obj).ok:
            self._status("Rejected replayed message")
            return

        if msg_type == "error":
            self._status(f"Phone error: {payload.get('message', 'unknown')}")
        if msg_type == "heartbeat":
            return
        if msg_type == "disconnect":
            self._stop.set()
            return
        if self.on_message:
            try:
                self.on_message(obj)
            except Exception:
                pass

    def _send_error(self, message: str) -> None:
        self._send_raw(make_message("error", {"message": message}, "server", 1, None))


def local_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"
    finally:
        sock.close()
