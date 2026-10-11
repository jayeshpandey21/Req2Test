from req2test.analyzer import analyze
from req2test.models import Requirement
from req2test.pipeline import run_pipeline
from req2test.runner import parse_junit

REQ = ("Users should be able to log in using their email and password. "
       "If the password is incorrect five times, the account should be temporarily locked.")


def test_analyzer_extracts_threshold_and_condition():
    a = analyze(Requirement("REQ-1", REQ))
    assert a.parameters["max_failed_attempts"] == 5
    assert a.parameters["feature"] == "login"
    assert len(a.conditions) == 1 and "five times" in a.conditions[0]["when"]


def test_good_target_passes_and_unexecuted_is_explicit():
    rep, _ = run_pipeline(REQ)
    assert rep["stages"]["executed"] and rep["summary"]["failed"] == 0
    assert rep["summary"]["unexecuted"] >= 1  # lockout-expiry has no spec


def test_buggy_target_is_caught():
    rep, _ = run_pipeline(REQ, target="req2test.demo_target.buggy_service")
    assert rep["summary"]["failed"] >= 1


def test_no_run_marks_everything_unexecuted():
    rep, _ = run_pipeline(REQ, execute=False)
    assert not rep["stages"]["executed"] and rep["summary"]["passed"] == 0


def test_approval_limits_generation_without_hiding_ambiguity():
    rep, source = run_pipeline(REQ, execute=False, approved_case_ids={"TC-001"})
    cases = {case["id"]: case for case in rep["cases"]}
    assert "test_tc_001" in source
    assert "test_tc_002" not in source
    assert cases["TC-001"]["generated"] is True
    assert cases["TC-002"]["detail"] == "Not approved for generation or execution"
    assert cases["TC-014"]["detail"] == "Lock duration is not specified in the requirement"


def test_generic_requirement_is_planned_but_not_executable():
    rep, _ = run_pipeline("When an order exceeds 100 dollars, shipping should be free.", execute=False)
    assert rep["total"] >= 2 and not rep["stages"]["generated"]


def test_parse_junit(tmp_path):
    f = tmp_path / "j.xml"
    f.write_text('<testsuites><testsuite><testcase name="a"/><testcase name="b"><failure message="x">boom</failure></testcase>'
                 '<testcase name="c"><skipped/></testcase></testsuite></testsuites>')
    r = parse_junit(f)
    assert [r[k]["status"] for k in "abc"] == ["passed", "failed", "skipped"]
