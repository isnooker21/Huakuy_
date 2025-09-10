# -*- coding: utf-8 -*-
"""
Hedge Pairing Closer Module
โมดูลสำหรับการปิดไม้แบบจับคู่ (Hedge Strategy)
"""

import logging
import itertools
import time
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class HedgeCombination:
    """ผลลัพธ์การจับคู่ไม้"""
    positions: List[Any]
    total_profit: float
    combination_type: str
    size: int
    confidence_score: float
    reason: str

@dataclass
class ClosingDecision:
    """การตัดสินใจปิดไม้"""
    should_close: bool
    positions_to_close: List[Any]
    method: str
    net_pnl: float
    expected_pnl: float
    position_count: int
    buy_count: int
    sell_count: int
    confidence_score: float
    reason: str

class HedgePairingCloser:
    """🚀 Hedge Pairing Closer - ระบบปิดไม้แบบจับคู่"""
    
    def __init__(self):
        # 🎯 Hedge Strategy Parameters
        self.min_combination_size = 2      # ขนาดการจับคู่ขั้นต่ำ
        self.max_combination_size = 8       # ขนาดการจับคู่สูงสุด
        self.min_net_profit = 0.1          # กำไรสุทธิขั้นต่ำ $0.1
        self.max_acceptable_loss = 5.0     # ขาดทุนที่ยอมรับได้ $5.0
        
        # 🔧 Position Generation Parameters
        self.enable_position_generation = True  # เปิดใช้งานการออกไม้เพิ่มเติม
        self.max_additional_positions = 3       # จำนวนไม้เพิ่มเติมสูงสุด
        self.additional_position_volume = 0.01  # ขนาดไม้เพิ่มเติม
        
        logger.info("🚀 Hedge Pairing Closer initialized")
        logger.info(f"   Min Combination Size: {self.min_combination_size}")
        logger.info(f"   Max Combination Size: {self.max_combination_size}")
        logger.info(f"   Min Net Profit: ${self.min_net_profit}")
        logger.info(f"   Position Generation: {'Enabled' if self.enable_position_generation else 'Disabled'}")
    
    def find_optimal_closing(self, positions: List[Any], account_info: Dict, 
                           market_conditions: Optional[Dict] = None) -> Optional[ClosingDecision]:
        """
        🧠 หาการปิดไม้ที่ดีที่สุดแบบจับคู่
        """
        try:
            if len(positions) < 1:
                logger.info("⏸️ Need at least 1 position for analysis")
                return None
            
            logger.info(f"🔍 HEDGE ANALYSIS: {len(positions)} positions")
            
            # 1. หาการจับคู่ไม้ที่มีอยู่
            profitable_combinations = self._find_profitable_combinations(positions)
            
            if profitable_combinations:
                # มีการจับคู่ที่เหมาะสม → ปิดไม้
                best_combination = profitable_combinations[0]
                logger.info(f"✅ HEDGE COMBINATION FOUND: {best_combination.combination_type}")
                logger.info(f"   Net P&L: ${best_combination.total_profit:.2f}")
                logger.info(f"   Positions: {best_combination.size}")
                
                return ClosingDecision(
                    should_close=True,
                    positions_to_close=best_combination.positions,
                    method="HEDGE_PAIRING",
                    net_pnl=best_combination.total_profit,
                    expected_pnl=best_combination.total_profit,
                    position_count=best_combination.size,
                    buy_count=sum(1 for p in best_combination.positions if p.type == 0),
                    sell_count=sum(1 for p in best_combination.positions if p.type == 1),
                    confidence_score=best_combination.confidence_score,
                    reason=best_combination.reason
                )
            
            # 2. ไม่มีการจับคู่ที่เหมาะสม → แสดงสถานะ
            logger.info("💤 No profitable combinations found - waiting for better conditions")
            logger.info(f"   Current positions: {len(positions)} total")
            logger.info(f"   Buy positions: {len([p for p in positions if getattr(p, 'type', 0) == 0])}")
            logger.info(f"   Sell positions: {len([p for p in positions if getattr(p, 'type', 0) == 1])}")
            
            # แสดงข้อมูลไม้ทั้งหมด
            for pos in positions:
                pos_type = "BUY" if getattr(pos, 'type', 0) == 0 else "SELL"
                profit = getattr(pos, 'profit', 0)
                ticket = getattr(pos, 'ticket', 'N/A')
                has_hedge = self._has_hedge_pair(positions, pos)
                hedge_status = "🔗 HEDGED" if has_hedge else "💤 NO HEDGE"
                logger.info(f"   {ticket}: {pos_type} ${profit:.2f} - {hedge_status}")
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error in hedge pairing analysis: {e}")
            return None
    
    def _find_profitable_combinations(self, positions: List[Any]) -> List[HedgeCombination]:
        """🔍 หาการจับคู่ไม้ที่ผลรวมเป็นบวก (ใช้หลักการ Hedge เท่านั้น)"""
        try:
            # หาการจับคู่แบบ Hedge เท่านั้น
            hedge_combinations = self._find_hedge_combinations(positions)
            if hedge_combinations:
                logger.info(f"🔍 Found {len(hedge_combinations)} hedge combinations")
                return hedge_combinations
            
            # หาไม้ที่ไม่มีคู่และไม้ที่มี Hedge แล้ว
            unpaired_profitable = []  # ไม้กำไรที่ไม่มีคู่
            unpaired_losing = []     # ไม้ติดลบที่ไม่มีคู่
            existing_hedge_pairs = [] # Hedge pairs ที่มีอยู่แล้ว
            
            # แยกไม้ตามสถานะ
            for pos in positions:
                pos_ticket = getattr(pos, 'ticket', 'N/A')
                pos_profit = getattr(pos, 'profit', 0)
                has_hedge = self._has_hedge_pair(positions, pos)
                
                if not has_hedge:
                    if pos_profit >= self.min_net_profit:
                        unpaired_profitable.append(pos)
                        logger.info(f"🔍 Unpaired profitable position: {pos_ticket} (${pos_profit:.2f})")
                    else:
                        unpaired_losing.append(pos)
                        logger.info(f"🔍 Unpaired losing position: {pos_ticket} (${pos_profit:.2f}) - waiting for opposite")
                else:
                    logger.info(f"🔍 Hedged position: {pos_ticket} (${pos_profit:.2f})")
            
            # หา Hedge pairs ที่มีอยู่แล้ว
            existing_hedge_pairs = self._find_existing_hedge_pairs(positions)
            
            logger.info(f"📊 Position Summary:")
            logger.info(f"   Unpaired profitable: {len(unpaired_profitable)}")
            logger.info(f"   Unpaired losing: {len(unpaired_losing)}")
            logger.info(f"   Existing hedge pairs: {len(existing_hedge_pairs)}")
            
            # หาการรวมที่ดีที่สุด: ไม้กำไรที่ไม่มีคู่ + Hedge pairs ที่ติดลบ
            profitable_combinations = self._find_helping_combinations(unpaired_profitable, existing_hedge_pairs)
            
            # ไม่มีการรวมแบบผสมอื่นๆ - ใช้เฉพาะระบบช่วยเหลือ
            
            # เรียงตามผลรวมกำไร (มากสุดก่อน)
            profitable_combinations.sort(key=lambda x: x.total_profit, reverse=True)
            
            logger.info(f"🔍 Found {len(profitable_combinations)} profitable combinations")
            return profitable_combinations
            
        except Exception as e:
            logger.error(f"❌ Error finding profitable combinations: {e}")
            return []
    
    def _is_same_type_combination(self, combination: List[Any]) -> bool:
        """ตรวจสอบว่าเป็นการจับคู่แบบเดียวกันหรือไม่"""
        try:
            if len(combination) < 2:
                return False
            
            # ตรวจสอบว่าเป็นไม้ประเภทเดียวกันทั้งหมดหรือไม่
            first_type = getattr(combination[0], 'type', 0)
            for pos in combination[1:]:
                if getattr(pos, 'type', 0) != first_type:
                    return False  # ไม่ใช่แบบเดียวกัน
            
            return True  # เป็นแบบเดียวกัน
            
        except Exception as e:
            logger.error(f"❌ Error checking same type combination: {e}")
            return False
    
    def _find_hedge_combinations(self, positions: List[Any]) -> List[HedgeCombination]:
        """หาการจับคู่แบบ Hedge (ตรงข้ามก่อนเสมอ)"""
        try:
            hedge_combinations = []
            
            # แยกไม้ Buy และ Sell
            buy_positions = [p for p in positions if getattr(p, 'type', 0) == 0]
            sell_positions = [p for p in positions if getattr(p, 'type', 0) == 1]
            
            logger.info(f"🔍 Analyzing hedge combinations: {len(buy_positions)} Buy, {len(sell_positions)} Sell (Total: {len(positions)} positions)")
            logger.info(f"🔍 Looking for hedge pairs without duplication...")
            
            # Step 1: จับคู่ตรงข้ามก่อนเสมอ (ไม่ซ้ำซ้อน)
            hedge_pairs = []
            used_positions = set()  # ติดตามไม้ที่ใช้แล้ว
            
            # หา Buy ติดลบ + Sell กำไร (ไม่ซ้ำซ้อน)
            for buy_pos in buy_positions:
                if getattr(buy_pos, 'profit', 0) < 0:  # Buy ติดลบ
                    buy_ticket = getattr(buy_pos, 'ticket', 'N/A')
                    if buy_ticket in used_positions:
                        continue  # ข้ามไม้ที่ใช้แล้ว
                    
                    for sell_pos in sell_positions:
                        if getattr(sell_pos, 'profit', 0) > 0:  # Sell กำไร
                            sell_ticket = getattr(sell_pos, 'ticket', 'N/A')
                            if sell_ticket in used_positions:
                                continue  # ข้ามไม้ที่ใช้แล้ว
                            
                            # จับคู่ไม้ที่ยังไม่ได้ใช้
                            hedge_pairs.append({
                                'buy': buy_pos,
                                'sell': sell_pos,
                                'type': 'BUY_LOSS_SELL_PROFIT'
                            })
                            used_positions.add(buy_ticket)
                            used_positions.add(sell_ticket)
                            logger.info(f"🔍 Found hedge pair: Buy {buy_ticket} (${getattr(buy_pos, 'profit', 0):.2f}) + Sell {sell_ticket} (${getattr(sell_pos, 'profit', 0):.2f})")
                            logger.info(f"   Used positions: {list(used_positions)}")
                            break  # หยุดเมื่อจับคู่แล้ว
            
            # หา Sell ติดลบ + Buy กำไร (ไม่ซ้ำซ้อน)
            for sell_pos in sell_positions:
                if getattr(sell_pos, 'profit', 0) < 0:  # Sell ติดลบ
                    sell_ticket = getattr(sell_pos, 'ticket', 'N/A')
                    if sell_ticket in used_positions:
                        continue  # ข้ามไม้ที่ใช้แล้ว
                    
                    for buy_pos in buy_positions:
                        if getattr(buy_pos, 'profit', 0) > 0:  # Buy กำไร
                            buy_ticket = getattr(buy_pos, 'ticket', 'N/A')
                            if buy_ticket in used_positions:
                                continue  # ข้ามไม้ที่ใช้แล้ว
                            
                            # จับคู่ไม้ที่ยังไม่ได้ใช้
                            hedge_pairs.append({
                                'buy': buy_pos,
                                'sell': sell_pos,
                                'type': 'SELL_LOSS_BUY_PROFIT'
                            })
                            used_positions.add(sell_ticket)
                            used_positions.add(buy_ticket)
                            logger.info(f"🔍 Found hedge pair: Sell {sell_ticket} (${getattr(sell_pos, 'profit', 0):.2f}) + Buy {buy_ticket} (${getattr(buy_pos, 'profit', 0):.2f})")
                            logger.info(f"   Used positions: {list(used_positions)}")
                            break  # หยุดเมื่อจับคู่แล้ว
            
            # แสดงสรุปการจับคู่
            logger.info(f"📊 Hedge pairing summary: {len(hedge_pairs)} pairs found")
            logger.info(f"   Used positions: {list(used_positions)}")
            logger.info(f"   Unused positions: {len(positions) - len(used_positions)}")
            
            # แสดงไม้ที่มี Hedge
            hedged_positions = []
            for pos in positions:
                if self._has_hedge_pair(positions, pos):
                    hedged_positions.append(getattr(pos, 'ticket', 'N/A'))
            
            if hedged_positions:
                logger.info(f"🔗 Hedged positions: {hedged_positions}")
                logger.info(f"   These positions will NOT be closed individually - waiting for additional positions")
            
            # Step 2: หาไม้อื่นๆ มาจับคู่เพิ่มเติม
            for hedge_pair in hedge_pairs:
                # หาไม้อื่นๆ ที่กำไรและไม่มี Hedge กับคู่อื่น
                additional_positions = self._find_additional_profitable_positions(
                    positions, hedge_pair['buy'], hedge_pair['sell']
                )
                
                if additional_positions:
                    # รวมไม้ทั้งหมด
                    all_positions = [hedge_pair['buy'], hedge_pair['sell']] + additional_positions
                    total_profit = sum(getattr(pos, 'profit', 0) for pos in all_positions)
                    
                    logger.info(f"🔍 Testing hedge with additional positions: ${total_profit:.2f}")
                    
                    if total_profit >= self.min_net_profit:
                        hedge_combinations.append(HedgeCombination(
                            positions=all_positions,
                            total_profit=total_profit,
                            combination_type=f"HEDGE_{hedge_pair['type']}_WITH_ADDITIONAL",
                            size=len(all_positions),
                            confidence_score=95.0,  # Hedge มีคะแนนสูงมาก
                            reason=f"Hedge: {hedge_pair['type']} with additional profitable positions"
                        ))
                        logger.info(f"✅ Complete hedge combination found: ${total_profit:.2f}")
                else:
                    # ถ้าไม่มีไม้อื่นๆ ให้จับคู่ Hedge เดี่ยว (ไม่สนใจผลรวม)
                    total_profit = getattr(hedge_pair['buy'], 'profit', 0) + getattr(hedge_pair['sell'], 'profit', 0)
                    
                    logger.info(f"🔍 Testing hedge pair only: ${total_profit:.2f}")
                    
                    # จับคู่ Hedge เดี่ยว (ไม่สนใจผลรวม)
                    hedge_combinations.append(HedgeCombination(
                        positions=[hedge_pair['buy'], hedge_pair['sell']],
                        total_profit=total_profit,
                        combination_type=f"HEDGE_{hedge_pair['type']}_ONLY",
                        size=2,
                        confidence_score=85.0,  # Hedge เดี่ยวมีคะแนนสูง
                        reason=f"Hedge: {hedge_pair['type']} (waiting for additional positions)"
                    ))
                    logger.info(f"✅ Hedge pair found: ${total_profit:.2f}")
            
            # เรียงตามผลรวมกำไร (มากสุดก่อน)
            hedge_combinations.sort(key=lambda x: x.total_profit, reverse=True)
            
            return hedge_combinations
            
        except Exception as e:
            logger.error(f"❌ Error finding hedge combinations: {e}")
            return []
    
    def _find_additional_profitable_positions(self, positions: List[Any], hedge_buy: Any, hedge_sell: Any) -> List[Any]:
        """หาไม้อื่นๆ ที่กำไรและไม่มี Hedge กับคู่อื่น"""
        try:
            additional_positions = []
            
            # หาไม้อื่นๆ ที่กำไร
            for pos in positions:
                if pos == hedge_buy or pos == hedge_sell:
                    continue  # ข้ามไม้ที่จับคู่ Hedge แล้ว
                
                if getattr(pos, 'profit', 0) > 0:  # ไม้กำไร
                    # ตรวจสอบว่าไม้นี้ไม่มี Hedge กับคู่อื่น
                    if not self._has_hedge_pair(positions, pos):
                        additional_positions.append(pos)
                        logger.info(f"🔍 Found additional profitable position: {getattr(pos, 'ticket', 'N/A')} (${getattr(pos, 'profit', 0):.2f})")
            
            return additional_positions
            
        except Exception as e:
            logger.error(f"❌ Error finding additional positions: {e}")
            return []
    
    def _find_existing_hedge_pairs(self, positions: List[Any]) -> List[dict]:
        """หา Hedge pairs ที่มีอยู่แล้ว"""
        try:
            hedge_pairs = []
            used_positions = set()
            
            # แยกไม้ Buy และ Sell
            buy_positions = [p for p in positions if getattr(p, 'type', 0) == 0]
            sell_positions = [p for p in positions if getattr(p, 'type', 0) == 1]
            
            # หา Buy ติดลบ + Sell กำไร
            for buy_pos in buy_positions:
                if getattr(buy_pos, 'profit', 0) < 0:  # Buy ติดลบ
                    buy_ticket = getattr(buy_pos, 'ticket', 'N/A')
                    if buy_ticket in used_positions:
                        continue
                    
                    for sell_pos in sell_positions:
                        if getattr(sell_pos, 'profit', 0) > 0:  # Sell กำไร
                            sell_ticket = getattr(sell_pos, 'ticket', 'N/A')
                            if sell_ticket in used_positions:
                                continue
                            
                            # จับคู่ไม้ที่ยังไม่ได้ใช้
                            total_profit = getattr(buy_pos, 'profit', 0) + getattr(sell_pos, 'profit', 0)
                            hedge_pairs.append({
                                'buy': buy_pos,
                                'sell': sell_pos,
                                'total_profit': total_profit,
                                'type': 'BUY_LOSS_SELL_PROFIT',
                                'positions': [buy_pos, sell_pos]
                            })
                            used_positions.add(buy_ticket)
                            used_positions.add(sell_ticket)
                            logger.info(f"🔍 Existing hedge pair: Buy {buy_ticket} + Sell {sell_ticket} = ${total_profit:.2f}")
                            break
            
            # หา Sell ติดลบ + Buy กำไร
            for sell_pos in sell_positions:
                if getattr(sell_pos, 'profit', 0) < 0:  # Sell ติดลบ
                    sell_ticket = getattr(sell_pos, 'ticket', 'N/A')
                    if sell_ticket in used_positions:
                        continue
                    
                    for buy_pos in buy_positions:
                        if getattr(buy_pos, 'profit', 0) > 0:  # Buy กำไร
                            buy_ticket = getattr(buy_pos, 'ticket', 'N/A')
                            if buy_ticket in used_positions:
                                continue
                            
                            # จับคู่ไม้ที่ยังไม่ได้ใช้
                            total_profit = getattr(sell_pos, 'profit', 0) + getattr(buy_pos, 'profit', 0)
                            hedge_pairs.append({
                                'buy': buy_pos,
                                'sell': sell_pos,
                                'total_profit': total_profit,
                                'type': 'SELL_LOSS_BUY_PROFIT',
                                'positions': [sell_pos, buy_pos]
                            })
                            used_positions.add(sell_ticket)
                            used_positions.add(buy_ticket)
                            logger.info(f"🔍 Existing hedge pair: Sell {sell_ticket} + Buy {buy_ticket} = ${total_profit:.2f}")
                            break
            
            return hedge_pairs
            
        except Exception as e:
            logger.error(f"❌ Error finding existing hedge pairs: {e}")
            return []
    
    def _find_helping_combinations(self, unpaired_profitable: List[Any], existing_hedge_pairs: List[dict]) -> List[HedgeCombination]:
        """หาไม้กำไรที่ไม่มีคู่ไปช่วย Hedge pairs ที่ติดลบ"""
        try:
            helping_combinations = []
            
            if not unpaired_profitable or not existing_hedge_pairs:
                logger.info("💤 No unpaired profitable positions or existing hedge pairs to help")
                return helping_combinations
            
            # หา Hedge pairs ที่ติดลบ
            losing_hedge_pairs = [pair for pair in existing_hedge_pairs if pair['total_profit'] < 0]
            
            if not losing_hedge_pairs:
                logger.info("💤 No losing hedge pairs to help")
                return helping_combinations
            
            logger.info(f"🔍 Found {len(losing_hedge_pairs)} losing hedge pairs to help")
            
            # ลองทุกการรวมของไม้กำไรที่ไม่มีคู่
            for size in range(1, len(unpaired_profitable) + 1):
                for profitable_combo in itertools.combinations(unpaired_profitable, size):
                    profitable_total = sum(getattr(pos, 'profit', 0) for pos in profitable_combo)
                    
                    # ลองช่วย Hedge pairs แต่ละคู่
                    for hedge_pair in losing_hedge_pairs:
                        combined_profit = profitable_total + hedge_pair['total_profit']
                        
                        logger.info(f"🔍 Testing: {len(profitable_combo)} profitable positions (${profitable_total:.2f}) + hedge pair (${hedge_pair['total_profit']:.2f}) = ${combined_profit:.2f}")
                        
                        if combined_profit >= self.min_net_profit:
                            # รวมไม้ทั้งหมด
                            all_positions = list(profitable_combo) + hedge_pair['positions']
                            
                            helping_combinations.append(HedgeCombination(
                                positions=all_positions,
                                total_profit=combined_profit,
                                combination_type=f"HELPING_{hedge_pair['type']}",
                                size=len(all_positions),
                                confidence_score=95.0,
                                reason=f"Unpaired profitable positions helping hedge pair: {hedge_pair['type']}"
                            ))
                            
                            logger.info(f"✅ Found helping combination: ${combined_profit:.2f}")
            
            # เรียงตามผลรวมกำไร (มากสุดก่อน)
            helping_combinations.sort(key=lambda x: x.total_profit, reverse=True)
            
            return helping_combinations
            
        except Exception as e:
            logger.error(f"❌ Error finding helping combinations: {e}")
            return []
    
    def _has_hedge_pair(self, positions: List[Any], position: Any) -> bool:
        """ตรวจสอบว่าไม้นี้มี Hedge กับคู่อื่นหรือไม่"""
        try:
            pos_type = getattr(position, 'type', 0)
            pos_profit = getattr(position, 'profit', 0)
            
            # หาไม้ตรงข้ามที่สามารถจับคู่ Hedge ได้
            for other_pos in positions:
                if other_pos == position:
                    continue
                
                other_type = getattr(other_pos, 'type', 0)
                other_profit = getattr(other_pos, 'profit', 0)
                
                # ตรวจสอบการจับคู่ Hedge ที่เป็นไปได้
                if pos_type != other_type:  # ไม้ตรงข้าม
                    # กรณี 1: ไม้นี้ติดลบ + ไม้ตรงข้ามกำไร
                    if pos_profit < 0 and other_profit > 0:
                        return True
                    # กรณี 2: ไม้นี้กำไร + ไม้ตรงข้ามติดลบ
                    elif pos_profit > 0 and other_profit < 0:
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Error checking hedge pair: {e}")
            return False
    
    def _get_combination_type(self, positions: List[Any]) -> str:
        """📊 คำนวณประเภทการจับคู่"""
        try:
            sell_count = sum(1 for pos in positions if getattr(pos, 'type', 0) == 1)
            buy_count = sum(1 for pos in positions if getattr(pos, 'type', 0) == 0)
            
            if sell_count > buy_count:
                return f"SELL_MAJORITY_{sell_count}S+{buy_count}B"
            elif buy_count > sell_count:
                return f"BUY_MAJORITY_{buy_count}B+{sell_count}S"
            else:
                return f"BALANCED_{sell_count}S+{buy_count}B"
                
        except Exception as e:
            logger.error(f"❌ Error calculating combination type: {e}")
            return "UNKNOWN"
    
    def _calculate_confidence_score(self, positions: List[Any], total_profit: float) -> float:
        """📈 คำนวณคะแนนความมั่นใจ"""
        try:
            # คำนวณคะแนนตามปัจจัยต่างๆ
            profit_score = min(100, max(0, total_profit * 2))  # กำไร
            size_score = min(100, max(0, len(positions) * 10))  # ขนาด
            balance_score = self._calculate_balance_score(positions)  # ความสมดุล
            
            # คะแนนรวม
            total_score = (profit_score + size_score + balance_score) / 3
            
            return min(100, max(0, total_score))
            
        except Exception as e:
            logger.error(f"❌ Error calculating confidence score: {e}")
            return 50.0
    
    def _calculate_balance_score(self, positions: List[Any]) -> float:
        """⚖️ คำนวณคะแนนความสมดุล"""
        try:
            sell_count = sum(1 for pos in positions if getattr(pos, 'type', 0) == 1)
            buy_count = sum(1 for pos in positions if getattr(pos, 'type', 0) == 0)
            total_count = len(positions)
            
            if total_count == 0:
                return 0
            
            # คะแนนความสมดุล (ยิ่งสมดุลยิ่งดี)
            balance_ratio = min(sell_count, buy_count) / max(sell_count, buy_count)
            balance_score = balance_ratio * 100
            
            return balance_score
            
        except Exception as e:
            logger.error(f"❌ Error calculating balance score: {e}")
            return 50.0
    
    def _generate_additional_positions(self, positions: List[Any]) -> List[Any]:
        """📈 สร้างไม้เพิ่มเติมเพื่อจับคู่"""
        try:
            additional_positions = []
            
            # หาไม้ที่ไม่มีการจับคู่
            unmatched_positions = self._find_unmatched_positions(positions)
            
            for pos in unmatched_positions[:self.max_additional_positions]:
                if getattr(pos, 'type', 0) == 1:  # Sell ติดลบ
                    # สร้าง Buy เพื่อจับคู่
                    new_buy = self._create_opposite_position(pos, "BUY")
                    if new_buy:
                        additional_positions.append(new_buy)
                
                elif getattr(pos, 'type', 0) == 0:  # Buy ติดลบ
                    # สร้าง Sell เพื่อจับคู่
                    new_sell = self._create_opposite_position(pos, "SELL")
                    if new_sell:
                        additional_positions.append(new_sell)
            
            logger.info(f"📈 Generated {len(additional_positions)} additional positions")
            return additional_positions
            
        except Exception as e:
            logger.error(f"❌ Error generating additional positions: {e}")
            return []
    
    def _find_unmatched_positions(self, positions: List[Any]) -> List[Any]:
        """🔍 หาไม้ที่ไม่มีการจับคู่"""
        try:
            unmatched_positions = []
            
            for pos in positions:
                profit = getattr(pos, 'profit', 0)
                
                # ไม้ติดลบที่ไม่มีการจับคู่
                if profit < 0:
                    unmatched_positions.append(pos)
            
            # เรียงตามขาดทุน (มากสุดก่อน)
            unmatched_positions.sort(key=lambda x: getattr(x, 'profit', 0))
            
            logger.info(f"🔍 Found {len(unmatched_positions)} unmatched positions")
            return unmatched_positions
            
        except Exception as e:
            logger.error(f"❌ Error finding unmatched positions: {e}")
            return []
    
    def _create_opposite_position(self, original_pos: Any, opposite_type: str) -> Optional[Any]:
        """🔄 สร้างไม้ตรงข้ามเพื่อจับคู่"""
        try:
            # สร้างไม้ใหม่ (จำลอง)
            new_pos = type('Position', (), {
                'ticket': f"NEW_{int(time.time())}",
                'symbol': getattr(original_pos, 'symbol', 'XAUUSD'),
                'type': 0 if opposite_type == "BUY" else 1,
                'volume': self.additional_position_volume,
                'price_open': getattr(original_pos, 'price_current', 0),
                'price_current': getattr(original_pos, 'price_current', 0),
                'profit': 0.0,  # ไม้ใหม่ยังไม่มีกำไร
                'time': int(time.time()),
                'comment': f"Hedge for {getattr(original_pos, 'ticket', 'unknown')}"
            })()
            
            logger.info(f"🔄 Created {opposite_type} position for ticket {getattr(original_pos, 'ticket', 'unknown')}")
            return new_pos
            
        except Exception as e:
            logger.error(f"❌ Error creating opposite position: {e}")
            return None

def create_hedge_pairing_closer() -> HedgePairingCloser:
    """สร้าง Hedge Pairing Closer"""
    return HedgePairingCloser()
