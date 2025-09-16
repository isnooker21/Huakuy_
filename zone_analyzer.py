import MetaTrader5 as mt5
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class ZoneAnalyzer:
    """🔍 วิเคราะห์ความแข็งแรงของ Support/Resistance Zones"""
    
    def __init__(self, mt5_connection):
        self.mt5_connection = mt5_connection
        self.symbol = None  # จะถูกตั้งค่าใน analyze_zones
        self.timeframes = [mt5.TIMEFRAME_M5, mt5.TIMEFRAME_M15, mt5.TIMEFRAME_M30, mt5.TIMEFRAME_H1]
        # ไม่ใช้ Daily timeframe เพราะมีปัญหา array comparison
        
        # Zone Detection Parameters
        self.min_touches = 2  # จำนวนครั้งที่ราคาต้องแตะ Zone
        self.zone_tolerance = 5.0  # ความยืดหยุ่นของ Zone (points)
        self.min_zone_strength = 30  # ความแข็งแรงขั้นต่ำ
        
        # Multi-TF Analysis
        self.tf_weights = {
            mt5.TIMEFRAME_M5: 0.1,
            mt5.TIMEFRAME_M15: 0.2,
            mt5.TIMEFRAME_M30: 0.3,
            mt5.TIMEFRAME_H1: 0.4
        }
        
        # Zone Strength Calculation
        self.price_action_weight = 0.4
        self.volume_weight = 0.3
        self.time_weight = 0.3
        
    def analyze_zones(self, symbol: str, lookback_hours: int = 24) -> Dict[str, List[Dict]]:
        """🔍 วิเคราะห์ Support/Resistance Zones จากหลาย Timeframe"""
        try:
            self.symbol = symbol  # ตั้งค่า symbol จาก parameter
            logger.info(f"🔍 Analyzing zones for {self.symbol} (lookback: {lookback_hours}h)")
            
            support_zones = []
            resistance_zones = []
            
            for tf in self.timeframes:
                tf_support, tf_resistance = self._analyze_timeframe_zones(tf, lookback_hours)
                support_zones.extend(tf_support)
                resistance_zones.extend(tf_resistance)
            
            # รวม Zones ที่ใกล้เคียงกัน
            merged_support = self._merge_nearby_zones(support_zones)
            merged_resistance = self._merge_nearby_zones(resistance_zones)
            
            # คำนวณ Zone Strength
            for zone in merged_support:
                zone['strength'] = self._calculate_zone_strength(zone, 'support')
                zone['type'] = 'support'
            
            for zone in merged_resistance:
                zone['strength'] = self._calculate_zone_strength(zone, 'resistance')
                zone['type'] = 'resistance'
            
            # เรียงตาม Strength
            merged_support.sort(key=lambda x: x['strength'], reverse=True)
            merged_resistance.sort(key=lambda x: x['strength'], reverse=True)
            
            logger.info(f"🔍 ZONE ANALYSIS COMPLETE: {len(merged_support)} support zones, {len(merged_resistance)} resistance zones")
            
            # Log details of strongest zones
            if merged_support:
                strongest_support = merged_support[0]
                logger.info(f"🔍 Strongest Support: {strongest_support['price']:.2f} (Strength: {strongest_support['strength']:.1f})")
            
            if merged_resistance:
                strongest_resistance = merged_resistance[0]
                logger.info(f"🔍 Strongest Resistance: {strongest_resistance['price']:.2f} (Strength: {strongest_resistance['strength']:.1f})")
            
            return {
                'support': merged_support,
                'resistance': merged_resistance
            }
            
        except Exception as e:
            logger.error(f"❌ Error analyzing zones: {e}")
            return {'support': [], 'resistance': []}
    
    def _analyze_timeframe_zones(self, timeframe, lookback_hours: int) -> Tuple[List[Dict], List[Dict]]:
        """🔍 วิเคราะห์ Zones ใน Timeframe เดียว"""
        try:
            # ดึงข้อมูลราคา
            bars_needed = int(lookback_hours * 60 / self._get_timeframe_minutes(timeframe))
            logger.debug(f"🔍 Requesting {bars_needed} bars for {timeframe} (lookback: {lookback_hours}h)")
            rates = mt5.copy_rates_from_pos(self.symbol, timeframe, 0, bars_needed)
            
            if rates is None or len(rates) < 50:
                logger.warning(f"⚠️ Insufficient data for timeframe {timeframe} (got {len(rates) if rates else 0} bars, need 50+)")
                return [], []
            
            # หา Pivot Points
            pivots = self._find_pivot_points(rates)
            
            # แยก Support และ Resistance
            support_zones = []
            resistance_zones = []
            
            for pivot in pivots:
                if pivot['touches'] >= self.min_touches:
                    zone_data = {
                        'price': pivot['price'],
                        'timeframe': timeframe,
                        'touches': pivot['touches'],
                        'timestamp': pivot['timestamp'],
                        'tf_weight': self.tf_weights.get(timeframe, 0.1)
                    }
                    
                    if pivot['type'] == 'support':
                        support_zones.append(zone_data)
                    else:
                        resistance_zones.append(zone_data)
            
            logger.debug(f"TF {timeframe}: {len(support_zones)} support, {len(resistance_zones)} resistance")
            return support_zones, resistance_zones
            
        except Exception as e:
            logger.error(f"❌ Error analyzing timeframe {timeframe}: {e}")
            return [], []
    
    def _find_pivot_points(self, rates) -> List[Dict]:
        """🔍 หา Pivot Points จากข้อมูลราคา"""
        try:
            pivots = []
            window = 3  # ใช้ window 3 bars
            
            for i in range(window, len(rates) - window):
                current_high = rates[i]['high']
                current_low = rates[i]['low']
                
                # ตรวจสอบ Support Pivot (Low)
                is_support_pivot = True
                for j in range(i - window, i + window + 1):
                    if j != i and j < len(rates) and rates[j]['low'] <= current_low:
                        is_support_pivot = False
                        break
                
                if is_support_pivot:
                    touches = self._count_touches(rates, current_low, 'support', i)
                    if touches >= self.min_touches:
                        pivots.append({
                            'type': 'support',
                            'price': current_low,
                            'touches': touches,
                            'timestamp': rates[i]['time'],
                            'index': i
                        })
                
                # ตรวจสอบ Resistance Pivot (High)
                is_resistance_pivot = True
                for j in range(i - window, i + window + 1):
                    if j != i and j < len(rates) and rates[j]['high'] >= current_high:
                        is_resistance_pivot = False
                        break
                
                if is_resistance_pivot:
                    touches = self._count_touches(rates, current_high, 'resistance', i)
                    if touches >= self.min_touches:
                        pivots.append({
                            'type': 'resistance',
                            'price': current_high,
                            'touches': touches,
                            'timestamp': rates[i]['time'],
                            'index': i
                        })
            
            return pivots
            
        except Exception as e:
            logger.error(f"❌ Error finding pivot points: {e}")
            return []
    
    def _count_touches(self, rates, price, zone_type, pivot_index) -> int:
        """🔍 นับจำนวนครั้งที่ราคาแตะ Zone"""
        try:
            touches = 1  # เริ่มที่ 1 เพราะ pivot เอง
            tolerance = self.zone_tolerance
            
            # ตรวจสอบ bars หลัง pivot
            for i in range(pivot_index + 1, len(rates)):
                if i < len(rates):
                    if zone_type == 'support':
                        if abs(rates[i]['low'] - price) <= tolerance:
                            touches += 1
                    else:  # resistance
                        if abs(rates[i]['high'] - price) <= tolerance:
                            touches += 1
            
            # ตรวจสอบ bars ก่อน pivot (ในระยะใกล้)
            start_idx = max(0, pivot_index - 50)  # ย้อนหลัง 50 bars
            for i in range(start_idx, pivot_index):
                if i < len(rates):
                    if zone_type == 'support':
                        if abs(rates[i]['low'] - price) <= tolerance:
                            touches += 1
                    else:  # resistance
                        if abs(rates[i]['high'] - price) <= tolerance:
                            touches += 1
            
            return touches
            
        except Exception as e:
            logger.error(f"❌ Error counting touches: {e}")
            return 0
    
    def _merge_nearby_zones(self, zones: List[Dict]) -> List[Dict]:
        """🔗 รวม Zones ที่ใกล้เคียงกัน"""
        try:
            if not zones:
                return []
            
            # เรียงตามราคา
            zones.sort(key=lambda x: x['price'])
            
            merged = []
            current_group = [zones[0]]
            
            for zone in zones[1:]:
                # ตรวจสอบว่าใกล้กับกลุ่มปัจจุบันหรือไม่
                group_avg_price = sum(z['price'] for z in current_group) / len(current_group)
                
                if abs(zone['price'] - group_avg_price) <= self.zone_tolerance:
                    current_group.append(zone)
                else:
                    # สร้าง merged zone จากกลุ่มปัจจุบัน
                    merged_zone = self._create_merged_zone(current_group)
                    merged.append(merged_zone)
                    current_group = [zone]
            
            # จัดการกลุ่มสุดท้าย
            if current_group:
                merged_zone = self._create_merged_zone(current_group)
                merged.append(merged_zone)
            
            logger.debug(f"🔗 Merged {len(zones)} zones into {len(merged)} zones")
            return merged
            
        except Exception as e:
            logger.error(f"❌ Error merging zones: {e}")
            return zones
    
    def _create_merged_zone(self, zone_group: List[Dict]) -> Dict:
        """🔗 สร้าง merged zone จากกลุ่ม zones"""
        try:
            # คำนวณราคาเฉลี่ยถ่วงน้ำหนัก
            total_weight = sum(z.get('tf_weight', 0.1) * z['touches'] for z in zone_group)
            weighted_price = sum(z['price'] * z.get('tf_weight', 0.1) * z['touches'] for z in zone_group)
            avg_price = weighted_price / total_weight if total_weight > 0 else sum(z['price'] for z in zone_group) / len(zone_group)
            
            # รวม touches
            total_touches = sum(z['touches'] for z in zone_group)
            
            # หา timestamp ล่าสุด
            latest_timestamp = max(z['timestamp'] for z in zone_group)
            
            # รวม timeframes
            timeframes = list(set(z['timeframe'] for z in zone_group))
            
            return {
                'price': round(avg_price, 2),
                'touches': total_touches,
                'timestamp': latest_timestamp,
                'timeframes': timeframes,
                'zone_count': len(zone_group)
            }
            
        except Exception as e:
            logger.error(f"❌ Error creating merged zone: {e}")
            return zone_group[0]
    
    def _calculate_zone_strength(self, zone: Dict, zone_type: str) -> float:
        """💪 คำนวณความแข็งแรงของ Zone"""
        try:
            # Price Action Strength (จำนวนครั้งที่แตะ)
            max_touches = 10
            price_action_score = min((zone['touches'] / max_touches) * 100, 100)
            
            # Multi-Timeframe Strength
            tf_score = len(zone.get('timeframes', [zone.get('timeframe')])) * 25
            tf_score = min(tf_score, 100)
            
            # Time Freshness (Zone ใหม่ = แข็งแรงกว่า)
            now = datetime.now().timestamp()
            zone_age_hours = (now - zone['timestamp']) / 3600
            time_score = max(100 - (zone_age_hours / 24) * 20, 20)  # ลดลง 20 points ต่อวัน
            
            # Zone Count Bonus (ถ้ามีหลาย zones รวมกัน)
            zone_count_bonus = min(zone.get('zone_count', 1) * 10, 30)
            
            # คำนวณ Zone Strength รวม
            total_strength = (
                price_action_score * self.price_action_weight +
                tf_score * 0.3 +
                time_score * self.time_weight +
                zone_count_bonus * 0.1
            )
            
            final_strength = min(total_strength, 100)
            
            logger.debug(f"💪 Zone {zone['price']}: PA={price_action_score:.1f}, TF={tf_score:.1f}, "
                        f"Time={time_score:.1f}, Bonus={zone_count_bonus:.1f} = {final_strength:.1f}")
            
            return round(final_strength, 1)
            
        except Exception as e:
            logger.error(f"❌ Error calculating zone strength: {e}")
            return 0.0
    
    def _get_timeframe_minutes(self, timeframe) -> int:
        """⏰ เปลี่ยน Timeframe เป็นนาที"""
        tf_minutes = {
            mt5.TIMEFRAME_M5: 5,
            mt5.TIMEFRAME_M15: 15,
            mt5.TIMEFRAME_M30: 30,
            mt5.TIMEFRAME_H1: 60
        }
        minutes = tf_minutes.get(timeframe, 5)
        logger.debug(f"🔍 Timeframe {timeframe} = {minutes} minutes")
        return minutes
    
    def get_zone_at_price(self, price: float, zones: Dict[str, List[Dict]], tolerance: float = None) -> Optional[Dict]:
        """🎯 หา Zone ที่ราคาปัจจุบัน"""
        try:
            if tolerance is None:
                tolerance = self.zone_tolerance
            
            # ตรวจสอบ Support Zones
            for zone in zones.get('support', []):
                if abs(zone['price'] - price) <= tolerance:
                    zone['zone_type'] = 'support'
                    return zone
            
            # ตรวจสอบ Resistance Zones
            for zone in zones.get('resistance', []):
                if abs(zone['price'] - price) <= tolerance:
                    zone['zone_type'] = 'resistance'
                    return zone
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting zone at price: {e}")
            return None
    
    def get_strongest_zones(self, zones: Dict[str, List[Dict]], count: int = 5) -> Dict[str, List[Dict]]:
        """🏆 หา Zones ที่แข็งแรงที่สุด"""
        try:
            support_zones = sorted(zones.get('support', []), key=lambda x: x.get('strength', 0), reverse=True)
            resistance_zones = sorted(zones.get('resistance', []), key=lambda x: x.get('strength', 0), reverse=True)
            
            return {
                'support': support_zones[:count],
                'resistance': resistance_zones[:count]
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting strongest zones: {e}")
            return {'support': [], 'resistance': []}
