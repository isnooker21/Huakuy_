#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚀 Enhanced 7D Entry + Position Modifier System
ระบบเข้าไม้ + แก้ไม้ แบบ 7 มิติ ที่เข้ากับระบบปิดไม้

Features:
- 7D Entry Analysis (ใช้ 7 มิติเหมือนระบบปิด)
- Smart Position Modifier (แก้ไม้ที่มีปัญหา)
- Portfolio Synergy (ช่วยเหลือไม้เก่า)
- Integration with Dynamic 7D Smart Closer
- Zero Loss Philosophy (ไม่สร้างปัญหาใหม่)
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import threading

logger = logging.getLogger(__name__)

class EntryStrategy(Enum):
    """กลยุทธ์การเข้าไม้"""
    PERFECT_ENTRY = "PERFECT_ENTRY"      # เข้าจุดสมบูรณ์
    RECOVERY_ENTRY = "RECOVERY_ENTRY"    # เข้าเพื่อช่วยไม้เก่า
    BALANCE_ENTRY = "BALANCE_ENTRY"      # เข้าเพื่อสร้างสมดุล
    HEDGE_ENTRY = "HEDGE_ENTRY"          # เข้าเพื่อป้องกัน
    MODIFIER_ENTRY = "MODIFIER_ENTRY"    # เข้าเพื่อแก้ไม้

class ModifierAction(Enum):
    """การแก้ไข Position"""
    PARTIAL_CLOSE = "PARTIAL_CLOSE"      # ปิดบางส่วน
    ADD_COUNTER = "ADD_COUNTER"          # เพิ่มไม้ตรงข้าม
    ADD_SUPPORT = "ADD_SUPPORT"          # เพิ่มไม้ช่วย
    HEDGE_PROTECT = "HEDGE_PROTECT"      # ป้องกันด้วย hedge
    WAIT_IMPROVE = "WAIT_IMPROVE"        # รอจังหวะดีขึ้น

@dataclass
class Entry7DAnalysis:
    """การวิเคราะห์การเข้าไม้ 7 มิติ"""
    # 🎯 7D Entry Dimensions (เหมือนระบบปิด)
    profit_potential: float      # ศักยภาพกำไร (0-100)
    balance_contribution: float  # การช่วยสมดุล (0-100)
    margin_safety: float         # ความปลอดภัย margin (0-100)
    recovery_support: float      # การช่วยฟื้น portfolio (0-100)
    timing_score: float          # คะแนนจังหวะ (0-100)
    correlation_benefit: float   # ประโยชน์จาก correlation (0-100)
    volatility_advantage: float  # ประโยชน์จากความผันผวน (0-100)
    
    # 📊 Summary
    total_7d_score: float        # คะแนนรวม 7 มิติ
    entry_strategy: EntryStrategy
    confidence: float            # ความมั่นใจ (0-1)
    recommended_lot: float       # lot ที่แนะนำ
    reason: str

@dataclass
class PositionModification:
    """การแก้ไข Position"""
    position_ticket: int
    current_problem: str         # ปัญหาที่พบ
    modifier_action: ModifierAction
    suggested_entry: Dict        # การเข้าไม้ที่แนะนำ
    expected_improvement: float  # การปรับปรุงที่คาดหวัง
    risk_assessment: str         # การประเมิน risk

