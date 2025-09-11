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
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing

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
        
        # 🚀 Performance Optimization
        self.use_parallel_processing = True  # ใช้การประมวลผลแบบขนาน
        self.max_workers = min(4, multiprocessing.cpu_count())  # จำนวน thread สูงสุด
        
        # 🧠 Smart Caching
        self.combination_cache = {}  # เก็บผลลัพธ์การจับคู่ไว้
        self.cache_hit_count = 0
        self.cache_miss_count = 0
        
        # ⚡ Early Termination
        self.early_termination_threshold = 5  # หยุดเมื่อพบ 5 combinations ที่ดี
        self.best_profit_threshold = 2.0  # หยุดเมื่อกำไรมากกว่า 2 เท่าของ threshold
        
        # 🎯 Smart Filtering for Large Portfolios
        self.large_portfolio_threshold = 30  # ถ้ามีไม้มากกว่า 30 ตัว
        self.max_positions_to_analyze = 20   # วิเคราะห์สูงสุด 20 ตัว
        self.priority_filtering = True       # ใช้การกรองตามความสำคัญ
        
        # 🚨 Emergency Mode Parameters (สำหรับพอร์ตที่แย่มาก)
        self.emergency_min_net_profit = 0.01  # กำไรขั้นต่ำในโหมดฉุกเฉิน $0.01
        self.emergency_threshold_percentage = 0.10  # 10% ในโหมดฉุกเฉิน
        
        # 🔧 Position Generation Parameters
        self.enable_position_generation = True  # เปิดใช้งานการออกไม้เพิ่มเติม
        self.max_additional_positions = 3       # จำนวนไม้เพิ่มเติมสูงสุด
        self.additional_position_volume = 0.01  # ขนาดไม้เพิ่มเติม
        
        # 🚀 Real-time P&L System
        self.pnl_cache = {}  # เก็บข้อมูล P&L ไว้
        self.cache_timeout = 1.0  # หมดอายุใน 1 วินาที
        self.portfolio_health_score = "ปานกลาง"  # สุขภาพพอร์ต
        self.performance_history = []  # ประวัติประสิทธิภาพ
        self.mt5_connection = None  # จะถูกตั้งค่าในภายหลัง
        
        logger.info("🚀 Hedge Pairing Closer initialized")
    
    def _parallel_search_combinations(self, positions: List[Any], search_type: str) -> List[HedgeCombination]:
        """🚀 Parallel search for combinations using multiple threads"""
        if not self.use_parallel_processing or len(positions) < 10:
            return []
        
        combinations = []
        
        # แบ่ง positions เป็น chunks สำหรับ parallel processing
        chunk_size = max(1, len(positions) // self.max_workers)
        position_chunks = [positions[i:i + chunk_size] for i in range(0, len(positions), chunk_size)]
        
        def search_chunk(chunk):
            chunk_combinations = []
            # ค้นหา combinations ใน chunk นี้
            for i, pos1 in enumerate(chunk):
                for j, pos2 in enumerate(chunk[i+1:], i+1):
                    if getattr(pos1, 'type', 0) != getattr(pos2, 'type', 0):  # ไม้ตรงข้าม
                        total_profit = getattr(pos1, 'profit', 0) + getattr(pos2, 'profit', 0)
                        if total_profit >= self.min_net_profit:
                            chunk_combinations.append(HedgeCombination(
                                positions=[pos1, pos2],
                                total_profit=total_profit,
                                combination_type=f"PARALLEL_{search_type}",
                                size=2,
                                confidence_score=85.0,
                                reason=f"Parallel {search_type}: ${total_profit:.2f}"
                            ))
            return chunk_combinations
        
        # ใช้ ThreadPoolExecutor สำหรับ parallel processing
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_chunk = {executor.submit(search_chunk, chunk): chunk for chunk in position_chunks}
            
            for future in as_completed(future_to_chunk):
                try:
                    chunk_combinations = future.result()
                    combinations.extend(chunk_combinations)
                except Exception as e:
                    logger.error(f"Error in parallel search: {e}")
        
        return combinations
    
    def _get_cache_key(self, positions: List[Any], search_type: str) -> str:
        """สร้าง cache key จาก positions"""
        # สร้าง key จาก ticket numbers และ profit
        position_data = []
        for pos in positions:
            position_data.append(f"{getattr(pos, 'ticket', 0)}_{getattr(pos, 'profit', 0):.2f}")
        
        return f"{search_type}_{hash(tuple(sorted(position_data)))}"
    
    def _get_cached_combinations(self, positions: List[Any], search_type: str) -> Optional[List[HedgeCombination]]:
        """ดึงผลลัพธ์จาก cache"""
        cache_key = self._get_cache_key(positions, search_type)
        
        if cache_key in self.combination_cache:
            self.cache_hit_count += 1
            logger.debug(f"🎯 Cache HIT for {search_type}")
            return self.combination_cache[cache_key]
        
        self.cache_miss_count += 1
        return None
    
    def _cache_combinations(self, positions: List[Any], search_type: str, combinations: List[HedgeCombination]):
        """เก็บผลลัพธ์ใน cache"""
        cache_key = self._get_cache_key(positions, search_type)
        self.combination_cache[cache_key] = combinations
        
        # จำกัดขนาด cache
        if len(self.combination_cache) > 100:
            # ลบ cache เก่าออก
            oldest_key = next(iter(self.combination_cache))
            del self.combination_cache[oldest_key]
    
    def _should_terminate_early(self, combinations: List[HedgeCombination], current_profit: float) -> bool:
        """ตรวจสอบว่าควรหยุดการค้นหาเร็วหรือไม่"""
        # หยุดเมื่อพบ combinations เพียงพอ
        if len(combinations) >= self.early_termination_threshold:
            return True
        
        # หยุดเมื่อกำไรมากกว่า threshold
        if current_profit >= self.min_net_profit * self.best_profit_threshold:
            return True
        
        return False
    
    def _smart_position_selection(self, positions: List[Any]) -> List[Any]:
        """🎯 เลือกไม้ที่สำคัญที่สุดสำหรับการวิเคราะห์"""
        if len(positions) <= self.large_portfolio_threshold:
            return positions  # ไม่ต้องกรองถ้าไม้ไม่เยอะ
        
        logger.info(f"🎯 Smart Selection: {len(positions)} → {self.max_positions_to_analyze} positions")
        
        # แยกไม้ตามประเภท
        buy_positions = [pos for pos in positions if getattr(pos, 'type', 0) == 0]
        sell_positions = [pos for pos in positions if getattr(pos, 'type', 0) == 1]
        
        # คำนวณ priority score สำหรับแต่ละไม้
        def calculate_priority_score(pos):
            profit = getattr(pos, 'profit', 0)
            volume = getattr(pos, 'volume', 0.01)
            
            # ไม้ที่ขาดทุนมาก = priority สูง (ต้องปิดก่อน)
            # ไม้ที่กำไรมาก = priority สูง (ใช้ช่วยได้)
            if profit < 0:
                return abs(profit) * 10  # ขาดทุนมาก = priority สูง
            else:
                return profit * 5  # กำไรมาก = priority สูง
        
        # เรียงตาม priority score
        buy_positions.sort(key=calculate_priority_score, reverse=True)
        sell_positions.sort(key=calculate_priority_score, reverse=True)
        
        # เลือกไม้ที่สำคัญที่สุด
        selected_buy = buy_positions[:self.max_positions_to_analyze // 2]
        selected_sell = sell_positions[:self.max_positions_to_analyze // 2]
        
        selected_positions = selected_buy + selected_sell
        
        logger.info(f"📊 Selected: {len(selected_buy)} Buy, {len(selected_sell)} Sell")
        
        return selected_positions
    
    def set_mt5_connection(self, mt5_connection):
        """ตั้งค่า MT5 Connection สำหรับ Real-time P&L"""
        self.mt5_connection = mt5_connection
        logger.info("🔗 MT5 Connection set for Real-time P&L")
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """📊 ดูสถิติประสิทธิภาพของระบบ"""
        total_cache_requests = self.cache_hit_count + self.cache_miss_count
        cache_hit_rate = (self.cache_hit_count / total_cache_requests * 100) if total_cache_requests > 0 else 0
        
        return {
            'cache_hit_rate': f"{cache_hit_rate:.1f}%",
            'cache_hits': self.cache_hit_count,
            'cache_misses': self.cache_miss_count,
            'cached_combinations': len(self.combination_cache),
            'parallel_processing': self.use_parallel_processing,
            'max_workers': self.max_workers,
            'early_termination_threshold': self.early_termination_threshold,
            'smart_filtering': self.priority_filtering,
            'large_portfolio_threshold': self.large_portfolio_threshold,
            'max_positions_to_analyze': self.max_positions_to_analyze
        }
    
    def _get_real_time_pnl(self, position: Any) -> float:
        """ดึง Floating P&L แบบ Real-time"""
        try:
            # ใช้ Caching เพื่อความเร็ว
            ticket = getattr(position, 'ticket', 'N/A')
            current_time = time.time()
            
            # ตรวจสอบว่า cache ยังใช้ได้ไหม
            if ticket in self.pnl_cache:
                cached_data = self.pnl_cache[ticket]
                if current_time - cached_data['timestamp'] < self.cache_timeout:
                    return cached_data['pnl']  # ใช้ข้อมูลเก่า
            
            # คำนวณ P&L จากราคาปัจจุบัน
            if self.mt5_connection and hasattr(self.mt5_connection, 'get_current_price'):
                current_price = self.mt5_connection.get_current_price(getattr(position, 'symbol', ''))
                if current_price is not None:
                    # คำนวณ P&L จริง
                    if getattr(position, 'type', 0) == 0:  # Buy
                        pnl = (current_price - getattr(position, 'open_price', 0)) * getattr(position, 'volume', 0) * 100000
                    else:  # Sell
                        pnl = (getattr(position, 'open_price', 0) - current_price) * getattr(position, 'volume', 0) * 100000
                    
                    # เก็บไว้ใน cache
                    self.pnl_cache[ticket] = {
                        'pnl': pnl,
                        'timestamp': current_time
                    }
                    
                    return pnl
            
            # Fallback: ใช้ข้อมูลเก่า
            fallback_pnl = getattr(position, 'profit', 0)
            self.pnl_cache[ticket] = {
                'pnl': fallback_pnl,
                'timestamp': current_time
            }
            
            return fallback_pnl
            
        except Exception as e:
            logger.error(f"Error getting real-time P&L: {e}")
            return getattr(position, 'profit', 0)
    
    def _analyze_portfolio_health(self, positions: List[Any], account_balance: float = 1000.0) -> dict:
        """วิเคราะห์สุขภาพพอร์ต"""
        try:
            # คำนวณ Floating P&L จริง
            real_pnl_list = [self._get_real_time_pnl(pos) for pos in positions]
            total_pnl = sum(real_pnl_list)
            position_count = len(positions)
            
            # คำนวณสุขภาพพอร์ต
            if total_pnl > 100:
                health_score = "ดีมาก"
            elif total_pnl > 0:
                health_score = "ดี"
            elif total_pnl > -50:
                health_score = "ปานกลาง"
            elif total_pnl > -100:
                health_score = "แย่"
            else:
                health_score = "แย่มาก"
            
            # คำนวณค่าเฉลี่ยของเงินทุนต่อไม้
            avg_balance_per_position = account_balance / position_count if position_count > 0 else account_balance
            
            self.portfolio_health_score = health_score
            
            return {
                'total_pnl': total_pnl,
                'position_count': position_count,
                'health_score': health_score,
                'avg_balance_per_position': avg_balance_per_position,
                'avg_pnl_per_position': total_pnl / position_count if position_count > 0 else 0
            }
        except Exception as e:
            logger.error(f"Error analyzing portfolio health: {e}")
            return {'health_score': 'ปานกลาง', 'total_pnl': 0}
    
    def find_optimal_closing(self, positions: List[Any], account_info: Dict, 
                           market_conditions: Optional[Dict] = None) -> Optional[ClosingDecision]:
        """
        🧠 หาการปิดไม้ที่ดีที่สุดแบบจับคู่
        """
        start_time = time.time()
        try:
            if len(positions) < 1:
                logger.info("⏸️ Need at least 1 position for analysis")
                return None
            
            # 🎯 Smart Position Selection สำหรับพอร์ตใหญ่
            if self.priority_filtering and len(positions) > self.large_portfolio_threshold:
                positions = self._smart_position_selection(positions)
                logger.info(f"🎯 Using Smart Selection: {len(positions)} positions")
            
            logger.info(f"🔍 HEDGE ANALYSIS: {len(positions)} positions")
            
            # Step 1: วิเคราะห์สุขภาพพอร์ต
            account_balance = account_info.get('balance', 1000.0)
            portfolio_health = self._analyze_portfolio_health(positions, account_balance)
            logger.info(f"📊 Portfolio Health: {portfolio_health['health_score']} (P&L: ${portfolio_health['total_pnl']:.2f})")
            
            # แสดง Emergency Mode ถ้าพอร์ตแย่มาก
            if portfolio_health['health_score'] in ["แย่", "แย่มาก"]:
                effective_min_profit = self._get_effective_min_net_profit()
                threshold_percentage = self._get_threshold_percentage()
                logger.warning(f"🚨 EMERGENCY MODE ACTIVATED!")
                logger.warning(f"   Min Net Profit: ${effective_min_profit:.2f} (ลดจาก ${self.min_net_profit:.2f})")
                logger.warning(f"   Threshold: {threshold_percentage*100:.1f}% (ลดลง)")
                logger.warning(f"   ระบบจะพยายามปิดไม้ให้ได้มากขึ้น!")
                
                # แสดงคำแนะนำสำหรับพอร์ตที่แย่มาก
                if portfolio_health['total_pnl'] < -50:
                    logger.warning(f"💡 คำแนะนำ: พอร์ตขาดทุนมาก (${portfolio_health['total_pnl']:.2f})")
                    logger.warning(f"   - รอให้ราคากลับมาหรือ")
                    logger.warning(f"   - ปิดไม้ที่ขาดทุนน้อยที่สุดก่อน")
                    logger.warning(f"   - หรือเพิ่มเงินทุนเพื่อลดความเสี่ยง")
            
            # Step 2: Smart Filtering - คัดกรองไม้ตามค่าเฉลี่ยของเงินทุน
            filtered_positions = self._smart_filter_positions(positions, account_balance)
            logger.info(f"🔍 Smart Filtering: {len(positions)} → {len(filtered_positions)} positions")
            
            # 1. หาการจับคู่ไม้ที่มีอยู่
            profitable_combinations = self._find_profitable_combinations(filtered_positions)
            
            if profitable_combinations:
                # มีการจับคู่ที่เหมาะสม → ปิดไม้
                best_combination = profitable_combinations[0]
                logger.info(f"✅ HEDGE COMBINATION FOUND: {best_combination.combination_type}")
                logger.info(f"   Net P&L: ${best_combination.total_profit:.2f}")
                logger.info(f"   Positions: {best_combination.size}")
                
                # บันทึกประสิทธิภาพ
                processing_time = time.time() - start_time
                self._record_performance(True, best_combination.total_profit, processing_time)
                
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
            logger.info("=" * 60)
            logger.info("💤 NO PROFITABLE COMBINATIONS FOUND")
            logger.info("=" * 60)
            logger.info(f"📊 Current positions: {len(positions)} total")
            logger.info(f"📊 Buy positions: {len([p for p in positions if getattr(p, 'type', 0) == 0])}")
            logger.info(f"📊 Sell positions: {len([p for p in positions if getattr(p, 'type', 0) == 1])}")
            
            logger.info("-" * 40)
            logger.info("📋 DETAILED POSITION LIST")
            logger.info("-" * 40)
            # แสดงข้อมูลไม้ทั้งหมด
            for pos in positions:
                pos_type = "BUY" if getattr(pos, 'type', 0) == 0 else "SELL"
                profit = getattr(pos, 'profit', 0)
                ticket = getattr(pos, 'ticket', 'N/A')
                has_hedge = self._has_hedge_pair(positions, pos)
                hedge_status = "🔗 HEDGED" if has_hedge else "💤 NO HEDGE"
                logger.info(f"   {ticket}: {pos_type} ${profit:.2f} - {hedge_status}")
            
            logger.info("=" * 60)
            
            # บันทึกประสิทธิภาพ
            processing_time = time.time() - start_time
            self._record_performance(False, 0.0, processing_time)
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error in hedge pairing analysis: {e}")
            processing_time = time.time() - start_time
            self._record_performance(False, 0.0, processing_time)
            return None
    
    def _smart_filter_positions(self, positions: List[Any], account_balance: float = 1000.0) -> List[Any]:
        """🔍 Smart Filtering - คัดกรองไม้ตามค่าเฉลี่ยของเงินทุน"""
        try:
            # คำนวณ threshold ตามค่าเฉลี่ยของเงินทุน
            threshold = self._calculate_portfolio_threshold(account_balance, len(positions))
            
            filtered_positions = []
            for pos in positions:
                # ใช้ P&L แบบ Real-time
                real_pnl = self._get_real_time_pnl(pos)
                volume = getattr(pos, 'volume', 0)
                
                # คัดกรองตามเงื่อนไข (ใช้ threshold ที่คำนวณจากค่าเฉลี่ยของเงินทุน)
                # รับไม้ทั้งหมด (ทั้งกำไรและขาดทุน)
                if True:  # รับไม้ทั้งหมด
                    if volume >= 0.01:  # ไม่เอาไม้ที่เล็กเกินไป
                        if abs(real_pnl) >= 0.1:  # ไม่เอาไม้ที่กำไร/ขาดทุนน้อยเกินไป
                            filtered_positions.append(pos)
                        else:
                            logger.debug(f"🔍 Filtered out: {getattr(pos, 'ticket', 'N/A')} (profit too small: ${real_pnl:.2f})")
                    else:
                        logger.debug(f"🔍 Filtered out: {getattr(pos, 'ticket', 'N/A')} (volume too small: {volume:.2f})")
                else:
                    logger.debug(f"🔍 Filtered out: {getattr(pos, 'ticket', 'N/A')} (loss too large: ${real_pnl:.2f})")
            
            logger.info(f"🔍 Smart Filtering: {len(positions)} → {len(filtered_positions)} positions (threshold: ${threshold:.2f})")
            return filtered_positions
            
        except Exception as e:
            logger.error(f"❌ Error in smart filtering: {e}")
            return positions  # Return original positions if error
    
    def _calculate_portfolio_threshold(self, account_balance: float, position_count: int) -> float:
        """คำนวณ threshold ตามค่าเฉลี่ยของเงินทุน"""
        try:
            if position_count == 0:
                return 0.0
            
            # คำนวณค่าเฉลี่ยของเงินทุนต่อไม้
            avg_balance_per_position = account_balance / position_count
            
            # คำนวณ threshold ตามเปอร์เซ็นต์ของเงินทุน
            threshold_percentage = self._get_threshold_percentage()
            threshold = avg_balance_per_position * threshold_percentage
            
            # กำหนด Min/Max threshold
            min_threshold = 1.0   # ไม่ต่ำกว่า $1.00
            max_threshold = 100.0 # ไม่สูงกว่า $100.00
            
            threshold = max(min_threshold, min(threshold, max_threshold))
            
            return threshold
        except Exception as e:
            logger.error(f"Error calculating portfolio threshold: {e}")
            return 10.0
    
    def _get_threshold_percentage(self) -> float:
        """ได้ threshold percentage ตามสุขภาพพอร์ต"""
        try:
            if self.portfolio_health_score == "ดีมาก":
                return 0.05  # 5%
            elif self.portfolio_health_score == "ดี":
                return 0.08  # 8%
            elif self.portfolio_health_score == "ปานกลาง":
                return 0.10  # 10%
            elif self.portfolio_health_score == "แย่":
                return 0.15  # 15%
            else:  # แย่มาก
                return 0.20  # 20%
        except Exception as e:
            logger.error(f"Error getting threshold percentage: {e}")
            return 0.10  # Default 10%
    
    def _get_effective_min_net_profit(self) -> float:
        """ได้ min_net_profit ที่มีประสิทธิภาพตามสุขภาพพอร์ต"""
        try:
            if self.portfolio_health_score in ["แย่", "แย่มาก"]:
                return self.emergency_min_net_profit  # $0.05 ในโหมดฉุกเฉิน
            else:
                return self.min_net_profit  # $0.1 ปกติ
        except Exception as e:
            logger.error(f"Error getting effective min net profit: {e}")
            return self.min_net_profit
    
    def _priority_based_selection(self, positions: List[Any]) -> List[Any]:
        """🎯 Priority-based Selection - เลือกไม้ตามความสำคัญ"""
        try:
            # คำนวณ Priority Score สำหรับแต่ละไม้
            priority_scores = []
            for pos in positions:
                priority_score = self._calculate_priority_score(pos)
                priority_scores.append((priority_score, pos))
            
            # เรียงตาม Priority Score (มากสุดก่อน)
            priority_scores.sort(key=lambda x: x[0], reverse=True)
            
            # เลือกเฉพาะไม้ที่มี Priority สูง (สูงสุด 15 ไม้)
            max_positions = min(15, len(positions))
            priority_positions = [pos for _, pos in priority_scores[:max_positions]]
            
            logger.info(f"🎯 Priority Selection: {len(positions)} → {len(priority_positions)} positions")
            return priority_positions
            
        except Exception as e:
            logger.error(f"❌ Error in priority selection: {e}")
            return positions  # Return original positions if error
    
    def _calculate_priority_score(self, position: Any) -> float:
        """📊 คำนวณ Priority Score จาก Real-time P&L"""
        try:
            # ใช้ P&L แบบ Real-time
            real_pnl = self._get_real_time_pnl(position)
            volume = getattr(position, 'volume', 0)
            
            # คำนวณ Priority Score
            priority_score = 0
            
            # ไม้ที่กำไรมาก = Priority สูง
            if real_pnl > 0:
                priority_score += real_pnl * 10
            
            # ไม้ที่ขาดทุนน้อย = Priority ปานกลาง
            elif real_pnl > -2.0:
                priority_score += abs(real_pnl) * 5
            
            # ไม้ที่ขาดทุนมาก = Priority ต่ำ
            else:
                priority_score += abs(real_pnl) * 2
            
            # ปริมาณมาก = Priority สูง
            priority_score += volume * 100
            
            # เพิ่มคะแนนตามสุขภาพพอร์ต
            if self.portfolio_health_score == "ดีมาก":
                priority_score *= 1.2  # เพิ่ม 20%
            elif self.portfolio_health_score == "ดี":
                priority_score *= 1.1  # เพิ่ม 10%
            elif self.portfolio_health_score == "แย่":
                priority_score *= 0.9   # ลด 10%
            elif self.portfolio_health_score == "แย่มาก":
                priority_score *= 0.8  # ลด 20%
            
            return priority_score
            
        except Exception as e:
            logger.error(f"❌ Error calculating priority score: {e}")
            return 0.0
    
    def _validate_system_performance(self) -> dict:
        """ตรวจสอบประสิทธิภาพระบบแบบ Real-time"""
        try:
            # ตรวจสอบความแม่นยำของการจับคู่
            accuracy_score = self._calculate_accuracy_score()
            
            # ตรวจสอบประสิทธิภาพการปิดไม้
            efficiency_score = self._calculate_efficiency_score()
            
            # ตรวจสอบความเร็วในการทำงาน
            speed_score = self._calculate_speed_score()
            
            # คำนวณ Overall Performance Score
            overall_score = (accuracy_score + efficiency_score + speed_score) / 3
            
            return {
                'accuracy_score': accuracy_score,
                'efficiency_score': efficiency_score,
                'speed_score': speed_score,
                'overall_score': overall_score,
                'status': 'ดีมาก' if overall_score > 0.8 else 'ดี' if overall_score > 0.6 else 'ปานกลาง'
            }
        except Exception as e:
            logger.error(f"Error validating system performance: {e}")
            return {}
    
    def _calculate_accuracy_score(self) -> float:
        """คำนวณ Accuracy Score"""
        try:
            # คำนวณจากประวัติประสิทธิภาพ
            if len(self.performance_history) < 5:
                return 0.75  # Default score
            
            recent_performance = self.performance_history[-10:]  # 10 ครั้งล่าสุด
            successful_closes = sum(1 for p in recent_performance if p.get('success', False))
            accuracy = successful_closes / len(recent_performance)
            
            return accuracy
        except Exception as e:
            logger.error(f"Error calculating accuracy score: {e}")
            return 0.75
    
    def _calculate_efficiency_score(self) -> float:
        """คำนวณ Efficiency Score"""
        try:
            # คำนวณจากประวัติประสิทธิภาพ
            if len(self.performance_history) < 5:
                return 0.70  # Default score
            
            recent_performance = self.performance_history[-10:]  # 10 ครั้งล่าสุด
            avg_profit = sum(p.get('profit', 0) for p in recent_performance) / len(recent_performance)
            
            # Normalize efficiency score (0-1)
            efficiency = min(1.0, max(0.0, (avg_profit + 10) / 20))  # -10 to +10 range
            
            return efficiency
        except Exception as e:
            logger.error(f"Error calculating efficiency score: {e}")
            return 0.70
    
    def _calculate_speed_score(self) -> float:
        """คำนวณ Speed Score"""
        try:
            # คำนวณจากประวัติประสิทธิภาพ
            if len(self.performance_history) < 5:
                return 0.80  # Default score
            
            recent_performance = self.performance_history[-10:]  # 10 ครั้งล่าสุด
            avg_time = sum(p.get('processing_time', 1.0) for p in recent_performance) / len(recent_performance)
            
            # Normalize speed score (0-1) - ยิ่งเร็วยิ่งดี
            speed = max(0.0, min(1.0, 2.0 - avg_time))  # 0-2 seconds range
            
            return speed
        except Exception as e:
            logger.error(f"Error calculating speed score: {e}")
            return 0.80
    
    def _record_performance(self, success: bool, profit: float, processing_time: float):
        """บันทึกประสิทธิภาพ"""
        try:
            performance_record = {
                'timestamp': time.time(),
                'success': success,
                'profit': profit,
                'processing_time': processing_time,
                'portfolio_health': self.portfolio_health_score
            }
            
            self.performance_history.append(performance_record)
            
            # เก็บเฉพาะ 100 รายการล่าสุด
            if len(self.performance_history) > 100:
                self.performance_history = self.performance_history[-100:]
                
        except Exception as e:
            logger.error(f"Error recording performance: {e}")
    
    def _find_helping_positions_for_hedged(self, positions: List[Any]) -> List[HedgeCombination]:
        """🔍 หาตัวช่วยสำหรับไม้ที่ HEDGED แล้ว"""
        try:
            combinations = []
            
            # หาไม้ที่ยังไม่ได้ใช้ (NO HEDGE)
            unpaired_positions = []
            for pos in positions:
                if not self._has_hedge_pair(positions, pos):
                    unpaired_positions.append(pos)
            
            logger.debug(f"🔍 Helping Positions: Found {len(unpaired_positions)} unpaired positions")
            
            if len(unpaired_positions) == 0:
                logger.debug("💤 No unpaired positions to help with")
                return combinations
            
            # หาไม้กำไรที่ยังไม่ได้ใช้
            profitable_unpaired = [pos for pos in unpaired_positions if getattr(pos, 'profit', 0) > 0]
            
            if len(profitable_unpaired) == 0:
                logger.debug("💤 No profitable unpaired positions to help with")
                return combinations
            
            logger.debug(f"💰 Found {len(profitable_unpaired)} profitable unpaired positions")
            
            # หาไม้ที่ HEDGED แล้วและติดลบ
            hedged_losing_pairs = []
            for pos in positions:
                if self._has_hedge_pair(positions, pos) and getattr(pos, 'profit', 0) < 0:
                    # หาคู่ของไม้นี้
                    pair_pos = self._find_pair_position(positions, pos)
                    if pair_pos:
                        pair_profit = getattr(pos, 'profit', 0) + getattr(pair_pos, 'profit', 0)
                        if pair_profit < 0:  # คู่ติดลบ
                            hedged_losing_pairs.append({
                                'buy': pos if getattr(pos, 'type', 0) == 0 else pair_pos,
                                'sell': pos if getattr(pos, 'type', 0) == 1 else pair_pos,
                                'profit': pair_profit
                            })
            
            logger.debug(f"📉 Found {len(hedged_losing_pairs)} losing hedge pairs")
            
            # ลองเพิ่มไม้กำไรที่ยังไม่ได้ใช้มาช่วยคู่ที่ติดลบ (จำกัดจำนวนการค้นหา)
            max_searches = min(50, len(hedged_losing_pairs) * len(profitable_unpaired))  # จำกัดการค้นหาสูงสุด 50 ครั้ง
            search_count = 0
            
            for losing_pair in hedged_losing_pairs:
                if search_count >= max_searches:
                    break
                    
                for helper_pos in profitable_unpaired:
                    if search_count >= max_searches:
                        break
                        
                    search_count += 1
                    total_profit = losing_pair['profit'] + getattr(helper_pos, 'profit', 0)
                    
                    if total_profit >= self.min_net_profit:
                        combinations.append(HedgeCombination(
                            positions=[losing_pair['buy'], losing_pair['sell'], helper_pos],
                            total_profit=total_profit,
                            combination_type="HELPING_HEDGED",
                            size=3,
                            confidence_score=90.0,
                            reason=f"Helping hedged pair: ${losing_pair['profit']:.2f} + Helper ${getattr(helper_pos, 'profit', 0):.2f}"
                        ))
                        
                        # หยุดเมื่อพบ combination ที่ดีแล้ว
                        if len(combinations) >= 3:
                            break
                
                if len(combinations) >= 3:
                    break
            
            # เรียงตามกำไร (มากสุดก่อน)
            combinations.sort(key=lambda x: x.total_profit, reverse=True)
            
            logger.info(f"🔍 Helping Positions: Found {len(combinations)} helping combinations")
            return combinations
            
        except Exception as e:
            logger.error(f"❌ Error in find helping positions for hedged: {e}")
            return []
    
    def _find_pair_position(self, positions: List[Any], position: Any) -> Optional[Any]:
        """🔍 หาคู่ของไม้ที่กำหนด"""
        try:
            pos_ticket = getattr(position, 'ticket', 'N/A')
            pos_type = getattr(position, 'type', 0)
            
            # หาไม้ตรงข้ามที่ยังไม่ได้ใช้
            for other_pos in positions:
                other_ticket = getattr(other_pos, 'ticket', 'N/A')
                other_type = getattr(other_pos, 'type', 0)
                
                if other_ticket != pos_ticket and other_type != pos_type:
                    # ตรวจสอบว่าไม้นี้เป็นคู่กันหรือไม่
                    if self._is_hedge_pair(position, other_pos):
                        return other_pos
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error finding pair position: {e}")
            return None
    
    def _is_hedge_pair(self, pos1: Any, pos2: Any) -> bool:
        """🔍 ตรวจสอบว่าไม้ 2 ตัวเป็นคู่กันหรือไม่"""
        try:
            type1 = getattr(pos1, 'type', 0)
            type2 = getattr(pos2, 'type', 0)
            
            # ต้องเป็นไม้ตรงข้าม
            if type1 == type2:
                return False
            
            # ต้องมีไม้หนึ่งกำไรและอีกไม้หนึ่งขาดทุน
            profit1 = getattr(pos1, 'profit', 0)
            profit2 = getattr(pos2, 'profit', 0)
            
            return (profit1 > 0 and profit2 < 0) or (profit1 < 0 and profit2 > 0)
            
        except Exception as e:
            logger.error(f"❌ Error checking hedge pair: {e}")
            return False
    
    def _try_alternative_pairing(self, positions: List[Any]) -> List[HedgeCombination]:
        """🔄 ลองจับคู่ใหม่จากไม้ทั้งหมดโดยไม่สนใจสถานะ HEDGED"""
        try:
            combinations = []
            
            # แยกไม้ตามประเภท
            buy_positions = [pos for pos in positions if getattr(pos, 'type', 0) == 0]
            sell_positions = [pos for pos in positions if getattr(pos, 'type', 0) == 1]
            
            logger.info(f"🔍 Alternative Pairing: {len(buy_positions)} Buy, {len(sell_positions)} Sell")
            
            # ลองจับคู่ Buy + Sell ทุกคู่ที่เป็นไปได้ (จำกัดจำนวนการค้นหา)
            max_searches = min(100, len(buy_positions) * len(sell_positions))  # จำกัดการค้นหาสูงสุด 100 ครั้ง
            search_count = 0
            
            for buy_pos in buy_positions:
                if search_count >= max_searches:
                    break
                    
                for sell_pos in sell_positions:
                    if search_count >= max_searches:
                        break
                        
                    search_count += 1
                    total_profit = getattr(buy_pos, 'profit', 0) + getattr(sell_pos, 'profit', 0)
                    
                    # ใช้ effective_min_profit แทน self.min_net_profit
                    effective_min_profit = self._get_effective_min_net_profit()
                    if total_profit >= effective_min_profit:
                        combinations.append(HedgeCombination(
                            positions=[buy_pos, sell_pos],
                            total_profit=total_profit,
                            combination_type="ALTERNATIVE_PAIR",
                            size=2,
                            confidence_score=90.0,
                            reason=f"Alternative pair: Buy ${getattr(buy_pos, 'profit', 0):.2f} + Sell ${getattr(sell_pos, 'profit', 0):.2f}"
                        ))
                        
                        # หยุดเมื่อพบ combination ที่ดีแล้ว
                        if len(combinations) >= 5:
                            break
                
                if len(combinations) >= 5:
                    break
            
            # เรียงตามกำไร (มากสุดก่อน)
            combinations.sort(key=lambda x: x.total_profit, reverse=True)
            
            logger.info(f"🔄 Alternative Pairing: Found {len(combinations)} possible pairs")
            return combinations
            
        except Exception as e:
            logger.error(f"❌ Error in try alternative pairing: {e}")
            return []
    
    def _try_dynamic_re_pairing(self, positions: List[Any]) -> List[HedgeCombination]:
        """🔄 ลองจับคู่ใหม่จากไม้ทั้งหมดเมื่อไม่มี Hedge Combinations"""
        try:
            combinations = []
            
            # แยกไม้ตามประเภท
            buy_positions = [pos for pos in positions if getattr(pos, 'type', 0) == 0]
            sell_positions = [pos for pos in positions if getattr(pos, 'type', 0) == 1]
            
            logger.info(f"🔍 Dynamic Re-pairing: {len(buy_positions)} Buy, {len(sell_positions)} Sell")
            
            # ลองจับคู่ Buy + Sell ทุกคู่ที่เป็นไปได้ (จำกัดจำนวนการค้นหา)
            max_searches = min(50, len(buy_positions) * len(sell_positions))  # จำกัดการค้นหาสูงสุด 50 ครั้ง
            search_count = 0
            
            for buy_pos in buy_positions:
                if test_count >= max_tests:
                    break
                    
                for sell_pos in sell_positions:
                    if test_count >= max_tests:
                        break
                        
                    test_count += 1
                    total_profit = getattr(buy_pos, 'profit', 0) + getattr(sell_pos, 'profit', 0)
                    
                    # ใช้ effective_min_profit แทน self.min_net_profit
                    effective_min_profit = self._get_effective_min_net_profit()
                    if total_profit >= effective_min_profit:
                        combinations.append(HedgeCombination(
                            positions=[buy_pos, sell_pos],
                            total_profit=total_profit,
                            combination_type="DYNAMIC_PAIR",
                            size=2,
                            confidence_score=85.0,
                            reason=f"Dynamic pair: Buy ${getattr(buy_pos, 'profit', 0):.2f} + Sell ${getattr(sell_pos, 'profit', 0):.2f}"
                        ))
                        
                        # หยุดเมื่อพบ combination ที่ดีแล้ว
                        if len(combinations) >= 3:
                            break
                
                if len(combinations) >= 3:
                    break
            
            # เรียงตามกำไร (มากสุดก่อน)
            combinations.sort(key=lambda x: x.total_profit, reverse=True)
            
            logger.info(f"🔄 Dynamic Re-pairing: Found {len(combinations)} possible pairs")
            return combinations
            
        except Exception as e:
            logger.error(f"❌ Error in try dynamic re-pairing: {e}")
            return []
    
    def _dynamic_re_pairing(self, hedge_pair: dict, positions: List[Any]) -> Optional[HedgeCombination]:
        """🔄 Dynamic Re-pairing - การจับคู่ใหม่แบบ Dynamic"""
        try:
            # หาไม้ที่ยังไม่ได้ใช้
            used_tickets = set()
            for pair in self._find_existing_hedge_pairs(positions):
                used_tickets.add(getattr(pair['buy'], 'ticket', 'N/A'))
                used_tickets.add(getattr(pair['sell'], 'ticket', 'N/A'))
            
            available_positions = [pos for pos in positions 
                                 if getattr(pos, 'ticket', 'N/A') not in used_tickets]
            
            if len(available_positions) < 2:
                return None
            
            # ทดสอบการจับคู่ใหม่
            best_alternative = None
            best_profit = -float('inf')
            
            for i, pos1 in enumerate(available_positions):
                for j, pos2 in enumerate(available_positions[i+1:], i+1):
                    if getattr(pos1, 'type', 0) != getattr(pos2, 'type', 0):  # ไม้ตรงข้าม
                        test_profit = getattr(pos1, 'profit', 0) + getattr(pos2, 'profit', 0)
                        
                        if test_profit > best_profit and test_profit >= self.min_net_profit:
                            best_alternative = [pos1, pos2]
                            best_profit = test_profit
            
            if best_alternative:
                return HedgeCombination(
                    positions=best_alternative,
                    total_profit=best_profit,
                    combination_type="DYNAMIC_RE_PAIRING",
                    size=2,
                    confidence_score=80.0,
                    reason="Dynamic re-pairing: Alternative pair found"
                )
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error in dynamic re-pairing: {e}")
            return None
    
    def _find_profitable_combinations(self, positions: List[Any]) -> List[HedgeCombination]:
        """🔍 หาการจับคู่ไม้ที่ผลรวมเป็นบวก (ใช้หลักการ Hedge เท่านั้น)"""
        try:
            # Step 2: Priority-based Selection - เลือกไม้ตามความสำคัญ
            priority_positions = self._priority_based_selection(positions)
            logger.info(f"🔍 Priority Selection: {len(positions)} → {len(priority_positions)} positions")
            
            # หาการจับคู่แบบ Hedge เท่านั้น
            hedge_combinations = self._find_hedge_combinations(priority_positions)
            if hedge_combinations:
                logger.info("-" * 40)
                logger.info("✅ HEDGE COMBINATIONS FOUND")
                logger.info("-" * 40)
                logger.info(f"🎯 Total combinations: {len(hedge_combinations)}")
                for i, combo in enumerate(hedge_combinations[:3]):  # แสดงแค่ 3 อันแรก
                    logger.info(f"   {i+1}. {combo.combination_type}: ${combo.total_profit:.2f} ({combo.size} positions)")
                if len(hedge_combinations) > 3:
                    logger.info(f"   ... and {len(hedge_combinations) - 3} more combinations")
                logger.info("=" * 60)
                return hedge_combinations
            
            # Step 2: ถ้าไม่มี Hedge Combinations ให้ลอง Dynamic Re-pairing
            logger.info("🔄 No hedge combinations found, trying dynamic re-pairing...")
            dynamic_combinations = self._try_dynamic_re_pairing(priority_positions)
            
            if dynamic_combinations:
                logger.info("-" * 40)
                logger.info("✅ DYNAMIC RE-PAIRING FOUND")
                logger.info("-" * 40)
                logger.info(f"🎯 Total combinations: {len(dynamic_combinations)}")
                for i, combo in enumerate(dynamic_combinations[:3]):  # แสดงแค่ 3 อันแรก
                    logger.info(f"   {i+1}. {combo.combination_type}: ${combo.total_profit:.2f} ({combo.size} positions)")
                if len(dynamic_combinations) > 3:
                    logger.info(f"   ... and {len(dynamic_combinations) - 3} more combinations")
                logger.info("=" * 60)
                return dynamic_combinations
            
            # Step 3: ถ้าไม่มี Dynamic Re-pairing ให้ลองจับคู่ใหม่จากไม้ทั้งหมด
            logger.info("🔄 No dynamic combinations found, trying alternative pairing...")
            alternative_combinations = self._try_alternative_pairing(priority_positions)
            
            if alternative_combinations:
                logger.info("-" * 40)
                logger.info("✅ ALTERNATIVE PAIRING FOUND")
                logger.info("-" * 40)
                logger.info(f"🎯 Total combinations: {len(alternative_combinations)}")
                for i, combo in enumerate(alternative_combinations[:3]):  # แสดงแค่ 3 อันแรก
                    logger.info(f"   {i+1}. {combo.combination_type}: ${combo.total_profit:.2f} ({combo.size} positions)")
                if len(alternative_combinations) > 3:
                    logger.info(f"   ... and {len(alternative_combinations) - 3} more combinations")
                logger.info("=" * 60)
                return alternative_combinations
            
            # Step 4: ถ้าไม่มี Alternative Pairing ให้ลองหาตัวช่วยสำหรับไม้ที่ HEDGED แล้ว
            logger.info("🔄 No alternative combinations found, looking for helping positions...")
            helping_combinations = self._find_helping_positions_for_hedged(priority_positions)
            
            if helping_combinations:
                logger.info("-" * 40)
                logger.info("✅ HELPING POSITIONS FOUND")
                logger.info("-" * 40)
                logger.info(f"🎯 Total combinations: {len(helping_combinations)}")
                for i, combo in enumerate(helping_combinations[:3]):  # แสดงแค่ 3 อันแรก
                    logger.info(f"   {i+1}. {combo.combination_type}: ${combo.total_profit:.2f} ({combo.size} positions)")
                if len(helping_combinations) > 3:
                    logger.info(f"   ... and {len(helping_combinations) - 3} more combinations")
                logger.info("=" * 60)
                return helping_combinations
            
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
            
            logger.info("-" * 40)
            logger.info("📊 POSITION STATUS SUMMARY")
            logger.info("-" * 40)
            logger.info(f"💰 Unpaired profitable: {len(unpaired_profitable)}")
            logger.info(f"📉 Unpaired losing: {len(unpaired_losing)}")
            logger.info(f"🔗 Existing hedge pairs: {len(existing_hedge_pairs)}")
            
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
            
            logger.info("=" * 60)
            logger.info("🔍 HEDGE ANALYSIS START")
            logger.info("=" * 60)
            logger.info(f"📊 Positions: {len(buy_positions)} Buy, {len(sell_positions)} Sell (Total: {len(positions)})")
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
            logger.info("-" * 40)
            logger.info("📊 HEDGE PAIRING SUMMARY")
            logger.info("-" * 40)
            logger.info(f"✅ Hedge pairs found: {len(hedge_pairs)}")
            logger.info(f"📋 Used positions: {list(used_positions)}")
            logger.info(f"📋 Unused positions: {len(positions) - len(used_positions)}")
            
            # แสดงไม้ที่มี Hedge
            hedged_positions = []
            for pos in positions:
                if self._has_hedge_pair(positions, pos):
                    hedged_positions.append(getattr(pos, 'ticket', 'N/A'))
            
            if hedged_positions:
                logger.info(f"🔗 Hedged positions: {hedged_positions}")
                logger.info(f"⚠️  These positions will NOT be closed individually - waiting for additional positions")
            
            # Step 2: หาไม้อื่นๆ มาจับคู่เพิ่มเติม
            for hedge_pair in hedge_pairs:
                hedge_profit = getattr(hedge_pair['buy'], 'profit', 0) + getattr(hedge_pair['sell'], 'profit', 0)
                
                # ถ้า hedge pair ติดลบ ให้หาไม้อื่นๆ มาช่วย
                if hedge_profit < 0:
                    logger.info(f"🔍 Hedge pair is losing (${hedge_profit:.2f}), looking for additional profitable positions...")
                    
                    # หาไม้อื่นๆ ที่กำไรและไม่ได้ใช้แล้ว
                    additional_positions = []
                    for pos in positions:
                        pos_ticket = getattr(pos, 'ticket', 'N/A')
                        if pos_ticket not in used_positions and getattr(pos, 'profit', 0) > 0:
                            additional_positions.append(pos)
                    
                    logger.debug(f"🔍 Found {len(additional_positions)} additional profitable positions")
                    
                    # ลองเพิ่มไม้ทีละตัวจนกว่าจะได้กำไร
                    best_combination = None
                    best_profit = hedge_profit
                    
                    # Early termination - ลดจำนวนการทดสอบ
                    max_attempts = min(len(additional_positions), 3)  # ลดจาก 5 เป็น 3
                    
                    for i in range(1, min(len(additional_positions) + 1, max_attempts + 1)):
                        for combo in itertools.combinations(additional_positions, i):
                            test_positions = [hedge_pair['buy'], hedge_pair['sell']] + list(combo)
                            test_profit = sum(getattr(pos, 'profit', 0) for pos in test_positions)
                            
                        effective_min_profit = self._get_effective_min_net_profit()
                        if test_profit > best_profit and test_profit >= effective_min_profit:
                            best_combination = test_positions
                            best_profit = test_profit
                            # ลด log output - แสดงเฉพาะเมื่อพบ combination ที่ดีขึ้นมาก
                            if test_profit > best_profit * 1.5:  # ดีขึ้นมากกว่า 50%
                                logger.info(f"✅ Found better combination: ${test_profit:.2f} with {len(test_positions)} positions")
                            
                            # Early break - หยุดเมื่อพบ combination ที่ดีพอ
                            if test_profit >= effective_min_profit * 2:  # กำไรมากกว่า 2 เท่าของ threshold
                                break
                    
                    if best_combination:
                        hedge_combinations.append(HedgeCombination(
                            positions=best_combination,
                            total_profit=best_profit,
                            combination_type=f"HEDGE_{hedge_pair['type']}_WITH_ADDITIONAL",
                            size=len(best_combination),
                            confidence_score=95.0,
                            reason=f"Hedge: {hedge_pair['type']} with additional profitable positions"
                        ))
                        logger.info(f"✅ Complete hedge combination found: ${best_profit:.2f}")
                    else:
                        logger.info(f"⚠️ No profitable combination found for hedge pair (${hedge_profit:.2f})")
                        # Step 3: Dynamic Re-pairing - ลองจับคู่ใหม่
                        alternative_pair = self._dynamic_re_pairing(hedge_pair, positions)
                        if alternative_pair:
                            hedge_combinations.append(alternative_pair)
                            logger.info(f"🔄 Dynamic Re-pairing: Found alternative pair")
                        # ไม่เพิ่ม hedge pair ที่ติดลบ
                else:
                    # ถ้า hedge pair กำไรแล้ว ให้จับคู่เดี่ยว
                    logger.info(f"✅ Hedge pair is profitable: ${hedge_profit:.2f}")
                    hedge_combinations.append(HedgeCombination(
                        positions=[hedge_pair['buy'], hedge_pair['sell']],
                        total_profit=hedge_profit,
                        combination_type=f"HEDGE_{hedge_pair['type']}_ONLY",
                        size=2,
                        confidence_score=90.0,
                        reason=f"Hedge: {hedge_pair['type']} (profitable pair)"
                    ))
            
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
            
            logger.info("-" * 40)
            logger.info("🔍 HELPING COMBINATIONS ANALYSIS")
            logger.info("-" * 40)
            logger.info(f"💰 Unpaired profitable positions: {len(unpaired_profitable)}")
            logger.info(f"📉 Losing hedge pairs to help: {len(losing_hedge_pairs)}")
            
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
        """ตรวจสอบว่าไม้นี้มี Hedge กับคู่อื่นหรือไม่ (ตรวจสอบจาก used_positions)"""
        try:
            # หา used_positions จาก hedge pairs ที่สร้างแล้ว
            used_positions = set()
            
            # หา hedge pairs ที่สร้างแล้ว
            buy_positions = [p for p in positions if getattr(p, 'type', 0) == 0]
            sell_positions = [p for p in positions if getattr(p, 'type', 0) == 1]
            
            # หา Buy ติดลบ + Sell กำไร
            for buy_pos in buy_positions:
                if getattr(buy_pos, 'profit', 0) < 0:
                    buy_ticket = getattr(buy_pos, 'ticket', 'N/A')
                    if buy_ticket in used_positions:
                        continue
                    
                    for sell_pos in sell_positions:
                        if getattr(sell_pos, 'profit', 0) > 0:
                            sell_ticket = getattr(sell_pos, 'ticket', 'N/A')
                            if sell_ticket in used_positions:
                                continue
                            
                            used_positions.add(buy_ticket)
                            used_positions.add(sell_ticket)
                            break
            
            # หา Sell ติดลบ + Buy กำไร
            for sell_pos in sell_positions:
                if getattr(sell_pos, 'profit', 0) < 0:
                    sell_ticket = getattr(sell_pos, 'ticket', 'N/A')
                    if sell_ticket in used_positions:
                        continue
                    
                    for buy_pos in buy_positions:
                        if getattr(buy_pos, 'profit', 0) > 0:
                            buy_ticket = getattr(buy_pos, 'ticket', 'N/A')
                            if buy_ticket in used_positions:
                                continue
                            
                            used_positions.add(sell_ticket)
                            used_positions.add(buy_ticket)
                            break
            
            # ตรวจสอบว่าไม้นี้อยู่ใน used_positions หรือไม่
            pos_ticket = getattr(position, 'ticket', 'N/A')
            return pos_ticket in used_positions
            
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
