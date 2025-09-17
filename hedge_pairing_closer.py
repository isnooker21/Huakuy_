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
class PositionStatus:
    """สถานะของไม้แต่ละตัว"""
    ticket: int
    position: Any
    status: str  # WINNER, LOSER, HELP_NEEDED, HEDGE_CANDIDATE, RECOVERY_NEEDED
    profit: float
    profit_percentage: float
    priority_score: float
    recommended_action: str
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
        
        # 🎯 Smart Position Tracking System
        self.position_tracking_enabled = True
        self.help_needed_threshold = -50.0  # ขาดทุนมากกว่า $50 ต้องการความช่วยเหลือ
        self.recovery_needed_threshold = -100.0  # ขาดทุนมากกว่า $100 ต้องการ Recovery
        self.winner_threshold = 10.0  # กำไรมากกว่า $10 ถือเป็น WINNER
        
        # 💰 Close All When Portfolio Profitable - ปิดไม้ทั้งหมดเมื่อพอร์ตเป็นบวก (ต้องจับคู่ Hedge ก่อน)
        self.close_all_when_profitable = False  # ปิดการปิดไม้ทั้งหมด - ใช้ Hedge Pairing แทน
        self.profitable_threshold_percentage = 2.0  # เพิ่มเป็น 2% ของเงินทุน (ยากขึ้น)
        self.min_profit_for_close_all = 20.0  # เพิ่มเป็น $20 (ยากขึ้น)
        self.urgent_profit_threshold = 100.0  # เพิ่มเป็น $100 (ยากขึ้น)
        
        # 🎯 Force Hedge Pairing - บังคับให้จับคู่ Hedge เสมอ
        self.force_hedge_pairing = True  # บังคับให้จับคู่ Hedge ก่อนปิด
        self.allow_single_side_closing = False  # ห้ามปิดไม้ฝั่งเดียว
        self.force_hedge_pairing_only = True  # บังคับให้ใช้ Hedge Pairing เท่านั้น
        
        # 🚨 Emergency Mode Parameters (สำหรับพอร์ตที่แย่มาก)
        self.emergency_min_net_profit = 0.01  # กำไรขั้นต่ำในโหมดฉุกเฉิน $0.01
        self.emergency_threshold_percentage = 0.10  # 10% ในโหมดฉุกเฉิน
        
        
        
        
        
        
        # 🔧 Position Generation Parameters
        self.enable_position_generation = True  # เปิดใช้งานการออกไม้เพิ่มเติม
        self.max_additional_positions = 3
        
        # 🎯 Multi-Helper System - ระบบหลักสำหรับการจับคู่และไม้ช่วย
        # ระบบอื่นๆ ถูกลบออกเพื่อไม่รบกวน Multi-Helper System
        
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
    
    def analyze_position_status(self, position: Any) -> PositionStatus:
        """🎯 วิเคราะห์สถานะของไม้แต่ละตัว"""
        try:
            if not self.position_tracking_enabled:
                return None
                
            ticket = getattr(position, 'ticket', 0)
            profit = getattr(position, 'profit', 0)
            pos_type = getattr(position, 'type', 0)
            price_open = getattr(position, 'price_open', 0)
            price_current = getattr(position, 'price_current', 0)
            volume = getattr(position, 'volume', 0)
            
            # คำนวณกำไรเป็นเปอร์เซ็นต์
            if price_open > 0:
                profit_percentage = (profit / (price_open * volume * 100)) * 100
            else:
                profit_percentage = 0
            
            # กำหนดสถานะ
            if profit >= self.winner_threshold:
                status = "WINNER"
                priority_score = 1.0  # ความสำคัญต่ำ
                recommended_action = "KEEP"
                reason = f"กำไรดี: ${profit:.2f}"
            elif profit <= self.recovery_needed_threshold:
                status = "RECOVERY_NEEDED"
                priority_score = 10.0  # ความสำคัญสูงมาก
                recommended_action = "URGENT_RECOVERY"
                reason = f"ขาดทุนมาก: ${profit:.2f} - ต้องการ Recovery"
            elif profit <= self.help_needed_threshold:
                status = "HELP_NEEDED"
                priority_score = 8.0  # ความสำคัญสูง
                recommended_action = "NEED_HELP"
                reason = f"ขาดทุนปานกลาง: ${profit:.2f} - ต้องการความช่วยเหลือ"
            elif profit < 0:
                status = "LOSER"
                priority_score = 5.0  # ความสำคัญปานกลาง
                recommended_action = "HEDGE_CANDIDATE"
                reason = f"ขาดทุนเล็กน้อย: ${profit:.2f} - เป็นตัวเลือก Hedge"
            else:
                status = "NEUTRAL"
                priority_score = 3.0  # ความสำคัญต่ำ
                recommended_action = "MONITOR"
                reason = f"กำไรเล็กน้อย: ${profit:.2f} - ติดตาม"
            
            # ปรับ Priority Score ตามประเภทไม้
            if pos_type == 0:  # BUY
                priority_score *= 1.2  # BUY มีความสำคัญสูงกว่า
            else:  # SELL
                priority_score *= 1.0  # SELL ความสำคัญปกติ
            
            return PositionStatus(
                ticket=ticket,
                position=position,
                status=status,
                profit=profit,
                profit_percentage=profit_percentage,
                priority_score=priority_score,
                recommended_action=recommended_action,
                reason=reason
            )
            
        except Exception as e:
            logger.error(f"❌ Error analyzing position status: {e}")
            return None
    
    def get_position_status_summary(self, positions: List[Any]) -> Dict:
        """📊 สรุปสถานะไม้ทั้งหมด"""
        try:
            if not self.position_tracking_enabled or not positions:
                return {}
            
            position_statuses = []
            status_counts = {
                'WINNER': 0,
                'LOSER': 0,
                'HELP_NEEDED': 0,
                'RECOVERY_NEEDED': 0,
                'NEUTRAL': 0
            }
            
            total_profit = 0
            urgent_positions = []
            help_needed_positions = []
            
            for position in positions:
                status = self.analyze_position_status(position)
                if status:
                    position_statuses.append(status)
                    status_counts[status.status] += 1
                    total_profit += status.profit
                    
                    if status.status == "RECOVERY_NEEDED":
                        urgent_positions.append(status)
                    elif status.status == "HELP_NEEDED":
                        help_needed_positions.append(status)
            
            # เรียงลำดับตาม Priority Score (สูงสุดก่อน)
            position_statuses.sort(key=lambda x: x.priority_score, reverse=True)
            
            return {
                'total_positions': len(positions),
                'status_counts': status_counts,
                'total_profit': total_profit,
                'urgent_positions': urgent_positions,
                'help_needed_positions': help_needed_positions,
                'all_statuses': position_statuses,
                'portfolio_health': self._assess_portfolio_health(status_counts, total_profit)
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting position status summary: {e}")
            return {}
    
    def _assess_portfolio_health(self, status_counts: Dict, total_profit: float) -> str:
        """🏥 ประเมินสุขภาพพอร์ต"""
        try:
            total_positions = sum(status_counts.values())
            if total_positions == 0:
                return "ไม่มีไม้"
            
            # คำนวณอัตราส่วน
            recovery_ratio = status_counts['RECOVERY_NEEDED'] / total_positions
            help_ratio = status_counts['HELP_NEEDED'] / total_positions
            winner_ratio = status_counts['WINNER'] / total_positions
            
            # ประเมินสุขภาพ
            if recovery_ratio > 0.3:  # มากกว่า 30% ต้องการ Recovery
                return "แย่มาก"
            elif recovery_ratio > 0.2 or help_ratio > 0.4:  # มากกว่า 20% Recovery หรือ 40% Help
                return "แย่"
            elif total_profit < -100:  # ขาดทุนมากกว่า $100
                return "แย่"
            elif winner_ratio > 0.5:  # มากกว่า 50% กำไร
                return "ดี"
            elif total_profit > 50:  # กำไรมากกว่า $50
                return "ดี"
            else:
                return "ปานกลาง"
                
        except Exception as e:
            logger.error(f"❌ Error assessing portfolio health: {e}")
            return "ไม่ทราบ"
        # 📊 Performance Tracking (ย้ายไปข้างบนแล้ว)
        self.mt5_connection = None  # จะถูกตั้งค่าในภายหลัง
        
        # ⏰ Advanced Search Timing (1 hour delay)
        self.last_advanced_search_time = 0  # เวลาล่าสุดที่ทำ Advanced Search
        
        logger.info("🚀 Hedge Pairing Closer initialized")
    
    def intelligent_closing_strategy(self, positions: List[Any]) -> ClosingDecision:
        """🧠 กลยุทธ์ปิดไม้ที่ฉลาด - ปิดไม้ไกลจากราคาปัจจุบันก่อนเสมอ"""
        try:
            if not self.position_tracking_enabled or not positions:
                return ClosingDecision(
                    should_close=False,
                    positions_to_close=[],
                    method="NO_POSITIONS",
                    net_pnl=0.0,
                    expected_pnl=0.0,
                    position_count=0,
                    buy_count=0,
                    sell_count=0,
                    confidence_score=0.0,
                    reason="ไม่มีไม้หรือระบบติดตามปิดอยู่"
                )
            
            # วิเคราะห์สถานะไม้ทั้งหมด
            status_summary = self.get_position_status_summary(positions)
            
            if not status_summary:
                return ClosingDecision(
                    should_close=False,
                    positions_to_close=[],
                    method="ANALYSIS_FAILED",
                    net_pnl=0.0,
                    expected_pnl=0.0,
                    position_count=len(positions),
                    buy_count=0,
                    sell_count=0,
                    confidence_score=0.0,
                    reason="ไม่สามารถวิเคราะห์สถานะไม้ได้"
                )
            
            urgent_positions = status_summary.get('urgent_positions', [])
            help_needed_positions = status_summary.get('help_needed_positions', [])
            all_statuses = status_summary.get('all_statuses', [])
            portfolio_health = status_summary.get('portfolio_health', 'ไม่ทราบ')
            
            logger.info("=" * 80)
            logger.info("🧠 [CLOSING STRATEGY] Intelligent Closing Strategy Started")
            logger.info("=" * 80)
            logger.info(f"📊 [PORTFOLIO] Health: {portfolio_health}")
            logger.info(f"📊 [PORTFOLIO] Urgent Positions: {len(urgent_positions)}")
            logger.info(f"📊 [PORTFOLIO] Help Needed Positions: {len(help_needed_positions)}")
            logger.info("-" * 80)
            
            # 🎯 1. ปิดไม้ไกลจากราคาปัจจุบันก่อนเสมอ (PRIORITY #1)
            logger.info("🎯 [PRIORITY 1] Checking furthest positions from current price...")
            furthest_positions = self._find_furthest_positions(positions)
            if furthest_positions:
                logger.info(f"✅ [PRIORITY 1] Found {len(furthest_positions)} furthest positions - Processing...")
                return self._close_furthest_positions(furthest_positions, all_statuses)
            else:
                logger.info("❌ [PRIORITY 1] No furthest positions found - Moving to next priority")
            
            # 2. ปิดไม้ที่ต้องการ Recovery ก่อน (RECOVERY_NEEDED)
            logger.info("🚨 [PRIORITY 2] Checking urgent positions (RECOVERY_NEEDED)...")
            if urgent_positions:
                # ตรวจสอบว่ามีไม้ติดลบหรือไม่
                total_urgent_profit = sum(pos.profit for pos in urgent_positions)
                if total_urgent_profit < 0:
                    logger.warning(f"⚠️ [PRIORITY 2] Urgent positions are losing (${total_urgent_profit:.2f}) - Skipping")
                    logger.warning(f"   🚫 [ZERO LOSS] Cannot close losing positions without helpers")
                else:
                    logger.info(f"✅ [PRIORITY 2] Found {len(urgent_positions)} urgent positions - Processing...")
                    return self._close_recovery_needed_positions(urgent_positions, all_statuses)
            else:
                logger.info("❌ [PRIORITY 2] No urgent positions found - Moving to next priority")
            
            # 3. หาไม้ที่สามารถปิดคู่กันได้ (HEDGE) - ลดเกณฑ์การจับคู่
            logger.info("🔗 [PRIORITY 3] Checking hedge candidates...")
            hedge_candidates = [s for s in all_statuses if s.recommended_action == "HEDGE_CANDIDATE"]
            if hedge_candidates:
                # ตรวจสอบว่ามีไม้ติดลบหรือไม่
                total_hedge_profit = sum(pos.profit for pos in hedge_candidates)
                
                # ลดเกณฑ์การจับคู่ - อนุญาตให้จับคู่ไม้ติดลบได้
                if total_hedge_profit < 0:
                    logger.warning(f"⚠️ [PRIORITY 3] Hedge candidates are losing (${total_hedge_profit:.2f}) - But will try pairing")
                    logger.info(f"   🔧 [HEDGE] Relaxed criteria - Allow pairing losing positions")
                
                # ลองจับคู่ไม้ติดลบ
                logger.info(f"🔍 [HEDGE] Attempting to pair {len(hedge_candidates)} hedge candidates...")
                hedge_decision = self._find_hedge_pairs(hedge_candidates, all_statuses)
                if hedge_decision.should_close:
                    logger.info(f"✅ [HEDGE] Pairing successful - Net P&L: ${hedge_decision.net_pnl:.2f}")
                    return hedge_decision
                else:
                    logger.warning(f"❌ [HEDGE] Cannot pair hedge candidates - Moving to next priority")
            else:
                logger.info("❌ [PRIORITY 3] No hedge candidates found - Moving to next priority")
            
            # 4. ปิดไม้ที่ต้องการความช่วยเหลือ (HELP_NEEDED)
            logger.info("🆘 [PRIORITY 4] Checking help needed positions...")
            if help_needed_positions:
                # ตรวจสอบว่ามีไม้ติดลบหรือไม่
                total_help_profit = sum(pos.profit for pos in help_needed_positions)
                if total_help_profit < 0:
                    logger.warning(f"⚠️ [PRIORITY 4] Help needed positions are losing (${total_help_profit:.2f}) - Skipping")
                    logger.warning(f"   🚫 [ZERO LOSS] Cannot close losing positions without helpers")
                else:
                    logger.info(f"✅ [PRIORITY 4] Found {len(help_needed_positions)} help needed positions - Processing...")
                    return self._close_help_needed_positions(help_needed_positions, all_statuses)
            else:
                logger.info("❌ [PRIORITY 4] No help needed positions found - Moving to next priority")
            
            # 5. ปิดไม้ที่ขาดทุนน้อยที่สุดก่อน (เฉพาะเมื่อไม่ติดลบ)
            losers = [s for s in all_statuses if s.status == "LOSER"]
            if losers:
                # ตรวจสอบว่ามีไม้ติดลบหรือไม่
                total_loser_profit = sum(pos.profit for pos in losers)
                if total_loser_profit < 0:
                    logger.info(f"🚫 INTELLIGENT CLOSING: All losers are losing (${total_loser_profit:.2f}) - Skipping")
                    logger.info(f"   ZERO LOSS POLICY: Cannot close losing positions without helpers")
                else:
                    return self._close_smallest_losers(losers)
            
            # 6. ปิดไม้กำไรเมื่อจำเป็น (เฉพาะเมื่อพอร์ตแย่ และไม่มีไม้ติดลบให้จับคู่)
            if portfolio_health in ["แย่", "แย่มาก"]:
                # ตรวจสอบว่ามีไม้ติดลบให้จับคู่หรือไม่
                losers = [s for s in all_statuses if s.status == "LOSER"]
                if losers:
                    logger.info(f"🚫 Portfolio health แย่ แต่มีไม้ติดลบ {len(losers)} ตัว - ข้ามการปิดไม้กำไร")
                    logger.info(f"   ควรจับคู่ไม้ติดลบก่อนปิดไม้กำไร")
                    return ClosingDecision(
                        should_close=False,
                        positions_to_close=[],
                        method="SKIP_WINNERS_FOR_LOSERS",
                        net_pnl=0.0,
                        expected_pnl=0.0,
                        position_count=len(positions),
                        buy_count=len([p for p in positions if getattr(p, 'type', 0) == 0]),
                        sell_count=len([p for p in positions if getattr(p, 'type', 0) == 1]),
                        confidence_score=0.0,
                        reason="มีไม้ติดลบให้จับคู่ - ข้ามการปิดไม้กำไร"
                    )
                
                # ไม่มีไม้ติดลบแล้วค่อยปิดไม้กำไร
                winners = [s for s in all_statuses if s.status == "WINNER"]
                if winners:
                    logger.info(f"⚠️ Portfolio health แย่ และไม่มีไม้ติดลบ - ปิดไม้กำไร {len(winners)} ตัว")
                    return self._close_some_winners(winners, portfolio_health)
            
            # ไม่มีไม้ที่ควรปิด
            return ClosingDecision(
                should_close=False,
                positions_to_close=[],
                method="NO_ACTION_NEEDED",
                net_pnl=0.0,
                expected_pnl=0.0,
                position_count=len(positions),
                buy_count=len([p for p in positions if getattr(p, 'type', 0) == 0]),
                sell_count=len([p for p in positions if getattr(p, 'type', 0) == 1]),
                confidence_score=0.0,
                reason="ไม่มีไม้ที่ควรปิดในขณะนี้"
            )
            
        except Exception as e:
            logger.error(f"❌ Error in intelligent closing strategy: {e}")
            return ClosingDecision(
                should_close=False,
                positions_to_close=[],
                method="ERROR",
                net_pnl=0.0,
                expected_pnl=0.0,
                position_count=len(positions) if positions else 0,
                buy_count=0,
                sell_count=0,
                confidence_score=0.0,
                reason=f"เกิดข้อผิดพลาด: {e}"
            )
    
    def _find_furthest_positions(self, positions: List[Any]) -> List[Any]:
        """🎯 หาไม้ที่ไกลจากราคาปัจจุบันมากที่สุด"""
        try:
            if not positions:
                return []
            
            # หาราคาปัจจุบัน
            import MetaTrader5 as mt5
            tick = mt5.symbol_info_tick(self.symbol)
            if not tick:
                logger.warning("⚠️ Cannot get current price for furthest position analysis")
                return []
            
            current_price = tick.bid
            logger.info(f"🎯 Current Price: {current_price:.5f}")
            
            # คำนวณระยะห่างจากราคาปัจจุบัน
            position_distances = []
            for pos in positions:
                try:
                    entry_price = getattr(pos, 'price_open', 0)
                    if entry_price > 0:
                        distance = abs(entry_price - current_price)
                        position_distances.append({
                            'position': pos,
                            'distance': distance,
                            'entry_price': entry_price,
                            'profit': getattr(pos, 'profit', 0),
                            'ticket': getattr(pos, 'ticket', 0)
                        })
                except Exception as e:
                    logger.warning(f"⚠️ Error calculating distance for position: {e}")
                    continue
            
            if not position_distances:
                return []
            
            # เรียงตามระยะห่าง (ไกลที่สุดก่อน)
            position_distances.sort(key=lambda x: x['distance'], reverse=True)
            
            # หาไม้ที่ไกลที่สุด (มากกว่า 5 points จากราคาปัจจุบัน)
            furthest_positions = []
            max_distance = position_distances[0]['distance']
            
            logger.info(f"🎯 Furthest Position Analysis:")
            logger.info(f"   Max Distance: {max_distance:.5f} points")
            
            for i, pos_data in enumerate(position_distances[:5]):  # แสดง 5 ตัวแรก
                logger.info(f"   {i+1}. Ticket {pos_data['ticket']}: Entry {pos_data['entry_price']:.5f}, Distance {pos_data['distance']:.5f}, Profit ${pos_data['profit']:.2f}")
            
            # เลือกไม้ที่ไกลที่สุด (มากกว่า 3 points) หรือไม้ที่ไกลที่สุด 2 ตัว
            for pos_data in position_distances:
                if pos_data['distance'] >= 3.0 or len(furthest_positions) < 2:
                    furthest_positions.append(pos_data['position'])
                    if len(furthest_positions) >= 3:  # สูงสุด 3 ตัว
                        break
            
            if furthest_positions:
                logger.info(f"🎯 Selected {len(furthest_positions)} furthest positions for closing priority")
                for i, pos in enumerate(furthest_positions):
                    entry_price = getattr(pos, 'price_open', 0)
                    distance = abs(entry_price - current_price)
                    profit = getattr(pos, 'profit', 0)
                    ticket = getattr(pos, 'ticket', 0)
                    logger.info(f"   {i+1}. Ticket {ticket}: Entry {entry_price:.5f}, Distance {distance:.5f}, Profit ${profit:.2f}")
            
            return furthest_positions
            
        except Exception as e:
            logger.error(f"❌ Error finding furthest positions: {e}")
            return []
    
    def _close_furthest_positions(self, furthest_positions: List[Any], all_statuses: List[PositionStatus]) -> ClosingDecision:
        """🎯 ปิดไม้ที่ไกลจากราคาปัจจุบันมากที่สุด - ปรับปรุงให้ฉลาดขึ้น"""
        try:
            if not furthest_positions:
                return ClosingDecision(
                    should_close=False,
                    positions_to_close=[],
                    method="NO_FURTHEST_POSITIONS",
                    net_pnl=0.0,
                    expected_pnl=0.0,
                    position_count=0,
                    buy_count=0,
                    sell_count=0,
                    confidence_score=0.0,
                    reason="ไม่มีไม้ไกลจากราคาปัจจุบัน"
                )
            
            # คำนวณกำไรรวมของไม้ไกล
            total_profit = sum(getattr(pos, 'profit', 0) for pos in furthest_positions)
            total_volume = sum(getattr(pos, 'volume', 0) for pos in furthest_positions)
            
            buy_count = len([pos for pos in furthest_positions if getattr(pos, 'type', 0) == 0])
            sell_count = len([pos for pos in furthest_positions if getattr(pos, 'type', 0) == 1])
            
            logger.info(f"🎯 CLOSING FURTHEST POSITIONS:")
            logger.info(f"   Positions: {len(furthest_positions)} (BUY: {buy_count}, SELL: {sell_count})")
            logger.info(f"   Total Profit: ${total_profit:.2f}")
            logger.info(f"   Total Volume: {total_volume:.2f}")
            
            # 🧠 SMART HEDGE PAIRING - หาไม้จับคู่ที่ฉลาดที่สุด
            if total_profit < 0:
                logger.warning(f"🚫 ZERO LOSS POLICY: Furthest positions are losing (${total_profit:.2f})")
                
                # หาไม้ช่วยที่ฉลาดที่สุด
                best_combination = self._find_smart_hedge_combination(furthest_positions, all_statuses)
                if best_combination:
                    logger.info(f"✅ SMART HEDGE SUCCESS: {best_combination['reason']} = ${best_combination['total_profit']:.2f}")
                    return best_combination
                else:
                    logger.warning(f"🚫 No smart hedge combination found for furthest positions")
                    return ClosingDecision(
                        should_close=False,
                        positions_to_close=[],
                        method="NO_SMART_HEDGE",
                        net_pnl=total_profit,
                        expected_pnl=total_profit,
                        position_count=len(furthest_positions),
                        buy_count=buy_count,
                        sell_count=sell_count,
                        confidence_score=0.0,
                        reason="ไม้ไกลติดลบและไม่มีไม้จับคู่ที่ฉลาด"
                    )
            
            # ไม้ไกลมีกำไร - ปิดได้เลย
            logger.info(f"✅ Furthest positions are profitable (${total_profit:.2f}) - Closing immediately")
            
            return ClosingDecision(
                should_close=True,
                positions_to_close=furthest_positions,
                method="FURTHEST_POSITIONS_PROFITABLE",
                net_pnl=total_profit,
                expected_pnl=total_profit,
                position_count=len(furthest_positions),
                buy_count=buy_count,
                sell_count=sell_count,
                confidence_score=95.0,
                reason=f"ปิดไม้ไกลกำไร: {len(furthest_positions)} ตัว (${total_profit:.2f})"
            )
            
        except Exception as e:
            logger.error(f"❌ Error closing furthest positions: {e}")
            return ClosingDecision(
                should_close=False,
                positions_to_close=[],
                method="ERROR",
                net_pnl=0.0,
                expected_pnl=0.0,
                position_count=0,
                buy_count=0,
                sell_count=0,
                confidence_score=0.0,
                reason=f"เกิดข้อผิดพลาด: {e}"
            )
    
    def _find_smart_hedge_combination(self, target_positions: List[Any], all_statuses: List[PositionStatus]) -> Optional[ClosingDecision]:
        """🧠 หาการจับคู่ไม้ที่ฉลาดที่สุด - เน้นกำไรรวมเป็นบวก"""
        try:
            # แยกไม้ตามประเภท
            target_buy = [pos for pos in target_positions if getattr(pos, 'type', 0) == 0]
            target_sell = [pos for pos in target_positions if getattr(pos, 'type', 0) == 1]
            
            # หาไม้ช่วยที่กำไร
            profitable_helpers = [s for s in all_statuses if s.status == "WINNER" and s.profit > 0]
            
            if not profitable_helpers:
                logger.warning("🚫 No profitable helpers available")
                return None
            
            best_combination = None
            best_profit = -999999.0
            
            # วิธีที่ 1: จับคู่ไม้ตรงข้ามกัน (BUY + SELL)
            if target_buy and target_sell:
                for buy_pos in target_buy:
                    for sell_pos in target_sell:
                        combined_profit = getattr(buy_pos, 'profit', 0) + getattr(sell_pos, 'profit', 0)
                        if combined_profit > best_profit:
                            best_profit = combined_profit
                            best_combination = {
                                'positions': [buy_pos, sell_pos],
                                'total_profit': combined_profit,
                                'method': 'OPPOSITE_PAIRING',
                                'reason': f"จับคู่ตรงข้าม: BUY {getattr(buy_pos, 'ticket', 'N/A')} + SELL {getattr(sell_pos, 'ticket', 'N/A')}"
                            }
            
            # วิธีที่ 2: ใช้ไม้ช่วยมาช่วยไม้ติดลบ
            for target_pos in target_positions:
                target_profit = getattr(target_pos, 'profit', 0)
                target_type = getattr(target_pos, 'type', 0)
                
                # หาไม้ช่วยที่ตรงข้ามกัน
                opposite_helpers = [h for h in profitable_helpers if h.position.type != target_type]
                
                for helper in opposite_helpers:
                    combined_profit = target_profit + helper.profit
                    if combined_profit > best_profit:
                        best_profit = combined_profit
                        best_combination = {
                            'positions': [target_pos, helper.position],
                            'total_profit': combined_profit,
                            'method': 'HELPER_PAIRING',
                            'reason': f"ไม้ช่วย: {getattr(target_pos, 'ticket', 'N/A')} + Helper {getattr(helper.position, 'ticket', 'N/A')}"
                        }
            
            # วิธีที่ 3: ใช้ไม้ช่วยหลายตัวมาช่วยไม้ติดลบ
            if len(profitable_helpers) >= 2:
                for target_pos in target_positions:
                    target_profit = getattr(target_pos, 'profit', 0)
                    target_type = getattr(target_pos, 'type', 0)
                    
                    # หาไม้ช่วยที่ตรงข้ามกัน
                    opposite_helpers = [h for h in profitable_helpers if h.position.type != target_type]
                    
                    # ลองใช้ไม้ช่วย 2-3 ตัว
                    for num_helpers in range(2, min(4, len(opposite_helpers) + 1)):
                        for helpers in itertools.combinations(opposite_helpers, num_helpers):
                            helpers_profit = sum(h.profit for h in helpers)
                            combined_profit = target_profit + helpers_profit
                            
                            if combined_profit > best_profit:
                                best_profit = combined_profit
                                best_combination = {
                                    'positions': [target_pos] + [h.position for h in helpers],
                                    'total_profit': combined_profit,
                                    'method': 'MULTI_HELPER_PAIRING',
                                    'reason': f"ไม้ช่วยหลายตัว: {getattr(target_pos, 'ticket', 'N/A')} + {num_helpers} helpers"
                                }
            
            # ตรวจสอบว่าพบการจับคู่ที่ดีหรือไม่
            if best_combination and best_profit > 0:
                positions_to_close = best_combination['positions']
                buy_count = len([p for p in positions_to_close if getattr(p, 'type', 0) == 0])
                sell_count = len([p for p in positions_to_close if getattr(p, 'type', 0) == 1])
                
                return ClosingDecision(
                    should_close=True,
                    positions_to_close=positions_to_close,
                    method=best_combination['method'],
                    net_pnl=best_profit,
                    expected_pnl=best_profit,
                    position_count=len(positions_to_close),
                    buy_count=buy_count,
                    sell_count=sell_count,
                    confidence_score=90.0,
                    reason=best_combination['reason']
                )
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error finding smart hedge combination: {e}")
            return None
    
    def _find_available_helpers(self, target_positions: List[Any], all_statuses: List[PositionStatus]) -> List[Any]:
        """🔍 หาไม้ช่วยที่ไม่ได้อยู่ในกลุ่มเป้าหมาย"""
        try:
            # หา tickets ของไม้เป้าหมาย
            target_tickets = set()
            for pos in target_positions:
                ticket = getattr(pos, 'ticket', 0)
                if ticket:
                    target_tickets.add(ticket)
            
            # หาไม้ช่วยจากสถานะทั้งหมด
            available_helpers = []
            for status in all_statuses:
                try:
                    pos = status.position
                    ticket = getattr(pos, 'ticket', 0)
                    
                    # ไม้ช่วยต้องไม่ใช่ไม้เป้าหมาย และต้องกำไร
                    if ticket not in target_tickets and status.profit > 0:
                        available_helpers.append(pos)
                except Exception as e:
                    logger.warning(f"⚠️ Error processing helper position: {e}")
                    continue
            
            # เรียงตามกำไร (มากก่อน)
            available_helpers.sort(key=lambda x: getattr(x, 'profit', 0), reverse=True)
            
            logger.info(f"🔍 Available Helpers: {len(available_helpers)} positions")
            for i, helper in enumerate(available_helpers[:5]):  # แสดง 5 ตัวแรก
                profit = getattr(helper, 'profit', 0)
                ticket = getattr(helper, 'ticket', 0)
                logger.info(f"   {i+1}. Ticket {ticket}: Profit ${profit:.2f}")
            
            return available_helpers
            
        except Exception as e:
            logger.error(f"❌ Error finding available helpers: {e}")
            return []

    def _close_recovery_needed_positions(self, urgent_positions: List[PositionStatus], all_statuses: List[PositionStatus]) -> ClosingDecision:
        """🚨 ปิดไม้ที่ต้องการ Recovery - ใช้ Smart Hedge Pairing"""
        try:
            # ใช้ Smart Hedge Pairing แทนการจับคู่แบบเก่า
            target_positions = [pos.position for pos in urgent_positions]
            best_combination = self._find_smart_hedge_combination(target_positions, all_statuses)
            
            if best_combination:
                logger.info(f"✅ RECOVERY SMART HEDGE SUCCESS: {best_combination['reason']} = ${best_combination['total_profit']:.2f}")
                return best_combination
            else:
                logger.warning(f"🚫 No smart recovery combination found")
                return ClosingDecision(
                    should_close=False,
                    positions_to_close=[],
                    method="NO_SMART_RECOVERY",
                    net_pnl=0.0,
                    expected_pnl=0.0,
                    position_count=0,
                    buy_count=0,
                    sell_count=0,
                    confidence_score=0.0,
                    reason="ไม้ Recovery ติดลบและไม่มีไม้จับคู่ที่ฉลาด"
                )
            
        except Exception as e:
            logger.error(f"❌ Error closing recovery needed positions: {e}")
            return ClosingDecision(
                should_close=False,
                positions_to_close=[],
                method="ERROR",
                net_pnl=0.0,
                expected_pnl=0.0,
                position_count=0,
                buy_count=0,
                sell_count=0,
                confidence_score=0.0,
                reason=f"เกิดข้อผิดพลาด: {e}"
            )
    
    def _find_hedge_pairs(self, hedge_candidates: List[PositionStatus], all_statuses: List[PositionStatus]) -> ClosingDecision:
        """🔄 หาไม้ที่สามารถปิดคู่กันได้ - ใช้ Smart Hedge Pairing"""
        try:
            # ใช้ Smart Hedge Pairing แทนการจับคู่แบบเก่า
            target_positions = [pos.position for pos in hedge_candidates]
            best_combination = self._find_smart_hedge_combination(target_positions, all_statuses)
            
            if best_combination:
                logger.info(f"✅ HEDGE SMART PAIRING SUCCESS: {best_combination['reason']} = ${best_combination['total_profit']:.2f}")
                return best_combination
            else:
                logger.warning(f"🚫 No smart hedge pairs found")
                return ClosingDecision(
                    should_close=False,
                    positions_to_close=[],
                    method="NO_SMART_HEDGE_PAIRS",
                    net_pnl=0.0,
                    expected_pnl=0.0,
                    position_count=0,
                    buy_count=0,
                    sell_count=0,
                    confidence_score=0.0,
                    reason="ไม่มีไม้จับคู่ที่ฉลาดสำหรับ Hedge"
                )
            
        except Exception as e:
            logger.error(f"❌ Error finding hedge pairs: {e}")
            return ClosingDecision(
                should_close=False,
                positions_to_close=[],
                method="ERROR",
                net_pnl=0.0,
                expected_pnl=0.0,
                position_count=0,
                buy_count=0,
                sell_count=0,
                confidence_score=0.0,
                reason=f"เกิดข้อผิดพลาด: {e}"
            )
    
    def _close_help_needed_positions(self, help_needed_positions: List[PositionStatus], all_statuses: List[PositionStatus]) -> ClosingDecision:
        """🆘 ปิดไม้ที่ต้องการความช่วยเหลือ - ใช้ Smart Hedge Pairing"""
        try:
            # ใช้ Smart Hedge Pairing แทนการจับคู่แบบเก่า
            target_positions = [pos.position for pos in help_needed_positions]
            best_combination = self._find_smart_hedge_combination(target_positions, all_statuses)
            
            if best_combination:
                logger.info(f"✅ HELP SMART HEDGE SUCCESS: {best_combination['reason']} = ${best_combination['total_profit']:.2f}")
                return best_combination
            else:
                logger.warning(f"🚫 No smart help combination found")
                return ClosingDecision(
                    should_close=False,
                    positions_to_close=[],
                    method="NO_SMART_HELP",
                    net_pnl=0.0,
                    expected_pnl=0.0,
                    position_count=0,
                    buy_count=0,
                    sell_count=0,
                    confidence_score=0.0,
                    reason="ไม้ Help ติดลบและไม่มีไม้จับคู่ที่ฉลาด"
                )
            
        except Exception as e:
            logger.error(f"❌ Error closing help needed positions: {e}")
            return ClosingDecision(
                should_close=False,
                positions_to_close=[],
                method="ERROR",
                net_pnl=0.0,
                expected_pnl=0.0,
                position_count=0,
                buy_count=0,
                sell_count=0,
                confidence_score=0.0,
                reason=f"เกิดข้อผิดพลาด: {e}"
            )
    
    def _close_smallest_losers(self, losers: List[PositionStatus]) -> ClosingDecision:
        """📉 ปิดไม้ที่ขาดทุนน้อยที่สุด"""
        try:
            # เรียงตามกำไร (ขาดทุนน้อยที่สุดก่อน)
            losers.sort(key=lambda x: x.profit, reverse=True)
            
            # ปิดไม้ที่ขาดทุนน้อยที่สุด 1-2 ตัว
            positions_to_close = losers[:2]  # ปิด 2 ตัวแรก
            
            total_profit = sum(pos.profit for pos in positions_to_close)
            
            # 🚫 ตรวจสอบว่าไม้ติดลบหรือไม่ - ถ้าติดลบให้ข้าม
            if total_profit < 0:
                logger.info(f"🚫 SMALLEST LOSERS: All positions are losing (${total_profit:.2f}) - Skipping")
                logger.info(f"   ZERO LOSS POLICY: Cannot close losing positions without helpers")
                return ClosingDecision(
                    should_close=False,
                    positions_to_close=[],
                    method="SKIP_LOSING_POSITIONS",
                    net_pnl=total_profit,
                    expected_pnl=total_profit,
                    position_count=len(positions_to_close),
                    buy_count=len([pos for pos in positions_to_close if getattr(pos.position, 'type', 0) == 0]),
                    sell_count=len([pos for pos in positions_to_close if getattr(pos.position, 'type', 0) == 1]),
                    confidence_score=0.0,
                    reason=f"Skip losing positions: {len(positions_to_close)} positions (${total_profit:.2f}) - Need helpers"
                )
            
            return ClosingDecision(
                should_close=True,
                positions_to_close=[pos.position for pos in positions_to_close],
                method="SMALLEST_LOSERS",
                net_pnl=total_profit,
                expected_pnl=total_profit,
                position_count=len(positions_to_close),
                buy_count=len([pos for pos in positions_to_close if getattr(pos.position, 'type', 0) == 0]),
                sell_count=len([pos for pos in positions_to_close if getattr(pos.position, 'type', 0) == 1]),
                confidence_score=0.7,
                reason=f"Close Smallest Losers: {len(positions_to_close)} positions (${total_profit:.2f})"
            )
            
        except Exception as e:
            logger.error(f"❌ Error closing smallest losers: {e}")
            return ClosingDecision(
                should_close=False,
                positions_to_close=[],
                method="ERROR",
                net_pnl=0.0,
                expected_pnl=0.0,
                position_count=0,
                buy_count=0,
                sell_count=0,
                confidence_score=0.0,
                reason=f"เกิดข้อผิดพลาด: {e}"
            )
    
    def _close_some_winners(self, winners: List[PositionStatus], portfolio_health: str) -> ClosingDecision:
        """💰 ปิดไม้กำไรบางตัวเมื่อจำเป็น"""
        try:
            # เรียงตามกำไร (กำไรมากที่สุดก่อน)
            winners.sort(key=lambda x: x.profit, reverse=True)
            
            # ปิดไม้กำไร 1-2 ตัว (เฉพาะเมื่อพอร์ตแย่)
            if portfolio_health == "แย่มาก":
                positions_to_close = winners[:2]  # ปิด 2 ตัว
            else:
                positions_to_close = winners[:1]  # ปิด 1 ตัว
            
            total_profit = sum(pos.profit for pos in positions_to_close)
            
            return ClosingDecision(
                should_close=True,
                positions_to_close=[pos.position for pos in positions_to_close],
                method="SOME_WINNERS",
                net_pnl=total_profit,
                expected_pnl=total_profit,
                position_count=len(positions_to_close),
                buy_count=len([pos for pos in positions_to_close if getattr(pos.position, 'type', 0) == 0]),
                sell_count=len([pos for pos in positions_to_close if getattr(pos.position, 'type', 0) == 1]),
                confidence_score=0.6,
                reason=f"Close Some Winners: {len(positions_to_close)} positions (${total_profit:.2f}) - Portfolio Health: {portfolio_health}"
            )
            
        except Exception as e:
            logger.error(f"❌ Error closing some winners: {e}")
            return ClosingDecision(
                should_close=False,
                positions_to_close=[],
                method="ERROR",
                net_pnl=0.0,
                expected_pnl=0.0,
                position_count=0,
                buy_count=0,
                sell_count=0,
                confidence_score=0.0,
                reason=f"เกิดข้อผิดพลาด: {e}"
            )
    
    def create_recovery_positions(self, positions: List[Any], current_price: float, zones: Dict = None) -> List[Dict]:
        """🚀 สร้างไม้ใหม่เพื่อช่วยไม้ที่ขาดทุน"""
        try:
            if not self.position_tracking_enabled or not positions:
                return []
            
            # วิเคราะห์สถานะไม้ทั้งหมด
            status_summary = self.get_position_status_summary(positions)
            
            if not status_summary:
                return []
            
            urgent_positions = status_summary.get('urgent_positions', [])
            help_needed_positions = status_summary.get('help_needed_positions', [])
            portfolio_health = status_summary.get('portfolio_health', 'ไม่ทราบ')
            
            recovery_positions = []
            
            # สร้างไม้ Recovery สำหรับไม้ที่ต้องการความช่วยเหลือ
            if urgent_positions or help_needed_positions:
                logger.info(f"🚀 Creating Recovery Positions - Portfolio Health: {portfolio_health}")
                logger.info(f"   Urgent Positions: {len(urgent_positions)}")
                logger.info(f"   Help Needed Positions: {len(help_needed_positions)}")
                
                # คำนวณขาดทุนรวมที่ต้องการ Recovery
                total_loss = sum(pos.profit for pos in urgent_positions + help_needed_positions)
                recovery_needed = abs(total_loss) * 1.5  # ต้องการกำไร 150% ของขาดทุน
                
                logger.info(f"   Total Loss: ${total_loss:.2f}")
                logger.info(f"   Recovery Needed: ${recovery_needed:.2f}")
                
                # สร้างไม้ BUY ที่ราคาต่ำเพื่อช่วยไม้ SELL ที่ขาดทุน
                if urgent_positions or help_needed_positions:
                    # หาไม้ SELL ที่ขาดทุน
                    sell_losers = [pos for pos in urgent_positions + help_needed_positions 
                                 if getattr(pos.position, 'type', 0) == 1]
                    
                    if sell_losers:
                        # สร้างไม้ BUY ที่ราคาต่ำกว่าไม้ SELL ที่ขาดทุน
                        for i, sell_loser in enumerate(sell_losers[:3]):  # สร้างสูงสุด 3 ตัว
                            sell_price = getattr(sell_loser.position, 'price_open', 0)
                            if sell_price > 0:
                                # สร้างไม้ BUY ที่ราคาต่ำกว่า 20-50 pips
                                recovery_price = sell_price - (20 + i * 10) * 0.1  # ลดลง 20, 30, 40 pips
                                recovery_volume = self._calculate_recovery_volume(recovery_needed, len(sell_losers))
                                
                                recovery_positions.append({
                                    'type': 'BUY',
                                    'price': recovery_price,
                                    'volume': recovery_volume,
                                    'purpose': 'RECOVERY',
                                    'target_loss': sell_loser.profit,
                                    'reason': f"Recovery for SELL {sell_loser.ticket} (${sell_loser.profit:.2f})"
                                })
                                
                                logger.info(f"   Recovery BUY: {recovery_price:.2f} (Volume: {recovery_volume})")
                
                # สร้างไม้ SELL ที่ราคาสูงเพื่อช่วยไม้ BUY ที่ขาดทุน
                buy_losers = [pos for pos in urgent_positions + help_needed_positions 
                             if getattr(pos.position, 'type', 0) == 0]
                
                if buy_losers:
                    # สร้างไม้ SELL ที่ราคาสูงกว่าไม้ BUY ที่ขาดทุน
                    for i, buy_loser in enumerate(buy_losers[:3]):  # สร้างสูงสุด 3 ตัว
                        buy_price = getattr(buy_loser.position, 'price_open', 0)
                        if buy_price > 0:
                            # สร้างไม้ SELL ที่ราคาสูงกว่า 20-50 pips
                            recovery_price = buy_price + (20 + i * 10) * 0.1  # เพิ่มขึ้น 20, 30, 40 pips
                            recovery_volume = self._calculate_recovery_volume(recovery_needed, len(buy_losers))
                            
                            recovery_positions.append({
                                'type': 'SELL',
                                'price': recovery_price,
                                'volume': recovery_volume,
                                'purpose': 'RECOVERY',
                                'target_loss': buy_loser.profit,
                                'reason': f"Recovery for BUY {buy_loser.ticket} (${buy_loser.profit:.2f})"
                            })
                            
                            logger.info(f"   Recovery SELL: {recovery_price:.2f} (Volume: {recovery_volume})")
            
            return recovery_positions
            
        except Exception as e:
            logger.error(f"❌ Error creating recovery positions: {e}")
            return []
    
    def _calculate_recovery_volume(self, recovery_needed: float, num_positions: int) -> float:
        """📊 คำนวณขนาดไม้สำหรับ Recovery"""
        try:
            # คำนวณขนาดไม้ตามขาดทุนที่ต้องการ Recovery
            base_volume = 0.01
            
            if recovery_needed > 200:
                base_volume = 0.05
            elif recovery_needed > 100:
                base_volume = 0.03
            elif recovery_needed > 50:
                base_volume = 0.02
            else:
                base_volume = 0.01
            
            # ปรับตามจำนวนไม้
            if num_positions > 3:
                base_volume *= 0.8  # ลดขนาดเมื่อมีไม้เยอะ
            elif num_positions == 1:
                base_volume *= 1.5  # เพิ่มขนาดเมื่อมีไม้เดียว
            
            # จำกัดขนาดไม้
            base_volume = max(0.01, min(0.1, base_volume))
            
            return base_volume
            
        except Exception as e:
            logger.error(f"❌ Error calculating recovery volume: {e}")
            return 0.01
    
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
            
            # 🧹 Analyze stale positions for potential inclusion of anchors (DISABLED)
            # stale_positions = self._identify_stale_positions(positions) if self.stale_clearing_enabled else []
            # allow_anchor_inclusion = self._should_include_anchors_for_stale_clearing(stale_positions, positions)
            stale_positions = []
            allow_anchor_inclusion = False
            
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
            
            # 🚫 DISABLED: ตรวจสอบการปิดไม้ทั้งหมดเมื่อพอร์ตเป็นบวก - ใช้ Hedge Pairing แทน
            # if self._check_close_all_profitable(positions, account_balance):
            #     logger.info("💰 CLOSE ALL POSITIONS - PORTFOLIO PROFITABLE")
            #     logger.info(f"🎯 Total Profit: ${total_profit:.2f} | Positions: {len(positions)}")
            #     return self._create_close_all_decision(positions, total_profit)
            
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
            
            
            # 🎯 Multi-Helper System - ระบบหลักสำหรับการจับคู่และไม้ช่วย
            # ระบบอื่นๆ ถูกลบออกเพื่อไม่รบกวน Multi-Helper System
            
            # 1. ตรวจสอบว่ามีไม้ทั้งสองฝั่งหรือไม่ (บังคับ Hedge Pairing)
            buy_positions = [pos for pos in filtered_positions if getattr(pos, 'type', 0) == 0]
            sell_positions = [pos for pos in filtered_positions if getattr(pos, 'type', 0) == 1]
            
            # อนุญาตให้ปิดไม้ฝั่งเดียวได้เฉพาะเมื่อมีไม้ฝั่งเดียวเท่านั้น
            if self.force_hedge_pairing_only and len(buy_positions) > 0 and len(sell_positions) > 0:
                # มีไม้ทั้งสองฝั่ง - ต้องใช้ Hedge Pairing เท่านั้น
                logger.info(f"🎯 HEDGE PAIRING REQUIRED: Both BUY and SELL positions exist")
                logger.info(f"   BUY positions: {len(buy_positions)}, SELL positions: {len(sell_positions)}")
            elif self.force_hedge_pairing_only and len(buy_positions) == 0 and len(sell_positions) == 0:
                # ไม่มีไม้เลย
                logger.info(f"🚫 NO POSITIONS: No positions to close")
                return None
            else:
                # มีไม้ฝั่งเดียว - อนุญาตให้ปิดได้
                if len(buy_positions) > 0:
                    logger.info(f"✅ SINGLE SIDE CLOSING: Only BUY positions ({len(buy_positions)}) - Allowed")
                elif len(sell_positions) > 0:
                    logger.info(f"✅ SINGLE SIDE CLOSING: Only SELL positions ({len(sell_positions)}) - Allowed")
            
            # 🧠 ใช้ระบบ Intelligent Closing Strategy แทนระบบเดิม
            logger.info(f"🧠 Using Intelligent Closing Strategy with {len(filtered_positions)} positions")
            intelligent_decision = self.intelligent_closing_strategy(filtered_positions)
            
            if intelligent_decision and intelligent_decision.should_close:
                # มีการตัดสินใจปิดไม้จากระบบ Intelligent
                logger.info(f"✅ INTELLIGENT CLOSING DECISION: {intelligent_decision.method}")
                logger.info(f"   Reason: {intelligent_decision.reason}")
                logger.info(f"   Net P&L: ${intelligent_decision.net_pnl:.2f}")
                logger.info(f"   Positions: {intelligent_decision.position_count}")
                logger.info(f"   Confidence: {intelligent_decision.confidence_score:.2f}")
                
                # บันทึกประสิทธิภาพ
                processing_time = time.time() - start_time
                self._record_performance(True, intelligent_decision.net_pnl, processing_time)
                
                return intelligent_decision
            
            # ถ้าระบบ Intelligent ไม่ตัดสินใจปิด ให้ลองใช้ระบบเดิมเป็น fallback
            logger.info(f"🔍 Intelligent system no action - trying legacy system with {len(filtered_positions)} positions")
            profitable_combinations = self._find_profitable_combinations(filtered_positions)
            
            # 1.5. ถ้าไม่มี Hedge Pairing และมีไม้ฝั่งเดียว ให้หาการปิดไม้ฝั่งเดียว
            if not profitable_combinations and (len(buy_positions) == 0 or len(sell_positions) == 0):
                logger.info(f"🔍 No hedge combinations found - checking single side closing")
                single_side_combinations = self._find_single_side_profitable(filtered_positions)
                if single_side_combinations:
                    profitable_combinations = single_side_combinations
            
            if profitable_combinations:
                # มีการจับคู่ที่เหมาะสม → ปิดไม้
                best_combination = profitable_combinations[0]
                
                # ตรวจสอบว่าเป็น Hedge Pairing หรือ Single Side
                if len(buy_positions) > 0 and len(sell_positions) > 0:
                    method_name = "LEGACY_HEDGE_PAIRING"
                    logger.info(f"✅ LEGACY HEDGE COMBINATION FOUND: {best_combination.combination_type}")
                else:
                    method_name = "LEGACY_SINGLE_SIDE_CLOSING"
                    logger.info(f"✅ LEGACY SINGLE SIDE COMBINATION FOUND: {best_combination.combination_type}")
                
                logger.info(f"   Net P&L: ${best_combination.total_profit:.2f}")
                logger.info(f"   Positions: {best_combination.size}")
                
                # บันทึกประสิทธิภาพ
                processing_time = time.time() - start_time
                self._record_performance(True, best_combination.total_profit, processing_time)
                
                return ClosingDecision(
                    should_close=True,
                    positions_to_close=best_combination.positions,
                    method=method_name,
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
            
            # ลองเพิ่มไม้กำไรที่ยังไม่ได้ใช้มาช่วยคู่ที่ติดลบ (ใช้หลายตัว)
            max_searches = min(100, len(hedged_losing_pairs) * len(profitable_unpaired))  # เพิ่มการค้นหาสูงสุด 100 ครั้ง
            search_count = 0
            
            logger.info(f"🔍 Enhanced Helping: {len(hedged_losing_pairs)} losing pairs, {len(profitable_unpaired)} helpers available")
            
            for losing_pair in hedged_losing_pairs:
                if search_count >= max_searches:
                    break
                    
                # ลองไม้ช่วยหลายตัว (1-5 ตัว)
                max_helpers = min(5, len(profitable_unpaired))
                best_combination = None
                best_profit = losing_pair['profit']
                
                for helper_count in range(1, max_helpers + 1):
                    for helper_combo in itertools.combinations(profitable_unpaired, helper_count):
                        if search_count >= max_searches:
                            break
                            
                        search_count += 1
                        helper_profit = sum(getattr(helper, 'profit', 0) for helper in helper_combo)
                        total_profit = losing_pair['profit'] + helper_profit
                        
                        if total_profit >= self.min_net_profit and total_profit > best_profit:
                            best_combination = [losing_pair['buy'], losing_pair['sell']] + list(helper_combo)
                            best_profit = total_profit
                            
                            logger.info(f"   💡 Found multi-helper combination: {len(helper_combo)} helpers, total profit: ${total_profit:.2f}")
                            
                            # หยุดเมื่อพบ combination ที่ดีพอ
                            if total_profit >= self.min_net_profit * 1.5:
                                break
                    
                    if search_count >= max_searches:
                        break
                
                if best_combination:
                        combinations.append(HedgeCombination(
                        positions=best_combination,
                        total_profit=best_profit,
                        combination_type="HELPING_HEDGED_MULTIPLE",
                        size=len(best_combination),
                        confidence_score=95.0,
                        reason=f"Multi-helper hedged pair: ${losing_pair['profit']:.2f} + {len(best_combination)-2} helpers = ${best_profit:.2f}"
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
            # ตรวจสอบว่ามีไม้ทั้งสองฝั่งหรือไม่
            buy_count = sum(1 for p in priority_positions if getattr(p, 'type', 0) == 0)
            sell_count = sum(1 for p in priority_positions if getattr(p, 'type', 0) == 1)
            
            if buy_count > 0 and sell_count > 0:
                # มีไม้ทั้งสองฝั่ง - ห้ามใช้ Single Side Closing
                logger.info("🚫 FORCE HEDGE PAIRING: Both BUY and SELL exist - Single side closing disabled")
                logger.info(f"   BUY positions: {buy_count}, SELL positions: {sell_count}")
            else:
                # มีไม้ฝั่งเดียว - อนุญาตให้ใช้ Single Side Closing
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
            
            # Step 1: จับคู่ตรงข้ามก่อนเสมอ (บังคับ Hedge Pairing)
            hedge_pairs = []
            used_positions = set()  # ติดตามไม้ที่ใช้แล้ว
            
            # บังคับจับคู่ BUY + SELL โดยไม่สนใจกำไร/ขาดทุน
            logger.info("🎯 FORCE HEDGE PAIRING: Matching BUY + SELL regardless of profit/loss")
            
            # จับคู่ BUY กับ SELL ทุกคู่ที่เป็นไปได้
            for buy_pos in buy_positions:
                buy_ticket = getattr(buy_pos, 'ticket', 'N/A')
                if buy_ticket in used_positions:
                    continue
                
                for sell_pos in sell_positions:
                    sell_ticket = getattr(sell_pos, 'ticket', 'N/A')
                    if sell_ticket in used_positions:
                        continue
                    
                    # จับคู่ไม้ที่ยังไม่ได้ใช้ (ไม่สนใจกำไร/ขาดทุน)
                    hedge_pairs.append({
                        'buy': buy_pos,
                        'sell': sell_pos,
                        'type': 'FORCE_HEDGE_PAIRING'
                    })
                    used_positions.add(buy_ticket)
                    used_positions.add(sell_ticket)
                    break  # หยุดเมื่อจับคู่แล้ว
            
            # แสดงสรุปการจับคู่ (เร็วขึ้น)
            logger.info("-" * 40)
            logger.info("📊 HEDGE PAIRING SUMMARY")
            logger.info("-" * 40)
            logger.info(f"✅ Hedge pairs found: {len(hedge_pairs)}")
            logger.info(f"📋 Used positions: {len(used_positions)}")
            logger.info(f"📋 Unused positions: {len(positions) - len(used_positions)}")
            
            # Step 2: สร้าง HedgeCombination สำหรับทุกคู่ (บังคับ Hedge Pairing)
            for hedge_pair in hedge_pairs:
                hedge_profit = getattr(hedge_pair['buy'], 'profit', 0) + getattr(hedge_pair['sell'], 'profit', 0)
                
                # สร้าง HedgeCombination ทุกคู่ (ไม่สนใจกำไร/ขาดทุน)
                hedge_combinations.append(HedgeCombination(
                    positions=[hedge_pair['buy'], hedge_pair['sell']],
                    total_profit=hedge_profit,
                    combination_type="FORCE_HEDGE_PAIRING",
                    size=2,
                    confidence_score=100.0,  # ให้คะแนนสูงสุดสำหรับ Hedge Pairing
                    reason=f"Force Hedge Pairing: BUY {getattr(hedge_pair['buy'], 'ticket', 'N/A')} + SELL {getattr(hedge_pair['sell'], 'ticket', 'N/A')}"
                ))
                
                # ถ้า hedge pair ติดลบ ให้หาไม้อื่นๆ มาช่วย (หลายตัว)
                if hedge_profit < 0:
                    # หาไม้ช่วยสำหรับคู่ที่ติดลบ (ใช้หลายตัว)
                    additional_positions = [pos for pos in positions 
                                          if getattr(pos, 'ticket', 'N/A') not in used_positions 
                                          and getattr(pos, 'profit', 0) > 0]
                    
                    logger.info(f"🔍 Looking for helping positions for losing hedge pair (${hedge_profit:.2f})")
                    logger.info(f"   Available helpers: {len(additional_positions)} profitable positions")
                    
                    # ลองเพิ่มไม้หลายตัวจนกว่าจะได้กำไร (เพิ่มจำนวนการทดสอบ)
                    best_combination = None
                    best_profit = hedge_profit
                    
                    # เพิ่มจำนวนการทดสอบ - ใช้ไม้ช่วยได้หลายตัว (ไม่จำกัดจำนวน)
                    max_attempts = min(len(additional_positions), 10)  # เพิ่มจาก 5 เป็น 10 (ไม่จำกัดจำนวน)
                    
                    for i in range(1, min(len(additional_positions) + 1, max_attempts + 1)):
                        for combo in itertools.combinations(additional_positions, i):
                            test_positions = [hedge_pair['buy'], hedge_pair['sell']] + list(combo)
                            test_profit = sum(getattr(pos, 'profit', 0) for pos in test_positions)
                            
                            effective_min_profit = self._get_effective_min_net_profit()
                            if test_profit > best_profit and test_profit >= effective_min_profit:
                                best_combination = test_positions
                                best_profit = test_profit
                                
                                logger.info(f"   💡 Found helping combination: {len(combo)} helpers, total profit: ${test_profit:.2f}")
                                logger.info(f"   🎯 Multi-Helper Success: Hedge pair + {len(combo)} helpers = ${test_profit:.2f}")
                                
                                # Early break - หยุดเมื่อพบ combination ที่ดีพอ
                                if test_profit >= effective_min_profit * 1.2:  # ลดจาก 1.5 เป็น 1.2 เพื่อให้หาผลลัพธ์ได้ง่ายขึ้น
                                    break
                        
                        # Early break - หยุดเมื่อพบ combination ที่ดีพอ
                        if best_combination and best_profit >= effective_min_profit * 1.2:  # ลดจาก 1.5 เป็น 1.2
                            break
                    
                    if best_combination:
                        hedge_combinations.append(HedgeCombination(
                            positions=best_combination,
                            total_profit=best_profit,
                            combination_type=f"HEDGE_WITH_MULTIPLE_HELPERS",
                            size=len(best_combination),
                            confidence_score=95.0,
                            reason=f"Hedge pair with {len(best_combination)-2} helping positions (${hedge_profit:.2f} → ${best_profit:.2f})"
                        ))
                        logger.info(f"✅ Complete hedge combination found: ${best_profit:.2f} with {len(best_combination)-2} helpers")
                    else:
                        # ไม่พบการรวมที่กำไร - รอไม้มาช่วยต่อไป
                        logger.info(f"⏳ No helping positions found for losing hedge pair (${hedge_profit:.2f}) - waiting...")
                        # ไม่เพิ่มเข้า hedge_combinations เพื่อรอไม้มาช่วย
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
            
            # เรียงตามความสำคัญ: Hedge Pairing ก่อน แล้วค่อยเรียงตามกำไร
            hedge_combinations.sort(key=lambda x: (
                x.combination_type != "FORCE_HEDGE_PAIRING",  # Hedge Pairing ก่อน
                -x.total_profit  # กำไรมากก่อน
            ))
            
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
        """🔍 หาไม้ฝั่งเดียวที่ P&L รวมเป็นบวก (เฉพาะเมื่อมีไม้ฝั่งเดียวเท่านั้น)"""
        try:
            # ตรวจสอบว่ามีไม้ฝั่งตรงข้ามหรือไม่
            buy_positions = [pos for pos in positions if getattr(pos, 'type', 0) == 0]
            sell_positions = [pos for pos in positions if getattr(pos, 'type', 0) == 1]
            
            # ถ้ามีไม้ฝั่งตรงข้ามทั้งสองฝั่ง ให้ข้ามฟังก์ชันนี้ (ใช้ Hedge Pairing แทน)
            if len(buy_positions) > 0 and len(sell_positions) > 0:
                logger.info("⚠️ Both BUY and SELL positions exist - using Hedge Pairing instead")
                return []
            
            # ตรวจสอบว่ามีไม้ฝั่งเดียวหรือไม่
            if len(buy_positions) == 0 and len(sell_positions) == 0:
                logger.info("⚠️ No positions found for single side closing")
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
    
    

    # ✅ Multi-Helper System - ระบบหลักสำหรับการจับคู่และไม้ช่วย
    # ระบบอื่นๆ (Advanced Pairing, Enhanced Helping, Stale Clearing) ถูกลบออกเพื่อไม่รบกวน Multi-Helper System


def create_hedge_pairing_closer(symbol: str = "EURUSD") -> HedgePairingCloser:
    """สร้าง HedgePairingCloser instance"""
    try:
        return HedgePairingCloser(symbol=symbol)
    except Exception as e:
        logger.error(f"❌ Failed to create HedgePairingCloser: {e}")
        raise
