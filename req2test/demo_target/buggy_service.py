"""Same service with an off-by-one bug (locks after N+1 failures) to demo failures."""
from .auth_service import AuthService, VALID_USER  # noqa: F401


def make_service(max_attempts=5):
    return AuthService((max_attempts or 5) + 1)
