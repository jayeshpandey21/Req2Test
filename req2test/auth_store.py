"""SQLite/PostgreSQL accounts, sessions, and per-user execution history."""
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

PASSWORD_ITERATIONS = 310_000
SESSION_TTL_SECONDS = 60 * 60 * 24 * 7
USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.-]{3,32}$")
_DUMMY_SALT = bytes.fromhex("583b1243cda01f634197d1fcb896cc51")
_DUMMY_HASH = hashlib.pbkdf2_hmac(
    "sha256", b"req2test-invalid-user", _DUMMY_SALT, PASSWORD_ITERATIONS
)


class AuthStore:
    def __init__(self, database_path: Path, database_url=None):
        self.database_url = database_url
        self.database_path = Path(database_path) if database_path is not None else None
        self._postgres = database_url is not None
        if self._postgres:
            parsed = urlparse(database_url)
            if parsed.scheme not in ("postgres", "postgresql"):
                raise ValueError("DATABASE_URL must use the postgres or postgresql scheme.")
        else:
            if self.database_path is None:
                raise ValueError("A SQLite database path or PostgreSQL URL is required.")
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self):
        if self._postgres:
            import pg8000.dbapi

            parsed = urlparse(self.database_url)
            connection = pg8000.dbapi.connect(
                user=unquote(parsed.username or ""),
                password=unquote(parsed.password or ""),
                host=parsed.hostname,
                port=parsed.port or 5432,
                database=unquote(parsed.path.lstrip("/")),
                ssl_context=True,
                timeout=10,
            )
        else:
            connection = sqlite3.connect(self.database_path, timeout=10)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA busy_timeout = 10000")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _execute(self, connection, query, parameters=()):
        if self._postgres:
            query = query.replace("?", "%s")
            cursor = connection.cursor()
            cursor.execute(query, parameters)
            return _MappingCursor(cursor)
        return connection.execute(query, parameters)

    def _initialize(self):
        with self._connect() as connection:
            statements = (
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    username_key TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    expires_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS sessions_expiry_idx ON sessions(expires_at);
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    created_at TEXT NOT NULL,
                    report_json TEXT NOT NULL,
                    report_markdown TEXT NOT NULL,
                    test_source TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS runs_user_date_idx
                    ON runs(user_id, created_at DESC);
                """
            )
            for statement in statements.split(";"):
                if statement.strip():
                    self._execute(connection, statement)

    def health_check(self):
        with self._connect() as connection:
            self._execute(connection, "SELECT 1")

    def _integrity_errors(self):
        if self._postgres:
            import pg8000.dbapi

            return (pg8000.dbapi.IntegrityError,)
        return (sqlite3.IntegrityError,)

    @staticmethod
    def validate_registration(username, password):
        if not isinstance(username, str) or not USERNAME_RE.fullmatch(username):
            raise ValueError(
                "Username must be 3–32 characters using letters, numbers, dots, dashes, or underscores."
            )
        if not isinstance(password, str) or not 12 <= len(password) <= 256:
            raise ValueError("Password must be between 12 and 256 characters.")

    @staticmethod
    def _password_hash(password, salt=None):
        salt = salt or secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS
        )
        return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt.hex()}${digest.hex()}"

    @staticmethod
    def _password_matches(password, encoded_hash):
        try:
            algorithm, iterations, salt_hex, expected_hex = encoded_hash.split("$")
            if algorithm != "pbkdf2_sha256":
                return False
            actual = hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
            )
            return hmac.compare_digest(actual.hex(), expected_hex)
        except (ValueError, TypeError, UnicodeEncodeError):
            return False

    @staticmethod
    def _public_user(row):
        return {"id": row["id"], "username": row["username"]}

    def register(self, username, password):
        self.validate_registration(username, password)
        normalized_username = username.strip()
        user_id = uuid.uuid4().hex
        created_at = datetime.now(timezone.utc).isoformat()
        encoded_hash = self._password_hash(password)
        try:
            with self._connect() as connection:
                self._execute(
                    connection,
                    """
                    INSERT INTO users(id, username, username_key, password_hash, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        normalized_username,
                        normalized_username.casefold(),
                        encoded_hash,
                        created_at,
                    ),
                )
        except self._integrity_errors() as error:
            raise ValueError("That username is already registered.") from error
        return {"id": user_id, "username": normalized_username}

    def authenticate(self, username, password):
        if not isinstance(username, str) or not isinstance(password, str):
            return None
        username_key = username.strip().casefold()
        with self._connect() as connection:
            row = self._execute(
                connection,
                "SELECT id, username, password_hash FROM users WHERE username_key = ?",
                (username_key,),
            ).fetchone()
        if row is None:
            self._password_matches(password, self._dummy_hash_string())
            return None
        if not self._password_matches(password, row["password_hash"]):
            return None
        return self._public_user(row)

    @staticmethod
    def _dummy_hash_string():
        return (
            f"pbkdf2_sha256${PASSWORD_ITERATIONS}${_DUMMY_SALT.hex()}${_DUMMY_HASH.hex()}"
        )

    def create_session(self, user_id):
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("ascii")).hexdigest()
        expires_at = int(time.time()) + SESSION_TTL_SECONDS
        with self._connect() as connection:
            self._execute(connection, "DELETE FROM sessions WHERE expires_at <= ?", (int(time.time()),))
            self._execute(
                connection,
                "INSERT INTO sessions(token_hash, user_id, expires_at) VALUES (?, ?, ?)",
                (token_hash, user_id, expires_at),
            )
        return raw_token

    def session_user(self, raw_token):
        if not isinstance(raw_token, str) or not raw_token:
            return None
        token_hash = hashlib.sha256(raw_token.encode("ascii", errors="ignore")).hexdigest()
        now = int(time.time())
        with self._connect() as connection:
            self._execute(connection, "DELETE FROM sessions WHERE expires_at <= ?", (now,))
            row = self._execute(
                connection,
                """
                SELECT users.id, users.username
                FROM sessions
                JOIN users ON users.id = sessions.user_id
                WHERE sessions.token_hash = ? AND sessions.expires_at > ?
                """,
                (token_hash, now),
            ).fetchone()
        return self._public_user(row) if row else None

    def delete_session(self, raw_token):
        if not isinstance(raw_token, str) or not raw_token:
            return
        token_hash = hashlib.sha256(raw_token.encode("ascii", errors="ignore")).hexdigest()
        with self._connect() as connection:
            self._execute(connection, "DELETE FROM sessions WHERE token_hash = ?", (token_hash,))

    def save_run(self, user_id, report, report_markdown, test_source):
        run_id = uuid.uuid4().hex
        created_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            self._execute(
                connection,
                """
                INSERT INTO runs(id, user_id, created_at, report_json, report_markdown, test_source)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    user_id,
                    created_at,
                    json.dumps(report),
                    report_markdown,
                    test_source,
                ),
            )
        return {"id": run_id, "created_at": created_at}

    def list_runs(self, user_id):
        with self._connect() as connection:
            rows = self._execute(
                connection,
                """
                SELECT id, created_at, report_json
                FROM runs
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT 100
                """,
                (user_id,),
            ).fetchall()
        result = []
        for row in rows:
            report = json.loads(row["report_json"])
            result.append(
                {
                    "id": row["id"],
                    "created_at": row["created_at"],
                    "requirement": report["requirement"],
                    "summary": report["summary"],
                    "total": report["total"],
                }
            )
        return result

    def get_run(self, user_id, run_id):
        with self._connect() as connection:
            row = self._execute(
                connection,
                """
                SELECT id, created_at, report_json, report_markdown, test_source
                FROM runs WHERE id = ? AND user_id = ?
                """,
                (run_id, user_id),
            ).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "created_at": row["created_at"],
            "report": json.loads(row["report_json"]),
            "report_markdown": row["report_markdown"],
            "test_source": row["test_source"],
        }


class _MappingCursor:
    def __init__(self, cursor):
        self.cursor = cursor

    def fetchone(self):
        row = self.cursor.fetchone()
        if row is None:
            return None
        return dict(zip((column[0] for column in self.cursor.description), row))

    def fetchall(self):
        columns = [column[0] for column in self.cursor.description]
        return [dict(zip(columns, row)) for row in self.cursor.fetchall()]
