"""
TREDO — Consensus Engine
Aggregates multiple strategy signals into a single execution decision.
"""

from abc import ABC, abstractmethod
from typing import Sequence

from backend.strategy.models import Signal


class BaseConsensus(ABC):
    """Abstract interface for all consensus engines."""
    
    @abstractmethod
    def compute(self, signals: Sequence[Signal], weights: dict[str, float] | None = None) -> Signal | None:
        """
        Aggregate multiple signals into one.
        """
        pass


class MajorityVoteConsensus(BaseConsensus):
    """
    Simple majority rules. The direction with the most votes wins.
    If tied, returns NONE.
    """
    def compute(self, signals: Sequence[Signal], weights: dict[str, float] | None = None) -> Signal | None:
        if not signals:
            return None

        votes = {"BUY": 0, "SELL": 0, "NONE": 0}
        reasons = []
        
        # We assume all signals are for the same symbol/timeframe/exchange
        # Grab metadata from the first signal
        ref = signals[0]

        for s in signals:
            votes[s.direction] += 1
            if isinstance(s.reason, list):
                reasons.extend(s.reason)
            else:
                reasons.append(f"{s.strategy}: {s.reason}")

        # Find the max vote
        winner = max(votes.items(), key=lambda x: x[1])
        direction = winner[0]
        count = winner[1]

        # Check for ties
        tied = [k for k, v in votes.items() if v == count]
        if len(tied) > 1:
            direction = "NONE"
            confidence = 0.0
        else:
            confidence = count / len(signals)

        return Signal(
            strategy="CONSENSUS",
            symbol=ref.symbol,
            direction=direction,
            confidence=confidence,
            reason=reasons,
            exchange=ref.exchange,
            market_type=ref.market_type,
            timeframe=ref.timeframe,
            timestamp=ref.timestamp
        )


class WeightedVoteConsensus(BaseConsensus):
    """
    Multiplier-based consensus.
    Each vote is scaled by strategy weight and signal confidence.
    """
    def compute(self, signals: Sequence[Signal], weights: dict[str, float] | None = None) -> Signal | None:
        if not signals:
            return None
            
        weights = weights or {}
        
        score_buy = 0.0
        score_sell = 0.0
        total_possible_score = 0.0
        reasons = []

        ref = signals[0]

        for s in signals:
            w = weights.get(s.strategy, 1.0)
            total_possible_score += w
            
            if s.direction == "BUY":
                score_buy += (s.confidence * w)
            elif s.direction == "SELL":
                score_sell += (s.confidence * w)
                
            reasons.append(f"{s.strategy}[w={w}]: {s.direction}({s.confidence:.2f})")

        if total_possible_score == 0:
            return None

        # Determine winner
        if score_buy > score_sell:
            direction = "BUY"
            confidence = score_buy / total_possible_score
        elif score_sell > score_buy:
            direction = "SELL"
            confidence = score_sell / total_possible_score
        else:
            direction = "NONE"
            confidence = 0.0

        return Signal(
            strategy="CONSENSUS",
            symbol=ref.symbol,
            direction=direction,
            confidence=confidence,
            reason=reasons,
            exchange=ref.exchange,
            market_type=ref.market_type,
            timeframe=ref.timeframe,
            timestamp=ref.timestamp
        )
