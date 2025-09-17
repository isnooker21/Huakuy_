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
        self.timeframes = [mt5.TIMEFRAME_M5]  # ใช้แค่ M5 เท่านั้น
        # ไม่ใช้ Daily timeframe เพราะมีปัญหา array comparison
        
        # Multi-Algorithm Zone Detection Parameters - ปรับให้หา zones ได้มากขึ้น
        self.min_touches = 1  # เกณฑ์ขั้นต่ำสำหรับการแตะ zone
        self.zone_tolerance = 25.0  # ความยืดหยุ่นในการรวม zones (เพิ่มจาก 20.0)
        self.min_zone_strength = 2  # ความแข็งแรงขั้นต่ำของ zone
        self.max_zones_per_type = 15  # จำนวน zone สูงสุดต่อประเภท
        
        # Multi-TF Analysis (ใช้แค่ M5)
        self.tf_weights = {
            mt5.TIMEFRAME_M5: 1.0  # ใช้แค่ M5 เท่านั้น
        }
        
        # Zone Strength Calculation
        self.price_action_weight = 0.4
        self.volume_weight = 0.3
        self.time_weight = 0.3
        
        # Multi-Algorithm Settings - ใช้แค่ Pivot Points ที่ทำงานได้ดี
        self.enable_pivot_points = True      # วิธีที่ 1: Pivot Points (หลัก)
        self.enable_volume_profile = False   # วิธีที่ 2: Volume Profile (ปิด - หา zones น้อย)
        self.enable_price_patterns = False   # วิธีที่ 3: Price Action Patterns (ปิด - หา zones มากเกินไป)
        
        # ปรับให้หา zones ได้มากขึ้น
        self.zone_tolerance = 25.0           # ความยืดหยุ่นในการรวม zones (เพิ่มจาก 15.0)
        self.min_zone_strength = 2           # ความแข็งแรงขั้นต่ำของ zone (ลดจาก 3)
        self.max_zones_per_type = 15         # จำนวน zone สูงสุดต่อประเภท (เพิ่มจาก 10)
        
    def analyze_zones(self, symbol: str, lookback_hours: int = 24) -> Dict[str, List[Dict]]:
        """🔍 วิเคราะห์ Support/Resistance Zones ด้วย Multi-Algorithm"""
        try:
            self.symbol = symbol  # ตั้งค่า symbol จาก parameter
            logger.info(f"🔍 [ZONE ANALYSIS] Analyzing zones for {self.symbol} (lookback: {lookback_hours}h)")
            logger.info(f"🔧 [ZONE ANALYSIS] Settings: tolerance={self.zone_tolerance}, min_strength={self.min_zone_strength}")
            logger.info(f"🎯 [ZONE ANALYSIS] Using Pivot Points only (Volume Profile & Patterns disabled for better performance)")
            
            support_zones = []
            resistance_zones = []
            
            for tf in self.timeframes:
                # ใช้ Multi-Algorithm หา zones
                tf_support, tf_resistance = self._analyze_timeframe_zones_multi_algorithm(tf, lookback_hours)
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
            
            # จำกัดจำนวน zones ตาม max_zones_per_type
            if len(merged_support) > self.max_zones_per_type:
                merged_support = merged_support[:self.max_zones_per_type]
            if len(merged_resistance) > self.max_zones_per_type:
                merged_resistance = merged_resistance[:self.max_zones_per_type]
            
            logger.info("=" * 80)
            logger.info(f"🎯 [ZONE ANALYSIS] ZONE ANALYSIS COMPLETE")
            logger.info("=" * 80)
            logger.info(f"📊 [RESULTS] Support: {len(merged_support)} zones, Resistance: {len(merged_resistance)} zones")
            
            # Log Support zones with algorithm info
            if merged_support:
                logger.info("📈 [SUPPORT ZONES] Found:")
                for i, zone in enumerate(merged_support[:10], 1):
                    algorithm = zone.get('algorithm', 'unknown')
                    algorithms_used = zone.get('algorithms_used', [algorithm])
                    zone_count = zone.get('zone_count', 1)
                    
                    if algorithm == 'consolidated':
                        logger.info(f"   {i}. Support: {zone['price']:.2f} (Strength: {zone['strength']:.1f}) [CONSOLIDATED: {zone_count} zones from {', '.join(algorithms_used)}]")
                    else:
                        logger.info(f"   {i}. Support: {zone['price']:.2f} (Strength: {zone['strength']:.1f}) [{algorithm.upper()}]")
                
                if len(merged_support) > 10:
                    logger.info(f"   ... และอีก {len(merged_support) - 10} zones")
            else:
                logger.warning("🚫 [SUPPORT ZONES] NO ZONES FOUND - ลองปรับ volume_threshold หรือ pattern_tolerance")
            
            # Log Resistance zones with algorithm info
            if merged_resistance:
                logger.info("📉 [RESISTANCE ZONES] Found:")
                for i, zone in enumerate(merged_resistance[:10], 1):
                    algorithm = zone.get('algorithm', 'unknown')
                    algorithms_used = zone.get('algorithms_used', [algorithm])
                    zone_count = zone.get('zone_count', 1)
                    
                    if algorithm == 'consolidated':
                        logger.info(f"   {i}. Resistance: {zone['price']:.2f} (Strength: {zone['strength']:.1f}) [CONSOLIDATED: {zone_count} zones from {', '.join(algorithms_used)}]")
                    else:
                        logger.info(f"   {i}. Resistance: {zone['price']:.2f} (Strength: {zone['strength']:.1f}) [{algorithm.upper()}]")
                
                if len(merged_resistance) > 10:
                    logger.info(f"   ... และอีก {len(merged_resistance) - 10} zones")
            else:
                logger.warning("🚫 [RESISTANCE ZONES] NO ZONES FOUND - ลองปรับ volume_threshold หรือ pattern_tolerance")
            
            logger.info("=" * 80)
            
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
    
    def _analyze_timeframe_zones_multi_algorithm(self, timeframe, lookback_hours: int) -> Tuple[List[Dict], List[Dict]]:
        """🎯 Multi-Algorithm Zone Detection - ใช้ 3 วิธีหา zones พร้อมกัน"""
        try:
            logger.info(f"🎯 [ZONE ANALYSIS] Starting zone analysis for timeframe {timeframe}")
            logger.info(f"🔧 [ZONE ANALYSIS] Using Pivot Points only (simple and effective)")
            
            # ดึงข้อมูลราคา
            rates = self._get_rates(timeframe, lookback_hours)
            if not rates or len(rates) < 50:
                logger.warning(f"❌ [ZONE ANALYSIS] Insufficient data for timeframe {timeframe}")
                return [], []
            
            all_support_zones = []
            all_resistance_zones = []
            
            # ใช้แค่ Pivot Points (วิธีเดียวที่ทำงานได้ดี)
            logger.info("🔍 [PIVOT POINTS] Starting analysis...")
            pivot_support, pivot_resistance = self._find_zones_from_pivots(rates)
            all_support_zones.extend(pivot_support)
            all_resistance_zones.extend(pivot_resistance)
            logger.info(f"✅ [PIVOT POINTS] Found {len(pivot_support)} support, {len(pivot_resistance)} resistance zones")
            
            # รวมและจัดเรียง zones ตาม strength
            final_support = self._consolidate_zones(all_support_zones, 'support')
            final_resistance = self._consolidate_zones(all_resistance_zones, 'resistance')
            
            logger.info(f"🎯 [ZONE ANALYSIS] Final Results: {len(final_support)} support, {len(final_resistance)} resistance zones")
            return final_support, final_resistance
            
        except Exception as e:
            logger.error(f"❌ [ZONE ANALYSIS] Error in zone analysis: {e}")
            return [], []

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
    
    def _find_zones_from_pivots(self, rates) -> Tuple[List[Dict], List[Dict]]:
        """🔍 Algorithm 1: หา zones จาก Pivot Points (เดิม)"""
        try:
            pivots = self._find_pivot_points(rates)
            support_zones = []
            resistance_zones = []
            
            for pivot in pivots:
                if pivot['type'] == 'support':
                    zone = {
                        'price': pivot['price'],
                        'touches': pivot['touches'],
                        'strength': pivot.get('support_score', pivot['touches'] * 10),
                        'timestamp': pivot['timestamp'],
                        'algorithm': 'pivot_points',
                        'rejection_strength': pivot.get('rejection_strength', 1.0),
                        'volume_factor': pivot.get('volume_factor', 1.0)
                    }
                    support_zones.append(zone)
                else:
                    zone = {
                        'price': pivot['price'],
                        'touches': pivot['touches'],
                        'strength': pivot.get('resistance_score', pivot['touches'] * 10),
                        'timestamp': pivot['timestamp'],
                        'algorithm': 'pivot_points',
                        'rejection_strength': pivot.get('rejection_strength', 1.0),
                        'volume_factor': pivot.get('volume_factor', 1.0)
                    }
                    resistance_zones.append(zone)
            
            return support_zones, resistance_zones
        except Exception as e:
            logger.error(f"❌ [ALGORITHM 1] Error in pivot points analysis: {e}")
            return [], []

    def _find_zones_from_volume_profile_adaptive(self, rates) -> Tuple[List[Dict], List[Dict]]:
        """📊 Algorithm 2: หา zones จาก Volume Profile (Adaptive) - Fast Mode"""
        try:
            if len(rates) < 20:
                return [], []
            
            # ลองแค่ 2 เกณฑ์ volume threshold (เร็วขึ้น)
            current_threshold = self.volume_threshold
            best_support = []
            best_resistance = []
            best_total = 0
            
            for attempt in range(self.max_attempts):
                logger.info(f"📊 [VOLUME PROFILE] Attempt {attempt + 1}: threshold={current_threshold:.1f}")
                
                support_zones, resistance_zones = self._find_zones_from_volume_profile(rates, current_threshold)
                total_zones = len(support_zones) + len(resistance_zones)
                
                logger.info(f"📊 [VOLUME PROFILE] Found {len(support_zones)} support, {len(resistance_zones)} resistance zones")
                
                # ถ้าเจอ zones เพียงพอ หรือเป็นครั้งสุดท้าย
                if total_zones >= self.min_zones_per_algorithm or attempt == self.max_attempts - 1:
                    best_support = support_zones
                    best_resistance = resistance_zones
                    best_total = total_zones
                    break
                
                # ถ้าเจอน้อยเกินไป ให้ลด threshold (ขั้นใหญ่ขึ้น)
                if total_zones < self.min_zones_per_algorithm:
                    current_threshold = max(current_threshold - self.volume_threshold_step, self.volume_threshold_min)
                    logger.info(f"📊 [VOLUME PROFILE] Too few zones, reducing threshold to {current_threshold:.1f}")
                else:
                    best_support = support_zones
                    best_resistance = resistance_zones
                    best_total = total_zones
                    break
            
            logger.info(f"📊 [VOLUME PROFILE] Final: {len(best_support)} support, {len(best_resistance)} resistance zones (total: {best_total})")
            return best_support, best_resistance
            
        except Exception as e:
            logger.error(f"❌ [ALGORITHM 2] Error in adaptive volume profile analysis: {e}")
            return [], []

    def _find_zones_from_volume_profile(self, rates, volume_threshold=None) -> Tuple[List[Dict], List[Dict]]:
        """📊 Algorithm 2: หา zones จาก Volume Profile"""
        try:
            if len(rates) < 20:
                return [], []
            
            # ใช้ threshold ที่ส่งมา หรือใช้ default
            if volume_threshold is None:
                volume_threshold = self.volume_threshold
            
            # สร้าง Volume Profile
            prices = [float(rate['close']) for rate in rates]
            volumes = [float(rate.get('tick_volume', 1)) for rate in rates]
            
            min_price = min(prices)
            max_price = max(prices)
            price_range = max_price - min_price
            
            if price_range == 0:
                return [], []
            
            # สร้าง bins สำหรับ volume profile
            bin_size = price_range / self.volume_profile_bins
            volume_bins = {}
            
            for i, (price, volume) in enumerate(zip(prices, volumes)):
                bin_index = int((price - min_price) / bin_size)
                bin_index = min(bin_index, self.volume_profile_bins - 1)
                
                if bin_index not in volume_bins:
                    volume_bins[bin_index] = {'volume': 0, 'prices': []}
                volume_bins[bin_index]['volume'] += volume
                volume_bins[bin_index]['prices'].append(price)
            
            # หา zones ที่มี volume สูง
            max_volume = max(bin_data['volume'] for bin_data in volume_bins.values())
            actual_threshold = max_volume * volume_threshold
            
            support_zones = []
            resistance_zones = []
            
            for bin_index, bin_data in volume_bins.items():
                if bin_data['volume'] >= actual_threshold:
                    avg_price = sum(bin_data['prices']) / len(bin_data['prices'])
                    volume_strength = (bin_data['volume'] / max_volume) * 100
                    
                    # กำหนดว่าเป็น support หรือ resistance ตามตำแหน่ง
                    price_position = (avg_price - min_price) / price_range
                    
                    zone = {
                        'price': avg_price,
                        'touches': len(bin_data['prices']),
                        'strength': volume_strength,
                        'timestamp': float(rates[-1]['time']),
                        'algorithm': 'volume_profile',
                        'volume': bin_data['volume']
                    }
                    
                    if price_position < 0.3:  # ราคาต่ำ = Support
                        support_zones.append(zone)
                    elif price_position > 0.7:  # ราคาสูง = Resistance
                        resistance_zones.append(zone)
            
            return support_zones, resistance_zones
        except Exception as e:
            logger.error(f"❌ [ALGORITHM 2] Error in volume profile analysis: {e}")
            return [], []

    def _find_zones_from_patterns_adaptive(self, rates) -> Tuple[List[Dict], List[Dict]]:
        """📈 Algorithm 3: หา zones จาก Price Action Patterns (Adaptive) - Fast Mode"""
        try:
            if len(rates) < 20:
                return [], []
            
            # ลองแค่ 2 เกณฑ์ pattern tolerance (เร็วขึ้น)
            current_tolerance = self.pattern_tolerance
            best_support = []
            best_resistance = []
            best_total = 0
            
            for attempt in range(self.max_attempts):
                logger.info(f"📈 [PRICE PATTERNS] Attempt {attempt + 1}: tolerance={current_tolerance:.1f}")
                
                support_zones, resistance_zones = self._find_zones_from_patterns(rates, current_tolerance)
                total_zones = len(support_zones) + len(resistance_zones)
                
                logger.info(f"📈 [PRICE PATTERNS] Found {len(support_zones)} support, {len(resistance_zones)} resistance zones")
                
                # ถ้าเจอ zones เพียงพอ หรือเป็นครั้งสุดท้าย
                if total_zones >= self.min_zones_per_algorithm or attempt == self.max_attempts - 1:
                    best_support = support_zones
                    best_resistance = resistance_zones
                    best_total = total_zones
                    break
                
                # ถ้าเจอน้อยเกินไป ให้เพิ่ม tolerance (ขั้นใหญ่ขึ้น)
                if total_zones < self.min_zones_per_algorithm:
                    current_tolerance = min(current_tolerance + self.pattern_tolerance_step, self.pattern_tolerance_max)
                    logger.info(f"📈 [PRICE PATTERNS] Too few zones, increasing tolerance to {current_tolerance:.1f}")
                else:
                    best_support = support_zones
                    best_resistance = resistance_zones
                    best_total = total_zones
                    break
            
            logger.info(f"📈 [PRICE PATTERNS] Final: {len(best_support)} support, {len(best_resistance)} resistance zones (total: {best_total})")
            return best_support, best_resistance
            
        except Exception as e:
            logger.error(f"❌ [ALGORITHM 3] Error in adaptive price patterns analysis: {e}")
            return [], []

    def _find_zones_from_patterns(self, rates, pattern_tolerance=None) -> Tuple[List[Dict], List[Dict]]:
        """📈 Algorithm 3: หา zones จาก Price Action Patterns"""
        try:
            if len(rates) < 20:
                return [], []
            
            # ใช้ tolerance ที่ส่งมา หรือใช้ default
            if pattern_tolerance is None:
                pattern_tolerance = self.pattern_tolerance
            
            support_zones = []
            resistance_zones = []
            
            # หา Double/Triple Tops และ Bottoms
            highs = [float(rate['high']) for rate in rates]
            lows = [float(rate['low']) for rate in rates]
            
            # หา Double/Triple Bottoms (Support)
            bottoms = self._find_double_triple_bottoms(lows, rates, pattern_tolerance)
            for bottom in bottoms:
                zone = {
                    'price': bottom['price'],
                    'touches': bottom['touches'],
                    'strength': bottom['strength'],
                    'timestamp': bottom['timestamp'],
                    'algorithm': 'price_patterns',
                    'pattern_type': bottom['pattern_type']
                }
                support_zones.append(zone)
            
            # หา Double/Triple Tops (Resistance)
            tops = self._find_double_triple_tops(highs, rates, pattern_tolerance)
            for top in tops:
                zone = {
                    'price': top['price'],
                    'touches': top['touches'],
                    'strength': top['strength'],
                    'timestamp': top['timestamp'],
                    'algorithm': 'price_patterns',
                    'pattern_type': top['pattern_type']
                }
                resistance_zones.append(zone)
            
            return support_zones, resistance_zones
        except Exception as e:
            logger.error(f"❌ [ALGORITHM 3] Error in price patterns analysis: {e}")
            return [], []

    def _find_double_triple_bottoms(self, lows, rates, tolerance=None) -> List[Dict]:
        """🔍 หา Double/Triple Bottoms"""
        bottoms = []
        if tolerance is None:
            tolerance = self.pattern_tolerance
        
        for i in range(2, len(lows) - 2):
            current_low = lows[i]
            
            # หา lows ที่ใกล้เคียงกัน
            similar_lows = []
            for j in range(max(0, i-10), min(len(lows), i+10)):
                if j != i and abs(lows[j] - current_low) <= tolerance:
                    similar_lows.append(j)
            
            if len(similar_lows) >= 1:  # Double Bottom หรือมากกว่า
                touches = len(similar_lows) + 1
                pattern_type = f"{'Triple' if touches >= 3 else 'Double'} Bottom"
                
                # คำนวณ strength
                strength = min(touches * 25, 100)
                
                bottoms.append({
                    'price': current_low,
                    'touches': touches,
                    'strength': strength,
                    'timestamp': float(rates[i]['time']),
                    'pattern_type': pattern_type
                })
        
        return bottoms

    def _find_double_triple_tops(self, highs, rates, tolerance=None) -> List[Dict]:
        """🔍 หา Double/Triple Tops"""
        tops = []
        if tolerance is None:
            tolerance = self.pattern_tolerance
        
        for i in range(2, len(highs) - 2):
            current_high = highs[i]
            
            # หา highs ที่ใกล้เคียงกัน
            similar_highs = []
            for j in range(max(0, i-10), min(len(highs), i+10)):
                if j != i and abs(highs[j] - current_high) <= tolerance:
                    similar_highs.append(j)
            
            if len(similar_highs) >= 1:  # Double Top หรือมากกว่า
                touches = len(similar_highs) + 1
                pattern_type = f"{'Triple' if touches >= 3 else 'Double'} Top"
                
                # คำนวณ strength
                strength = min(touches * 25, 100)
                
                tops.append({
                    'price': current_high,
                    'touches': touches,
                    'strength': strength,
                    'timestamp': float(rates[i]['time']),
                    'pattern_type': pattern_type
                })
        
        return tops

    def _get_rates(self, timeframe, lookback_hours: int):
        """📊 ดึงข้อมูลราคาจาก MT5"""
        try:
            if not self.mt5_connection.is_connected:
                logger.error("❌ MT5 not connected")
                return None
            
            # คำนวณจำนวน bars ที่ต้องการ (M5 = 12 bars ต่อชั่วโมง)
            bars_per_hour = 12  # M5 timeframe
            count = lookback_hours * bars_per_hour
            
            # ดึงข้อมูลราคา
            rates = self.mt5_connection.get_market_data(
                symbol=self.symbol,
                timeframe=timeframe,
                count=count
            )
            
            if rates is None or len(rates) == 0:
                logger.warning(f"❌ No rates data for {self.symbol} on timeframe {timeframe}")
                return None
            
            logger.info(f"📊 Retrieved {len(rates)} bars for {self.symbol} (lookback: {lookback_hours}h)")
            return rates
            
        except Exception as e:
            logger.error(f"❌ Error getting rates: {e}")
            return None

    def _consolidate_zones(self, zones, zone_type) -> List[Dict]:
        """🔄 รวม zones ที่ใกล้เคียงกันและจัดเรียงตาม strength"""
        try:
            if not zones:
                return []
            
            # จัดเรียงตาม strength
            zones.sort(key=lambda x: x['strength'], reverse=True)
            
            # รวม zones ที่ใกล้เคียงกัน
            consolidated = []
            used_indices = set()
            
            for i, zone in enumerate(zones):
                if i in used_indices:
                    continue
                
                # หา zones ที่ใกล้เคียงกัน
                nearby_zones = [zone]
                for j, other_zone in enumerate(zones[i+1:], i+1):
                    if j in used_indices:
                        continue
                    
                    price_diff = abs(zone['price'] - other_zone['price'])
                    if price_diff <= self.zone_tolerance:
                        nearby_zones.append(other_zone)
                        used_indices.add(j)
                
                # รวม zones ที่ใกล้เคียงกัน
                if len(nearby_zones) > 1:
                    # คำนวณค่าเฉลี่ย
                    avg_price = sum(z['price'] for z in nearby_zones) / len(nearby_zones)
                    total_touches = sum(z['touches'] for z in nearby_zones)
                    max_strength = max(z['strength'] for z in nearby_zones)
                    
                    consolidated_zone = {
                        'price': avg_price,
                        'touches': total_touches,
                        'strength': max_strength,
                        'timestamp': max(z['timestamp'] for z in nearby_zones),
                        'algorithm': 'consolidated',
                        'zone_count': len(nearby_zones),
                        'algorithms_used': list(set(z.get('algorithm', 'unknown') for z in nearby_zones))
                    }
                    consolidated.append(consolidated_zone)
                else:
                    consolidated.append(zone)
            
            # จำกัดจำนวน zones
            return consolidated[:self.max_zones_per_type]
            
        except Exception as e:
            logger.error(f"❌ Error consolidating {zone_type} zones: {e}")
            return zones[:self.max_zones_per_type]

    def _find_pivot_points(self, rates) -> List[Dict]:
        """🔍 หา Pivot Points จากข้อมูลราคา"""
        try:
            pivots = []
            window = 2  # ลด window เป็น 2 bars เพื่อหา pivot มากขึ้น
            logger.info(f"🔍 Finding pivot points from {len(rates)} bars with window={window}")
            
            for i in range(window, len(rates) - window):
                current_high = float(rates[i]['high'])
                current_low = float(rates[i]['low'])
                
                # ตรวจสอบ Support Pivot (Low) - ปรับให้หา Support ได้มากขึ้น
                is_support_pivot = True
                for j in range(i - window, i + window + 1):
                    if j != i and j < len(rates) and float(rates[j]['low']) < float(current_low) - 1.0:  # ลด tolerance จาก 2.0 เป็น 1.0
                        is_support_pivot = False
                        break
                
                if is_support_pivot:
                    touches = self._count_touches(rates, current_low, 'support', i)
                    if touches >= self.min_touches:
                        # เพิ่มการวิเคราะห์ Price Action
                        rejection_strength = self._calculate_rejection_strength(rates, i, 'support')
                        volume_factor = self._estimate_volume_factor(rates, i)
                        
                        # เพิ่มคะแนนสำหรับ Support เพื่อให้หาได้มากขึ้น
                        support_score = rejection_strength + volume_factor + (touches * 3)  # ลดจาก 5 เป็น 3
                        
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
                
                # ตรวจสอบ Resistance Pivot (High) - ปรับให้หา Resistance ได้มากขึ้น
                is_resistance_pivot = True
                for j in range(i - window, i + window + 1):
                    if j != i and j < len(rates) and float(rates[j]['high']) > float(current_high) + 1.0:  # เพิ่ม tolerance 1.0
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
            
            logger.info(f"🔍 Found {len(pivots)} pivot points")
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
            
            # รวม timeframes (ถ้ามี)
            timeframes = []
            for z in zone_group:
                if 'timeframe' in z:
                    timeframes.append(z['timeframe'])
                elif 'timeframes' in z:
                    timeframes.extend(z['timeframes'])
            
            # รวม algorithms ที่ใช้
            algorithms_used = list(set(z.get('algorithm', 'unknown') for z in zone_group))
            
            # คำนวณ strength สูงสุด
            max_strength = max(z.get('strength', 0) for z in zone_group)
            
            return {
                'price': round(avg_price, 2),
                'touches': total_touches,
                'strength': max_strength,
                'timestamp': latest_timestamp,
                'timeframes': list(set(timeframes)) if timeframes else [],
                'zone_count': len(zone_group),
                'algorithm': 'consolidated',
                'algorithms_used': algorithms_used
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
