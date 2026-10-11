import sqlite3

import pytest

from req2test.auth_store import AuthStore, SESSION_TTL_SECONDS


def test_registration_hashes_password_and_authenticates_case_insensitively(tmp_path):
    store = AuthStore(tmp_path / "accounts.sqlite3")
    user = store.register("Qa_Tester", "correct horse battery staple")

    assert user["username"] == "Qa_Tester"
    assert store.authenticate("qa_tester", "correct horse battery staple") == user
    assert store.authenticate("Qa_Tester", "incorrect password") is None

    with sqlite3.connect(store.database_path) as connection:
        password_hash = connection.execute(
            "SELECT password_hash FROM users WHERE id = ?", (user["id"],)
        ).fetchone()[0]
    assert "correct horse battery staple" not in password_hash
    assert password_hash.startswith("pbkdf2_sha256$")


def test_registration_rejects_invalid_credentials_and_duplicate_usernames(tmp_path):
    store = AuthStore(tmp_path / "accounts.sqlite3")

    with pytest.raises(ValueError, match="Username"):
        store.register("x", "a sufficiently long password")
    with pytest.raises(ValueError, match="Password"):
        store.register("qa_tester", "short")

    store.register("qa_tester", "correct horse battery staple")
    with pytest.raises(ValueError, match="already registered"):
        store.register("QA_TESTER", "another sufficiently long password")


def test_sessions_expire_and_are_revocable(tmp_path, monkeypatch):
    store = AuthStore(tmp_path / "accounts.sqlite3")
    user = store.register("qa_tester", "correct horse battery staple")
    now = 1_800_000_000
    monkeypatch.setattr("req2test.auth_store.time.time", lambda: now)
    token = store.create_session(user["id"])

    assert store.session_user(token) == user
    monkeypatch.setattr("req2test.auth_store.time.time", lambda: now + SESSION_TTL_SECONDS + 1)
    assert store.session_user(token) is None

    monkeypatch.setattr("req2test.auth_store.time.time", lambda: now)
    token = store.create_session(user["id"])
    store.delete_session(token)
    assert store.session_user(token) is None


def test_saved_reports_are_isolated_by_user(tmp_path):
    store = AuthStore(tmp_path / "accounts.sqlite3")
    owner = store.register("owner_user", "correct horse battery staple")
    other = store.register("other_user", "another correct horse battery staple")
    report = {
        "requirement": {"id": "REQ-1", "text": "private requirement"},
        "summary": {"passed": 1, "failed": 0, "skipped": 0, "unexecuted": 0},
        "total": 1,
        "cases": [],
    }

    saved = store.save_run(owner["id"], report, "# Private report", "test_code = True")

    assert len(store.list_runs(owner["id"])) == 1
    assert store.list_runs(other["id"]) == []
    assert store.get_run(owner["id"], saved["id"])["report"] == report
    assert store.get_run(other["id"], saved["id"]) is None
