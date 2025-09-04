# -*- coding: utf-8 -*-
"""
Advanced Breakout Recovery System
ระบบ Recovery แบบ Triple Position หลัง Breakout อย่างชาญฉลาด
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from calculations import Position

logger = logging.getLogger(__name__)

class BreakoutType(Enum):
    BULLISH = "BULLISH"      # ราคาทะลุขึ้น
    BEARISH = "BEARISH"      # ราคาทะลุลง
    NONE = "NONE"            # ไม่มี breakout

class RecoveryPhase(Enum):
    WAITING = "WAITING"                    # รอ breakout
    NEW_POSITION_OPENED = "NEW_POSITION_OPENED"  # เปิดไม้ใหม่แล้ว
    WAITING_PROFIT = "WAITING_PROFIT"      # รอไม้ใหม่มีกำไร
    READY_FOR_RECOVERY = "READY_FOR_RECOVERY"  # พร้อมทำ triple recovery
    COMPLETED = "COMPLETED"                # เสร็จสิ้น

@dataclass
class BreakoutLevel:
    price: float
    position: Position
    position_type: str  # "BUY" or "SELL"
    is_extreme: bool    # True ถ้าเป็นไม้สุดขั้ว (สูงสุด/ต่ำสุด)

@dataclass
class TripleRecoveryGroup:
    breakout_id: str
    breakout_type: BreakoutType
    breakout_price: float
    breakout_time: datetime
    phase: RecoveryPhase
    
    # Positions ที่เกี่ยวข้อง
    old_position: Position          # ไม้เก่าที่ breakout ผ่าน
    new_position: Optional[Position] = None  # ไม้ใหม่หลัง breakout
    target_recovery: Optional[Position] = None  # ไม้เก่าฝั่งตรงข้ามที่จะปิดด้วย
    
    # การตั้งค่า
    min_new_profit: float = 1.0     # กำไรขั้นต่ำของไม้ใหม่ (pips) - ยืดหยุ่นมาก
    min_net_profit: float = 0.5     # กำไรสุทธิขั้นต่ำก่อนปิด (pips) - ยืดหยุ่นมาก
    max_wait_time: int = 900        # รอสูงสุด 15 นาที (ลดลงเพื่อความยืดหยุ่น)
    
    # สถิติ
    created_time: datetime = field(default_factory=datetime.now)
    last_check_time: Optional[datetime] = None
    profit_history: List[float] = field(default_factory=list)

class AdvancedBreakoutRecovery:
    """ระบบ Recovery แบบ Triple Position หลัง Breakout"""
    
    def __init__(self, mt5_connection):
        self.mt5 = mt5_connection
        self.active_recoveries: Dict[str, TripleRecoveryGroup] = {}
        self.completed_recoveries: List[TripleRecoveryGroup] = []
        
        # การตั้งค่า
        self.breakout_threshold = 0.3      # 3 pips สำหรับ XAUUSD (แม่นยำขึ้น)
        self.position_age_threshold = 300   # 5 นาที
        self.max_concurrent_recoveries = 3  # สูงสุด 3 recovery พร้อมกัน
        
    def analyze_breakout_levels(self, positions: List[Position], current_price: float) -> Dict[str, Any]:
        """วิเคราะห์ระดับ breakout อย่างแม่นยำ"""
        try:
            if not positions:
                return {'has_levels': False, 'reason': 'ไม่มี positions'}
            
            # แยกประเภท positions
            buy_positions = [pos for pos in positions if pos.type == 0]
            sell_positions = [pos for pos in positions if pos.type == 1]
            
            if not buy_positions or not sell_positions:
                return {'has_levels': False, 'reason': 'ไม่มีทั้ง BUY และ SELL positions'}
            
            # หา extreme levels
            buy_levels = self._find_extreme_positions(buy_positions, "BUY")
            sell_levels = self._find_extreme_positions(sell_positions, "SELL")
            
            # ตรวจสอบ hierarchy violation
            max_buy = max(level.price for level in buy_levels)
            min_sell = min(level.price for level in sell_levels)
            
            is_overlapping = max_buy >= min_sell
            
            if not is_overlapping:
                return {
                    'has_levels': False, 
                    'reason': 'Price hierarchy ปกติ',
                    'max_buy': max_buy,
                    'min_sell': min_sell
                }
            
            # วิเคราะห์ breakout potential
            analysis = {
                'has_levels': True,
                'is_overlapping': True,
                'current_price': current_price,
                'max_buy': max_buy,
                'min_sell': min_sell,
                'buy_levels': buy_levels,
                'sell_levels': sell_levels,
                'breakout_analysis': self._analyze_breakout_potential(
                    current_price, buy_levels, sell_levels
                )
            }
            
            logger.info(f"📊 Breakout Levels Analysis:")
            logger.info(f"   Current Price: {current_price}")
            logger.info(f"   Max BUY Level: {max_buy}")
            logger.info(f"   Min SELL Level: {min_sell}")
            logger.info(f"   Overlapping: {is_overlapping}")
            logger.info(f"   BUY Levels: {len(buy_levels)}, SELL Levels: {len(sell_levels)}")
            
            # เพิ่ม reason สำหรับกรณี has_levels = True
            analysis['reason'] = f"Price hierarchy overlapping - analyzing breakout potential"
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing breakout levels: {e}")
            return {'has_levels': False, 'reason': f'เกิดข้อผิดพลาด: {str(e)}'}
    
    def _find_extreme_positions(self, positions: List[Position], pos_type: str) -> List[BreakoutLevel]:
        """หา positions ที่เป็นจุดสุดขั้ว"""
        try:
            if not positions:
                return []
            
            # เรียงตามราคา
            if pos_type == "BUY":
                # BUY: เรียงจากสูงไปต่ำ (สนใจไม้ที่สูงที่สุด)
                sorted_positions = sorted(positions, key=lambda x: x.price_open, reverse=True)
            else:
                # SELL: เรียงจากต่ำไปสูง (สนใจไม้ที่ต่ำที่สุด)
                sorted_positions = sorted(positions, key=lambda x: x.price_open)
            
            levels = []
            
            # หาไม้สุดขั้ว (top 3 positions)
            for i, pos in enumerate(sorted_positions[:3]):
                is_extreme = i == 0  # ไม้แรกเป็นสุดขั้ว
                
                level = BreakoutLevel(
                    price=pos.price_open,
                    position=pos,
                    position_type=pos_type,
                    is_extreme=is_extreme
                )
                levels.append(level)
            
            return levels
            
        except Exception as e:
            logger.error(f"Error finding extreme positions: {e}")
            return []
    
    def _analyze_breakout_potential(self, current_price: float, 
                                  buy_levels: List[BreakoutLevel],
                                  sell_levels: List[BreakoutLevel]) -> Dict[str, Any]:
        """วิเคราะห์โอกาสการ breakout"""
        try:
            # หาระดับสุดขั้ว
            max_buy_level = max(buy_levels, key=lambda x: x.price) if buy_levels else None
            min_sell_level = min(sell_levels, key=lambda x: x.price) if sell_levels else None
            
            if not max_buy_level or not min_sell_level:
                return {'potential': 'NONE', 'reason': 'ไม่มีระดับสุดขั้ว'}
            
            # คำนวณระยะห่าง
            distance_to_max_buy = abs(current_price - max_buy_level.price)
            distance_to_min_sell = abs(current_price - min_sell_level.price)
            
            analysis = {
                'max_buy_level': max_buy_level,
                'min_sell_level': min_sell_level,
                'distance_to_max_buy': distance_to_max_buy,
                'distance_to_min_sell': distance_to_min_sell,
                'breakout_threshold': self.breakout_threshold
            }
            
            # ตรวจสอบการ breakout พร้อมกำหนดกลยุทธ์การออกไม้
            if current_price > max_buy_level.price + self.breakout_threshold:
                # ทะลุขึ้นแล้ว - ตรวจสอบประเภทไม้ที่ถูกเบรค
                breakout_position_type = max_buy_level.position.type  # 0=BUY, 1=SELL
                
                if breakout_position_type == 0:  # BUY ถูกเบรค
                    # BUY ถูกเบรคขึ้น → รอแรงตลาด แล้วออก SELL ตรงข้าม
                    counter_action = 'WAIT_MARKET_STRENGTH_THEN_SELL'
                else:  # SELL ถูกเบรค  
                    # SELL ถูกเบรคขึ้น → ออกตามเงื่อนไขปกติ
                    counter_action = 'OPEN_SELL_NORMAL'
                
                analysis.update({
                    'potential': 'BULLISH_BREAKOUT',
                    'breakout_level': max_buy_level,
                    'breakout_position_type': 'BUY' if breakout_position_type == 0 else 'SELL',
                    'target_recovery_level': min_sell_level,
                    'recommended_action': counter_action,
                    'counter_trade_direction': 'SELL'
                })
            elif current_price < min_sell_level.price - self.breakout_threshold:
                # ทะลุลงแล้ว - ตรวจสอบประเภทไม้ที่ถูกเบรค
                breakout_position_type = min_sell_level.position.type  # 0=BUY, 1=SELL
                
                if breakout_position_type == 1:  # SELL ถูกเบรค
                    # SELL ถูกเบรคลง → รอแรงตลาด แล้วออก BUY ตรงข้าม
                    counter_action = 'WAIT_MARKET_STRENGTH_THEN_BUY'
                else:  # BUY ถูกเบรค
                    # BUY ถูกเบรคลง → ออกตามเงื่อนไขปกติ
                    counter_action = 'OPEN_BUY_NORMAL'
                
                analysis.update({
                    'potential': 'BEARISH_BREAKOUT',
                    'breakout_level': min_sell_level,
                    'breakout_position_type': 'SELL' if breakout_position_type == 1 else 'BUY',
                    'target_recovery_level': max_buy_level,
                    'recommended_action': counter_action,
                    'counter_trade_direction': 'BUY'
                })
            elif distance_to_max_buy <= self.breakout_threshold:
                # ใกล้จะทะลุขึ้น
                analysis.update({
                    'potential': 'APPROACHING_BULLISH',
                    'breakout_level': max_buy_level,
                    'target_recovery_level': min_sell_level,
                    'recommended_action': 'WAIT_FOR_BULLISH_BREAKOUT'
                })
            elif distance_to_min_sell <= self.breakout_threshold:
                # ใกล้จะทะลุลง
                analysis.update({
                    'potential': 'APPROACHING_BEARISH',
                    'breakout_level': min_sell_level,
                    'target_recovery_level': max_buy_level,
                    'recommended_action': 'WAIT_FOR_BEARISH_BREAKOUT'
                })
            else:
                # อยู่ตรงกลาง
                analysis.update({
                    'potential': 'CONSOLIDATION',
                    'recommended_action': 'WAIT_AND_MONITOR'
                })
            
            logger.debug(f"🎯 Breakout Potential Analysis: {analysis.get('potential', 'UNKNOWN')}")
            logger.debug(f"   Distance to Max BUY: {distance_to_max_buy:.2f} pips")
            logger.debug(f"   Distance to Min SELL: {distance_to_min_sell:.2f} pips")
            logger.debug(f"   Breakout Threshold: {self.breakout_threshold:.2f} pips")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing breakout potential: {e}")
            return {'potential': 'ERROR', 'reason': str(e)}
    
    def create_recovery_group(self, breakout_analysis: Dict[str, Any], current_price: float) -> Optional[str]:
        """สร้างกลุ่ม Triple Recovery"""
        try:
            potential = breakout_analysis.get('potential')
            
            if potential not in ['BULLISH_BREAKOUT', 'BEARISH_BREAKOUT']:
                return None
            
            # ตรวจสอบจำนวน recovery ที่ active
            if len(self.active_recoveries) >= self.max_concurrent_recoveries:
                logger.warning(f"มี recovery active เต็มแล้ว ({self.max_concurrent_recoveries})")
                return None
            
            # สร้าง recovery group
            breakout_id = f"recovery_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            breakout_type = BreakoutType.BULLISH if potential == 'BULLISH_BREAKOUT' else BreakoutType.BEARISH
            breakout_level = breakout_analysis['breakout_level']
            target_recovery_level = breakout_analysis['target_recovery_level']
            
            recovery_group = TripleRecoveryGroup(
                breakout_id=breakout_id,
                breakout_type=breakout_type,
                breakout_price=current_price,
                breakout_time=datetime.now(),
                phase=RecoveryPhase.WAITING,
                old_position=breakout_level.position,
                target_recovery=target_recovery_level.position
            )
            
            self.active_recoveries[breakout_id] = recovery_group
            
            logger.info(f"🎯 สร้าง Recovery Group: {breakout_id}")
            logger.info(f"   Type: {breakout_type.value}")
            logger.info(f"   Breakout Price: {current_price}")
            logger.info(f"   Old Position: {breakout_level.position.ticket} ({breakout_level.position_type})")
            logger.info(f"   Target Recovery: {target_recovery_level.position.ticket} ({target_recovery_level.position_type})")
            
            return breakout_id
            
        except Exception as e:
            logger.error(f"Error creating recovery group: {e}")
            return None
    
    def update_recovery_groups(self, current_price: float, positions: List[Position]) -> Dict[str, Any]:
        """อัพเดทสถานะของ recovery groups"""
        try:
            results = {
                'updated_groups': 0,
                'ready_for_recovery': [],
                'completed_groups': [],
                'expired_groups': [],
                'actions_needed': []
            }
            
            current_time = datetime.now()
            expired_groups = []
            
            for group_id, group in self.active_recoveries.items():
                # เช็คการหมดเวลา
                if (current_time - group.created_time).total_seconds() > group.max_wait_time:
                    expired_groups.append(group_id)
                    continue
                
                # อัพเดทสถานะ
                updated = self._update_single_recovery_group(group, current_price, positions)
                if updated:
                    results['updated_groups'] += 1
                
                # เช็คสถานะ
                if group.phase == RecoveryPhase.READY_FOR_RECOVERY:
                    results['ready_for_recovery'].append(group_id)
                elif group.phase == RecoveryPhase.COMPLETED:
                    results['completed_groups'].append(group_id)
                
                # เช็คการกระทำที่ต้องทำ
                action = self._check_required_actions(group, current_price)
                if action:
                    results['actions_needed'].append(action)
            
            # ลบ groups ที่หมดเวลา
            for group_id in expired_groups:
                expired_group = self.active_recoveries.pop(group_id)
                self.completed_recoveries.append(expired_group)
                results['expired_groups'].append(group_id)
                logger.warning(f"⏰ Recovery Group หมดเวลา: {group_id}")
            
            return results
            
        except Exception as e:
            logger.error(f"Error updating recovery groups: {e}")
            return {'error': str(e)}
    
    def _update_single_recovery_group(self, group: TripleRecoveryGroup, 
                                    current_price: float, positions: List[Position]) -> bool:
        """อัพเดท recovery group เดี่ยว"""
        try:
            group.last_check_time = datetime.now()
            updated = False
            
            # อัพเดทตาม phase
            if group.phase == RecoveryPhase.WAITING:
                # รอการเปิด position ใหม่
                new_pos = self._find_new_position_after_breakout(group, positions)
                if new_pos:
                    group.new_position = new_pos
                    group.phase = RecoveryPhase.NEW_POSITION_OPENED
                    updated = True
                    logger.info(f"✅ Recovery {group.breakout_id}: เปิด position ใหม่แล้ว {new_pos.ticket}")
            
            elif group.phase == RecoveryPhase.NEW_POSITION_OPENED:
                group.phase = RecoveryPhase.WAITING_PROFIT
                updated = True
            
            elif group.phase == RecoveryPhase.WAITING_PROFIT:
                # รอ position ใหม่มีกำไร
                if group.new_position and group.new_position.profit > group.min_new_profit:
                    group.phase = RecoveryPhase.READY_FOR_RECOVERY
                    updated = True
                    logger.info(f"🎯 Recovery {group.breakout_id}: พร้อมทำ Triple Recovery")
            
            # บันทึกประวัติกำไร
            if group.new_position:
                group.profit_history.append(group.new_position.profit)
            
            return updated
            
        except Exception as e:
            logger.error(f"Error updating single recovery group: {e}")
            return False
    
    def _find_new_position_after_breakout(self, group: TripleRecoveryGroup, 
                                        positions: List[Position]) -> Optional[Position]:
        """หา position ใหม่ที่เปิดหลัง breakout"""
        try:
            # หา position ที่เปิดหลัง breakout time
            for pos in positions:
                # เช็คเวลาเปิด
                if hasattr(pos, 'time_open') and pos.time_open:
                    try:
                        if hasattr(pos.time_open, 'timestamp'):
                            pos_time = datetime.fromtimestamp(pos.time_open.timestamp())
                        else:
                            pos_time = datetime.fromtimestamp(pos.time_open)
                        
                        # ต้องเปิดหลัง breakout
                        if pos_time <= group.breakout_time:
                            continue
                    except:
                        continue
                
                # เช็คประเภท position
                if group.breakout_type == BreakoutType.BULLISH:
                    # Bullish breakout ต้องเปิด SELL
                    if pos.type == 1 and pos.price_open > group.breakout_price:
                        return pos
                elif group.breakout_type == BreakoutType.BEARISH:
                    # Bearish breakout ต้องเปิด BUY
                    if pos.type == 0 and pos.price_open < group.breakout_price:
                        return pos
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding new position after breakout: {e}")
            return None
    
    def _check_required_actions(self, group: TripleRecoveryGroup, current_price: float) -> Optional[Dict[str, Any]]:
        """เช็คการกระทำที่ต้องทำ"""
        try:
            if group.phase == RecoveryPhase.WAITING:
                # ต้องเปิด position ใหม่
                if group.breakout_type == BreakoutType.BULLISH:
                    return {
                        'action': 'OPEN_SELL',
                        'group_id': group.breakout_id,
                        'target_price': current_price + 1.0,
                        'reason': 'เปิด SELL หลัง Bullish Breakout'
                    }
                elif group.breakout_type == BreakoutType.BEARISH:
                    return {
                        'action': 'OPEN_BUY',
                        'group_id': group.breakout_id,
                        'target_price': current_price - 1.0,
                        'reason': 'เปิด BUY หลัง Bearish Breakout'
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking required actions: {e}")
            return None
    
    def calculate_triple_recovery(self, group_id: str, portfolio_validator=None) -> Optional[Dict[str, Any]]:
        """คำนวณ Triple Recovery"""
        try:
            group = self.active_recoveries.get(group_id)
            if not group or group.phase != RecoveryPhase.READY_FOR_RECOVERY:
                return None
            
            positions = [group.old_position, group.new_position, group.target_recovery]
            
            # คำนวณกำไรรวม
            total_profit = sum(pos.profit for pos in positions if pos)
            
            # คำนวณ spread cost
            spread_cost = self._calculate_spread_cost(positions)
            
            # กำไรสุทธิ
            net_profit = total_profit - spread_cost
            
            # ใช้ Portfolio Health Validator ถ้ามี (จากระบบหลัก)
            should_close = net_profit >= group.min_net_profit
            
            if should_close and portfolio_validator:
                # สร้าง candidate สำหรับ validation
                validation_candidate = {
                    'positions': positions,
                    'net_profit': net_profit,
                    'total_profit': total_profit
                }
                
                validation = portfolio_validator(validation_candidate, None)
                if not validation['valid']:
                    logger.info(f"🛡️ Triple Recovery ถูกปฏิเสธโดย Portfolio Health: {validation['reason']}")
                    should_close = False
                else:
                    logger.info(f"✅ Triple Recovery ผ่าน Portfolio Health Check")
            
            result = {
                'group_id': group_id,
                'positions': positions,
                'total_profit': total_profit,
                'spread_cost': spread_cost,
                'net_profit': net_profit,
                'should_close': should_close,
                'min_required': group.min_net_profit
            }
            
            logger.info(f"🧮 Triple Recovery Calculation ({group_id}):")
            logger.info(f"   Old Position: {group.old_position.ticket} (${group.old_position.profit:.2f})")
            logger.info(f"   New Position: {group.new_position.ticket} (${group.new_position.profit:.2f})")
            logger.info(f"   Target Recovery: {group.target_recovery.ticket} (${group.target_recovery.profit:.2f})")
            logger.info(f"   Total Profit: ${total_profit:.2f}")
            logger.info(f"   Spread Cost: ${spread_cost:.2f}")
            logger.info(f"   Net Profit: ${net_profit:.2f}")
            logger.info(f"   Should Close: {should_close} (Min: ${group.min_net_profit:.2f})")
            
            return result
            
        except Exception as e:
            logger.error(f"Error calculating triple recovery: {e}")
            return None
    
    def should_execute_counter_trade(self, breakout_analysis: Dict, current_price: float, symbol: str = "XAUUSD") -> Dict[str, Any]:
        """ตรวจสอบว่าควรออกไม้ตรงข้ามหลัง breakout หรือไม่"""
        try:
            recommended_action = breakout_analysis.get('recommended_action', '')
            
            # ถ้าไม่ใช่กรณีที่ต้องรอแรงตลาด → ออกได้เลย
            if 'WAIT_MARKET_STRENGTH' not in recommended_action:
                return {
                    'should_trade': True,
                    'reason': 'Normal breakout - trade immediately',
                    'direction': breakout_analysis.get('counter_trade_direction', 'UNKNOWN')
                }
            
            # ตรวจสอบแรงตลาดสำหรับกรณีพิเศษ
            market_strength = self._analyze_market_strength(current_price, symbol)
            
            # เงื่อนไขการออกไม้ตรงข้าม
            trade_conditions = []
            
            # 1. ตรวจสอบ Volume
            if market_strength.get('volume_ratio', 0) > 1.2:
                trade_conditions.append('Volume สูง')
            
            # 2. ตรวจสอบ Momentum  
            if market_strength.get('momentum_strength', 0) > 30:
                trade_conditions.append('Momentum แรง')
            
            # 3. ตรวจสอบ ATR (ความผันผวน)
            if market_strength.get('atr_ratio', 0) > 1.5:
                trade_conditions.append('ATR สูง')
            
            # 4. ตรวจสอบเวลาหลัง breakout
            breakout_time_passed = market_strength.get('time_since_breakout', 0)
            if breakout_time_passed > 300:  # 5 นาที
                trade_conditions.append('เวลาผ่านไป 5+ นาที')
            
            # ต้องผ่านอย่างน้อย 2 เงื่อนไข
            should_trade = len(trade_conditions) >= 2
            
            return {
                'should_trade': should_trade,
                'reason': f"Market conditions: {', '.join(trade_conditions) if trade_conditions else 'ไม่เพียงพอ'}",
                'direction': breakout_analysis.get('counter_trade_direction', 'UNKNOWN'),
                'conditions_met': len(trade_conditions),
                'total_conditions': 4,
                'market_strength': market_strength
            }
            
        except Exception as e:
            logger.error(f"Error checking counter trade conditions: {e}")
            return {'should_trade': False, 'reason': f'Error: {str(e)}', 'direction': 'UNKNOWN'}
    
    def _analyze_market_strength(self, current_price: float, symbol: str) -> Dict[str, Any]:
        """วิเคราะห์แรงตลาดปัจจุบัน"""
        try:
            try:
                import MetaTrader5 as mt5
            except ImportError:
                logger.warning("MetaTrader5 not available for market strength analysis")
                return {'volume_ratio': 0, 'momentum_strength': 0, 'atr_ratio': 0, 'time_since_breakout': 0}
            
            # ดึงข้อมูล M5 ล่าสุด 20 แท่ง
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 20)
            if rates is None or len(rates) < 10:
                return {'volume_ratio': 0, 'momentum_strength': 0, 'atr_ratio': 0, 'time_since_breakout': 0}
            
            # คำนวณ Volume Ratio
            recent_volumes = [r['tick_volume'] for r in rates[-3:]]
            older_volumes = [r['tick_volume'] for r in rates[-10:-3]]
            avg_recent = sum(recent_volumes) / len(recent_volumes)
            avg_older = sum(older_volumes) / len(older_volumes)
            volume_ratio = avg_recent / avg_older if avg_older > 0 else 1.0
            
            # คำนวณ Momentum
            price_change = (rates[-1]['close'] - rates[-5]['close']) * 10  # pips
            momentum_strength = min(100, abs(price_change) * 3)
            
            # คำนวณ ATR Ratio
            atr_recent = sum([(r['high'] - r['low']) * 10 for r in rates[-3:]]) / 3
            atr_older = sum([(r['high'] - r['low']) * 10 for r in rates[-10:-3]]) / 7
            atr_ratio = atr_recent / atr_older if atr_older > 0 else 1.0
            
            return {
                'volume_ratio': volume_ratio,
                'momentum_strength': momentum_strength,
                'atr_ratio': atr_ratio,
                'time_since_breakout': 60,  # ประมาณการ - ควรใช้เวลาจริง
                'price_change_pips': price_change
            }
            
        except Exception as e:
            logger.error(f"Error analyzing market strength: {e}")
            return {'volume_ratio': 0, 'momentum_strength': 0, 'atr_ratio': 0, 'time_since_breakout': 0}
    
    def _calculate_spread_cost(self, positions: List[Position]) -> float:
        """คำนวณค่า spread สำหรับ positions"""
        try:
            if not positions:
                return 0.0
            
            # ประมาณการ spread cost (สามารถปรับปรุงให้แม่นยำกว่านี้)
            total_volume = sum(pos.volume for pos in positions if pos)
            
            # XAUUSD spread ประมาณ 3-5 pips
            estimated_spread_per_lot = 3.0
            total_spread_cost = total_volume * estimated_spread_per_lot
            
            return total_spread_cost
            
        except Exception as e:
            logger.error(f"Error calculating spread cost: {e}")
            return 0.0
    
    def execute_triple_recovery(self, group_id: str, portfolio_validator=None) -> Dict[str, Any]:
        """ดำเนินการ Triple Recovery (ใช้ Portfolio Health Validator ร่วมกัน)"""
        try:
            calculation = self.calculate_triple_recovery(group_id, portfolio_validator)
            if not calculation or not calculation['should_close']:
                return {
                    'success': False,
                    'reason': 'ยังไม่พร้อมสำหรับ Recovery หรือกำไรไม่เพียงพอ'
                }
            
            group = self.active_recoveries[group_id]
            positions = calculation['positions']
            tickets = [pos.ticket for pos in positions if pos]
            
            # ปิด positions พร้อมกัน
            result = self.mt5.close_positions_group_with_spread_check(tickets)
            
            if result['success']:
                # อัพเดทสถานะ
                group.phase = RecoveryPhase.COMPLETED
                self.completed_recoveries.append(group)
                del self.active_recoveries[group_id]
                
                logger.info(f"✅ Triple Recovery สำเร็จ! ({group_id})")
                logger.info(f"   ปิด Positions: {tickets}")
                logger.info(f"   กำไรสุทธิ: ${calculation['net_profit']:.2f}")
                
                return {
                    'success': True,
                    'group_id': group_id,
                    'closed_tickets': tickets,
                    'net_profit': calculation['net_profit'],
                    'message': f"Triple Recovery สำเร็จ - กำไรสุทธิ ${calculation['net_profit']:.2f}"
                }
            else:
                return {
                    'success': False,
                    'reason': f"ปิด positions ไม่สำเร็จ: {result.get('message', 'Unknown error')}"
                }
                
        except Exception as e:
            logger.error(f"Error executing triple recovery: {e}")
            return {
                'success': False,
                'reason': f'เกิดข้อผิดพลาด: {str(e)}'
            }
    
    def get_recovery_status(self) -> Dict[str, Any]:
        """ดึงสถานะของ recovery system"""
        try:
            return {
                'active_recoveries': len(self.active_recoveries),
                'completed_recoveries': len(self.completed_recoveries),
                'max_concurrent': self.max_concurrent_recoveries,
                'active_groups': {
                    group_id: {
                        'type': group.breakout_type.value,
                        'phase': group.phase.value,
                        'age_seconds': (datetime.now() - group.created_time).total_seconds(),
                        'new_position_profit': group.new_position.profit if group.new_position else None
                    }
                    for group_id, group in self.active_recoveries.items()
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting recovery status: {e}")
            return {'error': str(e)}
