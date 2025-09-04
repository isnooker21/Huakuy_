# -*- coding: utf-8 -*-
"""
Market Analysis Module
โมดูลสำหรับวิเคราะห์ตลาด Session Awareness และ Multi-Timeframe
"""

import logging
import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class MarketSession(Enum):
    ASIAN = "ASIAN"
    LONDON = "LONDON" 
    NEW_YORK = "NEW_YORK"
    OVERLAP_LONDON_NY = "OVERLAP_LONDON_NY"

class TrendDirection(Enum):
    UP = "UP"
    DOWN = "DOWN"
    SIDEWAYS = "SIDEWAYS"

class Momentum(Enum):
    STRONG = "STRONG"
    WEAK = "WEAK"
    NEUTRAL = "NEUTRAL"

@dataclass
class SessionCharacteristics:
    volume_level: str
    volatility_level: str
    major_pairs: List[str]
    behavior: str
    risk_factors: List[str]
    entry_threshold: float
    max_positions: int
    lot_multiplier: float
    spread_multiplier: float

@dataclass
class TimeframeAnalysis:
    timeframe: str
    trend_direction: TrendDirection
    momentum: Momentum
    strength: float
    volume_ratio: float
    signal_quality: str

class MarketSessionAnalyzer:
    """วิเคราะห์ช่วงเวลาตลาดและปรับกลยุทธ์"""
    
    def __init__(self):
        self.session_configs = {
            MarketSession.ASIAN: SessionCharacteristics(
                volume_level="LOW",
                volatility_level="LOW",
                major_pairs=["USDJPY", "AUDUSD", "NZDUSD"],
                behavior="Range-bound trading",
                risk_factors=["False breakouts", "Low liquidity"],
                entry_threshold=25.0,  # เข้มงวดกว่า
                max_positions=3,       # จำกัดจำนวน
                lot_multiplier=0.8,    # ลด lot size
                spread_multiplier=1.2  # เพิ่ม spread protection
            ),
            
            MarketSession.LONDON: SessionCharacteristics(
                volume_level="HIGH", 
                volatility_level="HIGH",
                major_pairs=["GBPUSD", "EURUSD", "USDCHF"],
                behavior="Strong trends and breakouts",
                risk_factors=["High slippage at open", "Gap risk"],
                entry_threshold=15.0,  # ผ่อนปรนกว่า
                max_positions=5,       # เพิ่มจำนวนได้
                lot_multiplier=1.2,    # เพิ่ม lot size
                spread_multiplier=1.0  # Normal spread
            ),
            
            MarketSession.NEW_YORK: SessionCharacteristics(
                volume_level="HIGHEST",
                volatility_level="HIGHEST", 
                major_pairs=["USDCAD", "XAUUSD"],
                behavior="Major moves with news impact",
                risk_factors=["News volatility", "End-of-day gaps"],
                entry_threshold=18.0,  # กลางๆ
                max_positions=4,       # ปานกลาง
                lot_multiplier=1.1,    # เพิ่มเล็กน้อย
                spread_multiplier=1.1  # เพิ่ม spread protection เล็กน้อย
            ),
            
            MarketSession.OVERLAP_LONDON_NY: SessionCharacteristics(
                volume_level="MAXIMUM",
                volatility_level="MAXIMUM",
                major_pairs=["EURUSD", "GBPUSD", "XAUUSD"],
                behavior="Highest liquidity and volatility",
                risk_factors=["Extreme volatility", "Fast moves"],
                entry_threshold=12.0,  # ผ่อนปรนมากที่สุด
                max_positions=6,       # สูงสุด
                lot_multiplier=1.5,    # เพิ่มมากที่สุด
                spread_multiplier=0.8  # ลด spread (liquidity สูง)
            )
        }
        
    def get_current_session(self) -> MarketSession:
        """หาช่วงเวลาตลาดปัจจุบัน"""
        try:
            # ใช้ GMT time
            utc_now = datetime.now(timezone.utc)
            hour = utc_now.hour
            
            # London + New York Overlap (13:00-17:00 GMT)
            if 13 <= hour < 17:
                return MarketSession.OVERLAP_LONDON_NY
                
            # London Session (08:00-17:00 GMT)
            elif 8 <= hour < 17:
                return MarketSession.LONDON
                
            # New York Session (13:00-22:00 GMT)
            elif 13 <= hour < 22:
                return MarketSession.NEW_YORK
                
            # Asian Session (22:00-08:00 GMT)
            else:
                return MarketSession.ASIAN
                
        except Exception as e:
            logger.error(f"Error determining market session: {e}")
            return MarketSession.ASIAN  # Default to most conservative
    
    def get_session_config(self, session: MarketSession = None) -> SessionCharacteristics:
        """ดึงการตั้งค่าของ session"""
        if session is None:
            session = self.get_current_session()
        return self.session_configs[session]
    
    def adjust_trading_parameters(self, base_params: Dict) -> Dict:
        """ปรับพารามิเตอร์การเทรดตาม session"""
        try:
            session = self.get_current_session()
            config = self.get_session_config(session)
            
            adjusted_params = base_params.copy()
            
            # ปรับพารามิเตอร์ตาม session
            adjusted_params.update({
                'current_session': session.value,
                'entry_threshold': config.entry_threshold,
                'max_positions': config.max_positions,
                'lot_multiplier': config.lot_multiplier,
                'spread_multiplier': config.spread_multiplier,
                'volume_level': config.volume_level,
                'volatility_level': config.volatility_level
            })
            
            logger.info(f"📊 Current Session: {session.value}")
            logger.info(f"   Entry Threshold: {config.entry_threshold}")
            logger.info(f"   Max Positions: {config.max_positions}")
            logger.info(f"   Lot Multiplier: {config.lot_multiplier}")
            
            return adjusted_params
            
        except Exception as e:
            logger.error(f"Error adjusting trading parameters: {e}")
            return base_params

