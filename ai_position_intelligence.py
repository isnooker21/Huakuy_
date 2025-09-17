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
        
        # AI Weights (ปรับได้จากการเรียนรู้)
        self.weights = {
            'pnl_weight': 0.35,
            'time_weight': 0.20,
            'distance_weight': 0.20,
            'balance_weight': 0.15,
            'market_context_weight': 0.10
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
            pnl_score = self._calculate_pnl_score(profit, volume)
            
            # 2. Time Score (20%)
            time_score = self._calculate_time_score(time_open)
            
            # 3. Distance Score (20%)
            distance_score = self._calculate_distance_score(price_open, current_price)
            
            # 4. Balance Score (15%)
            balance_score = self._calculate_balance_score(profit, volume)
            
            # 5. Market Context Score (10%)
            market_context_score = self._calculate_market_context_score(market_data, position)
            
            # คำนวณคะแนนรวม
            total_score = (
                pnl_score * self.weights['pnl_weight'] +
                time_score * self.weights['time_weight'] +
                distance_score * self.weights['distance_weight'] +
                balance_score * self.weights['balance_weight'] +
                market_context_score * self.weights['market_context_weight']
            )
            
            # สร้างคำแนะนำ
            recommendation = self._generate_recommendation(total_score, profit)
            
            # สร้างเหตุผล
            reasons = self._generate_reasons(pnl_score, time_score, distance_score, balance_score, market_context_score)
            
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
    
    def _calculate_pnl_score(self, profit: float, volume: float) -> float:
        """คำนวณคะแนน P&L"""
        try:
            if volume == 0:
                return 0.0
            
            # คำนวณกำไรต่อ lot
            profit_per_lot = profit / volume
            
            # แปลงเป็นคะแนน 0-100
            # กำไร $0.5 ต่อ 0.01 lot = 100 คะแนน
            # กำไร $0.25 ต่อ 0.01 lot = 50 คะแนน
            # ขาดทุน $0.25 ต่อ 0.01 lot = 0 คะแนน
            # ขาดทุน $0.5+ ต่อ 0.01 lot = 0 คะแนน
            
            if profit_per_lot >= 0.5:
                return 100.0
            elif profit_per_lot >= 0.25:
                return 50.0 + (profit_per_lot - 0.25) * 200  # 50-100
            elif profit_per_lot >= 0:
                return profit_per_lot * 200  # 0-50
            else:
                # ขาดทุน
                if profit_per_lot <= -0.5:
                    return 0.0
                else:
                    return max(0.0, 50.0 + profit_per_lot * 100)  # 0-50
                    
        except Exception as e:
            logger.error(f"❌ Error calculating P&L score: {e}")
            return 0.0
    
    def _calculate_time_score(self, time_open: datetime) -> float:
        """คำนวณคะแนนเวลา"""
        try:
            if not isinstance(time_open, datetime):
                return 50.0  # Default score
            
            # คำนวณเวลาที่เปิดไว้
            time_diff = datetime.now() - time_open
            hours_open = time_diff.total_seconds() / 3600
            
            # คะแนนตามเวลา (ไม้เก่า = คะแนนสูง = ควรปิด)
            if hours_open >= 24:  # 1 วันขึ้นไป
                return 100.0
            elif hours_open >= 12:  # 12 ชั่วโมง
                return 75.0
            elif hours_open >= 6:   # 6 ชั่วโมง
                return 50.0
            elif hours_open >= 3:   # 3 ชั่วโมง
                return 25.0
            else:  # น้อยกว่า 3 ชั่วโมง
                return 10.0
                
        except Exception as e:
            logger.error(f"❌ Error calculating time score: {e}")
            return 50.0
    
    def _calculate_distance_score(self, price_open: float, current_price: float) -> float:
        """คำนวณคะแนนระยะห่าง"""
        try:
            if price_open == 0:
                return 50.0
            
            # คำนวณเปอร์เซ็นต์การเปลี่ยนแปลง
            price_change = abs(current_price - price_open) / price_open * 100
            
            # คะแนนตามการเปลี่ยนแปลงราคา
            # เปลี่ยนแปลงมาก = คะแนนสูง = ควรปิด
            if price_change >= 2.0:  # 2% ขึ้นไป
                return 100.0
            elif price_change >= 1.0:  # 1%
                return 75.0
            elif price_change >= 0.5:  # 0.5%
                return 50.0
            elif price_change >= 0.2:  # 0.2%
                return 25.0
            else:  # น้อยกว่า 0.2%
                return 10.0
                
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
        """คำนวณคะแนน Market Context"""
        try:
            if not market_data:
                return 50.0  # Default score
            
            # ตรวจสอบ Market Context
            trend_direction = market_data.get('trend_direction', 'sideways')
            volatility = market_data.get('volatility', 'normal')
            
            # คะแนนตาม Market Context
            score = 50.0  # Base score
            
            # ปรับตาม Trend Direction
            if trend_direction == 'uptrend':
                if getattr(position, 'type', 0) == 0:  # BUY
                    score += 20  # BUY ใน uptrend = ดี
                else:  # SELL
                    score -= 20  # SELL ใน uptrend = ไม่ดี
            elif trend_direction == 'downtrend':
                if getattr(position, 'type', 0) == 0:  # BUY
                    score -= 20  # BUY ใน downtrend = ไม่ดี
                else:  # SELL
                    score += 20  # SELL ใน downtrend = ดี
            
            # ปรับตาม Volatility
            if volatility == 'high':
                score += 10  # High volatility = ควรปิด
            elif volatility == 'low':
                score -= 10  # Low volatility = ไม่รีบปิด
            
            return max(0.0, min(100.0, score))
            
        except Exception as e:
            logger.error(f"❌ Error calculating market context score: {e}")
            return 50.0
    
    def _generate_recommendation(self, total_score: float, profit: float) -> str:
        """สร้างคำแนะนำ"""
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
                         market_context_score: float) -> List[str]:
        """สร้างเหตุผล"""
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
        """คำนวณคะแนนการจับคู่"""
        try:
            ticket1 = getattr(pos1, 'ticket', 0)
            ticket2 = getattr(pos2, 'ticket', 0)
            profit1 = getattr(pos1, 'profit', 0)
            profit2 = getattr(pos2, 'profit', 0)
            volume1 = getattr(pos1, 'volume', 0)
            volume2 = getattr(pos2, 'volume', 0)
            time1 = getattr(pos1, 'time', datetime.now())
            time2 = getattr(pos2, 'time', datetime.now())
            
            # 1. Combined Profit (40%)
            combined_profit = profit1 + profit2
            profit_score = min(100.0, max(0.0, (combined_profit / (volume1 + volume2)) * 200))
            
            # 2. Risk Reduction (30%)
            risk_reduction = self._calculate_risk_reduction(pos1, pos2)
            
            # 3. Lot Balance (20%)
            lot_balance = self._calculate_lot_balance(volume1, volume2)
            
            # 4. Time Sync (10%)
            time_sync = self._calculate_time_sync(time1, time2)
            
            # คะแนนรวม
            combined_score = (
                profit_score * 0.4 +
                risk_reduction * 0.3 +
                lot_balance * 0.2 +
                time_sync * 0.1
            )
            
            # สร้างคำแนะนำ
            if combined_score >= 80:
                recommendation = "STRONG_PAIR"
            elif combined_score >= 60:
                recommendation = "GOOD_PAIR"
            elif combined_score >= 40:
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
