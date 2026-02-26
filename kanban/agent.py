from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
from threading import Condition, Lock, Thread
from typing import Callable, Literal

from kanban.model import KanbanBoard, Task, TaskStatus

AgentState = Literal["stopped", "running", "finishing"]
TaskExecutor = Callable[[Task], int]

TASK_TEXT_TOKEN = "TASK_TEXT"
STOP_TASK_TITLE = "STOP"

_DEFAULT_POLL_INTERVAL = 0.2
_TOKENS_USED_PATTERN = re.compile(r"tokens used[^0-9]*([0-9][0-9,]*)", re.IGNORECASE)


@dataclass(slots=True)
class AgentInvocation:
    task_id: int
    command: str
    prompt: str
    argv: list[str]
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0


@dataclass(slots=True)
class AgentRunResult:
    exit_code: int
    stdout: str = ""
    stderr: str = ""


ProcessRunner = Callable[[list[str]], int | AgentRunResult]


def default_prompt_template() -> str:
    return (
        "You are working on one task in a larger kanban board project. "
        "Read AGENTS.md to understand the repository and KANBAN.md to understand how to add new tasks to the kanban board. Then implement this task.\n\n"
        f"Task description: {TASK_TEXT_TOKEN}\n"
        "When finished, leave the workspace in a clean, reviewable state."
    )


class AgentExecutionConfig:
    def __init__(
        self,
        command: str = "codex exec",
        prompt_template: str | None = None,
        commit_after_each_task: bool = False,
    ) -> None:
        self._lock = Lock()
        self._command = command
        self._prompt_template = prompt_template or default_prompt_template()
        self._commit_after_each_task = commit_after_each_task

    def update(self, command: str, prompt_template: str, commit_after_each_task: bool = False) -> None:
        with self._lock:
            self._command = command
            self._prompt_template = prompt_template
            self._commit_after_each_task = commit_after_each_task

    def snapshot(self) -> tuple[str, str, bool]:
        with self._lock:
            return self._command, self._prompt_template, self._commit_after_each_task

    def render_prompt(self, task_title: str) -> str:
        _command, prompt_template, _commit_after_each_task = self.snapshot()
        return prompt_template.replace(TASK_TEXT_TOKEN, task_title)


def default_process_runner(argv: list[str]) -> AgentRunResult:
    try:
        result = subprocess.run(argv, check=False, capture_output=True, text=True)
    except OSError as exc:
        return AgentRunResult(exit_code=1, stdout="", stderr=str(exc))
    return AgentRunResult(
        exit_code=int(result.returncode),
        stdout=result.stdout or "",
        stderr=result.stderr or "",
    )


