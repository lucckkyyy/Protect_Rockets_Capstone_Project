"""Game rules for Aware Rockets: loading questions, scoring, progress, results.

Nothing in this file knows about Streamlit, so it is easy to test.

Scoring
  * Correct classification ........ +100 points  (max 500 per game)
  * Spotter bonus (optional) ...... up to +20 per round, only on correctly classified emails,
                                    for ticking the right warning signs
"""

from __future__ import annotations

import csv
import io
import json
import random
from dataclasses import dataclass, field
from pathlib import Path

CHOICES = ("Low Risk", "Suspicious", "High Risk")
LEVELS = ("easy", "medium", "hard")
ROUND_PLAN = ("easy", "easy", "medium", "medium", "hard")   # 5 rounds, rising difficulty
POINTS_PER_CORRECT = 100
BONUS_MAX_PER_ROUND = 20

# Warning signs the player can tick. Each question lists which of these really apply.
FLAG_OPTIONS = {
    "sender": "Suspicious sender address or domain",
    "replyto": "Reply-To goes somewhere else",
    "urgency": "Urgency, pressure or threats",
    "sensitive": "Asks for passwords, ID or bank details",
    "money": "Asks for money, fees or gift cards",
    "link": "Misleading or suspicious link",
    "offer": "Too-good-to-be-true offer",
    "generic": "Generic greeting",
    "auth": "Failed email authentication (SPF/DKIM/DMARC)",
}

REQUIRED_FIELDS = ("id", "level", "answer", "sender_name", "sender_email", "subject", "body",
                   "links", "red_flags", "explanation", "focus", "auth", "flag_tags")

QUESTIONS_PATH = Path(__file__).with_name("questions.json")

TIPS = {
    "sender": "Practice checking the sender's real address: look-alike domains, free mail accounts, "
              "and display names that only sound official.",
    "language": "Practice spotting pressure tactics: urgent deadlines, threats, prizes, and requests "
                "for money, gift cards or personal details.",
    "links": "Practice inspecting links before clicking: compare the shown text to the real "
             "destination and look for swapped characters in the domain.",
}
PERFECT_TIP = "Excellent work! Try again for a new set of emails to keep your skills sharp."


# --------------------------------------------------------------------------
# Question bank
# --------------------------------------------------------------------------
def load_questions(path: Path | str = QUESTIONS_PATH) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def validate_question(q: dict) -> list[str]:
    """Return a list of problems (empty list = question is fine)."""
    problems = [f"missing field '{k}'" for k in REQUIRED_FIELDS if k not in q]
    if q.get("answer") not in CHOICES:
        problems.append(f"answer must be one of {CHOICES}")
    if q.get("level") not in LEVELS:
        problems.append(f"level must be one of {LEVELS}")
    if not str(q.get("explanation", "")).strip():
        problems.append("explanation is empty")
    if q.get("answer") != "Low Risk" and not q.get("red_flags"):
        problems.append("risky emails need at least one red flag")
    for link in q.get("links", []):
        if "url" not in link or "text" not in link:
            problems.append("each link needs 'text' and 'url'")
    tags = q.get("flag_tags", [])
    if any(t not in FLAG_OPTIONS for t in tags):
        problems.append(f"flag_tags must come from {sorted(FLAG_OPTIONS)}")
    if q.get("answer") == "Low Risk" and tags:
        problems.append("a Low Risk email should have no flag_tags")
    if q.get("answer") != "Low Risk" and not tags:
        problems.append("risky emails need at least one flag_tag")
    for k in ("spf", "dkim", "dmarc"):
        if q.get("auth", {}).get(k) not in ("pass", "fail", "none"):
            problems.append(f"auth.{k} must be pass, fail or none")
    return problems


def select_rounds(questions: list[dict], seed: int | None = None) -> list[dict]:
    """Pick 5 different questions following ROUND_PLAN (easy, easy, medium, medium, hard)."""
    rng = random.Random(seed)
    pools = {lvl: [q for q in questions if q["level"] == lvl] for lvl in LEVELS}
    for lvl in LEVELS:
        rng.shuffle(pools[lvl])
    picked = []
    for lvl in ROUND_PLAN:
        if not pools[lvl]:
            raise ValueError(f"No '{lvl}' questions available")
        picked.append(pools[lvl].pop())
    return picked


def flag_bonus(selected: list[str] | tuple[str, ...], truth: list[str]) -> int:
    """Bonus points (0..BONUS_MAX_PER_ROUND) for the warning signs the player ticked.

    Risky email: each correct tick counts, each wrong tick cancels one.
    Legitimate email (no real warning signs): full bonus for ticking nothing.
    """
    chosen, real = set(selected), set(truth)
    if not real:
        return BONUS_MAX_PER_ROUND if not chosen else 0
    net = len(chosen & real) - len(chosen - real)
    return round(BONUS_MAX_PER_ROUND * max(0, net) / len(real))


