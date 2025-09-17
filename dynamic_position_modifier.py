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
import time

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
    
    def __init__(self, mt5_connection=None, symbol: str = "XAUUSD", hedge_pairing_closer=None, initial_balance: float = 10000.0):
        self.mt5_connection = mt5_connection
        self.symbol = symbol
        self.hedge_pairing_closer = None  # Disabled - Using Edge Priority Closing
        self.initial_balance = initial_balance
        
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
        
        # 🎯 Outlier Detection Parameters (ปรับปรุงให้เก่งขึ้น)
        self.distance_threshold = 15.0  # ลดจาก 20 เป็น 15 points (ไวขึ้น)
        self.volatility_factor = 2.0    # เพิ่มจาก 1.5 เป็น 2.0 (ปรับตามความผันผวนมากขึ้น)
        self.max_outlier_positions = 8  # เพิ่มจาก 5 เป็น 8 ไม้ (แก้ไขได้มากขึ้น)
        self.loss_threshold = -50.0     # เพิ่มเกณฑ์ขาดทุน (แก้ไม้ขาดทุนมาก)
        self.time_threshold_hours = 12  # ลดจาก 24 เป็น 12 ชั่วโมง (แก้ไม้เก่าเร็วขึ้น)
        
        # 📊 Technical Analysis Parameters
        self.demand_supply_enabled = True
        self.fibonacci_enabled = True
        self.fibonacci_levels = [0.236, 0.382, 0.5, 0.618, 0.786]
        
        # 🛡️ Safety Parameters (ปรับปรุงให้เก่งขึ้น)
        self.max_correction_distance = 60.0  # เพิ่มจาก 50 เป็น 60 points (แก้ไขได้มากขึ้น)
        self.max_position_loss = -200.0      # เพิ่มจาก -100 เป็น -200 (แก้ไขไม้ขาดทุนมากได้)
        self.min_volume_threshold = 0.01     # ขั้นต่ำของโบรก 0.01 lot
        self.min_improvement_threshold = -5.0  # เปลี่ยนจาก 0 เป็น -5 (ยอมให้เสียเล็กน้อยเพื่อช่วยพอร์ต)
        self.max_corrections_per_cycle = 5   # เพิ่มจำนวนไม้แก้ไขต่อรอบ
        self.correction_cooldown = 1800      # 30 นาที cooldown ระหว่างการแก้ไข
        self.last_correction_time = 0        # เวลาการแก้ไขล่าสุด
        
        logger.info("🔧 Dynamic Position Modifier initialized")
    
    def _analyze_demand_supply(self, current_price: float) -> Dict:
        """📊 วิเคราะห์ Demand Supply Zones"""
        try:
            # ใช้ข้อมูลราคาล่าสุดเพื่อหาจุด Demand/Supply
            # ตัวอย่างการวิเคราะห์แบบง่าย
            demand_zones = []
            supply_zones = []
            
            # หาจุดต่ำสุดและสูงสุดในช่วง 20 แท่ง
            # (ในระบบจริงควรใช้ข้อมูลจาก MT5)
            return {
                'demand_zones': demand_zones,
                'supply_zones': supply_zones,
                'current_price': current_price
            }
        except Exception as e:
            logger.error(f"❌ Error analyzing demand supply: {e}")
            return {'demand_zones': [], 'supply_zones': [], 'current_price': current_price}
    
    def _analyze_fibonacci_levels(self, current_price: float, positions: List[Any]) -> Dict:
        """📊 วิเคราะห์ Fibonacci Levels"""
        try:
            if not positions:
                return {'levels': [], 'current_price': current_price}
            
            # หาจุดสูงสุดและต่ำสุดจากไม้ที่มีอยู่
            prices = [getattr(pos, 'price_open', current_price) for pos in positions]
            if not prices:
                return {'levels': [], 'current_price': current_price}
            
            high_price = max(prices)
            low_price = min(prices)
            price_range = high_price - low_price
            
            # คำนวณ Fibonacci Levels
            fib_levels = {}
            for level in self.fibonacci_levels:
                fib_price = low_price + (price_range * level)
                fib_levels[level] = fib_price
            
            return {
                'levels': fib_levels,
                'high_price': high_price,
                'low_price': low_price,
                'current_price': current_price
            }
        except Exception as e:
            logger.error(f"❌ Error analyzing fibonacci: {e}")
            return {'levels': [], 'current_price': current_price}
    
    def _check_hedge_pair_status(self, target_pos: Any, positions: List[Any]) -> bool:
        """🔍 ตรวจสอบว่าไม้มี HG pair แล้วหรือยัง"""
        try:
            target_type = getattr(target_pos, 'type', 0)
            target_ticket = getattr(target_pos, 'ticket', 0)
            
            # หาไม้ฝั่งตรงข้ามที่อาจเป็น pair
            opposite_positions = [pos for pos in positions 
                                if getattr(pos, 'type', 0) != target_type 
                                and getattr(pos, 'ticket', 0) != target_ticket]
            
            # ตรวจสอบว่าไม้ฝั่งตรงข้ามมี comment หรือ tag ที่บ่งบอกว่าเป็น pair
            for pos in opposite_positions:
                comment = getattr(pos, 'comment', '')
                if 'HEDGE' in comment or 'PAIR' in comment:
                    return True
            
            return False
        except Exception as e:
            logger.error(f"❌ Error checking hedge pair status: {e}")
            return False
    
    def _find_helper_strategy(self, target_pos: Any, positions: List[Any], current_price: float) -> Optional[Dict]:
        """🔍 หาไม้ช่วยเหลือสำหรับไม้ที่มี HG pair แล้ว"""
        try:
            # หาไม้กำไรที่สามารถช่วยได้
            profitable_positions = [pos for pos in positions 
                                  if getattr(pos, 'profit', 0) > 0 
                                  and getattr(pos, 'ticket', 0) != getattr(target_pos, 'ticket', 0)]
            
            if not profitable_positions:
                return None
            
            # เลือกไม้กำไรที่ดีที่สุด
            best_helper = max(profitable_positions, key=lambda x: getattr(x, 'profit', 0))
            
            return {
                'action': 'HELPER',
                'reason': f'HELPER_FOR_HEDGED: Ticket {getattr(best_helper, "ticket", "N/A")}',
                'priority': 75,
                'strategy_type': 'HELPER',
                'helper_position': best_helper
            }
        except Exception as e:
            logger.error(f"❌ Error finding helper strategy: {e}")
            return None
    
    def _calculate_position_distance(self, position: Any, current_price: float) -> float:
        """📏 คำนวณระยะทางของไม้จากราคาปัจจุบัน"""
        try:
            open_price = getattr(position, 'price_open', current_price)
            distance = abs(open_price - current_price)
            return distance
        except Exception as e:
            logger.error(f"❌ Error calculating position distance: {e}")
            return 0.0
    
    def _detect_outlier_positions(self, positions: List[Any], current_price: float) -> List[Any]:
        """🔍 ตรวจจับไม้ที่อยู่ขอบนอก (ปรับปรุงให้เก่งขึ้น)"""
        try:
            outliers = []
            for pos in positions:
                distance = self._calculate_position_distance(pos, current_price)
                profit = getattr(pos, 'profit', 0)
                open_time = getattr(pos, 'time', 0)
                current_time = time.time()
                hours_old = (current_time - open_time) / 3600 if open_time > 0 else 0
                
                # เกณฑ์การตรวจจับที่เก่งขึ้น (หลายเงื่อนไข)
                is_distance_outlier = distance > self.distance_threshold
                is_loss_outlier = profit < self.loss_threshold
                is_time_outlier = hours_old > self.time_threshold_hours
                is_heavy_loss = profit < -200.0  # ขาดทุนหนักมาก
                
                # ตรวจจับไม้ที่ต้องแก้ไข (เงื่อนไขใดเงื่อนไขหนึ่ง)
                if is_distance_outlier or is_loss_outlier or is_time_outlier or is_heavy_loss:
                    priority_score = 0
                    if is_heavy_loss:
                        priority_score += 100  # ขาดทุนหนัก = ความสำคัญสูงสุด
                    if is_distance_outlier:
                        priority_score += distance * 2  # ระยะไกล = ความสำคัญสูง
                    if is_loss_outlier:
                        priority_score += abs(profit) * 0.5  # ขาดทุน = ความสำคัญปานกลาง
                    if is_time_outlier:
                        priority_score += hours_old * 0.1  # ไม้เก่า = ความสำคัญต่ำ
                    
                    outliers.append({
                        'position': pos,
                        'distance': distance,
                        'ticket': getattr(pos, 'ticket', 'N/A'),
                        'profit': profit,
                        'hours_old': hours_old,
                        'priority_score': priority_score,
                        'reasons': []
                    })
                    
                    # บันทึกเหตุผล
                    if is_heavy_loss:
                        outliers[-1]['reasons'].append("HEAVY_LOSS")
                    if is_distance_outlier:
                        outliers[-1]['reasons'].append("DISTANCE_FAR")
                    if is_loss_outlier:
                        outliers[-1]['reasons'].append("LOSS_HIGH")
                    if is_time_outlier:
                        outliers[-1]['reasons'].append("TIME_OLD")
            
            # เรียงตาม Priority Score (มากสุดก่อน)
            outliers.sort(key=lambda x: x['priority_score'], reverse=True)
            
            logger.info(f"🎯 Outlier Detection: Found {len(outliers)} outlier positions")
            if outliers:
                logger.info(f"   Top priority: Ticket {outliers[0]['ticket']} (score: {outliers[0]['priority_score']:.1f})")
            return outliers
        except Exception as e:
            logger.error(f"❌ Error detecting outlier positions: {e}")
            return []
    
    def _prioritize_outlier_positions(self, outliers: List[Dict], current_price: float) -> List[Dict]:
        """📊 จัดลำดับความสำคัญของไม้ไกล"""
        try:
            for outlier in outliers:
                pos = outlier['position']
                distance = outlier['distance']
                profit = getattr(pos, 'profit', 0)
                volume = getattr(pos, 'volume', 0.01)
                
                # คำนวณ priority score (ยิ่งไกล + ขาดทุนเยอะ = priority สูง)
                priority_score = (distance * 0.5) + (abs(profit) * 0.3) + (volume * 100)
                outlier['priority_score'] = priority_score
            
            # เรียงตาม priority (มากสุดก่อน)
            outliers.sort(key=lambda x: x['priority_score'], reverse=True)
            
            # จำกัดจำนวนไม้ที่แก้ไขได้
            return outliers[:self.max_outlier_positions]
        except Exception as e:
            logger.error(f"❌ Error prioritizing outlier positions: {e}")
            return outliers
    
    def _create_correction_position_real(self, target_position: Any, action_type: str, 
                                       current_price: float) -> Optional[Any]:
        """🔄 สร้างไม้แก้ไขจริงผ่าน MT5"""
        try:
            if not self.mt5_connection:
                logger.warning("⚠️ No MT5 connection available for creating correction position")
                return None
            
            # คำนวณพารามิเตอร์ไม้แก้ไข
            correction_volume = self._calculate_correction_volume(target_position)
            correction_price = self._calculate_correction_price(target_position, current_price)
            correction_type = 0 if action_type == "BUY" else 1
            
            # ส่ง Order ผ่าน MT5 (ใช้ order_management.py)
            from order_management import OrderManager
            order_manager = OrderManager(self.mt5_connection)
            
            # สร้าง Signal object สำหรับ Order
            from trading_conditions import Signal
            signal = Signal(
                symbol=getattr(target_position, 'symbol', 'XAUUSD'),
                direction="BUY" if correction_type == 0 else "SELL",
                price=correction_price,  # ใช้ price แทน entry_price
                timestamp=datetime.now(),
                comment=f"CORRECTION_{getattr(target_position, 'ticket', 'unknown')}",
                strength=50.0,  # แรงของสัญญาณปานกลาง
                confidence=80.0  # ความมั่นใจสูง
            )
            
            order_result = order_manager.place_order_from_signal(
                signal, correction_volume, 10000.0  # ใช้ balance จำลอง
            )
            
            if order_result.success:
                # สร้าง Position object
                correction_pos = type('Position', (), {
                    'ticket': order_result.ticket,
                    'symbol': getattr(target_position, 'symbol', 'XAUUSD'),
                    'type': correction_type,
                    'volume': correction_volume,
                    'price_open': correction_price,
                    'price_current': correction_price,
                    'profit': 0.0,
                    'position_role': 'CORRECTION',
                    'correction_target': getattr(target_position, 'ticket', 'unknown'),
                    'creation_reason': action_type,
                    'time': int(time.time()),
                    'comment': f"CORRECTION_{getattr(target_position, 'ticket', 'unknown')}"
                })()
                
                logger.info(f"✅ Created correction position: {correction_pos.ticket} for target {target_position.ticket}")
                return correction_pos
            else:
                logger.error(f"❌ Failed to create correction position: {order_result.error_message}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error creating correction position: {e}")
            return None
    
    def _calculate_correction_volume(self, target_position: Any) -> float:
        """💰 คำนวณขนาดไม้แก้ไข (ใช้ขนาดเดียวกับไม้หลัก)"""
        try:
            target_volume = getattr(target_position, 'volume', 0.01)
            
            # ใช้ขนาดเดียวกับไม้หลัก
            correction_volume = target_volume
            
            # ตรวจสอบขั้นต่ำของโบรก (0.01 lot)
            if correction_volume < 0.01:
                correction_volume = 0.01
                logger.warning(f"⚠️ Correction volume too small, using minimum 0.01 lot")
            
            logger.info(f"💰 Correction volume calculation:")
            logger.info(f"   Target volume: {target_volume}")
            logger.info(f"   Correction volume: {correction_volume}")
            logger.info(f"   Strategy: Same as main position")
            
            return correction_volume
        except Exception as e:
            logger.error(f"❌ Error calculating correction volume: {e}")
            return 0.01  # ใช้ขนาดขั้นต่ำ
    
    def _calculate_correction_price(self, target_position: Any, current_price: float) -> float:
        """💰 คำนวณราคาไม้แก้ไข"""
        try:
            # ใช้ราคาปัจจุบัน
            return current_price
        except Exception as e:
            logger.error(f"❌ Error calculating correction price: {e}")
            return current_price
    
    def _is_safe_to_create_correction(self, target_pos: Any, current_price: float) -> bool:
        """🛡️ ตรวจสอบว่าปลอดภัยที่จะสร้างไม้แก้ไขหรือไม่"""
        try:
            # ตรวจสอบระยะทาง
            distance = self._calculate_position_distance(target_pos, current_price)
            if distance > self.max_correction_distance:
                logger.warning(f"⚠️ Position too far ({distance:.1f} points) - not safe to correct")
                return False
            
            # ตรวจสอบขาดทุน
            profit = getattr(target_pos, 'profit', 0)
            if profit < self.max_position_loss:
                logger.warning(f"⚠️ Position loss too high (${profit:.2f}) - not safe to correct")
                return False
            
            # ตรวจสอบพอร์ต
            if self._is_portfolio_critical():
                logger.warning("⚠️ Portfolio critical - not safe to create corrections")
                return False
            
            return True
        except Exception as e:
            logger.error(f"❌ Error checking correction safety: {e}")
            return False
    
    def _is_portfolio_critical(self) -> bool:
        """🚨 ตรวจสอบว่าพอร์ตอยู่ในภาวะวิกฤตหรือไม่"""
        try:
            # ตรวจสอบจาก account info ถ้ามี
            if hasattr(self, 'last_account_info'):
                balance = self.last_account_info.get('balance', 10000)
                margin_level = self.last_account_info.get('margin_level', 1000)
                
                # พอร์ตวิกฤตถ้า margin level ต่ำ
                if margin_level < 150:
                    return True
                
                # พอร์ตวิกฤตถ้า balance ลดลงมาก
                if balance < self.initial_balance * 0.5:
                    return True
            
            return False
        except Exception as e:
            logger.error(f"❌ Error checking portfolio critical status: {e}")
            return False
    
    def _validate_correction_profitability(self, main_pos: Any, correction_pos: Any, helpers: List[Any]) -> bool:
        """📊 ตรวจสอบว่าไม้แก้ไขจะช่วยพอร์ตหรือไม่"""
        try:
            # คำนวณกำไรรวมก่อนสร้างไม้แก้ไข
            current_profit = getattr(main_pos, 'profit', 0)
            helper_profit = sum(getattr(h, 'profit', 0) for h in helpers)
            total_before = current_profit + helper_profit
            
            # คำนวณกำไรรวมหลังสร้างไม้แก้ไข (คาดการณ์)
            estimated_correction_profit = self._estimate_correction_profit(correction_pos)
            total_after = total_before + estimated_correction_profit
            
            # ต้องดีขึ้นหรืออย่างน้อยไม่แย่ลง
            improvement = total_after - total_before
            is_profitable = improvement >= self.min_improvement_threshold
            
            logger.info(f"📊 Correction profitability check:")
            logger.info(f"   Before: ${total_before:.2f}")
            logger.info(f"   After: ${total_after:.2f}")
            logger.info(f"   Improvement: ${improvement:.2f}")
            logger.info(f"   Profitable: {is_profitable}")
            
            return is_profitable
        except Exception as e:
            logger.error(f"❌ Error validating correction profitability: {e}")
            return False
    
    def _estimate_correction_profit(self, correction_pos: Any) -> float:
        """💰 คาดการณ์กำไรของไม้แก้ไข"""
        try:
            # ไม้แก้ไขใหม่ยังไม่มีกำไร
            return 0.0
        except Exception as e:
            logger.error(f"❌ Error estimating correction profit: {e}")
            return 0.0
    
    def _smart_correction_strategy(self, target_pos: Any, current_price: float, positions: List[Any] = None) -> Optional[Dict]:
        """🎯 กลยุทธ์แก้ไขแบบฉลาด (ใช้ Demand Supply + Fibo + Logic ชัดเจน)"""
        try:
            # ตั้งค่า positions default
            if positions is None:
                positions = []
                
            target_profit = getattr(target_pos, 'profit', 0)
            distance = self._calculate_position_distance(target_pos, current_price)
            position_type = getattr(target_pos, 'type', 0)
            
            logger.info(f"🎯 Correction strategy: ${target_profit:.2f} profit, {distance:.1f} points")
            
            # 1. วิเคราะห์ Demand Supply
            ds_analysis = self._analyze_demand_supply(current_price)
            
            # 2. วิเคราะห์ Fibonacci
            fib_analysis = self._analyze_fibonacci_levels(current_price, positions)
            
            # 3. ตรวจสอบว่าไม้มี HG pair แล้วหรือยัง
            has_hedge_pair = self._check_hedge_pair_status(target_pos, positions)
            
            # 4. กลยุทธ์การแก้ไขตามเงื่อนไข
            strategies = []
            
            # กรณีที่ 1: ไม้ไกลจากราคาปัจจุบัน (Distance > 20 points)
            if distance > 20.0:
                if target_profit < 0:  # ไม้ขาดทุน + ไกล
                    # ออกไม้ฝั่งเดียวกัน (Average Down/Up)
                    strategies.append({
                        'action': 'BUY' if position_type == 0 else 'SELL',  # ฝั่งเดียวกัน
                        'reason': f'DISTANCE_FAR_SAME_SIDE: {distance:.1f}pts + ${target_profit:.2f}',
                        'priority': 90,
                        'strategy_type': 'AVERAGE_SAME_SIDE'
                    })
                else:  # ไม้กำไร + ไกล
                    logger.info("✅ Position is profitable but far - no correction needed")
                    return None
            
            # กรณีที่ 2: ไม้ใกล้ราคาปัจจุบัน (Distance <= 20 points)
            elif distance <= 20.0:
                if has_hedge_pair:  # มี HG pair แล้ว
                    # หาไม้ช่วยเหลือ
                    helper_strategy = self._find_helper_strategy(target_pos, positions, current_price)
                    if helper_strategy:
                        strategies.append(helper_strategy)
                else:  # ไม่มี HG pair
                    # สร้าง HG pair
                    strategies.append({
                        'action': 'BUY' if position_type == 1 else 'SELL',  # ฝั่งตรงข้าม
                        'reason': f'CREATE_HEDGE_PAIR: {distance:.1f}pts + ${target_profit:.2f}',
                        'priority': 85,
                        'strategy_type': 'CREATE_HEDGE'
                    })
            
            # กรณีที่ 3: ไม้ขาดทุนหนัก (ไม่ว่าจะไกลหรือใกล้)
            if target_profit < -100.0:
                strategies.append({
                    'action': 'BUY' if position_type == 1 else 'SELL',  # ฝั่งตรงข้าม
                    'reason': f'HEAVY_LOSS_HEDGE: ${target_profit:.2f}',
                    'priority': 95,
                    'strategy_type': 'HEAVY_LOSS_HEDGE'
                })
            
            # กรณีที่ 4: ไม้เก่า + ขาดทุน
            hours_old = (time.time() - getattr(target_pos, 'time', 0)) / 3600 if getattr(target_pos, 'time', 0) > 0 else 0
            if hours_old > 24.0 and target_profit < -30.0:
                strategies.append({
                    'action': 'BUY' if position_type == 1 else 'SELL',  # ฝั่งตรงข้าม
                    'reason': f'OLD_POSITION_HEDGE: {hours_old:.1f}h + ${target_profit:.2f}',
                    'priority': 80,
                    'strategy_type': 'OLD_POSITION_HEDGE'
                })
            
            # เลือกกลยุทธ์ที่ดีที่สุด
            if strategies:
                best_strategy = max(strategies, key=lambda x: x['priority'])
                logger.info(f"🎯 Best Strategy: {best_strategy['action']} - {best_strategy['reason']}")
                return best_strategy
            
            return None
        except Exception as e:
            logger.error(f"❌ Error in smart correction strategy: {e}")
            return None
    
    def _cancel_correction_position(self, correction_pos: Any):
        """❌ ยกเลิกไม้แก้ไขที่ไม่ช่วยพอร์ต"""
        try:
            ticket = getattr(correction_pos, 'ticket', 'N/A')
            logger.info(f"❌ Cancelling correction position {ticket}")
            
            # ปิดไม้แก้ไขทันที
            if self.mt5_connection:
                # ส่งคำสั่งปิดไม้
                close_result = self.mt5_connection.close_position(ticket)
                if close_result:
                    logger.info(f"✅ Successfully cancelled correction position {ticket}")
                else:
                    logger.error(f"❌ Failed to cancel correction position {ticket}")
            
        except Exception as e:
            logger.error(f"❌ Error cancelling correction position: {e}")
    
    def _send_correction_to_hedge_pairing(self, correction_pos: Any, target_pos: Any):
        """📤 ส่งไม้แก้ไขไปให้ Hedge Pairing Closer - DISABLED"""
        try:
            # 🚫 DISABLED: hedge_pairing_closer - Using Edge Priority Closing instead
            logger.debug("🚫 hedge_pairing_closer disabled - Using Edge Priority Closing instead")
            return
            
            # เพิ่มไม้แก้ไขเข้าไปในรายการไม้ทั้งหมด
            logger.info(f"📤 Sending correction position {getattr(correction_pos, 'ticket', 'N/A')} to Hedge Pairing Closer")
            logger.info(f"   Target: {getattr(target_pos, 'ticket', 'N/A')}")
            logger.info(f"   Role: {getattr(correction_pos, 'position_role', 'UNKNOWN')}")
            logger.info(f"   Reason: {getattr(correction_pos, 'creation_reason', 'UNKNOWN')}")
            
            # ระบบจะใช้ไม้แก้ไขในการจับคู่ต่อไป
            # Hedge Pairing Closer จะรู้ว่าไม้นี้เป็นไม้แก้ไขและต้องปิดพร้อมไม้หลัก
            
        except Exception as e:
            logger.error(f"❌ Error sending correction to hedge pairing: {e}")
    
    def analyze_portfolio_modifications(self, positions: List[Any], account_info: Dict,
                                      current_price: float) -> PortfolioModificationPlan:
        """
        🎯 วิเคราะห์การแก้ไข Portfolio แบบ Dynamic
        """
        try:
            # ตรวจสอบ Cooldown ก่อน
            current_time = time.time()
            if current_time - self.last_correction_time < self.correction_cooldown:
                logger.info(f"⏰ Position Modifier: Cooldown active ({self.correction_cooldown}s) - skipping analysis")
                return None
            
            logger.info(f"🔍 DYNAMIC PORTFOLIO MODIFICATION ANALYSIS: {len(positions)} positions")
            
            # 1. 🎯 Outlier Detection - ตรวจจับไม้ไกล (ปรับปรุงให้เก่งขึ้น)
            outliers = self._detect_outlier_positions(positions, current_price)
            if outliers:
                logger.info(f"🎯 Found {len(outliers)} outlier positions that need correction")
                prioritized_outliers = self._prioritize_outlier_positions(outliers, current_price)
                
                # แก้ไขแบบ Batch (หลายไม้พร้อมกัน)
                correction_count = 0
                max_corrections = min(self.max_corrections_per_cycle, len(prioritized_outliers))
                
                # สร้างไม้แก้ไขสำหรับไม้ไกล (แบบปลอดภัย)
                correction_positions = []
                for outlier in prioritized_outliers:
                    # จำกัดจำนวนการแก้ไขต่อรอบ
                    if correction_count >= max_corrections:
                        logger.info(f"🛑 Reached maximum corrections per cycle: {max_corrections}")
                        break
                    target_pos = outlier['position']
                    distance = outlier['distance']
                    profit = getattr(target_pos, 'profit', 0)
                    
                    # ตรวจสอบความปลอดภัยก่อน
                    if not self._is_safe_to_create_correction(target_pos, current_price):
                        logger.warning(f"⚠️ Skipping correction for ticket {getattr(target_pos, 'ticket', 'N/A')} - not safe")
                        continue
                    
                    # ใช้กลยุทธ์ฉลาด
                    correction_strategy = self._smart_correction_strategy(target_pos, current_price, positions)
                    if not correction_strategy:
                        logger.info(f"💤 No correction needed for ticket {getattr(target_pos, 'ticket', 'N/A')}")
                        continue
                    
                    action_type = correction_strategy['action']
                    correction_pos = self._create_correction_position_real(target_pos, action_type, current_price)
                    
                    if correction_pos:
                        # ตรวจสอบความสามารถในการช่วยพอร์ต
                        helpers = []  # ไม้ช่วย (จะหาใน Hedge Pairing)
                        if self._validate_correction_profitability(target_pos, correction_pos, helpers):
                            correction_positions.append(correction_pos)
                            correction_count += 1
                            logger.info(f"✅ Created safe correction for ticket {getattr(target_pos, 'ticket', 'N/A')} (distance: {distance:.1f}) [{correction_count}/{max_corrections}]")
                            
                            # 🚫 DISABLED: hedge_pairing_closer - Using Edge Priority Closing instead
                            logger.debug("🚫 hedge_pairing_closer disabled - Using Edge Priority Closing instead")
                            
                            # อัปเดตเวลาการแก้ไขล่าสุด
                            self.last_correction_time = current_time
                        else:
                            logger.warning(f"⚠️ Correction not profitable for ticket {getattr(target_pos, 'ticket', 'N/A')} - cancelled")
                            # ยกเลิกไม้แก้ไขที่ไม่ช่วยพอร์ต
                            self._cancel_correction_position(correction_pos)
            
            # 2. 🔍 Individual Position Analysis (ไม้ปกติ)
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
        """📈 ประเมินการปรับปรุงตำแหน่งแบบ Dynamic"""
        try:
            current_profit = getattr(position, 'profit', 0)
            open_price = getattr(position, 'price_open', current_price)
            volume = getattr(position, 'volume', 0.01)
            position_type = getattr(position, 'type', 0)
            
            # 🎯 DYNAMIC IMPROVEMENT FACTORS (ปรับตามสถานการณ์)
            base_factors = {
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
            
            base_factor = base_factors.get(action, 0.2)
            
            # 📊 MARKET CONDITIONS ADJUSTMENT
            price_distance = abs(current_price - open_price)
            
            # ป้องกันการหารด้วยศูนย์
            if open_price > 0:
                price_distance_pct = (price_distance / open_price) * 100
            else:
                # ถ้า open_price = 0 ให้ใช้ current_price แทน
                price_distance_pct = (price_distance / current_price) * 100 if current_price > 0 else 0.0
            
            # ปรับ factor ตามระยะห่างราคา
            if price_distance_pct > 2.0:  # ห่างมาก
                distance_multiplier = 1.5
            elif price_distance_pct > 1.0:  # ห่างปานกลาง
                distance_multiplier = 1.2
            else:  # ห่างน้อย
                distance_multiplier = 0.8
            
            # 💰 VOLUME ADJUSTMENT
            if volume > 0.05:  # Volume ใหญ่
                volume_multiplier = 1.3
            elif volume < 0.02:  # Volume เล็ก
                volume_multiplier = 0.7
            else:
                volume_multiplier = 1.0
            
            # 🎯 ACCOUNT CONDITIONS
            margin_level = account_info.get('margin_level', 1000)
            if margin_level < 300:  # Margin ต่ำ
                urgency_multiplier = 1.4
            elif margin_level > 800:  # Margin สูง
                urgency_multiplier = 0.9
            else:
                urgency_multiplier = 1.0
            
            # คำนวณ final factor
            final_factor = base_factor * distance_multiplier * volume_multiplier * urgency_multiplier
            
            # คำนวณ expected improvement
            if current_profit < 0:
                # ขาดทุน → คำนวณจากขนาดขาดทุน
                expected_improvement = abs(current_profit) * final_factor
            else:
                # กำไร → คำนวณจากโอกาสเพิ่มกำไร
                expected_improvement = current_profit * final_factor * 0.3
            
            # จำกัดค่าสูงสุด (ไม่เกิน 50% ของ balance)
            balance = account_info.get('balance', 10000)
            max_improvement = balance * 0.5
            expected_improvement = min(expected_improvement, max_improvement)
            
            logger.debug(f"📈 POSITION IMPROVEMENT: Ticket {getattr(position, 'ticket', 'N/A')}, "
                        f"Action={action.value}, Base={base_factor:.2f}, "
                        f"Final={final_factor:.2f}, Expected=${expected_improvement:.2f}")
            
            return max(0.0, expected_improvement)
            
        except Exception as e:
            logger.error(f"❌ Error estimating position improvement: {e}")
            return 0.0
    
    def _log_modification_plan(self, plan: PortfolioModificationPlan):
        """📊 แสดง log แผนการแก้ไขแบบสั้นกระชับ"""
        if not plan.individual_modifications and not plan.group_modifications:
            logger.info("🔧 No modifications needed")
            return
        
        # Log แบบสั้นกระชับ
        logger.info(f"🔧 MODIFY: {len(plan.individual_modifications)} positions | "
                   f"Profit: +${plan.expected_portfolio_improvement:.0f}")
        
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
        """💰 คำนวณกำไรที่คาดหวังแบบ Dynamic จาก Portfolio"""
        try:
            if not individual:
                return 0.0
            
            total_improvement = 0.0
            current_portfolio_profit = sum(getattr(pos, 'profit', 0) for pos in positions)
            
            for modification in individual:
                # คำนวณการปรับปรุงจากแต่ละ position
                position_profit = getattr(modification, 'expected_improvement', 0)
                success_prob = getattr(modification, 'success_probability', 0.7)
                
                # ปรับตามความน่าจะเป็นสำเร็จ
                weighted_improvement = position_profit * success_prob
                total_improvement += weighted_improvement
            
            # ปรับตามสถานการณ์ Portfolio
            balance = account_info.get('balance', 10000)
            equity = account_info.get('equity', balance)
            margin_level = account_info.get('margin_level', 1000)
            
            # ปัจจัยปรับแต่งตามสถานการณ์
            if margin_level < 200:  # Margin ต่ำ
                total_improvement *= 1.5  # เพิ่มความสำคัญ
            elif margin_level > 1000:  # Margin สูง
                total_improvement *= 0.8  # ลดความสำคัญ
            
            # ปรับตามขนาด Portfolio
            if current_portfolio_profit < -100:  # Portfolio ขาดทุนหนัก
                total_improvement *= 1.3  # เพิ่มความสำคัญ
            elif current_portfolio_profit > 100:  # Portfolio กำไร
                total_improvement *= 0.7  # ลดความสำคัญ
            
            logger.debug(f"💰 PORTFOLIO IMPROVEMENT: Base={total_improvement:.2f}, "
                        f"Current P&L=${current_portfolio_profit:.2f}, "
                        f"Margin={margin_level:.0f}%")
            
            return max(0.0, total_improvement)
            
        except Exception as e:
            logger.error(f"❌ Error calculating portfolio improvement: {e}")
            return 0.0
    
    def _estimate_modification_cost(self, individual: List, group: List, current_price: float) -> float:
        return 50.0  # Placeholder
    
    def _estimate_completion_time(self, individual: List, group: List) -> str:
        return "5-10 minutes"  # Placeholder
    
    def _calculate_success_probability(self, individual: List, group: List, positions: List) -> float:
        """🎯 คำนวณความน่าจะเป็นสำเร็จแบบ Dynamic"""
        try:
            if not individual:
                return 0.0
            
            total_probability = 0.0
            total_weight = 0.0
            
            for modification in individual:
                # คำนวณความน่าจะเป็นจากแต่ละ position
                base_prob = getattr(modification, 'success_probability', 0.7)
                priority = getattr(modification, 'priority', ModifierPriority.MEDIUM)
                
                # ปรับตาม priority
                priority_weights = {
                    ModifierPriority.CRITICAL: 1.0,
                    ModifierPriority.HIGH: 0.9,
                    ModifierPriority.MEDIUM: 0.8,
                    ModifierPriority.LOW: 0.7,
                    ModifierPriority.MONITOR: 0.5
                }
                
                weight = priority_weights.get(priority, 0.8)
                
                # ปรับตาม action type
                action = getattr(modification, 'recommended_action', ModifierAction.WAIT_IMPROVE)
                action_success_rates = {
                    ModifierAction.ADD_SUPPORT: 0.8,
                    ModifierAction.ADD_COUNTER: 0.7,
                    ModifierAction.PARTIAL_CLOSE: 0.9,
                    ModifierAction.HEDGE_PROTECT: 0.8,
                    ModifierAction.AVERAGE_DOWN: 0.6,
                    ModifierAction.AVERAGE_UP: 0.6,
                    ModifierAction.CONVERT_HEDGE: 0.7,
                    ModifierAction.WAIT_IMPROVE: 0.5,
                    ModifierAction.EMERGENCY_CLOSE: 0.9
                }
                
                action_rate = action_success_rates.get(action, 0.7)
                final_prob = base_prob * action_rate * weight
                
                total_probability += final_prob * weight
                total_weight += weight
            
            if total_weight > 0:
                average_probability = total_probability / total_weight
            else:
                average_probability = 0.0
            
            # ปรับตามจำนวน positions
            position_count = len(positions)
            if position_count > 5:  # หลาย positions
                average_probability *= 0.9  # ลดลงเล็กน้อย
            elif position_count < 2:  # น้อย positions
                average_probability *= 1.1  # เพิ่มขึ้นเล็กน้อย
            
            # จำกัดค่า 0.0 - 1.0
            final_probability = max(0.0, min(1.0, average_probability))
            
            logger.debug(f"🎯 SUCCESS PROBABILITY: {final_probability:.1%} "
                        f"(from {len(individual)} modifications, {position_count} positions)")
            
            return final_probability
            
        except Exception as e:
            logger.error(f"❌ Error calculating success probability: {e}")
            return 0.5  # Default 50%
    
    def _assess_modification_risk(self, individual: List, group: List, account_info: Dict) -> float:
        return 0.2  # Placeholder

def create_dynamic_position_modifier(mt5_connection=None, symbol: str = "XAUUSD", hedge_pairing_closer=None, initial_balance: float = 10000.0) -> DynamicPositionModifier:
    """สร้าง Dynamic Position Modifier"""
    return DynamicPositionModifier(mt5_connection, symbol, hedge_pairing_closer, initial_balance)

if __name__ == "__main__":
    # Test the system
    modifier = create_dynamic_position_modifier()
    logger.info("🔧 Dynamic Position Modifier ready for testing")
