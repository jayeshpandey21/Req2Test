"""Local browser dashboard for the requirement-to-test pipeline."""
import json
import mimetypes
import os
import re
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .auth_store import AuthStore, SESSION_TTL_SECONDS
from .models import Analysis, TestCase
from .pipeline import plan_requirement, run_pipeline
from .report import to_markdown

MAX_REQUEST_BYTES = 256_000
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
AUTH_STORE = AuthStore(
    DATA_DIR / "req2test.sqlite3",
    database_url=os.environ.get("DATABASE_URL"),
)
APP_ORIGINS = {
    origin.strip().rstrip("/")
    for origin in os.environ.get("APP_ORIGINS", "").split(",")
    if origin.strip()
}
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "").casefold() == "true"
SESSION_COOKIE = "req2test_session"
RUN_ID_RE = re.compile(r"^[a-f0-9]{32}$")
ALLOWED_TARGETS = {
    "req2test.demo_target.auth_service",
    "req2test.demo_target.buggy_service",
}
STATIC_DIR = Path(__file__).with_name("static").resolve()


def _case_json(case: TestCase):
    return {
        "id": case.id,
        "requirement_id": case.requirement_id,
        "rule_ids": case.rule_ids,
        "title": case.title,
        "category": case.category,
        "steps": case.steps,
        "expected": case.expected,
        "executable": case.executable,
        "reason": case.reason,
    }


