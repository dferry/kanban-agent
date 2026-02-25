import unittest

from kanban.model import KanbanBoard, TaskStatus


class KanbanBoardTests(unittest.TestCase):
    def test_create_task_defaults_to_todo(self):
        board = KanbanBoard()

        task = board.create_task("Write docs")

        self.assertEqual(task.title, "Write docs")
        self.assertEqual(task.status, TaskStatus.TODO)
        self.assertEqual(task.id, 1)
        self.assertEqual(task.color, "#ef4444")

    def test_create_task_accepts_html_hex_color(self):
        board = KanbanBoard()

        task = board.create_task("Build API", color="#00FFCC")

        self.assertEqual(task.color, "#00ffcc")

    def test_create_task_rejects_invalid_color(self):
        board = KanbanBoard()

        with self.assertRaises(ValueError):
            board.create_task("Bad color", color="red")

    def test_move_task_updates_status(self):
        board = KanbanBoard()
        task = board.create_task("Build API")

        moved = board.move_task(task.id, TaskStatus.IN_PROGRESS)

        self.assertEqual(moved.status, TaskStatus.IN_PROGRESS)

    def test_move_unknown_task_raises_key_error(self):
        board = KanbanBoard()

        with self.assertRaises(KeyError):
            board.move_task(999, TaskStatus.DONE)

    def test_reorder_within_same_status(self):
        board = KanbanBoard()
        first = board.create_task("First")
        second = board.create_task("Second")
        third = board.create_task("Third")

        board.move_task(third.id, TaskStatus.TODO, index=0)

        tasks = board.list_tasks()
        self.assertEqual([task.id for task in tasks if task.status == TaskStatus.TODO], [third.id, first.id, second.id])

    def test_move_to_new_status_at_specific_index(self):
        board = KanbanBoard()
        todo_task = board.create_task("Todo")
        in_progress_a = board.create_task("In progress A")
        in_progress_b = board.create_task("In progress B")
        board.move_task(in_progress_a.id, TaskStatus.IN_PROGRESS)
        board.move_task(in_progress_b.id, TaskStatus.IN_PROGRESS)

        board.move_task(todo_task.id, TaskStatus.IN_PROGRESS, index=1)

        tasks = board.list_tasks()
        in_progress_ids = [task.id for task in tasks if task.status == TaskStatus.IN_PROGRESS]
        self.assertEqual(in_progress_ids, [in_progress_a.id, todo_task.id, in_progress_b.id])


if __name__ == "__main__":
    unittest.main()
