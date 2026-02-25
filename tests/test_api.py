import json
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from kanban.api import KanbanAPIServer
from kanban.model import KanbanBoard


class APITests(unittest.TestCase):
    def setUp(self):
        self.board = KanbanBoard()
        self.server = KanbanAPIServer(self.board, host="127.0.0.1", port=0)
        self.server.start()
        self.base = f"http://127.0.0.1:{self.server.port}"

    def tearDown(self):
        self.server.stop()

    def test_create_and_list_tasks(self):
        req = Request(
            f"{self.base}/tasks",
            data=json.dumps({"title": "Task from API"}).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urlopen(req) as response:
            self.assertEqual(response.status, 201)
            created = json.loads(response.read().decode("utf-8"))

        self.assertEqual(created["title"], "Task from API")
        self.assertEqual(created["status"], "todo")
        self.assertEqual(created["color"], "#ef4444")

        with urlopen(f"{self.base}/tasks") as response:
            self.assertEqual(response.status, 200)
            payload = json.loads(response.read().decode("utf-8"))

        self.assertEqual(len(payload["tasks"]), 1)
        self.assertEqual(payload["tasks"][0]["id"], created["id"])
        self.assertEqual(payload["tasks"][0]["color"], "#ef4444")

    def test_create_task_with_hex_color(self):
        req = Request(
            f"{self.base}/tasks",
            data=json.dumps({"title": "Colored task", "color": "#123AbC"}).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urlopen(req) as response:
            self.assertEqual(response.status, 201)
            created = json.loads(response.read().decode("utf-8"))

        self.assertEqual(created["color"], "#123abc")

    def test_move_task(self):
        task = self.board.create_task("Needs move")
        req = Request(
            f"{self.base}/tasks/{task.id}/move",
            data=json.dumps({"status": "in_progress"}).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )

        with urlopen(req) as response:
            self.assertEqual(response.status, 200)
            moved = json.loads(response.read().decode("utf-8"))

        self.assertEqual(moved["status"], "in_progress")

    def test_create_task_without_title_returns_bad_request(self):
        req = Request(
            f"{self.base}/tasks",
            data=json.dumps({}).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )

        with self.assertRaises(HTTPError) as err:
            urlopen(req)

        self.assertEqual(err.exception.code, 400)

    def test_create_task_with_invalid_color_returns_bad_request(self):
        req = Request(
            f"{self.base}/tasks",
            data=json.dumps({"title": "Bad color", "color": "purple"}).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )

        with self.assertRaises(HTTPError) as err:
            urlopen(req)

        self.assertEqual(err.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
