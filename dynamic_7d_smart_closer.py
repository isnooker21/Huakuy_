"""
🚀 Dynamic 7D Smart Closing System
ระบบปิดไม้อัจฉริยะที่ใช้ 7D Analysis และ Dynamic Methods

Features:
- Zero Loss Policy (ไม่ปิดขาดทุนเลย)
- Dynamic Method Selection (เลือกวิธีตามสถานการณ์)
- 7D Intelligence Integration (ใช้ 7D Score เลือกไม้)
- Portfolio Health Optimization (เน้นสุขภาพพอร์ต)
- Edge-Based Clearing (ปิดจากขอบบน-ล่าง)
- Multi-Size Groups (2-25 ไม้)
"""

import logging
import math
import random
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import time

logger = logging.getLogger(__name__)

@dataclass
class PortfolioHealth:
    """Portfolio Health Analysis"""
    balance: float
    equity: float
    margin: float
    free_margin: float
    margin_level: float
    total_pnl: float
    buy_count: int
    sell_count: int
    position_count: int
    buy_sell_ratio: float
    imbalance_percentage: float

@dataclass
class ClosingResult:
    """Closing Decision Result"""
    should_close: bool
    positions_to_close: List[Any]
    method: str
    net_pnl: float
    expected_pnl: float
    position_count: int
    buy_count: int
    sell_count: int
    portfolio_improvement: Dict[str, float]
    confidence_score: float
    reason: str