class MultiTimeframeAnalyzer:
    """วิเคราะห์หลาย Timeframe เพื่อยืนยันสัญญาณ"""
    
    def __init__(self, symbol: str = "XAUUSD"):
        self.symbol = symbol
        self.timeframes = {
            'H4': mt5.TIMEFRAME_H4,   # Major trend
            'H1': mt5.TIMEFRAME_H1,   # Momentum  
            'M15': mt5.TIMEFRAME_M15, # Entry signal
            'M5': mt5.TIMEFRAME_M5,   # Timing
            'M1': mt5.TIMEFRAME_M1    # Execution
        }
        
    def analyze_timeframe(self, timeframe: str, bars_count: int = 50) -> TimeframeAnalysis:
        """วิเคราะห์ timeframe เดี่ยว"""
        try:
            tf = self.timeframes.get(timeframe, mt5.TIMEFRAME_M1)
            
            # ดึงข้อมูล
            rates = mt5.copy_rates_from_pos(self.symbol, tf, 0, bars_count)
            if rates is None or len(rates) == 0:
                return self._default_analysis(timeframe)
            
            # วิเคราะห์ trend
            trend = self._analyze_trend(rates)
            
            # วิเคราะห์ momentum
            momentum = self._analyze_momentum(rates)
            
            # คำนวณ strength
            strength = self._calculate_strength(rates)
            
            # วิเคราะห์ volume
            volume_ratio = self._analyze_volume(rates)
            
            # ประเมิน signal quality
            signal_quality = self._assess_signal_quality(trend, momentum, strength)
            
            return TimeframeAnalysis(
                timeframe=timeframe,
                trend_direction=trend,
                momentum=momentum,
                strength=strength,
                volume_ratio=volume_ratio,
                signal_quality=signal_quality
            )
            
        except Exception as e:
            logger.error(f"Error analyzing timeframe {timeframe}: {e}")
            return self._default_analysis(timeframe)
    
    def _analyze_trend(self, rates) -> TrendDirection:
        """วิเคราะห์ทิศทาง trend"""
        try:
            # ใช้ EMA 20 และ EMA 50 เปรียบเทียบ
            closes = [r['close'] for r in rates[-20:]]
            
            if len(closes) < 10:
                return TrendDirection.SIDEWAYS
            
            # Simple trend analysis
            recent_avg = sum(closes[-5:]) / 5
            older_avg = sum(closes[:5]) / 5
            
            diff_pct = ((recent_avg - older_avg) / older_avg) * 100
            
            if diff_pct > 0.5:
                return TrendDirection.UP
            elif diff_pct < -0.5:
                return TrendDirection.DOWN
            else:
                return TrendDirection.SIDEWAYS
                
        except Exception:
            return TrendDirection.SIDEWAYS
    
    def _analyze_momentum(self, rates) -> Momentum:
        """วิเคราะห์ momentum"""
        try:
            # วิเคราะห์การเปลี่ยนแปลงราคาล่าสุด
            recent_rates = rates[-10:]
            price_changes = []
            
            for i in range(1, len(recent_rates)):
                change = ((recent_rates[i]['close'] - recent_rates[i-1]['close']) / 
                         recent_rates[i-1]['close']) * 100
                price_changes.append(abs(change))
            
            if not price_changes:
                return Momentum.NEUTRAL
            
            avg_change = sum(price_changes) / len(price_changes)
            
            if avg_change > 0.3:
                return Momentum.STRONG
            elif avg_change > 0.1:
                return Momentum.WEAK
            else:
                return Momentum.NEUTRAL
                
        except Exception:
            return Momentum.NEUTRAL
    
    def _calculate_strength(self, rates) -> float:
        """คำนวณความแข็งแกร่งของสัญญาณ"""
        try:
            # วิเคราะห์ range และ body ของแท่งเทียน
            recent_rates = rates[-5:]
            strengths = []
            
            for rate in recent_rates:
                high_low_range = rate['high'] - rate['low']
                body_size = abs(rate['close'] - rate['open'])
                
                if high_low_range > 0:
                    body_ratio = body_size / high_low_range
                    strengths.append(body_ratio)
            
            if strengths:
                return (sum(strengths) / len(strengths)) * 100
            else:
                return 0.0
                
        except Exception:
            return 0.0
    
    def _analyze_volume(self, rates) -> float:
        """วิเคราะห์ volume (สำหรับ XAUUSD ใช้ tick volume)"""
        try:
            volumes = [r['tick_volume'] for r in rates[-20:]]
            
            if len(volumes) < 10:
                return 1.0
            
            recent_vol = sum(volumes[-5:]) / 5
            avg_vol = sum(volumes) / len(volumes)
            
            if avg_vol > 0:
                return recent_vol / avg_vol
            else:
                return 1.0
                
        except Exception:
            return 1.0
    
    def _assess_signal_quality(self, trend: TrendDirection, momentum: Momentum, strength: float) -> str:
        """ประเมินคุณภาพสัญญาณ"""
        score = 0
        
        # Trend score
        if trend != TrendDirection.SIDEWAYS:
            score += 30
        
        # Momentum score
        if momentum == Momentum.STRONG:
            score += 40
        elif momentum == Momentum.WEAK:
            score += 20
        
        # Strength score
        if strength > 70:
            score += 30
        elif strength > 50:
            score += 20
        elif strength > 30:
            score += 10
        
        if score >= 80:
            return "EXCELLENT"
        elif score >= 60:
            return "GOOD"
        elif score >= 40:
            return "FAIR"
        else:
            return "POOR"
    
    def _default_analysis(self, timeframe: str) -> TimeframeAnalysis:
        """Default analysis เมื่อเกิด error"""
        return TimeframeAnalysis(
            timeframe=timeframe,
            trend_direction=TrendDirection.SIDEWAYS,
            momentum=Momentum.NEUTRAL,
            strength=0.0,
            volume_ratio=1.0,
            signal_quality="POOR"
        )
    
    def get_multi_timeframe_confirmation(self, signal_direction: str) -> Dict[str, Any]:
        """ดึงการยืนยันจากหลาย timeframe"""
        try:
            # วิเคราะห์แต่ละ timeframe
            analyses = {}
            for tf in ['H4', 'H1', 'M15', 'M5', 'M1']:
                analyses[tf] = self.analyze_timeframe(tf)
            
            # คำนวณ confidence score
            confidence_score = 0
            details = {}
            
            # H4 Trend (40% weight)
            h4_trend = analyses['H4'].trend_direction
            if signal_direction == "BUY" and h4_trend == TrendDirection.UP:
                confidence_score += 40
                details['h4_trend'] = "✅ Bullish"
            elif signal_direction == "SELL" and h4_trend == TrendDirection.DOWN:
                confidence_score += 40  
                details['h4_trend'] = "✅ Bearish"
            else:
                details['h4_trend'] = f"❌ {h4_trend.value}"
            
            # H1 Momentum (25% weight)
            h1_momentum = analyses['H1'].momentum
            if h1_momentum == Momentum.STRONG:
                confidence_score += 25
                details['h1_momentum'] = "✅ Strong"
            elif h1_momentum == Momentum.WEAK:
                confidence_score += 12
                details['h1_momentum'] = "⚠️ Weak"
            else:
                details['h1_momentum'] = "❌ Neutral"
            
            # M15 Signal Quality (20% weight)
            m15_quality = analyses['M15'].signal_quality
            if m15_quality in ["EXCELLENT", "GOOD"]:
                confidence_score += 20
                details['m15_signal'] = f"✅ {m15_quality}"
            elif m15_quality == "FAIR":
                confidence_score += 10
                details['m15_signal'] = f"⚠️ {m15_quality}"
            else:
                details['m15_signal'] = f"❌ {m15_quality}"
            
            # M5 Timing (10% weight)
            m5_strength = analyses['M5'].strength
            if m5_strength > 60:
                confidence_score += 10
                details['m5_timing'] = "✅ Good"
            elif m5_strength > 30:
                confidence_score += 5
                details['m5_timing'] = "⚠️ Fair"
            else:
                details['m5_timing'] = "❌ Poor"
            
            # M1 Execution (5% weight)
            m1_volume = analyses['M1'].volume_ratio
            if m1_volume > 1.2:
                confidence_score += 5
                details['m1_execution'] = "✅ High Volume"
            else:
                details['m1_execution'] = "❌ Low Volume"
            
            # ตัดสินใจ
            decision = self._make_mtf_decision(confidence_score)
            
            logger.info(f"📊 Multi-Timeframe Analysis:")
            logger.info(f"   H4 Trend: {details['h4_trend']}")
            logger.info(f"   H1 Momentum: {details['h1_momentum']}")
            logger.info(f"   M15 Signal: {details['m15_signal']}")
            logger.info(f"   M5 Timing: {details['m5_timing']}")
            logger.info(f"   M1 Execution: {details['m1_execution']}")
            logger.info(f"   Confidence Score: {confidence_score}/100")
            logger.info(f"   Decision: {decision['action']} (Multiplier: {decision['lot_multiplier']})")
            
            return {
                'confidence_score': confidence_score,
                'decision': decision,
                'details': details,
                'analyses': analyses
            }
            
        except Exception as e:
            logger.error(f"Error in multi-timeframe analysis: {e}")
            return {
                'confidence_score': 0,
                'decision': {'action': 'WAIT', 'lot_multiplier': 0, 'confidence': 'LOW'},
                'details': {},
                'analyses': {}
            }
    
    def _make_mtf_decision(self, score: int) -> Dict[str, Any]:
        """ตัดสินใจจาก confidence score"""
        if score >= 85:
            return {
                'action': 'ENTER_AGGRESSIVE',
                'lot_multiplier': 1.5,
                'confidence': 'VERY_HIGH'
            }
        elif score >= 70:
            return {
                'action': 'ENTER_NORMAL',
                'lot_multiplier': 1.2,
                'confidence': 'HIGH'
            }
        elif score >= 55:
            return {
                'action': 'ENTER_CONSERVATIVE', 
                'lot_multiplier': 1.0,
                'confidence': 'MEDIUM'
            }
        elif score >= 40:
            return {
                'action': 'ENTER_MINIMAL',
                'lot_multiplier': 0.8,
                'confidence': 'LOW'
            }
        else:
            return {
                'action': 'ENTER_FLEXIBLE',  # เปลี่ยนจาก WAIT เป็น ENTER_FLEXIBLE
                'lot_multiplier': 0.6,       # ยังให้เทรดได้แต่ lot เล็ก
                'confidence': 'VERY_LOW'
            }
