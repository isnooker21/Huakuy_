import MetaTrader5 as mt5
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class SmartEntrySystem:
    """🎯 ระบบเข้าไม้อัจฉริยะแบบใหม่ (Support/Resistance เท่านั้น)"""
    
    def __init__(self, mt5_connection, zone_analyzer):
        self.mt5_connection = mt5_connection
        self.zone_analyzer = zone_analyzer
        self.symbol = None  # จะถูกตั้งค่าจาก main system
        
        # Entry Parameters (ปรับใหม่ตาม Demand & Supply)
        self.support_buy_enabled = True      # เปิด Support entries (BUY ที่ Support)
        self.resistance_sell_enabled = True  # เปิด Resistance entries (SELL ที่ Resistance)
        
        # Dynamic Calculation Parameters
        self.profit_target_pips = 50  # เป้าหมายกำไร 50 pips ต่อ lot
        self.loss_threshold_pips = 50  # เกณฑ์ขาดทุน 50 pips ต่อ lot
        self.recovery_zone_strength = 80  # Zone strength สำหรับ Recovery
        self.min_zone_strength = 5  # Zone strength ขั้นต่ำสำหรับเข้าไม้ (ลดจาก 10)
        
        # Risk Management (Dynamic)
        self.risk_percent_per_trade = 0.01  # 1% ของ balance ต่อ trade
        self.max_daily_trades = 10  # ลดจำนวน trade ต่อวัน
        
        # Lot Size Management
        self.min_lot_size = 0.01
        self.max_lot_size = 1.0
        
        # Zone Tracking
        self.used_zones = {}  # {zone_key: {'timestamp': time, 'ticket': ticket}}
        self.daily_trade_count = 0
        self.last_reset_date = datetime.now().date()
        
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
    
    def calculate_dynamic_lot_size(self, zone_strength: float) -> float:
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
            base_lot_size = risk_amount / (self.profit_target_pips * 10)  # 10 = pip value
            
            # ปรับตาม zone strength
            strength_multiplier = {
                50: 0.5,   # 50-59: 0.5x
                60: 0.7,   # 60-69: 0.7x
                70: 0.8,   # 70-79: 0.8x
                80: 1.0,   # 80-89: 1.0x
                90: 1.2,   # 90-100: 1.2x
            }
            
            # หา multiplier ที่เหมาะสม
            final_multiplier = 0.5  # default
            for threshold, multiplier in strength_multiplier.items():
                if zone_strength >= threshold:
                    final_multiplier = multiplier
                else:
                    break
            
            final_lot_size = base_lot_size * final_multiplier
            
            # จำกัด lot size
            return max(self.min_lot_size, min(self.max_lot_size, final_lot_size))
            
        except Exception as e:
            logger.error(f"❌ Error calculating dynamic lot size: {e}")
            return self.min_lot_size  # fallback
    
    def calculate_pivot_point(self, current_price: float, zones: Dict[str, List[Dict]]) -> float:
        """📊 คำนวณ Pivot Point จากราคาปัจจุบันและ zones"""
        try:
            support_zones = zones.get('support', [])
            resistance_zones = zones.get('resistance', [])
            
            if not support_zones or not resistance_zones:
                return current_price
            
            # หา Support และ Resistance ที่ใกล้ราคาปัจจุบันที่สุด
            nearest_support = min(support_zones, key=lambda x: abs(x['price'] - current_price))
            nearest_resistance = min(resistance_zones, key=lambda x: abs(x['price'] - current_price))
            
            # คำนวณ Pivot Point
            pivot_point = (current_price + nearest_support['price'] + nearest_resistance['price']) / 3
            
            return pivot_point
            
        except Exception as e:
            logger.error(f"❌ Error calculating pivot point: {e}")
            return current_price  # fallback
    
    def select_zone_by_pivot_and_strength(self, current_price: float, zones: Dict[str, List[Dict]]) -> Tuple[Optional[str], Optional[Dict]]:
        """🎯 เลือก Zone ตาม Pivot Point + Zone Strength (วิธี C)"""
        try:
            # คำนวณ Pivot Point
            pivot_point = self.calculate_pivot_point(current_price, zones)
            
            support_zones = zones.get('support', [])
            resistance_zones = zones.get('resistance', [])
            
            if not support_zones or not resistance_zones:
                return None, None
            
            # เลือก Zone ตาม Pivot Point
            if current_price < pivot_point:
                # ราคาต่ำกว่า Pivot → หา Support ที่แข็งแกร่ง
                strong_supports = [zone for zone in support_zones if zone['strength'] >= self.min_zone_strength]
                if strong_supports:
                    best_support = max(strong_supports, key=lambda x: x['strength'])
                    return 'support', best_support
            else:
                # ราคาสูงกว่า Pivot → หา Resistance ที่แข็งแกร่ง
                strong_resistances = [zone for zone in resistance_zones if zone['strength'] >= self.min_zone_strength]
                if strong_resistances:
                    best_resistance = max(strong_resistances, key=lambda x: x['strength'])
                    return 'resistance', best_resistance
            
            return None, None
            
        except Exception as e:
            logger.error(f"❌ Error selecting zone by pivot and strength: {e}")
            return None, None
    
    def _is_valid_entry_zone(self, zone: Dict, current_price: float) -> bool:
        """✅ ตรวจสอบว่า Zone ใช้ได้หรือไม่"""
        try:
            # ตรวจสอบ Zone Strength
            if zone.get('strength', 0) < self.min_zone_strength:
                logger.debug(f"🚫 Zone {zone['price']} too weak: {zone.get('strength', 0)}")
                return False
            
            # ตรวจสอบว่าใช้ Zone นี้แล้วหรือยัง
            zone_key = self._generate_zone_key(zone)
            if zone_key in self.used_zones:
                logger.debug(f"🚫 Zone {zone['price']} already used")
                return False
            
            # ตรวจสอบระยะห่างจากราคาปัจจุบัน
            distance = abs(current_price - zone['price'])
            if distance > 15.0:  # ระยะห่างสูงสุด 15 pips
                logger.debug(f"🚫 Zone {zone['price']} too far: {distance}")
                return False
            
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
                # ลบ zones ที่ใช้แล้วเกิน 24 ชั่วโมง
                if current_time - zone_data['timestamp'] > timedelta(hours=24):
                    expired_zones.append(zone_key)
            
            for zone_key in expired_zones:
                del self.used_zones[zone_key]
                
        except Exception as e:
            logger.error(f"❌ Error cleaning up used zones: {e}")
    
    def analyze_entry_opportunity(self, symbol: str, current_price: float, zones: Dict[str, List[Dict]], 
                                existing_positions: List = None) -> Optional[Dict]:
        """🔍 วิเคราะห์โอกาสเข้าไม้แบบใหม่ (Support/Resistance เท่านั้น)"""
        try:
            self.symbol = symbol  # ตั้งค่า symbol ที่ถูกต้อง
            # รีเซ็ต daily counter
            self._reset_daily_counter()
            
            # ตรวจสอบ daily limit
            if self.daily_trade_count >= self.max_daily_trades:
                logger.debug("🚫 Daily trade limit reached")
                return None
            
            # ทำความสะอาด used_zones (ลบ zones เก่า)
            self._cleanup_used_zones()
            
            # 🎯 เลือก Zone ตาม Pivot Point + Zone Strength (วิธี C)
            zone_type, selected_zone = self.select_zone_by_pivot_and_strength(current_price, zones)
            
            if not zone_type or not selected_zone:
                # Log all available zones for debugging
                support_zones = zones.get('support', [])
                resistance_zones = zones.get('resistance', [])
                
                logger.warning("🚫 NO SUITABLE ZONE FOUND FOR ENTRY")
                logger.warning(f"   📊 Current Price: {current_price:.2f}")
                logger.warning(f"   📈 Available Support Zones: {len(support_zones)}")
                for i, zone in enumerate(support_zones[:3], 1):
                    logger.warning(f"      {i}. {zone['price']:.2f} (Strength: {zone['strength']:.1f})")
                
                logger.warning(f"   📉 Available Resistance Zones: {len(resistance_zones)}")
                for i, zone in enumerate(resistance_zones[:3], 1):
                    logger.warning(f"      {i}. {zone['price']:.2f} (Strength: {zone['strength']:.1f})")
                
                logger.warning("   🔧 ปรับแต่ง: ลด min_zone_strength หรือเพิ่ม zone_tolerance")
                return None
            
            # ตรวจสอบว่า Zone ใช้ได้หรือไม่
            if not self._is_valid_entry_zone(selected_zone, current_price):
                logger.debug(f"🚫 Zone {selected_zone['price']} is not valid")
                return None
            
            # คำนวณ lot size แบบ dynamic
            lot_size = self.calculate_dynamic_lot_size(selected_zone['strength'])
            
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
                'loss_threshold': self.calculate_dynamic_loss_threshold(lot_size)
            }
            
            logger.info(f"🎯 Entry Opportunity: {direction.upper()} at {current_price:.5f} "
                       f"(Zone: {selected_zone['price']:.5f}, Strength: {selected_zone['strength']}, "
                       f"Lot: {lot_size:.2f}, Target: ${profit_target:.2f})")
            
            return entry_opportunity
            
        except Exception as e:
            logger.error(f"❌ Error analyzing entry opportunity: {e}")
            return None
    
    def find_recovery_opportunity(self, symbol: str, current_price: float, zones: Dict[str, List[Dict]], 
                                 existing_positions: List = None) -> List[Dict]:
        """🚀 หาโอกาสสร้าง Recovery Position เพื่อแก้ไม้ที่ขาดทุน"""
        try:
            if not existing_positions:
                return []
            
            recovery_opportunities = []
            
            # หาไม้ที่ต้องการความช่วยเหลือ
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
                    
                    # ตรวจสอบว่าไม้ขาดทุนเกินเกณฑ์หรือไม่
                    if pos_profit >= loss_threshold:
                        continue  # ไม้ยังไม่ขาดทุนมาก
                    
                    # หา Zone ที่แข็งแกร่งสำหรับ Recovery
                    if pos_type == 0:  # BUY ไม้ขาดทุน
                        # หา Support Zone ที่แข็งแกร่งสำหรับสร้าง SELL Recovery
                        support_zones = zones.get('support', [])
                        strong_supports = [zone for zone in support_zones if zone['strength'] >= self.recovery_zone_strength]
                        
                        if strong_supports:
                            # หา Support ที่เหมาะสม (ต่ำกว่าไม้ BUY)
                            suitable_supports = [zone for zone in strong_supports if zone['price'] < pos_price - 20]
                            
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
                        strong_resistances = [zone for zone in resistance_zones if zone['strength'] >= self.recovery_zone_strength]
                        
                        if strong_resistances:
                            # หา Resistance ที่เหมาะสม (สูงกว่าไม้ SELL)
                            suitable_resistances = [zone for zone in strong_resistances if zone['price'] > pos_price + 20]
                            
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
            
            return recovery_opportunities[:3]  # ส่งคืนสูงสุด 3 โอกาส
            
        except Exception as e:
            logger.error(f"❌ Error finding recovery opportunity: {e}")
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
    
    def execute_entry(self, entry_plan: Dict) -> Optional[int]:
        """📈 ทำงานเข้าไม้"""
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
            
            # คำนวณ TP และ SL
            if direction == 'buy':
                tp_price = entry_price + (profit_target / (lot_size * 10))  # 50 pips
                sl_price = entry_price - (abs(loss_threshold) / (lot_size * 10))  # 50 pips
            else:  # sell
                tp_price = entry_price - (profit_target / (lot_size * 10))  # 50 pips
                sl_price = entry_price + (abs(loss_threshold) / (lot_size * 10))  # 50 pips
            
            # สร้างคำสั่งซื้อขาย
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": lot_size,
                "type": mt5.ORDER_TYPE_BUY if direction == 'buy' else mt5.ORDER_TYPE_SELL,
                "price": entry_price,
                "tp": tp_price,
                "sl": sl_price,
                "comment": f"Smart Entry: {reason}",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            # ส่งคำสั่ง
            result = mt5.order_send(request)
            
            # ตรวจสอบว่า result เป็น None หรือไม่
            if result is None:
                logger.error(f"❌ Failed to execute entry: mt5.order_send returned None")
                return None
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                logger.error(f"❌ Failed to execute entry: {result.retcode} - {result.comment}")
                return None
            
            # บันทึก zone ที่ใช้แล้ว
            zone_key = self._generate_zone_key(zone)
            self.used_zones[zone_key] = {
                'timestamp': datetime.now(),
                'ticket': result.order
            }
            
            # อัปเดต daily counter
            self.daily_trade_count += 1
            
            logger.info(f"✅ Entry executed: {direction.upper()} {lot_size:.2f} lots at {entry_price:.5f} "
                       f"(TP: {tp_price:.5f}, SL: {sl_price:.5f}) - {reason}")
            
            return result.order
                
        except Exception as e:
            logger.error(f"❌ Error executing entry: {e}")
            return None
    
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
