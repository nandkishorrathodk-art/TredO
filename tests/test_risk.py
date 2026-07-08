"""
TREDO — Risk Engine Tests
Tests every L0 meta-rule validation path.
Covers: trade validation, position sizing, drawdown limits,
cool-down, kill switch, rate limiting, daily trade limits.
"""

import time
import pytest
from pathlib import Path

from backend.risk.engine import RiskEngine, TradeRequest, RiskVerdict


RULES_PATH = Path(__file__).parent.parent / "backend" / "risk" / "meta_rules.yaml"


@pytest.fixture
def engine() -> RiskEngine:
    """Create a loaded risk engine."""
    e = RiskEngine(rules_path=RULES_PATH)
    e.load_rules()
    return e


@pytest.fixture
def valid_trade() -> TradeRequest:
    """A small, valid trade request."""
    return TradeRequest(
        symbol="BTC/USDT",
        side="buy",
        amount=0.001,
        price=71000.0,
        order_type="market",
        reason="Test signal: RSI oversold",
    )


# ── Loading Tests ────────────────────────────────────────


class TestLoading:
    def test_load_rules_success(self, engine: RiskEngine):
        assert engine.loaded is True
        assert "capital" in engine.rules
        assert "drawdown" in engine.rules
        assert "trading" in engine.rules
        assert "governance" in engine.rules

    def test_load_rules_file_not_found(self):
        e = RiskEngine(rules_path=Path("/nonexistent/rules.yaml"))
        with pytest.raises(FileNotFoundError):
            e.load_rules()

    def test_validate_before_load_fails(self):
        e = RiskEngine()
        trade = TradeRequest("BTC/USDT", "buy", 0.01, 71000, "market", "test")
        with pytest.raises(RuntimeError, match="not loaded"):
            e.validate(trade, 10000.0)

    def test_rules_values(self, engine: RiskEngine):
        cap = engine.rules["capital"]
        assert cap["max_single_trade_risk_pct"] == 1.5
        assert cap["max_leverage"] == 3.0
        assert cap["max_portfolio_exposure_pct"] == 50.0


# ── Basic Validation Tests ───────────────────────────────


class TestBasicValidation:
    def test_valid_trade_approved(self, engine: RiskEngine, valid_trade: TradeRequest):
        verdict = engine.validate(valid_trade, portfolio_value=10000.0)
        assert verdict.approved is True
        assert verdict.position_size == 0.001
        assert len(verdict.rejection_reasons) == 0

    def test_invalid_side_rejected(self, engine: RiskEngine):
        trade = TradeRequest("BTC/USDT", "short", 0.001, 71000, "market", "test")
        verdict = engine.validate(trade, 10000.0)
        assert verdict.rejected
        assert any("Invalid side" in r for r in verdict.rejection_reasons)

    def test_zero_amount_rejected(self, engine: RiskEngine):
        trade = TradeRequest("BTC/USDT", "buy", 0.0, 71000, "market", "test")
        verdict = engine.validate(trade, 10000.0)
        assert verdict.rejected
        assert any("Invalid amount" in r for r in verdict.rejection_reasons)

    def test_negative_price_rejected(self, engine: RiskEngine):
        trade = TradeRequest("BTC/USDT", "buy", 0.001, -100, "market", "test")
        verdict = engine.validate(trade, 10000.0)
        assert verdict.rejected


# ── L0 Capital Rules ────────────────────────────────────


