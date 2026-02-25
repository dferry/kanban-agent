from __future__ import annotations

import json
import re
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Any

from kanban.model import DEFAULT_TASK_COLOR, KanbanBoard, Task, TaskStatus

_MOVE_PATH = re.compile(r"^/tasks/(\d+)/move$")


class _KanbanHandler(BaseHTTPRequestHandler):
    board: KanbanBoard

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/tasks":
            self._send_json(404, {"error": "not found"})
            return

        tasks = [self._serialize_task(task) for task in self.board.list_tasks()]
        self._send_json(200, {"tasks": tasks})

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/tasks":
            payload = self._read_json()
            if payload is None:
                return

            title = payload.get("title")
            if not isinstance(title, str) or not title.strip():
                self._send_json(400, {"error": "title must be a non-empty string"})
                return
            color = payload.get("color", DEFAULT_TASK_COLOR)

            try:
                task = self.board.create_task(title, color=color)
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
                return

            self._send_json(201, self._serialize_task(task))
            return

        move_match = _MOVE_PATH.match(self.path)
        if move_match is None:
            self._send_json(404, {"error": "not found"})
            return

        payload = self._read_json()
        if payload is None:
            return

        raw_status = payload.get("status")
        try:
            status = TaskStatus(raw_status)
        except ValueError:
            self._send_json(400, {"error": "invalid status"})
            return

        task_id = int(move_match.group(1))
        try:
            task = self.board.move_task(task_id, status)
        except KeyError:
            self._send_json(404, {"error": "task not found"})
            return

        self._send_json(200, self._serialize_task(task))

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        # Keep tests and local runs quiet.
        return

    def _read_json(self) -> dict[str, Any] | None:
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            self._send_json(400, {"error": "missing request body"})
            return None

        try:
            length = int(raw_length)
        except ValueError:
            self._send_json(400, {"error": "invalid content length"})
            return None

        data = self.rfile.read(length)
        try:
            payload = json.loads(data.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json(400, {"error": "invalid json"})
            return None

        if not isinstance(payload, dict):
            self._send_json(400, {"error": "json body must be an object"})
            return None

        return payload

    def _serialize_task(self, task: Task) -> dict[str, Any]:
        payload = asdict(task)
        payload["status"] = task.status.value
        return payload

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class KanbanAPIServer:
    def __init__(self, board: KanbanBoard, host: str = "127.0.0.1", port: int = 8000) -> None:
        handler = type("KanbanHandler", (_KanbanHandler,), {"board": board})
        self._httpd = ThreadingHTTPServer((host, port), handler)
        self._thread: Thread | None = None

    @property
    def port(self) -> int:
        return int(self._httpd.server_address[1])

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        self._thread = Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