def _analysis_json(analysis: Analysis):
    return {
        "actors": analysis.actors,
        "rules": analysis.rules,
        "conditions": analysis.conditions,
        "acceptance_criteria": analysis.acceptance_criteria,
        "parameters": analysis.parameters,
    }


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "Req2TestDashboard/1.0"

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/health":
            try:
                AUTH_STORE.health_check()
            except Exception as error:
                self._send_json(503, {"status": "unavailable", "error": str(error)})
                return
            self._send_json(200, {"status": "ok"})
            return
        if path == "/api/session":
            user = self._current_user()
            self._send_json(200, {"user": user})
            return
        if path == "/api/history":
            user = self._require_user()
            if user is not None:
                self._send_json(200, {"runs": AUTH_STORE.list_runs(user["id"])})
            return
        if path.startswith("/api/history/"):
            user = self._require_user()
            if user is None:
                return
            run_id = path.rsplit("/", 1)[-1]
            if not RUN_ID_RE.fullmatch(run_id):
                self._send_json(404, {"error": "Report not found."})
                return
            saved_run = AUTH_STORE.get_run(user["id"], run_id)
            if saved_run is None:
                self._send_json(404, {"error": "Report not found."})
                return
            self._send_json(200, saved_run)
            return
        if path.startswith("/api/"):
            self._send_json(404, {"error": "Not found"})
            return
        relative_path = path.lstrip("/") or "index.html"
        file_path = (STATIC_DIR / relative_path).resolve()
        try:
            file_path.relative_to(STATIC_DIR)
        except ValueError:
            self._send_json(404, {"error": "Not found"})
            return
        if file_path.is_file():
            content = file_path.read_bytes()
            content_type, _ = mimetypes.guess_type(file_path.name)
            content_type = content_type or "application/octet-stream"
            if content_type.startswith(("text/", "application/javascript")):
                content_type += "; charset=utf-8"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(content)
            return
        if not STATIC_DIR.is_dir():
            self._send_json(503, {"error": "React UI is not built. Run `npm install` and `npm run build` in the frontend directory."})
            return
        self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        allowed_paths = {
            "/api/register",
            "/api/login",
            "/api/logout",
            "/api/plan",
            "/api/run",
        }
        if path not in allowed_paths:
            self._send_json(404, {"error": "Not found"})
            return
        try:
            self._check_request_origin()
            payload = self._read_payload()
            if path == "/api/register":
                self._register(payload)
                return
            if path == "/api/login":
                self._login(payload)
                return
            if path == "/api/logout":
                self._logout()
                return
            user = self._require_user()
            if user is None:
                return
            text = payload.get("text")
            if not isinstance(text, str) or not text.strip():
                raise ValueError("Enter a requirement before continuing.")
            if len(text) > 100_000:
                raise ValueError("Requirement text must be 100,000 characters or fewer.")
            if path == "/api/plan":
                self._plan(text)
            else:
                self._run(text, payload, user)
        except ValueError as error:
            self._send_json(400, {"error": str(error)})
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception as error:
            self._send_json(500, {"error": f"Pipeline failed: {error}"})

    def _read_payload(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValueError("Invalid request size.") from error
        if length <= 0 or length > MAX_REQUEST_BYTES:
            raise ValueError("Request body is empty or exceeds 256 KB.")
        try:
            payload = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise ValueError("Request must contain valid JSON.") from error
        if not isinstance(payload, dict):
            raise ValueError("Request must be a JSON object.")
        return payload

    def _check_request_origin(self):
        origin = self.headers.get("Origin")
        if not origin:
            return
        normalized_origin = origin.rstrip("/")
        parsed = urlparse(normalized_origin)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("Cross-origin requests are not allowed.")
        if APP_ORIGINS:
            allowed = normalized_origin.casefold() in {
                allowed_origin.casefold() for allowed_origin in APP_ORIGINS
            }
        else:
            host = self.headers.get("Host", "")
            allowed = parsed.netloc.casefold() == host.casefold()
        if not allowed:
            raise ValueError("Cross-origin requests are not allowed.")

    def _session_token(self):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
        except CookieError:
            return None
        morsel = cookie.get(SESSION_COOKIE)
        return morsel.value if morsel else None

    def _current_user(self):
        return AUTH_STORE.session_user(self._session_token())

    def _require_user(self):
        user = self._current_user()
        if user is None:
            self._send_json(401, {"error": "Sign in to continue."})
            return None
        return user

    def _register(self, payload):
        username = payload.get("username")
        password = payload.get("password")
        user = AUTH_STORE.register(username, password)
        self._establish_session(user)

    def _login(self, payload):
        user = AUTH_STORE.authenticate(payload.get("username"), payload.get("password"))
        if user is None:
            self._send_json(401, {"error": "Incorrect username or password."})
            return
        self._establish_session(user)

    def _establish_session(self, user):
        token = AUTH_STORE.create_session(user["id"])
        content = json.dumps({"user": user}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header(
            "Set-Cookie",
            f"{SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={SESSION_TTL_SECONDS}"
            + ("; Secure" if COOKIE_SECURE else ""),
        )
        self.end_headers()
        self.wfile.write(content)

    def _logout(self):
        AUTH_STORE.delete_session(self._session_token())
        content = json.dumps({"ok": True}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header(
            "Set-Cookie",
            f"{SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"
            + ("; Secure" if COOKIE_SECURE else ""),
        )
        self.end_headers()
        self.wfile.write(content)

    def _plan(self, text):
        req, analysis, cases, gaps = plan_requirement(text)
        self._send_json(200, {
            "requirement": {"id": req.id, "text": req.text},
            "analysis": _analysis_json(analysis),
            "cases": [_case_json(case) for case in cases],
            "missing_requirements": [gap.question for gap in gaps],
        })

    def _run(self, text, payload, user):
        approved = payload.get("approved_case_ids")
        if not isinstance(approved, list) or any(not isinstance(item, str) for item in approved):
            raise ValueError("Choose the scenarios to approve before generating tests.")
        _, _, cases, _ = plan_requirement(text)
        valid_case_ids = {case.id for case in cases if case.executable}
        if not set(approved).issubset(valid_case_ids):
            raise ValueError("The approved scenarios do not match this requirement. Analyze it again.")
        target = payload.get("target", "req2test.demo_target.auth_service")
        if target not in ALLOWED_TARGETS:
            raise ValueError("Select one of the available demo targets.")
        execute = payload.get("execute", True)
        if not isinstance(execute, bool):
            raise ValueError("The execute option must be true or false.")

        report, source = run_pipeline(
            text,
            execute=execute,
            target=target,
            out_dir=None,
            approved_case_ids=set(approved),
        )
        markdown = to_markdown(report)
        saved_run = AUTH_STORE.save_run(user["id"], report, markdown, source)
        self._send_json(200, {
            "id": saved_run["id"],
            "created_at": saved_run["created_at"],
            "report": report,
            "report_markdown": markdown,
            "test_source": source,
        })

    def _send_json(self, status, payload):
        content = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format_string, *args):
        print(f"[req2test] {self.address_string()} - {format_string % args}")


def serve(host="127.0.0.1", port=8000):
    if host not in ("127.0.0.1", "localhost", "::1", "0.0.0.0"):
        raise ValueError("Host must be localhost or 0.0.0.0.")
    if not 1 <= port <= 65535:
        raise ValueError("Port must be between 1 and 65535.")
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    print(f"Req2Test dashboard running at http://{host}:{port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Req2Test dashboard.")
    finally:
        server.server_close()
