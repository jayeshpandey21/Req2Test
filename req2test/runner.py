"""Step 5 - Test runner.

Runs generated tests in a separate pytest process: temp working dir, scrubbed
environment, hard timeout. This is process-level isolation, not a security
boundary - for untrusted targets run the same command inside a container.
"""
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


def parse_junit(path):
    out = {}
    for tc in ET.parse(path).getroot().iter("testcase"):
        status, msg = "passed", ""
        for tag in ("failure", "error", "skipped"):
            el = tc.find(tag)
            if el is not None:
                status = "skipped" if tag == "skipped" else "failed"
                msg = ((el.get("message") or "") + "\n" + (el.text or "")).strip()[:800]
                break
        out[tc.get("name")] = {"status": status, "message": msg}
    return out


def run_tests(source, target_module, pythonpath, timeout=60):
    with tempfile.TemporaryDirectory() as d:
        Path(d, "test_generated.py").write_text(source)
        junit = Path(d, "junit.xml")
        env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(pythonpath),
               "REQ2TEST_TARGET": target_module, "PYTHONDONTWRITEBYTECODE": "1"}
        cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
               "--junitxml", str(junit), "test_generated.py"]
        try:
            p = subprocess.run(cmd, cwd=d, env=env, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return {"ran": False, "error": f"timed out after {timeout}s", "results": {}}
        if not junit.exists():
            return {"ran": False, "error": (p.stdout + p.stderr)[-600:], "results": {}}
        return {"ran": True, "exit_code": p.returncode, "results": parse_junit(junit),
                "output_tail": p.stdout[-600:]}
