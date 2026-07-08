# 007. V2 Roadmap & Intelligence Philosophy

**Date:** 2026-07-08
**Status:** Accepted

## Context
TREDO V1 successfully established a robust, event-driven "Trading Operating System" with core infrastructure: Event Bus, Memory, Risk Engine, and Paper Execution. 

The immediate temptation for V2 is to build multiple autonomous AI agents (e.g., CEO Agent, Macro Agent, Physics Agent). However, allowing LLMs to make trading decisions without a foundation of high-quality market data, technical features, and backtested strategies inevitably leads to hallucinations and "LLM-generated opinions" rather than evidence-based decisions.

## Decision
We will not build Artificial General Intelligence (AGI) in V2. The explicit goal of V2 is **Better trading decisions based on evidence.**

The V2 roadmap will prioritize quantitative engineering over raw AI reasoning. We will build the foundation in this strict order:

1. **Market Scanner**: Live data ingestion (OHLCV, Order Book, Trades, Funding Rate, Open Interest).
2. **Feature Engine**: Converting raw data into technical features (RSI, ATR, EMA, VWAP, Volume Delta, etc.) to give AI clean, mathematical inputs.
3. **Strategy Engine**: Rule-based trading strategies (Trend, Mean Reversion, Momentum) that emit `SignalGenerated` events without executing trades.
4. **Universal Backtester**: Rigorous testing of strategies against historical data to generate metrics (Profit Factor, Sharpe, Max DD).
5. **Performance Analytics**: Real-time evaluation of live strategy performance.

**Only after these components are stable will we introduce AI Reasoning.** The LLM's role will be to evaluate the Market Features, Strategy Signals, and Risk Status to explain the context, generate confidence scores, and propose alternative scenarios. *The LLM will not place orders directly.*

Complex, multi-agent frameworks (HyperThinking, World Models, Agent Debate) are deferred to V3/V4.

## Consequences
- **Positive:** Ensures the AI operates on a solid mathematical foundation, eliminating hallucinations in trading execution.
- **Positive:** Keeps the project focused on building a reliable trading platform rather than an experimental AI playground.
- **Negative:** Delays the "flashy" multi-agent AI features, requiring more traditional quantitative development first.
