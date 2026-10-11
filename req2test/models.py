from dataclasses import dataclass


@dataclass
class Requirement:
    id: str
    text: str


@dataclass
class Analysis:
    requirement_id: str
    actors: list
    rules: list            # [{"id", "text"}]
    conditions: list       # [{"when", "then"}]
    acceptance_criteria: list
    parameters: dict       # e.g. {"feature": "login", "max_failed_attempts": 5}


@dataclass
class TestCase:
    __test__ = False       # keep pytest from collecting this dataclass
    id: str
    requirement_id: str
    rule_ids: list
    title: str
    category: str          # positive | negative | boundary | security | edge
    steps: list
    expected: str
    template: str          # key used by the generator
    executable: bool = True
    reason: str = ""       # why it is not executable
    code: str = ""         # filled by the generator


@dataclass
class Gap:
    requirement_id: str
    question: str