class TestCapitalRules:
    def test_exceeds_single_trade_risk(self, engine: RiskEngine):
        """Trade value > 1.5% of portfolio should be rejected."""
        trade = TradeRequest("BTC/USDT", "buy", 0.01, 71000, "market", "test")
        # 0.01 * 71000 = $710 = 7.1% of $10,000 → rejected
        verdict = engine.validate(trade, portfolio_value=10000.0)
        assert verdict.rejected
        assert any("Trade risk" in r for r in verdict.rejection_reasons)

    def test_within_single_trade_risk(self, engine: RiskEngine):
        """Trade value < 1.5% of portfolio should pass."""
        trade = TradeRequest("BTC/USDT", "buy", 0.001, 71000, "market", "test")
        # 0.001 * 71000 = $71 = 0.71% of $10,000 → approved
        verdict = engine.validate(trade, portfolio_value=10000.0)
        assert verdict.approved

    def test_exceeds_position_size_limit(self, engine: RiskEngine):
        """Position > 10% of portfolio should be rejected."""
        trade = TradeRequest("BTC/USDT", "buy", 0.001, 71000, "market", "test")
        # Existing position $900 + new $71 = $971 = 9.71% → OK
        # But if existing is $950 + $71 = $1021 = 10.2% → rejected
        positions = {"BTC/USDT": {"value": 960.0}}
        verdict = engine.validate(trade, 10000.0, positions)
        assert verdict.rejected
        assert any("Position" in r for r in verdict.rejection_reasons)

    def test_exceeds_portfolio_exposure(self, engine: RiskEngine):
        """Total exposure > 50% should be rejected."""
        trade = TradeRequest("BTC/USDT", "buy", 0.001, 71000, "market", "test")
        positions = {
            "ETH/USDT": {"value": 2500.0},
            "SOL/USDT": {"value": 2500.0},
        }
        # Existing $5000 + new $71 = $5071 = 50.7% → rejected
        verdict = engine.validate(trade, 10000.0, positions)
        assert verdict.rejected
        assert any("exposure" in r for r in verdict.rejection_reasons)

    def test_sell_doesnt_add_exposure(self, engine: RiskEngine):
        """Selling should not increase exposure count."""
        trade = TradeRequest("BTC/USDT", "sell", 0.001, 71000, "market", "close position")
        positions = {
            "BTC/USDT": {"value": 500.0},
            "ETH/USDT": {"value": 2500.0},
            "SOL/USDT": {"value": 2000.0},
        }
        # Sell doesn't add — total stays at $5000 = 50% → edge case
        verdict = engine.validate(trade, 10000.0, positions)
        assert verdict.approved

    def test_leverage_exceeded(self, engine: RiskEngine):
        """Leverage > 3x should be rejected."""
        trade = TradeRequest(
            "BTC/USDT", "buy", 0.001, 71000, "market", "test", leverage=5.0
        )
        verdict = engine.validate(trade, 10000.0)
        assert verdict.rejected
        assert any("Leverage" in r for r in verdict.rejection_reasons)


# ── L0 Governance ────────────────────────────────────────


class TestGovernance:
    def test_missing_reason_rejected(self, engine: RiskEngine):
        """Every trade must have a reason."""
        trade = TradeRequest("BTC/USDT", "buy", 0.001, 71000, "market", reason="")
        verdict = engine.validate(trade, 10000.0)
        assert verdict.rejected
        assert any("reason" in r.lower() for r in verdict.rejection_reasons)

    def test_with_reason_approved(self, engine: RiskEngine, valid_trade: TradeRequest):
        verdict = engine.validate(valid_trade, 10000.0)
        assert verdict.approved


# ── Drawdown & Cool-down ────────────────────────────────


class TestDrawdown:
    def test_daily_drawdown_blocks_trading(self, engine: RiskEngine, valid_trade: TradeRequest):
        """After 4% daily loss, trading is paused."""
        engine._daily_pnl = -450.0  # 4.5% of $10,000
        verdict = engine.validate(valid_trade, 10000.0)
        assert verdict.rejected
        assert any("Daily drawdown" in r for r in verdict.rejection_reasons)

    def test_weekly_drawdown_blocks_trading(self, engine: RiskEngine, valid_trade: TradeRequest):
        """After 8% weekly loss, trading is paused."""
        engine._weekly_pnl = -850.0  # 8.5% of $10,000
        verdict = engine.validate(valid_trade, 10000.0)
        assert verdict.rejected
        assert any("Weekly drawdown" in r for r in verdict.rejection_reasons)

    def test_cool_down_after_loss(self, engine: RiskEngine, valid_trade: TradeRequest):
        """30-min cool-down after significant loss."""
        engine._last_loss_time = time.time() - 60  # 1 min ago
        verdict = engine.validate(valid_trade, 10000.0)
        assert verdict.rejected
        assert any("Cool-down" in r for r in verdict.rejection_reasons)

    def test_cool_down_expired(self, engine: RiskEngine, valid_trade: TradeRequest):
        """After 30 minutes, cool-down should expire."""
        engine._last_loss_time = time.time() - (31 * 60)  # 31 min ago
        verdict = engine.validate(valid_trade, 10000.0)
        assert verdict.approved


