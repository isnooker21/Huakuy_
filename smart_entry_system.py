import MetaTrader5 as mt5
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Any
import logging

logger = logging.getLogger(__name__)

class SmartEntrySystem:
    """🎯 ระบบเข้าไม้อัจฉริยะแบบใหม่ (Support/Resistance เท่านั้น)"""
    
    def __init__(self, mt5_connection, zone_analyzer):
        self.mt5_connection = mt5_connection
        self.zone_analyzer = zone_analyzer
        self.symbol = None  # จะถูกตั้งค่าจาก main system
        
        # Entry Parameters (ปรับใหม่ให้แม่นยำขึ้น)
        self.support_buy_enabled = True      # เปิด Support entries (BUY ที่ Support)
        self.resistance_sell_enabled = True  # เปิด Resistance entries (SELL ที่ Resistance)
        
        # Enhanced Zone Selection Parameters - ปรับให้เหมาะสมกับ Zone Strength สูง
        self.profit_target_pips = 35  # เพิ่มเป้าหมายกำไรเป็น 35 pips (ลดความถี่การออกไม้)
        self.loss_threshold_pips = 30  # เพิ่มเกณฑ์ขาดทุนเป็น 30 pips (ลดความถี่การออกไม้)
        self.recovery_zone_strength = 10  # เพิ่ม Zone strength สำหรับ Recovery
        self.min_zone_strength = 0.05  # Zone strength ขั้นต่ำ (0.05 = 5% จาก 100)
        self.min_zone_touches = 1  # ลดจำนวน touches เป็น 1 ครั้ง (Zone Strength สูง = แตะน้อยก็ได้)
        self.min_algorithms_detected = 0  # ไม่จำกัด algorithms (Zone Strength สูง = พบจากวิธีเดียวก็ได้)
        
        # Enhanced Risk Management - ปรับให้เหมาะสมกับการเทรดคุณภาพ
        self.risk_percent_per_trade = 0.015  # ลดเป็น 1.5% ของ balance ต่อ trade (คุณภาพเหนือปริมาณ)
        self.max_daily_trades = 25  # เพิ่มจำนวน trade ต่อวันเป็น 25 (ให้เทรดได้มากขึ้น)
        
        # Zone Quality Filters - ปรับให้เหมาะสมกับ Zone Strength สูง
        self.min_zone_distance_pips = 5  # ลดระยะห่างขั้นต่ำเป็น 5 pips (Zone Strength สูง = ใกล้ก็ได้)
        self.max_zone_distance_pips = 200  # ระยะห่างสูงสุด 200 pips
        self.zone_cooldown_hours = 2  # ลด cooldown เป็น 2 ชั่วโมง (Zone Strength สูง = ใช้ได้บ่อย)
        self.min_time_between_trades = 30  # ลดเวลาระหว่าง trades เป็น 30 วินาที (Zone Strength สูง = เทรดได้บ่อย)
        
        # Market Condition Filters - ปรับการเข้าไม้ตามสภาพตลาด
        self.volatility_threshold = 0.8  # เกณฑ์ความผันผวน (ต่ำกว่า = ตลาดนิ่ง, สูงกว่า = ตลาดผันผวน)
        self.trend_strength_threshold = 0.6  # เกณฑ์ความแข็งแกร่งของเทรนด์
        self.volume_threshold = 1.2  # เกณฑ์ Volume (ต่ำกว่า = Volume ต่ำ, สูงกว่า = Volume สูง)
        
        # Lot Size Management
        self.min_lot_size = 0.01
        self.max_lot_size = 1.0
        
        # Zone Tracking
        self.used_zones = {}  # {zone_key: {'timestamp': time, 'ticket': ticket}}
        self.daily_trade_count = 0
        self.last_reset_date = datetime.now().date()
        self.last_trade_time = None  # เวลาคำสั่งล่าสุด
        
    def calculate_dynamic_profit_target(self, lot_size: float) -> float:
        """🎯 คำนวณเป้าหมายกำไรตาม lot size"""
        try:
            # คำนวณตาม pips ต่อ lot
            profit_target = lot_size * self.profit_target_pips * 10  # XAUUSD pip value = 10
            return max(5.0, profit_target)  # กำไรขั้นต่ำ $5
        except Exception as e:
            logger.error(f"❌ Error calculating dynamic profit target: {e}")
            return 5.0  # fallback
    
    def calculate_dynamic_loss_threshold(self, lot_size: float) -> float:
        """⚠️ คำนวณเกณฑ์ขาดทุนตาม lot size"""
        try:
            # คำนวณตาม pips ต่อ lot
            loss_threshold = lot_size * self.loss_threshold_pips * 10  # XAUUSD pip value = 10
            return -max(5.0, loss_threshold)  # ขาดทุนขั้นต่ำ -$5
        except Exception as e:
            logger.error(f"❌ Error calculating dynamic loss threshold: {e}")
            return -5.0  # fallback
    
    def calculate_dynamic_lot_size(self, zone_strength: float, zone: dict = None) -> float:
        """📊 คำนวณ lot size ตาม zone strength และ balance"""
        try:
            # ดึงข้อมูลบัญชี
            account_info = self.mt5_connection.get_account_info()
            if not account_info:
                return self.min_lot_size
            
            # ตรวจสอบว่า account_info เป็น dict หรือ object
            if isinstance(account_info, dict):
                balance = account_info.get('balance', 1000.0)
            else:
                balance = getattr(account_info, 'balance', 1000.0)
            
            # คำนวณ lot size ตาม % ของ balance
            risk_amount = balance * self.risk_percent_per_trade
            
            # ปรับ pip value สำหรับ XAUUSD (1 lot = 100 oz, pip value = 100)
            pip_value = 100  # XAUUSD pip value
            base_lot_size = risk_amount / (self.profit_target_pips * pip_value)
            
            # ปรับตาม zone strength แบบละเอียด (ปรับให้เหมาะสมกับ XAUUSD)
            # ใช้การคำนวณแบบต่อเนื่องแทนการแบ่งช่วง
            if zone_strength >= 90:
                # Zone แข็งแกร่งมาก (90-100): ใช้ lot มากที่สุด
                final_multiplier = 1.2 + (zone_strength - 90) * 0.02  # 1.2-1.4
            elif zone_strength >= 80:
                # Zone แข็งแกร่ง (80-89): ใช้ lot มาก
                final_multiplier = 1.0 + (zone_strength - 80) * 0.02  # 1.0-1.2
            elif zone_strength >= 70:
                # Zone ปานกลาง (70-79): ใช้ lot ปานกลาง
                final_multiplier = 0.8 + (zone_strength - 70) * 0.02  # 0.8-1.0
            elif zone_strength >= 60:
                # Zone อ่อน (60-69): ใช้ lot น้อย
                final_multiplier = 0.6 + (zone_strength - 60) * 0.02  # 0.6-0.8
            elif zone_strength >= 50:
                # Zone อ่อนมาก (50-59): ใช้ lot น้อยมาก
                final_multiplier = 0.4 + (zone_strength - 50) * 0.02  # 0.4-0.6
            else:
                # Zone อ่อนเกินไป (<50): ใช้ lot ขั้นต่ำ
                final_multiplier = 0.3
            
            # ปรับเพิ่มเติมตามปัจจัยอื่นๆ (ถ้ามี zone data)
            additional_multiplier = 1.0
            
            if zone:
                # ปรับตามจำนวน touches ของ zone
                touches = zone.get('touches', 1)
                if touches >= 5:
                    additional_multiplier *= 1.3  # Zone ที่แตะบ่อย = แข็งแกร่ง (เพิ่มจาก 1.2)
                elif touches >= 3:
                    additional_multiplier *= 1.15  # เพิ่มจาก 1.1
                elif touches <= 1:
                    additional_multiplier *= 0.9  # Zone ที่แตะน้อย = อ่อน (เพิ่มจาก 0.8)
                
                # ปรับตามจำนวน algorithms ที่พบ zone นี้
                algorithms_used = zone.get('algorithms_used', [])
                if isinstance(algorithms_used, list) and len(algorithms_used) >= 3:
                    additional_multiplier *= 1.25  # Zone ที่พบจากหลายวิธี = แข็งแกร่ง (เพิ่มจาก 1.15)
                elif len(algorithms_used) >= 2:
                    additional_multiplier *= 1.1  # เพิ่มจาก 1.05
                
                # ปรับตาม zone count (zones ที่รวมกัน)
                zone_count = zone.get('zone_count', 1)
                if zone_count >= 3:
                    additional_multiplier *= 1.2  # Zone ที่รวมกันหลายตัว = แข็งแกร่ง (เพิ่มจาก 1.1)
                
                # ปรับตาม market condition (ถ้ามีข้อมูล)
                market_condition = zone.get('market_condition', 'normal')
                if market_condition == 'trending':
                    additional_multiplier *= 1.2  # ตลาด trending = ใช้ lot มากกว่า (เพิ่มจาก 1.1)
                elif market_condition == 'sideways':
                    additional_multiplier *= 1.0  # ตลาด sideways = ใช้ lot ปกติ (เพิ่มจาก 0.9)
                elif market_condition == 'volatile':
                    additional_multiplier *= 0.9  # ตลาดผันผวน = ใช้ lot น้อยกว่า (เพิ่มจาก 0.8)
                
                # ปรับตามระยะห่างจาก current price
                current_price = zone.get('current_price', 0)
                zone_price = zone.get('price', 0)
                if current_price > 0 and zone_price > 0:
                    distance_pips = abs(current_price - zone_price) * 10000  # แปลงเป็น pips
                    if distance_pips <= 10:
                        additional_multiplier *= 1.3  # Zone ใกล้ราคาปัจจุบัน = แข็งแกร่ง (เพิ่มจาก 1.2)
                    elif distance_pips <= 20:
                        additional_multiplier *= 1.15  # เพิ่มจาก 1.1
                    elif distance_pips >= 50:
                        additional_multiplier *= 1.0  # Zone ไกลราคาปัจจุบัน = ปกติ (เพิ่มจาก 0.9)
            
            final_lot_size = base_lot_size * final_multiplier * additional_multiplier
            
            # Debug log
            logger.info(f"📊 [LOT CALCULATION] Balance: ${balance:.2f}, Risk: {self.risk_percent_per_trade*100:.1f}%")
            logger.info(f"📊 [LOT CALCULATION] Risk Amount: ${risk_amount:.2f}, Pip Value: {pip_value}")
            logger.info(f"📊 [LOT CALCULATION] Base Lot: {base_lot_size:.4f}, Zone Strength: {zone_strength:.1f}")
            logger.info(f"📊 [LOT CALCULATION] Strength Multiplier: {final_multiplier:.3f}")
            
            if zone:
                touches = zone.get('touches', 1)
                algorithms_used = zone.get('algorithms_used', [])
                zone_count = zone.get('zone_count', 1)
                logger.info(f"📊 [LOT CALCULATION] Touches: {touches}, Algorithms: {len(algorithms_used)}, Zone Count: {zone_count}")
            else:
                logger.info(f"📊 [LOT CALCULATION] No zone data available")
            
            logger.info(f"📊 [LOT CALCULATION] Additional Multiplier: {additional_multiplier:.3f}")
            logger.info(f"📊 [LOT CALCULATION] Final Lot: {final_lot_size:.4f}")
            
            # จำกัด lot size
            final_lot_size = max(self.min_lot_size, min(self.max_lot_size, final_lot_size))
            logger.info(f"📊 [LOT CALCULATION] Final Lot Size: {final_lot_size:.4f}")
            return final_lot_size
            
        except Exception as e:
            logger.error(f"❌ Error calculating dynamic lot size: {e}")
            return self.min_lot_size  # fallback
    
    def calculate_pivot_point(self, current_price: float, zones: Dict[str, List[Dict]]) -> float:
        """📊 คำนวณ Pivot Point จากราคาปัจจุบันและ zones"""
        try:
            support_zones = zones.get('support', [])
            resistance_zones = zones.get('resistance', [])
            
            logger.info(f"🔍 [PIVOT] Support zones: {len(support_zones)}, Resistance zones: {len(resistance_zones)}")
            
            if not support_zones or not resistance_zones:
                logger.warning(f"🚫 [PIVOT] Missing zones - using current price: {current_price}")
                return current_price
            
            # หา Support และ Resistance ที่ใกล้ราคาปัจจุบันที่สุด
            nearest_support = min(support_zones, key=lambda x: abs(x['price'] - current_price))
            nearest_resistance = min(resistance_zones, key=lambda x: abs(x['price'] - current_price))
            
            logger.info(f"🔍 [PIVOT] Nearest Support: {nearest_support['price']:.2f}, Resistance: {nearest_resistance['price']:.2f}")
            
            # คำนวณ Pivot Point
            pivot_point = (current_price + nearest_support['price'] + nearest_resistance['price']) / 3
            
            logger.info(f"🔍 [PIVOT] Calculated Pivot Point: {pivot_point:.2f}")
            return pivot_point
            
        except Exception as e:
            logger.error(f"❌ Error calculating pivot point: {e}")
            return current_price  # fallback
    
    def select_zone_by_pivot_and_strength(self, current_price: float, zones: Dict[str, List[Dict]]) -> Tuple[Optional[str], Optional[Dict]]:
        """🎯 เลือก Zone แบบ Enhanced - กรอง Zone ให้แม่นยำขึ้น"""
        try:
            # คำนวณ Pivot Point
            pivot_point = self.calculate_pivot_point(current_price, zones)
            support_zones = zones.get('support', [])
            resistance_zones = zones.get('resistance', [])
            
            logger.info(f"🔍 [ENHANCED ZONE SELECTION] Price: {current_price:.5f}, Pivot: {pivot_point:.5f}")
            logger.info(f"🔍 [ENHANCED ZONE SELECTION] Raw Zones: {len(support_zones)} support, {len(resistance_zones)} resistance")
            
            if not support_zones or not resistance_zones:
                logger.warning("🚫 [ENHANCED ZONE SELECTION] No support or resistance zones available")
                return None, None
            
            # 🎯 Enhanced Zone Filtering - กรอง Zone ให้แม่นยำขึ้น
            filtered_supports = self._filter_high_quality_zones(support_zones, current_price, 'support')
            filtered_resistances = self._filter_high_quality_zones(resistance_zones, current_price, 'resistance')
            
            logger.info(f"🔍 [ENHANCED ZONE SELECTION] Filtered Zones: {len(filtered_supports)} support, {len(filtered_resistances)} resistance")
            
            if not filtered_supports and not filtered_resistances:
                logger.warning("🚫 [ENHANCED ZONE SELECTION] No high-quality zones found after filtering")
                logger.info("🔄 [FALLBACK] Trying relaxed criteria...")
                
                # Fallback: ลดเกณฑ์ลงเพื่อหา Zone
                relaxed_supports = self._filter_relaxed_zones(support_zones, current_price, 'support')
                relaxed_resistances = self._filter_relaxed_zones(resistance_zones, current_price, 'resistance')
                
                if not relaxed_supports and not relaxed_resistances:
                    logger.warning("🚫 [FALLBACK] No zones found even with relaxed criteria")
                    return None, None
                
                # ใช้ relaxed zones
                filtered_supports = relaxed_supports
                filtered_resistances = relaxed_resistances
                logger.info(f"🔄 [FALLBACK] Using relaxed criteria: {len(filtered_supports)} support, {len(filtered_resistances)} resistance")
            
            # ตรวจสอบระยะห่างระหว่าง support และ resistance ที่ใกล้ที่สุด
            min_distance_pips = 30.0  # ลดระยะห่างขั้นต่ำเป็น 30 pips (ให้ยืดหยุ่นขึ้น)
            if filtered_supports and filtered_resistances:
                closest_support_price = min(filtered_supports, key=lambda x: abs(x['price'] - current_price))['price']
                closest_resistance_price = min(filtered_resistances, key=lambda x: abs(x['price'] - current_price))['price']
                distance_between_zones = abs(closest_support_price - closest_resistance_price) * 10000  # แปลงเป็น pips
                
                logger.info(f"🔍 [ENHANCED ZONE SELECTION] Distance between closest zones: {distance_between_zones:.1f} pips")
                
                if distance_between_zones < min_distance_pips:
                    logger.warning(f"🚫 [ENHANCED ZONE SELECTION] Zones too close: {distance_between_zones:.1f} pips < {min_distance_pips} pips")
                    return None, None
            
            # 🎯 เลือก Zone ตาม Pivot Point + Quality Score
            if current_price < pivot_point:
                # ราคาต่ำกว่า Pivot → หา Support ที่ดีที่สุด
                if filtered_supports:
                    best_support = self._select_best_zone(filtered_supports, current_price)
                    if best_support:
                        logger.info(f"✅ [ENHANCED ZONE SELECTION] Selected SUPPORT: {best_support['price']:.5f} (strength: {best_support['strength']:.1f}, touches: {best_support.get('touches', 0)})")
                        return 'support', best_support
                logger.warning("🚫 [ENHANCED ZONE SELECTION] No valid SUPPORT zones found")
            else:
                # ราคาสูงกว่า Pivot → หา Resistance ที่ดีที่สุด
                if filtered_resistances:
                    best_resistance = self._select_best_zone(filtered_resistances, current_price)
                    if best_resistance:
                        logger.info(f"✅ [ENHANCED ZONE SELECTION] Selected RESISTANCE: {best_resistance['price']:.5f} (strength: {best_resistance['strength']:.1f}, touches: {best_resistance.get('touches', 0)})")
                        return 'resistance', best_resistance
                logger.warning("🚫 [ENHANCED ZONE SELECTION] No valid RESISTANCE zones found")
            
            return None, None
            
        except Exception as e:
            logger.error(f"❌ Error in enhanced zone selection: {e}")
            return None, None
    
    def _filter_high_quality_zones(self, zones: List[Dict], current_price: float, zone_type: str) -> List[Dict]:
        """🎯 กรอง Zone แบบง่าย - เน้น Zone Strength เป็นหลัก"""
        try:
            filtered_zones = []
            
            for zone in zones:
                zone_price = zone.get('price', 0)
                zone_strength_raw = zone.get('strength', 0)
                touches = zone.get('touches', 0)
                algorithms_used = zone.get('algorithms_used', [])
                distance_pips = abs(zone_price - current_price) * 10000
                
                # เงื่อนไขหลัก: Zone Strength ต้องผ่านเกณฑ์ (แปลง 0-100 เป็น 0-1)
                zone_strength_normalized = zone_strength_raw / 100.0
                if zone_strength_normalized < self.min_zone_strength:
                    continue
                
                # เงื่อนไขรอง: ตรวจสอบพื้นฐาน
                if touches < self.min_zone_touches:
                    continue
                
                if isinstance(algorithms_used, list) and len(algorithms_used) < self.min_algorithms_detected:
                    continue
                
                if distance_pips < self.min_zone_distance_pips or distance_pips > self.max_zone_distance_pips:
                    continue
                
                # เงื่อนไขสุดท้าย: Cooldown และ Validity
                if self._is_zone_on_cooldown(zone):
                    continue
                
                if not self._is_valid_entry_zone(zone, current_price):
                    continue
                
                # Zone ผ่านทุกเงื่อนไข
                filtered_zones.append(zone)
            
            # เรียงตาม Quality Score (Strength + Touches + Algorithms)
            filtered_zones.sort(key=lambda x: self._calculate_zone_quality_score(x), reverse=True)
            
            logger.info(f"🔍 [ZONE FILTERING] {zone_type.upper()}: {len(zones)} → {len(filtered_zones)} zones after filtering")
            if filtered_zones:
                best_zone = filtered_zones[0]
                raw_strength = best_zone.get('strength', 0)
                normalized_strength = raw_strength / 100.0
                logger.info(f"🔍 [ZONE FILTERING] Best zone: {best_zone['price']:.5f} (Raw: {raw_strength:.1f}, Normalized: {normalized_strength:.3f})")
            
            return filtered_zones
            
        except Exception as e:
            logger.error(f"❌ Error filtering high-quality zones: {e}")
            return []
    
    def _filter_relaxed_zones(self, zones: List[Dict], current_price: float, zone_type: str) -> List[Dict]:
        """🔄 กรอง Zone แบบ Relaxed - เกณฑ์ผ่อนปรน"""
        try:
            filtered_zones = []
            
            for zone in zones:
                # 1. ตรวจสอบ Zone Strength (ลดเกณฑ์ - แปลงจาก 0-100 เป็น 0-1)
                zone_strength_raw = zone.get('strength', 0)
                zone_strength_normalized = zone_strength_raw / 100.0  # แปลงจาก 0-100 เป็น 0-1
                if zone_strength_normalized < 0.03:  # ลดจาก 0.05 เป็น 0.03
                    continue
                
                # 2. ตรวจสอบจำนวน Touches (ลดเกณฑ์)
                touches = zone.get('touches', 0)
                if touches < 1:  # ลดจาก 2 เป็น 1
                    continue
                
                # 3. ตรวจสอบจำนวน Algorithms (ลดเกณฑ์)
                algorithms_used = zone.get('algorithms_used', [])
                if isinstance(algorithms_used, list) and len(algorithms_used) < 1:  # ลดจาก 2 เป็น 1
                    continue
                
                # 4. ตรวจสอบระยะห่างจากราคาปัจจุบัน (เพิ่มเกณฑ์)
                distance_pips = abs(zone['price'] - current_price) * 10000
                if distance_pips < 10 or distance_pips > 300:  # ลดจาก 20-200 เป็น 10-300
                    continue
                
                # 5. ตรวจสอบว่า Zone ใช้แล้วหรือยัง (ลด Cooldown)
                if self._is_zone_on_relaxed_cooldown(zone):
                    continue
                
                # 6. ตรวจสอบ Zone Validity (ลดเกณฑ์)
                if self._is_valid_entry_zone_relaxed(zone, current_price):
                    filtered_zones.append(zone)
            
            # เรียงตาม Quality Score (Strength + Touches + Algorithms)
            filtered_zones.sort(key=lambda x: self._calculate_zone_quality_score(x), reverse=True)
            
            logger.info(f"🔄 [RELAXED FILTERING] {zone_type.upper()}: {len(zones)} → {len(filtered_zones)} zones after relaxed filtering")
            
            return filtered_zones
            
        except Exception as e:
            logger.error(f"❌ Error filtering relaxed zones: {e}")
            return []
    
    def _is_zone_on_relaxed_cooldown(self, zone: Dict) -> bool:
        """🕒 ตรวจสอบ Zone Cooldown แบบ Relaxed"""
        try:
            zone_key = self._generate_zone_key(zone)
            
            if zone_key in self.used_zones:
                last_used = self.used_zones[zone_key]['timestamp']
                time_since_used = datetime.now() - last_used
                
                # ลด cooldown เป็น 2 ชั่วโมง
                relaxed_cooldown_hours = 2
                if time_since_used.total_seconds() < (relaxed_cooldown_hours * 3600):
                    logger.debug(f"🕒 Zone {zone['price']} on relaxed cooldown: {time_since_used.total_seconds()/3600:.1f}h < {relaxed_cooldown_hours}h")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Error checking relaxed zone cooldown: {e}")
            return False
    
    def _is_valid_entry_zone_relaxed(self, zone: Dict, current_price: float) -> bool:
        """✅ ตรวจสอบ Zone แบบ Relaxed"""
        try:
            # ตรวจสอบระยะห่างจากคำสั่งที่เปิดอยู่แล้ว (ลดเกณฑ์)
            min_distance_from_existing = 15.0  # ลดจาก 35 เป็น 15 pips
            if hasattr(self, 'order_manager') and self.order_manager and self.symbol:
                try:
                    existing_positions = self.order_manager.get_positions_by_symbol(self.symbol)
                    for position in existing_positions:
                        if hasattr(position, 'price') and position.price > 0:
                            distance_from_existing = abs(zone['price'] - position.price) * 10000
                            if distance_from_existing < min_distance_from_existing:
                                logger.debug(f"🚫 Zone {zone['price']} too close to existing position: {distance_from_existing:.1f} pips")
                                return False
                except Exception as e:
                    logger.debug(f"⚠️ Could not check existing positions: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error validating relaxed entry zone: {e}")
            return False
    
    def _calculate_zone_quality_score(self, zone: Dict) -> float:
        """🎯 คำนวณ Quality Score ของ Zone"""
        try:
            strength_raw = zone.get('strength', 0)
            strength_normalized = strength_raw / 100.0  # แปลงจาก 0-100 เป็น 0-1
            touches = zone.get('touches', 0)
            algorithms_used = zone.get('algorithms_used', [])
            zone_count = zone.get('zone_count', 1)
            
            # คำนวณ Score
            score = 0.0
            
            # Strength Score (40%) - ใช้ค่า normalized
            score += strength_normalized * 40
            
            # Touches Score (30%)
            score += min(touches, 10) * 3  # สูงสุด 10 touches
            
            # Algorithms Score (20%)
            score += len(algorithms_used) * 2
            
            # Zone Count Score (10%)
            score += min(zone_count, 5) * 2  # สูงสุด 5 zones
            
            return score
            
        except Exception as e:
            logger.error(f"❌ Error calculating zone quality score: {e}")
            return 0.0
    
    def _select_best_zone(self, zones: List[Dict], current_price: float) -> Optional[Dict]:
        """🎯 เลือก Zone ที่ดีที่สุดจากรายการ Zone ที่กรองแล้ว"""
        try:
            if not zones:
                return None
            
            # เลือก Zone ที่มี Quality Score สูงสุดและไม่ไกลเกินไป
            best_zone = None
            best_score = -1
            
            for zone in zones[:5]:  # ดูแค่ 5 Zone แรก (เรียงตาม Quality Score แล้ว)
                quality_score = self._calculate_zone_quality_score(zone)
                distance_pips = abs(zone['price'] - current_price) * 10000
                
                # ให้คะแนนเพิ่มสำหรับ Zone ที่ไม่ไกลเกินไป
                if distance_pips <= 80:  # Zone ที่ใกล้ (≤80 pips)
                    quality_score *= 1.2
                elif distance_pips <= 120:  # Zone ที่ปานกลาง (≤120 pips)
                    quality_score *= 1.1
                
                if quality_score > best_score:
                    best_score = quality_score
                    best_zone = zone
            
            return best_zone
            
        except Exception as e:
            logger.error(f"❌ Error selecting best zone: {e}")
            return None
    
    def _is_zone_on_cooldown(self, zone: Dict) -> bool:
        """🕒 ตรวจสอบว่า Zone อยู่ในช่วง Cooldown หรือไม่ - ปรับตาม Zone Strength"""
        try:
            zone_key = self._generate_zone_key(zone)
            
            if zone_key in self.used_zones:
                last_used = self.used_zones[zone_key]['timestamp']
                time_since_used = datetime.now() - last_used
                
                # ปรับ cooldown ตาม Zone Strength
                zone_strength_raw = zone.get('strength', 0)
                if zone_strength_raw > 70:  # Zone Strength สูงมาก = cooldown สั้น
                    cooldown_hours = 1
                elif zone_strength_raw > 50:  # Zone Strength สูง = cooldown ปานกลาง
                    cooldown_hours = 2
                else:  # Zone Strength ปกติ = cooldown ปกติ
                    cooldown_hours = self.zone_cooldown_hours
                
                if time_since_used.total_seconds() < (cooldown_hours * 3600):
                    logger.debug(f"🕒 Zone {zone['price']} on cooldown: {time_since_used.total_seconds()/3600:.1f}h < {cooldown_hours}h")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Error checking zone cooldown: {e}")
            return False
    
    def _analyze_market_conditions(self, current_price: float, zones: Dict[str, List[Dict]]) -> Dict[str, Any]:
        """📊 วิเคราะห์สภาพตลาดเพื่อปรับการเข้าไม้"""
        try:
            market_conditions = {
                'volatility': 'normal',
                'trend': 'sideways',
                'volume': 'normal',
                'entry_recommendation': 'neutral'
            }
            
            # คำนวณความผันผวนจาก Support/Resistance
            support_zones = zones.get('support', [])
            resistance_zones = zones.get('resistance', [])
            
            if support_zones and resistance_zones:
                # หา Support และ Resistance ที่ใกล้ที่สุด
                closest_support = min(support_zones, key=lambda x: abs(x['price'] - current_price))
                closest_resistance = min(resistance_zones, key=lambda x: abs(x['price'] - current_price))
                
                # คำนวณระยะห่างระหว่าง Support/Resistance
                range_size = abs(closest_resistance['price'] - closest_support['price']) * 10000  # pips
                
                # วิเคราะห์ความผันผวน (ปรับให้ยืดหยุ่นขึ้น)
                if range_size > 300:  # เพิ่มเกณฑ์เป็น 300 pips = ตลาดผันผวน
                    market_conditions['volatility'] = 'high'
                elif range_size < 50:  # ลดเกณฑ์เป็น 50 pips = ตลาดนิ่ง
                    market_conditions['volatility'] = 'low'
                
                # วิเคราะห์เทรนด์
                pivot_point = self.calculate_pivot_point(current_price, zones)
                if current_price > pivot_point * 1.002:  # ราคาสูงกว่า Pivot มาก = Uptrend
                    market_conditions['trend'] = 'uptrend'
                elif current_price < pivot_point * 0.998:  # ราคาต่ำกว่า Pivot มาก = Downtrend
                    market_conditions['trend'] = 'downtrend'
                
                # ให้คำแนะนำการเข้าไม้ (ปรับใหม่ - ตลาดวิ่ง = โอกาสดี)
                if market_conditions['volatility'] == 'high':
                    market_conditions['entry_recommendation'] = 'high_volatility'  # ตลาดวิ่ง = โอกาสดีในการออกไม้
                elif market_conditions['volatility'] == 'low' and market_conditions['trend'] == 'sideways':
                    market_conditions['entry_recommendation'] = 'favorable'  # ตลาดนิ่ง = เข้าไม้ได้ดี
                elif market_conditions['trend'] in ['uptrend', 'downtrend']:
                    market_conditions['entry_recommendation'] = 'trend_following'  # ตลาดมีเทรนด์ = ตามเทรนด์
            
            logger.info(f"📊 [MARKET CONDITIONS] Volatility: {market_conditions['volatility']}, Trend: {market_conditions['trend']}, Recommendation: {market_conditions['entry_recommendation']}")
            
            return market_conditions
            
        except Exception as e:
            logger.error(f"❌ Error analyzing market conditions: {e}")
            return {'volatility': 'normal', 'trend': 'sideways', 'volume': 'normal', 'entry_recommendation': 'neutral'}
    
    def _should_enter_based_on_market_conditions(self, market_conditions: Dict[str, Any], zone_type: str) -> bool:
        """🎯 ตัดสินใจว่าควรเข้าไม้หรือไม่ตามสภาพตลาด"""
        try:
            recommendation = market_conditions.get('entry_recommendation', 'neutral')
            volatility = market_conditions.get('volatility', 'normal')
            trend = market_conditions.get('trend', 'sideways')
            
            # กรณีที่ตลาดวิ่ง (High Volatility) - โอกาสดีในการออกไม้
            if recommendation == 'high_volatility':
                logger.info("🚀 [MARKET FILTER] High volatility detected - GREAT opportunity for profit taking!")
                logger.info("💡 [MARKET FILTER] Market moving = More chances to close positions at profit")
                return True
            
            # กรณีที่ตลาดนิ่งมาก - อนุญาตเข้าไม้
            if recommendation == 'favorable':
                logger.info("✅ [MARKET FILTER] Market conditions favorable for entry")
                return True
            
            # กรณีที่ตลาดมีเทรนด์ - ตรวจสอบทิศทาง
            if recommendation == 'trend_following':
                if trend == 'uptrend' and zone_type == 'support':
                    logger.info("✅ [MARKET FILTER] Uptrend + Support zone - good for BUY")
                    return True
                elif trend == 'downtrend' and zone_type == 'resistance':
                    logger.info("✅ [MARKET FILTER] Downtrend + Resistance zone - good for SELL")
                    return True
                else:
                    logger.info(f"✅ [MARKET FILTER] Trend following - allowing entry (trend: {trend}, zone: {zone_type})")
                    return True  # อนุญาตเข้าไม้ในเทรนด์
            
            # กรณีปกติ - อนุญาตเข้าไม้
            if recommendation == 'neutral':
                logger.info("✅ [MARKET FILTER] Normal market conditions - allowing entry")
                return True
            
            # กรณีอื่นๆ - อนุญาตเข้าไม้ (ไม่บล็อก)
            logger.info("✅ [MARKET FILTER] Allowing entry - no blocking conditions")
            return True
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error checking market conditions for entry: {e}")
            return True  # Default to allowing entry if error
    
    def _is_valid_entry_zone(self, zone: Dict, current_price: float) -> bool:
        """✅ ตรวจสอบว่า Zone ใช้ได้หรือไม่ - แบบง่าย ไม่ซ้ำซ้อนกับเงื่อนไขอื่น"""
        try:
            # ตรวจสอบว่าใช้ Zone นี้แล้วหรือยัง (Cooldown)
            zone_key = self._generate_zone_key(zone)
            if zone_key in self.used_zones:
                logger.debug(f"🚫 Zone {zone['price']} already used")
                return False
            
            # ตรวจสอบระยะห่างจากคำสั่งที่เปิดอยู่แล้ว (ปรับตาม Zone Strength)
            zone_strength_raw = zone.get('strength', 0)
            if zone_strength_raw > 60:  # Zone Strength สูง = ลดระยะห่าง
                min_distance_from_existing = 15.0
            elif zone_strength_raw > 40:  # Zone Strength ปานกลาง
                min_distance_from_existing = 25.0
            else:  # Zone Strength ต่ำ = ระยะห่างปกติ
                min_distance_from_existing = 35.0
                
            if hasattr(self, 'order_manager') and self.order_manager and self.symbol:
                try:
                    existing_positions = self.order_manager.get_positions_by_symbol(self.symbol)
                    for position in existing_positions:
                        if hasattr(position, 'price') and position.price > 0:
                            distance_from_existing = abs(zone['price'] - position.price) * 10000  # แปลงเป็น pips
                            if distance_from_existing < min_distance_from_existing:
                                logger.debug(f"🚫 Zone {zone['price']} too close to existing position: {distance_from_existing:.1f} pips < {min_distance_from_existing} pips")
                                return False
                except Exception as e:
                    logger.debug(f"⚠️ Could not check existing positions: {e}")
                    # ไม่ให้ error หยุดการทำงาน
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error validating entry zone: {e}")
            return False
    
    def _generate_zone_key(self, zone: Dict) -> str:
        """🔑 สร้าง key สำหรับ Zone"""
        try:
            return f"{zone['price']:.5f}_{zone.get('strength', 0)}"
        except Exception as e:
            logger.error(f"❌ Error generating zone key: {e}")
            return f"{zone.get('price', 0):.5f}_0"
    
    def _reset_daily_counter(self):
        """🔄 รีเซ็ต daily counter"""
        try:
            current_date = datetime.now().date()
            if current_date != self.last_reset_date:
                self.daily_trade_count = 0
                self.last_reset_date = current_date
        except Exception as e:
            logger.error(f"❌ Error resetting daily counter: {e}")
    
    def _cleanup_used_zones(self):
        """🧹 ทำความสะอาด used_zones"""
        try:
            current_time = datetime.now()
            expired_zones = []
            
            for zone_key, zone_data in self.used_zones.items():
                # ลบ zones ที่ใช้แล้วเกิน cooldown period
                cooldown_hours = self.zone_cooldown_hours + 12  # เพิ่ม 12 ชั่วโมงเพื่อให้แน่ใจว่าใช้ได้
                if current_time - zone_data['timestamp'] > timedelta(hours=cooldown_hours):
                    expired_zones.append(zone_key)
            
            for zone_key in expired_zones:
                del self.used_zones[zone_key]
                
            if expired_zones:
                logger.info(f"🧹 [ZONE CLEANUP] Removed {len(expired_zones)} expired zones from cooldown")
                
        except Exception as e:
            logger.error(f"❌ Error cleaning up used zones: {e}")
    
    def analyze_entry_opportunity(self, symbol: str, current_price: float, zones: Dict[str, List[Dict]], 
                                existing_positions: List = None) -> Optional[Dict]:
        """🔍 วิเคราะห์โอกาสเข้าไม้แบบใหม่ (Support/Resistance เท่านั้น)"""
        try:
            logger.info(f"🔍 [SMART ENTRY] Starting entry analysis for {symbol} at {current_price:.5f}")
            logger.info(f"🔍 [SMART ENTRY] Zones received: {len(zones.get('support', []))} support, {len(zones.get('resistance', []))} resistance")
            self.symbol = symbol  # ตั้งค่า symbol ที่ถูกต้อง
            # รีเซ็ต daily counter
            self._reset_daily_counter()
            
            # ตรวจสอบ daily limit
            if self.daily_trade_count >= self.max_daily_trades:
                logger.debug("🚫 Daily trade limit reached")
                return None
            
            # ทำความสะอาด used_zones (ลบ zones เก่า)
            self._cleanup_used_zones()
            
            # ตรวจสอบเวลาระหว่างคำสั่งซื้อและขาย (ป้องกันการเปิดคำสั่งใกล้กันเกินไป)
            if hasattr(self, 'last_trade_time') and self.last_trade_time is not None:
                time_since_last_trade = (datetime.now() - self.last_trade_time).total_seconds()
                if time_since_last_trade < self.min_time_between_trades:
                    logger.debug(f"🚫 Too soon since last trade: {time_since_last_trade:.1f}s < {self.min_time_between_trades}s")
                    return None
            
            # 🎯 เลือก Zone ตาม Pivot Point + Zone Strength (วิธี C)
            zone_type, selected_zone = self.select_zone_by_pivot_and_strength(current_price, zones)
            
            if not zone_type or not selected_zone:
                # Log all available zones for debugging
                support_zones = zones.get('support', [])
                resistance_zones = zones.get('resistance', [])
                
                logger.warning("=" * 80)
                logger.warning("🚫 [SMART ENTRY] NO SUITABLE ZONE FOUND FOR ENTRY")
                logger.warning("=" * 80)
                logger.warning(f"📊 [SMART ENTRY] Current Price: {current_price:.5f}")
                logger.warning(f"📈 [SMART ENTRY] Available Support Zones: {len(support_zones)}")
                for i, zone in enumerate(support_zones[:5], 1):
                    distance = abs(zone['price'] - current_price)
                    logger.warning(f"      {i}. {zone['price']:.5f} (Strength: {zone['strength']:.1f}, Distance: {distance:.5f})")
                
                logger.warning(f"📉 [SMART ENTRY] Available Resistance Zones: {len(resistance_zones)}")
                for i, zone in enumerate(resistance_zones[:5], 1):
                    distance = abs(zone['price'] - current_price)
                    logger.warning(f"      {i}. {zone['price']:.5f} (Strength: {zone['strength']:.1f}, Distance: {distance:.5f})")
                
                logger.warning(f"🔧 [SMART ENTRY] Min Zone Strength: {self.min_zone_strength} (normalized from 0-100 scale)")
                logger.warning("🔧 [SMART ENTRY] Zone Strength Scale: Raw values 0-100, Normalized to 0-1 for comparison")
                logger.warning("🔧 [SMART ENTRY] Example: Zone with strength 67.8 = 0.678 normalized")
                return None
            
            # ตรวจสอบว่า Zone ใช้ได้หรือไม่
            if not self._is_valid_entry_zone(selected_zone, current_price):
                logger.warning(f"🚫 Zone {selected_zone['price']} is not valid for entry")
                logger.warning(f"   Current Price: {current_price:.2f}, Zone Price: {selected_zone['price']:.2f}")
                return None
            
            # 🎯 ตรวจสอบ Market Conditions ก่อนเข้าไม้
            market_conditions = self._analyze_market_conditions(current_price, zones)
            if not self._should_enter_based_on_market_conditions(market_conditions, zone_type):
                logger.warning(f"🚫 [MARKET FILTER] Entry blocked by market conditions")
                logger.warning(f"   Market: {market_conditions.get('volatility', 'unknown')} volatility, {market_conditions.get('trend', 'unknown')} trend")
                return None
            
            # คำนวณ lot size แบบ dynamic (ปรับตาม Market Conditions)
            lot_size = self.calculate_dynamic_lot_size(selected_zone['strength'], selected_zone)
            
            # ปรับ lot size ตาม Market Conditions (ปรับใหม่ - ตลาดวิ่ง = โอกาสดี)
            if market_conditions.get('entry_recommendation') == 'high_volatility':
                lot_size *= 1.3  # เพิ่ม lot size ในตลาดวิ่ง (โอกาสดีในการออกไม้)
                logger.info(f"📊 [LOT ADJUSTMENT] High volatility - increased lot size by 30% (great opportunity!)")
            elif market_conditions.get('entry_recommendation') == 'favorable':
                lot_size *= 1.2  # เพิ่ม lot size ในตลาดที่ดี
                logger.info(f"📊 [LOT ADJUSTMENT] Favorable conditions - increased lot size by 20%")
            elif market_conditions.get('volatility') == 'low':
                lot_size *= 0.9  # ลด lot size ในตลาดนิ่ง
                logger.info(f"📊 [LOT ADJUSTMENT] Low volatility - reduced lot size by 10%")
            
            # คำนวณเป้าหมายกำไรแบบ dynamic (ปรับตาม Market Conditions)
            profit_target = self.calculate_dynamic_profit_target(lot_size)
            
            # ปรับ profit target ตาม Market Conditions (ปรับใหม่ - ตลาดวิ่ง = โอกาสดี)
            if market_conditions.get('entry_recommendation') == 'high_volatility':
                profit_target *= 1.5  # เพิ่ม profit target ในตลาดวิ่ง (โอกาสดีในการออกไม้)
                logger.info(f"📊 [PROFIT ADJUSTMENT] High volatility - increased profit target by 50% (great opportunity!)")
            elif market_conditions.get('entry_recommendation') == 'favorable':
                profit_target *= 0.9  # ลด profit target ในตลาดที่ดี (ออกไม้เร็วขึ้น)
                logger.info(f"📊 [PROFIT ADJUSTMENT] Favorable conditions - reduced profit target by 10%")
            elif market_conditions.get('volatility') == 'low':
                profit_target *= 1.1  # เพิ่ม profit target ในตลาดนิ่ง (ออกไม้ช้าขึ้น)
                logger.info(f"📊 [PROFIT ADJUSTMENT] Low volatility - increased profit target by 10%")
            
            # สร้าง entry opportunity
            if zone_type == 'support':
                direction = 'buy'  # BUY ที่ Support
                entry_reason = f"Support BUY at {selected_zone['price']:.5f} (Strength: {selected_zone['strength']})"
                logger.info(f"🎯 SELECTED SUPPORT ZONE: {selected_zone['price']:.2f} (Strength: {selected_zone['strength']:.1f})")
            else:  # resistance
                direction = 'sell'  # SELL ที่ Resistance
                entry_reason = f"Resistance SELL at {selected_zone['price']:.5f} (Strength: {selected_zone['strength']})"
                logger.info(f"🎯 SELECTED RESISTANCE ZONE: {selected_zone['price']:.2f} (Strength: {selected_zone['strength']:.1f})")
            
            entry_opportunity = {
                'direction': direction,
                'entry_price': current_price,
                'zone': selected_zone,
                'reason': entry_reason,
                'priority_score': selected_zone['strength'],
                'zone_type': zone_type,
                'lot_size': lot_size,
                'profit_target': profit_target,
                'loss_threshold': self.calculate_dynamic_loss_threshold(lot_size),
                'market_conditions': market_conditions,  # เพิ่มข้อมูล Market Conditions
                'zone_touches': selected_zone.get('touches', 0),
                'zone_algorithms': len(selected_zone.get('algorithms_used', [])),
                'quality_score': self._calculate_zone_quality_score(selected_zone)
            }
            
            logger.info(f"🎯 Entry Opportunity: {direction.upper()} at {current_price:.5f} "
                       f"(Zone: {selected_zone['price']:.5f}, Strength: {selected_zone['strength']}, "
                       f"Lot: {lot_size:.2f}, Target: ${profit_target:.2f})")
            logger.info(f"📊 Market Conditions: {market_conditions.get('volatility', 'unknown')} volatility, "
                       f"{market_conditions.get('trend', 'unknown')} trend, "
                       f"Recommendation: {market_conditions.get('entry_recommendation', 'neutral')}")
            
            # เพิ่มข้อมูลพิเศษสำหรับตลาดวิ่ง
            if market_conditions.get('entry_recommendation') == 'high_volatility':
                logger.info(f"🚀 [HIGH VOLATILITY TRADE] Market is moving - Great opportunity for profit taking!")
                logger.info(f"💡 [STRATEGY] Enter now to catch the movement and close at higher profit!")
            logger.info(f"🎯 Zone Quality: {selected_zone.get('touches', 0)} touches, "
                       f"{len(selected_zone.get('algorithms_used', []))} algorithms, "
                       f"Quality Score: {self._calculate_zone_quality_score(selected_zone):.1f}")
            
            logger.info(f"✅ [SMART ENTRY] Entry opportunity created successfully - Ready for execution")
            return entry_opportunity
            
        except Exception as e:
            logger.error(f"❌ Error analyzing entry opportunity: {e}")
            return None
    
    def find_recovery_opportunity(self, symbol: str, current_price: float, zones: Dict[str, List[Dict]], 
                                 existing_positions: List = None) -> List[Dict]:
        """🚀 หาโอกาสสร้าง Recovery Position เพื่อแก้ไม้ที่ขาดทุน"""
        try:
            logger.info("=" * 80)
            logger.info("🔧 [RECOVERY SYSTEM] Starting recovery opportunity analysis")
            logger.info("=" * 80)
            logger.info(f"📊 [RECOVERY] Checking {len(existing_positions) if existing_positions else 0} positions")
            
            if not existing_positions:
                logger.warning("🚫 [RECOVERY] No existing positions to check")
                return []
            
            recovery_opportunities = []
            
            # หาไม้ที่ต้องการความช่วยเหลือ
            losing_positions = 0
            for position in existing_positions:
                try:
                    pos_type = getattr(position, 'type', 0)
                    pos_price = getattr(position, 'price_open', 0)
                    pos_profit = getattr(position, 'profit', 0)
                    pos_lot = getattr(position, 'volume', 0)
                    
                    if not pos_price or not pos_lot:
                        continue
                    
                    # คำนวณเกณฑ์ขาดทุนแบบ dynamic
                    loss_threshold = self.calculate_dynamic_loss_threshold(pos_lot)
                    
                    logger.debug(f"🔍 [RECOVERY] Position: {pos_type} at {pos_price}, Profit: ${pos_profit:.2f}, Threshold: ${loss_threshold:.2f}")
                    
                    # ตรวจสอบว่าไม้ขาดทุนเกินเกณฑ์หรือไม่
                    if pos_profit >= loss_threshold:
                        logger.debug(f"✅ [RECOVERY] Position profit ${pos_profit:.2f} >= threshold ${loss_threshold:.2f} - No recovery needed")
                        continue  # ไม้ยังไม่ขาดทุนมาก
                    
                    losing_positions += 1
                    logger.warning(f"🚨 [RECOVERY] Losing Position Found: {pos_type} at {pos_price}, Loss: ${pos_profit:.2f} (Threshold: ${loss_threshold:.2f})")
                    
                    # หา Zone ที่แข็งแกร่งสำหรับ Recovery
                    if pos_type == 0:  # BUY ไม้ขาดทุน
                        # หา Support Zone ที่แข็งแกร่งสำหรับสร้าง SELL Recovery
                        support_zones = zones.get('support', [])
                        logger.info(f"🔍 [RECOVERY] For BUY: Found {len(support_zones)} support zones")
                        
                        strong_supports = [zone for zone in support_zones if zone['strength'] >= self.recovery_zone_strength]
                        logger.info(f"🔍 [RECOVERY] For BUY: Found {len(strong_supports)} strong support zones (strength >= {self.recovery_zone_strength})")
                        
                        if strong_supports:
                            # หา Support ที่เหมาะสม (ต่ำกว่าไม้ BUY)
                            suitable_supports = [zone for zone in strong_supports if zone['price'] < pos_price - 5]  # ลดจาก 20 เป็น 5 pips
                            logger.info(f"🔍 [RECOVERY] For BUY: Found {len(suitable_supports)} suitable supports (price < {pos_price - 5:.2f})")
                            
                            if suitable_supports:
                                best_support = max(suitable_supports, key=lambda x: x['strength'])
                                
                                # คำนวณ Recovery lot size
                                recovery_lot_size = self.calculate_recovery_lot_size(pos_profit, pos_lot)
                                
                                recovery_opportunities.append({
                                    'direction': 'sell',
                                    'entry_price': best_support['price'],
                                    'zone': best_support,
                                    'target_loss': pos_profit,
                                    'target_position_lot': pos_lot,
                                    'reason': f"Recovery SELL for BUY position (Loss: ${pos_profit:.2f})",
                                    'zone_type': 'support'
                                })
                    
                    elif pos_type == 1:  # SELL ไม้ขาดทุน
                        # หา Resistance Zone ที่แข็งแกร่งสำหรับสร้าง BUY Recovery
                        resistance_zones = zones.get('resistance', [])
                        logger.info(f"🔍 [RECOVERY] For SELL: Found {len(resistance_zones)} resistance zones")
                        
                        strong_resistances = [zone for zone in resistance_zones if zone['strength'] >= self.recovery_zone_strength]
                        logger.info(f"🔍 [RECOVERY] For SELL: Found {len(strong_resistances)} strong resistance zones (strength >= {self.recovery_zone_strength})")
                        
                        if strong_resistances:
                            # หา Resistance ที่เหมาะสม (สูงกว่าไม้ SELL)
                            suitable_resistances = [zone for zone in strong_resistances if zone['price'] > pos_price + 5]  # ลดจาก 20 เป็น 5 pips
                            logger.info(f"🔍 [RECOVERY] For SELL: Found {len(suitable_resistances)} suitable resistances (price > {pos_price + 5:.2f})")
                            
                            if suitable_resistances:
                                best_resistance = max(suitable_resistances, key=lambda x: x['strength'])
                                
                                # คำนวณ Recovery lot size
                                recovery_lot_size = self.calculate_recovery_lot_size(pos_profit, pos_lot)
                                
                                recovery_opportunities.append({
                                    'direction': 'buy',
                                    'entry_price': best_resistance['price'],
                                    'zone': best_resistance,
                                    'target_loss': pos_profit,
                                    'target_position_lot': pos_lot,
                                    'reason': f"Recovery BUY for SELL position (Loss: ${pos_profit:.2f})",
                                    'zone_type': 'resistance'
                                })
                
                except Exception as e:
                    logger.error(f"❌ Error processing position for recovery: {e}")
                    continue
            
            # เรียงลำดับตาม priority (ไม้ที่ขาดทุนมากที่สุดก่อน)
            recovery_opportunities.sort(key=lambda x: x['target_loss'])
            
            logger.info("-" * 80)
            logger.info(f"📊 [RECOVERY] Summary: {losing_positions} losing positions, {len(recovery_opportunities)} recovery opportunities found")
            logger.info("-" * 80)
            
            if recovery_opportunities:
                logger.info("✅ [RECOVERY] Recovery opportunities found:")
                for i, opp in enumerate(recovery_opportunities):
                    logger.info(f"   {i+1}. {opp['reason']} at {opp['entry_price']:.2f}")
            else:
                logger.warning("🚫 [RECOVERY] No recovery opportunities found")
                if losing_positions > 0:
                    logger.warning("   🔧 [RECOVERY] Reason: No suitable zones found for recovery")
            
            return recovery_opportunities[:3]  # ส่งคืนสูงสุด 3 โอกาส
            
        except Exception as e:
            logger.error(f"❌ [RECOVERY] Error finding recovery opportunity: {e}")
            return []
    
    def calculate_recovery_lot_size(self, target_loss: float, target_position_lot: float) -> float:
        """📊 คำนวณ lot size สำหรับ Recovery Position"""
        try:
            # คำนวณ lot size ที่จะช่วยให้ไม้กลับมาทำกำไร
            # ใช้ lot size ที่จะช่วยให้ไม้กำไร 50 pips
            recovery_lot_size = abs(target_loss) / (self.profit_target_pips * 10)
            
            # ปรับตาม lot size ของไม้ที่ต้องการความช่วยเหลือ
            if target_position_lot > 0:
                # ใช้ lot size ที่ใกล้เคียงกับไม้ที่ต้องการความช่วยเหลือ
                recovery_lot_size = min(recovery_lot_size, target_position_lot * 1.5)
            
            # จำกัด lot size
            return max(self.min_lot_size, min(self.max_lot_size, recovery_lot_size))
                
        except Exception as e:
            logger.error(f"❌ Error calculating recovery lot size: {e}")
            return self.min_lot_size  # fallback
    
    def get_entry_statistics(self) -> Dict:
        """📊 สถิติการเข้าไม้"""
        try:
            return {
                'daily_trade_count': self.daily_trade_count,
                'max_daily_trades': self.max_daily_trades,
                'used_zones_count': len(self.used_zones),
                'support_buy_enabled': self.support_buy_enabled,
                'resistance_sell_enabled': self.resistance_sell_enabled,
                'min_zone_strength': self.min_zone_strength,
                'recovery_zone_strength': self.recovery_zone_strength,
                'profit_target_pips': self.profit_target_pips,
                'loss_threshold_pips': self.loss_threshold_pips,
                'risk_percent_per_trade': self.risk_percent_per_trade
            }
        except Exception as e:
            logger.error(f"❌ Error getting entry statistics: {e}")
            return {}
    def execute_entry(self, entry_plan: Dict) -> Optional[int]:
        """📈 ทำงานเข้าไม้ (ใช้ OrderManager แทน mt5.order_send)"""
        try:
            if not entry_plan:
                return None
            
            direction = entry_plan['direction']
            lot_size = entry_plan['lot_size']
            entry_price = entry_plan['entry_price']
            zone = entry_plan['zone']
            reason = entry_plan['reason']
            
            # ตั้งค่า Take Profit และ Stop Loss
            profit_target = entry_plan.get('profit_target', 50.0)
            loss_threshold = entry_plan.get('loss_threshold', -50.0)
            
            # ระบบแก้ไม้ - ไม่ตั้ง TP/SL (ให้ระบบปิดไม้จัดการเอง)
            tp_price = 0.0  # ไม่ตั้ง TP
            sl_price = 0.0  # ไม่ตั้ง SL
            
            logger.info(f"🚀 [SMART ENTRY] Executing entry: {direction.upper()} {lot_size:.2f} lots at {entry_price:.5f}")
            logger.info(f"   Reason: {reason}")
            
            # ใช้ OrderManager แทน mt5.order_send โดยตรง
            # สร้าง Signal object สำหรับ OrderManager
            from trading_conditions import Signal
            
            # กำหนด comment ตามประเภทการเข้าไม้
            if reason and ('Recovery' in str(reason) or 'recovery' in str(reason).lower()):
                comment = f"RECOVERY: {reason}"
                logger.info(f"🔧 [SMART ENTRY] Recovery Entry Comment: {comment}")
            else:
                comment = f"SMART_ENTRY: {reason}" if reason else f"SMART_ENTRY: {direction.upper()} at {entry_price:.5f}"
                logger.info(f"🎯 [SMART ENTRY] Smart Entry Comment: {comment}")
            
            # ตรวจสอบ comment ก่อนสร้าง Signal
            if not comment or comment is None:
                comment = f"SMART_ENTRY: {direction.upper()} at {entry_price:.5f}"
            
            signal = Signal(
                direction=direction.upper(),
                symbol=self.symbol,
                strength=zone.get('strength', 50),
                confidence=80.0,
                timestamp=datetime.now(),
                price=entry_price,
                comment=str(comment),  # แปลงเป็น string เสมอ
                stop_loss=0.0,  # ไม่ตั้ง SL
                take_profit=0.0  # ไม่ตั้ง TP
            )
            
            # ใช้ OrderManager ในการส่งคำสั่ง (ไฟล์ order_management.py)
            # ต้องส่ง order_manager มาจาก main system
            if hasattr(self, 'order_manager') and self.order_manager:
                logger.info(f"📤 [SMART ENTRY] Sending order to OrderManager (order_management.py)")
                logger.info(f"   Symbol: {signal.symbol}, Direction: {signal.direction}, Lot: {lot_size:.2f}")
                
                result = self.order_manager.place_order_from_signal(
                    signal=signal,
                    lot_size=lot_size,
                    account_balance=1000.0  # fallback balance
                )
                
                if result and hasattr(result, 'success') and result.success:
                    ticket = getattr(result, 'ticket', None)
                    logger.info(f"✅ [SMART ENTRY] Entry executed via OrderManager: Ticket {ticket}")
                    logger.info(f"   🎯 [SMART ENTRY] Recovery system - No TP/SL (managed by closing system)")
                    
                    # บันทึก zone ที่ใช้แล้ว
                    zone_key = self._generate_zone_key(zone)
                    self.used_zones[zone_key] = {
                        'timestamp': datetime.now(),
                        'ticket': ticket
                    }
                    
                    # อัปเดต daily counter
                    self.daily_trade_count += 1
                    
                    # อัปเดตเวลาคำสั่งล่าสุด
                    self.last_trade_time = datetime.now()
                
                    return ticket
                else:
                    error_msg = getattr(result, 'error_message', 'Unknown error') if result else 'No result'
                    logger.error(f"❌ [SMART ENTRY] OrderManager failed: {error_msg}")
                    return None
            else:
                logger.error(f"❌ [SMART ENTRY] OrderManager not available")
                return None
                
        except Exception as e:
            logger.error(f"❌ [SMART ENTRY] Error executing entry: {e}")
            return None
