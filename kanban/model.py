from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import json
from pathlib import Path
import re
from threading import RLock

DEFAULT_TASK_COLOR = "#ef4444"
_HEX_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")


class TaskStatus(StrEnum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    IGNORE = "ignore"


_TASK_STATUSES: tuple[TaskStatus, ...] = (
    TaskStatus.TODO,
    TaskStatus.IN_PROGRESS,
    TaskStatus.DONE,
    TaskStatus.IGNORE,
)


@dataclass(slots=True)
class Task:
    id: int
    title: str
    status: TaskStatus
    color: str


class KanbanBoard:
    """Thread-safe in-memory task board shared by GUI and API."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._tasks: dict[int, Task] = {}
        self._order: dict[TaskStatus, list[int]] = {status: [] for status in _TASK_STATUSES}
        self._next_id = 1

    def create_task(self, title: str, color: str = DEFAULT_TASK_COLOR) -> Task:
        clean_title = title.strip()
        if not clean_title:
            raise ValueError("title must not be empty")
        clean_color = validate_html_color(color)

        with self._lock:
            task = Task(id=self._next_id, title=clean_title, status=TaskStatus.TODO, color=clean_color)
            self._tasks[task.id] = task
            self._order[TaskStatus.TODO].append(task.id)
            self._next_id += 1
            return task

    def move_task(self, task_id: int, status: TaskStatus, index: int | None = None) -> Task:
        with self._lock:
            try:
                task = self._tasks[task_id]
            except KeyError as exc:
                raise KeyError(f"task {task_id} not found") from exc

            source_ids = self._order[task.status]
            source_ids.remove(task.id)

            target_ids = self._order[status]
            target_index = _normalize_insert_index(index=index, size=len(target_ids))
            target_ids.insert(target_index, task.id)

            task.status = status
            return task

    def delete_task(self, task_id: int) -> Task:
        with self._lock:
            try:
                task = self._tasks.pop(task_id)
            except KeyError as exc:
                raise KeyError(f"task {task_id} not found") from exc

            self._order[task.status].remove(task.id)
            return Task(id=task.id, title=task.title, status=task.status, color=task.color)

    def list_tasks(self) -> list[Task]:
        with self._lock:
            ordered_tasks: list[Task] = []
            for status in _TASK_STATUSES:
                for task_id in self._order[status]:
                    task = self._tasks[task_id]
                    ordered_tasks.append(Task(id=task.id, title=task.title, status=task.status, color=task.color))
            return ordered_tasks

    def get_task(self, task_id: int) -> Task:
        with self._lock:
            try:
                t = self._tasks[task_id]
            except KeyError as exc:
                raise KeyError(f"task {task_id} not found") from exc
            return Task(id=t.id, title=t.title, status=t.status, color=t.color)

    def to_dict(self) -> dict[str, object]:
        with self._lock:
            columns: dict[str, list[dict[str, object]]] = {}
            for status in _TASK_STATUSES:
                column_tasks: list[dict[str, object]] = []
                for task_id in self._order[status]:
                    task = self._tasks[task_id]
                    column_tasks.append({"id": task.id, "title": task.title, "color": task.color})
                columns[status.value] = column_tasks
            return {"version": 1, "columns": columns}

    def save_to_file(self, file_path: str | Path) -> None:
        path = Path(file_path)
        payload = self.to_dict()
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> KanbanBoard:
        if not isinstance(payload, dict):
            raise ValueError("board payload must be an object")
        raw_columns = payload.get("columns")
        if not isinstance(raw_columns, dict):
            raise ValueError("board payload must contain a columns object")

        board = cls()
        max_id = 0
        seen_ids: set[int] = set()
        for status in _TASK_STATUSES:
            if status is TaskStatus.IGNORE:
                column = raw_columns.get(status.value, [])
            else:
                column = raw_columns.get(status.value)
            if not isinstance(column, list):
                raise ValueError(f"column {status.value} must be a list")
            for row in column:
                if not isinstance(row, dict):
                    raise ValueError("task rows must be objects")
                task_id = row.get("id")
                title = row.get("title")
                color = row.get("color")
                if not isinstance(task_id, int) or task_id <= 0:
                    raise ValueError("task id must be a positive integer")
                if task_id in seen_ids:
                    raise ValueError("task ids must be unique")
                if not isinstance(title, str) or not title.strip():
                    raise ValueError("task title must be a non-empty string")

                clean_color = validate_html_color(color)
                clean_title = title.strip()
                task = Task(id=task_id, title=clean_title, status=status, color=clean_color)
                board._tasks[task_id] = task
                board._order[status].append(task_id)
                seen_ids.add(task_id)
                max_id = max(max_id, task_id)

        board._next_id = max_id + 1
        return board

    @classmethod
    def load_from_file(cls, file_path: str | Path) -> KanbanBoard:
        path = Path(file_path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_dict(payload)


def validate_html_color(raw_color: str) -> str:
    if not isinstance(raw_color, str):
        raise ValueError("color must be a string in #RRGGBB format")

    if _HEX_COLOR_PATTERN.match(raw_color) is None:
        raise ValueError("color must be an HTML hex code in #RRGGBB format")

    return raw_color.lower()


def _normalize_insert_index(index: int | None, size: int) -> int:
    if index is None:
        return size

    if index < 0:
        return 0

    if index > size:
        return size

    return index
