"""
🎯 Pure Price Action Analyzer - ไม่ใช้ Indicators
วิเคราะห์ Higher Highs/Lower Lows, Support/Resistance, Momentum จาก Raw Price Data
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import MetaTrader5 as mt5

logger = logging.getLogger(__name__)

@dataclass
class SwingPoint:
    """จุด Swing High/Low"""
    price: float
    timestamp: datetime
    type: str  # 'HIGH' or 'LOW'
    strength: int  # จำนวน candles ที่ confirm
    index: int  # position ใน data array

@dataclass
class SupportResistanceLevel:
    """ระดับ Support/Resistance"""
    price: float
    strength: float  # ความแข็งแรง (0-100)
    touch_count: int  # จำนวนครั้งที่ถูกแตะ
    last_touch: datetime
    type: str  # 'SUPPORT' or 'RESISTANCE'
    zone_range: Tuple[float, float]  # (min, max) ของ zone

@dataclass
class TrendAnalysis:
    """ผลการวิเคราะห์ Trend"""
    direction: str  # 'BULLISH', 'BEARISH', 'SIDEWAYS'
    strength: float  # ความแรง 0-100
    confidence: float  # ความมั่นใจ 0-100
    swing_structure: str  # 'HH_HL', 'LH_LL', 'CHOPPY'
    momentum: str  # 'STRONG', 'MODERATE', 'WEAK'
    last_swing_high: Optional[SwingPoint]
    last_swing_low: Optional[SwingPoint]

@dataclass
class PriceActionSignal:
    """สัญญาณจาก Price Action"""
    signal_type: str  # 'TREND_CONTINUATION', 'TREND_REVERSAL', 'BREAKOUT', 'PULLBACK'
    direction: str  # 'BUY', 'SELL', 'NEUTRAL'
    strength: float  # 0-100
    confidence: float  # 0-100
    entry_price: float
    reason: str
    invalidation_price: Optional[float]  # ราคาที่ signal invalid

class PriceActionAnalyzer:
    """🎯 Pure Price Action Analyzer - Real-time market structure analysis"""
    
    def __init__(self, symbol: str = "XAUUSD"):
        self.symbol = symbol
        self.swing_detection_period = 5  # จำนวน candles สำหรับ confirm swing
        self.min_swing_distance = 2.0   # ระยะห่างขั้นต่ำระหว่าง swing (pips)
        self.sr_zone_width = 1.0        # ความกว้าง S/R zone (pips)
        self.min_touch_count = 2         # จำนวนครั้งขั้นต่ำสำหรับ S/R
        
        # เก็บข้อมูล swing points
        self.swing_highs: List[SwingPoint] = []
        self.swing_lows: List[SwingPoint] = []
        self.sr_levels: List[SupportResistanceLevel] = []
        
        logger.info(f"🎯 Price Action Analyzer initialized for {symbol}")
        logger.info(f"   Swing Detection: {self.swing_detection_period} candles")
        logger.info(f"   Min Swing Distance: {self.min_swing_distance} pips")
    
    def analyze_market_structure(self, bars_count: int = 100) -> TrendAnalysis:
        """
        🔍 วิเคราะห์โครงสร้างตลาดจาก Raw Price Data
        
        Args:
            bars_count: จำนวน candles ที่ใช้วิเคราะห์
            
        Returns:
            TrendAnalysis: ผลการวิเคราะห์ trend และ market structure
        """
        try:
            # ดึงข้อมูลราคา
            rates = self._get_price_data(bars_count)
            if not rates or len(rates) < 20:
                return self._default_trend_analysis()
            
            # หา swing points
            self._detect_swing_points(rates)
            
            # วิเคราะห์ trend structure
            trend_analysis = self._analyze_trend_structure()
            
            # อัปเดต Support/Resistance levels
            self._update_sr_levels(rates)
            
            # Log ผลการวิเคราะห์
            self._log_market_structure(trend_analysis)
            
            return trend_analysis
            
        except Exception as e:
            logger.error(f"❌ Error analyzing market structure: {e}")
            return self._default_trend_analysis()
    
    def get_current_signal(self, current_price: float) -> Optional[PriceActionSignal]:
        """
        🎯 ได้สัญญาณจาก Price Action ปัจจุบัน
        
        Args:
            current_price: ราคาปัจจุบัน
            
        Returns:
            PriceActionSignal: สัญญาณการเทรด หรือ None ถ้าไม่มี
        """
        try:
            if not self.swing_highs or not self.swing_lows:
                return None
            
            # วิเคราะห์ trend ปัจจุบัน
            trend_analysis = self._analyze_trend_structure()
            
            # หาสัญญาณจาก Support/Resistance
            sr_signal = self._check_sr_signals(current_price)
            
            # หาสัญญาณจาก Swing Structure
            swing_signal = self._check_swing_signals(current_price, trend_analysis)
            
            # หาสัญญาณจาก Momentum
            momentum_signal = self._check_momentum_signals(current_price)
            
            # รวมสัญญาณทั้งหมด
            final_signal = self._combine_signals(sr_signal, swing_signal, momentum_signal, current_price)
            
            if final_signal:
                logger.info(f"🎯 Price Action Signal: {final_signal.signal_type} {final_signal.direction}")
                logger.info(f"   Strength: {final_signal.strength:.1f}% | Confidence: {final_signal.confidence:.1f}%")
                logger.info(f"   Reason: {final_signal.reason}")
            
            return final_signal
            
        except Exception as e:
            logger.error(f"❌ Error getting current signal: {e}")
            return None
    
    def get_support_resistance_levels(self) -> List[SupportResistanceLevel]:
        """📊 ได้ระดับ Support/Resistance ปัจจุบัน"""
        return sorted(self.sr_levels, key=lambda x: x.strength, reverse=True)
    
    def is_at_key_level(self, price: float, tolerance_pips: float = 2.0) -> Optional[SupportResistanceLevel]:
        """
        🎯 ตรวจสอบว่าราคาอยู่ใกล้ระดับสำคัญหรือไม่
        
        Args:
            price: ราคาที่ต้องการตรวจสอบ
            tolerance_pips: ระยะห่างที่ยอมรับได้ (pips)
            
        Returns:
            SupportResistanceLevel: ระดับที่ใกล้ที่สุด หรือ None
        """
        tolerance = tolerance_pips / 10  # แปลงเป็น price units
        
        for level in self.sr_levels:
            if level.zone_range[0] - tolerance <= price <= level.zone_range[1] + tolerance:
                return level
        
        return None
    
    def _get_price_data(self, bars_count: int):
        """ดึงข้อมูลราคาจาก MT5"""
        try:
            rates = mt5.copy_rates_from_pos(self.symbol, mt5.TIMEFRAME_M15, 0, bars_count)
            return rates
        except Exception as e:
            logger.error(f"Error getting price data: {e}")
            return None
    
    def _detect_swing_points(self, rates):
        """🔍 หา Swing Highs และ Swing Lows"""
        try:
            if len(rates) < self.swing_detection_period * 2 + 1:
                return
            
            self.swing_highs.clear()
            self.swing_lows.clear()
            
            for i in range(self.swing_detection_period, len(rates) - self.swing_detection_period):
                current_high = rates[i]['high']
                current_low = rates[i]['low']
                current_time = datetime.fromtimestamp(rates[i]['time'])
                
                # ตรวจสอบ Swing High
                is_swing_high = True
                for j in range(i - self.swing_detection_period, i + self.swing_detection_period + 1):
                    if j != i and rates[j]['high'] >= current_high:
                        is_swing_high = False
                        break
                
                if is_swing_high:
                    # ตรวจสอบระยะห่างจาก swing ก่อนหน้า
                    if not self.swing_highs or abs(current_high - self.swing_highs[-1].price) * 10 >= self.min_swing_distance:
                        swing_point = SwingPoint(
                            price=current_high,
                            timestamp=current_time,
                            type='HIGH',
                            strength=self.swing_detection_period,
                            index=i
                        )
                        self.swing_highs.append(swing_point)
                
                # ตรวจสอบ Swing Low
                is_swing_low = True
                for j in range(i - self.swing_detection_period, i + self.swing_detection_period + 1):
                    if j != i and rates[j]['low'] <= current_low:
                        is_swing_low = False
                        break
                
                if is_swing_low:
                    # ตรวจสอบระยะห่างจาก swing ก่อนหน้า
                    if not self.swing_lows or abs(current_low - self.swing_lows[-1].price) * 10 >= self.min_swing_distance:
                        swing_point = SwingPoint(
                            price=current_low,
                            timestamp=current_time,
                            type='LOW',
                            strength=self.swing_detection_period,
                            index=i
                        )
                        self.swing_lows.append(swing_point)
            
            # เก็บแค่ swing points ล่าสุด (20 จุด)
            self.swing_highs = self.swing_highs[-20:]
            self.swing_lows = self.swing_lows[-20:]
            
            logger.debug(f"🔍 Detected {len(self.swing_highs)} swing highs, {len(self.swing_lows)} swing lows")
            
        except Exception as e:
            logger.error(f"Error detecting swing points: {e}")
    
    def _analyze_trend_structure(self) -> TrendAnalysis:
        """📈 วิเคราะห์โครงสร้าง Trend จาก Swing Points"""
        try:
            if len(self.swing_highs) < 2 or len(self.swing_lows) < 2:
                return self._default_trend_analysis()
            
            # เรียง swing points ตามเวลา
            recent_highs = sorted(self.swing_highs[-4:], key=lambda x: x.timestamp)
            recent_lows = sorted(self.swing_lows[-4:], key=lambda x: x.timestamp)
            
            # วิเคราะห์ Higher Highs/Lower Lows
            hh_count = 0  # Higher Highs
            ll_count = 0  # Lower Lows
            hl_count = 0  # Higher Lows
            lh_count = 0  # Lower Highs
            
            # ตรวจสอบ Highs
            for i in range(1, len(recent_highs)):
                if recent_highs[i].price > recent_highs[i-1].price:
                    hh_count += 1
                else:
                    lh_count += 1
            
            # ตรวจสอบ Lows
            for i in range(1, len(recent_lows)):
                if recent_lows[i].price > recent_lows[i-1].price:
                    hl_count += 1
                else:
                    ll_count += 1
            
            # ตัดสินใจ Trend Direction
            bullish_score = hh_count + hl_count
            bearish_score = lh_count + ll_count
            
            if bullish_score > bearish_score + 1:
                direction = 'BULLISH'
                swing_structure = 'HH_HL'
                strength = min(100, (bullish_score / max(1, bearish_score)) * 30)
            elif bearish_score > bullish_score + 1:
                direction = 'BEARISH'
                swing_structure = 'LH_LL'
                strength = min(100, (bearish_score / max(1, bullish_score)) * 30)
            else:
                direction = 'SIDEWAYS'
                swing_structure = 'CHOPPY'
                strength = 30
            
            # คำนวณ Confidence
            total_swings = len(recent_highs) + len(recent_lows)
            confidence = min(100, (total_swings / 8) * 100) if total_swings > 0 else 50
            
            # กำหนด Momentum
            if strength >= 70:
                momentum = 'STRONG'
            elif strength >= 40:
                momentum = 'MODERATE'
            else:
                momentum = 'WEAK'
            
            return TrendAnalysis(
                direction=direction,
                strength=strength,
                confidence=confidence,
                swing_structure=swing_structure,
                momentum=momentum,
                last_swing_high=recent_highs[-1] if recent_highs else None,
                last_swing_low=recent_lows[-1] if recent_lows else None
            )
            
        except Exception as e:
            logger.error(f"Error analyzing trend structure: {e}")
            return self._default_trend_analysis()
    
    def _update_sr_levels(self, rates):
        """📊 อัปเดตระดับ Support/Resistance"""
        try:
            self.sr_levels.clear()
            
            # รวม swing points ทั้งหมด
            all_points = self.swing_highs + self.swing_lows
            if not all_points:
                return
            
            # จัดกลุ่มราคาที่ใกล้กัน
            price_clusters = {}
            for point in all_points:
                cluster_key = round(point.price / self.sr_zone_width) * self.sr_zone_width
                if cluster_key not in price_clusters:
                    price_clusters[cluster_key] = []
                price_clusters[cluster_key].append(point)
            
            # สร้าง S/R levels
            for cluster_price, points in price_clusters.items():
                if len(points) >= self.min_touch_count:
                    # คำนวณ strength จากจำนวน touch และความใหม่
                    touch_count = len(points)
                    recency_bonus = 0
                    
                    # ให้คะแนนเพิ่มสำหรับ touch ล่าสุด
                    latest_touch = max(points, key=lambda x: x.timestamp)
                    time_diff = (datetime.now() - latest_touch.timestamp).total_seconds() / 3600  # hours
                    if time_diff < 24:
                        recency_bonus = 20
                    elif time_diff < 72:
                        recency_bonus = 10
                    
                    strength = min(100, (touch_count * 25) + recency_bonus)
                    
                    # กำหนดประเภท S/R
                    high_points = [p for p in points if p.type == 'HIGH']
                    low_points = [p for p in points if p.type == 'LOW']
                    
                    if len(high_points) > len(low_points):
                        sr_type = 'RESISTANCE'
                    elif len(low_points) > len(high_points):
                        sr_type = 'SUPPORT'
                    else:
                        sr_type = 'SUPPORT_RESISTANCE'
                    
                    # สร้าง zone range
                    min_price = min(p.price for p in points) - self.sr_zone_width/20
                    max_price = max(p.price for p in points) + self.sr_zone_width/20
                    
                    sr_level = SupportResistanceLevel(
                        price=cluster_price,
                        strength=strength,
                        touch_count=touch_count,
                        last_touch=latest_touch.timestamp,
                        type=sr_type,
                        zone_range=(min_price, max_price)
                    )
                    
                    self.sr_levels.append(sr_level)
            
            # เรียงตาม strength
            self.sr_levels.sort(key=lambda x: x.strength, reverse=True)
            
            logger.debug(f"📊 Updated {len(self.sr_levels)} S/R levels")
            
        except Exception as e:
            logger.error(f"Error updating S/R levels: {e}")
    
    def _check_sr_signals(self, current_price: float) -> Optional[Dict]:
        """🎯 ตรวจสอบสัญญาณจาก Support/Resistance"""
        try:
            key_level = self.is_at_key_level(current_price, tolerance_pips=3.0)
            if not key_level:
                return None
            
            if key_level.type == 'SUPPORT' and key_level.strength >= 60:
                return {
                    'type': 'SR_BOUNCE',
                    'direction': 'BUY',
                    'strength': key_level.strength,
                    'reason': f'Bounce from strong support at {key_level.price:.2f}'
                }
            elif key_level.type == 'RESISTANCE' and key_level.strength >= 60:
                return {
                    'type': 'SR_BOUNCE',
                    'direction': 'SELL',
                    'strength': key_level.strength,
                    'reason': f'Rejection from strong resistance at {key_level.price:.2f}'
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking S/R signals: {e}")
            return None
    
    def _check_swing_signals(self, current_price: float, trend: TrendAnalysis) -> Optional[Dict]:
        """🎯 ตรวจสอบสัญญาณจาก Swing Structure"""
        try:
            if not trend.last_swing_high or not trend.last_swing_low:
                return None
            
            if trend.direction == 'BULLISH' and trend.strength >= 50:
                # หา Higher Low forming
                if current_price > trend.last_swing_low.price:
                    return {
                        'type': 'SWING_CONTINUATION',
                        'direction': 'BUY',
                        'strength': trend.strength,
                        'reason': f'Bullish continuation - Higher Low forming'
                    }
            elif trend.direction == 'BEARISH' and trend.strength >= 50:
                # หา Lower High forming
                if current_price < trend.last_swing_high.price:
                    return {
                        'type': 'SWING_CONTINUATION',
                        'direction': 'SELL',
                        'strength': trend.strength,
                        'reason': f'Bearish continuation - Lower High forming'
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking swing signals: {e}")
            return None
    
    def _check_momentum_signals(self, current_price: float) -> Optional[Dict]:
        """⚡ ตรวจสอบสัญญาณจาก Momentum"""
        try:
            # ใช้ recent price movement เป็น momentum indicator
            if not self.swing_highs or not self.swing_lows:
                return None
            
            recent_high = max(self.swing_highs[-3:], key=lambda x: x.timestamp) if len(self.swing_highs) >= 3 else self.swing_highs[-1]
            recent_low = min(self.swing_lows[-3:], key=lambda x: x.timestamp) if len(self.swing_lows) >= 3 else self.swing_lows[-1]
            
            # คำนวณ momentum score
            high_distance = abs(current_price - recent_high.price) * 10  # pips
            low_distance = abs(current_price - recent_low.price) * 10   # pips
            
            if high_distance < 5 and recent_high.timestamp > recent_low.timestamp:
                return {
                    'type': 'MOMENTUM_CONTINUATION',
                    'direction': 'BUY',
                    'strength': 60,
                    'reason': 'Near recent high with bullish momentum'
                }
            elif low_distance < 5 and recent_low.timestamp > recent_high.timestamp:
                return {
                    'type': 'MOMENTUM_CONTINUATION',
                    'direction': 'SELL',
                    'strength': 60,
                    'reason': 'Near recent low with bearish momentum'
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking momentum signals: {e}")
            return None
    
    def _combine_signals(self, sr_signal: Optional[Dict], swing_signal: Optional[Dict], 
                        momentum_signal: Optional[Dict], current_price: float) -> Optional[PriceActionSignal]:
        """🎯 รวมสัญญาณทั้งหมด"""
        try:
            signals = [s for s in [sr_signal, swing_signal, momentum_signal] if s is not None]
            if not signals:
                return None
            
            # หาสัญญาณที่แรงที่สุด
            best_signal = max(signals, key=lambda x: x['strength'])
            
            # คำนวณ confidence จากการสอดคล้องกัน
            same_direction = [s for s in signals if s['direction'] == best_signal['direction']]
            confidence = min(100, (len(same_direction) / len(signals)) * 100)
            
            # สร้าง final signal
            return PriceActionSignal(
                signal_type=best_signal['type'],
                direction=best_signal['direction'],
                strength=best_signal['strength'],
                confidence=confidence,
                entry_price=current_price,
                reason=best_signal['reason'],
                invalidation_price=None  # จะคำนวณภายหลัง
            )
            
        except Exception as e:
            logger.error(f"Error combining signals: {e}")
            return None
    
    def _default_trend_analysis(self) -> TrendAnalysis:
        """📊 Default trend analysis เมื่อไม่มีข้อมูลเพียงพอ"""
        return TrendAnalysis(
            direction='SIDEWAYS',
            strength=30,
            confidence=50,
            swing_structure='UNKNOWN',
            momentum='WEAK',
            last_swing_high=None,
            last_swing_low=None
        )
    
    def _log_market_structure(self, trend: TrendAnalysis):
        """📝 Log ผลการวิเคราะห์"""
        logger.info(f"📈 Market Structure Analysis:")
        logger.info(f"   Trend: {trend.direction} ({trend.swing_structure})")
        logger.info(f"   Strength: {trend.strength:.1f}% | Confidence: {trend.confidence:.1f}%")
        logger.info(f"   Momentum: {trend.momentum}")
        logger.info(f"   Swing Highs: {len(self.swing_highs)} | Swing Lows: {len(self.swing_lows)}")
        logger.info(f"   S/R Levels: {len(self.sr_levels)}")
        
        # Log ระดับ S/R ที่สำคัญ
        if self.sr_levels:
            top_levels = self.sr_levels[:3]
            logger.info(f"   Key Levels:")
            for i, level in enumerate(top_levels, 1):
                logger.info(f"     {i}. {level.type}: {level.price:.2f} (Strength: {level.strength:.0f}%)")
