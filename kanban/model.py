from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re
from threading import RLock

DEFAULT_TASK_COLOR = "#ef4444"
_HEX_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")


class TaskStatus(StrEnum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


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
        self._order: dict[TaskStatus, list[int]] = {
            TaskStatus.TODO: [],
            TaskStatus.IN_PROGRESS: [],
            TaskStatus.DONE: [],
        }
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

    def list_tasks(self) -> list[Task]:
        with self._lock:
            ordered_tasks: list[Task] = []
            for status in (TaskStatus.TODO, TaskStatus.IN_PROGRESS, TaskStatus.DONE):
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