class AgentController:
    def __init__(
        self,
        board: KanbanBoard,
        task_executor: TaskExecutor | None = None,
        execution_config: AgentExecutionConfig | None = None,
        process_runner: ProcessRunner | None = None,
        board_file: str | Path | None = None,
        poll_interval: float = _DEFAULT_POLL_INTERVAL,
    ) -> None:
        self._board = board
        self._task_executor = task_executor
        self._execution_config = execution_config or AgentExecutionConfig()
        self._process_runner = process_runner or default_process_runner
        self._board_file = Path(board_file) if board_file is not None else None
        self._poll_interval = poll_interval
        self._state: AgentState = "stopped"
        self._shutdown_requested = False
        self._condition = Condition()
        self._worker: Thread | None = None
        self._last_invocation: AgentInvocation | None = None
        self._session_executed_task = False

    @property
    def state(self) -> AgentState:
        with self._condition:
            return self._state

    def execution_config_snapshot(self) -> tuple[str, str, bool]:
        return self._execution_config.snapshot()

    def update_execution_config(
        self,
        command: str,
        prompt_template: str,
        commit_after_each_task: bool = False,
    ) -> None:
        self._execution_config.update(
            command=command,
            prompt_template=prompt_template,
            commit_after_each_task=commit_after_each_task,
        )

    def last_invocation(self) -> AgentInvocation | None:
        with self._condition:
            return self._last_invocation

    def cycle_state(self) -> AgentState:
        with self._condition:
            if self._state == "stopped":
                self._state = "running"
                self._session_executed_task = False
                self._ensure_worker_locked()
            elif self._state == "running":
                self._state = "finishing"
            else:
                self._state = "running"
                self._session_executed_task = False
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
                    if self._state == "running" and self._session_executed_task:
                        self._state = "stopped"
                    elif self._state == "running":
                        self._condition.wait(timeout=self._poll_interval)
                continue

            try:
                self._board.move_task(task.id, TaskStatus.IN_PROGRESS)
            except KeyError:
                continue

            if self._is_stop_task(task):
                try:
                    self._board.move_task(task.id, TaskStatus.DONE)
                except KeyError:
                    pass
                with self._condition:
                    if self._state == "running":
                        self._state = "stopped"
                        self._session_executed_task = True
                continue

            command, prompt, commit_after_each_task = self._task_execution_inputs(task)
            task_started_at = self._record_task_start(task=task, command=command, prompt=prompt)
            run_result = self._execute_task(task, command=command, prompt=prompt)
            if commit_after_each_task:
                self._run_git_commit(task.title)
            self._record_task_finish(task=task, run_result=run_result, task_started_at=task_started_at)
            with self._condition:
                self._session_executed_task = True

            try:
                self._board.move_task(task.id, TaskStatus.DONE)
            except KeyError:
                pass
            else:
                if self._board_file is not None:
                    self._board.save_to_file(self._board_file)

            with self._condition:
                if self._state == "finishing":
                    self._state = "stopped"

    def _next_todo_task(self) -> Task | None:
        for task in self._board.list_tasks():
            if task.status == TaskStatus.TODO:
                return task
        return None

    def _task_execution_inputs(self, task: Task) -> tuple[str, str, bool]:
        command, prompt_template, commit_after_each_task = self._execution_config.snapshot()
        prompt = prompt_template.replace(TASK_TEXT_TOKEN, task.title)
        return command, prompt, commit_after_each_task

    def _record_task_start(self, task: Task, *, command: str, prompt: str) -> datetime:
        task_started_at = datetime.now(timezone.utc)
        start_time = task_started_at.isoformat().replace("+00:00", "Z")
        self._board.update_task(
            task.id,
            command=command,
            prompt=prompt,
            start_time=start_time,
        )
        if self._board_file is not None:
            self._board.save_to_file(self._board_file)
        return task_started_at

    def _record_task_finish(
        self,
        *,
        task: Task,
        run_result: AgentRunResult,
        task_started_at: datetime,
    ) -> None:
        task_finished_at = datetime.now(timezone.utc)
        end_time = task_finished_at.isoformat().replace("+00:00", "Z")
        elapsed_seconds = max(0.0, (task_finished_at - task_started_at).total_seconds())
        duration = f"{elapsed_seconds:.3f}s"
        output = f"{run_result.stdout}{run_result.stderr}"
        tokens_used = self._extract_tokens_used(output)
        self._board.update_task(
            task.id,
            output=output,
            end_time=end_time,
            duration=duration,
            tokens_used=tokens_used,
            exit_code=str(run_result.exit_code),
        )

    def _extract_tokens_used(self, output: str) -> str:
        match = _TOKENS_USED_PATTERN.search(output)
        if match is None:
            return ""
        return match.group(1)

    def _execute_task(self, task: Task, *, command: str | None = None, prompt: str | None = None) -> AgentRunResult:
        if self._task_executor is not None:
            return AgentRunResult(exit_code=int(self._task_executor(task)))

        if command is None or prompt is None:
            command, prompt, _commit_after_each_task = self._task_execution_inputs(task)

        try:
            argv = shlex.split(command)
        except ValueError:
            argv = []

        if not argv:
            with self._condition:
                self._last_invocation = AgentInvocation(
                    task_id=task.id,
                    command=command,
                    prompt=prompt,
                    argv=[],
                    stderr="invalid command",
                    exit_code=1,
                )
            return AgentRunResult(exit_code=1, stderr="invalid command")

        full_argv = [*argv, prompt]
        run_result = self._normalize_run_result(self._process_runner(full_argv))
        with self._condition:
            self._last_invocation = AgentInvocation(
                task_id=task.id,
                command=command,
                prompt=prompt,
                argv=full_argv,
                stdout=run_result.stdout,
                stderr=run_result.stderr,
                exit_code=run_result.exit_code,
            )
        return run_result

    def _normalize_run_result(self, raw_result: int | AgentRunResult) -> AgentRunResult:
        if isinstance(raw_result, AgentRunResult):
            return raw_result
        return AgentRunResult(exit_code=int(raw_result))

    def _run_git_commit(self, task_title: str) -> AgentRunResult:
        return self._normalize_run_result(self._process_runner(["git", "commit", "-a", "-m", task_title]))

    def _is_stop_task(self, task: Task) -> bool:
        return task.title.strip().upper() == STOP_TASK_TITLE
