"""`boxoffice serve` — the UI, backed by real runs.

A stdlib HTTP server so the demo has no extra dependency. It serves
`boxoffice/ui/index.html` and two endpoints:

  GET  /api/health  -> transport, snapshot size, whether Gemini/ADK is importable
  POST /api/ask     -> runs the REAL pipeline and returns the answer, the exact
                       SQL, the grounding trace, the guardrail audit trail and
                       the run id

The UI calls these. When it cannot reach them (opened as a file:// page) it says
so on screen and falls back to a recorded transcript that is explicitly labelled
as recorded. Nothing in the UI is allowed to look live when it is not.
"""

from __future__ import annotations

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import offline_engine
from .config import settings

UI_DIR = Path(__file__).resolve().parent / "ui"
_ask_lock = threading.Lock()


def _health() -> dict:
    info = {
        "ok": True,
        "transport": settings.transport,
        "endpoint": None if settings.is_offline else settings.clickhouse_url,
        "database": settings.clickhouse_database,
        "allowed_tables": sorted(settings.allowed_table_set),
        "max_rows": settings.max_rows,
    }
    if settings.is_offline:
        info["snapshot"] = offline_engine.snapshot_stats()
    try:
        import google.adk  # noqa: F401
        info["adk_importable"] = True
    except Exception:
        info["adk_importable"] = False
    return info


class Handler(BaseHTTPRequestHandler):
    server_version = "boxoffice/1.0"

    def log_message(self, fmt, *args):  # quieter demo console
        print(f"[boxoffice] {self.address_string()} {fmt % args}")

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, payload: dict) -> None:
        self._send(code, json.dumps(payload, default=str).encode(), "application/json")

    def do_GET(self):  # noqa: N802
        if self.path.startswith("/api/health"):
            self._json(200, _health())
            return
        if self.path.startswith("/api/options"):
            from .projection import options
            try:
                with _ask_lock:
                    self._json(200, options())
            except Exception as exc:  # noqa: BLE001
                self._json(500, {"error": f"{exc.__class__.__name__}: {exc}"})
            return
        path = self.path.split("?", 1)[0]
        name = "index.html" if path in ("/", "") else path.lstrip("/")
        target = (UI_DIR / name).resolve()
        if not str(target).startswith(str(UI_DIR)) or not target.is_file():
            self._json(404, {"error": "not found"})
            return
        ctype = "text/html; charset=utf-8" if target.suffix == ".html" else "text/plain; charset=utf-8"
        self._send(200, target.read_bytes(), ctype)

    def do_POST(self):  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path not in ("/api/ask", "/api/project", "/api/narrate"):
            self._json(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length > 8192:
            self._json(413, {"error": "payload too large"})
            return
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._json(400, {"error": "invalid JSON"})
            return

        if path == "/api/project":
            genre = str(body.get("genre") or "").strip()
            year = body.get("year")
            if not genre or year is None:
                self._json(400, {"error": "genre and year are required"})
                return
            from .projection import project
            try:
                with _ask_lock:
                    out = project(genre, int(year))
            except Exception as exc:  # noqa: BLE001
                self._json(500, {"error": f"{exc.__class__.__name__}: {exc}"})
                return
            self._json(200, out)
            return

        if path == "/api/narrate":
            genre = str(body.get("genre") or "").strip()
            year = body.get("year")
            if not genre or year is None:
                self._json(400, {"error": "genre and year are required"})
                return
            title = str(body.get("title") or "")
            plot = str(body.get("plot") or "")
            from .projection import project
            from .narrate import narrate
            try:
                with _ask_lock:
                    proj = project(genre, int(year))
                    story = narrate(proj, title, plot)
            except Exception as exc:  # noqa: BLE001
                self._json(500, {"error": f"{exc.__class__.__name__}: {exc}"})
                return
            self._json(200, {"scenario": proj.get("scenario"), "abstained": proj.get("abstained"),
                             **story})
            return

        question = str(body.get("question") or "").strip()
        if not question:
            self._json(400, {"error": "question is required"})
            return

        from .main import ask

        try:
            # One run at a time: this is a demo server, and serialising keeps the
            # ActionLimiter budget legible on screen.
            with _ask_lock:
                out = asyncio.run(ask(question, use_llm=bool(body.get("use_llm"))))
        except Exception as exc:  # noqa: BLE001
            self._json(500, {"error": f"{exc.__class__.__name__}: {exc}"})
            return
        self._json(200, out)


def serve(port: int = 8765) -> None:
    # Cloud Run (and most PaaS) inject the listen port via $PORT and require a
    # bind on 0.0.0.0. Honour $PORT unless the caller passed an explicit
    # non-default --port on the command line, and bind all interfaces when a
    # host is provided so the container is reachable. Locally, with no $PORT and
    # no override, this stays on 127.0.0.1:8765 exactly as before.
    import os

    env_port = os.getenv("PORT")
    host = os.getenv("HOST", "0.0.0.0" if env_port else "127.0.0.1")
    if port == 8765 and env_port:
        try:
            port = int(env_port)
        except ValueError:
            pass
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"BoxOffice Brain UI on http://{host}:{port}  (transport={settings.transport})")
    print("Ask in the browser and every panel is filled from a real run.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()
