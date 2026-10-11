"""Step 3 - Test planner: scenarios, missing requirements, edge cases."""
import re
from .models import Analysis, Gap, Requirement, TestCase


def _rule(a: Analysis, pattern):
    ids = [r["id"] for r in a.rules if re.search(pattern, r["text"], re.I)]
    return ids or [a.rules[0]["id"]]


def plan(req: Requirement, a: Analysis):
    cases, gaps = [], []

    def add(cat, title, steps, expected, template, rules, executable=True, reason=""):
        cases.append(TestCase(f"TC-{len(cases) + 1:03d}", req.id, rules, title, cat,
                              steps, expected, template, executable, reason))

    if a.parameters.get("feature") == "login":
        n = a.parameters.get("max_failed_attempts")
        login_r = _rule(a, r"log ?in")
        lock_r = _rule(a, r"lock|incorrect")
        add("positive", "Valid email and password logs in",
            ["Submit valid credentials"], "Login succeeds, account not locked", "valid_login", login_r)
        add("negative", "Wrong password is rejected",
            ["Submit valid email with wrong password"], "Login fails", "wrong_password", login_r)
        add("negative", "Unknown email is rejected",
            ["Submit unregistered email"], "Login fails", "unknown_email", login_r)
        add("negative", "Empty email is rejected", ["Submit empty email"], "Login fails", "empty_email", login_r)
        add("negative", "Empty password is rejected", ["Submit empty password"], "Login fails", "empty_password", login_r)
        add("negative", "Malformed email is rejected", ["Submit 'not-an-email'"], "Login fails", "malformed_email", login_r)
        if n:
            add("boundary", f"{n - 1} wrong passwords do not lock the account",
                [f"Fail login {n - 1} times", "Login with correct password"],
                "Login succeeds", "n_minus_1_then_success", lock_r)
            add("boundary", f"{n} wrong passwords lock the account",
                [f"Fail login {n} times", "Login with correct password"],
                "Correct password is rejected and account reported locked", "lock_at_n", lock_r)
            add("boundary", "Locked account stays locked for further attempts",
                [f"Fail login {n} times", "Attempt several more logins"],
                "All attempts rejected while locked", "stays_locked", lock_r)
        add("security", "Errors do not reveal whether an email exists",
            ["Fail with unknown email", "Fail with wrong password"],
            "Both responses carry the same message", "no_user_enumeration", login_r)
        add("security", "SQL-injection payloads are rejected",
            ["Submit injection strings as email and password"], "Login fails", "sql_injection", login_r)
        add("security", "Password is never echoed in the response",
            ["Fail login with a wrong password"], "Response does not contain the password", "password_not_echoed", login_r)
        add("edge", "Very long inputs are handled safely",
            ["Submit 10k-char email and 100k-char password"], "Login fails without crashing", "very_long_input", login_r)
        if a.parameters.get("lockout"):
            add("edge", "Lockout expires after the lock period",
                ["Lock the account", "Wait for lock period", "Login with correct password"],
                "Login succeeds", "lockout_expires", lock_r, executable=False,
                reason="Lock duration is not specified in the requirement")

        q = [
            None if a.parameters["lockout_duration_specified"] else "How long is 'temporarily'? (minutes/hours, fixed or escalating)",
            "Does the failed-attempt counter reset after a successful login?",
            "Do failed attempts for unknown emails count toward any limit?",
            "Is email matching case-insensitive / whitespace-trimmed?",
            "Are there password length or complexity rules?",
            "What exactly does a locked response look like (message, status code)?",
            None if n else "How many failed attempts trigger the lock? (no number found)",
        ]
        gaps = [Gap(req.id, x) for x in q if x]
    else:
        # Generic fallback: scenarios from conditions/rules, not executable without an adapter.
        why = "No executable template for this requirement type; needs a target adapter"
        for i, c in enumerate(a.conditions, 1):
            rid = _rule(a, re.escape(c["when"][:20]))
            add("positive", f"When {c['when']}: {c['then']}", ["Create the condition"], c["then"],
                f"generic_{i}", rid, False, why)
            add("negative", f"When NOT ({c['when']}): outcome does not occur", ["Violate the condition"],
                f"Not: {c['then']}", f"generic_{i}n", rid, False, why)
        if not cases:
            for r in a.rules:
                add("positive", r["text"], ["Exercise the rule"], "Rule holds", "generic_rule", [r["id"]], False, why)
        gaps.append(Gap(req.id, "No acceptance criteria / thresholds detected; add concrete values."))
    return cases, gaps
