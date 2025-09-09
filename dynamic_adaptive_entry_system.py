# -*- coding: utf-8 -*-
"""
Dynamic Adaptive Entry System
ระบบเข้าเทรดแบบ Dynamic ที่ปรับตัวได้ในทุกสถานการณ์
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import math

logger = logging.getLogger(__name__)

class MarketCondition(Enum):
    """สภาวะตลาด"""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"
    QUIET = "quiet"
    BREAKOUT = "breakout"
    REVERSAL = "reversal"

class EntryStrategy(Enum):
    """กลยุทธ์การเข้าเทรด"""
    TREND_FOLLOWING = "trend_following"
    COUNTER_TREND = "counter_trend"
    BREAKOUT_ENTRY = "breakout_entry"
    REVERSAL_ENTRY = "reversal_entry"
    SCALPING_ENTRY = "scalping_entry"
    RECOVERY_ENTRY = "recovery_entry"
    BALANCE_ENTRY = "balance_entry"
    HEDGE_ENTRY = "hedge_entry"

class PortfolioHealth(Enum):
    """สุขภาพพอร์ต"""
    EXCELLENT = "excellent"      # > 80% health
    GOOD = "good"               # 60-80% health
    MODERATE = "moderate"       # 40-60% health
    POOR = "poor"              # 20-40% health
    CRITICAL = "critical"       # < 20% health

@dataclass
class DynamicEntryAnalysis:
    """ผลการวิเคราะห์การเข้าเทรดแบบ Dynamic"""
    should_enter: bool
    direction: str
    confidence: float
    lot_size: float
    entry_strategy: EntryStrategy
    market_condition: MarketCondition
    portfolio_health: PortfolioHealth
    risk_level: float
    expected_profit: float
    max_acceptable_loss: float
    entry_reasons: List[str]
    dynamic_adjustments: Dict[str, Any]
    emergency_overrides: List[str]

class DynamicAdaptiveEntrySystem:
    """ระบบเข้าเทรดแบบ Dynamic ที่ปรับตัวได้ทุกสถานการณ์"""
    
    def __init__(self, mt5_connection=None, symbol: str = "XAUUSD"):
        self.mt5_connection = mt5_connection
        self.symbol = symbol
        
        # 🎯 Dynamic Parameters - ปรับตัวตามสถานการณ์
        self.base_lot_size = 0.01
        self.max_lot_size = 1.0
        self.min_confidence_threshold = 30.0  # Dynamic threshold
        self.max_positions_per_direction = 10  # Dynamic limit
        
        # 📊 Market Analysis Parameters
        self.trend_strength_threshold = 0.6
        self.volatility_threshold = 0.5
        self.volume_threshold = 0.4
        
        # 🛡️ Risk Management Parameters (Dynamic)
        self.max_portfolio_risk = 0.15  # 15% max risk
        self.emergency_risk_limit = 0.25  # 25% emergency limit
        self.balance_tolerance = 0.3  # 30% imbalance tolerance
        
        # 🔧 Adaptive Settings
        self.adaptive_mode = True
        self.emergency_mode = False
        self.scalping_mode = False
        self.recovery_mode = False
        
        logger.info("🚀 Dynamic Adaptive Entry System initialized")
    
    def analyze_dynamic_entry(self, signal_direction: str, current_price: float,
                            positions: List[Any], account_info: Dict,
                            candle_data: Any = None) -> DynamicEntryAnalysis:
        """
        🎯 Dynamic Entry Analysis - วิเคราะห์การเข้าเทรดแบบ Dynamic
        """
        try:
            logger.info(f"🔍 DYNAMIC ENTRY ANALYSIS: {signal_direction} at {current_price:.2f}")
            
            # 1. 📊 Market Condition Analysis
            market_condition = self._analyze_market_condition(current_price, candle_data, positions)
            logger.info(f"   Market Condition: {market_condition.value}")
            
            # 2. 🏥 Portfolio Health Assessment
            portfolio_health = self._assess_portfolio_health(positions, account_info)
            logger.info(f"   Portfolio Health: {portfolio_health.value}")
            
            # 3. 🎯 Dynamic Strategy Selection
            entry_strategy = self._select_dynamic_strategy(
                signal_direction, market_condition, portfolio_health, positions
            )
            logger.info(f"   Entry Strategy: {entry_strategy.value}")
            
            # 4. ⚖️ Dynamic Risk Assessment
            risk_analysis = self._calculate_dynamic_risk(
                positions, account_info, market_condition, portfolio_health
            )
            
            # 5. 📈 Dynamic Lot Sizing
            dynamic_lot = self._calculate_dynamic_lot_size(
                signal_direction, market_condition, portfolio_health, 
                risk_analysis, positions, account_info
            )
            
            # 6. 🧠 Confidence Calculation
            confidence = self._calculate_dynamic_confidence(
                signal_direction, market_condition, portfolio_health,
                entry_strategy, risk_analysis, positions
            )
            
            # 7. 🚨 Emergency Overrides Check
            emergency_overrides = self._check_emergency_overrides(
                positions, account_info, market_condition, portfolio_health
            )
            
            # 8. 🎯 Final Entry Decision
            should_enter = self._make_dynamic_entry_decision(
                confidence, risk_analysis, emergency_overrides, portfolio_health
            )
            
            # 9. 🔧 Dynamic Adjustments
            dynamic_adjustments = self._apply_dynamic_adjustments(
                signal_direction, market_condition, portfolio_health, positions
            )
            
            # 10. 📝 Entry Reasons
            entry_reasons = self._compile_entry_reasons(
                should_enter, entry_strategy, market_condition, 
                portfolio_health, confidence, risk_analysis
            )
            
            analysis = DynamicEntryAnalysis(
                should_enter=should_enter,
                direction=dynamic_adjustments.get('final_direction', signal_direction),
                confidence=confidence,
                lot_size=dynamic_lot,
                entry_strategy=entry_strategy,
                market_condition=market_condition,
                portfolio_health=portfolio_health,
                risk_level=risk_analysis['risk_percentage'],
                expected_profit=dynamic_adjustments.get('expected_profit', 0.0),
                max_acceptable_loss=risk_analysis['max_loss'],
                entry_reasons=entry_reasons,
                dynamic_adjustments=dynamic_adjustments,
                emergency_overrides=emergency_overrides
            )
            
            self._log_dynamic_entry_decision(analysis)
            return analysis
            
        except Exception as e:
            logger.error(f"❌ Error in dynamic entry analysis: {e}")
            return self._create_safe_fallback_analysis(signal_direction)
    
    def _analyze_market_condition(self, current_price: float, candle_data: Any, 
                                positions: List[Any]) -> MarketCondition:
        """📊 วิเคราะห์สภาวะตลาดแบบ Dynamic"""
        try:
            if not candle_data:
                return MarketCondition.RANGING
            
            # Calculate price movement
            price_range = abs(candle_data.high - candle_data.low)
            body_size = abs(candle_data.close - candle_data.open)
            body_ratio = body_size / price_range if price_range > 0 else 0
            
            # Calculate volatility (simplified)
            volatility = price_range / current_price * 100
            
            # Determine condition
            if volatility > 0.5 and body_ratio > 0.7:
                if candle_data.close > candle_data.open:
                    return MarketCondition.TRENDING_UP
                else:
                    return MarketCondition.TRENDING_DOWN
            elif volatility > 0.8:
                return MarketCondition.VOLATILE
            elif volatility < 0.1:
                return MarketCondition.QUIET
            elif body_ratio > 0.8:
                return MarketCondition.BREAKOUT
            else:
                return MarketCondition.RANGING
                
        except Exception as e:
            logger.error(f"❌ Error analyzing market condition: {e}")
            return MarketCondition.RANGING
    
    def _assess_portfolio_health(self, positions: List[Any], account_info: Dict) -> PortfolioHealth:
        """🏥 ประเมินสุขภาพพอร์ตแบบ Dynamic"""
        try:
            if not positions:
                return PortfolioHealth.EXCELLENT
            
            total_profit = sum(getattr(pos, 'profit', 0) for pos in positions)
            balance = account_info.get('balance', 10000)
            equity = account_info.get('equity', balance)
            margin_level = account_info.get('margin_level', 1000)
            
            # Calculate health metrics
            profit_ratio = total_profit / balance if balance > 0 else 0
            equity_ratio = equity / balance if balance > 0 else 1
            margin_health = min(margin_level / 100, 10) if margin_level > 0 else 10
            
            # Calculate overall health score
            health_score = (
                (profit_ratio + 1) * 0.3 +  # Profit impact
                equity_ratio * 0.4 +         # Equity health
                min(margin_health, 1) * 0.3  # Margin health
            ) * 100
            
            if health_score >= 80:
                return PortfolioHealth.EXCELLENT
            elif health_score >= 60:
                return PortfolioHealth.GOOD
            elif health_score >= 40:
                return PortfolioHealth.MODERATE
            elif health_score >= 20:
                return PortfolioHealth.POOR
            else:
                return PortfolioHealth.CRITICAL
                
        except Exception as e:
            logger.error(f"❌ Error assessing portfolio health: {e}")
            return PortfolioHealth.MODERATE
    
    def _select_dynamic_strategy(self, signal_direction: str, market_condition: MarketCondition,
                               portfolio_health: PortfolioHealth, positions: List[Any]) -> EntryStrategy:
        """🎯 เลือกกลยุทธ์แบบ Dynamic"""
        try:
            buy_count = len([p for p in positions if getattr(p, 'type', 0) == 0])
            sell_count = len([p for p in positions if getattr(p, 'type', 1) == 1])
            losing_positions = len([p for p in positions if getattr(p, 'profit', 0) < 0])
            
            # Emergency conditions
            if portfolio_health == PortfolioHealth.CRITICAL:
                return EntryStrategy.RECOVERY_ENTRY
            
            # Balance conditions
            if abs(buy_count - sell_count) > 5:
                return EntryStrategy.BALANCE_ENTRY
            
            # Market-based strategy
            if market_condition in [MarketCondition.TRENDING_UP, MarketCondition.TRENDING_DOWN]:
                return EntryStrategy.TREND_FOLLOWING
            elif market_condition == MarketCondition.BREAKOUT:
                return EntryStrategy.BREAKOUT_ENTRY
            elif market_condition == MarketCondition.VOLATILE:
                return EntryStrategy.SCALPING_ENTRY
            elif market_condition == MarketCondition.RANGING:
                return EntryStrategy.COUNTER_TREND
            else:
                return EntryStrategy.TREND_FOLLOWING
                
        except Exception as e:
            logger.error(f"❌ Error selecting strategy: {e}")
            return EntryStrategy.TREND_FOLLOWING
    
    def _calculate_dynamic_risk(self, positions: List[Any], account_info: Dict,
                              market_condition: MarketCondition, 
                              portfolio_health: PortfolioHealth) -> Dict[str, float]:
        """⚖️ คำนวณความเสี่ยงแบบ Dynamic"""
        try:
            balance = account_info.get('balance', 10000)
            equity = account_info.get('equity', balance)
            margin = account_info.get('margin', 0)
            free_margin = account_info.get('margin_free', balance)
            
            # Base risk calculation
            base_risk = 0.02  # 2% base risk
            
            # Adjust risk based on portfolio health
            health_multiplier = {
                PortfolioHealth.EXCELLENT: 1.5,
                PortfolioHealth.GOOD: 1.2,
                PortfolioHealth.MODERATE: 1.0,
                PortfolioHealth.POOR: 0.7,
                PortfolioHealth.CRITICAL: 0.3
            }.get(portfolio_health, 1.0)
            
            # Adjust risk based on market condition
            market_multiplier = {
                MarketCondition.TRENDING_UP: 1.3,
                MarketCondition.TRENDING_DOWN: 1.3,
                MarketCondition.BREAKOUT: 1.1,
                MarketCondition.RANGING: 0.9,
                MarketCondition.VOLATILE: 0.8,
                MarketCondition.QUIET: 1.0,
                MarketCondition.REVERSAL: 0.7
            }.get(market_condition, 1.0)
            
            # Calculate dynamic risk
            dynamic_risk = base_risk * health_multiplier * market_multiplier
            
            # Apply limits
            max_risk = min(free_margin * 0.1 / balance, 0.05) if balance > 0 else 0.01
            final_risk = min(dynamic_risk, max_risk)
            
            return {
                'risk_percentage': final_risk,
                'max_loss': balance * final_risk,
                'recommended_margin': margin * 0.1,
                'health_multiplier': health_multiplier,
                'market_multiplier': market_multiplier
            }
            
        except Exception as e:
            logger.error(f"❌ Error calculating dynamic risk: {e}")
            return {
                'risk_percentage': 0.01,
                'max_loss': 100.0,
                'recommended_margin': 1000.0,
                'health_multiplier': 1.0,
                'market_multiplier': 1.0
            }
    
    def _calculate_dynamic_lot_size(self, signal_direction: str, market_condition: MarketCondition,
                                  portfolio_health: PortfolioHealth, risk_analysis: Dict,
                                  positions: List[Any], account_info: Dict) -> float:
        """📈 คำนวณขนาด Lot แบบ Dynamic"""
        try:
            balance = account_info.get('balance', 10000)
            max_loss = risk_analysis['max_loss']
            
            # Base lot calculation
            base_lot = max_loss / 1000  # Assume $10 per 0.01 lot risk
            
            # Adjust based on market condition
            market_adjustment = {
                MarketCondition.TRENDING_UP: 1.2,
                MarketCondition.TRENDING_DOWN: 1.2,
                MarketCondition.BREAKOUT: 1.1,
                MarketCondition.VOLATILE: 0.8,
                MarketCondition.QUIET: 0.9,
                MarketCondition.RANGING: 1.0,
                MarketCondition.REVERSAL: 0.7
            }.get(market_condition, 1.0)
            
            # Adjust based on portfolio health
            health_adjustment = {
                PortfolioHealth.EXCELLENT: 1.3,
                PortfolioHealth.GOOD: 1.1,
                PortfolioHealth.MODERATE: 1.0,
                PortfolioHealth.POOR: 0.8,
                PortfolioHealth.CRITICAL: 0.5
            }.get(portfolio_health, 1.0)
            
            # Position count adjustment
            position_count = len(positions)
            count_adjustment = max(0.5, 1.0 - (position_count * 0.05))
            
            # Calculate final lot size
            dynamic_lot = base_lot * market_adjustment * health_adjustment * count_adjustment
            
            # Apply limits
            dynamic_lot = max(0.01, min(dynamic_lot, self.max_lot_size))
            
            return round(dynamic_lot, 2)
            
        except Exception as e:
            logger.error(f"❌ Error calculating dynamic lot size: {e}")
            return 0.01
    
    def _calculate_dynamic_confidence(self, signal_direction: str, market_condition: MarketCondition,
                                    portfolio_health: PortfolioHealth, entry_strategy: EntryStrategy,
                                    risk_analysis: Dict, positions: List[Any]) -> float:
        """🧠 คำนวณความมั่นใจแบบ Dynamic"""
        try:
            base_confidence = 50.0
            
            # Market condition confidence - เพิ่ม confidence ในตลาดเงียบ
            market_confidence = {
                MarketCondition.TRENDING_UP: 75.0,
                MarketCondition.TRENDING_DOWN: 75.0,
                MarketCondition.BREAKOUT: 80.0,
                MarketCondition.RANGING: 65.0,    # เพิ่มจาก 60
                MarketCondition.VOLATILE: 50.0,   # เพิ่มจาก 45
                MarketCondition.QUIET: 70.0,      # เพิ่มจาก 55 เป็น 70
                MarketCondition.REVERSAL: 45.0    # เพิ่มจาก 40
            }.get(market_condition, 55.0)
            
            # Portfolio health confidence
            health_confidence = {
                PortfolioHealth.EXCELLENT: 85.0,
                PortfolioHealth.GOOD: 75.0,
                PortfolioHealth.MODERATE: 65.0,
                PortfolioHealth.POOR: 45.0,
                PortfolioHealth.CRITICAL: 25.0
            }.get(portfolio_health, 50.0)
            
            # Strategy confidence
            strategy_confidence = {
                EntryStrategy.TREND_FOLLOWING: 70.0,
                EntryStrategy.BREAKOUT_ENTRY: 75.0,
                EntryStrategy.COUNTER_TREND: 60.0,
                EntryStrategy.SCALPING_ENTRY: 55.0,
                EntryStrategy.RECOVERY_ENTRY: 40.0,
                EntryStrategy.BALANCE_ENTRY: 65.0,
                EntryStrategy.HEDGE_ENTRY: 50.0,
                EntryStrategy.REVERSAL_ENTRY: 45.0
            }.get(entry_strategy, 50.0)
            
            # Risk-adjusted confidence
            risk_confidence = max(30.0, 100.0 - (risk_analysis['risk_percentage'] * 1000))
            
            # Calculate weighted confidence
            final_confidence = (
                market_confidence * 0.3 +
                health_confidence * 0.3 +
                strategy_confidence * 0.2 +
                risk_confidence * 0.2
            )
            
            return min(95.0, max(10.0, final_confidence))
            
        except Exception as e:
            logger.error(f"❌ Error calculating confidence: {e}")
            return 50.0
    
    def _check_emergency_overrides(self, positions: List[Any], account_info: Dict,
                                 market_condition: MarketCondition, 
                                 portfolio_health: PortfolioHealth) -> List[str]:
        """🚨 ตรวจสอบ Emergency Overrides"""
        overrides = []
        
        try:
            margin_level = account_info.get('margin_level', 1000)
            equity = account_info.get('equity', 10000)
            balance = account_info.get('balance', 10000)
            
            # Margin call risk - แก้ไขการตรวจสอบเมื่อไม่มี positions
            if len(positions) > 0 and margin_level > 0 and margin_level < 100:
                overrides.append("MARGIN_CALL_RISK")
                logger.warning(f"🚨 MARGIN_CALL_RISK: {margin_level}% < 100%")
            elif len(positions) == 0:
                # ไม่มี positions = ไม่มีความเสี่ยง margin
                logger.debug(f"📊 No positions - Margin check skipped (Level: {margin_level}%)")
            
            # Equity protection
            if equity < balance * 0.7:
                overrides.append("EQUITY_PROTECTION")
            
            # Position limit
            if len(positions) > 20:
                overrides.append("POSITION_LIMIT")
            
            # Critical portfolio health
            if portfolio_health == PortfolioHealth.CRITICAL:
                overrides.append("CRITICAL_PORTFOLIO")
            
            # High volatility protection
            if market_condition == MarketCondition.VOLATILE:
                losing_positions = [p for p in positions if getattr(p, 'profit', 0) < -100]
                if len(losing_positions) > 5:
                    overrides.append("VOLATILITY_PROTECTION")
                    
        except Exception as e:
            logger.error(f"❌ Error checking emergency overrides: {e}")
            
        return overrides
    
    def _make_dynamic_entry_decision(self, confidence: float, risk_analysis: Dict,
                                   emergency_overrides: List[str], 
                                   portfolio_health: PortfolioHealth) -> bool:
        """🎯 ตัดสินใจเข้าเทรดแบบ Dynamic"""
        try:
            # Emergency blocks - แสดงรายละเอียด
            critical_overrides = ["MARGIN_CALL_RISK", "CRITICAL_PORTFOLIO"]
            blocked_overrides = [override for override in critical_overrides if override in emergency_overrides]
            if blocked_overrides:
                logger.warning(f"🚨 EMERGENCY BLOCK: {', '.join(blocked_overrides)}")
                return False
            
            # Dynamic confidence threshold - ลดให้เข้าได้ง่ายขึ้น
            health_threshold = {
                PortfolioHealth.EXCELLENT: 25.0,  # ลดจาก 40 เป็น 25
                PortfolioHealth.GOOD: 35.0,       # ลดจาก 50 เป็น 35
                PortfolioHealth.MODERATE: 45.0,   # ลดจาก 60 เป็น 45
                PortfolioHealth.POOR: 60.0,       # ลดจาก 70 เป็น 60
                PortfolioHealth.CRITICAL: 75.0    # ลดจาก 85 เป็น 75
            }.get(portfolio_health, 45.0)
            
            # Risk-adjusted threshold
            risk_threshold = health_threshold + (risk_analysis['risk_percentage'] * 500)
            
            return confidence >= risk_threshold
            
        except Exception as e:
            logger.error(f"❌ Error making entry decision: {e}")
            return False
    
    def _apply_dynamic_adjustments(self, signal_direction: str, market_condition: MarketCondition,
                                 portfolio_health: PortfolioHealth, positions: List[Any]) -> Dict[str, Any]:
        """🔧 ใช้การปรับแต่งแบบ Dynamic"""
        adjustments = {
            'final_direction': signal_direction,
            'expected_profit': 50.0,
            'adjustments_applied': []
        }
        
        try:
            buy_count = len([p for p in positions if getattr(p, 'type', 0) == 0])
            sell_count = len([p for p in positions if getattr(p, 'type', 1) == 1])
            
            # Balance adjustment
            if abs(buy_count - sell_count) > 3:
                if buy_count > sell_count and signal_direction == "BUY":
                    adjustments['final_direction'] = "SELL"
                    adjustments['adjustments_applied'].append("BALANCE_REVERSAL")
                elif sell_count > buy_count and signal_direction == "SELL":
                    adjustments['final_direction'] = "BUY"
                    adjustments['adjustments_applied'].append("BALANCE_REVERSAL")
            
            # Market condition adjustments
            if market_condition == MarketCondition.VOLATILE:
                adjustments['expected_profit'] *= 0.7
                adjustments['adjustments_applied'].append("VOLATILITY_ADJUSTMENT")
            elif market_condition in [MarketCondition.TRENDING_UP, MarketCondition.TRENDING_DOWN]:
                adjustments['expected_profit'] *= 1.3
                adjustments['adjustments_applied'].append("TREND_BOOST")
                
        except Exception as e:
            logger.error(f"❌ Error applying dynamic adjustments: {e}")
            
        return adjustments
    
    def _compile_entry_reasons(self, should_enter: bool, entry_strategy: EntryStrategy,
                             market_condition: MarketCondition, portfolio_health: PortfolioHealth,
                             confidence: float, risk_analysis: Dict) -> List[str]:
        """📝 รวบรวมเหตุผลการเข้าเทรด"""
        reasons = []
        
        if should_enter:
            reasons.append(f"Strategy: {entry_strategy.value}")
            reasons.append(f"Market: {market_condition.value}")
            reasons.append(f"Health: {portfolio_health.value}")
            reasons.append(f"Confidence: {confidence:.1f}%")
            reasons.append(f"Risk: {risk_analysis['risk_percentage']*100:.1f}%")
        else:
            reasons.append("ENTRY BLOCKED")
            if confidence < 50:
                reasons.append(f"Low confidence: {confidence:.1f}%")
            if risk_analysis['risk_percentage'] > 0.05:
                reasons.append(f"High risk: {risk_analysis['risk_percentage']*100:.1f}%")
            if portfolio_health in [PortfolioHealth.POOR, PortfolioHealth.CRITICAL]:
                reasons.append(f"Poor health: {portfolio_health.value}")
                
        return reasons
    
    def _log_dynamic_entry_decision(self, analysis: DynamicEntryAnalysis):
        """📊 แสดง log การตัดสินใจแบบสั้นกระชับ"""
        status = "✅ ENTER" if analysis.should_enter else "🚫 BLOCK"
        
        # Log แบบบรรทัดเดียว สั้นกระชับ
        logger.info(f"{status} {analysis.direction} {analysis.lot_size}lot | "
                   f"Conf:{analysis.confidence:.0f}% | {analysis.market_condition.value.upper()} | "
                   f"Health:{analysis.portfolio_health.value.upper()}")
        
        # แสดง emergency overrides เฉพาะเมื่อมี
        if analysis.emergency_overrides:
            logger.warning(f"🚨 {', '.join(analysis.emergency_overrides)}")
        
        # แสดง adjustments เฉพาะเมื่อมี
        if analysis.dynamic_adjustments.get('adjustments_applied'):
            logger.info(f"🔧 {', '.join(analysis.dynamic_adjustments['adjustments_applied'])}")
    
    def _create_safe_fallback_analysis(self, signal_direction: str) -> DynamicEntryAnalysis:
        """🛡️ สร้างการวิเคราะห์ fallback ที่ปลอดภัย"""
        return DynamicEntryAnalysis(
            should_enter=False,
            direction=signal_direction,
            confidence=0.0,
            lot_size=0.01,
            entry_strategy=EntryStrategy.TREND_FOLLOWING,
            market_condition=MarketCondition.RANGING,
            portfolio_health=PortfolioHealth.MODERATE,
            risk_level=0.01,
            expected_profit=0.0,
            max_acceptable_loss=100.0,
            entry_reasons=["SYSTEM_ERROR", "SAFE_FALLBACK"],
            dynamic_adjustments={'final_direction': signal_direction, 'expected_profit': 0.0, 'adjustments_applied': []},
            emergency_overrides=["SYSTEM_ERROR"]
        )

def create_dynamic_adaptive_entry_system(mt5_connection=None, symbol: str = "XAUUSD") -> DynamicAdaptiveEntrySystem:
    """สร้าง Dynamic Adaptive Entry System"""
    return DynamicAdaptiveEntrySystem(mt5_connection, symbol)

if __name__ == "__main__":
    # Test the system
    system = create_dynamic_adaptive_entry_system()
    logger.info("🚀 Dynamic Adaptive Entry System ready for testing")
