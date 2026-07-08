# TREDO — Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]
### Added
- V2.4 Replay Engine (Historical Time Machine)
  - `ReplayClock` with speed control.
  - `ReplayController` API.
  - `BaseReplaySource` for CSV data.

## [v2.3.3] - 2026-07-08
### Added
- **Strategy Manager**: Parallel execution of strategies, crash isolation, hot-reloading (enable/disable), metrics tracking in memory.
- **Consensus Engine**: `MajorityVoteConsensus` and `WeightedVoteConsensus` to aggregate multiple signals into a single `SignalGenerated` event.

## [v2.3.2] - 2026-07-08
### Added
- **Rule-Based Strategies**: EMA Cross, RSI Reversion, Bollinger Reversion.
- **Strategy Registry**: Extensible plugin system for strategies.

## [v2.3.1] - 2026-07-08
### Added
- **Strategy Interface**: `BaseStrategy` and `Signal` contract. Support for `market_type`.

## [v2.2.0] - 2026-07-08
### Added
- **Feature Engine**: Trend, Momentum, Volatility, Volume indicators mathematically optimized O(1).
- **Feature Store**: Centralized in-memory snapshot for strategies.

## [v2.1.0] - 2026-07-08
### Added
- **Market Scanner**: Live WebSocket connections to Binance and Bybit.
- **Normalizer**: Emits standard `CandleEvent`.

## [v1.0.0] - 2026-06
### Added
- Foundation: Event Bus, Risk Engine, API layout, Memory schema.
