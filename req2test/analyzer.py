"""Step 2 - Requirement analyzer.

Rule-based extraction so the pipeline runs offline and deterministically.
`analyze` is the single extension point: swap in an LLM-backed analyzer
that returns the same `Analysis` object.
"""
import re
from .models import Analysis, Requirement

NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
       "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
THRESHOLD = re.compile(
    r"\b(\d+|" + "|".join(NUM) + r")\s+(?:consecutive\s+|failed\s+|incorrect\s+)*(?:times|attempts|tries)\b")
ACTOR = re.compile(r"\b(users?|admins?|administrators?|customers?|guests?|managers?)\b", re.I)


def split_sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def analyze(req: Requirement) -> Analysis:
    sents = split_sentences(req.text)
    rules = [{"id": f"{req.id}-R{i}", "text": s} for i, s in enumerate(sents, 1)]

    conditions = []
    for s in sents:
        m = re.match(r"(?i)^(?:if|when|whenever|after)\s+(.*?),\s*(.*)$", s)
        if m:
            conditions.append({"when": m.group(1), "then": m.group(2).rstrip(".")})

    actors = sorted({a.lower().rstrip("s") for a in ACTOR.findall(req.text)})
    acceptance = [s for s in sents if re.search(r"\b(should|must|shall|will)\b", s, re.I)]

    low = req.text.lower()
    params = {}
    if re.search(r"\b(log ?in|sign ?in)\b", low) and "password" in low:
        params["feature"] = "login"
    m = THRESHOLD.search(low)
    if m:
        tok = m.group(1)
        params["max_failed_attempts"] = int(tok) if tok.isdigit() else NUM[tok]
    params["lockout"] = "lock" in low
    params["lockout_duration_specified"] = bool(
        re.search(r"\b\d+\s*(seconds?|minutes?|hours?)\b", low))
    return Analysis(req.id, actors, rules, conditions, acceptance, params)
