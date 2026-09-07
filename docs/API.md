# Local API

This API is for the running local app. It is not a hosted service or a stable public API contract.
The server listens on `127.0.0.1:8762` by default.

## Session checks

The index page supplies a random token for the current Python process.
The UI sends it in the `X-Local-Token` header. Every API request must use the current token.
POST requests must use `Content-Type: application/json`. The body limit is 36 MiB.
The server checks Host and Origin and does not enable cross-origin access.

Do not copy the token into a repository or enable network forwarding to the port.
Restarting the Python process changes the token.

## Common operations

| Method | Path | Input | Result |
| :--- | :--- | :--- | :--- |
| GET | `/api/info` | none | Name, version, paths, and local optional-tool availability. |
| GET | `/api/state` | none | Current application state and recent jobs. |
| GET | `/api/browse` | path, optional | Up to 1,500 visible folder entries. |
| GET | `/api/jobs/ID` | job ID in the path | Status, progress, result, or error. |
| POST | `/api/cancel` | id | Request cooperative job cancellation. |
| POST | `/api/upload` | name, base64 content | Save a new private inbox file. |
| POST | `/api/backup` | none | Write a database-only backup artifact. |

## Application operations

| Method | Path | Input | Result |
| :--- | :--- | :--- | :--- |
| GET | `/api/search` | q, mode: keyword or semantic or hybrid, extension, tag, root, limit; all optional | Return results, engine, and suggestions. |
| GET | `/api/preview` | id | Return one indexed record and text. |
| GET | `/api/duplicates` | none | Group matching nonempty content hashes. |
| GET | `/api/similar` | id | Return bounded word-overlap candidates. |
| POST | `/api/roots/add` | path; patterns and ocr, optional | Add a selected root without scanning it. |
| POST | `/api/roots/remove` | id | Remove its index records, not source files. |
| POST | `/api/scan` | id; force, optional | Start an index job. |
| POST | `/api/tags` | id, tags | Set at most 20 file tags. |
| POST | `/api/saved/add` | name, query; extension and tag, optional | Save a named search. |
| POST | `/api/saved/delete` | id | Delete one saved search. |
| POST | `/api/export` | query, format: json or csv; extension, tag, root, optional | Export at most 1,000 results. |
| POST | `/api/watch/start` | seconds | Start explicit interval rescans. |
| POST | `/api/watch/stop` | none | Stop interval rescans. |

### Example request body

Send this JSON to `POST /api/roots/add` with the current session token:

```json
{
  "path": "C:/Users/You/Documents",
  "ocr": false
}
```

Use paths from the computer running Python. Change the example path before sending the request.
A job-start response contains `job_id`. Read `/api/jobs/ID` until its status is terminal.
Read the error field when the job fails. Do not treat a queued response as a completed operation.

An artifact response contains its name, relative output path, and size. The browser download helper requests only paths under the app output directory.
Use `web/common.js` as the reference client for the exact response envelope and download route.

`POST /api/semantic/model` accepts a `path` to an existing trusted local neural model folder. An empty path selects the fitted local model.
