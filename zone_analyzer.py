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
        
        # Zone Detection Parameters (ปรับให้หา Support/Resistance ได้สมดุล)
        self.min_touches = 1  # ลดเกณฑ์ให้หา Zone ได้มากขึ้น (จาก 2)
        self.zone_tolerance = 20.0  # เพิ่มความยืดหยุ่น สำหรับ XAUUSD (จาก 15.0)
        self.min_zone_strength = 15  # ลดเกณฑ์ความแข็งแรง (จาก 20) เพื่อหา Support มากขึ้น
        
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
            
            # Log all Support zones with prices
            if merged_support:
                logger.info("📈 SUPPORT ZONES FOUND:")
                for i, zone in enumerate(merged_support[:5], 1):  # แสดง 5 zones ที่แข็งแกร่งที่สุด
                    logger.info(f"   {i}. Support: {zone['price']:.2f} (Strength: {zone['strength']:.1f})")
                if len(merged_support) > 5:
                    logger.info(f"   ... และอีก {len(merged_support) - 5} zones")
            else:
                logger.warning("🚫 NO SUPPORT ZONES FOUND - อาจเป็นเพราะตลาดไม่มี Support ที่แข็งแกร่งเพียงพอ")
            
            # Log all Resistance zones with prices
            if merged_resistance:
                logger.info("📉 RESISTANCE ZONES FOUND:")
                for i, zone in enumerate(merged_resistance[:5], 1):  # แสดง 5 zones ที่แข็งแกร่งที่สุด
                    logger.info(f"   {i}. Resistance: {zone['price']:.2f} (Strength: {zone['strength']:.1f})")
                if len(merged_resistance) > 5:
                    logger.info(f"   ... และอีก {len(merged_resistance) - 5} zones")
            else:
                logger.warning("🚫 NO RESISTANCE ZONES FOUND - อาจเป็นเพราะตลาดไม่มี Resistance ที่แข็งแกร่งเพียงพอ")
            
            # Log warning if no zones at all
            if not merged_support and not merged_resistance:
                logger.warning("🚫 NO ZONES FOUND AT ALL - ระบบไม่พบ Support หรือ Resistance zones เลย")
                logger.warning("   📊 ตรวจสอบ: ข้อมูลราคา, เกณฑ์ zone_tolerance, min_zone_strength")
                logger.warning("   🔧 ปรับแต่ง: ลด zone_tolerance หรือ min_zone_strength เพื่อหา zones ได้มากขึ้น")
            
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
            # 🚫 Skip problematic timeframes (Daily = 16385)
            if timeframe == 16385:
                logger.info(f"⏭️ Skipping problematic timeframe {timeframe} (Daily)")
                return [], []
            
            # ดึงข้อมูลราคา - จำกัดจำนวน bars เพื่อลดเวลาประมวลผล
            bars_needed = int(lookback_hours * 60 / self._get_timeframe_minutes(timeframe))
            bars_needed = min(bars_needed, 200)  # จำกัดสูงสุด 200 bars เพื่อลด CPU usage
            logger.debug(f"🔍 Requesting {bars_needed} bars for {timeframe} (lookback: {lookback_hours}h)")
            rates = mt5.copy_rates_from_pos(self.symbol, timeframe, 0, bars_needed)
            
            if rates is None:
                logger.warning(f"⚠️ No data received for timeframe {timeframe}")
                return [], []
            
            # ตรวจสอบชนิดของ rates - ถ้าเป็น NumPy structured array ให้แปลงเป็น dict
            if hasattr(rates, 'dtype'):  # NumPy structured array
                rates_list = []
                for rate in rates:
                    # แปลง structured array record เป็น dict
                    rate_dict = {
                        'time': float(rate['time']),
                        'open': float(rate['open']),
                        'high': float(rate['high']),
                        'low': float(rate['low']),
                        'close': float(rate['close']),
                        'tick_volume': int(rate['tick_volume']) if 'tick_volume' in rate.dtype.names else 0,
                        'spread': int(rate['spread']) if 'spread' in rate.dtype.names else 0,
                        'real_volume': int(rate['real_volume']) if 'real_volume' in rate.dtype.names else 0
                    }
                    rates_list.append(rate_dict)
                rates = rates_list
                logger.debug(f"🔄 Converted NumPy structured array to dict list: {len(rates)} bars")
            
            if len(rates) < 50:
                logger.warning(f"⚠️ Insufficient data for timeframe {timeframe} (got {len(rates)} bars, need 50+)")
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
            window = 5  # เพิ่ม window เป็น 5 bars ให้แม่นยำกว่า
            
            for i in range(window, len(rates) - window):
                current_high = float(rates[i]['high'])
                current_low = float(rates[i]['low'])
                
            # ตรวจสอบ Support Pivot (Low) - ปรับให้หา Support ได้มากขึ้น
            is_support_pivot = True
            for j in range(i - window, i + window + 1):
                if j != i and j < len(rates) and float(rates[j]['low']) < float(current_low) - 2.0:  # เพิ่ม tolerance
                    is_support_pivot = False
                    break
            
            if is_support_pivot:
                touches = self._count_touches(rates, current_low, 'support', i)
                if touches >= self.min_touches:
                    # เพิ่มการวิเคราะห์ Price Action
                    rejection_strength = self._calculate_rejection_strength(rates, i, 'support')
                    volume_factor = self._estimate_volume_factor(rates, i)
                    
                    # เพิ่มคะแนนสำหรับ Support เพื่อให้หาได้มากขึ้น
                    support_score = rejection_strength + volume_factor + (touches * 5)
                    
                    pivots.append({
                        'type': 'support',
                        'price': current_low,
                        'touches': touches,
                        'timestamp': float(rates[i]['time']),
                        'index': i,
                        'rejection_strength': rejection_strength,
                        'volume_factor': volume_factor,
                        'support_score': support_score
                    })
                
                # ตรวจสอบ Resistance Pivot (High)
                is_resistance_pivot = True
                for j in range(i - window, i + window + 1):
                    if j != i and j < len(rates) and float(rates[j]['high']) >= float(current_high):
                        is_resistance_pivot = False
                        break
                
                if is_resistance_pivot:
                    touches = self._count_touches(rates, current_high, 'resistance', i)
                    if touches >= self.min_touches:
                        # เพิ่มการวิเคราะห์ Price Action
                        rejection_strength = self._calculate_rejection_strength(rates, i, 'resistance')
                        volume_factor = self._estimate_volume_factor(rates, i)
                        
                        pivots.append({
                            'type': 'resistance',
                            'price': current_high,
                            'touches': touches,
                            'timestamp': float(rates[i]['time']),
                            'index': i,
                            'rejection_strength': rejection_strength,
                            'volume_factor': volume_factor
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
                        if abs(float(rates[i]['low']) - float(price)) <= tolerance:
                            touches += 1
                    else:  # resistance
                        if abs(float(rates[i]['high']) - float(price)) <= tolerance:
                            touches += 1
            
            # ตรวจสอบ bars ก่อน pivot (ในระยะใกล้)
            start_idx = max(0, pivot_index - 50)  # ย้อนหลัง 50 bars
            for i in range(start_idx, pivot_index):
                if i < len(rates):
                    if zone_type == 'support':
                        if abs(float(rates[i]['low']) - float(price)) <= tolerance:
                            touches += 1
                    else:  # resistance
                        if abs(float(rates[i]['high']) - float(price)) <= tolerance:
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
        """💪 คำนวณความแข็งแรงของ Zone (ปรับปรุงใหม่)"""
        try:
            # Price Action Strength (จำนวนครั้งที่แตะ)
            max_touches = 8  # ลดจาก 10
            price_action_score = min((zone['touches'] / max_touches) * 100, 100)
            
            # Multi-Timeframe Strength
            tf_score = len(zone.get('timeframes', [zone.get('timeframe')])) * 30  # เพิ่มจาก 25
            tf_score = min(tf_score, 100)
            
            # Time Freshness (Zone ใหม่ = แข็งแรงกว่า)
            now = datetime.now().timestamp()
            zone_age_hours = (now - zone['timestamp']) / 3600
            time_score = max(100 - (zone_age_hours / 12) * 15, 30)  # ลดเร็วกว่าเดิม
            
            # Zone Count Bonus (ถ้ามีหลาย zones รวมกัน)
            zone_count_bonus = min(zone.get('zone_count', 1) * 15, 40)  # เพิ่มโบนัส
            
            # Rejection Strength Bonus (ใหม่)
            rejection_bonus = 0
            if 'rejection_strength' in zone:
                rejection_bonus = (zone['rejection_strength'] - 1.0) * 20  # 0-40 points
            
            # Volume Factor Bonus (ใหม่)
            volume_bonus = 0
            if 'volume_factor' in zone:
                volume_bonus = (zone['volume_factor'] - 1.0) * 15  # 0-30 points
            
            # คำนวณ Zone Strength รวม (ปรับน้ำหนักใหม่)
            total_strength = (
                price_action_score * 0.25 +  # ลดน้ำหนัก PA
                tf_score * 0.35 +            # เพิ่มน้ำหนัก Multi-TF
                time_score * 0.20 +          # ลดน้ำหนัก Time
                zone_count_bonus * 0.10 +    # Zone count
                rejection_bonus * 0.05 +     # Rejection strength
                volume_bonus * 0.05          # Volume factor
            )
            
            final_strength = min(total_strength, 100)
            
            logger.debug(f"💪 Zone {zone['price']}: PA={price_action_score:.1f}, TF={tf_score:.1f}, "
                        f"Time={time_score:.1f}, Reject={rejection_bonus:.1f}, Vol={volume_bonus:.1f} = {final_strength:.1f}")
            
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
    
    def _calculate_rejection_strength(self, rates, pivot_index: int, zone_type: str) -> float:
        """💪 คำนวณความแรงของการ rejection ที่ Zone"""
        try:
            if pivot_index < 1 or pivot_index >= len(rates) - 1:
                return 1.0
            
            current_bar = rates[pivot_index]
            current_high = float(current_bar['high'])
            current_low = float(current_bar['low'])
            current_close = float(current_bar['close'])
            current_open = float(current_bar['open'])
            
            if zone_type == 'support':
                # วัดความแรงของ rejection จาก support
                lower_wick = current_open - current_low if current_close > current_open else current_close - current_low
                total_range = current_high - current_low
                
                if total_range > 0:
                    wick_ratio = lower_wick / total_range
                    rejection_strength = 1.0 + (wick_ratio * 2.0)  # 1.0 - 3.0
                else:
                    rejection_strength = 1.0
                    
            else:  # resistance
                # วัดความแรงของ rejection จาก resistance
                upper_wick = current_high - current_open if current_close < current_open else current_high - current_close
                total_range = current_high - current_low
                
                if total_range > 0:
                    wick_ratio = upper_wick / total_range
                    rejection_strength = 1.0 + (wick_ratio * 2.0)  # 1.0 - 3.0
                else:
                    rejection_strength = 1.0
            
            return min(rejection_strength, 3.0)  # จำกัดไม่เกิน 3.0
            
        except Exception as e:
            logger.error(f"❌ Error calculating rejection strength: {e}")
            return 1.0
    
    def _estimate_volume_factor(self, rates, pivot_index: int) -> float:
        """📊 ประมาณ volume factor จาก tick volume"""
        try:
            if pivot_index < 5 or pivot_index >= len(rates) - 5:
                return 1.0
            
            # ใช้ tick volume ถ้ามี
            current_volume = getattr(rates[pivot_index], 'tick_volume', 1)
            
            # คำนวณ average volume ของ bars ข้างเคียง
            avg_volume = 0
            count = 0
            for i in range(pivot_index - 5, pivot_index + 6):
                if 0 <= i < len(rates):
                    vol = getattr(rates[i], 'tick_volume', 1)
                    avg_volume += vol
                    count += 1
            
            if count > 0 and avg_volume > 0:
                avg_volume = avg_volume / count
                volume_factor = current_volume / avg_volume
                return min(max(volume_factor, 0.5), 3.0)  # จำกัด 0.5 - 3.0
            else:
                return 1.0
                
        except Exception as e:
            logger.error(f"❌ Error estimating volume factor: {e}")
            return 1.0
    
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
