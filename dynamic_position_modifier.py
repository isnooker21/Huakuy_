# -*- coding: utf-8 -*-
"""
Dynamic Position Modifier System
ระบบแก้ไขตำแหน่งแบบ Dynamic ที่จัดการได้ทุกสถานการณ์
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import math

logger = logging.getLogger(__name__)

class PositionProblem(Enum):
    """ประเภทปัญหาของตำแหน่ง"""
    HEAVY_LOSS = "heavy_loss"           # ขาดทุนหนัก
    DISTANCE_TOO_FAR = "distance_far"   # ห่างจากราคาปัจจุบันมาก
    TIME_TOO_LONG = "time_too_long"     # ถือนานเกินไป
    MARGIN_PRESSURE = "margin_pressure" # กดดัน margin
    IMBALANCE_CAUSE = "imbalance_cause" # ทำให้ portfolio ไม่สมดุล
    CORRELATION_BAD = "correlation_bad" # correlation ไม่ดี
    VOLATILITY_VICTIM = "volatility_victim" # ได้รับผลกระทบจากความผันผวน

class ModifierAction(Enum):
    """การดำเนินการแก้ไข"""
    ADD_SUPPORT = "add_support"         # เพิ่มตำแหน่งช่วยเหลือ
    ADD_COUNTER = "add_counter"         # เพิ่มตำแหน่งตรงข้าม
    PARTIAL_CLOSE = "partial_close"     # ปิดบางส่วน
    HEDGE_PROTECT = "hedge_protect"     # ป้องกันด้วย hedge
    AVERAGE_DOWN = "average_down"       # เฉลี่ยลง
    AVERAGE_UP = "average_up"          # เฉลี่ยขึ้น
    CONVERT_HEDGE = "convert_hedge"     # แปลงเป็น hedge
    WAIT_IMPROVE = "wait_improve"       # รอให้ดีขึ้น
    EMERGENCY_CLOSE = "emergency_close" # ปิดฉุกเฉิน

class ModifierPriority(Enum):
    """ความสำคัญของการแก้ไข"""
    CRITICAL = "critical"     # วิกฤต - ต้องทำทันที
    HIGH = "high"            # สูง - ควรทำเร็ว
    MEDIUM = "medium"        # ปานกลาง - ทำเมื่อมีโอกาส
    LOW = "low"              # ต่ำ - ทำเมื่อสะดวก
    MONITOR = "monitor"      # เฝาดู - ไม่ต้องทำ

@dataclass
class PositionModification:
    """ข้อมูลการแก้ไขตำแหน่ง"""
    position_ticket: int
    problems: List[PositionProblem]
    recommended_action: ModifierAction
    priority: ModifierPriority
    expected_improvement: float
    risk_assessment: float
    suggested_lot_size: float
    suggested_price: Optional[float]
    time_frame: str
    success_probability: float
    alternative_actions: List[ModifierAction]
    dynamic_parameters: Dict[str, Any]

@dataclass
class PortfolioModificationPlan:
    """แผนการแก้ไข Portfolio"""
    individual_modifications: List[PositionModification]
    group_modifications: List[Dict[str, Any]]
    emergency_actions: List[str]
    expected_portfolio_improvement: float
    estimated_cost: float
    estimated_time: str
    success_probability: float
    risk_level: float

class DynamicPositionModifier:
    """ระบบแก้ไขตำแหน่งแบบ Dynamic"""
    
    def __init__(self, mt5_connection=None, symbol: str = "XAUUSD"):
        self.mt5_connection = mt5_connection
        self.symbol = symbol
        
        # 🎯 Dynamic Thresholds - ปรับตัวตามสถานการณ์
        self.heavy_loss_threshold = -200.0  # Dynamic based on balance
        self.distance_threshold = 100.0     # Dynamic based on volatility
        self.time_threshold_hours = 24      # Dynamic based on market condition
        self.margin_pressure_threshold = 200 # Dynamic based on account size
        
        # 📊 Modifier Parameters
        self.max_support_positions = 3      # Dynamic limit
        self.max_hedge_ratio = 0.8         # Dynamic ratio
        self.emergency_loss_limit = -500.0  # Dynamic limit
        
        # 🧠 Learning Parameters
        self.success_history = {}
        self.failure_history = {}
        self.adaptation_rate = 0.1
        
        logger.info("🔧 Dynamic Position Modifier initialized")
    
    def analyze_portfolio_modifications(self, positions: List[Any], account_info: Dict,
                                      current_price: float) -> PortfolioModificationPlan:
        """
        🎯 วิเคราะห์การแก้ไข Portfolio แบบ Dynamic
        """
        try:
            logger.info(f"🔍 DYNAMIC PORTFOLIO MODIFICATION ANALYSIS: {len(positions)} positions")
            
            # 1. 🔍 Individual Position Analysis
            individual_modifications = []
            for position in positions:
                modification = self._analyze_individual_position(position, current_price, account_info)
                if modification:
                    individual_modifications.append(modification)
            
            # 2. 🤝 Group Modification Analysis
            group_modifications = self._analyze_group_modifications(positions, current_price, account_info)
            
            # 3. 🚨 Emergency Action Analysis
            emergency_actions = self._analyze_emergency_actions(positions, account_info)
            
            # 4. 📊 Portfolio Impact Calculation
            portfolio_improvement = self._calculate_portfolio_improvement(
                individual_modifications, group_modifications, positions, account_info
            )
            
            # 5. 💰 Cost Estimation
            estimated_cost = self._estimate_modification_cost(
                individual_modifications, group_modifications, current_price
            )
            
            # 6. ⏰ Time Estimation
            estimated_time = self._estimate_completion_time(
                individual_modifications, group_modifications
            )
            
            # 7. 🎯 Success Probability
            success_probability = self._calculate_success_probability(
                individual_modifications, group_modifications, positions
            )
            
            # 8. ⚖️ Risk Assessment
            risk_level = self._assess_modification_risk(
                individual_modifications, group_modifications, account_info
            )
            
            plan = PortfolioModificationPlan(
                individual_modifications=individual_modifications,
                group_modifications=group_modifications,
                emergency_actions=emergency_actions,
                expected_portfolio_improvement=portfolio_improvement,
                estimated_cost=estimated_cost,
                estimated_time=estimated_time,
                success_probability=success_probability,
                risk_level=risk_level
            )
            
            self._log_modification_plan(plan)
            return plan
            
        except Exception as e:
            logger.error(f"❌ Error analyzing portfolio modifications: {e}")
            return self._create_safe_modification_plan()
    
    def _analyze_individual_position(self, position: Any, current_price: float,
                                   account_info: Dict) -> Optional[PositionModification]:
        """🔍 วิเคราะห์การแก้ไขตำแหน่งเดี่ยว"""
        try:
            ticket = getattr(position, 'ticket', 0)
            position_type = getattr(position, 'type', 0)
            open_price = getattr(position, 'price_open', current_price)
            profit = getattr(position, 'profit', 0)
            volume = getattr(position, 'volume', 0.01)
            open_time = getattr(position, 'time', datetime.now().timestamp())
            
            # 1. 🔍 Problem Detection
            problems = self._detect_position_problems(position, current_price, account_info)
            
            if not problems:
                return None  # No problems found
            
            # 2. 🎯 Action Recommendation
            recommended_action = self._recommend_modifier_action(position, problems, current_price, account_info)
            
            # 3. 📊 Priority Assessment
            priority = self._assess_modifier_priority(problems, profit, account_info)
            
            # 4. 📈 Improvement Estimation
            expected_improvement = self._estimate_position_improvement(
                position, recommended_action, current_price, account_info
            )
            
            # 5. ⚖️ Risk Assessment
            risk_assessment = self._assess_modification_risk_individual(
                position, recommended_action, current_price
            )
            
            # 6. 💰 Lot Size Calculation
            suggested_lot_size = self._calculate_modifier_lot_size(
                position, recommended_action, current_price, account_info
            )
            
            # 7. 💰 Price Calculation
            suggested_price = self._calculate_modifier_price(
                position, recommended_action, current_price
            )
            
            # 8. 🎯 Success Probability
            success_probability = self._calculate_individual_success_probability(
                position, recommended_action, problems
            )
            
            # 9. 🔄 Alternative Actions
            alternative_actions = self._find_alternative_actions(
                position, recommended_action, problems
            )
            
            # 10. 🔧 Dynamic Parameters
            dynamic_parameters = self._calculate_dynamic_parameters(
                position, recommended_action, current_price, account_info
            )
            
            return PositionModification(
                position_ticket=ticket,
                problems=problems,
                recommended_action=recommended_action,
                priority=priority,
                expected_improvement=expected_improvement,
                risk_assessment=risk_assessment,
                suggested_lot_size=suggested_lot_size,
                suggested_price=suggested_price,
                time_frame=self._estimate_action_timeframe(recommended_action),
                success_probability=success_probability,
                alternative_actions=alternative_actions,
                dynamic_parameters=dynamic_parameters
            )
            
        except Exception as e:
            logger.error(f"❌ Error analyzing individual position: {e}")
            return None
    
    def _detect_position_problems(self, position: Any, current_price: float,
                                account_info: Dict) -> List[PositionProblem]:
        """🔍 ตรวจหาปัญหาของตำแหน่ง"""
        problems = []
        
        try:
            profit = getattr(position, 'profit', 0)
            open_price = getattr(position, 'price_open', current_price)
            position_type = getattr(position, 'type', 0)
            open_time = getattr(position, 'time', datetime.now().timestamp())
            balance = account_info.get('balance', 10000)
            
            # 1. 💸 Smart Loss Detection - ปรับตาม Lot Size
            lot_size = getattr(position, 'volume', 0.01)
            
            # Dynamic loss threshold based on lot size and balance
            base_loss_per_lot = -50.0  # -$50 per 0.01 lot
            lot_adjusted_loss = base_loss_per_lot * (lot_size / 0.01)
            balance_adjusted_loss = balance * -0.015  # 1.5% of balance
            
            # Use the more restrictive threshold
            smart_loss_threshold = max(lot_adjusted_loss, balance_adjusted_loss, self.heavy_loss_threshold)
            
            if profit < smart_loss_threshold:
                problems.append(PositionProblem.HEAVY_LOSS)
                logger.debug(f"💸 Smart Loss: ${profit:.2f} < ${smart_loss_threshold:.2f} (Lot:{lot_size}, Balance%:{balance_adjusted_loss:.2f})")
            
            # 2. Distance Detection
            distance = abs(current_price - open_price)
            # Dynamic distance threshold based on current volatility
            volatility_factor = self._calculate_current_volatility(current_price)
            dynamic_distance_threshold = self.distance_threshold * (1 + volatility_factor)
            
            if distance > dynamic_distance_threshold:
                problems.append(PositionProblem.DISTANCE_TOO_FAR)
            
            # 3. ⏰ Smart Time Detection - ปรับตามความผันผวนและระยะห่าง
            current_time = datetime.now().timestamp()
            hours_held = (current_time - open_time) / 3600
            
            # Calculate how much price moved during holding period
            price_movement = abs(current_price - open_price)
            volatility_factor = self._calculate_current_volatility(current_price)
            
            # Dynamic time threshold based on price movement and volatility
            # ถ้าราคาเคลื่อนไหวมาก = ตลาดเร็ว = ลดเวลาที่ยอมให้ถือ
            # ถ้าราคาเคลื่อนไหวน้อย = ตลาดเงียบ = เพิ่มเวลาที่ยอมให้ถือ
            base_time = self.time_threshold_hours
            
            if price_movement > 200:  # ราคาเคลื่อนไหวมาก (>200 points)
                smart_time_threshold = base_time * 0.5  # ลดเวลาลง 50%
                reason = "high_volatility"
            elif price_movement > 100:  # ราคาเคลื่อนไหวปานกลาง
                smart_time_threshold = base_time * 0.75  # ลดเวลาลง 25%
                reason = "medium_volatility"
            elif price_movement < 30:  # ราคาเคลื่อนไหวน้อย (<30 points)
                smart_time_threshold = base_time * 2.0  # เพิ่มเวลาขึ้น 100%
                reason = "low_volatility"
            else:
                smart_time_threshold = base_time
                reason = "normal_volatility"
            
            if hours_held > smart_time_threshold:
                problems.append(PositionProblem.TIME_TOO_LONG)
                logger.debug(f"⏰ Smart Time: {hours_held:.1f}h > {smart_time_threshold:.1f}h (Movement:{price_movement:.1f}, {reason})")
            
            # 4. Margin Pressure Detection
            margin_level = account_info.get('margin_level', 1000)
            if margin_level < self.margin_pressure_threshold:
                problems.append(PositionProblem.MARGIN_PRESSURE)
            
            # 5. Volatility Victim Detection
            if self._is_volatility_victim(position, current_price):
                problems.append(PositionProblem.VOLATILITY_VICTIM)
                
        except Exception as e:
            logger.error(f"❌ Error detecting position problems: {e}")
            
        return problems
    
    def _recommend_modifier_action(self, position: Any, problems: List[PositionProblem],
                                 current_price: float, account_info: Dict) -> ModifierAction:
        """🎯 แนะนำการดำเนินการแก้ไข"""
        try:
            profit = getattr(position, 'profit', 0)
            balance = account_info.get('balance', 10000)
            margin_level = account_info.get('margin_level', 1000)
            
            # Critical situations
            if profit < balance * -0.05:  # 5% of balance loss
                return ModifierAction.EMERGENCY_CLOSE
            
            if margin_level < 120:
                return ModifierAction.PARTIAL_CLOSE
            
            # Problem-based recommendations
            if PositionProblem.HEAVY_LOSS in problems:
                if profit < balance * -0.03:
                    return ModifierAction.ADD_SUPPORT
                else:
                    return ModifierAction.AVERAGE_DOWN
            
            if PositionProblem.DISTANCE_TOO_FAR in problems:
                return ModifierAction.ADD_COUNTER
            
            if PositionProblem.TIME_TOO_LONG in problems:
                if profit < 0:
                    return ModifierAction.ADD_SUPPORT
                else:
                    return ModifierAction.PARTIAL_CLOSE
            
            if PositionProblem.MARGIN_PRESSURE in problems:
                return ModifierAction.PARTIAL_CLOSE
            
            if PositionProblem.VOLATILITY_VICTIM in problems:
                return ModifierAction.HEDGE_PROTECT
            
            # Default action
            return ModifierAction.WAIT_IMPROVE
            
        except Exception as e:
            logger.error(f"❌ Error recommending modifier action: {e}")
            return ModifierAction.WAIT_IMPROVE
    
    def _assess_modifier_priority(self, problems: List[PositionProblem], profit: float,
                                account_info: Dict) -> ModifierPriority:
        """📊 ประเมินความสำคัญของการแก้ไข"""
        try:
            balance = account_info.get('balance', 10000)
            margin_level = account_info.get('margin_level', 1000)
            
            # Critical priorities
            if profit < balance * -0.05 or margin_level < 120:
                return ModifierPriority.CRITICAL
            
            # High priorities
            if (PositionProblem.HEAVY_LOSS in problems or 
                PositionProblem.MARGIN_PRESSURE in problems):
                return ModifierPriority.HIGH
            
            # Medium priorities
            if (PositionProblem.DISTANCE_TOO_FAR in problems or 
                PositionProblem.TIME_TOO_LONG in problems):
                return ModifierPriority.MEDIUM
            
            # Low priorities
            if PositionProblem.VOLATILITY_VICTIM in problems:
                return ModifierPriority.LOW
            
            return ModifierPriority.MONITOR
            
        except Exception as e:
            logger.error(f"❌ Error assessing modifier priority: {e}")
            return ModifierPriority.MONITOR
    
    def _analyze_group_modifications(self, positions: List[Any], current_price: float,
                                   account_info: Dict) -> List[Dict[str, Any]]:
        """🤝 วิเคราะห์การแก้ไขแบบกลุ่ม"""
        group_modifications = []
        
        try:
            # 1. Balance Correction Groups
            buy_positions = [p for p in positions if getattr(p, 'type', 0) == 0]
            sell_positions = [p for p in positions if getattr(p, 'type', 1) == 1]
            
            if abs(len(buy_positions) - len(sell_positions)) > 5:
                group_modifications.append({
                    'type': 'BALANCE_CORRECTION',
                    'description': f'Balance {len(buy_positions)}B vs {len(sell_positions)}S',
                    'action': 'ADD_COUNTER_POSITIONS',
                    'priority': 'HIGH',
                    'estimated_positions': abs(len(buy_positions) - len(sell_positions)) // 2
                })
            
            # 2. Heavy Loss Recovery Groups
            heavy_loss_positions = [p for p in positions if getattr(p, 'profit', 0) < -200]
            if len(heavy_loss_positions) > 3:
                group_modifications.append({
                    'type': 'HEAVY_LOSS_RECOVERY',
                    'description': f'{len(heavy_loss_positions)} positions with heavy losses',
                    'action': 'COORDINATED_SUPPORT',
                    'priority': 'CRITICAL',
                    'estimated_support_lot': len(heavy_loss_positions) * 0.01
                })
            
            # 3. Distance Clustering
            far_positions = []
            for pos in positions:
                distance = abs(current_price - getattr(pos, 'price_open', current_price))
                if distance > 200:  # 200 points away
                    far_positions.append(pos)
            
            if len(far_positions) > 2:
                group_modifications.append({
                    'type': 'DISTANCE_CLUSTERING',
                    'description': f'{len(far_positions)} positions too far from current price',
                    'action': 'CLUSTER_SUPPORT',
                    'priority': 'MEDIUM',
                    'estimated_bridge_positions': len(far_positions)
                })
                
        except Exception as e:
            logger.error(f"❌ Error analyzing group modifications: {e}")
            
        return group_modifications
    
    def _analyze_emergency_actions(self, positions: List[Any], account_info: Dict) -> List[str]:
        """🚨 วิเคราะห์การดำเนินการฉุกเฉิน"""
        emergency_actions = []
        
        try:
            balance = account_info.get('balance', 10000)
            equity = account_info.get('equity', balance)
            margin_level = account_info.get('margin_level', 1000)
            
            # Margin Call Risk - แก้ไขการตรวจสอบเมื่อไม่มี positions
            if len(positions) > 0 and margin_level > 0 and margin_level < 100:
                emergency_actions.append("MARGIN_CALL_PREVENTION")
            
            # Equity Protection
            if equity < balance * 0.8:
                emergency_actions.append("EQUITY_PROTECTION")
            
            # Heavy Loss Positions
            total_loss = sum(getattr(pos, 'profit', 0) for pos in positions if getattr(pos, 'profit', 0) < 0)
            if total_loss < balance * -0.1:  # 10% total loss
                emergency_actions.append("LOSS_LIMITATION")
            
            # Position Count Limit
            if len(positions) > 25:
                emergency_actions.append("POSITION_COUNT_CONTROL")
                
        except Exception as e:
            logger.error(f"❌ Error analyzing emergency actions: {e}")
            
        return emergency_actions
    
    def _calculate_current_volatility(self, current_price: float) -> float:
        """📊 คำนวณความผันผวนปัจจุบัน"""
        # Simplified volatility calculation
        # In real implementation, this would use historical price data
        return 0.5  # Default moderate volatility
    
    def _assess_market_speed(self) -> float:
        """⚡ ประเมินความเร็วของตลาด"""
        # Simplified market speed assessment
        # In real implementation, this would analyze recent price movements
        return 0.3  # Default moderate speed
    
    def _is_volatility_victim(self, position: Any, current_price: float) -> bool:
        """📊 ตรวจสอบว่าได้รับผลกระทบจากความผันผวนหรือไม่"""
        try:
            profit = getattr(position, 'profit', 0)
            open_price = getattr(position, 'price_open', current_price)
            
            # Simple check: if position is losing and price moved significantly
            distance = abs(current_price - open_price)
            return profit < 0 and distance > 100
            
        except Exception as e:
            logger.error(f"❌ Error checking volatility victim: {e}")
            return False
    
    def _estimate_position_improvement(self, position: Any, action: ModifierAction,
                                     current_price: float, account_info: Dict) -> float:
        """📈 ประเมินการปรับปรุงตำแหน่ง"""
        try:
            current_profit = getattr(position, 'profit', 0)
            
            # Improvement estimates based on action type
            improvement_factors = {
                ModifierAction.ADD_SUPPORT: 0.6,
                ModifierAction.ADD_COUNTER: 0.4,
                ModifierAction.PARTIAL_CLOSE: 0.3,
                ModifierAction.HEDGE_PROTECT: 0.5,
                ModifierAction.AVERAGE_DOWN: 0.7,
                ModifierAction.AVERAGE_UP: 0.7,
                ModifierAction.CONVERT_HEDGE: 0.4,
                ModifierAction.WAIT_IMPROVE: 0.1,
                ModifierAction.EMERGENCY_CLOSE: 0.0
            }
            
            factor = improvement_factors.get(action, 0.2)
            
            # Calculate expected improvement
            if current_profit < 0:
                expected_improvement = abs(current_profit) * factor
            else:
                expected_improvement = current_profit * factor * 0.5
                
            return expected_improvement
            
        except Exception as e:
            logger.error(f"❌ Error estimating position improvement: {e}")
            return 0.0
    
    def _log_modification_plan(self, plan: PortfolioModificationPlan):
        """📊 แสดง log แผนการแก้ไขแบบสั้นกระชับ"""
        if not plan.individual_modifications and not plan.group_modifications:
            logger.info("🔧 No modifications needed")
            return
        
        # Log แบบบรรทัดเดียว สั้นกระชับ
        logger.info(f"🔧 MODIFY: {len(plan.individual_modifications)}pos | "
                   f"Profit:+${plan.expected_portfolio_improvement:.0f} | "
                   f"Success:{plan.success_probability:.0%}")
        
        # แสดง high priority เฉพาะที่สำคัญ
        critical_mods = [mod for mod in plan.individual_modifications 
                        if mod.priority == ModifierPriority.CRITICAL]
        
        if critical_mods:
            for mod in critical_mods[:2]:  # แสดงแค่ 2 อันแรก
                logger.warning(f"🚨 CRITICAL: Ticket {mod.position_ticket} - {mod.recommended_action.value}")
        
        # แสดง emergency actions เฉพาะเมื่อมี
        if plan.emergency_actions:
            logger.warning(f"🚨 EMERGENCY: {', '.join(plan.emergency_actions[:2])}")
    
    def _create_safe_modification_plan(self) -> PortfolioModificationPlan:
        """🛡️ สร้างแผนการแก้ไข fallback ที่ปลอดภัย"""
        return PortfolioModificationPlan(
            individual_modifications=[],
            group_modifications=[],
            emergency_actions=["SYSTEM_ERROR"],
            expected_portfolio_improvement=0.0,
            estimated_cost=0.0,
            estimated_time="unknown",
            success_probability=0.0,
            risk_level=0.0
        )
    
    # Additional helper methods would be implemented here...
    def _assess_modification_risk_individual(self, position: Any, action: ModifierAction, current_price: float) -> float:
        return 0.3  # Placeholder
    
    def _calculate_modifier_lot_size(self, position: Any, action: ModifierAction, current_price: float, account_info: Dict) -> float:
        return 0.01  # Placeholder
    
    def _calculate_modifier_price(self, position: Any, action: ModifierAction, current_price: float) -> Optional[float]:
        return None  # Placeholder
    
    def _calculate_individual_success_probability(self, position: Any, action: ModifierAction, problems: List[PositionProblem]) -> float:
        return 0.7  # Placeholder
    
    def _find_alternative_actions(self, position: Any, action: ModifierAction, problems: List[PositionProblem]) -> List[ModifierAction]:
        return [ModifierAction.WAIT_IMPROVE]  # Placeholder
    
    def _calculate_dynamic_parameters(self, position: Any, action: ModifierAction, current_price: float, account_info: Dict) -> Dict[str, Any]:
        return {}  # Placeholder
    
    def _estimate_action_timeframe(self, action: ModifierAction) -> str:
        return "immediate"  # Placeholder
    
    def _calculate_portfolio_improvement(self, individual: List, group: List, positions: List, account_info: Dict) -> float:
        return 100.0  # Placeholder
    
    def _estimate_modification_cost(self, individual: List, group: List, current_price: float) -> float:
        return 50.0  # Placeholder
    
    def _estimate_completion_time(self, individual: List, group: List) -> str:
        return "5-10 minutes"  # Placeholder
    
    def _calculate_success_probability(self, individual: List, group: List, positions: List) -> float:
        return 0.75  # Placeholder
    
    def _assess_modification_risk(self, individual: List, group: List, account_info: Dict) -> float:
        return 0.2  # Placeholder

def create_dynamic_position_modifier(mt5_connection=None, symbol: str = "XAUUSD") -> DynamicPositionModifier:
    """สร้าง Dynamic Position Modifier"""
    return DynamicPositionModifier(mt5_connection, symbol)

if __name__ == "__main__":
    # Test the system
    modifier = create_dynamic_position_modifier()
    logger.info("🔧 Dynamic Position Modifier ready for testing")
