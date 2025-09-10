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
            
            # 2. ไม่มีการจับคู่ที่เหมาะสม → ออกไม้เพิ่มเติม
            if self.enable_position_generation:
                logger.info("🔄 No profitable combinations found - generating additional positions")
                additional_positions = self._generate_additional_positions(positions)
                
                if additional_positions:
                    logger.info(f"📈 Generated {len(additional_positions)} additional positions")
                    # ลองหาการจับคู่อีกครั้ง
                    all_positions = positions + additional_positions
                    new_combinations = self._find_profitable_combinations(all_positions)
                    
                    if new_combinations:
                        best_combination = new_combinations[0]
                        logger.info(f"✅ NEW HEDGE COMBINATION FOUND: {best_combination.combination_type}")
                        logger.info(f"   Net P&L: ${best_combination.total_profit:.2f}")
                        logger.info(f"   Positions: {best_combination.size}")
                        
                        return ClosingDecision(
                            should_close=True,
                            positions_to_close=best_combination.positions,
                            method="HEDGE_PAIRING_WITH_GENERATION",
                            net_pnl=best_combination.total_profit,
                            expected_pnl=best_combination.total_profit,
                            position_count=best_combination.size,
                            buy_count=sum(1 for p in best_combination.positions if p.type == 0),
                            sell_count=sum(1 for p in best_combination.positions if p.type == 1),
                            confidence_score=best_combination.confidence_score,
                            reason=best_combination.reason
                        )
            
            logger.info("💤 No closing opportunities found - waiting for better conditions")
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
            
            # ถ้าไม่มี Hedge ให้หาการรวมอื่นๆ ที่ไม่ใช่แบบเดียวกัน
            profitable_combinations = []
            
            for size in range(self.min_combination_size, min(self.max_combination_size + 1, len(positions) + 1)):
                # ลองทุกการรวมของขนาดนี้
                for combination in itertools.combinations(positions, size):
                    # ตรวจสอบว่าไม่ใช่การจับคู่แบบเดียวกัน
                    if self._is_same_type_combination(combination):
                        continue  # ข้ามการจับคู่แบบเดียวกัน
                    
                    total_profit = sum(getattr(pos, 'profit', 0) for pos in combination)
                    
                    # ตรวจสอบเงื่อนไข
                    if total_profit >= self.min_net_profit:
                        combination_type = self._get_combination_type(combination)
                        confidence_score = self._calculate_confidence_score(combination, total_profit)
                        
                        profitable_combinations.append(HedgeCombination(
                            positions=list(combination),
                            total_profit=total_profit,
                            combination_type=combination_type,
                            size=size,
                            confidence_score=confidence_score,
                            reason=f"Mixed combination: {combination_type}"
                        ))
            
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
            
            logger.info(f"🔍 Analyzing hedge combinations: {len(buy_positions)} Buy, {len(sell_positions)} Sell")
            
            # Step 1: จับคู่ตรงข้ามก่อนเสมอ (ไม่สนใจผลรวม)
            hedge_pairs = []
            
            # หา Buy ติดลบ + Sell กำไร
            for buy_pos in buy_positions:
                if getattr(buy_pos, 'profit', 0) < 0:  # Buy ติดลบ
                    for sell_pos in sell_positions:
                        if getattr(sell_pos, 'profit', 0) > 0:  # Sell กำไร
                            hedge_pairs.append({
                                'buy': buy_pos,
                                'sell': sell_pos,
                                'type': 'BUY_LOSS_SELL_PROFIT'
                            })
                            logger.info(f"🔍 Found hedge pair: Buy {getattr(buy_pos, 'ticket', 'N/A')} (${getattr(buy_pos, 'profit', 0):.2f}) + Sell {getattr(sell_pos, 'ticket', 'N/A')} (${getattr(sell_pos, 'profit', 0):.2f})")
            
            # หา Sell ติดลบ + Buy กำไร
            for sell_pos in sell_positions:
                if getattr(sell_pos, 'profit', 0) < 0:  # Sell ติดลบ
                    for buy_pos in buy_positions:
                        if getattr(buy_pos, 'profit', 0) > 0:  # Buy กำไร
                            hedge_pairs.append({
                                'buy': buy_pos,
                                'sell': sell_pos,
                                'type': 'SELL_LOSS_BUY_PROFIT'
                            })
                            logger.info(f"🔍 Found hedge pair: Sell {getattr(sell_pos, 'ticket', 'N/A')} (${getattr(sell_pos, 'profit', 0):.2f}) + Buy {getattr(buy_pos, 'ticket', 'N/A')} (${getattr(buy_pos, 'profit', 0):.2f})")
            
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
    
    def _has_hedge_pair(self, positions: List[Any], position: Any) -> bool:
        """ตรวจสอบว่าไม้นี้มี Hedge กับคู่อื่นหรือไม่"""
        try:
            pos_type = getattr(position, 'type', 0)
            pos_profit = getattr(position, 'profit', 0)
            
            # หาไม้ตรงข้ามที่กำไร
            for other_pos in positions:
                if other_pos == position:
                    continue
                
                other_type = getattr(other_pos, 'type', 0)
                other_profit = getattr(other_pos, 'profit', 0)
                
                # ตรวจสอบว่าเป็นไม้ตรงข้ามและกำไร
                if pos_type != other_type and other_profit > 0:
                    return True  # มี Hedge กับคู่อื่น
            
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
