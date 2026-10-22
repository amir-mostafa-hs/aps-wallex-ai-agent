"""Candidate screening engine, review priority queue, and AI call rate limiter."""
from __future__ import annotations
import heapq
import itertools
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence, Literal
from wallex_agent.domain.types import Candidate


@dataclass
class ReviewItem:
    item_type: Literal["POSITION", "CANDIDATE"]
    symbol: str
    priority: float
    context: Mapping[str, Any] = field(default_factory=dict)


class ReviewPriorityQueue:
    """Priority queue prioritizing critical position reviews over new candidate evaluations."""

    def __init__(self) -> None:
        self._heap: list[tuple[float, int, ReviewItem]] = []
        self._counter = itertools.count()

    def push(self, item: ReviewItem) -> None:
        # Negative priority so higher numeric priority pops first
        count = next(self._counter)
        heapq.heappush(self._heap, (-item.priority, count, item))

    def pop(self) -> ReviewItem | None:
        if not self._heap:
            return None
        _, _, item = heapq.heappop(self._heap)
        return item

    def __len__(self) -> int:
        return len(self._heap)


class AICallBudget:
    """Enforces rate limits on AI LLM invocations (interval and sliding window budget)."""

    def __init__(self, min_interval_seconds: float = 30.0, max_calls_per_minute: int = 3) -> None:
        self.min_interval_seconds = min_interval_seconds
        self.max_calls_per_minute = max_calls_per_minute
        self._call_history: list[float] = []

    def can_call(self, current_time: float) -> bool:
        # 1. Check minimum interval from last call
        if self._call_history:
            if (current_time - self._call_history[-1]) < self.min_interval_seconds:
                return False

        # 2. Prune calls older than 60 seconds
        window_start = current_time - 60.0
        active_calls = [ts for ts in self._call_history if ts >= window_start]
        if len(active_calls) >= self.max_calls_per_minute:
            return False

        return True

    def record_call(self, current_time: float) -> None:
        self._call_history.append(current_time)
        # Keep list bounded
        window_start = current_time - 60.0
        self._call_history = [ts for ts in self._call_history if ts >= window_start]


class CandidateScanner:
    """Evaluates markets and ranks candidates based on objective quantitative criteria."""

    def __init__(
        self,
        max_spread_bps: float = 150.0,
        min_volume_threshold: float = 100.0,
    ) -> None:
        self.max_spread_bps = max_spread_bps
        self.min_volume_threshold = min_volume_threshold

    def evaluate_candidate(
        self,
        symbol: str,
        features: Mapping[str, float],
        spread_bps: float,
        is_stale: bool,
    ) -> Candidate:
        """Evaluates a single market and produces a Candidate record."""
        latest_vol = features.get("latest_volume", 0.0)

        # Exclusion checks
        if is_stale:
            return {
                "symbol": symbol,
                "score": 0.0,
                "features": dict(features),
                "estimated_cost_bps": spread_bps + 40.0,
                "is_eligible": False,
                "exclusion_reason": "STALE_DATA",
            }

        if spread_bps > self.max_spread_bps:
            return {
                "symbol": symbol,
                "score": 0.0,
                "features": dict(features),
                "estimated_cost_bps": spread_bps + 40.0,
                "is_eligible": False,
                "exclusion_reason": "WIDE_SPREAD",
            }

        if latest_vol < self.min_volume_threshold:
            return {
                "symbol": symbol,
                "score": 0.0,
                "features": dict(features),
                "estimated_cost_bps": spread_bps + 40.0,
                "is_eligible": False,
                "exclusion_reason": "LOW_VOLUME",
            }

        # Calculate composite opportunity score
        ret_pct = features.get("return_pct", 0.0)
        rel_vol = features.get("relative_volume", 1.0)
        volat = features.get("volatility", 1.0)

        # Baseline scoring formula: favors momentum + volume expansion with reasonable volatility
        raw_score = (max(ret_pct, 0.0) * 0.4) + (rel_vol * 3.0) + (volat * 1.5)
        cost_penalty = (spread_bps / 50.0)
        score = max(raw_score - cost_penalty, 0.0)

        return {
            "symbol": symbol,
            "score": float(score),
            "features": dict(features),
            "estimated_cost_bps": float(spread_bps + 40.0),
            "is_eligible": True,
            "exclusion_reason": None,
        }

    def rank_candidates(
        self,
        candidates: Sequence[Candidate],
        top_k: int = 3,
    ) -> list[Candidate]:
        """Filters for eligible candidates and returns the top K sorted descending by score."""
        eligible = [c for c in candidates if c.get("is_eligible") is True]
        eligible.sort(key=lambda c: c["score"], reverse=True)
        return eligible[:top_k]
