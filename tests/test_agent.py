from __future__ import annotations

import threading
import time
import unittest

from kanban.agent import AgentController
from kanban.model import KanbanBoard, Task, TaskStatus


def _wait_for(predicate, timeout: float = 2.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition not reached before timeout")


class AgentControllerTests(unittest.TestCase):
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

        self.assertEqual(executed, [task.id])
        self.assertEqual(controller.state, "running")

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

        self.assertEqual(executions, [first.id, second.id])
        self.assertEqual(controller.state, "running")


if __name__ == "__main__":
    unittest.main()
