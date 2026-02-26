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
    command: str = ""
    prompt: str = ""
    output: str = ""
    start_time: str = ""
    end_time: str = ""
    duration: str = ""
    tokens_used: str = ""
    exit_code: str = ""


class KanbanBoard:
    """Thread-safe in-memory task board shared by GUI and API."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._tasks: dict[int, Task] = {}
        self._order: dict[TaskStatus, list[int]] = {status: [] for status in _TASK_STATUSES}
        self._next_id = 1
        self._agent_execution_command = "codex exec"
        self._agent_execution_prompt_template = ""

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

    def update_task(
        self,
        task_id: int,
        *,
        title: str | None = None,
        color: str | None = None,
        command: str | None = None,
        prompt: str | None = None,
        output: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        duration: str | None = None,
        tokens_used: str | None = None,
        exit_code: str | None = None,
    ) -> Task:
        with self._lock:
            try:
                task = self._tasks[task_id]
            except KeyError as exc:
                raise KeyError(f"task {task_id} not found") from exc

            if title is not None:
                clean_title = title.strip()
                if not clean_title:
                    raise ValueError("title must not be empty")
                task.title = clean_title

            if color is not None:
                task.color = validate_html_color(color)

            if command is not None:
                task.command = _require_string_field(command, "command")
            if prompt is not None:
                task.prompt = _require_string_field(prompt, "prompt")
            if output is not None:
                task.output = _require_string_field(output, "output")
            if start_time is not None:
                task.start_time = _require_string_field(start_time, "start_time")
            if end_time is not None:
                task.end_time = _require_string_field(end_time, "end_time")
            if duration is not None:
                task.duration = _require_string_field(duration, "duration")
            if tokens_used is not None:
                task.tokens_used = _require_string_field(tokens_used, "tokens_used")
            if exit_code is not None:
                task.exit_code = _require_string_field(exit_code, "exit_code")

            return _copy_task(task)

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
            return _copy_task(task)

    def list_tasks(self) -> list[Task]:
        with self._lock:
            ordered_tasks: list[Task] = []
            for status in _TASK_STATUSES:
                for task_id in self._order[status]:
                    task = self._tasks[task_id]
                    ordered_tasks.append(_copy_task(task))
            return ordered_tasks

    def get_task(self, task_id: int) -> Task:
        with self._lock:
            try:
                t = self._tasks[task_id]
            except KeyError as exc:
                raise KeyError(f"task {task_id} not found") from exc
            return _copy_task(t)

    def set_agent_execution_config(self, *, command: str, prompt_template: str) -> None:
        if not isinstance(command, str):
            raise ValueError("agent execution command must be a string")
        if not isinstance(prompt_template, str):
            raise ValueError("agent execution prompt template must be a string")
        with self._lock:
            self._agent_execution_command = command
            self._agent_execution_prompt_template = prompt_template

    def agent_execution_config_snapshot(self) -> tuple[str, str]:
        with self._lock:
            return self._agent_execution_command, self._agent_execution_prompt_template

    def to_dict(self) -> dict[str, object]:
        with self._lock:
            columns: dict[str, list[dict[str, object]]] = {}
            for status in _TASK_STATUSES:
                column_tasks: list[dict[str, object]] = []
                for task_id in self._order[status]:
                    task = self._tasks[task_id]
                    column_tasks.append(
                        {
                            "id": task.id,
                            "title": task.title,
                            "color": task.color,
                            "command": task.command,
                            "prompt": task.prompt,
                            "output": task.output,
                            "start_time": task.start_time,
                            "end_time": task.end_time,
                            "duration": task.duration,
                            "tokens_used": task.tokens_used,
                            "exit_code": task.exit_code,
                        }
                    )
                columns[status.value] = column_tasks
            return {
                "version": 1,
                "columns": columns,
                "agent_execution": {
                    "command": self._agent_execution_command,
                    "prompt_template": self._agent_execution_prompt_template,
                },
            }

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
        raw_agent_execution = payload.get("agent_execution")
        if raw_agent_execution is not None:
            if not isinstance(raw_agent_execution, dict):
                raise ValueError("agent_execution must be an object")
            command = raw_agent_execution.get("command")
            prompt_template = raw_agent_execution.get("prompt_template")
            if not isinstance(command, str):
                raise ValueError("agent_execution.command must be a string")
            if not isinstance(prompt_template, str):
                raise ValueError("agent_execution.prompt_template must be a string")
            board.set_agent_execution_config(command=command, prompt_template=prompt_template)

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
                command = row.get("command", "")
                prompt = row.get("prompt", "")
                output = row.get("output", "")
                start_time = row.get("start_time", "")
                end_time = row.get("end_time", "")
                duration = row.get("duration", "")
                tokens_used = row.get("tokens_used", "")
                exit_code = row.get("exit_code", "")
                if not isinstance(task_id, int) or task_id <= 0:
                    raise ValueError("task id must be a positive integer")
                if task_id in seen_ids:
                    raise ValueError("task ids must be unique")
                if not isinstance(title, str) or not title.strip():
                    raise ValueError("task title must be a non-empty string")
                if not isinstance(command, str):
                    raise ValueError("task command must be a string")
                if not isinstance(prompt, str):
                    raise ValueError("task prompt must be a string")
                if not isinstance(output, str):
                    raise ValueError("task output must be a string")
                if not isinstance(start_time, str):
                    raise ValueError("task start_time must be a string")
                if not isinstance(end_time, str):
                    raise ValueError("task end_time must be a string")
                if not isinstance(duration, str):
                    raise ValueError("task duration must be a string")
                if not isinstance(tokens_used, str):
                    raise ValueError("task tokens_used must be a string")
                if not isinstance(exit_code, str):
                    raise ValueError("task exit_code must be a string")

                clean_color = validate_html_color(color)
                clean_title = title.strip()
                task = Task(
                    id=task_id,
                    title=clean_title,
                    status=status,
                    color=clean_color,
                    command=command.strip(),
                    prompt=prompt.strip(),
                    output=output.strip(),
                    start_time=start_time.strip(),
                    end_time=end_time.strip(),
                    duration=duration.strip(),
                    tokens_used=tokens_used.strip(),
                    exit_code=exit_code.strip(),
                )
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


def _copy_task(task: Task) -> Task:
    return Task(
        id=task.id,
        title=task.title,
        status=task.status,
        color=task.color,
        command=task.command,
        prompt=task.prompt,
        output=task.output,
        start_time=task.start_time,
        end_time=task.end_time,
        duration=task.duration,
        tokens_used=task.tokens_used,
        exit_code=task.exit_code,
    )


def _require_string_field(value: str, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    return value.strip()
