from __future__ import annotations

import http.client
import socket
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from server import Handler, run_qcad  # noqa: E402
from http.server import ThreadingHTTPServer  # noqa: E402


def test_handler_has_a_socket_timeout() -> None:
    # Défense contre une connexion lente/muette (slowloris) : sans ce timeout,
    # un client qui n'envoie jamais le corps annoncé bloque un thread pour
    # toujours (rfile.read(length) attend indéfiniment).
    assert Handler.timeout is not None
    assert 0 < Handler.timeout <= 120


def test_passthrough_rejects_too_short_body() -> None:
    import pytest

    with pytest.raises(RuntimeError):
        run_qcad(b"short")


def _start_server() -> tuple[ThreadingHTTPServer, threading.Thread]:
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, thread


def test_invalid_content_length_header_returns_400_not_a_crash() -> None:
    httpd, thread = _start_server()
    try:
        host, port = httpd.server_address[0], httpd.server_address[1]
        with socket.create_connection((host, port), timeout=5) as sock:
            request = (
                b"POST /normalize HTTP/1.1\r\n"
                b"Host: localhost\r\n"
                b"Content-Length: not-a-number\r\n"
                b"Connection: close\r\n"
                b"\r\n"
            )
            sock.sendall(request)
            response = b""
            sock.settimeout(5)
            try:
                while True:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    response += chunk
            except TimeoutError:
                pass
        assert response.startswith(b"HTTP/1.0 400") or response.startswith(b"HTTP/1.1 400")
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def test_oversized_content_length_is_rejected() -> None:
    httpd, thread = _start_server()
    try:
        host, port = httpd.server_address[0], httpd.server_address[1]
        conn = http.client.HTTPConnection(host, port, timeout=5)
        try:
            conn.request("POST", "/normalize", body=b"", headers={"Content-Length": str(10**9)})
            resp = conn.getresponse()
            assert resp.status == 400
        finally:
            conn.close()
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)
