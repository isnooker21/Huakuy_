# -*- coding: utf-8 -*-
"""
Smart Recovery System
ระบบปิด Position อย่างชาญฉลาด เพื่อฟื้นฟูพอร์ตและรักษากำไรรวม
"""

import logging
import MetaTrader5 as mt5
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from calculations import Position

logger = logging.getLogger(__name__)

@dataclass
class RecoveryCandidate:
    """ตัวเลือกสำหรับการปิดแบบ Recovery"""
    profit_position: Position
    losing_position: Position
    net_profit: float
    recovery_score: float
    spread_cost: float
    margin_freed: float
    reason: str

class SmartRecoverySystem:
    """ระบบปิด Position แบบ Smart Recovery"""
    
    def __init__(self, mt5_connection):
        self.mt5 = mt5_connection
        self.minimum_position_age = 300  # 5 นาที (วินาที)
        self.minimum_distance_pips = 10  # 10 pips
        self.minimum_net_profit = 1.0    # $1 กำไรสุทธิขั้นต่ำ
        
    def analyze_recovery_opportunities(self, positions: List[Position], 
                                     account_balance: float,
                                     current_price: float) -> List[RecoveryCandidate]:
        """วิเคราะห์โอกาสในการทำ Recovery"""
        try:
            if not positions or len(positions) < 2:
                return []
            
            # แยกประเภท positions
            profitable_positions = [pos for pos in positions if pos.profit > 0]
            losing_positions = [pos for pos in positions if pos.profit < 0]
            
            if not profitable_positions or not losing_positions:
                logger.info("💡 ไม่มีโอกาส Recovery - ต้องมีทั้งไม้กำไรและไม้ขาดทุน")
                return []
            
            # กรองไม้ขาดทุนที่เหมาะสม
            suitable_losing = self._filter_suitable_losing_positions(
                losing_positions, current_price
            )
            
            if not suitable_losing:
                logger.info("💡 ไม่มีไม้ขาดทุนที่เหมาะสมสำหรับ Recovery")
                return []
            
            # หาคู่ที่เหมาะสม
            candidates = []
            
            for losing_pos in suitable_losing:
                for profit_pos in profitable_positions:
                    candidate = self._evaluate_recovery_pair(
                        profit_pos, losing_pos, account_balance, current_price
                    )
                    
                    if candidate and candidate.net_profit > self.minimum_net_profit:
                        candidates.append(candidate)
            
            # เรียงตาม recovery score
            candidates.sort(key=lambda x: x.recovery_score, reverse=True)
            
            logger.info(f"🎯 พบโอกาส Recovery: {len(candidates)} คู่")
            for i, candidate in enumerate(candidates[:3]):  # แสดง top 3
                logger.info(f"   {i+1}. Profit: ${candidate.net_profit:.2f}, "
                          f"Score: {candidate.recovery_score:.1f} - {candidate.reason}")
            
            return candidates
            
        except Exception as e:
            logger.error(f"Error analyzing recovery opportunities: {e}")
            return []
    
    def _filter_suitable_losing_positions(self, losing_positions: List[Position], 
                                        current_price: float) -> List[Position]:
        """กรองไม้ขาดทุนที่เหมาะสมสำหรับ Recovery"""
        suitable = []
        current_time = datetime.now()
        
        for pos in losing_positions:
            # เช็คอายุของ position
            if pos.time_open:
                try:
                    if hasattr(pos.time_open, 'timestamp'):
                        pos_time = datetime.fromtimestamp(pos.time_open.timestamp())
                    else:
                        pos_time = datetime.fromtimestamp(pos.time_open)
                    
                    age_seconds = (current_time - pos_time).total_seconds()
                    
                    if age_seconds < self.minimum_position_age:
                        logger.debug(f"Position {pos.ticket} อายุน้อยเกินไป ({age_seconds:.0f}s)")
                        continue
                except Exception as e:
                    logger.warning(f"Cannot determine age of position {pos.ticket}: {e}")
                    continue
            
            # เช็คระยะห่างจากราคาปัจจุบัน
            distance = abs(pos.price_open - current_price)
            min_distance = current_price * (self.minimum_distance_pips / 10000)  # Convert pips to price
            
            if distance < min_distance:
                logger.debug(f"Position {pos.ticket} ใกล้ราคาปัจจุบันเกินไป")
                continue
            
            # เช็คว่าขาดทุนไม่มากเกินไป (ไม่เกิน 50% ของ balance)
            if abs(pos.profit) > account_balance * 0.5:
                logger.debug(f"Position {pos.ticket} ขาดทุนมากเกินไป")
                continue
            
            suitable.append(pos)
        
        return suitable
    
    def _evaluate_recovery_pair(self, profit_pos: Position, losing_pos: Position,
                               account_balance: float, current_price: float) -> Optional[RecoveryCandidate]:
        """ประเมินคู่ position สำหรับ Recovery"""
        try:
            # คำนวณ spread cost
            spread_cost = self._calculate_spread_cost(profit_pos, losing_pos)
            
            # คำนวณกำไรสุทธิ
            gross_profit = profit_pos.profit + losing_pos.profit
            net_profit = gross_profit - spread_cost
            
            if net_profit <= 0:
                return None
            
            # คำนวณ margin ที่จะได้คืน
            margin_freed = self._calculate_margin_freed(profit_pos, losing_pos, current_price)
            
            # คำนวณ recovery score
            recovery_score = self._calculate_recovery_score(
                profit_pos, losing_pos, account_balance, current_price, margin_freed
            )
            
            # สร้างเหตุผล
            reason = self._generate_recovery_reason(profit_pos, losing_pos, net_profit, recovery_score)
            
            return RecoveryCandidate(
                profit_position=profit_pos,
                losing_position=losing_pos,
                net_profit=net_profit,
                recovery_score=recovery_score,
                spread_cost=spread_cost,
                margin_freed=margin_freed,
                reason=reason
            )
            
        except Exception as e:
            logger.error(f"Error evaluating recovery pair: {e}")
            return None
    
    def _calculate_spread_cost(self, profit_pos: Position, losing_pos: Position) -> float:
        """คำนวณค่า spread ที่จะเสียไปเมื่อปิด"""
        try:
            # ดึงข้อมูล spread ปัจจุบัน
            symbol_info = mt5.symbol_info(profit_pos.symbol)
            if not symbol_info:
                return 5.0  # Default spread cost
            
            current_tick = mt5.symbol_info_tick(profit_pos.symbol)
            if not current_tick:
                return 5.0
            
            spread_points = current_tick.ask - current_tick.bid
            
            # คำนวณค่า spread สำหรับ 2 positions
            if 'XAU' in profit_pos.symbol.upper():
                spread_cost_per_lot = spread_points * 100  # XAUUSD
            else:
                spread_cost_per_lot = spread_points * 100000  # Forex
            
            total_spread_cost = (spread_cost_per_lot * profit_pos.volume + 
                               spread_cost_per_lot * abs(losing_pos.volume))
            
            return total_spread_cost
            
        except Exception as e:
            logger.error(f"Error calculating spread cost: {e}")
            return 5.0
    
    def _calculate_margin_freed(self, profit_pos: Position, losing_pos: Position, 
                               current_price: float) -> float:
        """คำนวณ margin ที่จะได้คืนเมื่อปิด positions"""
        try:
            # ประมาณการ margin requirement
            if 'XAU' in profit_pos.symbol.upper():
                margin_per_lot = current_price * 100 * 0.02  # 2% margin for XAUUSD
            else:
                margin_per_lot = 100000 * 0.01  # 1% margin for Forex
            
            total_margin = (margin_per_lot * profit_pos.volume + 
                          margin_per_lot * abs(losing_pos.volume))
            
            return total_margin
            
        except Exception:
            return 0.0
    
    def _calculate_recovery_score(self, profit_pos: Position, losing_pos: Position,
                                 account_balance: float, current_price: float,
                                 margin_freed: float) -> float:
        """คำนวณคะแนน Recovery"""
        try:
            score = 0.0
            
            # 1. Distance Score (30%) - ไม้ที่ห่างจากราคาปัจจุบันได้คะแนนสูง
            losing_distance = abs(losing_pos.price_open - current_price)
            distance_score = min(losing_distance / current_price * 1000, 30.0)
            score += distance_score
            
            # 2. Loss Amount Score (25%) - ไม้ที่ขาดทุนมากได้คะแนนสูง
            loss_amount = abs(losing_pos.profit)
            loss_score = min(loss_amount / account_balance * 500, 25.0)
            score += loss_score
            
            # 3. Age Score (20%) - ไม้ที่เก่ากว่าได้คะแนนสูง
            try:
                current_time = datetime.now()
                if hasattr(losing_pos.time_open, 'timestamp'):
                    pos_time = datetime.fromtimestamp(losing_pos.time_open.timestamp())
                else:
                    pos_time = datetime.fromtimestamp(losing_pos.time_open)
                
                age_hours = (current_time - pos_time).total_seconds() / 3600
                age_score = min(age_hours / 24 * 20, 20.0)  # Max 20 points for 24+ hours
                score += age_score
            except Exception:
                score += 5.0  # Default age score
            
            # 4. Margin Impact Score (15%) - การคืน margin
            margin_score = min(margin_freed / account_balance * 300, 15.0)
            score += margin_score
            
            # 5. Portfolio Health Score (10%) - ผลกระทบต่อพอร์ต
            portfolio_impact = (loss_amount / account_balance) * 100
            if portfolio_impact > 10:  # ถ้าขาดทุนเกิน 10% ของ balance
                score += 10.0
            elif portfolio_impact > 5:
                score += 5.0
            
            return score
            
        except Exception as e:
            logger.error(f"Error calculating recovery score: {e}")
            return 0.0
    
    def _generate_recovery_reason(self, profit_pos: Position, losing_pos: Position,
                                 net_profit: float, recovery_score: float) -> str:
        """สร้างเหตุผลสำหรับการ Recovery"""
        try:
            reasons = []
            
            # เหตุผลหลัก
            if recovery_score > 80:
                reasons.append("High priority recovery")
            elif recovery_score > 60:
                reasons.append("Good recovery opportunity")
            else:
                reasons.append("Moderate recovery")
            
            # รายละเอียด
            if abs(losing_pos.profit) > 20:
                reasons.append(f"Remove ${abs(losing_pos.profit):.0f} loss")
            
            if net_profit > 10:
                reasons.append(f"Net profit ${net_profit:.0f}")
            
            return " | ".join(reasons)
            
        except Exception:
            return "Portfolio recovery"
    
    def execute_recovery(self, candidate: RecoveryCandidate) -> Dict[str, Any]:
        """ดำเนินการ Recovery"""
        try:
            logger.info(f"🎯 เริ่ม Smart Recovery:")
            logger.info(f"   Profit Position: {candidate.profit_position.ticket} (+${candidate.profit_position.profit:.2f})")
            logger.info(f"   Losing Position: {candidate.losing_position.ticket} (${candidate.losing_position.profit:.2f})")
            logger.info(f"   Net Profit: ${candidate.net_profit:.2f}")
            logger.info(f"   Reason: {candidate.reason}")
            
            # ปิดทั้งสอง positions
            tickets = [candidate.profit_position.ticket, candidate.losing_position.ticket]
            result = self.mt5.close_positions_group_with_spread_check(tickets)
            
            if result['success'] and len(result['closed_tickets']) == 2:
                logger.info(f"✅ Smart Recovery สำเร็จ!")
                logger.info(f"   ปิด Positions: {result['closed_tickets']}")
                logger.info(f"   กำไรสุทธิ: ${result['total_profit']:.2f}")
                logger.info(f"   Margin Freed: ${candidate.margin_freed:.2f}")
                
                return {
                    'success': True,
                    'closed_tickets': result['closed_tickets'],
                    'net_profit': result['total_profit'],
                    'margin_freed': candidate.margin_freed,
                    'message': f"Recovery successful - Net profit ${result['total_profit']:.2f}"
                }
            else:
                # บางตัวปิดไม่ได้
                partial_success = len(result['closed_tickets']) > 0
                
                logger.warning(f"⚠️ Smart Recovery บางส่วน:")
                logger.warning(f"   ปิดได้: {result['closed_tickets']}")
                logger.warning(f"   รอกำไรเพิ่ม: {len(result.get('rejected_tickets', []))}")
                logger.warning(f"   ล้มเหลว: {result.get('failed_tickets', [])}")
                
                return {
                    'success': partial_success,
                    'closed_tickets': result['closed_tickets'],
                    'rejected_tickets': result.get('rejected_tickets', []),
                    'failed_tickets': result.get('failed_tickets', []),
                    'net_profit': result['total_profit'],
                    'message': result['message']
                }
                
        except Exception as e:
            logger.error(f"Error executing recovery: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': f"Recovery failed: {str(e)}"
            }
    
    def should_trigger_recovery(self, positions: List[Position], 
                               account_balance: float, 
                               current_equity: float) -> bool:
        """ตรวจสอบว่าควร trigger Recovery หรือไม่"""
        try:
            if not positions or len(positions) < 2:
                return False
            
            # เช็คเงื่อนไข trigger
            conditions_met = 0
            total_conditions = 5
            
            # 1. มี positions ขาดทุน
            losing_positions = [pos for pos in positions if pos.profit < 0]
            if losing_positions:
                conditions_met += 1
                logger.debug("✅ มี positions ขาดทุน")
            
            # 2. Equity ต่ำกว่า Balance มากกว่า 5%
            equity_ratio = current_equity / account_balance
            if equity_ratio < 0.95:
                conditions_met += 1
                logger.debug(f"✅ Equity ratio ต่ำ: {equity_ratio:.3f}")
            
            # 3. มีการขาดทุนรวมเกิน 2% ของ balance
            total_loss = sum([abs(pos.profit) for pos in losing_positions])
            if total_loss > account_balance * 0.02:
                conditions_met += 1
                logger.debug(f"✅ ขาดทุนรวมสูง: ${total_loss:.2f}")
            
            # 4. มี positions อายุมากกว่า 10 นาที
            old_positions = []
            current_time = datetime.now()
            for pos in losing_positions:
                try:
                    if hasattr(pos.time_open, 'timestamp'):
                        pos_time = datetime.fromtimestamp(pos.time_open.timestamp())
                    else:
                        pos_time = datetime.fromtimestamp(pos.time_open)
                    
                    age_seconds = (current_time - pos_time).total_seconds()
                    if age_seconds > 600:  # 10 นาที
                        old_positions.append(pos)
                except Exception:
                    continue
            
            if old_positions:
                conditions_met += 1
                logger.debug(f"✅ มี positions เก่า: {len(old_positions)} ตัว")
            
            # 5. มี positions กำไรที่สามารถใช้ปิดคู่ได้
            profitable_positions = [pos for pos in positions if pos.profit > 5.0]  # กำไรอย่างน้อย $5
            if profitable_positions:
                conditions_met += 1
                logger.debug(f"✅ มี positions กำไร: {len(profitable_positions)} ตัว")
            
            # ต้องผ่านอย่างน้อย 3 จาก 5 เงื่อนไข
            should_trigger = conditions_met >= 3
            
            if should_trigger:
                logger.info(f"🎯 ควร trigger Smart Recovery ({conditions_met}/{total_conditions} เงื่อนไข)")
            else:
                logger.debug(f"💡 ยังไม่ควร Recovery ({conditions_met}/{total_conditions} เงื่อนไข)")
            
            return should_trigger
            
        except Exception as e:
            logger.error(f"Error checking recovery trigger: {e}")
            return False
