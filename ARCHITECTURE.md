# Architecture

This document describes the purpose of each project file and how components are intended to be used together.

## Top-Level Files

- `README.md`
  - Primary user documentation.
  - Use this for installation, runtime commands, and high-level feature overview.

- `API.md`
  - HTTP API reference.
  - Use this when integrating with the JSON API (`/tasks`, create, move, error handling, payload formats).

- `AGENTS.md`
  - Instructions for software agents working in this repository.
  - Defines workflow expectations (especially TDD), scope boundaries, and quality standards.

- `ARCHITECTURE.md` (this file)
  - Project map for developers and agents.
  - Use this first to understand where behavior lives before editing.

- `board.json` / `.board.json`
  - Runtime board state files (JSON persistence data).
  - `board.json` is an explicit path example.
  - `.board.json` is the default hidden board file in the current working directory when `--board-file` is not provided.

## Python Package: `kanban/`

- `kanban/__init__.py`
  - Package marker for the `kanban` module namespace.

- `kanban/model.py`
  - Core domain model and persistence layer.
  - Responsibilities:
    - Task and status definitions (`Task`, `TaskStatus`).
    - In-memory board state (`KanbanBoard`) with thread safety.
    - Task creation, movement, and ordering logic.
    - Color validation (`#RRGGBB`).
    - Save/load board JSON (`save_to_file`, `load_from_file`, `to_dict`, `from_dict`).
  - This is the source of truth for board behavior and ordering semantics.

- `kanban/api.py`
  - HTTP server and JSON API.
  - Responsibilities:
    - Expose board operations over HTTP.
    - Validate request payloads and return JSON responses/errors.
    - Serialize model tasks for API clients.
  - Uses a shared `KanbanBoard` instance.

- `kanban/gui.py`
  - Tkinter graphical interface.
  - Responsibilities:
    - Render board columns and task cards.
    - Handle drag-and-drop move/reorder interactions.
    - Handle color selection modes (fixed colors, RNG, Cycle).
    - Handle scroll behavior for task columns.
    - Save board via button and on window-close (`X`) event.
  - Uses a shared `KanbanBoard` instance and optional persistence path.

- `kanban/app.py`
  - Application entrypoint and composition root.
  - Responsibilities:
    - Parse CLI args (`--host`, `--port`, `--board-file`).
    - Resolve default board file (`.board.json`) when none is provided.
    - Load persisted board state at startup.
    - Start API server and GUI with shared board instance.
    - Save board on shutdown.

## Tests: `tests/`

- `tests/test_model.py`
  - Unit tests for model behavior.
  - Covers task creation, color validation, ordering/reordering, movement semantics, and save/load persistence integrity.

- `tests/test_api.py`
  - Integration-style tests for HTTP API.
  - Starts a local server and validates create/list/move behavior and validation errors.

- `tests/test_app.py`
  - Unit tests for app-level board-file resolution.
  - Verifies default `.board.json` behavior and explicit path behavior.

## Generated/Transient Files

- `kanban/__pycache__/...`, `tests/__pycache__/...`
  - Python bytecode caches generated at runtime/test time.
  - Not part of business logic.

## Runtime Flow

1. Start app via `python -m kanban.app`.
2. `app.py` resolves board file and loads persisted state (if present).
3. A single `KanbanBoard` instance is shared by GUI (`gui.py`) and API server (`api.py`).
4. User and API operations mutate the same in-memory model (`model.py`).
5. Board state is saved to JSON via GUI save action and on normal app shutdown/close.
