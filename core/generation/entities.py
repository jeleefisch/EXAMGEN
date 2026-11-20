"""Plain data containers for the generation engine (no Django)."""
from dataclasses import dataclass, field

MC, TF = "MC", "TF"
CHOICE_COUNT = {MC: 4, TF: 2}


@dataclass(frozen=True)
class Question:
    """A bank question as the engine sees it. Text lives in the database;
    the engine only needs identity, classification and the answer position."""
    id: int
    topic: str
    difficulty: str
    qtype: str            # "MC" or "TF"
    n_choices: int
    correct_index: int    # position of the correct choice in the ORIGINAL order

    def __post_init__(self):
        if self.qtype not in CHOICE_COUNT:
            raise ValueError(f"question {self.id}: unknown type {self.qtype!r}")
        if self.n_choices != CHOICE_COUNT[self.qtype]:
            raise ValueError(f"question {self.id}: {self.qtype} needs "
                             f"{CHOICE_COUNT[self.qtype]} choices")
        if not 0 <= self.correct_index < self.n_choices:
            raise ValueError(f"question {self.id}: correct_index out of range")


@dataclass(frozen=True)
class GeneratedItem:
    position: int          # 1-based number on the paper
    question_id: int
    topic: str
    difficulty: str
    choice_order: tuple    # original choice indexes, in displayed order
    correct_label: str     # letter of the correct answer on THIS paper


@dataclass
class GeneratedVersion:
    code: str
    seed: str
    attempts: int
    items: list

    @property
    def question_ids(self):
        return frozenset(i.question_id for i in self.items)


@dataclass
class GenerationReport:
    requested: int
    feasible: bool = True
    problems: list = field(default_factory=list)
    versions: list = field(default_factory=list)
    overlaps: list = field(default_factory=list)      # OverlapResult per pair
    summary: dict = None                              # mean / max Jaccard
    warnings: list = field(default_factory=list)
    selection_estimate: int = 0   # possible selections for the first allocation
    duration_ms: float = 0.0

    @property
    def success_count(self):
        return len(self.versions)