import MetaTrader5 as mt5
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class PortfolioAnchor:
    """⚓ ระบบจัดการ Hold Positions เพื่อค้ำพอร์ต"""
    
    def __init__(self, mt5_connection, zone_analyzer):
        self.mt5_connection = mt5_connection
        self.zone_analyzer = zone_analyzer
        self.symbol = None  # จะถูกตั้งค่าจาก main system
        
        # Anchor Parameters
        self.max_anchor_positions = 4  # สูงสุด 4 ไม้ anchor
        self.min_anchor_distance = 50.0  # ระยะห่างขั้นต่ำระหว่าง anchors (points)
        self.anchor_lot_size = 0.20  # ขนาด lot สำหรับ anchor
        self.max_anchor_age_hours = 48  # อายุสูงสุดของ anchor (ชั่วโมง)
        
        # Portfolio Protection
        self.portfolio_risk_threshold = -500.0  # เมื่อพอร์ตขาดทุนเกิน $500
        self.anchor_profit_target = 100.0  # เป้าหมายกำไรของ anchor
        self.emergency_anchor_trigger = -1000.0  # กำไรขาดทุนที่เปิด emergency anchor
        
        # Price Level Management
        self.support_anchor_enabled = True  # Buy anchor ที่ Support แข็งแรง
        self.resistance_anchor_enabled = True  # Sell anchor ที่ Resistance แข็งแรง
        self.dynamic_anchor_enabled = True  # Anchor ตามสถานการณ์พอร์ต
        
        # Anchor Tracking
        self.anchor_positions = {}  # {ticket: anchor_info}
        self.last_anchor_check = 0
        self.anchor_check_interval = 300  # ตรวจสอบทุก 5 นาที
        
    def analyze_anchor_needs(self, symbol: str, current_price: float, portfolio_profit: float, 
                           zones: Dict[str, List[Dict]], existing_positions: List) -> Optional[Dict]:
        """🔍 วิเคราะห์ความจำเป็นในการสร้าง Anchor"""
        try:
            self.symbol = symbol  # ตั้งค่า symbol ที่ถูกต้อง
            # ตรวจสอบเวลา
            current_time = datetime.now().timestamp()
            if current_time - self.last_anchor_check < self.anchor_check_interval:
                return None
            
            self.last_anchor_check = current_time
            
            # ทำความสะอาด anchor positions เก่า
            self._cleanup_old_anchors()
            
            # ตรวจสอบจำนวน anchor ปัจจุบัน
            current_anchor_count = len(self.anchor_positions)
            if current_anchor_count >= self.max_anchor_positions:
                logger.debug(f"⚓ Max anchor positions reached: {current_anchor_count}")
                return None
            
            # วิเคราะห์ความจำเป็น
            anchor_needs = []
            
            # 1. Emergency Anchor (พอร์ตขาดทุนหนัก)
            if portfolio_profit <= self.emergency_anchor_trigger:
                emergency_anchor = self._analyze_emergency_anchor(current_price, zones, existing_positions)
                if emergency_anchor:
                    anchor_needs.append(emergency_anchor)
            
            # 2. Portfolio Protection Anchor
            elif portfolio_profit <= self.portfolio_risk_threshold:
                protection_anchor = self._analyze_protection_anchor(current_price, zones, existing_positions)
                if protection_anchor:
                    anchor_needs.append(protection_anchor)
            
            # 3. Strategic Anchor (ตาม Zone แข็งแรง)
            strategic_anchor = self._analyze_strategic_anchor(current_price, zones, existing_positions)
            if strategic_anchor:
                anchor_needs.append(strategic_anchor)
            
            # เลือก Anchor ที่ดีที่สุด
            if anchor_needs:
                best_anchor = max(anchor_needs, key=lambda x: x['priority_score'])
                logger.info(f"⚓ Best anchor opportunity: {best_anchor['direction']} at {current_price} "
                           f"(Reason: {best_anchor['reason']}, Score: {best_anchor['priority_score']})")
                return best_anchor
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error analyzing anchor needs: {e}")
            return None
    
    def _analyze_emergency_anchor(self, current_price: float, zones: Dict[str, List[Dict]], 
                                existing_positions: List) -> Optional[Dict]:
        """🚨 วิเคราะห์ Emergency Anchor"""
        try:
            logger.warning(f"🚨 Emergency anchor analysis triggered (Portfolio loss critical)")
            
            # หา Zone แข็งแรงที่สุดที่ใกล้ราคาปัจจุบัน
            strongest_zones = self.zone_analyzer.get_strongest_zones(zones, count=3)
            
            best_anchor = None
            best_score = 0
            
            # ตรวจสอบ Support Zones (Buy Anchor)
            for zone in strongest_zones.get('support', []):
                distance = current_price - zone['price']
                if 10 <= distance <= 100:  # ราคาเหนือ Support 10-100 points
                    score = zone['strength'] + (100 - distance) * 0.5  # ใกล้ = ดีกว่า
                    if score > best_score:
                        best_score = score
                        best_anchor = {
                            'direction': 'buy',
                            'zone': zone,
                            'lot_size': self.anchor_lot_size * 1.5,  # Emergency = lot ใหญ่กว่า
                            'reason': 'Emergency Support Anchor',
                            'priority_score': score + 50,  # Emergency bonus
                            'anchor_type': 'emergency'
                        }
            
            # ตรวจสอบ Resistance Zones (Sell Anchor)
            for zone in strongest_zones.get('resistance', []):
                distance = zone['price'] - current_price
                if 10 <= distance <= 100:  # ราคาใต้ Resistance 10-100 points
                    score = zone['strength'] + (100 - distance) * 0.5
                    if score > best_score:
                        best_score = score
                        best_anchor = {
                            'direction': 'sell',
                            'zone': zone,
                            'lot_size': self.anchor_lot_size * 1.5,
                            'reason': 'Emergency Resistance Anchor',
                            'priority_score': score + 50,
                            'anchor_type': 'emergency'
                        }
            
            return best_anchor
            
        except Exception as e:
            logger.error(f"❌ Error analyzing emergency anchor: {e}")
            return None
    
    def _analyze_protection_anchor(self, current_price: float, zones: Dict[str, List[Dict]], 
                                 existing_positions: List) -> Optional[Dict]:
        """🛡️ วิเคราะห์ Protection Anchor"""
        try:
            # วิเคราะห์ bias ของพอร์ตปัจจุบัน
            portfolio_bias = self._analyze_portfolio_bias(existing_positions)
            
            # หา Zone ที่เหมาะสมสำหรับ counter-balance
            suitable_zones = []
            
            if portfolio_bias == 'bullish':
                # พอร์ต bias Buy -> ต้อง Sell Anchor
                for zone in zones.get('resistance', []):
                    distance = zone['price'] - current_price
                    if 5 <= distance <= 50 and zone['strength'] >= 60:
                        suitable_zones.append({
                            'direction': 'sell',
                            'zone': zone,
                            'distance': distance,
                            'score': zone['strength'] + (50 - distance)
                        })
            
            elif portfolio_bias == 'bearish':
                # พอร์ต bias Sell -> ต้อง Buy Anchor
                for zone in zones.get('support', []):
                    distance = current_price - zone['price']
                    if 5 <= distance <= 50 and zone['strength'] >= 60:
                        suitable_zones.append({
                            'direction': 'buy',
                            'zone': zone,
                            'distance': distance,
                            'score': zone['strength'] + (50 - distance)
                        })
            
            # เลือก Zone ที่ดีที่สุด
            if suitable_zones:
                best_zone = max(suitable_zones, key=lambda x: x['score'])
                return {
                    'direction': best_zone['direction'],
                    'zone': best_zone['zone'],
                    'lot_size': self.anchor_lot_size,
                    'reason': f'Portfolio Protection ({portfolio_bias} bias)',
                    'priority_score': best_zone['score'] + 30,  # Protection bonus
                    'anchor_type': 'protection'
                }
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error analyzing protection anchor: {e}")
            return None
    
    def _analyze_strategic_anchor(self, current_price: float, zones: Dict[str, List[Dict]], 
                                existing_positions: List) -> Optional[Dict]:
        """🎯 วิเคราะห์ Strategic Anchor"""
        try:
            # หา Zone แข็งแรงที่สุดที่ไม่มี anchor อยู่แล้ว
            strongest_zones = self.zone_analyzer.get_strongest_zones(zones, count=5)
            
            candidate_anchors = []
            
            # ตรวจสอบ Support Zones
            if self.support_anchor_enabled:
                for zone in strongest_zones.get('support', []):
                    if not self._has_anchor_near_price(zone['price']):
                        distance = current_price - zone['price']
                        if 20 <= distance <= 80 and zone['strength'] >= 70:
                            candidate_anchors.append({
                                'direction': 'buy',
                                'zone': zone,
                                'distance': distance,
                                'score': zone['strength']
                            })
            
            # ตรวจสอบ Resistance Zones
            if self.resistance_anchor_enabled:
                for zone in strongest_zones.get('resistance', []):
                    if not self._has_anchor_near_price(zone['price']):
                        distance = zone['price'] - current_price
                        if 20 <= distance <= 80 and zone['strength'] >= 70:
                            candidate_anchors.append({
                                'direction': 'sell',
                                'zone': zone,
                                'distance': distance,
                                'score': zone['strength']
                            })
            
            # เลือกตัวที่ดีที่สุด
            if candidate_anchors:
                best_candidate = max(candidate_anchors, key=lambda x: x['score'])
                return {
                    'direction': best_candidate['direction'],
                    'zone': best_candidate['zone'],
                    'lot_size': self.anchor_lot_size,
                    'reason': f'Strategic Anchor at strong {best_candidate["zone"]["type"]}',
                    'priority_score': best_candidate['score'],
                    'anchor_type': 'strategic'
                }
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error analyzing strategic anchor: {e}")
            return None
    
    def _analyze_portfolio_bias(self, positions: List) -> str:
        """📊 วิเคราะห์ bias ของพอร์ต"""
        try:
            if not positions:
                return 'neutral'
            
            buy_volume = sum(pos.volume for pos in positions if pos.type == mt5.ORDER_TYPE_BUY)
            sell_volume = sum(pos.volume for pos in positions if pos.type == mt5.ORDER_TYPE_SELL)
            
            total_volume = buy_volume + sell_volume
            if total_volume == 0:
                return 'neutral'
            
            buy_ratio = buy_volume / total_volume
            
            if buy_ratio > 0.6:
                return 'bullish'
            elif buy_ratio < 0.4:
                return 'bearish'
            else:
                return 'neutral'
                
        except Exception as e:
            logger.error(f"❌ Error analyzing portfolio bias: {e}")
            return 'neutral'
    
    def _has_anchor_near_price(self, price: float) -> bool:
        """🔍 ตรวจสอบว่ามี anchor ใกล้ราคานี้หรือไม่"""
        try:
            for ticket, anchor_info in self.anchor_positions.items():
                anchor_price = anchor_info.get('entry_price', 0)
                if abs(anchor_price - price) < self.min_anchor_distance:
                    return True
            return False
        except Exception as e:
            logger.error(f"❌ Error checking anchor near price: {e}")
            return False
    
    def execute_anchor(self, anchor_plan: Dict, current_price: float) -> Optional[int]:
        """⚓ ดำเนินการสร้าง Anchor Position"""
        try:
            if not anchor_plan:
                return None
            
            direction = anchor_plan['direction']
            lot_size = anchor_plan['lot_size']
            
            # กำหนด order type
            if direction == 'buy':
                order_type = mt5.ORDER_TYPE_BUY
            else:
                order_type = mt5.ORDER_TYPE_SELL
            
            # สร้าง request
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": lot_size,
                "type": order_type,
                "comment": f"Anchor: {anchor_plan['reason']}",
                "type_time": mt5.ORDER_TIME_GTC,
                "magic": 789012  # Magic number แยกจาก Smart Entry
            }
            
            # ส่ง order
            result = mt5.order_send(request)
            
            if result is None:
                logger.error(f"❌ Anchor creation failed: MT5 order_send returned None")
                return None
            
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                ticket = result.order
                
                # บันทึกข้อมูล anchor
                self.anchor_positions[ticket] = {
                    'entry_price': current_price,
                    'entry_time': datetime.now().timestamp(),
                    'direction': direction,
                    'lot_size': lot_size,
                    'anchor_type': anchor_plan['anchor_type'],
                    'zone_price': anchor_plan['zone']['price'],
                    'reason': anchor_plan['reason']
                }
                
                logger.info(f"⚓ Anchor created: {direction.upper()} {lot_size} lots at {current_price} "
                           f"(Ticket: {ticket}, Type: {anchor_plan['anchor_type']})")
                
                return ticket
            else:
                logger.error(f"❌ Anchor creation failed: {getattr(result, 'comment', 'Unknown error')} (Code: {getattr(result, 'retcode', 'Unknown')})")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error executing anchor: {e}")
            return None
    
    def manage_existing_anchors(self, current_price: float) -> List[Dict]:
        """🔧 จัดการ Anchor Positions ที่มีอยู่"""
        try:
            management_actions = []
            
            for ticket, anchor_info in list(self.anchor_positions.items()):
                # ตรวจสอบว่า position ยังอยู่หรือไม่
                position = mt5.positions_get(ticket=ticket)
                if not position:
                    # Position ถูกปิดแล้ว
                    del self.anchor_positions[ticket]
                    logger.info(f"⚓ Anchor {ticket} removed (position closed)")
                    continue
                
                position = position[0]
                current_profit = position.profit
                
                # ตรวจสอบเงื่อนไขปิด
                close_reason = self._should_close_anchor(anchor_info, current_profit, current_price)
                if close_reason:
                    management_actions.append({
                        'action': 'close',
                        'ticket': ticket,
                        'reason': close_reason,
                        'current_profit': current_profit
                    })
            
            return management_actions
            
        except Exception as e:
            logger.error(f"❌ Error managing existing anchors: {e}")
            return []
    
    def _should_close_anchor(self, anchor_info: Dict, current_profit: float, current_price: float) -> Optional[str]:
        """🤔 ตรวจสอบว่าควรปิด Anchor หรือไม่"""
        try:
            # 1. ตรวจสอบกำไร
            if current_profit >= self.anchor_profit_target:
                return f"Profit target reached: ${current_profit:.2f}"
            
            # 2. ตรวจสอบอายุ
            current_time = datetime.now().timestamp()
            age_hours = (current_time - anchor_info['entry_time']) / 3600
            if age_hours >= self.max_anchor_age_hours:
                return f"Max age reached: {age_hours:.1f} hours"
            
            # 3. ตรวจสอบระยะห่างจาก Zone (สำหรับ Strategic Anchor)
            if anchor_info.get('anchor_type') == 'strategic':
                zone_price = anchor_info.get('zone_price', 0)
                distance = abs(current_price - zone_price)
                if distance > 100:  # ห่างจาก zone มากเกินไป
                    return f"Too far from zone: {distance:.1f} points"
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error checking anchor close conditions: {e}")
            return None
    
    def close_anchor(self, ticket: int, reason: str) -> bool:
        """🔒 ปิด Anchor Position"""
        try:
            # ดึงข้อมูล position
            position = mt5.positions_get(ticket=ticket)
            if not position:
                logger.warning(f"⚠️ Anchor position {ticket} not found")
                return False
            
            position = position[0]
            
            # กำหนด order type สำหรับปิด
            if position.type == mt5.ORDER_TYPE_BUY:
                close_type = mt5.ORDER_TYPE_SELL
            else:
                close_type = mt5.ORDER_TYPE_BUY
            
            # สร้าง request
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": position.symbol,
                "volume": position.volume,
                "type": close_type,
                "position": ticket,
                "comment": f"Anchor Close: {reason}",
                "type_time": mt5.ORDER_TIME_GTC,
                "magic": position.magic
            }
            
            # ส่ง order
            result = mt5.order_send(request)
            
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                # ลบจาก tracking
                if ticket in self.anchor_positions:
                    del self.anchor_positions[ticket]
                
                logger.info(f"🔒 Anchor closed: {ticket} (Reason: {reason}, Profit: ${position.profit:.2f})")
                return True
            else:
                logger.error(f"❌ Failed to close anchor {ticket}: {result.comment}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error closing anchor: {e}")
            return False
    
    def _cleanup_old_anchors(self) -> None:
        """🧹 ทำความสะอาด anchor positions เก่า"""
        try:
            current_time = datetime.now().timestamp()
            max_age_seconds = self.max_anchor_age_hours * 3600
            
            expired_anchors = []
            for ticket, anchor_info in self.anchor_positions.items():
                age_seconds = current_time - anchor_info['entry_time']
                if age_seconds > max_age_seconds:
                    expired_anchors.append(ticket)
            
            for ticket in expired_anchors:
                del self.anchor_positions[ticket]
                logger.debug(f"🧹 Removed expired anchor tracking: {ticket}")
                
        except Exception as e:
            logger.error(f"❌ Error cleaning old anchors: {e}")
    
    def get_anchor_statistics(self) -> Dict:
        """📊 สถิติ Anchor Positions"""
        try:
            active_anchors = len(self.anchor_positions)
            
            anchor_types = {}
            total_age_hours = 0
            
            for anchor_info in self.anchor_positions.values():
                anchor_type = anchor_info.get('anchor_type', 'unknown')
                anchor_types[anchor_type] = anchor_types.get(anchor_type, 0) + 1
                
                age_hours = (datetime.now().timestamp() - anchor_info['entry_time']) / 3600
                total_age_hours += age_hours
            
            avg_age_hours = total_age_hours / active_anchors if active_anchors > 0 else 0
            
            return {
                'active_anchors': active_anchors,
                'max_anchors': self.max_anchor_positions,
                'anchor_types': anchor_types,
                'average_age_hours': round(avg_age_hours, 1),
                'remaining_slots': self.max_anchor_positions - active_anchors
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting anchor statistics: {e}")
            return {}
    
    def update_settings(self, settings: Dict) -> None:
        """⚙️ อัปเดตการตั้งค่า"""
        try:
            if 'max_anchor_positions' in settings:
                self.max_anchor_positions = settings['max_anchor_positions']
            
            if 'anchor_lot_size' in settings:
                self.anchor_lot_size = settings['anchor_lot_size']
            
            if 'portfolio_risk_threshold' in settings:
                self.portfolio_risk_threshold = settings['portfolio_risk_threshold']
            
            if 'anchor_profit_target' in settings:
                self.anchor_profit_target = settings['anchor_profit_target']
            
            logger.info(f"⚙️ Portfolio Anchor settings updated: {settings}")
            
        except Exception as e:
            logger.error(f"❌ Error updating settings: {e}")
