from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from ...frontend import read_dashboard_asset, render_dashboard_html
from .runtime import MonitorAppState, create_run, list_runs, load_snapshot, read_artifact, read_run_log


def serve_dashboard(app_state: MonitorAppState, host: str, port: int) -> None:
    server = ThreadingHTTPServer((host, port), build_handler(app_state))
    print(f"Dashboard listening on http://{host}:{port}")
    print(f"Runtime root: {app_state.runtime_root}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def build_handler(app_state: MonitorAppState) -> type[BaseHTTPRequestHandler]:
    class DashboardHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/favicon.ico":
                self.send_response(HTTPStatus.NO_CONTENT)
                self.end_headers()
                return
            if parsed.path.startswith("/static/"):
                asset_name = parsed.path.removeprefix("/static/")
                try:
                    body, content_type = read_dashboard_asset(asset_name)
                except FileNotFoundError:
                    self.send_error(HTTPStatus.NOT_FOUND, "Static asset not found")
                    return
                self._send_text(body, content_type)
                return
            if parsed.path in {"/", "/index.html"}:
                self._send_text(render_dashboard_html(app_state.initial_run_id), "text/html; charset=utf-8")
                return
            if parsed.path == "/api/runs":
                self._send_json({"runs": list_runs(app_state.runtime_root)})
                return
            if parsed.path.startswith("/api/runs/") and parsed.path.endswith("/snapshot"):
                run_id = parsed.path.split("/")[3]
                snapshot = load_snapshot(app_state.runtime_root, run_id)
                if snapshot is None:
                    self.send_error(HTTPStatus.NOT_FOUND, "Run not found")
                    return
                self._send_json(snapshot)
                return
            if parsed.path.startswith("/api/runs/") and parsed.path.endswith("/artifact"):
                run_id = parsed.path.split("/")[3]
                query = parse_qs(parsed.query)
                requested_path = ((query.get("path") or [""])[0]).strip()
                if not requested_path:
                    self.send_error(HTTPStatus.BAD_REQUEST, "Missing artifact path")
                    return
                try:
                    self._send_json(read_artifact(app_state.runtime_root, run_id, requested_path))
                except PermissionError as exc:
                    self.send_error(HTTPStatus.FORBIDDEN, str(exc))
                except FileNotFoundError as exc:
                    self.send_error(HTTPStatus.NOT_FOUND, str(exc))
                return
            if parsed.path.startswith("/api/runs/") and parsed.path.endswith("/log"):
                run_id = parsed.path.split("/")[3]
                try:
                    self._send_text(read_run_log(app_state.runtime_root, run_id), "text/plain; charset=utf-8")
                except FileNotFoundError as exc:
                    self.send_error(HTTPStatus.NOT_FOUND, str(exc))
                return
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/api/runs":
                body = self.rfile.read(int(self.headers.get("Content-Length", "0") or "0"))
                data = json.loads(body or "{}")
                self._send_json(create_run(app_state, str(data.get("prompt") or "")))
                return
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

        def _send_json(self, payload: dict[str, object]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_text(self, text: str, content_type: str) -> None:
            body = text.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return DashboardHandler
