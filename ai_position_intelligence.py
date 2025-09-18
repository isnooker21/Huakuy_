# -*- coding: utf-8 -*-
"""
🧠 AI Position Intelligence Module
โมดูลสำหรับ AI Intelligence ในการปิดไม้และการจัดการ Position
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
import os

logger = logging.getLogger(__name__)

@dataclass
class PositionScore:
    """คลาสสำหรับเก็บคะแนนของ Position"""
    ticket: int
    score: float  # 0-100
    pnl_score: float
    time_score: float
    distance_score: float
    balance_score: float
    market_context_score: float
    reasons: List[str]
    recommendation: str  # "CLOSE_NOW", "CLOSE_LATER", "HOLD"

@dataclass
class PairScore:
    """คลาสสำหรับเก็บคะแนนการจับคู่ไม้"""
    position1_ticket: int
    position2_ticket: int
    combined_score: float  # 0-100
    combined_profit: float
    risk_reduction: float
    lot_balance: float
    time_sync: float
    recommendation: str  # "STRONG_PAIR", "GOOD_PAIR", "WEAK_PAIR", "NO_PAIR"

@dataclass
class AIDecision:
    """คลาสสำหรับเก็บการตัดสินใจของ AI"""
    decision_type: str  # "CLOSE_SINGLE", "CLOSE_PAIR", "CLOSE_GROUP", "HOLD_ALL"
    positions_to_close: List[int]
    expected_profit: float
    confidence: float  # 0-100
    reasoning: str
    timestamp: datetime

class AIPositionIntelligence:
    """🧠 AI Position Intelligence สำหรับการปิดไม้"""
    
    def __init__(self, brain_file: str = "ai_position_brain.json"):
        self.brain_file = brain_file
        self.decision_history = []
        self.performance_stats = {
            'total_decisions': 0,
            'successful_decisions': 0,
            'accuracy_rate': 0.0,
            'total_profit': 0.0,
            'average_profit_per_decision': 0.0
        }
        
        # AI Weights (ปรับได้จากการเรียนรู้) - ปรับปรุงให้เหมาะสมกับ XAUUSD
        self.weights = {
            'pnl_weight': 0.35,        # P&L
            'time_weight': 0.20,       # เวลา
            'distance_weight': 0.15,   # ระยะห่าง
            'balance_weight': 0.10,    # Balance
            'market_context_weight': 0.10,  # Market context
            'risk_management_weight': 0.10  # เพิ่ม Risk management
        }
        
        # Load existing AI brain if available
        self.load_ai_brain()
    
    def calculate_position_intelligence_score(self, position, current_price: float, 
                                            market_data: Dict = None) -> PositionScore:
        """
        คำนวณคะแนน AI Intelligence สำหรับ Position
        
        Args:
            position: Position object
            current_price: ราคาปัจจุบัน
            market_data: ข้อมูลตลาด
            
        Returns:
            PositionScore: คะแนนและคำแนะนำ
        """
        try:
            ticket = getattr(position, 'ticket', 0)
            profit = getattr(position, 'profit', 0)
            volume = getattr(position, 'volume', 0)
            price_open = getattr(position, 'price_open', 0)
            time_open = getattr(position, 'time', datetime.now())
            
            # 1. P&L Score (35%)
            pnl_score = self._calculate_pnl_score(profit, volume, market_data)
            
            # 2. Time Score (20%)
            time_score = self._calculate_time_score(time_open, market_data)
            
            # 3. Distance Score (20%)
            distance_score = self._calculate_distance_score(price_open, current_price, market_data)
            
            # 4. Balance Score (15%)
            balance_score = self._calculate_balance_score(profit, volume)
            
            # 5. Market Context Score (10%)
            market_context_score = self._calculate_market_context_score(market_data, position)
            
            # 6. Risk Management Score (10%) - เพิ่มใหม่
            risk_management_score = self._calculate_risk_management_score(position, market_data)
            
            # คำนวณคะแนนรวม
            total_score = (
                pnl_score * self.weights['pnl_weight'] +
                time_score * self.weights['time_weight'] +
                distance_score * self.weights['distance_weight'] +
                balance_score * self.weights['balance_weight'] +
                market_context_score * self.weights['market_context_weight'] +
                risk_management_score * self.weights['risk_management_weight']
            )
            
            # สร้างคำแนะนำ
            recommendation = self._generate_recommendation(total_score, profit, market_data)
            
            # สร้างเหตุผล
            reasons = self._generate_reasons(pnl_score, time_score, distance_score, balance_score, market_context_score, risk_management_score)
            
            return PositionScore(
                ticket=ticket,
                score=total_score,
                pnl_score=pnl_score,
                time_score=time_score,
                distance_score=distance_score,
                balance_score=balance_score,
                market_context_score=market_context_score,
                reasons=reasons,
                recommendation=recommendation
            )
            
        except Exception as e:
            logger.error(f"❌ Error calculating position score: {e}")
            return PositionScore(
                ticket=getattr(position, 'ticket', 0),
                score=0.0,
                pnl_score=0.0,
                time_score=0.0,
                distance_score=0.0,
                balance_score=0.0,
                market_context_score=0.0,
                reasons=[f"Error: {str(e)}"],
                recommendation="HOLD"
            )
    
    def _calculate_pnl_score(self, profit: float, volume: float, market_data: Dict = None) -> float:
        """คำนวณคะแนน P&L แบบปรับปรุง - พิจารณา spread, commission, และ market volatility"""
        try:
            if volume == 0:
                return 0.0
            
            # คำนวณกำไรต่อ lot
            profit_per_lot = profit / volume
            
            # คำนวณต้นทุนการปิด (spread + commission)
            spread_cost = 0.3  # XAUUSD spread cost per lot
            commission_cost = 0.1  # Commission cost per lot
            total_cost_per_lot = spread_cost + commission_cost
            
            # คำนวณกำไรสุทธิหลังหักต้นทุน
            net_profit_per_lot = profit_per_lot - total_cost_per_lot
            
            # ปรับตาม market volatility
            volatility_multiplier = 1.0
            if market_data:
                volatility = market_data.get('volatility', 'normal')
                if volatility == 'high':
                    volatility_multiplier = 1.2  # High volatility = ควรปิดเร็วขึ้น
                elif volatility == 'low':
                    volatility_multiplier = 0.8  # Low volatility = ไม่รีบปิด
            
            # คำนวณคะแนนตามกำไรสุทธิ
            if net_profit_per_lot >= 0.8:  # กำไรสุทธิมาก
                base_score = 100.0
            elif net_profit_per_lot >= 0.5:  # กำไรสุทธิปานกลาง
                base_score = 75.0 + (net_profit_per_lot - 0.5) * 83.33  # 75-100
            elif net_profit_per_lot >= 0.2:  # กำไรสุทธิน้อย
                base_score = 50.0 + (net_profit_per_lot - 0.2) * 83.33  # 50-75
            elif net_profit_per_lot >= 0:  # กำไรสุทธิเล็กน้อย
                base_score = 25.0 + net_profit_per_lot * 125.0  # 25-50
            else:
                # ขาดทุน - คำนวณตามระดับการขาดทุน
                if net_profit_per_lot <= -1.0:  # ขาดทุนมาก
                    base_score = 0.0
                elif net_profit_per_lot <= -0.5:  # ขาดทุนปานกลาง
                    base_score = 10.0 + (net_profit_per_lot + 1.0) * 20.0  # 0-10
                else:  # ขาดทุนน้อย
                    base_score = 15.0 + (net_profit_per_lot + 0.5) * 20.0  # 10-15
            
            # ปรับตาม volatility
            final_score = base_score * volatility_multiplier
            
            # จำกัดคะแนนระหว่าง 0-100
            return max(0.0, min(100.0, final_score))
                    
        except Exception as e:
            logger.error(f"❌ Error calculating P&L score: {e}")
            return 0.0
    
    def _calculate_time_score(self, time_open: datetime, market_data: Dict = None) -> float:
        """คำนวณคะแนนเวลาแบบปรับปรุง - พิจารณา market session และ volatility"""
        try:
            if not isinstance(time_open, datetime):
                return 50.0  # Default score
            
            # คำนวณเวลาที่เปิดไว้
            time_diff = datetime.now() - time_open
            hours_open = time_diff.total_seconds() / 3600
            
            # คำนวณคะแนนพื้นฐานตามเวลา
            if hours_open >= 48:  # 2 วันขึ้นไป
                base_score = 100.0
            elif hours_open >= 24:  # 1 วันขึ้นไป
                base_score = 85.0
            elif hours_open >= 12:  # 12 ชั่วโมง
                base_score = 70.0
            elif hours_open >= 6:   # 6 ชั่วโมง
                base_score = 50.0
            elif hours_open >= 3:   # 3 ชั่วโมง
                base_score = 30.0
            elif hours_open >= 1:   # 1 ชั่วโมง
                base_score = 15.0
            else:  # น้อยกว่า 1 ชั่วโมง
                base_score = 5.0
            
            # ปรับตาม market session
            session_multiplier = 1.0
            if market_data:
                session = market_data.get('session', 'unknown')
                current_hour = datetime.now().hour
                
                # ปรับตาม session ที่เปิดอยู่
                if session == 'london' or (8 <= current_hour <= 16):
                    session_multiplier = 1.2  # London/NY session = ควรปิดเร็วขึ้น
                elif session == 'new_york' or (13 <= current_hour <= 21):
                    session_multiplier = 1.1  # NY session = ควรปิดเร็วขึ้นเล็กน้อย
                elif session == 'asia' or (0 <= current_hour <= 8):
                    session_multiplier = 0.9  # Asia session = ไม่รีบปิด
                
                # ปรับตาม volatility
                volatility = market_data.get('volatility', 'normal')
                if volatility == 'high':
                    session_multiplier *= 1.3  # High volatility = ควรปิดเร็วขึ้น
                elif volatility == 'low':
                    session_multiplier *= 0.8  # Low volatility = ไม่รีบปิด
            
            # คำนวณคะแนนสุดท้าย
            final_score = base_score * session_multiplier
            
            # จำกัดคะแนนระหว่าง 0-100
            return max(0.0, min(100.0, final_score))
                
        except Exception as e:
            logger.error(f"❌ Error calculating time score: {e}")
            return 50.0
    
    def _calculate_distance_score(self, price_open: float, current_price: float, market_data: Dict = None) -> float:
        """คำนวณคะแนนระยะห่างแบบปรับปรุง - เหมาะสมกับ XAUUSD และ market conditions"""
        try:
            if price_open == 0:
                return 50.0
            
            # คำนวณระยะห่างเป็น pips สำหรับ XAUUSD
            price_diff = abs(current_price - price_open)
            distance_pips = price_diff  # XAUUSD: 1 USD = 1 pip
            
            # คำนวณเปอร์เซ็นต์การเปลี่ยนแปลง
            price_change = price_diff / price_open * 100
            
            # คะแนนพื้นฐานตามระยะห่าง (pips)
            if distance_pips >= 50:  # 50 pips ขึ้นไป
                base_score = 100.0
            elif distance_pips >= 30:  # 30 pips
                base_score = 85.0
            elif distance_pips >= 20:  # 20 pips
                base_score = 70.0
            elif distance_pips >= 10:  # 10 pips
                base_score = 50.0
            elif distance_pips >= 5:   # 5 pips
                base_score = 30.0
            elif distance_pips >= 2:   # 2 pips
                base_score = 15.0
            else:  # น้อยกว่า 2 pips
                base_score = 5.0
            
            # ปรับตาม market volatility
            volatility_multiplier = 1.0
            if market_data:
                volatility = market_data.get('volatility', 'normal')
                if volatility == 'high':
                    volatility_multiplier = 1.3  # High volatility = ควรปิดเร็วขึ้น
                elif volatility == 'low':
                    volatility_multiplier = 0.7  # Low volatility = ไม่รีบปิด
                
                # ปรับตาม trend direction
                trend_direction = market_data.get('trend_direction', 'sideways')
                if trend_direction == 'trending':
                    volatility_multiplier *= 1.1  # Trending market = ควรปิดเร็วขึ้น
                elif trend_direction == 'sideways':
                    volatility_multiplier *= 0.9  # Sideways market = ไม่รีบปิด
            
            # คำนวณคะแนนสุดท้าย
            final_score = base_score * volatility_multiplier
            
            # จำกัดคะแนนระหว่าง 0-100
            return max(0.0, min(100.0, final_score))
                
        except Exception as e:
            logger.error(f"❌ Error calculating distance score: {e}")
            return 50.0
    
    def _calculate_balance_score(self, profit: float, volume: float) -> float:
        """คำนวณคะแนนผลกระทบต่อ Balance"""
        try:
            if volume == 0:
                return 50.0
            
            # คำนวณผลกระทบต่อ Balance
            balance_impact = profit / volume * 100  # % ต่อ lot
            
            # คะแนนตามผลกระทบ
            if balance_impact >= 5.0:  # 5% ขึ้นไป
                return 100.0
            elif balance_impact >= 2.5:  # 2.5%
                return 75.0
            elif balance_impact >= 1.0:  # 1%
                return 50.0
            elif balance_impact >= 0.5:  # 0.5%
                return 25.0
            else:  # น้อยกว่า 0.5%
                return 10.0
                
        except Exception as e:
            logger.error(f"❌ Error calculating balance score: {e}")
            return 50.0
    
    def _calculate_market_context_score(self, market_data: Dict, position) -> float:
        """คำนวณคะแนน Market Context แบบปรับปรุง - เพิ่มปัจจัย volatility และ risk"""
        try:
            if not market_data:
                return 50.0  # Default score
            
            # ตรวจสอบ Market Context
            trend_direction = market_data.get('trend_direction', 'sideways')
            volatility = market_data.get('volatility', 'normal')
            session = market_data.get('session', 'unknown')
            news_impact = market_data.get('news_impact', 'none')
            
            # คะแนนตาม Market Context
            score = 50.0  # Base score
            
            # 1. Trend Direction (30%)
            if trend_direction == 'uptrend':
                if getattr(position, 'type', 0) == 0:  # BUY
                    score += 25  # BUY ใน uptrend = ดีมาก
                else:  # SELL
                    score -= 25  # SELL ใน uptrend = ไม่ดี
            elif trend_direction == 'downtrend':
                if getattr(position, 'type', 0) == 0:  # BUY
                    score -= 25  # BUY ใน downtrend = ไม่ดี
                else:  # SELL
                    score += 25  # SELL ใน downtrend = ดีมาก
            elif trend_direction == 'sideways':
                score += 5  # Sideways = ปานกลาง
            
            # 2. Volatility (25%)
            if volatility == 'high':
                score += 20  # High volatility = ควรปิดเร็ว
            elif volatility == 'normal':
                score += 5   # Normal volatility = ปานกลาง
            elif volatility == 'low':
                score -= 10  # Low volatility = ไม่รีบปิด
            
            # 3. Market Session (20%)
            if session == 'london' or session == 'new_york':
                score += 15  # Major sessions = ควรปิดเร็ว
            elif session == 'asia':
                score += 5   # Asia session = ปานกลาง
            else:
                score += 0   # Unknown session
            
            # 4. News Impact (15%)
            if news_impact == 'high':
                score += 20  # High news impact = ควรปิดเร็ว
            elif news_impact == 'medium':
                score += 10  # Medium news impact = ควรปิด
            elif news_impact == 'low':
                score += 5   # Low news impact = ปานกลาง
            else:
                score += 0   # No news impact
            
            # 5. Risk Level (10%)
            risk_level = market_data.get('risk_level', 'normal')
            if risk_level == 'high':
                score += 15  # High risk = ควรปิดเร็ว
            elif risk_level == 'normal':
                score += 5   # Normal risk = ปานกลาง
            elif risk_level == 'low':
                score -= 5   # Low risk = ไม่รีบปิด
            
            return max(0.0, min(100.0, score))
            
        except Exception as e:
            logger.error(f"❌ Error calculating market context score: {e}")
            return 50.0
    
    def _calculate_risk_management_score(self, position, market_data: Dict = None) -> float:
        """คำนวณคะแนน Risk Management - พิจารณา drawdown, exposure, และ correlation"""
        try:
            score = 50.0  # Base score
            
            # 1. Drawdown Analysis (40%)
            profit = getattr(position, 'profit', 0)
            volume = getattr(position, 'volume', 0)
            
            if volume > 0:
                profit_per_lot = profit / volume
                
                # คำนวณ drawdown level
                if profit_per_lot <= -1.0:  # ขาดทุนมาก
                    score += 30  # ควรปิดเร็ว
                elif profit_per_lot <= -0.5:  # ขาดทุนปานกลาง
                    score += 20  # ควรปิด
                elif profit_per_lot <= -0.2:  # ขาดทุนน้อย
                    score += 10  # ควรปิดเล็กน้อย
                elif profit_per_lot >= 0.5:  # กำไรมาก
                    score += 25  # ควรปิดเพื่อเก็บกำไร
                elif profit_per_lot >= 0.2:  # กำไรปานกลาง
                    score += 15  # ควรปิด
                else:  # กำไร/ขาดทุนน้อย
                    score += 5   # ปานกลาง
            
            # 2. Exposure Analysis (30%)
            if market_data:
                total_exposure = market_data.get('total_exposure', 0)
                max_exposure = market_data.get('max_exposure', 1000)
                
                if max_exposure > 0:
                    exposure_ratio = total_exposure / max_exposure
                    
                    if exposure_ratio >= 0.8:  # Exposure สูง
                        score += 25  # ควรปิดเร็ว
                    elif exposure_ratio >= 0.6:  # Exposure ปานกลาง
                        score += 15  # ควรปิด
                    elif exposure_ratio >= 0.4:  # Exposure ปกติ
                        score += 5   # ปานกลาง
                    else:  # Exposure ต่ำ
                        score -= 5   # ไม่รีบปิด
            
            # 3. Correlation Analysis (20%)
            if market_data:
                correlation = market_data.get('correlation', 0)
                
                if abs(correlation) >= 0.8:  # Correlation สูง
                    score += 20  # ควรปิดเร็ว
                elif abs(correlation) >= 0.6:  # Correlation ปานกลาง
                    score += 10  # ควรปิด
                elif abs(correlation) >= 0.4:  # Correlation ปกติ
                    score += 5   # ปานกลาง
                else:  # Correlation ต่ำ
                    score -= 5   # ไม่รีบปิด
            
            # 4. Volatility Risk (10%)
            if market_data:
                volatility = market_data.get('volatility', 'normal')
                
                if volatility == 'high':
                    score += 15  # High volatility = ควรปิดเร็ว
                elif volatility == 'normal':
                    score += 5   # Normal volatility = ปานกลาง
                elif volatility == 'low':
                    score -= 5   # Low volatility = ไม่รีบปิด
            
            return max(0.0, min(100.0, score))
            
        except Exception as e:
            logger.error(f"❌ Error calculating risk management score: {e}")
            return 50.0
    
    def _generate_recommendation(self, total_score: float, profit: float, market_data: Dict = None) -> str:
        """สร้างคำแนะนำแบบปรับปรุง - พิจารณา market conditions"""
        try:
            # ปรับเกณฑ์ตาม market volatility
            volatility_threshold_adjustment = 0
            if market_data:
                volatility = market_data.get('volatility', 'normal')
                if volatility == 'high':
                    volatility_threshold_adjustment = -10  # High volatility = ควรปิดเร็วขึ้น
                elif volatility == 'low':
                    volatility_threshold_adjustment = 10   # Low volatility = ไม่รีบปิด
            
            # ปรับเกณฑ์ตาม profit level
            profit_threshold_adjustment = 0
            if profit > 0:
                profit_threshold_adjustment = -5  # กำไร = ควรปิดเร็วขึ้น
            elif profit < -10:
                profit_threshold_adjustment = 5   # ขาดทุนมาก = ไม่รีบปิด
            
            # คำนวณเกณฑ์ที่ปรับแล้ว
            close_now_threshold = 80 + volatility_threshold_adjustment + profit_threshold_adjustment
            close_later_threshold = 60 + volatility_threshold_adjustment + profit_threshold_adjustment
            hold_threshold = 40 + volatility_threshold_adjustment + profit_threshold_adjustment
            
            # จำกัดเกณฑ์ให้อยู่ในช่วงที่สมเหตุสมผล
            close_now_threshold = max(70, min(90, close_now_threshold))
            close_later_threshold = max(50, min(80, close_later_threshold))
            hold_threshold = max(30, min(60, hold_threshold))
            
            if total_score >= close_now_threshold:
                return "CLOSE_NOW"
            elif total_score >= close_later_threshold:
                return "CLOSE_LATER"
            elif total_score >= hold_threshold:
                return "HOLD"
            else:
                return "HOLD"
                
        except Exception as e:
            logger.error(f"❌ Error generating recommendation: {e}")
            # Fallback to original logic
            if total_score >= 80:
                return "CLOSE_NOW"
            elif total_score >= 60:
                return "CLOSE_LATER"
            elif total_score >= 40:
                return "HOLD"
            else:
                return "HOLD"
    
    def _generate_reasons(self, pnl_score: float, time_score: float, 
                         distance_score: float, balance_score: float, 
                         market_context_score: float, risk_management_score: float) -> List[str]:
        """สร้างเหตุผลแบบปรับปรุง - รวม risk management"""
        reasons = []
        
        if pnl_score >= 70:
            reasons.append("High P&L score")
        elif pnl_score <= 30:
            reasons.append("Low P&L score")
        
        if time_score >= 70:
            reasons.append("Position is old")
        elif time_score <= 30:
            reasons.append("Position is new")
        
        if distance_score >= 70:
            reasons.append("Large price movement")
        elif distance_score <= 30:
            reasons.append("Small price movement")
        
        if balance_score >= 70:
            reasons.append("High balance impact")
        elif balance_score <= 30:
            reasons.append("Low balance impact")
        
        if market_context_score >= 70:
            reasons.append("Favorable market context")
        elif market_context_score <= 30:
            reasons.append("Unfavorable market context")
        
        if risk_management_score >= 70:
            reasons.append("High risk management score")
        elif risk_management_score <= 30:
            reasons.append("Low risk management score")
        
        return reasons
    
    def find_optimal_pairs(self, positions: List, current_price: float, 
                          market_data: Dict = None) -> List[PairScore]:
        """
        หาการจับคู่ไม้ที่ดีที่สุด
        
        Args:
            positions: รายการ Position
            current_price: ราคาปัจจุบัน
            market_data: ข้อมูลตลาด
            
        Returns:
            List[PairScore]: รายการการจับคู่ที่ดีที่สุด
        """
        try:
            pair_scores = []
            
            # สร้างรายการ BUY และ SELL positions
            buy_positions = []
            sell_positions = []
            
            for pos in positions:
                pos_type = getattr(pos, 'type', 0)
                if pos_type == 0:  # BUY
                    buy_positions.append(pos)
                else:  # SELL
                    sell_positions.append(pos)
            
            # จับคู่ BUY กับ BUY (กำไรมาก + ขาดทุน)
            for i, buy1 in enumerate(buy_positions):
                for j, buy2 in enumerate(buy_positions[i+1:], i+1):
                    pair_score = self._calculate_pair_score(buy1, buy2, current_price, market_data)
                    if pair_score:
                        pair_scores.append(pair_score)
            
            # จับคู่ SELL กับ SELL (กำไรมาก + ขาดทุน)
            for i, sell1 in enumerate(sell_positions):
                for j, sell2 in enumerate(sell_positions[i+1:], i+1):
                    pair_score = self._calculate_pair_score(sell1, sell2, current_price, market_data)
                    if pair_score:
                        pair_scores.append(pair_score)
            
            # เรียงตามคะแนน (มากไปน้อย)
            pair_scores.sort(key=lambda x: x.combined_score, reverse=True)
            
            return pair_scores[:10]  # คืน 10 คู่ที่ดีที่สุด
            
        except Exception as e:
            logger.error(f"❌ Error finding optimal pairs: {e}")
            return []
    
    def _calculate_pair_score(self, pos1, pos2, current_price: float, 
                            market_data: Dict = None) -> Optional[PairScore]:
        """คำนวณคะแนนการจับคู่แบบปรับปรุง - เพิ่มปัจจัย market context และ risk management"""
        try:
            ticket1 = getattr(pos1, 'ticket', 0)
            ticket2 = getattr(pos2, 'ticket', 0)
            profit1 = getattr(pos1, 'profit', 0)
            profit2 = getattr(pos2, 'profit', 0)
            volume1 = getattr(pos1, 'volume', 0)
            volume2 = getattr(pos2, 'volume', 0)
            time1 = getattr(pos1, 'time', datetime.now())
            time2 = getattr(pos2, 'time', datetime.now())
            price1 = getattr(pos1, 'price_open', 0)
            price2 = getattr(pos2, 'price_open', 0)
            
            # 1. Combined Profit (35%) - ลดน้ำหนักลง
            combined_profit = profit1 + profit2
            total_volume = volume1 + volume2
            if total_volume > 0:
                profit_per_lot = combined_profit / total_volume
                # คำนวณต้นทุนการปิด
                spread_cost = 0.3 * total_volume
                commission_cost = 0.1 * total_volume
                net_profit = combined_profit - spread_cost - commission_cost
                net_profit_per_lot = net_profit / total_volume
                
                # คะแนนตามกำไรสุทธิ
                if net_profit_per_lot >= 0.5:
                    profit_score = 100.0
                elif net_profit_per_lot >= 0.2:
                    profit_score = 50.0 + (net_profit_per_lot - 0.2) * 166.67  # 50-100
                elif net_profit_per_lot >= 0:
                    profit_score = net_profit_per_lot * 250.0  # 0-50
                else:
                    profit_score = max(0.0, 25.0 + net_profit_per_lot * 125.0)  # 0-25
            else:
                profit_score = 0.0
            
            # 2. Risk Reduction (25%) - ลดน้ำหนักลง
            risk_reduction = self._calculate_risk_reduction(pos1, pos2)
            
            # 3. Lot Balance (15%) - ลดน้ำหนักลง
            lot_balance = self._calculate_lot_balance(volume1, volume2)
            
            # 4. Time Sync (10%) - ลดน้ำหนักลง
            time_sync = self._calculate_time_sync(time1, time2)
            
            # 5. Market Context (15%) - เพิ่มใหม่
            market_context_score = self._calculate_pair_market_context(pos1, pos2, market_data)
            
            # คะแนนรวม
            combined_score = (
                profit_score * 0.35 +
                risk_reduction * 0.25 +
                lot_balance * 0.15 +
                time_sync * 0.10 +
                market_context_score * 0.15
            )
            
            # สร้างคำแนะนำ
            if combined_score >= 85:
                recommendation = "STRONG_PAIR"
            elif combined_score >= 70:
                recommendation = "GOOD_PAIR"
            elif combined_score >= 50:
                recommendation = "WEAK_PAIR"
            else:
                recommendation = "NO_PAIR"
            
            return PairScore(
                position1_ticket=ticket1,
                position2_ticket=ticket2,
                combined_score=combined_score,
                combined_profit=combined_profit,
                risk_reduction=risk_reduction,
                lot_balance=lot_balance,
                time_sync=time_sync,
                recommendation=recommendation
            )
            
        except Exception as e:
            logger.error(f"❌ Error calculating pair score: {e}")
            return None
    
    def _calculate_risk_reduction(self, pos1, pos2) -> float:
        """คำนวณการลดความเสี่ยง"""
        try:
            # ถ้าเป็นไม้คนละทิศทาง = ลดความเสี่ยงได้
            type1 = getattr(pos1, 'type', 0)
            type2 = getattr(pos2, 'type', 0)
            
            if type1 != type2:
                return 100.0  # คนละทิศทาง = ลดความเสี่ยงได้มาก
            else:
                return 50.0  # ทิศทางเดียวกัน = ลดความเสี่ยงได้น้อย
                
        except Exception as e:
            logger.error(f"❌ Error calculating risk reduction: {e}")
            return 50.0
    
    def _calculate_lot_balance(self, volume1: float, volume2: float) -> float:
        """คำนวณความสมดุลของ Lot Size"""
        try:
            if volume1 == 0 and volume2 == 0:
                return 50.0
            
            # คำนวณความแตกต่างของ Lot Size
            if volume1 > 0 and volume2 > 0:
                ratio = min(volume1, volume2) / max(volume1, volume2)
                return ratio * 100
            else:
                return 50.0
                
        except Exception as e:
            logger.error(f"❌ Error calculating lot balance: {e}")
            return 50.0
    
    def _calculate_time_sync(self, time1: datetime, time2: datetime) -> float:
        """คำนวณความใกล้เคียงของเวลา"""
        try:
            if not isinstance(time1, datetime) or not isinstance(time2, datetime):
                return 50.0
            
            # คำนวณความแตกต่างของเวลา
            time_diff = abs((time1 - time2).total_seconds() / 3600)  # ชั่วโมง
            
            # คะแนนตามความใกล้เคียงของเวลา
            if time_diff <= 1:  # 1 ชั่วโมง
                return 100.0
            elif time_diff <= 6:  # 6 ชั่วโมง
                return 75.0
            elif time_diff <= 24:  # 1 วัน
                return 50.0
            else:  # มากกว่า 1 วัน
                return 25.0
                
        except Exception as e:
            logger.error(f"❌ Error calculating time sync: {e}")
            return 50.0
    
    def _calculate_pair_market_context(self, pos1, pos2, market_data: Dict = None) -> float:
        """คำนวณคะแนน Market Context สำหรับการจับคู่ไม้"""
        try:
            if not market_data:
                return 50.0  # Default score
            
            score = 50.0  # Base score
            
            # ตรวจสอบประเภทไม้
            type1 = getattr(pos1, 'type', 0)
            type2 = getattr(pos2, 'type', 0)
            
            # 1. Hedge Pair Analysis (40%)
            if type1 != type2:  # ไม้คนละทิศทาง (Hedge)
                score += 30  # Hedge pair = ดีมาก
            else:  # ไม้ทิศทางเดียวกัน
                score += 10  # Same direction = ดีปานกลาง
            
            # 2. Market Volatility (25%)
            volatility = market_data.get('volatility', 'normal')
            if volatility == 'high':
                score += 20  # High volatility = ควรปิดเร็ว
            elif volatility == 'normal':
                score += 10  # Normal volatility = ปานกลาง
            elif volatility == 'low':
                score += 5   # Low volatility = ไม่รีบปิด
            
            # 3. Trend Direction (20%)
            trend_direction = market_data.get('trend_direction', 'sideways')
            if trend_direction == 'trending':
                score += 15  # Trending market = ควรปิดเร็ว
            elif trend_direction == 'sideways':
                score += 5   # Sideways market = ปานกลาง
            
            # 4. Market Session (15%)
            session = market_data.get('session', 'unknown')
            if session in ['london', 'new_york']:
                score += 15  # Major sessions = ควรปิดเร็ว
            elif session == 'asia':
                score += 8   # Asia session = ปานกลาง
            else:
                score += 5   # Unknown session
            
            return max(0.0, min(100.0, score))
            
        except Exception as e:
            logger.error(f"❌ Error calculating pair market context: {e}")
            return 50.0
    
    def log_decision(self, decision: AIDecision, outcome: Dict = None):
        """บันทึกการตัดสินใจและผลลัพธ์"""
        try:
            # บันทึกการตัดสินใจ
            decision_record = {
                'timestamp': decision.timestamp.isoformat(),
                'decision_type': decision.decision_type,
                'positions_to_close': decision.positions_to_close,
                'expected_profit': decision.expected_profit,
                'confidence': decision.confidence,
                'reasoning': decision.reasoning,
                'outcome': outcome
            }
            
            self.decision_history.append(decision_record)
            
            # อัพเดทสถิติ
            self.performance_stats['total_decisions'] += 1
            
            if outcome and outcome.get('success', False):
                self.performance_stats['successful_decisions'] += 1
                self.performance_stats['total_profit'] += outcome.get('actual_profit', 0)
            
            # คำนวณ accuracy rate
            if self.performance_stats['total_decisions'] > 0:
                self.performance_stats['accuracy_rate'] = (
                    self.performance_stats['successful_decisions'] / 
                    self.performance_stats['total_decisions']
                )
            
            # คำนวณ average profit
            if self.performance_stats['successful_decisions'] > 0:
                self.performance_stats['average_profit_per_decision'] = (
                    self.performance_stats['total_profit'] / 
                    self.performance_stats['successful_decisions']
                )
            
            logger.info(f"🧠 AI Decision logged: {decision.decision_type} - Confidence: {decision.confidence:.1f}%")
            
        except Exception as e:
            logger.error(f"❌ Error logging decision: {e}")
    
    def save_ai_brain(self):
        """บันทึก AI Brain เป็น JSON"""
        try:
            brain_data = {
                'version': '1.0',
                'created': datetime.now().isoformat(),
                'weights': self.weights,
                'performance_stats': self.performance_stats,
                'decision_history': self.decision_history[-100:]  # เก็บ 100 รายการล่าสุด
            }
            
            with open(self.brain_file, 'w', encoding='utf-8') as f:
                json.dump(brain_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"🧠 AI Brain saved to {self.brain_file}")
            
        except Exception as e:
            logger.error(f"❌ Error saving AI brain: {e}")
    
    def load_ai_brain(self):
        """โหลด AI Brain จาก JSON"""
        try:
            if os.path.exists(self.brain_file):
                with open(self.brain_file, 'r', encoding='utf-8') as f:
                    brain_data = json.load(f)
                
                # โหลด weights
                if 'weights' in brain_data:
                    self.weights.update(brain_data['weights'])
                
                # โหลด performance stats
                if 'performance_stats' in brain_data:
                    self.performance_stats.update(brain_data['performance_stats'])
                
                # โหลด decision history
                if 'decision_history' in brain_data:
                    self.decision_history = brain_data['decision_history']
                
                logger.info(f"🧠 AI Brain loaded from {self.brain_file}")
                logger.info(f"   Accuracy Rate: {self.performance_stats.get('accuracy_rate', 0):.2%}")
                logger.info(f"   Total Decisions: {self.performance_stats.get('total_decisions', 0)}")
                
            else:
                logger.info("🧠 No existing AI Brain found - Starting fresh")
                
        except Exception as e:
            logger.error(f"❌ Error loading AI brain: {e}")
    
    def get_ai_stats(self) -> Dict[str, Any]:
        """ดึงสถิติ AI"""
        return {
            'accuracy_rate': self.performance_stats.get('accuracy_rate', 0),
            'total_decisions': self.performance_stats.get('total_decisions', 0),
            'successful_decisions': self.performance_stats.get('successful_decisions', 0),
            'total_profit': self.performance_stats.get('total_profit', 0),
            'average_profit_per_decision': self.performance_stats.get('average_profit_per_decision', 0),
            'weights': self.weights,
            'recent_decisions': len(self.decision_history)
        }
    
    def reset_ai_brain(self):
        """รีเซ็ต AI Brain"""
        try:
            # Reset performance stats
            self.performance_stats = {
                'total_decisions': 0,
                'successful_decisions': 0,
                'accuracy_rate': 0.0,
                'total_profit': 0.0,
                'average_profit_per_decision': 0.0
            }
            
            # Reset weights to default
            self.weights = {
                'pnl_weight': 0.35,
                'time_weight': 0.20,
                'distance_weight': 0.20,
                'balance_weight': 0.15,
                'market_context_weight': 0.10
            }
            
            # Clear decision history
            self.decision_history = []
            
            # Delete brain file if exists
            if os.path.exists(self.brain_file):
                os.remove(self.brain_file)
            
            logger.info("🧠 AI Position Intelligence Brain reset successfully")
            
        except Exception as e:
            logger.error(f"❌ Error resetting AI brain: {e}")
