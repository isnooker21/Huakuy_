# -*- coding: utf-8 -*-
"""
Real Time Tracker
ตัวหลักในการติดตามการเปลี่ยนแปลงแบบ Real-time
"""

import logging
import time
import asyncio
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import threading
from queue import Queue

logger = logging.getLogger(__name__)

@dataclass
class PriceChange:
    """ข้อมูลการเปลี่ยนแปลงราคา"""
    symbol: str
    old_price: float
    new_price: float
    change_pips: float
    timestamp: float
    change_percent: float

@dataclass
class PositionChange:
    """ข้อมูลการเปลี่ยนแปลง Position"""
    ticket: int
    change_type: str  # 'opened', 'closed', 'modified'
    old_profit: float
    new_profit: float
    timestamp: float
    details: Dict[str, Any]

@dataclass
class AlertThreshold:
    """เกณฑ์การแจ้งเตือน"""
    price_change: float = 10.0      # 10 pips
    profit_change: float = 20.0     # $20
    new_position: bool = True
    position_closed: bool = True
    status_change: bool = True

class RealTimeTracker:
    """ตัวหลักในการติดตาม Real-time Changes"""
    
    def __init__(self, trading_system):
        self.trading_system = trading_system
        self.price_monitors = {}
        self.position_monitors = {}
        self.alert_thresholds = AlertThreshold()
        
        # 🎯 Real-time Status Tracking
        self.status_tracker = None
        self.last_price = 0.0
        self.last_update = 0.0
        self.update_threshold = 3.0  # 3 วินาที
        self.price_change_threshold = 5.0  # 5 pips
        
        # 📊 Monitoring Data
        self.price_history = {}
        self.position_history = {}
        self.status_history = {}
        self.max_history_size = 100
        
        # 🔄 Threading
        self.monitoring_thread = None
        self.stop_monitoring = False
        self.update_queue = Queue()
        
        # 📈 Performance Metrics
        self.update_count = 0
        self.last_performance_check = 0
        self.performance_metrics = {
            'avg_update_time': 0.0,
            'updates_per_second': 0.0,
            'memory_usage': 0.0
        }
        
        # 🎯 Callbacks
        self.status_change_callbacks = []
        self.price_change_callbacks = []
        self.position_change_callbacks = []
        
    def start_monitoring(self):
        """เริ่มการติดตาม Real-time"""
        try:
            if self.monitoring_thread and self.monitoring_thread.is_alive():
                logger.warning("⚠️ [MONITORING] Already running")
                return
            
            self.stop_monitoring = False
            self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
            self.monitoring_thread.start()
            
            logger.info("🚀 [MONITORING] Started real-time tracking")
            
        except Exception as e:
            logger.error(f"❌ Error starting monitoring: {e}")
    
    def stop_monitoring(self):
        """หยุดการติดตาม Real-time"""
        try:
            self.stop_monitoring = True
            if self.monitoring_thread:
                self.monitoring_thread.join(timeout=5.0)
            
            logger.info("🛑 [MONITORING] Stopped real-time tracking")
            
        except Exception as e:
            logger.error(f"❌ Error stopping monitoring: {e}")
    
    def _monitoring_loop(self):
        """Loop หลักในการติดตาม"""
        try:
            while not self.stop_monitoring:
                current_time = time.time()
                
                # ตรวจสอบการเปลี่ยนแปลงราคา
                self._check_price_changes()
                
                # ตรวจสอบการเปลี่ยนแปลง Position
                self._check_position_changes()
                
                # ตรวจสอบการเปลี่ยนแปลงสถานะ
                self._check_status_changes()
                
                # อัพเดท Performance Metrics
                self._update_performance_metrics()
                
                # รอสักครู่ก่อนตรวจสอบครั้งต่อไป
                time.sleep(0.5)  # ตรวจสอบทุก 0.5 วินาที
                
        except Exception as e:
            logger.error(f"❌ Error in monitoring loop: {e}")
    
    def _check_price_changes(self):
        """ตรวจสอบการเปลี่ยนแปลงราคา"""
        try:
            if not hasattr(self.trading_system, 'mt5_connection'):
                return
            
            # ดึงราคาปัจจุบัน
            current_price = self._get_current_price()
            if current_price == 0:
                return
            
            current_time = time.time()
            
            # ตรวจสอบว่าต้องอัพเดทหรือไม่
            if self._should_update_price(current_price, current_time):
                self._update_price_tracking(current_price, current_time)
                
        except Exception as e:
            logger.error(f"❌ Error checking price changes: {e}")
    
    def _check_position_changes(self):
        """ตรวจสอบการเปลี่ยนแปลง Position"""
        try:
            if not hasattr(self.trading_system, 'order_manager'):
                return
            
            # ดึง Position ปัจจุบัน
            current_positions = self._get_current_positions()
            if not current_positions:
                return
            
            current_time = time.time()
            
            # เปรียบเทียบกับ Position เก่า
            self._compare_positions(current_positions, current_time)
            
        except Exception as e:
            logger.error(f"❌ Error checking position changes: {e}")
    
    def _check_status_changes(self):
        """ตรวจสอบการเปลี่ยนแปลงสถานะ"""
        try:
            if not hasattr(self.trading_system, 'status_manager'):
                return
            
            # ดึงสถานะปัจจุบัน
            current_statuses = self.trading_system.status_manager.get_all_statuses()
            if not current_statuses:
                return
            
            current_time = time.time()
            
            # เปรียบเทียบกับสถานะเก่า
            self._compare_statuses(current_statuses, current_time)
            
        except Exception as e:
            logger.error(f"❌ Error checking status changes: {e}")
    
    def _should_update_price(self, current_price: float, current_time: float) -> bool:
        """ตรวจสอบว่าควรอัพเดทราคาหรือไม่"""
        try:
            # ตรวจสอบการเปลี่ยนแปลงราคา
            if self.last_price > 0:
                price_change = abs(current_price - self.last_price)
                price_change_pips = price_change * 10000  # แปลงเป็น pips
                
                if price_change_pips >= self.price_change_threshold:
                    logger.debug(f"💰 [PRICE CHANGE] {price_change_pips:.1f} pips")
                    return True
            
            # ตรวจสอบเวลาที่ผ่านไป
            time_passed = current_time - self.last_update
            if time_passed >= self.update_threshold:
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Error checking price update: {e}")
            return False
    
    def _update_price_tracking(self, current_price: float, current_time: float):
        """อัพเดทการติดตามราคา"""
        try:
            # เก็บประวัติราคา
            self._store_price_history(current_price, current_time)
            
            # อัพเดทข้อมูล
            self.last_price = current_price
            self.last_update = current_time
            
            # เรียก Callbacks
            self._trigger_price_change_callbacks(current_price, current_time)
            
            # อัพเดท Status Tracker
            if self.status_tracker:
                self.status_tracker.last_price = current_price
                self.status_tracker.last_update = current_time
            
        except Exception as e:
            logger.error(f"❌ Error updating price tracking: {e}")
    
    def _store_price_history(self, price: float, timestamp: float):
        """เก็บประวัติราคา"""
        try:
            self.price_history[timestamp] = price
            
            # จำกัดขนาดประวัติ
            if len(self.price_history) > self.max_history_size:
                oldest_key = min(self.price_history.keys())
                del self.price_history[oldest_key]
                
        except Exception as e:
            logger.error(f"❌ Error storing price history: {e}")
    
    def _compare_positions(self, current_positions: List[Any], current_time: float):
        """เปรียบเทียบ Position เก่าและใหม่"""
        try:
            # สร้าง Dictionary ของ Position ปัจจุบัน
            current_pos_dict = {
                getattr(pos, 'ticket', 0): {
                    'ticket': getattr(pos, 'ticket', 0),
                    'profit': getattr(pos, 'profit', 0.0),
                    'volume': getattr(pos, 'volume', 0.0),
                    'type': getattr(pos, 'type', 0),
                    'price_open': getattr(pos, 'price_open', 0.0),
                    'price_current': getattr(pos, 'price_current', 0.0)
                }
                for pos in current_positions
            }
            
            # เปรียบเทียบกับ Position เก่า
            old_positions = self.position_history.get('last_positions', {})
            
            # ตรวจสอบ Position ใหม่
            new_tickets = set(current_pos_dict.keys()) - set(old_positions.keys())
            for ticket in new_tickets:
                self._handle_position_opened(current_pos_dict[ticket], current_time)
            
            # ตรวจสอบ Position ที่ปิด
            closed_tickets = set(old_positions.keys()) - set(current_pos_dict.keys())
            for ticket in closed_tickets:
                self._handle_position_closed(ticket, old_positions[ticket], current_time)
            
            # ตรวจสอบ Position ที่เปลี่ยนแปลง
            for ticket, current_pos in current_pos_dict.items():
                if ticket in old_positions:
                    old_pos = old_positions[ticket]
                    if self._position_changed(old_pos, current_pos):
                        self._handle_position_modified(old_pos, current_pos, current_time)
            
            # อัพเดทประวัติ
            self.position_history['last_positions'] = current_pos_dict
            
        except Exception as e:
            logger.error(f"❌ Error comparing positions: {e}")
    
    def _compare_statuses(self, current_statuses: Dict[int, Any], current_time: float):
        """เปรียบเทียบสถานะเก่าและใหม่"""
        try:
            old_statuses = self.status_history.get('last_statuses', {})
            
            for ticket, current_status in current_statuses.items():
                if ticket in old_statuses:
                    old_status = old_statuses[ticket]
                    if old_status.status != current_status.status:
                        self._handle_status_changed(ticket, old_status, current_status, current_time)
            
            # อัพเดทประวัติ
            self.status_history['last_statuses'] = current_statuses
            
        except Exception as e:
            logger.error(f"❌ Error comparing statuses: {e}")
    
    def _position_changed(self, old_pos: Dict, new_pos: Dict) -> bool:
        """ตรวจสอบว่า Position เปลี่ยนแปลงหรือไม่"""
        try:
            # ตรวจสอบการเปลี่ยนแปลงที่สำคัญ
            profit_change = abs(new_pos['profit'] - old_pos['profit'])
            price_change = abs(new_pos['price_current'] - old_pos['price_current'])
            
            return (profit_change >= self.alert_thresholds.profit_change or 
                   price_change >= 0.001)  # 0.1 pips
            
        except Exception as e:
            logger.error(f"❌ Error checking position change: {e}")
            return False
    
    def _handle_position_opened(self, position: Dict, timestamp: float):
        """จัดการ Position ใหม่"""
        try:
            logger.info(f"🆕 [POSITION OPENED] #{position['ticket']} - "
                       f"Profit: ${position['profit']:.2f}")
            
            # เรียก Callbacks
            self._trigger_position_change_callbacks('opened', position, timestamp)
            
        except Exception as e:
            logger.error(f"❌ Error handling position opened: {e}")
    
    def _handle_position_closed(self, ticket: int, old_position: Dict, timestamp: float):
        """จัดการ Position ที่ปิด"""
        try:
            logger.info(f"🔚 [POSITION CLOSED] #{ticket} - "
                       f"Final Profit: ${old_position['profit']:.2f}")
            
            # เรียก Callbacks
            self._trigger_position_change_callbacks('closed', {'ticket': ticket}, timestamp)
            
        except Exception as e:
            logger.error(f"❌ Error handling position closed: {e}")
    
    def _handle_position_modified(self, old_position: Dict, new_position: Dict, timestamp: float):
        """จัดการ Position ที่เปลี่ยนแปลง"""
        try:
            profit_change = new_position['profit'] - old_position['profit']
            
            if abs(profit_change) >= self.alert_thresholds.profit_change:
                logger.info(f"📊 [POSITION MODIFIED] #{new_position['ticket']} - "
                           f"Profit Change: ${profit_change:.2f}")
                
                # เรียก Callbacks
                self._trigger_position_change_callbacks('modified', new_position, timestamp)
                
        except Exception as e:
            logger.error(f"❌ Error handling position modified: {e}")
    
    def _handle_status_changed(self, ticket: int, old_status: Any, new_status: Any, timestamp: float):
        """จัดการการเปลี่ยนแปลงสถานะ"""
        try:
            logger.info(f"🔄 [STATUS CHANGED] #{ticket} - "
                       f"From: {old_status.status} To: {new_status.status}")
            
            # เรียก Callbacks
            self._trigger_status_change_callbacks(ticket, old_status, new_status, timestamp)
            
        except Exception as e:
            logger.error(f"❌ Error handling status changed: {e}")
    
    def _get_current_price(self) -> float:
        """ดึงราคาปัจจุบัน"""
        try:
            if hasattr(self.trading_system, 'mt5_connection'):
                symbol = getattr(self.trading_system, 'actual_symbol', 'XAUUSD')
                tick = self.trading_system.mt5_connection.get_current_tick(symbol)
                if tick:
                    return (tick['bid'] + tick['ask']) / 2
            return 0.0
            
        except Exception as e:
            logger.error(f"❌ Error getting current price: {e}")
            return 0.0
    
    def _get_current_positions(self) -> List[Any]:
        """ดึง Position ปัจจุบัน"""
        try:
            if hasattr(self.trading_system, 'order_manager'):
                return self.trading_system.order_manager.get_positions()
            return []
            
        except Exception as e:
            logger.error(f"❌ Error getting current positions: {e}")
            return []
    
    def _trigger_price_change_callbacks(self, price: float, timestamp: float):
        """เรียก Price Change Callbacks"""
        try:
            for callback in self.price_change_callbacks:
                try:
                    callback(price, timestamp)
                except Exception as e:
                    logger.error(f"❌ Error in price change callback: {e}")
                    
        except Exception as e:
            logger.error(f"❌ Error triggering price change callbacks: {e}")
    
    def _trigger_position_change_callbacks(self, change_type: str, position: Dict, timestamp: float):
        """เรียก Position Change Callbacks"""
        try:
            for callback in self.position_change_callbacks:
                try:
                    callback(change_type, position, timestamp)
                except Exception as e:
                    logger.error(f"❌ Error in position change callback: {e}")
                    
        except Exception as e:
            logger.error(f"❌ Error triggering position change callbacks: {e}")
    
    def _trigger_status_change_callbacks(self, ticket: int, old_status: Any, new_status: Any, timestamp: float):
        """เรียก Status Change Callbacks"""
        try:
            for callback in self.status_change_callbacks:
                try:
                    callback(ticket, old_status, new_status, timestamp)
                except Exception as e:
                    logger.error(f"❌ Error in status change callback: {e}")
                    
        except Exception as e:
            logger.error(f"❌ Error triggering status change callbacks: {e}")
    
    def _update_performance_metrics(self):
        """อัพเดท Performance Metrics"""
        try:
            current_time = time.time()
            
            if current_time - self.last_performance_check >= 60:  # ทุก 1 นาที
                self.update_count += 1
                
                # คำนวณ Updates per Second
                time_elapsed = current_time - self.last_performance_check
                self.performance_metrics['updates_per_second'] = self.update_count / time_elapsed
                
                # Reset counters
                self.update_count = 0
                self.last_performance_check = current_time
                
                # Log Performance
                logger.debug(f"📈 [PERFORMANCE] Updates/sec: {self.performance_metrics['updates_per_second']:.2f}")
                
        except Exception as e:
            logger.error(f"❌ Error updating performance metrics: {e}")
    
    # 🎯 Callback Management
    def add_price_change_callback(self, callback: Callable):
        """เพิ่ม Price Change Callback"""
        self.price_change_callbacks.append(callback)
    
    def add_position_change_callback(self, callback: Callable):
        """เพิ่ม Position Change Callback"""
        self.position_change_callbacks.append(callback)
    
    def add_status_change_callback(self, callback: Callable):
        """เพิ่ม Status Change Callback"""
        self.status_change_callbacks.append(callback)
    
    def remove_callback(self, callback: Callable):
        """ลบ Callback"""
        if callback in self.price_change_callbacks:
            self.price_change_callbacks.remove(callback)
        if callback in self.position_change_callbacks:
            self.position_change_callbacks.remove(callback)
        if callback in self.status_change_callbacks:
            self.status_change_callbacks.remove(callback)
    
    # 🎯 Configuration
    def set_update_threshold(self, threshold: float):
        """ตั้งค่า Update Threshold"""
        self.update_threshold = threshold
        logger.info(f"🔧 [CONFIG] Update threshold set to {threshold} seconds")
    
    def set_price_change_threshold(self, threshold: float):
        """ตั้งค่า Price Change Threshold"""
        self.price_change_threshold = threshold
        logger.info(f"🔧 [CONFIG] Price change threshold set to {threshold} pips")
    
    def set_alert_thresholds(self, thresholds: AlertThreshold):
        """ตั้งค่า Alert Thresholds"""
        self.alert_thresholds = thresholds
        logger.info(f"🔧 [CONFIG] Alert thresholds updated")
    
    # 🎯 Status Methods
    def is_monitoring(self) -> bool:
        """ตรวจสอบว่ากำลังติดตามอยู่หรือไม่"""
        return self.monitoring_thread and self.monitoring_thread.is_alive() and not self.stop_monitoring
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """ดึง Performance Metrics"""
        return self.performance_metrics.copy()
    
    def get_price_history(self, limit: int = 50) -> Dict[float, float]:
        """ดึงประวัติราคา"""
        try:
            sorted_history = sorted(self.price_history.items(), reverse=True)
            return dict(sorted_history[:limit])
        except Exception as e:
            logger.error(f"❌ Error getting price history: {e}")
            return {}
    
    def clear_history(self):
        """ล้างประวัติ"""
        self.price_history.clear()
        self.position_history.clear()
        self.status_history.clear()
        logger.info("🧹 [HISTORY] Cleared all history")
    
    # 🚀 ORDER TRACKING & MANAGEMENT FUNCTIONS
    
    def track_order(self, order_data: Dict[str, Any]) -> bool:
        """ติดตาม Order ใหม่"""
        try:
            ticket = order_data.get('ticket', 0)
            if not ticket:
                logger.error("❌ [ORDER TRACK] No ticket provided")
                return False
            
            # เก็บข้อมูล Order สำหรับติดตาม
            if not hasattr(self, 'tracked_orders'):
                self.tracked_orders = {}
            
            self.tracked_orders[ticket] = {
                'ticket': ticket,
                'symbol': order_data.get('symbol', 'UNKNOWN'),
                'type': order_data.get('type', 'MARKET'),
                'direction': order_data.get('direction', 'BUY'),
                'volume': order_data.get('volume', 0.0),
                'price': order_data.get('price', 0.0),
                'sl': order_data.get('sl', 0.0),
                'tp': order_data.get('tp', 0.0),
                'comment': order_data.get('comment', ''),
                'magic': order_data.get('magic', 0),
                'status': 'PENDING',
                'created_time': time.time(),
                'last_update': time.time(),
                'retry_count': 0,
                'max_retries': 3
            }
            
            logger.info(f"📝 [ORDER TRACK] Tracking order {ticket}: {order_data.get('direction', 'BUY')} {order_data.get('symbol', 'UNKNOWN')} {order_data.get('volume', 0.0)}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error tracking order: {e}")
            return False
    
    def close_order(self, ticket: int, reason: str = "") -> bool:
        """ปิด Order ตาม Ticket"""
        try:
            if not hasattr(self, 'tracked_orders') or ticket not in self.tracked_orders:
                logger.warning(f"⚠️ [ORDER CLOSE] Order {ticket} not tracked")
                return False
            
            # ใช้ OrderManager ปิด Position
            if hasattr(self.trading_system, 'order_manager'):
                # ดึงข้อมูล Position จาก OrderManager
                positions = self.trading_system.order_manager.get_positions()
                target_position = None
                
                for pos in positions:
                    if hasattr(pos, 'ticket') and pos.ticket == ticket:
                        target_position = pos
                        break
                
                if target_position:
                    # ใช้ close_positions_group เพื่อปิดออเดอร์
                    result = self.trading_system.order_manager.close_positions_group([target_position], reason)
                    
                    if result.success:
                        logger.info(f"✅ [ORDER CLOSE] Successfully closed order {ticket}: {reason} - Profit: ${result.total_profit:.2f}")
                        
                        # อัพเดทสถานะ
                        self.tracked_orders[ticket]['status'] = 'CLOSED'
                        self.tracked_orders[ticket]['last_update'] = time.time()
                        
                        return True
                    else:
                        logger.error(f"❌ [ORDER CLOSE] Failed to close order {ticket}: {result.error_message}")
                        return False
                else:
                    logger.error(f"❌ [ORDER CLOSE] Position {ticket} not found in OrderManager")
                    return False
            else:
                logger.error("❌ [ORDER CLOSE] OrderManager not available")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error closing order {ticket}: {e}")
            return False
    
    def close_orders_by_status(self, status: str, reason: str = "") -> Dict[str, Any]:
        """ปิด Order ตามสถานะ"""
        try:
            if not hasattr(self, 'tracked_orders'):
                return {'success': False, 'message': 'No tracked orders'}
            
            orders_to_close = []
            for ticket, order in self.tracked_orders.items():
                if order.get('status') == status:
                    orders_to_close.append(ticket)
            
            if not orders_to_close:
                return {'success': True, 'message': f'No orders with status {status} found', 'closed_count': 0}
            
            # ใช้ OrderManager ปิดหลาย Order
            if hasattr(self.trading_system, 'order_manager'):
                # ดึงข้อมูล Position จาก OrderManager
                positions = self.trading_system.order_manager.get_positions()
                target_positions = []
                
                for pos in positions:
                    if hasattr(pos, 'ticket') and pos.ticket in orders_to_close:
                        target_positions.append(pos)
                
                if target_positions:
                    result = self.trading_system.order_manager.close_positions_group(target_positions, reason)
                    
                    if result.success:
                        # อัพเดทสถานะ
                        for ticket in orders_to_close:
                            if ticket in self.tracked_orders:
                                self.tracked_orders[ticket]['status'] = 'CLOSED'
                                self.tracked_orders[ticket]['last_update'] = time.time()
                        
                        logger.info(f"✅ [ORDER CLOSE] Successfully closed {len(orders_to_close)} orders with status {status} - Profit: ${result.total_profit:.2f}")
                        return {
                            'success': True, 
                            'message': f'Closed {len(orders_to_close)} orders',
                            'closed_count': len(orders_to_close),
                            'closed_tickets': orders_to_close,
                            'total_profit': result.total_profit
                        }
                    else:
                        logger.error(f"❌ [ORDER CLOSE] Failed to close orders: {result.error_message}")
                        return {'success': False, 'message': result.error_message}
                else:
                    logger.error(f"❌ [ORDER CLOSE] No matching positions found for orders with status {status}")
                    return {'success': False, 'message': f'No matching positions found for orders with status {status}'}
            else:
                logger.error("❌ [ORDER CLOSE] OrderManager not available")
                return {'success': False, 'message': 'OrderManager not available'}
                
        except Exception as e:
            logger.error(f"❌ Error closing orders by status: {e}")
            return {'success': False, 'message': str(e)}
    
    def close_orders_by_profit(self, min_profit: float = 0.0, max_profit: float = None, reason: str = "") -> Dict[str, Any]:
        """ปิด Order ตาม Profit"""
        try:
            if not hasattr(self, 'tracked_orders'):
                return {'success': False, 'message': 'No tracked orders'}
            
            orders_to_close = []
            current_positions = self._get_current_positions()
            
            # สร้าง mapping ของ ticket -> profit
            position_profits = {}
            for pos in current_positions:
                ticket = getattr(pos, 'ticket', 0)
                profit = getattr(pos, 'profit', 0.0)
                position_profits[ticket] = profit
            
            for ticket, order in self.tracked_orders.items():
                if order.get('status') == 'FILLED':
                    profit = position_profits.get(ticket, 0.0)
                    
                    # ตรวจสอบเงื่อนไข profit
                    if max_profit is None:
                        if profit >= min_profit:
                            orders_to_close.append(ticket)
                    else:
                        if min_profit <= profit <= max_profit:
                            orders_to_close.append(ticket)
            
            if not orders_to_close:
                return {'success': True, 'message': f'No orders matching profit criteria', 'closed_count': 0}
            
            # ใช้ OrderManager ปิดหลาย Order
            if hasattr(self.trading_system, 'order_manager'):
                # ดึงข้อมูล Position จาก OrderManager
                positions = self.trading_system.order_manager.get_positions()
                target_positions = []
                
                for pos in positions:
                    if hasattr(pos, 'ticket') and pos.ticket in orders_to_close:
                        target_positions.append(pos)
                
                if target_positions:
                    result = self.trading_system.order_manager.close_positions_group(target_positions, reason)
                    
                    if result.success:
                        # อัพเดทสถานะ
                        for ticket in orders_to_close:
                            if ticket in self.tracked_orders:
                                self.tracked_orders[ticket]['status'] = 'CLOSED'
                                self.tracked_orders[ticket]['last_update'] = time.time()
                        
                        logger.info(f"✅ [ORDER CLOSE] Successfully closed {len(orders_to_close)} orders by profit - Profit: ${result.total_profit:.2f}")
                        return {
                            'success': True, 
                            'message': f'Closed {len(orders_to_close)} orders by profit',
                            'closed_count': len(orders_to_close),
                            'closed_tickets': orders_to_close,
                            'total_profit': result.total_profit
                        }
                    else:
                        logger.error(f"❌ [ORDER CLOSE] Failed to close orders by profit: {result.error_message}")
                        return {'success': False, 'message': result.error_message}
                else:
                    logger.error(f"❌ [ORDER CLOSE] No matching positions found for profit-based orders")
                    return {'success': False, 'message': 'No matching positions found for profit-based orders'}
            else:
                logger.error("❌ [ORDER CLOSE] OrderManager not available")
                return {'success': False, 'message': 'OrderManager not available'}
                
        except Exception as e:
            logger.error(f"❌ Error closing orders by profit: {e}")
            return {'success': False, 'message': str(e)}
    
    def get_tracked_orders(self) -> Dict[int, Dict[str, Any]]:
        """ดึง Order ที่ติดตามทั้งหมด"""
        try:
            if not hasattr(self, 'tracked_orders'):
                return {}
            return self.tracked_orders.copy()
        except Exception as e:
            logger.error(f"❌ Error getting tracked orders: {e}")
            return {}
    
    def get_orders_by_status(self, status: str) -> List[Dict[str, Any]]:
        """ดึง Order ตามสถานะ"""
        try:
            if not hasattr(self, 'tracked_orders'):
                return []
            
            return [
                order for order in self.tracked_orders.values() 
                if order.get('status') == status
            ]
        except Exception as e:
            logger.error(f"❌ Error getting orders by status: {e}")
            return []
    
    def get_order_statistics(self) -> Dict[str, Any]:
        """ดึงสถิติ Order"""
        try:
            if not hasattr(self, 'tracked_orders'):
                return {
                    'total_orders': 0,
                    'pending_orders': 0,
                    'filled_orders': 0,
                    'closed_orders': 0,
                    'error_orders': 0
                }
            
            total_orders = len(self.tracked_orders)
            pending_orders = len([o for o in self.tracked_orders.values() if o.get('status') == 'PENDING'])
            filled_orders = len([o for o in self.tracked_orders.values() if o.get('status') == 'FILLED'])
            closed_orders = len([o for o in self.tracked_orders.values() if o.get('status') == 'CLOSED'])
            error_orders = len([o for o in self.tracked_orders.values() if o.get('status') == 'ERROR'])
            
            return {
                'total_orders': total_orders,
                'pending_orders': pending_orders,
                'filled_orders': filled_orders,
                'closed_orders': closed_orders,
                'error_orders': error_orders,
                'success_rate': (filled_orders / total_orders * 100) if total_orders > 0 else 0
            }
        except Exception as e:
            logger.error(f"❌ Error getting order statistics: {e}")
            return {}
    
    def update_order_status(self, ticket: int, status: str) -> bool:
        """อัพเดทสถานะ Order"""
        try:
            if not hasattr(self, 'tracked_orders') or ticket not in self.tracked_orders:
                return False
            
            old_status = self.tracked_orders[ticket].get('status')
            self.tracked_orders[ticket]['status'] = status
            self.tracked_orders[ticket]['last_update'] = time.time()
            
            if old_status != status:
                logger.info(f"🔄 [ORDER STATUS] #{ticket}: {old_status} → {status}")
            
            return True
        except Exception as e:
            logger.error(f"❌ Error updating order status: {e}")
            return False
    
    def auto_close_orders_by_condition(self, condition_func: Callable, reason: str = "Auto Close") -> Dict[str, Any]:
        """ปิดออเดอร์อัตโนมัติตามเงื่อนไขที่กำหนด"""
        try:
            if not hasattr(self, 'tracked_orders'):
                return {'success': False, 'message': 'No tracked orders'}
            
            orders_to_close = []
            current_positions = self._get_current_positions()
            
            # สร้าง mapping ของ ticket -> position
            position_map = {}
            for pos in current_positions:
                ticket = getattr(pos, 'ticket', 0)
                position_map[ticket] = pos
            
            for ticket, order in self.tracked_orders.items():
                if order.get('status') == 'FILLED' and ticket in position_map:
                    position = position_map[ticket]
                    
                    # ตรวจสอบเงื่อนไข
                    if condition_func(position, order):
                        orders_to_close.append(ticket)
            
            if not orders_to_close:
                return {'success': True, 'message': 'No orders matching condition', 'closed_count': 0}
            
            # ใช้ OrderManager ปิดหลาย Order
            if hasattr(self.trading_system, 'order_manager'):
                target_positions = [position_map[ticket] for ticket in orders_to_close if ticket in position_map]
                
                if target_positions:
                    result = self.trading_system.order_manager.close_positions_group(target_positions, reason)
                    
                    if result.success:
                        # อัพเดทสถานะ
                        for ticket in orders_to_close:
                            if ticket in self.tracked_orders:
                                self.tracked_orders[ticket]['status'] = 'CLOSED'
                                self.tracked_orders[ticket]['last_update'] = time.time()
                        
                        logger.info(f"✅ [AUTO CLOSE] Successfully closed {len(orders_to_close)} orders by condition - Profit: ${result.total_profit:.2f}")
                        return {
                            'success': True, 
                            'message': f'Closed {len(orders_to_close)} orders by condition',
                            'closed_count': len(orders_to_close),
                            'closed_tickets': orders_to_close,
                            'total_profit': result.total_profit
                        }
                    else:
                        logger.error(f"❌ [AUTO CLOSE] Failed to close orders by condition: {result.error_message}")
                        return {'success': False, 'message': result.error_message}
                else:
                    logger.error(f"❌ [AUTO CLOSE] No matching positions found for condition-based orders")
                    return {'success': False, 'message': 'No matching positions found for condition-based orders'}
            else:
                logger.error("❌ [AUTO CLOSE] OrderManager not available")
                return {'success': False, 'message': 'OrderManager not available'}
                
        except Exception as e:
            logger.error(f"❌ Error auto closing orders by condition: {e}")
            return {'success': False, 'message': str(e)}
    
    def close_orders_by_magic_number(self, magic_number: int, reason: str = "") -> Dict[str, Any]:
        """ปิดออเดอร์ตาม Magic Number"""
        try:
            if not hasattr(self, 'tracked_orders'):
                return {'success': False, 'message': 'No tracked orders'}
            
            orders_to_close = []
            for ticket, order in self.tracked_orders.items():
                if order.get('magic') == magic_number and order.get('status') == 'FILLED':
                    orders_to_close.append(ticket)
            
            if not orders_to_close:
                return {'success': True, 'message': f'No orders with magic number {magic_number} found', 'closed_count': 0}
            
            # ใช้ OrderManager ปิดหลาย Order
            if hasattr(self.trading_system, 'order_manager'):
                positions = self.trading_system.order_manager.get_positions()
                target_positions = []
                
                for pos in positions:
                    if hasattr(pos, 'ticket') and pos.ticket in orders_to_close:
                        target_positions.append(pos)
                
                if target_positions:
                    result = self.trading_system.order_manager.close_positions_group(target_positions, reason)
                    
                    if result.success:
                        # อัพเดทสถานะ
                        for ticket in orders_to_close:
                            if ticket in self.tracked_orders:
                                self.tracked_orders[ticket]['status'] = 'CLOSED'
                                self.tracked_orders[ticket]['last_update'] = time.time()
                        
                        logger.info(f"✅ [ORDER CLOSE] Successfully closed {len(orders_to_close)} orders with magic {magic_number} - Profit: ${result.total_profit:.2f}")
                        return {
                            'success': True, 
                            'message': f'Closed {len(orders_to_close)} orders with magic {magic_number}',
                            'closed_count': len(orders_to_close),
                            'closed_tickets': orders_to_close,
                            'total_profit': result.total_profit
                        }
                    else:
                        logger.error(f"❌ [ORDER CLOSE] Failed to close orders with magic {magic_number}: {result.error_message}")
                        return {'success': False, 'message': result.error_message}
                else:
                    logger.error(f"❌ [ORDER CLOSE] No matching positions found for magic {magic_number}")
                    return {'success': False, 'message': f'No matching positions found for magic {magic_number}'}
            else:
                logger.error("❌ [ORDER CLOSE] OrderManager not available")
                return {'success': False, 'message': 'OrderManager not available'}
                
        except Exception as e:
            logger.error(f"❌ Error closing orders by magic number: {e}")
            return {'success': False, 'message': str(e)}
