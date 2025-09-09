# -*- coding: utf-8 -*-
"""
Dynamic Adaptive Closer System
ระบบปิดตำแหน่งแบบ Dynamic ที่ปรับตัวได้ทุกสถานการณ์
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import math

logger = logging.getLogger(__name__)

class ClosingStrategy(Enum):
    """กลยุทธ์การปิดตำแหน่ง"""
    PROFIT_TAKING = "profit_taking"
    LOSS_CUTTING = "loss_cutting"
    BALANCE_RECOVERY = "balance_recovery"
    MARGIN_RELIEF = "margin_relief"
    RISK_REDUCTION = "risk_reduction"
    PORTFOLIO_OPTIMIZATION = "portfolio_optimization"
    EMERGENCY_EXIT = "emergency_exit"
    SCALPING_EXIT = "scalping_exit"

class MarketTiming(Enum):
    """จังหวะตลาด"""
    PERFECT = "perfect"       # จังหวะสมบูรณ์แบบ
    GOOD = "good"            # จังหวะดี
    ACCEPTABLE = "acceptable" # จังหวะพอใช้
    POOR = "poor"            # จังหวะไม่ดี
    TERRIBLE = "terrible"    # จังหวะแย่

class ClosingUrgency(Enum):
    """ความเร่งด่วนในการปิด"""
    IMMEDIATE = "immediate"   # ทันที
    HIGH = "high"            # เร่งด่วน
    MEDIUM = "medium"        # ปานกลาง
    LOW = "low"              # ไม่เร่งด่วน
    WAIT = "wait"            # รอจังหวะ

@dataclass
class DynamicClosingAnalysis:
    """ผลการวิเคราะห์การปิดแบบ Dynamic"""
    should_close: bool
    closing_strategy: ClosingStrategy
    market_timing: MarketTiming
    urgency: ClosingUrgency
    positions_to_close: List[int]  # ticket numbers
    expected_profit: float
    risk_reduction: float
    confidence: float
    alternative_strategies: List[ClosingStrategy]
    dynamic_adjustments: Dict[str, Any]
    closing_reasons: List[str]

@dataclass
class ClosingGroup:
    """กลุ่มการปิดตำแหน่ง"""
    group_id: str
    positions: List[Any]
    total_profit: float
    total_volume: float
    closing_reason: str
    priority: int
    estimated_execution_time: float

class DynamicAdaptiveCloser:
    """ระบบปิดตำแหน่งแบบ Dynamic ที่ปรับตัวได้ทุกสถานการณ์"""
    
    def __init__(self, mt5_connection=None, symbol: str = "XAUUSD"):
        self.mt5_connection = mt5_connection
        self.symbol = symbol
        
        # 🎯 Dynamic Closing Parameters - ปรับให้ปิดได้ง่ายขึ้น
        self.min_profit_threshold = 2.0     # ลดจาก 5 เป็น 2
        self.max_loss_threshold = -100.0    # ลดจาก -200 เป็น -100
        self.balance_tolerance = 0.3        # เพิ่มจาก 20% เป็น 30%
        self.margin_safety_level = 150      # ลดจาก 200 เป็น 150
        
        # 📊 Market Timing Parameters
        self.volatility_window = 14         # periods for volatility calculation
        self.trend_strength_threshold = 0.7
        self.momentum_threshold = 0.6
        
        # 🧠 Adaptive Learning
        self.closing_success_history = {}
        self.market_pattern_memory = {}
        self.adaptation_factor = 0.15
        
        # 🎯 Multi-Strategy Weights (Dynamic)
        self.strategy_weights = {
            ClosingStrategy.PROFIT_TAKING: 1.0,
            ClosingStrategy.BALANCE_RECOVERY: 1.2,
            ClosingStrategy.MARGIN_RELIEF: 1.5,
            ClosingStrategy.RISK_REDUCTION: 1.1,
            ClosingStrategy.PORTFOLIO_OPTIMIZATION: 0.9,
            ClosingStrategy.EMERGENCY_EXIT: 2.0,
            ClosingStrategy.SCALPING_EXIT: 0.8
        }
        
        logger.info("💰 Dynamic Adaptive Closer initialized")
    
    def analyze_dynamic_closing(self, positions: List[Any], account_info: Dict,
                              current_price: float, market_data: Dict = None) -> DynamicClosingAnalysis:
        """
        🎯 Dynamic Closing Analysis - วิเคราะห์การปิดตำแหน่งแบบ Dynamic
        """
        try:
            logger.info(f"🔍 DYNAMIC CLOSING ANALYSIS: {len(positions)} positions")
            
            # 1. 📊 Market Timing Assessment
            market_timing = self._assess_market_timing(current_price, market_data, positions)
            logger.info(f"   Market Timing: {market_timing.value}")
            
            # 2. 🚨 Urgency Assessment
            urgency = self._assess_closing_urgency(positions, account_info, market_timing)
            logger.info(f"   Urgency: {urgency.value}")
            
            # 3. 🎯 Strategy Selection
            closing_strategy = self._select_closing_strategy(positions, account_info, market_timing, urgency)
            logger.info(f"   Strategy: {closing_strategy.value}")
            
            # 4. 🎪 Position Selection
            positions_to_close = self._select_positions_to_close(
                positions, closing_strategy, current_price, account_info
            )
            
            # 5. 💰 Profit Calculation
            expected_profit = self._calculate_expected_profit(positions_to_close, current_price)
            
            # 6. ⚖️ Risk Reduction Calculation
            risk_reduction = self._calculate_risk_reduction(positions_to_close, account_info)
            
            # 7. 🧠 Confidence Assessment
            confidence = self._calculate_closing_confidence(
                closing_strategy, market_timing, urgency, positions_to_close
            )
            
            # 8. 🔄 Alternative Strategies
            alternative_strategies = self._find_alternative_strategies(
                closing_strategy, positions, account_info, market_timing
            )
            
            # 9. 🔧 Dynamic Adjustments
            dynamic_adjustments = self._apply_closing_adjustments(
                positions_to_close, closing_strategy, market_timing, current_price
            )
            
            # 10. 📝 Closing Reasons
            closing_reasons = self._compile_closing_reasons(
                closing_strategy, market_timing, urgency, positions_to_close, account_info
            )
            
            # 11. 🎯 Final Decision
            should_close = self._make_final_closing_decision(
                confidence, urgency, expected_profit, risk_reduction, account_info
            )
            
            analysis = DynamicClosingAnalysis(
                should_close=should_close,
                closing_strategy=closing_strategy,
                market_timing=market_timing,
                urgency=urgency,
                positions_to_close=[getattr(pos, 'ticket', 0) for pos in positions_to_close],
                expected_profit=expected_profit,
                risk_reduction=risk_reduction,
                confidence=confidence,
                alternative_strategies=alternative_strategies,
                dynamic_adjustments=dynamic_adjustments,
                closing_reasons=closing_reasons
            )
            
            self._log_closing_analysis(analysis)
            return analysis
            
        except Exception as e:
            logger.error(f"❌ Error in dynamic closing analysis: {e}")
            return self._create_safe_closing_analysis()
    
    def create_closing_groups(self, positions: List[Any], closing_strategy: ClosingStrategy,
                            current_price: float) -> List[ClosingGroup]:
        """🎪 สร้างกลุ่มการปิดตำแหน่งแบบ Dynamic"""
        try:
            groups = []
            
            if closing_strategy == ClosingStrategy.PROFIT_TAKING:
                groups = self._create_profit_groups(positions, current_price)
            elif closing_strategy == ClosingStrategy.BALANCE_RECOVERY:
                groups = self._create_balance_groups(positions, current_price)
            elif closing_strategy == ClosingStrategy.MARGIN_RELIEF:
                groups = self._create_margin_relief_groups(positions, current_price)
            elif closing_strategy == ClosingStrategy.RISK_REDUCTION:
                groups = self._create_risk_reduction_groups(positions, current_price)
            elif closing_strategy == ClosingStrategy.PORTFOLIO_OPTIMIZATION:
                groups = self._create_optimization_groups(positions, current_price)
            elif closing_strategy == ClosingStrategy.EMERGENCY_EXIT:
                groups = self._create_emergency_groups(positions, current_price)
            else:
                groups = self._create_default_groups(positions, current_price)
            
            # Sort by priority
            groups.sort(key=lambda g: g.priority, reverse=True)
            
            logger.info(f"🎪 Created {len(groups)} closing groups for {closing_strategy.value}")
            return groups
            
        except Exception as e:
            logger.error(f"❌ Error creating closing groups: {e}")
            return []
    
    def _assess_market_timing(self, current_price: float, market_data: Dict,
                            positions: List[Any]) -> MarketTiming:
        """📊 ประเมินจังหวะตลาด"""
        try:
            if not market_data:
                return MarketTiming.ACCEPTABLE
            
            # Simplified market timing assessment
            volatility = market_data.get('volatility', 0.5)
            trend_strength = market_data.get('trend_strength', 0.5)
            volume = market_data.get('volume', 0.5)
            
            # Calculate timing score
            timing_score = (
                (1 - volatility) * 0.4 +      # Lower volatility = better timing
                trend_strength * 0.3 +         # Strong trend = better timing
                volume * 0.3                   # Good volume = better timing
            )
            
            if timing_score >= 0.8:
                return MarketTiming.PERFECT
            elif timing_score >= 0.6:
                return MarketTiming.GOOD
            elif timing_score >= 0.4:
                return MarketTiming.ACCEPTABLE
            elif timing_score >= 0.2:
                return MarketTiming.POOR
            else:
                return MarketTiming.TERRIBLE
                
        except Exception as e:
            logger.error(f"❌ Error assessing market timing: {e}")
            return MarketTiming.ACCEPTABLE
    
    def _assess_closing_urgency(self, positions: List[Any], account_info: Dict,
                              market_timing: MarketTiming) -> ClosingUrgency:
        """🚨 ประเมินความเร่งด่วนในการปิด"""
        try:
            balance = account_info.get('balance', 10000)
            equity = account_info.get('equity', balance)
            margin_level = account_info.get('margin_level', 1000)
            
            # Emergency conditions - สอดคล้องกับระบบอื่น
            if margin_level < 100:  # เปลี่ยนจาก 120 เป็น 100
                return ClosingUrgency.IMMEDIATE
            
            if equity < balance * 0.8:
                return ClosingUrgency.IMMEDIATE
            
            # High urgency conditions
            total_loss = sum(getattr(pos, 'profit', 0) for pos in positions if getattr(pos, 'profit', 0) < 0)
            if total_loss < balance * -0.1:  # 10% total loss
                return ClosingUrgency.HIGH
            
            if len(positions) > 20:
                return ClosingUrgency.HIGH
            
            # Medium urgency conditions
            losing_positions = [pos for pos in positions if getattr(pos, 'profit', 0) < -100]
            if len(losing_positions) > 5:
                return ClosingUrgency.MEDIUM
            
            # Market timing influence
            if market_timing == MarketTiming.PERFECT:
                return ClosingUrgency.HIGH  # Good time to close
            elif market_timing == MarketTiming.TERRIBLE:
                return ClosingUrgency.WAIT  # Wait for better timing
            
            return ClosingUrgency.LOW
            
        except Exception as e:
            logger.error(f"❌ Error assessing closing urgency: {e}")
            return ClosingUrgency.MEDIUM
    
    def _select_closing_strategy(self, positions: List[Any], account_info: Dict,
                               market_timing: MarketTiming, urgency: ClosingUrgency) -> ClosingStrategy:
        """🎯 เลือกกลยุทธ์การปิด"""
        try:
            balance = account_info.get('balance', 10000)
            margin_level = account_info.get('margin_level', 1000)
            
            # Emergency conditions
            if urgency == ClosingUrgency.IMMEDIATE:
                if margin_level < 120:
                    return ClosingStrategy.MARGIN_RELIEF
                else:
                    return ClosingStrategy.EMERGENCY_EXIT
            
            # Profit opportunities
            profitable_positions = [pos for pos in positions if getattr(pos, 'profit', 0) > 10]
            if len(profitable_positions) > 3 and market_timing in [MarketTiming.PERFECT, MarketTiming.GOOD]:
                return ClosingStrategy.PROFIT_TAKING
            
            # Balance issues
            buy_positions = [pos for pos in positions if getattr(pos, 'type', 0) == 0]
            sell_positions = [pos for pos in positions if getattr(pos, 'type', 1) == 1]
            if abs(len(buy_positions) - len(sell_positions)) > 5:
                return ClosingStrategy.BALANCE_RECOVERY
            
            # Risk management
            high_risk_positions = [pos for pos in positions if getattr(pos, 'profit', 0) < -150]
            if len(high_risk_positions) > 3:
                return ClosingStrategy.RISK_REDUCTION
            
            # Default strategy
            return ClosingStrategy.PORTFOLIO_OPTIMIZATION
            
        except Exception as e:
            logger.error(f"❌ Error selecting closing strategy: {e}")
            return ClosingStrategy.PORTFOLIO_OPTIMIZATION
    
    def _select_positions_to_close(self, positions: List[Any], strategy: ClosingStrategy,
                                 current_price: float, account_info: Dict) -> List[Any]:
        """🎪 เลือกตำแหน่งที่จะปิด"""
        try:
            if strategy == ClosingStrategy.PROFIT_TAKING:
                return self._select_profitable_positions(positions, current_price)
            elif strategy == ClosingStrategy.BALANCE_RECOVERY:
                return self._select_balance_positions(positions, current_price)
            elif strategy == ClosingStrategy.MARGIN_RELIEF:
                return self._select_margin_relief_positions(positions, account_info)
            elif strategy == ClosingStrategy.RISK_REDUCTION:
                return self._select_risk_positions(positions, current_price)
            elif strategy == ClosingStrategy.EMERGENCY_EXIT:
                return self._select_emergency_positions(positions, account_info)
            else:
                return self._select_optimal_positions(positions, current_price, account_info)
                
        except Exception as e:
            logger.error(f"❌ Error selecting positions to close: {e}")
            return []
    
    def _select_profitable_positions(self, positions: List[Any], current_price: float) -> List[Any]:
        """💰 เลือกตำแหน่งที่มีกำไร - ลดเกณฑ์ให้ปิดได้ง่ายขึ้น"""
        profitable = [pos for pos in positions if getattr(pos, 'profit', 0) > 1]  # ลดจาก 10 เป็น 1
        # Sort by profit descending
        profitable.sort(key=lambda pos: getattr(pos, 'profit', 0), reverse=True)
        return profitable[:8]  # เพิ่มจาก 5 เป็น 8
    
    def _select_balance_positions(self, positions: List[Any], current_price: float) -> List[Any]:
        """⚖️ เลือกตำแหน่งเพื่อสมดุล"""
        buy_positions = [pos for pos in positions if getattr(pos, 'type', 0) == 0]
        sell_positions = [pos for pos in positions if getattr(pos, 'type', 1) == 1]
        
        selected = []
        
        if len(buy_positions) > len(sell_positions):
            # Too many BUYs, select some profitable BUYs to close
            profitable_buys = [pos for pos in buy_positions if getattr(pos, 'profit', 0) > 0]
            profitable_buys.sort(key=lambda pos: getattr(pos, 'profit', 0), reverse=True)
            selected.extend(profitable_buys[:2])
        elif len(sell_positions) > len(buy_positions):
            # Too many SELLs, select some profitable SELLs to close
            profitable_sells = [pos for pos in sell_positions if getattr(pos, 'profit', 0) > 0]
            profitable_sells.sort(key=lambda pos: getattr(pos, 'profit', 0), reverse=True)
            selected.extend(profitable_sells[:2])
        
        return selected
    
    def _create_profit_groups(self, positions: List[Any], current_price: float) -> List[ClosingGroup]:
        """💰 สร้างกลุ่มการปิดเพื่อเก็บกำไร"""
        groups = []
        
        try:
            profitable_positions = [pos for pos in positions if getattr(pos, 'profit', 0) > 1]  # ลดจาก 10 เป็น 1
            
            if profitable_positions:
                # Group by profit level - ลดเกณฑ์ให้ปิดได้ง่ายขึ้น
                high_profit = [pos for pos in profitable_positions if getattr(pos, 'profit', 0) > 20]  # ลดจาก 50 เป็น 20
                medium_profit = [pos for pos in profitable_positions if 2 < getattr(pos, 'profit', 0) <= 20]  # ลดจาก 10 เป็น 2
                
                if high_profit:
                    groups.append(ClosingGroup(
                        group_id="HIGH_PROFIT",
                        positions=high_profit,
                        total_profit=sum(getattr(pos, 'profit', 0) for pos in high_profit),
                        total_volume=sum(getattr(pos, 'volume', 0) for pos in high_profit),
                        closing_reason="High profit taking",
                        priority=10,
                        estimated_execution_time=2.0
                    ))
                
                if medium_profit:
                    groups.append(ClosingGroup(
                        group_id="MEDIUM_PROFIT",
                        positions=medium_profit,
                        total_profit=sum(getattr(pos, 'profit', 0) for pos in medium_profit),
                        total_volume=sum(getattr(pos, 'volume', 0) for pos in medium_profit),
                        closing_reason="Medium profit taking",
                        priority=7,
                        estimated_execution_time=3.0
                    ))
                    
        except Exception as e:
            logger.error(f"❌ Error creating profit groups: {e}")
            
        return groups
    
    def _log_closing_analysis(self, analysis: DynamicClosingAnalysis):
        """📊 แสดง log การวิเคราะห์การปิดแบบสั้นกระชับ"""
        status = "✅ CLOSE" if analysis.should_close else "🚫 HOLD"
        
        # Log แบบบรรทัดเดียว สั้นกระชับ
        logger.info(f"{status} {len(analysis.positions_to_close)}pos | "
                   f"${analysis.expected_profit:.0f} | "
                   f"Conf:{analysis.confidence:.0f}% | "
                   f"{analysis.market_timing.value.upper()} | "
                   f"{analysis.urgency.value.upper()}")
        
        # แสดง alternatives เฉพาะเมื่อไม่ปิด
        if not analysis.should_close and analysis.alternative_strategies:
            alt = analysis.alternative_strategies[0].value if analysis.alternative_strategies else "none"
            logger.info(f"💡 Alt: {alt}")
    
    def _create_safe_closing_analysis(self) -> DynamicClosingAnalysis:
        """🛡️ สร้างการวิเคราะห์ fallback ที่ปลอดภัย"""
        return DynamicClosingAnalysis(
            should_close=False,
            closing_strategy=ClosingStrategy.PORTFOLIO_OPTIMIZATION,
            market_timing=MarketTiming.ACCEPTABLE,
            urgency=ClosingUrgency.WAIT,
            positions_to_close=[],
            expected_profit=0.0,
            risk_reduction=0.0,
            confidence=0.0,
            alternative_strategies=[],
            dynamic_adjustments={},
            closing_reasons=["SYSTEM_ERROR", "SAFE_FALLBACK"]
        )
    
    # Placeholder methods for remaining functionality
    def _calculate_expected_profit(self, positions: List[Any], current_price: float) -> float:
        return sum(getattr(pos, 'profit', 0) for pos in positions)
    
    def _calculate_risk_reduction(self, positions: List[Any], account_info: Dict) -> float:
        return 0.1  # 10% risk reduction placeholder
    
    def _calculate_closing_confidence(self, strategy: ClosingStrategy, timing: MarketTiming, 
                                    urgency: ClosingUrgency, positions: List[Any]) -> float:
        base_confidence = 60.0
        timing_bonus = {MarketTiming.PERFECT: 20, MarketTiming.GOOD: 10, MarketTiming.ACCEPTABLE: 0, 
                       MarketTiming.POOR: -10, MarketTiming.TERRIBLE: -20}.get(timing, 0)
        return min(95.0, max(10.0, base_confidence + timing_bonus))
    
    def _find_alternative_strategies(self, strategy: ClosingStrategy, positions: List[Any], 
                                   account_info: Dict, timing: MarketTiming) -> List[ClosingStrategy]:
        return [ClosingStrategy.PROFIT_TAKING, ClosingStrategy.RISK_REDUCTION]
    
    def _apply_closing_adjustments(self, positions: List[Any], strategy: ClosingStrategy, 
                                 timing: MarketTiming, current_price: float) -> Dict[str, Any]:
        return {'timing_adjustment': timing.value, 'position_count': len(positions)}
    
    def _compile_closing_reasons(self, strategy: ClosingStrategy, timing: MarketTiming,
                               urgency: ClosingUrgency, positions: List[Any], account_info: Dict) -> List[str]:
        return [f"Strategy: {strategy.value}", f"Timing: {timing.value}", f"Urgency: {urgency.value}"]
    
    def _make_final_closing_decision(self, confidence: float, urgency: ClosingUrgency,
                                   expected_profit: float, risk_reduction: float, account_info: Dict) -> bool:
        if urgency == ClosingUrgency.IMMEDIATE:
            return True
        if confidence > 70 and expected_profit > 20:
            return True
        return False
    
    # Additional placeholder methods for position selection
    def _select_margin_relief_positions(self, positions: List[Any], account_info: Dict) -> List[Any]:
        return positions[:3]  # Simple selection
    
    def _select_risk_positions(self, positions: List[Any], current_price: float) -> List[Any]:
        return [pos for pos in positions if getattr(pos, 'profit', 0) < -100][:3]
    
    def _select_emergency_positions(self, positions: List[Any], account_info: Dict) -> List[Any]:
        return positions[:5]  # Emergency - close first 5
    
    def _select_optimal_positions(self, positions: List[Any], current_price: float, account_info: Dict) -> List[Any]:
        return positions[:2]  # Conservative selection
    
    # Implement actual group creation methods
    def _create_balance_groups(self, positions: List[Any], current_price: float) -> List[ClosingGroup]:
        """⚖️ สร้างกลุ่มเพื่อปรับสมดุล"""
        groups = []
        try:
            buy_positions = [pos for pos in positions if getattr(pos, 'type', 0) == 0]
            sell_positions = [pos for pos in positions if getattr(pos, 'type', 1) == 1]
            
            if abs(len(buy_positions) - len(sell_positions)) > 2:
                # เลือกตำแหน่งที่มีกำไรจากฝั่งที่เยอะกว่า
                if len(buy_positions) > len(sell_positions):
                    profitable_buys = [pos for pos in buy_positions if getattr(pos, 'profit', 0) > 0]
                    if profitable_buys:
                        groups.append(ClosingGroup(
                            group_id="BALANCE_BUYS",
                            positions=profitable_buys[:3],
                            total_profit=sum(getattr(pos, 'profit', 0) for pos in profitable_buys[:3]),
                            total_volume=sum(getattr(pos, 'volume', 0) for pos in profitable_buys[:3]),
                            closing_reason="Balance recovery - reduce BUYs",
                            priority=8,
                            estimated_execution_time=2.0
                        ))
                else:
                    profitable_sells = [pos for pos in sell_positions if getattr(pos, 'profit', 0) > 0]
                    if profitable_sells:
                        groups.append(ClosingGroup(
                            group_id="BALANCE_SELLS",
                            positions=profitable_sells[:3],
                            total_profit=sum(getattr(pos, 'profit', 0) for pos in profitable_sells[:3]),
                            total_volume=sum(getattr(pos, 'volume', 0) for pos in profitable_sells[:3]),
                            closing_reason="Balance recovery - reduce SELLs",
                            priority=8,
                            estimated_execution_time=2.0
                        ))
        except Exception as e:
            logger.error(f"❌ Error creating balance groups: {e}")
        return groups
    
    def _create_margin_relief_groups(self, positions: List[Any], current_price: float) -> List[ClosingGroup]:
        """🚨 สร้างกลุ่มเพื่อบรรเทา margin"""
        groups = []
        try:
            # เลือกตำแหน่งที่มีกำไรมากที่สุด
            profitable = [pos for pos in positions if getattr(pos, 'profit', 0) > 0]
            profitable.sort(key=lambda pos: getattr(pos, 'profit', 0), reverse=True)
            
            if profitable:
                groups.append(ClosingGroup(
                    group_id="MARGIN_RELIEF",
                    positions=profitable[:5],  # ปิด 5 ตัวที่กำไรดีที่สุด
                    total_profit=sum(getattr(pos, 'profit', 0) for pos in profitable[:5]),
                    total_volume=sum(getattr(pos, 'volume', 0) for pos in profitable[:5]),
                    closing_reason="Margin relief - urgent closing",
                    priority=10,
                    estimated_execution_time=1.0
                ))
        except Exception as e:
            logger.error(f"❌ Error creating margin relief groups: {e}")
        return groups
    
    def _create_risk_reduction_groups(self, positions: List[Any], current_price: float) -> List[ClosingGroup]:
        """⚖️ สร้างกลุ่มเพื่อลดความเสี่ยง"""
        groups = []
        try:
            # เลือกตำแหน่งที่มีกำไรเล็กน้อย
            small_profit = [pos for pos in positions if 0 < getattr(pos, 'profit', 0) < 20]
            
            if small_profit:
                groups.append(ClosingGroup(
                    group_id="RISK_REDUCTION",
                    positions=small_profit[:4],
                    total_profit=sum(getattr(pos, 'profit', 0) for pos in small_profit[:4]),
                    total_volume=sum(getattr(pos, 'volume', 0) for pos in small_profit[:4]),
                    closing_reason="Risk reduction - small profits",
                    priority=6,
                    estimated_execution_time=2.5
                ))
        except Exception as e:
            logger.error(f"❌ Error creating risk reduction groups: {e}")
        return groups
    
    def _create_optimization_groups(self, positions: List[Any], current_price: float) -> List[ClosingGroup]:
        """📊 สร้างกลุ่มเพื่อเพิ่มประสิทธิภาพ"""
        groups = []
        try:
            # เลือกตำแหน่งที่มีกำไรปานกลาง
            medium_profit = [pos for pos in positions if 5 < getattr(pos, 'profit', 0) < 50]
            
            if medium_profit:
                groups.append(ClosingGroup(
                    group_id="OPTIMIZATION",
                    positions=medium_profit[:3],
                    total_profit=sum(getattr(pos, 'profit', 0) for pos in medium_profit[:3]),
                    total_volume=sum(getattr(pos, 'volume', 0) for pos in medium_profit[:3]),
                    closing_reason="Portfolio optimization",
                    priority=5,
                    estimated_execution_time=3.0
                ))
        except Exception as e:
            logger.error(f"❌ Error creating optimization groups: {e}")
        return groups
    
    def _create_emergency_groups(self, positions: List[Any], current_price: float) -> List[ClosingGroup]:
        """🚨 สร้างกลุ่มฉุกเฉิน"""
        groups = []
        try:
            # เลือกตำแหน่งใดๆ ที่มีกำไร
            any_profit = [pos for pos in positions if getattr(pos, 'profit', 0) > -5]  # รวมขาดทุนเล็กน้อย
            
            if any_profit:
                groups.append(ClosingGroup(
                    group_id="EMERGENCY",
                    positions=any_profit[:6],
                    total_profit=sum(getattr(pos, 'profit', 0) for pos in any_profit[:6]),
                    total_volume=sum(getattr(pos, 'volume', 0) for pos in any_profit[:6]),
                    closing_reason="Emergency exit - any available",
                    priority=9,
                    estimated_execution_time=1.5
                ))
        except Exception as e:
            logger.error(f"❌ Error creating emergency groups: {e}")
        return groups
    
    def _create_default_groups(self, positions: List[Any], current_price: float) -> List[ClosingGroup]:
        """🔄 สร้างกลุ่มเริ่มต้น"""
        groups = []
        try:
            # เลือกตำแหน่งที่มีกำไรเล็กน้อย
            any_positive = [pos for pos in positions if getattr(pos, 'profit', 0) > 0]
            
            if any_positive:
                groups.append(ClosingGroup(
                    group_id="DEFAULT",
                    positions=any_positive[:2],
                    total_profit=sum(getattr(pos, 'profit', 0) for pos in any_positive[:2]),
                    total_volume=sum(getattr(pos, 'volume', 0) for pos in any_positive[:2]),
                    closing_reason="Default closing",
                    priority=4,
                    estimated_execution_time=2.0
                ))
        except Exception as e:
            logger.error(f"❌ Error creating default groups: {e}")
        return groups

def create_dynamic_adaptive_closer(mt5_connection=None, symbol: str = "XAUUSD") -> DynamicAdaptiveCloser:
    """สร้าง Dynamic Adaptive Closer"""
    return DynamicAdaptiveCloser(mt5_connection, symbol)

if __name__ == "__main__":
    # Test the system
    closer = create_dynamic_adaptive_closer()
    logger.info("💰 Dynamic Adaptive Closer ready for testing")
