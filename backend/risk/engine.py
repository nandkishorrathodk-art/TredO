"""
TREDO — Risk Engine
The mandatory gate between every trade signal and execution.
No order reaches the exchange without passing through this engine.

Flow:
    Signal → Risk Validation → Position Size → Daily Loss Check
    → Exposure Check → L0 Rules → Approved? → Execute

Features:
- Loads immutable L0 meta-rules from YAML
- Validates every trade request before execution
- Calculates safe position size based on risk budget
- Tracks daily P&L and enforces drawdown limits
- Enforces cool-down periods after losses
- Rate limits order frequency
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

RULES_PATH = Path(__file__).parent / "meta_rules.yaml"


@dataclass
class TradeRequest:
    """A trade request that must pass risk validation before execution."""
    symbol: str
    side: str          # "buy" or "sell"
    amount: float      # Quantity in base currency
    price: float       # Current/limit price
    order_type: str    # "market" or "limit"
    reason: str = ""   # Why this trade? (required by L0)
    leverage: float = 1.0


@dataclass
class RiskVerdict:
    """Result of risk validation. Only approved=True trades can execute."""
    approved: bool
    trade: TradeRequest
    position_size: float       # Approved size (may be reduced)
    risk_amount: float         # Dollar amount at risk
    risk_pct: float            # Percentage of portfolio at risk
    rejection_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def rejected(self) -> bool:
        return not self.approved


class RiskEngine:
    """
    Immutable risk gate. Every trade must pass through validate()
    before reaching the exchange.

    Usage:
        engine = RiskEngine()
        engine.load_rules()

        verdict = engine.validate(
            trade=TradeRequest(symbol="BTC/USDT", side="buy", amount=0.01, price=71000),
            portfolio_value=10000.0,
            open_positions={"ETH/USDT": {"value": 1500.0}},
        )

        if verdict.approved:
            # safe to execute with verdict.position_size
            pass
        else:
            print(verdict.rejection_reasons)
    """

    def __init__(self, rules_path: Path | None = None) -> None:
        self._rules_path = rules_path or RULES_PATH
        self._rules: dict[str, Any] = {}
        self._loaded = False

        # Daily tracking state
        self._daily_pnl: float = 0.0
        self._weekly_pnl: float = 0.0
        self._daily_trade_count: int = 0
        self._last_order_time: float = 0.0
        self._last_loss_time: float = 0.0
        self._tracking_day: str = ""
        self._tracking_week: str = ""
        self._kill_switch_active: bool = False

    @property
    def loaded(self) -> bool:
        return self._loaded

    @property
    def kill_switch_active(self) -> bool:
        return self._kill_switch_active

    @property
    def rules(self) -> dict[str, Any]:
        return self._rules

    def load_rules(self) -> None:
        """Load L0 meta-rules from YAML. Called once at startup."""
        if not self._rules_path.exists():
            raise FileNotFoundError(f"Meta-rules file not found: {self._rules_path}")

        with open(self._rules_path, encoding="utf-8") as f:
            self._rules = yaml.safe_load(f)

        self._loaded = True
        logger.info("L0 meta-rules loaded from %s", self._rules_path)

    def _require_loaded(self) -> None:
        if not self._loaded:
            raise RuntimeError("Risk engine not loaded. Call load_rules() first.")

    # ── Core Validation ──────────────────────────────────────

    def validate(
        self,
        trade: TradeRequest,
        portfolio_value: float,
        open_positions: dict[str, dict[str, float]] | None = None,
    ) -> RiskVerdict:
        """
        Validate a trade request against ALL L0 meta-rules.

        Args:
            trade: The proposed trade
            portfolio_value: Total portfolio value in quote currency
            open_positions: Dict of symbol → {"value": float} for open positions

        Returns:
            RiskVerdict with approved/rejected status and reasons
        """
        self._require_loaded()

        positions = open_positions or {}
        reasons: list[str] = []
        warnings: list[str] = []

        # === Kill switch check ===
        if self._kill_switch_active:
            reasons.append("KILL SWITCH ACTIVE — all trading halted")
            return self._make_verdict(trade, False, 0, 0, 0, reasons, warnings)

        # === Basic validation ===
        if trade.side not in ("buy", "sell"):
            reasons.append(f"Invalid side: {trade.side}")

        if trade.amount <= 0:
            reasons.append(f"Invalid amount: {trade.amount}")

        if trade.price <= 0:
            reasons.append(f"Invalid price: {trade.price}")

        # === L0: Reasoning required ===
        gov = self._rules.get("governance", {})
        if gov.get("require_reasoning", True) and not trade.reason:
            reasons.append("L0: Trade reason is required (governance.require_reasoning)")

        # === L0: Leverage check ===
        cap = self._rules.get("capital", {})
        max_leverage = cap.get("max_leverage", 3.0)
        if trade.leverage > max_leverage:
            reasons.append(
                f"L0: Leverage {trade.leverage}x exceeds max {max_leverage}x"
            )

        # === L0: Single trade risk ===
        trade_value = trade.amount * trade.price
        max_risk_pct = cap.get("max_single_trade_risk_pct", 1.5)
        risk_pct = (trade_value / portfolio_value * 100) if portfolio_value > 0 else 100
        if risk_pct > max_risk_pct:
            reasons.append(
                f"L0: Trade risk {risk_pct:.2f}% exceeds max {max_risk_pct}%"
            )

        # === L0: Position size limit ===
        max_pos_pct = cap.get("max_position_size_pct", 10.0)
        existing_value = positions.get(trade.symbol, {}).get("value", 0.0)
        new_pos_value = existing_value + trade_value if trade.side == "buy" else existing_value
        pos_pct = (new_pos_value / portfolio_value * 100) if portfolio_value > 0 else 100
        if pos_pct > max_pos_pct:
            reasons.append(
                f"L0: Position {pos_pct:.2f}% exceeds max {max_pos_pct}%"
            )

        # === L0: Total portfolio exposure ===
        max_exposure_pct = cap.get("max_portfolio_exposure_pct", 50.0)
        total_exposure = sum(p.get("value", 0) for p in positions.values())
        if trade.side == "buy":
            total_exposure += trade_value
        exposure_pct = (total_exposure / portfolio_value * 100) if portfolio_value > 0 else 0
        if exposure_pct > max_exposure_pct:
            reasons.append(
                f"L0: Portfolio exposure {exposure_pct:.2f}% exceeds max {max_exposure_pct}%"
            )

        # === L0: Daily drawdown ===
        dd = self._rules.get("drawdown", {})
        max_daily_dd = dd.get("max_daily_drawdown_pct", 4.0)
        daily_dd_pct = abs(self._daily_pnl / portfolio_value * 100) if portfolio_value > 0 and self._daily_pnl < 0 else 0
        if daily_dd_pct >= max_daily_dd:
            reasons.append(
                f"L0: Daily drawdown {daily_dd_pct:.2f}% exceeds max {max_daily_dd}%"
            )

        # === L0: Weekly drawdown ===
        max_weekly_dd = dd.get("max_weekly_drawdown_pct", 8.0)
        weekly_dd_pct = abs(self._weekly_pnl / portfolio_value * 100) if portfolio_value > 0 and self._weekly_pnl < 0 else 0
        if weekly_dd_pct >= max_weekly_dd:
            reasons.append(
                f"L0: Weekly drawdown {weekly_dd_pct:.2f}% exceeds max {max_weekly_dd}%"
            )

        # === L0: Cool-down after loss ===
        cool_down_min = dd.get("cool_down_minutes", 30)
        if self._last_loss_time > 0:
            elapsed = (time.time() - self._last_loss_time) / 60
            if elapsed < cool_down_min:
                remaining = cool_down_min - elapsed
                reasons.append(
                    f"L0: Cool-down active — {remaining:.0f} minutes remaining"
                )

        # === L0: Daily trade limit ===
        trading_rules = self._rules.get("trading", {})
        max_trades = trading_rules.get("max_daily_trades", 50)
        if self._daily_trade_count >= max_trades:
            reasons.append(
                f"L0: Daily trade limit reached ({self._daily_trade_count}/{max_trades})"
            )

        # === L0: Order interval ===
        min_interval = trading_rules.get("min_order_interval_seconds", 5)
        if self._last_order_time > 0:
            since_last = time.time() - self._last_order_time
            if since_last < min_interval:
                reasons.append(
                    f"L0: Order too fast — wait {min_interval - since_last:.1f}s"
                )

        # === Warnings (non-blocking) ===
        if risk_pct > max_risk_pct * 0.8:
            warnings.append(f"Near risk limit: {risk_pct:.2f}% of {max_risk_pct}%")
        if self._daily_trade_count > max_trades * 0.8:
            warnings.append(f"Near trade limit: {self._daily_trade_count}/{max_trades}")

        # === Compute approved position size ===
        approved = len(reasons) == 0
        safe_size = trade.amount if approved else 0.0

        return self._make_verdict(
            trade, approved, safe_size, trade_value, risk_pct, reasons, warnings
        )

    @staticmethod
    def _make_verdict(
        trade: TradeRequest,
        approved: bool,
        size: float,
        risk_amount: float,
        risk_pct: float,
        reasons: list[str],
        warnings: list[str],
    ) -> RiskVerdict:
        return RiskVerdict(
            approved=approved,
            trade=trade,
            position_size=size,
            risk_amount=risk_amount,
            risk_pct=risk_pct,
            rejection_reasons=reasons,
            warnings=warnings,
        )

    # ── Position Sizing ──────────────────────────────────────

    def calculate_safe_size(
        self,
        symbol: str,
        price: float,
        portfolio_value: float,
        stop_loss_pct: float = 2.0,
    ) -> float:
        """
        Calculate the maximum safe position size based on risk rules.

        Uses the formula: size = (portfolio * max_risk%) / (price * stop_loss%)
        This ensures that if stop-loss triggers, max loss = max_risk% of portfolio.

        Args:
            symbol: Trading pair
            price: Current price
            portfolio_value: Total portfolio value
            stop_loss_pct: Stop loss distance in percent

        Returns:
            Maximum safe position size in base currency
        """
        self._require_loaded()

        cap = self._rules.get("capital", {})
        max_risk_pct = cap.get("max_single_trade_risk_pct", 1.5)

        risk_budget = portfolio_value * (max_risk_pct / 100)
        price_risk = price * (stop_loss_pct / 100)

        if price_risk <= 0:
            return 0.0

        return risk_budget / price_risk

    # ── State Tracking ───────────────────────────────────────

    def record_trade_result(self, pnl: float) -> None:
        """
        Record a completed trade's P&L for drawdown tracking.
        Call this after every trade execution.
        """
        self._daily_pnl += pnl
        self._weekly_pnl += pnl
        self._daily_trade_count += 1
        self._last_order_time = time.time()

        # Trigger cool-down on significant loss
        dd = self._rules.get("drawdown", {})
        sig_loss_pct = dd.get("significant_loss_pct", 2.0)
        if pnl < 0 and abs(pnl) > sig_loss_pct:
            self._last_loss_time = time.time()
            logger.warning("Significant loss recorded: $%.2f — cool-down triggered", pnl)

    def reset_daily(self) -> None:
        """Reset daily counters. Call at start of each trading day."""
        self._daily_pnl = 0.0
        self._daily_trade_count = 0
        self._last_loss_time = 0.0
        logger.info("Daily risk counters reset")

    def reset_weekly(self) -> None:
        """Reset weekly counters. Call at start of each trading week."""
        self._weekly_pnl = 0.0
        self.reset_daily()
        logger.info("Weekly risk counters reset")

    # ── Kill Switch ──────────────────────────────────────────

    def activate_kill_switch(self, reason: str = "Manual activation") -> None:
        """Immediately halt ALL trading. No trade can pass validation."""
        self._kill_switch_active = True
        logger.critical("KILL SWITCH ACTIVATED: %s", reason)

    def deactivate_kill_switch(self) -> None:
        """Re-enable trading after kill switch."""
        self._kill_switch_active = False
        logger.info("Kill switch deactivated — trading resumed")

    # ── Status ───────────────────────────────────────────────

    def get_status(self) -> dict[str, Any]:
        """Get current risk engine status for dashboard."""
        return {
            "loaded": self._loaded,
            "kill_switch": self._kill_switch_active,
            "daily_pnl": self._daily_pnl,
            "weekly_pnl": self._weekly_pnl,
            "daily_trades": self._daily_trade_count,
            "max_daily_trades": self._rules.get("trading", {}).get("max_daily_trades", 50),
            "in_cool_down": self._is_in_cool_down(),
        }

    def _is_in_cool_down(self) -> bool:
        """Check if currently in cool-down period."""
        if self._last_loss_time <= 0:
            return False
        dd = self._rules.get("drawdown", {})
        cool_down_min = dd.get("cool_down_minutes", 30)
        elapsed = (time.time() - self._last_loss_time) / 60
        return elapsed < cool_down_min
