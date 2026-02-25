from __future__ import annotations

import argparse

from kanban.api import KanbanAPIServer
from kanban.gui import KanbanGUI
from kanban.model import KanbanBoard


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Kanban board with GUI and JSON API")
    parser.add_argument("--host", default="127.0.0.1", help="API host")
    parser.add_argument("--port", default=8000, type=int, help="API port")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    board = KanbanBoard()

    api = KanbanAPIServer(board, host=args.host, port=args.port)
    api.start()
    print(f"Kanban API running on http://{args.host}:{api.port}")

    try:
        gui = KanbanGUI(board)
        gui.run()
    finally:
        api.stop()


if __name__ == "__main__":
    main()
