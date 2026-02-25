# Feature Ideas

## Task Management UX

- [ ] Show a small `X` button on task-card hover so users can delete tasks quickly without opening extra dialogs.
- [ ] Add a fourth column named `Ignore` so tasks can be removed from the active `To Do` queue temporarily.
- [ ] Support bulk actions (multi-select move, ignore, delete) for faster backlog cleanup.
- [ ] Add task edit mode (rename title, change color, add notes) via right-click or double-click.

## Agent Execution

- [ ] Capture stdout/stderr and exit code for each agent run and persist it per task.
- [ ] Open task run details by double-clicking completed tasks (`Done`) to view execution output/history.
- [ ] Add retry policy controls for failed tasks (manual retry, auto-retry with max attempts, backoff).
- [ ] Add per-task timeout and cancel controls for long-running/stuck agent executions.
- [ ] Allow templated command/prompt profiles (e.g., `fast`, `deep`, `review`) selectable from UI.

## Board Behavior

- [ ] Add explicit `Failed` status (or badge) so failed executions are visible without reading logs.
- [ ] Persist and display timestamps (`created_at`, `started_at`, `finished_at`) for each task.
- [ ] Add optional dependencies/blockers so tasks can be queued but not executed until prerequisites are done.
- [ ] Add auto-stop rules (e.g., stop after N tasks, stop on first failure).

## API / Integrations

- [ ] Add API endpoints for delete/update task (`DELETE /tasks/{id}`, `PATCH /tasks/{id}`).
- [ ] Add API support for `Ignore` column operations and filtering by status.
- [ ] Provide webhook/event stream integration for state changes (`task_started`, `task_done`, `task_failed`).
- [ ] Add simple auth mode for API usage in shared environments
- [ ] Add support for integrating with other AI platforms than Codex.

## Observability / Safety

- [ ] Add an activity feed panel showing recent task transitions and agent invocations.
- [ ] Add persistent execution logs directory with rotation and retention controls.
- [ ] Add confirmation safeguards for destructive actions (delete, clear column, bulk move).
- [ ] Add health indicators in UI (agent running, queue size, active task, last error).
- [ ] Store token usage on a per-task basis, allow accounting or reporting on token usage for the entire board or sets of tasks.