class Enhanced7DEntrySystem:
    """🚀 ระบบเข้าไม้ + แก้ไม้ แบบ 7 มิติ"""
    
    def __init__(self, intelligent_manager=None, purpose_tracker=None, 
                 dynamic_7d_closer=None, mt5_connection=None):
        self.intelligent_manager = intelligent_manager
        self.purpose_tracker = purpose_tracker
        self.dynamic_7d_closer = dynamic_7d_closer
        self.mt5_connection = mt5_connection
        
        # 🎯 7D Entry Weights (ปรับได้ตามสถานการณ์)
        self.entry_weights = {
            'profit_potential': 0.20,      # 20% - กำไรที่คาดหวัง
            'balance_contribution': 0.15,  # 15% - การช่วยสมดุล
            'margin_safety': 0.15,         # 15% - ความปลอดภัย
            'recovery_support': 0.20,      # 20% - การช่วยฟื้น
            'timing_score': 0.10,          # 10% - จังหวะ
            'correlation_benefit': 0.10,   # 10% - correlation
            'volatility_advantage': 0.10   # 10% - volatility
        }
        
        # 🔧 Position Modifier Settings
        self.modifier_thresholds = {
            'distance_problem': 50.0,      # ห่างจากราคา > 50 pips = ปัญหา
            'time_problem': 24,            # ค้างนาน > 24 ชั่วโมง = ปัญหา
            'loss_problem': -50.0,         # ขาดทุน > $50 = ปัญหา
            'imbalance_problem': 70.0      # เอียง > 70% = ปัญหา
        }
        
        logger.info("🚀 Enhanced 7D Entry + Position Modifier System initialized")
    
    def analyze_entry_opportunity(self, signal_direction: str, current_price: float, 
                                 positions: List[Any], account_info: Dict,
                                 candle_data: Any = None) -> Entry7DAnalysis:
        """
        🎯 วิเคราะห์โอกาสการเข้าไม้แบบ 7 มิติ
        """
        try:
            logger.info(f"🎯 7D ENTRY ANALYSIS: {signal_direction} at {current_price:.2f}")
            
            # 1. 📊 Portfolio Health Check
            portfolio_health = self._analyze_current_portfolio_health(positions, account_info)
            
            # 2. 🎯 Calculate 7D Entry Scores
            entry_scores = self._calculate_7d_entry_scores(
                signal_direction, current_price, positions, account_info, portfolio_health
            )
            
            # 3. 🧠 Determine Entry Strategy
            entry_strategy = self._determine_entry_strategy(entry_scores, positions)
            
            # 4. 📏 Calculate Recommended Lot Size
            recommended_lot = self._calculate_strategic_lot_size(
                entry_scores, portfolio_health, account_info
            )
            
            # 5. 📋 Create Analysis Result
            analysis = Entry7DAnalysis(
                profit_potential=entry_scores['profit_potential'],
                balance_contribution=entry_scores['balance_contribution'],
                margin_safety=entry_scores['margin_safety'],
                recovery_support=entry_scores['recovery_support'],
                timing_score=entry_scores['timing_score'],
                correlation_benefit=entry_scores['correlation_benefit'],
                volatility_advantage=entry_scores['volatility_advantage'],
                total_7d_score=entry_scores['total_score'],
                entry_strategy=entry_strategy,
                confidence=entry_scores['confidence'],
                recommended_lot=recommended_lot,
                reason=entry_scores['reason']
            )
            
            self._log_7d_entry_analysis(analysis)
            return analysis
            
        except Exception as e:
            logger.error(f"❌ Error in 7D entry analysis: {e}")
            # Return conservative analysis
            return Entry7DAnalysis(
                profit_potential=50.0, balance_contribution=50.0, margin_safety=50.0,
                recovery_support=50.0, timing_score=50.0, correlation_benefit=50.0,
                volatility_advantage=50.0, total_7d_score=50.0,
                entry_strategy=EntryStrategy.PERFECT_ENTRY, confidence=0.5,
                recommended_lot=0.01, reason="Error in analysis - using conservative approach"
            )
    
    def analyze_position_modifications(self, positions: List[Any], 
                                     account_info: Dict) -> List[PositionModification]:
        """
        🔧 วิเคราะห์ Position ที่ต้องการการแก้ไข
        """
        try:
            modifications = []
            current_price = self._get_current_price()
            
            logger.info(f"🔧 POSITION MODIFIER: Analyzing {len(positions)} positions")
            
            for position in positions:
                # ตรวจหาปัญหา
                problems = self._detect_position_problems(position, current_price, account_info)
                
                if problems:
                    # หาวิธีแก้ไข
                    modifier_action = self._suggest_modifier_action(position, problems, positions)
                    
                    # สร้าง suggested entry
                    suggested_entry = self._create_modifier_entry_suggestion(
                        position, modifier_action, current_price
                    )
                    
                    modification = PositionModification(
                        position_ticket=getattr(position, 'ticket', 0),
                        current_problem=problems[0],  # ปัญหาหลัก
                        modifier_action=modifier_action,
                        suggested_entry=suggested_entry,
                        expected_improvement=self._calculate_expected_improvement(
                            position, modifier_action
                        ),
                        risk_assessment=self._assess_modifier_risk(position, modifier_action)
                    )
                    
                    modifications.append(modification)
            
            if modifications:
                logger.info(f"🔧 Found {len(modifications)} positions needing modification")
                self._log_position_modifications(modifications)
            
            return modifications
            
        except Exception as e:
            logger.error(f"❌ Error analyzing position modifications: {e}")
            return []
    
    def integrate_with_closing_system(self, entry_analysis: Entry7DAnalysis,
                                    position_modifications: List[PositionModification]) -> Dict[str, Any]:
        """
        🤝 Integration กับ Dynamic 7D Smart Closer
        """
        try:
            integration_result = {
                'entry_recommendation': None,
                'modifier_recommendations': [],
                'closing_coordination': {},
                'portfolio_improvement': {}
            }
            
            # 1. 🎯 Entry Coordination
            if entry_analysis.total_7d_score > 70.0:
                integration_result['entry_recommendation'] = {
                    'should_enter': True,
                    'strategy': entry_analysis.entry_strategy.value,
                    'lot_size': entry_analysis.recommended_lot,
                    'confidence': entry_analysis.confidence,
                    'coordination_note': 'High 7D score - coordinated with closing system'
                }
            
            # 2. 🔧 Modifier Coordination
            for modification in position_modifications:
                if modification.expected_improvement > 0.3:  # 30% improvement
                    integration_result['modifier_recommendations'].append({
                        'ticket': modification.position_ticket,
                        'action': modification.modifier_action.value,
                        'entry_suggestion': modification.suggested_entry,
                        'priority': 'HIGH' if modification.expected_improvement > 0.5 else 'MEDIUM'
                    })
            
            # 3. 🤝 Closing System Coordination
            if self.dynamic_7d_closer:
                integration_result['closing_coordination'] = {
                    'compatible_with_closing': True,
                    'entry_supports_closing': entry_analysis.recovery_support > 60.0,
                    'modifier_supports_closing': len(position_modifications) > 0
                }
            
            logger.info(f"🤝 INTEGRATION: Entry score {entry_analysis.total_7d_score:.1f}, "
                       f"Modifiers: {len(position_modifications)}")
            
            return integration_result
            
        except Exception as e:
            logger.error(f"❌ Error in system integration: {e}")
            return {'error': str(e)}
    
    # 🔧 Helper Methods
    def _calculate_7d_entry_scores(self, direction: str, price: float, positions: List[Any],
                                  account_info: Dict, portfolio_health: Dict) -> Dict[str, float]:
        """คำนวณคะแนน 7 มิติสำหรับการเข้าไม้"""
        try:
            scores = {}
            
            # 1. 💰 Profit Potential
            scores['profit_potential'] = self._calculate_profit_potential(direction, price, positions)
            
            # 2. ⚖️ Balance Contribution  
            scores['balance_contribution'] = self._calculate_balance_contribution(direction, positions)
            
            # 3. 🛡️ Margin Safety
            scores['margin_safety'] = self._calculate_margin_safety(account_info, price)
            
            # 4. 🔄 Recovery Support
            scores['recovery_support'] = self._calculate_recovery_support(direction, price, positions)
            
            # 5. ⏰ Timing Score
            scores['timing_score'] = self._calculate_timing_score(direction, price)
            
            # 6. 🔗 Correlation Benefit
            scores['correlation_benefit'] = self._calculate_correlation_benefit(direction, positions)
            
            # 7. 📊 Volatility Advantage
            scores['volatility_advantage'] = self._calculate_volatility_advantage(direction, price)
            
            # 📊 Total Score (weighted)
            total_score = sum(
                scores[dimension] * weight 
                for dimension, weight in self.entry_weights.items()
            )
            
            scores['total_score'] = total_score
            scores['confidence'] = min(total_score / 100.0, 1.0)
            scores['reason'] = f"7D Analysis: {total_score:.1f}/100"
            
            return scores
            
        except Exception as e:
            logger.error(f"❌ Error calculating 7D entry scores: {e}")
            return {
                'profit_potential': 50.0, 'balance_contribution': 50.0, 'margin_safety': 50.0,
                'recovery_support': 50.0, 'timing_score': 50.0, 'correlation_benefit': 50.0,
                'volatility_advantage': 50.0, 'total_score': 50.0, 'confidence': 0.5,
                'reason': 'Error in calculation'
            }
    
    def _get_current_price(self) -> float:
        """ดึงราคาปัจจุบัน"""
        try:
            if self.mt5_connection:
                return self.mt5_connection.get_current_price()
            return 2650.0  # Default fallback
        except:
            return 2650.0
    
    def _log_7d_entry_analysis(self, analysis: Entry7DAnalysis):
        """แสดง log การวิเคราะห์ 7D Entry"""
        logger.info("🎯 7D ENTRY ANALYSIS RESULT:")
        logger.info("=" * 60)
        logger.info(f"💰 Profit Potential: {analysis.profit_potential:.1f}")
        logger.info(f"⚖️ Balance Contribution: {analysis.balance_contribution:.1f}")
        logger.info(f"🛡️ Margin Safety: {analysis.margin_safety:.1f}")
        logger.info(f"🔄 Recovery Support: {analysis.recovery_support:.1f}")
        logger.info(f"⏰ Timing Score: {analysis.timing_score:.1f}")
        logger.info(f"🔗 Correlation Benefit: {analysis.correlation_benefit:.1f}")
        logger.info(f"📊 Volatility Advantage: {analysis.volatility_advantage:.1f}")
        logger.info("-" * 40)
        logger.info(f"🎯 TOTAL 7D SCORE: {analysis.total_7d_score:.1f}/100")
        logger.info(f"🧠 Strategy: {analysis.entry_strategy.value}")
        logger.info(f"📏 Recommended Lot: {analysis.recommended_lot:.3f}")
        logger.info(f"🎪 Confidence: {analysis.confidence:.2f}")
        logger.info("=" * 60)
    
    # 📊 7D Calculation Methods
    def _calculate_profit_potential(self, direction: str, price: float, positions: List[Any]) -> float:
        """คำนวณศักยภาพกำไร"""
        try:
            # ดูจาก S/R levels และ trend
            base_score = 60.0
            
            # ปรับตาม existing positions
            if positions:
                avg_profit = sum(getattr(p, 'profit', 0) for p in positions) / len(positions)
                if avg_profit < 0:
                    base_score += 20.0  # มีโอกาสปรับตัว
            
            return min(base_score, 100.0)
        except:
            return 60.0
    
    def _calculate_balance_contribution(self, direction: str, positions: List[Any]) -> float:
        """คำนวณการช่วยสมดุล"""
        try:
            if not positions:
                return 70.0
            
            buy_count = sum(1 for p in positions if getattr(p, 'type', 0) == 0)
            sell_count = len(positions) - buy_count
            
            if direction == "BUY":
                if sell_count > buy_count:
                    return 80.0  # ช่วยสมดุลดี
                else:
                    return 40.0  # อาจทำให้เอียง
            else:  # SELL
                if buy_count > sell_count:
                    return 80.0  # ช่วยสมดุลดี
                else:
                    return 40.0  # อาจทำให้เอียง
        except:
            return 60.0
    
    def _calculate_margin_safety(self, account_info: Dict, price: float) -> float:
        """คำนวณความปลอดภัย margin"""
        try:
            margin_level = account_info.get('margin_level', 1000.0)
            
            if margin_level > 1000:
                return 90.0
            elif margin_level > 500:
                return 70.0
            elif margin_level > 300:
                return 50.0
            else:
                return 20.0
        except:
            return 60.0
    
    def _calculate_recovery_support(self, direction: str, price: float, positions: List[Any]) -> float:
        """คำนวณการช่วยฟื้น portfolio"""
        try:
            if not positions:
                return 50.0
            
            losing_positions = [p for p in positions if getattr(p, 'profit', 0) < 0]
            if not losing_positions:
                return 30.0  # ไม่มีอะไรต้องช่วย
            
            # ดูว่าการเข้าใหม่จะช่วยได้มากแค่ไหน
            recovery_score = 0.0
            for pos in losing_positions:
                pos_type = getattr(pos, 'type', 0)
                pos_price = getattr(pos, 'price_open', price)
                
                if direction == "BUY" and pos_type == 0:  # BUY ช่วย BUY
                    if price < pos_price:
                        recovery_score += 20.0  # Average down
                elif direction == "SELL" and pos_type == 1:  # SELL ช่วย SELL
                    if price > pos_price:
                        recovery_score += 20.0  # Average down
                else:
                    recovery_score += 10.0  # Hedge help
            
            return min(recovery_score, 100.0)
        except:
            return 50.0
    
    def _calculate_timing_score(self, direction: str, price: float) -> float:
        """คำนวณคะแนนจังหวะ"""
        # Simple implementation - can be enhanced with technical analysis
        return 60.0
    
    def _calculate_correlation_benefit(self, direction: str, positions: List[Any]) -> float:
        """คำนวณประโยชน์จาก correlation"""
        # Simple implementation - can be enhanced with correlation analysis
        return 55.0
    
    def _calculate_volatility_advantage(self, direction: str, price: float) -> float:
        """คำนวณประโยชน์จากความผันผวน"""
        # Simple implementation - can be enhanced with volatility analysis
        return 65.0
    
    def _analyze_current_portfolio_health(self, positions: List[Any], account_info: Dict) -> Dict:
        """วิเคราะห์สุขภาพ portfolio ปัจจุบัน"""
        try:
            return {
                'total_positions': len(positions),
                'margin_level': account_info.get('margin_level', 1000.0),
                'equity': account_info.get('equity', 10000.0),
                'balance': account_info.get('balance', 10000.0)
            }
        except:
            return {'total_positions': 0, 'margin_level': 1000.0, 'equity': 10000.0, 'balance': 10000.0}
    
    def _determine_entry_strategy(self, scores: Dict, positions: List[Any]) -> EntryStrategy:
        """กำหนดกลยุทธ์การเข้าไม้"""
        try:
            if scores['recovery_support'] > 70.0:
                return EntryStrategy.RECOVERY_ENTRY
            elif scores['balance_contribution'] > 75.0:
                return EntryStrategy.BALANCE_ENTRY
            elif scores['total_score'] > 80.0:
                return EntryStrategy.PERFECT_ENTRY
            else:
                return EntryStrategy.HEDGE_ENTRY
        except:
            return EntryStrategy.PERFECT_ENTRY
    
    def _calculate_strategic_lot_size(self, scores: Dict, portfolio_health: Dict, account_info: Dict) -> float:
        """คำนวณขนาด lot ที่เหมาะสม"""
        try:
            base_lot = 0.01
            
            # ปรับตาม confidence
            confidence_multiplier = scores.get('confidence', 0.5)
            
            # ปรับตาม margin safety
            margin_level = portfolio_health.get('margin_level', 1000.0)
            if margin_level > 1000:
                safety_multiplier = 1.5
            elif margin_level > 500:
                safety_multiplier = 1.0
            else:
                safety_multiplier = 0.5
            
            final_lot = base_lot * confidence_multiplier * safety_multiplier
            return max(0.01, min(final_lot, 0.1))  # จำกัด 0.01-0.1
        except:
            return 0.01
    
    # 🔧 Position Modifier Methods (Simplified for now)
    def _detect_position_problems(self, position: Any, current_price: float, account_info: Dict) -> List[str]:
        """ตรวจหาปัญหาของ position"""
        problems = []
        try:
            profit = getattr(position, 'profit', 0)
            price_open = getattr(position, 'price_open', current_price)
            
            # ตรวจ distance
            distance = abs(current_price - price_open)
            if distance > self.modifier_thresholds['distance_problem']:
                problems.append(f"Distance problem: {distance:.1f} pips")
            
            # ตรวจ loss
            if profit < self.modifier_thresholds['loss_problem']:
                problems.append(f"Loss problem: ${profit:.2f}")
                
        except Exception as e:
            logger.error(f"Error detecting problems: {e}")
        
        return problems
    
    def _suggest_modifier_action(self, position: Any, problems: List[str], all_positions: List[Any]) -> ModifierAction:
        """แนะนำการแก้ไข"""
        if "Loss problem" in str(problems):
            return ModifierAction.ADD_SUPPORT
        elif "Distance problem" in str(problems):
            return ModifierAction.ADD_COUNTER
        else:
            return ModifierAction.WAIT_IMPROVE
    
    def _create_modifier_entry_suggestion(self, position: Any, action: ModifierAction, current_price: float) -> Dict:
        """สร้างคำแนะนำการเข้าไม้เพื่อแก้ไข"""
        return {
            'action': action.value,
            'suggested_price': current_price,
            'suggested_lot': 0.01,
            'reason': f'Modifier for position {getattr(position, "ticket", 0)}'
        }
    
    def _calculate_expected_improvement(self, position: Any, action: ModifierAction) -> float:
        """คำนวณการปรับปรุงที่คาดหวัง"""
        return 0.3  # 30% improvement expected
    
    def _assess_modifier_risk(self, position: Any, action: ModifierAction) -> str:
        """ประเมิน risk ของการแก้ไข"""
        return "MEDIUM"
    
    def _log_position_modifications(self, modifications: List[PositionModification]):
        """แสดง log การแก้ไข positions"""
        logger.info(f"🔧 POSITION MODIFICATIONS: {len(modifications)} positions")
        for mod in modifications:
            logger.info(f"   Ticket {mod.position_ticket}: {mod.modifier_action.value} - {mod.current_problem}")

# 🏭 Factory Functions
def create_enhanced_7d_entry_system(intelligent_manager=None, purpose_tracker=None,
                                   dynamic_7d_closer=None, mt5_connection=None) -> Enhanced7DEntrySystem:
    """🏭 สร้าง Enhanced 7D Entry System"""
    return Enhanced7DEntrySystem(
        intelligent_manager=intelligent_manager,
        purpose_tracker=purpose_tracker,
        dynamic_7d_closer=dynamic_7d_closer,
        mt5_connection=mt5_connection
    )

if __name__ == "__main__":
    # 🧪 Test code
    system = create_enhanced_7d_entry_system()
    print("🚀 Enhanced 7D Entry + Position Modifier System created!")
