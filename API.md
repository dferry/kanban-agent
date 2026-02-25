# HTTP API

This project exposes a JSON API for managing kanban tasks.

## Base URL

`http://127.0.0.1:8000`

If you run with a different host/port, replace accordingly.

## Data Model

Task object:

```json
{
  "id": 1,
  "title": "Implement drag and drop",
  "status": "todo",
  "color": "#3b82f6"
}
```

Fields:
- `id` (integer): server-assigned unique task ID
- `title` (string): task title
- `status` (string): one of:
  - `todo`
  - `in_progress`
  - `done`
- `color` (string): HTML color code in `#RRGGBB` format

## Endpoints

## 1) List Tasks

`GET /tasks`

Returns all tasks in the board.

Example:

```bash
curl -s http://127.0.0.1:8000/tasks
```

Success response (`200 OK`):

```json
{
  "tasks": [
    {
      "id": 1,
      "title": "Implement drag and drop",
      "status": "todo"
    }
  ]
}
```

## 2) Create Task

`POST /tasks`

Creates a new task in the `todo` column.

Request headers:
- `Content-Type: application/json`

Request body:

```json
{
  "title": "Write unit tests",
  "color": "#22c55e"
}
```

Notes:
- `color` is optional.
- If omitted, default is `#ef4444`.
- If provided, it must match `#RRGGBB`.

Example:

```bash
curl -s -X POST http://127.0.0.1:8000/tasks \
  -H 'Content-Type: application/json' \
  -d '{"title":"Write unit tests","color":"#22c55e"}'
```

Success response (`201 Created`):

```json
{
  "id": 2,
  "title": "Write unit tests",
  "status": "todo",
  "color": "#22c55e"
}
```

Validation errors (`400 Bad Request`):
- Missing or empty title:

```json
{
  "error": "title must be a non-empty string"
}
```

Other possible `400` errors:
- `{"error":"missing request body"}`
- `{"error":"invalid content length"}`
- `{"error":"invalid json"}`
- `{"error":"json body must be an object"}`
- `{"error":"color must be an HTML hex code in #RRGGBB format"}`

## 3) Move Task

`POST /tasks/{id}/move`

Moves an existing task to a different status.

Path parameter:
- `id` (integer): task ID

Request headers:
- `Content-Type: application/json`

Request body:

```json
{
  "status": "in_progress"
}
```

Allowed status values:
- `todo`
- `in_progress`
- `done`

Example:

```bash
curl -s -X POST http://127.0.0.1:8000/tasks/2/move \
  -H 'Content-Type: application/json' \
  -d '{"status":"done"}'
```

Success response (`200 OK`):

```json
{
  "id": 2,
  "title": "Write unit tests",
  "status": "done",
  "color": "#22c55e"
}
```

Errors:
- Invalid status (`400 Bad Request`):

```json
{
  "error": "invalid status"
}
```

- Task not found (`404 Not Found`):

```json
{
  "error": "task not found"
}
```

## Common Errors

- Unknown route: `404` with

```json
{
  "error": "not found"
}
```

## Quick Workflow Example

```bash
# 1) Create
curl -s -X POST http://127.0.0.1:8000/tasks \
  -H 'Content-Type: application/json' \
  -d '{"title":"Ship MVP","color":"#a855f7"}'

# 2) List
curl -s http://127.0.0.1:8000/tasks

# 3) Move to in progress
curl -s -X POST http://127.0.0.1:8000/tasks/1/move \
  -H 'Content-Type: application/json' \
  -d '{"status":"in_progress"}'

# 4) Move to done
curl -s -X POST http://127.0.0.1:8000/tasks/1/move \
  -H 'Content-Type: application/json' \
  -d '{"status":"done"}'
```
