# -*- coding: utf-8 -*-
"""
Market Condition Detector
ตรวจจับสภาวะตลาดแบบ Real-time
"""

import logging
import time
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import deque

logger = logging.getLogger(__name__)

@dataclass
class MarketCondition:
    """ข้อมูลสภาวะตลาด"""
    condition: str  # 'volatile', 'trending', 'sideways'
    volatility_level: float
    trend_direction: str  # 'up', 'down', 'sideways'
    strength: float  # 0-1
    confidence: float  # 0-1
    timestamp: float
    parameters: Dict[str, Any]

@dataclass
class VolatilityLevel:
    """ระดับความผันผวน"""
    level: str  # 'low', 'medium', 'high'
    threshold: float
    update_frequency: int  # วินาที
    zone_tolerance: float
    min_zone_strength: float

class MarketConditionDetector:
    """ตรวจจับสภาวะตลาดแบบ Real-time"""
    
    def __init__(self):
        self.current_condition = MarketCondition(
            condition='sideways',
            volatility_level=0.01,
            trend_direction='sideways',
            strength=0.5,
            confidence=0.5,
            timestamp=time.time(),
            parameters={}
        )
        
        # 📊 Data Storage
        self.price_history = deque(maxlen=1000)  # เก็บราคา 1000 ครั้งล่าสุด
        self.volume_history = deque(maxlen=1000)
        self.volatility_history = deque(maxlen=100)
        
        # 🎯 Volatility Levels
        self.volatility_levels = {
            'low': VolatilityLevel('low', 0.005, 10, 0.1, 0.03),
            'medium': VolatilityLevel('medium', 0.01, 5, 0.05, 0.02),
            'high': VolatilityLevel('high', 0.02, 2, 0.001, 0.001)
        }
        
        # 🔄 Analysis Parameters
        self.analysis_interval = 5.0  # วิเคราะห์ทุก 5 วินาที
        self.last_analysis_time = 0.0
        self.min_data_points = 20  # ข้อมูลขั้นต่ำสำหรับการวิเคราะห์
        
        # 📈 Trend Detection
        self.trend_periods = [5, 10, 20, 50]  # ระยะเวลาสำหรับการวิเคราะห์เทรนด์
        self.trend_thresholds = {
            'strong': 0.7,
            'medium': 0.5,
            'weak': 0.3
        }
        
        # 🎯 News Event Detection
        self.news_detection_enabled = True
        self.volume_spike_threshold = 2.0  # 2x ปกติ
        self.price_jump_threshold = 0.01  # 1%
        
        # 📊 Performance Metrics
        self.analysis_count = 0
        self.last_performance_check = 0.0
        
    def update_price_data(self, price: float, volume: float = 0.0, timestamp: float = None):
        """อัพเดทข้อมูลราคา"""
        try:
            if timestamp is None:
                timestamp = time.time()
            
            # เก็บข้อมูลราคา
            self.price_history.append({
                'price': price,
                'volume': volume,
                'timestamp': timestamp
            })
            
            # เก็บข้อมูล Volume
            if volume > 0:
                self.volume_history.append({
                    'volume': volume,
                    'timestamp': timestamp
                })
            
            # ตรวจสอบว่าต้องวิเคราะห์ใหม่หรือไม่
            if timestamp - self.last_analysis_time >= self.analysis_interval:
                self._analyze_market_condition()
                
        except Exception as e:
            logger.error(f"❌ Error updating price data: {e}")
    
    def _analyze_market_condition(self):
        """วิเคราะห์สภาวะตลาด"""
        try:
            current_time = time.time()
            
            # ตรวจสอบข้อมูลเพียงพอหรือไม่
            if len(self.price_history) < self.min_data_points:
                logger.debug("📊 [ANALYSIS] Insufficient data for analysis")
                return
            
            # วิเคราะห์ความผันผวน
            volatility_level = self._detect_volatility_level()
            
            # วิเคราะห์ทิศทางเทรนด์
            trend_direction = self._detect_trend_direction()
            
            # วิเคราะห์ความแข็งแกร่ง
            strength = self._calculate_market_strength()
            
            # วิเคราะห์ความเชื่อมั่น
            confidence = self._calculate_confidence()
            
            # กำหนดสภาวะตลาด
            condition = self._determine_market_condition(volatility_level, trend_direction, strength)
            
            # ตรวจสอบเหตุการณ์ข่าว
            news_events = self._detect_news_events()
            
            # สร้าง MarketCondition Object
            new_condition = MarketCondition(
                condition=condition,
                volatility_level=volatility_level,
                trend_direction=trend_direction,
                strength=strength,
                confidence=confidence,
                timestamp=current_time,
                parameters={
                    'news_events': news_events,
                    'data_points': len(self.price_history),
                    'analysis_time': current_time - self.last_analysis_time
                }
            )
            
            # อัพเดทสภาวะปัจจุบัน
            self.current_condition = new_condition
            self.last_analysis_time = current_time
            self.analysis_count += 1
            
            # Log ผลการวิเคราะห์
            self._log_analysis_results(new_condition)
            
            # อัพเดท Performance Metrics
            self._update_performance_metrics()
            
        except Exception as e:
            logger.error(f"❌ Error analyzing market condition: {e}")
    
    def _detect_volatility_level(self) -> float:
        """ตรวจจับระดับความผันผวน"""
        try:
            if len(self.price_history) < 10:
                return 0.01
            
            # คำนวณ Standard Deviation ของราคา
            prices = [item['price'] for item in list(self.price_history)[-50:]]  # 50 ข้อมูลล่าสุด
            volatility = np.std(prices) / np.mean(prices)
            
            # เก็บประวัติความผันผวน
            self.volatility_history.append({
                'volatility': volatility,
                'timestamp': time.time()
            })
            
            return volatility
            
        except Exception as e:
            logger.error(f"❌ Error detecting volatility: {e}")
            return 0.01
    
    def _detect_trend_direction(self) -> str:
        """ตรวจจับทิศทางเทรนด์"""
        try:
            if len(self.price_history) < 20:
                return 'sideways'
            
            # วิเคราะห์เทรนด์ในหลายช่วงเวลา
            trend_scores = []
            
            for period in self.trend_periods:
                if len(self.price_history) >= period:
                    trend_score = self._calculate_trend_score(period)
                    trend_scores.append(trend_score)
            
            if not trend_scores:
                return 'sideways'
            
            # คำนวณคะแนนเทรนด์เฉลี่ย
            avg_trend_score = np.mean(trend_scores)
            
            # กำหนดทิศทางเทรนด์
            if avg_trend_score > self.trend_thresholds['strong']:
                return 'up'
            elif avg_trend_score < -self.trend_thresholds['strong']:
                return 'down'
            else:
                return 'sideways'
                
        except Exception as e:
            logger.error(f"❌ Error detecting trend direction: {e}")
            return 'sideways'
    
    def _calculate_trend_score(self, period: int) -> float:
        """คำนวณคะแนนเทรนด์"""
        try:
            recent_prices = [item['price'] for item in list(self.price_history)[-period:]]
            
            # คำนวณ Linear Regression
            x = np.arange(len(recent_prices))
            y = np.array(recent_prices)
            
            # คำนวณ slope
            slope = np.polyfit(x, y, 1)[0]
            
            # แปลงเป็นคะแนน -1 ถึง 1
            max_slope = np.std(y) * 0.1  # 10% ของ standard deviation
            trend_score = np.clip(slope / max_slope, -1, 1)
            
            return trend_score
            
        except Exception as e:
            logger.error(f"❌ Error calculating trend score: {e}")
            return 0.0
    
    def _calculate_market_strength(self) -> float:
        """คำนวณความแข็งแกร่งของตลาด"""
        try:
            if len(self.price_history) < 10:
                return 0.5
            
            # คำนวณจากความผันผวนและเทรนด์
            volatility = self._detect_volatility_level()
            trend_score = abs(self._calculate_trend_score(20))
            
            # รวมคะแนน (0-1)
            strength = (volatility * 10 + trend_score) / 2
            strength = np.clip(strength, 0, 1)
            
            return strength
            
        except Exception as e:
            logger.error(f"❌ Error calculating market strength: {e}")
            return 0.5
    
    def _calculate_confidence(self) -> float:
        """คำนวณความเชื่อมั่นในการวิเคราะห์"""
        try:
            # ตรวจสอบข้อมูลเพียงพอหรือไม่
            data_confidence = min(len(self.price_history) / 100, 1.0)
            
            # ตรวจสอบความสอดคล้องของข้อมูล
            if len(self.volatility_history) < 5:
                return data_confidence * 0.5
            
            # คำนวณความสอดคล้องของความผันผวน
            recent_volatilities = [item['volatility'] for item in list(self.volatility_history)[-5:]]
            volatility_consistency = 1.0 - (np.std(recent_volatilities) / np.mean(recent_volatilities))
            volatility_consistency = np.clip(volatility_consistency, 0, 1)
            
            # รวมคะแนนความเชื่อมั่น
            confidence = (data_confidence + volatility_consistency) / 2
            
            return confidence
            
        except Exception as e:
            logger.error(f"❌ Error calculating confidence: {e}")
            return 0.5
    
    def _determine_market_condition(self, volatility: float, trend: str, strength: float) -> str:
        """กำหนดสภาวะตลาด"""
        try:
            # ตรวจสอบความผันผวนสูง
            if volatility > self.volatility_levels['high'].threshold:
                return 'volatile'
            
            # ตรวจสอบเทรนด์แข็งแกร่ง
            if trend in ['up', 'down'] and strength > 0.7:
                return 'trending'
            
            # สภาวะปกติ
            return 'sideways'
            
        except Exception as e:
            logger.error(f"❌ Error determining market condition: {e}")
            return 'sideways'
    
    def _detect_news_events(self) -> List[Dict[str, Any]]:
        """ตรวจจับเหตุการณ์ข่าว"""
        try:
            if not self.news_detection_enabled:
                return []
            
            events = []
            
            # ตรวจสอบ Volume Spike
            if len(self.volume_history) >= 10:
                recent_volumes = [item['volume'] for item in list(self.volume_history)[-10:]]
                avg_volume = np.mean(recent_volumes[:-1])  # ยกเว้นข้อมูลล่าสุด
                current_volume = recent_volumes[-1]
                
                if avg_volume > 0 and current_volume > avg_volume * self.volume_spike_threshold:
                    events.append({
                        'type': 'volume_spike',
                        'severity': 'high',
                        'current_volume': current_volume,
                        'avg_volume': avg_volume,
                        'ratio': current_volume / avg_volume
                    })
            
            # ตรวจสอบ Price Jump
            if len(self.price_history) >= 5:
                recent_prices = [item['price'] for item in list(self.price_history)[-5:]]
                price_change = abs(recent_prices[-1] - recent_prices[-2]) / recent_prices[-2]
                
                if price_change > self.price_jump_threshold:
                    events.append({
                        'type': 'price_jump',
                        'severity': 'high',
                        'price_change': price_change,
                        'current_price': recent_prices[-1],
                        'previous_price': recent_prices[-2]
                    })
            
            return events
            
        except Exception as e:
            logger.error(f"❌ Error detecting news events: {e}")
            return []
    
    def _log_analysis_results(self, condition: MarketCondition):
        """Log ผลการวิเคราะห์"""
        try:
            logger.info(f"📊 [MARKET ANALYSIS] {condition.condition.upper()} - "
                       f"Volatility: {condition.volatility_level:.4f}, "
                       f"Trend: {condition.trend_direction}, "
                       f"Strength: {condition.strength:.2f}, "
                       f"Confidence: {condition.confidence:.2f}")
            
            # Log เหตุการณ์ข่าว
            if condition.parameters.get('news_events'):
                for event in condition.parameters['news_events']:
                    logger.warning(f"📰 [NEWS EVENT] {event['type'].upper()} - "
                                 f"Severity: {event['severity']}")
                    
        except Exception as e:
            logger.error(f"❌ Error logging analysis results: {e}")
    
    def _update_performance_metrics(self):
        """อัพเดท Performance Metrics"""
        try:
            current_time = time.time()
            
            if current_time - self.last_performance_check >= 60:  # ทุก 1 นาที
                analysis_rate = self.analysis_count / 60.0
                logger.debug(f"📈 [PERFORMANCE] Analysis rate: {analysis_rate:.2f}/sec")
                
                # Reset counters
                self.analysis_count = 0
                self.last_performance_check = current_time
                
        except Exception as e:
            logger.error(f"❌ Error updating performance metrics: {e}")
    
    # 🎯 Public Methods
    def get_current_condition(self) -> MarketCondition:
        """ดึงสภาวะตลาดปัจจุบัน"""
        return self.current_condition
    
    def get_volatility_level(self) -> VolatilityLevel:
        """ดึงระดับความผันผวนปัจจุบัน"""
        try:
            volatility = self.current_condition.volatility_level
            
            if volatility > self.volatility_levels['high'].threshold:
                return self.volatility_levels['high']
            elif volatility > self.volatility_levels['medium'].threshold:
                return self.volatility_levels['medium']
            else:
                return self.volatility_levels['low']
                
        except Exception as e:
            logger.error(f"❌ Error getting volatility level: {e}")
            return self.volatility_levels['low']
    
    def get_zone_parameters(self) -> Dict[str, float]:
        """ดึงพารามิเตอร์ Zone ตามสภาวะตลาด"""
        try:
            volatility_level = self.get_volatility_level()
            
            return {
                'zone_tolerance': volatility_level.zone_tolerance,
                'min_zone_strength': volatility_level.min_zone_strength,
                'update_frequency': volatility_level.update_frequency
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting zone parameters: {e}")
            return {
                'zone_tolerance': 0.1,
                'min_zone_strength': 0.03,
                'update_frequency': 10
            }
    
    def is_volatile_market(self) -> bool:
        """ตรวจสอบว่าตลาดผันผวนหรือไม่"""
        return self.current_condition.condition == 'volatile'
    
    def is_trending_market(self) -> bool:
        """ตรวจสอบว่าตลาดมีเทรนด์หรือไม่"""
        return self.current_condition.condition == 'trending'
    
    def is_sideways_market(self) -> bool:
        """ตรวจสอบว่าตลาดเป็น sideways หรือไม่"""
        return self.current_condition.condition == 'sideways'
    
    def get_trend_direction(self) -> str:
        """ดึงทิศทางเทรนด์"""
        return self.current_condition.trend_direction
    
    def get_market_strength(self) -> float:
        """ดึงความแข็งแกร่งของตลาด"""
        return self.current_condition.strength
    
    def get_confidence(self) -> float:
        """ดึงความเชื่อมั่นในการวิเคราะห์"""
        return self.current_condition.confidence
    
    def has_news_events(self) -> bool:
        """ตรวจสอบว่ามีเหตุการณ์ข่าวหรือไม่"""
        return len(self.current_condition.parameters.get('news_events', [])) > 0
    
    def get_news_events(self) -> List[Dict[str, Any]]:
        """ดึงรายการเหตุการณ์ข่าว"""
        return self.current_condition.parameters.get('news_events', [])
    
    # 🎯 Configuration
    def set_analysis_interval(self, interval: float):
        """ตั้งค่าช่วงเวลาการวิเคราะห์"""
        self.analysis_interval = interval
        logger.info(f"🔧 [CONFIG] Analysis interval set to {interval} seconds")
    
    def set_volatility_thresholds(self, low: float, medium: float, high: float):
        """ตั้งค่าเกณฑ์ความผันผวน"""
        self.volatility_levels['low'].threshold = low
        self.volatility_levels['medium'].threshold = medium
        self.volatility_levels['high'].threshold = high
        logger.info(f"🔧 [CONFIG] Volatility thresholds updated")
    
    def set_news_detection(self, enabled: bool):
        """เปิด/ปิดการตรวจจับข่าว"""
        self.news_detection_enabled = enabled
        logger.info(f"🔧 [CONFIG] News detection {'enabled' if enabled else 'disabled'}")
    
    def set_volume_spike_threshold(self, threshold: float):
        """ตั้งค่าเกณฑ์ Volume Spike"""
        self.volume_spike_threshold = threshold
        logger.info(f"🔧 [CONFIG] Volume spike threshold set to {threshold}x")
    
    def set_price_jump_threshold(self, threshold: float):
        """ตั้งค่าเกณฑ์ Price Jump"""
        self.price_jump_threshold = threshold
        logger.info(f"🔧 [CONFIG] Price jump threshold set to {threshold*100}%")
    
    # 🎯 Utility Methods
    def clear_history(self):
        """ล้างประวัติข้อมูล"""
        self.price_history.clear()
        self.volume_history.clear()
        self.volatility_history.clear()
        logger.info("🧹 [HISTORY] Cleared all market data history")
    
    def get_data_summary(self) -> Dict[str, Any]:
        """ดึงสรุปข้อมูล"""
        return {
            'price_data_points': len(self.price_history),
            'volume_data_points': len(self.volume_history),
            'volatility_data_points': len(self.volatility_history),
            'analysis_count': self.analysis_count,
            'current_condition': self.current_condition.condition,
            'last_analysis': self.last_analysis_time
        }