class Dynamic7DSmartCloser:
    """🚀 Dynamic 7D Smart Closing System"""
    
    def __init__(self, intelligent_manager=None, purpose_tracker=None, 
                 market_analyzer=None, price_action_analyzer=None):
        self.intelligent_manager = intelligent_manager
        self.purpose_tracker = purpose_tracker
        self.market_analyzer = market_analyzer
        self.price_action_analyzer = price_action_analyzer
        
        # 🧠 INTELLIGENT Parameters (ไม่ใช้เกณฑ์คงที่ - ให้ระบบตัดสินใจเอง)
        self.base_safety_buffer = 0.0  # ไม่มีเกณฑ์คงที่ - ให้ระบบตัดสินใจเอง
        self.base_max_group_size = 50  # เพิ่มสูงสุดให้ระบบเลือกได้มากขึ้น
        self.min_group_size = 1        # ลดต่ำสุดให้ระบบยืดหยุ่นมากขึ้น
        
        # 🎯 SMART CLOSING STRATEGY: ปิดเฉพาะไม้กำไร + ไม้เก่า (ไม่ปิดขาดทุนเลย)
        self.smart_closing_enabled = True
        self.min_net_profit = 0.1      # กำไรสุทธิขั้นต่ำ $0.1
        self.max_acceptable_loss = 0.0  # ไม่ยอมรับขาดทุนเลย = $0
        self.old_position_hours = 24    # ไม้เก่า = ถือเกิน 24 ชั่วโมง
        self.far_loss_threshold = 0.0   # ไม่ปิดไม้ขาดทุนเลย = $0
        
        # Dynamic thresholds
        self.emergency_margin_threshold = 150.0  # Margin Level < 150%
        self.critical_margin_threshold = 120.0   # Margin Level < 120%
        self.imbalance_threshold = 70.0          # Imbalance > 70%
        
        # 🧠 Purpose-Aware Configuration - ปรับให้เน้นปิด Problem positions
        self.purpose_priority_weights = {
            'RECOVERY_HELPER': 0.6,      # ลดน้ำหนักมากขึ้น - ไม่ปิดง่าย
            'PROBLEM_POSITION': 2.0,     # เพิ่มน้ำหนักมาก - ต้องปิดด่วน
            'BALANCE_KEEPER': 0.8,       # ลดลง - ให้ทางปิด Problem
            'PROFIT_TAKER': 1.5,         # เพิ่มน้ำหนัก - ปิดได้
            'TREND_FOLLOWER': 0.5,       # ลดน้ำหนักมาก - เก็บไว้
            'HEDGE_POSITION': 1.0        # ปกติ
        }
        
        # 🎯 Distance-based Priority (เพิ่มใหม่)
        self.distance_priority_multiplier = {
            'near': 0.8,      # ใกล้ราคาปัจจุบัน - ลดความสำคัญ
            'medium': 1.0,    # ระยะปานกลาง - ปกติ
            'far': 1.5,       # ไกล - เพิ่มความสำคัญ
            'very_far': 2.0   # ไกลมาก - เพิ่มความสำคัญมาก
        }
        
        logger.info("🚀 Dynamic 7D Smart Closer initialized - Purpose-Aware Mode")
        logger.info(f"   🧠 Purpose Tracker: {'✅' if purpose_tracker else '❌'}")
        logger.info(f"   📊 Market Analyzer: {'✅' if market_analyzer else '❌'}")
    
    def find_optimal_closing(self, positions: List[Any], account_info: Dict, 
                           market_conditions: Optional[Dict] = None) -> Optional[ClosingResult]:
        """
        🎯 หาการปิดไม้ที่ดีที่สุด
        """
        try:
            if len(positions) < 2:
                logger.info("⏸️ Need at least 2 positions for closing")
                return None
            
            logger.info(f"🚀 DYNAMIC 7D ANALYSIS: {len(positions)} positions")
            
            # 1. 📊 Portfolio Health Analysis
            portfolio_health = self._analyze_portfolio_health(positions, account_info)
            logger.info(f"💊 Portfolio Health: Margin {portfolio_health.margin_level:.1f}%, "
                       f"Imbalance {portfolio_health.imbalance_percentage:.1f}%")
            
            # 2. 🧠 Purpose Analysis (if available)
            position_purposes = {}
            current_price = self._get_current_price()
            
            if self.purpose_tracker:
                try:
                    for position in positions:
                        purpose_analysis = self.purpose_tracker.analyze_position_purpose(
                            position, positions, account_info, current_price
                        )
                        position_ticket = str(getattr(position, 'ticket', id(position)))
                        position_purposes[position_ticket] = purpose_analysis
                    
                    logger.info(f"🧠 Purpose Analysis completed for {len(position_purposes)} positions")
                    purpose_summary = self.purpose_tracker.get_purpose_summary()
                    logger.info(f"📊 Purpose Summary: {purpose_summary}")
                    
                    # 🔍 Debug: แสดงรายละเอียด Problem positions
                    problem_positions = [ticket for ticket, purpose in position_purposes.items() 
                                       if purpose.purpose.value == 'PROBLEM_POSITION']
                    if problem_positions:
                        logger.info(f"🚨 Found {len(problem_positions)} PROBLEM_POSITION(s):")
                        for ticket in problem_positions:
                            purpose = position_purposes[ticket]
                            logger.info(f"   {ticket}: {purpose.sub_purpose}")
                    else:
                        logger.info("🔍 No PROBLEM_POSITION detected - investigating why...")
                except Exception as e:
                    logger.warning(f"⚠️ Purpose Analysis failed: {e}")
            
            # 3. 🧠 7D Analysis (if available)
            position_scores = None
            if self.intelligent_manager:
                try:
                    margin_health = self.intelligent_manager._analyze_margin_health(account_info)
                    position_scores = self.intelligent_manager._score_all_positions(positions, account_info, margin_health)
                    logger.info(f"🧠 7D Scores calculated for {len(position_scores)} positions")
                except Exception as e:
                    logger.warning(f"⚠️ 7D Analysis failed: {e}, using fallback")
            
            # 4. 🔄 Calculate Dynamic Parameters
            dynamic_params = self._calculate_dynamic_parameters(portfolio_health, market_conditions)
            logger.info(f"🔄 Dynamic Params: Max Size {dynamic_params['max_size']}, "
                       f"Safety Buffer ${dynamic_params['safety_buffer']:.1f}")
            
            # 5. 🎯 Dynamic Method Selection
            selected_methods = self._select_dynamic_methods(portfolio_health, market_conditions, dynamic_params)
            logger.info(f"🎯 Selected {len(selected_methods)} dynamic methods")
            
            # 6. 🔄 Try methods by priority
            best_result = None
            best_score = -999999
            
            for method_name, min_size, max_size, priority in selected_methods:
                # ใช้ Dynamic Max Size
                dynamic_max_size = min(max_size, dynamic_params['max_size'])
                logger.debug(f"🔍 Trying {method_name} (sizes {min_size}-{max_size}, priority {priority:.1f})")
                
                for size in range(min_size, min(dynamic_max_size + 1, len(positions) + 1)):
                    # ใช้ Purpose-Aware 7D หรือ 7D หรือ fallback
                    if position_purposes and position_scores:
                        result = self._try_purpose_aware_7d_method(
                            method_name, position_scores, position_purposes, size, portfolio_health
                        )
                    elif position_scores:
                        result = self._try_7d_method(method_name, position_scores, size, portfolio_health)
                    else:
                        result = self._try_fallback_method(method_name, positions, size, portfolio_health)
                    
                    if result and self._intelligent_closing_decision(result, dynamic_params):  # Intelligent Decision
                        # คำนวณ Total Impact Score
                        impact_score = self._calculate_total_impact_score(result, portfolio_health)
                        final_score = impact_score * priority  # Apply priority multiplier
                        
                        logger.debug(f"💰 {method_name}_{size}: Net ${result['net_pnl']:.2f}, "
                                   f"Impact {impact_score:.1f}, Final {final_score:.1f}")
                        
                        if final_score > best_score:
                            best_score = final_score
                            best_result = result
                            best_result['method'] = f"{method_name}_{size}"
                            best_result['priority'] = priority
                            best_result['impact_score'] = impact_score
                            best_result['final_score'] = final_score
            
            if best_result:
                # Create final result
                closing_result = ClosingResult(
                    should_close=True,
                    positions_to_close=best_result['positions'],
                    method=best_result['method'],
                    net_pnl=best_result['net_pnl'],
                    expected_pnl=best_result['net_pnl'],
                    position_count=len(best_result['positions']),
                    buy_count=len([p for p in best_result['positions'] if getattr(p, 'type', 0) == 0]),
                    sell_count=len([p for p in best_result['positions'] if getattr(p, 'type', 0) == 1]),
                    portfolio_improvement=best_result.get('portfolio_improvement', {}),
                    confidence_score=min(100, best_result['final_score']),
                    reason=f"Dynamic 7D: {best_result['method']}, Priority {best_result['priority']:.1f}"
                )
                
                logger.info(f"✅ BEST CLOSING FOUND: {closing_result.method}")
                logger.info(f"💰 Net P&L: ${closing_result.net_pnl:.2f}, "
                           f"Positions: {closing_result.position_count} "
                           f"({closing_result.buy_count}B+{closing_result.sell_count}S)")
                logger.info(f"🏆 Confidence: {closing_result.confidence_score:.1f}%")
                
                return closing_result
            
            logger.info("⏸️ No profitable closing opportunities found")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error in dynamic closing analysis: {e}")
            return None
    
    def _analyze_portfolio_health(self, positions: List[Any], account_info: Dict) -> PortfolioHealth:
        """📊 วิเคราะห์สุขภาพพอร์ต"""
        try:
            balance = account_info.get('balance', 0)
            equity = account_info.get('equity', balance)
            margin = account_info.get('margin', 1)
            free_margin = account_info.get('free_margin', equity - margin)
            margin_level = (equity / max(margin, 1)) * 100
            
            total_pnl = sum(getattr(pos, 'profit', 0) for pos in positions)
            buy_count = len([p for p in positions if getattr(p, 'type', 0) == 0])
            sell_count = len([p for p in positions if getattr(p, 'type', 0) == 1])
            position_count = len(positions)
            
            buy_sell_ratio = buy_count / max(1, sell_count)
            imbalance_percentage = abs(buy_count - sell_count) / max(1, position_count) * 100
            
            return PortfolioHealth(
                balance=balance,
                equity=equity,
                margin=margin,
                free_margin=free_margin,
                margin_level=margin_level,
                total_pnl=total_pnl,
                buy_count=buy_count,
                sell_count=sell_count,
                position_count=position_count,
                buy_sell_ratio=buy_sell_ratio,
                imbalance_percentage=imbalance_percentage
            )
        except Exception as e:
            logger.error(f"❌ Error analyzing portfolio health: {e}")
            return PortfolioHealth(0, 0, 1, 0, 100, 0, 0, 0, 0, 1.0, 0)
    
    def _calculate_dynamic_parameters(self, portfolio_health: PortfolioHealth, 
                                    market_conditions: Optional[Dict] = None) -> Dict[str, Any]:
        """🔄 คำนวณ Dynamic Parameters ตามสถานการณ์"""
        try:
            total_positions = portfolio_health.position_count
            margin_level = portfolio_health.margin_level
            imbalance = portfolio_health.imbalance_percentage
            
            # 🎯 Dynamic Max Group Size
            if margin_level < self.critical_margin_threshold:
                # 🚨 วิกฤตมาก - ปิดได้มากที่สุด
                max_size = min(int(total_positions * 0.8), 100)  # ปิด 80% หรือ 100 ไม้
                reason = "Critical Margin Emergency"
            elif margin_level < self.emergency_margin_threshold:
                # ⚠️ เสี่ยงสูง - ปิดได้เยอะ
                max_size = min(int(total_positions * 0.6), 75)   # ปิด 60% หรือ 75 ไม้
                reason = "Emergency Margin Relief"
            elif imbalance > 80:
                # ⚖️ ไม่สมดุลมาก - ปิดได้พอสมควร
                max_size = min(int(total_positions * 0.5), 60)   # ปิด 50% หรือ 60 ไม้
                reason = "Severe Imbalance"
            elif total_positions > 100:
                # 📊 ไม้เยอะมาก - ปิดได้เยอะ
                max_size = min(int(total_positions * 0.4), 50)   # ปิด 40% หรือ 50 ไม้
                reason = "High Position Count"
            elif total_positions > 50:
                # 📊 ไม้ปานกลาง - ปิดได้ปานกลาง
                max_size = min(int(total_positions * 0.35), 35)  # ปิด 35% หรือ 35 ไม้
                reason = "Medium Position Count"
            elif total_positions > 20:
                # 📊 ไม้น้อย - ปิดได้น้อย
                max_size = min(int(total_positions * 0.3), 25)   # ปิด 30% หรือ 25 ไม้
                reason = "Low Position Count"
            else:
                # 📊 ไม้น้อยมาก - ปิดได้น้อยมาก
                max_size = min(int(total_positions * 0.25), 15)  # ปิด 25% หรือ 15 ไม้
                reason = "Very Low Position Count"
            
            # ไม่ให้ต่ำกว่า minimum
            max_size = max(max_size, 5)
            
            # 💰 DYNAMIC PROFIT TAKING - ปรับตามสถานการณ์จริง
            safety_buffer = self._calculate_dynamic_profit_threshold(
                margin_level, total_positions, imbalance, portfolio_health
            )
            
            # 🎯 Dynamic Priority Multiplier
            if margin_level < self.critical_margin_threshold:
                priority_multiplier = 2.0  # เร่งด่วนมาก
            elif margin_level < self.emergency_margin_threshold:
                priority_multiplier = 1.5  # เร่งด่วน
            elif imbalance > self.imbalance_threshold:
                priority_multiplier = 1.3  # เน้น Balance
            else:
                priority_multiplier = 1.0  # ปกติ
            
            # 📊 Market Conditions Adjustment
            if market_conditions:
                volatility = market_conditions.get('volatility', 0.5)
                
                # Convert string volatility to numeric value
                if isinstance(volatility, str):
                    volatility_map = {
                        'low': 0.2,
                        'medium': 0.5,
                        'high': 0.8,
                        'very_high': 1.0
                    }
                    volatility = volatility_map.get(volatility.lower(), 0.5)
                
                # Ensure volatility is numeric
                try:
                    volatility = float(volatility)
                except (ValueError, TypeError):
                    volatility = 0.5  # Default to medium
                
                if volatility > 0.8:  # ตลาดผันผวนมาก
                    max_size = int(max_size * 0.8)  # ลดขนาด 20%
                    safety_buffer *= 1.2  # เพิ่มเกณฑ์ 20%
                elif volatility < 0.3:  # ตลาดเงียบ
                    max_size = int(max_size * 1.2)  # เพิ่มขนาด 20%
                    safety_buffer *= 0.9  # ลดเกณฑ์ 10%
            
            dynamic_params = {
                'max_size': max_size,
                'safety_buffer': safety_buffer,
                'priority_multiplier': priority_multiplier,
                'reason': reason,
                'total_positions': total_positions,
                'margin_level': margin_level,
                'imbalance': imbalance
            }
            
            logger.info(f"🔄 DYNAMIC PARAMS: Max Size {max_size} (Reason: {reason})")
            logger.info(f"💰 Safety Buffer: ${safety_buffer:.1f}, Priority Multiplier: {priority_multiplier:.1f}")
            
            return dynamic_params
            
        except Exception as e:
            logger.error(f"❌ Error calculating dynamic parameters: {e}")
            # Fallback to safe defaults
            return {
                'max_size': self.base_max_group_size,
                'safety_buffer': self.base_safety_buffer,
                'priority_multiplier': 1.0,
                'reason': 'Fallback Default',
                'total_positions': portfolio_health.position_count,
                'margin_level': portfolio_health.margin_level,
                'imbalance': portfolio_health.imbalance_percentage
            }
    
    def _calculate_dynamic_profit_threshold(self, margin_level: float, total_positions: int, 
                                          imbalance: float, portfolio_health: PortfolioHealth) -> float:
        """💰 คำนวณเกณฑ์กำไรแบบ Dynamic"""
        try:
            # 🎯 Base threshold
            base_threshold = self.base_safety_buffer
            
            # 📊 Analyze losing positions ratio
            losing_ratio = 0
            total_loss_amount = 0
            if hasattr(portfolio_health, 'total_pnl') and portfolio_health.total_pnl < 0:
                # Estimate losing positions (simplified)
                losing_ratio = min(0.9, abs(portfolio_health.total_pnl) / max(portfolio_health.equity * 0.1, 100))
                total_loss_amount = abs(portfolio_health.total_pnl)
            
            # 🚨 CRITICAL CONDITIONS - ลดเกณฑ์มาก
            if margin_level < self.critical_margin_threshold:
                dynamic_threshold = 0.3  # เร่งด่วนมาก - ยอมขาดทุนเล็กน้อย
                reason = "Critical Margin - Emergency Exit"
                
            elif margin_level < self.emergency_margin_threshold:
                dynamic_threshold = 0.8  # เร่งด่วน - เกณฑ์ต่ำ
                reason = "Emergency Margin - Quick Exit"
                
            # ⚖️ HIGH IMBALANCE - ลดเกณฑ์เพื่อปรับสมดุล
            elif imbalance > 85:
                dynamic_threshold = 0.5  # ไม่สมดุลมาก - เร่งปรับ
                reason = "Severe Imbalance - Force Balance"
                
            elif imbalance > 70:
                dynamic_threshold = 1.0  # ไม่สมดุล - ลดเกณฑ์
                reason = "High Imbalance - Balance Recovery"
                
            # 📊 HIGH POSITION COUNT - ลดเกณฑ์เพื่อลดไม้
            elif total_positions > 150:
                dynamic_threshold = 0.5  # ไม้เยอะมาก - เร่งลด
                reason = "Massive Position Count - Urgent Reduction"
                
            elif total_positions > 100:
                dynamic_threshold = 1.0  # ไม้เยอะ - ลดเกณฑ์
                reason = "High Position Count - Position Reduction"
                
            elif total_positions > 50:
                dynamic_threshold = 1.5  # ไม้ปานกลาง - เกณฑ์ปานกลาง
                reason = "Medium Position Count - Moderate Exit"
                
            # 💔 HIGH LOSING RATIO - ลดเกณฑ์เพื่อเครียไม้แย่
            elif losing_ratio > 0.7:  # 70% ของ equity ขาดทุน
                dynamic_threshold = 0.2  # ขาดทุนหนัก - เร่งเครีย
                reason = "Heavy Loss Situation - Clear Bad Positions"
                
            elif losing_ratio > 0.5:  # 50% ของ equity ขาดทุน
                dynamic_threshold = 0.8  # ขาดทุนปานกลาง - ลดเกณฑ์
                reason = "Moderate Loss Situation - Recovery Mode"
                
            elif losing_ratio > 0.3:  # 30% ของ equity ขาดทุน
                dynamic_threshold = 1.2  # ขาดทุนน้อย - เกณฑ์ปานกลาง
                reason = "Light Loss Situation - Cautious Exit"
                
            # 😊 GOOD CONDITIONS - เกณฑ์ปกติ
            elif total_positions < 20:
                dynamic_threshold = base_threshold * 1.2  # ไม้น้อย - เกณฑ์สูงขึ้น
                reason = "Low Position Count - Higher Standards"
                
            else:
                dynamic_threshold = base_threshold  # ปกติ - เกณฑ์มาตรฐาน
                reason = "Normal Conditions - Standard Threshold"
            
            # 🔄 PORTFOLIO HEALTH ADJUSTMENT
            if portfolio_health.free_margin > 5000:
                # Free Margin ดี - ยืดหยุ่นได้มากขึ้น
                if losing_ratio > 0.5:  # แต่ถ้าขาดทุนเยอะ ก็ลดเกณฑ์
                    dynamic_threshold *= 0.7  # ลดเกณฑ์ 30%
                    reason += " + High Free Margin Flexibility"
                elif total_positions > 80:  # หรือไม้เยอะ ก็ลดเกณฑ์
                    dynamic_threshold *= 0.8  # ลดเกณฑ์ 20%
                    reason += " + Position Count Adjustment"
            
            # 🎯 MINIMUM & MAXIMUM LIMITS
            dynamic_threshold = max(0.1, min(dynamic_threshold, 3.0))  # ระหว่าง $0.1 - $3.0
            
            logger.info(f"💰 DYNAMIC PROFIT: ${dynamic_threshold:.1f} (Reason: {reason})")
            logger.info(f"📊 Analysis: Positions {total_positions}, Imbalance {imbalance:.1f}%, "
                       f"Losing Ratio {losing_ratio*100:.1f}%, Margin {margin_level:.1f}%")
            
            return dynamic_threshold
            
        except Exception as e:
            logger.error(f"❌ Error calculating dynamic profit threshold: {e}")
            return self.base_safety_buffer  # Fallback
    
    def _select_dynamic_methods(self, portfolio_health: PortfolioHealth, 
                               market_conditions: Optional[Dict] = None,
                               dynamic_params: Optional[Dict] = None) -> List[Tuple[str, int, int, float]]:
        """🎯 เลือกวิธีการปิดแบบ Dynamic"""
        methods = []
        
        # 📊 Dynamic method selection based on parameters
        total_positions = portfolio_health.position_count
        max_size = dynamic_params.get('max_size', 25) if dynamic_params else 25
        priority_multiplier = dynamic_params.get('priority_multiplier', 1.0) if dynamic_params else 1.0
        
        if total_positions > 40:
            # เยอะมาก → เน้น Large Groups (ใช้ Dynamic Max Size)
            methods.extend([
                ('large_groups_7d', 15, min(max_size, 50), 1.0 * priority_multiplier),
                ('mixed_edge_7d', 12, min(max_size, 40), 0.9 * priority_multiplier),
                ('emergency_mass_closing', 20, min(max_size, 60), 0.8 * priority_multiplier)
            ])
        elif total_positions > 25:
            # ปานกลาง → เน้น Medium Groups (ใช้ Dynamic Max Size)
            methods.extend([
                ('medium_groups_7d', 8, min(max_size, 30), 1.0 * priority_multiplier),
                ('mixed_edge_7d', 8, min(max_size, 25), 0.9 * priority_multiplier),
                ('smart_7d_selection', 6, min(max_size, 20), 0.8 * priority_multiplier)
            ])
        elif total_positions > 10:
            # น้อย → เน้น Small Groups (ใช้ Dynamic Max Size)
            methods.extend([
                ('small_groups_7d', 4, min(max_size, 15), 1.0 * priority_multiplier),
                ('balanced_pairs_7d', 2, min(max_size, 10), 0.9 * priority_multiplier),
                ('smart_7d_selection', 3, min(max_size, 12), 0.8 * priority_multiplier)
            ])
        else:
            # น้อยมาก → เน้น Pairs (ใช้ Dynamic Max Size)
            methods.extend([
                ('balanced_pairs_7d', 2, min(max_size, 8), 1.0 * priority_multiplier),
                ('smart_7d_selection', 2, min(max_size, 10), 0.9 * priority_multiplier)
            ])
        
        # 🎯 Problem Position Priority Methods (เพิ่มใหม่)
        methods.extend([
            ('distant_problem_clearing', 3, min(max_size, 40), 1.8 * priority_multiplier),  # ปิด Problem ไกลๆ
            ('problem_helper_pairing', 2, min(max_size, 30), 1.7 * priority_multiplier),    # จับคู่ Problem+Helper
            ('balanced_problem_exit', 4, min(max_size, 35), 1.6 * priority_multiplier)      # ปิด Problem แบบสมดุล
        ])
        
        # ⚖️ Imbalance-based selection (ใช้ Dynamic Max Size)
        if portfolio_health.imbalance_percentage > self.imbalance_threshold:
            methods.extend([
                ('force_balance_7d', 4, min(max_size, 30), 1.3 * priority_multiplier),
                ('cross_balance_groups_7d', 6, min(max_size, 35), 1.2 * priority_multiplier)
            ])
        
        # 🚨 Margin-based selection (ใช้ Dynamic Max Size)
        if portfolio_health.margin_level < self.emergency_margin_threshold:
            methods.extend([
                ('emergency_margin_relief', 8, min(max_size, 50), 1.5 * priority_multiplier),
                ('high_margin_impact_7d', 6, min(max_size, 40), 1.4 * priority_multiplier)
            ])
        
        # 🎯 Edge-based methods (always available, ใช้ Dynamic Max Size)
        methods.extend([
            ('top_edge_7d', 3, min(max_size, 25), 0.7 * priority_multiplier),
            ('bottom_edge_7d', 3, min(max_size, 25), 0.7 * priority_multiplier),
            ('mixed_edge_7d', 4, min(max_size, 30), 0.8 * priority_multiplier)
        ])
        
        # Sort by priority (highest first)
        return sorted(methods, key=lambda x: x[3], reverse=True)
    
    def _try_purpose_aware_7d_method(self, method_name: str, position_scores: List[Any],
                                   position_purposes: Dict[str, Any], size: int, 
                                   portfolio_health: PortfolioHealth) -> Optional[Dict]:
        """🧠 ลองใช้วิธีการที่มี Purpose Intelligence + 7D Scores"""
        try:
            # 📊 Enhance position scores with Purpose Intelligence
            enhanced_scores = self._enhance_scores_with_purpose(position_scores, position_purposes)
            
            # 🎯 Use enhanced scores in existing 7D methods
            return self._try_7d_method_with_enhanced_scores(method_name, enhanced_scores, size, portfolio_health)
            
        except Exception as e:
            logger.error(f"❌ Error in Purpose-Aware 7D method {method_name}: {e}")
            # Fallback to regular 7D method
            return self._try_7d_method(method_name, position_scores, size, portfolio_health)
    
    def _try_7d_method(self, method_name: str, position_scores: List[Any], 
                      size: int, portfolio_health: PortfolioHealth) -> Optional[Dict]:
        """🧠 ลองใช้วิธีการที่มี 7D Scores"""
        try:
            if method_name == 'smart_7d_selection':
                # เรียงตาม 7D Score + BALANCED
                logger.debug(f"🧠 Smart 7D Selection: size={size}")
                
                # 🎯 CRITICAL FIX: ใช้ balanced selection
                buy_scores = [s for s in position_scores if getattr(s.position, 'type', 0) == 0]
                sell_scores = [s for s in position_scores if getattr(s.position, 'type', 0) == 1]
                
                if not buy_scores or not sell_scores:
                    # 🎯 SMART UNBALANCED MODE: ปิดแบบไม่ balance เมื่อจำเป็น
                    logger.info(f"🔄 Smart 7D: Unbalanced portfolio - using single-type closing")
                    all_scores = buy_scores + sell_scores
                    all_scores.sort(key=lambda x: x.total_score, reverse=True)
                    selected = all_scores[:min(size, len(all_scores))]
                    
                    type_name = "BUY" if buy_scores else "SELL"
                    logger.info(f"✅ Unbalanced Close: {len(selected)} {type_name} positions selected")
                else:
                    # เรียงตาม score
                    buy_scores.sort(key=lambda x: x.total_score, reverse=True)
                    sell_scores.sort(key=lambda x: x.total_score, reverse=True)
                    
                    # เลือกแบบ balanced
                    buy_count = max(1, size // 2)
                    sell_count = size - buy_count
                    
                    selected_buys = buy_scores[:buy_count] if len(buy_scores) >= buy_count else buy_scores
                    selected_sells = sell_scores[:sell_count] if len(sell_scores) >= sell_count else sell_scores
                    
                    if len(selected_buys) == 0 or len(selected_sells) == 0:
                        # 🎯 FALLBACK: ใช้ที่มี
                        selected = selected_buys + selected_sells
                        logger.info(f"🔄 Smart 7D Fallback: Using available positions ({len(selected)} total)")
                    else:
                        selected = selected_buys + selected_sells
                        logger.info(f"✅ Smart 7D Balance: {len(selected_buys)}B+{len(selected_sells)}S = {len(selected)} total")
                
            elif method_name == 'top_edge_7d':
                # ขอบบน + 7D Score + BALANCED
                logger.debug(f"🔝 Top Edge 7D: size={size}")
                
                # 🎯 CRITICAL FIX: ใช้ balanced method แทน
                all_positions = [score.position for score in position_scores]
                selected_positions = self._select_top_edge_balanced(all_positions, size)
                
                if selected_positions:
                    # แปลงกลับเป็น position scores
                    selected_tickets = [getattr(pos, 'ticket', None) for pos in selected_positions]
                    selected = [score for score in position_scores 
                              if getattr(score.position, 'ticket', None) in selected_tickets]
                    
                    # ตรวจสอบ balance
                    buys = len([s for s in selected if getattr(s.position, 'type', 0) == 0])
                    sells = len([s for s in selected if getattr(s.position, 'type', 0) == 1])
                    logger.debug(f"🔝 Top Edge Balance: {buys}B+{sells}S = {len(selected)} total")
                else:
                    # 🎯 UNBALANCED TOP EDGE: ใช้ positions ที่มี เรียงตามราคาสูงสุด
                    position_scores.sort(key=lambda x: getattr(x.position, 'price_open', 0), reverse=True)
                    selected = position_scores[:min(size, len(position_scores))]
                    logger.info(f"🔄 Top Edge Unbalanced: {len(selected)} positions from highest prices")
                
            elif method_name == 'bottom_edge_7d':
                # ขอบล่าง + 7D Score + BALANCED
                logger.debug(f"🔻 Bottom Edge 7D: size={size}")
                
                # 🎯 CRITICAL FIX: ใช้ balanced method แทน
                all_positions = [score.position for score in position_scores]
                selected_positions = self._select_bottom_edge_balanced(all_positions, size)
                
                if selected_positions:
                    # แปลงกลับเป็น position scores
                    selected_tickets = [getattr(pos, 'ticket', None) for pos in selected_positions]
                    selected = [score for score in position_scores 
                              if getattr(score.position, 'ticket', None) in selected_tickets]
                    
                    # ตรวจสอบ balance
                    buys = len([s for s in selected if getattr(s.position, 'type', 0) == 0])
                    sells = len([s for s in selected if getattr(s.position, 'type', 0) == 1])
                    logger.info(f"🔻 Bottom Edge Balance: {buys}B+{sells}S = {len(selected)} total")
                else:
                    # 🎯 UNBALANCED BOTTOM EDGE: ใช้ positions ที่มี เรียงตามราคาต่ำสุด
                    position_scores.sort(key=lambda x: getattr(x.position, 'price_open', 0))
                    selected = position_scores[:min(size, len(position_scores))]
                    logger.info(f"🔄 Bottom Edge Unbalanced: {len(selected)} positions from lowest prices")
                
            elif method_name == 'mixed_edge_7d':
                # ขอบผสม + 7D Score + BALANCED
                logger.debug(f"🔀 Mixed Edge 7D: size={size}")
                
                # 🎯 CRITICAL FIX: ใช้ balanced methods แทน
                all_positions = [score.position for score in position_scores]
                selected_positions = self._select_mixed_edge_balanced(all_positions, size)
                
                if selected_positions:
                    # แปลงกลับเป็น position scores
                    selected_tickets = [getattr(pos, 'ticket', None) for pos in selected_positions]
                    selected = [score for score in position_scores 
                              if getattr(score.position, 'ticket', None) in selected_tickets]
                    
                    # ตรวจสอบ balance
                    buys = len([s for s in selected if getattr(s.position, 'type', 0) == 0])
                    sells = len([s for s in selected if getattr(s.position, 'type', 0) == 1])
                    logger.info(f"🔀 Mixed Edge Balance: {buys}B+{sells}S = {len(selected)} total")
                else:
                    # 🎯 UNBALANCED MIXED EDGE: ใช้ positions ที่มี เรียงตาม 7D score
                    position_scores.sort(key=lambda x: x.total_score, reverse=True)
                    selected = position_scores[:min(size, len(position_scores))]
                    logger.info(f"🔄 Mixed Edge Unbalanced: {len(selected)} positions by 7D score")
                    
            elif method_name == 'force_balance_7d':
                # บังคับ Balance + 7D Score
                selected = self._find_7d_balance_combination(position_scores, size, portfolio_health)
                
            elif method_name in ['small_groups_7d', 'medium_groups_7d', 'large_groups_7d']:
                # กลุ่มต่างขนาด + 7D Score
                selected = self._find_7d_optimal_group(position_scores, size, portfolio_health)
                
            elif method_name == 'emergency_margin_relief':
                # Emergency Margin + 7D Score
                selected = self._find_7d_margin_relief(position_scores, size, portfolio_health)
                
            else:
                # Fallback to smart selection + BALANCED
                logger.debug(f"🔄 Fallback Smart Selection: size={size}")
                
                # 🎯 CRITICAL FIX: ใช้ balanced fallback
                buy_scores = [s for s in position_scores if getattr(s.position, 'type', 0) == 0]
                sell_scores = [s for s in position_scores if getattr(s.position, 'type', 0) == 1]
                
                if not buy_scores or not sell_scores:
                    # 🎯 FINAL FALLBACK: ปิดแบบไม่ balance
                    logger.info(f"🔄 Final Fallback: Unbalanced closing")
                    all_scores = buy_scores + sell_scores
                    all_scores.sort(key=lambda x: x.total_score, reverse=True)
                    selected = all_scores[:min(size, len(all_scores))]
                    
                    type_name = "BUY" if buy_scores else "SELL"
                    logger.info(f"✅ Final Fallback: {len(selected)} {type_name} positions")
                else:
                    # เรียงตาม score
                    buy_scores.sort(key=lambda x: x.total_score, reverse=True)
                    sell_scores.sort(key=lambda x: x.total_score, reverse=True)
                    
                    # เลือกแบบ balanced
                    buy_count = max(1, size // 2)
                    sell_count = size - buy_count
                    
                    selected_buys = buy_scores[:buy_count] if len(buy_scores) >= buy_count else buy_scores
                    selected_sells = sell_scores[:sell_count] if len(sell_scores) >= sell_count else sell_scores
                    
                    if len(selected_buys) == 0 or len(selected_sells) == 0:
                        # 🎯 ใช้ที่มี
                        selected = selected_buys + selected_sells
                        logger.info(f"🔄 Fallback Partial: Using available positions ({len(selected)} total)")
                    else:
                        selected = selected_buys + selected_sells
                        logger.info(f"✅ Fallback Balance: {len(selected_buys)}B+{len(selected_sells)}S = {len(selected)} total")
            
            if not selected:
                return None
            
            # คำนวณผลลัพธ์
            positions = [score.position for score in selected]
            return self._calculate_combination_result(positions, portfolio_health)
            
        except Exception as e:
            logger.error(f"❌ Error in 7D method {method_name}: {e}")
            return None
    
    def _try_fallback_method(self, method_name: str, positions: List[Any], 
                           size: int, portfolio_health: PortfolioHealth) -> Optional[Dict]:
        """🔄 ลองใช้วิธีการ Fallback (ไม่มี 7D)"""
        try:
            if method_name.endswith('_7d'):
                # ลบ _7d suffix สำหรับ fallback
                base_method = method_name.replace('_7d', '')
            else:
                base_method = method_name
            
            if base_method == 'smart_selection':
                # เรียงตาม profit
                sorted_positions = sorted(positions, 
                                        key=lambda x: getattr(x, 'profit', 0), reverse=True)
                selected = sorted_positions[:size]
                
            elif base_method == 'top_edge':
                # ขอบบน - 🎯 FORCE BUY+SELL BALANCE
                selected = self._select_top_edge_balanced(positions, size)
                
            elif base_method == 'bottom_edge':
                # ขอบล่าง - 🎯 FORCE BUY+SELL BALANCE  
                selected = self._select_bottom_edge_balanced(positions, size)
                
            elif base_method == 'mixed_edge':
                # ขอบผสม - 🎯 FORCE BUY+SELL BALANCE
                selected = self._select_mixed_edge_balanced(positions, size)
                
            else:
                # Default: เรียงตาม profit
                sorted_positions = sorted(positions, 
                                        key=lambda x: getattr(x, 'profit', 0), reverse=True)
                selected = sorted_positions[:size]
            
            if not selected:
                return None
            
            return self._calculate_combination_result(selected, portfolio_health)
            
        except Exception as e:
            logger.error(f"❌ Error in fallback method {method_name}: {e}")
            return None
    
    def _get_top_edge_positions(self, position_scores: List[Any]) -> List[Any]:
        """🔝 หา positions ขอบบน (ราคาสูงสุด)"""
        return sorted(position_scores, 
                     key=lambda x: getattr(x.position, 'open_price', 0), reverse=True)
    
    def _get_bottom_edge_positions(self, position_scores: List[Any]) -> List[Any]:
        """🔻 หา positions ขอบล่าง (ราคาต่ำสุด)"""
        return sorted(position_scores, 
                     key=lambda x: getattr(x.position, 'open_price', 0))
    
    def _find_7d_balance_combination(self, position_scores: List[Any], size: int, 
                                   portfolio_health: PortfolioHealth) -> List[Any]:
        """⚖️ หาชุดที่ Balance และมี 7D Score ดี"""
        try:
            buy_scores = [s for s in position_scores if getattr(s.position, 'type', 0) == 0]
            sell_scores = [s for s in position_scores if getattr(s.position, 'type', 0) == 1]
            
            # เรียงตาม 7D Score
            buy_scores.sort(key=lambda x: x.total_score, reverse=True)
            sell_scores.sort(key=lambda x: x.total_score, reverse=True)
            
            # พยายาม balance
            target_buy = size // 2
            target_sell = size - target_buy
            
            selected_buys = buy_scores[:min(target_buy, len(buy_scores))]
            selected_sells = sell_scores[:min(target_sell, len(sell_scores))]
            
            # เติมให้ครบ size ถ้าไม่พอ
            selected = selected_buys + selected_sells
            if len(selected) < size:
                remaining_scores = [s for s in position_scores if s not in selected]
                remaining_scores.sort(key=lambda x: x.total_score, reverse=True)
                selected.extend(remaining_scores[:size - len(selected)])
            
            return selected[:size]
            
        except Exception as e:
            logger.error(f"❌ Error finding 7D balance combination: {e}")
            return []
    
    def _find_7d_optimal_group(self, position_scores: List[Any], size: int, 
                             portfolio_health: PortfolioHealth) -> List[Any]:
        """🎯 หากลุ่มที่ดีที่สุดตาม 7D Score"""
        try:
            # เรียงตาม 7D Score
            sorted_scores = sorted(position_scores, key=lambda x: x.total_score, reverse=True)
            
            # เลือก top positions
            return sorted_scores[:size]
            
        except Exception as e:
            logger.error(f"❌ Error finding 7D optimal group: {e}")
            return []
    
    def _find_7d_margin_relief(self, position_scores: List[Any], size: int, 
                             portfolio_health: PortfolioHealth) -> List[Any]:
        """🚨 หาชุดที่ช่วยลด Margin Risk"""
        try:
            # เรียงตาม margin_impact (สูงสุดก่อน) และ profit
            sorted_scores = sorted(position_scores, 
                                 key=lambda x: (x.margin_impact, x.profit_score), reverse=True)
            
            return sorted_scores[:size]
            
        except Exception as e:
            logger.error(f"❌ Error finding 7D margin relief: {e}")
            return []
    
    def _calculate_combination_result(self, positions: List[Any], 
                                    portfolio_health: PortfolioHealth) -> Dict:
        """💰 คำนวณผลลัพธ์ของการปิดชุด positions"""
        try:
            if not positions:
                return None
            
            # คำนวณ P&L รวม
            total_profit = sum(getattr(pos, 'profit', 0) for pos in positions)
            
            # คำนวณ cost การปิด
            closing_cost = self._calculate_closing_cost(positions)
            
            net_pnl = total_profit - closing_cost
            
            # คำนวณการปรับปรุง Portfolio
            buy_count = len([p for p in positions if getattr(p, 'type', 0) == 0])
            sell_count = len([p for p in positions if getattr(p, 'type', 0) == 1])
            
            portfolio_improvement = {
                'pnl_improvement': net_pnl,
                'position_reduction': len(positions),
                'balance_improvement': self._calculate_balance_improvement(
                    buy_count, sell_count, portfolio_health
                ),
                'margin_improvement': self._calculate_margin_improvement(
                    positions, portfolio_health
                )
            }
            
            return {
                'positions': positions,
                'total_profit': total_profit,
                'closing_cost': closing_cost,
                'net_pnl': net_pnl,
                'buy_count': buy_count,
                'sell_count': sell_count,
                'portfolio_improvement': portfolio_improvement
            }
            
        except Exception as e:
            logger.error(f"❌ Error calculating combination result: {e}")
            return None
    
    def _calculate_closing_cost(self, positions: List[Any]) -> float:
        """💸 คำนวณ cost การปิด"""
        try:
            total_volume = sum(getattr(pos, 'volume', 0.01) for pos in positions)
            
            # ประมาณการ cost (spread + commission + slippage)
            spread_cost = total_volume * 0.8    # $0.8 per lot
            commission_cost = total_volume * 0.3  # $0.3 per lot  
            slippage_cost = total_volume * 1.0   # $1.0 per lot
            
            return spread_cost + commission_cost + slippage_cost
            
        except Exception as e:
            logger.error(f"❌ Error calculating closing cost: {e}")
            return len(positions) * 2.0  # Fallback cost
    
    def _calculate_balance_improvement(self, buy_count: int, sell_count: int, 
                                     portfolio_health: PortfolioHealth) -> float:
        """⚖️ คำนวณการปรับปรุง Balance"""
        try:
            current_imbalance = abs(portfolio_health.buy_count - portfolio_health.sell_count)
            after_buy_count = portfolio_health.buy_count - buy_count
            after_sell_count = portfolio_health.sell_count - sell_count
            after_imbalance = abs(after_buy_count - after_sell_count)
            
            return current_imbalance - after_imbalance
            
        except Exception as e:
            logger.error(f"❌ Error calculating balance improvement: {e}")
            return 0.0
    
    def _calculate_margin_improvement(self, positions: List[Any], 
                                    portfolio_health: PortfolioHealth) -> float:
        """📊 คำนวณการปรับปรุง Margin"""
        try:
            # ประมาณการ margin ที่จะได้คืน
            total_volume = sum(getattr(pos, 'volume', 0.01) for pos in positions)
            margin_per_lot = 100  # ประมาณ $100 per lot
            margin_released = total_volume * margin_per_lot
            
            current_margin = portfolio_health.margin
            after_margin = current_margin - margin_released
            
            current_margin_level = portfolio_health.margin_level
            after_margin_level = (portfolio_health.equity / max(after_margin, 1)) * 100
            
            return after_margin_level - current_margin_level
            
        except Exception as e:
            logger.error(f"❌ Error calculating margin improvement: {e}")
            return 0.0
    
    def _calculate_total_impact_score(self, result: Dict, portfolio_health: PortfolioHealth) -> float:
        """🏆 คำนวณคะแนนผลกระทบรวม"""
        try:
            improvement = result['portfolio_improvement']
            
            # 1. P&L Score (40%)
            pnl_score = improvement['pnl_improvement'] * 10
            
            # 2. Position Reduction Score (25%)
            reduction_score = improvement['position_reduction'] * 5
            
            # 3. Balance Improvement Score (20%)
            balance_score = improvement['balance_improvement'] * 8
            
            # 4. Margin Improvement Score (15%)
            margin_score = improvement['margin_improvement'] * 2
            
            total_score = (pnl_score * 0.4 + reduction_score * 0.25 + 
                          balance_score * 0.2 + margin_score * 0.15)
            
            return max(0, total_score)
            
        except Exception as e:
            logger.error(f"❌ Error calculating total impact score: {e}")
            return 0.0
    
    def _enhance_scores_with_purpose(self, position_scores: List[Any], 
                                   position_purposes: Dict[str, Any]) -> List[Any]:
        """🧠 Enhance 7D Scores with Purpose Intelligence"""
        try:
            enhanced_scores = []
            
            for score_obj in position_scores:
                position_ticket = str(getattr(score_obj.position, 'ticket', id(score_obj.position)))
                purpose_analysis = position_purposes.get(position_ticket)
                
                if purpose_analysis:
                    # 📊 Calculate Purpose-Enhanced Score
                    purpose_weight = self.purpose_priority_weights.get(
                        purpose_analysis.purpose.value, 1.0
                    )
                    
                    # Base 7D Score
                    base_7d_score = getattr(score_obj, 'total_score', 50.0)
                    
                    # Purpose adjustments
                    purpose_score = purpose_analysis.purpose_score
                    adaptability = purpose_analysis.adaptability
                    problem_solving = purpose_analysis.problem_solving_potential
                    
                    # 🎯 Distance-based Priority
                    current_price = self._get_current_price()
                    position_price = getattr(score_obj.position, 'open_price', current_price)
                    distance_pips = abs(current_price - position_price) * 0.1  # XAUUSD: 1 point = 0.1 pip
                    
                    distance_category = self._get_distance_category(distance_pips)
                    distance_multiplier = self.distance_priority_multiplier.get(distance_category, 1.0)
                    
                    # 🧠 Enhanced Score Calculation (รวม Distance Factor)
                    enhanced_score = (
                        base_7d_score * 0.5 +           # 50% 7D Score (ลดลง)
                        purpose_score * 0.3 +           # 30% Purpose Score (เพิ่มขึ้น)
                        adaptability * 0.1 +            # 10% Adaptability
                        problem_solving * 0.1           # 10% Problem Solving (เพิ่มขึ้น)
                    ) * purpose_weight * distance_multiplier
                    
                    # 🎯 Special Purpose Logic
                    if purpose_analysis.purpose.value == 'RECOVERY_HELPER':
                        # Helper ที่ช่วยหลายไม้ = คะแนนต่ำ (ไม่ปิด)
                        if len(purpose_analysis.helper_for) > 1:
                            enhanced_score *= 0.6
                    
                    elif purpose_analysis.purpose.value == 'PROBLEM_POSITION':
                        # Problem ที่มี helper = คะแนนสูง (ปิดได้)
                        if len(purpose_analysis.needs_help_from) > 0:
                            enhanced_score *= 1.4
                    
                    elif purpose_analysis.purpose.value == 'TREND_FOLLOWER':
                        # Trend Follower ที่ตาม trend แรง = คะแนนต่ำ (เก็บไว้)
                        if purpose_analysis.trend_compatibility > 80:
                            enhanced_score *= 0.5
                    
                    # Create enhanced score object
                    enhanced_obj = type('EnhancedScore', (), {
                        'position': score_obj.position,
                        'total_score': enhanced_score,
                        'original_7d_score': base_7d_score,
                        'purpose_analysis': purpose_analysis,
                        'purpose_weight': purpose_weight,
                        'profit_score': getattr(score_obj, 'profit_score', 0),
                        'balance_score': getattr(score_obj, 'balance_score', 0),
                        'margin_impact': getattr(score_obj, 'margin_impact', 0),
                        'recovery_potential': getattr(score_obj, 'recovery_potential', 0),
                        'time_score': getattr(score_obj, 'time_score', 0),
                        'correlation_score': getattr(score_obj, 'correlation_score', 0),
                        'volatility_score': getattr(score_obj, 'volatility_score', 0)
                    })()
                    
                    enhanced_scores.append(enhanced_obj)
                    
                else:
                    # No purpose analysis - use original score
                    enhanced_scores.append(score_obj)
            
            logger.debug(f"🧠 Enhanced {len(enhanced_scores)} scores with Purpose Intelligence")
            return enhanced_scores
            
        except Exception as e:
            logger.error(f"❌ Error enhancing scores with purpose: {e}")
            return position_scores
    
    def _try_7d_method_with_enhanced_scores(self, method_name: str, enhanced_scores: List[Any],
                                          size: int, portfolio_health: PortfolioHealth) -> Optional[Dict]:
        """🎯 Use enhanced scores in 7D methods"""
        try:
            # 🧠 Purpose-Aware Method Selection
            if method_name == 'smart_purpose_pairing':
                return self._smart_purpose_pairing(enhanced_scores, size, portfolio_health)
            
            elif method_name == 'recovery_helper_protection':
                return self._recovery_helper_protection(enhanced_scores, size, portfolio_health)
            
            elif method_name == 'problem_position_clearing':
                return self._problem_position_clearing(enhanced_scores, size, portfolio_health)
            
            elif method_name == 'distant_problem_clearing':
                return self._distant_problem_clearing(enhanced_scores, size, portfolio_health)
            
            elif method_name == 'problem_helper_pairing':
                return self._smart_purpose_pairing(enhanced_scores, size, portfolio_health)
            
            elif method_name == 'balanced_problem_exit':
                return self._balanced_problem_exit(enhanced_scores, size, portfolio_health)
            
            else:
                # Use existing 7D methods with enhanced scores
                return self._try_7d_method(method_name, enhanced_scores, size, portfolio_health)
                
        except Exception as e:
            logger.error(f"❌ Error in enhanced 7D method {method_name}: {e}")
            return None
    
    def _smart_purpose_pairing(self, enhanced_scores: List[Any], size: int, 
                             portfolio_health: PortfolioHealth) -> Optional[Dict]:
        """🧠 Smart Purpose-Based Pairing"""
        try:
            # หา Problem Positions ที่ต้องการความช่วยเหลือ
            problem_positions = [
                s for s in enhanced_scores 
                if hasattr(s, 'purpose_analysis') and 
                s.purpose_analysis.purpose.value == 'PROBLEM_POSITION'
            ]
            
            # หา Recovery Helpers ที่สามารถช่วยได้
            helper_positions = [
                s for s in enhanced_scores 
                if hasattr(s, 'purpose_analysis') and 
                s.purpose_analysis.purpose.value == 'RECOVERY_HELPER'
            ]
            
            # หา Profit Takers ที่พร้อมปิด
            profit_positions = [
                s for s in enhanced_scores 
                if hasattr(s, 'purpose_analysis') and 
                s.purpose_analysis.purpose.value == 'PROFIT_TAKER'
            ]
            
            if not problem_positions and not profit_positions:
                return None
            
            selected = []
            
            # 🎯 Strategy 1: Problem + Helper Pairing
            if problem_positions and helper_positions:
                for problem in problem_positions[:size//2]:
                    # หา Helper ที่เหมาะสมที่สุด
                    best_helper = None
                    best_compatibility = 0
                    
                    for helper in helper_positions:
                        if helper in selected:
                            continue
                        
                        # เช็คความเข้ากันได้
                        problem_ticket = str(getattr(problem.position, 'ticket', ''))
                        if problem_ticket in helper.purpose_analysis.helper_for:
                            compatibility = 100  # Perfect match
                        else:
                            # คำนวณความเข้ากันได้จากราคาและประเภท
                            compatibility = self._calculate_pairing_compatibility(
                                problem.position, helper.position
                            )
                        
                        if compatibility > best_compatibility:
                            best_compatibility = compatibility
                            best_helper = helper
                    
                    if best_helper and best_compatibility > 60:
                        selected.extend([problem, best_helper])
                        helper_positions.remove(best_helper)
                        
                        if len(selected) >= size:
                            break
            
            # 🎯 Strategy 2: Fill remaining with Profit Takers
            remaining_size = size - len(selected)
            if remaining_size > 0 and profit_positions:
                profit_sorted = sorted(profit_positions, 
                                     key=lambda x: x.total_score, reverse=True)
                selected.extend(profit_sorted[:remaining_size])
            
            # 🎯 Strategy 3: Fill remaining with highest scores
            if len(selected) < size:
                remaining = [s for s in enhanced_scores if s not in selected]
                remaining_sorted = sorted(remaining, 
                                        key=lambda x: x.total_score, reverse=True)
                selected.extend(remaining_sorted[:size - len(selected)])
            
            if not selected:
                return None
            
            positions = [s.position for s in selected[:size]]
            return self._calculate_combination_result(positions, portfolio_health)
            
        except Exception as e:
            logger.error(f"❌ Error in smart purpose pairing: {e}")
            return None
    
    def _calculate_pairing_compatibility(self, problem_position: Any, helper_position: Any) -> float:
        """🔗 คำนวณความเข้ากันได้ของการจับคู่"""
        try:
            # เช็คประเภทตรงข้าม
            problem_type = getattr(problem_position, 'type', 0)
            helper_type = getattr(helper_position, 'type', 0)
            
            if problem_type == helper_type:
                return 0  # ประเภทเดียวกัน ไม่เหมาะ
            
            # เช็คระยะห่างราคา
            problem_price = getattr(problem_position, 'open_price', 0)
            helper_price = getattr(helper_position, 'open_price', 0)
            distance = abs(problem_price - helper_price) * 0.1  # XAUUSD: 1 point = 0.1 pip
            
            # เช็คกำไร/ขาดทุน
            problem_profit = getattr(problem_position, 'profit', 0)
            helper_profit = getattr(helper_position, 'profit', 0)
            
            # คำนวณ compatibility
            compatibility = 50  # Base
            
            # Distance factor
            if distance < 20:
                compatibility += 30
            elif distance < 50:
                compatibility += 20
            elif distance < 100:
                compatibility += 10
            
            # Profit balance factor
            if helper_profit > abs(problem_profit) * 0.8:  # Helper กำไรพอปิด Problem
                compatibility += 20
            elif helper_profit > abs(problem_profit) * 0.5:
                compatibility += 10
            
            return min(100, compatibility)
            
        except Exception as e:
            logger.error(f"❌ Error calculating pairing compatibility: {e}")
            return 0
    
    def _distant_problem_clearing(self, enhanced_scores: List[Any], size: int, 
                                portfolio_health: PortfolioHealth) -> Optional[Dict]:
        """🎯 ปิด Problem Positions ที่ไกลเป็นพิเศษ"""
        try:
            current_price = self._get_current_price()
            
            # หา Problem positions ที่ไกลมาก
            distant_problems = []
            for score in enhanced_scores:
                if hasattr(score, 'purpose_analysis'):
                    purpose = score.purpose_analysis.purpose.value
                    if purpose == 'PROBLEM_POSITION':
                        position_price = getattr(score.position, 'open_price', current_price)
                        distance = abs(current_price - position_price) * 0.1  # XAUUSD: 1 point = 0.1 pip
                        
                        if distance > 15:  # ไกลกว่า 15 pips (ปรับสำหรับ pip ที่ถูกต้อง)
                            distant_problems.append({
                                'score': score,
                                'distance': distance,
                                'priority': score.total_score + (distance * 0.01)  # เพิ่ม priority ตามระยะ
                            })
            
            if not distant_problems:
                return None
            
            # เรียงตาม priority (ไกลสุด + Problem score สูงสุด)
            distant_problems.sort(key=lambda x: x['priority'], reverse=True)
            
            # เลือกไม้ที่จะปิด
            selected_problems = distant_problems[:min(size//2, len(distant_problems))]
            selected_positions = [item['score'] for item in selected_problems]
            
            # หา Helper positions หรือ Profit takers เพื่อจับคู่
            helpers_and_profits = []
            for score in enhanced_scores:
                if hasattr(score, 'purpose_analysis'):
                    purpose = score.purpose_analysis.purpose.value
                    if purpose in ['RECOVERY_HELPER', 'PROFIT_TAKER']:
                        helpers_and_profits.append(score)
            
            # เติมให้ครบ size
            remaining_size = size - len(selected_positions)
            if remaining_size > 0 and helpers_and_profits:
                helpers_sorted = sorted(helpers_and_profits, 
                                      key=lambda x: x.total_score, reverse=True)
                selected_positions.extend(helpers_sorted[:remaining_size])
            
            # ถ้ายังไม่ครบ เติมด้วยคะแนนสูงสุด
            if len(selected_positions) < size:
                remaining = [s for s in enhanced_scores if s not in selected_positions]
                remaining_sorted = sorted(remaining, 
                                        key=lambda x: x.total_score, reverse=True)
                selected_positions.extend(remaining_sorted[:size - len(selected_positions)])
            
            if not selected_positions:
                return None
            
            positions = [s.position for s in selected_positions[:size]]
            
            logger.info(f"🎯 DISTANT PROBLEM CLEARING: {len(selected_problems)} problems + "
                       f"{len(selected_positions) - len(selected_problems)} helpers")
            
            return self._calculate_combination_result(positions, portfolio_health)
            
        except Exception as e:
            logger.error(f"❌ Error in distant problem clearing: {e}")
            return None
    
    def _balanced_problem_exit(self, enhanced_scores: List[Any], size: int, 
                             portfolio_health: PortfolioHealth) -> Optional[Dict]:
        """⚖️ ปิด Problem positions แบบรักษาสมดุล"""
        try:
            # หา Problem positions แยกตาม BUY/SELL
            buy_problems = []
            sell_problems = []
            
            for score in enhanced_scores:
                if hasattr(score, 'purpose_analysis'):
                    if score.purpose_analysis.purpose.value == 'PROBLEM_POSITION':
                        position_type = getattr(score.position, 'type', 0)
                        if position_type == 0:  # BUY
                            buy_problems.append(score)
                        else:  # SELL
                            sell_problems.append(score)
            
            if not buy_problems and not sell_problems:
                return None
            
            # เรียงตามคะแนน
            buy_problems.sort(key=lambda x: x.total_score, reverse=True)
            sell_problems.sort(key=lambda x: x.total_score, reverse=True)
            
            selected = []
            target_buy = size // 2
            target_sell = size - target_buy
            
            # เลือกแบบสมดุล
            selected.extend(buy_problems[:min(target_buy, len(buy_problems))])
            selected.extend(sell_problems[:min(target_sell, len(sell_problems))])
            
            # ถ้าไม่ครบ เติมด้วย Helpers
            if len(selected) < size:
                helpers = [s for s in enhanced_scores 
                          if hasattr(s, 'purpose_analysis') and 
                          s.purpose_analysis.purpose.value in ['RECOVERY_HELPER', 'PROFIT_TAKER']
                          and s not in selected]
                
                helpers.sort(key=lambda x: x.total_score, reverse=True)
                selected.extend(helpers[:size - len(selected)])
            
            if not selected:
                return None
            
            positions = [s.position for s in selected[:size]]
            
            logger.info(f"⚖️ BALANCED PROBLEM EXIT: {len(selected)} positions "
                       f"(Problems: {len([s for s in selected if hasattr(s, 'purpose_analysis') and s.purpose_analysis.purpose.value == 'PROBLEM_POSITION'])})")
            
            return self._calculate_combination_result(positions, portfolio_health)
            
        except Exception as e:
            logger.error(f"❌ Error in balanced problem exit: {e}")
            return None
    
    def _get_current_price(self) -> float:
        """💰 ดึงราคาปัจจุบัน"""
        try:
            # Try to get current price from MT5
            try:
                import MetaTrader5 as mt5
                tick = mt5.symbol_info_tick("XAUUSD")
                if tick:
                    return (tick.bid + tick.ask) / 2
            except ImportError:
                pass
        except:
            pass
        
        # Fallback price
        return 2000.0
    
    def _select_top_edge_balanced(self, positions: List[Any], size: int) -> List[Any]:
        """🔝 เลือก positions ขอบบนแบบ BUY+SELL Balance"""
        try:
            # แยก BUY/SELL
            buy_positions = [p for p in positions if getattr(p, 'type', 0) == 0]
            sell_positions = [p for p in positions if getattr(p, 'type', 0) == 1]
            
            # เรียงตามราคา (สูง→ต่ำ)
            buy_positions.sort(key=lambda x: getattr(x, 'open_price', 0), reverse=True)
            sell_positions.sort(key=lambda x: getattr(x, 'open_price', 0), reverse=True)
            
            # เลือกแบบ Balance
            selected = []
            buy_needed = max(1, size // 2)
            sell_needed = size - buy_needed
            
            selected.extend(buy_positions[:buy_needed])
            selected.extend(sell_positions[:sell_needed])
            
            # ตรวจสอบ Balance
            final_buys = len([p for p in selected if getattr(p, 'type', 0) == 0])
            final_sells = len([p for p in selected if getattr(p, 'type', 0) == 1])
            
            if final_buys == 0 or final_sells == 0:
                logger.debug(f"❌ Top edge cannot create balance: {final_buys}B+{final_sells}S")
                return []
                
            logger.debug(f"🔝 Top edge balanced: {final_buys}B+{final_sells}S")
            return selected
            
        except Exception as e:
            logger.error(f"❌ Error in top edge balanced selection: {e}")
            return []
    
    def _select_bottom_edge_balanced(self, positions: List[Any], size: int) -> List[Any]:
        """🔻 เลือก positions ขอบล่างแบบ BUY+SELL Balance"""
        try:
            # แยก BUY/SELL
            buy_positions = [p for p in positions if getattr(p, 'type', 0) == 0]
            sell_positions = [p for p in positions if getattr(p, 'type', 0) == 1]
            
            # เรียงตามราคา (ต่ำ→สูง)
            buy_positions.sort(key=lambda x: getattr(x, 'open_price', 0))
            sell_positions.sort(key=lambda x: getattr(x, 'open_price', 0))
            
            # เลือกแบบ Balance
            selected = []
            buy_needed = max(1, size // 2)
            sell_needed = size - buy_needed
            
            selected.extend(buy_positions[:buy_needed])
            selected.extend(sell_positions[:sell_needed])
            
            # ตรวจสอบ Balance
            final_buys = len([p for p in selected if getattr(p, 'type', 0) == 0])
            final_sells = len([p for p in selected if getattr(p, 'type', 0) == 1])
            
            if final_buys == 0 or final_sells == 0:
                logger.debug(f"❌ Bottom edge cannot create balance: {final_buys}B+{final_sells}S")
                return []
                
            logger.debug(f"🔻 Bottom edge balanced: {final_buys}B+{final_sells}S")
            return selected
            
        except Exception as e:
            logger.error(f"❌ Error in bottom edge balanced selection: {e}")
            return []
    
    def _select_mixed_edge_balanced(self, positions: List[Any], size: int) -> List[Any]:
        """🔄 เลือก positions ขอบผสมแบบ BUY+SELL Balance"""
        try:
            # แยก BUY/SELL
            buy_positions = [p for p in positions if getattr(p, 'type', 0) == 0]
            sell_positions = [p for p in positions if getattr(p, 'type', 0) == 1]
            
            # เรียงตามราคา
            buy_high = sorted(buy_positions, key=lambda x: getattr(x, 'open_price', 0), reverse=True)
            buy_low = sorted(buy_positions, key=lambda x: getattr(x, 'open_price', 0))
            sell_high = sorted(sell_positions, key=lambda x: getattr(x, 'open_price', 0), reverse=True)  
            sell_low = sorted(sell_positions, key=lambda x: getattr(x, 'open_price', 0))
            
            # เลือกแบบ Mixed Edge + Balance
            selected = []
            target_per_type = size // 4  # แบ่ง 4 ส่วน: BUY-high, BUY-low, SELL-high, SELL-low
            
            if target_per_type < 1:
                target_per_type = 1
            
            # เลือกจากแต่ละขอบ
            selected.extend(buy_high[:target_per_type])    # BUY ขอบบน
            selected.extend(buy_low[:target_per_type])     # BUY ขอบล่าง
            selected.extend(sell_high[:target_per_type])   # SELL ขอบบน
            selected.extend(sell_low[:target_per_type])    # SELL ขอบล่าง
            
            # ปรับให้ได้ขนาดที่ต้องการ
            if len(selected) > size:
                selected = selected[:size]
            
            # ตรวจสอบ Balance
            final_buys = len([p for p in selected if getattr(p, 'type', 0) == 0])
            final_sells = len([p for p in selected if getattr(p, 'type', 0) == 1])
            
            if final_buys == 0 or final_sells == 0:
                logger.debug(f"❌ Mixed edge cannot create balance: {final_buys}B+{final_sells}S")
                return []
                
            logger.debug(f"🔄 Mixed edge balanced: {final_buys}B+{final_sells}S")
            return selected
            
        except Exception as e:
            logger.error(f"❌ Error in mixed edge balanced selection: {e}")
            return []
    
    def _get_distance_category(self, distance_pips: float) -> str:
        """📏 จัดหมวดหมู่ระยะห่าง - ปรับสำหรับทองคำ"""
        if distance_pips < 3:       # < 3 pips = ใกล้มาก
            return 'near'
        elif distance_pips < 10:    # 3-10 pips = ปานกลาง
            return 'medium'
        elif distance_pips < 30:    # 10-30 pips = ไกล
            return 'far'
        else:                       # > 30 pips = ไกลมาก
            return 'very_far'
    
    def _intelligent_closing_decision(self, result: Dict, dynamic_params: Dict) -> bool:
        """🧠 การตัดสินใจปิดแบบอัจฉริยะ - ปิดไม้กำไร + ไม้ขาดทุนไกล + ไม้เก่า"""
        try:
            net_pnl = result.get('net_pnl', 0)
            positions = result.get('positions', [])
            portfolio_improvement = result.get('portfolio_improvement', {})
            
            # 🎯 SMART CLOSING STRATEGY CHECK
            if self.smart_closing_enabled:
                # ตรวจสอบว่าการปิดนี้ฉลาดหรือไม่
                if net_pnl < self.min_net_profit:
                    logger.debug(f"🚫 SMART CLOSING: Rejecting - Net P&L ${net_pnl:.2f} < ${self.min_net_profit:.2f}")
                    return False
                
                # วิเคราะห์ไม้ที่จะปิด (เฉพาะไม้กำไรและไม้เก่า)
                profitable_positions = [pos for pos in positions if getattr(pos, 'profit', 0) > 0]
                old_positions = []
                
                current_time = time.time()
                for pos in positions:
                    profit = getattr(pos, 'profit', 0)
                    open_time = getattr(pos, 'time', current_time)
                    hours_old = (current_time - open_time) / 3600
                    
                    # ไม้เก่าที่มีกำไรหรือไม่ขาดทุน
                    if hours_old > self.old_position_hours and profit >= 0:
                        old_positions.append(pos)
                
                # ตรวจสอบว่ามีไม้ที่ควรปิดหรือไม่ (เฉพาะไม้กำไรและไม้เก่า)
                has_profitable = len(profitable_positions) > 0
                has_old_positions = len(old_positions) > 0
                
                if not (has_profitable or has_old_positions):
                    logger.debug(f"🚫 SMART CLOSING: Rejecting - No profitable or old positions (no loss positions allowed)")
                    return False
                
                # ตรวจสอบว่าไม่มีไม้ขาดทุนในชุดที่จะปิด
                losing_positions = [pos for pos in positions if getattr(pos, 'profit', 0) < 0]
                if len(losing_positions) > 0:
                    logger.debug(f"🚫 SMART CLOSING: Rejecting - Contains {len(losing_positions)} losing positions (not allowed)")
                    return False
                
                logger.debug(f"✅ SMART CLOSING: Accepting - Net P&L ${net_pnl:.2f}, "
                           f"Profitable: {len(profitable_positions)}, "
                           f"Old: {len(old_positions)} (No loss positions)")
            
            # 🎯 INTELLIGENT FACTORS (ไม่ใช้เกณฑ์กำไรคงที่)
            
            # 1. 📊 Portfolio Health Impact
            health_impact = portfolio_improvement.get('pnl_improvement', 0)
            position_reduction = portfolio_improvement.get('position_reduction', 0)
            balance_improvement = portfolio_improvement.get('balance_improvement', 0)
            margin_improvement = portfolio_improvement.get('margin_improvement', 0)
            
            # 2. 🧠 Intelligent Scoring
            intelligent_score = 0
            
            # P&L Factor (ไม่ใช่เกณฑ์คงที่)
            if net_pnl > 0:
                intelligent_score += 30  # กำไร = +30 คะแนน
            elif net_pnl > -10:  # ขาดทุนเล็กน้อย
                intelligent_score += 20  # ขาดทุนเล็กน้อย = +20 คะแนน
            elif net_pnl > -50:  # ขาดทุนปานกลาง
                intelligent_score += 10  # ขาดทุนปานกลาง = +10 คะแนน
            else:
                intelligent_score -= 10  # ขาดทุนมาก = -10 คะแนน
            
            # Position Reduction Factor
            if position_reduction > 0:
                intelligent_score += min(25, position_reduction * 2)  # ลดไม้ = +25 คะแนน
            
            # Balance Improvement Factor
            if balance_improvement > 0:
                intelligent_score += min(20, balance_improvement * 5)  # ปรับสมดุล = +20 คะแนน
            
            # Margin Improvement Factor
            if margin_improvement > 0:
                intelligent_score += min(15, margin_improvement * 3)  # ปรับ margin = +15 คะแนน
            
            # 3. 🎯 Dynamic Context Analysis
            margin_level = dynamic_params.get('margin_level', 1000)
            total_positions = dynamic_params.get('total_positions', 0)
            imbalance = dynamic_params.get('imbalance', 0)
            
            # Margin Context
            if margin_level < 150:
                intelligent_score += 20  # Margin ต่ำ = +20 คะแนน
            elif margin_level < 200:
                intelligent_score += 10  # Margin ปานกลาง = +10 คะแนน
            
            # Position Count Context
            if total_positions > 50:
                intelligent_score += 15  # ไม้เยอะ = +15 คะแนน
            elif total_positions > 20:
                intelligent_score += 10  # ไม้ปานกลาง = +10 คะแนน
            
            # Imbalance Context
            if imbalance > 70:
                intelligent_score += 15  # ไม่สมดุล = +15 คะแนน
            elif imbalance > 50:
                intelligent_score += 10  # ไม่สมดุลปานกลาง = +10 คะแนน
            
            # 4. 🎯 INTELLIGENT DECISION - DYNAMIC MODE
            # ใช้ Dynamic Thresholds ที่ปรับตามสถานการณ์
            dynamic_threshold = self._calculate_dynamic_decision_threshold(result, dynamic_params)
            should_close = intelligent_score > dynamic_threshold
            
            if should_close:
                logger.info(f"🧠 INTELLIGENT DECISION: Score {intelligent_score:.1f} → CLOSE "
                           f"(P&L: ${net_pnl:.2f}, Positions: {len(positions)}, "
                           f"Health: {health_impact:.1f}, Balance: {balance_improvement:.1f})")
            else:
                logger.debug(f"🧠 INTELLIGENT DECISION: Score {intelligent_score:.1f} → HOLD "
                           f"(P&L: ${net_pnl:.2f}, Positions: {len(positions)})")
            
            return should_close
            
        except Exception as e:
            logger.error(f"❌ Error in intelligent closing decision: {e}")
            # Fallback: ปิดถ้ามีกำไร
            return result.get('net_pnl', 0) > 0
    
    def _calculate_dynamic_decision_threshold(self, result: Dict, dynamic_params: Dict) -> float:
        """🎯 คำนวณเกณฑ์การตัดสินใจแบบ Dynamic"""
        try:
            net_pnl = result.get('net_pnl', 0)
            positions_count = len(result.get('positions', []))
            health_impact = result.get('health_impact', 0)
            balance_improvement = result.get('balance_improvement', 0)
            
            # Base threshold
            base_threshold = 40.0
            
            # Adjust based on profit size
            if net_pnl > 50:
                threshold_adjustment = -15.0  # กำไรใหญ่ → เกณฑ์ต่ำลง
            elif net_pnl > 20:
                threshold_adjustment = -10.0  # กำไรปานกลาง → เกณฑ์ต่ำลง
            elif net_pnl > 5:
                threshold_adjustment = -5.0   # กำไรเล็ก → เกณฑ์ต่ำลง
            elif net_pnl > 0:
                threshold_adjustment = 0.0    # กำไรเล็กน้อย → เกณฑ์ปกติ
            else:
                threshold_adjustment = +10.0  # ไม่มีกำไร → เกณฑ์สูงขึ้น
            
            # Adjust based on position count
            if positions_count > 10:
                threshold_adjustment -= 5.0   # ไม้เยอะ → เกณฑ์ต่ำลง
            elif positions_count > 5:
                threshold_adjustment -= 2.0   # ไม้ปานกลาง → เกณฑ์ต่ำลง
            elif positions_count < 3:
                threshold_adjustment += 5.0   # ไม้น้อย → เกณฑ์สูงขึ้น
            
            # Adjust based on health impact
            if health_impact > 20:
                threshold_adjustment -= 10.0  # สุขภาพดีขึ้นมาก → เกณฑ์ต่ำลง
            elif health_impact > 10:
                threshold_adjustment -= 5.0   # สุขภาพดีขึ้น → เกณฑ์ต่ำลง
            elif health_impact < -10:
                threshold_adjustment += 10.0  # สุขภาพแย่ลง → เกณฑ์สูงขึ้น
            
            # Adjust based on balance improvement
            if balance_improvement > 5:
                threshold_adjustment -= 5.0   # ยอดเงินดีขึ้น → เกณฑ์ต่ำลง
            elif balance_improvement < -5:
                threshold_adjustment += 5.0   # ยอดเงินแย่ลง → เกณฑ์สูงขึ้น
            
            # Calculate final threshold
            final_threshold = max(20.0, min(70.0, base_threshold + threshold_adjustment))
            
            logger.debug(f"🎯 DYNAMIC THRESHOLD: {final_threshold:.1f} "
                        f"(Base: {base_threshold:.1f}, Adj: {threshold_adjustment:+.1f}, "
                        f"P&L: \${net_pnl:.2f}, Positions: {positions_count}, "
                        f"Health: {health_impact:.1f}, Balance: {balance_improvement:.1f})")
            
            return final_threshold
            
        except Exception as e:
            logger.error(f"❌ Error calculating dynamic decision threshold: {e}")
            return 40.0  # Fallback to safe threshold


def create_dynamic_7d_smart_closer(intelligent_manager=None, purpose_tracker=None, 
                                 market_analyzer=None, price_action_analyzer=None):
    """🏭 Factory function สำหรับสร้าง Dynamic 7D Smart Closer"""
    return Dynamic7DSmartCloser(intelligent_manager, purpose_tracker, market_analyzer, price_action_analyzer)


if __name__ == "__main__":
    # Demo Dynamic 7D Smart Closer
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    logger.info("🚀 Dynamic 7D Smart Closer Demo")
    logger.info("This system provides intelligent, dynamic position closing")
    logger.info("Features: Zero Loss, 7D Intelligence, Edge Clearing, Multi-Size Groups")
    logger.info("Dynamic 7D Smart Closer ready for integration!")
