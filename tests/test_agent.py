from __future__ import annotations

import threading
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
import json

from kanban.agent import AgentController, AgentExecutionConfig, AgentRunResult, default_process_runner
from kanban.model import KanbanBoard, Task, TaskStatus


def _wait_for(predicate, timeout: float = 2.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition not reached before timeout")


class AgentControllerTests(unittest.TestCase):
    def test_default_process_runner_captures_stdout_stderr_and_exit_code(self) -> None:
        result = default_process_runner(
            [
                "python",
                "-c",
                "import sys; print('hello'); print('oops', file=sys.stderr); raise SystemExit(3)",
            ]
        )

        self.assertEqual(result.exit_code, 3)
        self.assertEqual(result.stdout, "hello\n")
        self.assertEqual(result.stderr, "oops\n")

    def test_execution_config_replaces_task_text_token(self) -> None:
        config = AgentExecutionConfig(command="codex exec", prompt_template="Implement TASK_TEXT now")

        prompt = config.render_prompt("Wire API")

        self.assertEqual(prompt, "Implement Wire API now")

    def test_cycle_state_transitions(self) -> None:
        board = KanbanBoard()
        controller = AgentController(board, task_executor=lambda _task: 0, poll_interval=0.01)
        self.addCleanup(controller.shutdown)

        self.assertEqual(controller.state, "stopped")
        self.assertEqual(controller.cycle_state(), "running")
        self.assertEqual(controller.cycle_state(), "finishing")
        self.assertEqual(controller.cycle_state(), "running")

    def test_running_consumes_todo_and_moves_to_done(self) -> None:
        board = KanbanBoard()
        task = board.create_task("Implement parser")
        executed: list[int] = []

        controller = AgentController(
            board,
            task_executor=lambda current: executed.append(current.id) or 0,
            poll_interval=0.01,
        )
        self.addCleanup(controller.shutdown)

        controller.cycle_state()  # stopped -> running
        _wait_for(lambda: board.get_task(task.id).status == TaskStatus.DONE)
        _wait_for(lambda: controller.state == "stopped")

        self.assertEqual(executed, [task.id])
        self.assertEqual(controller.state, "stopped")

    def test_finishing_waits_for_current_task_then_stops(self) -> None:
        board = KanbanBoard()
        first = board.create_task("Task 1")
        second = board.create_task("Task 2")
        allow_finish = threading.Event()
        started = threading.Event()

        def executor(current: Task) -> int:
            started.set()
            allow_finish.wait(timeout=2)
            return 0

        controller = AgentController(board, task_executor=executor, poll_interval=0.01)
        self.addCleanup(controller.shutdown)

        controller.cycle_state()  # stopped -> running
        self.assertTrue(started.wait(timeout=1))
        self.assertEqual(controller.cycle_state(), "finishing")

        allow_finish.set()
        _wait_for(lambda: controller.state == "stopped")

        self.assertEqual(board.get_task(first.id).status, TaskStatus.DONE)
        self.assertEqual(board.get_task(second.id).status, TaskStatus.TODO)

    def test_finishing_to_running_resumes_after_current_task(self) -> None:
        board = KanbanBoard()
        first = board.create_task("Task 1")
        second = board.create_task("Task 2")
        allow_finish = threading.Event()
        started = threading.Event()
        executions: list[int] = []

        def executor(current: Task) -> int:
            executions.append(current.id)
            started.set()
            if current.id == first.id:
                allow_finish.wait(timeout=2)
            return 0

        controller = AgentController(board, task_executor=executor, poll_interval=0.01)
        self.addCleanup(controller.shutdown)

        controller.cycle_state()  # stopped -> running
        self.assertTrue(started.wait(timeout=1))
        self.assertEqual(controller.cycle_state(), "finishing")
        self.assertEqual(controller.cycle_state(), "running")

        allow_finish.set()
        _wait_for(lambda: board.get_task(second.id).status == TaskStatus.DONE)
        _wait_for(lambda: controller.state == "stopped")

        self.assertEqual(executions, [first.id, second.id])
        self.assertEqual(controller.state, "stopped")

    def test_controller_reads_latest_execution_config_for_each_task(self) -> None:
        board = KanbanBoard()
        first = board.create_task("Task 1")
        second = board.create_task("Task 2")
        allow_first_to_finish = threading.Event()
        first_started = threading.Event()
        calls: list[list[str]] = []
        config = AgentExecutionConfig(command="codex exec", prompt_template="First TASK_TEXT")

        def process_runner(argv: list[str]) -> int:
            calls.append(argv)
            if len(calls) == 1:
                first_started.set()
                allow_first_to_finish.wait(timeout=2)
            return 0

        controller = AgentController(
            board,
            execution_config=config,
            process_runner=process_runner,
            poll_interval=0.01,
        )
        self.addCleanup(controller.shutdown)

        controller.cycle_state()  # stopped -> running
        self.assertTrue(first_started.wait(timeout=1))

        config.update(command="codex exec --model gpt-5", prompt_template="Second TASK_TEXT")
        allow_first_to_finish.set()

        _wait_for(lambda: board.get_task(second.id).status == TaskStatus.DONE)

        self.assertEqual(calls[0], ["codex", "exec", "First Task 1"])
        self.assertEqual(calls[1], ["codex", "exec", "--model", "gpt-5", "Second Task 2"])

    def test_commit_after_each_task_runs_git_commit_with_task_title(self) -> None:
        board = KanbanBoard()
        task = board.create_task("Ship parser")
        calls: list[list[str]] = []

        controller = AgentController(
            board,
            execution_config=AgentExecutionConfig(
                command="codex exec",
                prompt_template="Run TASK_TEXT",
                commit_after_each_task=True,
            ),
            process_runner=lambda argv: calls.append(argv) or 0,
            poll_interval=0.01,
        )
        self.addCleanup(controller.shutdown)

        controller.cycle_state()  # stopped -> running
        _wait_for(lambda: board.get_task(task.id).status == TaskStatus.DONE)

        self.assertEqual(
            calls,
            [
                ["codex", "exec", "Run Ship parser"],
                ["git", "commit", "-a", "-m", "Ship parser"],
            ],
        )

    def test_last_invocation_captures_stdout_stderr_and_exit_code(self) -> None:
        board = KanbanBoard()
        task = board.create_task("Task 1")

        controller = AgentController(
            board,
            execution_config=AgentExecutionConfig(command="codex exec", prompt_template="Run TASK_TEXT"),
            process_runner=lambda _argv: AgentRunResult(exit_code=9, stdout="ok output", stderr="bad output"),
            poll_interval=0.01,
        )
        self.addCleanup(controller.shutdown)

        controller.cycle_state()  # stopped -> running
        _wait_for(lambda: board.get_task(task.id).status == TaskStatus.DONE)

        invocation = controller.last_invocation()
        self.assertIsNotNone(invocation)
        assert invocation is not None
        self.assertEqual(invocation.exit_code, 9)
        self.assertEqual(invocation.stdout, "ok output")
        self.assertEqual(invocation.stderr, "bad output")

    def test_stop_task_becoming_active_transitions_running_to_stopped(self) -> None:
        board = KanbanBoard()
        first = board.create_task("Task 1")
        stop = board.create_task("STOP")
        trailing = board.create_task("Task 3")
        executions: list[int] = []

        controller = AgentController(
            board,
            task_executor=lambda current: executions.append(current.id) or 0,
            poll_interval=0.01,
        )
        self.addCleanup(controller.shutdown)

        controller.cycle_state()  # stopped -> running

        _wait_for(lambda: board.get_task(stop.id).status == TaskStatus.DONE)
        _wait_for(lambda: controller.state == "stopped")

        self.assertEqual(executions, [first.id])
        self.assertEqual(board.get_task(first.id).status, TaskStatus.DONE)
        self.assertEqual(board.get_task(stop.id).status, TaskStatus.DONE)
        self.assertEqual(board.get_task(trailing.id).status, TaskStatus.TODO)

    def test_task_start_persists_start_time_command_and_prompt_to_board_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            board_file = Path(temp_dir) / ".board.json"
            board = KanbanBoard()
            task = board.create_task("Implement parser")
            release_runner = threading.Event()
            started_runner = threading.Event()

            def process_runner(_argv: list[str]) -> int:
                started_runner.set()
                release_runner.wait(timeout=2)
                return 0

            controller = AgentController(
                board,
                execution_config=AgentExecutionConfig(
                    command="codex exec --model gpt-5",
                    prompt_template="Run TASK_TEXT now",
                ),
                process_runner=process_runner,
                board_file=board_file,
                poll_interval=0.01,
            )
            self.addCleanup(controller.shutdown)

            controller.cycle_state()  # stopped -> running
            self.assertTrue(started_runner.wait(timeout=1))

            payload = json.loads(board_file.read_text(encoding="utf-8"))
            persisted_task = payload["columns"]["in_progress"][0]
            self.assertEqual(persisted_task["id"], task.id)
            self.assertEqual(persisted_task["command"], "codex exec --model gpt-5")
            self.assertEqual(persisted_task["prompt"], "Run Implement parser now")
            self.assertTrue(persisted_task["start_time"])

            release_runner.set()
            _wait_for(lambda: board.get_task(task.id).status == TaskStatus.DONE)

    def test_task_finish_persists_output_end_time_duration_and_exit_code_to_board_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            board_file = Path(temp_dir) / ".board.json"
            board = KanbanBoard()
            task = board.create_task("Collect output")

            controller = AgentController(
                board,
                execution_config=AgentExecutionConfig(
                    command="codex exec",
                    prompt_template="Run TASK_TEXT",
                ),
                process_runner=lambda _argv: AgentRunResult(
                    exit_code=7,
                    stdout="line one\ntokens used 12,345\n",
                    stderr="line two\n",
                ),
                board_file=board_file,
                poll_interval=0.01,
            )
            self.addCleanup(controller.shutdown)

            controller.cycle_state()  # stopped -> running
            _wait_for(lambda: board.get_task(task.id).status == TaskStatus.DONE)

            payload = json.loads(board_file.read_text(encoding="utf-8"))
            persisted_task = payload["columns"]["done"][0]
            self.assertEqual(persisted_task["id"], task.id)
            self.assertEqual(persisted_task["output"], "line one\ntokens used 12,345\nline two")
            self.assertTrue(persisted_task["end_time"])
            self.assertTrue(persisted_task["duration"])
            self.assertEqual(persisted_task["tokens_used"], "12,345")
            self.assertEqual(persisted_task["exit_code"], "7")


if __name__ == "__main__":
    unittest.main()
