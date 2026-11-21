#!/usr/bin/env python3
"""Mock Android TCP server (JSON lines) for testing Windows client without Android device."""
from __future__ import annotations

import json
import socket
import sys


def main() -> int:
    host = "0.0.0.0"
    port = 27123
    if len(sys.argv) >= 2:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print("Usage: python mock_android_server.py [port]")
            return 2
    print(f"[mock-android] Listening on {host}:{port} (Ctrl+C to stop)")
    with socket.create_server((host, port), reuse_port=True) as srv:
        while True:
            conn, addr = srv.accept()
            print(f"[mock-android] Connected: {addr}")
            with conn:
                f = conn.makefile("rwb")
                # hello
                hello = {"protocolVersion": 1, "type": "hello", "role": "android-mock"}
                f.write((json.dumps(hello) + "\n").encode())
                f.flush()
                for line in f:
                    text = line.decode("utf-8", errors="replace").strip()
                    if not text:
                        continue
                    print(f"[mock-android] recv: {text}")
                    try:
                        obj = json.loads(text)
                        ack = {"protocolVersion": 1, "type": "ack", "echoType": obj.get("type")}
                    except Exception:
                        ack = {"type": "error", "message": "invalid json"}
                    f.write((json.dumps(ack) + "\n").encode())
                    f.flush()
            print("[mock-android] Disconnected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
