# -*- coding: utf-8 -*-
"""
Zone Rebalancer & Smart Distribution System
ระบบปรับสมดุลโซนและกระจาย Orders อย่างชาญฉลาด
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
from calculations import Position
from price_zone_analysis import PriceZoneAnalyzer, ZoneAnalysisResult, SmartEntryRecommendation

logger = logging.getLogger(__name__)

class RebalanceAction(Enum):
    ADD_BUY = "ADD_BUY"
    ADD_SELL = "ADD_SELL"
    CLOSE_EXCESS = "CLOSE_EXCESS"
    MOVE_ORDER = "MOVE_ORDER"
    WAIT = "WAIT"

class RebalancePriority(Enum):
    CRITICAL = "CRITICAL"    # ต้องทำทันที
    HIGH = "HIGH"           # ควรทำเร็ว
    MEDIUM = "MEDIUM"       # ทำเมื่อมีโอกาส
    LOW = "LOW"             # ทำเมื่อสะดวก

@dataclass
class RebalanceRecommendation:
    action: RebalanceAction
    priority: RebalancePriority
    target_zone_id: int
    target_price_range: Tuple[float, float]
    order_type: str  # BUY, SELL
    suggested_volume: float
    confidence_score: float
    reason: str
    expected_improvement: float  # คาดว่าจะปรับปรุงคะแนนได้เท่าไหร่
    alternative_actions: List[Dict[str, Any]]

@dataclass
class RebalanceResult:
    total_recommendations: int
    critical_actions: int
    high_priority_actions: int
    expected_score_improvement: float
    estimated_time_to_balance: int  # นาที
    recommendations: List[RebalanceRecommendation]
    summary: str

class ZoneRebalancer:
    """ระบบปรับสมดุลโซนและกระจาย Orders"""
    
    def __init__(self, zone_analyzer: PriceZoneAnalyzer):
        self.zone_analyzer = zone_analyzer
        self.last_rebalance_time = None
        self.rebalance_history: List[Dict] = []
        
        # การตั้งค่า
        self.min_rebalance_interval = 300  # 5 นาที
        self.critical_imbalance_threshold = 0.8  # 80% ไม่สมดุลถือว่าวิกฤต
        self.target_balance_ratio = 0.6  # เป้าหมาย 60:40 ถือว่าสมดุลดี
        self.max_zone_density = 5  # Orders สูงสุดต่อโซน
        self.min_improvement_threshold = 5.0  # คะแนนขั้นต่ำที่ควรปรับปรุง
        
    def analyze_rebalance_needs(self, positions: List[Position], 
                              current_price: float) -> RebalanceResult:
        """วิเคราะห์ความต้องการในการปรับสมดุล"""
        try:
            # วิเคราะห์สถานะปัจจุบัน
            analysis = self.zone_analyzer.analyze_position_distribution(positions)
            
            if analysis.overall_health_score >= 80:
                return RebalanceResult(
                    total_recommendations=0,
                    critical_actions=0,
                    high_priority_actions=0,
                    expected_score_improvement=0.0,
                    estimated_time_to_balance=0,
                    recommendations=[],
                    summary="การกระจายดีเยี่ยม - ไม่ต้องปรับสมดุล"
                )
            
            # หาปัญหาและสร้างคำแนะนำ
            recommendations = []
            
            # 1. แก้ไขโซนวิกฤต
            critical_recs = self._handle_critical_zones(analysis, current_price)
            recommendations.extend(critical_recs)
            
            # 2. กรอกโซนว่าง
            fill_recs = self._handle_empty_zones(analysis, positions, current_price)
            recommendations.extend(fill_recs)
            
            # 3. ปรับสมดุลโซนที่ไม่สมดุล
            balance_recs = self._handle_imbalanced_zones(analysis, current_price)
            recommendations.extend(balance_recs)
            
            # 4. ลดความหนาแน่นโซนที่กระจุก
            density_recs = self._handle_high_density_zones(analysis, current_price)
            recommendations.extend(density_recs)
            
            # เรียงลำดับความสำคัญ
            recommendations.sort(key=lambda x: self._get_priority_score(x.priority), reverse=True)
            
            # คำนวณสถิติ
            result = self._compile_rebalance_result(recommendations, analysis)
            
            logger.info(f"🎯 วิเคราะห์การปรับสมดุล:")
            logger.info(f"   คะแนนปัจจุบัน: {analysis.overall_health_score:.1f}/100")
            logger.info(f"   คำแนะนำทั้งหมด: {result.total_recommendations}")
            logger.info(f"   การปรับปรุงคาดการณ์: +{result.expected_score_improvement:.1f}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing rebalance needs: {e}")
            return RebalanceResult(
                total_recommendations=0,
                critical_actions=0,
                high_priority_actions=0,
                expected_score_improvement=0.0,
                estimated_time_to_balance=0,
                recommendations=[],
                summary=f"เกิดข้อผิดพลาด: {str(e)}"
            )
    
    def _handle_critical_zones(self, analysis: ZoneAnalysisResult, 
                             current_price: float) -> List[RebalanceRecommendation]:
        """จัดการโซนวิกฤต"""
        recommendations = []
        
        try:
            for zone_id, zone in analysis.zone_map.items():
                if zone.zone_health.value != "CRITICAL":
                    continue
                
                total_orders = zone.buy_count + zone.sell_count
                if total_orders == 0:
                    continue  # โซนว่างไม่ใช่วิกฤต
                
                # หาทิศทางที่ขาด
                buy_ratio = zone.buy_count / total_orders
                sell_ratio = zone.sell_count / total_orders
                
                if buy_ratio > 0.8:  # กระจุก BUY
                    needed_action = RebalanceAction.ADD_SELL
                    order_type = "SELL"
                    imbalance = buy_ratio - 0.5
                elif sell_ratio > 0.8:  # กระจุก SELL
                    needed_action = RebalanceAction.ADD_BUY
                    order_type = "BUY"
                    imbalance = sell_ratio - 0.5
                else:
                    continue
                
                # คำนวณปริมาณที่ต้องเพิ่ม
                suggested_volume = self._calculate_rebalance_volume(zone, order_type)
                
                # คำนวณการปรับปรุงคาดการณ์
                expected_improvement = imbalance * 50  # ประมาณการ
                
                recommendation = RebalanceRecommendation(
                    action=needed_action,
                    priority=RebalancePriority.CRITICAL,
                    target_zone_id=zone_id,
                    target_price_range=(zone.price_min, zone.price_max),
                    order_type=order_type,
                    suggested_volume=suggested_volume,
                    confidence_score=90.0,
                    reason=f"โซนวิกฤต - กระจุก {order_type} {imbalance*100:.1f}%",
                    expected_improvement=expected_improvement,
                    alternative_actions=[]
                )
                
                recommendations.append(recommendation)
                
        except Exception as e:
            logger.error(f"Error handling critical zones: {e}")
        
        return recommendations
    
    def _handle_empty_zones(self, analysis: ZoneAnalysisResult, positions: List[Position],
                          current_price: float) -> List[RebalanceRecommendation]:
        """จัดการโซนว่าง"""
        recommendations = []
        
        try:
            if analysis.empty_zones <= 2:  # โซนว่างน้อยไม่เป็นปัญหา
                return recommendations
            
            # หาโซนว่างที่ควรกรอก
            empty_zones = [zone_id for zone_id, zone in analysis.zone_map.items()
                          if zone.buy_count + zone.sell_count == 0]
            
            # เลือกโซนที่ใกล้ราคาปัจจุบันหรือเป็น Hot zone
            priority_zones = []
            for zone_id in empty_zones:
                zone = analysis.zone_map[zone_id]
                distance_from_current = abs(zone.price_center - current_price)
                
                # คำนวณความสำคัญ
                if zone.zone_type.value == "HOT":
                    priority = RebalancePriority.HIGH
                    confidence = 80.0
                elif distance_from_current < 50:  # ใกล้ราคาปัจจุบัน
                    priority = RebalancePriority.MEDIUM
                    confidence = 70.0
                else:
                    priority = RebalancePriority.LOW
                    confidence = 60.0
                
                # ตัดสินใจทิศทาง - สลับกับโซนข้างเคียง
                adjacent_zones = self._get_adjacent_zones(zone_id, analysis.zone_map)
                suggested_direction = self._suggest_direction_for_empty_zone(
                    adjacent_zones, positions
                )
                
                suggested_volume = 0.01  # Volume เริ่มต้น
                
                recommendation = RebalanceRecommendation(
                    action=RebalanceAction.ADD_BUY if suggested_direction == "BUY" else RebalanceAction.ADD_SELL,
                    priority=priority,
                    target_zone_id=zone_id,
                    target_price_range=(zone.price_min, zone.price_max),
                    order_type=suggested_direction,
                    suggested_volume=suggested_volume,
                    confidence_score=confidence,
                    reason=f"กรอกโซนว่าง - ปรับปรุงการกระจาย",
                    expected_improvement=5.0,
                    alternative_actions=[]
                )
                
                priority_zones.append(recommendation)
            
            # เลือกแค่โซนที่สำคัญที่สุด 3 อัน
            priority_zones.sort(key=lambda x: self._get_priority_score(x.priority), reverse=True)
            recommendations.extend(priority_zones[:3])
            
        except Exception as e:
            logger.error(f"Error handling empty zones: {e}")
        
        return recommendations
    
    def _handle_imbalanced_zones(self, analysis: ZoneAnalysisResult,
                               current_price: float) -> List[RebalanceRecommendation]:
        """จัดการโซนที่ไม่สมดุล"""
        recommendations = []
        
        try:
            for zone_id, zone in analysis.zone_map.items():
                total_orders = zone.buy_count + zone.sell_count
                if total_orders <= 1:  # ไม่มีหรือมี order เดียวข้าม
                    continue
                
                buy_ratio = zone.buy_count / total_orders
                imbalance = abs(buy_ratio - 0.5)
                
                # ตรวจสอบว่าไม่สมดุลเกินเกณฑ์หรือไม่
                if imbalance < 0.3:  # สมดุลพอใช้
                    continue
                
                # กำหนดความสำคัญ
                if imbalance > 0.6:
                    priority = RebalancePriority.HIGH
                elif imbalance > 0.4:
                    priority = RebalancePriority.MEDIUM
                else:
                    priority = RebalancePriority.LOW
                
                # หาทิศทางที่ต้องเพิ่ม
                if buy_ratio > 0.6:
                    needed_action = RebalanceAction.ADD_SELL
                    order_type = "SELL"
                else:
                    needed_action = RebalanceAction.ADD_BUY
                    order_type = "BUY"
                
                suggested_volume = self._calculate_rebalance_volume(zone, order_type)
                expected_improvement = imbalance * 30
                
                recommendation = RebalanceRecommendation(
                    action=needed_action,
                    priority=priority,
                    target_zone_id=zone_id,
                    target_price_range=(zone.price_min, zone.price_max),
                    order_type=order_type,
                    suggested_volume=suggested_volume,
                    confidence_score=75.0,
                    reason=f"ปรับสมดุล - ไม่สมดุล {imbalance*100:.1f}%",
                    expected_improvement=expected_improvement,
                    alternative_actions=[]
                )
                
                recommendations.append(recommendation)
                
        except Exception as e:
            logger.error(f"Error handling imbalanced zones: {e}")
        
        return recommendations
    
    def _handle_high_density_zones(self, analysis: ZoneAnalysisResult,
                                 current_price: float) -> List[RebalanceRecommendation]:
        """จัดการโซนที่มีความหนาแน่นสูง"""
        recommendations = []
        
        try:
            for zone_id, zone in analysis.zone_map.items():
                total_orders = zone.buy_count + zone.sell_count
                if total_orders <= self.max_zone_density:
                    continue
                
                # โซนมี orders เยอะเกินไป
                excess_orders = total_orders - self.max_zone_density
                
                # แนะนำให้ปิดบางส่วน หรือ กระจายไปโซนอื่น
                recommendation = RebalanceRecommendation(
                    action=RebalanceAction.CLOSE_EXCESS,
                    priority=RebalancePriority.MEDIUM,
                    target_zone_id=zone_id,
                    target_price_range=(zone.price_min, zone.price_max),
                    order_type="MIXED",
                    suggested_volume=excess_orders * 0.01,  # ประมาณการ
                    confidence_score=65.0,
                    reason=f"ลดความหนาแน่น - เกิน {excess_orders} orders",
                    expected_improvement=10.0,
                    alternative_actions=[]
                )
                
                recommendations.append(recommendation)
                
        except Exception as e:
            logger.error(f"Error handling high density zones: {e}")
        
        return recommendations
    
    def _calculate_rebalance_volume(self, zone, order_type: str) -> float:
        """คำนวณปริมาณ volume ที่ควรเพิ่มเพื่อปรับสมดุล"""
        try:
            total_orders = zone.buy_count + zone.sell_count
            if total_orders == 0:
                return 0.01  # Volume เริ่มต้น
            
            # คำนวณจำนวนที่ต้องเพิ่มเพื่อให้สมดุล
            if order_type == "BUY":
                current_buy = zone.buy_count
                target_buy = (total_orders + 1) // 2
                needed = max(1, target_buy - current_buy)
            else:  # SELL
                current_sell = zone.sell_count
                target_sell = (total_orders + 1) // 2
                needed = max(1, target_sell - current_sell)
            
            # คำนวณ volume เฉลี่ย
            avg_volume = (zone.buy_volume + zone.sell_volume) / total_orders if total_orders > 0 else 0.01
            
            return max(0.01, min(avg_volume * needed, 0.1))  # จำกัดไม่เกิน 0.1
            
        except Exception as e:
            logger.error(f"Error calculating rebalance volume: {e}")
            return 0.01
    
    def _get_adjacent_zones(self, zone_id: int, zone_map: Dict) -> List[int]:
        """หาโซนข้างเคียง"""
        adjacent = []
        if zone_id - 1 in zone_map:
            adjacent.append(zone_id - 1)
        if zone_id + 1 in zone_map:
            adjacent.append(zone_id + 1)
        return adjacent
    
    def _suggest_direction_for_empty_zone(self, adjacent_zones: List[int], 
                                        positions: List[Position]) -> str:
        """แนะนำทิศทางสำหรับโซนว่าง"""
        try:
            if not adjacent_zones:
                # ถ้าไม่มีโซนข้างเคียง ดูจากสัดส่วนรวม
                total_buy = sum(1 for pos in positions if pos.type.upper() == 'BUY')
                total_sell = sum(1 for pos in positions if pos.type.upper() == 'SELL')
                
                return "SELL" if total_buy > total_sell else "BUY"
            
            # ดูจากโซนข้างเคียงแล้วเลือกทิศทางตรงข้าม
            adjacent_buy_count = 0
            adjacent_sell_count = 0
            
            for adj_zone_id in adjacent_zones:
                zone = self.zone_analyzer.zones.get(adj_zone_id)
                if zone:
                    adjacent_buy_count += zone.buy_count
                    adjacent_sell_count += zone.sell_count
            
            # เลือกทิศทางที่ขาด
            return "BUY" if adjacent_sell_count > adjacent_buy_count else "SELL"
            
        except Exception as e:
            logger.error(f"Error suggesting direction for empty zone: {e}")
            return "BUY"
    
    def _get_priority_score(self, priority: RebalancePriority) -> int:
        """แปลงความสำคัญเป็นคะแนน"""
        return {
            RebalancePriority.CRITICAL: 4,
            RebalancePriority.HIGH: 3,
            RebalancePriority.MEDIUM: 2,
            RebalancePriority.LOW: 1
        }.get(priority, 1)
    
    def _compile_rebalance_result(self, recommendations: List[RebalanceRecommendation],
                                analysis: ZoneAnalysisResult) -> RebalanceResult:
        """รวบรวมผลการวิเคราะห์"""
        try:
            total_recommendations = len(recommendations)
            critical_actions = sum(1 for rec in recommendations 
                                 if rec.priority == RebalancePriority.CRITICAL)
            high_priority_actions = sum(1 for rec in recommendations 
                                      if rec.priority == RebalancePriority.HIGH)
            
            expected_score_improvement = sum(rec.expected_improvement for rec in recommendations)
            
            # ประมาณเวลาในการปรับสมดุล
            estimated_time = critical_actions * 2 + high_priority_actions * 5  # นาที
            
            # สร้างสรุป
            if total_recommendations == 0:
                summary = "การกระจายดี - ไม่ต้องปรับสมดุล"
            elif critical_actions > 0:
                summary = f"ต้องปรับสมดุลด่วน - มี {critical_actions} การกระทำวิกฤต"
            elif high_priority_actions > 0:
                summary = f"ควรปรับสมดุล - มี {high_priority_actions} การกระทำสำคัญ"
            else:
                summary = f"ปรับสมดุลเมื่อสะดวก - มี {total_recommendations} คำแนะนำ"
            
            return RebalanceResult(
                total_recommendations=total_recommendations,
                critical_actions=critical_actions,
                high_priority_actions=high_priority_actions,
                expected_score_improvement=expected_score_improvement,
                estimated_time_to_balance=estimated_time,
                recommendations=recommendations,
                summary=summary
            )
            
        except Exception as e:
            logger.error(f"Error compiling rebalance result: {e}")
            return RebalanceResult(
                total_recommendations=0,
                critical_actions=0,
                high_priority_actions=0,
                expected_score_improvement=0.0,
                estimated_time_to_balance=0,
                recommendations=[],
                summary="เกิดข้อผิดพลาดในการวิเคราะห์"
            )
    
    def should_trigger_rebalance(self, analysis: ZoneAnalysisResult) -> bool:
        """ตรวจสอบว่าควร trigger การปรับสมดุลหรือไม่"""
        try:
            # เช็คเวลา
            if self.last_rebalance_time:
                time_since_last = (datetime.now() - self.last_rebalance_time).total_seconds()
                if time_since_last < self.min_rebalance_interval:
                    return False
            
            # เช็คเงื่อนไข trigger
            conditions_met = 0
            
            # 1. คะแนนรวมต่ำ
            if analysis.overall_health_score < 60:
                conditions_met += 1
            
            # 2. มีโซนวิกฤต
            if analysis.critical_zones > 0:
                conditions_met += 1
            
            # 3. โซนไม่สมดุลมาก
            if analysis.imbalanced_zones > analysis.total_zones * 0.5:
                conditions_met += 1
            
            # 4. โซนว่างมากเกินไป
            if analysis.empty_zones > analysis.total_zones * 0.4:
                conditions_met += 1
            
            # ต้องผ่านอย่างน้อย 2 เงื่อนไข
            should_trigger = conditions_met >= 2
            
            if should_trigger:
                logger.info(f"🎯 ควร trigger Rebalance ({conditions_met}/4 เงื่อนไข)")
            
            return should_trigger
            
        except Exception as e:
            logger.error(f"Error checking rebalance trigger: {e}")
            return False
    
    def get_rebalance_summary(self, result: RebalanceResult) -> str:
        """สร้างสรุปการปรับสมดุลแบบ readable"""
        try:
            if result.total_recommendations == 0:
                return "✅ การกระจายดีเยี่ยม - ไม่ต้องปรับสมดุล"
            
            lines = []
            lines.append(f"🎯 สรุปการปรับสมดุล:")
            lines.append(f"   📊 คำแนะนำทั้งหมด: {result.total_recommendations}")
            
            if result.critical_actions > 0:
                lines.append(f"   🚨 วิกฤต: {result.critical_actions} การกระทำ")
            
            if result.high_priority_actions > 0:
                lines.append(f"   ⚠️ สำคัญ: {result.high_priority_actions} การกระทำ")
            
            lines.append(f"   📈 คะแนนคาดการณ์: +{result.expected_score_improvement:.1f}")
            lines.append(f"   ⏱️ เวลาประมาณ: {result.estimated_time_to_balance} นาที")
            
            # แสดงคำแนะนำสำคัญ 3 อันดับแรก
            if result.recommendations:
                lines.append(f"   🎯 คำแนะนำสำคัญ:")
                for i, rec in enumerate(result.recommendations[:3], 1):
                    lines.append(f"      {i}. Zone {rec.target_zone_id}: {rec.action.value} "
                               f"({rec.priority.value}) - {rec.reason}")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"Error creating rebalance summary: {e}")
            return "❌ เกิดข้อผิดพลาดในการสร้างสรุป"
