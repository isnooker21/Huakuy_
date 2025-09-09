"""
🎯 Smart Entry Timing System
ระบบเข้าไม้อัจฉริยะที่ป้องกัน BUY สูง SELL ต่ำ

Features:
- Price Hierarchy Enforcement (BUY < SELL เสมอ)
- Entry Quality Analysis
- Strategic Entry Timing
- Support/Resistance Detection
- Market Structure Analysis
- Perfect Entry Point Detection
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)

class EntryQuality(Enum):
    """คุณภาพจุดเข้า"""
    EXCELLENT = "EXCELLENT"  # เข้าได้เลย - จุดดีมาก
    GOOD = "GOOD"           # เข้าได้ - จุดดี
    AVERAGE = "AVERAGE"     # เข้าได้ - จุดปกติ
    POOR = "POOR"          # รอดีกว่า - จุดแย่
    TERRIBLE = "TERRIBLE"   # ห้ามเข้า - จุดแย่มาก

class EntryTiming(Enum):
    """การจัดการเวลาเข้า"""
    ENTER_NOW = "ENTER_NOW"           # เข้าทันที
    WAIT_PULLBACK = "WAIT_PULLBACK"   # รอ pullback
    WAIT_BREAKOUT = "WAIT_BREAKOUT"   # รอ breakout
    SKIP_SIGNAL = "SKIP_SIGNAL"       # ข้ามสัญญาณนี้

@dataclass
class PriceLevel:
    """ระดับราคาสำคัญ"""
    price: float
    level_type: str  # "SUPPORT", "RESISTANCE", "PIVOT"
    strength: float  # 0.0-1.0
    touches: int     # จำนวนครั้งที่ราคาแตะ
    age_minutes: int # อายุของ level

@dataclass
class EntryAnalysis:
    """ผลการวิเคราะห์จุดเข้า"""
    quality: EntryQuality
    timing: EntryTiming
    score: float  # 0-100
    current_price: float
    suggested_price: float  # ราคาที่แนะนำให้เข้า
    wait_reason: str
    confidence: float
    price_hierarchy_ok: bool  # เป็นไปตาม BUY < SELL หรือไม่
    strategic_value: float    # คุณค่าเชิงกลยุทธ์

class SmartEntryTiming:
    """🎯 ระบบเข้าไม้อัจฉริยะ"""
    
    def __init__(self, mt5_connection=None, symbol: str = "XAUUSD"):
        self.mt5 = mt5_connection
        self.symbol = symbol
        
        # 📊 Market Structure Detection
        self.lookback_periods = 50  # จำนวน candle ที่ดูย้อนหลัง
        self.support_resistance_strength = 0.7  # ความแข็งแกร่งขั้นต่ำ
        
        # 🎯 Entry Quality Thresholds
        self.excellent_distance = 5.0   # ห่างจาก S/R น้อยกว่า 5 points = EXCELLENT
        self.good_distance = 10.0       # ห่างจาก S/R น้อยกว่า 10 points = GOOD
        self.poor_distance = 20.0       # ห่างจาก S/R มากกว่า 20 points = POOR
        
        # 🔄 Price Hierarchy Rules
        self.min_buy_sell_distance = 10.0  # BUY ต้องต่ำกว่า SELL อย่างน้อย 10 points
        self.hierarchy_buffer = 5.0        # buffer สำหรับ price hierarchy
        
        # 📈 Market Analysis
        self.price_history = []
        self.support_levels = []
        self.resistance_levels = []
        self.last_analysis_time = None
        
        logger.info("🎯 Smart Entry Timing System initialized")
    
    def analyze_entry_opportunity(self, signal_direction: str, current_price: float, 
                                 existing_positions: List[Any] = None) -> EntryAnalysis:
        """
        🔍 วิเคราะห์โอกาสการเข้าไม้
        
        Args:
            signal_direction: "BUY" หรือ "SELL"
            current_price: ราคาปัจจุบัน
            existing_positions: ตำแหน่งที่มีอยู่
            
        Returns:
            EntryAnalysis: ผลการวิเคราะห์
        """
        try:
            logger.info(f"🔍 Analyzing {signal_direction} entry at {current_price:.2f}")
            
            # 1. 📊 อัพเดท Market Structure
            self._update_market_structure(current_price)
            
            # 2. 🔄 เช็ค Price Hierarchy
            hierarchy_check = self._check_price_hierarchy(
                signal_direction, current_price, existing_positions
            )
            
            # 3. 🎯 วิเคราะห์ Entry Quality
            quality_analysis = self._analyze_entry_quality(signal_direction, current_price)
            
            # 4. ⏰ กำหนด Entry Timing
            timing_decision = self._determine_entry_timing(
                signal_direction, current_price, quality_analysis, hierarchy_check
            )
            
            # 5. 💎 คำนวณ Strategic Value
            strategic_value = self._calculate_strategic_value(
                signal_direction, current_price, existing_positions
            )
            
            # 6. 📋 สร้างผลลัพธ์
            analysis = EntryAnalysis(
                quality=quality_analysis['quality'],
                timing=timing_decision['timing'],
                score=quality_analysis['score'],
                current_price=current_price,
                suggested_price=timing_decision['suggested_price'],
                wait_reason=timing_decision['reason'],
                confidence=quality_analysis['confidence'],
                price_hierarchy_ok=hierarchy_check['ok'],
                strategic_value=strategic_value
            )
            
            logger.info(f"📊 Entry Analysis: {analysis.quality.value} - {analysis.timing.value}")
            logger.info(f"   Score: {analysis.score:.1f}, Confidence: {analysis.confidence:.1f}")
            logger.info(f"   Hierarchy OK: {analysis.price_hierarchy_ok}")
            
            return analysis
            
        except Exception as e:
            logger.error(f"❌ Error analyzing entry opportunity: {e}")
            return self._create_default_analysis(signal_direction, current_price)
    
    def _update_market_structure(self, current_price: float):
        """📊 อัพเดทโครงสร้างตลาด"""
        try:
            # เก็บประวัติราคา
            self.price_history.append({
                'price': current_price,
                'timestamp': datetime.now()
            })
            
            # เก็บแค่ข้อมูล 200 จุดล่าสุด
            if len(self.price_history) > 200:
                self.price_history = self.price_history[-200:]
            
            # อัพเดท S/R ทุก 5 นาที
            now = datetime.now()
            if (self.last_analysis_time is None or 
                (now - self.last_analysis_time).total_seconds() > 300):
                
                self._detect_support_resistance()
                self.last_analysis_time = now
                
        except Exception as e:
            logger.error(f"❌ Error updating market structure: {e}")
    
    def _detect_support_resistance(self):
        """🔍 ตรวจจับ Support/Resistance"""
        try:
            if len(self.price_history) < 20:
                return
            
            prices = [p['price'] for p in self.price_history[-50:]]  # ดู 50 จุดล่าสุด
            
            # หา Local Highs/Lows
            highs = []
            lows = []
            
            for i in range(2, len(prices) - 2):
                # Local High
                if (prices[i] > prices[i-1] and prices[i] > prices[i-2] and
                    prices[i] > prices[i+1] and prices[i] > prices[i+2]):
                    highs.append(prices[i])
                
                # Local Low
                if (prices[i] < prices[i-1] and prices[i] < prices[i-2] and
                    prices[i] < prices[i+1] and prices[i] < prices[i+2]):
                    lows.append(prices[i])
            
            # สร้าง Resistance Levels จาก Highs
            self.resistance_levels = []
            for high in highs:
                touches = sum(1 for p in prices if abs(p - high) <= 2.0)  # นับจุดที่ใกล้ ±2 points
                if touches >= 2:  # ต้องแตะอย่างน้อย 2 ครั้ง
                    strength = min(touches / 5.0, 1.0)  # ความแข็งแกร่ง
                    self.resistance_levels.append(PriceLevel(
                        price=high,
                        level_type="RESISTANCE",
                        strength=strength,
                        touches=touches,
                        age_minutes=5
                    ))
            
            # สร้าง Support Levels จาก Lows
            self.support_levels = []
            for low in lows:
                touches = sum(1 for p in prices if abs(p - low) <= 2.0)
                if touches >= 2:
                    strength = min(touches / 5.0, 1.0)
                    self.support_levels.append(PriceLevel(
                        price=low,
                        level_type="SUPPORT", 
                        strength=strength,
                        touches=touches,
                        age_minutes=5
                    ))
            
            # เรียงลำดับและเก็บแค่ระดับที่แข็งแกร่ง
            self.resistance_levels.sort(key=lambda x: x.strength, reverse=True)
            self.support_levels.sort(key=lambda x: x.strength, reverse=True)
            
            self.resistance_levels = self.resistance_levels[:3]  # เก็บแค่ 3 ระดับที่แข็งแกร่งที่สุด
            self.support_levels = self.support_levels[:3]
            
            logger.debug(f"📊 Updated S/R: {len(self.support_levels)} supports, {len(self.resistance_levels)} resistances")
            
        except Exception as e:
            logger.error(f"❌ Error detecting S/R: {e}")
    
    def _check_price_hierarchy(self, signal_direction: str, current_price: float, 
                              existing_positions: List[Any] = None) -> Dict[str, Any]:
        """
        🔄 เช็ค Price Hierarchy: BUY < SELL เสมอ
        """
        try:
            if not existing_positions:
                return {'ok': True, 'reason': 'No existing positions'}
            
            # แยกประเภท positions
            buy_positions = [p for p in existing_positions if getattr(p, 'type', 0) == 0]  # MT5 BUY = 0
            sell_positions = [p for p in existing_positions if getattr(p, 'type', 1) == 1]  # MT5 SELL = 1
            
            if signal_direction == "BUY":
                # BUY ใหม่ต้องต่ำกว่า SELL ที่มีอยู่ทั้งหมด
                if sell_positions:
                    min_sell_price = min(getattr(p, 'price_open', current_price) for p in sell_positions)
                    if current_price >= (min_sell_price - self.hierarchy_buffer):
                        return {
                            'ok': False,
                            'reason': f'BUY {current_price:.2f} too close to SELL {min_sell_price:.2f}',
                            'suggested_price': min_sell_price - self.min_buy_sell_distance,
                            'min_sell_price': min_sell_price
                        }
            
            elif signal_direction == "SELL":
                # SELL ใหม่ต้องสูงกว่า BUY ที่มีอยู่ทั้งหมด
                if buy_positions:
                    max_buy_price = max(getattr(p, 'price_open', current_price) for p in buy_positions)
                    if current_price <= (max_buy_price + self.hierarchy_buffer):
                        return {
                            'ok': False,
                            'reason': f'SELL {current_price:.2f} too close to BUY {max_buy_price:.2f}',
                            'suggested_price': max_buy_price + self.min_buy_sell_distance,
                            'max_buy_price': max_buy_price
                        }
            
            return {'ok': True, 'reason': 'Price hierarchy maintained'}
            
        except Exception as e:
            logger.error(f"❌ Error checking price hierarchy: {e}")
            return {'ok': True, 'reason': 'Error in hierarchy check'}
    
    def _analyze_entry_quality(self, signal_direction: str, current_price: float) -> Dict[str, Any]:
        """🎯 วิเคราะห์คุณภาพจุดเข้า"""
        try:
            # หาระดับ S/R ที่ใกล้ที่สุด
            nearest_support = None
            nearest_resistance = None
            
            if self.support_levels:
                nearest_support = min(self.support_levels, 
                                    key=lambda x: abs(x.price - current_price))
            
            if self.resistance_levels:
                nearest_resistance = min(self.resistance_levels,
                                       key=lambda x: abs(x.price - current_price))
            
            # คำนวณคะแนน
            score = 50.0  # เริ่มต้นที่ 50
            confidence = 0.5
            quality = EntryQuality.AVERAGE
            reasons = []
            
            if signal_direction == "BUY":
                # BUY ดีเมื่อใกล้ Support
                if nearest_support:
                    distance = abs(current_price - nearest_support.price)
                    support_strength = nearest_support.strength
                    
                    if distance <= self.excellent_distance and support_strength >= 0.8:
                        quality = EntryQuality.EXCELLENT
                        score = 90 + (support_strength * 10)
                        confidence = 0.9
                        reasons.append(f"Excellent BUY near strong support {nearest_support.price:.2f}")
                    
                    elif distance <= self.good_distance and support_strength >= 0.6:
                        quality = EntryQuality.GOOD
                        score = 70 + (support_strength * 15)
                        confidence = 0.7
                        reasons.append(f"Good BUY near support {nearest_support.price:.2f}")
                    
                    elif distance >= self.poor_distance:
                        quality = EntryQuality.POOR
                        score = 30 - (distance / 2)
                        confidence = 0.3
                        reasons.append(f"Poor BUY far from support (distance: {distance:.1f})")
                
                # BUY แย่เมื่อใกล้ Resistance
                if nearest_resistance:
                    distance = abs(current_price - nearest_resistance.price)
                    if distance <= self.good_distance:
                        quality = EntryQuality.POOR
                        score = max(score - 30, 10)
                        confidence = max(confidence - 0.3, 0.1)
                        reasons.append(f"BUY too close to resistance {nearest_resistance.price:.2f}")
            
            elif signal_direction == "SELL":
                # SELL ดีเมื่อใกล้ Resistance
                if nearest_resistance:
                    distance = abs(current_price - nearest_resistance.price)
                    resistance_strength = nearest_resistance.strength
                    
                    if distance <= self.excellent_distance and resistance_strength >= 0.8:
                        quality = EntryQuality.EXCELLENT
                        score = 90 + (resistance_strength * 10)
                        confidence = 0.9
                        reasons.append(f"Excellent SELL near strong resistance {nearest_resistance.price:.2f}")
                    
                    elif distance <= self.good_distance and resistance_strength >= 0.6:
                        quality = EntryQuality.GOOD
                        score = 70 + (resistance_strength * 15)
                        confidence = 0.7
                        reasons.append(f"Good SELL near resistance {nearest_resistance.price:.2f}")
                    
                    elif distance >= self.poor_distance:
                        quality = EntryQuality.POOR
                        score = 30 - (distance / 2)
                        confidence = 0.3
                        reasons.append(f"Poor SELL far from resistance (distance: {distance:.1f})")
                
                # SELL แย่เมื่อใกล้ Support
                if nearest_support:
                    distance = abs(current_price - nearest_support.price)
                    if distance <= self.good_distance:
                        quality = EntryQuality.POOR
                        score = max(score - 30, 10)
                        confidence = max(confidence - 0.3, 0.1)
                        reasons.append(f"SELL too close to support {nearest_support.price:.2f}")
            
            return {
                'quality': quality,
                'score': max(min(score, 100), 0),  # จำกัดระหว่าง 0-100
                'confidence': max(min(confidence, 1.0), 0.1),  # จำกัดระหว่าง 0.1-1.0
                'reasons': reasons,
                'nearest_support': nearest_support,
                'nearest_resistance': nearest_resistance
            }
            
        except Exception as e:
            logger.error(f"❌ Error analyzing entry quality: {e}")
            return {
                'quality': EntryQuality.AVERAGE,
                'score': 50.0,
                'confidence': 0.5,
                'reasons': ['Error in quality analysis'],
                'nearest_support': None,
                'nearest_resistance': None
            }
    
    def _determine_entry_timing(self, signal_direction: str, current_price: float,
                               quality_analysis: Dict, hierarchy_check: Dict) -> Dict[str, Any]:
        """⏰ กำหนดเวลาการเข้า"""
        try:
            # ถ้า Price Hierarchy ไม่ผ่าน
            if not hierarchy_check['ok']:
                return {
                    'timing': EntryTiming.SKIP_SIGNAL,
                    'suggested_price': hierarchy_check.get('suggested_price', current_price),
                    'reason': f"Price Hierarchy: {hierarchy_check['reason']}"
                }
            
            # ตัดสินใจตาม Entry Quality
            quality = quality_analysis['quality']
            
            if quality == EntryQuality.EXCELLENT:
                return {
                    'timing': EntryTiming.ENTER_NOW,
                    'suggested_price': current_price,
                    'reason': 'Excellent entry point - execute immediately'
                }
            
            elif quality == EntryQuality.GOOD:
                return {
                    'timing': EntryTiming.ENTER_NOW,
                    'suggested_price': current_price,
                    'reason': 'Good entry point - safe to execute'
                }
            
            elif quality == EntryQuality.AVERAGE:
                return {
                    'timing': EntryTiming.ENTER_NOW,
                    'suggested_price': current_price,
                    'reason': 'Average entry point - acceptable'
                }
            
            elif quality == EntryQuality.POOR:
                # หาราคาที่ดีกว่า
                better_price = self._suggest_better_price(signal_direction, current_price, quality_analysis)
                return {
                    'timing': EntryTiming.WAIT_PULLBACK,
                    'suggested_price': better_price,
                    'reason': f'Wait for better price: {better_price:.2f} (current: {current_price:.2f})'
                }
            
            else:  # TERRIBLE
                return {
                    'timing': EntryTiming.SKIP_SIGNAL,
                    'suggested_price': current_price,
                    'reason': 'Terrible entry point - skip this signal'
                }
            
        except Exception as e:
            logger.error(f"❌ Error determining entry timing: {e}")
            return {
                'timing': EntryTiming.ENTER_NOW,
                'suggested_price': current_price,
                'reason': 'Default timing due to error'
            }
    
    def _suggest_better_price(self, signal_direction: str, current_price: float, 
                             quality_analysis: Dict) -> float:
        """💡 แนะนำราคาที่ดีกว่า"""
        try:
            if signal_direction == "BUY":
                # BUY ควรใกล้ Support
                if quality_analysis['nearest_support']:
                    support_price = quality_analysis['nearest_support'].price
                    return support_price + 2.0  # เข้าใกล้ support แต่ไม่ติดขอบ
                else:
                    return current_price - 10.0  # รอราคาลง 10 points
            
            elif signal_direction == "SELL":
                # SELL ควรใกล้ Resistance
                if quality_analysis['nearest_resistance']:
                    resistance_price = quality_analysis['nearest_resistance'].price
                    return resistance_price - 2.0  # เข้าใกล้ resistance แต่ไม่ติดขอบ
                else:
                    return current_price + 10.0  # รอราคาขึ้น 10 points
            
            return current_price
            
        except Exception as e:
            logger.error(f"❌ Error suggesting better price: {e}")
            return current_price
    
    def _calculate_strategic_value(self, signal_direction: str, current_price: float, 
                                  existing_positions: List[Any] = None) -> float:
        """💎 คำนวณคุณค่าเชิงกลยุทธ์"""
        try:
            strategic_value = 50.0  # ค่าเริ่มต้น
            
            if not existing_positions:
                return strategic_value
            
            # วิเคราะห์ Portfolio Balance
            buy_positions = [p for p in existing_positions if getattr(p, 'type', 0) == 0]
            sell_positions = [p for p in existing_positions if getattr(p, 'type', 1) == 1]
            
            total_positions = len(existing_positions)
            buy_ratio = len(buy_positions) / total_positions if total_positions > 0 else 0.5
            sell_ratio = len(sell_positions) / total_positions if total_positions > 0 else 0.5
            
            # ถ้า Portfolio ไม่สมดุล → Strategic Value สูงขึ้นสำหรับการสมดุล
            if signal_direction == "BUY" and buy_ratio < 0.4:  # BUY น้อยเกินไป
                strategic_value += 30.0
            elif signal_direction == "SELL" and sell_ratio < 0.4:  # SELL น้อยเกินไป
                strategic_value += 30.0
            elif signal_direction == "BUY" and buy_ratio > 0.7:  # BUY เยอะเกินไป
                strategic_value -= 20.0
            elif signal_direction == "SELL" and sell_ratio > 0.7:  # SELL เยอะเกินไป
                strategic_value -= 20.0
            
            # วิเคราะห์ Position Quality ที่มีอยู่
            losing_positions = [p for p in existing_positions 
                               if getattr(p, 'profit', 0) < 0]
            
            if losing_positions:
                # ถ้ามีไม้ขาดทุน → Strategic Value สูงขึ้นสำหรับการช่วยเหลือ
                avg_loss = sum(getattr(p, 'profit', 0) for p in losing_positions) / len(losing_positions)
                if avg_loss < -50:  # ขาดทุนมาก
                    strategic_value += 20.0
            
            return max(min(strategic_value, 100.0), 0.0)
            
        except Exception as e:
            logger.error(f"❌ Error calculating strategic value: {e}")
            return 50.0
    
    def _create_default_analysis(self, signal_direction: str, current_price: float) -> EntryAnalysis:
        """📋 สร้างผลการวิเคราะห์เริ่มต้น (กรณี error)"""
        return EntryAnalysis(
            quality=EntryQuality.AVERAGE,
            timing=EntryTiming.ENTER_NOW,
            score=50.0,
            current_price=current_price,
            suggested_price=current_price,
            wait_reason="Default analysis due to error",
            confidence=0.5,
            price_hierarchy_ok=True,
            strategic_value=50.0
        )
    
    def get_market_structure_info(self) -> Dict[str, Any]:
        """📊 ดึงข้อมูลโครงสร้างตลาด"""
        try:
            return {
                'support_levels': [
                    {
                        'price': level.price,
                        'strength': level.strength,
                        'touches': level.touches
                    } for level in self.support_levels
                ],
                'resistance_levels': [
                    {
                        'price': level.price,
                        'strength': level.strength,
                        'touches': level.touches
                    } for level in self.resistance_levels
                ],
                'price_history_count': len(self.price_history),
                'last_analysis': self.last_analysis_time
            }
        except Exception as e:
            logger.error(f"❌ Error getting market structure info: {e}")
            return {}

# 🏭 Factory Function
def create_smart_entry_timing(mt5_connection=None, symbol: str = "XAUUSD") -> SmartEntryTiming:
    """🏭 สร้าง Smart Entry Timing System"""
    return SmartEntryTiming(mt5_connection, symbol)
