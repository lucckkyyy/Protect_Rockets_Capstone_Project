"""Lifetime player profile: awareness rank, streaks and totals, saved between games.

Stored in a small JSON file (player_stats.json) next to the app. When the game runs on
one person's computer this is their personal profile. Set the environment variable
PHISHGUARD_STATS_PATH to store it elsewhere.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_PATH = Path(__file__).with_name("player_stats.json")

# (minimum XP, rank title). XP = classification points + spotter bonus from every game.
RANKS = [(0, "Rookie"), (600, "Analyst"), (1800, "Defender"), (3600, "Guardian")]

EMPTY = {
    "games_played": 0, "best_score": 0, "xp": 0,
    "total_correct": 0, "total_answered": 0,
    "current_streak": 0, "best_streak": 0,
}


def stats_path() -> Path:
    return Path(os.environ.get("PHISHGUARD_STATS_PATH") or DEFAULT_PATH)


def load_stats(path: Path | None = None) -> dict:
    path = path or stats_path()
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return {**EMPTY, **{k: int(data.get(k, 0)) for k in EMPTY}}
    except (OSError, ValueError, TypeError):
        return dict(EMPTY)


def save_stats(stats: dict, path: Path | None = None) -> None:
    path = path or stats_path()
    try:
        Path(path).write_text(json.dumps(stats, indent=2), encoding="utf-8")
    except OSError:
        pass   # a read-only folder must never crash the game


def record_game(stats: dict, game) -> dict:
    """Return a NEW stats dict updated with a finished game (does not touch the disk)."""
    s = dict(stats)
    s["games_played"] += 1
    s["best_score"] = max(s["best_score"], game.total_points)
    s["xp"] += game.total_points
    s["total_answered"] += len(game.results)
    s["total_correct"] += game.correct_count
    for r in game.results:
        s["current_streak"] = s["current_streak"] + 1 if r.correct else 0
        s["best_streak"] = max(s["best_streak"], s["current_streak"])
    return s


def rank_for(xp: int) -> str:
    title = RANKS[0][1]
    for need, name in RANKS:
        if xp >= need:
            title = name
    return title


def next_rank(xp: int) -> tuple[str, int] | None:
    """(name, XP still needed) for the next rank, or None at the top."""
    for need, name in RANKS:
        if xp < need:
            return name, need - xp
    return None


def lifetime_accuracy(stats: dict) -> float:
    return stats["total_correct"] / stats["total_answered"] if stats["total_answered"] else 0.0
