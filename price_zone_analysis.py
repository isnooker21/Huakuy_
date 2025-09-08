# -*- coding: utf-8 -*-
"""
Price Zone Analysis & Smart Distribution System
ระบบวิเคราะห์โซนราคาและการกระจายตัว Orders อย่างชาญฉลาด
"""

import logging
import MetaTrader5 as mt5
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import math
from calculations import Position

logger = logging.getLogger(__name__)

class ZoneHealth(Enum):
    EXCELLENT = "EXCELLENT"    # สมดุลดี 80-100%
    GOOD = "GOOD"             # สมดุลพอใช้ 60-79%
    FAIR = "FAIR"             # ไม่สมดุลเล็กน้อย 40-59%
    POOR = "POOR"             # ไม่สมดุลมาก 20-39%
    CRITICAL = "CRITICAL"     # วิกฤต 0-19%

class ZoneType(Enum):
    HOT = "HOT"               # โซนที่ราคาผ่านบ่อย
    NORMAL = "NORMAL"         # โซนปกติ
    DEAD = "DEAD"             # โซนที่ราคาไม่ค่อยแตะ
    SUPPORT = "SUPPORT"       # โซน Support
    RESISTANCE = "RESISTANCE" # โซน Resistance

@dataclass
class PriceZone:
    zone_id: int
    price_min: float
    price_max: float
    price_center: float
    buy_orders: List[Position] = field(default_factory=list)
    sell_orders: List[Position] = field(default_factory=list)
    buy_count: int = 0
    sell_count: int = 0
    buy_volume: float = 0.0
    sell_volume: float = 0.0
    total_profit: float = 0.0
    zone_type: ZoneType = ZoneType.NORMAL
    zone_health: ZoneHealth = ZoneHealth.EXCELLENT
    balance_score: float = 100.0
    last_price_visit: Optional[datetime] = None
    visit_frequency: int = 0

@dataclass
class ZoneAnalysisResult:
    total_zones: int
    active_zones: int
    empty_zones: int
    balanced_zones: int
    imbalanced_zones: int
    critical_zones: int
    overall_health_score: float
    distribution_quality: str
    recommendations: List[str]
    zone_map: Dict[int, PriceZone]

@dataclass
class SmartEntryRecommendation:
    recommended_action: str  # BUY, SELL, WAIT
    target_zone_id: int
    target_price_range: Tuple[float, float]
    confidence_score: float
    reason: str
    alternative_zones: List[int]
    lot_size_multiplier: float

