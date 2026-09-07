# Architecture

The browser imports local ES modules. It sends JSON requests to a loopback-only Python server. Session tokens, Host checks, Origin checks, size bounds, and a Content Security Policy restrict requests.

`app/service.py` exposes project operations. `localdesk/jobs.py` runs bounded tasks and persists status. Tasks check source paths and content hashes before creating new output files.

`localdesk/storage.py` runs SQLite in memory. `localdesk/vault.py` writes authenticated encrypted snapshots. User-login services use the OS credential store only after explicit installation.

Project operations are independent of the browser. Tests can instantiate `Application` with a temporary directory. UI tests start the real server and use the same API that normal users use.
