from __future__ import annotations

import threading
import time
import unittest

from kanban.agent import AgentController, AgentExecutionConfig
from kanban.model import KanbanBoard, Task, TaskStatus


def _wait_for(predicate, timeout: float = 2.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition not reached before timeout")


class AgentControllerTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
