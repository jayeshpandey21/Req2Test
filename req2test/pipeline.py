import json
from pathlib import Path
from .analyzer import analyze
from .generator import generate
from .planner import plan
from .models import Requirement
from .report import build_report, to_markdown
from .runner import run_tests

ROOT = Path(__file__).resolve().parent.parent


def plan_requirement(text, req_id="REQ-1"):
    req = Requirement(req_id, text.strip())
    analysis = analyze(req)
    cases, gaps = plan(req, analysis)
    return req, analysis, cases, gaps


def run_pipeline(text, req_id="REQ-1", execute=True,
                 target="req2test.demo_target.auth_service", out_dir=None, timeout=60,
                 approved_case_ids=None):
    req, analysis, cases, gaps = plan_requirement(text, req_id)
    if approved_case_ids is not None:
        for case in cases:
            if case.executable and case.id not in approved_case_ids:
                case.executable = False
                case.reason = "Not approved for generation or execution"
    source = generate(cases, analysis)
    run = run_tests(source, target, ROOT, timeout) if execute else None
    rep = build_report(req, analysis, cases, gaps, source, run)
    if out_dir:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "test_generated.py").write_text(source)
        (out / "report.json").write_text(json.dumps(rep, indent=2))
        (out / "report.md").write_text(to_markdown(rep))
    return rep, source