# ── Rate Limiting ────────────────────────────────────────


class TestRateLimiting:
    def test_daily_trade_limit(self, engine: RiskEngine, valid_trade: TradeRequest):
        """Max 50 trades per day."""
        engine._daily_trade_count = 50
        verdict = engine.validate(valid_trade, 10000.0)
        assert verdict.rejected
        assert any("trade limit" in r.lower() for r in verdict.rejection_reasons)

    def test_order_too_fast(self, engine: RiskEngine, valid_trade: TradeRequest):
        """Orders must be at least 5 seconds apart."""
        engine._last_order_time = time.time() - 1  # 1 second ago
        verdict = engine.validate(valid_trade, 10000.0)
        assert verdict.rejected
        assert any("too fast" in r.lower() for r in verdict.rejection_reasons)

    def test_order_after_interval(self, engine: RiskEngine, valid_trade: TradeRequest):
        """Orders with enough interval should pass."""
        engine._last_order_time = time.time() - 10  # 10 seconds ago
        verdict = engine.validate(valid_trade, 10000.0)
        assert verdict.approved


# ── Kill Switch ──────────────────────────────────────────


class TestKillSwitch:
    def test_kill_switch_blocks_everything(self, engine: RiskEngine, valid_trade: TradeRequest):
        engine.activate_kill_switch("Test emergency")
        verdict = engine.validate(valid_trade, 10000.0)
        assert verdict.rejected
        assert any("KILL SWITCH" in r for r in verdict.rejection_reasons)

    def test_kill_switch_deactivate(self, engine: RiskEngine, valid_trade: TradeRequest):
        engine.activate_kill_switch("Test")
        engine.deactivate_kill_switch()
        verdict = engine.validate(valid_trade, 10000.0)
        assert verdict.approved

    def test_kill_switch_status(self, engine: RiskEngine):
        assert engine.kill_switch_active is False
        engine.activate_kill_switch("Test")
        assert engine.kill_switch_active is True


# ── Position Sizing ──────────────────────────────────────


class TestPositionSizing:
    def test_calculate_safe_size(self, engine: RiskEngine):
        """With $10k portfolio, 1.5% risk, 2% stop-loss, BTC at $71k."""
        size = engine.calculate_safe_size(
            symbol="BTC/USDT",
            price=71000.0,
            portfolio_value=10000.0,
            stop_loss_pct=2.0,
        )
        # risk_budget = 10000 * 0.015 = $150
        # price_risk = 71000 * 0.02 = $1420
        # size = 150 / 1420 = ~0.1056
        assert 0.10 < size < 0.11

    def test_zero_stop_loss_returns_zero(self, engine: RiskEngine):
        size = engine.calculate_safe_size("BTC/USDT", 71000, 10000, 0.0)
        assert size == 0.0


# ── State Tracking ───────────────────────────────────────


class TestStateTracking:
    def test_record_trade_updates_counters(self, engine: RiskEngine):
        engine.record_trade_result(50.0)
        assert engine._daily_pnl == 50.0
        assert engine._weekly_pnl == 50.0
        assert engine._daily_trade_count == 1

    def test_record_loss_triggers_cool_down(self, engine: RiskEngine):
        engine.record_trade_result(-3.0)  # > 2% significant loss
        assert engine._last_loss_time > 0

    def test_reset_daily(self, engine: RiskEngine):
        engine.record_trade_result(-100.0)
        engine.reset_daily()
        assert engine._daily_pnl == 0.0
        assert engine._daily_trade_count == 0

    def test_reset_weekly(self, engine: RiskEngine):
        engine.record_trade_result(-100.0)
        engine.reset_weekly()
        assert engine._weekly_pnl == 0.0

    def test_get_status(self, engine: RiskEngine):
        status = engine.get_status()
        assert status["loaded"] is True
        assert status["kill_switch"] is False
        assert "daily_pnl" in status
        assert "daily_trades" in status
