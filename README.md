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

## Run

```bash
python -m kanban.app --host 127.0.0.1 --port 8000
```

To load existing board data on startup and autosave on exit:

```bash
python -m kanban.app --host 127.0.0.1 --port 8000 --board-file ./board.json
```

In the GUI, click `Save Board` to write the current board to a JSON file at any time.
If `--board-file` is not provided, the app automatically uses `./.board.json` in the current working directory.
If that file exists, it is loaded on startup; when the window close button (`X`) is used, the board is saved before exit.

When started, the API is available at:

`http://127.0.0.1:8000`

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
