# Kanban Agent

A Python kanban board for Linux with:
- Tkinter GUI (mouse drag and drop between columns)
- Built-in JSON API server for creating and moving tasks

## Features
- Three workflow columns: `To Do`, `In Progress`, `Done`
- Create tasks from the GUI
- Set new-task color from buttons: red, green, blue, purple, cyan, magenta, or RNG
- Render each task as a colored rectangle in the board
- Move tasks by clicking and dragging between columns
- Reorder tasks within a column via drag and drop
- Vertical scrollbar in each column for long task lists
- Save board state to JSON (tasks, order within each column, and colors)
- Load board state from JSON on startup
- JSON API to create, list, and move tasks programmatically
- Shared in-memory task store between GUI and API
- Agent runner that can consume `To Do` tasks automatically via Codex CLI subprocesses

## Run

Navigate to project directory and start the Kanban Agent with:


```bash
PYTHONPATH=/path/to/this/repo python -m kanban.app --host 127.0.0.1 --port 8000
```

By default, your board is automatically saved when closing program with X button and loaded when starting the agent. The board is stored as a hidden file as .board.json

You can specify an explicit board file with the argument:

```bash
--board-file ./board.json
```

In the GUI, click `Save Board` to write the current board to a JSON file at any time.
If `--board-file` is not provided, the app automatically uses `./.board.json` in the current working directory.
If that file exists, it is loaded on startup; when the window close button (`X`) is used, the board is saved before exit.

When started, the API is available by default at:

`http://127.0.0.1:8000`

## Agent Control Button

The top-row agent button controls autonomous task execution:

- `STOPPED` (red): idle, no task consumption.
- Click once `STOPPED` (red) -> `RUNNING` (green) to consume `To Do` tasks in order.
  - For each task: move to `In Progress`, launch an independent `codex exec` subprocess with a task prompt, then move to `Finished` when the subprocess exits.
- Click again `RUNNING` (green) -> `FINISHING` (yellow): do not start new tasks, wait for the current subprocess to finish, then transition to `STOPPED`.
- Click `FINISHING` (yellow) -> `RUNNING` (green) to resume continuous mode without stopping.

The default task prompt tells Codex this is one task in a larger project and to read `AGENTS.md`.

At the bottom of the UI, the `Agent Execution Box` lets you edit:
- Command (default: `codex exec`)
- Prompt template

The controller reads these values for each new task execution, so changes apply while the board is running.
Use `TASK_TEXT` in the prompt template to inject the task title from the card being executed.

The same box also shows the last command/prompt values actually used for the most recent task invocation.

## API

### List tasks

```bash
curl -s http://127.0.0.1:8000/tasks
```

### Create task

```bash
curl -s -X POST http://127.0.0.1:8000/tasks \
  -H 'Content-Type: application/json' \
  -d '{"title":"Implement drag and drop", "color":"#3b82f6"}'
```

### Move task

```bash
curl -s -X POST http://127.0.0.1:8000/tasks/1/move \
  -H 'Content-Type: application/json' \
  -d '{"status":"in_progress"}'
```

Valid statuses:
- `todo`
- `in_progress`
- `done`

## Tests

```bash
python -m unittest discover -s tests -v
```
