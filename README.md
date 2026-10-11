# Autonomous Requirement-to-Test Generation Pipeline

This project turns a natural-language requirement into a structured test plan, executable pytest cases, and a final execution report.

Example requirement:

> Users should be able to log in using their email and password. If the password is incorrect five times, the account should be temporarily locked.

A QA engineer would normally read the requirement, identify scenarios, write tests, run them, and summarize the results. This application automates that workflow.

## What this project does

- Accepts a requirement as text or as a file
- Extracts actors, rules, conditions, thresholds, and acceptance criteria
- Generates positive, negative, boundary, security, and edge-case scenarios
- Converts supported requirements into executable pytest tests
- Runs the generated tests in isolation
- Produces a report with case status and traceability back to the original requirement

The key distinction is this:
- Generating a test case is not the same as executing it
- The system tracks both stages separately and clearly marks cases as passed, failed, skipped, or unexecuted

## Core features

1. Requirement ingestion
   - Paste text or upload a requirement document, user story, acceptance criteria, or API specification.

2. Test scenario generation
   - Generate positive, negative, boundary, security, and edge-case scenarios.

3. Test code generation
   - Convert approved scenarios into pytest or API tests.

4. Test execution
   - Execute generated tests inside an isolated environment and capture results.

5. Reporting and traceability
   - Show passed, failed, skipped, and unexecuted tests with traceability links to the source requirement.

## Project pipeline

```text
Step 1 — Requirement input
    Text, user story, or specification

Step 2 — Requirement analyzer
    Extract rules, conditions, actors, and acceptance criteria

Step 3 — Test planner
    Identify scenarios, missing requirements, and edge cases

Step 4 — Test generator
    Produce structured cases and executable test files

Step 5 — Isolated test runner
    Run approved tests against a target system

Step 6 — Results dashboard
    Report results, failure evidence, coverage, and traceability
```

## Quick start

```bash
pip install -r requirements.txt
npm --prefix frontend install
npm --prefix frontend run build
python -m req2test --web
python -m req2test "Users should be able to log in using their email and password. If the password is incorrect five times, the account should be temporarily locked."
python -m req2test "Users should be able to log in using their email and password. If the password is incorrect five times, the account should be temporarily locked." --target req2test.demo_target.buggy_service
python -m req2test --file requirement.txt --no-run
pytest tests/
```

The browser dashboard is implemented in React and served by the Python backend at `http://127.0.0.1:8000`. Create an account with a unique username and a 12-character minimum password, then sign in to use a private workspace. The dashboard supports pasted text and `.txt`/`.md` files, scenario approval, test execution, a pipeline map, and a scenario-category pie chart. The Test scenarios and Execution report tabs show current work and the signed-in user's saved history. Passwords are stored as salted PBKDF2 hashes; sessions use HttpOnly, SameSite cookies. User accounts and reports are stored locally in `data/req2test.sqlite3`. This is a local prototype, not a hardened public internet service. Press `Ctrl+C` in the terminal to stop the local server.

Generated output is written to `./out/`:
- `test_generated.py`
- `report.md`
- `report.json`

Dashboard runs are stored per account in the local SQLite database instead of being written to the shared `out/` directory.

## Public deployment (Vercel + Render)

The React dashboard can be hosted on Vercel, but its Python API and persistent
account/report database must also be deployed. The checked-in `render.yaml`
defines a Python API service and a Render-managed PostgreSQL database.
`frontend/vercel.json` proxies `/api/*` to the Python service so browser
sessions remain same-origin.

1. In Vercel, import this repository and set the project root to `frontend`.
   Use `npm run build` as the build command and `dist` as the output directory.
2. In Render, create a Blueprint from this repository using `render.yaml`.
   Review the database plan and price shown by Render before creating resources.
   Set `APP_ORIGINS` to the exact public Vercel origin (for example,
   `https://req2test.vercel.app`). Render provides `DATABASE_URL` to the API;
   `COOKIE_SECURE` is enabled by the Blueprint.
3. Deploy the Vercel project and verify `/api/health` returns `{"status":"ok"}`.

The default Vercel rewrite targets
`https://req2test-api-jayeshpandey21.onrender.com`. If Render assigns a
different service URL, update that destination in `frontend/vercel.json` and
redeploy the Vercel project. Add the Vercel production origin to Render's
`APP_ORIGINS` setting, without a trailing slash. Render's Free web service
sleeps when idle; review its current plan limits before deploying. Preview
deployments are not allowed by default; add an exact preview origin only if it
is intentionally trusted.

For local development, omit `DATABASE_URL` to keep using SQLite. When the
`VERCEL` environment variable is set, Vite builds into `frontend/dist`;
otherwise it builds into the Python server's `req2test/static` directory.

## Plugging in your own target system

Expose a module with the following contract:

```python
VALID_USER = (email, password)


def make_service(max_attempts):
    return object_with_login_method()
```

The login method should return:

```python
{"success": bool, "locked": bool, "message": str}
```

Then pass the target module to the CLI using `--target your.module`.

## Current scope

- Rule-based analyzer and planner
- Login/lockout requirement templates are executable
- Other requirement classes are planned but may remain unexecuted when no template exists
- Explicitly distinguishes generated vs executed stages in the report
- Per-user login, sessions, and saved execution reports

## Project structure

```text
req2test/
    __init__.py
    __main__.py
    analyzer.py
    planner.py
    generator.py
    runner.py
    report.py
    pipeline.py
    models.py
    auth_store.py
    demo_target/
        auth_service.py
        buggy_service.py
    static/                 # Built React dashboard assets

frontend/
    src/
        main.jsx            # React dashboard and scenario pie chart
        styles.css
    package.json
    vite.config.js

tests/
    test_pipeline.py
    test_auth_store.py
```

## Next improvements

- LLM-backed requirement analyzer
- More requirement templates beyond login/lockout
- API specification ingestion
- Docker-based isolated execution for untrusted targets
