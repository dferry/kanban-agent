from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from threading import Condition, Lock, Thread
from typing import Callable, Literal

from kanban.model import KanbanBoard, Task, TaskStatus

AgentState = Literal["stopped", "running", "finishing"]
TaskExecutor = Callable[[Task], int]
ProcessRunner = Callable[[list[str]], int]

TASK_TEXT_TOKEN = "TASK_TEXT"

_DEFAULT_POLL_INTERVAL = 0.2


@dataclass(slots=True)
class AgentInvocation:
    task_id: int
    command: str
    prompt: str
    argv: list[str]


def default_prompt_template() -> str:
    return (
        "You are working on one task in a larger kanban project. "
        "Read AGENTS.md in the repository first, then implement this task.\n\n"
        f"Task title: {TASK_TEXT_TOKEN}\n"
        "When finished, leave the workspace in a clean, reviewable state."
    )


class AgentExecutionConfig:
    def __init__(self, command: str = "codex exec", prompt_template: str | None = None) -> None:
        self._lock = Lock()
        self._command = command
        self._prompt_template = prompt_template or default_prompt_template()

    def update(self, command: str, prompt_template: str) -> None:
        with self._lock:
            self._command = command
            self._prompt_template = prompt_template

    def snapshot(self) -> tuple[str, str]:
        with self._lock:
            return self._command, self._prompt_template

    def render_prompt(self, task_title: str) -> str:
        _command, prompt_template = self.snapshot()
        return prompt_template.replace(TASK_TEXT_TOKEN, task_title)


def default_process_runner(argv: list[str]) -> int:
    try:
        result = subprocess.run(argv, check=False)
    except OSError:
        return 1
    return int(result.returncode)


class AgentController:
    def __init__(
        self,
        board: KanbanBoard,
        task_executor: TaskExecutor | None = None,
        execution_config: AgentExecutionConfig | None = None,
        process_runner: ProcessRunner | None = None,
        poll_interval: float = _DEFAULT_POLL_INTERVAL,
    ) -> None:
        self._board = board
        self._task_executor = task_executor
        self._execution_config = execution_config or AgentExecutionConfig()
        self._process_runner = process_runner or default_process_runner
        self._poll_interval = poll_interval
        self._state: AgentState = "stopped"
        self._shutdown_requested = False
        self._condition = Condition()
        self._worker: Thread | None = None
        self._last_invocation: AgentInvocation | None = None

    @property
    def state(self) -> AgentState:
        with self._condition:
            return self._state

    def execution_config_snapshot(self) -> tuple[str, str]:
        return self._execution_config.snapshot()

    def update_execution_config(self, command: str, prompt_template: str) -> None:
        self._execution_config.update(command=command, prompt_template=prompt_template)

    def last_invocation(self) -> AgentInvocation | None:
        with self._condition:
            return self._last_invocation

    def cycle_state(self) -> AgentState:
        with self._condition:
            if self._state == "stopped":
                self._state = "running"
                self._ensure_worker_locked()
            elif self._state == "running":
                self._state = "finishing"
            else:
                self._state = "running"
                self._ensure_worker_locked()

            self._condition.notify_all()
            return self._state

    def shutdown(self) -> None:
        worker: Thread | None
        with self._condition:
            self._shutdown_requested = True
            self._state = "stopped"
            self._condition.notify_all()
            worker = self._worker

        if worker is not None:
            worker.join(timeout=5)

    def _ensure_worker_locked(self) -> None:
        if self._worker is not None and self._worker.is_alive():
            return

        self._worker = Thread(target=self._worker_loop, daemon=True)
        self._worker.start()

    def _worker_loop(self) -> None:
        while True:
            with self._condition:
                while not self._shutdown_requested and self._state == "stopped":
                    self._condition.wait()
                if self._shutdown_requested:
                    return

                if self._state == "finishing":
                    self._state = "stopped"
                    continue

            task = self._next_todo_task()
            if task is None:
                with self._condition:
                    if self._state == "running":
                        self._condition.wait(timeout=self._poll_interval)
                continue

            try:
                self._board.move_task(task.id, TaskStatus.IN_PROGRESS)
            except KeyError:
                continue

            self._execute_task(task)

            try:
                self._board.move_task(task.id, TaskStatus.DONE)
            except KeyError:
                pass

            with self._condition:
                if self._state == "finishing":
                    self._state = "stopped"

    def _next_todo_task(self) -> Task | None:
        for task in self._board.list_tasks():
            if task.status == TaskStatus.TODO:
                return task
        return None

    def _execute_task(self, task: Task) -> int:
        if self._task_executor is not None:
            return self._task_executor(task)

        command, prompt_template = self._execution_config.snapshot()
        prompt = prompt_template.replace(TASK_TEXT_TOKEN, task.title)

        try:
            argv = shlex.split(command)
        except ValueError:
            argv = []

        if not argv:
            with self._condition:
                self._last_invocation = AgentInvocation(task_id=task.id, command=command, prompt=prompt, argv=[])
            return 1

        full_argv = [*argv, prompt]
        with self._condition:
            self._last_invocation = AgentInvocation(task_id=task.id, command=command, prompt=prompt, argv=full_argv)
        return self._process_runner(full_argv)
