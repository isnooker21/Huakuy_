# -*- coding: utf-8 -*-
"""
🧠 AI Learning System Module
โมดูลสำหรับ AI Learning System ที่เรียนรู้และปรับปรุงตัวเอง
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import numpy as np

from ai_position_intelligence import AIPositionIntelligence
from ai_entry_intelligence import AIEntryIntelligence

logger = logging.getLogger(__name__)

@dataclass
class LearningMetrics:
    """คลาสสำหรับเก็บ Learning Metrics"""
    metric_name: str
    current_value: float
    target_value: float
    improvement_rate: float  # % ต่อสัปดาห์
    confidence: float  # 0-100

@dataclass
class WeightAdjustment:
    """คลาสสำหรับเก็บการปรับน้ำหนัก"""
    weight_name: str
    old_value: float
    new_value: float
    adjustment_reason: str
    timestamp: datetime

class AILearningSystem:
    """🧠 AI Learning System ที่เรียนรู้และปรับปรุงตัวเอง"""
    
    def __init__(self, position_intelligence: AIPositionIntelligence, 
                 entry_intelligence: AIEntryIntelligence):
        self.position_intelligence = position_intelligence
        self.entry_intelligence = entry_intelligence
        
        # Learning parameters
        self.learning_rate = 0.01  # ความเร็วในการเรียนรู้
        self.min_learning_samples = 10  # จำนวนตัวอย่างขั้นต่ำก่อนเรียนรู้
        self.learning_interval_hours = 24  # เรียนรู้ทุก 24 ชั่วโมง
        self.last_learning_time = None
        
        # Learning history
        self.weight_adjustment_history = []
        self.performance_history = []
        
        # Learning targets
        self.target_metrics = {
            'position_accuracy': 75.0,  # เป้าหมายความแม่นยำ 75%
            'entry_accuracy': 70.0,     # เป้าหมายความแม่นยำ 70%
            'profit_improvement': 20.0, # เป้าหมายกำไรเพิ่มขึ้น 20%
            'decision_speed': 100.0     # เป้าหมายความเร็ว < 100ms
        }
        
        # Learning weights
        self.learning_weights = {
            'recent_performance': 0.6,  # ผลลัพธ์ล่าสุด 60%
            'historical_performance': 0.3,  # ผลลัพธ์ในอดีต 30%
            'market_conditions': 0.1    # สภาวะตลาด 10%
        }
    
    def learn_from_outcomes(self, decision_type: str, outcomes: List[Dict]):
        """
        เรียนรู้จากผลลัพธ์การตัดสินใจ
        
        Args:
            decision_type: ประเภทการตัดสินใจ ("ENTRY" หรือ "CLOSE")
            outcomes: รายการผลลัพธ์
        """
        try:
            logger.info(f"🧠 Learning from {len(outcomes)} {decision_type} outcomes")
            
            # ตรวจสอบจำนวนตัวอย่าง
            if len(outcomes) < self.min_learning_samples:
                logger.debug(f"🧠 Not enough samples for learning: {len(outcomes)} < {self.min_learning_samples}")
                return
            
            # เรียนรู้ตามประเภท
            if decision_type == "ENTRY":
                self._learn_from_entry_outcomes(outcomes)
            elif decision_type == "CLOSE":
                self._learn_from_closing_outcomes(outcomes)
            
            # บันทึกเวลาการเรียนรู้ล่าสุด
            self.last_learning_time = datetime.now()
            
            # บันทึก AI Brains
            self.position_intelligence.save_ai_brain()
            self.entry_intelligence.save_ai_brain()
            
            logger.info(f"🧠 Learning completed for {decision_type} decisions")
            
        except Exception as e:
            logger.error(f"❌ Error in learning from outcomes: {e}")
    
    def _learn_from_entry_outcomes(self, outcomes: List[Dict]):
        """เรียนรู้จากผลลัพธ์การเข้าไม้"""
        try:
            # คำนวณ success rate
            successful_entries = sum(1 for outcome in outcomes if outcome.get('success', False))
            success_rate = successful_entries / len(outcomes) if outcomes else 0
            
            # คำนวณ average profit
            total_profit = sum(outcome.get('profit', 0) for outcome in outcomes)
            average_profit = total_profit / len(outcomes) if outcomes else 0
            
            logger.info(f"🧠 Entry Learning: Success Rate: {success_rate:.2%}, Avg Profit: ${average_profit:.2f}")
            
            # ปรับน้ำหนักตามผลลัพธ์
            if success_rate >= 0.7:  # Success rate ดี
                self._adjust_entry_weights_positive(outcomes)
            elif success_rate <= 0.4:  # Success rate แย่
                self._adjust_entry_weights_negative(outcomes)
            
            # ปรับน้ำหนักตามกำไร
            if average_profit > 10:  # กำไรมาก
                self._adjust_entry_weights_for_profit(outcomes)
            
            # บันทึก performance
            self.performance_history.append({
                'timestamp': datetime.now().isoformat(),
                'type': 'entry',
                'success_rate': success_rate,
                'average_profit': average_profit,
                'sample_count': len(outcomes)
            })
            
        except Exception as e:
            logger.error(f"❌ Error learning from entry outcomes: {e}")
    
    def _learn_from_closing_outcomes(self, outcomes: List[Dict]):
        """เรียนรู้จากผลลัพธ์การปิดไม้"""
        try:
            # คำนวณ success rate
            successful_closings = sum(1 for outcome in outcomes if outcome.get('success', False))
            success_rate = successful_closings / len(outcomes) if outcomes else 0
            
            # คำนวณ average profit
            total_profit = sum(outcome.get('profit', 0) for outcome in outcomes)
            average_profit = total_profit / len(outcomes) if outcomes else 0
            
            logger.info(f"🧠 Closing Learning: Success Rate: {success_rate:.2%}, Avg Profit: ${average_profit:.2f}")
            
            # ปรับน้ำหนักตามผลลัพธ์
            if success_rate >= 0.75:  # Success rate ดี
                self._adjust_position_weights_positive(outcomes)
            elif success_rate <= 0.45:  # Success rate แย่
                self._adjust_position_weights_negative(outcomes)
            
            # ปรับน้ำหนักตามกำไร
            if average_profit > 5:  # กำไรมาก
                self._adjust_position_weights_for_profit(outcomes)
            
            # บันทึก performance
            self.performance_history.append({
                'timestamp': datetime.now().isoformat(),
                'type': 'closing',
                'success_rate': success_rate,
                'average_profit': average_profit,
                'sample_count': len(outcomes)
            })
            
        except Exception as e:
            logger.error(f"❌ Error learning from closing outcomes: {e}")
    
    def _adjust_entry_weights_positive(self, outcomes: List[Dict]):
        """ปรับน้ำหนัก Entry ตามผลลัพธ์ที่ดี"""
        try:
            # วิเคราะห์ปัจจัยที่ทำให้สำเร็จ
            high_profit_outcomes = [o for o in outcomes if o.get('profit', 0) > 20]
            
            if high_profit_outcomes:
                # เพิ่มน้ำหนักของปัจจัยที่ทำให้กำไรมาก
                self.entry_intelligence.weights['zone_quality_weight'] += self.learning_rate
                self.entry_intelligence.weights['timing_weight'] += self.learning_rate * 0.5
                
                # ลดน้ำหนักของปัจจัยอื่น
                self.entry_intelligence.weights['portfolio_impact_weight'] -= self.learning_rate * 0.5
                
                # ปรับน้ำหนัก Zone Quality
                self.entry_intelligence.zone_weights['strength_weight'] += self.learning_rate
                
                self._record_weight_adjustment('entry_positive', {
                    'zone_quality_weight': self.learning_rate,
                    'timing_weight': self.learning_rate * 0.5,
                    'strength_weight': self.learning_rate
                })
                
                logger.info("🧠 Entry weights adjusted positively")
            
        except Exception as e:
            logger.error(f"❌ Error adjusting entry weights positively: {e}")
    
    def _adjust_entry_weights_negative(self, outcomes: List[Dict]):
        """ปรับน้ำหนัก Entry ตามผลลัพธ์ที่ไม่ดี"""
        try:
            # วิเคราะห์ปัจจัยที่ทำให้ล้มเหลว
            negative_profit_outcomes = [o for o in outcomes if o.get('profit', 0) < -10]
            
            if negative_profit_outcomes:
                # ลดน้ำหนักของปัจจัยที่ทำให้ขาดทุน
                self.entry_intelligence.weights['market_context_weight'] -= self.learning_rate
                self.entry_intelligence.weights['timing_weight'] -= self.learning_rate * 0.5
                
                # เพิ่มน้ำหนักของปัจจัยที่ปลอดภัยกว่า
                self.entry_intelligence.weights['portfolio_impact_weight'] += self.learning_rate
                
                # ปรับน้ำหนัก Zone Quality
                self.entry_intelligence.zone_weights['freshness_weight'] += self.learning_rate
                
                self._record_weight_adjustment('entry_negative', {
                    'market_context_weight': -self.learning_rate,
                    'timing_weight': -self.learning_rate * 0.5,
                    'freshness_weight': self.learning_rate
                })
                
                logger.info("🧠 Entry weights adjusted negatively")
            
        except Exception as e:
            logger.error(f"❌ Error adjusting entry weights negatively: {e}")
    
    def _adjust_position_weights_positive(self, outcomes: List[Dict]):
        """ปรับน้ำหนัก Position ตามผลลัพธ์ที่ดี"""
        try:
            # วิเคราะห์ปัจจัยที่ทำให้ปิดไม้สำเร็จ
            high_profit_outcomes = [o for o in outcomes if o.get('profit', 0) > 10]
            
            if high_profit_outcomes:
                # เพิ่มน้ำหนักของปัจจัยที่ทำให้ปิดไม้ได้ดี
                self.position_intelligence.weights['pnl_weight'] += self.learning_rate
                self.position_intelligence.weights['time_weight'] += self.learning_rate * 0.5
                
                # ลดน้ำหนักของปัจจัยอื่น
                self.position_intelligence.weights['distance_weight'] -= self.learning_rate * 0.3
                
                self._record_weight_adjustment('position_positive', {
                    'pnl_weight': self.learning_rate,
                    'time_weight': self.learning_rate * 0.5,
                    'distance_weight': -self.learning_rate * 0.3
                })
                
                logger.info("🧠 Position weights adjusted positively")
            
        except Exception as e:
            logger.error(f"❌ Error adjusting position weights positively: {e}")
    
    def _adjust_position_weights_negative(self, outcomes: List[Dict]):
        """ปรับน้ำหนัก Position ตามผลลัพธ์ที่ไม่ดี"""
        try:
            # วิเคราะห์ปัจจัยที่ทำให้ปิดไม้ไม่สำเร็จ
            negative_profit_outcomes = [o for o in outcomes if o.get('profit', 0) < -5]
            
            if negative_profit_outcomes:
                # ลดน้ำหนักของปัจจัยที่ทำให้ปิดไม้ผิด
                self.position_intelligence.weights['balance_weight'] -= self.learning_rate
                self.position_intelligence.weights['market_context_weight'] -= self.learning_rate * 0.5
                
                # เพิ่มน้ำหนักของปัจจัยที่ปลอดภัยกว่า
                self.position_intelligence.weights['time_weight'] += self.learning_rate * 0.5
                
                self._record_weight_adjustment('position_negative', {
                    'balance_weight': -self.learning_rate,
                    'market_context_weight': -self.learning_rate * 0.5,
                    'time_weight': self.learning_rate * 0.5
                })
                
                logger.info("🧠 Position weights adjusted negatively")
            
        except Exception as e:
            logger.error(f"❌ Error adjusting position weights negatively: {e}")
    
    def _adjust_entry_weights_for_profit(self, outcomes: List[Dict]):
        """ปรับน้ำหนัก Entry ตามกำไร"""
        try:
            # วิเคราะห์ปัจจัยที่ทำให้กำไรมาก
            very_high_profit_outcomes = [o for o in outcomes if o.get('profit', 0) > 50]
            
            if very_high_profit_outcomes:
                # เพิ่มน้ำหนักของปัจจัยที่ทำให้กำไรมาก
                self.entry_intelligence.weights['zone_quality_weight'] += self.learning_rate * 1.5
                self.entry_intelligence.zone_weights['strength_weight'] += self.learning_rate * 1.5
                
                self._record_weight_adjustment('entry_profit', {
                    'zone_quality_weight': self.learning_rate * 1.5,
                    'strength_weight': self.learning_rate * 1.5
                })
                
                logger.info("🧠 Entry weights adjusted for high profit")
            
        except Exception as e:
            logger.error(f"❌ Error adjusting entry weights for profit: {e}")
    
    def _adjust_position_weights_for_profit(self, outcomes: List[Dict]):
        """ปรับน้ำหนัก Position ตามกำไร"""
        try:
            # วิเคราะห์ปัจจัยที่ทำให้ปิดไม้ได้กำไรมาก
            very_high_profit_outcomes = [o for o in outcomes if o.get('profit', 0) > 25]
            
            if very_high_profit_outcomes:
                # เพิ่มน้ำหนักของปัจจัยที่ทำให้ปิดไม้ได้กำไรมาก
                self.position_intelligence.weights['pnl_weight'] += self.learning_rate * 1.5
                self.position_intelligence.weights['time_weight'] += self.learning_rate * 1.0
                
                self._record_weight_adjustment('position_profit', {
                    'pnl_weight': self.learning_rate * 1.5,
                    'time_weight': self.learning_rate * 1.0
                })
                
                logger.info("🧠 Position weights adjusted for high profit")
            
        except Exception as e:
            logger.error(f"❌ Error adjusting position weights for profit: {e}")
    
    def _record_weight_adjustment(self, adjustment_type: str, adjustments: Dict[str, float]):
        """บันทึกการปรับน้ำหนัก"""
        try:
            for weight_name, adjustment in adjustments.items():
                weight_adjustment = WeightAdjustment(
                    weight_name=weight_name,
                    old_value=0.0,  # จะต้องเก็บค่าเก่าไว้
                    new_value=adjustment,
                    adjustment_reason=adjustment_type,
                    timestamp=datetime.now()
                )
                self.weight_adjustment_history.append(weight_adjustment)
            
        except Exception as e:
            logger.error(f"❌ Error recording weight adjustment: {e}")
    
    def normalize_weights(self):
        """ทำให้น้ำหนักรวมเป็น 1.0"""
        try:
            # Normalize Entry Weights
            entry_total = sum(self.entry_intelligence.weights.values())
            if entry_total > 0:
                for key in self.entry_intelligence.weights:
                    self.entry_intelligence.weights[key] /= entry_total
            
            # Normalize Zone Weights
            zone_total = sum(self.entry_intelligence.zone_weights.values())
            if zone_total > 0:
                for key in self.entry_intelligence.zone_weights:
                    self.entry_intelligence.zone_weights[key] /= zone_total
            
            # Normalize Position Weights
            position_total = sum(self.position_intelligence.weights.values())
            if position_total > 0:
                for key in self.position_intelligence.weights:
                    self.position_intelligence.weights[key] /= position_total
            
            logger.info("🧠 Weights normalized")
            
        except Exception as e:
            logger.error(f"❌ Error normalizing weights: {e}")
    
    def should_learn_now(self) -> bool:
        """ตรวจสอบว่าควรเรียนรู้ตอนนี้หรือไม่"""
        try:
            if self.last_learning_time is None:
                return True
            
            time_since_last_learning = datetime.now() - self.last_learning_time
            return time_since_last_learning.total_seconds() >= (self.learning_interval_hours * 3600)
            
        except Exception as e:
            logger.error(f"❌ Error checking if should learn: {e}")
            return False
    
    def get_learning_metrics(self) -> List[LearningMetrics]:
        """ดึง Learning Metrics"""
        try:
            metrics = []
            
            # Position Intelligence Metrics
            position_stats = self.position_intelligence.get_ai_stats()
            position_accuracy = position_stats.get('accuracy_rate', 0) * 100
            
            metrics.append(LearningMetrics(
                metric_name="Position Accuracy",
                current_value=position_accuracy,
                target_value=self.target_metrics['position_accuracy'],
                improvement_rate=self._calculate_improvement_rate('position_accuracy', position_accuracy),
                confidence=self._calculate_confidence('position', position_stats)
            ))
            
            # Entry Intelligence Metrics
            entry_stats = self.entry_intelligence.get_ai_stats()
            entry_accuracy = entry_stats.get('accuracy_rate', 0) * 100
            
            metrics.append(LearningMetrics(
                metric_name="Entry Accuracy",
                current_value=entry_accuracy,
                target_value=self.target_metrics['entry_accuracy'],
                improvement_rate=self._calculate_improvement_rate('entry_accuracy', entry_accuracy),
                confidence=self._calculate_confidence('entry', entry_stats)
            ))
            
            # Profit Improvement
            total_profit = position_stats.get('total_profit', 0) + entry_stats.get('total_profit', 0)
            profit_improvement = self._calculate_profit_improvement(total_profit)
            
            metrics.append(LearningMetrics(
                metric_name="Profit Improvement",
                current_value=profit_improvement,
                target_value=self.target_metrics['profit_improvement'],
                improvement_rate=self._calculate_improvement_rate('profit', profit_improvement),
                confidence=self._calculate_confidence('profit', {'total_profit': total_profit})
            ))
            
            return metrics
            
        except Exception as e:
            logger.error(f"❌ Error getting learning metrics: {e}")
            return []
    
    def _calculate_improvement_rate(self, metric_name: str, current_value: float) -> float:
        """คำนวณอัตราการปรับปรุง"""
        try:
            # ใช้ข้อมูลจาก performance_history
            recent_performance = [p for p in self.performance_history 
                                if (datetime.now() - datetime.fromisoformat(p['timestamp'])).days <= 7]
            
            if not recent_performance:
                return 0.0
            
            # คำนวณการปรับปรุงในช่วง 7 วันที่ผ่านมา
            if metric_name in ['position_accuracy', 'entry_accuracy']:
                values = [p.get('success_rate', 0) * 100 for p in recent_performance]
            elif metric_name == 'profit':
                values = [p.get('average_profit', 0) for p in recent_performance]
            else:
                return 0.0
            
            if len(values) < 2:
                return 0.0
            
            # คำนวณการเปลี่ยนแปลงต่อสัปดาห์
            improvement = (values[-1] - values[0]) / len(values) * 7
            return improvement
            
        except Exception as e:
            logger.error(f"❌ Error calculating improvement rate: {e}")
            return 0.0
    
    def _calculate_confidence(self, intelligence_type: str, stats: Dict) -> float:
        """คำนวณความมั่นใจ"""
        try:
            if intelligence_type == 'position':
                total_decisions = stats.get('total_decisions', 0)
                accuracy = stats.get('accuracy_rate', 0)
            elif intelligence_type == 'entry':
                total_decisions = stats.get('total_entries', 0)
                accuracy = stats.get('accuracy_rate', 0)
            elif intelligence_type == 'profit':
                total_profit = stats.get('total_profit', 0)
                return min(100.0, total_profit / 100 * 10)  # $100 = 10% confidence
            else:
                return 50.0
            
            # ความมั่นใจขึ้นกับจำนวนการตัดสินใจและความแม่นยำ
            sample_confidence = min(100.0, total_decisions * 2)  # 50 decisions = 100% sample confidence
            accuracy_confidence = accuracy * 100
            
            return (sample_confidence + accuracy_confidence) / 2
            
        except Exception as e:
            logger.error(f"❌ Error calculating confidence: {e}")
            return 50.0
    
    def _calculate_profit_improvement(self, total_profit: float) -> float:
        """คำนวณการปรับปรุงกำไร"""
        try:
            # คำนวณเปอร์เซ็นต์การปรับปรุงจาก baseline
            baseline_profit = 1000  # Baseline profit
            improvement = ((total_profit - baseline_profit) / baseline_profit) * 100
            return max(0.0, improvement)
            
        except Exception as e:
            logger.error(f"❌ Error calculating profit improvement: {e}")
            return 0.0
    
    def get_learning_summary(self) -> Dict[str, Any]:
        """ดึงสรุปการเรียนรู้"""
        try:
            metrics = self.get_learning_metrics()
            
            return {
                'learning_metrics': [
                    {
                        'name': m.metric_name,
                        'current': m.current_value,
                        'target': m.target_value,
                        'improvement_rate': m.improvement_rate,
                        'confidence': m.confidence
                    } for m in metrics
                ],
                'weight_adjustments': len(self.weight_adjustment_history),
                'performance_history': len(self.performance_history),
                'last_learning_time': self.last_learning_time.isoformat() if self.last_learning_time else None,
                'should_learn_now': self.should_learn_now(),
                'learning_rate': self.learning_rate
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting learning summary: {e}")
            return {}
    
    def save_learning_data(self, filename: str = "ai_learning_data.json"):
        """บันทึกข้อมูลการเรียนรู้"""
        try:
            learning_data = {
                'learning_rate': self.learning_rate,
                'min_learning_samples': self.min_learning_samples,
                'learning_interval_hours': self.learning_interval_hours,
                'target_metrics': self.target_metrics,
                'learning_weights': self.learning_weights,
                'weight_adjustment_history': [
                    {
                        'weight_name': wa.weight_name,
                        'old_value': wa.old_value,
                        'new_value': wa.new_value,
                        'adjustment_reason': wa.adjustment_reason,
                        'timestamp': wa.timestamp.isoformat()
                    } for wa in self.weight_adjustment_history[-50:]  # เก็บ 50 รายการล่าสุด
                ],
                'performance_history': self.performance_history[-100:],  # เก็บ 100 รายการล่าสุด
                'last_learning_time': self.last_learning_time.isoformat() if self.last_learning_time else None
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(learning_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"🧠 Learning data saved to {filename}")
            
        except Exception as e:
            logger.error(f"❌ Error saving learning data: {e}")
    
    def load_learning_data(self, filename: str = "ai_learning_data.json"):
        """โหลดข้อมูลการเรียนรู้"""
        try:
            import os
            if not os.path.exists(filename):
                logger.info("🧠 No existing learning data found - Starting fresh")
                return
            
            with open(filename, 'r', encoding='utf-8') as f:
                learning_data = json.load(f)
            
            # โหลด parameters
            self.learning_rate = learning_data.get('learning_rate', 0.01)
            self.min_learning_samples = learning_data.get('min_learning_samples', 10)
            self.learning_interval_hours = learning_data.get('learning_interval_hours', 24)
            self.target_metrics = learning_data.get('target_metrics', self.target_metrics)
            self.learning_weights = learning_data.get('learning_weights', self.learning_weights)
            
            # โหลด history
            if 'weight_adjustment_history' in learning_data:
                self.weight_adjustment_history = [
                    WeightAdjustment(
                        weight_name=wa['weight_name'],
                        old_value=wa['old_value'],
                        new_value=wa['new_value'],
                        adjustment_reason=wa['adjustment_reason'],
                        timestamp=datetime.fromisoformat(wa['timestamp'])
                    ) for wa in learning_data['weight_adjustment_history']
                ]
            
            if 'performance_history' in learning_data:
                self.performance_history = learning_data['performance_history']
            
            if 'last_learning_time' in learning_data and learning_data['last_learning_time']:
                self.last_learning_time = datetime.fromisoformat(learning_data['last_learning_time'])
            
            logger.info(f"🧠 Learning data loaded from {filename}")
            
        except Exception as e:
            logger.error(f"❌ Error loading learning data: {e}")
    
    def start_learning(self):
        """เริ่มการเรียนรู้"""
        try:
            self.is_learning = True
            logger.info("🧠 AI Learning started")
        except Exception as e:
            logger.error(f"❌ Error starting AI learning: {e}")
    
    def stop_learning(self):
        """หยุดการเรียนรู้"""
        try:
            self.is_learning = False
            logger.info("🧠 AI Learning stopped")
        except Exception as e:
            logger.error(f"❌ Error stopping AI learning: {e}")
