"""Step 6 - Results: stage status, per-case outcome, traceability."""
from collections import Counter


def build_report(req, analysis, cases, gaps, source, run):
    ran = bool(run and run.get("ran"))
    results = run["results"] if ran else {}
    rows = []
    for c in cases:
        name = f"test_{c.id.lower().replace('-', '_')}"
        if not c.executable:
            status, detail = "unexecuted", c.reason
        elif not ran:
            status = "unexecuted"
            detail = "Generated but not run" + (f" ({run['error']})" if run else "")
        elif name in results:
            status, detail = results[name]["status"], results[name]["message"]
        else:
            status, detail = "unexecuted", "Not found in run output"
        rows.append({"id": c.id, "title": c.title, "category": c.category, "requirement": c.requirement_id,
                     "rules": c.rule_ids, "status": status, "detail": detail, "generated": c.executable})
    summary = Counter(r["status"] for r in rows)
    stages = {"ingested": True, "analyzed": True, "planned": True,
              "generated": any(c.executable for c in cases), "executed": ran}
    trace = {}
    for r in rows:
        for rid in r["rules"]:
            trace.setdefault(rid, Counter())[r["status"]] += 1
    return {"requirement": {"id": req.id, "text": req.text},
            "analysis": {"actors": analysis.actors, "parameters": analysis.parameters,
                         "rules": analysis.rules, "conditions": analysis.conditions},
            "stages": stages,
            "summary": {k: summary.get(k, 0) for k in ("passed", "failed", "skipped", "unexecuted")},
            "total": len(rows), "cases": rows,
            "traceability": {k: dict(v) for k, v in trace.items()},
            "missing_requirements": [g.question for g in gaps]}


def to_markdown(rep):
    s, st = rep["summary"], rep["stages"]
    L = [f"# Test report - {rep['requirement']['id']}", "", f"> {rep['requirement']['text']}", "",
         "## Pipeline stages"]
    L += [f"- {k}: **{'done' if v else 'NOT done'}**" for k, v in st.items()]
    L += ["", "## Summary",
          f"{rep['total']} cases - passed {s['passed']}, failed {s['failed']}, "
          f"skipped {s['skipped']}, unexecuted {s['unexecuted']}", "",
          "## Cases", "| ID | Category | Title | Status | Traces |", "|---|---|---|---|---|"]
    for r in rep["cases"]:
        L.append(f"| {r['id']} | {r['category']} | {r['title']} | {r['status']} | {', '.join(r['rules'])} |")
    bad = [r for r in rep["cases"] if r["status"] == "failed"]
    if bad:
        L += ["", "## Failure evidence"] + [f"### {r['id']} {r['title']}\n```\n{r['detail']}\n```" for r in bad]
    un = [r for r in rep["cases"] if r["status"] == "unexecuted" and not r["generated"]]
    if un:
        L += ["", "## Unexecuted (no test generated)"] + [f"- {r['id']} {r['title']} - {r['detail']}" for r in un]
    L += ["", "## Requirement traceability", "| Rule | Cases by status |", "|---|---|"]
    L += [f"| {k} | {v} |" for k, v in rep["traceability"].items()]
    L += ["", "## Missing requirements to clarify"] + [f"- {q}" for q in rep["missing_requirements"]]
    return "\n".join(L) + "\n"
