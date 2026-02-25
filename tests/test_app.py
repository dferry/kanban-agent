import unittest
from pathlib import Path

from kanban.app import DEFAULT_BOARD_FILENAME, resolve_board_file


class AppTests(unittest.TestCase):
    def test_resolve_board_file_defaults_to_hidden_board_in_cwd(self):
        cwd = Path("/tmp/example")

        resolved = resolve_board_file(None, cwd=cwd)

        self.assertEqual(resolved, cwd / DEFAULT_BOARD_FILENAME)

    def test_resolve_board_file_uses_explicit_value(self):
        cwd = Path("/tmp/example")

        resolved = resolve_board_file("custom-board.json", cwd=cwd)

        self.assertEqual(resolved, Path("custom-board.json"))


if __name__ == "__main__":
    unittest.main()
