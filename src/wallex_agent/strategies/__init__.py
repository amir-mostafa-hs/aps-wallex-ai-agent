"""Wallex Opportunity Agent Strategies."""
from wallex_agent.strategies.trend_filtered_pullback import evaluate_pullback_setup
from wallex_agent.strategies.momentum import evaluate_momentum_setup
from wallex_agent.strategies.trend_following import evaluate_trend_following_setup
from wallex_agent.strategies.dispatcher import dispatch_strategy_setup

__all__ = [
    "evaluate_pullback_setup",
    "evaluate_momentum_setup",
    "evaluate_trend_following_setup",
    "dispatch_strategy_setup",
]
