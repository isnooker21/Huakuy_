# -*- coding: utf-8 -*-
"""
🧠 AI Entry Intelligence Module
โมดูลสำหรับ AI Intelligence ในการเข้าไม้และการวิเคราะห์โอกาส
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
import os

logger = logging.getLogger(__name__)

@dataclass
class ZoneScore:
    """คลาสสำหรับเก็บคะแนนของ Zone"""
    zone_id: str
    zone_type: str  # "support" หรือ "resistance"
    score: float  # 0-100
    strength_score: float
    freshness_score: float
    distance_score: float
    market_context_score: float
    recommendation: str  # "STRONG_ENTRY", "GOOD_ENTRY", "WEAK_ENTRY", "NO_ENTRY"

@dataclass
class EntryAnalysis:
    """คลาสสำหรับเก็บการวิเคราะห์โอกาสเข้าไม้"""
    symbol: str
    current_price: float
    zone_scores: List[ZoneScore]
    market_context_score: float
    portfolio_impact_score: float
    timing_score: float
    overall_score: float  # 0-100
    recommendation: str
    confidence: float  # 0-100
    reasoning: str
    timestamp: datetime

@dataclass
class EntryDecision:
    """คลาสสำหรับเก็บการตัดสินใจเข้าไม้"""
    decision_type: str  # "STRONG_BUY", "BUY", "WEAK_BUY", "NO_ENTRY"
    direction: str  # "BUY" หรือ "SELL"
    zone_id: str
    entry_price: float
    lot_size: float
    confidence: float  # 0-100
    reasoning: str
    timestamp: datetime

class AIEntryIntelligence:
    """🧠 AI Entry Intelligence สำหรับการเข้าไม้"""
    
    def __init__(self, brain_file: str = "ai_entry_brain.json"):
        self.brain_file = brain_file
        self.entry_history = []
        self.performance_stats = {
            'total_entries': 0,
            'successful_entries': 0,
            'accuracy_rate': 0.0,
            'total_profit': 0.0,
            'average_profit_per_entry': 0.0
        }
        
        # AI Weights (ปรับได้จากการเรียนรู้)
        self.weights = {
            'zone_quality_weight': 0.30,
            'market_context_weight': 0.25,
            'portfolio_impact_weight': 0.25,
            'timing_weight': 0.20
        }
        
        # Zone Quality Weights
        self.zone_weights = {
            'strength_weight': 0.40,
            'freshness_weight': 0.30,
            'distance_weight': 0.30
        }
        
        # Load existing AI brain if available
        self.load_ai_brain()
    
    def analyze_entry_opportunity(self, symbol: str, current_price: float, 
                                zones: Dict[str, List[Dict]], positions: List,
                                market_data: Dict = None) -> EntryAnalysis:
        """
        วิเคราะห์โอกาสเข้าไม้ด้วย AI
        
        Args:
            symbol: สัญลักษณ์
            current_price: ราคาปัจจุบัน
            zones: รายการ Zone
            positions: รายการ Position ปัจจุบัน
            market_data: ข้อมูลตลาด
            
        Returns:
            EntryAnalysis: การวิเคราะห์โอกาสเข้าไม้
        """
        try:
            logger.info(f"🧠 AI Entry Analysis for {symbol} at {current_price:.5f}")
            
            # 1. วิเคราะห์ Zone Quality
            zone_scores = self._analyze_zone_quality(zones, current_price)
            
            # 2. วิเคราะห์ Market Context
            market_context_score = self._analyze_market_context(market_data, current_price)
            
            # 3. วิเคราะห์ Portfolio Impact
            portfolio_impact_score = self._analyze_portfolio_impact(positions, symbol)
            
            # 4. วิเคราะห์ Entry Timing
            timing_score = self._analyze_entry_timing(market_data, current_price)
            
            # คำนวณคะแนนรวม
            overall_score = (
                self._calculate_overall_zone_score(zone_scores) * self.weights['zone_quality_weight'] +
                market_context_score * self.weights['market_context_weight'] +
                portfolio_impact_score * self.weights['portfolio_impact_weight'] +
                timing_score * self.weights['timing_weight']
            )
            
            # สร้างคำแนะนำ
            recommendation = self._generate_entry_recommendation(overall_score, zone_scores)
            
            # สร้างความมั่นใจ
            confidence = self._calculate_confidence(overall_score, zone_scores, market_context_score)
            
            # สร้างเหตุผล
            reasoning = self._generate_entry_reasoning(zone_scores, market_context_score, 
                                                     portfolio_impact_score, timing_score)
            
            return EntryAnalysis(
                symbol=symbol,
                current_price=current_price,
                zone_scores=zone_scores,
                market_context_score=market_context_score,
                portfolio_impact_score=portfolio_impact_score,
                timing_score=timing_score,
                overall_score=overall_score,
                recommendation=recommendation,
                confidence=confidence,
                reasoning=reasoning,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"❌ Error in AI entry analysis: {e}")
            return EntryAnalysis(
                symbol=symbol,
                current_price=current_price,
                zone_scores=[],
                market_context_score=0.0,
                portfolio_impact_score=0.0,
                timing_score=0.0,
                overall_score=0.0,
                recommendation="NO_ENTRY",
                confidence=0.0,
                reasoning=f"Error: {str(e)}",
                timestamp=datetime.now()
            )
    
    def _analyze_zone_quality(self, zones: Dict[str, List[Dict]], current_price: float) -> List[ZoneScore]:
        """วิเคราะห์คุณภาพของ Zone"""
        try:
            zone_scores = []
            
            # วิเคราะห์ Support Zones
            support_zones = zones.get('support', [])
            for zone in support_zones:
                zone_score = self._calculate_zone_score(zone, current_price, 'support')
                if zone_score:
                    zone_scores.append(zone_score)
            
            # วิเคราะห์ Resistance Zones
            resistance_zones = zones.get('resistance', [])
            for zone in resistance_zones:
                zone_score = self._calculate_zone_score(zone, current_price, 'resistance')
                if zone_score:
                    zone_scores.append(zone_score)
            
            # เรียงตามคะแนน (มากไปน้อย)
            zone_scores.sort(key=lambda x: x.score, reverse=True)
            
            return zone_scores
            
        except Exception as e:
            logger.error(f"❌ Error analyzing zone quality: {e}")
            return []
    
    def _calculate_zone_score(self, zone: Dict, current_price: float, zone_type: str) -> Optional[ZoneScore]:
        """คำนวณคะแนนของ Zone"""
        try:
            zone_id = zone.get('id', f"{zone_type}_{current_price}")
            strength = zone.get('strength', 0.0)
            price_level = zone.get('price_level', current_price)
            timestamp = zone.get('timestamp', datetime.now())
            
            # 1. Strength Score (40%)
            strength_score = min(100.0, strength * 100)
            
            # 2. Freshness Score (30%)
            freshness_score = self._calculate_zone_freshness(timestamp)
            
            # 3. Distance Score (30%)
            distance_score = self._calculate_zone_distance(price_level, current_price, zone_type)
            
            # คะแนนรวม
            total_score = (
                strength_score * self.zone_weights['strength_weight'] +
                freshness_score * self.zone_weights['freshness_weight'] +
                distance_score * self.zone_weights['distance_weight']
            )
            
            # สร้างคำแนะนำ
            if total_score >= 80:
                recommendation = "STRONG_ENTRY"
            elif total_score >= 60:
                recommendation = "GOOD_ENTRY"
            elif total_score >= 40:
                recommendation = "WEAK_ENTRY"
            else:
                recommendation = "NO_ENTRY"
            
            return ZoneScore(
                zone_id=zone_id,
                zone_type=zone_type,
                score=total_score,
                strength_score=strength_score,
                freshness_score=freshness_score,
                distance_score=distance_score,
                market_context_score=0.0,  # จะคำนวณแยก
                recommendation=recommendation
            )
            
        except Exception as e:
            logger.error(f"❌ Error calculating zone score: {e}")
            return None
    
    def _calculate_zone_freshness(self, timestamp: datetime) -> float:
        """คำนวณความสดของ Zone"""
        try:
            if not isinstance(timestamp, datetime):
                return 50.0  # Default score
            
            # คำนวณเวลาที่ผ่านมา
            time_diff = datetime.now() - timestamp
            hours_ago = time_diff.total_seconds() / 3600
            
            # คะแนนตามความสด (Zone ใหม่ = คะแนนสูง)
            if hours_ago <= 1:  # 1 ชั่วโมง
                return 100.0
            elif hours_ago <= 6:  # 6 ชั่วโมง
                return 75.0
            elif hours_ago <= 24:  # 1 วัน
                return 50.0
            elif hours_ago <= 72:  # 3 วัน
                return 25.0
            else:  # มากกว่า 3 วัน
                return 10.0
                
        except Exception as e:
            logger.error(f"❌ Error calculating zone freshness: {e}")
            return 50.0
    
    def _calculate_zone_distance(self, zone_price: float, current_price: float, zone_type: str) -> float:
        """คำนวณคะแนนระยะห่างจาก Zone"""
        try:
            if zone_price == 0:
                return 50.0
            
            # คำนวณระยะห่างเป็นเปอร์เซ็นต์
            distance = abs(current_price - zone_price) / zone_price * 100
            
            # คะแนนตามระยะห่าง (ใกล้ Zone = คะแนนสูง)
            if distance <= 0.1:  # 0.1%
                return 100.0
            elif distance <= 0.2:  # 0.2%
                return 90.0
            elif distance <= 0.5:  # 0.5%
                return 75.0
            elif distance <= 1.0:  # 1%
                return 50.0
            elif distance <= 2.0:  # 2%
                return 25.0
            else:  # มากกว่า 2%
                return 10.0
                
        except Exception as e:
            logger.error(f"❌ Error calculating zone distance: {e}")
            return 50.0
    
    def _analyze_market_context(self, market_data: Dict, current_price: float) -> float:
        """วิเคราะห์ Market Context"""
        try:
            if not market_data:
                return 50.0  # Default score
            
            score = 50.0  # Base score
            
            # 1. Trend Direction (40%)
            trend_direction = market_data.get('trend_direction', 'sideways')
            if trend_direction == 'uptrend':
                score += 20
            elif trend_direction == 'downtrend':
                score -= 10
            # sideways = no change
            
            # 2. Volatility (30%)
            volatility = market_data.get('volatility', 'normal')
            if volatility == 'high':
                score += 15  # High volatility = โอกาสมาก
            elif volatility == 'low':
                score -= 10  # Low volatility = โอกาสน้อย
            
            # 3. Market Session (20%)
            session = market_data.get('session', 'unknown')
            if session in ['london', 'new_york']:
                score += 10  # Major sessions = โอกาสดี
            elif session == 'asia':
                score += 5  # Asia session = โอกาสปานกลาง
            
            # 4. News Impact (10%)
            news_impact = market_data.get('news_impact', 'none')
            if news_impact == 'high':
                score -= 15  # High news impact = เสี่ยง
            elif news_impact == 'medium':
                score -= 5  # Medium news impact = เสี่ยงปานกลาง
            
            return max(0.0, min(100.0, score))
            
        except Exception as e:
            logger.error(f"❌ Error analyzing market context: {e}")
            return 50.0
    
    def _analyze_portfolio_impact(self, positions: List, symbol: str) -> float:
        """วิเคราะห์ผลกระทบต่อ Portfolio"""
        try:
            if not positions:
                return 100.0  # ไม่มีไม้ = โอกาสดี
            
            # คำนวณจำนวนไม้และกำไร
            total_positions = len(positions)
            total_profit = sum(getattr(pos, 'profit', 0) for pos in positions)
            total_volume = sum(getattr(pos, 'volume', 0) for pos in positions)
            
            score = 100.0  # Base score
            
            # 1. Position Count Impact (40%)
            if total_positions >= 20:
                score -= 30  # ไม้เยอะมาก = เสี่ยง
            elif total_positions >= 10:
                score -= 15  # ไม้เยอะ = เสี่ยงปานกลาง
            elif total_positions >= 5:
                score -= 5  # ไม้ปานกลาง = เสี่ยงน้อย
            
            # 2. Profit Impact (30%)
            if total_volume > 0:
                profit_per_lot = total_profit / total_volume
                if profit_per_lot >= 0.5:
                    score -= 20  # กำไรมาก = ลดโอกาส
                elif profit_per_lot >= 0.25:
                    score -= 10  # กำไรปานกลาง = ลดโอกาสเล็กน้อย
                elif profit_per_lot <= -0.5:
                    score += 20  # ขาดทุนมาก = เพิ่มโอกาส
            
            # 3. Balance Impact (30%)
            if total_profit >= 1000:
                score -= 15  # กำไรมาก = ลดโอกาส
            elif total_profit <= -500:
                score += 15  # ขาดทุน = เพิ่มโอกาส
            
            return max(0.0, min(100.0, score))
            
        except Exception as e:
            logger.error(f"❌ Error analyzing portfolio impact: {e}")
            return 50.0
    
    def _analyze_entry_timing(self, market_data: Dict, current_price: float) -> float:
        """วิเคราะห์จังหวะเข้าไม้"""
        try:
            score = 50.0  # Base score
            
            # 1. Price Action (40%)
            price_action = market_data.get('price_action', 'neutral')
            if price_action == 'strong_bullish':
                score += 20  # แรงขาขึ้น = BUY ดี
            elif price_action == 'strong_bearish':
                score += 20  # แรงขาลง = SELL ดี
            elif price_action == 'bullish':
                score += 10  # ขาขึ้น = BUY ดีปานกลาง
            elif price_action == 'bearish':
                score += 10  # ขาลง = SELL ดีปานกลาง
            
            # 2. Volume Analysis (30%)
            volume_analysis = market_data.get('volume_analysis', 'normal')
            if volume_analysis == 'high':
                score += 15  # Volume สูง = โอกาสดี
            elif volume_analysis == 'low':
                score -= 10  # Volume ต่ำ = โอกาสน้อย
            
            # 3. Time of Day (20%)
            current_hour = datetime.now().hour
            if 8 <= current_hour <= 16:  # London/NY overlap
                score += 10  # Major sessions = โอกาสดี
            elif 0 <= current_hour <= 6:  # Asia session
                score += 5  # Asia session = โอกาสปานกลาง
            
            # 4. Market Structure (10%)
            market_structure = market_data.get('market_structure', 'neutral')
            if market_structure == 'trending':
                score += 5  # Trending = โอกาสดี
            elif market_structure == 'ranging':
                score -= 5  # Ranging = โอกาสน้อย
            
            return max(0.0, min(100.0, score))
            
        except Exception as e:
            logger.error(f"❌ Error analyzing entry timing: {e}")
            return 50.0
    
    def _calculate_overall_zone_score(self, zone_scores: List[ZoneScore]) -> float:
        """คำนวณคะแนน Zone โดยรวม"""
        try:
            if not zone_scores:
                return 0.0
            
            # ใช้คะแนน Zone ที่ดีที่สุด
            best_zone = zone_scores[0]
            return best_zone.score
            
        except Exception as e:
            logger.error(f"❌ Error calculating overall zone score: {e}")
            return 0.0
    
    def _generate_entry_recommendation(self, overall_score: float, zone_scores: List[ZoneScore]) -> str:
        """สร้างคำแนะนำการเข้าไม้"""
        try:
            if overall_score >= 80 and zone_scores:
                return "STRONG_ENTRY"
            elif overall_score >= 60 and zone_scores:
                return "GOOD_ENTRY"
            elif overall_score >= 40 and zone_scores:
                return "WEAK_ENTRY"
            else:
                return "NO_ENTRY"
                
        except Exception as e:
            logger.error(f"❌ Error generating entry recommendation: {e}")
            return "NO_ENTRY"
    
    def _calculate_confidence(self, overall_score: float, zone_scores: List[ZoneScore], 
                            market_context_score: float) -> float:
        """คำนวณความมั่นใจ"""
        try:
            base_confidence = overall_score
            
            # ปรับตามจำนวน Zone ที่ดี
            if len(zone_scores) >= 3:
                base_confidence += 10  # Zone หลายตัว = มั่นใจมากขึ้น
            elif len(zone_scores) >= 2:
                base_confidence += 5
            
            # ปรับตาม Market Context
            if market_context_score >= 70:
                base_confidence += 10  # Market Context ดี = มั่นใจมากขึ้น
            elif market_context_score <= 30:
                base_confidence -= 10  # Market Context แย่ = มั่นใจน้อยลง
            
            return max(0.0, min(100.0, base_confidence))
            
        except Exception as e:
            logger.error(f"❌ Error calculating confidence: {e}")
            return 50.0
    
    def _generate_entry_reasoning(self, zone_scores: List[ZoneScore], market_context_score: float,
                                portfolio_impact_score: float, timing_score: float) -> str:
        """สร้างเหตุผลการเข้าไม้"""
        try:
            reasons = []
            
            if zone_scores:
                best_zone = zone_scores[0]
                reasons.append(f"Best zone: {best_zone.zone_type} (score: {best_zone.score:.1f})")
            
            if market_context_score >= 70:
                reasons.append("Favorable market context")
            elif market_context_score <= 30:
                reasons.append("Unfavorable market context")
            
            if portfolio_impact_score >= 70:
                reasons.append("Good portfolio impact")
            elif portfolio_impact_score <= 30:
                reasons.append("Poor portfolio impact")
            
            if timing_score >= 70:
                reasons.append("Good entry timing")
            elif timing_score <= 30:
                reasons.append("Poor entry timing")
            
            return "; ".join(reasons) if reasons else "No specific reasons"
            
        except Exception as e:
            logger.error(f"❌ Error generating entry reasoning: {e}")
            return f"Error: {str(e)}"
    
    def log_entry_decision(self, decision: EntryDecision, outcome: Dict = None):
        """บันทึกการตัดสินใจเข้าไม้และผลลัพธ์"""
        try:
            # บันทึกการตัดสินใจ
            entry_record = {
                'timestamp': decision.timestamp.isoformat(),
                'decision_type': decision.decision_type,
                'direction': decision.direction,
                'zone_id': decision.zone_id,
                'entry_price': decision.entry_price,
                'lot_size': decision.lot_size,
                'confidence': decision.confidence,
                'reasoning': decision.reasoning,
                'outcome': outcome
            }
            
            self.entry_history.append(entry_record)
            
            # อัพเดทสถิติ
            self.performance_stats['total_entries'] += 1
            
            if outcome and outcome.get('success', False):
                self.performance_stats['successful_entries'] += 1
                self.performance_stats['total_profit'] += outcome.get('profit', 0)
            
            # คำนวณ accuracy rate
            if self.performance_stats['total_entries'] > 0:
                self.performance_stats['accuracy_rate'] = (
                    self.performance_stats['successful_entries'] / 
                    self.performance_stats['total_entries']
                )
            
            # คำนวณ average profit
            if self.performance_stats['successful_entries'] > 0:
                self.performance_stats['average_profit_per_entry'] = (
                    self.performance_stats['total_profit'] / 
                    self.performance_stats['successful_entries']
                )
            
            logger.info(f"🧠 AI Entry Decision logged: {decision.decision_type} - Confidence: {decision.confidence:.1f}%")
            
        except Exception as e:
            logger.error(f"❌ Error logging entry decision: {e}")
    
    def save_ai_brain(self):
        """บันทึก AI Brain เป็น JSON"""
        try:
            brain_data = {
                'version': '1.0',
                'created': datetime.now().isoformat(),
                'weights': self.weights,
                'zone_weights': self.zone_weights,
                'performance_stats': self.performance_stats,
                'entry_history': self.entry_history[-100:]  # เก็บ 100 รายการล่าสุด
            }
            
            with open(self.brain_file, 'w', encoding='utf-8') as f:
                json.dump(brain_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"🧠 AI Entry Brain saved to {self.brain_file}")
            
        except Exception as e:
            logger.error(f"❌ Error saving AI entry brain: {e}")
    
    def load_ai_brain(self):
        """โหลด AI Brain จาก JSON"""
        try:
            if os.path.exists(self.brain_file):
                with open(self.brain_file, 'r', encoding='utf-8') as f:
                    brain_data = json.load(f)
                
                # โหลด weights
                if 'weights' in brain_data:
                    self.weights.update(brain_data['weights'])
                
                if 'zone_weights' in brain_data:
                    self.zone_weights.update(brain_data['zone_weights'])
                
                # โหลด performance stats
                if 'performance_stats' in brain_data:
                    self.performance_stats.update(brain_data['performance_stats'])
                
                # โหลด entry history
                if 'entry_history' in brain_data:
                    self.entry_history = brain_data['entry_history']
                
                logger.info(f"🧠 AI Entry Brain loaded from {self.brain_file}")
                logger.info(f"   Accuracy Rate: {self.performance_stats.get('accuracy_rate', 0):.2%}")
                logger.info(f"   Total Entries: {self.performance_stats.get('total_entries', 0)}")
                
            else:
                logger.info("🧠 No existing AI Entry Brain found - Starting fresh")
                
        except Exception as e:
            logger.error(f"❌ Error loading AI entry brain: {e}")
    
    def get_ai_stats(self) -> Dict[str, Any]:
        """ดึงสถิติ AI"""
        return {
            'accuracy_rate': self.performance_stats.get('accuracy_rate', 0),
            'total_entries': self.performance_stats.get('total_entries', 0),
            'successful_entries': self.performance_stats.get('successful_entries', 0),
            'total_profit': self.performance_stats.get('total_profit', 0),
            'average_profit_per_entry': self.performance_stats.get('average_profit_per_entry', 0),
            'weights': self.weights,
            'zone_weights': self.zone_weights,
            'recent_entries': len(self.entry_history)
        }
    
    def reset_ai_brain(self):
        """รีเซ็ต AI Brain"""
        try:
            # Reset performance stats
            self.performance_stats = {
                'total_entries': 0,
                'successful_entries': 0,
                'accuracy_rate': 0.0,
                'total_profit': 0.0,
                'average_profit_per_entry': 0.0
            }
            
            # Reset weights to default
            self.weights = {
                'zone_quality_weight': 0.30,
                'market_context_weight': 0.25,
                'portfolio_impact_weight': 0.25,
                'timing_weight': 0.20
            }
            
            self.zone_weights = {
                'strength_weight': 0.40,
                'freshness_weight': 0.30,
                'distance_weight': 0.30
            }
            
            # Clear entry history
            self.entry_history = []
            
            # Delete brain file if exists
            if os.path.exists(self.brain_file):
                os.remove(self.brain_file)
            
            logger.info("🧠 AI Entry Intelligence Brain reset successfully")
            
        except Exception as e:
            logger.error(f"❌ Error resetting AI brain: {e}")
