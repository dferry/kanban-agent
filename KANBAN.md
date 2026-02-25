# Kanban Integration Guide

This project provides a shared Kanban board that agents can use for planning and execution across repositories.

## How To Use This Board

- Add new work as tasks in the `To Do` column.
- Tasks in `To Do` are queued work and will be completed in the future by the automation/agent runner.
- Keep task titles specific and implementation-oriented so another agent can execute them directly.

## Add A Task Through The HTTP API

Use `POST /tasks` to enqueue a new task in `todo`:

```bash
curl -s -X POST http://127.0.0.1:8000/tasks \
  -H 'Content-Type: application/json' \
  -d '{"title":"Add retry logic for failed webhook deliveries"}'
```

Expected result:
- The task is created in the `To Do` column (`status: "todo"`).
- It will be picked up and completed in a future execution cycle.
