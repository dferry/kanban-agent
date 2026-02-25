from __future__ import annotations

import subprocess
from threading import Condition, Thread
from typing import Callable, Literal

from kanban.model import KanbanBoard, Task, TaskStatus

AgentState = Literal["stopped", "running", "finishing"]
TaskExecutor = Callable[[Task], int]

_DEFAULT_POLL_INTERVAL = 0.2


def build_agent_prompt(task: Task) -> str:
    return (
        "You are working on one task in a larger kanban project. "
        "Read AGENTS.md in the repository first, then implement this task.\n\n"
        f"Task ID: {task.id}\n"
        f"Task title: {task.title}\n"
        "When finished, leave the workspace in a clean, reviewable state."
    )


def default_task_executor(task: Task) -> int:
    command = ["codex", "exec", build_agent_prompt(task)]
    try:
        result = subprocess.run(command, check=False)
    except OSError:
        return 1
    return int(result.returncode)


class AgentController:
    def __init__(
        self,
        board: KanbanBoard,
        task_executor: TaskExecutor | None = None,
        poll_interval: float = _DEFAULT_POLL_INTERVAL,
    ) -> None:
        self._board = board
        self._task_executor = task_executor or default_task_executor
        self._poll_interval = poll_interval
        self._state: AgentState = "stopped"
        self._shutdown_requested = False
        self._condition = Condition()
        self._worker: Thread | None = None

    @property
    def state(self) -> AgentState:
        with self._condition:
            return self._state

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

            self._task_executor(task)

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
