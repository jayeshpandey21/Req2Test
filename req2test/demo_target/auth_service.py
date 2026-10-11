"""Demo system-under-test implementing the login/lockout requirement."""
import re

VALID_USER = ("user@example.com", "Secret#123")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
GENERIC = "Invalid email or password."


class AuthService:
    def __init__(self, max_attempts=5):
        self.max_attempts = max_attempts
        self.users = {VALID_USER[0]: VALID_USER[1]}
        self.failures, self.locked = {}, set()

    @staticmethod
    def _r(ok, locked, msg):
        return {"success": ok, "locked": locked, "message": msg}

    def login(self, email, password):
        if not (isinstance(email, str) and isinstance(password, str)
                and password and EMAIL_RE.match(email)):
            return self._r(False, False, GENERIC)
        if email in self.locked:
            return self._r(False, True, "Account temporarily locked.")
        if self.users.get(email) == password:
            self.failures.pop(email, None)
            return self._r(True, False, "Welcome.")
        if email in self.users:
            self.failures[email] = self.failures.get(email, 0) + 1
            if self.failures[email] >= self.max_attempts:
                self.locked.add(email)
                return self._r(False, True, "Account temporarily locked.")
        return self._r(False, False, GENERIC)


def make_service(max_attempts=5):
    return AuthService(max_attempts or 5)
