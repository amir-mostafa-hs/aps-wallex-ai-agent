import pytest
from wallex_agent.domain.types import Candidate, PositionRecord
from wallex_agent.scanner import (
    CandidateScanner,
    ReviewPriorityQueue,
    ReviewItem,
    AICallBudget,
)


def test_candidate_scoring_and_filtering():
    scanner = CandidateScanner(max_spread_bps=100.0, min_volume_threshold=500.0)

    # 1. Stale candidate is excluded
    stale_cand = scanner.evaluate_candidate(
        symbol="BTCTMN",
        features={"return_pct": 2.5, "relative_volume": 2.0, "volatility": 1.5, "latest_volume": 1000.0},
        spread_bps=20.0,
        is_stale=True,
    )
    assert stale_cand["is_eligible"] is False
    assert stale_cand["exclusion_reason"] == "STALE_DATA"

    # 2. Wide spread candidate is excluded
    wide_spread_cand = scanner.evaluate_candidate(
        symbol="ETHTMN",
        features={"return_pct": 3.0, "relative_volume": 2.5, "volatility": 1.0, "latest_volume": 1000.0},
        spread_bps=150.0,  # exceeds 100 bps
        is_stale=False,
    )
    assert wide_spread_cand["is_eligible"] is False
    assert wide_spread_cand["exclusion_reason"] == "WIDE_SPREAD"

    # 3. Eligible candidate gets positive score
    good_cand = scanner.evaluate_candidate(
        symbol="SOLTMN",
        features={"return_pct": 2.0, "relative_volume": 3.0, "volatility": 1.2, "latest_volume": 1500.0},
        spread_bps=25.0,
        is_stale=False,
    )
    assert good_cand["is_eligible"] is True
    assert good_cand["score"] > 0.0


def test_ranking_candidates_returns_top_k():
    scanner = CandidateScanner()
    candidates = [
        {"symbol": "SYM1", "score": 10.5, "features": {}, "estimated_cost_bps": 20.0, "is_eligible": True, "exclusion_reason": None},
        {"symbol": "SYM2", "score": 25.0, "features": {}, "estimated_cost_bps": 15.0, "is_eligible": True, "exclusion_reason": None},
        {"symbol": "SYM3", "score": 5.0, "features": {}, "estimated_cost_bps": 10.0, "is_eligible": True, "exclusion_reason": None},
        {"symbol": "SYM4", "score": 30.0, "features": {}, "estimated_cost_bps": 50.0, "is_eligible": False, "exclusion_reason": "WIDE_SPREAD"},
    ]
    top = scanner.rank_candidates(candidates, top_k=2)
    assert len(top) == 2
    assert top[0]["symbol"] == "SYM2"  # score 25.0
    assert top[1]["symbol"] == "SYM1"  # score 10.5


def test_review_priority_queue_prioritizes_open_positions():
    queue = ReviewPriorityQueue()

    # Add a new candidate entry
    queue.push(ReviewItem(item_type="CANDIDATE", symbol="BTCTMN", priority=10.0, context={}))

    # Add an open position close to stop loss (should get much higher priority)
    queue.push(ReviewItem(item_type="POSITION", symbol="ETHTMN", priority=100.0, context={"reason": "NEAR_STOP"}))

    first = queue.pop()
    assert first is not None
    assert first.item_type == "POSITION"
    assert first.symbol == "ETHTMN"

    second = queue.pop()
    assert second is not None
    assert second.item_type == "CANDIDATE"
    assert second.symbol == "BTCTMN"


def test_ai_call_budget_enforces_rate_limits():
    # Min interval 30 seconds, max 3 calls per 60 seconds
    budget = AICallBudget(min_interval_seconds=30.0, max_calls_per_minute=3)

    t0 = 1000.0
    assert budget.can_call(current_time=t0) is True
    budget.record_call(current_time=t0)

    # 10 seconds later: cannot call (violates 30s min interval)
    assert budget.can_call(current_time=t0 + 10.0) is False

    # 31 seconds later: can call second time
    assert budget.can_call(current_time=t0 + 31.0) is True
    budget.record_call(current_time=t0 + 31.0)

    # 62 seconds later: can call third time
    assert budget.can_call(current_time=t0 + 62.0) is True
    budget.record_call(current_time=t0 + 62.0)

    # 70 seconds later: cannot call because in [10.0..70.0] already 3 calls were made
    assert budget.can_call(current_time=t0 + 70.0) is False
