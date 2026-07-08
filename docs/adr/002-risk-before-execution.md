# ADR 002: Risk Engine Before Execution

## Problem
AI agents can hallucinate or make irrational trading decisions based on incorrect interpretations of data. If an agent has direct access to the Exchange module, a single hallucination could drain the portfolio.

## Decision
We built an immutable, synchronous Risk Engine that sits directly between Signal Generation (Agents) and Execution (Exchange). All trade signals MUST be approved by the Risk Engine before they are executed.

## Alternatives Considered
- **Agent Self-Regulation:** Relying on the LLM to understand risk limits. (Rejected: LLMs are non-deterministic and cannot be trusted with capital preservation).
- **Post-Trade Analysis:** Analyzing risk after trades are placed to stop future trades. (Rejected: Too late, capital is already exposed).

## Why this approach
- **Safety First:** Acts as a hard "seat belt" for the entire system.
- **Deterministic:** Risk rules (max exposure, daily drawdown, rate limits) are mathematical and immutable, overriding any AI logic.
- **Clear Separation:** AI agents focus on "what to buy", Risk Engine focuses on "how much is safe to buy".

## Consequences
- **Pros:** Guarantees capital preservation regardless of agent behavior; provides peace of mind when transitioning to live trading.
- **Cons:** Agents may experience frustration if their high-conviction trades are repeatedly rejected by the Risk Engine; requires passing rejection reasons back to agents so they can learn.
