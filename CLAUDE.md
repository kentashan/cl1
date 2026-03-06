# CLAUDE.md

This file provides guidance for AI assistants working in this repository.

## Project Overview

**cl1** is a Japan Google Trends daily fetcher. It automatically retrieves
trending searches in Japan via the Google Trends API, accumulates the results
in a JSON file, and keeps a 30-day rolling history. A GitHub Actions workflow
runs the script once per day and commits the output back to the repository.

## Repository Structure

```
cl1/
├── fetch_trends.py              # Main script — fetches and stores trends
├── requirements.txt             # Python dependencies (requests==2.32.3)
├── trends.json                  # Generated output (auto-committed by CI)
├── .github/
│   └── workflows/
│       └── daily_trends.yml     # Scheduled GitHub Actions workflow
└── README.md                    # Project readme
```

## Key Files

### `fetch_trends.py`

The single Python module that does all the work:

| Function | Purpose |
|---|---|
| `fetch_japan_trends()` | Calls the Google Trends `dailytrends` endpoint for `geo=JP`, strips the XSSI prefix (`)]}'`), and returns a flat list of trend dicts |
| `load_existing(path)` | Reads the current `trends.json` or returns a blank skeleton `{"updated_at": null, "history": {}}` |
| `save(path, payload)` | Serialises the payload to `trends.json` with `ensure_ascii=False` and 2-space indentation |
| `main()` | Orchestrates fetch → merge → prune → save → log |

**Output schema for `trends.json`:**

```json
{
  "updated_at": "<ISO-8601 UTC timestamp>",
  "history": {
    "YYYY-MM-DD": [
      {
        "date": "YYYYMMDD",
        "rank": 1,
        "query": "trend title",
        "traffic": "200K+",
        "articles": [
          { "title": "...", "url": "...", "source": "..." }
        ]
      }
    ]
  }
}
```

- At most **3 articles** are stored per trend item.
- History is pruned to the **most recent 30 days** on every run.
- Timestamps are stored as **UTC** even though the Google Trends query uses
  the JST timezone offset (`tz=-540`).

### `.github/workflows/daily_trends.yml`

- **Trigger:** `schedule` (cron `0 0 * * *` — UTC midnight / JST 09:00) plus
  `workflow_dispatch` for on-demand runs.
- **Permission:** `contents: write` so the workflow can commit and push
  `trends.json`.
- **Steps:** checkout → Python 3.12 setup with pip cache → install deps →
  run script → commit & push only when `trends.json` changed.
- Commit author is `github-actions[bot]`; message format:
  `chore: update Japan trends YYYY-MM-DD`.

## Development Workflow

### Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Running locally

```bash
python fetch_trends.py
```

This writes/updates `trends.json` in the working directory and prints the
top 10 trends to stdout.

### Dependencies

Only one runtime dependency: `requests==2.32.3` (pinned exact version).

When adding new dependencies:
1. Add the package with a pinned version to `requirements.txt`.
2. Document why it is needed in the PR description.

### No test suite / linter config yet

There are currently no automated tests or linter configuration files. When
adding tests, use **pytest**. For linting, **ruff** is the preferred tool for
this codebase style.

## Conventions

### Python style

- Python **3.12** (uses modern union syntax, `list[dict]` type hints, etc.).
- Functions are annotated with return types.
- Keep the script self-contained in `fetch_trends.py`; avoid splitting into
  multiple modules unless the file grows significantly.
- `ensure_ascii=False` in `json.dump` — Japanese characters must be stored
  as-is, not escaped.

### Git / Branch conventions

- Default branch: `main` (remote) / `master` (local default).
- Feature/fix branches follow the pattern:
  `<author>/<slug>` or `claude/<task-slug>-<session-id>`.
- Commit message format (from CI example):
  - `chore:` for automated/maintenance commits
  - `feat:` for new features
  - `fix:` for bug fixes
- Only `trends.json` is ever auto-committed by the workflow; all other changes
  go through normal PRs.

### What NOT to change

- The XSSI prefix stripping logic (`raw.index("\n") + 1`) is intentional —
  Google Trends prepends `)]}',\n` to every response.
- The 30-day history cap prevents unbounded file growth; do not remove it
  without adding an alternative size guard.
- The `timeout=30` on the HTTP request is intentional; do not remove it.

## CI/CD

All CI runs through GitHub Actions. The only workflow is `daily_trends.yml`.

| What | Value |
|---|---|
| Runner | `ubuntu-latest` |
| Python | `3.12` |
| pip cache | enabled (keyed on `requirements.txt`) |
| Secrets needed | `GITHUB_TOKEN` (auto-provided) |

To trigger manually: **Actions → Daily Japan Trends → Run workflow**.
