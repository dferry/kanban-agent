# Kanban Agent

A Python kanban board for Linux with:
- Automatic execution of tasks with Codex CLI
- Built-in JSON API server so agents can create new tasks autonomously
- Tkinter GUI for user to manually create tasks and move them between columns
    - Colors!
    - Control over how tasks are prompted to Codex CLI
    - An agent control button to stop and start autonomous task completion

## Run Instructions

Check out this repository on your machine. Then create a second repository for your desired project:

- Run `git init` so Codex CLI doesn't balk at running
- Run Codex CLI once so you can trust the directory
- Copy KANBAN.md from this repo to your project directory (the task agent looks for this by default)
- Create an AGENTS.md file or have your project agent create one as your first task (the task agent looks for this by default)

Navigate to project directory and start the Kanban Agent with:


```bash
python -m kanban.app --host 127.0.0.1 --port 8000
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

The controller reads these values for each new task execution, so changes apply while the board is running. These values are persisted in the board JSON file and restored on next startup. Use `TASK_TEXT` in the prompt template to inject the task title from the card being executed.

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
