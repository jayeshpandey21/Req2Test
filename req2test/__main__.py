import argparse
import sys
from pathlib import Path
from .pipeline import run_pipeline
from .report import to_markdown


def main():
    p = argparse.ArgumentParser(prog="req2test", description="Requirement -> tests -> run -> report")
    p.add_argument("text", nargs="?", help="Requirement text (or use --file)")
    p.add_argument("--file", help="Path to a requirement .txt/.md file")
    p.add_argument("--no-run", action="store_true", help="Generate only; do not execute")
    p.add_argument("--target", default="req2test.demo_target.auth_service")
    p.add_argument("--out", default="out")
    p.add_argument("--web", action="store_true", help="Start the browser-based dashboard")
    p.add_argument("--host", default="127.0.0.1", help="Web dashboard host (default: localhost)")
    p.add_argument("--port", type=int, default=8000, help="Web dashboard port")
    a = p.parse_args()
    if a.web:
        from .web import serve
        serve(a.host, a.port)
        return 0
    text = Path(a.file).read_text() if a.file else a.text
    if not text:
        p.error("provide requirement text or --file")
    rep, _ = run_pipeline(text, execute=not a.no_run, target=a.target, out_dir=a.out)
    print(to_markdown(rep))
    print(f"Artifacts written to ./{a.out}/")
    return 1 if rep["summary"]["failed"] else 0


sys.exit(main())
