import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

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
        self.assertEqual(task.notes, "")

    def test_update_task_can_change_title_color_and_notes(self):
        board = KanbanBoard()
        task = board.create_task("Initial title", color="#112233")

        updated = board.update_task(task.id, title="  Updated title  ", color="#abcdef", notes="  Added notes  ")

        self.assertEqual(updated.title, "Updated title")
        self.assertEqual(updated.color, "#abcdef")
        self.assertEqual(updated.notes, "Added notes")
        fetched = board.get_task(task.id)
        self.assertEqual(fetched.title, "Updated title")
        self.assertEqual(fetched.color, "#abcdef")
        self.assertEqual(fetched.notes, "Added notes")

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

    def test_delete_task_removes_it_from_board(self):
        board = KanbanBoard()
        keep = board.create_task("Keep")
        remove = board.create_task("Remove")

        deleted = board.delete_task(remove.id)

        self.assertEqual(deleted.id, remove.id)
        self.assertEqual([task.id for task in board.list_tasks()], [keep.id])

    def test_delete_unknown_task_raises_key_error(self):
        board = KanbanBoard()

        with self.assertRaises(KeyError):
            board.delete_task(999)

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

    def test_save_and_load_preserves_order_status_and_color(self):
        board = KanbanBoard()
        first = board.create_task("First", color="#ff0000")
        second = board.create_task("Second", color="#00ff00")
        third = board.create_task("Third", color="#0000ff")
        board.move_task(third.id, TaskStatus.IN_PROGRESS)
        board.move_task(second.id, TaskStatus.IN_PROGRESS, index=0)
        board.move_task(first.id, TaskStatus.DONE)

        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "board.json"
            board.save_to_file(path)
            loaded = KanbanBoard.load_from_file(path)

        loaded_tasks = loaded.list_tasks()
        self.assertEqual(
            [(task.title, task.status.value, task.color) for task in loaded_tasks],
            [
                ("Second", "in_progress", "#00ff00"),
                ("Third", "in_progress", "#0000ff"),
                ("First", "done", "#ff0000"),
            ],
        )

    def test_load_from_missing_file_raises_file_not_found(self):
        with TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "missing.json"
            with self.assertRaises(FileNotFoundError):
                KanbanBoard.load_from_file(missing)

    def test_from_dict_accepts_legacy_payload_without_ignore_column(self):
        payload = {
            "version": 1,
            "columns": {
                "todo": [{"id": 1, "title": "Legacy task", "color": "#abcdef"}],
                "in_progress": [],
                "done": [],
            },
        }

        board = KanbanBoard.from_dict(payload)

        tasks = board.list_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].title, "Legacy task")
        self.assertEqual(tasks[0].status, TaskStatus.TODO)

    def test_save_and_load_preserves_agent_execution_config(self):
        board = KanbanBoard()
        board.set_agent_execution_config(
            command="codex exec --model gpt-5",
            prompt_template="Implement TASK_TEXT with tests",
        )

        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "board.json"
            board.save_to_file(path)
            loaded = KanbanBoard.load_from_file(path)

        self.assertEqual(
            loaded.agent_execution_config_snapshot(),
            ("codex exec --model gpt-5", "Implement TASK_TEXT with tests"),
        )


if __name__ == "__main__":
    unittest.main()
