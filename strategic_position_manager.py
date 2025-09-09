"""
🛡️ Strategic Position Manager
ระบบจัดการไม้เชิงกลยุทธ์ - HOLD ไม้ดี ปิดไม้แย่เร็ว

Features:
- Strategic Hold System (HOLD ไม้ดีนานขึ้น)
- Capital Protection (กั้นหน้าทุน)
- Position Quality Classification
- Smart Exit Timing
- Portfolio Balance Optimization
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)

class PositionQuality(Enum):
    """คุณภาพของตำแหน่ง"""
    STRATEGIC_ASSET = "STRATEGIC_ASSET"    # ไม้ดีมาก - HOLD นาน
    GOOD_ENTRY = "GOOD_ENTRY"             # ไม้ดี - HOLD ปกติ
    AVERAGE_ENTRY = "AVERAGE_ENTRY"       # ไม้ปกติ - ตาม 7D
    POOR_ENTRY = "POOR_ENTRY"             # ไม้แย่ - หา exit เร็ว
    PROBLEM_POSITION = "PROBLEM_POSITION"  # ไม้ปัญหา - ต้องแก้ไข

class HoldStrategy(Enum):
    """กลยุทธ์การ Hold"""
    HOLD_STRATEGIC = "HOLD_STRATEGIC"      # Hold เชิงกลยุทธ์
    HOLD_RECOVERY = "HOLD_RECOVERY"        # Hold รอ recovery
    HOLD_BALANCE = "HOLD_BALANCE"          # Hold เพื่อ balance
    ALLOW_CLOSE = "ALLOW_CLOSE"            # อนุญาตให้ปิด
    FORCE_CLOSE = "FORCE_CLOSE"            # บังคับปิด

@dataclass
class PositionAnalysis:
    """ผลการวิเคราะห์ตำแหน่ง"""
    position: Any
    quality: PositionQuality
    hold_strategy: HoldStrategy
    strategic_value: float    # 0-100
    entry_quality_score: float
    current_performance: float
    expected_profit: float
    hold_duration_target: int  # นาที
    capital_protection_level: float
    should_override_close: bool
    reason: str

class StrategicPositionManager:
    """🛡️ ระบบจัดการตำแหน่งเชิงกลยุทธ์"""
    
    def __init__(self, smart_entry_timing=None):
        self.smart_entry_timing = smart_entry_timing
        
        # 🎯 Position Quality Thresholds
        self.strategic_asset_threshold = 85.0    # คะแนน entry > 85 = STRATEGIC_ASSET
        self.good_entry_threshold = 70.0         # คะแนน entry > 70 = GOOD_ENTRY
        self.poor_entry_threshold = 40.0         # คะแนน entry < 40 = POOR_ENTRY
        
        # ⏰ Hold Duration Targets (นาที)
        self.strategic_hold_duration = 240       # 4 ชั่วโมง
        self.good_hold_duration = 120           # 2 ชั่วโมง
        self.average_hold_duration = 60         # 1 ชั่วโมง
        self.poor_hold_duration = 30            # 30 นาที
        
        # 💰 Profit Expectations
        self.strategic_profit_target = 50.0      # เป้าหมายกำไร strategic positions
        self.good_profit_target = 30.0          # เป้าหมายกำไร good positions
        self.average_profit_target = 15.0       # เป้าหมายกำไร average positions
        
        # 🛡️ Capital Protection
        self.protection_levels = {
            PositionQuality.STRATEGIC_ASSET: 0.9,    # ป้องกัน 90%
            PositionQuality.GOOD_ENTRY: 0.7,         # ป้องกัน 70%
            PositionQuality.AVERAGE_ENTRY: 0.5,      # ป้องกัน 50%
            PositionQuality.POOR_ENTRY: 0.2,         # ป้องกัน 20%
            PositionQuality.PROBLEM_POSITION: 0.0    # ไม่ป้องกัน
        }
        
        # 📊 Performance Tracking
        self.position_entries = {}  # เก็บข้อมูลการเข้าของแต่ละ position
        
        logger.info("🛡️ Strategic Position Manager initialized")
    
    def record_position_entry(self, position: Any, entry_analysis: Any):
        """📝 บันทึกข้อมูลการเข้าของ position"""
        try:
            ticket = getattr(position, 'ticket', id(position))
            
            self.position_entries[ticket] = {
                'entry_time': datetime.now(),
                'entry_price': getattr(position, 'price_open', 0),
                'entry_quality': entry_analysis.quality if entry_analysis else PositionQuality.AVERAGE_ENTRY,
                'entry_score': entry_analysis.score if entry_analysis else 50.0,
                'strategic_value': entry_analysis.strategic_value if entry_analysis else 50.0,
                'expected_profit': self._calculate_expected_profit(position, entry_analysis)
            }
            
            logger.info(f"📝 Recorded entry for position {ticket}: "
                       f"{self.position_entries[ticket]['entry_quality'].value}")
            
        except Exception as e:
            logger.error(f"❌ Error recording position entry: {e}")
    
    def analyze_position_strategy(self, position: Any, current_price: float, 
                                 portfolio_context: Dict = None) -> PositionAnalysis:
        """
        🔍 วิเคราะห์กลยุทธ์สำหรับตำแหน่ง
        
        Args:
            position: ตำแหน่งที่จะวิเคราะห์
            current_price: ราคาปัจจุบัน
            portfolio_context: บริบทของ portfolio
            
        Returns:
            PositionAnalysis: ผลการวิเคราะห์
        """
        try:
            ticket = getattr(position, 'ticket', id(position))
            
            # 1. 📊 ดึงข้อมูลการเข้า
            entry_info = self.position_entries.get(ticket, {})
            entry_quality = entry_info.get('entry_quality', PositionQuality.AVERAGE_ENTRY)
            entry_score = entry_info.get('entry_score', 50.0)
            
            # 2. 📈 วิเคราะห์ Performance ปัจจุบัน
            current_performance = self._analyze_current_performance(position, current_price)
            
            # 3. 🎯 จำแนกคุณภาพตำแหน่ง
            position_quality = self._classify_position_quality(
                entry_score, current_performance, position
            )
            
            # 4. 🛡️ กำหนดกลยุทธ์การ Hold
            hold_strategy = self._determine_hold_strategy(
                position_quality, current_performance, entry_info, portfolio_context
            )
            
            # 5. 💎 คำนวณ Strategic Value
            strategic_value = self._calculate_strategic_value(
                position, entry_info, current_performance, portfolio_context
            )
            
            # 6. ⏰ คำนวณเป้าหมายการ Hold
            hold_duration_target = self._calculate_hold_duration(position_quality, entry_info)
            
            # 7. 🛡️ ระดับการป้องกันทุน
            protection_level = self.protection_levels.get(position_quality, 0.5)
            
            # 8. 🚫 ตัดสินใจ Override Close
            should_override = self._should_override_close(
                position_quality, hold_strategy, current_performance, entry_info
            )
            
            # 9. 📋 สร้างผลลัพธ์
            analysis = PositionAnalysis(
                position=position,
                quality=position_quality,
                hold_strategy=hold_strategy,
                strategic_value=strategic_value,
                entry_quality_score=entry_score,
                current_performance=current_performance,
                expected_profit=entry_info.get('expected_profit', 15.0),
                hold_duration_target=hold_duration_target,
                capital_protection_level=protection_level,
                should_override_close=should_override,
                reason=self._generate_strategy_reason(position_quality, hold_strategy, current_performance)
            )
            
            logger.debug(f"🔍 Position {ticket} Strategy: {position_quality.value} → {hold_strategy.value}")
            
            return analysis
            
        except Exception as e:
            logger.error(f"❌ Error analyzing position strategy: {e}")
            return self._create_default_analysis(position, current_price)
    
    def _calculate_expected_profit(self, position: Any, entry_analysis: Any) -> float:
        """💰 คำนวณเป้าหมายกำไรที่คาดหวัง"""
        try:
            if not entry_analysis:
                return self.average_profit_target
            
            # ตาม Entry Quality
            if entry_analysis.quality == entry_analysis.quality.EXCELLENT:
                return self.strategic_profit_target
            elif entry_analysis.quality == entry_analysis.quality.GOOD:
                return self.good_profit_target
            else:
                return self.average_profit_target
                
        except Exception as e:
            logger.error(f"❌ Error calculating expected profit: {e}")
            return self.average_profit_target
    
    def _analyze_current_performance(self, position: Any, current_price: float) -> float:
        """📈 วิเคราะห์ผลการดำเนินงานปัจจุบัน"""
        try:
            current_profit = getattr(position, 'profit', 0.0)
            entry_price = getattr(position, 'price_open', current_price)
            position_type = getattr(position, 'type', 0)
            
            # คำนวณ Points Profit/Loss
            if position_type == 0:  # BUY
                points_diff = current_price - entry_price
            else:  # SELL
                points_diff = entry_price - current_price
            
            # แปลงเป็น Performance Score (0-100)
            # +50 points = 100 score, -50 points = 0 score
            performance_score = 50 + (points_diff * 1.0)  # 1 point = 1 score
            
            return max(min(performance_score, 100.0), 0.0)
            
        except Exception as e:
            logger.error(f"❌ Error analyzing current performance: {e}")
            return 50.0
    
    def _classify_position_quality(self, entry_score: float, current_performance: float, 
                                  position: Any) -> PositionQuality:
        """🎯 จำแนกคุณภาพตำแหน่ง"""
        try:
            current_profit = getattr(position, 'profit', 0.0)
            
            # Strategic Asset: Entry ดีมาก และมีกำไรดี
            if (entry_score >= self.strategic_asset_threshold and 
                current_performance >= 60.0):
                return PositionQuality.STRATEGIC_ASSET
            
            # Good Entry: Entry ดี
            elif entry_score >= self.good_entry_threshold:
                return PositionQuality.GOOD_ENTRY
            
            # Problem Position: ขาดทุนมากและ entry แย่
            elif (entry_score <= self.poor_entry_threshold and 
                  current_profit < -100.0):
                return PositionQuality.PROBLEM_POSITION
            
            # Poor Entry: Entry แย่
            elif entry_score <= self.poor_entry_threshold:
                return PositionQuality.POOR_ENTRY
            
            # Average Entry: ปกติ
            else:
                return PositionQuality.AVERAGE_ENTRY
                
        except Exception as e:
            logger.error(f"❌ Error classifying position quality: {e}")
            return PositionQuality.AVERAGE_ENTRY
    
    def _determine_hold_strategy(self, quality: PositionQuality, performance: float,
                                entry_info: Dict, portfolio_context: Dict = None) -> HoldStrategy:
        """🛡️ กำหนดกลยุทธ์การ Hold"""
        try:
            # Strategic Asset: HOLD เชิงกลยุทธ์
            if quality == PositionQuality.STRATEGIC_ASSET:
                if performance >= 70.0:  # กำไรดีมาก
                    return HoldStrategy.HOLD_STRATEGIC
                else:
                    return HoldStrategy.HOLD_RECOVERY
            
            # Good Entry: HOLD ปกติ
            elif quality == PositionQuality.GOOD_ENTRY:
                if performance >= 60.0:  # กำไรดี
                    return HoldStrategy.HOLD_STRATEGIC
                elif performance >= 40.0:  # กำไรปกติ
                    return HoldStrategy.ALLOW_CLOSE
                else:  # รอ recovery
                    return HoldStrategy.HOLD_RECOVERY
            
            # Problem Position: บังคับปิด
            elif quality == PositionQuality.PROBLEM_POSITION:
                return HoldStrategy.FORCE_CLOSE
            
            # Poor Entry: หา exit เร็ว
            elif quality == PositionQuality.POOR_ENTRY:
                if performance <= 30.0:  # แย่มาก
                    return HoldStrategy.FORCE_CLOSE
                else:
                    return HoldStrategy.ALLOW_CLOSE
            
            # Average: ตาม 7D ปกติ
            else:
                return HoldStrategy.ALLOW_CLOSE
                
        except Exception as e:
            logger.error(f"❌ Error determining hold strategy: {e}")
            return HoldStrategy.ALLOW_CLOSE
    
    def _calculate_strategic_value(self, position: Any, entry_info: Dict, 
                                  performance: float, portfolio_context: Dict = None) -> float:
        """💎 คำนวณคุณค่าเชิงกลยุทธ์"""
        try:
            base_value = entry_info.get('strategic_value', 50.0)
            
            # เพิ่มค่าตาม Performance
            performance_bonus = (performance - 50.0) * 0.5  # Performance แต่ละ point = +0.5 value
            
            # เพิ่มค่าตามเวลาที่ Hold
            entry_time = entry_info.get('entry_time', datetime.now())
            hold_duration = (datetime.now() - entry_time).total_seconds() / 60  # นาที
            time_bonus = min(hold_duration / 60.0 * 10.0, 20.0)  # สูงสุด +20 จากเวลา
            
            # Portfolio Balance Bonus
            balance_bonus = 0.0
            if portfolio_context:
                # ถ้า Portfolio ไม่สมดุล → ตำแหน่งที่ช่วยสมดุลจะมีค่ามากขึ้น
                position_type = getattr(position, 'type', 0)
                buy_ratio = portfolio_context.get('buy_ratio', 0.5)
                
                if position_type == 0 and buy_ratio < 0.4:  # BUY น้อย
                    balance_bonus = 15.0
                elif position_type == 1 and buy_ratio > 0.6:  # SELL น้อย
                    balance_bonus = 15.0
            
            total_value = base_value + performance_bonus + time_bonus + balance_bonus
            
            return max(min(total_value, 100.0), 0.0)
            
        except Exception as e:
            logger.error(f"❌ Error calculating strategic value: {e}")
            return 50.0
    
    def _calculate_hold_duration(self, quality: PositionQuality, entry_info: Dict) -> int:
        """⏰ คำนวณเวลา Hold ที่เหมาะสม"""
        try:
            base_duration = {
                PositionQuality.STRATEGIC_ASSET: self.strategic_hold_duration,
                PositionQuality.GOOD_ENTRY: self.good_hold_duration,
                PositionQuality.AVERAGE_ENTRY: self.average_hold_duration,
                PositionQuality.POOR_ENTRY: self.poor_hold_duration,
                PositionQuality.PROBLEM_POSITION: 10  # ปิดเร็วที่สุด
            }.get(quality, self.average_hold_duration)
            
            return base_duration
            
        except Exception as e:
            logger.error(f"❌ Error calculating hold duration: {e}")
            return self.average_hold_duration
    
    def _should_override_close(self, quality: PositionQuality, strategy: HoldStrategy,
                              performance: float, entry_info: Dict) -> bool:
        """🚫 ตัดสินใจว่าควร Override การปิดหรือไม่"""
        try:
            # Strategic positions: Override ถ้ายังไม่ถึงเป้า
            if (quality == PositionQuality.STRATEGIC_ASSET and 
                strategy == HoldStrategy.HOLD_STRATEGIC):
                expected_profit = entry_info.get('expected_profit', 50.0)
                current_profit = performance - 50.0  # แปลงกลับเป็น points
                
                if current_profit < expected_profit * 0.7:  # ยังไม่ถึง 70% ของเป้า
                    return True
            
            # Good positions: Override ถ้ากำไรยังน้อย
            elif (quality == PositionQuality.GOOD_ENTRY and 
                  strategy == HoldStrategy.HOLD_STRATEGIC):
                if performance < 65.0:  # ยังไม่ถึงกำไรที่ดี
                    return True
            
            # Recovery positions: Override ถ้ายังขาดทุน
            elif strategy == HoldStrategy.HOLD_RECOVERY:
                if performance < 45.0:  # ยังขาดทุนอยู่
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Error determining override close: {e}")
            return False
    
    def _generate_strategy_reason(self, quality: PositionQuality, strategy: HoldStrategy, 
                                 performance: float) -> str:
        """📝 สร้างเหตุผลของกลยุทธ์"""
        try:
            perf_desc = "excellent" if performance >= 70 else "good" if performance >= 50 else "poor"
            
            if strategy == HoldStrategy.HOLD_STRATEGIC:
                return f"{quality.value.lower()} with {perf_desc} performance - strategic hold"
            elif strategy == HoldStrategy.HOLD_RECOVERY:
                return f"{quality.value.lower()} waiting for recovery"
            elif strategy == HoldStrategy.FORCE_CLOSE:
                return f"{quality.value.lower()} requires immediate exit"
            else:
                return f"{quality.value.lower()} - standard management"
                
        except Exception as e:
            logger.error(f"❌ Error generating strategy reason: {e}")
            return "Standard position management"
    
    def _create_default_analysis(self, position: Any, current_price: float) -> PositionAnalysis:
        """📋 สร้างการวิเคราะห์เริ่มต้น"""
        return PositionAnalysis(
            position=position,
            quality=PositionQuality.AVERAGE_ENTRY,
            hold_strategy=HoldStrategy.ALLOW_CLOSE,
            strategic_value=50.0,
            entry_quality_score=50.0,
            current_performance=50.0,
            expected_profit=15.0,
            hold_duration_target=60,
            capital_protection_level=0.5,
            should_override_close=False,
            reason="Default analysis due to error"
        )
    
    def get_portfolio_strategic_summary(self, positions: List[Any]) -> Dict[str, Any]:
        """📊 สรุปกลยุทธ์ Portfolio"""
        try:
            if not positions:
                return {}
            
            quality_counts = {}
            strategy_counts = {}
            total_strategic_value = 0.0
            override_count = 0
            
            for position in positions:
                analysis = self.analyze_position_strategy(position, 0.0)  # ใช้ current_price = 0 เป็น placeholder
                
                quality = analysis.quality.value
                strategy = analysis.hold_strategy.value
                
                quality_counts[quality] = quality_counts.get(quality, 0) + 1
                strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1
                total_strategic_value += analysis.strategic_value
                
                if analysis.should_override_close:
                    override_count += 1
            
            return {
                'total_positions': len(positions),
                'quality_distribution': quality_counts,
                'strategy_distribution': strategy_counts,
                'average_strategic_value': total_strategic_value / len(positions),
                'positions_with_override': override_count,
                'strategic_assets': quality_counts.get('STRATEGIC_ASSET', 0),
                'problem_positions': quality_counts.get('PROBLEM_POSITION', 0)
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting portfolio strategic summary: {e}")
            return {}

# 🏭 Factory Function
def create_strategic_position_manager(smart_entry_timing=None) -> StrategicPositionManager:
    """🏭 สร้าง Strategic Position Manager"""
    return StrategicPositionManager(smart_entry_timing)
