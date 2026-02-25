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

- `kanban/agent.py`
  - Background agent controller for autonomous task consumption.
  - Responsibilities:
    - Maintain explicit runtime state (`stopped`, `running`, `finishing`).
    - Consume tasks from `todo` in order.
    - Move tasks through `in_progress` to `done`.
    - Launch one subprocess per task (default uses `codex exec` with a task-specific prompt that references `AGENTS.md`).
  - Uses a shared `KanbanBoard` instance.

- `kanban/gui.py`
  - Tkinter graphical interface.
  - Responsibilities:
    - Render board columns and task cards.
    - Handle drag-and-drop move/reorder interactions.
    - Handle color selection modes (fixed colors, RNG, Cycle).
    - Handle scroll behavior for task columns.
    - Expose agent control button state transitions (`STOPPED`/`RUNNING`/`FINISHING`).
    - Save board via button and on window-close (`X`) event.
  - Uses a shared `KanbanBoard` instance, optional persistence path, and optional `AgentController`.

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
  - Verifies default `.board.json` behavior, explicit path behavior, and app-level agent controller wiring.

- `tests/test_gui.py`
  - GUI-focused unit tests for isolated UI behavior.
  - Covers the agent control button state cycle/styling and controller-driven state synchronization.

- `tests/test_agent.py`
  - Unit tests for autonomous agent runtime behavior.
  - Covers controller state transitions, task consumption, finishing semantics, and resume behavior.

## Generated/Transient Files

- `kanban/__pycache__/...`, `tests/__pycache__/...`
  - Python bytecode caches generated at runtime/test time.
  - Not part of business logic.

## Runtime Flow

1. Start app via `python -m kanban.app`.
2. `app.py` resolves board file and loads persisted state (if present).
3. `app.py` creates one `AgentController` (`agent.py`) with the shared board.
4. A single `KanbanBoard` instance is shared by GUI (`gui.py`), API server (`api.py`), and agent controller (`agent.py`).
5. In `RUNNING` mode, the agent controller consumes `todo` tasks and executes one subprocess per task.
6. User and API operations mutate the same in-memory model (`model.py`).
7. Board state is saved to JSON via GUI save action and on normal app shutdown/close.