class PriceZoneAnalyzer:
    """ระบบวิเคราะห์โซนราคาและการกระจายตัว"""
    
    def __init__(self, symbol: str = "XAUUSD", num_zones: int = 10, zone_width_pips: float = None):
        self.symbol = symbol
        self.num_zones = num_zones
        self.zone_width_pips = zone_width_pips or self._calculate_dynamic_zone_width()
        self.zones: Dict[int, PriceZone] = {}
        self.price_history: List[Tuple[datetime, float]] = []
        self.last_analysis_time = None
        
        # การตั้งค่า
        self.balance_threshold = 0.3  # 30% ความแตกต่างถือว่าไม่สมดุล
        self.critical_threshold = 0.7  # 70% ความแตกต่างถือว่าวิกฤต
        self.min_visit_frequency = 5    # ความถี่ขั้นต่ำถือว่า Hot Zone
        self.dead_zone_hours = 24      # ไม่มีราคาผ่านเกิน 24 ชม. = Dead Zone
        
    def _calculate_dynamic_zone_width(self) -> float:
        """คำนวณความกว้างโซนแบบ Dynamic ตาม volatility"""
        try:
            # ดึงข้อมูล ATR (Average True Range) ย้อนหลัง 20 แท่ง
            rates = mt5.copy_rates_from_pos(self.symbol, mt5.TIMEFRAME_H1, 0, 20)
            if rates is None or len(rates) == 0:
                return 20.0  # Default 20 pips สำหรับ XAUUSD
            
            # คำนวณ ATR
            atr_values = []
            for i in range(1, len(rates)):
                high_low = rates[i]['high'] - rates[i]['low']
                high_close = abs(rates[i]['high'] - rates[i-1]['close'])
                low_close = abs(rates[i]['low'] - rates[i-1]['close'])
                true_range = max(high_low, high_close, low_close)
                atr_values.append(true_range)
            
            avg_atr = sum(atr_values) / len(atr_values) if atr_values else 20.0
            
            # แปลงเป็น pips และปรับขนาดโซน
            if 'XAU' in self.symbol.upper():
                zone_width = (avg_atr / 0.1) * 0.5  # XAUUSD: ครึ่งหนึ่งของ ATR
            else:
                zone_width = (avg_atr / 0.0001) * 0.3  # Forex: 30% ของ ATR
            
            # จำกัดขนาดโซน
            return max(10.0, min(zone_width, 50.0))
            
        except Exception as e:
            logger.error(f"Error calculating dynamic zone width: {e}")
            return 20.0
    
    def initialize_zones(self, current_price: float, price_range_factor: float = 2.0) -> None:
        """สร้างโซนราคาเริ่มต้นรอบๆ ราคาปัจจุบัน"""
        try:
            # คำนวณช่วงราคาที่จะแบ่งโซน
            if 'XAU' in self.symbol.upper():
                pip_value = 0.1  # XAUUSD
            else:
                pip_value = 0.0001  # Forex
            
            zone_width_price = self.zone_width_pips * pip_value
            total_range = zone_width_price * self.num_zones * price_range_factor
            
            # กำหนดราคาเริ่มต้นและสิ้นสุด
            range_start = current_price - (total_range / 2)
            range_end = current_price + (total_range / 2)
            
            # สร้างโซน
            self.zones.clear()
            for i in range(self.num_zones):
                zone_min = range_start + (i * zone_width_price)
                zone_max = zone_min + zone_width_price
                zone_center = (zone_min + zone_max) / 2
                
                self.zones[i] = PriceZone(
                    zone_id=i,
                    price_min=zone_min,
                    price_max=zone_max,
                    price_center=zone_center
                )
            
            logger.info(f"🏗️ สร้างโซนราคา {self.num_zones} โซน")
            logger.info(f"   ช่วงราคา: {range_start:.2f} - {range_end:.2f}")
            logger.info(f"   ความกว้างโซน: {self.zone_width_pips:.1f} pips")
            logger.info(f"   ราคาปัจจุบัน: {current_price:.2f}")
            
        except Exception as e:
            logger.error(f"Error initializing zones: {e}")
    
    def update_price_history(self, price: float) -> None:
        """อัพเดทประวัติราคาสำหรับการวิเคราะห์"""
        try:
            current_time = datetime.now()
            self.price_history.append((current_time, price))
            
            # เก็บข้อมูลแค่ 24 ชั่วโมง
            cutoff_time = current_time - timedelta(hours=24)
            self.price_history = [
                (time, p) for time, p in self.price_history 
                if time > cutoff_time
            ]
            
            # อัพเดทการเยี่ยมชมโซน
            self._update_zone_visits(price, current_time)
            
        except Exception as e:
            logger.error(f"Error updating price history: {e}")
    
    def _update_zone_visits(self, price: float, timestamp: datetime) -> None:
        """อัพเดทการเยี่ยมชมโซนจากราคา"""
        try:
            for zone in self.zones.values():
                if zone.price_min <= price <= zone.price_max:
                    zone.last_price_visit = timestamp
                    zone.visit_frequency += 1
                    break
        except Exception as e:
            logger.error(f"Error updating zone visits: {e}")
    
    def classify_zones(self) -> None:
        """จำแนกประเภทโซนตามการเยี่ยมชมและพฤติกรรม"""
        try:
            current_time = datetime.now()
            
            for zone in self.zones.values():
                # ตรวจสอบ Dead Zone
                if zone.last_price_visit is None:
                    zone.zone_type = ZoneType.DEAD
                else:
                    time_since_visit = (current_time - zone.last_price_visit).total_seconds() / 3600
                    
                    if time_since_visit > self.dead_zone_hours:
                        zone.zone_type = ZoneType.DEAD
                    elif zone.visit_frequency >= self.min_visit_frequency:
                        zone.zone_type = ZoneType.HOT
                    else:
                        zone.zone_type = ZoneType.NORMAL
                
                # TODO: เพิ่มการตรวจสอบ Support/Resistance ในอนาคต
                # ใช้ข้อมูลประวัติราคาเพื่อหา S/R levels
                
        except Exception as e:
            logger.error(f"Error classifying zones: {e}")
    
    def analyze_position_distribution(self, positions: List[Position]) -> ZoneAnalysisResult:
        """วิเคราะห์การกระจายตัวของ Positions ในแต่ละโซน"""
        try:
            if not self.zones:
                logger.info("🎯 เริ่มต้นระบบ Zone: สร้างโซนอัตโนมัติจากราคาปัจจุบัน")
                current_price = positions[0].price_open if positions else 2000.0
                self.initialize_zones(current_price)
            
            # รีเซ็ตข้อมูลโซน
            for zone in self.zones.values():
                zone.buy_orders.clear()
                zone.sell_orders.clear()
                zone.buy_count = 0
                zone.sell_count = 0
                zone.buy_volume = 0.0
                zone.sell_volume = 0.0
                zone.total_profit = 0.0
            
            # จัดกลุ่ม Positions เข้าโซน
            for position in positions:
                zone_id = self._find_zone_for_price(position.price_open)
                if zone_id is not None:
                    zone = self.zones[zone_id]
                    
                    if position.type == 0:  # BUY
                        zone.buy_orders.append(position)
                        zone.buy_count += 1
                        zone.buy_volume += position.volume
                    else:  # SELL (type == 1)
                        zone.sell_orders.append(position)
                        zone.sell_count += 1
                        zone.sell_volume += position.volume
                    
                    zone.total_profit += position.profit
            
            # คำนวณคะแนนสมดุลแต่ละโซน
            self._calculate_zone_balance_scores()
            
            # จำแนกประเภทโซน
            self.classify_zones()
            
            # สร้างผลการวิเคราะห์
            result = self._generate_analysis_result()
            
            self.last_analysis_time = datetime.now()
            
            logger.info(f"📊 วิเคราะห์การกระจาย {len(positions)} Positions")
            logger.info(f"   คะแนนรวม: {result.overall_health_score:.1f}/100")
            logger.info(f"   โซนสมดุล: {result.balanced_zones}/{result.total_zones}")
            logger.info(f"   โซนวิกฤต: {result.critical_zones}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing position distribution: {e}")
            return self._create_empty_result()
    
    def _find_zone_for_price(self, price: float) -> Optional[int]:
        """หาโซนที่เหมาะสมสำหรับราคาที่กำหนด"""
        try:
            for zone_id, zone in self.zones.items():
                if zone.price_min <= price <= zone.price_max:
                    return zone_id
            
            # ถ้าไม่อยู่ในโซนใดๆ ให้หาโซนที่ใกล้ที่สุด
            closest_zone_id = None
            min_distance = float('inf')
            
            for zone_id, zone in self.zones.items():
                distance = min(
                    abs(price - zone.price_min),
                    abs(price - zone.price_max),
                    abs(price - zone.price_center)
                )
                
                if distance < min_distance:
                    min_distance = distance
                    closest_zone_id = zone_id
            
            return closest_zone_id
            
        except Exception as e:
            logger.error(f"Error finding zone for price {price}: {e}")
            return None
    
    def _calculate_zone_balance_scores(self) -> None:
        """คำนวณคะแนนสมดุลของแต่ละโซน"""
        try:
            for zone in self.zones.values():
                total_orders = zone.buy_count + zone.sell_count
                
                if total_orders == 0:
                    # โซนว่าง - ถือว่าสมดุลดี
                    zone.balance_score = 100.0
                    zone.zone_health = ZoneHealth.EXCELLENT
                elif total_orders == 1:
                    # มี order เดียว - ถือว่าสมดุลพอใช้
                    zone.balance_score = 70.0
                    zone.zone_health = ZoneHealth.GOOD
                else:
                    # คำนวณความไม่สมดุล
                    buy_ratio = zone.buy_count / total_orders
                    sell_ratio = zone.sell_count / total_orders
                    imbalance = abs(buy_ratio - sell_ratio)
                    
                    # คำนวณคะแนน (0-100)
                    balance_score = (1 - imbalance) * 100
                    zone.balance_score = balance_score
                    
                    # กำหนด Health Level
                    if balance_score >= 80:
                        zone.zone_health = ZoneHealth.EXCELLENT
                    elif balance_score >= 60:
                        zone.zone_health = ZoneHealth.GOOD
                    elif balance_score >= 40:
                        zone.zone_health = ZoneHealth.FAIR
                    elif balance_score >= 20:
                        zone.zone_health = ZoneHealth.POOR
                    else:
                        zone.zone_health = ZoneHealth.CRITICAL
                        
        except Exception as e:
            logger.error(f"Error calculating zone balance scores: {e}")
    
    def _generate_analysis_result(self) -> ZoneAnalysisResult:
        """สร้างผลการวิเคราะห์"""
        try:
            total_zones = len(self.zones)
            active_zones = sum(1 for zone in self.zones.values() 
                             if zone.buy_count + zone.sell_count > 0)
            empty_zones = total_zones - active_zones
            
            # นับโซนตามสถานะ
            health_counts = {health: 0 for health in ZoneHealth}
            for zone in self.zones.values():
                health_counts[zone.zone_health] += 1
            
            balanced_zones = (health_counts[ZoneHealth.EXCELLENT] + 
                            health_counts[ZoneHealth.GOOD])
            imbalanced_zones = (health_counts[ZoneHealth.FAIR] + 
                              health_counts[ZoneHealth.POOR])
            critical_zones = health_counts[ZoneHealth.CRITICAL]
            
            # คำนวณคะแนนรวม
            total_score = sum(zone.balance_score for zone in self.zones.values())
            overall_health_score = total_score / total_zones if total_zones > 0 else 0
            
            # กำหนดคุณภาพการกระจาย
            if overall_health_score >= 80:
                distribution_quality = "ดีเยี่ยม"
            elif overall_health_score >= 60:
                distribution_quality = "ดี"
            elif overall_health_score >= 40:
                distribution_quality = "พอใช้"
            elif overall_health_score >= 20:
                distribution_quality = "แย่"
            else:
                distribution_quality = "วิกฤต"
            
            # สร้างคำแนะนำ
            recommendations = self._generate_recommendations(
                empty_zones, imbalanced_zones, critical_zones
            )
            
            return ZoneAnalysisResult(
                total_zones=total_zones,
                active_zones=active_zones,
                empty_zones=empty_zones,
                balanced_zones=balanced_zones,
                imbalanced_zones=imbalanced_zones,
                critical_zones=critical_zones,
                overall_health_score=overall_health_score,
                distribution_quality=distribution_quality,
                recommendations=recommendations,
                zone_map=self.zones.copy()
            )
            
        except Exception as e:
            logger.error(f"Error generating analysis result: {e}")
            return self._create_empty_result()
    
    def _generate_recommendations(self, empty_zones: int, imbalanced_zones: int, 
                                critical_zones: int) -> List[str]:
        """สร้างคำแนะนำการปรับปรุง"""
        recommendations = []
        
        try:
            if critical_zones > 0:
                recommendations.append(f"🚨 มี {critical_zones} โซนวิกฤต - ต้องปรับสมดุลด่วน")
            
            if imbalanced_zones > 3:
                recommendations.append(f"⚠️ มี {imbalanced_zones} โซนไม่สมดุล - ควรกระจาย Orders")
            
            if empty_zones > 5:
                recommendations.append(f"📍 มี {empty_zones} โซนว่าง - ควรเติม Orders")
            
            # หาโซนที่ต้องการการปรับปรุงเฉพาะ
            buy_heavy_zones = []
            sell_heavy_zones = []
            
            for zone_id, zone in self.zones.items():
                total = zone.buy_count + zone.sell_count
                if total > 0:
                    buy_ratio = zone.buy_count / total
                    if buy_ratio > 0.7:
                        buy_heavy_zones.append(zone_id)
                    elif buy_ratio < 0.3:
                        sell_heavy_zones.append(zone_id)
            
            if buy_heavy_zones:
                recommendations.append(f"📈 โซน {buy_heavy_zones} กระจุก BUY - ควรเพิ่ม SELL")
            
            if sell_heavy_zones:
                recommendations.append(f"📉 โซน {sell_heavy_zones} กระจุก SELL - ควรเพิ่ม BUY")
            
            if not recommendations:
                recommendations.append("✅ การกระจายดี - รักษาสมดุลปัจจุบัน")
                
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            recommendations.append("❌ เกิดข้อผิดพลาดในการสร้างคำแนะนำ")
        
        return recommendations
    
    def _create_empty_result(self) -> ZoneAnalysisResult:
        """สร้างผลการวิเคราะห์เปล่าเมื่อเกิด error"""
        return ZoneAnalysisResult(
            total_zones=0,
            active_zones=0,
            empty_zones=0,
            balanced_zones=0,
            imbalanced_zones=0,
            critical_zones=0,
            overall_health_score=0.0,
            distribution_quality="ไม่สามารถวิเคราะห์ได้",
            recommendations=["❌ เกิดข้อผิดพลาดในการวิเคราะห์"],
            zone_map={}
        )
    
    def get_smart_entry_recommendation(self, signal_direction: str, current_price: float, 
                                     positions: List[Position]) -> SmartEntryRecommendation:
        """แนะนำจุดเข้าที่ชาญฉลาดตามการกระจายโซน"""
        try:
            # วิเคราะห์การกระจายปัจจุบัน
            analysis = self.analyze_position_distribution(positions)
            
            if not analysis.zone_map:
                return SmartEntryRecommendation(
                    recommended_action="WAIT",
                    target_zone_id=-1,
                    target_price_range=(0, 0),
                    confidence_score=0.0,
                    reason="ไม่สามารถวิเคราะห์โซนได้",
                    alternative_zones=[],
                    lot_size_multiplier=1.0
                )
            
            # หาโซนที่เหมาะสมสำหรับ entry
            target_zones = self._find_optimal_entry_zones(signal_direction, analysis.zone_map)
            
            if not target_zones:
                return SmartEntryRecommendation(
                    recommended_action="WAIT",
                    target_zone_id=-1,
                    target_price_range=(0, 0),
                    confidence_score=0.0,
                    reason="ไม่พบโซนที่เหมาะสมสำหรับการเข้า",
                    alternative_zones=[],
                    lot_size_multiplier=1.0
                )
            
            # เลือกโซนที่ดีที่สุด
            best_zone_id = target_zones[0]
            best_zone = analysis.zone_map[best_zone_id]
            
            # คำนวณ confidence score
            confidence_score = self._calculate_entry_confidence(
                signal_direction, best_zone, analysis
            )
            
            # กำหนด lot size multiplier
            lot_multiplier = self._calculate_lot_multiplier(best_zone, confidence_score)
            
            # สร้างเหตุผล
            reason = self._generate_entry_reason(signal_direction, best_zone, confidence_score)
            
            return SmartEntryRecommendation(
                recommended_action=signal_direction,
                target_zone_id=best_zone_id,
                target_price_range=(best_zone.price_min, best_zone.price_max),
                confidence_score=confidence_score,
                reason=reason,
                alternative_zones=target_zones[1:3],  # เอา 2 อันดับถัดไป
                lot_size_multiplier=lot_multiplier
            )
            
        except Exception as e:
            logger.error(f"Error getting smart entry recommendation: {e}")
            return SmartEntryRecommendation(
                recommended_action="WAIT",
                target_zone_id=-1,
                target_price_range=(0, 0),
                confidence_score=0.0,
                reason=f"เกิดข้อผิดพลาด: {str(e)}",
                alternative_zones=[],
                lot_size_multiplier=1.0
            )
    
    def _find_optimal_entry_zones(self, direction: str, zone_map: Dict[int, PriceZone]) -> List[int]:
        """หาโซนที่เหมาะสมที่สุดสำหรับการเข้า"""
        try:
            zone_scores = []
            
            for zone_id, zone in zone_map.items():
                score = 0.0
                
                # 1. Zone Health Score (40%)
                if zone.zone_health == ZoneHealth.EXCELLENT:
                    score += 40
                elif zone.zone_health == ZoneHealth.GOOD:
                    score += 30
                elif zone.zone_health == ZoneHealth.FAIR:
                    score += 20
                elif zone.zone_health == ZoneHealth.POOR:
                    score += 10
                else:  # CRITICAL
                    score += 0
                
                # 2. Direction Balance Score (35%)
                total_orders = zone.buy_count + zone.sell_count
                if total_orders == 0:
                    # โซนว่าง - ดีสำหรับทุกทิศทาง
                    score += 35
                else:
                    if direction.upper() == "BUY":
                        # ต้องการ BUY - โซนที่มี SELL มากจะได้คะแนนสูง
                        sell_ratio = zone.sell_count / total_orders
                        score += sell_ratio * 35
                    else:  # SELL
                        # ต้องการ SELL - โซนที่มี BUY มากจะได้คะแนนสูง
                        buy_ratio = zone.buy_count / total_orders
                        score += buy_ratio * 35
                
                # 3. Zone Type Score (15%)
                if zone.zone_type == ZoneType.HOT:
                    score += 15
                elif zone.zone_type == ZoneType.NORMAL:
                    score += 10
                elif zone.zone_type == ZoneType.SUPPORT or zone.zone_type == ZoneType.RESISTANCE:
                    score += 12
                else:  # DEAD
                    score += 5
                
                # 4. Profit Potential Score (10%)
                if zone.total_profit > 0:
                    score += 10
                elif zone.total_profit > -10:
                    score += 5
                else:
                    score += 0
                
                zone_scores.append((zone_id, score))
            
            # เรียงตาม score จากสูงไปต่ำ
            zone_scores.sort(key=lambda x: x[1], reverse=True)
            
            # คืนค่า zone_id ที่มี score สูง
            return [zone_id for zone_id, score in zone_scores if score > 30]
            
        except Exception as e:
            logger.error(f"Error finding optimal entry zones: {e}")
            return []
    
    def _calculate_entry_confidence(self, direction: str, zone: PriceZone, 
                                  analysis: ZoneAnalysisResult) -> float:
        """คำนวณความมั่นใจในการเข้า"""
        try:
            confidence = 0.0
            
            # 1. Zone Health (40%)
            confidence += zone.balance_score * 0.4 / 100
            
            # 2. Overall Portfolio Health (30%)
            confidence += analysis.overall_health_score * 0.3 / 100
            
            # 3. Zone Activity (20%)
            if zone.zone_type == ZoneType.HOT:
                confidence += 20
            elif zone.zone_type == ZoneType.NORMAL:
                confidence += 15
            else:
                confidence += 10
            
            # 4. Direction Alignment (10%)
            total_orders = zone.buy_count + zone.sell_count
            if total_orders > 0:
                if direction.upper() == "BUY" and zone.sell_count > zone.buy_count:
                    confidence += 10
                elif direction.upper() == "SELL" and zone.buy_count > zone.sell_count:
                    confidence += 10
                else:
                    confidence += 5
            else:
                confidence += 10  # โซนว่างดี
            
            return min(confidence, 100.0)
            
        except Exception as e:
            logger.error(f"Error calculating entry confidence: {e}")
            return 50.0
    
    def _calculate_lot_multiplier(self, zone: PriceZone, confidence: float) -> float:
        """คำนวณตัวคูณ lot size ตาม zone และ confidence"""
        try:
            multiplier = 1.0
            
            # ปรับตาม confidence
            if confidence >= 80:
                multiplier *= 1.3
            elif confidence >= 60:
                multiplier *= 1.1
            elif confidence >= 40:
                multiplier *= 1.0
            else:
                multiplier *= 0.8
            
            # ปรับตาม zone type
            if zone.zone_type == ZoneType.HOT:
                multiplier *= 1.2
            elif zone.zone_type == ZoneType.DEAD:
                multiplier *= 0.8
            
            # ปรับตาม zone health
            if zone.zone_health == ZoneHealth.EXCELLENT:
                multiplier *= 1.1
            elif zone.zone_health == ZoneHealth.CRITICAL:
                multiplier *= 0.9
            
            return max(0.5, min(multiplier, 2.0))  # จำกัดระหว่าง 0.5-2.0
            
        except Exception as e:
            logger.error(f"Error calculating lot multiplier: {e}")
            return 1.0
    
    def _generate_entry_reason(self, direction: str, zone: PriceZone, confidence: float) -> str:
        """สร้างเหตุผลสำหรับการแนะนำ entry"""
        try:
            reasons = []
            
            # Zone health
            reasons.append(f"Zone {zone.zone_id} ({zone.zone_health.value})")
            
            # Balance
            total_orders = zone.buy_count + zone.sell_count
            if total_orders == 0:
                reasons.append("โซนว่าง")
            else:
                buy_ratio = zone.buy_count / total_orders
                if direction.upper() == "BUY" and buy_ratio < 0.5:
                    reasons.append(f"ขาด BUY ({zone.buy_count}:{zone.sell_count})")
                elif direction.upper() == "SELL" and buy_ratio > 0.5:
                    reasons.append(f"ขาด SELL ({zone.buy_count}:{zone.sell_count})")
            
            # Zone type
            if zone.zone_type != ZoneType.NORMAL:
                reasons.append(f"{zone.zone_type.value} zone")
            
            # Confidence
            if confidence >= 80:
                reasons.append("ความมั่นใจสูง")
            elif confidence >= 60:
                reasons.append("ความมั่นใจดี")
            else:
                reasons.append("ความมั่นใจปานกลาง")
            
            return " | ".join(reasons)
            
        except Exception as e:
            logger.error(f"Error generating entry reason: {e}")
            return "การแนะนำแบบอัตโนมัติ"
    
    def get_zone_map_display(self, current_price: float) -> str:
        """สร้างแผนที่โซนสำหรับแสดงผล"""
        try:
            if not self.zones:
                return "ไม่มีข้อมูลโซน"
            
            lines = []
            lines.append("📊 PRICE ZONE MAP")
            lines.append("=" * 50)
            
            # เรียงโซนจากบนลงล่าง (ราคาสูงไปต่ำ)
            sorted_zones = sorted(self.zones.items(), key=lambda x: x[1].price_center, reverse=True)
            
            for zone_id, zone in sorted_zones:
                # สถานะโซน
                if zone.price_min <= current_price <= zone.price_max:
                    price_indicator = "👉"
                else:
                    price_indicator = "  "
                
                # Health indicator
                if zone.zone_health == ZoneHealth.EXCELLENT:
                    health_icon = "✅"
                elif zone.zone_health == ZoneHealth.GOOD:
                    health_icon = "🟢"
                elif zone.zone_health == ZoneHealth.FAIR:
                    health_icon = "🟡"
                elif zone.zone_health == ZoneHealth.POOR:
                    health_icon = "🟠"
                else:
                    health_icon = "🔴"
                
                # Orders info
                if zone.buy_count + zone.sell_count == 0:
                    orders_info = "Empty"
                else:
                    orders_info = f"B:{zone.buy_count} S:{zone.sell_count}"
                
                # Zone type
                type_icon = {
                    ZoneType.HOT: "🔥",
                    ZoneType.NORMAL: "⚪",
                    ZoneType.DEAD: "💤",
                    ZoneType.SUPPORT: "🟢",
                    ZoneType.RESISTANCE: "🔴"
                }.get(zone.zone_type, "⚪")
                
                line = (f"{price_indicator} Zone {zone_id:2d}: "
                       f"[{zone.price_min:7.2f}-{zone.price_max:7.2f}] "
                       f"{health_icon} {type_icon} {orders_info:8s} "
                       f"Score:{zone.balance_score:5.1f}")
                
                lines.append(line)
            
            lines.append("=" * 50)
            lines.append(f"Current Price: {current_price:.2f}")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"Error creating zone map display: {e}")
            return "เกิดข้อผิดพลาดในการสร้างแผนที่โซน"
