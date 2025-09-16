import MetaTrader5 as mt5
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class SmartEntrySystem:
    """🎯 ระบบเข้าไม้อัจฉริยะตาม Zone Strength"""
    
    def __init__(self, mt5_connection, zone_analyzer):
        self.mt5_connection = mt5_connection
        self.zone_analyzer = zone_analyzer
        self.symbol = None  # จะถูกตั้งค่าจาก main system
        
        # Entry Parameters
        self.min_zone_strength = 50  # ความแข็งแรงขั้นต่ำ
        self.max_zone_distance = 15.0  # ระยะห่างสูงสุดจาก Zone (points)
        self.min_lot_size = 0.01
        self.max_lot_size = 1.0
        
        # Zone Strength to Lot Size Mapping
        self.strength_lot_mapping = {
            'weak': (0.01, 0.05),      # 30-50
            'medium': (0.05, 0.15),    # 50-70
            'strong': (0.15, 0.30),    # 70-85
            'very_strong': (0.30, 0.50) # 85-100
        }
        
        # Risk Management
        self.max_risk_per_trade = 0.02  # 2% ของบัญชี
        self.max_daily_trades = 15
        self.max_positions_per_zone = 1  # 1 ไม้ต่อ Zone
        
        # Zone Tracking
        self.used_zones = {}  # {zone_key: {'timestamp': time, 'ticket': ticket}}
        self.daily_trade_count = 0
        self.last_reset_date = datetime.now().date()
        
        # Entry Logic Parameters
        self.support_buy_enabled = True   # Buy ที่ Support
        self.resistance_sell_enabled = True  # Sell ที่ Resistance
        self.breakout_entries = False     # Breakout entries (ปิดไว้ก่อน)
        
    def analyze_entry_opportunity(self, symbol: str, current_price: float, zones: Dict[str, List[Dict]], 
                                existing_positions: List = None) -> Optional[Dict]:
        """🔍 วิเคราะห์โอกาสเข้าไม้"""
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
            
            # หาโอกาสเข้าไม้
            entry_opportunities = []
            
            # ตรวจสอบ Support Zones (Buy)
            if self.support_buy_enabled:
                support_ops = self._analyze_support_entries(current_price, zones.get('support', []))
                entry_opportunities.extend(support_ops)
            
            # ตรวจสอบ Resistance Zones (Sell)
            if self.resistance_sell_enabled:
                resistance_ops = self._analyze_resistance_entries(current_price, zones.get('resistance', []))
                entry_opportunities.extend(resistance_ops)
            
            # เลือกโอกาสที่ดีที่สุด
            if entry_opportunities:
                best_opportunity = max(entry_opportunities, key=lambda x: x['priority_score'])
                logger.info(f"🎯 Best entry opportunity: {best_opportunity['direction']} at {best_opportunity['entry_price']} "
                           f"(Zone: {best_opportunity['zone']['price']}, Strength: {best_opportunity['zone']['strength']})")
                return best_opportunity
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error analyzing entry opportunity: {e}")
            return None
    
    def _analyze_support_entries(self, current_price: float, support_zones: List[Dict]) -> List[Dict]:
        """📈 วิเคราะห์โอกาส Buy ที่ Support"""
        try:
            opportunities = []
            
            for zone in support_zones:
                # ตรวจสอบว่าราคาใกล้ Support หรือไม่
                distance = current_price - zone['price']  # ระยะห่างจาก Support
                
                # ราคาต้องอยู่เหนือ Support แต่ไม่ไกลเกินไป
                if 0 < distance <= self.max_zone_distance:
                    # ตรวจสอบเงื่อนไขอื่นๆ
                    if self._is_valid_entry_zone(zone, current_price):
                        lot_size = self._calculate_lot_size(zone['strength'])
                        priority_score = self._calculate_priority_score(zone, distance, 'buy')
                        
                        opportunities.append({
                            'zone': zone,
                            'direction': 'buy',
                            'lot_size': lot_size,
                            'entry_price': current_price,
                            'zone_key': self._generate_zone_key(zone),
                            'distance': distance,
                            'priority_score': priority_score,
                            'entry_reason': f"Support bounce at {zone['price']}"
                        })
            
            return opportunities
            
        except Exception as e:
            logger.error(f"❌ Error analyzing support entries: {e}")
            return []
    
    def _analyze_resistance_entries(self, current_price: float, resistance_zones: List[Dict]) -> List[Dict]:
        """📉 วิเคราะห์โอกาส Sell ที่ Resistance"""
        try:
            opportunities = []
            
            for zone in resistance_zones:
                # ตรวจสอบว่าราคาใกล้ Resistance หรือไม่
                distance = zone['price'] - current_price  # ระยะห่างจาก Resistance
                
                # ราคาต้องอยู่ใต้ Resistance แต่ไม่ไกลเกินไป
                if 0 < distance <= self.max_zone_distance:
                    # ตรวจสอบเงื่อนไขอื่นๆ
                    if self._is_valid_entry_zone(zone, current_price):
                        lot_size = self._calculate_lot_size(zone['strength'])
                        priority_score = self._calculate_priority_score(zone, distance, 'sell')
                        
                        opportunities.append({
                            'zone': zone,
                            'direction': 'sell',
                            'lot_size': lot_size,
                            'entry_price': current_price,
                            'zone_key': self._generate_zone_key(zone),
                            'distance': distance,
                            'priority_score': priority_score,
                            'entry_reason': f"Resistance rejection at {zone['price']}"
                        })
            
            return opportunities
            
        except Exception as e:
            logger.error(f"❌ Error analyzing resistance entries: {e}")
            return []
    
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
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error validating entry zone: {e}")
            return False
    
    def _calculate_lot_size(self, zone_strength: float) -> float:
        """📊 คำนวณ Lot Size ตาม Zone Strength"""
        try:
            # กำหนดหมวดหมู่ความแข็งแรง
            if zone_strength < 50:
                strength_category = 'weak'
            elif zone_strength < 70:
                strength_category = 'medium'
            elif zone_strength < 85:
                strength_category = 'strong'
            else:
                strength_category = 'very_strong'
            
            min_lot, max_lot = self.strength_lot_mapping[strength_category]
            
            # คำนวณ Lot Size ตาม Strength (Linear interpolation)
            strength_ratio = (zone_strength - 30) / 70  # 30-100 -> 0-1
            strength_ratio = max(0, min(1, strength_ratio))
            
            lot_size = min_lot + (max_lot - min_lot) * strength_ratio
            
            # จำกัดขอบเขต
            lot_size = max(self.min_lot_size, min(self.max_lot_size, lot_size))
            
            # ปัดเศษ
            lot_size = round(lot_size, 2)
            
            logger.debug(f"📊 Zone strength {zone_strength} -> {strength_category} -> {lot_size} lots")
            return lot_size
            
        except Exception as e:
            logger.error(f"❌ Error calculating lot size: {e}")
            return self.min_lot_size
    
    def _calculate_priority_score(self, zone: Dict, distance: float, direction: str) -> float:
        """🎯 คำนวณคะแนนความสำคัญ"""
        try:
            # Base score จาก Zone Strength
            base_score = zone.get('strength', 0)
            
            # Distance bonus (ใกล้ = ดีกว่า)
            max_distance = self.max_zone_distance
            distance_bonus = (max_distance - distance) / max_distance * 20
            
            # Touches bonus
            touches_bonus = min(zone.get('touches', 0) * 2, 20)
            
            # Multi-timeframe bonus
            tf_count = len(zone.get('timeframes', []))
            tf_bonus = tf_count * 5
            
            # Zone freshness (Zone ใหม่ = ดีกว่า)
            now = datetime.now().timestamp()
            zone_age_hours = (now - zone.get('timestamp', now)) / 3600
            freshness_bonus = max(10 - zone_age_hours / 24, 0)
            
            total_score = base_score + distance_bonus + touches_bonus + tf_bonus + freshness_bonus
            
            logger.debug(f"🎯 Priority score: Base={base_score}, Dist={distance_bonus:.1f}, "
                        f"Touch={touches_bonus}, TF={tf_bonus}, Fresh={freshness_bonus:.1f} = {total_score:.1f}")
            
            return round(total_score, 1)
            
        except Exception as e:
            logger.error(f"❌ Error calculating priority score: {e}")
            return 0.0
    
    def _generate_zone_key(self, zone: Dict) -> str:
        """🔑 สร้าง Zone Key สำหรับ tracking"""
        try:
            zone_type = zone.get('type', 'unknown')
            price = zone.get('price', 0)
            return f"{zone_type}_{price:.2f}"
        except Exception as e:
            logger.error(f"❌ Error generating zone key: {e}")
            return f"unknown_{datetime.now().timestamp()}"
    
    def mark_zone_used(self, zone_key: str, ticket: int) -> None:
        """✅ ทำเครื่องหมายว่าใช้ Zone แล้ว"""
        try:
            self.used_zones[zone_key] = {
                'timestamp': datetime.now().timestamp(),
                'ticket': ticket
            }
            self.daily_trade_count += 1
            logger.info(f"✅ Zone {zone_key} marked as used (Ticket: {ticket})")
        except Exception as e:
            logger.error(f"❌ Error marking zone as used: {e}")
    
    def _cleanup_used_zones(self, max_age_hours: int = 24) -> None:
        """🧹 ทำความสะอาด used_zones (ลบ zones เก่า)"""
        try:
            current_time = datetime.now().timestamp()
            max_age_seconds = max_age_hours * 3600
            
            expired_zones = []
            for zone_key, data in self.used_zones.items():
                if current_time - data['timestamp'] > max_age_seconds:
                    expired_zones.append(zone_key)
            
            for zone_key in expired_zones:
                del self.used_zones[zone_key]
                logger.debug(f"🧹 Cleaned expired zone: {zone_key}")
            
            if expired_zones:
                logger.info(f"🧹 Cleaned {len(expired_zones)} expired zones")
                
        except Exception as e:
            logger.error(f"❌ Error cleaning used zones: {e}")
    
    def _reset_daily_counter(self) -> None:
        """🔄 รีเซ็ต daily counter"""
        try:
            current_date = datetime.now().date()
            if current_date != self.last_reset_date:
                self.daily_trade_count = 0
                self.last_reset_date = current_date
                logger.info(f"🔄 Daily counter reset for {current_date}")
        except Exception as e:
            logger.error(f"❌ Error resetting daily counter: {e}")
    
    def execute_entry(self, entry_plan: Dict) -> Optional[int]:
        """🚀 ดำเนินการเข้าไม้"""
        try:
            if not entry_plan:
                return None
            
            symbol = self.symbol
            lot_size = entry_plan['lot_size']
            direction = entry_plan['direction']
            entry_price = entry_plan['entry_price']
            
            # กำหนด order type
            if direction == 'buy':
                order_type = mt5.ORDER_TYPE_BUY
                action = mt5.TRADE_ACTION_DEAL
            else:
                order_type = mt5.ORDER_TYPE_SELL
                action = mt5.TRADE_ACTION_DEAL
            
            # สร้าง request
            request = {
                "action": action,
                "symbol": symbol,
                "volume": lot_size,
                "type": order_type,
                "comment": f"Smart Entry: {entry_plan['entry_reason']}",
                "type_time": mt5.ORDER_TIME_GTC,
                "magic": 123456
            }
            
            # 🔍 Debug Log
            logger.info(f"🔍 SMART ENTRY DEBUG:")
            logger.info(f"   Symbol: {symbol}")
            logger.info(f"   Volume: {lot_size}")
            logger.info(f"   Direction: {direction}")
            logger.info(f"   Order Type: {order_type}")
            logger.info(f"   MT5 Connected: {mt5.initialize()}")
            logger.info(f"   Account Info: {mt5.account_info()}")
            logger.info(f"   Symbol Info: {mt5.symbol_info(symbol)}")
            
            # ส่ง order
            result = mt5.order_send(request)
            logger.info(f"🔍 MT5 order_send result: {result}")
            
            if result is None:
                logger.error(f"❌ Entry failed: MT5 order_send returned None")
                return None
            
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                ticket = result.order
                logger.info(f"🚀 Entry executed: {direction.upper()} {lot_size} lots at {entry_price} "
                           f"(Ticket: {ticket}, Zone: {entry_plan['zone']['price']})")
                
                # ทำเครื่องหมายว่าใช้ Zone แล้ว
                self.mark_zone_used(entry_plan['zone_key'], ticket)
                
                return ticket
            else:
                logger.error(f"❌ Entry failed: {getattr(result, 'comment', 'Unknown error')} (Code: {getattr(result, 'retcode', 'Unknown')})")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error executing entry: {e}")
            return None
    
    def get_entry_statistics(self) -> Dict:
        """📊 สถิติการเข้าไม้"""
        try:
            return {
                'daily_trades': self.daily_trade_count,
                'max_daily_trades': self.max_daily_trades,
                'used_zones_count': len(self.used_zones),
                'remaining_daily_trades': max(0, self.max_daily_trades - self.daily_trade_count),
                'last_reset_date': str(self.last_reset_date)
            }
        except Exception as e:
            logger.error(f"❌ Error getting entry statistics: {e}")
            return {}
    
    def update_settings(self, settings: Dict) -> None:
        """⚙️ อัปเดตการตั้งค่า"""
        try:
            if 'min_zone_strength' in settings:
                self.min_zone_strength = settings['min_zone_strength']
            
            if 'max_zone_distance' in settings:
                self.max_zone_distance = settings['max_zone_distance']
            
            if 'max_daily_trades' in settings:
                self.max_daily_trades = settings['max_daily_trades']
            
            if 'support_buy_enabled' in settings:
                self.support_buy_enabled = settings['support_buy_enabled']
            
            if 'resistance_sell_enabled' in settings:
                self.resistance_sell_enabled = settings['resistance_sell_enabled']
            
            logger.info(f"⚙️ Smart Entry settings updated: {settings}")
            
        except Exception as e:
            logger.error(f"❌ Error updating settings: {e}")
