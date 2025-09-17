import MetaTrader5 as mt5
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import logging

# 🧠 AI INTELLIGENCE SYSTEMS
from ai_entry_intelligence import AIEntryIntelligence, EntryDecision, EntryAnalysis
from ai_decision_engine import AIDecisionEngine, CombinedDecision

logger = logging.getLogger(__name__)

class SmartEntrySystem:
    """🎯 ระบบเข้าไม้อัจฉริยะแบบใหม่ (Support/Resistance เท่านั้น)"""
    
    def __init__(self, mt5_connection, zone_analyzer):
        self.mt5_connection = mt5_connection
        self.zone_analyzer = zone_analyzer
        self.symbol = None  # จะถูกตั้งค่าจาก main system
        
        # 🧠 AI INTELLIGENCE SYSTEMS
        self.ai_entry_intelligence = AIEntryIntelligence()
        self.ai_decision_engine = AIDecisionEngine()
        
        # Entry Parameters (ปรับให้เทรดได้ทุกสภาวะตลาด)
        self.support_buy_enabled = True      # เปิด Support entries (BUY ที่ Support)
        self.resistance_sell_enabled = True  # เปิด Resistance entries (SELL ที่ Resistance)
        self.trend_following_enabled = True  # เปิด Trend Following entries
        self.breakout_enabled = True         # เปิด Breakout entries
        self.range_trading_enabled = True    # เปิด Range Trading entries
        
        # Dynamic Calculation Parameters - ปรับให้เทรดได้บ่อยขึ้น
        self.profit_target_pips = 20  # ลดเป้าหมายกำไรเพื่อให้ปิดง่ายขึ้น
        self.loss_threshold_pips = 30  # เพิ่มเกณฑ์ขาดทุนเพื่อให้มีโอกาสมากขึ้น
        self.recovery_zone_strength = 5  # ลด Zone strength เพื่อหา zone ได้มากขึ้น
        self.min_zone_strength = 0.01  # ลด Zone strength ขั้นต่ำเพื่อหาโอกาสได้มากขึ้น
        
        # Risk Management (Dynamic) - ปรับให้เทรดได้บ่อยขึ้น
        self.risk_percent_per_trade = 0.015  # ลดความเสี่ยงต่อ trade เพื่อเทรดได้บ่อยขึ้น
        self.max_daily_trades = 50  # เพิ่มจำนวน trade ต่อวัน
        self.min_time_between_trades = 15  # ลดเวลาระหว่าง trades เป็น 15 วินาที
        
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
        """🎯 เลือก Zone ตาม Pivot Point + Zone Strength (วิธี C) - ปรับปรุงให้ตรวจสอบระยะห่าง"""
        try:
            # คำนวณ Pivot Point
            pivot_point = self.calculate_pivot_point(current_price, zones)
            support_zones = zones.get('support', [])
            resistance_zones = zones.get('resistance', [])
            
            # แสดงราคาใกล้เคียงกับ current_price (ลด log)
            if support_zones:
                closest_support = min(support_zones, key=lambda x: abs(x['price'] - current_price))
                distance_support = abs(closest_support['price'] - current_price)
            if resistance_zones:
                closest_resistance = min(resistance_zones, key=lambda x: abs(x['price'] - current_price))
                distance_resistance = abs(closest_resistance['price'] - current_price)
            
            logger.info(f"🔍 [ZONE SELECTION] Price: {current_price:.5f}, Pivot: {pivot_point:.5f}")
            logger.info(f"🔍 [ZONE SELECTION] Zones: {len(support_zones)} support, {len(resistance_zones)} resistance")
            if support_zones:
                logger.info(f"🔍 [ZONE SELECTION] Closest support: {closest_support['price']:.5f} (distance: {distance_support:.5f})")
            if resistance_zones:
                logger.info(f"🔍 [ZONE SELECTION] Closest resistance: {closest_resistance['price']:.5f} (distance: {distance_resistance:.5f})")
            
            if not support_zones or not resistance_zones:
                logger.warning("🚫 [ZONE SELECTION] No support or resistance zones available")
                return None, None
            
            # ตรวจสอบระยะห่างระหว่าง support และ resistance ที่ใกล้ที่สุด (ลดข้อจำกัด)
            min_distance_pips = 20.0  # ลดระยะห่างขั้นต่ำเป็น 20 pips เพื่อหาโอกาสได้มากขึ้น
            if support_zones and resistance_zones:
                closest_support_price = min(support_zones, key=lambda x: abs(x['price'] - current_price))['price']
                closest_resistance_price = min(resistance_zones, key=lambda x: abs(x['price'] - current_price))['price']
                distance_between_zones = abs(closest_support_price - closest_resistance_price) * 100  # แปลงเป็น pips สำหรับ XAUUSD
                
                logger.info(f"🔍 [ZONE SELECTION] Distance between closest zones: {distance_between_zones:.1f} pips")
                
                if distance_between_zones < min_distance_pips:
                    logger.warning(f"🚫 [ZONE SELECTION] Zones too close: {distance_between_zones:.1f} pips < {min_distance_pips} pips")
                    logger.warning(f"🚫 [ZONE SELECTION] Support: {closest_support_price:.5f}, Resistance: {closest_resistance_price:.5f}")
                    return None, None
            
            # เลือก Zone ตาม Pivot Point (ปรับให้เลือกที่ใกล้ที่สุด + กรองตามระยะห่าง)
            if current_price < pivot_point:
                # ราคาต่ำกว่า Pivot → หา Support ที่ใกล้ที่สุด
                valid_supports = []
                for zone in support_zones:
                    if zone['strength'] >= self.min_zone_strength:
                        # ตรวจสอบระยะห่างด้วย Dynamic Distance (ปรับให้สอดคล้องกับ XAUUSD)
                        price_diff = abs(current_price - zone['price'])
                        distance = price_diff * 100  # แปลงเป็น pips สำหรับ XAUUSD
                        zone_strength = zone.get('strength', 0)
                        
                        # Dynamic Distance ตาม Zone Strength (ปรับให้สอดคล้องกับ validation)
                        if zone_strength >= 0.8:
                            max_distance = 500.0  # Zone แข็งแกร่งมาก = 500 pips (5.0 USD)
                        elif zone_strength >= 0.5:
                            max_distance = 400.0  # Zone แข็งแกร่ง = 400 pips (4.0 USD)
                        elif zone_strength >= 0.2:
                            max_distance = 300.0  # Zone ปานกลาง = 300 pips (3.0 USD)
                        else:
                            max_distance = 200.0  # Zone อ่อนแอ = 200 pips (2.0 USD)
                        
                        if distance <= max_distance:
                            valid_supports.append(zone)
                
                logger.info(f"🔍 [ZONE SELECTION] Looking for SUPPORT zones. Valid: {len(valid_supports)} (min_strength: {self.min_zone_strength})")
                
                if valid_supports:
                    # เลือก Support ที่ใกล้ที่สุดและแข็งแกร่งพอ
                    best_support = min(valid_supports, key=lambda x: abs(current_price - x['price']))
                    distance_pips = abs(current_price - best_support['price']) * 100
                    logger.info(f"✅ [ZONE SELECTION] Selected SUPPORT: {best_support['price']:.5f} (strength: {best_support['strength']:.1f}, distance: {distance_pips:.1f} pips)")
                    return 'support', best_support
                else:
                    # 🎯 Fallback: ถ้าไม่มี zone ที่ผ่าน validation ให้เลือกที่ใกล้ที่สุด
                    logger.warning("🚫 [ZONE SELECTION] No valid SUPPORT zones found, trying fallback...")
                    if support_zones:
                        closest_support = min(support_zones, key=lambda x: abs(current_price - x['price']))
                        distance_pips = abs(current_price - closest_support['price']) * 100
                        logger.info(f"🔄 [ZONE SELECTION] Fallback SUPPORT: {closest_support['price']:.5f} (strength: {closest_support['strength']:.1f}, distance: {distance_pips:.1f} pips)")
                        return 'support', closest_support
                    else:
                        logger.warning("🚫 [ZONE SELECTION] No SUPPORT zones available")
                
            else:
                # ราคาสูงกว่า Pivot → หา Resistance ที่ใกล้ที่สุด
                valid_resistances = []
                for zone in resistance_zones:
                    if zone['strength'] >= self.min_zone_strength:
                        # ตรวจสอบระยะห่างด้วย Dynamic Distance (ปรับให้สอดคล้องกับ XAUUSD)
                        price_diff = abs(current_price - zone['price'])
                        distance = price_diff * 100  # แปลงเป็น pips สำหรับ XAUUSD
                        zone_strength = zone.get('strength', 0)
                        
                        # Dynamic Distance ตาม Zone Strength (ปรับให้สอดคล้องกับ validation)
                        if zone_strength >= 0.8:
                            max_distance = 500.0  # Zone แข็งแกร่งมาก = 500 pips (5.0 USD)
                        elif zone_strength >= 0.5:
                            max_distance = 400.0  # Zone แข็งแกร่ง = 400 pips (4.0 USD)
                        elif zone_strength >= 0.2:
                            max_distance = 300.0  # Zone ปานกลาง = 300 pips (3.0 USD)
                        else:
                            max_distance = 200.0  # Zone อ่อนแอ = 200 pips (2.0 USD)
                        
                        if distance <= max_distance:
                            valid_resistances.append(zone)
                
                logger.info(f"🔍 [ZONE SELECTION] Looking for RESISTANCE zones. Valid: {len(valid_resistances)} (min_strength: {self.min_zone_strength})")
                
                if valid_resistances:
                    # เลือก Resistance ที่ใกล้ที่สุดและแข็งแกร่งพอ
                    best_resistance = min(valid_resistances, key=lambda x: abs(current_price - x['price']))
                    distance_pips = abs(current_price - best_resistance['price']) * 100
                    logger.info(f"✅ [ZONE SELECTION] Selected RESISTANCE: {best_resistance['price']:.5f} (strength: {best_resistance['strength']:.1f}, distance: {distance_pips:.1f} pips)")
                    return 'resistance', best_resistance
                else:
                    # 🎯 Fallback: ถ้าไม่มี zone ที่ผ่าน validation ให้เลือกที่ใกล้ที่สุด
                    logger.warning("🚫 [ZONE SELECTION] No valid RESISTANCE zones found, trying fallback...")
                    if resistance_zones:
                        closest_resistance = min(resistance_zones, key=lambda x: abs(current_price - x['price']))
                        distance_pips = abs(current_price - closest_resistance['price']) * 100
                        logger.info(f"🔄 [ZONE SELECTION] Fallback RESISTANCE: {closest_resistance['price']:.5f} (strength: {closest_resistance['strength']:.1f}, distance: {distance_pips:.1f} pips)")
                        return 'resistance', closest_resistance
                    else:
                        logger.warning("🚫 [ZONE SELECTION] No RESISTANCE zones available")
                
            # 🎯 Final Fallback: ถ้าไม่มี zone ที่ผ่าน validation ให้เลือกที่ใกล้ที่สุด
            if support_zones or resistance_zones:
                all_zones = support_zones + resistance_zones
                closest_zone = min(all_zones, key=lambda x: abs(current_price - x['price']))
                distance_pips = abs(current_price - closest_zone['price']) * 100
                zone_type = 'support' if closest_zone in support_zones else 'resistance'
                logger.warning(f"🔄 [ZONE SELECTION] Final fallback - selecting closest {zone_type.upper()}: {closest_zone['price']:.5f} (strength: {closest_zone['strength']:.1f}, distance: {distance_pips:.1f} pips)")
                return zone_type, closest_zone
            
            return None, None
            
        except Exception as e:
            logger.error(f"❌ Error selecting zone by pivot and strength: {e}")
            return None, None
    
    def _is_valid_entry_zone(self, zone: Dict, current_price: float, zones: Dict = None) -> bool:
        """✅ ตรวจสอบว่า Zone ใช้ได้หรือไม่"""
        try:
            # ตรวจสอบ Zone Strength
            if zone.get('strength', 0) < self.min_zone_strength:
                logger.info(f"🚫 Zone {zone['price']} too weak: {zone.get('strength', 0)} < {self.min_zone_strength}")
                return False
            
            # ตรวจสอบว่าใช้ Zone นี้แล้วหรือยัง (Dynamic Reuse Logic)
            zone_key = self._generate_zone_key(zone)
            if zone_key in self.used_zones:
                zone_data = self.used_zones[zone_key]
                time_since_used = datetime.now() - zone_data['timestamp']
                
                # 🎯 Dynamic Zone Reuse: อนุญาตให้ใช้ซ้ำได้ตามเงื่อนไข
                zone_strength = zone.get('strength', 0)
                current_strength = zone_data.get('strength', 0)
                
                # เงื่อนไขการใช้ซ้ำ:
                # 1. Zone แข็งแกร่งขึ้น (strength เพิ่มขึ้น)
                # 2. ผ่านไปแล้วอย่างน้อย 30 นาที
                # 3. Zone แข็งแกร่งมาก (strength > 0.8) ใช้ซ้ำได้เร็วขึ้น
                can_reuse = False
                
                if zone_strength > current_strength + 0.1:  # Strength เพิ่มขึ้น
                    can_reuse = True
                    logger.info(f"✅ Zone {zone['price']} can reuse - strength improved: {current_strength:.2f} → {zone_strength:.2f}")
                elif zone_strength >= 0.8 and time_since_used > timedelta(minutes=30):  # Zone แข็งแกร่งมาก
                    can_reuse = True
                    logger.info(f"✅ Zone {zone['price']} can reuse - strong zone after {time_since_used}")
                elif time_since_used > timedelta(hours=1):  # ผ่านไปแล้ว 1 ชั่วโมง
                    can_reuse = True
                    logger.info(f"✅ Zone {zone['price']} can reuse - time passed: {time_since_used}")
                
                if not can_reuse:
                    logger.info(f"🚫 Zone {zone['price']} already used (strength: {current_strength:.2f}, time: {time_since_used})")
                    return False
            
            # ตรวจสอบระยะห่างจากราคาปัจจุบัน - Dynamic Distance ตาม Zone Strength
            # สำหรับ XAUUSD: 1 pip = 0.01, ต้องแปลงเป็น pips
            price_diff = abs(current_price - zone['price'])
            distance = price_diff * 100  # แปลงเป็น pips สำหรับ XAUUSD
            
            # 🎯 Dynamic Distance: Zone แข็งแกร่ง = ระยะห่างมากขึ้น (ปรับให้ยืดหยุ่นมากขึ้น)
            zone_strength = zone.get('strength', 0)
            
            # เพิ่มระยะห่างสูงสุดเพื่อให้มีโอกาสมากขึ้น (ปรับให้เหมาะสมกับ XAUUSD)
            if zone_strength >= 0.8:
                max_distance = 500.0  # Zone แข็งแกร่งมาก = 500 pips (5.0 USD)
            elif zone_strength >= 0.5:
                max_distance = 400.0  # Zone แข็งแกร่ง = 400 pips (4.0 USD)
            elif zone_strength >= 0.2:
                max_distance = 300.0  # Zone ปานกลาง = 300 pips (3.0 USD)
            else:
                max_distance = 200.0  # Zone อ่อนแอ = 200 pips (2.0 USD)
            
            # 🎯 Market Condition Adjustment: ปรับตามสภาวะตลาด
            # ถ้าราคาอยู่ในช่วง sideways หรือ range ให้เพิ่มระยะห่าง
            if hasattr(self, 'zone_analyzer') and self.zone_analyzer:
                try:
                    # ตรวจสอบว่าเป็น range market หรือไม่
                    support_zones = zones.get('support', [])
                    resistance_zones = zones.get('resistance', [])
                    
                    if support_zones and resistance_zones:
                        support_price = min([z['price'] for z in support_zones])
                        resistance_price = max([z['price'] for z in resistance_zones])
                        range_size = resistance_price - support_price
                        
                        # ถ้า range เล็ก (sideways market) ให้เพิ่มระยะห่าง
                        if range_size < 1.0:  # Range < 1.0 USD (100 pips สำหรับ XAUUSD)
                            max_distance *= 1.5  # เพิ่ม 50%
                            logger.debug(f"🎯 Range market detected, increased max_distance to {max_distance:.1f} pips")
                except Exception as e:
                    logger.debug(f"⚠️ Could not check market condition: {e}")
                
            if distance > max_distance:
                logger.info(f"🚫 Zone {zone['price']} too far: {distance:.1f} pips (max: {max_distance}, strength: {zone_strength:.2f})")
                return False
            
            # ตรวจสอบระยะห่างจากคำสั่งที่เปิดอยู่แล้ว (ป้องกันการเปิดคำสั่งใกล้กันเกินไป)
            min_distance_from_existing = 20.0  # ระยะห่างขั้นต่ำ 20 pips จากคำสั่งที่มีอยู่
            if hasattr(self, 'order_manager') and self.order_manager and self.symbol:
                try:
                    existing_positions = self.order_manager.get_positions_by_symbol(self.symbol)
                    for position in existing_positions:
                        if hasattr(position, 'price') and position.price > 0:
                            distance_from_existing = abs(zone['price'] - position.price) * 10000  # แปลงเป็น pips
                            if distance_from_existing < min_distance_from_existing:
                                logger.warning(f"🚫 Zone {zone['price']} too close to existing position at {position.price}: {distance_from_existing:.1f} pips < {min_distance_from_existing} pips")
                                return False
                except Exception as e:
                    logger.debug(f"⚠️ Could not check existing positions: {e}")
                    # ไม่ให้ error หยุดการทำงาน
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error validating entry zone: {e}")
            return False
    
    def _generate_zone_key(self, zone: Dict) -> str:
        """🔑 สร้าง key สำหรับ Zone (Dynamic - ใช้เฉพาะ price)"""
        try:
            # ใช้เฉพาะ price โดยไม่รวม strength เพื่อให้ zone เดียวกันสามารถใช้ซ้ำได้
            return f"{zone['price']:.5f}"
        except Exception as e:
            logger.error(f"❌ Error generating zone key: {e}")
            return f"{zone.get('price', 0):.5f}"
    
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
        """🧹 ทำความสะอาด used_zones (Dynamic - ใช้เวลาสั้นลง)"""
        try:
            current_time = datetime.now()
            expired_zones = []
            
            for zone_key, zone_data in self.used_zones.items():
                # 🎯 Dynamic Cleanup: ลดเวลาลงเหลือ 2-4 ชั่วโมง ตาม market volatility
                time_since_used = current_time - zone_data['timestamp']
                
                # ถ้าเป็น zone ที่แข็งแกร่ง (strength > 0.7) ให้ใช้ซ้ำได้เร็วขึ้น
                if 'strength' in zone_data and zone_data['strength'] > 0.7:
                    cleanup_hours = 2  # Zone แข็งแกร่ง = 2 ชั่วโมง
                else:
                    cleanup_hours = 4  # Zone ปกติ = 4 ชั่วโมง
                
                if time_since_used > timedelta(hours=cleanup_hours):
                    expired_zones.append(zone_key)
                    logger.debug(f"🧹 Zone {zone_key} expired after {time_since_used}")
            
            for zone_key in expired_zones:
                del self.used_zones[zone_key]
                logger.info(f"🧹 Cleaned up expired zone: {zone_key}")
                
        except Exception as e:
            logger.error(f"❌ Error cleaning up used zones: {e}")
    
    def analyze_entry_opportunity(self, symbol: str, current_price: float, zones: Dict[str, List[Dict]], 
                                existing_positions: List = None) -> Optional[Dict]:
        """🧠 AI-Enhanced Entry Analysis - ใช้ AI Intelligence ในการวิเคราะห์โอกาสเข้าไม้"""
        try:
            logger.info(f"🧠 [AI ENTRY] Starting AI-enhanced entry analysis for {symbol} at {current_price:.5f}")
            logger.info(f"🧠 [AI ENTRY] Zones received: {len(zones.get('support', []))} support, {len(zones.get('resistance', []))} resistance")
            self.symbol = symbol  # ตั้งค่า symbol ที่ถูกต้อง
            
            # รีเซ็ต daily counter
            self._reset_daily_counter()
            
            # ตรวจสอบ daily limit
            if self.daily_trade_count >= self.max_daily_trades:
                logger.debug("🚫 Daily trade limit reached")
                return None
            
            # ทำความสะอาด used_zones (ลบ zones เก่า)
            self._cleanup_used_zones()
            
            # ตรวจสอบเวลาระหว่างคำสั่งซื้อและขาย (ลดข้อจำกัดเวลา)
            if hasattr(self, 'last_trade_time') and self.last_trade_time is not None:
                time_since_last_trade = (datetime.now() - self.last_trade_time).total_seconds()
                if time_since_last_trade < self.min_time_between_trades:
                    logger.debug(f"🚫 Too soon since last trade: {time_since_last_trade:.1f}s < {self.min_time_between_trades}s")
                    return None
            
            # 🧠 AI Entry Analysis
            market_data = {
                'current_price': current_price,
                'trend_direction': 'sideways',  # TODO: วิเคราะห์จากข้อมูลจริง
                'volatility': 'normal',  # TODO: วิเคราะห์จากข้อมูลจริง
                'session': 'unknown'  # TODO: วิเคราะห์จากข้อมูลจริง
            }
            
            # ใช้ AI Decision Engine วิเคราะห์โอกาสเข้าไม้
            ai_decision = self.ai_decision_engine.make_entry_decision(
                symbol, current_price, zones, existing_positions or [], market_data
            )
            
            # ตรวจสอบ AI Decision
            if ai_decision.final_decision.get('action') == 'NO_ENTRY':
                logger.debug(f"🧠 AI recommends no entry: {ai_decision.final_decision.get('reasoning', 'No reasoning')}")
                return None
            
            # 🎯 เลือก Zone ตาม AI Decision หรือ Traditional Logic
            zone_type, selected_zone = self._select_zone_from_ai_decision(ai_decision, current_price, zones)
            
            # ถ้า AI ไม่แนะนำ Zone ให้ใช้ Traditional Logic
            if not zone_type or not selected_zone:
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
                
                logger.warning(f"🔧 [SMART ENTRY] Min Zone Strength: {self.min_zone_strength}")
                logger.warning("🔧 [SMART ENTRY] Suggestion: ลด min_zone_strength หรือเพิ่ม zone_tolerance")
                return None
            
            # ตรวจสอบว่า Zone ใช้ได้หรือไม่
            if not self._is_valid_entry_zone(selected_zone, current_price, zones):
                logger.warning(f"🚫 Zone {selected_zone['price']} is not valid for entry")
                logger.warning(f"   Current Price: {current_price:.2f}, Zone Price: {selected_zone['price']:.2f}")
                return None
            
            # คำนวณ lot size แบบ dynamic
            lot_size = self.calculate_dynamic_lot_size(selected_zone['strength'], selected_zone)
            
            # คำนวณเป้าหมายกำไรแบบ dynamic
            profit_target = self.calculate_dynamic_profit_target(lot_size)
            
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
                'ai_decision': ai_decision  # เพิ่ม AI Decision
            }
            
            logger.info(f"🧠 AI Entry Opportunity: {direction.upper()} at {current_price:.5f} "
                       f"(Zone: {selected_zone['price']:.5f}, Strength: {selected_zone['strength']}, "
                       f"Lot: {lot_size:.2f}, Target: ${profit_target:.2f}, "
                       f"AI Confidence: {ai_decision.confidence:.1f}%)")
            
            logger.info(f"✅ [AI ENTRY] AI-enhanced entry opportunity created successfully - Ready for execution")
            return entry_opportunity
            
        except Exception as e:
            logger.error(f"❌ Error in AI-enhanced entry analysis: {e}")
            return None
    
    def _select_zone_from_ai_decision(self, ai_decision, current_price: float, zones: Dict[str, List[Dict]]) -> Tuple[Optional[str], Optional[Dict]]:
        """เลือก Zone จาก AI Decision"""
        try:
            # ตรวจสอบ AI Decision
            if not ai_decision or not ai_decision.ai_decision:
                return None, None
            
            ai_entry_decision = ai_decision.ai_decision
            direction = ai_entry_decision.direction
            
            # หา Zone ที่เหมาะสมตาม AI Decision - กรองตามระยะห่างด้วย
            if direction == "BUY":
                # หา Support Zone ที่ดีที่สุด
                support_zones = zones.get('support', [])
                if support_zones:
                    # กรอง Support Zones ตามระยะห่างก่อน
                    valid_supports = []
                    for zone in support_zones:
                        distance = abs(current_price - zone['price'])
                        zone_strength = zone.get('strength', 0)
                        
                        # Dynamic Distance ตาม Zone Strength
                        if zone_strength >= 0.8:
                            max_distance = 150.0  # Zone แข็งแกร่งมาก = 150 pips
                        elif zone_strength >= 0.5:
                            max_distance = 100.0  # Zone แข็งแกร่ง = 100 pips
                        elif zone_strength >= 0.2:
                            max_distance = 75.0   # Zone ปานกลาง = 75 pips
                        else:
                            max_distance = 50.0   # Zone อ่อนแอ = 50 pips
                        
                        if distance <= max_distance:
                            valid_supports.append(zone)
                    
                    if valid_supports:
                        # เลือก Zone ที่แข็งแกร่งที่สุดจากที่กรองแล้ว
                        best_zone = max(valid_supports, key=lambda z: z.get('strength', 0))
                        return 'support', best_zone
            elif direction == "SELL":
                # หา Resistance Zone ที่ดีที่สุด
                resistance_zones = zones.get('resistance', [])
                if resistance_zones:
                    # กรอง Resistance Zones ตามระยะห่างก่อน
                    valid_resistances = []
                    for zone in resistance_zones:
                        distance = abs(current_price - zone['price'])
                        zone_strength = zone.get('strength', 0)
                        
                        # Dynamic Distance ตาม Zone Strength
                        if zone_strength >= 0.8:
                            max_distance = 150.0  # Zone แข็งแกร่งมาก = 150 pips
                        elif zone_strength >= 0.5:
                            max_distance = 100.0  # Zone แข็งแกร่ง = 100 pips
                        elif zone_strength >= 0.2:
                            max_distance = 75.0   # Zone ปานกลาง = 75 pips
                        else:
                            max_distance = 50.0   # Zone อ่อนแอ = 50 pips
                        
                        if distance <= max_distance:
                            valid_resistances.append(zone)
                    
                    if valid_resistances:
                        # เลือก Zone ที่แข็งแกร่งที่สุดจากที่กรองแล้ว
                        best_zone = max(valid_resistances, key=lambda z: z.get('strength', 0))
                        return 'resistance', best_zone
            
            return None, None
            
        except Exception as e:
            logger.error(f"❌ Error selecting zone from AI decision: {e}")
            return None, None
    
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
                            # หา Support ที่เหมาะสม (ต่ำกว่าไม้ BUY) + กรองตามระยะห่าง
                            suitable_supports = []
                            for zone in strong_supports:
                                if zone['price'] < pos_price - 5:  # ลดจาก 20 เป็น 5 pips
                                    # ตรวจสอบระยะห่างจากราคาปัจจุบัน
                                    distance = abs(current_price - zone['price'])
                                    zone_strength = zone.get('strength', 0)
                                    
                                    # Dynamic Distance ตาม Zone Strength
                                    if zone_strength >= 0.8:
                                        max_distance = 150.0  # Zone แข็งแกร่งมาก = 150 pips
                                    elif zone_strength >= 0.5:
                                        max_distance = 100.0  # Zone แข็งแกร่ง = 100 pips
                                    elif zone_strength >= 0.2:
                                        max_distance = 75.0   # Zone ปานกลาง = 75 pips
                                    else:
                                        max_distance = 50.0   # Zone อ่อนแอ = 50 pips
                                    
                                    if distance <= max_distance:
                                        suitable_supports.append(zone)
                            
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
                            # หา Resistance ที่เหมาะสม (สูงกว่าไม้ SELL) + กรองตามระยะห่าง
                            suitable_resistances = []
                            for zone in strong_resistances:
                                if zone['price'] > pos_price + 5:  # ลดจาก 20 เป็น 5 pips
                                    # ตรวจสอบระยะห่างจากราคาปัจจุบัน
                                    distance = abs(current_price - zone['price'])
                                    zone_strength = zone.get('strength', 0)
                                    
                                    # Dynamic Distance ตาม Zone Strength
                                    if zone_strength >= 0.8:
                                        max_distance = 150.0  # Zone แข็งแกร่งมาก = 150 pips
                                    elif zone_strength >= 0.5:
                                        max_distance = 100.0  # Zone แข็งแกร่ง = 100 pips
                                    elif zone_strength >= 0.2:
                                        max_distance = 75.0   # Zone ปานกลาง = 75 pips
                                    else:
                                        max_distance = 50.0   # Zone อ่อนแอ = 50 pips
                                    
                                    if distance <= max_distance:
                                        suitable_resistances.append(zone)
                            
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
                comment = f"AI_ENTRY: {reason}" if reason else f"AI_ENTRY: {direction.upper()} at {entry_price:.5f}"
                logger.info(f"🧠 [AI ENTRY] AI Entry Comment: {comment}")
            
            # 🧠 บันทึก AI Decision (ถ้ามี)
            ai_decision = entry_plan.get('ai_decision')
            if ai_decision:
                logger.info(f"🧠 AI Decision included: {ai_decision.final_decision.get('action', 'UNKNOWN')} - Confidence: {ai_decision.confidence:.1f}%")
            
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
                    
                    # บันทึก zone ที่ใช้แล้ว (รวม strength เพื่อ dynamic reuse)
                    zone_key = self._generate_zone_key(zone)
                    self.used_zones[zone_key] = {
                        'timestamp': datetime.now(),
                        'ticket': ticket,
                        'strength': zone.get('strength', 0)  # เพิ่ม strength เพื่อ dynamic reuse
                    }
                    
                    # อัปเดต daily counter
                    self.daily_trade_count += 1
                    
                    # อัปเดตเวลาคำสั่งล่าสุด
                    self.last_trade_time = datetime.now()
                    
                    # 🧠 บันทึกผลลัพธ์ให้ AI Learning System
                    if ai_decision:
                        outcome = {
                            'success': True,
                            'ticket': ticket,
                            'direction': direction,
                            'lot_size': lot_size,
                            'entry_price': entry_price
                        }
                        self.ai_decision_engine.log_decision_outcome(ai_decision, outcome)
                        logger.info(f"🧠 AI Decision outcome logged for ticket {ticket}")
                
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