# --------------------------------------------------------------------------
# Game state
# --------------------------------------------------------------------------
@dataclass
class RoundResult:
    question_id: str
    level: str
    focus: str
    player: str
    correct_answer: str
    detector: str
    points: int
    flags_selected: tuple[str, ...] = ()
    flags_true: tuple[str, ...] = ()
    bonus: int = 0

    @property
    def correct(self) -> bool:
        return self.player == self.correct_answer

    @property
    def detector_correct(self) -> bool:
        return self.detector == self.correct_answer

    @property
    def flags_hit(self) -> list[str]:
        return [f for f in self.flags_true if f in self.flags_selected]

    @property
    def flags_missed(self) -> list[str]:
        return [f for f in self.flags_true if f not in self.flags_selected]

    @property
    def flags_wrong(self) -> list[str]:
        return [f for f in self.flags_selected if f not in self.flags_true]


@dataclass
class GameState:
    rounds: list[dict]
    index: int = 0
    results: list[RoundResult] = field(default_factory=list)

    # ---- progress ----
    @property
    def total_rounds(self) -> int:
        return len(self.rounds)

    @property
    def max_points(self) -> int:
        return self.total_rounds * POINTS_PER_CORRECT

    @property
    def max_bonus(self) -> int:
        return self.total_rounds * BONUS_MAX_PER_ROUND

    @property
    def current(self) -> dict:
        return self.rounds[self.index]

    @property
    def answered_current(self) -> bool:
        return len(self.results) > self.index

    @property
    def finished(self) -> bool:
        return self.index >= self.total_rounds

    @property
    def score(self) -> int:
        """Classification points only (max 500)."""
        return sum(r.points for r in self.results)

    @property
    def bonus(self) -> int:
        return sum(r.bonus for r in self.results)

    @property
    def total_points(self) -> int:
        return self.score + self.bonus

    @property
    def correct_count(self) -> int:
        return sum(r.correct for r in self.results)

    @property
    def accuracy(self) -> float:
        return self.correct_count / self.total_rounds if self.total_rounds else 0.0

    @property
    def streak(self) -> int:
        """Current run of correct answers within this game."""
        n = 0
        for r in reversed(self.results):
            if not r.correct:
                break
            n += 1
        return n

    # ---- actions ----
    def submit(self, choice: str, detector_verdict: str,
               flags: list[str] | tuple[str, ...] = ()) -> RoundResult | None:
        """Record the player's answer. Returns None if the round was already answered
        (so repeated clicks can never earn extra points)."""
        if self.finished or self.answered_current:
            return None
        if choice not in CHOICES:
            raise ValueError(f"Invalid choice: {choice}")
        q = self.current
        flags = tuple(f for f in dict.fromkeys(flags) if f in FLAG_OPTIONS)
        correct = choice == q["answer"]
        result = RoundResult(
            q["id"], q["level"], q["focus"], choice, q["answer"], detector_verdict,
            POINTS_PER_CORRECT if correct else 0,
            flags_selected=flags, flags_true=tuple(q["flag_tags"]),
            bonus=flag_bonus(flags, q["flag_tags"]) if correct else 0)
        self.results.append(result)
        return result

    def next_round(self) -> None:
        """Move on - only allowed once the current round has been answered."""
        if self.answered_current:
            self.index += 1

    # ---- results ----
    def learning_tip(self) -> str:
        missed = [r.focus for r in self.results if not r.correct]
        if not missed:
            return PERFECT_TIP
        top = max(set(missed), key=missed.count)
        return TIPS.get(top, PERFECT_TIP)

    def to_csv(self) -> str:
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["round", "question_id", "level", "your_answer", "correct_answer",
                    "detector_answer", "you_correct", "detector_correct", "points",
                    "flags_selected", "bonus"])
        for i, r in enumerate(self.results, 1):
            w.writerow([i, r.question_id, r.level, r.player, r.correct_answer,
                        r.detector, r.correct, r.detector_correct, r.points,
                        "|".join(r.flags_selected), r.bonus])
        w.writerow([])
        w.writerow(["total_points", self.score, "max_points", self.max_points,
                    "bonus", self.bonus, "accuracy", f"{self.accuracy:.0%}"])
        return buf.getvalue()


def new_game(questions: list[dict] | None = None, seed: int | None = None) -> GameState:
    return GameState(rounds=select_rounds(questions or load_questions(), seed))
