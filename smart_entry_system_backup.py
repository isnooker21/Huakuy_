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
        
        # Entry Parameters (ปรับให้แม่นยำขึ้น)
        self.min_zone_strength = 25  # ความแข็งแรงขั้นต่ำ (ลดจาก 35)
        self.max_zone_distance = 15.0  # ระยะห่างสูงสุดจาก Zone (ลดจาก 25)
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
        self.use_balance_calculation = True  # ใช้การคำนวณจาก balance
        self.max_daily_trades = 15
        self.max_positions_per_zone = 1  # 1 ไม้ต่อ Zone
        
        # Zone Tracking
        self.used_zones = {}  # {zone_key: {'timestamp': time, 'ticket': ticket}}
        self.daily_trade_count = 0
        self.last_reset_date = datetime.now().date()
        
        # Entry Logic Parameters (ปรับใหม่ตาม Demand & Supply)
        self.support_buy_enabled = True      # เปิด Support entries (BUY ที่ Support)
        self.resistance_sell_enabled = True  # เปิด Resistance entries (SELL ที่ Resistance)
        
        # Dynamic Calculation Parameters
        self.profit_target_pips = 50  # เป้าหมายกำไร 50 pips ต่อ lot
        self.loss_threshold_pips = 50  # เกณฑ์ขาดทุน 50 pips ต่อ lot
        self.recovery_zone_strength = 80  # Zone strength สำหรับ Recovery
        self.min_zone_strength = 50  # Zone strength ขั้นต่ำสำหรับเข้าไม้
        
        # Risk Management (Dynamic)
        self.risk_percent_per_trade = 0.01  # 1% ของ balance ต่อ trade
        self.max_daily_trades = 10  # ลดจำนวน trade ต่อวัน
        
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
            
            balance = account_info.balance
            
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

    # ลบฟังก์ชัน analyze_position_balance (ไม่ใช้แล้ว)
        """📊 วิเคราะห์ความสมดุลของไม้ในรัศมีรอบๆ ราคาปัจจุบัน"""
        try:
            if not existing_positions:
                return {
                    'buy_count': 0,
                    'sell_count': 0,
                    'total_count': 0,
                    'buy_ratio': 0.0,
                    'sell_ratio': 0.0,
                    'needs_buy': False,
                    'needs_sell': False,
                    'is_balanced': True,
                    'radius_pips': radius_pips
                }
            
            # คำนวณรัศมี (50 pips = 500 points)
            radius_points = radius_pips * 10  # 50 pips = 500 points
            min_price = current_price - radius_points if current_price else 0
            max_price = current_price + radius_points if current_price else float('inf')
            
            # นับไม้ในรัศมี
            buy_in_zone = []
            sell_in_zone = []
            
            for pos in existing_positions:
                try:
                    pos_price = getattr(pos, 'price', 0)
                    pos_type = getattr(pos, 'type', 0)
                    
                    if min_price <= pos_price <= max_price:
                        if pos_type == 0:  # BUY
                            buy_in_zone.append(pos)
                        elif pos_type == 1:  # SELL
                            sell_in_zone.append(pos)
                except Exception as e:
                    logger.error(f"❌ Error processing position: {e}")
                    continue
            
            buy_count = len(buy_in_zone)
            sell_count = len(sell_in_zone)
            total_count = buy_count + sell_count
            
            # คำนวณอัตราส่วน
            if total_count > 0:
                buy_ratio = buy_count / total_count
                sell_ratio = sell_count / total_count
            else:
                buy_ratio = 0.0
                sell_ratio = 0.0
            
            # ตรวจสอบว่าต้องการเติมไม้ฝั่งไหน (ใช้เงื่อนไขที่เข้มกว่า)
            needs_buy = sell_count > buy_count + 1  # SELL มากกว่า BUY มากกว่า 1 ตัว
            needs_sell = buy_count > sell_count + 1  # BUY มากกว่า SELL มากกว่า 1 ตัว
            is_balanced = not needs_buy and not needs_sell
            
            logger.info(f"📊 Zone Balance Analysis (รัศมี {radius_pips} pips):")
            logger.info(f"   ราคาปัจจุบัน: {current_price:.2f}")
            logger.info(f"   รัศมี: {min_price:.2f} - {max_price:.2f}")
            logger.info(f"   BUY ในรัศมี: {buy_count} ({buy_ratio:.1%})")
            logger.info(f"   SELL ในรัศมี: {sell_count} ({sell_ratio:.1%})")
            logger.info(f"   Needs BUY: {needs_buy}, Needs SELL: {needs_sell}")
            
            return {
                'buy_count': buy_count,
                'sell_count': sell_count,
                'total_count': total_count,
                'buy_ratio': buy_ratio,
                'sell_ratio': sell_ratio,
                'needs_buy': needs_buy,
                'needs_sell': needs_sell,
                'is_balanced': is_balanced,
                'radius_pips': radius_pips,
                'min_price': min_price,
                'max_price': max_price
            }
            
        except Exception as e:
            logger.error(f"❌ Error analyzing position balance: {e}")
            return {
                'buy_count': 0,
                'sell_count': 0,
                'total_count': 0,
                'balance_ratio': 0.0,
                'needs_buy': False,
                'needs_sell': False,
                'is_balanced': True
            }
    
    def check_position_distribution(self, new_price: float, existing_positions: List = None, is_balance_entry: bool = False) -> bool:
        """🔍 ตรวจสอบการกระจายตัวของไม้ (ไม่บังคับกับไม้ Zone-Based Balance)"""
        try:
            if not existing_positions or not self.position_distribution_enabled:
                return True
            
            # ไม่บังคับระยะห่างกับไม้ Zone-Based Balance
            if is_balance_entry:
                logger.info("🎯 Zone Balance entry - skipping distance check")
                return True
            
            # ตรวจสอบระยะห่างระหว่างไม้ (เฉพาะไม้ปกติ)
            for pos in existing_positions:
                try:
                    pos_price = getattr(pos, 'price_open', 0)
                    if pos_price > 0:
                        distance = abs(new_price - pos_price) * 10000  # แปลงเป็น pips
                        if distance < self.min_distance_between_positions:
                            logger.info(f"⚠️ Position too close: {distance:.1f} pips < {self.min_distance_between_positions} pips")
                            return False
                except Exception as e:
                    logger.error(f"❌ Error checking position distance: {e}")
                    continue
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error checking position distribution: {e}")
            return True

    def find_zone_balance_opportunity(self, symbol: str, current_price: float, zones: Dict[str, List[Dict]], 
                                     existing_positions: List = None) -> Optional[Dict]:
        """🎯 หาโอกาสเติมไม้ตาม Zone เพื่อความสมดุล"""
        try:
            if not self.zone_balance_enabled:
                return None
            
            # วิเคราะห์ความสมดุลของไม้ในรัศมี 50 pips
            balance_analysis = self.analyze_position_balance(existing_positions, current_price, 50.0)
            
            if balance_analysis['is_balanced']:
                logger.info("✅ Positions are balanced - no need to add more")
                return None
            
            # หา Zone ที่เหมาะสมสำหรับเติมไม้
            if balance_analysis['needs_buy']:
                # ต้องการเติม BUY - หา Support Zones
                support_zones = zones.get('support', [])
                best_zone = self._find_best_zone_for_balance(support_zones, current_price, 'buy')
                
                if best_zone:
                    # ตรวจสอบการกระจายตัว (ไม่บังคับกับไม้ Zone Balance)
                    if self.check_position_distribution(best_zone['price'], existing_positions, is_balance_entry=True):
                        return {
                            'direction': 'buy',
                            'zone': best_zone,
                            'reason': f"Zone Balance: Add BUY at Support {best_zone['price']:.5f}",
                            'zone_strength': best_zone['strength'],
                            'zone_type': 'support'
                        }
            
            elif balance_analysis['needs_sell']:
                # ต้องการเติม SELL - หา Resistance Zones
                resistance_zones = zones.get('resistance', [])
                best_zone = self._find_best_zone_for_balance(resistance_zones, current_price, 'sell')
                
                if best_zone:
                    # ตรวจสอบการกระจายตัว (ไม่บังคับกับไม้ Zone Balance)
                    if self.check_position_distribution(best_zone['price'], existing_positions, is_balance_entry=True):
                        return {
                            'direction': 'sell',
                            'zone': best_zone,
                            'reason': f"Zone Balance: Add SELL at Resistance {best_zone['price']:.5f}",
                            'zone_strength': best_zone['strength'],
                            'zone_type': 'resistance'
                        }
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error finding zone balance opportunity: {e}")
            return None
    
    def _find_best_zone_for_balance(self, zones: List[Dict], current_price: float, direction: str) -> Optional[Dict]:
        """🔍 หา Zone ที่ดีที่สุดสำหรับเติมไม้"""
        try:
            if not zones:
                return None
            
            # กรอง Zone ที่แข็งแกร่งพอ
            strong_zones = [zone for zone in zones if zone.get('strength', 0) >= self.min_zone_strength_for_balance]
            
            if not strong_zones:
                logger.info(f"⚠️ No strong zones found for {direction} (min strength: {self.min_zone_strength_for_balance})")
                return None
            
            # หา Zone ที่ใกล้ราคาปัจจุบันที่สุด
            best_zone = None
            min_distance = float('inf')
            
            for zone in strong_zones:
                zone_price = zone.get('price', 0)
                if zone_price > 0:
                    distance = abs(current_price - zone_price)
                    if distance < min_distance:
                        min_distance = distance
                        best_zone = zone
            
            if best_zone:
                logger.info(f"🎯 Best zone for {direction}: {best_zone['price']:.5f} (strength: {best_zone['strength']}, distance: {min_distance:.5f})")
            
            return best_zone
            
        except Exception as e:
            logger.error(f"❌ Error finding best zone for balance: {e}")
            return None
        
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
                logger.debug("🚫 No suitable zone found")
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
            else:  # resistance
                direction = 'sell'  # SELL ที่ Resistance
                entry_reason = f"Resistance SELL at {selected_zone['price']:.5f} (Strength: {selected_zone['strength']})"
            
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

    # ลบฟังก์ชัน Breakout Entries (ไม่ใช้แล้ว)
    
    def _analyze_balance_entries(self, current_price: float, zones: Dict[str, List[Dict]], existing_positions: List) -> List[Dict]:
        """⚖️ วิเคราะห์โอกาสเพื่อสร้างความสมดุล (เปิดไม้ฝั่งตรงข้าม)"""
        try:
            opportunities = []
            
            # นับไม้แต่ละฝั่ง
            buy_count = len([p for p in existing_positions if getattr(p, 'type', 0) == 0])
            sell_count = len([p for p in existing_positions if getattr(p, 'type', 1) == 1])
            
            # ถ้าไม้ฝั่งใดฝั่งหนึ่งมากเกินไป ให้เปิดฝั่งตรงข้าม
            if sell_count > buy_count + 2:  # SELL มากกว่า BUY เกิน 2 ตัว
                # หาโอกาส BUY
                for zone in zones.get('support', []):
                    distance = abs(current_price - zone['price'])
                    if distance <= self.max_zone_distance:
                        if self._is_valid_entry_zone(zone, current_price):
                            lot_size = self._calculate_lot_size(zone['strength'], is_balance_entry=False)
                            priority_score = self._calculate_priority_score(zone, distance, 'buy') + 20  # เพิ่มคะแนนสำหรับ balance
                            
                            opportunities.append({
                                'zone': zone,
                                'direction': 'buy',
                                'lot_size': lot_size,
                                'entry_price': current_price,
                                'zone_key': self._generate_zone_key(zone),
                                'distance': distance,
                                'priority_score': priority_score,
                                'entry_reason': f"Balance BUY - SELL heavy ({sell_count} vs {buy_count})"
                            })
                            break  # หาแค่ 1 โอกาส
            
            elif buy_count > sell_count + 2:  # BUY มากกว่า SELL เกิน 2 ตัว
                # หาโอกาส SELL
                for zone in zones.get('resistance', []):
                    distance = abs(current_price - zone['price'])
                    if distance <= self.max_zone_distance:
                        if self._is_valid_entry_zone(zone, current_price):
                            lot_size = self._calculate_lot_size(zone['strength'], is_balance_entry=False)
                            priority_score = self._calculate_priority_score(zone, distance, 'sell') + 20  # เพิ่มคะแนนสำหรับ balance
                            
                            opportunities.append({
                                'zone': zone,
                                'direction': 'sell',
                                'lot_size': lot_size,
                                'entry_price': current_price,
                                'zone_key': self._generate_zone_key(zone),
                                'distance': distance,
                                'priority_score': priority_score,
                                'entry_reason': f"Balance SELL - BUY heavy ({buy_count} vs {sell_count})"
                            })
                            break  # หาแค่ 1 โอกาส
            
            return opportunities
            
        except Exception as e:
            logger.error(f"❌ Error analyzing balance entries: {e}")
            return []
    
    def _analyze_support_entries(self, current_price: float, support_zones: List[Dict]) -> List[Dict]:
        """📉 วิเคราะห์โอกาส Sell ที่ Support (สลับการทำงาน)"""
        try:
            opportunities = []
            
            for zone in support_zones:
                # ตรวจสอบว่าราคาใกล้ Support หรือไม่ (Sell ที่ราคาต่ำ - สลับ)
                distance = abs(current_price - zone['price'])  # ระยะห่างจาก Support
                
                # ราคาต้องใกล้ Support (ต่ำกว่าหรือใกล้เคียง) - ปรับให้แม่นยำขึ้น
                if current_price <= zone['price'] + 5.0 and distance <= self.max_zone_distance:
                    # ตรวจสอบเงื่อนไขอื่นๆ
                    if self._is_valid_entry_zone(zone, current_price):
                        lot_size = self._calculate_lot_size(zone['strength'], is_balance_entry=False)
                        priority_score = self._calculate_priority_score(zone, distance, 'sell')
                        
                        opportunities.append({
                            'zone': zone,
                            'direction': 'sell',  # เปลี่ยนเป็น sell
                            'lot_size': lot_size,
                            'entry_price': current_price,
                            'zone_key': self._generate_zone_key(zone),
                            'distance': distance,
                            'priority_score': priority_score,
                            'entry_reason': f"Support rejection at {zone['price']}"  # เปลี่ยนเป็น rejection
                        })
            
            return opportunities
            
        except Exception as e:
            logger.error(f"❌ Error analyzing support entries: {e}")
            return []
    
    def _analyze_resistance_entries(self, current_price: float, resistance_zones: List[Dict]) -> List[Dict]:
        """📈 วิเคราะห์โอกาส Buy ที่ Resistance (สลับการทำงาน)"""
        try:
            opportunities = []
            
            for zone in resistance_zones:
                # ตรวจสอบว่าราคาใกล้ Resistance หรือไม่ (Buy ที่ราคาสูง - สลับ)
                distance = abs(current_price - zone['price'])  # ระยะห่างจาก Resistance
                
                # ราคาต้องใกล้ Resistance (สูงกว่าหรือใกล้เคียง) - ปรับให้แม่นยำขึ้น
                if current_price >= zone['price'] - 5.0 and distance <= self.max_zone_distance:
                    # ตรวจสอบเงื่อนไขอื่นๆ
                    if self._is_valid_entry_zone(zone, current_price):
                        lot_size = self._calculate_lot_size(zone['strength'], is_balance_entry=False)
                        priority_score = self._calculate_priority_score(zone, distance, 'buy')
                        
                        opportunities.append({
                            'zone': zone,
                            'direction': 'buy',  # เปลี่ยนเป็น buy
                            'lot_size': lot_size,
                            'entry_price': current_price,
                            'zone_key': self._generate_zone_key(zone),
                            'distance': distance,
                            'priority_score': priority_score,
                            'entry_reason': f"Resistance bounce at {zone['price']}"  # เปลี่ยนเป็น bounce
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
    
    def _calculate_lot_size(self, zone_strength: float, is_balance_entry: bool = False) -> float:
        """📊 คำนวณ Lot Size ตาม Zone Strength และ Account Balance"""
        try:
            if self.use_balance_calculation:
                lot_size = self._calculate_lot_size_from_balance(zone_strength)
            else:
                lot_size = self._calculate_lot_size_from_strength(zone_strength)
            
            # สำหรับ Zone Balance entries ให้ใช้ lot size เล็กกว่า
            if is_balance_entry:
                lot_size *= 0.5  # ลดลง 50%
                lot_size = max(self.min_lot_size, lot_size)  # จำกัดไม่ให้ต่ำกว่า min_lot_size
            
            return lot_size
                
        except Exception as e:
            logger.error(f"❌ Error calculating lot size: {e}")
            return self.min_lot_size
    
    def _calculate_lot_size_from_balance(self, zone_strength: float) -> float:
        """💰 คำนวณ lot size จาก account balance"""
        try:
            # ดึงข้อมูล account
            account_info = mt5.account_info()
            if not account_info:
                logger.warning("❌ Cannot get account info, using default lot size")
                return self.min_lot_size
            
            balance = account_info.balance
            equity = account_info.equity
            
            # ใช้ equity หรือ balance ที่น้อยกว่า
            available_capital = min(balance, equity)
            
            # คำนวณ risk amount ตาม zone strength
            # Zone แข็งแรง = เสี่ยงมากขึ้น (แต่ไม่เกิน 2%)
            if zone_strength >= 85:
                risk_percent = 2.0  # Very strong zone = 2%
            elif zone_strength >= 70:
                risk_percent = 1.5  # Strong zone = 1.5%
            elif zone_strength >= 50:
                risk_percent = 1.0  # Medium zone = 1%
            else:
                risk_percent = 0.5  # Weak zone = 0.5%
            
            risk_amount = available_capital * (risk_percent / 100.0)
            
            # คำนวณ lot size (สมมติ 1 lot = $1000 risk สำหรับ XAUUSD)
            calculated_lot = risk_amount / 1000.0
            
            # จำกัด lot size สำหรับทุนเล็ก
            min_lot = 0.01
            max_lot = min(0.10, available_capital / 2000.0)  # ไม่เกิน balance/2000
            final_lot = max(min_lot, min(calculated_lot, max_lot))
            
            logger.info(f"💰 Smart Entry lot: Balance=${balance:.0f}, Zone={zone_strength:.1f}, Risk={risk_percent}%, Lot={final_lot:.2f}")
            
            return round(final_lot, 2)
            
        except Exception as e:
            logger.error(f"❌ Error calculating lot from balance: {e}")
            return self.min_lot_size
    
    def _calculate_lot_size_from_strength(self, zone_strength: float) -> float:
        """📊 คำนวณ Lot Size ตาม Zone Strength (วิธีเดิม)"""
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
            
            # ตรวจสอบว่าเป็น Zone Balance entry หรือไม่
            is_balance_entry = entry_plan.get('reason', '').startswith('Zone Balance')
            
            # สร้าง request
            request = {
                "action": action,
                "symbol": symbol,
                "volume": lot_size,
                "type": order_type,
                "comment": f"SmartEntry{'Balance' if is_balance_entry else ''}",
                "type_time": mt5.ORDER_TIME_GTC,
                "magic": 123456
            }
            
            # ส่ง order
            result = mt5.order_send(request)
            
            # Debug เฉพาะเมื่อมี error
            if result is None:
                logger.error(f"🔍 MT5 Error: {mt5.last_error()}")
                logger.error(f"🔍 Request was: {request}")
            
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
    
    def find_recovery_opportunity(self, symbol: str, current_price: float, zones: Dict[str, List[Dict]], 
                                 existing_positions: List = None) -> List[Dict]:
        """🚀 หาโอกาสสร้างไม้ Recovery เพื่อช่วยไม้ที่ขาดทุน"""
        try:
            if not existing_positions:
                return []
            
            # วิเคราะห์สถานะไม้ทั้งหมด
            status_summary = self.get_position_status_summary(existing_positions)
            
            if not status_summary:
                return []
            
            urgent_positions = status_summary.get('urgent_positions', [])
            help_needed_positions = status_summary.get('help_needed_positions', [])
            portfolio_health = status_summary.get('portfolio_health', 'ไม่ทราบ')
            
            recovery_opportunities = []
            
            # สร้างโอกาส Recovery สำหรับไม้ที่ต้องการความช่วยเหลือ
            if urgent_positions or help_needed_positions:
                logger.info(f"🚀 Finding Recovery Opportunities - Portfolio Health: {portfolio_health}")
                logger.info(f"   Urgent Positions: {len(urgent_positions)}")
                logger.info(f"   Help Needed Positions: {len(help_needed_positions)}")
                
                # หาไม้ SELL ที่ขาดทุน
                sell_losers = [pos for pos in urgent_positions + help_needed_positions 
                             if getattr(pos.position, 'type', 0) == 1]
                
                if sell_losers:
                    # หา Support Zone ที่แข็งแกร่งสำหรับสร้างไม้ BUY Recovery
                    support_zones = zones.get('support', [])
                    strong_support_zones = [zone for zone in support_zones if zone.get('strength', 0) >= 80]
                    
                    for i, sell_loser in enumerate(sell_losers[:3]):  # สร้างสูงสุด 3 ตัว
                        sell_price = getattr(sell_loser.position, 'price_open', 0)
                        if sell_price > 0:
                            # หา Support Zone ที่เหมาะสม
                            best_zone = None
                            for zone in strong_support_zones:
                                if zone['price'] < sell_price - 10:  # ต้องต่ำกว่าไม้ SELL อย่างน้อย 10 pips
                                    best_zone = zone
                                    break
                            
                            if best_zone:
                                recovery_opportunities.append({
                                    'direction': 'buy',
                                    'entry_price': best_zone['price'],
                                    'zone': best_zone,
                                    'target_loss': sell_loser.profit,
                                    'reason': f"Recovery BUY for SELL {sell_loser.ticket} (${sell_loser.profit:.2f})"
                                })
                            else:
                                # ถ้าไม่มี Zone ที่เหมาะสม ให้สร้างที่ราคาต่ำกว่า
                                recovery_price = sell_price - (20 + i * 10) * 0.1
                                recovery_opportunities.append({
                                    'direction': 'buy',
                                    'entry_price': recovery_price,
                                    'zone': {'price': recovery_price, 'strength': 50},
                                    'target_loss': sell_loser.profit,
                                    'reason': f"Recovery BUY for SELL {sell_loser.ticket} (${sell_loser.profit:.2f})"
                                })
                
                # หาไม้ BUY ที่ขาดทุน
                buy_losers = [pos for pos in urgent_positions + help_needed_positions 
                             if getattr(pos.position, 'type', 0) == 0]
                
                if buy_losers:
                    # หา Resistance Zone ที่แข็งแกร่งสำหรับสร้างไม้ SELL Recovery
                    resistance_zones = zones.get('resistance', [])
                    strong_resistance_zones = [zone for zone in resistance_zones if zone.get('strength', 0) >= 80]
                    
                    for i, buy_loser in enumerate(buy_losers[:3]):  # สร้างสูงสุด 3 ตัว
                        buy_price = getattr(buy_loser.position, 'price_open', 0)
                        if buy_price > 0:
                            # หา Resistance Zone ที่เหมาะสม
                            best_zone = None
                            for zone in strong_resistance_zones:
                                if zone['price'] > buy_price + 10:  # ต้องสูงกว่าไม้ BUY อย่างน้อย 10 pips
                                    best_zone = zone
                                    break
                            
                            if best_zone:
                                recovery_opportunities.append({
                                    'direction': 'sell',
                                    'entry_price': best_zone['price'],
                                    'zone': best_zone,
                                    'target_loss': buy_loser.profit,
                                    'reason': f"Recovery SELL for BUY {buy_loser.ticket} (${buy_loser.profit:.2f})"
                                })
                            else:
                                # ถ้าไม่มี Zone ที่เหมาะสม ให้สร้างที่ราคาสูงกว่า
                                recovery_price = buy_price + (20 + i * 10) * 0.1
                                recovery_opportunities.append({
                                    'direction': 'sell',
                                    'entry_price': recovery_price,
                                    'zone': {'price': recovery_price, 'strength': 50},
                                    'target_loss': buy_loser.profit,
                                    'reason': f"Recovery SELL for BUY {buy_loser.ticket} (${buy_loser.profit:.2f})"
                                })
            
            return recovery_opportunities
            
        except Exception as e:
            logger.error(f"❌ Error finding recovery opportunity: {e}")
            return []
    
    def _calculate_recovery_lot_size(self, target_loss: float) -> float:
        """📊 คำนวณขนาดไม้สำหรับ Recovery"""
        try:
            # คำนวณขนาดไม้ตามขาดทุนที่ต้องการ Recovery
            base_volume = 0.01
            
            if abs(target_loss) > 200:
                base_volume = 0.05
            elif abs(target_loss) > 100:
                base_volume = 0.03
            elif abs(target_loss) > 50:
                base_volume = 0.02
            else:
                base_volume = 0.01
            
            # จำกัดขนาดไม้
            base_volume = max(0.01, min(0.1, base_volume))
            
            return base_volume
            
        except Exception as e:
            logger.error(f"❌ Error calculating recovery lot size: {e}")
            return 0.01
