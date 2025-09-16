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
    
    def __init__(self, symbol: str = "XAUUSD"):
        # 🎯 Hedge Strategy Parameters
        self.symbol = symbol                # Symbol สำหรับเทรด
        self.min_combination_size = 2      # ขนาดการจับคู่ขั้นต่ำ
        self.max_combination_size = 12      # ขนาดการจับคู่สูงสุด (เพิ่มจาก 8)
        self.min_net_profit = 0.05         # กำไรสุทธิขั้นต่ำ $0.05 (ลดจาก 0.1)
        self.max_acceptable_loss = 10.0    # ขาดทุนที่ยอมรับได้ $10.0 (เพิ่มจาก 5.0)
        
        # 🚀 Dynamic Performance Optimization - ปรับตามจำนวนไม้และสถานะพอร์ต
        self.use_parallel_processing = True   # เปิดการประมวลผลแบบขนาน
        self.max_workers = 2  # ใช้ 2 threads (ไม่มากเกินไป)
        
        # 🧠 Smart Caching
        self.combination_cache = {}  # เก็บผลลัพธ์การจับคู่ไว้
        self.cache_hit_count = 0
        self.cache_miss_count = 0
        
        # 📊 Performance Tracking
        self.performance_history = []  # ประวัติประสิทธิภาพ
        
        # ⚡ Dynamic Early Termination - ปรับตามจำนวนไม้
        self.base_early_termination = 3  # ฐาน 3 combinations
        self.base_best_profit_threshold = 1.5  # ฐาน 1.5 เท่า
        
        # 🎯 Dynamic Smart Filtering - ปรับตามจำนวนไม้
        self.small_portfolio_threshold = 20    # ไม้น้อย: 1-20 ตัว
        self.medium_portfolio_threshold = 60   # ไม้ปานกลาง: 21-60 ตัว
        self.large_portfolio_threshold = 100   # ไม้เยอะ: 61+ ตัว
        self.priority_filtering = True        # ใช้การกรองตามความสำคัญ
        
        # 🛡️ SW Filter (Stop Loss) - ป้องกันไม้กองกระจุก
        self.sw_filter_enabled = True
        self.clustering_threshold = 0.1  # 0.1 จุด (เข้มมาก - เฉพาะไม้ที่ใกล้กันมาก)
        self.max_clustered_positions = 3  # สูงสุด 3 ไม้ใกล้กัน
        self.density_radius = 1.0  # 1 จุด (ลดลงมาก)
        self.max_density = 5  # สูงสุด 5 ไม้ในรัศมี
        self.min_std_deviation = 0.5  # ส่วนเบี่ยงเบนมาตรฐานขั้นต่ำ 0.5 จุด (ลดลงมาก)
        
        # ลบ Bar Close System ออกทั้งหมด - ทำงานทันที
        # self.wait_for_bar_close = True
        # self.last_bar_time = {}  # {timeframe: bar_time} - เวลาของแท่งล่าสุดแต่ละ TF
        # self.bar_close_wait_enabled = True
        # self.timeframes = ['M5', 'M15', 'M30', 'H1']  # TF ที่ใช้
        
        # 💰 Close All When Portfolio Profitable - ปิดไม้ทั้งหมดเมื่อพอร์ตเป็นบวก (ต้องจับคู่ Hedge ก่อน)
        self.close_all_when_profitable = False  # ปิดการปิดไม้ทั้งหมด - ใช้ Hedge Pairing แทน
        self.profitable_threshold_percentage = 2.0  # เพิ่มเป็น 2% ของเงินทุน (ยากขึ้น)
        self.min_profit_for_close_all = 20.0  # เพิ่มเป็น $20 (ยากขึ้น)
        self.urgent_profit_threshold = 100.0  # เพิ่มเป็น $100 (ยากขึ้น)
        
        # 🎯 Force Hedge Pairing - บังคับให้จับคู่ Hedge เสมอ
        self.force_hedge_pairing = True  # บังคับให้จับคู่ Hedge ก่อนปิด
        self.allow_single_side_closing = False  # ห้ามปิดไม้ฝั่งเดียว
        
        # 🚨 Emergency Mode Parameters (สำหรับพอร์ตที่แย่มาก)
        self.emergency_min_net_profit = 0.01  # กำไรขั้นต่ำในโหมดฉุกเฉิน $0.01
        self.emergency_threshold_percentage = 0.10  # 10% ในโหมดฉุกเฉิน
        
        
        
        
        
        
        # 🔧 Position Generation Parameters
        self.enable_position_generation = True  # เปิดใช้งานการออกไม้เพิ่มเติม
        self.max_additional_positions = 3
        
        # 🧠 Advanced Pairing Strategies - กลยุทธ์การจับคู่ขั้นสูง
        self.advanced_pairing_enabled = True
        self.multi_level_pairing = True  # จับคู่หลายระดับ (2-3-4-5 ไม้)
        self.cascade_pairing = True  # จับคู่แบบต่อเนื่อง (A+B, A+B+C, A+B+C+D)
        self.reverse_pairing = True  # จับคู่ย้อนกลับ (หาไม้ช่วยจากไม้ที่เสียมาก)
        self.smart_priority_pairing = True  # จับคู่ตามความสำคัญ (ไม้เสียมากก่อน)
        
        # 🎯 Enhanced Helping System - ระบบช่วยเหลือขั้นสูง
        self.enhanced_helping_enabled = True
        self.multi_helper_system = True  # ไม้ช่วยหลายตัว (Helper1+Helper2+Main)
        self.cascade_helping = True  # ช่วยแบบต่อเนื่อง (Helper→Main→Helper2)
        self.smart_helper_selection = True  # เลือกไม้ช่วยอย่างฉลาด
        self.emergency_helper_mode = True  # โหมดช่วยเหลือฉุกเฉิน (ไม้เสียมาก)
        
        # 🧹 Stale Position Clearing - ระบบเคลียร์ไม้ค้างพอร์ต
        self.stale_clearing_enabled = True
        self.stale_age_threshold_hours = 24  # อายุไม้ค้าง ≥ 24 ชั่วโมง
        self.stale_loss_threshold = -5.0  # ขาดทุนหนัก ≤ -$5
        self.stale_priority_bonus = 0.3  # โบนัสความสำคัญ +30%
        self.stale_anchor_inclusion_enabled = True  # ใช้ Anchor ได้เมื่อไม้ค้างเยอะ
        self.stale_anchor_threshold_avg = True  # ใช้ค่าเฉลี่ยไม้ค้าง
        
        # 📊 Advanced Filtering - การกรองขั้นสูง
        self.advanced_filtering_enabled = True
        self.distance_based_pairing = True  # จับคู่ตามระยะห่างราคา
        self.time_based_pairing = True  # จับคู่ตามอายุไม้
        self.volume_based_pairing = True  # จับคู่ตามขนาดไม้
        self.profit_ratio_pairing = True  # จับคู่ตามอัตราส่วนกำไร/ขาดทุน
        
        # 🎯 Dynamic Adjustment Methods
        self._adjust_performance_settings = self._get_dynamic_performance_settings
        self.additional_position_volume = 0.01  # ขนาดไม้เพิ่มเติม
        
        # 🚀 Real-time P&L System
        self.pnl_cache = {}  # เก็บข้อมูล P&L ไว้
        self.cache_timeout = 1.0  # หมดอายุใน 1 วินาที
        self.portfolio_health_score = "ปานกลาง"  # สุขภาพพอร์ต
    
    def _get_dynamic_performance_settings(self, position_count: int, portfolio_health: str = "ปานกลาง") -> dict:
        """🎯 Dynamic Performance Settings - ปรับตามจำนวนไม้และสถานะพอร์ต"""
        try:
            # กำหนดประเภทพอร์ต
            if position_count <= self.small_portfolio_threshold:
                portfolio_type = "small"
            elif position_count <= self.medium_portfolio_threshold:
                portfolio_type = "medium"
            else:
                portfolio_type = "large"
            
            # กำหนดการตั้งค่าตามประเภทพอร์ต
            if portfolio_type == "small":
                # ไม้น้อย: วิเคราะห์ทั้งหมด, หา pair ทุกความเป็นไปได้
                settings = {
                    'max_positions_to_analyze': position_count,  # วิเคราะห์ทั้งหมด
                    'early_termination_threshold': 5,  # หา pair มากขึ้น
                    'best_profit_threshold': 2.0,  # หา pair ที่ดีกว่า
                    'max_searches': 200,  # ค้นหามากขึ้น
                    'max_attempts': 5,  # ลองมากขึ้น
                    'use_parallel_processing': False,  # ไม่ต้องใช้ parallel
                    'max_workers': 1
                }
            elif portfolio_type == "medium":
                # ไม้ปานกลาง: สมดุลระหว่างความเร็วและประสิทธิภาพ
                settings = {
                    'max_positions_to_analyze': min(40, position_count),  # วิเคราะห์ 40 ตัว
                    'early_termination_threshold': 4,  # หา pair ปานกลาง
                    'best_profit_threshold': 1.8,  # หา pair ที่ดี
                    'max_searches': 150,  # ค้นหาปานกลาง
                    'max_attempts': 4,  # ลองปานกลาง
                    'use_parallel_processing': True,  # ใช้ parallel
                    'max_workers': 2
                }
            else:
                # ไม้เยอะ: เน้นความเร็ว, กรองไม้สำคัญ
                settings = {
                    'max_positions_to_analyze': min(50, position_count),  # วิเคราะห์ 50 ตัว
                    'early_termination_threshold': 3,  # หา pair เร็ว
                    'best_profit_threshold': 1.5,  # หา pair เร็ว
                    'max_searches': 100,  # ค้นหาน้อย
                    'max_attempts': 3,  # ลองน้อย
                    'use_parallel_processing': True,  # ใช้ parallel
                    'max_workers': 2
                }
            
            # ปรับตามสุขภาพพอร์ต
            if portfolio_health in ["แย่", "แย่มาก"]:
                # พอร์ตแย่: หา pair มากขึ้น, ใช้เวลานานขึ้น
                settings['early_termination_threshold'] = min(8, settings['early_termination_threshold'] + 2)
                settings['max_searches'] = min(300, settings['max_searches'] + 50)
                settings['max_attempts'] = min(8, settings['max_attempts'] + 2)
            elif portfolio_health == "ดี":
                # พอร์ตดี: หา pair เร็ว, ใช้เวลาน้อย
                settings['early_termination_threshold'] = max(2, settings['early_termination_threshold'] - 1)
                settings['max_searches'] = max(50, settings['max_searches'] - 25)
                settings['max_attempts'] = max(2, settings['max_attempts'] - 1)
            
            return settings
            
        except Exception as e:
            logger.error(f"❌ Error getting dynamic performance settings: {e}")
            # Fallback to default settings
            return {
                'max_positions_to_analyze': 30,
                'early_termination_threshold': 3,
                'best_profit_threshold': 1.5,
                'max_searches': 100,
                'max_attempts': 3,
                'use_parallel_processing': True,
                'max_workers': 2
            }
        # 📊 Performance Tracking (ย้ายไปข้างบนแล้ว)
        self.mt5_connection = None  # จะถูกตั้งค่าในภายหลัง
        
        # ⏰ Advanced Search Timing (1 hour delay)
        self.last_advanced_search_time = 0  # เวลาล่าสุดที่ทำ Advanced Search
        
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
    
    def _apply_sw_filter(self, positions: List[Any]) -> List[Any]:
        """🛡️ ใช้ SW Filter เพื่อกรองไม้ที่กองกระจุก"""
        try:
            if not self.sw_filter_enabled:
                return positions
            
            filtered_positions = []
            rejected_count = 0
            
            for pos in positions:
                # ตรวจสอบ SW Filter
                sw_ok, sw_msg = self._sw_filter_check(pos, filtered_positions)
                
                if sw_ok:
                    filtered_positions.append(pos)
                else:
                    rejected_count += 1
                    logger.debug(f"🚫 SW Filter rejected: {sw_msg}")
            
            if rejected_count > 0:
                logger.info(f"🛡️ SW Filter: Rejected {rejected_count} positions due to clustering")
                logger.info(f"📊 SW Filter: {len(positions)} → {len(filtered_positions)} positions")
            
            return filtered_positions
            
        except Exception as e:
            logger.error(f"❌ Error applying SW filter: {e}")
            return positions
    
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
        """ดึง P&L จาก position.profit โดยตรง (ไม่คำนวณ real-time)"""
        try:
            # ใช้ข้อมูลจาก position.profit โดยตรง (ไม่คำนวณ real-time)
            return getattr(position, 'profit', 0)
            
        except Exception as e:
            logger.error(f"Error getting P&L: {e}")
            return getattr(position, 'profit', 0)
    
    def _get_current_price(self) -> float:
        """📊 ดึงราคาปัจจุบันจาก MT5"""
        try:
            if not self.mt5_connection:
                return 0.0
            
            # ใช้ get_current_tick แทน get_current_price
            tick_data = self.mt5_connection.get_current_tick(self.symbol)
            if tick_data is None:
                return 0.0
            
            # ใช้ราคาเฉลี่ยระหว่าง bid และ ask
            current_price = (tick_data['bid'] + tick_data['ask']) / 2
            return current_price
            
        except Exception as e:
            logger.error(f"❌ Error getting current price: {e}")
            return 0.0
    
    def _check_position_clustering(self, new_position, existing_positions):
        """ตรวจสอบว่าไม้ใหม่จะทำให้เกิดการกองกระจุกใกล้ๆ หรือไม่ (ใช้ราคาปัจจุบัน)"""
        try:
            if not self.sw_filter_enabled:
                return True, "SW filter disabled"
            
            # ใช้ราคาปัจจุบันของไม้ใหม่
            new_price = getattr(new_position, 'price', 0)
            if new_price == 0:
                new_price = getattr(new_position, 'price_open', 0)
            
            # นับไม้ที่อยู่ใกล้กัน (ใช้ราคาเปิด)
            nearby_positions = 0
            logger.debug(f"🔍 SW Filter Debug - New Price: {new_price}")
            for i, pos in enumerate(existing_positions):
                existing_price = getattr(pos, 'price_open', 0)
                if existing_price == 0:
                    existing_price = getattr(pos, 'price', 0)
                if existing_price == 0:
                    existing_price = getattr(pos, 'price_current', 0)
                
                distance = abs(new_price - existing_price)
                logger.debug(f"   Position {i+1}: price_open={getattr(pos, 'price_open', 'N/A')}, price_current={getattr(pos, 'price_current', 'N/A')}, used={existing_price} (distance: {distance:.2f} points)")
                
                if distance <= self.clustering_threshold:
                    nearby_positions += 1
            
            # ถ้ามีไม้ใกล้กันมากเกินไป ให้หยุดออกไม้
            if nearby_positions >= self.max_clustered_positions:
                logger.warning(f"🚫 SW FILTER: Too many positions clustered near {new_price} ({nearby_positions} positions within {self.clustering_threshold} points)")
                return False, f"Too many positions clustered near {new_price} ({nearby_positions} positions within {self.clustering_threshold} points)"
            
            logger.info(f"✅ SW FILTER: Clustering check passed - {nearby_positions} positions within {self.clustering_threshold} points (max: {self.max_clustered_positions})")
            return True, "OK"
            
        except Exception as e:
            logger.error(f"❌ Error checking position clustering: {e}")
            return False, "Error"
    
    def _check_position_density(self, new_position, existing_positions):
        """ตรวจสอบความหนาแน่นของไม้ในพื้นที่ใกล้เคียง (ใช้ราคาปัจจุบัน)"""
        try:
            if not self.sw_filter_enabled:
                return True, "SW filter disabled"
            
            # ใช้ราคาปัจจุบันของไม้ใหม่
            new_price = getattr(new_position, 'price', 0)
            if new_price == 0:
                new_price = getattr(new_position, 'price_open', 0)
            
            # นับไม้ในรัศมี (ใช้ราคาเปิด)
            positions_in_radius = 0
            for pos in existing_positions:
                existing_price = getattr(pos, 'price_open', 0)
                if existing_price == 0:
                    existing_price = getattr(pos, 'price', 0)
                if existing_price == 0:
                    existing_price = getattr(pos, 'price_current', 0)
                
                distance = abs(new_price - existing_price)
                
                if distance <= self.density_radius:
                    positions_in_radius += 1
            
            # ถ้าไม้หนาแน่นเกินไป ให้หยุดออกไม้
            if positions_in_radius >= self.max_density:
                logger.warning(f"🚫 SW FILTER: Position density too high near {new_price} ({positions_in_radius} positions in {self.density_radius} points)")
                return False, f"Position density too high near {new_price} ({positions_in_radius} positions in {self.density_radius} points)"
            
            logger.info(f"✅ SW FILTER: Density check passed - {positions_in_radius} positions in {self.density_radius} points (max: {self.max_density})")
            return True, "OK"
            
        except Exception as e:
            logger.error(f"❌ Error checking position density: {e}")
            return False, "Error"
    
    def _check_position_distribution(self, new_position, existing_positions):
        """ตรวจสอบการกระจายของไม้ในพอร์ต (ใช้ราคาปัจจุบัน)"""
        try:
            if not self.sw_filter_enabled:
                return True, "SW filter disabled"
            
            if len(existing_positions) < 5:
                return True, "Not enough positions to check distribution"
            
            # คำนวณการกระจายของไม้ (ใช้ราคาเปิด)
            prices = []
            for pos in existing_positions:
                price = getattr(pos, 'price_open', 0)
                if price == 0:
                    price = getattr(pos, 'price', 0)
                if price == 0:
                    price = getattr(pos, 'price_current', 0)
                prices.append(price)
            
            new_price = getattr(new_position, 'price', 0)
            if new_price == 0:
                new_price = getattr(new_position, 'price_open', 0)
            prices.append(new_price)
            
            # คำนวณค่าเฉลี่ยและส่วนเบี่ยงเบนมาตรฐาน
            mean_price = sum(prices) / len(prices)
            variance = sum((p - mean_price) ** 2 for p in prices) / len(prices)
            std_deviation = variance ** 0.5
            
            # ถ้าการกระจายน้อยเกินไป (ไม้กองกัน) ให้หยุดออกไม้
            if std_deviation < self.min_std_deviation:
                logger.warning(f"🚫 SW FILTER: Positions too clustered (std_dev: {std_deviation:.2f} < {self.min_std_deviation})")
                return False, f"Positions too clustered (std_dev: {std_deviation:.2f} < {self.min_std_deviation})"
            
            logger.info(f"✅ SW FILTER: Distribution check passed - std: {std_deviation:.2f} (min: {self.min_std_deviation})")
            return True, "OK"
            
        except Exception as e:
            logger.error(f"❌ Error checking position distribution: {e}")
            return False, "Error"
    
    def _sw_filter_check(self, new_position, existing_positions):
        """ระบบกรอง SW แบบรวม"""
        try:
            if not self.sw_filter_enabled:
                return True, "SW filter disabled"
            
            logger.debug(f"🔍 SW FILTER: Checking new position against {len(existing_positions)} existing positions")
            logger.debug(f"🔍 SW FILTER: New position price: {getattr(new_position, 'price', 'N/A')} | price_open: {getattr(new_position, 'price_open', 'N/A')} | price_current: {getattr(new_position, 'price_current', 'N/A')}")
            
            # ตรวจสอบการกองกระจุก
            clustering_ok, clustering_msg = self._check_position_clustering(new_position, existing_positions)
            if not clustering_ok:
                logger.warning(f"🚫 SW FILTER: {clustering_msg}")
                return False, clustering_msg
            
            # ตรวจสอบความหนาแน่น
            density_ok, density_msg = self._check_position_density(new_position, existing_positions)
            if not density_ok:
                logger.warning(f"🚫 SW FILTER: {density_msg}")
                return False, density_msg
            
            # ตรวจสอบการกระจาย
            distribution_ok, distribution_msg = self._check_position_distribution(new_position, existing_positions)
            if not distribution_ok:
                logger.warning(f"🚫 SW FILTER: {distribution_msg}")
                return False, distribution_msg
            
            logger.info("✅ SW FILTER: Position passed all checks - ALLOWING TRADE")
            return True, "All checks passed"
            
        except Exception as e:
            logger.error(f"❌ Error in SW filter check: {e}")
            return False, "Error"
    
    def _check_bar_close(self, timeframe: str = 'M5') -> bool:
        """⏰ ตรวจสอบว่าแท่งปัจจุบันปิดแล้วหรือยัง - แยกตาม TF"""
        try:
            if not self.bar_close_wait_enabled:
                return True  # ไม่ต้องรอปิดแท่ง
            
            if not self.mt5_connection:
                return True  # ไม่มี MT5 connection
            
            # ใช้ default symbol หรือ symbol ที่ตั้งค่าไว้
            symbol = getattr(self, 'symbol', 'XAUUSD')
            
            # แปลง TF string เป็น MT5 constant
            tf_mapping = {
                'M5': 5,    # 5 minutes
                'M15': 15,  # 15 minutes
                'M30': 30,  # 30 minutes
                'H1': 60    # 1 hour
            }
            
            tf_minutes = tf_mapping.get(timeframe, 5)  # default M5
            
            # ดึงข้อมูลแท่งปัจจุบันตาม TF
            try:
                import MetaTrader5 as mt5
                rates = mt5.copy_rates_from_pos(symbol, tf_minutes, 0, 1)
                if rates is None or len(rates) == 0:
                    return True  # ไม่สามารถดึงข้อมูลได้
                
                current_bar_time = rates[0]['time']
                
                # ถ้ายังไม่มีข้อมูลแท่งเก่าสำหรับ TF นี้
                if timeframe not in self.last_bar_time:
                    self.last_bar_time[timeframe] = current_bar_time
                    logger.info(f"⏰ First run - waiting for {timeframe} bar close")
                    return False  # รอปิดแท่ง
                
                # ตรวจสอบว่าแท่งใหม่เริ่มแล้วหรือยัง
                if current_bar_time > self.last_bar_time[timeframe]:
                    self.last_bar_time[timeframe] = current_bar_time
                    logger.info(f"✅ {timeframe} Bar closed - ready to trade")
                    return True  # แท่งปิดแล้ว พร้อมเทรด
                
                # ยังไม่ปิดแท่ง (ไม่ log ถี่ๆ)
                return False
                
            except Exception as e:
                logger.error(f"❌ Error checking {timeframe} bar close: {e}")
                return True  # ถ้า error ให้อนุญาตเทรด
            
        except Exception as e:
            logger.error(f"❌ Error checking bar close: {e}")
            return True  # ถ้า error ให้อนุญาตเทรด
    
    def _should_wait_for_bar_close(self, timeframe: str = 'M5') -> bool:
        """⏰ ตรวจสอบว่าควรรอปิดแท่งหรือไม่ - แยกตาม TF"""
        try:
            if not self.wait_for_bar_close:
                return False  # ไม่ต้องรอปิดแท่ง
            
            return not self._check_bar_close(timeframe)
            
        except Exception as e:
            logger.error(f"❌ Error checking if should wait: {e}")
            return False  # ถ้า error ให้ไม่รอ
    
    def _check_close_all_profitable(self, positions: List[Any], account_balance: float) -> bool:
        """💰 ตรวจสอบว่าควรปิดไม้ทั้งหมดเมื่อพอร์ตเป็นบวกหรือไม่ (ต้องจับคู่ Hedge ก่อน)"""
        try:
            # 🚫 DISABLED: ปิดการปิดไม้ทั้งหมด - ใช้ Hedge Pairing แทน
            if not self.close_all_when_profitable:
                logger.info("🚫 Close All When Profitable DISABLED - Using Hedge Pairing instead")
                return False
            
            if len(positions) < 1:
                return False  # ไม่มีไม้ให้ปิด
            
            # ตรวจสอบว่ามีไม้ทั้งสองฝั่งหรือไม่
            buy_positions = [pos for pos in positions if getattr(pos, 'type', 0) == 0]
            sell_positions = [pos for pos in positions if getattr(pos, 'type', 0) == 1]
            
            # ถ้ามีไม้ทั้งสองฝั่ง ให้ใช้ Hedge Pairing แทน
            if len(buy_positions) > 0 and len(sell_positions) > 0:
                logger.info("🎯 Both BUY and SELL positions exist - Using Hedge Pairing instead of Close All")
                return False
            
            # คำนวณกำไรรวมของพอร์ต (เร็วขึ้น)
            total_profit = sum(getattr(pos, 'profit', 0) for pos in positions)
            
            # ตรวจสอบเงื่อนไขการปิดไม้ทั้งหมด (ยากขึ้นมาก)
            
            # เงื่อนไข 1: กำไรรวมมากกว่าเปอร์เซ็นต์ที่กำหนด (ยากขึ้น)
            if account_balance > 0:
                profit_percentage = (total_profit / account_balance) * 100
                if profit_percentage >= self.profitable_threshold_percentage:
                    logger.info(f"💰 Portfolio profitable: {profit_percentage:.2f}% >= {self.profitable_threshold_percentage}%")
                    return True
            
            # เงื่อนไข 2: กำไรรวมมากกว่าจำนวนเงินขั้นต่ำ (ยากขึ้น)
            if total_profit >= self.min_profit_for_close_all:
                logger.info(f"💰 Portfolio profitable: ${total_profit:.2f} >= ${self.min_profit_for_close_all}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Error checking close all profitable: {e}")
            return False
    
    def _create_close_all_decision(self, positions: List[Any], total_profit: float) -> ClosingDecision:
        """💰 สร้างการตัดสินใจปิดไม้ทั้งหมด"""
        try:
            # สร้างรายการไม้ที่จะปิด
            positions_to_close = []
            buy_count = 0
            sell_count = 0
            
            for pos in positions:
                pos_type = getattr(pos, 'type', 0)
                if pos_type == 0:  # BUY
                    buy_count += 1
                else:  # SELL
                    sell_count += 1
                
                positions_to_close.append({
                    'ticket': getattr(pos, 'ticket', 'N/A'),
                    'symbol': getattr(pos, 'symbol', 'XAUUSD'),
                    'type': 'BUY' if pos_type == 0 else 'SELL',
                    'volume': getattr(pos, 'volume', 0),
                    'profit': getattr(pos, 'profit', 0)
                })
            
            # สร้าง ClosingDecision
            decision = ClosingDecision(
                should_close=True,
                positions_to_close=positions_to_close,
                method="CLOSE_ALL_PROFITABLE",
                net_pnl=total_profit,
                expected_pnl=total_profit,
                position_count=len(positions),
                buy_count=buy_count,
                sell_count=sell_count,
                confidence_score=95.0,
                reason=f"Close all positions - Portfolio profitable: ${total_profit:.2f}"
            )
            
            return decision
            
        except Exception as e:
            logger.error(f"❌ Error creating close all decision: {e}")
            return None
    
    def _analyze_portfolio_health(self, positions: List[Any], account_balance: float = 1000.0) -> dict:
        """วิเคราะห์สุขภาพพอร์ต"""
        try:
            # คำนวณ P&L จาก position.profit โดยตรง (ไม่ใช้ real-time calculation)
            total_pnl = sum(getattr(pos, 'profit', 0) for pos in positions)
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
            # 🚫 Exclude Portfolio Anchor positions (magic 789012) from closing candidates
            original_count = len(positions) if positions else 0
            anchor_positions = [pos for pos in (positions or []) if getattr(pos, 'magic', None) == 789012]
            positions = [pos for pos in (positions or []) if getattr(pos, 'magic', None) != 789012]
            excluded = original_count - len(positions)
            if excluded > 0:
                logger.info(f"🛡️ Excluding {excluded} anchor positions from closing candidates")
            
            # 🧹 Analyze stale positions for potential inclusion of anchors
            stale_positions = self._identify_stale_positions(positions) if self.stale_clearing_enabled else []
            allow_anchor_inclusion = self._should_include_anchors_for_stale_clearing(stale_positions, positions)
            
            if allow_anchor_inclusion and anchor_positions:
                logger.info(f"🧹 STALE CLEARING: Including {len(anchor_positions)} anchors for stale position clearing")
                positions.extend(anchor_positions)  # Add anchors back to candidates

            if len(positions) < 1:
                logger.info("⏸️ Need at least 1 position for analysis")
                return None
            
            # ลบ Bar Close System ออกทั้งหมด - ทำงานทันที
            # if self._should_wait_for_bar_close():
            #     return None
            
            # แสดงจำนวนไม้ทั้งหมดก่อนกรอง (เฉพาะเมื่อมีไม้)
            self.original_position_count = len(positions)
            if len(positions) > 0:
                logger.info(f"📊 TOTAL POSITIONS (ex-anchors): {len(positions)} positions")
            
            # ตรวจสอบการปิดไม้ทั้งหมดเมื่อพอร์ตเป็นบวก (เร็วขึ้น)
            account_balance = account_info.get('balance', 1000.0)
            total_profit = sum(getattr(pos, 'profit', 0) for pos in positions)
            
            
            # ตรวจสอบกำไรเร่งด่วนก่อน (ปิดทันที) - เอาออกเพราะซ้ำซ้อนกับ Close All
            # if total_profit >= self.urgent_profit_threshold:
            #     logger.info("🚨 URGENT CLOSE ALL - VERY PROFITABLE")
            #     logger.info(f"🎯 Total Profit: ${total_profit:.2f} | Positions: {len(positions)}")
            #     return self._create_close_all_decision(positions, total_profit)
            
            # ตรวจสอบการปิดไม้ทั้งหมดเมื่อพอร์ตเป็นบวก (เร็วขึ้น)
            if self._check_close_all_profitable(positions, account_balance):
                logger.info("💰 CLOSE ALL POSITIONS - PORTFOLIO PROFITABLE")
                logger.info(f"🎯 Total Profit: ${total_profit:.2f} | Positions: {len(positions)}")
                return self._create_close_all_decision(positions, total_profit)
            
            # Step 1: วิเคราะห์สุขภาพพอร์ตก่อน
            account_balance = account_info.get('balance', 1000.0)
            portfolio_health = self._analyze_portfolio_health(positions, account_balance)
            
            # 🎯 Dynamic Performance Settings - ปรับตามจำนวนไม้และสถานะพอร์ต
            dynamic_settings = self._get_dynamic_performance_settings(len(positions), portfolio_health['health_score'])
            
            # ใช้ dynamic settings
            max_positions_to_analyze = dynamic_settings['max_positions_to_analyze']
            early_termination_threshold = dynamic_settings['early_termination_threshold']
            best_profit_threshold = dynamic_settings['best_profit_threshold']
            
            logger.info(f"🎯 Dynamic Settings: {len(positions)} positions → {max_positions_to_analyze} to analyze")
            logger.info(f"   Early Termination: {early_termination_threshold}, Best Profit: {best_profit_threshold}x")
            
            # 🎯 Smart Position Selection สำหรับพอร์ตใหญ่
            if self.priority_filtering and len(positions) > max_positions_to_analyze:
                original_count = len(positions)
                positions = self._smart_position_selection(positions)
                logger.info(f"🎯 Smart Selection: {original_count} → {len(positions)} positions")
            else:
                logger.info(f"🎯 Using All Positions: {len(positions)} positions")
            
            # แสดงการวิเคราะห์เฉพาะเมื่อมีไม้
            if len(positions) > 0:
                logger.info(f"🔍 HEDGE ANALYSIS: {len(positions)} positions")
            
            # Step 1: วิเคราะห์สุขภาพพอร์ต (ย้ายไปข้างบนแล้ว)
            
            # แสดงสถานะพอร์ตเฉพาะเมื่อเปลี่ยนสถานะ
            if not hasattr(self, '_last_portfolio_status'):
                self._last_portfolio_status = None
            
            current_status = portfolio_health['health_score']
            if current_status != self._last_portfolio_status:
                logger.info(f"📊 Portfolio Health: {current_status} (P&L: ${portfolio_health['total_pnl']:.2f})")
                self._last_portfolio_status = current_status
            
            # Step 2: Smart Filtering - คัดกรองไม้ตามค่าเฉลี่ยของเงินทุน
            filtered_positions = self._smart_filter_positions(positions, account_balance)
            if len(positions) > 0:
                logger.info(f"🔍 Smart Filtering: {len(positions)} → {len(filtered_positions)} positions")
            
            # Step 2.5: SW Filter - ปิดการใช้งานใน find_optimal_closing
            # SW Filter ควรใช้สำหรับออกไม้ใหม่ ไม่ใช่ปิดไม้
            # if self.sw_filter_enabled:
            #     filtered_positions = self._apply_sw_filter(filtered_positions)
            #     logger.info(f"🛡️ SW Filter: Applied clustering protection")
            
            
            # 0.4. Stale Position Clearing - ระบบเคลียร์ไม้ค้างพอร์ต
            if self.stale_clearing_enabled and stale_positions:
                stale_combinations = self._find_stale_clearing_combinations(filtered_positions, stale_positions)
                if stale_combinations:
                    logger.info(f"🧹 STALE CLEARING FOUND: {len(stale_combinations)} combinations")
                    best_stale = stale_combinations[0]
                    logger.info(f"   Best: {best_stale.combination_type}: ${best_stale.total_profit:.2f} ({best_stale.size} positions)")
                    logger.info(f"   Clearing {len([p for p in best_stale.positions if self._is_stale_position(p)])} stale positions")
                    
                    processing_time = time.time() - start_time
                    self._record_performance(True, best_stale.total_profit, processing_time)
                    
                    return ClosingDecision(
                        should_close=True,
                        positions_to_close=best_stale.positions,
                        method="STALE_CLEARING",
                        net_pnl=best_stale.total_profit,
                        expected_pnl=best_stale.total_profit,
                        position_count=best_stale.size,
                        buy_count=sum(1 for p in best_stale.positions if getattr(p, 'type', 0) == 0),
                        sell_count=sum(1 for p in best_stale.positions if getattr(p, 'type', 0) == 1),
                        confidence_score=best_stale.confidence_score,
                        reason=best_stale.reason
                    )
            
            # 0.5. Advanced Pairing - กลยุทธ์การจับคู่ขั้นสูง
            if self.advanced_pairing_enabled:
                advanced_combinations = self._find_advanced_pairing_combinations(filtered_positions)
                if advanced_combinations:
                    logger.info(f"🧠 ADVANCED PAIRING FOUND: {len(advanced_combinations)} combinations")
                    best_advanced = advanced_combinations[0]
                    logger.info(f"   Best: {best_advanced.combination_type}: ${best_advanced.total_profit:.2f} ({best_advanced.size} positions)")
                    
                    processing_time = time.time() - start_time
                    self._record_performance(True, best_advanced.total_profit, processing_time)
                    
                    return ClosingDecision(
                        should_close=True,
                        positions_to_close=best_advanced.positions,
                        method="ADVANCED_PAIRING",
                        net_pnl=best_advanced.total_profit,
                        expected_pnl=best_advanced.total_profit,
                        position_count=best_advanced.size,
                        buy_count=sum(1 for p in best_advanced.positions if getattr(p, 'type', 0) == 0),
                        sell_count=sum(1 for p in best_advanced.positions if getattr(p, 'type', 0) == 1),
                        confidence_score=best_advanced.confidence_score,
                        reason=best_advanced.reason
                    )
            
            # 0.6. Enhanced Helping - ระบบช่วยเหลือขั้นสูง
            if self.enhanced_helping_enabled:
                enhanced_helping = self._find_enhanced_helping_combinations(filtered_positions)
                if enhanced_helping:
                    logger.info(f"🎯 ENHANCED HELPING FOUND: {len(enhanced_helping)} combinations")
                    best_helping = enhanced_helping[0]
                    logger.info(f"   Best: {best_helping.combination_type}: ${best_helping.total_profit:.2f} ({best_helping.size} positions)")
                    
                    processing_time = time.time() - start_time
                    self._record_performance(True, best_helping.total_profit, processing_time)
                    
                    return ClosingDecision(
                        should_close=True,
                        positions_to_close=best_helping.positions,
                        method="ENHANCED_HELPING",
                        net_pnl=best_helping.total_profit,
                        expected_pnl=best_helping.total_profit,
                        position_count=best_helping.size,
                        buy_count=sum(1 for p in best_helping.positions if p.type == 0),
                        sell_count=sum(1 for p in best_helping.positions if p.type == 1),
                        confidence_score=best_helping.confidence_score,
                        reason=best_helping.reason
                    )
            
            # 1. หาการจับคู่ไม้ที่มีอยู่
            logger.info(f"🔍 Starting profitable combinations search with {len(filtered_positions)} positions")
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
            logger.info(f"📊 Analyzed positions: {len(positions)} total")
            logger.info(f"📊 Buy positions: {len([p for p in positions if getattr(p, 'type', 0) == 0])}")
            logger.info(f"📊 Sell positions: {len([p for p in positions if getattr(p, 'type', 0) == 1])}")
            
            # แสดงข้อมูลไม้ที่ถูกกรองออก (เฉพาะเมื่อมีไม้)
            if hasattr(self, 'original_position_count') and self.original_position_count > len(positions) and len(positions) > 0:
                filtered_count = self.original_position_count - len(positions)
                logger.info(f"📊 Filtered out: {filtered_count} positions (too many for analysis)")
                logger.info(f"📊 Total positions in system: {self.original_position_count}")
            
            # แสดงเฉพาะจำนวนสุทธิ (เฉพาะเมื่อมีไม้)
            if len(positions) > 0:
                logger.info(f"📊 Summary: {len(positions)} positions analyzed")
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
            
            # เลือกเฉพาะไม้ที่มี Priority สูง (ปรับตามจำนวนไม้)
            if len(positions) <= 20:
                max_positions = len(positions)  # วิเคราะห์ทั้งหมด
            elif len(positions) <= 50:
                max_positions = min(30, len(positions))  # วิเคราะห์ 30 ไม้
            else:
                max_positions = min(40, len(positions))  # วิเคราะห์ 40 ไม้
            priority_positions = [pos for _, pos in priority_scores[:max_positions]]
            
            logger.info(f"🎯 Priority Selection: {len(positions)} → {len(priority_positions)} positions")
            return priority_positions
            
        except Exception as e:
            logger.error(f"❌ Error in priority selection: {e}")
            return positions  # Return original positions if error
    
    def _calculate_priority_score(self, position: Any) -> float:
        """📊 คำนวณ Priority Score จาก Real-time P&L และระยะห่างจากราคาปัจจุบัน"""
        try:
            # ใช้ P&L แบบ Real-time
            real_pnl = self._get_real_time_pnl(position)
            volume = getattr(position, 'volume', 0)
            
            # คำนวณระยะห่างจากราคาปัจจุบัน
            current_price = self._get_current_price()
            open_price = getattr(position, 'price_open', 0)
            distance = abs(current_price - open_price)
            
            # คำนวณ Priority Score
            priority_score = 0
            
            # ไม้ที่เสียไกลๆ = Priority สูงสุด (ต้องปิดก่อน)
            if real_pnl < -5.0 and distance > 5.0:  # เสียมาก + ไกลมาก
                priority_score += abs(real_pnl) * 25  # คะแนนสูงสุด
                priority_score += distance * 10  # เพิ่มคะแนนตามระยะห่าง
            elif real_pnl < -2.0 and distance > 3.0:  # เสียปานกลาง + ไกลปานกลาง
                priority_score += abs(real_pnl) * 20  # คะแนนสูง
                priority_score += distance * 8  # เพิ่มคะแนนตามระยะห่าง
            elif real_pnl < 0:  # เสียน้อย
                priority_score += abs(real_pnl) * 15  # คะแนนปานกลาง
                priority_score += distance * 5  # เพิ่มคะแนนตามระยะห่าง
            else:  # กำไร
                priority_score += real_pnl * 10  # คะแนนต่ำ
                priority_score += distance * 2  # เพิ่มคะแนนตามระยะห่าง (น้อย)
            
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
            
            # Step 2: หาไม้ช่วยสำหรับคู่ที่ HEDGED แล้ว
            logger.info("🔍 STEP 2: HELPING POSITIONS")
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
            
            # Step 2.5: หาไม้ฝั่งเดียวที่ P&L รวมเป็นบวก (เฉพาะเมื่อไม่มีไม้ฝั่งตรงข้าม)
            logger.info("🔍 STEP 2.5: SINGLE SIDE PROFITABLE CLOSING")
            single_side_combinations = self._find_single_side_profitable(priority_positions)
            
            if single_side_combinations:
                logger.info("-" * 40)
                logger.info("✅ SINGLE SIDE PROFITABLE FOUND")
                logger.info("-" * 40)
                logger.info(f"🎯 Total combinations: {len(single_side_combinations)}")
                for i, combo in enumerate(single_side_combinations[:3]):  # แสดงแค่ 3 อันแรก
                    logger.info(f"   {i+1}. {combo.combination_type}: ${combo.total_profit:.2f} ({combo.size} positions)")
                if len(single_side_combinations) > 3:
                    logger.info(f"   ... and {len(single_side_combinations) - 3} more combinations")
                logger.info("=" * 60)
                return single_side_combinations
            
            # Step 3-4: Advanced Search (ทุก 5 นาที)
            current_time = time.time()
            if not hasattr(self, 'last_advanced_search_time'):
                self.last_advanced_search_time = 0
            should_run_advanced = (current_time - self.last_advanced_search_time) >= 300  # 5 นาที = 300 วินาที (ลดจาก 1 ชั่วโมง)
            
            if should_run_advanced:
                logger.info("⏰ Running advanced search (5+ minutes since last run)")
                
                # Step 3: Dynamic Re-pairing
                logger.info("🔍 STEP 3: DYNAMIC RE-PAIRING")
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
                    self.last_advanced_search_time = current_time  # อัปเดตเวลา
                    return dynamic_combinations
                
                # Step 4: Alternative Pairing
                logger.info("🔍 STEP 4: ALTERNATIVE PAIRING")
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
                    self.last_advanced_search_time = current_time  # อัปเดตเวลา
                    return alternative_combinations
                
                # อัปเดตเวลาแม้ไม่เจอ combination
                self.last_advanced_search_time = current_time
                logger.info("⏰ Advanced search completed, next run in 1 hour")
            else:
                time_remaining = 3600 - (current_time - self.last_advanced_search_time)
                minutes_remaining = int(time_remaining / 60)
                logger.info(f"⏰ Advanced search skipped ({minutes_remaining} min until next run)")
            
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
                        # ไม้กำไรที่ไม่มีคู่
                    else:
                        unpaired_losing.append(pos)
                        # ไม้ติดลบที่ไม่มีคู่
                else:
                    # ไม้ที่มีคู่แล้ว
                    pass
            
            # หา Hedge pairs ที่มีอยู่แล้ว
            existing_hedge_pairs = self._find_existing_hedge_pairs(positions)
            
            logger.info("=" * 50)
            logger.info("📊 POSITION STATUS SUMMARY")
            logger.info("=" * 50)
            logger.info(f"💰 Unpaired profitable: {len(unpaired_profitable)}")
            logger.info(f"📉 Unpaired losing: {len(unpaired_losing)}")
            logger.info(f"🔗 Existing hedge pairs: {len(existing_hedge_pairs)}")
            logger.info("=" * 50)
            
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
    
    def _find_hedge_combinations(self, positions: List[Any], dynamic_settings: dict = None) -> List[HedgeCombination]:
        """หาการจับคู่แบบ Hedge (ตรงข้ามก่อนเสมอ) - เร็วขึ้น"""
        try:
            hedge_combinations = []
            
            # แยกไม้ Buy และ Sell (เร็วขึ้น)
            buy_positions = [p for p in positions if getattr(p, 'type', 0) == 0]
            sell_positions = [p for p in positions if getattr(p, 'type', 0) == 1]
            
            logger.info("=" * 60)
            logger.info("🔍 HEDGE ANALYSIS START")
            logger.info("=" * 60)
            logger.info(f"📊 Positions: {len(buy_positions)} Buy, {len(sell_positions)} Sell (Total: {len(positions)})")
            
            # Step 1: จับคู่ตรงข้ามก่อนเสมอ (เร็วขึ้น - O(n log n))
            hedge_pairs = []
            used_positions = set()  # ติดตามไม้ที่ใช้แล้ว
            
            # เรียงไม้ตามกำไร (เร็วขึ้น)
            buy_loss = [p for p in buy_positions if getattr(p, 'profit', 0) < 0]
            buy_profit = [p for p in buy_positions if getattr(p, 'profit', 0) > 0]
            sell_loss = [p for p in sell_positions if getattr(p, 'profit', 0) < 0]
            sell_profit = [p for p in sell_positions if getattr(p, 'profit', 0) > 0]
            
            # หา Buy ติดลบ + Sell กำไร (เร็วขึ้น)
            for buy_pos in buy_loss:
                buy_ticket = getattr(buy_pos, 'ticket', 'N/A')
                if buy_ticket in used_positions:
                    continue
                
                for sell_pos in sell_profit:
                    sell_ticket = getattr(sell_pos, 'ticket', 'N/A')
                    if sell_ticket in used_positions:
                        continue
                    
                    # จับคู่ไม้ที่ยังไม่ได้ใช้
                    hedge_pairs.append({
                        'buy': buy_pos,
                        'sell': sell_pos,
                        'type': 'BUY_LOSS_SELL_PROFIT'
                    })
                    used_positions.add(buy_ticket)
                    used_positions.add(sell_ticket)
                    break  # หยุดเมื่อจับคู่แล้ว
            
            # หา Sell ติดลบ + Buy กำไร (เร็วขึ้น)
            for sell_pos in sell_loss:
                sell_ticket = getattr(sell_pos, 'ticket', 'N/A')
                if sell_ticket in used_positions:
                    continue
                
                for buy_pos in buy_profit:
                    buy_ticket = getattr(buy_pos, 'ticket', 'N/A')
                    if buy_ticket in used_positions:
                        continue
                    
                    # จับคู่ไม้ที่ยังไม่ได้ใช้
                    hedge_pairs.append({
                        'buy': buy_pos,
                        'sell': sell_pos,
                        'type': 'SELL_LOSS_BUY_PROFIT'
                    })
                    used_positions.add(sell_ticket)
                    used_positions.add(buy_ticket)
                    break  # หยุดเมื่อจับคู่แล้ว
            
            # แสดงสรุปการจับคู่ (เร็วขึ้น)
            logger.info("-" * 40)
            logger.info("📊 HEDGE PAIRING SUMMARY")
            logger.info("-" * 40)
            logger.info(f"✅ Hedge pairs found: {len(hedge_pairs)}")
            logger.info(f"📋 Used positions: {len(used_positions)}")
            logger.info(f"📋 Unused positions: {len(positions) - len(used_positions)}")
            
            # Step 2: หาไม้อื่นๆ มาจับคู่เพิ่มเติม (เร็วขึ้น)
            for hedge_pair in hedge_pairs:
                hedge_profit = getattr(hedge_pair['buy'], 'profit', 0) + getattr(hedge_pair['sell'], 'profit', 0)
                
                # ถ้า hedge pair ติดลบ ให้หาไม้อื่นๆ มาช่วย
                if hedge_profit < 0:
                    # หาไม้ช่วยสำหรับคู่ที่ติดลบ (เร็วขึ้น)
                    additional_positions = [pos for pos in positions 
                                          if getattr(pos, 'ticket', 'N/A') not in used_positions 
                                          and getattr(pos, 'profit', 0) > 0]
                    
                    # ลองเพิ่มไม้ทีละตัวจนกว่าจะได้กำไร (เร็วขึ้น)
                    best_combination = None
                    best_profit = hedge_profit
                    
                    # Early termination - ลดจำนวนการทดสอบ
                    max_attempts = min(len(additional_positions), 2)  # ลดจาก 3 เป็น 2
                    
                    for i in range(1, min(len(additional_positions) + 1, max_attempts + 1)):
                        for combo in itertools.combinations(additional_positions, i):
                            test_positions = [hedge_pair['buy'], hedge_pair['sell']] + list(combo)
                            test_profit = sum(getattr(pos, 'profit', 0) for pos in test_positions)
                            
                            effective_min_profit = self._get_effective_min_net_profit()
                            if test_profit > best_profit and test_profit >= effective_min_profit:
                                best_combination = test_positions
                                best_profit = test_profit
                                
                                # Early break - หยุดเมื่อพบ combination ที่ดีพอ
                                if test_profit >= effective_min_profit * 1.5:  # กำไรมากกว่า 1.5 เท่าของ threshold
                                    break
                        
                        # Early break - หยุดเมื่อพบ combination ที่ดีพอ
                        if best_combination and best_profit >= effective_min_profit * 1.5:
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
                        # ไม่พบการรวมที่กำไร - ข้าม Dynamic Re-pairing เพื่อความเร็ว
                        pass
                else:
                    # ถ้า hedge pair กำไรแล้ว ให้จับคู่เดี่ยว
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
        """หาไม้อื่นๆ ที่กำไรและไม่มี Hedge กับคู่อื่น (เร็วขึ้น)"""
        try:
            # หาไม้อื่นๆ ที่กำไร (เร็วขึ้น - ใช้ list comprehension)
            additional_positions = [pos for pos in positions 
                                  if pos != hedge_buy and pos != hedge_sell 
                                  and getattr(pos, 'profit', 0) > 0]
            
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
                            # พบ hedge pair
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
                            # พบ hedge pair
                            break
            
            return hedge_pairs
            
        except Exception as e:
            logger.error(f"❌ Error finding existing hedge pairs: {e}")
            return []
    
    def _find_single_side_profitable(self, positions: List[Any]) -> List[HedgeCombination]:
        """🔍 หาไม้ฝั่งเดียวที่ P&L รวมเป็นบวก (เฉพาะเมื่อไม่มีไม้ฝั่งตรงข้าม) - DISABLED"""
        try:
            # 🚫 DISABLED: ห้ามปิดไม้ฝั่งเดียว - ต้องจับคู่ Hedge เสมอ
            if not self.allow_single_side_closing:
                logger.info("🚫 Single side closing DISABLED - Force Hedge Pairing only")
                return []
            
            # ตรวจสอบว่ามีไม้ฝั่งตรงข้ามหรือไม่
            buy_positions = [pos for pos in positions if getattr(pos, 'type', 0) == 0]
            sell_positions = [pos for pos in positions if getattr(pos, 'type', 0) == 1]
            
            # ถ้ามีไม้ฝั่งตรงข้ามทั้งสองฝั่ง ให้ข้ามฟังก์ชันนี้
            if len(buy_positions) > 0 and len(sell_positions) > 0:
                logger.info("⚠️ Both BUY and SELL positions exist - skipping single side closing")
                return []
            
            # ถ้ามีไม้ฝั่งเดียวเท่านั้น ให้หาการรวมที่กำไร
            if len(buy_positions) >= 2:
                logger.info("🔍 Only BUY positions found - looking for profitable BUY combinations")
                return self._find_single_side_combinations(buy_positions, "BUY_ONLY")
            elif len(sell_positions) >= 2:
                logger.info("🔍 Only SELL positions found - looking for profitable SELL combinations")
                return self._find_single_side_combinations(sell_positions, "SELL_ONLY")
            else:
                logger.info("⚠️ Not enough positions for single side closing (need at least 2)")
                return []
                
        except Exception as e:
            logger.error(f"❌ Error in find single side profitable: {e}")
            return []
    
    def _find_single_side_combinations(self, positions: List[Any], side_type: str) -> List[HedgeCombination]:
        """🔍 หาการรวมไม้ฝั่งเดียวที่กำไร"""
        try:
            combinations = []
            used_positions = set()
            
            # หาการรวม 2-4 ไม้
            for combo_size in range(2, min(5, len(positions) + 1)):
                for combo in self._generate_combinations(positions, combo_size):
                    # ตรวจสอบว่าไม้ไม่ซ้ำ
                    combo_tickets = [getattr(pos, 'ticket', 'N/A') for pos in combo]
                    if any(ticket in used_positions for ticket in combo_tickets):
                        continue
                    
                    # คำนวณกำไรรวม
                    total_profit = sum(getattr(pos, 'profit', 0) for pos in combo)
                    
                    # ตรวจสอบว่ากำไรรวมเป็นบวก
                    if total_profit >= self.min_net_profit:
                        # สร้าง HedgeCombination
                        combination = HedgeCombination(
                            positions=combo,
                            total_profit=total_profit,
                            combination_type=f"{side_type}_{combo_size}",
                            size=len(combo),
                            confidence_score=min(95.0, 70.0 + (total_profit * 2)),
                            reason=f"Single side profitable: {side_type} {combo_size} positions"
                        )
                        combinations.append(combination)
                        
                        # เพิ่มไม้ที่ใช้แล้ว
                        used_positions.update(combo_tickets)
            
            return combinations
            
        except Exception as e:
            logger.error(f"❌ Error in find single side combinations: {e}")
            return []
    
    def _generate_combinations(self, positions: List[Any], combo_size: int) -> List[List[Any]]:
        """🔍 สร้างการรวมไม้ตามขนาดที่กำหนด"""
        try:
            from itertools import combinations
            return list(combinations(positions, combo_size))
        except Exception as e:
            logger.error(f"❌ Error generating combinations: {e}")
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
    
    
    def _find_advanced_pairing_combinations(self, positions: List[Any]) -> List[HedgeCombination]:
        """🧠 หาการจับคู่ขั้นสูง - กลยุทธ์หลากหลาย"""
        try:
            if len(positions) < 2:
                return []
            
            advanced_combinations = []
            
            # 1. Multi-Level Pairing - จับคู่หลายระดับ (2-3-4-5 ไม้)
            if self.multi_level_pairing:
                multi_level = self._find_multi_level_pairing(positions)
                advanced_combinations.extend(multi_level)
            
            # 2. Cascade Pairing - จับคู่แบบต่อเนื่อง (A+B, A+B+C, A+B+C+D)
            if self.cascade_pairing:
                cascade = self._find_cascade_pairing(positions)
                advanced_combinations.extend(cascade)
            
            # 3. Reverse Pairing - จับคู่ย้อนกลับ (หาไม้ช่วยจากไม้ที่เสียมาก)
            if self.reverse_pairing:
                reverse = self._find_reverse_pairing(positions)
                advanced_combinations.extend(reverse)
            
            # 4. Smart Priority Pairing - จับคู่ตามความสำคัญ (ไม้เสียมากก่อน)
            if self.smart_priority_pairing:
                smart_priority = self._find_smart_priority_pairing(positions)
                advanced_combinations.extend(smart_priority)
            
            # เรียงตามกำไร (มากไปน้อย)
            advanced_combinations.sort(key=lambda x: x.total_profit, reverse=True)
            
            return advanced_combinations[:10]  # ส่งคืนแค่ 10 อันแรก
            
        except Exception as e:
            logger.error(f"❌ Error in advanced pairing: {e}")
            return []
    
    def _find_multi_level_pairing(self, positions: List[Any]) -> List[HedgeCombination]:
        """🔢 จับคู่หลายระดับ (2-3-4-5 ไม้)"""
        try:
            combinations = []
            
            # แยกไม้ Buy และ Sell
            buy_positions = [p for p in positions if getattr(p, 'type', 0) == 0]
            sell_positions = [p for p in positions if getattr(p, 'type', 0) == 1]
            
            # จับคู่ 2 ไม้ (Buy + Sell)
            for buy_pos in buy_positions:
                for sell_pos in sell_positions:
                    total_profit = getattr(buy_pos, 'profit', 0) + getattr(sell_pos, 'profit', 0)
                    if total_profit >= self.min_net_profit:
                        combinations.append(HedgeCombination(
                            positions=[buy_pos, sell_pos],
                            total_profit=total_profit,
                            combination_type="MULTI_LEVEL_2",
                            size=2,
                            confidence_score=min(90.0, 60.0 + (total_profit * 10)),
                            reason=f"Multi-level 2: ${total_profit:.2f}"
                        ))
            
            # จับคู่ 3 ไม้ (Buy + Sell + Helper)
            for buy_pos in buy_positions:
                for sell_pos in sell_positions:
                    for helper_pos in positions:
                        if helper_pos not in [buy_pos, sell_pos]:
                            total_profit = (getattr(buy_pos, 'profit', 0) + 
                                          getattr(sell_pos, 'profit', 0) + 
                                          getattr(helper_pos, 'profit', 0))
                            if total_profit >= self.min_net_profit:
                                combinations.append(HedgeCombination(
                                    positions=[buy_pos, sell_pos, helper_pos],
                                    total_profit=total_profit,
                                    combination_type="MULTI_LEVEL_3",
                                    size=3,
                                    confidence_score=min(95.0, 70.0 + (total_profit * 8)),
                                    reason=f"Multi-level 3: ${total_profit:.2f}"
                                ))
            
            return combinations[:5]  # ส่งคืนแค่ 5 อันแรก
            
        except Exception as e:
            logger.error(f"❌ Error in multi-level pairing: {e}")
            return []
    
    def _find_cascade_pairing(self, positions: List[Any]) -> List[HedgeCombination]:
        """🔄 จับคู่แบบต่อเนื่อง (A+B, A+B+C, A+B+C+D)"""
        try:
            combinations = []
            
            # หาไม้ที่เสียมากที่สุดก่อน
            losing_positions = [p for p in positions if getattr(p, 'profit', 0) < 0]
            losing_positions.sort(key=lambda x: getattr(x, 'profit', 0))  # เรียงจากเสียมากไปน้อย
            
            # หาไม้ที่กำไรมากที่สุด
            profitable_positions = [p for p in positions if getattr(p, 'profit', 0) > 0]
            profitable_positions.sort(key=lambda x: getattr(x, 'profit', 0), reverse=True)  # เรียงจากกำไรมากไปน้อย
            
            # Cascade: ไม้เสีย + ไม้กำไร (ต่อเนื่อง)
            for losing_pos in losing_positions[:3]:  # ไม้เสียมาก 3 อันแรก
                for profit_pos in profitable_positions[:5]:  # ไม้กำไร 5 อันแรก
                    total_profit = getattr(losing_pos, 'profit', 0) + getattr(profit_pos, 'profit', 0)
                    if total_profit >= self.min_net_profit:
                        combinations.append(HedgeCombination(
                            positions=[losing_pos, profit_pos],
                            total_profit=total_profit,
                            combination_type="CASCADE_2",
                            size=2,
                            confidence_score=min(85.0, 65.0 + (total_profit * 12)),
                            reason=f"Cascade 2: ${total_profit:.2f}"
                        ))
            
            return combinations[:5]  # ส่งคืนแค่ 5 อันแรก
            
        except Exception as e:
            logger.error(f"❌ Error in cascade pairing: {e}")
            return []
    
    def _find_reverse_pairing(self, positions: List[Any]) -> List[HedgeCombination]:
        """🔄 จับคู่ย้อนกลับ (หาไม้ช่วยจากไม้ที่เสียมาก)"""
        try:
            combinations = []
            
            # หาไม้ที่เสียมากที่สุด
            losing_positions = [p for p in positions if getattr(p, 'profit', 0) < -5.0]  # เสียมากกว่า $5
            losing_positions.sort(key=lambda x: getattr(x, 'profit', 0))  # เรียงจากเสียมากไปน้อย
            
            # หาไม้ที่กำไร (เป็น Helper)
            helper_positions = [p for p in positions if getattr(p, 'profit', 0) > 0]
            helper_positions.sort(key=lambda x: getattr(x, 'profit', 0), reverse=True)  # เรียงจากกำไรมากไปน้อย
            
            # Reverse: ไม้เสียมาก + ไม้ช่วย
            for losing_pos in losing_positions[:2]:  # ไม้เสียมาก 2 อันแรก
                for helper_pos in helper_positions[:3]:  # ไม้ช่วย 3 อันแรก
                    total_profit = getattr(losing_pos, 'profit', 0) + getattr(helper_pos, 'profit', 0)
                    if total_profit >= self.min_net_profit:
                        combinations.append(HedgeCombination(
                            positions=[losing_pos, helper_pos],
                            total_profit=total_profit,
                            combination_type="REVERSE_PAIRING",
                            size=2,
                            confidence_score=min(95.0, 75.0 + (total_profit * 15)),
                            reason=f"Reverse pairing: ${total_profit:.2f}"
                        ))
            
            return combinations[:3]  # ส่งคืนแค่ 3 อันแรก
            
        except Exception as e:
            logger.error(f"❌ Error in reverse pairing: {e}")
            return []
    
    def _find_smart_priority_pairing(self, positions: List[Any]) -> List[HedgeCombination]:
        """🧠 จับคู่ตามความสำคัญ (ไม้เสียมากก่อน)"""
        try:
            combinations = []
            
            # คำนวณ Priority Score สำหรับแต่ละไม้
            priority_positions = []
            for pos in positions:
                profit = getattr(pos, 'profit', 0)
                volume = getattr(pos, 'volume', 0.01)
                time_open = getattr(pos, 'time', 0)
                
                # Priority Score = (ขาดทุน * ขนาด * เวลา) / 1000
                priority_score = abs(profit) * volume * (time.time() - time_open) / 1000
                priority_positions.append((pos, priority_score))
            
            # เรียงตาม Priority Score (มากไปน้อย)
            priority_positions.sort(key=lambda x: x[1], reverse=True)
            
            # จับคู่ไม้ที่มี Priority สูง
            for i, (pos1, score1) in enumerate(priority_positions[:5]):
                for j, (pos2, score2) in enumerate(priority_positions[i+1:6]):
                    total_profit = getattr(pos1, 'profit', 0) + getattr(pos2, 'profit', 0)
                    if total_profit >= self.min_net_profit:
                        combinations.append(HedgeCombination(
                            positions=[pos1, pos2],
                            total_profit=total_profit,
                            combination_type="SMART_PRIORITY",
                            size=2,
                            confidence_score=min(90.0, 70.0 + (total_profit * 10)),
                            reason=f"Smart priority: ${total_profit:.2f}"
                        ))
            
            return combinations[:3]  # ส่งคืนแค่ 3 อันแรก
            
        except Exception as e:
            logger.error(f"❌ Error in smart priority pairing: {e}")
            return []
    
    def _find_enhanced_helping_combinations(self, positions: List[Any]) -> List[HedgeCombination]:
        """🎯 ระบบช่วยเหลือขั้นสูง"""
        try:
            if len(positions) < 2:
                return []
            
            enhanced_combinations = []
            
            # 1. Multi-Helper System - ไม้ช่วยหลายตัว
            if self.multi_helper_system:
                multi_helper = self._find_multi_helper_combinations(positions)
                enhanced_combinations.extend(multi_helper)
            
            # 2. Cascade Helping - ช่วยแบบต่อเนื่อง
            if self.cascade_helping:
                cascade_helping = self._find_cascade_helping_combinations(positions)
                enhanced_combinations.extend(cascade_helping)
            
            # 3. Smart Helper Selection - เลือกไม้ช่วยอย่างฉลาด
            if self.smart_helper_selection:
                smart_helper = self._find_smart_helper_combinations(positions)
                enhanced_combinations.extend(smart_helper)
            
            # 4. Emergency Helper Mode - โหมดช่วยเหลือฉุกเฉิน
            if self.emergency_helper_mode:
                emergency_helper = self._find_emergency_helper_combinations(positions)
                enhanced_combinations.extend(emergency_helper)
            
            # เรียงตามกำไร (มากไปน้อย)
            enhanced_combinations.sort(key=lambda x: x.total_profit, reverse=True)
            
            return enhanced_combinations[:8]  # ส่งคืนแค่ 8 อันแรก
            
        except Exception as e:
            logger.error(f"❌ Error in enhanced helping: {e}")
            return []
    
    def _find_multi_helper_combinations(self, positions: List[Any]) -> List[HedgeCombination]:
        """🤝 ไม้ช่วยหลายตัว (Helper1+Helper2+Main)"""
        try:
            combinations = []
            
            # หาไม้ที่เสียมาก
            losing_positions = [p for p in positions if getattr(p, 'profit', 0) < -2.0]
            losing_positions.sort(key=lambda x: getattr(x, 'profit', 0))  # เรียงจากเสียมากไปน้อย
            
            # หาไม้ที่กำไร (Helper)
            helper_positions = [p for p in positions if getattr(p, 'profit', 0) > 0]
            helper_positions.sort(key=lambda x: getattr(x, 'profit', 0), reverse=True)  # เรียงจากกำไรมากไปน้อย
            
            # Multi-Helper: ไม้เสีย + Helper1 + Helper2
            for losing_pos in losing_positions[:2]:  # ไม้เสียมาก 2 อันแรก
                for helper1 in helper_positions[:3]:  # Helper1
                    for helper2 in helper_positions[1:4]:  # Helper2 (ไม่ซ้ำกับ Helper1)
                        if helper1 != helper2:
                            total_profit = (getattr(losing_pos, 'profit', 0) + 
                                          getattr(helper1, 'profit', 0) + 
                                          getattr(helper2, 'profit', 0))
                            if total_profit >= self.min_net_profit:
                                combinations.append(HedgeCombination(
                                    positions=[losing_pos, helper1, helper2],
                                    total_profit=total_profit,
                                    combination_type="MULTI_HELPER",
                                    size=3,
                                    confidence_score=min(95.0, 80.0 + (total_profit * 8)),
                                    reason=f"Multi-helper: ${total_profit:.2f}"
                                ))
            
            return combinations[:3]  # ส่งคืนแค่ 3 อันแรก
            
        except Exception as e:
            logger.error(f"❌ Error in multi-helper combinations: {e}")
            return []
    
    def _find_cascade_helping_combinations(self, positions: List[Any]) -> List[HedgeCombination]:
        """🔄 ช่วยแบบต่อเนื่อง (Helper→Main→Helper2)"""
        try:
            combinations = []
            
            # หาไม้ที่เสียมาก
            losing_positions = [p for p in positions if getattr(p, 'profit', 0) < -3.0]
            losing_positions.sort(key=lambda x: getattr(x, 'profit', 0))
            
            # หาไม้ที่กำไร (Helper)
            helper_positions = [p for p in positions if getattr(p, 'profit', 0) > 0]
            helper_positions.sort(key=lambda x: getattr(x, 'profit', 0), reverse=True)
            
            # Cascade Helping: ไม้เสีย + Helper1 + Helper2 + Helper3
            for losing_pos in losing_positions[:1]:  # ไม้เสียมาก 1 อันแรก
                for helper1 in helper_positions[:2]:  # Helper1
                    for helper2 in helper_positions[1:3]:  # Helper2
                        for helper3 in helper_positions[2:4]:  # Helper3
                            # ตรวจสอบไม่ซ้ำกันโดยใช้ ticket
                            tickets = [getattr(helper1, 'ticket', 0), getattr(helper2, 'ticket', 0), getattr(helper3, 'ticket', 0)]
                            if len(set(tickets)) == 3:  # ไม่ซ้ำกัน
                                total_profit = (getattr(losing_pos, 'profit', 0) + 
                                              getattr(helper1, 'profit', 0) + 
                                              getattr(helper2, 'profit', 0) + 
                                              getattr(helper3, 'profit', 0))
                                if total_profit >= self.min_net_profit:
                                    combinations.append(HedgeCombination(
                                        positions=[losing_pos, helper1, helper2, helper3],
                                        total_profit=total_profit,
                                        combination_type="CASCADE_HELPING",
                                        size=4,
                                        confidence_score=min(98.0, 85.0 + (total_profit * 6)),
                                        reason=f"Cascade helping: ${total_profit:.2f}"
                                    ))
            
            return combinations[:2]  # ส่งคืนแค่ 2 อันแรก
            
        except Exception as e:
            logger.error(f"❌ Error in cascade helping: {e}")
            return []
    
    def _find_smart_helper_combinations(self, positions: List[Any]) -> List[HedgeCombination]:
        """🧠 เลือกไม้ช่วยอย่างฉลาด"""
        try:
            combinations = []
            
            # หาไม้ที่เสียมาก
            losing_positions = [p for p in positions if getattr(p, 'profit', 0) < -1.0]
            losing_positions.sort(key=lambda x: getattr(x, 'profit', 0))
            
            # หาไม้ที่กำไร (Helper) - เลือกอย่างฉลาด
            helper_positions = [p for p in positions if getattr(p, 'profit', 0) > 0]
            
            # Smart Selection: เลือก Helper ที่เหมาะสมกับไม้เสีย
            for losing_pos in losing_positions[:3]:
                best_helpers = []
                losing_profit = getattr(losing_pos, 'profit', 0)
                
                for helper_pos in helper_positions:
                    helper_profit = getattr(helper_pos, 'profit', 0)
                    # เลือก Helper ที่กำไรพอที่จะช่วยไม้เสียได้
                    if helper_profit >= abs(losing_profit) * 0.5:  # กำไรอย่างน้อย 50% ของขาดทุน
                        best_helpers.append((helper_pos, helper_profit))
                
                # เรียงตามกำไร (มากไปน้อย)
                best_helpers.sort(key=lambda x: x[1], reverse=True)
                
                # จับคู่กับ Helper ที่ดีที่สุด
                for helper_pos, helper_profit in best_helpers[:2]:
                    total_profit = losing_profit + helper_profit
                    if total_profit >= self.min_net_profit:
                        combinations.append(HedgeCombination(
                            positions=[losing_pos, helper_pos],
                            total_profit=total_profit,
                            combination_type="SMART_HELPER",
                            size=2,
                            confidence_score=min(95.0, 75.0 + (total_profit * 12)),
                            reason=f"Smart helper: ${total_profit:.2f}"
                        ))
            
            return combinations[:4]  # ส่งคืนแค่ 4 อันแรก
            
        except Exception as e:
            logger.error(f"❌ Error in smart helper: {e}")
            return []
    
    def _find_emergency_helper_combinations(self, positions: List[Any]) -> List[HedgeCombination]:
        """🚨 โหมดช่วยเหลือฉุกเฉิน (ไม้เสียมาก)"""
        try:
            combinations = []
            
            # หาไม้ที่เสียมาก (Emergency)
            emergency_positions = [p for p in positions if getattr(p, 'profit', 0) < -10.0]
            emergency_positions.sort(key=lambda x: getattr(x, 'profit', 0))
            
            # หาไม้ที่กำไร (Emergency Helper)
            emergency_helpers = [p for p in positions if getattr(p, 'profit', 0) > 5.0]
            emergency_helpers.sort(key=lambda x: getattr(x, 'profit', 0), reverse=True)
            
            # Emergency: ไม้เสียมาก + Emergency Helper
            for emergency_pos in emergency_positions[:2]:  # ไม้เสียมาก 2 อันแรก
                for emergency_helper in emergency_helpers[:3]:  # Emergency Helper 3 อันแรก
                    total_profit = (getattr(emergency_pos, 'profit', 0) + 
                                  getattr(emergency_helper, 'profit', 0))
                    if total_profit >= self.min_net_profit:
                        combinations.append(HedgeCombination(
                            positions=[emergency_pos, emergency_helper],
                            total_profit=total_profit,
                            combination_type="EMERGENCY_HELPER",
                            size=2,
                            confidence_score=min(99.0, 90.0 + (total_profit * 5)),
                            reason=f"Emergency helper: ${total_profit:.2f}"
                        ))
            
            return combinations[:2]  # ส่งคืนแค่ 2 อันแรก
            
        except Exception as e:
            logger.error(f"❌ Error in emergency helper: {e}")
            return []
    
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
    
    def _identify_stale_positions(self, positions: List[Any]) -> List[Any]:
        """🧹 ระบุไม้ค้างพอร์ต"""
        try:
            stale_positions = []
            current_time = time.time()
            
            for pos in positions:
                # ตรวจสอบอายุไม้
                pos_time = getattr(pos, 'time', current_time)
                age_hours = (current_time - pos_time) / 3600
                
                # ตรวจสอบขาดทุน
                profit = getattr(pos, 'profit', 0)
                
                # เงื่อนไขไม้ค้าง: อายุ ≥ threshold หรือ ขาดทุนหนัก
                is_old = age_hours >= self.stale_age_threshold_hours
                is_heavy_loss = profit <= self.stale_loss_threshold
                
                if is_old or is_heavy_loss:
                    stale_positions.append(pos)
                    logger.debug(f"🧹 Stale position: Ticket {getattr(pos, 'ticket', 'N/A')}, "
                               f"Age: {age_hours:.1f}h, Profit: ${profit:.2f}")
            
            if stale_positions:
                logger.info(f"🧹 Found {len(stale_positions)} stale positions")
            
            return stale_positions
            
        except Exception as e:
            logger.error(f"❌ Error identifying stale positions: {e}")
            return []
    
    def _should_include_anchors_for_stale_clearing(self, stale_positions: List[Any], all_positions: List[Any]) -> bool:
        """🧹 ตรวจสอบว่าควรใช้ Anchor ช่วยเคลียร์ไม้ค้างหรือไม่"""
        try:
            if not self.stale_anchor_inclusion_enabled or not stale_positions:
                return False
            
            if self.stale_anchor_threshold_avg:
                # ใช้ค่าเฉลี่ยไม้ค้าง
                avg_stale_loss = sum(getattr(pos, 'profit', 0) for pos in stale_positions) / len(stale_positions)
                threshold_met = avg_stale_loss <= self.stale_loss_threshold
                logger.info(f"🧹 Avg stale loss: ${avg_stale_loss:.2f}, threshold: ${self.stale_loss_threshold}")
            else:
                # ใช้จำนวนไม้ค้าง ≥ 5
                threshold_met = len(stale_positions) >= 5
                logger.info(f"🧹 Stale count: {len(stale_positions)}, threshold: 5")
            
            if threshold_met:
                logger.info("🧹 Anchor inclusion approved for stale clearing")
            
            return threshold_met
            
        except Exception as e:
            logger.error(f"❌ Error checking anchor inclusion: {e}")
            return False
    
    def _is_stale_position(self, position: Any) -> bool:
        """🧹 ตรวจสอบว่าเป็นไม้ค้างหรือไม่"""
        try:
            current_time = time.time()
            pos_time = getattr(position, 'time', current_time)
            age_hours = (current_time - pos_time) / 3600
            profit = getattr(position, 'profit', 0)
            
            is_old = age_hours >= self.stale_age_threshold_hours
            is_heavy_loss = profit <= self.stale_loss_threshold
            
            return is_old or is_heavy_loss
            
        except Exception as e:
            logger.error(f"❌ Error checking if stale position: {e}")
            return False
    
    def _find_stale_clearing_combinations(self, positions: List[Any], stale_positions: List[Any]) -> List[HedgeCombination]:
        """🧹 หาการจับคู่เพื่อเคลียร์ไม้ค้างพอร์ต"""
        try:
            combinations = []
            
            # แยกไม้ตามประเภท
            stale_pos = stale_positions[:10]  # จำกัดไม้ค้างสูงสุด 10 ตัว
            profitable_pos = [p for p in positions if getattr(p, 'profit', 0) > 0]
            anchor_pos = [p for p in positions if getattr(p, 'magic', None) == 789012]
            
            logger.info(f"🧹 Stale clearing: {len(stale_pos)} stale, {len(profitable_pos)} profitable, {len(anchor_pos)} anchors")
            
            # กลยุทธ์ 1: ไม้ค้าง + ไม้กำไร
            for stale_combo_size in range(1, min(len(stale_pos) + 1, 6)):  # 1-5 ไม้ค้าง
                for stale_combo in itertools.combinations(stale_pos, stale_combo_size):
                    stale_loss = sum(getattr(p, 'profit', 0) for p in stale_combo)
                    
                    # หาไม้กำไรที่พอชดเชย
                    for profit_combo_size in range(1, min(len(profitable_pos) + 1, 6)):
                        for profit_combo in itertools.combinations(profitable_pos, profit_combo_size):
                            profit_gain = sum(getattr(p, 'profit', 0) for p in profit_combo)
                            total_profit = stale_loss + profit_gain
                            
                            if total_profit >= self.min_net_profit:
                                combo_positions = list(stale_combo) + list(profit_combo)
                                
                                # คำนวณ priority score (โบนัสสำหรับไม้ค้าง)
                                base_score = 60.0 + (total_profit * 10)
                                stale_bonus = len(stale_combo) * self.stale_priority_bonus * 100
                                priority_score = min(95.0, base_score + stale_bonus)
                                
                                combinations.append(HedgeCombination(
                                    positions=combo_positions,
                                    total_profit=total_profit,
                                    combination_type=f"STALE_CLEAR_{len(stale_combo)}S+{len(profit_combo)}P",
                                    size=len(combo_positions),
                                    confidence_score=priority_score,
                                    reason=f"Stale clearing: {len(stale_combo)} stale + {len(profit_combo)} profitable = ${total_profit:.2f}"
                                ))
            
            # กลยุทธ์ 2: ไม้ค้าง + ไม้กำไร + Anchor (ถ้าได้รับอนุญาต)
            if anchor_pos:
                for stale_combo_size in range(2, min(len(stale_pos) + 1, 5)):  # 2-4 ไม้ค้าง
                    for stale_combo in itertools.combinations(stale_pos, stale_combo_size):
                        stale_loss = sum(getattr(p, 'profit', 0) for p in stale_combo)
                        
                        # รวมไม้กำไร + Anchor
                        helper_positions = profitable_pos + anchor_pos
                        for helper_combo_size in range(1, min(len(helper_positions) + 1, 6)):
                            for helper_combo in itertools.combinations(helper_positions, helper_combo_size):
                                helper_gain = sum(getattr(p, 'profit', 0) for p in helper_combo)
                                total_profit = stale_loss + helper_gain
                                
                                if total_profit >= self.min_net_profit:
                                    combo_positions = list(stale_combo) + list(helper_combo)
                                    anchor_count = sum(1 for p in helper_combo if getattr(p, 'magic', None) == 789012)
                                    
                                    # คำนวณ priority score (โบนัสพิเศษสำหรับ Anchor)
                                    base_score = 70.0 + (total_profit * 12)
                                    stale_bonus = len(stale_combo) * self.stale_priority_bonus * 100
                                    anchor_bonus = anchor_count * 20  # โบนัส Anchor
                                    priority_score = min(98.0, base_score + stale_bonus + anchor_bonus)
                                    
                                    combinations.append(HedgeCombination(
                                        positions=combo_positions,
                                        total_profit=total_profit,
                                        combination_type=f"STALE_CLEAR_{len(stale_combo)}S+{len(helper_combo)-anchor_count}P+{anchor_count}A",
                                        size=len(combo_positions),
                                        confidence_score=priority_score,
                                        reason=f"Stale+Anchor clearing: {len(stale_combo)} stale + {anchor_count} anchors = ${total_profit:.2f}"
                                    ))
            
            # เรียงตาม priority score (สูงสุดก่อน)
            combinations.sort(key=lambda x: x.confidence_score, reverse=True)
            
            return combinations[:5]  # ส่งคืนแค่ 5 อันแรก
            
        except Exception as e:
            logger.error(f"❌ Error finding stale clearing combinations: {e}")
            return []

def create_hedge_pairing_closer(symbol: str = "XAUUSD") -> HedgePairingCloser:
    """สร้าง Hedge Pairing Closer"""
    return HedgePairingCloser(symbol=symbol)
