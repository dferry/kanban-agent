from __future__ import annotations

import argparse
from pathlib import Path

from kanban.agent import AgentController
from kanban.api import KanbanAPIServer
from kanban.gui import KanbanGUI
from kanban.model import KanbanBoard

DEFAULT_BOARD_FILENAME = ".board.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Kanban board with GUI and JSON API")
    parser.add_argument("--host", default="127.0.0.1", help="API host")
    parser.add_argument("--port", default=8000, type=int, help="API port")
    parser.add_argument("--board-file", default=None, help="Optional JSON file used to load/save board state")
    return parser.parse_args()


def resolve_board_file(board_file: str | None, cwd: Path | None = None) -> Path:
    if board_file:
        return Path(board_file)
    root = cwd or Path.cwd()
    return root / DEFAULT_BOARD_FILENAME


def build_agent_controller(board: KanbanBoard) -> AgentController:
    return AgentController(board)


def main() -> None:
    args = parse_args()
    board_file = resolve_board_file(args.board_file)
    if board_file.exists():
        board = KanbanBoard.load_from_file(board_file)
    else:
        board = KanbanBoard()

    api = KanbanAPIServer(board, host=args.host, port=args.port)
    api.start()
    agent_controller = build_agent_controller(board)
    print(f"Kanban API running on http://{args.host}:{api.port}")
    print(f"Board persistence file: {board_file}")

    try:
        gui = KanbanGUI(board, board_file=board_file, agent_controller=agent_controller)
        gui.run()
    finally:
        agent_controller.shutdown()
        board.save_to_file(board_file)
        api.stop()


if __name__ == "__main__":
    main()
