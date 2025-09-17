# -*- coding: utf-8 -*-
"""
🧠 AI Decision Engine Module
โมดูลสำหรับ AI Decision Engine ที่รวม AI Intelligence กับการตัดสินใจ
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

from ai_position_intelligence import AIPositionIntelligence, AIDecision, PositionScore, PairScore
from ai_entry_intelligence import AIEntryIntelligence, EntryDecision, EntryAnalysis, ZoneScore

logger = logging.getLogger(__name__)

@dataclass
class CombinedDecision:
    """คลาสสำหรับเก็บการตัดสินใจที่รวม AI + Traditional"""
    decision_type: str  # "ENTRY", "CLOSE", "HOLD"
    ai_decision: Any  # AI Decision object
    traditional_decision: Any  # Traditional Decision object
    final_decision: Any  # Final combined decision
    confidence: float  # 0-100
    reasoning: str
    timestamp: datetime

class AIDecisionEngine:
    """🧠 AI Decision Engine ที่รวม AI Intelligence กับการตัดสินใจ"""
    
    def __init__(self):
        self.position_intelligence = AIPositionIntelligence()
        self.entry_intelligence = AIEntryIntelligence()
        self.decision_history = []
        
        # Decision weights (ปรับได้จากการเรียนรู้)
        self.decision_weights = {
            'ai_weight': 0.70,  # AI มีน้ำหนัก 70%
            'traditional_weight': 0.30  # Traditional มีน้ำหนัก 30%
        }
    
    def make_entry_decision(self, symbol: str, current_price: float, zones: Dict[str, List[Dict]], 
                          positions: List, market_data: Dict = None, 
                          traditional_analysis: Dict = None) -> CombinedDecision:
        """
        ตัดสินใจเข้าไม้ด้วย AI + Traditional Logic
        
        Args:
            symbol: สัญลักษณ์
            current_price: ราคาปัจจุบัน
            zones: รายการ Zone
            positions: รายการ Position ปัจจุบัน
            market_data: ข้อมูลตลาด
            traditional_analysis: การวิเคราะห์แบบเดิม
            
        Returns:
            CombinedDecision: การตัดสินใจที่รวม AI + Traditional
        """
        try:
            logger.info(f"🧠 AI Decision Engine: Making entry decision for {symbol}")
            
            # 1. AI Entry Analysis
            ai_analysis = self.entry_intelligence.analyze_entry_opportunity(
                symbol, current_price, zones, positions, market_data
            )
            
            # 2. AI Entry Decision
            ai_decision = self._create_ai_entry_decision(ai_analysis, current_price)
            
            # 3. Traditional Analysis (ถ้ามี)
            traditional_decision = traditional_analysis or {}
            
            # 4. Combine AI + Traditional
            final_decision = self._combine_entry_decisions(ai_decision, traditional_decision)
            
            # 5. Create Combined Decision
            combined_decision = CombinedDecision(
                decision_type="ENTRY",
                ai_decision=ai_decision,
                traditional_decision=traditional_decision,
                final_decision=final_decision,
                confidence=self._calculate_combined_confidence(ai_decision, traditional_decision),
                reasoning=self._generate_combined_reasoning(ai_decision, traditional_decision),
                timestamp=datetime.now()
            )
            
            # 6. Log decision
            self.decision_history.append(combined_decision)
            
            logger.info(f"🧠 Entry Decision: {final_decision.get('action', 'UNKNOWN')} - Confidence: {combined_decision.confidence:.1f}%")
            
            return combined_decision
            
        except Exception as e:
            logger.error(f"❌ Error in AI entry decision: {e}")
            return CombinedDecision(
                decision_type="ENTRY",
                ai_decision=None,
                traditional_decision=traditional_analysis,
                final_decision={"action": "NO_ENTRY", "reason": f"Error: {str(e)}"},
                confidence=0.0,
                reasoning=f"Error: {str(e)}",
                timestamp=datetime.now()
            )
    
    def make_closing_decision(self, positions: List, current_price: float, 
                            market_data: Dict = None, traditional_analysis: Dict = None) -> CombinedDecision:
        """
        ตัดสินใจปิดไม้ด้วย AI + Traditional Logic
        
        Args:
            positions: รายการ Position
            current_price: ราคาปัจจุบัน
            market_data: ข้อมูลตลาด
            traditional_analysis: การวิเคราะห์แบบเดิม
            
        Returns:
            CombinedDecision: การตัดสินใจที่รวม AI + Traditional
        """
        try:
            logger.info(f"🧠 AI Decision Engine: Making closing decision for {len(positions)} positions")
            
            # 1. AI Position Analysis
            position_scores = []
            for pos in positions:
                score = self.position_intelligence.calculate_position_intelligence_score(
                    pos, current_price, market_data
                )
                position_scores.append(score)
            
            # 2. AI Pair Analysis
            pair_scores = self.position_intelligence.find_optimal_pairs(
                positions, current_price, market_data
            )
            
            # 3. AI Closing Decision
            ai_decision = self._create_ai_closing_decision(position_scores, pair_scores)
            
            # 4. Traditional Analysis (ถ้ามี)
            traditional_decision = traditional_analysis or {}
            
            # 5. Combine AI + Traditional
            final_decision = self._combine_closing_decisions(ai_decision, traditional_decision)
            
            # 6. Create Combined Decision
            combined_decision = CombinedDecision(
                decision_type="CLOSE",
                ai_decision=ai_decision,
                traditional_decision=traditional_decision,
                final_decision=final_decision,
                confidence=self._calculate_combined_confidence(ai_decision, traditional_decision),
                reasoning=self._generate_combined_reasoning(ai_decision, traditional_decision),
                timestamp=datetime.now()
            )
            
            # 7. Log decision
            self.decision_history.append(combined_decision)
            
            logger.info(f"🧠 Closing Decision: {final_decision.get('action', 'UNKNOWN')} - Confidence: {combined_decision.confidence:.1f}%")
            
            return combined_decision
            
        except Exception as e:
            logger.error(f"❌ Error in AI closing decision: {e}")
            return CombinedDecision(
                decision_type="CLOSE",
                ai_decision=None,
                traditional_decision=traditional_analysis,
                final_decision={"action": "HOLD_ALL", "reason": f"Error: {str(e)}"},
                confidence=0.0,
                reasoning=f"Error: {str(e)}",
                timestamp=datetime.now()
            )
    
    def _create_ai_entry_decision(self, ai_analysis: EntryAnalysis, current_price: float) -> EntryDecision:
        """สร้าง AI Entry Decision จาก Analysis"""
        try:
            # หา Zone ที่ดีที่สุด
            best_zone = None
            if ai_analysis.zone_scores:
                best_zone = ai_analysis.zone_scores[0]
            
            # กำหนด Direction
            direction = "BUY"
            if best_zone and best_zone.zone_type == "resistance":
                direction = "SELL"
            elif best_zone and best_zone.zone_type == "support":
                direction = "BUY"
            
            # กำหนด Lot Size
            lot_size = 0.01  # Default
            if ai_analysis.overall_score >= 80:
                lot_size = 0.05  # Strong entry
            elif ai_analysis.overall_score >= 60:
                lot_size = 0.03  # Good entry
            elif ai_analysis.overall_score >= 40:
                lot_size = 0.02  # Weak entry
            
            return EntryDecision(
                decision_type=ai_analysis.recommendation,
                direction=direction,
                zone_id=best_zone.zone_id if best_zone else "unknown",
                entry_price=current_price,
                lot_size=lot_size,
                confidence=ai_analysis.confidence,
                reasoning=ai_analysis.reasoning,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"❌ Error creating AI entry decision: {e}")
            return EntryDecision(
                decision_type="NO_ENTRY",
                direction="BUY",
                zone_id="error",
                entry_price=current_price,
                lot_size=0.0,
                confidence=0.0,
                reasoning=f"Error: {str(e)}",
                timestamp=datetime.now()
            )
    
    def _create_ai_closing_decision(self, position_scores: List[PositionScore], 
                                  pair_scores: List[PairScore]) -> AIDecision:
        """สร้าง AI Closing Decision จาก Scores"""
        try:
            # หาไม้ที่ควรปิด
            positions_to_close = []
            expected_profit = 0.0
            
            # 1. ไม้เดี่ยวที่คะแนนสูง
            high_score_positions = [ps for ps in position_scores if ps.score >= 70]
            for ps in high_score_positions:
                positions_to_close.append(ps.ticket)
                # ประมาณการกำไร (ใช้คะแนนเป็นตัวประมาณ)
                expected_profit += ps.score * 0.1  # 1 คะแนน = $0.1
            
            # 2. คู่ที่ดี
            good_pairs = [ps for ps in pair_scores if ps.recommendation in ["STRONG_PAIR", "GOOD_PAIR"]]
            for pair in good_pairs[:2]:  # เอาแค่ 2 คู่ที่ดีที่สุด
                if pair.position1_ticket not in positions_to_close:
                    positions_to_close.append(pair.position1_ticket)
                if pair.position2_ticket not in positions_to_close:
                    positions_to_close.append(pair.position2_ticket)
                expected_profit += pair.combined_profit
            
            # กำหนดประเภทการตัดสินใจ
            if len(positions_to_close) >= 4:
                decision_type = "CLOSE_GROUP"
            elif len(positions_to_close) >= 2:
                decision_type = "CLOSE_PAIR"
            elif len(positions_to_close) == 1:
                decision_type = "CLOSE_SINGLE"
            else:
                decision_type = "HOLD_ALL"
            
            # คำนวณความมั่นใจ
            confidence = 0.0
            if high_score_positions:
                confidence += len(high_score_positions) * 20
            if good_pairs:
                confidence += len(good_pairs) * 15
            confidence = min(100.0, confidence)
            
            # สร้างเหตุผล
            reasoning_parts = []
            if high_score_positions:
                reasoning_parts.append(f"{len(high_score_positions)} high-score positions")
            if good_pairs:
                reasoning_parts.append(f"{len(good_pairs)} good pairs")
            reasoning = "; ".join(reasoning_parts) if reasoning_parts else "No clear closing opportunity"
            
            return AIDecision(
                decision_type=decision_type,
                positions_to_close=positions_to_close,
                expected_profit=expected_profit,
                confidence=confidence,
                reasoning=reasoning,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"❌ Error creating AI closing decision: {e}")
            return AIDecision(
                decision_type="HOLD_ALL",
                positions_to_close=[],
                expected_profit=0.0,
                confidence=0.0,
                reasoning=f"Error: {str(e)}",
                timestamp=datetime.now()
            )
    
    def _combine_entry_decisions(self, ai_decision: EntryDecision, 
                               traditional_decision: Dict) -> Dict[str, Any]:
        """รวม AI Entry Decision กับ Traditional Decision"""
        try:
            # เริ่มจาก AI Decision
            combined = {
                'action': ai_decision.decision_type,
                'direction': ai_decision.direction,
                'lot_size': ai_decision.lot_size,
                'confidence': ai_decision.confidence,
                'reasoning': ai_decision.reasoning,
                'ai_recommendation': ai_decision.decision_type,
                'traditional_recommendation': traditional_decision.get('recommendation', 'UNKNOWN')
            }
            
            # ปรับตาม Traditional Decision ถ้าต่างกันมาก
            traditional_recommendation = traditional_decision.get('recommendation', 'UNKNOWN')
            
            if ai_decision.decision_type == "NO_ENTRY" and traditional_recommendation == "STRONG_BUY":
                # Traditional บอกให้เข้า แต่ AI บอกไม่เข้า
                combined['action'] = "WEAK_BUY"  # ลดลง
                combined['lot_size'] = min(combined['lot_size'], 0.02)  # ลด lot size
                combined['reasoning'] += "; Traditional suggests entry but AI is cautious"
                
            elif ai_decision.decision_type == "STRONG_ENTRY" and traditional_recommendation == "NO_ENTRY":
                # AI บอกให้เข้าแรง แต่ Traditional บอกไม่เข้า
                combined['action'] = "BUY"  # ลดลง
                combined['lot_size'] = min(combined['lot_size'], 0.03)  # ลด lot size
                combined['reasoning'] += "; AI suggests strong entry but traditional is cautious"
            
            return combined
            
        except Exception as e:
            logger.error(f"❌ Error combining entry decisions: {e}")
            return {
                'action': 'NO_ENTRY',
                'direction': 'BUY',
                'lot_size': 0.0,
                'confidence': 0.0,
                'reasoning': f"Error: {str(e)}"
            }
    
    def _combine_closing_decisions(self, ai_decision: AIDecision, 
                                 traditional_decision: Dict) -> Dict[str, Any]:
        """รวม AI Closing Decision กับ Traditional Decision"""
        try:
            # เริ่มจาก AI Decision
            combined = {
                'action': ai_decision.decision_type,
                'positions_to_close': ai_decision.positions_to_close,
                'expected_profit': ai_decision.expected_profit,
                'confidence': ai_decision.confidence,
                'reasoning': ai_decision.reasoning,
                'ai_recommendation': ai_decision.decision_type,
                'traditional_recommendation': traditional_decision.get('recommendation', 'UNKNOWN')
            }
            
            # ปรับตาม Traditional Decision
            traditional_recommendation = traditional_decision.get('recommendation', 'UNKNOWN')
            
            if ai_decision.decision_type == "HOLD_ALL" and traditional_recommendation == "CLOSE_ALL":
                # Traditional บอกให้ปิดหมด แต่ AI บอกให้ถือ
                combined['action'] = "CLOSE_GROUP"  # ปิดบางส่วน
                combined['reasoning'] += "; Traditional suggests closing all but AI is cautious"
                
            elif ai_decision.decision_type == "CLOSE_GROUP" and traditional_recommendation == "HOLD_ALL":
                # AI บอกให้ปิดหลายไม้ แต่ Traditional บอกให้ถือ
                combined['action'] = "CLOSE_SINGLE"  # ปิดแค่ไม้เดียว
                combined['positions_to_close'] = ai_decision.positions_to_close[:1]  # เอาแค่ตัวแรก
                combined['reasoning'] += "; AI suggests closing multiple but traditional is cautious"
            
            return combined
            
        except Exception as e:
            logger.error(f"❌ Error combining closing decisions: {e}")
            return {
                'action': 'HOLD_ALL',
                'positions_to_close': [],
                'expected_profit': 0.0,
                'confidence': 0.0,
                'reasoning': f"Error: {str(e)}"
            }
    
    def _calculate_combined_confidence(self, ai_decision: Any, traditional_decision: Dict) -> float:
        """คำนวณความมั่นใจรวม"""
        try:
            ai_confidence = getattr(ai_decision, 'confidence', 50.0)
            traditional_confidence = traditional_decision.get('confidence', 50.0)
            
            # รวมด้วยน้ำหนัก
            combined_confidence = (
                ai_confidence * self.decision_weights['ai_weight'] +
                traditional_confidence * self.decision_weights['traditional_weight']
            )
            
            return min(100.0, max(0.0, combined_confidence))
            
        except Exception as e:
            logger.error(f"❌ Error calculating combined confidence: {e}")
            return 50.0
    
    def _generate_combined_reasoning(self, ai_decision: Any, traditional_decision: Dict) -> str:
        """สร้างเหตุผลรวม"""
        try:
            ai_reasoning = getattr(ai_decision, 'reasoning', 'No AI reasoning')
            traditional_reasoning = traditional_decision.get('reasoning', 'No traditional reasoning')
            
            return f"AI: {ai_reasoning} | Traditional: {traditional_reasoning}"
            
        except Exception as e:
            logger.error(f"❌ Error generating combined reasoning: {e}")
            return f"Error: {str(e)}"
    
    def log_decision_outcome(self, decision: CombinedDecision, outcome: Dict):
        """บันทึกผลลัพธ์การตัดสินใจ"""
        try:
            # บันทึกผลลัพธ์ใน AI Intelligence
            if decision.decision_type == "ENTRY" and decision.ai_decision:
                self.entry_intelligence.log_entry_decision(decision.ai_decision, outcome)
            elif decision.decision_type == "CLOSE" and decision.ai_decision:
                self.position_intelligence.log_decision(decision.ai_decision, outcome)
            
            # บันทึกใน Decision Engine
            decision_record = {
                'timestamp': decision.timestamp.isoformat(),
                'decision_type': decision.decision_type,
                'final_decision': decision.final_decision,
                'confidence': decision.confidence,
                'reasoning': decision.reasoning,
                'outcome': outcome
            }
            
            logger.info(f"🧠 Decision outcome logged: {decision.decision_type} - Success: {outcome.get('success', False)}")
            
        except Exception as e:
            logger.error(f"❌ Error logging decision outcome: {e}")
    
    def save_all_ai_brains(self):
        """บันทึก AI Brains ทั้งหมด"""
        try:
            self.position_intelligence.save_ai_brain()
            self.entry_intelligence.save_ai_brain()
            logger.info("🧠 All AI Brains saved successfully")
        except Exception as e:
            logger.error(f"❌ Error saving AI brains: {e}")
    
    def load_all_ai_brains(self):
        """โหลด AI Brains ทั้งหมด"""
        try:
            self.position_intelligence.load_ai_brain()
            self.entry_intelligence.load_ai_brain()
            logger.info("🧠 All AI Brains loaded successfully")
        except Exception as e:
            logger.error(f"❌ Error loading AI brains: {e}")
    
    def get_combined_ai_stats(self) -> Dict[str, Any]:
        """ดึงสถิติ AI รวม"""
        try:
            position_stats = self.position_intelligence.get_ai_stats()
            entry_stats = self.entry_intelligence.get_ai_stats()
            
            return {
                'position_intelligence': position_stats,
                'entry_intelligence': entry_stats,
                'total_decisions': len(self.decision_history),
                'decision_weights': self.decision_weights
            }
        except Exception as e:
            logger.error(f"❌ Error getting combined AI stats: {e}")
            return {}
    
    def reset_all_ai_brains(self):
        """รีเซ็ต AI Brains ทั้งหมด"""
        try:
            self.position_intelligence.reset_ai_brain()
            self.entry_intelligence.reset_ai_brain()
            self.decision_history = []
            logger.info("🧠 All AI Brains reset successfully")
        except Exception as e:
            logger.error(f"❌ Error resetting all AI brains: {e}")
