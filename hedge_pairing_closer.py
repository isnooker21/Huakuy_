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
        """🔍 หาการจับคู่ไม้ที่ผลรวมเป็นบวก"""
        try:
            profitable_combinations = []
            
            # ลองทุกขนาดของการรวม (2 ถึง max_combination_size)
            for size in range(self.min_combination_size, min(self.max_combination_size + 1, len(positions) + 1)):
                # ลองทุกการรวมของขนาดนี้
                for combination in itertools.combinations(positions, size):
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
                            reason=f"Hedge combination: {combination_type}"
                        ))
            
            # เรียงตามผลรวมกำไร (มากสุดก่อน)
            profitable_combinations.sort(key=lambda x: x.total_profit, reverse=True)
            
            logger.info(f"🔍 Found {len(profitable_combinations)} profitable combinations")
            return profitable_combinations
            
        except Exception as e:
            logger.error(f"❌ Error finding profitable combinations: {e}")
            return []
    
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
