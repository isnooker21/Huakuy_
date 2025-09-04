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
        self.minimum_position_age = 60   # ลดเหลือ 1 นาที (วินาที) 
        self.minimum_distance_pips = 5   # ลดเหลือ 5 pips
        self.minimum_net_profit_per_lot = 0.10  # $0.10 ต่อ lot (สำหรับ 0.01 lot = $0.001)
        
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
                losing_positions, current_price, account_balance
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
                    
                    if candidate:
                        # ใช้ minimum profit ตาม lot size แทนค่าตายตัว
                        min_required = self._calculate_minimum_net_profit(profit_pos, losing_pos)
                        if candidate.net_profit > min_required:
                            candidates.append(candidate)
                        else:
                            logger.debug(f"🚫 Candidate rejected: Net ${candidate.net_profit:.3f} < Required ${min_required:.3f} (lots: {profit_pos.volume + losing_pos.volume})")
            
            # เรียงตาม recovery score
            candidates.sort(key=lambda x: x.recovery_score, reverse=True)
            
            # กรองเฉพาะ candidates ที่มีประสิทธิภาพในการกำจัดไม้ขาดทุน
            smart_candidates = self._filter_smart_recovery_candidates(candidates, positions)
            
            logger.info(f"🎯 พบโอกาส Recovery: {len(smart_candidates)} คู่ (จากทั้งหมด {len(candidates)} คู่)")
            for i, candidate in enumerate(smart_candidates[:3]):  # แสดง top 3
                profit_loss_ratio = abs(candidate.profit_position.profit / candidate.losing_position.profit) if candidate.losing_position.profit != 0 else 0
                total_lots = candidate.profit_position.volume + candidate.losing_position.volume
                min_required = self._calculate_minimum_net_profit(candidate.profit_position, candidate.losing_position)
                
                logger.info(f"   {i+1}. Net: ${candidate.net_profit:.3f} (ต้องการ ${min_required:.3f}), Score: {candidate.recovery_score:.1f}")
                logger.info(f"       Profit: ${candidate.profit_position.profit:.3f} ({candidate.profit_position.volume} lot) vs Loss: ${candidate.losing_position.profit:.3f} ({candidate.losing_position.volume} lot)")
                logger.info(f"       รวม: {total_lots} lots, อัตราส่วน: {profit_loss_ratio:.1f}:1")
            
            return smart_candidates
            
        except Exception as e:
            logger.error(f"Error analyzing recovery opportunities: {e}")
            return []
    
    def _filter_suitable_losing_positions(self, losing_positions: List[Position], 
                                        current_price: float, account_balance: float) -> List[Position]:
        """กรองไม้ขาดทุนที่เหมาะสมสำหรับ Recovery"""
        suitable = []
        current_time = datetime.now()
        total_positions = len(losing_positions)
        
        # ปรับเงื่อนไขตามจำนวนไม้ - ยิ่งมีไม้เยอะยิ่งยืดหยุ่น
        if total_positions > 40:
            dynamic_min_age = 30      # 30 วินาที สำหรับไม้เยอะมาก
            dynamic_min_distance = 2  # 2 pips
        elif total_positions > 20:
            dynamic_min_age = 45      # 45 วินาที สำหรับไม้ปานกลาง
            dynamic_min_distance = 3  # 3 pips
        else:
            dynamic_min_age = self.minimum_position_age  # 60 วินาที สำหรับไม้น้อย
            dynamic_min_distance = self.minimum_distance_pips  # 5 pips
        
        logger.info(f"🎯 Dynamic Filter: {total_positions} ไม้ - ใช้อายุขั้นต่ำ {dynamic_min_age}s, ระยะ {dynamic_min_distance} pips")
        
        for pos in losing_positions:
            # เช็คอายุของ position
            if pos.time_open:
                try:
                    if hasattr(pos.time_open, 'timestamp'):
                        pos_time = datetime.fromtimestamp(pos.time_open.timestamp())
                    else:
                        pos_time = datetime.fromtimestamp(pos.time_open)
                    
                    age_seconds = (current_time - pos_time).total_seconds()
                    
                    if age_seconds < dynamic_min_age:
                        logger.debug(f"Position {pos.ticket} อายุน้อยเกินไป ({age_seconds:.0f}s < {dynamic_min_age}s)")
                        continue
                except Exception as e:
                    logger.warning(f"Cannot determine age of position {pos.ticket}: {e}")
                    continue
            
            # เช็คระยะห่างจากราคาปัจจุบัน (ใช้ dynamic distance)
            distance = abs(pos.price_open - current_price)
            min_distance = current_price * (dynamic_min_distance / 10000)  # แปลง pips เป็นราคา
            
            if distance < min_distance:
                logger.debug(f"Position {pos.ticket} ใกล้ราคาปัจจุบันเกินไป ({distance:.5f} < {min_distance:.5f})")
                continue
            
            # เช็คว่าขาดทุนไม่มากเกินไป (ไม่เกิน 50% ของ balance)
            if abs(pos.profit) > account_balance * 0.5:
                logger.debug(f"Position {pos.ticket} ขาดทุนมากเกินไป")
                continue
            
            suitable.append(pos)
        
        return suitable
    
    def _calculate_minimum_net_profit(self, profit_pos: Position, losing_pos: Position) -> float:
        """คำนวณกำไรสุทธิขั้นต่ำตาม lot size"""
        try:
            # รวม lot ของทั้งสองไม้
            total_lot = profit_pos.volume + losing_pos.volume
            
            # คำนวณกำไรขั้นต่ำตาม lot (ยิ่งมี lot เยอะยิ่งต้องกำไรมาก)
            min_profit = total_lot * self.minimum_net_profit_per_lot
            
            # สำหรับ lot เล็กมาก (เช่น 0.01) ให้ minimum ต่ำสุด
            if total_lot <= 0.02:  # รวมกัน <= 0.02 lot
                min_profit = 0.001  # แค่ $0.001 เท่านั้น!
            elif total_lot <= 0.05:  # รวมกัน <= 0.05 lot  
                min_profit = 0.005  # แค่ $0.005
            elif total_lot <= 0.1:   # รวมกัน <= 0.1 lot
                min_profit = 0.01   # แค่ $0.01
            
            logger.debug(f"💰 Lot-based minimum: {total_lot} lots → ${min_profit:.3f} minimum profit")
            return min_profit
            
        except Exception as e:
            logger.error(f"Error calculating minimum profit: {e}")
            return 0.001  # fallback ต่ำสุด
    
    def _filter_smart_recovery_candidates(self, candidates: List[RecoveryCandidate], 
                                         all_positions: List[Position]) -> List[RecoveryCandidate]:
        """กรองเฉพาะ candidates ที่ช่วยกำจัดไม้ขาดทุนใหญ่อย่างมีประสิทธิภาพ"""
        if not candidates:
            return candidates
            
        try:
            # วิเคราะห์สถานการณ์ portfolio
            losing_positions = [pos for pos in all_positions if pos.profit < 0]
            losing_positions.sort(key=lambda x: x.profit)  # เรียงจากขาดทุนมากสุดไปน้อยสุด
            
            # หาไม้ขาดทุน worst 20%
            worst_count = max(1, len(losing_positions) // 5)  # อย่างน้อย 1 ตัว
            worst_losing = losing_positions[:worst_count]
            worst_tickets = [pos.ticket for pos in worst_losing]
            
            # กรอง candidates ที่ช่วยกำจัดไม้ขาดทุนใหญ่
            priority_candidates = []
            regular_candidates = []
            
            for candidate in candidates:
                losing_ticket = candidate.losing_position.ticket
                profit_loss_ratio = abs(candidate.profit_position.profit / candidate.losing_position.profit) if candidate.losing_position.profit != 0 else 0
                
                # เงื่อนไขสำหรับ Priority Candidates
                is_priority = (
                    losing_ticket in worst_tickets or  # กำจัดไม้ขาดทุนใหญ่
                    profit_loss_ratio >= 1.5 or       # กำไรมากกว่าขาดทุน 1.5 เท่า
                    abs(candidate.losing_position.profit) > 50  # ไม้ขาดทุนเกิน $50
                )
                
                if is_priority:
                    priority_candidates.append(candidate)
                else:
                    regular_candidates.append(candidate)
            
            # ให้ความสำคัญกับ priority candidates ก่อน แต่ไม่เกิน 70% ของทั้งหมด
            max_priority = max(1, len(candidates) * 7 // 10)  # 70%
            result = priority_candidates[:max_priority]
            
            # เติม regular candidates ที่เหลือ
            remaining_slots = len(candidates) - len(result)
            if remaining_slots > 0:
                result.extend(regular_candidates[:remaining_slots])
            
            logger.info(f"🎯 Smart Filter: เลือก {len(priority_candidates)} Priority + {min(remaining_slots, len(regular_candidates))} Regular")
            
            return result
            
        except Exception as e:
            logger.error(f"Error filtering smart candidates: {e}")
            return candidates  # fallback ให้ candidates เดิม
    
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
            
            # ป้องกัน division by zero
            if account_balance <= 0 or current_price <= 0:
                logger.warning(f"Invalid values for score calculation: balance={account_balance}, price={current_price}")
                return 0.0
            
            # 1. Distance Score (30%) - ไม้ที่ห่างจากราคาปัจจุบันได้คะแนนสูง
            losing_distance = abs(losing_pos.price_open - current_price)
            distance_score = min(losing_distance / current_price * 1000, 30.0)
            score += distance_score
            
            # 2. Loss Amount Score (35%) - ไม้ที่ขาดทุนมากได้คะแนนสูงขึ้น (เพิ่มจาก 25% เป็น 35%)
            loss_amount = abs(losing_pos.profit)
            loss_score = min(loss_amount / abs(account_balance) * 700, 35.0)  # เพิ่มน้ำหนักและใช้ abs()
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
            if account_balance > 0:
                margin_score = min(margin_freed / account_balance * 300, 15.0)
                score += margin_score
            
            # 5. Smart Recovery Priority Score (15%) - ความสำคัญในการกำจัดไม้ขาดทุน
            if account_balance != 0:
                portfolio_impact = (loss_amount / abs(account_balance)) * 100
                
                # เพิ่มคะแนนสำหรับไม้ขาดทุนใหญ่ที่ควรกำจัดด่วน
                if portfolio_impact > 15:  # ขาดทุนเกิน 15% ของ balance - ต้องกำจัดด่วน
                    score += 15.0
                elif portfolio_impact > 10:  # ขาดทุนเกิน 10% ของ balance
                    score += 12.0
                elif portfolio_impact > 5:  # ขาดทุนเกิน 5% ของ balance
                    score += 8.0
                elif portfolio_impact > 2:  # ขาดทุนเกิน 2% ของ balance
                    score += 5.0
                
                # เพิ่มคะแนนถ้าไม้กำไรใหญ่พอที่จะกำจัดไม้ขาดทุนได้
                profit_to_loss_ratio = abs(profit_pos.profit / losing_pos.profit) if losing_pos.profit != 0 else 0
                if profit_to_loss_ratio >= 2.0:  # กำไรมากกว่าขาดทุน 2 เท่า
                    score += 10.0
                elif profit_to_loss_ratio >= 1.5:  # กำไรมากกว่าขาดทุน 1.5 เท่า
                    score += 7.0
                elif profit_to_loss_ratio >= 1.2:  # กำไรมากกว่าขาดทุน 1.2 เท่า
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
    
    def execute_recovery(self, candidate: RecoveryCandidate, portfolio_validator=None) -> Dict[str, Any]:
        """ดำเนินการ Recovery (ใช้ Portfolio Health Validator ร่วมกัน)"""
        try:
            positions_to_close = [candidate.profit_position, candidate.losing_position]
            
            # ใช้ Portfolio Health Validator ถ้ามี (จากระบบหลัก)
            if portfolio_validator:
                validation = portfolio_validator(candidate, None)  # current_state จะถูกส่งจาก caller
                if not validation['valid']:
                    logger.warning(f"❌ Smart Recovery ถูกปฏิเสธโดย Portfolio Health: {validation['reason']}")
                    return {'success': False, 'reason': f"Portfolio Health: {validation['reason']}"}
                
                logger.info(f"✅ Portfolio Health Check ผ่าน: {validation['reason']}")
            
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
            position_count = len(positions) if positions else 0
            logger.debug(f"🔍 Checking Recovery Trigger - positions: {position_count}")
            
            if not positions or len(positions) < 2:
                logger.debug(f"🔍 Not enough positions for recovery: {position_count}")
                return False
            
            # ถ้ามีไม้เยอะมาก (>40) ลดเงื่อนไขให้ง่ายขึ้น
            if position_count > 40:
                logger.info(f"🎯 มีไม้เยอะ ({position_count}) - ใช้เงื่อนไข Recovery แบบง่าย")
                losing_positions = [pos for pos in positions if pos.profit < 0]
                profitable_positions = [pos for pos in positions if pos.profit > 0]
                return len(losing_positions) > 0 and len(profitable_positions) > 0
            
            # เช็คเงื่อนไข trigger ปกติ
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
            
            # ปรับเงื่อนไขตามจำนวนไม้
            if position_count > 30:
                required_conditions = 2  # ไม้เยอะ ใช้เงื่อนไข 2/5
            elif position_count > 20:
                required_conditions = 2  # ไม้ปานกลาง ใช้เงื่อนไข 2/5  
            else:
                required_conditions = 3  # ไม้น้อย ใช้เงื่อนไข 3/5
            
            should_trigger = conditions_met >= required_conditions
            
            if should_trigger:
                logger.info(f"🎯 ควร trigger Smart Recovery ({conditions_met}/{total_conditions} เงื่อนไข, ต้องการ {required_conditions})")
            else:
                logger.debug(f"💡 ยังไม่ควร Recovery ({conditions_met}/{total_conditions} เงื่อนไข, ต้องการ {required_conditions})")
            
            return should_trigger
            
        except Exception as e:
            logger.error(f"Error checking recovery trigger: {e}")
            return False
