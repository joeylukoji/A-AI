#!/usr/bin/env python3
"""Sidecar CAD : POST /normalize (DXF in, DXF out). QCAD si dispo, sinon LibreCAD / passthrough."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

MAX_BODY = 8 * 1024 * 1024
QCAD_BIN = os.environ.get("QCAD_BIN", "qcad")
SCRIPT = Path(os.environ.get("QCAD_SCRIPT", "/app/normalize_dxf.js"))
PORT = int(os.environ.get("QCAD_PORT", "9090"))


def run_qcad(src: bytes) -> bytes:
    bin_name = Path(QCAD_BIN).name.lower()
    if "qcad" not in bin_name or not SCRIPT.is_file():
        # LibreCAD n'a pas le même CLI ; le DXF Go AC1015 est déjà éditable.
        if len(src) < 16:
            raise RuntimeError("DXF vide")
        return src
    with tempfile.TemporaryDirectory(prefix="aai-qcad-") as tmp:
        tmp_path = Path(tmp)
        infile = tmp_path / "in.dxf"
        outfile = tmp_path / "out.dxf"
        infile.write_bytes(src)
        cmd = [
            QCAD_BIN,
            "-no-gui",
            "-allow-multiple-instances",
            "-autostart",
            str(SCRIPT),
            "--",
            str(infile),
            str(outfile),
        ]
        if shutil.which("xvfb-run") and os.environ.get("QT_QPA_PLATFORM") != "offscreen":
            cmd = ["xvfb-run", "-a", "-s", "-screen 0 1024x768x24"] + cmd
        subprocess.run(
            cmd,
            check=True,
            timeout=25,
            cwd=tmp,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        out = outfile.read_bytes()
        if len(out) < 16:
            raise RuntimeError("DXF QCAD vide")
        return out


class Handler(BaseHTTPRequestHandler):
    # Borne le temps passé à lire les en-têtes / le corps d'une requête lente
    # ou muette (type slowloris) : socketserver applique ce timeout à la
    # connexion et lève socket.timeout, qui coupe proprement la requête.
    timeout = 30

    def log_message(self, fmt: str, *args) -> None:
        print(f"qcad {self.address_string()} {fmt % args}")

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        tool = "qcad" if "qcad" in Path(QCAD_BIN).name.lower() else "librecad"
        if path == "/healthz":
            body = f'{{"status":"ok","tool":"{tool}"}}\n'.encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path in {"/", "/qcad", "/librecad"}:
            html = f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><title>A-AI CAD</title></head>
<body style="font-family:sans-serif;max-width:40rem;margin:2rem auto;line-height:1.5">
<h1>Pas d’interface QCAD ici</h1>
<p>Le port <code>9090</code> est un service interne ({tool}). Il n’ouvre pas le logiciel CAD.</p>
<ol>
<li>Va sur <a href="http://localhost:8080">http://localhost:8080</a></li>
<li>Ouvre ton projet</li>
<li>Clique <strong>Exporter DXF pour QCAD / LibreCAD</strong></li>
<li>Ouvre le fichier <code>plan.dxf</code> avec LibreCAD ou QCAD Community <em>sur ton PC</em></li>
</ol>
<p><a href="/healthz">healthz</a></p>
</body></html>
"""
            body = html.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

    def do_POST(self) -> None:
        if self.path.rstrip("/") != "/normalize":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            self.send_error(400, "invalid Content-Length")
            return
        if length <= 0 or length > MAX_BODY:
            self.send_error(400, "invalid Content-Length")
            return
        raw = self.rfile.read(length)
        try:
            out = run_qcad(raw)
        except Exception as exc:
            msg = f"qcad normalize failed: {exc}\n".encode()
            self.send_response(502)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(msg)))
            self.end_headers()
            self.wfile.write(msg)
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/dxf")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)


def main() -> None:
    httpd = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"qcad sidecar :{PORT} bin={QCAD_BIN}")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
